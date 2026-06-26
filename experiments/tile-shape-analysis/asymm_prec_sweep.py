#!/usr/bin/env python3
"""
Best tile shape for asymmetric B precision.

Fix m=16, k=16, A_PREC=8B. Sweep n ∈ {4,8,12,16,24,32,48,96}.
B_PREC ∈ {1, 2, 4, 8} bytes.
Modes: normal memory and PRNG FIFO (--Bfifo).

Matrix: 96×96×96, L1=8KB (8B lines), L2=32KB (64B lines).
FIFO gen_cost=10 cy/elem, cap=64, MULAC=32cy, reg=4×4×4.

Theory: C+2A ≤ L1 gives n≤32 as optimum regardless of B_PREC,
because in C-stationary B has no L1 footprint (FIFO) or is always
reloaded M/m times (memory) independent of n.
"""

import os, subprocess, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE  = "../../asymm"
TEMP_CONFIG = "/tmp/asymm_prec_sweep.conf"
OUTPUT_DIR  = "."

MAT    = 96
A_PREC = 8
M_FIXED = 16
K_FIXED = 16

L1_KB  = 8
L2_KB  = 32
MULAC  = 32
FIFO_GEN_COST = 10
FIFO_CAPACITY = 64

N_VALUES  = [4, 8, 12, 16, 24, 32, 48, 96]
B_PRECS   = [1, 2, 4, 8]


def write_config(b_prec):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT}\nA_WIDTH_DIM={MAT}\nB_WIDTH_DIM={MAT}\n")
        f.write(f"A_PRECISION_BYTES={A_PREC}\nB_PRECISION_BYTES={b_prec}\n")
        f.write(f"L1_SIZE_BYTES={L1_KB*1024}\nL1_LINE_SIZE_BYTES=8\n")
        f.write("L1_ASSOC=4\nL1_ACCESS_CYCLES=4\n")
        f.write("L1_REPLACEMENT_POLICY=LRU\nL1_WRITE_POLICY=WRITE_BACK\n")
        f.write(f"L2_SIZE_BYTES={L2_KB*1024}\nL2_LINE_SIZE_BYTES=64\n")
        f.write("L2_ASSOC=8\nL2_ACCESS_CYCLES=15\n")
        f.write("L2_REPLACEMENT_POLICY=LRU\nL2_WRITE_POLICY=WRITE_BACK\n")
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\nPRNG_GEN_COST_PER_LINE=64\n")
        f.write(f"PRNG_FIFO_CAPACITY={FIFO_CAPACITY}\n")
        f.write(f"PRNG_FIFO_GEN_COST={FIFO_GEN_COST}\n")
        f.write(f"REG_M=4\nREG_N=4\nREG_K=4\n")
        f.write(f"MULAC_CYCLES={MULAC}\n")
        f.write("SP_ACCESS_CYCLES=1\nSP_BANKS=8\nSP_WORD_SIZE_BYTES=8\n")


def parse_cycles(stdout):
    for line in stdout.splitlines():
        m = re.match(r"Cycles:\s+(\d+)", line.strip())
        if m:
            return int(m.group(1))
    return None


def run(n, b_prec, fifo=False):
    write_config(b_prec)
    cmd = [EXECUTABLE]
    if fifo:
        cmd.append("--Bfifo")
    cmd += ["--config", TEMP_CONFIG, str(M_FIXED), str(n), str(K_FIXED)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tag = "FIFO" if fifo else "mem"
        print(f"  FAIL n={n} B={b_prec}B {tag}: {r.stderr.strip()[:80]}")
        return None
    return parse_cycles(r.stdout)


# ── collect ──────────────────────────────────────────────────────────────────
# data[b_prec][fifo][n] = cycles
data = {bp: {False: {}, True: {}} for bp in B_PRECS}

for bp in B_PRECS:
    print(f"\nB_PREC = {bp}B")
    for fifo in [False, True]:
        tag = "FIFO" if fifo else "mem "
        row = []
        for n in N_VALUES:
            c = run(n, bp, fifo)
            data[bp][fifo][n] = c
            v = f"n={n}:{c/1e6:.2f}M" if c else f"n={n}:FAIL"
            row.append(v)
        print(f"  [{tag}]  " + "  ".join(row))


# ── plot ─────────────────────────────────────────────────────────────────────
COLORS = ["#e41a1c", "#ff7f00", "#4daf4a", "#377eb8"]  # 1B 2B 4B 8B
STYLES = {False: "-", True: "--"}

fig, (ax_mem, ax_fifo) = plt.subplots(1, 2, figsize=(14, 5.5))

def plot_panel(ax, fifo, title):
    for bp, color in zip(B_PRECS, COLORS):
        ns  = [n for n in N_VALUES if data[bp][fifo].get(n) is not None]
        cyc = [data[bp][fifo][n] / 1e6 for n in ns]
        ax.plot(ns, cyc, marker="o", color=color, linewidth=2.2,
                markersize=7, label=f"B={bp}B")

        if cyc:
            bi = cyc.index(min(cyc))
            bn, bc = ns[bi], cyc[bi]
            ax.annotate(f"n={bn}",
                        xy=(bn, bc),
                        xytext=(bn + 2, bc + 0.25),
                        fontsize=8, color=color,
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.1))

    # corrected theoretical boundary (C+2A = L1 → n=32)
    ax.axvline(x=32, color="black", linestyle="--", linewidth=1.2, alpha=0.6,
               label="C+2A = L1 (n=32)")
    ax.axvspan(33, 97, alpha=0.06, color="red", label="C+2A > L1")

    ax.set_xticks(N_VALUES)
    ax.set_xticklabels([str(n) for n in N_VALUES])
    ax.set_xlabel("Tile n  (shape = 16 × n × 16)", fontweight="bold")
    ax.set_ylabel("Total CPU Cycles (Millions)", fontweight="bold")
    ax.set_title(title, fontweight="bold", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(linestyle="--", alpha=0.5)

plot_panel(ax_mem,  False,
           "Memory mode (B from DRAM)\nA=8B, B precision varies")
plot_panel(ax_fifo, True,
           "PRNG FIFO mode (B from FIFO)\nA=8B, B precision varies")

fig.suptitle(
    f"Best Tile Shape vs B Precision  —  C-stationary\n"
    f"Matrix {MAT}³  A={A_PREC}B  L1={L1_KB}KB  L2={L2_KB}KB  "
    f"reg=4³  FIFO gen_cost={FIFO_GEN_COST}cy  MULAC={MULAC}cy",
    fontsize=10, fontweight="bold"
)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = f"{OUTPUT_DIR}/asymm_prec_sweep.png"
fig.savefig(out, dpi=180)
plt.close(fig)
print(f"\n→ saved {out}")

# ── summary table ─────────────────────────────────────────────────────────────
print("\nOptimal n per B_PREC and mode:")
print(f"{'B_PREC':>8}  {'mem best n':>12}  {'mem cycles':>12}  {'fifo best n':>12}  {'fifo cycles':>12}")
for bp in B_PRECS:
    for fifo in [False, True]:
        ns  = [n for n in N_VALUES if data[bp][fifo].get(n) is not None]
        cyc = [data[bp][fifo][n] for n in ns]
        if cyc:
            bi = cyc.index(min(cyc))
            if not fifo:
                mem_n, mem_c = ns[bi], cyc[bi]
            else:
                fif_n, fif_c = ns[bi], cyc[bi]
    print(f"{bp:>6}B  {mem_n:>12}  {mem_c/1e6:>10.2f}M  {fif_n:>12}  {fif_c/1e6:>10.2f}M")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)
