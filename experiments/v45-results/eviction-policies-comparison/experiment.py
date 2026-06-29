from pathlib import Path
from experiments.harness import (
    Flags, Result, run_grid, top_bottom_table, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# Hardware + workload constants -- everything that does NOT vary across cells.
# This is the only place this experiment touches matrix shape / cache geometry.
BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, 
    "L1_SIZE_BYTES": 4096, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 8192, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
}

B_WIDTH = [96, 192, ]
DIMS = [4, 8, 16, 32]

def run() -> None:
    base_config = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="prng_mem", stationary="C", three_d_reg=True)
    flags = Flags(b_source="prng_mem", stationary="C", three_d_reg=True)
    blocks: list[str] = []
    for h,w,d in zip(DIMS_WIDTH, DIMS_DEPTH, DIM):
        print(f"\n--- {prec_name} ---")
        results: list[Result] = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base_config,
            base_overrides={**BASE_OVERRIDES, **prec_over},
            sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
            flags=flags,
        )
        blocks.append(top_bottom_table(
            title=prec_name,
            results=results,
            axis_keys=["TILE_M", "TILE_N", "TILE_K"],
        ))

    write_report(
        EXPERIMENT_DIR / "README.md",
        title="Your experiment title",
        blocks=blocks,
    )
