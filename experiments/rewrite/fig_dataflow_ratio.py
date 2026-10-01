"""F4b: does C-stationary end up worse than B-stationary for every tile?
T_C / T_B against gc, at TN = 32, one line per TM (default setup).

Each line starts below 1 (C wins while gc / R_M < alpha_B), crosses 1 at its
own crossover gc* = R_M * alpha_B, and rises towards M / (R_M * ceil(M/TM))
(the ratio of the two generation costs, gc/R_M vs gc*ceil(M/TM)/M; = TM/R_M
when TM divides M) once both dataflows are generation-bound. TM = R_M = 4
stays at 1: B-stationary then reuses each element over only 4 rows, exactly
like C-stationary. At gc = 100: TM 8/16/32/64 reach 2/4/8/16 exactly; TM = 128
is still memory-bound (its tile thrashes, alpha ~3.0), so it sits at ~8 and
would reach its limit 24 only for gc >~ 290.

Checked on 85 tiles (see TODO_EXPER.md, F4): C is slower on every tile with
TM > 4; the predicted crossover is right on 80/85 (the misses are TM = 4).

SMALL=True runs a quick sample first (gc in steps of 5).

run:  .venv/bin/python experiments/rewrite/fig_dataflow_ratio.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import GRID, INK_2, legend_above, plt, save, series

NAME = "fig_dataflow_ratio"
SMALL = False
GC = list(range(0, 101, 5)) if SMALL else list(range(0, 101))
TM = [4, 8, 16, 32, 64, 128]
TN = 32
MNK = 192 * 256 * 256


def main() -> None:
    base = Params(tile_w=TN, l1_assoc=-1)
    params = [replace(base, orientation=o, tile_h=tm, gen_cost=gc)
              for o in ("weight", "output") for tm in TM for gc in GC]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.orientation, p.tile_h, p.gen_cost): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.axhline(1, color=INK_2, linewidth=1.0, zorder=1)
    for i, tm in enumerate(TM):
        ratio = [t[("output", tm, gc)] / t[("weight", tm, gc)] for gc in GC]
        ax.plot(GC, ratio, label=f"$T_M = {tm}$",
                markevery=1 if SMALL else 5, **series(i))

    ax.set_yscale("log", base=2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.grid(True, which="major", color=GRID)
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel(r"$T_C \,/\, T_B$")
    ax.set_xlim(0, GC[-1])
    legend_above(ax, ncols=len(TM))
    print(save(fig, "dataflow", NAME + ("_small" if SMALL else "")))

    for tm in TM:
        r = t[("output", tm, GC[-1])] / t[("weight", tm, GC[-1])]
        limit = 192 / (4 * -(-192 // tm))   # M / (R_M * ceil(M/TM)), = TM/R_M if TM | M
        print(f"  TM={tm:>3}: T_C/T_B at gc={GC[-1]} = {r:.2f}  (generation-bound limit {limit:g})")


if __name__ == "__main__":
    main()
