#!/usr/bin/env python3
"""
Theory validation: sweep tile ASPECT RATIO at fixed tile area.

Fix m*n = AREA = 256 elements, k=16.
Sweep (m,n) pairs: (4,64), (8,32), (16,16), (32,8), (64,4).

Theory (paper: Mixed Precision Tiling, ρ = B_PREC/A_PREC):
  Optimal n/m ratio = A_PREC / B_PREC = 1/ρ
  → B=8B: n/m=1  → (16,16)
  → B=4B: n/m=2  → nearest (8,32) or (16,16)
  → B=2B: n/m=4  → (8,32) exactly
  → B=1B: n/m=8  → nearest (4,64) or (8,32)

For FIFO mode: B is free (ρ→0) → widest feasible tile (lowest m) wins.
L1 constraint (C+2A ≤ L1): m(n+2k) ≤ 1024 → (4,64) and (8,32) and (16,16) pass;
  (32,8) and (64,4) violate → expect L1 thrashing for those.

Matrix: 256³, A=8B, L1=8KB (8B lines), L2=32KB (64B lines).
FIFO gen_cost=10cy, cap=64, MULAC=32cy, REG=4³.
"""

import os, subprocess, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE  = "../../asymm"
TEMP_CONFIG = "/tmp/theory_ratio.conf"
OUTPUT_DIR  = "."

MAT    = 256
A_PREC = 8
K_FIXED = 16

L1_KB  = 8
L2_KB  = 32
MULAC  = 32
FIFO_GEN_COST = 10
FIFO_CAPACITY = 64

AREA = 256  # fixed m*n product

# (m, n) pairs with fixed area=256
SHAPES = [(4, 64), (8, 32), (16, 16), (32, 8), (64, 4)]
B_PRECS = [1, 2, 4, 8]


def write_config(b_prec):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT}\nA_WIDTH_DIM={MAT}\nB_WIDTH_DIM={MAT}\n")
        f.write(f"A_PRECISION_BYTES={A_PREC}\nB_PRECISION_BYTES={b_prec}\n")
        f.write(f"L1_SIZE_BYTES={L1_KB*1024}\nL1_LINE_SIZE_BYTES=32\n")
        f.write("L1_ASSOC=4\nL1_ACCESS_CYCLES=4\n")
        f.write("L1_REPLACEMENT_POLICY=LRU\nL1_WRITE_POLICY=WRITE_BACK\n")
        f.write(f"L2_SIZE_BYTES={L2_KB*1024}\nL2_LINE_SIZE_BYTES=64\n")
        f.write("L2_ASSOC=8\nL2_ACCESS_CYCLES=15\n")
        f.write("L2_REPLACEMENT_POLICY=LRU\nL2_WRITE_POLICY=WRITE_BACK\n")
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\nPRNG_GEN_COST_PER_LINE=64\n")
        f.write(f"PRNG_FIFO_CAPACITY={FIFO_CAPACITY}\n")
        f.write(f"PRNG_FIFO_GEN_COST={FIFO_GEN_COST}\n")
        f.write("REG_M=4\nREG_N=4\nREG_K=4\n")
        f.write(f"MULAC_CYCLES={MULAC}\n")
        f.write("SP_ACCESS_CYCLES=1\nSP_BANKS=8\nSP_WORD_SIZE_BYTES=8\n")


def parse_cycles(stdout):
    for line in stdout.splitlines():
        m = re.match(r"Cycles:\s+(\d+)", line.strip())
        if m:
            return int(m.group(1))
    return None


def run(m, n, b_prec, fifo=False):
    write_config(b_prec)
    cmd = [EXECUTABLE]
    if fifo:
        cmd.append("--Bfifo")
    cmd += ["--config", TEMP_CONFIG, str(m), str(n), str(K_FIXED)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tag = "FIFO" if fifo else "mem"
        print(f"  FAIL ({m},{n}) B={b_prec}B {tag}: {r.stderr.strip()[:80]}")
        return None
    return parse_cycles(r.stdout)


L1_LINE = 32  # bytes per L1 line

def l1_ok(m, n, k=K_FIXED):
    """C+2A ≤ L1 in L1 lines (L1_LINE=32B, A_PREC=8B → 4 A-elems per line)."""
    elems_per_line = L1_LINE // A_PREC
    l1_lines = L1_KB * 1024 // L1_LINE
    return (m * (n + 2 * k) + elems_per_line - 1) // elems_per_line <= l1_lines


# ── collect ──────────────────────────────────────────────────────────────────
# data[b_prec][fifo][(m,n)] = cycles
data = {bp: {False: {}, True: {}} for bp in B_PRECS}

for bp in B_PRECS:
    rho = bp / A_PREC
    opt_ratio = A_PREC / bp
    print(f"\nB_PREC={bp}B  ρ={rho:.3f}  theory optimal n/m={opt_ratio:.1f}")
    for m, n in SHAPES:
        ratio = n / m
        ok = "✓" if l1_ok(m, n) else "✗L1"
        for fifo in [False, True]:
            c = run(m, n, bp, fifo)
            data[bp][fifo][(m, n)] = c
        mc = data[bp][False][(m, n)]
        fc = data[bp][True][(m, n)]
        mv = f"{mc/1e6:.2f}M" if mc else "FAIL"
        fv = f"{fc/1e6:.2f}M" if fc else "FAIL"
        print(f"  ({m:2d},{n:2d}) ratio={ratio:5.1f} [{ok}]  mem={mv}  fifo={fv}")


# ── plot ─────────────────────────────────────────────────────────────────────
COLORS = ["#e41a1c", "#ff7f00", "#4daf4a", "#377eb8"]

fig, (ax_mem, ax_fifo) = plt.subplots(1, 2, figsize=(14, 5.5))

ratios = [n / m for m, n in SHAPES]

def plot_panel(ax, fifo, title):
    for bp, color in zip(B_PRECS, COLORS):
        cyc = [data[bp][fifo].get((m, n)) for m, n in SHAPES]
        valid = [(r, c / 1e6) for r, c in zip(ratios, cyc) if c is not None]
        if not valid:
            continue
        rs, cs = zip(*valid)
        ax.plot(rs, cs, marker="o", color=color, linewidth=2.2,
                markersize=7, label=f"B={bp}B")

        # annotate minimum among valid L1-feasible points
        feasible = [(r, c) for r, c, (m, n) in
                    zip(rs, cs, SHAPES) if l1_ok(m, n) and
                    data[bp][fifo].get((m, n)) is not None]
        if feasible:
            best_r, best_c = min(feasible, key=lambda x: x[1])
            ax.annotate(f"best\nn/m={best_r:.0f}",
                        xy=(best_r, best_c),
                        xytext=(best_r * 1.3, best_c + 3),
                        fontsize=7.5, color=color,
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.1))

        # theoretical optimal ratio (memory mode only)
        if not fifo:
            opt = A_PREC / bp
            ax.axvline(x=opt, color=color, linestyle=":", linewidth=1.0, alpha=0.6)

    # shade L1-violating region
    ax.axvspan(0.23, 0.5 - 0.01, alpha=0.06, color="red")  # ratio < 0.5: (64,4),(32,8)
    ax.axvline(x=0.5, color="grey", linestyle="--", linewidth=1.0, alpha=0.5)

    ax.set_xscale("log", base=2)
    ax.set_xticks(ratios)
    ax.set_xticklabels([f"{n}/{m}\n({m}×{n})" for m, n in SHAPES], fontsize=8)
    ax.set_xlabel("Tile ratio  n/m  (wide → right)", fontweight="bold")
    ax.set_ylabel("Total CPU Cycles (Millions)", fontweight="bold")
    ax.set_title(title, fontweight="bold", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(linestyle="--", alpha=0.5)

    # annotate L1 status above x-axis
    for (m, n) in SHAPES:
        r = n / m
        label = "✓" if l1_ok(m, n) else "✗"
        color_l = "green" if l1_ok(m, n) else "red"
        ax.annotate(label, xy=(r, ax.get_ylim()[0]),
                    xytext=(r, ax.get_ylim()[0]),
                    ha="center", fontsize=9, color=color_l)


plot_panel(ax_mem,  False,
           "Memory mode  (B from DRAM)\nDotted verticals = theory optimal n/m per B precision")
plot_panel(ax_fifo, True,
           "PRNG FIFO mode  (B free)\nTheory: widest feasible tile wins")

fig.suptitle(
    f"Theory Validation: Fixed Tile Area = {AREA} elements  (m×n={AREA}, k={K_FIXED})\n"
    f"Matrix {MAT}³  A={A_PREC}B  L1={L1_KB}KB  L2={L2_KB}KB  "
    f"FIFO gen_cost={FIFO_GEN_COST}cy  MULAC={MULAC}cy",
    fontsize=10, fontweight="bold"
)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = f"{OUTPUT_DIR}/theory_ratio_sweep.png"
fig.savefig(out, dpi=180)
plt.close(fig)
print(f"\n→ saved {out}")

# ── summary ──────────────────────────────────────────────────────────────────
print(f"\n{'B':>5}  {'ρ':>5}  {'theory n/m':>11}  {'mem best':>10}  {'mem n/m':>8}  {'fifo best':>10}  {'fifo n/m':>9}")
for bp in B_PRECS:
    rho = bp / A_PREC
    opt = A_PREC / bp
    # best among L1-feasible shapes
    mem_pts  = [(n/m, data[bp][False][(m,n)]) for m,n in SHAPES
                if l1_ok(m,n) and data[bp][False].get((m,n))]
    fifo_pts = [(n/m, data[bp][True][(m,n)])  for m,n in SHAPES
                if l1_ok(m,n) and data[bp][True].get((m,n))]
    mr, mc_ = min(mem_pts,  key=lambda x: x[1]) if mem_pts  else (0,0)
    fr, fc_ = min(fifo_pts, key=lambda x: x[1]) if fifo_pts else (0,0)
    print(f"{bp:>4}B  {rho:>5.3f}  {opt:>11.1f}  {mc_/1e6:>8.2f}M  {mr:>8.1f}  {fc_/1e6:>8.2f}M  {fr:>9.1f}")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)
