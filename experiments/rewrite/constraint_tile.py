"""constraint_tile: the best tile when the B tile has a minimum size.

With T_K = K the B tile is K x T_N, so "the B tile must hold at least S_min
elements" means T_N >= S_min / K. Working point, runs, notation and the
gamma_0 axis are those of fifo_feasibility; the runs are read from its cache
(nothing new is simulated unless that cache is missing).

One experiment, constraint_experiment: for every generator cost of the
fifo_feasibility sweep and every minimum width, the best allowed tile and its
cost relative to the unconstrained best, measured and predicted by the max
model from the calibration. Figure: cost.png.

run:  .venv/bin/python experiments/rewrite/constraint_tile.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import fifo_feasibility as ff  # noqa: E402
from harness import out_dir  # noqa: E402

NAME = "constraint_tile"
MINS = (16, 32, 64, 128, 256)          # minimum T_N; 8 is the unconstrained grid


def allowed(tn_min: int) -> list[tuple[int, int]]:
    return [t for t in ff.TILES if t[1] >= tn_min]


def constraint_experiment(out: Path) -> str:
    """Best tile and its cost under T_N >= T_N,min, every g_c of the
    fifo_feasibility sweep. Figure: cost.png. Returns the README."""
    cal = ff.calibrate()
    res = ff.run(ff.sweep_params(cal))         # cached by fifo_feasibility
    knee, af = cal["knee"], cal["alpha_f"]
    gcs = ff.sweep_gcs(cal)
    x = [gc / knee for gc in gcs]

    meas = {m: [ff.best(res, gc, tiles=allowed(m)) for gc in gcs] for m in MINS}
    free = [ff.best(res, gc) for gc in gcs]
    cost = {m: [c / u for (c, _), (u, _) in zip(meas[m], free)] for m in MINS}
    pcost = {m: [ff.predict(cal, gc, tiles=allowed(m))[0] / ff.predict(cal, gc)[0]
                 for gc in gcs] for m in MINS}

    # figure ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    fine = np.geomspace(min(x), max(x), 400)
    for m, color in zip(MINS, ff.RAMP):
        tiles = allowed(m)
        ax.plot(fine, [ff.predict(cal, g * knee, tiles=tiles)[0] / ff.predict(cal, g * knee)[0]
                       for g in fine], color=color, lw=1.2)
        ax.scatter(x, cost[m], s=16, color=color, zorder=3,
                   label=f"$T_N$ ≥ {m}  ({ff.K * m // 1024}K elements)")
    ax.axvline(1, color=ff.AXIS, lw=0.8)
    ax.text(1.03, 0.97, "knee", rotation=90, color=ff.MUTED, fontsize=8, va="top",
            transform=ax.get_xaxis_transform())
    ax.axhline(1, color=ff.INK2, lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("γ₀ = $g_c$ / knee   (as in fifo_feasibility)")
    ax.set_ylabel("best allowed tile / best tile\n(cycles per MAC)")
    ax.set_title("Cost of a minimum B tile width: dots measured, lines predicted "
                 "from the calibration")
    ax.legend(loc="upper left", fontsize=8, title="minimum width (B tile size)",
              title_fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "cost.png")
    plt.close(fig)

    # numbers for the README ----------------------------------------------------
    lim_f = ff.largest_tm(lambda tn: 1.0)
    lim_c = {tn: max((tm for tm in ff.TMS if ff.fill_c(tm, tn) <= 1), default=None)
             for tn in ff.TNS}
    grid = np.geomspace(0.5, gcs[-1], 4000)
    rows = []
    for m in MINS:
        tiles = allowed(m)
        a0, t0 = min((af[t], t) for t in tiles)
        start = next(g for g in grid if ff.predict(cal, g, tiles=tiles)[0] > 1.01 * a0)
        worst, i = max((c, i) for i, c in enumerate(cost[m]))
        worst_txt = (f"{worst:.2f} at γ₀ = {x[i]:.2f}, {ff.tile_str(meas[m][i][1])} "
                     f"against {ff.tile_str(free[i][1])}" if worst > 1.005 else "none")
        rows.append(f"| T_N ≥ {m} | {ff.K * m} | "
                    f"{'one tile column' if m == ff.N else lim_f[m]} | {lim_c[m]} | "
                    f"{ff.tile_str(t0)}, {a0:.4f} | g_c = {start:.1f}, γ₀ = {start / knee:.2f} | "
                    f"{worst_txt} |")

    def at(m: int, g0: float) -> tuple[float, float, str, str]:
        i = min(range(len(x)), key=lambda j: abs(x[j] - g0))
        return cost[m][i], x[i], ff.tile_str(meas[m][i][1]), ff.tile_str(free[i][1])

    small = max(max(cost[16]), max(cost[32]))
    c64, x64, t64, u64 = max((at(64, g) for g in x), key=lambda r: r[0])
    c256, x256, t256, u256 = max((at(256, g) for g in x), key=lambda r: r[0])
    knee_rows = [i for i, g in enumerate(x) if 0.7 < g < 1.3]
    under = [(m, x[i], cost[m][i], pcost[m][i]) for m in MINS for i in knee_rows
             if pcost[m][i] - cost[m][i] > 0.05]
    under_txt = "; ".join(f"T_N ≥ {m} at γ₀ = {g:.2f}: {c:.2f} against {p:.2f}"
                          for m, g, c, p in under[:3])
    err = max(abs(c / p - 1) for m in MINS for c, p in zip(cost[m], pcost[m]))

    theory = f"""
The best allowed tile is the allowed tile with the lowest max(α_f, β). A
minimum width costs nothing as long as some allowed tile both has α close to
α_f0 and hides the generator at that g_c. Two limits from the calibration
decide which tiles qualify as T_N grows:

- f ≤ 1, the A band surviving a tile row. Past it A is read once per tile
  column, so it costs little when there are few tile columns: 8% to 11% at
  T_N = 128, where there are two.
- The limit inside a tile, T_M · (max(T_N·A_P, line) + 2·line) ≤ L1. Past it
  C is read from DRAM again during the tile, and α more than doubles. It caps
  T_M at {lim_c[128]} for T_N = 128 and at {lim_c[256]} for T_N = 256.

A capped T_M means more tile rows, so B is generated more often: β = g_c ⌈M/T_M⌉
/ M. The constraint therefore costs nothing while the generator is hidden at
the capped tile, starts to cost at that tile's own knee, α · M / ⌈M/T_M⌉, and
costs nothing again once g_c is so large that the unconstrained optimum is
itself the widest tall tile (96×256).
"""
    reading = f"""
T_N ≥ 16 and T_N ≥ 32 are close to free: at most {small:.2f} times the
unconstrained best. Wider minimums cost in a band of γ₀ that starts earlier
and gets worse the wider the minimum. T_N ≥ 64 costs up to {c64:.2f} times at
γ₀ = {x64:.2f}, where the unconstrained optimum is {u64} and the constraint
forces {t64}. T_N = 256 means one tile column, the whole of B generated per
tile row. The limit inside a tile then caps T_M at {lim_c[256]}, so B is
generated {ff.tile_rows(lim_c[256])} times, and it costs up to {c256:.2f} times
at γ₀ = {x256:.2f} (best allowed {t256}, against {u256}). At the far right
every curve returns to 1, because the unconstrained optimum is 96×256 there
too.

So the best tile under a minimum width is the tallest allowed tile whose α
stays near α_f0, which is the tile at one of the two limits. It differs from
the unconstrained optimum only between that tile's knee and the point where
the unconstrained optimum itself becomes 96×256.

The max model predicts the costs within {err:.0%} everywhere. The largest
misses are near the knee, where it predicts a cost and the measurement shows
little or none ({under_txt}). Near the knee the measured optimum is already
the wide tile 48×128: each tile starts with an empty FIFO, and fewer, wider
tiles have fewer of those starts. The max model doesn't see the starts, so it
prefers the narrow 48×16 and charges the minimum width for giving it up.
"""
    origin = f"""
The constraint is taken as given here; two properties of the generator bear
on it. A generator that emits a fixed word per step, in the order the core
consumes B, needs a whole number of words per pop. A pop is r²·B_P =
{ff.R * ff.R * ff.B_P} bytes here, one 64-byte word, so the word size puts no
limit on T_N. And each tile's B block is a function of its {ff.SEED}-byte seed,
so there are at most 2^{8 * ff.SEED} different blocks whatever the tile size;
a larger tile does not hold more randomness. A minimum size has to come from
what B is used for.
"""
    issues = """
- The FIFO starts empty at every tile, so near the knee the number of tiles
  matters and wide tiles look better than the max model predicts. Part of why
  a minimum width costs nothing at the knee comes from this restart.
- T_K is always K, so a minimum B tile can only be met by widening T_N. With a
  tile-level T_K, a B tile of T_K × T_N could also grow along K; this
  simulator can't test that.
- T_M moves in steps of 8 (one register block), so the caps above are on that
  grid.
"""
    L = [f"# {NAME}: the best tile when the B tile has a minimum size", "",
         "If B has to be generated in tiles of at least S_min elements, which tile is "
         "best, and what does the constraint cost? With T_K = K the B tile is K × T_N, "
         "so the constraint is T_N ≥ S_min / K. Working point, runs and notation are "
         "those of [fifo_feasibility](../fifo_feasibility/README.md); this experiment "
         "reads its runs and simulates nothing new.", "",
         f"run: `.venv/bin/python experiments/rewrite/{NAME}.py`", "",
         "## What the max model predicts", "", theory.strip(), "",
         "| minimum | S_min, elements | tallest T_M with f ≤ 1 | tallest T_M inside the tile "
         "limit | best allowed tile at g_c = 0, α | predicted to start costing | largest "
         "measured cost |", "|---|---|---|---|---|---|---|", *rows, "",
         "## Results", "", "![cost](cost.png)", "", reading.strip(), "",
         "Cost of each minimum, measured / predicted, and the best allowed tile:", "",
         "| g_c | γ₀ | best tile | " + " | ".join(f"T_N ≥ {m}" for m in MINS) + " |",
         "|---|---|---|" + "---|" * len(MINS)]
    for i, gc in enumerate(gcs):
        L.append(f"| {gc} | {x[i]:.2f} | {ff.tile_str(free[i][1])} | " + " | ".join(
            f"{cost[m][i]:.2f} / {pcost[m][i]:.2f}, {ff.tile_str(meas[m][i][1])}"
            for m in MINS) + " |")
    L += ["", "## Where a minimum could come from", "", origin.strip(), "",
          "## Simulator issues these runs expose", "", issues.strip(), ""]
    return "\n".join(L)


def main() -> None:
    ff.style()
    out = out_dir(NAME)
    (out / "README.md").write_text(constraint_experiment(out))
    print((out / "README.md").read_text())


if __name__ == "__main__":
    main()
