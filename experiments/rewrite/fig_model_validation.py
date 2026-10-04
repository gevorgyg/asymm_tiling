"""Predicted vs measured runtime, simple model vs refined model (report 3.3.5).

All runs of the fig_best_tile grid with gc > 0 (192x256x256, TM 4..192,
TN 4..128 in steps of 4, gc up to 600; default setup). Nothing is re-run.

  simple:   max(alpha(TM, TN), gc / TM)                    (report 3.3.1)
  refined:  1/M sum over rows of tiles max(r alpha(r), gc) + startup,
            startup = gc R^2 ceil(M/TM) ceil(N/TN) / MNK    (report 3.3.4)

alpha(r), the alpha of a tile of exactly r rows, is recovered from the
gc = 0 runs by un-mixing the edge tile (smallest heights first).

  fig_model_validation:  two panels, measured vs predicted (log axes), with
                         the diagonal; a perfect model puts every point on it.

run:  .venv/bin/python experiments/rewrite/fig_model_validation.py
"""

from dataclasses import replace

import fig_best_tile as fbt
from harness import Params, out_dir, run_many
from plot_style import INK_2, SERIES, plt, save

NAME = "fig_model_validation"
M, K, N, R = fbt.M, fbt.K, fbt.N, fbt.R
MNK = M * K * N


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def main() -> None:
    assert not fbt.SMALL
    params = [replace(Params(l1_assoc=-1), tile_h=tm, tile_w=tn, gen_cost=gc)
              for gc in fbt.GC for tm in fbt.TM for tn in fbt.TN]
    stats = run_many(params, out_dir(fbt.NAME) / "results.json")
    t = {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    alpha = {(tm, tn): t[(0, tm, tn)] for tm in fbt.TM for tn in fbt.TN}
    pure = {}   # alpha of a tile of exactly tm rows: remove the edge tile, smallest first
    for tn in fbt.TN:
        for tm in fbt.TM:
            e = M % tm
            pure[(tm, tn)] = (M * alpha[(tm, tn)] - (e * pure[(e, tn)] if e else 0)) / (M - e)

    def simple(tm: int, tn: int, gc: int) -> float:
        return max(alpha[(tm, tn)], gc / tm)

    def refined(tm: int, tn: int, gc: int) -> float:
        full, e = divmod(M, tm)
        rows = [tm] * full + ([e] if e else [])
        startup = gc * R * R * cdiv(M, tm) * cdiv(N, tn) / MNK
        return sum(max(r * pure[(r, tn)], gc) for r in rows) / M + startup

    runs = [(gc, tm, tn) for gc in fbt.GC if gc > 0 for tm in fbt.TM for tn in fbt.TN]
    measured = [t[r] for r in runs]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.6), sharey=True)
    for ax, model, label in ((axes[0], simple, "predicted, simple model"),
                             (axes[1], refined, "predicted, refined model")):
        predicted = [model(tm, tn, gc) for gc, tm, tn in runs]
        ax.scatter(predicted, measured, s=3, color=SERIES[0], alpha=0.15, linewidths=0,
                   rasterized=True)
        lo, hi = 0.7, 40
        ax.plot([lo, hi], [lo, hi], color=INK_2, linewidth=1.0, linestyle="--")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel(f"{label} (cycles / MAC)")
        within = sum(abs(m / p - 1) <= 0.01 for m, p in zip(measured, predicted)) / len(runs)
        print(f"{label}: within 1 % {within:.1%} of {len(runs)} runs")
    axes[0].set_ylabel("measured (cycles / MAC)")
    print(save(fig, "model", NAME))


if __name__ == "__main__":
    main()
