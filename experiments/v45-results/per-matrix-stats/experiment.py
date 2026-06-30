"""Per-region A/B/C hit-rate and DRAM decomposition from traces."""

import json
import math
import tempfile
from pathlib import Path

from experiments.harness import (
    Flags, PALETTE_REGION, grid_plot, render_config, run_with_trace,
    summarize_config, workspace_root, write_report,
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

REGIMES = [
    ("L1=16K", {"L1_SIZE_BYTES": 16384, "L2_SIZE_BYTES": 65536}),
    ("L1=64K", {"L1_SIZE_BYTES": 65536, "L2_SIZE_BYTES": 262144}),
]
PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
]
TILE_DIMS = [4, 8, 12, 16, 24, 32, 48]
L2_LINE_BYTES = 64


def _cache_path(regime: str, precision: str) -> Path:
    return EXPERIMENT_DIR / f"results_{regime}_{precision.replace(' ', '_')}.json"


def _by_ratio(rows: list[dict]) -> dict[float, list[dict]]:
    out: dict[float, list[dict]] = {}
    for r in rows:
        out.setdefault(r["ratio"], []).append(r)
    return out


def _plot_hit_rates(by_panel: dict, out: Path) -> None:
    def panel_fn(ax, key, rows_):
        by_ratio = _by_ratio(rows_)
        ratios = sorted(by_ratio)
        for matrix in ("A", "B", "C"):
            xs = [math.log2(r) for r in ratios]
            ys = []
            for r in ratios:
                vals = [
                    (c["per_matrix"][matrix]["l1_hit_rate"]
                     if c["per_matrix"][matrix]["l1_lookups"] > 0 else 0.0)
                    for c in by_ratio[r]
                ]
                ys.append(sum(vals) / len(vals))
            ax.plot(xs, ys, marker="o", color=PALETTE_REGION[matrix], label=matrix)
        ax.set_xlabel("log₂(T_N / T_M)")
        ax.set_ylabel("L1 hit rate")
        ax.set_title(str(key))
        ax.set_ylim(0, 1.02)
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend()

    grid_plot(by_panel, panel_fn=panel_fn, out_path=out,
              ncols=2, subplot_size=(6.5, 4),
              title=("Per-matrix L1 hit rate (avg over tile pairs sharing a ratio)\n"
                     + summarize_config(BASE_OVERRIDES)))


def _plot_dram_shares(by_panel: dict, out: Path) -> None:
    def panel_fn(ax, key, rows_):
        by_ratio = _by_ratio(rows_)
        ratios = sorted(by_ratio)
        xs = [math.log2(r) for r in ratios]
        shares = {"A": [], "B": [], "C": []}
        for r in ratios:
            cells = by_ratio[r]
            tot_per = {m: sum(c["per_matrix"][m]["dram_bytes"] for c in cells) / len(cells)
                       for m in ("A", "B", "C")}
            tot = sum(tot_per.values()) or 1
            for m in ("A", "B", "C"):
                shares[m].append(tot_per[m] / tot)
        ax.stackplot(xs, shares["A"], shares["B"], shares["C"],
                     colors=[PALETTE_REGION[m] for m in ("A", "B", "C")],
                     labels=["A", "B", "C"])
        ax.set_xlabel("log₂(T_N / T_M)")
        ax.set_ylabel("share of DRAM bytes")
        ax.set_title(str(key))
        ax.legend(loc="upper right")

    grid_plot(by_panel, panel_fn=panel_fn, out_path=out,
              ncols=2, subplot_size=(6.5, 4),
              title="Per-matrix DRAM share\n" + summarize_config(BASE_OVERRIDES))


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    by_panel: dict[tuple[str, str], list[dict]] = {}

    for regime_name, regime_over in REGIMES:
        for prec_name, prec_over in PRECISIONS:
            cache_p = _cache_path(regime_name, prec_name)
            cache: dict = {}
            if cache_p.exists():
                try:
                    cache = json.loads(cache_p.read_text())
                except json.JSONDecodeError:
                    cache = {}
            print(f"\n=== {regime_name} / {prec_name} ===")
            for tm in TILE_DIMS:
                for tn in TILE_DIMS:
                    key = f"{tm}x{tn}"
                    if key in cache:
                        rec = cache[key]
                        print(f"  cache hit  {key}")
                    else:
                        overrides = {
                            **BASE_OVERRIDES, **regime_over, **prec_over,
                            "TILE_M": tm, "TILE_N": tn,
                        }
                        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
                            f.write(render_config(base, overrides))
                            tmp = Path(f.name)
                        try:
                            _, ts = run_with_trace(tmp, flags, overrides)
                        finally:
                            tmp.unlink(missing_ok=True)
                        per_matrix = {}
                        for name, rs in ts.regions.items():
                            hr = (rs.l1_hits / rs.l1_lookups) if rs.l1_lookups else 0.0
                            per_matrix[name] = {
                                "l1_lookups": rs.l1_lookups,
                                "l1_hits":    rs.l1_hits,
                                "l1_hit_rate": hr,
                                "dram_bytes": rs.dram_accesses * L2_LINE_BYTES,
                            }
                        rec = {"tile_m": tm, "tile_n": tn,
                               "ratio": tn / tm, "per_matrix": per_matrix}
                        cache[key] = rec
                        cache_p.write_text(json.dumps(cache, indent=2))
                        print(f"  ran        {key}")
                    by_panel.setdefault((regime_name, prec_name), []).append(rec)

    _plot_hit_rates(by_panel, EXPERIMENT_DIR / "hit_rate_per_matrix.png")
    _plot_dram_shares(by_panel, EXPERIMENT_DIR / "dram_share_per_matrix.png")

    lines: list[str] = []
    lines.append("# per-matrix-stats\n")
    lines.append("![Hit rate per matrix](hit_rate_per_matrix.png)\n")
    lines.append("![DRAM share per matrix](dram_share_per_matrix.png)\n")
    write_report(EXPERIMENT_DIR / "README.md", "per-matrix-stats", lines)
