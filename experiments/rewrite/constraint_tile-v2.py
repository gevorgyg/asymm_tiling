"""constraint_tile-v2: the FIFO when the generator needs large B tiles.

The second version of constraint_tile, redone after a review of the first.
The first version and its outputs are kept as they were; the README lists
what changed. A generator that has to make at least S_min elements from each
seed needs B tiles of at least S_min elements. With T_K = K the B tile is
K x T_N, so the tiles have to be at least S_min / K wide. Working point and
notation are those of fifo_feasibility-v2. Its cached runs give every graph
but the FIFO-size one, whose runs are cached in out/constraint_tile-v2/.

Three experiments. Each is one function that returns its README section and
draws its graphs, each by its own plot_ function:

  minimum_experiment     the fastest tile under each minimum width at every
                         generator cost, against memory-B, and the tile each
                         minimum runs near its limit -> tiles.png, core.png,
                         cycles.png
  depth_experiment       the slowest generator that still beats memory-B,
                         against FIFO capacity, on those tiles -> depth.png
  composites_experiment  what each minimum costs against gamma_0, with the
                         fastest tile written in every point ->
                         composites/no_minimum.png, composites/cost_min*.png

run:  .venv/bin/python experiments/rewrite/constraint_tile-v2.py
"""

from __future__ import annotations

import importlib
import math
from itertools import groupby
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from harness import out_dir, run_many  # noqa: E402

ff = importlib.import_module("fifo_feasibility-v2")   # the file name has a hyphen

NAME = "constraint_tile-v2"
MINS = (8, 16, 32, 64, 128, 256, 512)   # minimum T_N; 8 allows every tile
MEM_TILE = ff.PAIR[0]                   # 32x16, one of memory-B's three fastest tiles
COSTS = 1.01                            # a minimum "costs" when 1% slower
# the map's diverging scale: blue below memory-B, gray at it, red above
DIVERGING = ("#0d366b", "#256abf", "#9ec5f4", "#f0efec", "#f2aaa6", "#e34948", "#9c2a29")


def allowed(m: int) -> list[tuple[int, int]]:
    return [t for t in ff.TILES if t[1] >= m]


def height(tm: int) -> float:
    """MACs per generated element of B. B is generated once per tile row, so
    each element serves M / ceil(M / T_M) MACs: T_M when T_M divides M."""
    return ff.M / ff.tile_rows(tm)


def limit_tile(cal: dict, m: int) -> tuple[int, int]:
    """The tile a minimum width runs with the slowest generator it can use:
    of the tiles at least m wide whose cycles per MAC at g_c = 0 are below
    memory-B's, the one whose elements of B serve the most MACs, and the
    faster one if two serve as many."""
    af, mem = cal["alpha_f"], cal["alpha_m"][MEM_TILE]
    return max((t for t in allowed(m) if af[t] < mem), key=lambda t: (height(t[0]), -af[t]))


def run(params: list) -> dict:
    """Stats of the runs this experiment adds to fifo_feasibility-v2's,
    cached in out/constraint_tile-v2/results.json."""
    return dict(zip(params, run_many(params, out_dir(NAME) / "results.json")))


def rng(vals, fmt: str = ".2f") -> str:
    lo, hi = f"{min(vals):{fmt}}", f"{max(vals):{fmt}}"
    return lo if lo == hi else f"{lo} to {hi}"


def size(d: int) -> str:
    return f"{d // 1024} KB" if d >= 1024 else f"{d} B"


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
    return ", ".join(f"{a:.2f}" if a == b else f"{a:.2f} to {b:.2f}" for a, b in bs)


def minimums(ms: list[int]) -> str:
    return ", ".join(map(str, ms))


def span(vals: list[int]) -> str:
    """'a' or 'a to b', with thousands separators."""
    return f"{vals[0]:,}" if len(vals) == 1 else f"{vals[0]:,} to {vals[-1]:,}"


# ---- figures: one function per graph -------------------------------------------
def plot_tiles(gcs: list[int], cells: dict, mem: float, path: Path) -> None:
    """The fastest tile at least T_N,min wide for every minimum (across) and
    g_c (up), with its cycles per MAC, on a diverging scale whose middle is
    memory-B's fastest tile."""
    grid = np.array([[cells[(m, gc)][0] for m in MINS] for gc in gcs])
    norm = TwoSlopeNorm(vmin=grid.min(), vcenter=mem, vmax=grid.max())
    fig, ax = plt.subplots(figsize=(9.4, 0.5 * len(gcs) + 2.0))
    im = ax.imshow(grid, cmap=LinearSegmentedColormap.from_list("div", DIVERGING), norm=norm,
                   origin="lower", aspect="auto")
    for i, gc in enumerate(gcs):
        for j, m in enumerate(MINS):
            v, t = cells[(m, gc)]
            ax.text(j, i, f"{v:.3f}\n{ff.tile_str(t)}", ha="center", va="center", fontsize=8,
                    linespacing=1.25, color="white" if abs(norm(v) - 0.5) > 0.3 else ff.INK)
    ax.set_xticks(range(len(MINS)), MINS)
    ax.set_yticks(range(len(gcs)), gcs)
    ax.grid(False)
    ax.set_xlabel("minimum $T_N$")
    ax.set_ylabel("$g_c$ [cycles]")
    top = ax.secondary_xaxis("top")
    top.set_xticks(range(len(MINS)), [f"{ff.K * m:,}" for m in MINS])
    top.set_xlabel("$S_{min} = K\\,T_N$ [elements]")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("cycles per MAC", fontsize=11)
    lo, hi = grid.min(), grid.max()
    ticks = [v for v in (0.42, 0.46, 0.50) if lo < v < mem] + [mem]
    ticks += [v for v in (0.75, 1.0, 1.5, 2.0, 3.0) if mem < v < hi]
    cb.set_ticks(ticks, labels=[f"{v:.3g}" for v in ticks])
    ff.save(fig, path)


def plot_core(alpha: dict, mem: float, path: Path) -> None:
    """Cycles per MAC with a free generator against T_M, one line per T_N of
    a minimum, and memory-B's fastest tile."""
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for tn, color in zip(MINS[1:], ff.CATS):
        ax.plot(ff.TMS, [alpha[(tm, tn)] for tm in ff.TMS], color=color, marker="o", ms=3.5,
                lw=1.4, label=f"$T_N$ = {tn}")
    ax.axhline(mem, color=ff.MUTED, lw=1.2, ls="--",
               label=f"B from memory, {ff.tile_str(MEM_TILE)}")
    ff.log_axis(ax.yaxis, [0.4, 0.5, 0.6, 0.8, 1, 1.5, 2])
    ax.set_xticks(ff.TMS)
    ax.set_xlabel("$T_M$")
    ax.set_ylabel("cycles per MAC at $g_c$ = 0")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ff.save(fig, path)


def plot_cycles(gcs: list[int], lines: dict[str, list[float]], mem: float, path: Path,
                xmax: float, ymax: float) -> None:
    """Cycles per MAC against g_c on the tiles the minimums run near their
    limit, 2 KB FIFO, and memory-B's fastest tile. Linear axes, so a line is
    flat and then straight."""
    fig, ax = ff.new_axes()
    for (label, ys), color in zip(lines.items(), ff.CATS):
        ax.plot(gcs, ys, color=color, marker="o", ms=3, lw=1.4, label=label)
    ax.axhline(mem, color=ff.MUTED, lw=1.2, ls="--",
               label=f"B from memory, {ff.tile_str(MEM_TILE)}")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("$g_c$ [cycles]")
    ax.set_ylabel("cycles per MAC")
    ax.legend(loc="lower right")
    ff.save(fig, path)


def plot_depth(caps: tuple[int, ...], lines: dict[str, list[float]], path: Path) -> None:
    """The largest g_c at which the FIFO beats memory-B's fastest tile,
    against FIFO capacity, one line per tile."""
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    xs = range(len(caps))
    for (label, ys), color in zip(lines.items(), ff.CATS):
        ax.plot(xs, ys, color=color, marker="o", ms=3.5, lw=1.4, label=label)
    ax.set_xticks(xs, [f"{d // 1024}K" if d >= 1024 else str(d) for d in caps])
    ff.log_axis(ax.yaxis, [2, 3, 5, 10, 20, 30])
    ax.set_ylim(2, 35)
    ax.set_xlabel("FIFO capacity [bytes]")
    ax.set_ylabel("largest $g_c$ at which the FIFO wins [cycles]")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    ff.save(fig, path)


def plot_fastest(xs: list[float], ys: list[float], tiles: list, xlabel: str, path: Path) -> None:
    """Cycles per MAC on the fastest tile of any width against gamma_0, the
    tile written in every point."""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ff.draw_tile_points(ax, xs, ys, tiles, ff.BLUE)
    ff.log_axis(ax.xaxis, [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20])
    ff.log_axis(ax.yaxis, [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5])
    ff.pad_log(ax, ys)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("FIFO cycles per MAC on best_tile\n"
                  "best_tile: the fastest tile of any width at this $g_c$", fontsize=10)
    ff.save(fig, path)


def plot_cost(xs: list[float], ys: list[float], tiles: list, m: int, xlabel: str,
              path: Path) -> None:
    """What the minimum T_N >= m costs against gamma_0, the fastest allowed
    tile written in every point, and no cost at 1."""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ff.draw_tile_points(ax, xs, ys, tiles, ff.ORANGE)
    ax.axhline(1, color=ff.MUTED, lw=1.2, ls="--", zorder=1)
    ff.log_axis(ax.xaxis, [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20])
    span = max(max(ys) - 1, 0.05)
    ax.set_ylim(1 - 0.16 * span, max(ys) + 0.16 * span)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("FIFO cycles per MAC on best_tile\n/ on the fastest tile of any width\n"
                  f"best_tile: the fastest tile with $T_N$ ≥ {m} at this $g_c$", fontsize=10)
    ax.legend(handles=[Line2D([], [], color=ff.ORANGE, lw=1.3, label=f"minimum $T_N$ = {m}"),
                       Line2D([], [], color=ff.MUTED, lw=1.2, ls="--", label="no minimum")],
              loc="upper left")
    ff.save(fig, path)


# ---- experiments ----------------------------------------------------------------
def minimum_experiment(cal: dict, res: dict, out: Path) -> tuple[dict, str]:
    """The fastest tile under every minimum width at every generator cost of
    the fifo_feasibility-v2 sweep, against memory-B's fastest tile, and the
    tile each minimum runs with the slowest generator it can use. Graphs:
    tiles.png, core.png, cycles.png."""
    af, am = cal["alpha_f"], cal["alpha_m"]
    mem = am[MEM_TILE]
    assert mem == cal["a_m0"], "MEM_TILE is not one of memory-B's fastest tiles"
    gcs = ff.all_gcs(cal)
    fastest = {(m, gc): ff.best(res, gc, tiles=allowed(m)) for m in MINS for gc in gcs}
    wins = {m: ff.crossing(gcs, [mem / fastest[(m, gc)][0] for gc in gcs]) for m in MINS}
    rows = [gc for gc in ff.sweep_gcs(cal) if gc <= 2 * max(wins.values())]
    plot_tiles(rows, {(m, gc): (fastest[(m, gc)][0], fastest[(m, gc)][1][0])
                      for m in MINS for gc in rows}, mem, out / "tiles.png")
    plot_core(af, mem, out / "core.png")

    # the tile each minimum runs near its limit, and the minimums it serves
    groups: dict[tuple[int, int], list[int]] = {}
    for m in MINS:
        groups.setdefault(limit_tile(cal, m), []).append(m)
    tiles = list(groups)
    first, second, *rest = tiles
    assert height(first[0]) == height(second[0]), "the text assumes two equally tall tiles"
    rule = {t: height(t[0]) * mem for t in tiles}
    xmax = min(gc for gc in ff.sweep_gcs(cal) if gc >= 1.5 * max(wins.values()))
    near = [gc for gc in gcs if gc <= xmax]
    plot_cycles(near, {f"FIFO on {ff.tile_str(t)}: minimum $T_N$ = {minimums(ms)}":
                       [ff.cpm(res[ff.fifo(t, gc)]) for gc in near] for t, ms in groups.items()},
                mem, out / "cycles.png", xmax, 2 * mem)

    # numbers for the README ----------------------------------------------------
    gc1 = gcs[0]
    at1 = [fastest[(m, gc1)][0] for m in MINS]
    cost = [(fastest[(m, gc)][0] / fastest[(MINS[0], gc)][0], -m, gc)
            for m in groups[second] for gc in gcs if gc < wins[m]]
    c_top, m_top, gc_top = max(cost)
    m_top = -m_top
    v_top, t_top = fastest[(m_top, gc_top)][0], fastest[(m_top, gc_top)][1][0]
    v_free, t_free = fastest[(MINS[0], gc_top)][0], fastest[(MINS[0], gc_top)][1][0]
    lim_f = ff.largest_tm(lambda tm, tn: ff.fill(tm, tn, "fifo"))
    lim_t = ff.largest_tm(ff.fill_tile)
    several = [tn for tn in MINS[1:] if ff.N // tn > 1]
    fit = [af[t] for t in ff.TILES if ff.N // t[1] > 1 and ff.fill(*t) <= 1]
    beyond = [af[t] for t in ff.TILES if ff.fill_tile(*t) > 1]
    spill = [t for t in tiles if ff.fill(*t) > 1 and ff.N // t[1] > 1]
    optimism = [1 - wins[m] / rule[t] for t, ms in groups.items() for m in ms]
    table = ["| minimum T_N | S_min, elements | tallest tile below memory-B | its cycles per MAC "
             "at g_c = 0 | slowest g_c by the rule | measured, 2 KB FIFO |",
             "|---|---|---|---|---|---|"]
    table += [f"| {span(ms)} | {span([ff.K * m for m in ms])} | {ff.tile_str(t)} | "
              f"{af[t]:.3f} | {rule[t]:.1f} | {rng([wins[m] for m in ms], '.1f')} |"
              for t, ms in groups.items()]
    narrower = and_or([f"T_N ≥ {minimums(groups[t])} to g_c = {rng([wins[m] for m in groups[t]], '.1f')}"
                       for t in rest])
    mem_tiles = ff.and_list(ff.tile_str(t) for t in cal["ties_m"])

    text = f"""
## Which tile to run, and when to load B instead

![the fastest tile for each minimum width and g_c](tiles.png)

The map has a column for each minimum width, from T_N ≥ {MINS[0]}, which allows
every tile, to T_N ≥ {MINS[-1]}, and a row for each generator cost up to
g_c = {rows[-1]}. The top axis gives the same minimum as S_min = K·T_N
elements. Each cell names the fastest tile at least that wide and its cycles
per MAC with the 2 KB FIFO. Tiles within 0.5% of each other count as tied, and
the cell names the one with the fewest tile rows. Memory-B's fastest tiles,
{mem_tiles}, take {mem:.3f} cycles per MAC, the gray middle of the colour
scale: blue cells beat memory-B, red cells lose to it.

- With a fast generator the minimum hardly matters. At g_c = {gc1} the fastest
  tile under every minimum takes {rng(at1, '.3f')} cycles per MAC, because
  every width has a tile short enough to keep in L1 what its tile row reuses.
- For minimums up to T_N ≥ {groups[second][-1]}, B tiles of {ff.K * groups[second][-1]:,} elements, the
  FIFO still beats memory-B while g_c < {rng([wins[m] for m in groups[second]], '.1f')}, against
  {wins[MINS[0]]:.1f} with no minimum. A wide minimum allows only short tiles
  that keep A in L1, and a short tile can't hide as slow a generator, so the
  FIFO moves to {ff.tile_str(second)} at {af[second]:.3f} cycles per MAC. While the FIFO
  still wins, that costs up to {c_top - 1:.0%}: at g_c = {gc_top}, T_N ≥ {m_top} runs
  {ff.tile_str(t_top)} at {v_top:.3f} cycles per MAC, against {v_free:.3f} on {ff.tile_str(t_free)} with
  no minimum.
- Wider minimums cut the slowest generator that still wins: {narrower}.
- A generator slower than {wins[MINS[0]]:.1f} cycles per element loses to memory-B under
  every minimum and with none, so there the minimum doesn't change the
  decision.

## Why, and how to find the tile for your own minimum

![cycles per MAC at g_c = 0 against T_M](core.png)

Cycles per MAC with a generator that costs nothing, against the tile's
height, one line per width, and memory-B's {mem:.3f} dashed. While the A band
and two C tiles fit in L1 (f ≤ 1), a tile takes {rng(fit, '.3f')} cycles per MAC.
A wider tile has a wider C tile, so fewer rows fit: the tallest tile with
f ≤ 1 is {ff.and_list(f"{lim_f[tn]} rows at T_N = {tn}" for tn in several)}. At T_N = {ff.N}
there is one tile column, so only the tile limit applies, and it allows
{lim_t[ff.N]} rows. Past f = 1, A is read again for every tile column, which costs
little when there are few: {ff.and_list(f"{ff.tile_str(t)} takes {af[t]:.3f} cycles per MAC with {ff.N // t[1]} tile columns" for t in spill)}.
Past the tile limit, T_M·(max(T_N·A_P, line) + 2·line) > L1, the C tile no
longer stays in L1 from one k step to the next, and the cost jumps to
{rng(beyond, '.1f')} cycles per MAC.

The generator sets the other half. B is generated once per tile row, so each
element serves T_M MACs. Section 1 of fifo_feasibility-v2 found that a tile
then takes about

```
FIFO cycles per MAC ≈ max(cycles per MAC at g_c = 0, g_c · ⌈M/T_M⌉ / M)
```

A tile therefore beats memory-B while its point in the graph is below the
dashed line and g_c < T_M × {mem:.3f}, with M/⌈M/T_M⌉ in place of T_M when T_M
doesn't divide M. The slower the generator, the taller the tile it needs.
Under a minimum, the tile for the slowest generator is the tallest one at
least that wide whose point is below the dashed line:

{chr(10).join(table)}

The rule is {rng([100 * o for o in optimism], '.0f')}% optimistic. The FIFO-size section shows where
the gap comes from.

## The four tiles against g_c

![cycles per MAC against g_c on the four tiles](cycles.png)

Cycles per MAC against g_c on the tiles of the table, with the 2 KB FIFO, and
memory-B dashed. Each line stays at its cost with a free generator until
g_c · ⌈M/T_M⌉ / M overtakes it, and climbs from there. {ff.tile_str(second)} starts
{af[second] - af[first]:.3f} cycles per MAC above {ff.tile_str(first)}, but both are {first[0]} rows tall, so
from g_c ≈ {round(height(first[0]) * af[second])} they climb together and cross memory-B at nearly the same
g_c. The shorter tiles climb faster, because B is generated once per tile
row: {ff.and_list(f"{ff.tile_rows(t[0])} times on {ff.tile_str(t)}" for t in rest)}, against
{ff.tile_rows(first[0])} times on the {first[0]}-row tiles.
"""
    data = {"groups": groups, "rule": rule, "wins": wins, "mem": mem}
    return data, text.strip()


def and_or(items: list[str]) -> str:
    """'a', 'a and b', 'a, b and c' for clauses."""
    return ff.and_list(items) if items else "none"


def depth_experiment(cal: dict, data: dict, out: Path) -> str:
    """The slowest generator at which each tile of minimum_experiment's table
    still beats memory-B's fastest tile, for FIFO capacities from 64 B to
    64 KB. Graph: depth.png."""
    af, mem, groups, rule = cal["alpha_f"], data["mem"], data["groups"], data["rule"]
    caps = ff.DEPTHS[1:]
    gcs = {t: list(range(1, math.ceil(1.3 * rule[t]) + 1)) for t in groups}
    params = [ff.fifo(t, gc, d) for t in groups for gc in gcs[t] for d in caps]
    res = run(params)

    def limit(t: tuple[int, int], d: int) -> float:
        ys = [mem / ff.cpm(res[ff.fifo(t, gc, d)]) for gc in gcs[t]]
        return ff.crossing(gcs[t], ys) if ys[0] >= 1 else math.nan

    lines = {t: [limit(t, d) for d in caps] for t in groups}
    plot_depth(caps, {f"FIFO on {ff.tile_str(t)}: minimum $T_N$ = {minimums(ms)}": lines[t]
                      for t, ms in groups.items()}, out / "depth.png")

    first, *_ = groups
    reach = [t for t in groups if lines[t][-1] >= 0.99 * rule[t]]
    short = [t for t in groups if t not in reach]
    two = caps.index(ff.FIFO_BYTES)
    table = ["| tile | minimum T_N | slowest g_c by the rule | 2 KB FIFO | 64 KB FIFO | elements made "
             "during the C tile's misses, at the rule's g_c | smallest FIFO within 1% of 64 KB |",
             "|---|---|---|---|---|---|---|"]
    for t, ms in groups.items():
        enough = next(d for d, g in zip(caps, lines[t]) if g >= 0.99 * lines[t][-1])
        table.append(f"| {ff.tile_str(t)} | {minimums(ms)} | {rule[t]:.1f} | {lines[t][two]:.1f} | "
                     f"{lines[t][-1]:.1f} | {ff.burst(t, rule[t]):,.0f} | {size(enough)} |")
    gap = [1 - lines[t][-1] / rule[t] for t in short]
    text = f"""
## How big a FIFO

![largest g_c at which the FIFO wins, against FIFO capacity](depth.png)

The slowest generator at which each tile of the table still beats memory-B
on {ff.tile_str(MEM_TILE)}, against FIFO capacity. The wider the tile, the larger the FIFO it
needs to get to the rule's limit.

{chr(10).join(table)}

At the start of every tile the FIFO is empty, and the core reads every line
of the C tile from DRAM, one miss after another (fifo_feasibility-v2,
simulator issues). The generator works ahead during those misses. A FIFO
that holds what it makes there, T_M·⌈T_N·A_P/line⌉·(t_mem + t_1) / g_c
elements, keeps that lead for the rest of the tile. A wider tile has a wider
C tile and a longer stretch of misses. With that much FIFO,
{ff.and_list(ff.tile_str(t) for t in reach)} reach the rule's limit.

{ff.and_list(ff.tile_str(t) for t in short)} stays {rng([100 * g for g in gap], '.0f')}% below the rule at any capacity. The
first tile of each of its tile rows reads the A band from DRAM, and the
{ff.N // first[1] - 1} later tiles don't, so the generator has time to spare in the first
tile and too little in the others. The FIFO restarts empty at every tile and
can't carry the spare time over; the worked example in fifo_feasibility-v2's
composite section takes {ff.tile_str(first)} apart tile by tile. On
{ff.tile_str(list(groups)[1])} every tile reads A again, so all its tiles are alike.
"""
    return text.strip(), len(params)


def composites_experiment(cal: dict, res: dict, out: Path) -> str:
    """What each minimum costs against gamma_0, as the fastest allowed tile's
    cycles per MAC over the fastest tile's of any width, in composites/. Each
    point has its fastest tile written in it: the allowed one in
    cost_min<T_N>.png, the one of any width in no_minimum.png. Returns the
    README of composites/."""
    comp = out / "composites"
    comp.mkdir(exist_ok=True)
    af = cal["alpha_f"]
    t0, g0 = ff.best_tile_ref(cal)
    gcs = ff.sweep_gcs(cal)
    xs = [gc / g0 for gc in gcs]
    xlabel = ff.gamma0_label(cal)
    free = [ff.best(res, gc) for gc in gcs]
    plot_fastest(xs, [v for v, _ in free], [ts[0] for _, ts in free], xlabel,
                 comp / "no_minimum.png")
    drawn, rows, none, two = [], [], [], []
    for m in MINS[1:]:
        meas = [ff.best(res, gc, tiles=allowed(m)) for gc in gcs]
        cost = [v / u for (v, _), (u, _) in zip(meas, free)]
        if max(cost) <= COSTS:
            none.append(m)
            continue
        plot_cost(xs, cost, [ts[0] for _, ts in meas], m, xlabel, comp / f"cost_min{m}.png")
        drawn.append(m)
        i = max(range(len(gcs)), key=lambda i: cost[i])
        bs = bands(xs, cost)
        rows.append(f"| T_N ≥ {m} | {ff.K * m:,} | {bands_str(bs)} | {cost[i]:.2f} | {xs[i]:.2f} | "
                    f"{ff.tile_str(meas[i][1][0])} | {ff.tile_str(free[i][1][0])} |")
        if len(bs) == 2:
            (_, end1), (start2, _) = bs
            gap = sorted({meas[j][1][0] for j in range(len(xs)) if end1 < xs[j] < start2})
            two.append(f"{ff.and_list(ff.tile_str(t) for t in gap)} for T_N ≥ {m}")
    order = [k for k, _ in groupby(ff.tile_str(ts[0]) for _, ts in free)]
    images = "\n\n".join(f"![cost of T_N ≥ {m}](cost_min{m}.png)" for m in drawn)
    no_graph = (f"T_N ≥ {ff.and_list(none)} costs less than 1% at every g_c, so it has no "
                "graph." if none else "")
    two_text = (f"Two of the curves have two bands, because between the bands the "
                f"minimum allows a tile within 1% of the fastest tile of any width: "
                f"{', and '.join(two)}." if two else "")
    text = f"""
# {NAME}: composite graphs

Each graph here has γ₀ on its x axis, with the formula in the axis label. A
point that comes from a fastest tile has that tile written in it. The minimum
widths, the working point and the runs are those of the
[main README](../README.md).

γ₀ = g_c / g_0, where g_0 = α_f · M / ⌈M/T_M⌉ on best_tile₀, the FIFO's
fastest tile with a free generator. best_tile₀ is {ff.tile_str(t0)}, so
g_0 = {af[t0]:.3f} · {ff.M} / {ff.tile_rows(t0[0])} = {g0:.1f} cycles, the slowest generator that tile keeps up
with.

## The fastest tile of any width

![the fastest tile of any width against γ₀](no_minimum.png)

Cycles per MAC on the fastest tile of any width, with the 2 KB FIFO. Every
cost below divides by this. As the generator slows down, the fastest tile
goes through {ff.and_list(order)}.

## What each minimum costs

{images}

Cycles per MAC on the fastest tile at least T_N,min wide, over cycles per MAC
on the fastest tile of any width. Each point names the fastest tile the
minimum allows; no_minimum.png names the other. {no_graph}

| minimum | S_min, elements | γ₀ where it costs more than 1% | largest cost | at γ₀ | fastest tile allowed there | fastest tile of any width there |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Each curve stays at 1 while some tile at least that wide is as fast as the
fastest tile of any width. It rises once the generator is too slow for the
short tiles the minimum allows: a wide tile has to be short to keep A in L1,
and on a short tile each element of B serves few MACs. It comes back to 1 at
large γ₀, where generation sets the time and the {ff.TMS[-1]}-row tiles of every
width take the same time. {two_text}
"""
    return text.strip()


COMPOSITES = """
## Composite graphs

`composites/` holds what each minimum costs against γ₀, with the fastest tile
written in every point. [composites/README.md](composites/README.md) explains
the graphs.
"""

ISSUES = """
## Simulator issues these runs expose

- The FIFO starts empty at every tile, so the time a generator gains while
  the core is slow in one tile can't carry into the next. That keeps the
  FIFO on 48×16 below the rule at any FIFO size.
- At the start of every tile the core reads its whole C tile from DRAM, one
  miss after another, before it computes. That stretch sets the FIFO size
  the wide tiles need.
- T_K is always K, so a minimum B tile can only be met by widening T_N. With a
  tile-level T_K, a B tile of T_K × T_N could also grow along K; this
  simulator can't test that.
"""

CHANGES = """
## Changes from the first version

The first version is `constraint_tile.py`, with its outputs in
`out/constraint_tile/`; both are unchanged. It gave each minimum's cost as
the fastest allowed tile over the fastest tile of any width, against γ₀. This
version compares the FIFO under each minimum with memory-B's fastest tile, in
cycles per MAC and g_c, and moves the cost against γ₀ to `composites/`, with
the fastest tile written in every point. It also finds the tile a minimum
runs near its limit from the cycles per MAC at g_c = 0, measures how the FIFO
size moves that limit, and runs N = 512 with minimums up to T_N ≥ 512, where
the first version ran N = 256.
"""


def header(cal: dict, n_new: int) -> str:
    return f"""
# {NAME}: the FIFO when the generator needs large B tiles

Some generators need to make at least S_min elements from each seed, for the
quality of their numbers or to pay back their start-up. The FIFO takes one
seed per tile, and with T_K = K a tile's B block is K × T_N elements, so such
a generator needs tiles at least S_min / K wide. This experiment asks what
that minimum width costs, and when it makes loading B from memory the faster
choice. Memory-B reads B and has no minimum.

The machine is the one of [fifo_feasibility-v2](../fifo_feasibility-v2/README.md):
its working point, its {len(ff.TILES)} tiles (T_M from {ff.TMS[0]} to {ff.TMS[-1]} in steps of 8, T_N from
{ff.TNS[0]} to {ff.TNS[-1]}) and its 2 KB FIFO. With K = {ff.K}, the minimum widths {MINS[1]} to {MINS[-1]}
are B tiles of {ff.K * MINS[1]:,} to {ff.K * MINS[-1]:,} elements. g_c is the generator's cycles per
element of B. The runs come from fifo_feasibility-v2's cache, except the
{n_new:,} runs of the FIFO-size graph, which are cached in
`out/{NAME}/results.json`.

run: `.venv/bin/python experiments/rewrite/{NAME}.py`
"""


def main() -> None:
    ff.style()
    out = out_dir(NAME)
    cal = ff.calibrate()
    res = ff.run(ff.sweep_params(cal))         # cached by fifo_feasibility-v2
    data, min_text = minimum_experiment(cal, res, out)
    depth_text, n_new = depth_experiment(cal, data, out)
    comp_text = composites_experiment(cal, res, out)
    (out / "composites" / "README.md").write_text(comp_text + "\n")
    parts = [header(cal, n_new).strip(), min_text, depth_text, COMPOSITES.strip(),
             ISSUES.strip(), CHANGES.strip()]
    (out / "README.md").write_text("\n\n".join(parts) + "\n")
    print((out / "README.md").read_text())


if __name__ == "__main__":
    main()
