"""constraint_tile-v2: the best tile when the B tile has a minimum size.

The second version of constraint_tile, redone after a review of the first.
The first version and its outputs are kept as they were; the README lists
what changed. With T_K = K the B tile is K x T_N, so "the B tile must hold at
least S_min elements" means T_N >= S_min / K. Working point, runs, notation
and the gamma_0 axis are those of fifo_feasibility-v2, and the runs are read
from its cache (nothing new is simulated unless that cache is missing).

One experiment, constraint_experiment: for every generator cost of the
fifo_feasibility-v2 sweep and every minimum width, the best allowed tile and
its cost against the best tile overall, measured and predicted by the max
model from the calibration, and the cost at the knee for FIFO capacities from
256 bytes to 32 KB. Figure: cost.png, one panel per minimum.

run:  .venv/bin/python experiments/rewrite/constraint_tile-v2.py
"""

from __future__ import annotations

import importlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from harness import out_dir  # noqa: E402

ff = importlib.import_module("fifo_feasibility-v2")   # the file name has a hyphen

NAME = "constraint_tile-v2"
MINS = (16, 32, 64, 128, 256)          # minimum T_N; 8 is the whole grid
COSTS = 1.01                           # a minimum "costs" when 1% slower


def allowed(tn_min: int) -> list[tuple[int, int]]:
    return [t for t in ff.TILES if t[1] >= tn_min]


def bands(xs: list[float], ys: list[float]) -> list[tuple[float, float]]:
    """Runs of consecutive points with y above COSTS, as (first x, last x)."""
    out, start, prev = [], None, None
    for xv, yv in zip(xs, ys):
        if yv > COSTS and start is None:
            start = xv
        if yv <= COSTS and start is not None:
            out.append((start, prev))
            start = None
        prev = xv
    if start is not None:
        out.append((start, prev))
    return out


def bands_str(bs: list[tuple[float, float]]) -> str:
    if not bs:
        return "none"
    return ", ".join(f"{a:.2f}" if a == b else f"{a:.2f} to {b:.2f}" for a, b in bs)


def constraint_experiment(out: Path) -> str:
    """Best tile and its cost under T_N >= T_N,min, at every g_c of the
    fifo_feasibility-v2 sweep, and at the knee for several FIFO capacities.
    Figure: cost.png. Returns the README."""
    cal = ff.calibrate()
    res = ff.run(ff.sweep_params(cal))         # cached by fifo_feasibility-v2
    knee, af = cal["knee"], cal["alpha_f"]
    gcs = ff.sweep_gcs(cal)
    x = [gc / knee for gc in gcs]

    meas = {m: [ff.best(res, gc, tiles=allowed(m)) for gc in gcs] for m in MINS}
    free = [ff.best(res, gc) for gc in gcs]
    cost = {m: [c / u for (c, _), (u, _) in zip(meas[m], free)] for m in MINS}
    pcost = {m: [ff.predict(cal, gc, tiles=allowed(m))[0] / ff.predict(cal, gc)[0]
                 for gc in gcs] for m in MINS}

    # figure: one panel per minimum ------------------------------------------
    fine = np.geomspace(min(x), max(x), 400)
    fig, axes = plt.subplots(1, len(MINS), figsize=(13.2, 3.6), sharey=True)
    for ax, m in zip(axes, MINS):
        tiles = allowed(m)
        ax.plot(fine, [ff.predict(cal, g * knee, tiles=tiles)[0] / ff.predict(cal, g * knee)[0]
                       for g in fine], color=ff.BLUE, lw=1.3, label="max model")
        ax.scatter(x, cost[m], s=14, color=ff.INK, zorder=3, label="measured")
        ax.axvline(1, color=ff.AXIS, lw=0.8)
        ax.axhline(1, color=ff.INK2, lw=0.8)
        ax.set_xscale("log")
        ff.plain_ticks(ax.xaxis, [0.1, 0.5, 1, 2, 4, 16])
        ax.set_title(f"$T_N$ ≥ {m}: B tile ≥ {ff.K * m // 1024}K elements", fontsize=9)
        ax.set_xlabel("γ₀ = $g_c$ / knee")
    axes[0].text(1.06, 2.75, "knee", rotation=90, color=ff.MUTED, fontsize=7.5, va="top")
    axes[0].set_ylabel("best allowed tile / best tile\n(cycles per MAC)")
    axes[0].set_ylim(0.9, 2.85)
    axes[0].legend(loc="upper left", fontsize=7.5)
    fig.suptitle("Cost of a minimum B tile width, 2 KB FIFO", x=0.01, ha="left",
                 fontsize=9.5, color=ff.INK)
    fig.tight_layout()
    fig.savefig(out / "cost.png")
    plt.close(fig)

    # the same at the knee for several FIFO capacities ------------------------
    knee_gc = round(knee)
    dres = ff.run(ff.depth_params(cal))        # cached by fifo_feasibility-v2
    caps = (256, 512, 1024, 2048, 4096, ff.UNLIMITED)
    depth_rows = []
    for d in caps:
        u, ut = ff.best(dres, knee_gc, d)
        cells = [ff.best(dres, knee_gc, d, allowed(m))[0] / u for m in MINS]
        depth_rows.append(f"| {d} | {ff.tiles_str(ut, 1)} | " + " | ".join(f"{c:.2f}" for c in cells) + " |")
    at512 = {m: ff.best(dres, knee_gc, 512, allowed(m))[0] / ff.best(dres, knee_gc, 512)[0] for m in MINS}

    # numbers for the README ----------------------------------------------------
    lim_f = ff.largest_tm(lambda tm, tn: ff.fill(tm, tn, "fifo"))
    lim_t = ff.largest_tm(ff.fill_tile)
    grid = list(np.geomspace(min(gcs), max(gcs), 2000))
    rows = []
    for m in MINS:
        tiles = allowed(m)
        a0 = {t: af[t] for t in tiles}
        p_b = bands([g / knee for g in grid],
                    [ff.predict(cal, g, tiles=tiles)[0] / ff.predict(cal, g)[0] for g in grid])
        worst, i = max((c, i) for i, c in enumerate(cost[m]))
        worst_txt = (f"{worst:.2f} at γ₀ = {x[i]:.2f}: {ff.tiles_str(meas[m][i][1], 1)} against "
                     f"{ff.tiles_str(free[i][1], 1)}" if worst > COSTS else "none")
        rows.append(f"| T_N ≥ {m} | {ff.K * m:,} | "
                    f"{'one tile column' if m == ff.N else lim_f[m]} | {lim_t[m]} | "
                    f"{ff.tiles_str(ff.ranked(a0), 1)}, {min(a0.values()):.4f} | "
                    f"{bands_str(p_b)} | {bands_str(bands(x, cost[m]))} | {worst_txt} |")

    errs = [(c / p - 1, m, i) for m in MINS for i, (c, p) in enumerate(zip(cost[m], pcost[m]))]
    e_max, m_max, i_max = max(errs, key=lambda e: abs(e[0]))
    above = [(m, gcs[i]) for e, m, i in errs if e > 0.05]
    below = [(m, gcs[i]) for e, m, i in errs if e < -0.05]
    t_pred = ff.predict(cal, gcs[i_max], tiles=allowed(m_max))[1]
    b_pred, a_pred = ff.beta(gcs[i_max], t_pred[0]), af[t_pred]

    def cells(pairs: list[tuple[int, int]]) -> str:
        by_m: dict[int, list[int]] = {}
        for m, gc in pairs:
            by_m.setdefault(m, []).append(gc)
        return "; ".join(f"T_N ≥ {m} at g_c = {', '.join(map(str, v))}" for m, v in by_m.items())

    def back_to_one(m: int) -> str:
        # the gamma_0 from which the cost stays below COSTS, and the allowed
        # tile that is that close to the best there
        i = max((i for i in range(len(x)) if cost[m][i] > COSTS), default=None)
        if i is None or i + 1 >= len(x):
            return "never on this grid"
        return f"from γ₀ = {x[i + 1]:.2f} ({ff.tile_str(meas[m][i + 1][1][0])})"

    two = [m for m in MINS if len(bands(x, cost[m])) == 2]

    w32, i32 = max((c, i) for i, c in enumerate(cost[32]))
    theory = f"""
The best allowed tile is the allowed tile with the lowest max(α_f, β), and a
minimum width costs nothing whenever the best tile overall is itself allowed.
Two limits from the calibration decide which wide tiles keep α near α_f0:

- f ≤ 1, the A band surviving a tile row. Past it A is read again for every
  tile column, which costs little when there are few tile columns: 8% to 11%
  at T_N = 128, where there are two.
- The tile limit, T_M · (max(T_N·A_P, line) + 2·line) ≤ L1. Past it C is read
  from DRAM again inside the tile and α more than doubles. It caps T_M at
  {lim_t[128]} for T_N = 128 and at {lim_t[256]} for T_N = 256.

While the generator is hidden, the best allowed tile is the tallest allowed
tile inside both limits. Once β dominates, the best allowed tile is the one
with the fewest tile rows, whatever its α, because β = g_c ⌈M/T_M⌉ / M then
sets the time. A minimum costs in between: from the g_c where generation
starts to show at the allowed tiles until the best tile overall is allowed
again.
"""
    reading = f"""
T_N ≥ 16 {'costs nothing: the best tile overall is always at least 16 wide' if max(cost[16]) == 1 else f'never costs more than {max(cost[16]) - 1:.1%}'}. T_N ≥ 32 costs up to
{w32 - 1:.0%}, at γ₀ = {x[i32]:.2f} ({ff.tiles_str(meas[32][i32][1], 1)}
against {ff.tiles_str(free[i32][1], 1)}). Wider minimums cost in bands of γ₀
that start earlier and cost more the wider the minimum; the bands are in the
table above. {' and '.join(f'T_N ≥ {m}' for m in two)} have two bands each,
with no cost between them: around the knee the best tile overall is 48×128,
which they allow. Each wide minimum costs less than 1% again once an allowed
tile comes within 1% of the best: T_N ≥ 64 {back_to_one(64)}, T_N ≥ 128
{back_to_one(128)} and T_N ≥ 256 {back_to_one(256)}. Where tiles tie within
0.5% the table lists them, and which one is named is only the tie rule.

These costs are for the 2 KB FIFO. Near the knee the best tile overall needs
that depth: with 512 bytes the best tile is 48×16 and every minimum from
T_N ≥ 32 up costs at least {min(at512[m] for m in MINS if m >= 32) - 1:.1%}
(table below). With 2 KB and more the best tile overall is 48×128 and
T_N ≥ 32, 64 and 128 cost nothing at the knee.

The max model predicts the costs within {abs(e_max):.0%}. Its largest miss is
at γ₀ = {x[i_max]:.2f} for T_N ≥ {m_max}: measured {cost[m_max][i_max]:.2f},
predicted {pcost[m_max][i_max]:.2f}. There the tile the model picks,
{ff.tile_str(t_pred)}, sits at its own γ ≈ 1 (β = {b_pred:.3f}, α =
{a_pred:.3f}), where the max model is weakest (see the composites in
fifo_feasibility-v2). The model under-predicts the cost by more than 5% at
{len(above)} points ({cells(above)}) and over-predicts it by more than 5% at
{len(below)} ({cells(below) if below else 'none'}).
"""
    issues = """
- The FIFO starts empty at every tile, so the lead the generator builds while
  the core is slow in one tile can't carry into the next. Near γ = 1 that
  favours tiles whose core work is the same in every tile: 48×128, with f > 1,
  reads A again in every tile, and that is why it beats 48×16 at the knee with
  a 2 KB FIFO and why T_N ≥ 32 to 128 cost nothing there.
- T_K is always K, so a minimum B tile can only be met by widening T_N. With a
  tile-level T_K, a B tile of T_K × T_N could also grow along K; this
  simulator can't test that.
"""
    changes = """
The first version is `constraint_tile.py`, with its outputs in
`out/constraint_tile/`; both are unchanged. A review found its table right
and two of its conclusions wrong. This version states the best-tile rule as
the minimum of max(α, β) over the allowed tiles (the first version said the
best tile always sits at one of the two limits), gives the cost bands from
the data, reports where the max model misses in both directions (the largest
miss is far past the knee, not near it), marks ties, shows how the cost at the
knee depends on FIFO depth, draws one panel per minimum, and drops the
section on where a minimum could come from, which was outside the question.
"""
    L = [f"# {NAME}: the best tile when the B tile has a minimum size", "",
         "If B has to be generated in tiles of at least S_min elements, which tile is "
         "best, and what does the constraint cost? With T_K = K the B tile is K × T_N, "
         "so the constraint is T_N ≥ S_min / K. Working point, runs and notation are "
         "those of [fifo_feasibility-v2](../fifo_feasibility-v2/README.md); this experiment "
         "reads its runs and simulates nothing new. The tiles are its grid: T_M from 8 to "
         "96 in steps of 8 and T_N from 8 to 256, and a minimum keeps the tiles with "
         "T_N ≥ T_N,min. A minimum costs when the best allowed tile is more than 1% slower "
         "than the best tile overall. Tiles within 0.5% of the best are ties; the one named "
         "first has the fewest tile rows.", "",
         f"run: `.venv/bin/python experiments/rewrite/{NAME}.py`", "",
         "## Changes from the first version", "", changes.strip(), "",
         "## What the max model predicts", "", theory.strip(), "",
         "| minimum | S_min, elements | tallest T_M with f ≤ 1 | tallest T_M inside the tile "
         "limit | best allowed tile at g_c = 0, α | γ₀ where it costs, max model | γ₀ where "
         "it costs, measured | largest measured cost |",
         "|---|---|---|---|---|---|---|---|", *rows, "",
         "## Results", "", "![cost](cost.png)", "", reading.strip(), "",
         f"Cost of each minimum at the knee (g_c = {knee_gc}) by FIFO capacity:", "",
         "| capacity, bytes | best tile overall | " + " | ".join(f"T_N ≥ {m}" for m in MINS) + " |",
         "|---|---|" + "---|" * len(MINS), *depth_rows, "",
         "Cost of each minimum with the 2 KB FIFO, measured / max model, and the best "
         "allowed tile:", "",
         "| g_c | γ₀ | best tile overall | " + " | ".join(f"T_N ≥ {m}" for m in MINS) + " |",
         "|---|---|---|" + "---|" * len(MINS)]
    for i, gc in enumerate(gcs):
        L.append(f"| {gc} | {x[i]:.2f} | {ff.tiles_str(free[i][1], 1)} | " + " | ".join(
            f"{cost[m][i]:.2f} / {pcost[m][i]:.2f}, {ff.tiles_str(meas[m][i][1], 1)}"
            for m in MINS) + " |")
    L += ["", "## Simulator issues these runs expose", "", issues.strip(), ""]
    return "\n".join(L)


def main() -> None:
    ff.style()
    out = out_dir(NAME)
    (out / "README.md").write_text(constraint_experiment(out))
    print((out / "README.md").read_text())


if __name__ == "__main__":
    main()
