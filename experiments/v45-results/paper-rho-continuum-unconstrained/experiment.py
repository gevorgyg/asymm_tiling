"""H1: verify T_N/T_M = 1/ρ at unconstrained L1 (see WRITEUP.md)."""

import json
import math
from pathlib import Path

from experiments.harness import (
    Flags, PALETTE_RHO, Result, lineplot, run_grid, summarize_config,
    workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# 512^3 matmul, M = 256K / 8 = 32K C-entries; mn = 262144 >> M so tiling matters
BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 512, "A_WIDTH_DIM": 512, "B_WIDTH_DIM": 512,
    "A_PRECISION_BYTES": 8,
    "L1_SIZE_BYTES": 262144, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_SIZE_BYTES": 524288, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_K": 64,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

RHOS_AND_BPREC = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
TILE_DIMS = [4, 8, 16, 32, 64, 128, 256]  # divisors of 512 ∩ multiples of 4
L2_LINE_BYTES = BASE_OVERRIDES["L2_LINE_SIZE_BYTES"]


def _dram_bytes(metrics) -> int:
    return metrics.l2.line_fills * L2_LINE_BYTES


def _curve(results: list[Result]) -> dict[float, dict]:
    """Map aspect ratio T_N/T_M -> {dram_bytes_min, pair_min, square_dram_at_same_area}."""
    by_ratio: dict[float, list[Result]] = {}
    for r in results:
        m, n = int(r.overrides["TILE_M"]), int(r.overrides["TILE_N"])
        by_ratio.setdefault(n / m, []).append(r)
    out = {}
    for ratio, rs in by_ratio.items():
        best = min(rs, key=lambda x: _dram_bytes(x.metrics))
        out[ratio] = {
            "dram_min": _dram_bytes(best.metrics),
            "pair": (int(best.overrides["TILE_M"]), int(best.overrides["TILE_N"])),
            "cycles": best.metrics.cycles,
        }
    return out


def _square_dram(results: list[Result]) -> int:
    """The DRAM at the best square tile T_M=T_N."""
    squares = [r for r in results if r.overrides["TILE_M"] == r.overrides["TILE_N"]]
    return min(_dram_bytes(r.metrics) for r in squares)


def _plot(per_rho: dict, out_path: Path) -> None:
    series = {
        f"ρ = {rho}": [(math.log2(r), curve[r]["dram_min"] / 1024) for r in sorted(curve)]
        for rho, curve in per_rho.items()
    }
    vlines = {f"ρ = {rho}": math.log2(1 / rho) for rho in per_rho}
    colors = {f"ρ = {rho}": PALETTE_RHO[rho] for rho in per_rho}
    lineplot(
        series, out_path=out_path, vlines=vlines, colors=colors,
        xlabel="log₂(T_N / T_M)", ylabel="DRAM (KB)",
        title=("H1: DRAM vs aspect ratio (dashed = predicted optimum 1/ρ)\n"
               + summarize_config(BASE_OVERRIDES)),
    )


def _analytical_speedup(rho: float) -> float:
    return (1 + rho) / (2 * math.sqrt(rho))


def _empirical_speedup(curve: dict, square_dram: int) -> tuple[float, float]:
    opt_ratio = min(curve, key=lambda r: curve[r]["dram_min"])
    opt_dram = curve[opt_ratio]["dram_min"]
    return square_dram / opt_dram, opt_ratio


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    per_rho_curve: dict[float, dict] = {}
    per_rho_square_dram: dict[float, int] = {}

    for rho, b_prec in RHOS_AND_BPREC:
        print(f"\n=== ρ = {rho} (B_PRECISION_BYTES = {b_prec}) ===")
        results = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**BASE_OVERRIDES, "B_PRECISION_BYTES": b_prec},
            sweep_axes={"TILE_M": TILE_DIMS, "TILE_N": TILE_DIMS},
            flags=flags,
            cache_path=EXPERIMENT_DIR / f"results_rho_{b_prec}b.json",
        )
        per_rho_curve[rho] = _curve(results)
        per_rho_square_dram[rho] = _square_dram(results)

    _plot(per_rho_curve, EXPERIMENT_DIR / "dram_vs_aspect_ratio.png")

    lines: list[str] = []
    lines.append("# Paper validation — unconstrained continuum (H1)\n")
    lines.append("![DRAM vs aspect ratio](dram_vs_aspect_ratio.png)\n")
    lines.append("\n## Speedup vs square tiles\n")
    lines.append("| ρ | predicted optimum log₂(1/ρ) | empirical optimum log₂ | analytical speedup | measured speedup |")
    lines.append("|---|---|---|---|---|")
    for rho, b_prec in RHOS_AND_BPREC:
        curve = per_rho_curve[rho]
        sq = per_rho_square_dram[rho]
        emp_speedup, emp_ratio = _empirical_speedup(curve, sq)
        # measured speedup convention: dram_at_square / dram_at_opt  →  higher is better
        lines.append(
            f"| {rho} | {math.log2(1 / rho):+.2f} | {math.log2(emp_ratio):+.2f} | "
            f"{1 / _analytical_speedup(rho):.3f} | {1 / emp_speedup:.3f} |"
        )
    # the analytical formula (1+ρ)/(2√ρ) is the **traffic ratio** opt/square (<=1),
    # so we report its reciprocal (>=1) to keep "speedup" in the conventional direction.

    write_report(EXPERIMENT_DIR / "README.md", "paper-rho-continuum-unconstrained", lines)
    # also dump raw curves for downstream consumers
    (EXPERIMENT_DIR / "curves.json").write_text(json.dumps({
        str(rho): {str(k): v for k, v in c.items()}
        for rho, c in per_rho_curve.items()
    }, indent=2))
