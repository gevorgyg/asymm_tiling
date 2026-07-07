"""Tile-shape sweep including the matrix-spanning dim 96, C-stationary.

Same shape as empirical-tile-sweeps but the tile grid includes 96, so
degenerate strips (full-height / full-width tiles) participate.
"""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, describe_changes, plot_metric_family,
    run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14,
}

PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
    ("Symmetric Single", {"A_PRECISION_BYTES": 4, "B_PRECISION_BYTES": 4}),
]

DIMS = [8, 12, 16, 24, 32, 48, 96]

TITLE = "Tile-shape sweep incl. matrix-spanning tiles (96³, C-stationary)"
BASE_NAME = "tile_sweep_96"


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    cells: list[Cell] = []
    records: list[dict] = []
    for prec_name, prec_over in PRECISIONS:
        print(f"\n--- {prec_name} ---")
        duals = run_grid_dual(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**BASE_OVERRIDES, **prec_over},
            sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
            flags=flags,
        )
        for d in duals:
            tm, tn = int(d.overrides["TILE_M"]), int(d.overrides["TILE_N"])
            cells.append(Cell(x=math.log2(tn / tm), series=prec_name,
                              traffic=d.traffic, cycles=d.cycles))
            records.append({"precision": prec_name, "d": d})

    caption = describe_changes(BASE_OVERRIDES, base)
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name=BASE_NAME,
        title=TITLE, caption=caption, xlabel="log₂(TILE_N / TILE_M)",
    )

    lines = [f"Non-default config: {caption}\n",
             "Points sharing an aspect ratio take the best (minimum) value.\n"]
    lines += [f"![{k}]({BASE_NAME}_{k}.png)\n" for k in METRICS]
    lines.append("\n## Best tile per metric\n")
    lines.append("| metric | precision | tile (M×N×K) | value |")
    lines.append("|---|---|---|---|")
    for key, (_, extract) in METRICS.items():
        for prec_name, _ in PRECISIONS:
            rs = [r["d"] for r in records if r["precision"] == prec_name]
            best = min(rs, key=lambda d: extract(d.cycles if key == "cycles" else d.traffic))
            v = extract(best.cycles if key == "cycles" else best.traffic)
            tile = "×".join(str(best.overrides[k]) for k in ("TILE_M", "TILE_N", "TILE_K"))
            lines.append(f"| {key} | {prec_name} | {tile} | {v:,.0f} |")
    write_report(EXPERIMENT_DIR / "README.md", TITLE, ["\n".join(lines)])
