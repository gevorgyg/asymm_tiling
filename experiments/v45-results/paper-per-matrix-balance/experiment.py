"""H3: verify A/B DRAM contributions balance at predicted optimum (see WRITEUP.md)."""

import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path

from experiments.harness import (
    Flags, PALETTE_REGION, grid_plot, render_config, run_with_trace,
    summarize_config, workspace_root, write_report,
)
from experiments.harness.trace_analysis import TraceStats

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES_COMMON: dict[str, object] = {
    "A_HEIGHT_DIM": 512, "A_WIDTH_DIM": 512, "B_WIDTH_DIM": 512,
    "A_PRECISION_BYTES": 8,
    "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_K": 64,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

REGIMES = [
    ("L1=256K", {"L1_SIZE_BYTES": 262144, "L2_SIZE_BYTES": 524288}),
    ("L1=16K",  {"L1_SIZE_BYTES": 16384,  "L2_SIZE_BYTES": 65536}),
]

RHOS_AND_BPREC = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
TILE_DIMS = [4, 8, 16, 32, 64, 128, 256]
L2_LINE_BYTES = 64


def _predicted_opt_pair(rho: float) -> tuple[int, int]:
    """Smallest-area divisor pair whose T_N/T_M is closest to 1/ρ."""
    target = 1.0 / rho
    candidates = [
        (m, n) for m in TILE_DIMS for n in TILE_DIMS
    ]
    # rank by (distance to target ratio, area)
    candidates.sort(key=lambda mn: (abs(math.log2((mn[1] / mn[0]) / target)), mn[0] * mn[1]))
    return candidates[0]


def _square_pair_matching_area(opt_pair: tuple[int, int]) -> tuple[int, int]:
    """Pick the square (T_M=T_N) with area closest to opt_pair's."""
    target_area = opt_pair[0] * opt_pair[1]
    sq = sorted(TILE_DIMS, key=lambda d: abs(d * d - target_area))
    return sq[0], sq[0]


def _trace_dram_bytes(stats: TraceStats) -> dict[str, int]:
    return {name: rs.dram_accesses * L2_LINE_BYTES for name, rs in stats.regions.items()}


def _run_cell(base: str, full_overrides: dict, flags: Flags) -> tuple:
    config_text = render_config(base, full_overrides)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(config_text)
        tmp = Path(f.name)
    try:
        m, ts = run_with_trace(tmp, flags, full_overrides)
    finally:
        tmp.unlink(missing_ok=True)
    return m, ts


def _plot(records: list[dict], out: Path) -> None:
    panels: dict[str, list[dict]] = {}
    for regime_name, _ in REGIMES:
        for rho in (1.0, 0.5, 0.25, 0.125):
            key = f"{regime_name}, ρ={rho}"
            cell = [r for r in records if r["regime"] == regime_name and r["rho"] == rho]
            cell.sort(key=lambda r: 0 if r["kind"] == "predicted_opt" else 1)
            panels[key] = cell

    # only label bars (and call legend) on the very first panel; one shared legend
    legend_key = next(iter(panels))

    def panel_fn(ax, key, cell):
        if not cell:
            ax.set_title(f"{key} (no data)"); return
        labels = [f"{r['kind']}\n{r['pair'][0]}x{r['pair'][1]}" for r in cell]
        xs = list(range(len(cell)))
        bottoms = [0.0] * len(cell)
        any_nonzero = False
        for matrix in ("A", "B", "C"):
            vals = [r["per_matrix_dram"].get(matrix, 0) / 1024 for r in cell]
            any_nonzero = any_nonzero or any(v > 0 for v in vals)
            ax.bar(xs, vals, bottom=bottoms, color=PALETTE_REGION[matrix],
                   label=matrix if key == legend_key else None)
            bottoms = [b + v for b, v in zip(bottoms, vals)]
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(key)
        # avoid NaN tick-space when every bar is 0
        if not any_nonzero:
            ax.set_ylim(0, 1)
        ax.set_ylabel("DRAM (KB)")
        if key == legend_key:
            ax.legend(loc="upper right")

    grid_plot(panels, panel_fn=panel_fn, out_path=out, ncols=4,
              subplot_size=(4, 4),
              title=("H3: per-matrix DRAM at predicted optimum vs square\n"
                     + summarize_config(BASE_OVERRIDES_COMMON)))


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    cache_file = EXPERIMENT_DIR / "trace_results.json"
    cache: dict = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            cache = {}

    records: list[dict] = []
    for regime_name, regime_over in REGIMES:
        for rho, b_prec in RHOS_AND_BPREC:
            opt = _predicted_opt_pair(rho)
            sq = _square_pair_matching_area(opt)
            for kind, pair in [("predicted_opt", opt), ("square", sq)]:
                # skip the duplicate when ρ=1 (opt is square already)
                if kind == "square" and pair == opt and rho == 1.0:
                    continue
                key = f"{regime_name}|rho={rho}|kind={kind}|pair={pair[0]}x{pair[1]}"
                if key in cache:
                    rec = cache[key]
                    print(f"  cache hit  {key}")
                else:
                    print(f"  running    {key}")
                    overrides = {
                        **BASE_OVERRIDES_COMMON, **regime_over,
                        "B_PRECISION_BYTES": b_prec,
                        "TILE_M": pair[0], "TILE_N": pair[1],
                    }
                    metrics, ts = _run_cell(base, overrides, flags)
                    per_matrix = _trace_dram_bytes(ts)
                    rec = {
                        "regime": regime_name,
                        "rho": rho,
                        "kind": kind,
                        "pair": list(pair),
                        "total_dram_kb": metrics.l2.line_fills * L2_LINE_BYTES / 1024,
                        "per_matrix_dram": per_matrix,
                        "cycles": metrics.cycles,
                    }
                    cache[key] = rec
                    cache_file.write_text(json.dumps(cache, indent=2))
                records.append({**rec, "pair": tuple(rec["pair"])})

    _plot(records, EXPERIMENT_DIR / "per_matrix_dram.png")

    lines: list[str] = []
    lines.append("# Paper validation — per-matrix balance at optimum (H3)\n")
    lines.append("![Per-matrix DRAM](per_matrix_dram.png)\n")
    lines.append("\n## Balance table\n")
    lines.append("| regime | ρ | tile | A KB | B KB | C KB | A:B | total KB |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in records:
        a = r["per_matrix_dram"].get("A", 0) / 1024
        b = r["per_matrix_dram"].get("B", 0) / 1024
        c = r["per_matrix_dram"].get("C", 0) / 1024
        ab = a / b if b > 0 else float("inf")
        lines.append(
            f"| {r['regime']} | {r['rho']} | "
            f"{r['kind']}={r['pair'][0]}x{r['pair'][1]} | "
            f"{a:.1f} | {b:.1f} | {c:.1f} | {ab:.2f} | {r['total_dram_kb']:.1f} |"
        )
    write_report(EXPERIMENT_DIR / "README.md", "paper-per-matrix-balance", lines)
