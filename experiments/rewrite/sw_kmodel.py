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

  sw_kmodel_alpha:  alpha against T_M (T_N = 16) for four values of K, with
                    the predicted first cliff of each K (dotted).
  sw_kmodel:        per way of getting alpha, the share of the 780 cases
                    (130 matrices x 6 gc) within 1 %, 1-5 % and more than 5 %
                    of the best tile, and the worst case.

run:  .venv/bin/python experiments/rewrite/sw_kmodel.py
"""

from dataclasses import replace
import math
import random
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
ALPHA_TN = 16   # the first cliff is largest for narrow tiles (0.85 -> 1.5)


def lines(elems: int) -> int:
    return math.ceil(elems / LINE_ELEMS)


def fits(r: int, tn: int, k: int) -> bool:
    return r * (lines(k) + 2 * lines(tn)) < L1_LINES


MEM = 180   # memory latency: the extra cost of a miss


def c_misses(tn: int, k: int) -> float:
    """compulsory misses of C per MAC: C is loaded once from memory, one line
    per LINE_ELEMS elements (a line is shared by neighbouring tiles that are
    narrower than a line), and every element of C takes K MACs."""
    return MEM / (LINE_ELEMS * k)


def kmodel(tables: dict, ks: list, with_k_term: bool = False):
    """alpha of a row of height r and width tn at any K, from the calibrations ks.
    with_k_term: the calibration's own C-miss term is replaced by the target K's."""
    def alpha(r: int, tn: int, k: int) -> float:
        same = [c for c in ks if fits(r, tn, c) == fits(r, tn, k)] or ks
        c = min(same, key=lambda c: abs(math.log(c / k)))
        a = S.nearest(tables[c], r, tn)
        return a - c_misses(tn, c) + c_misses(tn, k) if with_k_term else a
    return alpha


def unmix_cols(alpha: dict, n_cal: int) -> dict:
    """alpha of a tile of exactly width T_N: take the narrow last column
    (n_cal mod T_N) out of the mix, smallest widths first (as row_alpha does
    for heights). Added 2026-10-20: the narrow last column has its own alpha."""
    pure = {}
    for tn in sorted({w for _, w in alpha}):
        for tm in sorted({h for h, _ in alpha}):
            if (tm, tn) not in alpha:
                continue
            e = n_cal % tn
            done = [w for h, w in pure if h == tm]
            if e == 0 or not done:
                pure[(tm, tn)] = alpha[(tm, tn)]
            else:
                w = min(done, key=lambda w: (abs(w - e), w))
                pure[(tm, tn)] = (n_cal * alpha[(tm, tn)] - e * pure[(tm, w)]) / (n_cal - e)
    return pure


def row_cost(alpha, r: int, tn: int, k: int, n: int) -> float:
    """alpha of a whole row of tiles of height r: its full tiles and its narrow
    last tile (n mod T_N), weighted by width."""
    if getattr(alpha, "cols_mixed", False):
        return alpha(r, tn, k)   # measured at this very N: the last column is already in it
    full, e = divmod(n, tn)
    v = full * tn * alpha(r, tn, k)
    if e:
        v += e * alpha(r, min(S.TN, key=lambda w: (abs(w - e), w)), k)
    return v / n


def predict(alpha, tm: int, tn: int, m: int, k: int, n: int, gc: int) -> float:
    s = gc * S.R * S.R * math.ceil(n / tn) / (k * n)
    full, e = divmod(m, tm)
    work = full * max(tm * row_cost(alpha, tm, tn, k, n) + s, gc)
    if e:
        work += max(e * row_cost(alpha, e, tn, k, n) + s, gc)
    return work / m


def calibration_tables(tt: dict) -> dict:
    """the template tables: widths and heights both un-mixed."""
    return {k: S.row_alpha(unmix_cols({(tm, tn): tt[(S.TEMPLATE_M, k, S.TEMPLATE_N, 0, tm, tn)]
                                       for tm in S.TEMPLATE_TM for tn in S.TN}, S.TEMPLATE_N),
                           S.TEMPLATE_M)
            for k in S.TEMPLATE_K}


def more_shapes() -> list:
    """100 more test matrices (the user asked, 2026-10-20: "way more than 20"),
    drawn at random with a fixed seed: M in 64..384, K in 128..1024 (the
    calibrated range), N in 96..512, K and N padded to a multiple of 16, at most
    30 M MACs each (to bound the run time)."""
    rng = random.Random(20261020)
    out = []
    while len(out) < 100:
        m = rng.randrange(64, 385)
        k = S.pad16(rng.randrange(128, 1025))
        n = S.pad16(rng.randrange(96, 513))
        if m * k * n <= 30_000_000 and (m, k, n) not in out:
            out.append((m, k, n))
    return out


MORE_SHAPES = more_shapes()


def big_k_shapes() -> list:
    """10 test matrices with K above the large calibration (the user asked,
    2026-10-21): M in 64..384, K in 1280..4096, N in 96..512, K and N padded
    to a multiple of 16, at most 100 M MACs each."""
    rng = random.Random(20261021)
    out = []
    while len(out) < 10:
        m = rng.randrange(64, 385)
        k = S.pad16(rng.randrange(1280, 4097))
        n = S.pad16(rng.randrange(96, 513))
        if m * k * n <= 100_000_000 and (m, k, n) not in out:
            out.append((m, k, n))
    return out


BIG_K_SHAPES = big_k_shapes()


def main() -> None:
    base = Params(l1_assoc=-1)
    tt = S.runtime([replace(base, m=S.TEMPLATE_M, k=k, n=S.TEMPLATE_N, tile_h=tm, tile_w=tn,
                            gen_cost=0)
                    for k in S.TEMPLATE_K for tm in S.TEMPLATE_TM for tn in S.TN], "templates.json")
    st = S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                    for m, k, n in S.SHAPES for gc in [0] + S.TEST_GC
                    for tm, tn in S.test_tiles(m, n)], "shapes_padded.json")
    st |= S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                     for m, k, n in MORE_SHAPES for gc in [0] + S.TEST_GC
                     for tm, tn in S.test_tiles(m, n)], "shapes_more.json")
    st |= S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                     for m, k, n in BIG_K_SHAPES for gc in [0] + S.TEST_GC
                     for tm, tn in S.test_tiles(m, n)], "shapes_big_k.json")
    shapes = list(S.SHAPES) + MORE_SHAPES + BIG_K_SHAPES
    tables = calibration_tables(tt)

    # 1. alpha at the K values in between, from the calibrations only
    lines_out = ["## alpha of the other K values, from the calibrations", "",
                 "| calibrations | K | within 3 % | within 5 % | worst |", "|---|---|---|---|---|"]
    for name, (ks, with_k) in CALIBRATIONS.items():
        a = kmodel(tables, ks, with_k)
        for k in [kk for kk in S.TEMPLATE_K if kk not in ks]:
            errs = [abs(tt[(S.TEMPLATE_M, k, S.TEMPLATE_N, 0, tm, tn)] /
                        predict(a, tm, tn, S.TEMPLATE_M, k, S.TEMPLATE_N, 0) - 1)
                    for tm in S.TEMPLATE_TM if S.TEMPLATE_M % tm == 0 for tn in S.TN]
            lines_out.append(f"| {name} {ks} | {k} | {sum(e <= .03 for e in errs) / len(errs):.0%} | "
                             f"{sum(e <= .05 for e in errs) / len(errs):.0%} | {max(errs):.1%} |")

    # 2. the tile choice on the 130 padded test matrices (the first 20 + 100 random + 10 big K)
    ways = {"own table": None, **{f"K model, {n}": v for n, v in CALIBRATIONS.items()},
            "one table ($K = 256$)": ([256], False)}
    excess = {}
    for name, way in ways.items():
        excess[name] = []
        for m, k, n in shapes:
            tiles = S.test_tiles(m, n)
            if way is None:
                own = S.row_alpha({tl: st[(m, k, n, 0, *tl)] for tl in tiles}, m)
                a = lambda r, tn, kk, own=own: S.nearest(own, r, tn)
                a.cols_mixed = True
            elif len(way[0]) == 1:
                a = lambda r, tn, kk, t=tables[way[0][0]]: S.nearest(t, r, tn)
            else:
                a = kmodel(tables, *way)
            for gc in S.TEST_GC:
                meas = {tl: st[(m, k, n, gc, *tl)] for tl in tiles}
                pick = min(tiles, key=lambda tl: (predict(a, *tl, m, k, n, gc), a(*tl, k)))
                excess[name].append(meas[pick] / min(meas.values()) - 1)
    lines_out += ["", "## tile choice on the 130 padded matrices (20 + 100 random + 10 big K, 6 gc each)", "",
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
    ax.set_ylim(0, 2)
    ax.plot([], [], color=INK_2, linestyle=":", linewidth=1.0, label="predicted first cliff")
    legend_above(ax, ncols=len(ALPHA_K) + 1)
    print(save(fig, "software/s8_kmodel", "sw_kmodel_alpha"))

    # figure: the tile choice, as stacked bars (same style as sw_templates)
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    bins = [("within 1%", lambda x: x <= 0.01), ("1% to 5%", lambda x: 0.01 < x <= 0.05),
            ("more than 5%", lambda x: x > 0.05)]
    colors = [SERIES[2], SERIES[3], SERIES[1]]
    shown = {"own table": "own table (every matrix calibrated)",
             "K model, two calibrations + 1/K term": "K model",
             "K model, two calibrations": "K model without the $1 slash K$ term",
             "one table ($K = 256$)": "one table for all ($K = 256$)"}
    order = list(reversed(list(shown)))
    left = [0.0] * len(order)
    ax.set_axisbelow(True)
    ax.grid(False, axis="y")
    for j, (label, inside) in enumerate(bins):
        shares = [100 * sum(map(inside, excess[name])) / len(excess[name]) for name in order]
        ax.barh(range(len(order)), shares, left=left, color=colors[j], label=label, height=0.6)
        left = [a + b for a, b in zip(left, shares)]
    for i, name in enumerate(order):
        ax.text(101, i, f"worst {max(excess[name]):.0%}", va="center", fontsize=9)
    ax.set_yticks(range(len(order)), [shown[name].replace("$1 slash K$", "$1/K$") for name in order])
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the cases (%)")
    legend_above(ax, ncols=len(bins))
    print(save(fig, "software/s8_kmodel", "sw_kmodel"))


# more K: 192 x K x 256 (only K changes), the calibrations at 128 and 1024.
# Between the calibrations the model should work for any K; 96 and 1280 are
# outside them (the user asked, 2026-10-20).
SWEEP_K = [96, 144, 160, 176, 208, 224, 240, 272, 320, 448, 576, 640, 704, 896, 960, 1280,
           2048, 4096]
SWEEP_PLOT_K = [160, 320, 640]   # never calibrated
SWEEP_PLOT_TN = 16


def k_sweep() -> None:
    base = Params(l1_assoc=-1)
    tt = S.runtime([replace(base, m=S.TEMPLATE_M, k=k, n=S.TEMPLATE_N, tile_h=tm, tile_w=tn,
                            gen_cost=0)
                    for k in S.TEMPLATE_K for tm in S.TEMPLATE_TM for tn in S.TN], "templates.json")
    tables = calibration_tables(tt)
    m, n = S.TEMPLATE_M, S.TEMPLATE_N
    tiles = S.test_tiles(m, n)
    st = S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                    for k in SWEEP_K for gc in [0] + S.TEST_GC for tm, tn in tiles], "k_sweep.json")
    a = kmodel(tables, [128, 1024], True)
    rows = ["| K | alpha within 3 % | alpha within 5 % | alpha worst | pick: worst over gc |",
            "|---|---|---|---|---|"]
    for k in SWEEP_K:
        errs = [abs(st[(m, k, n, 0, tm, tn)] / predict(a, tm, tn, m, k, n, 0) - 1)
                for tm, tn in tiles if m % tm == 0]
        picks = []
        for gc in S.TEST_GC:
            meas = {tl: st[(m, k, n, gc, *tl)] for tl in tiles}
            pick = min(tiles, key=lambda tl: (predict(a, *tl, m, k, n, gc), a(*tl, k)))
            picks.append(meas[pick] / min(meas.values()) - 1)
        rows.append(f"| {k}{' (outside)' if k < 128 or k > 1024 else ''} | "
                    f"{sum(e <= .03 for e in errs) / len(errs):.0%} | "
                    f"{sum(e <= .05 for e in errs) / len(errs):.0%} | {max(errs):.1%} | "
                    f"{max(picks):.2%} |")
    report = (f"# {NAME}: more K (192 x K x 256), calibrations at 128 and 1024\n\n" +
              "\n".join(rows) + "\n")
    (out_dir(NAME) / "README_k_sweep.md").write_text(report)
    print(report)

    # sw_kmodel_sweep: alpha at K values that were never calibrated, measured
    # (markers) against the prediction from the 128 and 1024 calibrations
    # (dashed; predict() at gc = 0 averages the full and the short row like
    # the measurement does)
    tms = [tm for tm in S.TEST_TM if tm <= 128]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, k in enumerate(SWEEP_PLOT_K):
        ax.plot(tms, [st[(m, k, n, 0, tm, SWEEP_PLOT_TN)] for tm in tms], linestyle="none",
                label=f"measured, $K = {k}$", **series(i))
        ax.plot(tms, [predict(a, tm, SWEEP_PLOT_TN, m, k, n, 0) for tm in tms],
                color=SERIES[i], linestyle="--", linewidth=1.2)
    ax.plot([], [], color=INK_2, linestyle="--", linewidth=1.2, label="predicted")
    ax.set_xlabel("$T_M$")
    ax.set_ylabel(r"$\alpha$ (cycles / MAC)")
    ax.set_xlim(0, 132)
    ax.set_ylim(0, 2)
    legend_above(ax, ncols=len(SWEEP_PLOT_K) + 1)
    print(save(fig, "software/s8_kmodel", "sw_kmodel_sweep"))


def validation() -> None:
    """sw_kmodel_validation: like fig_model_validation (report 4.5.1), predicted
    against measured runtime for every tile and gc > 0 of the 20 padded matrices
    and the K sweep: one calibration for all (K 256, ignores K) on the left, the
    K model (calibrations at 128 and 1024) on the right."""
    base = Params(l1_assoc=-1)
    tt = S.runtime([replace(base, m=S.TEMPLATE_M, k=k, n=S.TEMPLATE_N, tile_h=tm, tile_w=tn,
                            gen_cost=0)
                    for k in S.TEMPLATE_K for tm in S.TEMPLATE_TM for tn in S.TN], "templates.json")
    tables = calibration_tables(tt)
    shapes = list(S.SHAPES) + [(S.TEMPLATE_M, k, S.TEMPLATE_N) for k in SWEEP_K]
    st = S.runtime([replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
                    for m, k, n in S.SHAPES for gc in [0] + S.TEST_GC
                    for tm, tn in S.test_tiles(m, n)], "shapes_padded.json")
    st |= S.runtime([replace(base, m=S.TEMPLATE_M, k=k, n=S.TEMPLATE_N, tile_h=tm, tile_w=tn,
                             gen_cost=gc)
                     for k in SWEEP_K for gc in [0] + S.TEST_GC
                     for tm, tn in S.test_tiles(S.TEMPLATE_M, S.TEMPLATE_N)], "k_sweep.json")
    one = lambda r, tn, k, t=tables[256]: S.nearest(t, r, tn)
    ways = {"predicted, one calibration for all": one,
            "predicted, K model": kmodel(tables, [128, 1024], True)}
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.6), sharey=True)
    out = []
    for ax, (label, a) in zip(axes, ways.items()):
        pred, meas = [], []
        for m, k, n in shapes:
            for gc in S.TEST_GC:
                for tm, tn in S.test_tiles(m, n):
                    pred.append(predict(a, tm, tn, m, k, n, gc))
                    meas.append(st[(m, k, n, gc, tm, tn)])
        ax.scatter(pred, meas, s=3, color=SERIES[0], alpha=0.15, linewidths=0, rasterized=True)
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
        e = [mm / p - 1 for mm, p in zip(meas, pred)]
        out.append(f"{label}: {len(e)} runs, within 1 % {sum(abs(x) <= .01 for x in e) / len(e):.1%}, "
                   f"within 5 % {sum(abs(x) <= .05 for x in e) / len(e):.1%}, "
                   f"predicted too slow (> 1 %) {sum(x < -.01 for x in e)}, too fast (> 1 %) {sum(x > .01 for x in e)}")
    axes[0].set_ylabel("measured (cycles / MAC)")
    print(save(fig, "software/s8_kmodel", "sw_kmodel_validation"))
    print("\n".join(out))
    with open(out_dir(NAME) / "README.md", "a") as f:
        f.write("\n## predicted vs measured (20 matrices + K sweep, gc > 0)\n\n" + "\n".join(out) + "\n")


if __name__ == "__main__":
    main()
    k_sweep()
    validation()
