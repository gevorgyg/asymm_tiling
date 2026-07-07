"""Per-matrix decomposition of L1 traffic vs the paper's per-term formula.

The paper's per-C-block reads are ρzk (cheap input) + k·M/z (expensive input)
+ M (the C block itself); AM-GM balances the two input terms exactly at the
optimum. In our tile variables (bytes, line-aware):

    A_in = blocks · T_M · lines(k·A_p)      ∝ 1/T_N
    B_in = blocks · k   · lines(T_N·B_p)    ∝ 1/T_M   (word model)
    C_in = blocks · T_M · lines(T_N·C_p)    ≈ mn·C_p

so B_in/A_in = ρ·(T_N/T_M) in the word model, crossing 1 at T_N/T_M = 1/ρ.
Region-tagged level-2 traces supply the measured per-matrix L1 line fills.
"""

import json
import math
import tempfile
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, PALETTE_REGION, PALETTE_RHO, describe_changes,
    grid_plot, lineplot, plot_metric_family, render_config, run_grid_dual,
    run_with_trace, stacked_bars, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

M_DIM = N_DIM = K_DIM = 128
A_P = 8
LINE = 64

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": M_DIM, "A_WIDTH_DIM": K_DIM, "B_WIDTH_DIM": N_DIM,
    "A_PRECISION_BYTES": A_P,
    # fully associative: the paper's fast-memory model
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": 16384 // LINE,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": LINE, "L2_ASSOC": 65536 // LINE,
    "L2_ACCESS_CYCLES": 14,
    "TILE_K": K_DIM,
}

RHOS = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
FAMILIES = {
    1024: [(128, 8), (64, 16), (32, 32), (16, 64), (8, 128)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
# predicted-optimal tile per rho (T_N/T_M = 1/rho, smallest fitting family)
OPT_TILE = {1.0: (32, 32), 0.5: (16, 32), 0.25: (16, 64), 0.125: (8, 64)}

FLAGS = Flags(b_source="mem", stationary="C", three_d_reg=True,
              outer_products=True, mulac_norecord=True)


def _lines(seg_bytes: int) -> int:
    return LINE * math.ceil(seg_bytes / LINE)


def _model_in(tm: int, tn: int, b_p: int) -> dict[str, float]:
    """Line-aware per-matrix L1 BytesIn prediction."""
    blocks = (M_DIM // tm) * (N_DIM // tn)
    return {
        "A": blocks * tm * _lines(K_DIM * A_P),
        "B": blocks * K_DIM * _lines(tn * b_p),
        "C": blocks * tm * _lines(tn * A_P),
    }


def _trace_cell(base: str, overrides: dict) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(render_config(base, overrides))
        cfg = Path(f.name)
    try:
        _, ts = run_with_trace(cfg, FLAGS, overrides)
    finally:
        cfg.unlink(missing_ok=True)
    return {
        name: {
            "bytes_in": rs.line_fills_l1 * LINE,
            "bytes_out_dirty_evicts": rs.evicts_l1_dirty * LINE,
        }
        for name, rs in ts.regions.items()
    }


def _sweep(base: str) -> list[dict]:
    cache_p = EXPERIMENT_DIR / "trace_results.json"
    cache: dict = {}
    if cache_p.exists():
        try:
            cache = json.loads(cache_p.read_text())
        except json.JSONDecodeError:
            cache = {}

    records: list[dict] = []
    for rho, b_p in RHOS:
        for area, tiles in FAMILIES.items():
            print(f"\n--- ρ={rho:g} / area={area} words ---")
            for tm, tn in tiles:
                overrides = {**BASE_OVERRIDES, "B_PRECISION_BYTES": b_p,
                             "TILE_M": tm, "TILE_N": tn}
                key = f"rho={rho:g}|{tm}x{tn}"
                if key in cache:
                    per_matrix = cache[key]
                    print(f"  cache hit  {key}")
                else:
                    per_matrix = _trace_cell(base, overrides)
                    cache[key] = per_matrix
                    cache_p.write_text(json.dumps(cache, indent=2))
                    print(f"  traced     {key}")
                duals = run_grid_dual(
                    experiment_dir=EXPERIMENT_DIR,
                    base_config_text=base,
                    base_overrides=overrides,
                    flags=Flags(b_source="mem", stationary="C",
                                three_d_reg=True, outer_products=True),
                )
                records.append({
                    "rho": rho, "b_p": b_p, "area": area, "tm": tm, "tn": tn,
                    "ratio": math.log2(tn / tm), "per_matrix": per_matrix,
                    "d": duals[0],
                })
    return records


def _plot_per_matrix(records: list[dict], caption: str) -> None:
    def panel(ax, key, payload):
        rs, b_p, rho = payload["records"], payload["b_p"], payload["rho"]
        ratios = sorted({r["ratio"] for r in rs})
        for matrix in ("A", "B", "C"):
            pts = sorted((r["ratio"], r["per_matrix"][matrix]["bytes_in"] / 1e6)
                         for r in rs)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o", ms=5,
                    color=PALETTE_REGION[matrix], label=f"{matrix} measured")
            model = []
            for x in ratios:
                r0 = next(r for r in rs if r["ratio"] == x)
                model.append((x, _model_in(r0["tm"], r0["tn"], b_p)[matrix] / 1e6))
            ax.plot([p[0] for p in model], [p[1] for p in model], "--", lw=1,
                    color=PALETTE_REGION[matrix], alpha=0.7,
                    label=f"{matrix} line-aware model")
        ax.axvline(math.log2(1 / rho), color="#999999", ls="-.", lw=1)
        ax.set_title(str(key), fontsize=10)
        ax.set_xlabel("log₂(T_N / T_M)")
        ax.set_ylabel("L1 BytesIn (MB)")
        ax.set_yscale("log")
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend(fontsize=6)

    panels = {
        f"ρ={rho:g} (predicted opt at {math.log2(1 / rho):g})": {
            "rho": rho, "b_p": b_p,
            "records": [r for r in records if r["rho"] == rho],
        }
        for rho, b_p in RHOS
    }
    grid_plot(panels, panel_fn=panel, ncols=2, subplot_size=(6.5, 4),
              out_path=EXPERIMENT_DIR / "per_matrix_reads_vs_model.png",
              title="Per-matrix L1 reads vs the paper's per-term formula\n" + caption)


def _plot_balance(records: list[dict], caption: str) -> None:
    series: dict[str, list[tuple[float, float]]] = {}
    vlines: dict[str, float] = {}
    for rho, _b in RHOS:
        label = f"ρ={rho:g}"
        by_x: dict[float, list[float]] = {}
        for r in records:
            if r["rho"] != rho or r["per_matrix"]["A"]["bytes_in"] == 0:
                continue
            ba = r["per_matrix"]["B"]["bytes_in"] / r["per_matrix"]["A"]["bytes_in"]
            by_x.setdefault(r["ratio"], []).append(ba)
        series[label] = sorted((x, sum(v) / len(v)) for x, v in by_x.items())
        vlines[label] = math.log2(1 / rho)
    xs = sorted({x for pts in series.values() for x, _ in pts})
    series["B = A"] = [(xs[0], 1.0), (xs[-1], 1.0)]
    lineplot(
        series, out_path=EXPERIMENT_DIR / "balance_B_over_A.png",
        vlines=vlines,
        colors={**{f"ρ={r:g}": c for r, c in PALETTE_RHO.items()},
                "B = A": "#999999"},
        xlabel="log₂(T_N / T_M)", ylabel="B BytesIn / A BytesIn (log scale)",
        title="AM-GM balance: input traffic ratio, crossing 1 at the predicted optimum\n"
              + caption,
    )


def _plot_writes(records: list[dict], caption: str) -> None:
    groups, comp = [], {"A": [], "B": [], "C": []}
    for rho, _b in RHOS:
        tm, tn = OPT_TILE[rho]
        r = next(r for r in records
                 if r["rho"] == rho and (r["tm"], r["tn"]) == (tm, tn))
        groups.append(f"ρ={rho:g}\n{tm}×{tn}")
        for mx in comp:
            comp[mx].append(r["per_matrix"][mx]["bytes_out_dirty_evicts"] / 1e3)
    stacked_bars(
        groups, comp, out_path=EXPERIMENT_DIR / "per_matrix_writes.png",
        colors=PALETTE_REGION, ylabel="L1 dirty-evict bytes (KB)",
        title="Who writes? L1 dirty evictions per matrix at the predicted optimum\n"
              + caption,
    )


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    records = _sweep(base)
    caption = describe_changes(
        {k: v for k, v in BASE_OVERRIDES.items() if k != "TILE_K"}, base,
        extras={"TILE_K": K_DIM, "order": "outer products"},
    )

    _plot_per_matrix(records, caption)
    _plot_balance(records, caption)
    _plot_writes(records, caption)

    cells = [Cell(x=r["ratio"], series=f"ρ={r['rho']:g}",
                  traffic=r["d"].traffic, cycles=r["d"].cycles)
             for r in records]
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name="per_matrix_balance",
        title="Per-matrix balance sweep (best of both families)",
        caption=caption, xlabel="log₂(T_N / T_M)",
        colors={f"ρ={r:g}": c for r, c in PALETTE_RHO.items()},
    )

    lines = [f"Non-default config: {caption}, flags: --outer_products\n",
             "![per-matrix reads](per_matrix_reads_vs_model.png)\n",
             "![balance](balance_B_over_A.png)\n",
             "![writes](per_matrix_writes.png)\n"]
    lines.append("\n## B/A read balance at the predicted optimum (want ≈ 1)\n")
    lines.append("| ρ | tile | measured B/A | word-model B/A |")
    lines.append("|---|---|---|---|")
    for rho, b_p in RHOS:
        tm, tn = OPT_TILE[rho]
        r = next(r for r in records
                 if r["rho"] == rho and (r["tm"], r["tn"]) == (tm, tn))
        ba = (r["per_matrix"]["B"]["bytes_in"]
              / max(1, r["per_matrix"]["A"]["bytes_in"]))
        lines.append(f"| {rho:g} | {tm}×{tn} | {ba:.3f} | {rho * tn / tm:g} |")
    for k in METRICS:
        lines.append(f"\n![{k}](per_matrix_balance_{k}.png)")
    write_report(EXPERIMENT_DIR / "README.md",
                 "paper-per-matrix-balance", ["\n".join(lines)])
