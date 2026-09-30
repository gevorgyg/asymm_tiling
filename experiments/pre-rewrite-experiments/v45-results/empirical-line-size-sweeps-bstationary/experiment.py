"""Line-size sweep (L1=L2), 96^3, B-stationary: best tile per line size."""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, describe_changes, plot_metric_family,
    run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_SIZE_BYTES": 16384, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 65536, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14,
}

PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
    ("Symmetric Single", {"A_PRECISION_BYTES": 4, "B_PRECISION_BYTES": 4}),
]

DIMS = [8, 12, 16, 24, 32, 48, 96]
LINE_SIZES = [16, 32, 64, 128]

TITLE = "Line-size sweep, best tile per line size (96³, B-stationary)"
BASE_NAME = "line_size_sweep_bstat"


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="B", three_d_reg=True)

    cells: list[Cell] = []
    records: list[dict] = []
    for prec_name, prec_over in PRECISIONS:
        for line in LINE_SIZES:
            print(f"\n--- {prec_name} / {line}B lines ---")
            duals = run_grid_dual(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={**BASE_OVERRIDES, **prec_over,
                                "L1_LINE_SIZE_BYTES": line,
                                "L2_LINE_SIZE_BYTES": line},
                sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
                flags=flags,
            )
            for d in duals:
                cells.append(Cell(x=math.log2(line), series=prec_name,
                                  traffic=d.traffic, cycles=d.cycles))
                records.append({"precision": prec_name,
                                "point": f"{line}B", "d": d})

    caption = describe_changes(BASE_OVERRIDES, base)
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name=BASE_NAME,
        title=TITLE, caption=caption, xlabel="log₂(line bytes)",
    )

    lines = [f"Non-default config: {caption or '(all defaults)'}\n",
             "Each x point takes the best (minimum) value over all tile shapes.\n"]
    lines += [f"![{k}]({BASE_NAME}_{k}.png)\n" for k in METRICS]
    lines.append("\n## Best cell per metric\n")
    lines.append("| metric | precision | line | tile (M×N×K) | value |")
    lines.append("|---|---|---|---|---|")
    for key, (_, extract) in METRICS.items():
        for prec_name, _ in PRECISIONS:
            rs = [r for r in records if r["precision"] == prec_name]
            best = min(rs, key=lambda r: extract(
                r["d"].cycles if key == "cycles" else r["d"].traffic))
            m = best["d"].cycles if key == "cycles" else best["d"].traffic
            tile = "×".join(str(best["d"].overrides[k])
                            for k in ("TILE_M", "TILE_N", "TILE_K"))
            lines.append(f"| {key} | {prec_name} | {best['point']} | {tile} "
                         f"| {extract(m):,.0f} |")
    write_report(EXPERIMENT_DIR / "README.md", TITLE, ["\n".join(lines)])
