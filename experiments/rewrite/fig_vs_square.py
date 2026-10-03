"""F6: how much does choosing the tile shape matter? B-stationary, default
setup.

For a fixed TN, the best TM (over TM 4..192 step 4) against the square tile
TM = TN. Gain = time saved = (T_square - T_best) / T_square.

  fig_vs_square:       gain (%) vs gc, one line per TN in {8, 16, 32, 64};
  fig_vs_square_cost:  cycles / MAC vs gc, best TM (solid) and square
                       (dashed), same colors.

No new runs: everything comes from fig_best_tile's cache (run that first).
The README also compares the overall best tile with the best square tile.

run:  .venv/bin/python experiments/rewrite/fig_vs_square.py
"""

from dataclasses import replace

import fig_best_tile as fbt
from harness import Params, out_dir, run_many
from plot_style import INK, legend_above, plt, save, series

NAME = "fig_vs_square"
TN = [8, 16, 32, 64]
GC = fbt.GC
TM = fbt.TM


def symlog_gc(ax) -> None:
    ax.set_xscale("symlog", linthresh=1, linscale=0.5)
    ax.set_xticks(fbt.GC_TICKS)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlim(0, GC[-1])
    ax.set_xlabel("$g_c$ (cycles / element)")


def main() -> None:
    assert not fbt.SMALL, "needs the full fig_best_tile grid"
    base = Params(l1_assoc=-1)
    tiles = [(tm, tn) for tm in TM for tn in fbt.TN]
    params = [replace(base, tile_h=tm, tile_w=tn, gen_cost=gc) for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(fbt.NAME) / "results.json")
    t = {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / fbt.MNK
         for p, s in zip(params, stats)}

    best = {(gc, tn): min((t[(gc, tm, tn)], tm) for tm in TM) for gc in GC for tn in TN}
    square = {(gc, tn): t[(gc, tn, tn)] for gc in GC for tn in TN}
    gain = {k: 100 * (square[k] - best[k][0]) / square[k] for k in best}

    # the overall best tile against the best square tile of any size
    squares = [s for s in fbt.TN if s in TM]
    overall = {gc: min(t[(gc, *tl)] for tl in tiles) for gc in GC}
    best_square = {gc: min(t[(gc, s, s)] for s in squares) for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, tn in enumerate(TN):
        ax.plot(GC, [gain[(gc, tn)] for gc in GC], label=f"$T_N = {tn}$", **series(i))
    ax.plot(GC, [100 * (best_square[gc] - overall[gc]) / best_square[gc] for gc in GC],
            color=INK, linestyle="--", linewidth=2.0, zorder=5, label="best of any size")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g} %"))
    ax.set_ylim(0, 100)
    ax.set_ylabel("time saved vs square tile")
    symlog_gc(ax)
    legend_above(ax, ncols=len(TN) + 1)
    print(save(fig, "tile_choice", NAME))

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, tn in enumerate(TN):
        ax.plot(GC, [best[(gc, tn)][0] for gc in GC], label=f"$T_N = {tn}$", **series(i))
        ax.plot(GC, [square[(gc, tn)] for gc in GC], linestyle="--", linewidth=1.2,
                color=series(i)["color"])
    ax.plot([], [], color="0.4", linestyle="--", linewidth=1.2, label="square")
    ax.set_yscale("log", base=2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_ylabel("cycles / MAC")
    symlog_gc(ax)
    legend_above(ax, ncols=len(TN) + 1)
    print(save(fig, "tile_choice", NAME + "_cost"))

    # overall best tile vs best square tile
    lines = ["| gc | " + " | ".join(f"TN={tn}: best TM, gain" for tn in TN) +
             " | overall best | best square | gain |", "|---" * (len(TN) + 4) + "|"]
    for gc in GC:
        overall = min((t[(gc, *tl)], tl) for tl in tiles)
        sq = min((t[(gc, s, s)], s) for s in fbt.TN if s in TM)
        cells = [f"{best[(gc, tn)][1]}, {gain[(gc, tn)]:.0f} %" for tn in TN]
        lines.append(f"| {gc} | " + " | ".join(cells) +
                     f" | {overall[1]}: {overall[0]:.3f} | {sq[1]}×{sq[1]}: {sq[0]:.3f} | "
                     f"{100 * (sq[0] - overall[0]) / sq[0]:.0f} % |")
    report = "# fig_vs_square: best TM vs square tile (time saved)\n\n" + "\n".join(lines) + "\n"
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
