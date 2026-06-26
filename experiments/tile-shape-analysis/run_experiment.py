#!/usr/bin/env python3
"""
Tile shape × B precision × PRNG FIFO comparison.

Tile shapes (C-stationary, reg 4×4×4):
  - Square   16×16×16   (A+C = 4 KB)
  - Wide     16×48×16   (A+C = 8 KB = L1)
  - Tall     48×16×16   (A+C = 12 KB > L1)

B precisions: 1B, 2B, 4B, 8B.
Modes: normal memory vs --Bfifo.

Matrix: 96×96×96, A precision 8B.
L1=8KB (8B lines), L2=32KB (64B lines).
FIFO gen_cost=10 cy/elem, capacity=64.
"""

import os, subprocess, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE  = "../../asymm"
TEMP_CONFIG = "/tmp/tile_shape_exp.conf"
OUTPUT_DIR  = "."

MAT    = 96
A_PREC = 8
REG    = 4

L1_KB  = 8
L2_KB  = 32
MULAC  = 32      # enough slack for FIFO to prefill during computation

FIFO_GEN_COST  = 10
FIFO_CAPACITY  = 64

TILE_SHAPES = {
    "Square\n16×16×16":  (16, 16, 16),
    "Wide\n16×48×16":    (16, 48, 16),
    "Tall\n48×16×16":    (48, 16, 16),
}
B_PRECISIONS = [1, 2, 4, 8]

SHAPE_COLORS  = ["#1f77b4", "#d62728", "#2ca02c"]
MODE_HATCHES  = ["", "///"]
MODE_LABELS   = ["Memory (no PRNG)", "PRNG FIFO"]


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
        f.write(f"REG_M={REG}\nREG_N={REG}\nREG_K={REG}\n")
        f.write(f"MULAC_CYCLES={MULAC}\n")
        f.write("SP_ACCESS_CYCLES=1\nSP_BANKS=8\nSP_WORD_SIZE_BYTES=8\n")


def parse_cycles(stdout):
    for line in stdout.splitlines():
        m = re.match(r"Cycles:\s+(\d+)", line.strip())
        if m:
            return int(m.group(1))
    return None


def run(m, n, k, b_prec, fifo=False):
    write_config(b_prec)
    cmd = [EXECUTABLE]
    if fifo:
        cmd.append("--Bfifo")
    cmd += ["--config", TEMP_CONFIG, str(m), str(n), str(k)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        mode = "FIFO" if fifo else "mem"
        print(f"  FAIL {m}×{n}×{k} B={b_prec}B {mode}: {r.stderr.strip()[:100]}")
        return None
    return parse_cycles(r.stdout)


# ── collect results ──────────────────────────────────────────────────────────
print(f"Matrix {MAT}³  A={A_PREC}B  L1={L1_KB}KB  L2={L2_KB}KB")
print(f"FIFO gen_cost={FIFO_GEN_COST}cy  cap={FIFO_CAPACITY}")
print(f"MULAC={MULAC}cy  REG={REG}³\n")

# results[label][b_prec] = (mem_cycles, fifo_cycles)
results = {label: {} for label in TILE_SHAPES}

for label, (m, n, k) in TILE_SHAPES.items():
    short = label.replace("\n", " ")
    print(f"Tile {short}")
    for bp in B_PRECISIONS:
        mc = run(m, n, k, bp, fifo=False)
        fc = run(m, n, k, bp, fifo=True)
        if mc is None or fc is None:
            results[label][bp] = (mc, fc)
            print(f"  B={bp}B  FAILED")
        else:
            sp = mc / fc
            results[label][bp] = (mc, fc)
            print(f"  B={bp}B  mem={mc/1e6:.2f}M  fifo={fc/1e6:.2f}M  speedup={sp:.2f}x")
    print()

# ── Figure 1: absolute cycles ────────────────────────────────────────────────
fig1, axes = plt.subplots(1, len(B_PRECISIONS), figsize=(14, 5.5), sharey=False)

for col, bp in enumerate(B_PRECISIONS):
    ax = axes[col]
    x  = np.arange(len(TILE_SHAPES))
    w  = 0.35
    for i, (label, color) in enumerate(zip(TILE_SHAPES, SHAPE_COLORS)):
        mc, fc = results[label].get(bp, (None, None))
        if mc is not None:
            b1 = ax.bar(x[i] - w/2, mc/1e6, w, color=color,
                        alpha=0.85, edgecolor="black", linewidth=0.7,
                        label=f"{label.split(chr(10))[1]} mem")
            ax.text(x[i]-w/2, mc/1e6 + 0.15, f"{mc/1e6:.1f}", ha="center",
                    fontsize=7, rotation=90)
        if fc is not None:
            b2 = ax.bar(x[i] + w/2, fc/1e6, w, color=color,
                        alpha=0.45, edgecolor="black", linewidth=0.7,
                        hatch="///",
                        label=f"{label.split(chr(10))[1]} FIFO")
            ax.text(x[i]+w/2, fc/1e6 + 0.15, f"{fc/1e6:.1f}", ha="center",
                    fontsize=7, rotation=90)

    short_labels = [lbl.split("\n")[1] for lbl in TILE_SHAPES]
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=8, rotation=10)
    ax.set_title(f"B = {bp}B", fontweight="bold", fontsize=10)
    ax.set_xlabel("Tile shape", fontsize=8)
    if col == 0:
        ax.set_ylabel("Total Cycles (Millions)", fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_ylim(bottom=0)

# shared legend (solid = memory, hatched = FIFO)
from matplotlib.patches import Patch
legend_els = (
    [Patch(facecolor=c, edgecolor="black", label=list(TILE_SHAPES.keys())[i].split("\n")[1])
     for i, c in enumerate(SHAPE_COLORS)] +
    [Patch(facecolor="grey", alpha=0.85, edgecolor="black", label="Memory"),
     Patch(facecolor="grey", alpha=0.45, edgecolor="black", hatch="///", label="PRNG FIFO")]
)
fig1.legend(handles=legend_els, loc="upper center", ncol=5,
            fontsize=8, bbox_to_anchor=(0.5, 1.02))
fig1.suptitle(
    f"Absolute Cycles: Memory vs PRNG FIFO\n"
    f"Matrix {MAT}³  A={A_PREC}B  L1={L1_KB}KB  L2={L2_KB}KB  "
    f"FIFO gen_cost={FIFO_GEN_COST}cy  MULAC={MULAC}cy",
    fontsize=9, y=1.10
)
fig1.tight_layout()
fig1.savefig(f"{OUTPUT_DIR}/fig1_absolute_cycles.png", dpi=180, bbox_inches="tight")
plt.close(fig1)
print("→ saved fig1_absolute_cycles.png")


# ── Figure 2: FIFO speedup vs B precision ───────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(8, 5))

for label, color in zip(TILE_SHAPES, SHAPE_COLORS):
    speedups = []
    valid_prec = []
    for bp in B_PRECISIONS:
        mc, fc = results[label].get(bp, (None, None))
        if mc and fc:
            speedups.append(mc / fc)
            valid_prec.append(bp)
    short = label.split("\n")[0]
    ax2.plot(valid_prec, speedups, marker="o", color=color, linewidth=2.5,
             label=f"{label.replace(chr(10), '  ')}")
    for prec, sp in zip(valid_prec, speedups):
        ax2.annotate(f"{sp:.2f}x", (prec, sp),
                     textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=8, color=color)

ax2.axhline(y=1.0, color="black", linestyle=":", linewidth=1.2, label="break-even")
ax2.set_xticks(B_PRECISIONS)
ax2.set_xticklabels([f"{b}B" for b in B_PRECISIONS])
ax2.set_xlabel("B Element Precision (bytes)", fontweight="bold")
ax2.set_ylabel("PRNG FIFO Speedup  (memory / fifo)", fontweight="bold")
ax2.set_title(
    f"PRNG FIFO Speedup vs B Precision\n"
    f"Matrix {MAT}³  L1={L1_KB}KB  L2={L2_KB}KB  "
    f"gen_cost={FIFO_GEN_COST}cy  cap={FIFO_CAPACITY}  MULAC={MULAC}cy",
    fontweight="bold", fontsize=10
)
ax2.legend(fontsize=9)
ax2.grid(linestyle="--", alpha=0.5)
fig2.tight_layout()
fig2.savefig(f"{OUTPUT_DIR}/fig2_fifo_speedup_vs_precision.png", dpi=180)
plt.close(fig2)
print("→ saved fig2_fifo_speedup_vs_precision.png")

if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)
print("\nDone.")
