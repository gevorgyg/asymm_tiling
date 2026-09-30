#!/usr/bin/env python3
"""
Two PRNG FIFO stall experiments:

Experiment 1 — stalls vs. FIFO capacity, lines = mulac_cycles
  X: FIFO capacity 1..512 (log)   Y: stall cycles   fixed gen_cost=10

Experiment 2 — stalls vs. gen_cost, lines = FIFO capacity
  X: gen_cost 1..50              Y: stall cycles   fixed mulac_cycles=32

Fixed: matrix 256³, tile 32×32×32, reg 4×4×4, B precision 2 bytes,
       C-stationary, --Bfifo, no scratchpad.
"""

import os
import subprocess
import re
import matplotlib.pyplot as plt
import numpy as np

EXECUTABLE = "../../asymm"
TEMP_CONFIG = "/tmp/fifo_stall_sweep.conf"
OUTPUT_DIR = "."

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── sweep parameters ─────────────────────────────────────────────────────────
MATRIX_DIM   = 256
TILE_M, TILE_N, TILE_K = 32, 32, 32
REG_M, REG_N, REG_K    = 4, 4, 4
B_PRECISION  = 2          # bytes per B element
GEN_COST     = 10         # cycles to generate one element

MULAC_VALUES   = [0, 8, 32, 128, 512]
CAPACITY_VALUES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]


def write_config(fifo_capacity, mulac_cycles, gen_cost=GEN_COST):
    with open(TEMP_CONFIG, "w") as f:
        f.write(f"A_HEIGHT_DIM={MATRIX_DIM}\n")
        f.write(f"A_WIDTH_DIM={MATRIX_DIM}\n")
        f.write(f"B_WIDTH_DIM={MATRIX_DIM}\n")
        f.write("A_PRECISION_BYTES=8\n")
        f.write(f"B_PRECISION_BYTES={B_PRECISION}\n")

        f.write("L1_SIZE_BYTES=8192\n")
        f.write("L1_LINE_SIZE_BYTES=8\n")
        f.write("L1_ASSOC=4\n")
        f.write("L1_ACCESS_CYCLES=4\n")
        f.write("L1_REPLACEMENT_POLICY=LRU\n")
        f.write("L1_WRITE_POLICY=WRITE_BACK\n")

        f.write("L2_SIZE_BYTES=131072\n")
        f.write("L2_LINE_SIZE_BYTES=64\n")
        f.write("L2_ASSOC=8\n")
        f.write("L2_ACCESS_CYCLES=15\n")
        f.write("L2_REPLACEMENT_POLICY=LRU\n")
        f.write("L2_WRITE_POLICY=WRITE_BACK\n")

        f.write("MEM_ACCESS_CYCLES=180\n")
        f.write("PRNG_ACCESS_CYCLES=2\n")
        f.write("PRNG_GEN_COST_PER_LINE=64\n")

        f.write(f"PRNG_FIFO_CAPACITY={fifo_capacity}\n")
        f.write(f"PRNG_FIFO_GEN_COST={gen_cost}\n")

        f.write(f"REG_M={REG_M}\n")
        f.write(f"REG_N={REG_N}\n")
        f.write(f"REG_K={REG_K}\n")
        f.write(f"MULAC_CYCLES={mulac_cycles}\n")

        f.write("SP_ACCESS_CYCLES=1\n")
        f.write("SP_BANKS=8\n")
        f.write("SP_WORD_SIZE_BYTES=8\n")


def parse_stats(stdout):
    stats = {}
    current = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("--- ") and line.endswith(" ---"):
            current = line.strip("- ").strip()
            continue
        if current == "PRNG FIFO":
            m = re.match(r"(\w+):\s+(\d+)", line)
            if m:
                stats[m.group(1).lower()] = int(m.group(2))
        elif current == "System":
            m = re.match(r"Cycles:\s+(\d+)", line)
            if m:
                stats["cycles"] = int(m.group(1))
    return stats


def run_sim(fifo_capacity, mulac_cycles):
    write_config(fifo_capacity, mulac_cycles)
    cmd = [
        EXECUTABLE,
        "--Bfifo",
        "--config", TEMP_CONFIG,
        str(TILE_M), str(TILE_N), str(TILE_K),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  FAILED: cap={fifo_capacity} mulac={mulac_cycles}")
        print(res.stderr[:400])
        return None
    return parse_stats(res.stdout)


def run_sim_gencost(fifo_capacity, mulac_cycles, gen_cost):
    write_config(fifo_capacity, mulac_cycles, gen_cost=gen_cost)
    cmd = [
        EXECUTABLE,
        "--Bfifo",
        "--config", TEMP_CONFIG,
        str(TILE_M), str(TILE_N), str(TILE_K),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  FAILED: cap={fifo_capacity} mulac={mulac_cycles} gen_cost={gen_cost}")
        print(res.stderr[:400])
        return None
    return parse_stats(res.stdout)


def theoretical_saturation_capacity(mulac_cycles):
    """
    Minimum FIFO capacity needed to have zero stalls (rough estimate).
    Between consecutive B reg-tile reads the gap is:
        A_reg_load_cycles + mulac_cycles
    where A_reg_load_cycles ≈ REG_M * REG_K * L1_ACCESS_CYCLES = 4*4*4 = 64 cy.
    Elements generated per gap  = floor(gap / GEN_COST)
    Elements needed per B tile  = REG_N * REG_K
    If gap/GEN_COST >= REG_N*REG_K, a FIFO of capacity 1 suffices.
    Otherwise we need pre-buffering; this returns the approx pre-fill size.
    """
    reg_elements = REG_N * REG_K
    a_load_cycles = REG_M * REG_K * 4   # L1 hit cost
    gap = a_load_cycles + mulac_cycles
    gen_per_gap = gap / GEN_COST
    if gen_per_gap >= reg_elements:
        return 1
    shortage_per_tile = reg_elements - gen_per_gap
    # pre-fill needed over all rtk iterations (approx)
    return int(shortage_per_tile * (TILE_K // REG_K))


# ── main sweep ────────────────────────────────────────────────────────────────
print(f"Experiment: FIFO stalls vs capacity for mulac in {MULAC_VALUES}")
print(f"Matrix {MATRIX_DIM}³  tile {TILE_M}×{TILE_N}×{TILE_K}  "
      f"reg {REG_M}×{REG_N}×{REG_K}  gen_cost={GEN_COST}\n")

# results[mulac] = list of (capacity, stall_cycles, total_cycles)
results = {}
for mulac in MULAC_VALUES:
    results[mulac] = []
    for cap in CAPACITY_VALUES:
        s = run_sim(cap, mulac)
        stalls = s.get("stallcycles", 0) if s else 0
        cycles = s.get("cycles", 0) if s else 0
        results[mulac].append((cap, stalls, cycles))
        print(f"  mulac={mulac:4d}  cap={cap:4d}  "
              f"stall_cycles={stalls:>12,}  total_cycles={cycles:>12,}")
    print()

# ── plot ─────────────────────────────────────────────────────────────────────
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

fig, (ax_stall, ax_total) = plt.subplots(1, 2, figsize=(14, 5.5))

for (mulac, color) in zip(MULAC_VALUES, COLORS):
    caps    = [r[0] for r in results[mulac]]
    stalls  = [r[1] / 1e6 for r in results[mulac]]
    totals  = [r[2] / 1e6 for r in results[mulac]]
    label   = f"mulac={mulac} cy"
    ax_stall.plot(caps, stalls, marker="o", color=color, label=label, linewidth=2)
    ax_total.plot(caps, totals, marker="o", color=color, label=label, linewidth=2)

ax_stall.set_xscale("log", base=2)
ax_stall.set_xticks(CAPACITY_VALUES)
ax_stall.set_xticklabels([str(c) for c in CAPACITY_VALUES], rotation=45)
ax_stall.set_xlabel("FIFO Capacity (elements)", fontweight="bold")
ax_stall.set_ylabel("FIFO Stall Cycles (Millions)", fontweight="bold")
ax_stall.set_title(
    f"FIFO Stall Cycles vs. FIFO Capacity\n"
    f"Matrix {MATRIX_DIM}³ · tile {TILE_M}×{TILE_N}×{TILE_K} · "
    f"reg {REG_M}×{REG_N}×{REG_K} · gen_cost={GEN_COST}",
    fontsize=10, fontweight="bold"
)
ax_stall.grid(True, which="both", linestyle="--", alpha=0.5)
ax_stall.legend()

ax_total.set_xscale("log", base=2)
ax_total.set_xticks(CAPACITY_VALUES)
ax_total.set_xticklabels([str(c) for c in CAPACITY_VALUES], rotation=45)
ax_total.set_xlabel("FIFO Capacity (elements)", fontweight="bold")
ax_total.set_ylabel("Total CPU Cycles (Millions)", fontweight="bold")
ax_total.set_title(
    f"Total Cycles vs. FIFO Capacity\n"
    f"Matrix {MATRIX_DIM}³ · tile {TILE_M}×{TILE_N}×{TILE_K} · "
    f"reg {REG_M}×{REG_N}×{REG_K} · gen_cost={GEN_COST}",
    fontsize=10, fontweight="bold"
)
ax_total.grid(True, which="both", linestyle="--", alpha=0.5)
ax_total.legend()

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "fifo_stalls_vs_capacity.png"), dpi=200)
plt.close()
print(f"Plot saved to {OUTPUT_DIR}/fifo_stalls_vs_capacity.png")

# ── text summary ─────────────────────────────────────────────────────────────
print("\n=== Summary table ===")
header = f"{'cap':>6}" + "".join(f"  mulac={m:>3}(stalls M)" for m in MULAC_VALUES)
print(header)
for i, cap in enumerate(CAPACITY_VALUES):
    row = f"{cap:>6}"
    for mulac in MULAC_VALUES:
        stall_m = results[mulac][i][1] / 1e6
        row += f"  {stall_m:>14.2f}"
    print(row)

# ── Experiment 2: stalls vs. gen_cost ────────────────────────────────────────
GEN_COST_VALUES  = [1, 2, 5, 10, 20, 30, 50]
CAP_LINES        = [8, 16, 32, 64, 128]
MULAC_FIXED      = 32

print(f"\nExperiment 2: FIFO stalls vs gen_cost for capacities {CAP_LINES}")
print(f"Fixed mulac_cycles={MULAC_FIXED}\n")

# results2[cap] = list of (gen_cost, stall_cycles, total_cycles)
results2 = {}
for cap in CAP_LINES:
    results2[cap] = []
    for gc in GEN_COST_VALUES:
        s = run_sim_gencost(cap, MULAC_FIXED, gc)
        stalls = s.get("stallcycles", 0) if s else 0
        cycles = s.get("cycles", 0) if s else 0
        results2[cap].append((gc, stalls, cycles))
        print(f"  cap={cap:4d}  gen_cost={gc:3d}  "
              f"stall_cycles={stalls:>12,}  total_cycles={cycles:>12,}")
    print()

# ── plot 2 ───────────────────────────────────────────────────────────────────
COLORS2 = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

fig2, (ax2_stall, ax2_total) = plt.subplots(1, 2, figsize=(14, 5.5))

for cap, color in zip(CAP_LINES, COLORS2):
    gcs    = [r[0] for r in results2[cap]]
    stalls = [r[1] / 1e6 for r in results2[cap]]
    totals = [r[2] / 1e6 for r in results2[cap]]
    ax2_stall.plot(gcs, stalls, marker="o", color=color,
                   label=f"cap={cap}", linewidth=2)
    ax2_total.plot(gcs, totals, marker="o", color=color,
                   label=f"cap={cap}", linewidth=2)

# mark the theoretical zero-stall threshold: gen_cost <= (A_load + mulac) / elem_per_tile
a_load_approx = REG_M * REG_K * 4    # L1 hit cost for A reg tile
elem_per_tile = REG_N * REG_K
threshold_gc  = (a_load_approx + MULAC_FIXED) / elem_per_tile
ax2_stall.axvline(x=threshold_gc, color="black", linestyle=":", linewidth=1.5,
                  label=f"zero-stall threshold ≈ {threshold_gc:.1f} cy/elem")

ax2_stall.set_xlabel("Generator Cost (cycles / element)", fontweight="bold")
ax2_stall.set_ylabel("FIFO Stall Cycles (Millions)", fontweight="bold")
ax2_stall.set_title(
    f"FIFO Stall Cycles vs. Generator Cost\n"
    f"Matrix {MATRIX_DIM}³ · tile {TILE_M}×{TILE_N}×{TILE_K} · "
    f"reg {REG_M}×{REG_N}×{REG_K} · mulac={MULAC_FIXED}",
    fontsize=10, fontweight="bold"
)
ax2_stall.grid(True, linestyle="--", alpha=0.5)
ax2_stall.legend()

ax2_total.set_xlabel("Generator Cost (cycles / element)", fontweight="bold")
ax2_total.set_ylabel("Total CPU Cycles (Millions)", fontweight="bold")
ax2_total.set_title(
    f"Total Cycles vs. Generator Cost\n"
    f"Matrix {MATRIX_DIM}³ · tile {TILE_M}×{TILE_N}×{TILE_K} · "
    f"reg {REG_M}×{REG_N}×{REG_K} · mulac={MULAC_FIXED}",
    fontsize=10, fontweight="bold"
)
ax2_total.grid(True, linestyle="--", alpha=0.5)
ax2_total.legend()

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "fifo_stalls_vs_gencost.png"), dpi=200)
plt.close()
print(f"Plot saved to {OUTPUT_DIR}/fifo_stalls_vs_gencost.png")

print("\n=== Gen-cost summary table ===")
header2 = f"{'gen_cost':>10}" + "".join(f"  cap={c:>3}(stalls M)" for c in CAP_LINES)
print(header2)
for i, gc in enumerate(GEN_COST_VALUES):
    row = f"{gc:>10}"
    for cap in CAP_LINES:
        stall_m = results2[cap][i][1] / 1e6
        row += f"  {stall_m:>14.2f}"
    print(row)

# cleanup
if os.path.exists(TEMP_CONFIG):
    os.remove(TEMP_CONFIG)
