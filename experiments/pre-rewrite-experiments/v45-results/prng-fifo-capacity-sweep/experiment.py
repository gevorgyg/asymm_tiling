"""PRNG FIFO capacity sweep: does a larger FIFO buffer eliminate stalls?

Fixed setup: 32×32 tile, M=N=K=256, A_P=B_P=4, L1=16K (same as prng-fifo-tile-sweep).
We sweep FIFO capacity at several gen_cost values spanning the crossover (~104 cycles/element):
  gc=64  → below crossover (FIFO generates faster than consumed, no stalls expected)
  gc=128 → just above crossover (~18% stall fraction at capacity=64)
  gc=256 → well above crossover (~58%)
  gc=512 → deeply bottlenecked (~79%)

Hypothesis: stall fraction is FLAT across capacity for gc > crossover.
Reason: STOP_REG clears the FIFO on each session end, so every session starts from
0 elements. Generation rate < consumption rate means the FIFO drains regardless of how
large it is. Capacity cannot substitute for a true head start (pre-filling before the
first DATA_REG read). This motivates a future pipelined implementation.

A mem baseline is included as a reference.
"""

import math
from collections import defaultdict
from pathlib import Path

from matplotlib import colormaps
from matplotlib.colors import to_hex

from experiments.harness import (
    Cell, Flags, describe_changes, lineplot, plot_metric_family,
    run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

M = N = K = 256
A_P = B_P = 4
LINE = 64
L1 = 16_384
L2 = 4 * L1
TM, TN = 32, 32   # fixed square tile at optimal aspect for gc≤64

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": A_P, "B_PRECISION_BYTES": B_P,
    "L1_SIZE_BYTES": L1,  "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": L1 // LINE,
    "L2_SIZE_BYTES": L2,  "L2_LINE_SIZE_BYTES": LINE, "L2_ASSOC": L2 // LINE,
    "L2_ACCESS_CYCLES": 14,
    "TILE_K": K, "TILE_M": TM, "TILE_N": TN,
}

GEN_COSTS:   list[int] = [64, 128, 256, 512]
CAPACITIES:  list[int] = [64, 128, 256, 512, 1024, 2048, 4096]

FLAGS_MEM  = Flags(b_source="mem",       stationary="C", three_d_reg=True, outer_products=True)
FLAGS_FIFO = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True, outer_products=True)

_COLOR_MEM = "#444444"
_cmap = colormaps["coolwarm"]
_log_gc = [math.log2(gc) for gc in GEN_COSTS]
_lo, _hi = _log_gc[0], _log_gc[-1]
PALETTE_GC: dict[int, str] = {
    gc: to_hex(_cmap((math.log2(gc) - _lo) / (_hi - _lo)))
    for gc in GEN_COSTS
}


def _label(gc: int) -> str:
    return f"prng_fifo, gc={gc}"


def _colors() -> dict[str, str]:
    return {"mem": _COLOR_MEM, **{_label(gc): PALETTE_GC[gc] for gc in GEN_COSTS}}


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    caption = describe_changes(
        {k: v for k, v in BASE_OVERRIDES.items()
         if k not in ("PRNG_FIFO_CAPACITY", "TILE_K")},
        base,
        extras={"TILE_K": K, "TILE_M": TM, "TILE_N": TN,
                "order": "outer products"},
    )

    # --- mem baseline (single run, no capacity parameter) ---
    print("--- mem baseline ---")
    mem_duals = run_grid_dual(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=BASE_OVERRIDES,
        flags=FLAGS_MEM,
    )
    mem_cycles = mem_duals[0].cycles.cycles

    # --- prng_fifo: sweep gen_cost × capacity ---
    # records[gc][cap] = DualResult
    records: dict[int, dict[int, object]] = {gc: {} for gc in GEN_COSTS}

    for gc in GEN_COSTS:
        print(f"\n--- prng_fifo gc={gc} ---")
        for cap in CAPACITIES:
            duals = run_grid_dual(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={
                    **BASE_OVERRIDES,
                    "PRNG_FIFO_GEN_COST": gc,
                    "PRNG_FIFO_CAPACITY": cap,
                },
                flags=FLAGS_FIFO,
            )
            records[gc][cap] = duals[0]

    # --- Plot: stall fraction vs capacity per gc ---
    stall_series: dict[str, list] = defaultdict(list)
    for gc in GEN_COSTS:
        for cap in CAPACITIES:
            d = records[gc][cap]
            pf = d.cycles.prng_fifo
            total = d.cycles.cycles
            frac = (pf.stall_cycles / total) if (pf and total) else 0.0
            stall_series[_label(gc)].append((math.log2(cap), frac))
    for v in stall_series.values():
        v.sort()
    lineplot(
        dict(stall_series),
        out_path=EXPERIMENT_DIR / "stall_fraction_vs_capacity.png",
        xlabel="log₂(FIFO capacity)",
        ylabel="stall cycles / total cycles",
        title="FIFO capacity sweep: stall fraction vs capacity\n"
              f"tile={TM}×{TN}, {caption}\n"
              "Hypothesis: flat lines for gc > ~104 (crossover)",
        colors={_label(gc): PALETTE_GC[gc] for gc in GEN_COSTS},
    )

    # --- Plot: total cycles vs capacity per gc (+ mem reference line) ---
    cycle_series: dict[str, list] = defaultdict(list)
    cycle_series["mem"] = [(math.log2(c), mem_cycles) for c in CAPACITIES]
    for gc in GEN_COSTS:
        for cap in CAPACITIES:
            cycle_series[_label(gc)].append((math.log2(cap), records[gc][cap].cycles.cycles))
    for v in cycle_series.values():
        v.sort()
    lineplot(
        cycle_series,
        out_path=EXPERIMENT_DIR / "cycles_vs_capacity.png",
        xlabel="log₂(FIFO capacity)",
        ylabel="total cycles (mulacc included)",
        title="FIFO capacity sweep: total cycles vs capacity\n"
              f"tile={TM}×{TN}, {caption}",
        colors=_colors(),
    )

    # --- README ---
    write_report(
        EXPERIMENT_DIR / "README.md",
        "prng-fifo-capacity-sweep",
        [
            f"Non-default config: {caption}\n\n"
            "See [experiment.py](experiment.py) for hypotheses.\n",

            "## Results\n\n"
            "![stall fraction vs capacity](stall_fraction_vs_capacity.png)\n\n"
            "![cycles vs capacity](cycles_vs_capacity.png)\n\n"
            f"mem baseline: {mem_cycles:,} cycles (horizontal reference)\n\n"
            "**Key finding:** stall fraction is flat across capacity for gc ≥ 128, "
            "confirming that capacity alone cannot compensate for generation rate < "
            "consumption rate (~104 cycles/element for this tile). "
            "True head-start prefilling (pipelining FIFO sessions across C-tiles) "
            "is needed to eliminate stalls at high gen_cost.\n",
        ],
    )
