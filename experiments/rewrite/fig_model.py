"""F3: the model's two costs against TM, at TN = 32 (default setup).

  - alpha(TM): measured at gc = 0 (solid);
  - the B term gc * ceil(M/TM) / M for two gc values (dashed staircases);
  - the measured runtime T / MNK at those gc values (markers).

The model predicts T / MNK = max(alpha, B term) + startup, so the markers
should follow the upper envelope of the solid line and the staircase.
gc = 30: B falls below alpha at TM ~ 32, the optimum is alpha-bound.
gc = 200: B dominates almost everywhere, the optimum moves to the largest
tiles (TM = 128: only 2 rows of tiles).

SMALL=True runs a quick sample first (TM in steps of 8).

run:  .venv/bin/python experiments/rewrite/fig_model.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import SERIES, legend_above, plt, save, series

NAME = "fig_model"
SMALL = False
TM = [4] + list(range(8, 129, 8)) if SMALL else list(range(4, 129, 4))
TN = 32
GC = [30, 100, 200]
M, K, N = 192, 256, 256
MNK = M * K * N


def b_term(gc: int, tm: int) -> float:
    return gc * -(-M // tm) / M


def b_simple(gc: int, tm: float) -> float:
    return gc / tm


# fig_model_simple: the simple model's B term gc / TM (report 3.3.3; the
# markers break away from it where TM does not divide M); fig_model: the
# refined staircase gc * ceil(M/TM) / M (report 3.3.4)
VARIANTS = {"fig_model_simple": b_simple, "fig_model": b_term}


def main() -> None:
    base = Params(tile_w=TN, l1_assoc=-1)
    params = [replace(base, tile_h=tm, gen_cost=gc) for gc in [0] + GC for tm in TM]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.gen_cost, p.tile_h): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    for name, b in VARIANTS.items():
        fig, ax = plt.subplots(figsize=(7.0, 4.0))
        ax.plot(TM, [t[(0, tm)] for tm in TM], label=r"$\alpha$ ($g_c = 0$)", **series(0))
        # blank legend entry, so that each legend column holds one gc (model above measured)
        ax.plot([], [], linestyle="none", label=" ")
        for i, gc in enumerate(GC, start=1):
            dense = [x / 4 for x in range(4 * TM[0], 4 * TM[-1] + 1)]
            ax.plot(dense, [b(gc, x) if b is b_simple else b(gc, int(x)) for x in dense],
                    color=SERIES[i], linestyle="--", linewidth=1.4,
                    label=f"B term, $g_c = {gc}$")
            ax.plot(TM, [t[(gc, tm)] for tm in TM], linestyle="none",
                    label=f"measured, $g_c = {gc}$", **series(i))

        ax.set_xlabel("$T_M$")
        ax.set_ylabel("cycles / MAC")
        ax.set_xlim(0, max(TM) + 4)
        ax.set_ylim(0, 6)
        legend_above(ax, ncols=1 + len(GC))
        print(save(fig, "model", name + ("_small" if SMALL else "")))


if __name__ == "__main__":
    main()
