"""S8: K in the model (report: 4.4 refinement 4, and 4.5.2 for the test).

K changes alpha in one way only: whether the strip of A of a row of tiles
(T_M x K) still fits in L1 next to the tiles of C. Within "fits" and "does
not fit", alpha changes by a few percent with K, and the other cliffs do
not involve K at all. So alpha at any K comes from a few calibration
tables:
  - a row of tiles of height r and width T_N fits at K when
      r * (lines of a row of A + 2 * lines of a row of the tile of C) < L1 lines
    (A stays from one tile to the next only next to the C tile being finished
    and the next one coming in);
  - its alpha is taken from the calibration table, among those where the row
    has the same fit state, with the closest K.

Nothing is re-run: the calibrations are the sw_templates templates
(192 x K x 256, gc = 0), the test matrices are its 20 padded shapes.

  sw_kmodel_alpha:  alpha against T_M (T_N = 32) for four values of K, with
                    the predicted first cliff of each K (dotted).
  sw_kmodel:        per way of getting alpha, the share of the 120 cases
                    (20 matrices x 6 gc) within 1 %, 1-5 % and more than 5 %
                    of the best tile, and the worst case.

run:  .venv/bin/python experiments/rewrite/sw_kmodel.py
"""

from dataclasses import replace
import math
import statistics

import sw_templates as S
from harness import Params, out_dir
from plot_style import SERIES, INK_2, legend_above, plt, save, series

NAME = "sw_kmodel"
L1_LINES = 16384 // 64
LINE_ELEMS = 64 // 4
CALIBRATIONS = {"two calibrations": ([128, 1024], False),
                "two calibrations + 1/K term": ([128, 1024], True),
                "three calibrations": ([128, 384, 1024], False),
                "three calibrations + 1/K term": ([128, 384, 1024], True)}
ALPHA_K = [128, 256, 512, 1024]   # for the alpha figure
ALPHA_TN = 32


def lines(elems: int) -> int:
    return math.ceil(elems / LINE_ELEMS)


def fits(r: int, tn: int, k: int) -> bool:
    return r * (lines(k) + 2 * lines(tn)) < L1_LINES


MEM = 180   # memory latency: the extra cost of a miss


def c_misses(tn: int, k: int) -> float:
    """compulsory misses of C per MAC: every tile loads its C once from memory,
    lines(tn) lines per row of the tile, shared by the tn * k MACs of that row."""
    return MEM * lines(tn) / (tn * k)


def kmodel(tables: dict, ks: list, with_k_term: bool = False):
    """alpha of a row of height r and width tn at any K, from the calibrations ks.
    with_k_term: the calibration's own C-miss term is replaced by the target K's."""
    def alpha(r: int, tn: int, k: int) -> float:
        same = [c for c in ks if fits(r, tn, c) == fits(r, tn, k)] or ks
        c = min(same, key=lambda c: abs(math.log(c / k)))
        a = S.nearest(tables[c], r, tn)
        return a - c_misses(tn, c) + c_misses(tn, k) if with_k_term else a
    return alpha


def predict(alpha, tm: int, tn: int, m: int, k: int, n: int, gc: int) -> float:
    s = gc * S.R * S.R * math.ceil(n / tn) / (k * n)
    full, e = divmod(m, tm)
    work = full * max(tm * alpha(tm, tn, k) + s, gc)
    if e:
        work += max(e * alpha(e, tn, k) + s, gc)
    return work / m


def main() -> None:
    base = Params(l1_assoc=-1)
    tt = S.runtime([replace(base, m=S.TEMPLATE_M, k=k, n=S.TEMPLATE_N, tile_h=tm, tile_w=tn,
                            gen_cost=0)
                    for k in S.TEMPLATE_K for tm in S.TEMPLATE_TM for tn in S.TN], "templates.json")
    st = S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                    for m, k, n in S.SHAPES for gc in [0] + S.TEST_GC
                    for tm, tn in S.test_tiles(m, n)], "shapes_padded.json")
    tables = {k: S.row_alpha({(tm, tn): tt[(S.TEMPLATE_M, k, S.TEMPLATE_N, 0, tm, tn)]
                              for tm in S.TEMPLATE_TM for tn in S.TN}, S.TEMPLATE_M)
              for k in S.TEMPLATE_K}

    # 1. alpha at the K values in between, from the calibrations only
    lines_out = ["## alpha of the other K values, from the calibrations", "",
                 "| calibrations | K | within 3 % | within 5 % | worst |", "|---|---|---|---|---|"]
    for name, ks in CALIBRATIONS.items():
        a = kmodel(tables, ks)
        for k in [kk for kk in S.TEMPLATE_K if kk not in ks]:
            errs = [abs(tt[(S.TEMPLATE_M, k, S.TEMPLATE_N, 0, tm, tn)] / a(tm, tn, k) - 1)
                    for tm in S.TEMPLATE_TM if S.TEMPLATE_M % tm == 0 for tn in S.TN]
            lines_out.append(f"| {name} {ks} | {k} | {sum(e <= .03 for e in errs) / len(errs):.0%} | "
                             f"{sum(e <= .05 for e in errs) / len(errs):.0%} | {max(errs):.1%} |")

    # 2. the tile choice on the 20 padded test matrices
    ways = {"own table": None, **{f"K model, {n}": ks for n, ks in CALIBRATIONS.items()},
            "one table ($K = 256$)": [256]}
    excess = {}
    for name, ks in ways.items():
        excess[name] = []
        for m, k, n in S.SHAPES:
            tiles = S.test_tiles(m, n)
            if ks is None:
                own = S.row_alpha({tl: st[(m, k, n, 0, *tl)] for tl in tiles}, m)
                a = lambda r, tn, kk, own=own: S.nearest(own, r, tn)
            elif len(ks) == 1:
                a = lambda r, tn, kk, t=tables[ks[0]]: S.nearest(t, r, tn)
            else:
                a = kmodel(tables, ks)
            for gc in S.TEST_GC:
                meas = {tl: st[(m, k, n, gc, *tl)] for tl in tiles}
                pick = min(tiles, key=lambda tl: (predict(a, *tl, m, k, n, gc), a(*tl, k)))
                excess[name].append(meas[pick] / min(meas.values()) - 1)
    lines_out += ["", "## tile choice on the 20 padded matrices (6 gc each)", "",
                  "| alpha from | median | within 1 % | within 5 % | worst |", "|---|---|---|---|---|"]
    for name, xs in excess.items():
        lines_out.append(f"| {name} | {statistics.median(xs):.2%} | "
                         f"{sum(x <= .01 for x in xs) / len(xs):.0%} | "
                         f"{sum(x <= .05 for x in xs) / len(xs):.0%} | {max(xs):.1%} |")
    report = f"# {NAME}: K in the model\n\n" + "\n".join(lines_out) + "\n"
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)

    # figure: alpha against T_M for several K, with the predicted first cliff
    tms = [tm for tm in S.TEMPLATE_TM if tm <= 128]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, k in enumerate(ALPHA_K):
        ax.plot(tms, [tt[(S.TEMPLATE_M, k, S.TEMPLATE_N, 0, tm, ALPHA_TN)] for tm in tms],
                markevery=2, label=f"$K = {k}$", **series(i))
        cliff = next(tm for tm in range(1, 200) if not fits(tm, ALPHA_TN, k))
        ax.axvline(cliff, color=SERIES[i], linestyle=":", linewidth=1.0)
    ax.set_xlabel("$T_M$")
    ax.set_ylabel(r"$\alpha$ (cycles / MAC)")
    ax.set_xlim(0, 132)
    ax.set_ylim(0, 4.5)
    ax.plot([], [], color=INK_2, linestyle=":", linewidth=1.0, label="predicted first cliff")
    legend_above(ax, ncols=len(ALPHA_K) + 1)
    print(save(fig, "software/s8_kmodel", "sw_kmodel_alpha"))

    # figure: the tile choice, as stacked bars (same style as sw_templates)
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    bins = [("within 1%", lambda x: x <= 0.01), ("1% to 5%", lambda x: 0.01 < x <= 0.05),
            ("more than 5%", lambda x: x > 0.05)]
    colors = [SERIES[2], SERIES[3], SERIES[1]]
    order = list(reversed(list(ways)))
    left = [0.0] * len(order)
    ax.set_axisbelow(True)
    ax.grid(False, axis="y")
    for j, (label, inside) in enumerate(bins):
        shares = [100 * sum(map(inside, excess[name])) / len(excess[name]) for name in order]
        ax.barh(range(len(order)), shares, left=left, color=colors[j], label=label, height=0.6)
        left = [a + b for a, b in zip(left, shares)]
    for i, name in enumerate(order):
        ax.text(101, i, f"worst {max(excess[name]):.0%}", va="center", fontsize=9)
    ax.set_yticks(range(len(order)), order)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the cases (%)")
    legend_above(ax, ncols=len(bins))
    print(save(fig, "software/s8_kmodel", "sw_kmodel"))


if __name__ == "__main__":
    main()
