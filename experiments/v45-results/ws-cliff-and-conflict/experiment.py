"""Fine L1 sweep around WS; per-set evict heatmap (see WRITEUP.md)."""

import json
import tempfile
from pathlib import Path

from experiments.harness import (
    Flags, grid_plot, lineplot, render_config, run_with_trace,
    summarize_config, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# Fixed tile (chosen so its WS is awkward enough that several L1 sizes bracket it)
TILE_M, TILE_N, TILE_K = 16, 16, 96
A_PRECISION, B_PRECISION = 8, 2          # Asymmetric, C_prec = 8
WS_BYTES = TILE_M * TILE_K * A_PRECISION + TILE_K * TILE_N * B_PRECISION + TILE_M * TILE_N * max(A_PRECISION, B_PRECISION)

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "A_PRECISION_BYTES": A_PRECISION, "B_PRECISION_BYTES": B_PRECISION,
    "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_SIZE_BYTES": 4 * WS_BYTES * 4, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_M": TILE_M, "TILE_N": TILE_N, "TILE_K": TILE_K,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}


def _round_up_to_unit(b: int, unit: int = 512) -> int:
    """L1 size must be a multiple of line_size * assoc = 512 for our setup."""
    return ((b + unit - 1) // unit) * unit


def _sweep_l1_sizes() -> list[int]:
    """0.5·WS to 4·WS in 1/16-WS increments, snapped to unit."""
    sizes = sorted({_round_up_to_unit(WS_BYTES * x // 16) for x in range(8, 65)})
    return sizes


def _plot_cliff(records: list[dict], out: Path) -> None:
    rs = sorted(records, key=lambda r: r["l1_bytes"])
    series = {"hit rate": [(r["l1_bytes"] / WS_BYTES, r["l1_hit_rate"]) for r in rs]}
    # L1_SIZE is swept; show everything else from BASE_OVERRIDES
    summary = summarize_config(
        {k: v for k, v in BASE_OVERRIDES.items() if not k.startswith("L1_SIZE")},
        extras={"tile": f"{TILE_M}x{TILE_N}x{TILE_K}", "WS": f"{WS_BYTES}B"},
    )
    lineplot(
        series, out_path=out,
        vlines={"hit rate": 1.0},
        xlabel="L1 size / working set", ylabel="L1 hit rate",
        title=f"Hit-rate cliff\n{summary}",
    )


def _plot_heatmap(records: list[dict], out: Path) -> None:
    targets = [0.5, 1.0, 2.0]
    picks = [min(records, key=lambda r: abs(r["l1_bytes"] - WS_BYTES * t)) for t in targets]
    panels = {f"L1 = {p['l1_bytes']} B (× {p['l1_bytes']/WS_BYTES:.2f} WS)": p
              for p in picks}

    def panel_fn(ax, key, p):
        evicts = p["evicts_per_set"]
        if not evicts:
            ax.set_title(f"{key} (no evicts)")
            return
        max_set = max(int(k) for k in evicts)
        arr = [evicts.get(str(i), 0) for i in range(max_set + 1)]
        ax.bar(range(len(arr)), arr, color="#EF553B")
        ax.set_title(key)
        ax.set_xlabel("L1 set index")
        ax.set_ylabel("Evicts")

    grid_plot(panels, panel_fn=panel_fn, out_path=out,
              ncols=len(panels), subplot_size=(5, 4),
              title="L1 evicts per set at three L1 sizes\n"
                    + summarize_config(
                        {k: v for k, v in BASE_OVERRIDES.items() if not k.startswith("L1_SIZE")},
                        extras={"tile": f"{TILE_M}x{TILE_N}x{TILE_K}"}))


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    cache_p = EXPERIMENT_DIR / "results.json"
    cache: dict = {}
    if cache_p.exists():
        try:
            cache = json.loads(cache_p.read_text())
        except json.JSONDecodeError:
            cache = {}

    print(f"WS = {WS_BYTES} bytes; sweeping L1 in {len(_sweep_l1_sizes())} steps")
    records: list[dict] = []
    for l1 in _sweep_l1_sizes():
        key = str(l1)
        if key in cache:
            rec = cache[key]
            print(f"  cache hit  L1={l1}")
        else:
            overrides = {**BASE_OVERRIDES, "L1_SIZE_BYTES": l1}
            with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
                f.write(render_config(base, overrides))
                tmp = Path(f.name)
            try:
                metrics, ts = run_with_trace(tmp, flags, overrides)
            finally:
                tmp.unlink(missing_ok=True)
            evicts_per_set = {str(k): v for k, v in ts.l1_evicts_per_set.items()}
            rec = {
                "l1_bytes": l1,
                "l1_hit_rate": metrics.l1.hit_rate,
                "cycles": metrics.cycles,
                "evicts_per_set": evicts_per_set,
            }
            cache[key] = rec
            cache_p.write_text(json.dumps(cache, indent=2))
            print(f"  ran        L1={l1}  hit_rate={metrics.l1.hit_rate:.3f}")
        records.append(rec)

    _plot_cliff(records, EXPERIMENT_DIR / "hit_rate_vs_L1.png")
    _plot_heatmap(records, EXPERIMENT_DIR / "evicts_per_set_heatmap.png")

    lines: list[str] = []
    lines.append("# ws-cliff-and-conflict\n")
    lines.append(f"Tile: {TILE_M}x{TILE_N}x{TILE_K}, WS = {WS_BYTES} bytes\n")
    lines.append("![Hit-rate cliff](hit_rate_vs_L1.png)\n")
    lines.append("![Evicts per set](evicts_per_set_heatmap.png)\n")
    write_report(EXPERIMENT_DIR / "README.md", "ws-cliff-and-conflict", lines)
