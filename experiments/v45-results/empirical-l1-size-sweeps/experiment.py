"""Sweep L1 size across tile shapes, 3 precisions, C-stationary."""

from pathlib import Path

from experiments.harness import (
    Flags, Result, run_grid, top_bottom_table, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
}

PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
    ("Symmetric Single", {"A_PRECISION_BYTES": 4, "B_PRECISION_BYTES": 4}),
]

DIMS     = [8, 12, 16, 24, 32, 48, 96]
L1_SIZES = [4096, 8192, 16384, 32768, 65536]


def run() -> None:
    base_config = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    blocks: list[str] = []
    for size in L1_SIZES:
        for prec_name, prec_over in PRECISIONS:
            print(f"\n--- L1={size}B  {prec_name} ---")
            results: list[Result] = run_grid(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base_config,
                base_overrides={**BASE_OVERRIDES, **prec_over,
                                "L1_SIZE_BYTES": size},
                sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
                flags=flags,
            )
            blocks.append(top_bottom_table(
                title=f"L1={size}B -- {prec_name}",
                results=results,
                axis_keys=["TILE_M", "TILE_N", "TILE_K"],
            ))

    write_report(
        EXPERIMENT_DIR / "README.md",
        title="L1 Size Sweep (C-stationary)",
        blocks=blocks,
    )
