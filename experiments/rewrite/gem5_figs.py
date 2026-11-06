"""Figures of the gem5 section (report: gem5 Simulation).

Reads the runs of gem5/asymm/run_tiles.py:
  gem5/asymm/exp/tiles/results.csv     the main grid, free generator
  gem5/asymm/exp/gencost/results.csv   slow generator, g_c > 0 (optional)

run:  python3 experiments/rewrite/gem5_figs.py
"""

import csv
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

from plot_style import INK, INK_2, SURFACE, legend_above, save, series

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2] / "gem5" / "asymm" / "exp"
REPORT = HERE.parents[1] / "report" / "typst" / "figures"

M = 192
K = 128
N = 512
TM = [8, 16, 32, 48, 64, 96, 192]
TN = [8, 16, 32, 64, 128]
SETTING = [(0, 1, "no padding, prefetcher"), (16, 0, "padding, no prefetcher"),
           (16, 1, "padding, prefetcher")]
NAME = ["$B$ in memory", "seeded PRNG-FIFO", "counter PRNG-FIFO"]

BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95",
         "#0d366b"]
DIVERGE = ["#a83232", "#e34948", "#f0a8a7", "#f0efec", "#9ec5f4", "#2a78d6",
           "#184f95"]
SEQ = LinearSegmentedColormap.from_list("seq", BLUES)
DIV = LinearSegmentedColormap.from_list("div", DIVERGE)


def load(name):
    path = EXP / name / "results.csv"
    if not path.exists():
        return None
    return list(csv.DictReader(open(path)))


rows = load("tiles")
gc_rows = load("gencost")


def get(tm, tn, mode, pad, pf, field, gen=0, data=None):
    for r in (data or rows):
        if (int(r["tm"]) == tm and int(r["tn"]) == tn
                and int(r["mode"]) == mode and int(r["pad"]) == pad
                and int(r["prefetch"]) == pf
                and int(float(r.get("gen_cost", 0))) == gen):
            return float(r[field])
    return None


def ksteps(tm, tn):
    """One k-step = one pass of the column-block loop of a tile."""
    return (M // tm) * (N // tn) * (K // 8)


def reads(tm):
    """FIFO reads on the correct path: all of B, 8 bytes at a time, once
    per row band."""
    return (M // tm) * K * N // 8


def grid(fn):
    return [[fn(tm, tn) for tn in TN] for tm in TM]


def short(v):
    if v >= 10:
        return "%.1f" % v
    if v >= 1:
        return "%.2f" % v
    return ("%.3f" % v)[1:]


def heat(ax, z, cmap, norm, fmt):
    im = ax.imshow(z, cmap=cmap, norm=norm, aspect="auto")
    for i in range(len(TM)):
        for j in range(len(TN)):
            r, g, b, a = cmap(norm(z[i][j]))
            ink = SURFACE
            if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55:
                ink = INK
            ax.text(j, i, fmt(z[i][j]), ha="center", va="center",
                    fontsize=7.5, color=ink)
    ax.set_xticks(range(len(TN)))
    ax.set_xticklabels(TN)
    ax.set_yticks(range(len(TM)))
    ax.set_yticklabels(TM)
    ax.set_xlabel("$T_N$")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    return im


def outline(ax, z):
    """Box around the smallest cell (the best tile)."""
    best = min((z[i][j], i, j) for i in range(len(TM))
               for j in range(len(TN)))
    ax.add_patch(Rectangle((best[2] - 0.5, best[1] - 0.5), 1, 1, fill=False,
                           edgecolor=INK, linewidth=1.8))


def label(ax, text):
    ax.set_title(text, fontsize=9.5, fontweight="normal", color=INK_2)


def colorbar(fig, im, axs, text):
    cb = fig.colorbar(im, ax=axs, shrink=0.85, pad=0.02)
    cb.set_label(text, color=INK_2)
    cb.outline.set_visible(False)


# ------------------------------------------------------------- main grid

def cycles():
    fig, axs = plt.subplots(2, 3, figsize=(8.6, 5.6), layout="constrained")
    norm = LogNorm(0.27, 1.9)
    for col in range(3):
        pad, pf, text = SETTING[col]
        for row in range(2):
            mode = [0, 2][row]
            ax = axs[row][col]

            def cpm(tm, tn):
                return get(tm, tn, mode, pad, pf, "cycles_per_mac")
            z = grid(cpm)
            im = heat(ax, z, SEQ, norm, short)
            outline(ax, z)
            if row == 0:
                label(ax, text)
                ax.set_xlabel("")
            if col == 0:
                ax.set_ylabel(NAME[mode] + "\n$T_M$")
    colorbar(fig, im, axs, "cycles per MAC")
    return fig


def misses():
    """Capacity steps: without the prefetcher they show in the misses, with
    it the L1 step is hidden. All with padding, so there are no conflicts."""
    fig, axs = plt.subplots(1, 2, figsize=(8, 3.2))
    lines = [(0, 0, "$B$ in memory"),
             (2, 0, "counter PRNG-FIFO"),
             (2, 1, "counter PRNG-FIFO, prefetcher on")]
    fields = ["l1d_miss", "l2_miss"]
    ylab = ["$L_1$D misses", "$L_2$ misses"]
    for p in range(2):
        ax = axs[p]
        for i in range(3):
            mode, pf, text = lines[i]
            y = [get(tm, 16, mode, 16, pf, fields[p]) for tm in TM]
            st = series([1, 0, 0][i])
            if i == 2:
                st["linestyle"] = "--"
            ax.plot(range(len(TM)), y, label=text, **st)
        ax.set_xticks(range(len(TM)))
        ax.set_xticklabels(TM)
        ax.set_yscale("log")
        ax.set_xlabel("$T_M$ ($T_N$ = 16, padding)")
        ax.set_ylabel(ylab[p])
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncols=3, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


def speedup():
    fig, axs = plt.subplots(1, 3, figsize=(8.6, 3.3), layout="constrained")
    norm = TwoSlopeNorm(vmin=0.9, vcenter=1.0, vmax=1.35)
    for col in range(3):
        pad, pf, text = SETTING[col]

        def ratio(tm, tn):
            m = get(tm, tn, 0, pad, pf, "cycles_per_mac")
            return m / get(tm, tn, 2, pad, pf, "cycles_per_mac")
        im = heat(axs[col], grid(ratio), DIV, norm, lambda v: "%.2f" % v)
        label(axs[col], text)
    axs[0].set_ylabel("$T_M$")
    colorbar(fig, im, axs, "speedup (cycles with $B$ in memory\n"
                           "/ cycles with the PRNG-FIFO)")
    return fig


def mispredict():
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.4), layout="constrained")

    def all_bp(tm, tn):
        return get(tm, tn, 2, 16, 1, "cond_incorrect") / ksteps(tm, tn)

    def wrong(tm, tn):
        return (get(tm, tn, 2, 16, 1, "pops") - reads(tm)) / ksteps(tm, tn)
    im0 = heat(axs[0], grid(all_bp), SEQ, LogNorm(0.04, 20), short)
    label(axs[0], "mispredicted branches per k-step")
    im1 = heat(axs[1], grid(wrong), SEQ, Normalize(0, 1.6),
               lambda v: "%.2f" % v)
    label(axs[1], "wrong-path reads of $B$ per k-step")
    axs[0].set_ylabel("$T_M$")
    fig.colorbar(im0, ax=axs[0], shrink=0.85).outline.set_visible(False)
    fig.colorbar(im1, ax=axs[1], shrink=0.85).outline.set_visible(False)
    return fig


def seeded():
    """Seeded PRNG-FIFO: share of reads that got the wrong elements of B,
    because a wrong-path read moved the stream on."""
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.4), layout="constrained")

    def wrong(tm, tn):
        return (get(tm, tn, 1, 16, 1, "pops") - reads(tm)) / ksteps(tm, tn)

    def bad(tm, tn):
        return 100 * get(tm, tn, 1, 16, 1, "stream_mismatch") / reads(tm)
    im0 = heat(axs[0], grid(wrong), SEQ, Normalize(0, 1.6),
               lambda v: "%.2f" % v)
    label(axs[0], "wrong-path reads of $B$ per k-step")
    im1 = heat(axs[1], grid(bad), SEQ, Normalize(0, 100),
               lambda v: "%.0f" % v)
    label(axs[1], "reads that got the wrong $B$ (%)")
    axs[0].set_ylabel("$T_M$")
    fig.colorbar(im0, ax=axs[0], shrink=0.85).outline.set_visible(False)
    fig.colorbar(im1, ax=axs[1], shrink=0.85).outline.set_visible(False)
    return fig


# ------------------------------------------------- slow generator (g_c > 0)

def gen_costs():
    return sorted({int(float(r["gen_cost"])) for r in gc_rows
                   if int(r["mode"]) == 2})


def gencost_tiles():
    """Cycles per MAC of the counter PRNG-FIFO for every tile, one panel per
    g_c, with the best tile boxed (padding and prefetcher on)."""
    gcs = [g for g in gen_costs() if g in (0, 32, 64, 128)]
    fig, axs = plt.subplots(1, len(gcs), figsize=(2.2 * len(gcs) + 1.2, 3.6),
                            layout="constrained", sharey=True)
    z_all = [grid(lambda tm, tn: get(tm, tn, 2, 16, 1, "cycles_per_mac", g,
                                     gc_rows)) for g in gcs]
    lo = min(min(r) for z in z_all for r in z)
    hi = max(max(r) for z in z_all for r in z)
    norm = LogNorm(lo, hi)
    for i, g in enumerate(gcs):
        im = heat(axs[i], z_all[i], SEQ, norm, short)
        outline(axs[i], z_all[i])
        label(axs[i], "$g_c = %d$" % g)
    axs[0].set_ylabel("$T_M$")
    colorbar(fig, im, axs, "cycles per MAC")
    return fig


def best(mode, g, data):
    out = None
    for tm in TM:
        for tn in TN:
            v = get(tm, tn, mode, 16, 1, "cycles_per_mac", g if mode else 0,
                    data)
            if v is not None and (out is None or v < out[0]):
                out = (v, tm, tn)
    return out


def gencost_speedup():
    """Best PRNG-FIFO tile against the best tile with B in memory."""
    gcs = gen_costs()
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    mem = best(0, 0, gc_rows)[0]
    fifo = [best(2, g, gc_rows)[0] for g in gcs]
    ax.plot(gcs, [mem / f for f in fifo], label="best tile of each",
            **series(0))
    tm0, tn0 = best(2, 0, gc_rows)[1:]
    same = [mem / get(tm0, tn0, 2, 16, 1, "cycles_per_mac", g, gc_rows)
            for g in gcs]
    ax.plot(gcs, same, label="best tile of $g_c = 0$ (%d x %d) kept"
            % (tm0, tn0), **series(1))
    ax.axhline(1.0, color=INK_2, linewidth=1, linestyle="--")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xticks(gcs)
    ax.set_xticklabels(gcs)
    ax.set_xlabel("$g_c$ (cycles per element)")
    ax.set_ylabel("speedup over $B$ in memory")
    legend_above(ax, 1)
    return fig


def main():
    figs = [(cycles, "gem5_cycles"), (misses, "gem5_misses"),
            (speedup, "gem5_speedup"), (mispredict, "gem5_mispredict"),
            (seeded, "gem5_seeded")]
    if gc_rows:
        figs += [(gencost_tiles, "gem5_gencost_tiles"),
                 (gencost_speedup, "gem5_gencost_speedup")]
    for fn, name in figs:
        png = save(fn(), "gem5", name)
        shutil.copy(png.with_suffix(".svg"), REPORT / (name + ".svg"))
        print("wrote", png, "and", REPORT / (name + ".svg"))


if __name__ == "__main__":
    main()
