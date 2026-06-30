"""H2: empirical optimum shifts left of 1/ρ at constrained L1 (see WRITEUP.md)."""

import json
import math
from pathlib import Path

from experiments.harness import (
    Flags, PALETTE_RHO, Result, lineplot, run_grid, summarize_config,
    workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# 512^3 matmul, M = 16K / 8 = 2K C-entries; mn = 262144 >> M, highly constrained
BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 512, "A_WIDTH_DIM": 512, "B_WIDTH_DIM": 512,
    "A_PRECISION_BYTES": 8,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_K": 64,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

RHOS_AND_BPREC = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
TILE_DIMS = [4, 8, 16, 32, 64, 128, 256]
L2_LINE_BYTES = BASE_OVERRIDES["L2_LINE_SIZE_BYTES"]


def _dram(metrics) -> int:
    return metrics.l2.line_fills * L2_LINE_BYTES


def _curve(results: list[Result]) -> dict[float, dict]:
    by_ratio: dict[float, list[Result]] = {}
    for r in results:
        m, n = int(r.overrides["TILE_M"]), int(r.overrides["TILE_N"])
        by_ratio.setdefault(n / m, []).append(r)
    return {
        ratio: {
            "dram_min": min(_dram(r.metrics) for r in rs),
            "pair": (lambda r: (int(r.overrides["TILE_M"]), int(r.overrides["TILE_N"])))(
                min(rs, key=lambda r: _dram(r.metrics))
            ),
        }
        for ratio, rs in by_ratio.items()
    }


def _empirical_opt_log2_ratio(curve: dict) -> float:
    opt = min(curve, key=lambda r: curve[r]["dram_min"])
    return math.log2(opt)


def _plot_curves(per_rho: dict, out: Path) -> None:
    series = {
        f"ρ = {rho}": [(math.log2(r), curve[r]["dram_min"] / 1024) for r in sorted(curve)]
        for rho, curve in per_rho.items()
    }
    vlines = {f"ρ = {rho}": math.log2(1 / rho) for rho in per_rho}
    colors = {f"ρ = {rho}": PALETTE_RHO[rho] for rho in per_rho}
    lineplot(
        series, out_path=out, vlines=vlines, colors=colors,
        xlabel="log₂(T_N / T_M)", ylabel="DRAM (KB)",
        title=("H2: DRAM vs aspect ratio (dashed = predicted optimum 1/ρ)\n"
               + summarize_config(BASE_OVERRIDES)),
    )


def _plot_shift(per_rho_shift: dict, out: Path) -> None:
    rhos = sorted(per_rho_shift)
    series = {"shift": [(math.log2(r), per_rho_shift[r]) for r in rhos]}
    lineplot(
        series, out_path=out,
        xlabel="log₂(ρ)", ylabel="log₂(empirical opt) − log₂(predicted opt)",
        title=("H2: leftward shift of empirical optimum vs ρ "
               "(negative = empirical is left of predicted)\n"
               + summarize_config(BASE_OVERRIDES)),
        figsize=(8, 5),
    )


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    per_rho_curve: dict[float, dict] = {}
    per_rho_shift: dict[float, float] = {}

    for rho, b_prec in RHOS_AND_BPREC:
        print(f"\n=== ρ = {rho} (B={b_prec} B) ===")
        results = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**BASE_OVERRIDES, "B_PRECISION_BYTES": b_prec},
            sweep_axes={"TILE_M": TILE_DIMS, "TILE_N": TILE_DIMS},
            flags=flags,
            cache_path=EXPERIMENT_DIR / f"results_rho_{b_prec}b.json",
        )
        curve = _curve(results)
        per_rho_curve[rho] = curve
        emp_log2 = _empirical_opt_log2_ratio(curve)
        per_rho_shift[rho] = emp_log2 - math.log2(1 / rho)

    _plot_curves(per_rho_curve, EXPERIMENT_DIR / "dram_vs_aspect_ratio.png")
    _plot_shift(per_rho_shift, EXPERIMENT_DIR / "shift_vs_rho.png")

    lines: list[str] = []
    lines.append("# Paper validation — constrained shift (H2)\n")
    lines.append("![Shift vs ρ](shift_vs_rho.png)\n")
    lines.append("![DRAM vs aspect ratio](dram_vs_aspect_ratio.png)\n")
    lines.append("\n## Shift per ρ\n")
    lines.append("| ρ | predicted log₂ | empirical log₂ | shift |")
    lines.append("|---|---|---|---|")
    for rho, _ in RHOS_AND_BPREC:
        pred = math.log2(1 / rho)
        emp = pred + per_rho_shift[rho]
        lines.append(f"| {rho} | {pred:+.2f} | {emp:+.2f} | {per_rho_shift[rho]:+.2f} |")
    write_report(EXPERIMENT_DIR / "README.md", "paper-rho-shift-constrained", lines)
    (EXPERIMENT_DIR / "shifts.json").write_text(json.dumps(per_rho_shift, indent=2))
