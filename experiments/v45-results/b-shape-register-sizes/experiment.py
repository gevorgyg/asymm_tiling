import itertools
from pathlib import Path
from experiments.harness import (
    Flags, Result, run_grid, top_bottom_table, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, 
    "L1_SIZE_BYTES": 4096, "L1_LINE_SIZE_BYTES": 4, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 8192, "L2_LINE_SIZE_BYTES": 4, "L2_ASSOC": 8,
}

B_WIDTHS = [96, 192]
REG_DIMS = [2, 4, 8] 
TILE_CANDIDATES = [4, 8, 16, 32]

def run() -> None:
    base_config = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="prng_mem", stationary="C", three_d_reg=True)
    blocks: list[str] = []

    for b_width, reg_m, reg_n, reg_k in itertools.product(B_WIDTHS, REG_DIMS, REG_DIMS, REG_DIMS):
        valid_tile_m = [t for t in TILE_CANDIDATES if t % reg_m == 0]
        valid_tile_n = [t for t in TILE_CANDIDATES if t % reg_n == 0]
        valid_tile_k = [t for t in TILE_CANDIDATES if t % reg_k == 0]

        # Skip this combination entirely if any axis has no valid tile sizes
        if not (valid_tile_m and valid_tile_n and valid_tile_k):
            continue
            
        title = f"B={b_width} | REG=({reg_m},{reg_n},{reg_k})"
        print(f"\n--- {title} ---")
        
        current_overrides = {
            **BASE_OVERRIDES, 
            "B_WIDTH_DIM": b_width,
            "REG_M": reg_m, 
            "REG_N": reg_n, 
            "REG_K": reg_k
        }
        
        results: list[Result] = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base_config,
            base_overrides=current_overrides,
            sweep_axes={
                "TILE_M": valid_tile_m, 
                "TILE_N": valid_tile_n, 
                "TILE_K": valid_tile_k
            },
            flags=flags,
        )
        
        blocks.append(top_bottom_table(
            title=title,
            results=results,
            axis_keys=["TILE_M", "TILE_N", "TILE_K"],
        ))

    write_report(
        EXPERIMENT_DIR / "README.md",
        title="Register, B-Shape, and Tile Sweep",
        blocks=blocks,
    )
