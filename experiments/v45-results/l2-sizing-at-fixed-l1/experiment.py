"""sweep L2/L1 ratio at fixed L1 sizes to find L2's diminishing-returns point."""

import json
import math
from pathlib import Path

from experiments.harness import (
    Flags, Result, lineplot, run_grid, summarize_config,
    workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_K": 96,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

L1_SIZES   = [8192, 16384, 32768]
L2_RATIOS  = [1, 2, 4, 8, 16, 64]
PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
]
TILE_DIMS  = [4, 8, 12, 16, 24, 32, 48]
L2_LINE_BYTES = BASE_OVERRIDES["L2_LINE_SIZE_BYTES"]


def _best(results: list[Result]) -> tuple[int, int]:
    """Return (best cycles, DRAM bytes at that cell)."""
    best = min(results, key=lambda r: r.metrics.cycles)
    return best.metrics.cycles, best.metrics.l2.line_fills * L2_LINE_BYTES


def _plot(metric_per_l1: dict, key: str, ylabel: str, out: Path) -> None:
    series = {
        f"{prec}, L1={l1 // 1024}K": [(math.log2(r), curve[r][key]) for r in sorted(curve)]
        for (prec, l1), curve in metric_per_l1.items()
    }
    # cache geometry varies inside the sweep; show the invariant bits in the title
    summary = summarize_config({k: v for k, v in BASE_OVERRIDES.items()
                                if not k.startswith(("L1_SIZE", "L2_SIZE"))})
    lineplot(
        series, out_path=out,
        xlabel="log₂(L2 / L1)", ylabel=ylabel,
        title=f"{ylabel} vs L2/L1 ratio (best tile per cell)\n{summary}",
    )


def _elbow(curve: dict[int, dict], threshold: float = 0.05) -> int:
    """First L2/L1 ratio above which extra L2 gains <`threshold` of cycles."""
    sorted_ratios = sorted(curve)
    if not sorted_ratios:
        return -1
    prev = curve[sorted_ratios[0]]["cycles"]
    for r in sorted_ratios[1:]:
        cur = curve[r]["cycles"]
        if prev - cur < threshold * prev:
            return r
        prev = cur
    return sorted_ratios[-1]


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    # metric_per_l1[(prec, l1)] -> {ratio: {cycles, dram_kb}}
    metric_per_l1: dict[tuple[str, int], dict[int, dict]] = {}

    for prec, prec_over in PRECISIONS:
        for l1 in L1_SIZES:
            for ratio in L2_RATIOS:
                l2 = l1 * ratio
                print(f"\n=== {prec} | L1={l1//1024}K | L2/L1={ratio} (L2={l2//1024}K) ===")
                results = run_grid(
                    experiment_dir=EXPERIMENT_DIR,
                    base_config_text=base,
                    base_overrides={
                        **BASE_OVERRIDES, **prec_over,
                        "L1_SIZE_BYTES": l1, "L2_SIZE_BYTES": l2,
                    },
                    sweep_axes={"TILE_M": TILE_DIMS, "TILE_N": TILE_DIMS},
                    flags=flags,
                    cache_path=EXPERIMENT_DIR / f"results_{prec.replace(' ', '_')}_L1_{l1}_L2_{l2}.json",
                )
                cycles, dram_bytes = _best(results)
                metric_per_l1.setdefault((prec, l1), {})[ratio] = {
                    "cycles": cycles, "dram_kb": dram_bytes / 1024,
                }

    _plot(metric_per_l1, "cycles", "cycles (best tile)",
          EXPERIMENT_DIR / "cycles_vs_l2.png")
    _plot(metric_per_l1, "dram_kb", "DRAM (KB, best tile)",
          EXPERIMENT_DIR / "dram_vs_l2.png")

    lines: list[str] = []
    lines.append("# l2-sizing-at-fixed-l1\n")
    lines.append("![Cycles vs L2/L1](cycles_vs_l2.png)\n")
    lines.append("![DRAM vs L2/L1](dram_vs_l2.png)\n")
    lines.append("\n## Elbow (smallest L2/L1 with <5% cycle gain from the next-larger L2)\n")
    lines.append("| precision | L1 | elbow L2/L1 |")
    lines.append("|---|---|---|")
    for (prec, l1), curve in metric_per_l1.items():
        lines.append(f"| {prec} | {l1 // 1024}K | {_elbow(curve)}× |")
    write_report(EXPERIMENT_DIR / "README.md", "l2-sizing-at-fixed-l1", lines)
    (EXPERIMENT_DIR / "metric_per_l1.json").write_text(json.dumps({
        f"{p}|{l}": {str(k): v for k, v in c.items()}
        for (p, l), c in metric_per_l1.items()
    }, indent=2))
