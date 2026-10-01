"""F7: how good is the model's tile choice?

For every case (one hardware/matrix config at one gc > 0) the model picks
  argmin max(alpha, gc * ceil(M/TM) / M) + S,   S = tiles * R^2 * gc / MNK,
(ties to the lower alpha), with alpha measured at gc = 0 on the same config.
Excess = T(model's tile) / T(best tile) - 1, both measured: 0 = exact pick.

Sets of cases, all from existing caches:
  - 6 matrices x 3 L1 sizes (fully assoc / 8-way / 4-way): model_sweep and
    assoc_sweep, 11 gc each, a coarse tile grid (~100 tiles);
  - default setup, all tiles: fig_best_tile, 192x256x256 on the 16 KB fully
    associative L1, every tile TM 4..192 x TN 4..128 in steps of 4, gc 1..600.

  fig_model_accuracy:          per set, the share of cases where the model's
                               tile is exact / within 1 % / within 5 % /
                               worse (stacked bars): how accurate;
  fig_model_accuracy_balance:  excess vs B / alpha of the model's tile: why
                               it misses (the misses sit near B = alpha,
                               where generation and memory only partly
                               overlap).

run:  .venv/bin/python experiments/rewrite/fig_model_accuracy.py
"""

from collections import defaultdict
from dataclasses import replace

import fig_best_tile as fbt
import model_sweep as ms
from harness import Params, out_dir, run_many
from plot_style import GRID, INK_2, SERIES, legend_above, plt, save, series

NAME = "fig_model_accuracy"
SWEEP = "6 matrices × 3 L1 sizes"
FA, W8, W4 = f"{SWEEP}, fully assoc", f"{SWEEP}, 8-way", f"{SWEEP}, 4-way"
ALL_TILES = "default setup, all tiles"
GROUPS = [FA, W8, W4, ALL_TILES]
BINS = [("exact", lambda r: r["pick"] == r["best"]),
        ("within 1 %", lambda r: r["excess"] <= 0.01),
        ("within 5 %", lambda r: r["excess"] <= 0.05),
        ("worse", lambda r: True)]
BIN_COLORS = ["#1d4f91", "#2a78d6", "#9ec5f0", SERIES[7]]   # blue ramp, red = worse


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def add(cases: dict, group: str, config, p: Params, cycles: float) -> None:
    """cases[(group, config, gc)][tile] = measured T / MNK"""
    cases[(group, config, p.gen_cost)][(p.tile_h, p.tile_w)] = cycles / (p.m * p.k * p.n)


def collect() -> tuple[dict, dict]:
    cases = defaultdict(dict)
    shape = {}   # (group, config) -> (m, k, n, reg_dim)

    base = [replace(p, gen_cost=gc) for gc in [0] + ms.GC for _, _, p in ms.configs()]
    for group, assoc, cache in ((FA, -1, out_dir(ms.NAME) / "results.json"),
                                (W8, 3, out_dir("assoc_sweep") / "results_8-way.json"),
                                (W4, 2, out_dir("assoc_sweep") / "results_4-way.json")):
        params = [replace(p, l1_assoc=assoc) for p in base]
        for p, s in zip(params, run_many(params, cache)):
            config = (p.l1_size, (p.m, p.k, p.n))
            add(cases, group, config, p, s["Simulation: Total cycles"])
            shape[(group, config)] = (p.m, p.k, p.n, p.reg_dim)

    assert not fbt.SMALL
    params = [replace(Params(l1_assoc=-1), tile_h=tm, tile_w=tn, gen_cost=gc)
              for gc in fbt.GC for tm in fbt.TM for tn in fbt.TN]
    for p, s in zip(params, run_many(params, out_dir(fbt.NAME) / "results.json")):
        add(cases, ALL_TILES, "default", p, s["Simulation: Total cycles"])
        shape[(ALL_TILES, "default")] = (p.m, p.k, p.n, p.reg_dim)
    return cases, shape


def evaluate(cases: dict, shape: dict) -> list[dict]:
    rows = []
    for (group, config, gc), tiles in cases.items():
        if gc == 0:
            continue
        m, k, n, r = shape[(group, config)]
        cal = cases[(group, config, 0)]

        def model(t):
            b = gc * cdiv(m, t[0]) / m
            s = cdiv(m, t[0]) * cdiv(n, t[1]) * r * r * gc / (m * n * k)
            return max(cal[t], b) + s, cal[t], b

        pick = min(tiles, key=lambda t: model(t)[:2])
        best = min(tiles, key=tiles.get)
        _, alpha, b = model(pick)
        rows.append({"group": group, "config": config, "gc": gc, "pick": pick, "best": best,
                     "excess": tiles[pick] / tiles[best] - 1, "balance": b / alpha})
    return rows


def bin_of(r: dict) -> int:
    return next(i for i, (_, test) in enumerate(BINS) if test(r))


def percent_axis(axis) -> None:
    axis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{100 * v:g} %"))


def main() -> None:
    rows = evaluate(*collect())
    by = {g: [r for r in rows if r["group"] == g] for g in GROUPS}

    # how accurate: stacked share of cases per bin, one bar per set
    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    labels = [f"{g} ({len(by[g])})" for g in GROUPS][::-1]
    left = [0.0] * len(GROUPS)
    for i, (name, _) in enumerate(BINS):
        share = [sum(bin_of(r) == i for r in by[g]) / len(by[g]) for g in GROUPS][::-1]
        ax.barh(labels, share, left=left, height=0.6, color=BIN_COLORS[i], label=name,
                edgecolor="white", linewidth=1.0)
        left = [a + b for a, b in zip(left, share)]
    percent_axis(ax.xaxis)
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of cases")
    ax.grid(False, axis="y")
    legend_above(ax, ncols=len(BINS))
    print(save(fig, "model", NAME))

    # why: excess against B / alpha of the model's tile
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.axvline(1, color=INK_2, linewidth=1.0, zorder=1)
    for i, g in enumerate(GROUPS):
        ax.plot([r["balance"] for r in by[g]], [r["excess"] for r in by[g]],
                linestyle="none", markersize=4.5, alpha=0.7, label=g, **series(i))
    ax.set_xscale("log", base=10)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_yscale("symlog", linthresh=0.01, linscale=0.5)
    percent_axis(ax.yaxis)
    ax.set_ylim(0, 1)
    ax.grid(True, color=GRID)
    ax.set_xlabel(r"$B \,/\, \alpha$ of the model's tile")
    ax.set_ylabel("extra time over the best tile")
    legend_above(ax, ncols=2)
    print(save(fig, "model", NAME + "_balance"))

    lines = ["| cases | n | exact tile | TM* right | within 1 % | within 5 % | worst | "
             "misses > 1 % with 0.5 < B/alpha < 2 |", "|---" * 8 + "|"]
    for g in GROUPS + ["all"]:
        rs = rows if g == "all" else by[g]
        n = len(rs)
        bad = [r for r in rs if r["excess"] > 0.01]
        near = sum(0.5 < r["balance"] < 2 for r in bad)
        lines.append(f"| {g} | {n} | {sum(r['pick'] == r['best'] for r in rs) / n:.0%} "
                     f"| {sum(r['pick'][0] == r['best'][0] for r in rs) / n:.0%} "
                     f"| {sum(r['excess'] <= 0.01 for r in rs) / n:.0%} "
                     f"| {sum(r['excess'] <= 0.05 for r in rs) / n:.0%} "
                     f"| {max(r['excess'] for r in rs):.1%} | {near}/{len(bad)} |")
    worst = sorted(rows, key=lambda r: -r["excess"])[:15]
    lines += ["", "## Worst 15", "", "| cases | config | gc | model | best | excess | B/alpha |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['group']} | {r['config']} | {r['gc']} | {r['pick']} | {r['best']} "
              f"| {r['excess']:.1%} | {r['balance']:.2f} |" for r in worst]
    report = (f"# {NAME}\n\nModel: max(alpha, gc·⌈M/TM⌉/M) + S, ties to the lower "
              f"alpha.\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
