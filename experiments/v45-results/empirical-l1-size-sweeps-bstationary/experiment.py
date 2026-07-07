"""L1-size sweep, 96^3, B-stationary: best tile shape per L1 size."""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, describe_changes, plot_metric_family,
    run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14,
}

PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
    ("Symmetric Single", {"A_PRECISION_BYTES": 4, "B_PRECISION_BYTES": 4}),
]

DIMS = [8, 12, 16, 24, 32, 48, 96]
L1_SIZES = [4096, 8192, 16384, 32768, 65536]

TITLE = "L1-size sweep, best tile per size (96³, B-stationary)"
BASE_NAME = "l1_size_sweep_bstat"


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="B", three_d_reg=True)

    cells: list[Cell] = []
    records: list[dict] = []
    for prec_name, prec_over in PRECISIONS:
        for l1 in L1_SIZES:
            print(f"\n--- {prec_name} / L1={l1 // 1024}K ---")
            duals = run_grid_dual(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={**BASE_OVERRIDES, **prec_over,
                                "L1_SIZE_BYTES": l1},
                sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
                flags=flags,
            )
            for d in duals:
                cells.append(Cell(x=math.log2(l1 / 1024), series=prec_name,
                                  traffic=d.traffic, cycles=d.cycles))
                records.append({"precision": prec_name,
                                "point": f"L1={l1 // 1024}K", "d": d})

    caption = describe_changes(BASE_OVERRIDES, base)
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name=BASE_NAME,
        title=TITLE, caption=caption, xlabel="log₂(L1 KiB)",
    )

    lines = [f"Non-default config: {caption}\n",
             "Each x point takes the best (minimum) value over all tile shapes.\n"]
    lines += [f"![{k}]({BASE_NAME}_{k}.png)\n" for k in METRICS]
    lines.append("\n## Best cell per metric\n")
    lines.append("| metric | precision | L1 | tile (M×N×K) | value |")
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
