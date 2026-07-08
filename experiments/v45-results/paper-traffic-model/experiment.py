"""Reads/writes formula from Multiplication_by_a_Random_Matrix.pdf vs measured L1 traffic.

The paper predicts, for a C-stationary rank-1-update matmul with the C block
resident in fast memory (see WRITEUP.md):

    reads  = m*n*k*(A_p/T_N + B_p/T_M) + m*n*C_p     [L1 BytesIn]
    writes = m*n*C_p                                  [L1 BytesOut]
    optimum at T_N/T_M = 1/rho,  rho = B_p/A_p

Sweeps constant-area tile families (the paper fixes M = T_M*T_N) x rho x two
cache regimes: fully associative (the paper's fast-memory model) and 8-way
associative. C-stationary is the paper's rank-1 streaming order.
"""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, PALETTE_RHO, describe_changes, grid_plot,
    paper_model, plot_metric_family, run_grid_dual, workspace_root,
    write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

M = N = K = 256
A_P = 8            # C precision follows max(A_p, B_p) = 8 throughout
LINE = 64

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": A_P,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": LINE,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": LINE,
    "L2_ACCESS_CYCLES": 14,
    "TILE_K": K,
}

REGIMES = [
    ("fully-assoc (paper model)", {"L1_ASSOC": 16384 // LINE, "L2_ASSOC": 65536 // LINE}),
    ("8-way assoc",               {"L1_ASSOC": 8, "L2_ASSOC": 8}),
]
RHOS = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]   # (rho, B_PRECISION_BYTES)

# Constant C-tile area families (words); the paper optimizes shape at fixed M.
FAMILIES = {
    1024: [(256, 4), (128, 8), (64, 16), (32, 32), (16, 64), (8, 128), (4, 256)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
FAMILY_MARKERS = {1024: "o", 512: "s"}

FLAGS = Flags(b_source="mem", stationary="C", three_d_reg=True)


def _sweep() -> list[dict]:
    base = (workspace_root() / "default.config").read_text()
    records: list[dict] = []
    for regime, regime_over in REGIMES:
        for rho, b_p in RHOS:
            for area, tiles in FAMILIES.items():
                print(f"\n--- {regime} / ρ={rho} / area={area} words ---")
                for tm, tn in tiles:
                    duals = run_grid_dual(
                        experiment_dir=EXPERIMENT_DIR,
                        base_config_text=base,
                        base_overrides={
                            **BASE_OVERRIDES, **regime_over,
                            "B_PRECISION_BYTES": b_p,
                            "TILE_M": tm, "TILE_N": tn,
                        },
                        flags=FLAGS,
                    )
                    d = duals[0]
                    records.append({
                        "regime": regime, "rho": rho, "b_p": b_p,
                        "area": area, "tm": tm, "tn": tn,
                        "ratio": math.log2(tn / tm), "d": d,
                    })
    return records


def _panel(ax, key, payload) -> None:
    rho, metric = payload["rho"], payload["metric"]
    b_p = payload["b_p"]
    for area, tiles in FAMILIES.items():
        pts = sorted((r["ratio"], getattr(r["d"].traffic.l1, metric))
                     for r in payload["records"] if r["area"] == area)
        xs, ys = zip(*pts)
        ax.plot(xs, [y / 1e6 for y in ys], FAMILY_MARKERS[area], ms=5,
                color=PALETTE_RHO[rho], label=f"measured, {area}-word C tile")

        # word model, continuous in the aspect ratio at fixed area
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

        # line-aware model at the actual grid tiles
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


def _model_plots(records: list[dict], caption: str) -> None:
    for metric, fname, what in [
        ("bytes_in", "l1_reads_vs_model.png", "L1 reads (BytesIn)"),
        ("bytes_out", "l1_writes_vs_model.png", "L1 writes (BytesOut)"),
    ]:
        panels = {}
        for rho, b_p in RHOS:
            for regime, _ in REGIMES:
                rs = [r for r in records
                      if r["rho"] == rho and r["regime"] == regime]
                panels[f"ρ={rho:g} — {regime}"] = {
                    "rho": rho, "b_p": b_p, "metric": metric, "records": rs,
                }
        grid_plot(
            panels, panel_fn=_panel, ncols=2, subplot_size=(6.5, 4),
            out_path=EXPERIMENT_DIR / fname,
            title=f"{what} vs paper prediction, constant-area tile families\n{caption}",
        )


def _argmin_savings_report(records: list[dict], caption: str) -> None:
    lines = [f"Non-default config: {caption}\n",
             "Reads = L1 BytesIn, writes = L1 BytesOut (the paper's fast-memory "
             "boundary). See WRITEUP.md for the claims under test.\n",
             "![reads](l1_reads_vs_model.png)\n",
             "![writes](l1_writes_vs_model.png)\n"]

    lines.append("\n## Optimal aspect ratio: measured vs predicted (per family)\n")
    lines.append("| regime | ρ | area (words) | measured argmin T_N/T_M "
                 "| model argmin (same grid) | predicted 1/ρ |")
    lines.append("|---|---|---|---|---|---|")
    for regime, _ in REGIMES:
        for rho, b_p in RHOS:
            for area, tiles in FAMILIES.items():
                rs = [r for r in records if r["regime"] == regime
                      and r["rho"] == rho and r["area"] == area]
                best = min(rs, key=lambda r: r["d"].traffic.l1.bytes_in)
                model_best = min(tiles, key=lambda t: paper_model.reads_bytes_line_aware(
                    M, N, K, t[0], t[1], A_P, b_p, A_P, LINE))
                lines.append(
                    f"| {regime} | {rho:g} | {area} "
                    f"| {best['tn'] / best['tm']:g} "
                    f"| {model_best[1] / model_best[0]:g} | {1 / rho:g} |")

    lines.append("\n## Savings vs square tile (1024-word family, measured reads)\n")
    lines.append("| regime | ρ | reads(best)/reads(32×32) | paper asymptotic 2√ρ/(1+ρ) |")
    lines.append("|---|---|---|---|")
    for regime, _ in REGIMES:
        for rho, _b in RHOS:
            rs = [r for r in records if r["regime"] == regime
                  and r["rho"] == rho and r["area"] == 1024]
            best = min(r["d"].traffic.l1.bytes_in for r in rs)
            square = next(r["d"].traffic.l1.bytes_in for r in rs
                          if r["tm"] == r["tn"] == 32)
            lines.append(f"| {regime} | {rho:g} | {best / square:.3f} "
                         f"| {paper_model.savings_vs_square(rho):.3f} |")

    lines.append("\n## Writes = mn·C_p check (ideal regime)\n")
    lines.append("| ρ | max |writes − mn·C_p| / mn·C_p over all tiles |")
    lines.append("|---|---|")
    target = paper_model.writes_bytes(M, N, A_P)
    for rho, _b in RHOS:
        rs = [r for r in records if r["regime"] == REGIMES[0][0] and r["rho"] == rho]
        dev = max(abs(r["d"].traffic.l1.bytes_out - target) / target for r in rs)
        lines.append(f"| {rho:g} | {dev:.4f} |")

    for k in METRICS:
        lines.append(f"\n![{k}](traffic_model_{k}.png)")
    write_report(EXPERIMENT_DIR / "README.md",
                 "paper-traffic-model", ["\n".join(lines)])


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    records = _sweep()
    caption = describe_changes(
        {k: v for k, v in BASE_OVERRIDES.items() if k != "TILE_K"}, base,
        extras={"TILE_K": K},
    )
    _model_plots(records, caption)

    cells = [
        Cell(x=r["ratio"], series=f"ρ={r['rho']:g}",
             traffic=r["d"].traffic, cycles=r["d"].cycles)
        for r in records if r["regime"] == REGIMES[0][0]
    ]
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name="traffic_model",
        title="Paper traffic model sweep, fully-assoc cache (best of both families)",
        caption=caption, xlabel="log₂(T_N / T_M)",
        colors={f"ρ={r:g}": c for r, c in PALETTE_RHO.items()},
        vlines={f"ρ={rho:g}": math.log2(1 / rho) for rho, _ in RHOS},
    )
    _argmin_savings_report(records, caption)
