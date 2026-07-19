"""Generate result charts for every math-model-no-l2 experiment.

Outputs PNGs into each experiment's own directory.

Usage:
    python plot_all.py
"""

import json
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── Design tokens (same palette as presentation) ─────────────────────────────
BLUE     = "#2a78d6"
GREEN    = "#1baf7a"
YELLOW   = "#eda100"
VIOLET   = "#4a3aa7"
RED      = "#e34948"
SURFACE  = "#fcfcfb"
INK      = "#0b0b0b"
INK_MUT  = "#52514e"
MUTED    = "#898781"
GRID     = "#e1e0d9"
BASELINE = "#c3c2b7"

CAT = [BLUE, GREEN, YELLOW, VIOLET, RED]   # categorical slots 1-5

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Liberation Sans", "Arial"],
    "font.size": 11,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelcolor": INK_MUT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "lines.linewidth": 2.0,
    "lines.markersize": 6,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.facecolor": SURFACE,
})

HERE = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# E3 — α(TM) calibration
# ─────────────────────────────────────────────────────────────────────────────

def plot_e3():
    OUT = HERE / "e3-alpha-calibration"
    data = json.load(open(OUT / "results.json"))
    MNK = 256 ** 3

    # collect α per (TM, TN) at gc=0
    table = defaultdict(dict)
    for v in data.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        M = ov["A_HEIGHT_DIM"]
        table[tm][tn] = v["metrics"]["cycles"] / (M * 256 * 256)

    TM_ALL = sorted(table)
    TN_VALS = sorted({tn for d in table.values() for tn in d})
    COLORS_TN = {tn: c for tn, c in zip(TN_VALS, CAT)}

    # Chart 1: multi-TN α vs TM
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    EVICT_IDX = {32: None, 64: None}   # filled below
    for tn in TN_VALS:
        xs = [tm for tm in TM_ALL if tn in table[tm]]
        ys = [table[tm][tn] for tm in xs]
        ax.plot(xs, ys, color=COLORS_TN[tn], lw=2.2, marker="o", ms=6,
                label=f"$T_N = {tn}$", zorder=3)
    ax.set_xlabel("Tile-M dimension ($T_M$)", fontsize=12, labelpad=6)
    ax.set_ylabel("α  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only", fontsize=13, pad=10)
    ax.set_xticks(TM_ALL)
    ax.set_xticklabels([str(t) for t in TM_ALL])
    ax.legend(labelcolor=INK_MUT, loc="upper left")
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_vs_tm_multitn.png")
    plt.close(fig)
    print("  ✓ e3/alpha_vs_tm_multitn.png")


# ─────────────────────────────────────────────────────────────────────────────
# E4 — cache-fill mechanism
# ─────────────────────────────────────────────────────────────────────────────

def plot_e4():
    OUT = HERE / "e4-cfill-mechanism"
    data = json.load(open(OUT / "results.json"))

    rows = []
    for v in data.values():
        ov = v["overrides"]
        M = ov["A_HEIGHT_DIM"]
        TK = ov["TILE_K"]
        mnk = M * 256 * 256
        alpha = v["metrics"]["cycles"] / mnk
        fills = v["metrics"]["l1"]["line_fills"]
        fills_per_mnk = fills / mnk
        rows.append((ov["TILE_M"], ov["TILE_N"], TK, alpha, fills_per_mnk))

    # group by TM for TN=32
    rows32 = sorted((tm, tk, a, f) for tm, tn, tk, a, f in rows if tn == 32)
    by_tm_tk = defaultdict(dict)
    for tm, tk, a, f in rows32:
        by_tm_tk[tm][tk] = (a, f)

    TM_VALS = sorted(by_tm_tk)
    TK_VALS = sorted({tk for d in by_tm_tk.values() for tk in d})
    cmap = plt.colormaps["viridis"].resampled(len(TK_VALS))
    TK_COLORS = {tk: mpl.colors.to_hex(cmap(i)) for i, tk in enumerate(TK_VALS)}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))

    for tk in TK_VALS:
        xs = [tm for tm in TM_VALS if tk in by_tm_tk[tm]]
        alphas = [by_tm_tk[tm][tk][0] for tm in xs]
        fills  = [by_tm_tk[tm][tk][1] for tm in xs]
        lbl = f"$T_K = {tk}$"
        ax1.plot(xs, alphas, color=TK_COLORS[tk], lw=2.2, marker="o", ms=6, label=lbl)
        ax2.plot(xs, fills,  color=TK_COLORS[tk], lw=2.2, marker="o", ms=6, label=lbl)

    for ax in (ax1, ax2):
        ax.set_xlabel("Tile-M ($T_M$)", fontsize=12, labelpad=6)
        ax.set_xticks(TM_VALS)
        ax.legend(labelcolor=INK_MUT)

    ax1.set_ylabel("α  (cycles / output element)", fontsize=12, labelpad=6)
    ax1.set_title("A-load cost α vs $T_M$", fontsize=13, pad=8)
    ax2.set_ylabel("L1 line fills / MNK", fontsize=12, labelpad=6)
    ax2.set_title("L1 cache-line fills vs $T_M$", fontsize=13, pad=8)

    fig.suptitle("E4: Cache-fill mechanism  —  L1-only, $T_N = 32$, $g_c = 0$",
                 fontsize=13, y=1.02)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "cfill_mechanism.png")
    plt.close(fig)
    print("  ✓ e4/cfill_mechanism.png")


# ─────────────────────────────────────────────────────────────────────────────
# E6 — full α(TM, TN) surface
# ─────────────────────────────────────────────────────────────────────────────

def plot_e6():
    OUT = HERE / "e6-tn-independence"
    data = json.load(open(OUT / "results.json"))

    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]
    table = defaultdict(dict)
    for v in data.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if tm in TM_ALL and tn in TN_ALL:
            table[tm][tn] = v["metrics"]["cycles"] / (ov["A_HEIGHT_DIM"] * 256 * 256)

    # ── Chart 1: heatmap ─────────────────────────────────────────────────────
    Z = np.array([[table[tm].get(tn, np.nan) for tn in TN_ALL] for tm in TM_ALL])
    Z_cap = np.clip(Z, 0, 7.0)

    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    im = ax.imshow(Z_cap, aspect="auto", cmap="YlOrRd", vmin=3.1, vmax=7.0, origin="upper")
    for i, tm in enumerate(TM_ALL):
        for j, tn in enumerate(TN_ALL):
            val = table[tm].get(tn, np.nan)
            txt = f"**{val:.1f}**" if val > 7 else (f"{val:.2f}" if not np.isnan(val) else "—")
            color = "white" if val > 5.5 else INK
            ax.text(j, i, txt, ha="center", va="center", fontsize=9,
                    color=color, fontweight="bold" if val > 7 else "normal")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("α  (cycles / output element)", fontsize=11)
    ax.axhline(1.5, color=BLUE, lw=1.5, ls="--", alpha=0.7)
    ax.text(len(TN_ALL) - 0.45, 1.3, "L1 / DRAM boundary", color=BLUE,
            fontsize=8.5, ha="right", va="bottom")
    ax.set_xticks(range(len(TN_ALL))); ax.set_xticklabels([str(t) for t in TN_ALL], fontsize=11)
    ax.set_yticks(range(len(TM_ALL))); ax.set_yticklabels([str(t) for t in TM_ALL], fontsize=11)
    ax.set_xlabel("$T_N$", fontsize=13, labelpad=6)
    ax.set_ylabel("$T_M$", fontsize=13, labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only", fontsize=13, pad=10)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_heatmap.png")
    plt.close(fig)
    print("  ✓ e6/alpha_heatmap.png")

    # ── Chart 2: α vs TN for fixed TM ────────────────────────────────────────
    L1_TMS  = [8, 12];         DRAM_TMS = [24, 32]
    STYLES = {
        8:  dict(color=BLUE,            ls="-",  label="$T_M = 8$   (L1)"),
        12: dict(color="#1c5cab",       ls="--", label="$T_M = 12$  (L1)"),
        24: dict(color=RED,             ls="-",  label="$T_M = 24$  (DRAM)"),
        32: dict(color="#b02b2a",       ls="--", label="$T_M = 32$  (DRAM)"),
    }
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    for tm in L1_TMS + DRAM_TMS:
        xs = [tn for tn in TN_ALL if table[tm].get(tn)]
        ys = [table[tm][tn] for tn in xs]
        sty = STYLES[tm]
        ax.plot(xs, ys, color=sty["color"], ls=sty["ls"], lw=2.2,
                marker="o", ms=6, label=sty["label"], zorder=3)
    ax.axhline(3.396, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(65, 3.30, "L1 baseline ≈ 3.4", color=MUTED, fontsize=8.5, ha="right")
    ax.set_xlabel("$T_N$", fontsize=12, labelpad=6)
    ax.set_ylabel("α  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only", fontsize=13, pad=10)
    ax.set_xticks(TN_ALL); ax.set_xticklabels([str(t) for t in TN_ALL])
    ax.set_ylim(2.8, 7.0)
    ax.legend(labelcolor=INK_MUT)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_vs_tn.png")
    plt.close(fig)
    print("  ✓ e6/alpha_vs_tn.png")

    # ── Chart 3: α vs TM for different TN ────────────────────────────────────
    COLORS_TN = {4: BLUE, 8: GREEN, 16: YELLOW, 32: VIOLET, 64: RED}
    EVICT_IDX = {32: 7, 64: 5}
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for tn in TN_ALL:
        color = COLORS_TN[tn]
        ei = EVICT_IDX.get(tn, len(TM_ALL))
        xs_s = TM_ALL[:ei]; ys_s = [table[tm].get(tn) for tm in xs_s]
        xs_e = TM_ALL[ei-1:]; ys_e = [table[tm].get(tn) for tm in xs_e]
        if None not in ys_s:
            ax.plot(xs_s, ys_s, color=color, lw=2.2, marker="o", ms=6,
                    label=f"$T_N = {tn}$", zorder=3)
        if ei < len(TM_ALL) and None not in ys_e:
            ax.plot(xs_e, ys_e, color=color, lw=2.2, marker="o", ms=6,
                    ls="--", alpha=0.45, zorder=3)
    ax.set_xlabel("Tile-M dimension ($T_M$)", fontsize=12, labelpad=6)
    ax.set_ylabel("α  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only", fontsize=13, pad=10)
    ax.set_xticks(TM_ALL); ax.set_xticklabels([str(t) for t in TM_ALL])
    ax.set_ylim(2.8, 10.5)
    ax.legend(labelcolor=INK_MUT, loc="upper left")
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_vs_tm.png")
    plt.close(fig)
    print("  ✓ e6/alpha_vs_tm.png")


# ─────────────────────────────────────────────────────────────────────────────
# E8 — gc boundary sweep / TM* transitions
# ─────────────────────────────────────────────────────────────────────────────

def plot_e8():
    OUT = HERE / "e8-gc-boundary-sweep"
    data = json.load(open(OUT / "results.json"))
    MNK = 192 * 256 * 256

    TN_ALL = [4, 8, 16, 32, 64]
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    COLORS_TN = {4: BLUE, 8: GREEN, 16: YELLOW, 32: VIOLET, 64: RED}

    gc_tn_tm_alpha = defaultdict(list)   # (gc, tn) -> [(tm, alpha)]
    for v in data.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if gc == 0 or tn not in TN_ALL or tm not in TM_ALL:
            continue
        alpha = v["metrics"]["cycles"] / MNK
        gc_tn_tm_alpha[(gc, tn)].append((tm, alpha))

    GC_VALS = sorted({gc for gc, _ in gc_tn_tm_alpha})

    # best TM* and best α per (gc, tn)
    best = {}
    for (gc, tn), entries in gc_tn_tm_alpha.items():
        tm_star, alpha_star = min(entries, key=lambda x: x[1])
        best[(gc, tn)] = (tm_star, alpha_star)

    # ── Chart 1: TM* trajectory ───────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for tn in TN_ALL:
        xs = sorted(gc for gc, t in best if t == tn)
        ys = [best[(gc, tn)][0] for gc in xs]
        ax.step(xs, ys, where="post", color=COLORS_TN[tn], lw=2.5,
                label=f"$T_N = {tn}$", zorder=3)
        ax.scatter(xs, ys, color=COLORS_TN[tn], s=40, zorder=4)
    ax.set_xscale("symlog", linthresh=80, linscale=0.8)
    xticks = [0, 20, 40, 60, 80, 150, 400]
    ax.set_xticks(xticks); ax.set_xticklabels([str(v) for v in xticks])
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.set_yticks([12, 32, 64, 96]); ax.set_yticklabels(["12", "32", "64", "96"])
    ax.set_ylim(4, 115); ax.set_xlim(0, 430)
    ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax.set_ylabel("Optimal $T_M^*$", fontsize=12, labelpad=6)
    ax.set_title(r"Calibrated $T_M^*$ vs $g_c$  —  L1-only", fontsize=13, pad=10)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), labelcolor=INK_MUT, fontsize=11)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "tm_star_trajectory.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e8/tm_star_trajectory.png")

    # ── Chart 2: best α* vs gc per TN ────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for tn in TN_ALL:
        xs = sorted(gc for gc, t in best if t == tn)
        ys = [best[(gc, tn)][1] for gc in xs]
        ax.plot(xs, ys, color=COLORS_TN[tn], lw=2.2, marker="o", ms=6,
                label=f"$T_N = {tn}$", zorder=3)
    ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax.set_ylabel("α*  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title(r"Best achievable $\alpha^*$ vs $g_c$  —  L1-only", fontsize=13, pad=10)
    ax.set_xscale("symlog", linthresh=80, linscale=0.8)
    ax.set_xticks(xticks); ax.set_xticklabels([str(v) for v in xticks])
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.legend(loc="upper left", labelcolor=INK_MUT)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "best_alpha_vs_gc.png")
    plt.close(fig)
    print("  ✓ e8/best_alpha_vs_gc.png")


# ─────────────────────────────────────────────────────────────────────────────
# E13 — FIFO-B vs Memory-B
# ─────────────────────────────────────────────────────────────────────────────

def plot_e13():
    OUT = HERE / "e13-fifo-vs-mem"
    data13 = json.load(open(OUT / "results.json"))
    data8  = json.load(open(HERE / "e8-gc-boundary-sweep/results.json"))
    MNK = 192 * 256 * 256

    TN_ALL = [4, 8, 16, 32, 64]
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]

    # Memory-B: best α per TN (at gc=0 — Memory-B has no gc)
    mem_best = {}
    mem_table = defaultdict(dict)
    for v in data13.values():
        ov = v["overrides"]
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if tm in TM_ALL and tn in TN_ALL:
            alpha = v["metrics"]["cycles"] / MNK
            mem_table[tn][tm] = alpha
    for tn in TN_ALL:
        if mem_table[tn]:
            mem_best[tn] = min(mem_table[tn].values())

    # FIFO-B gc=0: best α per TN (from E8)
    fifo_gc0 = defaultdict(dict)
    for v in data8.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if tm in TM_ALL and tn in TN_ALL:
            fifo_gc0[tn][tm] = v["metrics"]["cycles"] / MNK
    fifo_best = {tn: min(fifo_gc0[tn].values()) for tn in TN_ALL if fifo_gc0[tn]}

    # FIFO-B: best α per (gc, TN) — all gc values
    fifo_gc = defaultdict(list)
    for v in data8.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if tn not in TN_ALL or tm not in TM_ALL:
            continue
        fifo_gc[(gc, tn)].append(v["metrics"]["cycles"] / MNK)
    GC_VALS = sorted({gc for gc, _ in fifo_gc})

    # ── Chart 1: grouped bar — absolute α per TN ─────────────────────────────
    x = np.arange(len(TN_ALL)); w = 0.35
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.bar(x - w/2, [mem_best[tn]  for tn in TN_ALL], w, color=RED,  label="Memory-B (optimal $T_M^*$)", zorder=3)
    ax.bar(x + w/2, [fifo_best[tn] for tn in TN_ALL], w, color=BLUE, label="FIFO-B ($g_c = 0$)", zorder=3)
    for xi, tn in enumerate(TN_ALL):
        adv = (mem_best[tn] - fifo_best[tn]) / mem_best[tn] * 100
        ax.text(xi, mem_best[tn] + 0.15, f"−{adv:.0f}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"$T_N = {t}$" for t in TN_ALL], fontsize=11)
    ax.set_ylabel("α*  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title("FIFO-B vs Memory-B  —  L1-only, $g_c = 0$", fontsize=13, pad=10)
    ax.set_ylim(0, 9.5)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(labelcolor=INK_MUT, loc="upper right")
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "fifo_vs_mem_absolute.png")
    plt.close(fig)
    print("  ✓ e13/fifo_vs_mem_absolute.png")

    # ── Chart 2: FIFO advantage % per TN ─────────────────────────────────────
    adv_pct = [(mem_best[tn] - fifo_best[tn]) / mem_best[tn] * 100 for tn in TN_ALL]
    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    bars = ax.bar(x, adv_pct, color=BLUE, width=0.55, zorder=3)
    for bar, pct in zip(bars, adv_pct):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                f"{pct:.1f}%", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"$T_N = {t}$" for t in TN_ALL])
    ax.set_ylabel("FIFO speedup over Memory-B (%)", fontsize=12, labelpad=6)
    ax.set_title("FIFO-B advantage  —  L1-only, $g_c = 0$", fontsize=13, pad=10)
    ax.set_ylim(0, 65)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "fifo_advantage_pct.png")
    plt.close(fig)
    print("  ✓ e13/fifo_advantage_pct.png")

    # ── Chart 3: FIFO best α vs gc (TN=32) + Memory-B crossover ─────────────
    tn = 32
    gc_xs = sorted({gc for gc, t in fifo_gc if t == tn})
    gc_ys = [min(fifo_gc[(gc, tn)]) for gc in gc_xs]
    mem_line = mem_best[tn]
    gc_star_approx = None
    for i in range(len(gc_ys) - 1):
        if gc_ys[i] <= mem_line <= gc_ys[i+1]:
            gc_star_approx = gc_xs[i] + (mem_line - gc_ys[i]) / (gc_ys[i+1] - gc_ys[i]) * (gc_xs[i+1] - gc_xs[i])
            break

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.axhline(mem_line, color=RED, lw=2, ls="--", label="Memory-B", zorder=2)
    ax.plot(gc_xs, gc_ys, color=BLUE, lw=2.2, marker="o", ms=6,
            label="FIFO-B (optimal $T_M^*$)", zorder=3)
    if gc_star_approx:
        ax.axvline(gc_star_approx, color=MUTED, lw=1, ls=":", zorder=1)
        ax.text(gc_star_approx + 4, 5.5, f"$g_c^* \\approx {gc_star_approx:.0f}$",
                color=MUTED, fontsize=9)
    ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax.set_ylabel("α*  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title("FIFO-B vs Memory-B  —  L1-only, $T_N = 32$", fontsize=13, pad=10)
    ax.set_xlim(-5, 420)
    ax.set_ylim(2.9, 7.0)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(50))
    ax.legend(labelcolor=INK_MUT)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "fifo_vs_mem_gc.png")
    plt.close(fig)
    print("  ✓ e13/fifo_vs_mem_gc.png")


# ─────────────────────────────────────────────────────────────────────────────
# E14 — pipelined FIFO
# ─────────────────────────────────────────────────────────────────────────────

def plot_e14():
    OUT = HERE / "e14-pipelined-fifo-vs-mem"
    data14 = json.load(open(OUT / "results.json"))
    data8  = json.load(open(HERE / "e8-gc-boundary-sweep/results.json"))
    data13 = json.load(open(HERE / "e13-fifo-vs-mem/results.json"))
    MNK = 192 * 256 * 256

    TN_SHOW = [32]   # focus chart on TN=32; add TN=64 variant below
    TM_ALL  = [8, 12, 16, 24, 32, 48, 64, 96]
    PREFILLS = [1, 2, 4]
    PIPE_COLORS = {1: BLUE, 2: GREEN, 4: YELLOW}

    for tn_focus in [32, 64]:
        # pipelined FIFO
        pipe = defaultdict(list)
        for v in data14.values():
            ov = v["overrides"]
            if ov["TILE_N"] != tn_focus or ov["TILE_M"] not in TM_ALL:
                continue
            pipe[(ov["PRNG_FIFO_NUM_PREFILL"], ov["PRNG_FIFO_GEN_COST"])].append(
                v["metrics"]["cycles"] / MNK)

        GC14 = sorted({gc for _, gc in pipe})

        # standard FIFO from E8
        std = defaultdict(list)
        for v in data8.values():
            ov = v["overrides"]
            if ov["TILE_N"] != tn_focus or ov["TILE_M"] not in TM_ALL:
                continue
            std[ov["PRNG_FIFO_GEN_COST"]].append(v["metrics"]["cycles"] / MNK)
        std_xs = sorted(std); std_ys = [min(std[gc]) for gc in std_xs]

        # Memory-B from E13
        mem_alphas = []
        for v in data13.values():
            ov = v["overrides"]
            if ov["TILE_N"] != tn_focus or ov["TILE_M"] not in TM_ALL:
                continue
            mem_alphas.append(v["metrics"]["cycles"] / MNK)
        mem_line = min(mem_alphas) if mem_alphas else None

        fig, ax = plt.subplots(figsize=(8.0, 5.0))
        if mem_line:
            ax.axhline(mem_line, color=RED, lw=2, ls="--", label="Memory-B", zorder=2)
            ax.text(max(GC14) * 1.02, mem_line + 0.1, "Memory-B",
                    color=RED, fontsize=10, va="bottom")
        ax.plot(std_xs, std_ys, color=MUTED, lw=1.8, ls=":", marker="o", ms=5,
                label="FIFO-B standard", zorder=3)
        for pf in PREFILLS:
            xs = sorted(gc for _, gc in pipe if _ == pf)
            ys = [min(pipe[(pf, gc)]) for gc in xs]
            ax.plot(xs, ys, color=PIPE_COLORS[pf], lw=2.2, marker="o", ms=6,
                    label=f"FIFO-B pipelined $N = {pf}$", zorder=4)
        ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
        ax.set_ylabel("α*  (cycles / output element)", fontsize=12, labelpad=6)
        ax.set_title(f"Pipelined FIFO-B vs Memory-B  —  L1-only, $T_N = {tn_focus}$",
                     fontsize=13, pad=10)
        ax.set_xlim(-30, max(GC14) * 1.08)
        ax.tick_params(labelsize=11)
        ax.legend(labelcolor=INK_MUT, loc="upper left")
        fig.tight_layout(pad=1.2)
        fname = f"pipelining_gc_tn{tn_focus}.png"
        fig.savefig(OUT / fname)
        plt.close(fig)
        print(f"  ✓ e14/{fname}")


# ─────────────────────────────────────────────────────────────────────────────
# e-l1size-regime — regime boundary shifts with L1 size
# ─────────────────────────────────────────────────────────────────────────────

def plot_l1size():
    OUT = HERE / "e-l1size-regime"
    data = json.load(open(OUT / "results.json"))

    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]
    L1S    = [8192, 16384, 32768, 65536]
    L1_LABELS = {8192: "8 KB", 16384: "16 KB", 32768: "32 KB", 65536: "64 KB"}
    L1_COLORS = {8192: RED, 16384: BLUE, 32768: GREEN, 65536: YELLOW}

    table = defaultdict(lambda: defaultdict(dict))  # l1 -> tn -> tm -> alpha
    for v in data.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        l1, tm, tn = ov["L1_SIZE_BYTES"], ov["TILE_M"], ov["TILE_N"]
        if l1 in L1S and tm in TM_ALL and tn in TN_ALL:
            table[l1][tn][tm] = v["metrics"]["cycles"] / (ov["A_HEIGHT_DIM"] * 256 * 256)

    # ── Chart 1: α(TM) at TN=32 for each L1 size ─────────────────────────────
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for l1 in L1S:
        xs = [tm for tm in TM_ALL if table[l1][32].get(tm)]
        ys = [min(table[l1][32][tm], 11.0) for tm in xs]
        ax.plot(xs, ys, color=L1_COLORS[l1], lw=2.2, marker="o", ms=6,
                label=f"L1 = {L1_LABELS[l1]}", zorder=3)
        # mark regime boundary TM_L1 = L1/1024
        bnd = l1 // 1024
        ax.axvline(bnd, color=L1_COLORS[l1], lw=1, ls=":", alpha=0.5, zorder=1)
    ax.set_xlabel("Tile-M dimension ($T_M$)", fontsize=12, labelpad=6)
    ax.set_ylabel("α  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title(r"$\alpha(T_M)$ at $g_c = 0$, $T_N = 32$  — regime boundary shifts with L1",
                 fontsize=13, pad=10)
    ax.set_xticks(TM_ALL); ax.set_xticklabels([str(t) for t in TM_ALL])
    ax.set_ylim(2.8, 11); ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(labelcolor=INK_MUT, loc="upper left")
    ax.text(0.98, 0.97, "Dotted verticals: predicted L1/DRAM boundary",
            transform=ax.transAxes, ha="right", va="top", fontsize=9, color=MUTED)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "l1size_regime_tn32.png")
    plt.close(fig)
    print("  ✓ e-l1size/l1size_regime_tn32.png")

    # ── Chart 2: heatmaps side-by-side for each L1 size ──────────────────────
    fig, axes = plt.subplots(1, 4, figsize=(18, 5.0), sharey=True)
    for ax, l1 in zip(axes, L1S):
        Z = np.array([[table[l1][tn].get(tm, np.nan) for tn in TN_ALL] for tm in TM_ALL])
        Z_cap = np.clip(Z, 0, 7.0)
        im = ax.imshow(Z_cap.T, aspect="auto", cmap="YlOrRd",
                       vmin=3.1, vmax=7.0, origin="upper")
        for i, tn in enumerate(TN_ALL):
            for j, tm in enumerate(TM_ALL):
                val = table[l1][tn].get(tm, np.nan)
                txt = f"{val:.1f}" if not np.isnan(val) else "—"
                color = "white" if (not np.isnan(val) and val > 5.5) else INK
                ax.text(j, i, txt, ha="center", va="center", fontsize=7.5,
                        color=color, fontweight="bold" if (not np.isnan(val) and val > 7) else "normal")
        ax.set_title(f"L1 = {L1_LABELS[l1]}", fontsize=12)
        ax.set_xticks(range(len(TM_ALL))); ax.set_xticklabels([str(t) for t in TM_ALL], fontsize=8, rotation=45)
        ax.set_yticks(range(len(TN_ALL))); ax.set_yticklabels([str(t) for t in TN_ALL], fontsize=9)
        ax.set_xlabel("$T_M$", fontsize=11)
        if ax == axes[0]:
            ax.set_ylabel("$T_N$", fontsize=11)
    fig.colorbar(im, ax=axes[-1], fraction=0.046, pad=0.04, label="α")
    fig.suptitle(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only, regime boundary shifts with L1 size",
                 fontsize=13, y=1.01)
    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "l1size_heatmaps.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e-l1size/l1size_heatmaps.png")


# ─────────────────────────────────────────────────────────────────────────────
# E8 — model validation: predicted vs empirical
# ─────────────────────────────────────────────────────────────────────────────

def plot_e8_validation():
    OUT = HERE / "e8-gc-boundary-sweep"
    data = json.load(open(OUT / "results.json"))
    MNK = 192 * 256 * 256
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]
    COLORS_TN = {4: BLUE, 8: GREEN, 16: YELLOW, 32: VIOLET, 64: RED}

    # Build calibration table from gc=0
    alpha_table = defaultdict(dict)
    for v in data.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        alpha_table[tm][tn] = v["metrics"]["cycles"] / MNK

    # Collect gc>0 measurements
    test = defaultdict(lambda: defaultdict(dict))
    for v in data.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if gc == 0 or tm not in TM_ALL or tn not in TN_ALL:
            continue
        test[(gc, tn)][tm] = v["metrics"]["cycles"] / MNK

    GC_VALS = sorted({gc for gc, _ in test})

    # Compute predicted and empirical for every (gc, tn) test case
    records = []   # (gc, tn, pred_tm, emp_tm, pred_alpha, emp_alpha)
    for gc in GC_VALS:
        for tn in TN_ALL:
            tm_map = test[(gc, tn)]
            if not tm_map:
                continue
            emp_tm = min(tm_map, key=lambda t: tm_map[t])
            emp_alpha = tm_map[emp_tm]
            model_scores = {
                tm: max(alpha_table[tm][tn], gc / tm)
                for tm in TM_ALL if tn in alpha_table[tm]
            }
            pred_tm = min(model_scores, key=lambda t: model_scores[t])
            pred_alpha = model_scores[pred_tm]
            records.append((gc, tn, pred_tm, emp_tm, pred_alpha, emp_alpha))

    n_match = sum(1 for r in records if r[2] == r[3])
    n_total = len(records)

    # ── Scatter: predicted TM* vs empirical TM* ──────────────────────────────
    # TM values are discrete; jitter per TN so overlapping points stay visible
    TN_JITTER = {tn: (i - 2) * 1.2 for i, tn in enumerate(TN_ALL)}

    fig, ax = plt.subplots(figsize=(6.5, 6.0))

    # diagonal = perfect prediction
    diag = [TM_ALL[0] - 4, TM_ALL[-1] + 4]
    ax.plot(diag, diag, color=BASELINE, lw=1.5, ls="--", zorder=1, label="perfect fit (y = x)")

    for tn in TN_ALL:
        pts = [(r[2], r[3]) for r in records if r[1] == tn]
        if not pts:
            continue
        jit = TN_JITTER[tn]
        px = [x + jit for x, _ in pts]
        py = [y + jit for _, y in pts]
        ax.scatter(px, py, color=COLORS_TN[tn], s=65, zorder=3,
                   edgecolors="white", linewidths=0.7, label=f"$T_N = {tn}$")

    ticks = TM_ALL
    ax.set_xticks(ticks); ax.set_xticklabels([str(t) for t in ticks], fontsize=10)
    ax.set_yticks(ticks); ax.set_yticklabels([str(t) for t in ticks], fontsize=10)
    ax.set_xlim(TM_ALL[0] - 6, TM_ALL[-1] + 6)
    ax.set_ylim(TM_ALL[0] - 6, TM_ALL[-1] + 6)
    ax.set_aspect("equal")
    ax.set_xlabel("Model predicted $T_M^*$", fontsize=13, labelpad=8)
    ax.set_ylabel("Empirical best $T_M^*$", fontsize=13, labelpad=8)
    ax.set_title("Optimal tile prediction vs empirical\n(70 test cases, 14 $g_c$ values × 5 $T_N$ values)",
                 fontsize=13, pad=10)
    ax.text(0.05, 0.97, f"{n_match}/{n_total} correct  ({100*n_match/n_total:.0f}%)",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=13, fontweight="bold", color=INK)
    ax.legend(labelcolor=INK_MUT, loc="lower right", fontsize=10)

    fig.tight_layout(pad=1.4)
    fig.savefig(OUT / "prediction_fit.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e8/prediction_fit.png")


# ─────────────────────────────────────────────────────────────────────────────
# E8 — optimal asymmetric tiling vs square tile
# ─────────────────────────────────────────────────────────────────────────────

def plot_e8_vs_square():
    OUT = HERE / "e8-gc-boundary-sweep"
    data = json.load(open(OUT / "results.json"))
    MNK = 192 * 256 * 256
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [8, 16, 32, 64]   # TN=4 excluded: TM=4 not in sweep
    COLORS_TN = {8: GREEN, 16: YELLOW, 32: VIOLET, 64: RED}
    GC_VALS = [15, 30, 38, 42, 47, 50, 52, 57, 68, 74, 100, 150, 250, 400]

    # Collect all measured gc>0 values: (gc, tn, tm) -> alpha
    measured = defaultdict(dict)
    for v in data.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if gc == 0 or tm not in TM_ALL or tn not in TN_ALL:
            continue
        measured[(gc, tn)][tm] = v["metrics"]["cycles"] / MNK

    # For each (gc, tn): pick empirically best TM (optimal) and TM=TN (square)
    results = {}   # (tn, gc) -> (optimal_alpha, square_alpha)
    for tn in TN_ALL:
        for gc in GC_VALS:
            tm_map = measured[(gc, tn)]
            if not tm_map or tn not in tm_map:
                continue
            optimal_alpha = min(tm_map.values())
            square_alpha  = tm_map[tn]              # TM = TN, directly measured
            results[(tn, gc)] = (optimal_alpha, square_alpha)

    # ── Chart 1: performance curves — optimal vs square ───────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))

    for tn in TN_ALL:
        color = COLORS_TN[tn]
        opt_ys    = [results[(tn, gc)][0] for gc in GC_VALS]
        square_ys = [results[(tn, gc)][1] for gc in GC_VALS]
        ax1.plot(GC_VALS, opt_ys,    color=color, lw=2.4, ls="-",  marker="o", ms=5,
                 label=f"$T_N = {tn}$  optimal", zorder=3)
        ax1.plot(GC_VALS, square_ys, color=color, lw=1.8, ls="--", marker="s", ms=5,
                 alpha=0.6, zorder=2)

    # legend proxies
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], color=COLORS_TN[tn], lw=2, label=f"$T_N = {tn}$")
               for tn in TN_ALL]
    handles += [
        Line2D([0], [0], color=MUTED, lw=2.4, ls="-",  label="optimal $T_M^*$"),
        Line2D([0], [0], color=MUTED, lw=1.8, ls="--", label="square  $T_M = T_N$"),
    ]
    ax1.legend(handles=handles, labelcolor=INK_MUT, fontsize=9, ncol=2, loc="upper left")
    ax1.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax1.set_ylabel("Performance cost  (cycles / output element)", fontsize=12, labelpad=6)
    ax1.set_title("Optimal asymmetric tiling vs square tiling", fontsize=13, pad=10)
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(50))

    # ── Chart 2: speedup % of optimal over square ─────────────────────────────
    for tn in TN_ALL:
        color = COLORS_TN[tn]
        speedup = [(results[(tn, gc)][1] - results[(tn, gc)][0]) / results[(tn, gc)][1] * 100
                   for gc in GC_VALS]
        ax2.plot(GC_VALS, speedup, color=color, lw=2.4, marker="o", ms=5,
                 label=f"$T_N = {tn}$", zorder=3)

    ax2.axhline(0, color=BASELINE, lw=1, ls="--", zorder=1)
    ax2.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax2.set_ylabel("Speedup over square tile (%)", fontsize=12, labelpad=6)
    ax2.set_title("Gain from asymmetric tile selection", fontsize=13, pad=10)
    ax2.xaxis.set_major_locator(ticker.MultipleLocator(50))
    ax2.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax2.legend(labelcolor=INK_MUT, loc="upper right", fontsize=10)

    fig.suptitle("L1-only  —  empirically measured performance (E8 sweep)",
                 fontsize=13, y=1.01)
    fig.tight_layout(pad=1.4)
    fig.savefig(OUT / "optimal_vs_square.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e8/optimal_vs_square.png")


# ─────────────────────────────────────────────────────────────────────────────
# E8 — globally best (TM*, TN*) per gc
# ─────────────────────────────────────────────────────────────────────────────

def plot_e8_best_shape():
    OUT = HERE / "e8-gc-boundary-sweep"
    data = json.load(open(OUT / "results.json"))
    MNK = 192 * 256 * 256

    measured = defaultdict(dict)   # gc -> (tm,tn) -> alpha
    for v in data.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if gc == 0:
            continue
        measured[gc][(tm, tn)] = v["metrics"]["cycles"] / MNK

    GC_VALS = sorted(measured)
    best_tm   = [min(measured[gc], key=lambda k: measured[gc][k])[0] for gc in GC_VALS]
    best_tn   = [min(measured[gc], key=lambda k: measured[gc][k])[1] for gc in GC_VALS]
    best_alpha = [measured[gc][min(measured[gc], key=lambda k: measured[gc][k])] for gc in GC_VALS]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.0, 7.0), sharex=True)

    # ── Panel 1: TM* and TN* step functions ───────────────────────────────────
    ax1.step(GC_VALS, best_tm, where="post", color=BLUE, lw=2.5, label="$T_M^*$", zorder=3)
    ax1.step(GC_VALS, best_tn, where="post", color=RED,  lw=2.5, label="$T_N^*$", zorder=3)
    ax1.scatter(GC_VALS, best_tm, color=BLUE, s=50, zorder=4, edgecolors="white", lw=0.7)
    ax1.scatter(GC_VALS, best_tn, color=RED,  s=50, zorder=4, edgecolors="white", lw=0.7)

    # annotate each regime with (TM, TN) labels at transitions
    prev = None
    for i, gc in enumerate(GC_VALS):
        pair = (best_tm[i], best_tn[i])
        if pair != prev:
            ax1.annotate(f"({best_tm[i]}, {best_tn[i]})",
                         xy=(gc, max(best_tm[i], best_tn[i])),
                         xytext=(gc, max(best_tm[i], best_tn[i]) + 8),
                         fontsize=8.5, color=INK_MUT, ha="left",
                         arrowprops=dict(arrowstyle="-", color=BASELINE, lw=0.8))
            prev = pair

    tile_vals = sorted({*best_tm, *best_tn})
    ax1.set_yticks(tile_vals)
    ax1.set_yticklabels([str(t) for t in tile_vals])
    ax1.set_ylabel("Tile dimension", fontsize=12, labelpad=6)
    ax1.set_title("Globally optimal tile shape $(T_M^*, T_N^*)$ vs $g_c$  —  L1-only",
                  fontsize=13, pad=10)
    ax1.legend(labelcolor=INK_MUT, loc="upper left")
    ax1.set_ylim(0, 115)

    # ── Panel 2: best α* achieved ─────────────────────────────────────────────
    ax2.plot(GC_VALS, best_alpha, color=BLUE, lw=2.4, marker="o", ms=6,
             zorder=3, label="optimal $(T_M^*, T_N^*)$")
    ax2.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax2.set_ylabel("Best $\\alpha^*$  (cycles / output element)", fontsize=12, labelpad=6)
    ax2.set_title("Best achievable performance per $g_c$", fontsize=13, pad=10)
    ax2.xaxis.set_major_locator(ticker.MultipleLocator(50))

    fig.tight_layout(pad=1.4)
    fig.savefig(OUT / "best_shape_per_gc.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e8/best_shape_per_gc.png")


# ─────────────────────────────────────────────────────────────────────────────
# FIFO optimal vs Memory-B square tile
# ─────────────────────────────────────────────────────────────────────────────

def plot_fifo_vs_mem_square():
    OUT = HERE / "e8-gc-boundary-sweep"
    data8  = json.load(open(OUT / "results.json"))
    data13 = json.load(open(HERE / "e13-fifo-vs-mem/results.json"))
    MNK = 192 * 256 * 256
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]

    # FIFO: best (TM,TN) globally at each gc (measured)
    fifo = defaultdict(dict)   # gc -> (tm,tn) -> alpha
    for v in data8.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if tm not in TM_ALL or tn not in TN_ALL:
            continue
        fifo[gc][(tm, tn)] = v["metrics"]["cycles"] / MNK

    GC_VALS = sorted(fifo)
    fifo_best = {gc: min(fifo[gc].values()) for gc in GC_VALS}
    fifo_best_tile = {gc: min(fifo[gc], key=lambda k: fifo[gc][k]) for gc in GC_VALS}

    # Memory-B: all tiles (4B, 4B symmetric)
    mem = {}   # (tm,tn) -> alpha
    for v in data13.values():
        ov = v["overrides"]
        mem[(ov["TILE_M"], ov["TILE_N"])] = v["metrics"]["cycles"] / MNK

    # Best square tile for Memory-B
    square_tiles = {(tm, tn): a for (tm, tn), a in mem.items() if tm == tn}
    mem_sq_best_tile, mem_sq_alpha = min(square_tiles.items(), key=lambda x: x[1])

    # Best overall tile for Memory-B (for reference)
    mem_best_tile, mem_best_alpha = min(mem.items(), key=lambda x: x[1])

    fig, ax = plt.subplots(figsize=(8.5, 5.2))

    # Memory-B reference lines (constant — no gc dependence)
    ax.axhline(mem_sq_alpha, color=RED, lw=2, ls="--", zorder=2,
               label=f"Memory-B  best square $T_M\\!=\\!T_N\\!=\\!{mem_sq_best_tile[0]}$  "
                     f"(α = {mem_sq_alpha:.2f})")
    ax.axhline(mem_best_alpha, color=RED, lw=1.2, ls=":", zorder=2, alpha=0.6,
               label=f"Memory-B  best asymmetric $({mem_best_tile[0]},\\,{mem_best_tile[1]})$  "
                     f"(α = {mem_best_alpha:.2f})")

    # FIFO line
    xs = list(GC_VALS)
    ys = [fifo_best[gc] for gc in xs]
    ax.plot(xs, ys, color=BLUE, lw=2.5, marker="o", ms=7, zorder=3,
            label="FIFO-B  optimal $(T_M^*, T_N^*)$ per $g_c$")

    # Crossover annotation
    crossover_gc = None
    for i in range(len(xs) - 1):
        if ys[i] <= mem_sq_alpha <= ys[i + 1]:
            t = (mem_sq_alpha - ys[i]) / (ys[i + 1] - ys[i])
            crossover_gc = xs[i] + t * (xs[i + 1] - xs[i])
            break
    if crossover_gc:
        ax.axvline(crossover_gc, color=MUTED, lw=1, ls=":", zorder=1)
        ax.text(crossover_gc + 6, mem_sq_alpha + 0.1,
                f"crossover ≈ $g_c$ = {crossover_gc:.0f}",
                color=MUTED, fontsize=10)

    # Label each FIFO point with its best tile
    prev_tile = None
    for gc, alpha in zip(xs, ys):
        tile = fifo_best_tile[gc]
        if tile != prev_tile:
            ax.annotate(f"({tile[0]},{tile[1]})", xy=(gc, alpha),
                        xytext=(gc, alpha - 0.18), fontsize=8,
                        color=BLUE, ha="center", va="top")
            prev_tile = tile

    ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax.set_ylabel("Performance cost  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title("FIFO-B (optimal tile) vs Memory-B (best square tile, 4B×4B)\n"
                 "L1-only  —  measured", fontsize=13, pad=10)
    ax.set_xlim(-10, 415)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(50))
    ax.legend(labelcolor=INK_MUT, loc="upper left", fontsize=10)

    fig.tight_layout(pad=1.4)
    fig.savefig(OUT / "fifo_vs_mem_square.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e8/fifo_vs_mem_square.png")


# ─────────────────────────────────────────────────────────────────────────────
# Pipelined FIFO vs Memory-B square tile (global optimal tile per gc)
# ─────────────────────────────────────────────────────────────────────────────

def plot_pipeline_vs_mem_square():
    OUT14 = HERE / "e14-pipelined-fifo-vs-mem"
    OUT8  = HERE / "e8-gc-boundary-sweep"
    OUT13 = HERE / "e13-fifo-vs-mem"
    data14 = json.load(open(OUT14 / "results.json"))
    data8  = json.load(open(OUT8  / "results.json"))
    data13 = json.load(open(OUT13 / "results.json"))
    MNK = 192 * 256 * 256
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]

    # Memory-B: best square tile
    mem = {(v["overrides"]["TILE_M"], v["overrides"]["TILE_N"]): v["metrics"]["cycles"] / MNK
           for v in data13.values()}
    square_tiles = {t: a for t, a in mem.items() if t[0] == t[1]}
    mem_sq_tile, mem_sq_alpha = min(square_tiles.items(), key=lambda x: x[1])

    # E8 calibration table (gc=0) — used for analytic extension
    alpha_table = defaultdict(dict)
    for v in data8.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] == 0:
            alpha_table[ov["TILE_M"]][ov["TILE_N"]] = v["metrics"]["cycles"] / MNK

    # Standard FIFO (N=0 / E8): measured up to gc=400, analytic beyond
    e8_measured = defaultdict(dict)
    for v in data8.values():
        ov = v["overrides"]
        gc, tm, tn = ov["PRNG_FIFO_GEN_COST"], ov["TILE_M"], ov["TILE_N"]
        if gc == 0 or tm not in TM_ALL or tn not in TN_ALL:
            continue
        e8_measured[gc][(tm, tn)] = v["metrics"]["cycles"] / MNK

    gc_std_measured = sorted(e8_measured)
    std_best = {gc: min(e8_measured[gc].values()) for gc in gc_std_measured}

    # Analytic extension for gc beyond E8 range
    for gc in [700, 1200, 2000]:
        scores = {(tm, tn): max(alpha_table[tm][tn], gc / tm)
                  for tm in TM_ALL for tn in TN_ALL if tn in alpha_table[tm]}
        std_best[gc] = min(scores.values())

    # Pipelined: N=2 and N=4 from E14
    e14_best = defaultdict(dict)   # N -> gc -> best_alpha
    for v in data14.values():
        ov = v["overrides"]
        N  = ov["PRNG_FIFO_NUM_PREFILL"]
        gc = ov["PRNG_FIFO_GEN_COST"]
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if N not in [2, 4] or tm not in TM_ALL or tn not in TN_ALL:
            continue
        key = (tm, tn)
        if key not in e14_best[N] or v["metrics"]["cycles"] / MNK < e14_best[N].get(gc, {}).get(key, 1e9):
            e14_best[N].setdefault(gc, {})[key] = v["metrics"]["cycles"] / MNK
    # collapse to best per gc
    pipe_best = {}
    for N in [2, 4]:
        pipe_best[N] = {gc: min(e14_best[N][gc].values()) for gc in e14_best[N]}

    COLORS = {"std": BLUE, 2: GREEN, 4: YELLOW}
    LABELS = {
        "std": "FIFO-B  $N=1$  (standard, measured/model)",
        2: "FIFO-B  $N=2$  (pipelined, measured)",
        4: "FIFO-B  $N=4$  (pipelined, measured)",
    }

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.axhline(mem_sq_alpha, color=RED, lw=2, ls="--", zorder=2,
               label=f"Memory-B  best square $T_M\\!=\\!T_N\\!=\\!{mem_sq_tile[0]}$  (α = {mem_sq_alpha:.2f})")

    # Standard N=1
    xs0 = sorted(std_best); ys0 = [std_best[gc] for gc in xs0]
    ax.plot(xs0, ys0, color=COLORS["std"], lw=2.4, marker="o", ms=6, zorder=5, label=LABELS["std"])

    # Pipelined N=2, N=4
    for N in [4, 2]:
        xs = sorted(pipe_best[N]); ys = [pipe_best[N][gc] for gc in xs]
        ax.plot(xs, ys, color=COLORS[N], lw=2.4, marker="o", ms=6, zorder=4, label=LABELS[N])
        for i in range(len(xs) - 1):
            if ys[i] <= mem_sq_alpha <= ys[i + 1]:
                t = (mem_sq_alpha - ys[i]) / (ys[i + 1] - ys[i])
                cx = xs[i] + t * (xs[i + 1] - xs[i])
                ax.axvline(cx, color=COLORS[N], lw=0.9, ls=":", alpha=0.5, zorder=1)
                ax.text(cx + 20, mem_sq_alpha + 0.15 * (N // 2),
                        f"$g_c \\approx {cx:.0f}$", color=COLORS[N], fontsize=9)
                break

    # Crossover for standard
    for i in range(len(xs0) - 1):
        if ys0[i] <= mem_sq_alpha <= ys0[i + 1]:
            t = (mem_sq_alpha - ys0[i]) / (ys0[i + 1] - ys0[i])
            cx = xs0[i] + t * (xs0[i + 1] - xs0[i])
            ax.axvline(cx, color=COLORS["std"], lw=0.9, ls=":", alpha=0.5, zorder=1)
            ax.text(cx + 20, mem_sq_alpha - 0.3,
                    f"$g_c \\approx {cx:.0f}$", color=COLORS["std"], fontsize=9)
            break

    ax.set_xlabel("B generation cost $g_c$  (cycles / element)", fontsize=12, labelpad=6)
    ax.set_ylabel("Performance cost  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title("Pipelined FIFO-B (optimal tile) vs Memory-B (best square, 4B×4B)\n"
                 "L1-only  —  E8 measured + analytic extension, E14 measured", fontsize=13, pad=10)
    ax.set_xlim(-30, 2100)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(200))
    ax.legend(labelcolor=INK_MUT, loc="upper left", fontsize=10)
    fig.tight_layout(pad=1.4)
    fig.savefig(OUT14 / "pipelined_vs_mem_square.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e14/pipelined_vs_mem_square.png")


# ─────────────────────────────────────────────────────────────────────────────
# C-tile cache footprint: FIFO-B vs Memory-B (side-by-side alpha heatmaps)
# ─────────────────────────────────────────────────────────────────────────────

def plot_ctile_footprint():
    OUT = HERE / "e13-fifo-vs-mem"
    data13 = json.load(open(OUT / "results.json"))
    data6  = json.load(open(HERE / "e6-tn-independence/results.json"))
    MNK = 192 * 256 * 256
    TM_ALL = [8, 12, 16, 24, 32, 48, 64, 96]
    TN_ALL = [4, 8, 16, 32, 64]

    # FIFO-B alpha table (gc=0) from E6
    fifo = defaultdict(dict)
    for v in data6.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if tm in TM_ALL and tn in TN_ALL:
            fifo[tm][tn] = v["metrics"]["cycles"] / (ov["A_HEIGHT_DIM"] * 256 * 256)

    # Memory-B alpha table from E13
    mem = defaultdict(dict)
    for v in data13.values():
        ov = v["overrides"]
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        mem[tm][tn] = v["metrics"]["cycles"] / MNK

    CLIFF = 6.0   # threshold above which we call it an eviction cliff

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    datasets = [("FIFO-B  (B streamed, no cache pressure from B)", fifo, BLUE),
                ("Memory-B  (B occupies L1, squeezes A and C)", mem, RED)]

    for ax, (title, table, accent) in zip(axes, datasets):
        Z = np.array([[table[tm].get(tn, np.nan) for tn in TN_ALL] for tm in TM_ALL])
        VMAX = 12.0
        Z_disp = np.clip(Z, 0, VMAX)

        im = ax.imshow(Z_disp, aspect="auto", cmap="YlOrRd",
                       vmin=3.1, vmax=VMAX, origin="upper")

        for i, tm in enumerate(TM_ALL):
            for j, tn in enumerate(TN_ALL):
                val = table[tm].get(tn, np.nan)
                if np.isnan(val):
                    continue
                is_cliff = val > CLIFF
                txt = f"{val:.1f}" if val >= 10 else f"{val:.2f}"
                color = "white" if is_cliff else INK
                weight = "bold" if is_cliff else "normal"
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=9, color=color, fontweight=weight)

        # Mark cliff boundary: outline cells where cliff starts
        for i, tm in enumerate(TM_ALL):
            for j, tn in enumerate(TN_ALL):
                val = table[tm].get(tn, np.nan)
                if not np.isnan(val) and val > CLIFF:
                    rect = plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                         fill=False, edgecolor=accent,
                                         lw=2.0, zorder=5)
                    ax.add_patch(rect)

        ax.set_xticks(range(len(TN_ALL))); ax.set_xticklabels([str(t) for t in TN_ALL], fontsize=11)
        ax.set_yticks(range(len(TM_ALL))); ax.set_yticklabels([str(t) for t in TM_ALL], fontsize=11)
        ax.set_xlabel("$T_N$", fontsize=13, labelpad=6)
        ax.set_ylabel("$T_M$", fontsize=13, labelpad=6)
        ax.set_title(title, fontsize=12, pad=8, color=accent)

    fig.colorbar(im, ax=axes[-1], fraction=0.046, pad=0.04, label="α  (cycles / output element)")
    fig.suptitle("C-tile eviction cliff: FIFO-B leaves more L1 space → cliff pushed to larger tiles\n"
                 "Outlined cells: eviction cliff (α > 6)",
                 fontsize=13, y=1.02)
    fig.tight_layout(pad=1.4)
    fig.savefig(OUT / "ctile_footprint.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ e13/ctile_footprint.png")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Plotting E3...")
    plot_e3()
    print("Plotting E4...")
    plot_e4()
    print("Plotting E6...")
    plot_e6()
    print("Plotting E8...")
    plot_e8()
    print("Plotting E8 validation...")
    plot_e8_validation()
    print("Plotting E13...")
    plot_e13()
    print("Plotting E14...")
    plot_e14()
    print("Plotting e-l1size-regime...")
    plot_l1size()
    print("\nDone.")
