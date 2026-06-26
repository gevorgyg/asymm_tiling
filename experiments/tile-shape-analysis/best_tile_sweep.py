#!/usr/bin/env python3
"""
Empirical best-tile-size sweep.

Fix m=16, k=16.  Sweep n ∈ {4,8,12,16,24,32,48,96} (all divide 96, multiple of reg=4).
Run two L2 sizes:
  - Small L2 = 32 KB  (A+B+C = 216 KB >> L2 → many L2 misses)
  - Large L2 = 256 KB (A+B+C = 216 KB  < L2 → all data fits)

Run two modes each: normal memory  and  PRNG FIFO (--Bfifo).

Matrix: 96×96×96, A prec = B prec = 8B.
L1 = 8 KB (8B lines), MULAC = 32cy, reg = 4×4×4.
FIFO gen_cost = 10 cy/elem, capacity = 64.

Theory (corrected):
  - Naive "A+C = L1" gives n=48, but this ignores the K-tile transition:
    loading A(tk+1) must not evict C → need C + 2*A ≤ L1.
    C = 16*n*8B,  A = 16*16*8B = 2KB  →  n ≤ 32.
  - With FIFO (B not in cache): optimum at n = 32 (C+2A = 8KB = L1).
  - With memory + large L2 (B cached in L2): smaller n wins (B cache locality).
"""

import os, subprocess, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE  = "../../asymm"
TEMP_CONFIG = "/tmp/tile_sweep_best.conf"
OUTPUT_DIR  = "."

MAT    = 96
A_PREC = 8
B_PREC = 8
REG    = 4
MULAC  = 32
FIFO_GEN_COST = 10
FIFO_CAPACITY = 64

L1_KB = 8
L2_SMALL_KB  = 32     # matrices (3 × 72KB = 216KB) >> L2
L2_LARGE_KB  = 256    # matrices (216KB) < L2 → all fits

# n values: divisors of 96 that are multiples of reg=4
N_VALUES = [4, 8, 12, 16, 24, 32, 48, 96]
M_FIXED  = 16
K_FIXED  = 16

def c_plus_2a_kb(n):
    """C-tile + 2×A-tile footprint in KB (corrected L1 condition)."""
    a_tile = M_FIXED * K_FIXED * A_PREC
    c_tile = M_FIXED * n * A_PREC
    return (c_tile + 2 * a_tile) / 1024


def write_config(l2_kb):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MAT}\nA_WIDTH_DIM={MAT}\nB_WIDTH_DIM={MAT}\n")
        f.write(f"A_PRECISION_BYTES={A_PREC}\nB_PRECISION_BYTES={B_PREC}\n")
        f.write(f"L1_SIZE_BYTES={L1_KB*1024}\nL1_LINE_SIZE_BYTES=8\n")
        f.write("L1_ASSOC=4\nL1_ACCESS_CYCLES=4\n")
        f.write("L1_REPLACEMENT_POLICY=LRU\nL1_WRITE_POLICY=WRITE_BACK\n")
        f.write(f"L2_SIZE_BYTES={l2_kb*1024}\nL2_LINE_SIZE_BYTES=64\n")
        f.write("L2_ASSOC=8\nL2_ACCESS_CYCLES=15\n")
        f.write("L2_REPLACEMENT_POLICY=LRU\nL2_WRITE_POLICY=WRITE_BACK\n")
        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\nPRNG_GEN_COST_PER_LINE=64\n")
        f.write(f"PRNG_FIFO_CAPACITY={FIFO_CAPACITY}\n")
        f.write(f"PRNG_FIFO_GEN_COST={FIFO_GEN_COST}\n")
        f.write(f"REG_M={REG}\nREG_N={REG}\nREG_K={REG}\n")
        f.write(f"MULAC_CYCLES={MULAC}\n")
        f.write("SP_ACCESS_CYCLES=1\nSP_BANKS=8\nSP_WORD_SIZE_BYTES=8\n")


def parse_cycles(stdout):
    for line in stdout.splitlines():
        m = re.match(r"Cycles:\s+(\d+)", line.strip())
        if m:
            return int(m.group(1))
    return None


def run(n, l2_kb, fifo=False):
    write_config(l2_kb)
    cmd = [EXECUTABLE]
    if fifo:
        cmd.append("--Bfifo")
    cmd += ["--config", TEMP_CONFIG, str(M_FIXED), str(n), str(K_FIXED)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tag = "FIFO" if fifo else "mem"
        print(f"  FAIL n={n} L2={l2_kb}KB {tag}: {r.stderr.strip()[:80]}")
        return None
    return parse_cycles(r.stdout)


# ── collect ──────────────────────────────────────────────────────────────────
data = {}   # data[(l2_kb, fifo)] = {n: cycles}

for l2_kb, label in [(L2_SMALL_KB, "Small"), (L2_LARGE_KB, "Large")]:
    mat_total = 3 * MAT * MAT * A_PREC / 1024
    print(f"\nL2 = {l2_kb} KB  ({label}, matrices = {mat_total:.0f} KB total)")
    for fifo in [False, True]:
        key = (l2_kb, fifo)
        data[key] = {}
        tag = "FIFO" if fifo else "mem "
        row = []
        for n in N_VALUES:
            c = run(n, l2_kb, fifo)
            data[key][n] = c
            v = f"{c/1e6:.2f}M" if c else "FAIL"
            row.append(f"n={n}: {v}")
        print(f"  [{tag}]  " + "  ".join(row))

# ── plot ─────────────────────────────────────────────────────────────────────
fig, (ax_small, ax_large) = plt.subplots(1, 2, figsize=(14, 5.5))

def plot_panel(ax, l2_kb, title):
    colors = {"mem": "#d62728", "fifo": "#1f77b4"}
    markers = {"mem": "s", "fifo": "o"}

    for fifo, mode_label, color, marker in [
        (False, "Memory (no PRNG)", colors["mem"], markers["mem"]),
        (True,  "PRNG FIFO",        colors["fifo"], markers["fifo"]),
    ]:
        key = (l2_kb, fifo)
        ns  = [n for n in N_VALUES if data[key].get(n) is not None]
        cyc = [data[key][n] / 1e6 for n in ns]
        ax.plot(ns, cyc, marker=marker, color=color, linewidth=2.2,
                markersize=7, label=mode_label)

        # annotate minimum
        if cyc:
            best_idx = cyc.index(min(cyc))
            best_n   = ns[best_idx]
            best_c   = cyc[best_idx]
            ax.annotate(f"best\nn={best_n}",
                        xy=(best_n, best_c),
                        xytext=(best_n + 3, best_c + 0.3),
                        fontsize=8, color=color,
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.2))

    # shade region where C+2A > L1 (corrected condition)
    ax.axvspan(32 + 1, 97, alpha=0.07, color="red",
               label=f"C+2A > L1 ({L1_KB} KB)")
    # vertical line at corrected theoretical optimum (C+2A = L1 → n=32)
    ax.axvline(x=32, color="black", linestyle="--", linewidth=1.2, alpha=0.5,
               label="C+2A = L1 (n=32)")

    # secondary x labels: A+C footprint
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(N_VALUES)
    ax2.set_xticklabels([f"{c_plus_2a_kb(n):.1f}K" for n in N_VALUES], fontsize=7.5,
                        color="#555555", rotation=30)
    ax2.set_xlabel("C+2A tile footprint", fontsize=8, color="#555555")

    ax.set_xticks(N_VALUES)
    ax.set_xticklabels([str(n) for n in N_VALUES])
    ax.set_xlabel("Tile n   (shape = 16 × n × 16)", fontweight="bold")
    ax.set_ylabel("Total CPU Cycles (Millions)", fontweight="bold")
    ax.set_title(title, fontweight="bold", fontsize=11)
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(linestyle="--", alpha=0.5)

mat_kb = MAT * MAT * A_PREC // 1024
plot_panel(ax_small, L2_SMALL_KB,
           f"Small L2 = {L2_SMALL_KB} KB\n"
           f"(matrices = {3*mat_kb} KB >> L2 → frequent L2 misses)")
plot_panel(ax_large, L2_LARGE_KB,
           f"Large L2 = {L2_LARGE_KB} KB\n"
           f"(matrices = {3*mat_kb} KB < L2 → fits in cache)")

fig.suptitle(
    f"Empirical Best Tile vs L2 Size\n"
    f"Matrix {MAT}³  A=B={A_PREC}B  L1={L1_KB}KB  reg={REG}³  "
    f"FIFO gen_cost={FIFO_GEN_COST}cy  MULAC={MULAC}cy",
    fontsize=10, fontweight="bold"
)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = f"{OUTPUT_DIR}/best_tile_sweep.png"
fig.savefig(out, dpi=180)
plt.close(fig)

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)
print(f"\n→ saved {out}")
