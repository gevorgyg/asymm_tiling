import csv
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize
from matplotlib.colors import TwoSlopeNorm

from plot_style import INK, INK_2, SURFACE, save, series

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2] / "gem5" / "asymm" / "exp" / "tiles"
REPORT = HERE.parents[1] / "report" / "typst" / "figures"

M = 192
K = 128
N = 512
TM = [8, 16, 32, 48, 64, 96, 192]
TN = [8, 16, 32, 64, 128]
SETTING = [(0, 1, "pad 0, prefetch"), (16, 0, "pad 16, no prefetch"),
           (16, 1, "pad 16, prefetch")]
NAME = ["memory B", "seeded FIFO", "counter FIFO"]

BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95",
         "#0d366b"]
DIVERGE = ["#a83232", "#e34948", "#f0a8a7", "#f0efec", "#9ec5f4", "#2a78d6",
           "#184f95"]
SEQ = LinearSegmentedColormap.from_list("seq", BLUES)
DIV = LinearSegmentedColormap.from_list("div", DIVERGE)

rows = list(csv.DictReader(open(EXP / "results.csv")))


def get(tm, tn, mode, pad, pf, field):
    for r in rows:
        if (int(r["tm"]) == tm and int(r["tn"]) == tn
                and int(r["mode"]) == mode and int(r["pad"]) == pad
                and int(r["prefetch"]) == pf):
            return float(r[field])
    return None


def stat(tm, tn, mode, pad, pf, name):
    d = "tm%d_tn%d_m%d_g0_c2048_p%d_pad%d_pop1" % (tm, tn, mode, pf, pad)
    for line in open(EXP / d / "stats.txt"):
        if line.startswith("---------- End"):
            break
        f = line.split()
        if len(f) > 1 and f[0] == name:
            return float(f[1])
    return None


def ksteps(tm, tn):
    return (M // tm) * (N // tn) * (K // 8)


def grid(fn):
    z = []
    for tm in TM:
        row = []
        for tn in TN:
            row.append(fn(tm, tn))
        z.append(row)
    return z


def short(v):
    if v >= 10:
        return "%.1f" % v
    if v >= 1:
        return "%.2f" % v
    return ("%.3f" % v)[1:]


def heat(ax, z, cmap, norm, fmt):
    ax.imshow(z, cmap=cmap, norm=norm, aspect="auto")
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


def label(ax, text):
    ax.set_title(text, fontsize=9.5, fontweight="normal", color=INK_2)


def cycles():
    fig, axs = plt.subplots(2, 3, figsize=(8, 5.6))
    norm = LogNorm(0.27, 1.9)
    for col in range(3):
        pad, pf, text = SETTING[col]
        for row in range(2):
            mode = [0, 2][row]
            ax = axs[row][col]

            def cpm(tm, tn):
                return get(tm, tn, mode, pad, pf, "cycles_per_mac")
            heat(ax, grid(cpm), SEQ, norm, short)
            if row == 0:
                label(ax, text)
                ax.set_xlabel("")
            if col == 0:
                ax.set_ylabel(NAME[mode] + "\n$T_M$")
    fig.tight_layout()
    return fig


def misses():
    fig, axs = plt.subplots(1, 2, figsize=(8, 3.2))
    lines = [(0, 0, "memory B, pad 0"), (0, 16, "memory B, pad 16"),
             (2, 16, "counter FIFO, pad 16")]
    fields = ["l1d_miss", "l2_miss"]
    ylab = ["$L_1$D misses", "$L_2$ misses"]
    for p in range(2):
        ax = axs[p]
        for i in range(3):
            mode, pad, text = lines[i]
            y = []
            for tm in TM:
                y.append(get(tm, 16, mode, pad, 1, fields[p]))
            st = series([1, 1, 2][i])
            if i == 0:
                st["color"] = INK_2
                st["linestyle"] = "--"
            ax.plot(range(len(TM)), y, label=text, **st)
        ax.set_xticks(range(len(TM)))
        ax.set_xticklabels(TM)
        ax.set_yscale("log")
        ax.set_xlabel("$T_M$ ($T_N$ = 16, prefetch on)")
        ax.set_ylabel(ylab[p])
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncols=3, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


def speedup():
    fig, axs = plt.subplots(1, 3, figsize=(8, 3.3))
    norm = TwoSlopeNorm(vmin=0.9, vcenter=1.0, vmax=1.35)
    for col in range(3):
        pad, pf, text = SETTING[col]

        def ratio(tm, tn):
            m = get(tm, tn, 0, pad, pf, "cycles_per_mac")
            return m / get(tm, tn, 2, pad, pf, "cycles_per_mac")
        heat(axs[col], grid(ratio), DIV, norm, lambda v: "%.2f" % v)
        label(axs[col], text)
    axs[0].set_ylabel("$T_M$")
    fig.tight_layout()
    return fig


def mispredict():
    fig, axs = plt.subplots(1, 2, figsize=(6.4, 3.4))

    def all_bp(tm, tn):
        n = stat(tm, tn, 2, 16, 1, "system.cpu.branchPred.condIncorrect")
        return n / ksteps(tm, tn)

    def wrong(tm, tn):
        n = get(tm, tn, 2, 16, 1, "pops") - (M // tm) * K * N // 8
        return n / ksteps(tm, tn)
    heat(axs[0], grid(all_bp), SEQ, LogNorm(0.04, 20), short)
    label(axs[0], "all mispredicted branches")
    heat(axs[1], grid(wrong), SEQ, Normalize(0, 1.6),
         lambda v: "%.2f" % v)
    label(axs[1], "wrong-path $B$ reads")
    axs[0].set_ylabel("$T_M$")
    fig.tight_layout()
    return fig


def main():
    figs = [(cycles, "gem5_cycles"), (misses, "gem5_misses"),
            (speedup, "gem5_speedup"), (mispredict, "gem5_mispredict")]
    for fn, name in figs:
        png = save(fn(), "gem5", name)
        shutil.copy(png.with_suffix(".svg"), REPORT / (name + ".svg"))
        print("wrote", png, "and", REPORT / (name + ".svg"))


if __name__ == "__main__":
    main()
