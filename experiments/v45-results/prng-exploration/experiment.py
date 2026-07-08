"""Sweep PRNG-FIFO parameters one knob at a time, C- vs B-stationary.

Fixed FIFO workload (m=128, n=512, k=64, tile 32×128 at the predicted aspect
4, equal 8 B precision). From a parity baseline (A's per-element DRAM cost =
B's per-element generation cost = 20 cycles, 8 B seed, 64-deep FIFO) each knob
is swept alone while the others stay at baseline. Both loop orders are plotted
so the effect of each knob on the recompute-vs-fetch balance is visible.

Knobs:
  MEM_ACCESS_CYCLES     -- A's DRAM cost (per line; /8 per element)
  PRNG_FIFO_GEN_COST    -- B's generation cost per element
  PRNG_FIFO_SEED_BYTES  -- seed storage read per B tile
  PRNG_FIFO_CAPACITY    -- FIFO depth (governs generation stalls)
"""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, PALETTE_POLICY, describe_changes, lineplot,
    plot_metric_family, run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

M, N, K = 128, 512, 64
PREC, LINE = 8, 64
TILE_M, TILE_N = 32, 128     # aspect 4

BASELINE: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": PREC, "B_PRECISION_BYTES": PREC,
    "L1_SIZE_BYTES": 4096, "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 16384, "L2_LINE_SIZE_BYTES": LINE, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14,
    "MEM_ACCESS_CYCLES": 160,      # 20 cyc/element at 8 elems/line
    "PRNG_FIFO_GEN_COST": 20,      # matched: 20 cyc/element
    "PRNG_FIFO_CAPACITY": 64,
    "PRNG_FIFO_SEED_BYTES": 8,
    "TILE_M": TILE_M, "TILE_N": TILE_N, "TILE_K": K,
}

KNOBS: dict[str, list[int]] = {
    "MEM_ACCESS_CYCLES":    [40, 80, 160, 320, 640],
    "PRNG_FIFO_GEN_COST":   [5, 10, 20, 40, 80],
    "PRNG_FIFO_SEED_BYTES": [4, 8, 16, 32, 64, 128],
    "PRNG_FIFO_CAPACITY":   [1, 4, 16, 64, 256],
}

STATIONARY = [("C-stationary", "C"), ("B-stationary", "B")]
SERIES_COLOR = {"C-stationary": PALETTE_POLICY["LRU"],
                "B-stationary": PALETTE_POLICY["MRU"]}


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    caption = describe_changes(
        {k: v for k, v in BASELINE.items()
         if k not in ("TILE_M", "TILE_N", "TILE_K")},
        base, extras={"tile": f"{TILE_M}×{TILE_N}×{K}", "B": "FIFO"})

    stall_rows: dict[str, list] = {name: [] for name, _ in STATIONARY}

    for knob, values in KNOBS.items():
        cells: list[Cell] = []
        for name, stat in STATIONARY:
            flags = Flags(b_source="prng_fifo", stationary=stat, three_d_reg=True)
            for v in values:
                duals = run_grid_dual(
                    experiment_dir=EXPERIMENT_DIR,
                    base_config_text=base,
                    base_overrides={**BASELINE, knob: v},
                    flags=flags,
                    cache_path=EXPERIMENT_DIR / f"results_{knob}.json",
                )
                d = duals[0]
                cells.append(Cell(x=math.log2(v), series=name,
                                  traffic=d.traffic, cycles=d.cycles))
                if knob == "PRNG_FIFO_CAPACITY":
                    fifo = d.traffic.prng_fifo
                    stall_rows[name].append(
                        (math.log2(v), fifo.stall_cycles if fifo else 0))

        plot_metric_family(
            cells, out_dir=EXPERIMENT_DIR, base_name=f"knob_{knob}",
            title=f"PRNG exploration — sweep {knob}",
            caption=caption, xlabel=f"log₂({knob})",
            colors=SERIES_COLOR,
        )

    lineplot(
        {name: sorted(rows) for name, rows in stall_rows.items()},
        out_path=EXPERIMENT_DIR / "fifo_stall_cycles_vs_capacity.png",
        colors=SERIES_COLOR,
        xlabel="log₂(PRNG_FIFO_CAPACITY)", ylabel="FIFO stall cycles",
        title=f"FIFO stalls vs buffer depth\n{caption}",
    )

    lines = [f"Non-default config: {caption}\n",
             "Parity baseline: A DRAM cost = B generation cost = 20 cyc/element. "
             "Each knob swept alone; both loop orders shown.\n"]
    for knob in KNOBS:
        lines.append(f"\n### sweep {knob}\n")
        for k in METRICS:
            lines.append(f"![{knob} {k}](knob_{knob}_{k}.png)\n")
    lines.append("\n### FIFO stalls vs capacity\n")
    lines.append("![stalls](fifo_stall_cycles_vs_capacity.png)\n")
    write_report(EXPERIMENT_DIR / "README.md", "prng-exploration",
                 ["\n".join(lines)])
