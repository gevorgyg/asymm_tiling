"""F5: the best tile (TM*, TN*) against gc, B-stationary, default setup
(192x256x256, 16 KB fully associative L1, no L2).

Every tile of the grid is simulated at every gc; the measured best tile is
the argmin of the total cycles. One plot: TM* blue, TN* red.

  measured (solid + markers) and the model's pick (thin dashed, same color):
    T / MNK = max(alpha(TM, TN), gc * ceil(M/TM) / M) + S,
    S = tiles * R^2 * gc / MNK   (one FIFO startup per tile),
  with alpha measured at gc = 0 on the same tile.
  Near ties (tiles within 1 % of the best) are listed in the README table,
  not drawn.

The out/fig_best_tile/README.md table also gives how close the runner-up
tiles are (near ties make TN* jumpy) and what the model's pick costs.

SMALL=True runs a quick sample first (coarse tile grid, fewer gc).

run:  .venv/bin/python experiments/rewrite/fig_best_tile.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import SERIES, legend_above, plt, save, series

NAME = "fig_best_tile"
SMALL = False
M, K, N, R = 192, 256, 256, 4
MNK = M * K * N
if SMALL:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 16, 24, 32, 48, 64, 96, 128]
    GC = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 50, 70, 100, 150, 200, 300, 400,
          500, 600]
else:
    TM = list(range(4, M + 1, 4))
    TN = list(range(4, 129, 4))
    GC = sorted({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 23, 26, 30,
                 35, 40, 45, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200,
                 230, 260, 300, 350, 400, 450, 500, 550, 600})
NEAR = 0.01   # "near tie": within 1 % of the best
GC_TICKS = [0, 1, 3, 10, 30, 100, 300, 600]


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def model(alpha: float, tm: int, tn: int, gc: int) -> float:
    tiles = cdiv(M, tm) * cdiv(N, tn)
    return max(alpha, gc * cdiv(M, tm) / M) + tiles * R * R * gc / MNK


def main() -> None:
    base = Params(l1_assoc=-1)
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(base, tile_h=tm, tile_w=tn, gen_cost=gc)
              for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    best, pick, lines = {}, {}, []
    for gc in GC:
        cost = {tile: t[(gc, *tile)] for tile in tiles}
        best[gc] = min(tiles, key=lambda tl: cost[tl])
        pick[gc] = min(tiles, key=lambda tl: (model(t[(0, *tl)], *tl, gc), t[(0, *tl)]))
        b = cost[best[gc]]
        near = sorted((tl for tl in tiles if cost[tl] <= b * (1 + NEAR)), key=lambda tl: cost[tl])
        lines.append(f"| {gc} | {best[gc]} | {b:.3f} | {len(near)}: "
                     f"{', '.join(map(str, near[1:6]))}{' ...' if len(near) > 6 else ''} | "
                     f"{pick[gc]} | {100 * (cost[pick[gc]] / b - 1):.1f} % | "
                     f"{100 * (cost[(16, 32)] / b - 1):.0f} % |")

    # steps-post gives each gc the interval up to the next one; the axis ends
    # at the last gc, so the repeated last value only closes the line there
    xs = GC + [GC[-1] * 1.25]

    def ys(f):
        return [f(gc) for gc in GC] + [f(GC[-1])]

    # both dimensions on one plot, T_M* blue, T_N* red
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, s, label in ((0, 0, "$T_M^*$"), (1, 7, "$T_N^*$")):
        style = series(s) | {"marker": "os"[i]}
        ax.plot(xs, ys(lambda gc: best[gc][i]), drawstyle="steps-post", label=label,
                markevery=len(GC) * [True] + [False], **style)
        ax.plot(xs, ys(lambda gc: pick[gc][i]), drawstyle="steps-post", color=SERIES[s],
                linestyle="--", linewidth=1.0, alpha=0.8,
                label=f"{label} model")
    ax.set_yscale("log", base=2)
    ax.set_yticks([8, 12, 16, 24, 32, 48, 64, 96, 128])
    ax.set_ylim(7, 150)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_ylabel("tile dimension")
    ax.set_xscale("symlog", linthresh=1, linscale=0.5)
    ax.set_xticks(GC_TICKS)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlim(0, GC[-1])
    ax.set_xlabel("$g_c$ (cycles / element)")
    legend_above(ax, ncols=4)
    print(save(fig, "tile_choice", NAME + ("_small" if SMALL else "")))

    header = ["| gc | best (TM, TN) | cycles / MAC | tiles within 1 % (next 5) | "
              "model pick | its excess | 16×32 excess |", "|---|---|---|---|---|---|---|"]
    report = (f"# fig_best_tile{' (small)' if SMALL else ''}: best B-stationary tile vs gc\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc.\n\n" + "\n".join(header + lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
