"""S7 (software engineer): can a few calibration tables ("templates") serve
many matrices? (report: replaces most of "Does The Best Tile Depend On The
Matrix Shape?")

The calibration table holds alpha per row of tiles. M only sets how many rows
there are (computed by the model), N barely changes alpha, but K sets the
size of the tile of A (T_M x K), so the templates are indexed by K:

  templates: 192 x K x 256 for K in TEMPLATE_K, gc = 0 only, every height
             4..192 in steps of 4 and the widths in TN.
  test shapes: matrices whose sizes are not powers of two; every tile of
             TEST_TM x TN at gc 0 (the shape's own table) and at TEST_GC (to
             find the true best tile).

For every test shape and gc > 0, the refined model picks a tile from a table,
and we measure how much slower it is than the true best tile. The tables:
  - own:          the shape's own table (the ideal);
  - next up:      the template with the smallest K >= the shape's K, from all
                  the templates (TEMPLATE_K);
  - next up, few: the same rule from only TEMPLATE_K_FEW;
  - nearest:      the template with the closest K (log scale);
  - default:      the K = 256 template only (what the report did before);
  - same ratios:  the shape scaled by RATIO_SCALE in every dimension (the same
                  ratios, a larger K), calibrated at gc 0.

A short last row whose height is not in a table uses the nearest measured
height. Default setup otherwise (16 KB fully associative L1, no L2,
B-stationary, R = 4).

Results of the first tries (2026-10-16, see TODO_EXPER.md): rows of C that do
not start on a 64-byte line move the thrashing cliff, so the shapes are padded
(PAD=True: K and N rounded up to a multiple of 16 elements, emulated by
enlarging the matrix, as in the associativity section); and the template must
have a K at least as large as the shape's ("next up"), because a tile of A
that fits at a smaller K may not fit at the real one.

SMALL=True: the first 10 test shapes only.

run:  .venv/bin/python experiments/rewrite/sw_templates.py
"""

from dataclasses import replace
import math
import statistics

from harness import Params, out_dir, run_many
from plot_style import SERIES, legend_above, plt, save

LABELS = {"own": "own table", "next up": "next K up (7 templates)",
          "next up, few": "next K up (4 templates)", "nearest": "closest K (7 templates)",
          "default": "one table ($K = 256$)", "same ratios": "same ratios"}

NAME = "sw_templates"
SMALL = False
PAD = True
R = 4
TEMPLATE_M, TEMPLATE_N = 192, 256
TEMPLATE_K = [128, 192, 256, 384, 512, 768, 1024]
TEMPLATE_K_FEW = [128, 256, 512, 1024]
TEMPLATE_TM = list(range(4, 193, 4))
TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
TEST_TM = [4, 8, 12, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192]
TEST_GC = [5, 10, 20, 40, 80, 160]
RATIO_SCALE = 1.5
SHAPES = [   # (M, K, N), sizes that are not powers of two
    (150, 300, 200), (200, 200, 300), (100, 500, 150), (300, 120, 250), (250, 400, 100),
    (180, 350, 180), (120, 700, 120), (400, 150, 200), (160, 600, 130), (240, 260, 200),
    # added for the full run
    (210, 176, 240), (90, 432, 272), (330, 240, 144), (170, 560, 96), (260, 320, 160),
    (140, 800, 112), (360, 112, 224), (190, 464, 208), (110, 656, 176), (280, 208, 128),
]
if SMALL:
    SHAPES = SHAPES[:10]


def pad16(x: int) -> int:
    return -(-x // 16) * 16


if PAD:
    SHAPES = [(m, pad16(k), pad16(n)) for m, k, n in SHAPES]
SUFFIX = ("_padded" if PAD else "") + ("_small" if SMALL else "")


def scaled(shape: tuple) -> tuple:
    m, k, n = shape
    return round(m * RATIO_SCALE), pad16(round(k * RATIO_SCALE)), pad16(round(n * RATIO_SCALE))


def nearest(table: dict, r: int, tn: int) -> float:
    """alpha of a row of height r; the nearest measured height if r was not measured."""
    if (r, tn) in table:
        return table[(r, tn)]
    heights = [h for h, w in table if w == tn]
    return table[(min(heights, key=lambda h: (abs(h - r), h)), tn)]


def row_alpha(alpha: dict, m_cal: int) -> dict:
    """alpha of a single row of tiles: take the short last row out of the mix."""
    pure = {}
    for tm, tn in sorted(alpha):
        e = m_cal % tm
        if e == 0 or not any(w == tn for _, w in pure):
            # no short row, or no smaller height measured yet (e.g. 150 mod 4):
            # the short row is taken to cost the same as the full rows
            pure[(tm, tn)] = alpha[(tm, tn)]
            continue
        total = m_cal * alpha[(tm, tn)] - e * nearest(pure, e, tn)
        pure[(tm, tn)] = total / (m_cal - e)
    return pure


def predict(pure: dict, tm: int, tn: int, m: int, k: int, n: int, gc: int) -> float:
    rows = [tm] * (m // tm) + ([m % tm] if m % tm else [])
    s = gc * R * R * math.ceil(n / tn) / (k * n)   # startup of one row of tiles, memory side
    return sum(max(r * nearest(pure, r, tn) + s, gc) for r in rows) / m


def runtime(params: list, file: str) -> dict:
    stats = run_many(params, out_dir(NAME) / file)
    return {(p.m, p.k, p.n, p.gen_cost, p.tile_h, p.tile_w):
            s["Simulation: Total cycles"] / (p.m * p.k * p.n) for p, s in zip(params, stats)}


def test_tiles(m: int, n: int) -> list:
    return [(tm, tn) for tm in TEST_TM if tm <= m for tn in TN if tn <= n]


def next_up(k: int, ks: list) -> int:
    return min([kt for kt in ks if kt >= k] or [max(ks)])


def main() -> None:
    base = Params(l1_assoc=-1)
    tparams = [replace(base, m=TEMPLATE_M, k=k, n=TEMPLATE_N, tile_h=tm, tile_w=tn, gen_cost=0)
               for k in TEMPLATE_K for tm in TEMPLATE_TM for tn in TN]
    tt = runtime(tparams, "templates.json")
    templates = {k: row_alpha({(tm, tn): tt[(TEMPLATE_M, k, TEMPLATE_N, 0, tm, tn)]
                               for tm in TEMPLATE_TM for tn in TN}, TEMPLATE_M)
                 for k in TEMPLATE_K}

    sparams = [replace(base, m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
               for m, k, n in SHAPES for gc in [0] + TEST_GC for tm, tn in test_tiles(m, n)]
    st = runtime(sparams, f"shapes{SUFFIX}.json")

    # the same-ratio control: each shape scaled up, calibrated at gc 0 on the same tiles
    rparams = [replace(base, m=sm, k=sk, n=sn, tile_h=tm, tile_w=tn, gen_cost=0)
               for shape in SHAPES for sm, sk, sn in [scaled(shape)]
               for tm, tn in test_tiles(*shape[::2])]
    rt = runtime(rparams, f"ratios{SUFFIX}.json")

    names = ["own", "next up", "next up, few", "nearest", "default", "same ratios"]
    excess = {name: [] for name in names}
    lines = ["| shape | next up K (all / few) | " + " | ".join(names) + " |",
             "|---|---|" + "---|" * len(names)]
    for m, k, n in SHAPES:
        tiles = test_tiles(m, n)
        alpha_own = {tl: st[(m, k, n, 0, *tl)] for tl in tiles}
        sm, sk, sn = scaled((m, k, n))
        alpha_ratio = {tl: rt[(sm, sk, sn, 0, *tl)] for tl in tiles}
        k_up, k_up_few = next_up(k, TEMPLATE_K), next_up(k, TEMPLATE_K_FEW)
        tables = {
            "own": row_alpha(alpha_own, m),
            "next up": templates[k_up],
            "next up, few": templates[k_up_few],
            "nearest": templates[min(TEMPLATE_K, key=lambda kt: abs(math.log(kt / k)))],
            "default": templates[256],
            "same ratios": row_alpha(alpha_ratio, sm),
        }
        worst = {}
        for name, pure in tables.items():
            worst[name] = 0.0
            for gc in TEST_GC:
                meas = {tl: st[(m, k, n, gc, *tl)] for tl in tiles}
                pick = min(tiles, key=lambda tl: (predict(pure, *tl, m, k, n, gc),
                                                  nearest(pure, *tl)))
                x = meas[pick] / min(meas.values()) - 1
                excess[name].append(x)
                worst[name] = max(worst[name], x)
        lines.append(f"| {m}×{k}×{n} | {k_up} / {k_up_few} | " +
                     " | ".join(f"{worst[name]:.1%}" for name in names) + " |")

    summary = ["", "| table | median excess | cases within 1 % | within 5 % | worst |",
               "|---|---|---|---|---|"]
    for name, xs in excess.items():
        summary.append(f"| {name} | {statistics.median(xs):.2%} | "
                       f"{sum(x <= 0.01 for x in xs) / len(xs):.0%} | "
                       f"{sum(x <= 0.05 for x in xs) / len(xs):.0%} | {max(xs):.1%} |")
    report = (f"# {NAME}{SUFFIX}: calibration templates by K\n\n"
              f"Excess = measured runtime of the picked tile / best measured tile - 1, over gc "
              f"{TEST_GC}, {len(SHAPES)} shapes.{' K and N padded to a multiple of 16.' if PAD else ''} "
              f"Worst excess per shape and table:\n\n" + "\n".join(lines + summary) + "\n")
    (out_dir(NAME) / f"README{SUFFIX}.md").write_text(report)
    print(report)

    # sw_templates: per table, the share of cases within 1 %, 1-5 % and worse
    # (stacked bars), with the worst case written at the end of each bar
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    bins = [("within 1%", lambda x: x <= 0.01), ("1% to 5%", lambda x: 0.01 < x <= 0.05),
            ("more than 5%", lambda x: x > 0.05)]
    order = list(reversed(names))   # the first table on top
    left = [0.0] * len(order)
    colors = [SERIES[2], SERIES[3], SERIES[1]]   # green / yellow / red: good to bad
    ax.set_axisbelow(True)
    ax.grid(False, axis="y")
    for j, (label, inside) in enumerate(bins):
        shares = [100 * sum(map(inside, excess[name])) / len(excess[name]) for name in order]
        ax.barh(range(len(order)), shares, left=left, color=colors[j], label=label, height=0.6)
        left = [a + b for a, b in zip(left, shares)]
    for i, name in enumerate(order):
        ax.text(101, i, f"worst {max(excess[name]):.0%}", va="center", fontsize=9)
    ax.set_yticks(range(len(order)), [LABELS[name] for name in order])
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the cases (%)")
    legend_above(ax, ncols=len(bins))
    print(save(fig, "software/s7_templates", "sw_templates"))


if __name__ == "__main__":
    main()
