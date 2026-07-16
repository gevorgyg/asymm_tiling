"""No-L2 paper-model experiments: traffic validation and cycle-optimal alignment.

With both L1 and L2 (v45 experiments), the cycle-optimal tile shape can differ
from the paper's traffic-optimal prediction because L2 introduces an asymmetry
between A and B miss costs: when T_M is large, the A tile overflows L2 and every
A miss pays L2 latency + DRAM latency; when T_N is large, the A tile stays in L2
and pays only L2 latency. This pushes the cycle optimum away from T_N/T_M = 1/ρ.

With --no-l2, every L1 miss costs exactly one DRAM penalty (uniform per miss).
Hypothesis: cycles ∝ L1 BytesIn, so cycle-argmin = traffic-argmin = 1/ρ.

This experiment runs two sub-sweeps:
  1. Traffic model (M=N=K=256): L1 BytesIn vs the paper's formula, plus a
     cycle-vs-traffic optimal comparison table.
  2. Per-matrix balance (M=N=K=128): per-matrix L1 trace decomposition, checking
     that the B/A ratio still crosses 1 at T_N/T_M = 1/ρ.
"""

import json
import math
import tempfile
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, PALETTE_REGION, PALETTE_RHO, describe_changes,
    grid_plot, lineplot, paper_model, plot_metric_family, render_config,
    run_grid_dual, run_with_trace, stacked_bars, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

LINE = 64
A_P  = 8

FLAGS = Flags(b_source="mem", stationary="A", three_d_reg=True, no_l2=True)

# ── Traffic-model sweep (M=N=K=256) ──────────────────────────────────────────

M = N = K = 256
TM_BASE: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": A_P,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": 16384 // LINE,
    "TILE_K": K,
}
RHOS    = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
FAMILIES = {
    1024: [(256, 4), (128, 8), (64, 16), (32, 32), (16, 64), (8, 128), (4, 256)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
FAMILY_MARKERS = {1024: "o", 512: "s"}

# ── Per-matrix balance sweep (M=N=K=128) ─────────────────────────────────────

M_S = N_S = K_S = 128
PM_BASE: dict[str, object] = {
    "A_HEIGHT_DIM": M_S, "A_WIDTH_DIM": K_S, "B_WIDTH_DIM": N_S,
    "A_PRECISION_BYTES": A_P,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": 16384 // LINE,
    "L2_LINE_SIZE_BYTES": LINE,   # unused by sim (--no-l2), needed by run_with_trace
    "TILE_K": K_S,
}
FAMILIES_128 = {
    1024: [(128, 8), (64, 16), (32, 32), (16, 64), (8, 128)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
OPT_TILE  = {1.0: (32, 32), 0.5: (16, 32), 0.25: (16, 64), 0.125: (8, 64)}
FLAGS_NR  = Flags(b_source="mem", stationary="A", three_d_reg=True,
                  no_l2=True, mulac_norecord=True)


# ── Part 1: traffic-model sweep ───────────────────────────────────────────────

def _tm_sweep() -> list[dict]:
    base = (workspace_root() / "default.config").read_text()
    records: list[dict] = []
    for rho, b_p in RHOS:
        for area, tiles in FAMILIES.items():
            print(f"\n--- ρ={rho:g} / area={area} words ---")
            for tm, tn in tiles:
                duals = run_grid_dual(
                    experiment_dir=EXPERIMENT_DIR,
                    base_config_text=base,
                    base_overrides={**TM_BASE, "B_PRECISION_BYTES": b_p,
                                    "TILE_M": tm, "TILE_N": tn},
                    flags=FLAGS,
                    cache_path=EXPERIMENT_DIR / "tm_results.json",
                )
                d = duals[0]
                records.append({
                    "rho": rho, "b_p": b_p, "area": area,
                    "tm": tm, "tn": tn,
                    "ratio": math.log2(tn / tm),
                    "d": d,
                })
    return records


def _panel_traffic(ax, key, payload) -> None:
    rho, metric, b_p = payload["rho"], payload["metric"], payload["b_p"]
    for area, tiles in FAMILIES.items():
        pts = sorted((r["ratio"], getattr(r["d"].traffic.l1, metric))
                     for r in payload["records"] if r["area"] == area)
        xs, ys = zip(*pts)
        ax.plot(xs, [y / 1e6 for y in ys], FAMILY_MARKERS[area], ms=5,
                color=PALETTE_RHO[rho], label=f"measured, {area}-word tile")

        curve_x = [xs[0] + i * (xs[-1] - xs[0]) / 200 for i in range(201)]
        if metric == "bytes_in":
            word = [paper_model.reads_bytes(
                        M, N, K, math.sqrt(area / 2**x), math.sqrt(area * 2**x),
                        A_P, b_p, A_P) / 1e6
                    for x in curve_x]
        else:
            word = [paper_model.writes_bytes(M, N, A_P) / 1e6 for _ in curve_x]
        ax.plot(curve_x, word, "--", lw=1, color=PALETTE_RHO[rho], alpha=0.7,
                label=f"word model, {area}w" if area == 1024 else None)

        fn = (paper_model.reads_bytes_line_aware if metric == "bytes_in"
              else lambda m, n, k, tm, tn, a, b, c, l:
                   paper_model.writes_bytes_line_aware(m, n, tm, tn, c, l))
        law = sorted((math.log2(tn / tm),
                      fn(M, N, K, tm, tn, A_P, b_p, A_P, LINE) / 1e6)
                     for tm, tn in tiles)
        ax.plot([p[0] for p in law], [p[1] for p in law], ":", lw=1.2,
                color="#444444",
                label=f"line-aware, {area}w" if area == 1024 else None)

    ax.axvline(math.log2(1 / rho), color="#999999", ls="-.", lw=1,
               label=f"predicted opt = {1 / rho:g}")
    ax.set_title(str(key), fontsize=10)
    ax.set_xlabel("log₂(T_N / T_M)")
    ax.set_ylabel("MB")
    ax.set_yscale("log")
    ax.grid(True, ls=":", alpha=0.5)
    ax.legend(fontsize=6)


def _plot_traffic(records: list[dict], caption: str) -> None:
    for metric, fname, what in [
        ("bytes_in",  "traffic_reads_vs_model.png",  "L1 reads (BytesIn)"),
        ("bytes_out", "traffic_writes_vs_model.png", "L1 writes (BytesOut)"),
    ]:
        panels = {
            f"ρ={rho:g}": {"rho": rho, "b_p": b_p, "metric": metric,
                            "records": [r for r in records if r["rho"] == rho]}
            for rho, b_p in RHOS
        }
        grid_plot(
            panels, panel_fn=_panel_traffic, ncols=2, subplot_size=(6.5, 4),
            out_path=EXPERIMENT_DIR / fname,
            title=f"{what} vs paper prediction (no-L2)\n{caption}",
        )


def _cycle_vs_traffic_table(records: list[dict]) -> list[str]:
    lines = [
        "\n## Cycle-optimal vs traffic-optimal tile (the key test)\n",
        "With no L2, every L1 miss costs DRAM latency (uniform). "
        "Expected: argmin(cycles) = argmin(L1 BytesIn) = paper's 1/ρ.\n",
        "| ρ | area | traffic argmin T_N/T_M "
        "| cycle argmin T_N/T_M | match? | predicted 1/ρ |",
        "|---|---|---|---|---|---|",
    ]
    for rho, b_p in RHOS:
        for area in FAMILIES:
            rs = [r for r in records if r["rho"] == rho and r["area"] == area]
            t_best = min(rs, key=lambda r: r["d"].traffic.l1.bytes_in)
            c_best = min(rs, key=lambda r: r["d"].cycles.cycles)
            t_ratio = t_best["tn"] / t_best["tm"]
            c_ratio = c_best["tn"] / c_best["tm"]
            match = "yes" if (t_best["tm"], t_best["tn"]) == (c_best["tm"], c_best["tn"]) else "no"
            lines.append(
                f"| {rho:g} | {area} "
                f"| {t_ratio:g} | {c_ratio:g} | {match} | {1/rho:g} |")
    return lines


def _savings_table(records: list[dict]) -> list[str]:
    lines = [
        "\n## Savings vs square tile (1024-word family, measured reads)\n",
        "| ρ | reads(best)/reads(32×32) | paper asymptotic 2√ρ/(1+ρ) |",
        "|---|---|---|",
    ]
    for rho, _ in RHOS:
        rs = [r for r in records if r["rho"] == rho and r["area"] == 1024]
        best   = min(r["d"].traffic.l1.bytes_in for r in rs)
        square = next(r["d"].traffic.l1.bytes_in for r in rs
                      if r["tm"] == r["tn"] == 32)
        lines.append(f"| {rho:g} | {best / square:.3f} "
                     f"| {paper_model.savings_vs_square(rho):.3f} |")
    return lines


# ── Part 2: per-matrix balance ────────────────────────────────────────────────

def _line_bytes(seg_bytes: int) -> int:
    return LINE * math.ceil(seg_bytes / LINE)


def _model_in(tm: int, tn: int, b_p: int) -> dict[str, float]:
    blocks = (M_S // tm) * (N_S // tn)
    return {
        "A": blocks * tm * _line_bytes(K_S * A_P),
        "B": blocks * K_S * _line_bytes(tn * b_p),
        "C": blocks * tm * _line_bytes(tn * A_P),
    }


def _trace_cell(base: str, overrides: dict) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(render_config(base, overrides))
        cfg = Path(f.name)
    try:
        _, ts = run_with_trace(cfg, FLAGS_NR, overrides)
    finally:
        cfg.unlink(missing_ok=True)
    return {
        name: {
            "bytes_in": rs.line_fills_l1 * LINE,
            "bytes_out_dirty_evicts": rs.evicts_l1_dirty * LINE,
        }
        for name, rs in ts.regions.items()
    }


def _pm_sweep() -> list[dict]:
    base    = (workspace_root() / "default.config").read_text()
    cache_p = EXPERIMENT_DIR / "trace_results.json"
    cache: dict = {}
    if cache_p.exists():
        try:
            cache = json.loads(cache_p.read_text())
        except json.JSONDecodeError:
            cache = {}

    records: list[dict] = []
    for rho, b_p in RHOS:
        for area, tiles in FAMILIES_128.items():
            print(f"\n--- balance ρ={rho:g} / area={area} words ---")
            for tm, tn in tiles:
                overrides = {**PM_BASE, "B_PRECISION_BYTES": b_p,
                             "TILE_M": tm, "TILE_N": tn}
                key = f"nol2|rho={rho:g}|{tm}x{tn}"
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
                    flags=FLAGS,
                    cache_path=EXPERIMENT_DIR / "pm_results.json",
                )
                records.append({
                    "rho": rho, "b_p": b_p, "area": area,
                    "tm": tm, "tn": tn,
                    "ratio": math.log2(tn / tm),
                    "per_matrix": per_matrix,
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
              title="Per-matrix L1 reads vs paper formula (no-L2)\n" + caption)


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
        xlabel="log₂(T_N / T_M)", ylabel="B BytesIn / A BytesIn",
        title="AM-GM balance: B/A traffic ratio, crossing 1 at 1/ρ (no-L2)\n"
              + caption,
    )


def _plot_writes(records: list[dict], caption: str) -> None:
    groups: list[str] = []
    comp: dict[str, list[float]] = {"A": [], "B": [], "C": []}
    for rho, _b in RHOS:
        tm, tn = OPT_TILE[rho]
        r = next((r for r in records
                  if r["rho"] == rho and (r["tm"], r["tn"]) == (tm, tn)), None)
        if r is None:
            continue
        groups.append(f"ρ={rho:g}\n{tm}×{tn}")
        for mx in comp:
            comp[mx].append(r["per_matrix"][mx]["bytes_out_dirty_evicts"] / 1e3)
    stacked_bars(
        groups, comp, out_path=EXPERIMENT_DIR / "per_matrix_writes.png",
        colors=PALETTE_REGION, ylabel="L1 dirty-evict bytes (KB)",
        title="Who writes? L1 dirty evictions at predicted optimum (no-L2)\n"
              + caption,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # Part 1: traffic model
    print("=== Part 1: traffic model sweep (M=N=K=256, no-L2) ===")
    tm_records = _tm_sweep()
    tm_caption = describe_changes(
        {k: v for k, v in TM_BASE.items() if k != "TILE_K"}, base,
        extras={"TILE_K": K, "no_l2": True},
    )
    _plot_traffic(tm_records, tm_caption)
    plot_metric_family(
        [Cell(x=r["ratio"], series=f"ρ={r['rho']:g}",
              traffic=r["d"].traffic, cycles=r["d"].cycles)
         for r in tm_records],
        out_dir=EXPERIMENT_DIR, base_name="traffic_model",
        title="Traffic model sweep (no-L2), fully-assoc L1",
        caption=tm_caption, xlabel="log₂(T_N / T_M)",
        colors={f"ρ={r:g}": c for r, c in PALETTE_RHO.items()},
        vlines={f"ρ={rho:g}": math.log2(1 / rho) for rho, _ in RHOS},
    )

    # Part 2: per-matrix balance
    print("\n=== Part 2: per-matrix balance (M=N=K=128, no-L2) ===")
    pm_records = _pm_sweep()
    pm_caption = describe_changes(
        {k: v for k, v in PM_BASE.items() if k != "TILE_K"}, base,
        extras={"TILE_K": K_S, "no_l2": True},
    )
    _plot_per_matrix(pm_records, pm_caption)
    _plot_balance(pm_records, pm_caption)
    _plot_writes(pm_records, pm_caption)
    plot_metric_family(
        [Cell(x=r["ratio"], series=f"ρ={r['rho']:g}",
              traffic=r["d"].traffic, cycles=r["d"].cycles)
         for r in pm_records],
        out_dir=EXPERIMENT_DIR, base_name="per_matrix_balance",
        title="Per-matrix balance sweep (no-L2), fully-assoc L1",
        caption=pm_caption, xlabel="log₂(T_N / T_M)",
        colors={f"ρ={r:g}": c for r, c in PALETTE_RHO.items()},
        vlines={f"ρ={rho:g}": math.log2(1 / rho) for rho, _ in RHOS},
    )

    # Report
    report = [
        "No-L2 paper-model experiment: tests whether removing L2 aligns the\n"
        "cycle-optimal tile with the paper's traffic-predicted optimum.\n\n"
        "With L2, large T_M causes the A tile to overflow L2; each A miss then\n"
        "pays L2 latency + DRAM. This asymmetry shifts the cycle optimum away\n"
        "from T_N/T_M = 1/ρ. Without L2 all L1 misses cost only DRAM latency,\n"
        "so cycles ∝ L1 BytesIn and the cycle optimum should match 1/ρ.\n",

        "\n## Part 1: Traffic model validation (M=N=K=256)\n",
        f"Config: {tm_caption}\n",
        "![reads](traffic_reads_vs_model.png)\n",
        "![writes](traffic_writes_vs_model.png)\n",
    ]
    report.extend(_cycle_vs_traffic_table(tm_records))
    report.extend(_savings_table(tm_records))

    report.append("\n## Writes = mn·C_p check\n")
    report.append("| ρ | max |writes − mn·C_p| / mn·C_p over all tiles |")
    report.append("|---|---|")
    target = paper_model.writes_bytes(M, N, A_P)
    for rho, _b in RHOS:
        rs = [r for r in tm_records if r["rho"] == rho]
        dev = max(abs(r["d"].traffic.l1.bytes_out - target) / target for r in rs)
        report.append(f"| {rho:g} | {dev:.4f} |")

    for k in METRICS:
        report.append(f"\n![{k}](traffic_model_{k}.png)")

    report.append("\n## Part 2: Per-matrix balance (M=N=K=128)\n")
    report.append(f"Config: {pm_caption}\n")
    report.append("![per-matrix reads](per_matrix_reads_vs_model.png)\n")
    report.append("![balance](balance_B_over_A.png)\n")
    report.append("![writes](per_matrix_writes.png)\n")

    report.append("\n## B/A balance at the predicted optimum (want ≈ 1)\n")
    report.append("| ρ | tile | measured B/A | word-model B/A |")
    report.append("|---|---|---|---|")
    for rho, b_p in RHOS:
        tm, tn = OPT_TILE[rho]
        r = next((r for r in pm_records
                  if r["rho"] == rho and (r["tm"], r["tn"]) == (tm, tn)), None)
        if r is None:
            continue
        ba = (r["per_matrix"]["B"]["bytes_in"]
              / max(1, r["per_matrix"]["A"]["bytes_in"]))
        report.append(f"| {rho:g} | {tm}×{tn} | {ba:.3f} | {rho * tn / tm:g} |")

    for k in METRICS:
        report.append(f"\n![{k}](per_matrix_balance_{k}.png)")

    write_report(EXPERIMENT_DIR / "README.md", "paper-model-no-l2",
                 ["\n".join(report)])
