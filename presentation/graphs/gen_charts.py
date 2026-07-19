"""Generate presentation charts from experiment results.

Charts produced:
  1. alpha_vs_tm.png       — α(TM) curve (hockey stick), L1-only, gc=0
  2. fifo_vs_mem_gc.png    — FIFO optimal vs Memory-B as function of gen_cost
  3. fifo_adv_tn.png       — FIFO advantage % vs TN (bar chart)
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── Design system tokens (validated palette) ─────────────────────────────────
BLUE      = "#2a78d6"   # slot 1 — FIFO / main series
RED       = "#e34948"   # slot 6 — Memory-B (contrast 4.7:1; CVD ΔE 74.6)
SURFACE   = "#fcfcfb"
INK       = "#0b0b0b"
INK_MUT   = "#52514e"
MUTED     = "#898781"
GRID      = "#e1e0d9"
BASELINE  = "#c3c2b7"

# ── Global matplotlib style ──────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family":         "sans-serif",
    "font.sans-serif":     ["DejaVu Sans", "Liberation Sans", "Arial", "sans-serif"],
    "font.size":           11,
    "axes.facecolor":      SURFACE,
    "figure.facecolor":    SURFACE,
    "axes.edgecolor":      BASELINE,
    "axes.grid":           True,
    "grid.color":          GRID,
    "grid.linewidth":      0.8,
    "axes.spines.top":     False,
    "axes.spines.right":   False,
    "axes.spines.left":    True,
    "axes.spines.bottom":  True,
    "axes.labelcolor":     INK_MUT,
    "xtick.color":         MUTED,
    "ytick.color":         MUTED,
    "xtick.labelsize":     10,
    "ytick.labelsize":     10,
    "axes.titlesize":      12,
    "axes.titleweight":    "bold",
    "axes.titlecolor":     INK,
    "legend.frameon":      False,
    "legend.fontsize":     10,
    "lines.linewidth":     2.0,
    "lines.markersize":    7,
    "savefig.dpi":         150,
    "savefig.bbox":        "tight",
    "savefig.facecolor":   SURFACE,
})

OUT = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — α(TM): A-load cost per element, L1-only, gc=0, TN=32
# Source: E3-nol2 calibration
# Message: α is flat in the safe zone (TM 8–64), then cliffs at TM=96
# ─────────────────────────────────────────────────────────────────────────────

def chart_alpha_vs_tm():
    TM = [8, 12, 16, 24, 32, 48, 64, 96]

    # From E6-nol2, gc=0; L1=16384 B, A_P=B_P=C_P=4 B
    DATA = {
        4:  [3.3997, 3.3159, 6.0524, 6.0067, 5.9839, 5.9609, 5.9492, 5.9374],
        8:  [3.3973, 3.3146, 4.6403, 4.5966, 4.5747, 4.5527, 4.5415, 4.5302],
        16: [3.3963, 3.3139, 3.9343, 3.8916, 3.8701, 3.8486, 3.8377, 3.8266],
        32: [3.3958, 3.3133, 3.5811, 3.5387, 3.5174, 3.4959, 3.4849, 9.0329],
        64: [3.3957, 3.4378, 3.4041, 3.3617, 3.3403, 4.3896, 8.8731, 8.8756],
    }
    COLORS = {
        4:  "#2a78d6",
        8:  "#1baf7a",
        16: "#eda100",
        32: "#4a3aa7",
        64: "#e34948",
    }
    # index from which the C-tile eviction causes α to spike
    EVICT_IDX = {32: 7, 64: 5}   # TM=96 for TN=32; TM=48 for TN=64

    fig, ax = plt.subplots(figsize=(7.8, 5.0))

    for tn, alphas in DATA.items():
        color = COLORS[tn]
        ei = EVICT_IDX.get(tn, len(TM))
        # solid: safe zone
        ax.plot(TM[:ei], alphas[:ei], color=color, lw=2.2, marker="o", ms=6,
                zorder=3, label=f"$T_N = {tn}$")
        # dashed: eviction zone (overlap one point for continuity)
        if ei < len(TM):
            ax.plot(TM[ei-1:], alphas[ei-1:], color=color, lw=2.2, marker="o",
                    ms=6, ls="--", alpha=0.45, zorder=3)

    # Annotate the two eviction boundaries
    ax.annotate("C-tile eviction\n($T_N{=}64$, $T_M{\\geq}48$)",
                xy=(48, 4.39), xytext=(50, 6.5),
                arrowprops=dict(arrowstyle="-|>", color=COLORS[64], lw=1, alpha=0.8),
                fontsize=9.5, color=COLORS[64], ha="left")
    ax.annotate("C-tile eviction\n($T_N{=}32$, $T_M{=}96$)",
                xy=(96, 9.03), xytext=(70, 9.3),
                arrowprops=dict(arrowstyle="-|>", color=COLORS[32], lw=1, alpha=0.8),
                fontsize=9.5, color=COLORS[32], ha="right")

    ax.set_xlabel("Tile-M dimension ($T_M$)", labelpad=8, fontsize=12)
    ax.set_ylabel("α  (cycles / output element)", labelpad=8, fontsize=12)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c = 0$  —  L1-only", fontsize=13, pad=10)
    ax.set_xticks(TM)
    ax.set_xticklabels([str(t) for t in TM], fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_ylim(2.8, 10.5)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(loc="upper left", labelcolor=INK_MUT, fontsize=11)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_vs_tm.png")
    plt.close(fig)
    print("  ✓ alpha_vs_tm.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — FIFO vs Memory-B: α* vs gen_cost (TN=32, L1-only)
# Source: E8-nol2 (FIFO best per gc) + E13-nol2 (Memory-B α)
# Message: FIFO beats memory up to gc ≈ 200, then memory wins
# ─────────────────────────────────────────────────────────────────────────────

def chart_fifo_vs_mem_gc():
    GC = [0, 15, 30, 38, 42, 47, 50, 52, 57, 68, 74, 100, 150, 250, 400]
    FIFO_ALPHA = [
        3.3133, 3.3155, 3.3179, 3.3192,   # TM*=12 regime
        3.4861, 3.4862, 3.4863, 3.4864, 3.4865, 3.4869, 3.4871,  # TM*=64 regime
        3.4879, 3.4894,                    # TM*=64 plateau
        3.9931, 6.3368,                    # B-bound rise
    ]
    MEM_ALPHA = 3.7540   # Memory-B best: TM=64, TN=32

    # Crossover interpolation between gc=150 (α=3.489) and gc=250 (α=3.993)
    gc_star = 150 + (MEM_ALPHA - 3.4894) / (3.9931 - 3.4894) * (250 - 150)

    fig, ax = plt.subplots(figsize=(6.5, 3.8))

    # Memory-B: horizontal dashed red line
    ax.axhline(MEM_ALPHA, color=RED, lw=2, ls="--", zorder=2, label="Memory-B  (α = 3.754)")
    # Label at right end
    ax.text(405, MEM_ALPHA + 0.06, "Memory-B", color=RED, fontsize=9,
            ha="left", va="bottom")

    # FIFO: solid blue line
    ax.plot(GC, FIFO_ALPHA, color=BLUE, lw=2, marker="o", ms=6,
            zorder=3, label="FIFO-B (optimal TM*)")

    # Annotate TM* regime change
    ax.annotate("TM* shifts\n12 → 64", xy=(42, 3.486),
                xytext=(65, 3.62),
                arrowprops=dict(arrowstyle="-|>", color=INK_MUT, lw=1),
                fontsize=8.5, color=INK_MUT, ha="left")

    # Crossover marker
    ax.axvline(gc_star, color=MUTED, lw=1.1, ls=":", zorder=1)
    ax.text(gc_star + 4, 5.2, f"gc* ≈ {gc_star:.0f}", color=MUTED,
            fontsize=9, va="top")

    # Shade FIFO-wins region
    ax.axvspan(0, gc_star, alpha=0.06, color=BLUE, zorder=0)
    ax.text(20, 6.0, "FIFO wins", color=BLUE, fontsize=9, alpha=0.7)
    ax.axvspan(gc_star, 410, alpha=0.06, color=RED, zorder=0)
    ax.text(280, 6.0, "Memory\nwins", color=RED, fontsize=9, alpha=0.7)

    ax.set_xlabel("B generation cost  gc  (cycles / element)", labelpad=6)
    ax.set_ylabel("α* = T / MNK  (cycles per element)", labelpad=6)
    ax.set_title("FIFO-B vs Memory-B  —  L1-only, TN = 32")
    ax.set_xlim(-5, 420)
    ax.set_ylim(2.9, 7.0)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(50))

    ax.legend(loc="upper left", labelcolor=INK_MUT)
    fig.tight_layout()
    fig.savefig(OUT / "fifo_vs_mem_gc.png")
    plt.close(fig)
    print("  ✓ fifo_vs_mem_gc.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 3 — FIFO advantage % vs TN (bar chart, gc=0, L1-only)
# Source: E8-nol2 (FIFO gc=0) + E13-nol2 (Memory-B best)
# Message: small TN → much larger speedup (stride effect)
# ─────────────────────────────────────────────────────────────────────────────

def chart_fifo_adv_tn():
    TN        = [4,    8,    16,   32,   64   ]
    MEM_BEST  = [7.3834, 5.2428, 4.1725, 3.7540, 3.6915]
    FIFO_GC0  = [3.3159, 3.3146, 3.3139, 3.3133, 3.3403]
    ADV_PCT   = [(m - f) / m * 100 for m, f in zip(MEM_BEST, FIFO_GC0)]

    x = np.arange(len(TN))
    fig, ax = plt.subplots(figsize=(5.5, 3.8))

    bars = ax.bar(x, ADV_PCT, color=BLUE, width=0.55, zorder=3)

    # Direct labels above each bar
    for bar, pct in zip(bars, ADV_PCT):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.8,
                f"{pct:.1f}%", ha="center", va="bottom",
                fontsize=10, color=INK, fontweight="bold")

    # Reference line at 0
    ax.axhline(0, color=BASELINE, lw=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels([f"TN = {t}" for t in TN])
    ax.set_ylabel("FIFO speedup over Memory-B (%)", labelpad=6)
    ax.set_title("FIFO-B advantage vs tile width  —  L1-only, gc = 0")
    ax.set_ylim(0, 65)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(10))

    # Annotation explaining the stride effect at TN=4
    ax.annotate("B stride: 4 cache lines\nper 4×4 register block →\nfull L1 pressure at TN=4",
                xy=(0, ADV_PCT[0]),
                xytext=(1.0, 58),
                arrowprops=dict(arrowstyle="-|>", color=INK_MUT, lw=1),
                fontsize=8.5, color=INK_MUT, ha="left", va="top")

    fig.tight_layout()
    fig.savefig(OUT / "fifo_adv_tn.png")
    plt.close(fig)
    print("  ✓ fifo_adv_tn.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 4 — Model intuition: α(TM) vs gc/TM for two gc values
# Source: E3-nol2 calibration; gc/TM is analytical
# Message: α is the hockey stick; gc/TM is a hyperbola; T_M* is their crossing
# ─────────────────────────────────────────────────────────────────────────────

def chart_model_intuition():
    TM    = [4,     8,     12,    16,    24,    32,    48,    64,    96,    128  ]
    ALPHA = [3.646, 3.396, 3.313, 3.581, 3.539, 3.518, 3.496, 3.485, 9.033, 9.051]

    GC_VALS = [50, 200]
    GC_COLORS  = ["#2a78d6", "#1baf7a"]
    GC_LABELS  = ["$g_c = 50$", "$g_c = 200$"]

    TM_dense = np.array(TM, dtype=float)

    fig, ax = plt.subplots(figsize=(7.8, 5.0))

    # ── α(TM): red hockey stick ───────────────────────────────────────────────
    tm_safe,  al_safe  = zip(*[(tm, a) for tm, a in zip(TM, ALPHA) if tm <= 64])
    tm_cliff, al_cliff = zip(*[(tm, a) for tm, a in zip(TM, ALPHA) if tm >= 64])
    ax.plot(tm_safe,  al_safe,
            color=RED, lw=2.5, marker="o", ms=7, zorder=4,
            label=r"$\alpha(T_M,\;T_N{=}32)$  (measured)")
    ax.plot(tm_cliff, al_cliff,
            color=RED, lw=2.5, marker="o", ms=7, zorder=4, ls="--", alpha=0.45)

    # C-tile eviction boundary — push text up so it doesn't crowd the cliff
    ax.axvline(64, color=RED, lw=1.2, ls=":", zorder=2, alpha=0.5)
    ax.text(67, 10.2,
            "C-tile eviction\n$T_M{\\times}T_N{\\times}C_P > L1$",
            color=RED, fontsize=10, va="top", alpha=0.85, linespacing=1.5)

    # ── gc/TM hyperbolas + max envelope ──────────────────────────────────────
    alpha_arr = np.array(ALPHA)
    for gc, color, label in zip(GC_VALS, GC_COLORS, GC_LABELS):
        gc_over_tm = gc / TM_dense
        max_curve  = np.maximum(alpha_arr, gc_over_tm)

        ax.plot(TM_dense, gc_over_tm, color=color, lw=1.4, ls=":",
                zorder=2, alpha=0.55)
        ax.plot(TM_dense, max_curve, color=color, lw=2.5,
                zorder=3, label=f"max(α, {label.strip('$')}$/T_M$)")

        diff = alpha_arr - gc_over_tm
        for k in range(len(diff) - 1):
            if diff[k] * diff[k+1] <= 0 and TM[k] <= 64:
                t0, t1 = TM[k], TM[k+1]
                d0, d1 = diff[k], diff[k+1]
                tm_star = t0 - d0 * (t1 - t0) / (d1 - d0)
                cost_star = np.interp(tm_star, TM_dense, alpha_arr)
                ax.axvline(tm_star, color=color, lw=1.2, ls="--", alpha=0.45, zorder=1)
                ax.annotate(f"$T_M^*\\!\\approx\\!{tm_star:.0f}$",
                            xy=(tm_star, cost_star),
                            xytext=(tm_star + 5, cost_star + 1.0),
                            arrowprops=dict(arrowstyle="-|>", color=color,
                                            lw=1.0, alpha=0.8),
                            fontsize=11, color=color, ha="left")
                break

    ax.set_xlabel("Tile-M dimension ($T_M$)", labelpad=8, fontsize=12)
    ax.set_ylabel("cycles per output element", labelpad=8, fontsize=12)
    ax.set_title(r"$T = MNK \times \max(\alpha(T_M),\; g_c/T_M)$  —  L1-only, $T_N = 32$",
                 fontsize=13, pad=10)
    # Drop 128 from x-ticks to avoid crowding; leave gap between 12 and 16
    ax.set_xticks(TM)
    ax.set_xticklabels([str(t) for t in TM], fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_ylim(0, 12)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax.legend(loc="upper right", labelcolor=INK_MUT, fontsize=11)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "model_intuition.png")
    plt.close(fig)
    print("  ✓ model_intuition.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 5 — α(TM, TN): TN independence in L1 regime, 1/TN slope in DRAM regime
# Source: E6-nol2  (gc=0 entries, M=192, N=K=256)
# Message: L1 tiles (TM=8,12) are flat; DRAM tiles (TM=24,32) slope with 1/TN
# ─────────────────────────────────────────────────────────────────────────────

def chart_tn_dependence():
    TN = [4, 8, 16, 32, 64]

    # From E6-nol2 results.json, gc=0
    DATA = {
        8:  [3.3997, 3.3973, 3.3963, 3.3958, 3.3957],  # L1 tile
        12: [3.3159, 3.3146, 3.3139, 3.3133, None    ],  # L1 tile (TN=64 overflow)
        24: [6.0067, 4.5966, 3.8916, 3.5387, 3.3617  ],  # DRAM tile
        32: [5.9839, 4.5747, 3.8701, 3.5174, 3.3403  ],  # DRAM tile
    }

    # L1: blue family;  DRAM: red family
    STYLES = {
        8:  dict(color="#2a78d6", ls="-",  label=r"$T_M=8$   (L1 tile)"),
        12: dict(color="#1c5cab", ls="--", label=r"$T_M=12$  (L1 tile)"),
        24: dict(color="#e34948", ls="-",  label=r"$T_M=24$  (DRAM tile)"),
        32: dict(color="#b02b2a", ls="--", label=r"$T_M=32$  (DRAM tile)"),
    }

    fig, ax = plt.subplots(figsize=(6.0, 3.6))

    for tm, alphas in DATA.items():
        sty = STYLES[tm]
        # filter out None (overflow)
        xs = [tn for tn, a in zip(TN, alphas) if a is not None]
        ys = [a  for a           in alphas     if a is not None]
        ax.plot(xs, ys, color=sty["color"], ls=sty["ls"],
                lw=2, marker="o", ms=6, zorder=3, label=sty["label"])

    # Reference line: flat at TM=8 level
    ax.axhline(3.396, color=MUTED, lw=0.8, ls=":", zorder=1)
    ax.text(65, 3.30, "L1 baseline ≈ 3.4", color=MUTED, fontsize=8, ha="right")

    # Shade regions
    ax.text(7, 5.5, "DRAM tiles\n(1/TN slope)", color="#e34948",
            fontsize=9, ha="left", va="top")
    ax.text(7, 3.58, "L1 tiles\n(flat)", color="#2a78d6",
            fontsize=9, ha="left", va="bottom")

    ax.set_xlabel("Tile-N dimension ($T_N$)", labelpad=6)
    ax.set_ylabel("α  (cycles / output element)", labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ at $g_c=0$  —  L1-only")
    ax.set_xticks(TN)
    ax.set_xticklabels([str(t) for t in TN])
    ax.set_ylim(2.8, 7.0)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(loc="upper right", labelcolor=INK_MUT, fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT / "tn_dependence.png")
    plt.close(fig)
    print("  ✓ tn_dependence.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 6 — TM* prediction accuracy: 4 methods compared
# Source: E8-nol2 (theoretical), E11 (2-param), E12 (3-param), calibrated
# Message: regression substantially outperforms theory
# ─────────────────────────────────────────────────────────────────────────────

def chart_tm_star_accuracy():
    # Regression accuracy: 3-param formula α = a + b/TN + c·TN
    # L1-only: calibrated 70/70=100%, regression 41/70=59%  (E8-nol2)
    # L2 hier: calibrated 65/70=93%,  regression 55/70=79%  (E12)
    groups = [
        ("L2 hierarchy",  93,  79,  "#e1e0d9", BLUE),
        ("L1-only",      100,  59,  "#e1e0d9", RED),
    ]

    fig, ax = plt.subplots(figsize=(5.5, 3.2))

    bar_h = 0.32
    gap   = 0.9
    yticks, ylabels = [], []

    for i, (label, calib_pct, reg_pct, calib_col, reg_col) in enumerate(groups):
        base = i * gap
        # calibrated bar (background reference)
        ax.barh(base + bar_h/2 + bar_h*0.6, calib_pct, height=bar_h,
                color=calib_col, zorder=2, label=("Calibrated (upper bound)" if i==0 else None))
        ax.text(calib_pct + 1, base + bar_h/2 + bar_h*0.6,
                f"{calib_pct}%", va="center", ha="left", fontsize=10,
                color=MUTED, fontstyle="italic")
        # regression bar
        ax.barh(base, reg_pct, height=bar_h, color=reg_col, zorder=3,
                label=("Regression formula" if i==0 else None))
        ax.text(reg_pct + 1, base,
                f"{reg_pct}%", va="center", ha="left", fontsize=11,
                fontweight="bold", color=INK)

        yticks.append(base + bar_h*0.8)
        ylabels.append(label)

    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=11)
    ax.set_xlabel("$T_M^*$ prediction accuracy  (%)", labelpad=6, fontsize=11)
    ax.set_title("Regression accuracy — 70 $(g_c, T_N)$ test cases", pad=8, fontsize=12)
    ax.set_xlim(0, 114)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.xaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.invert_yaxis()
    ax.legend(loc="lower right", labelcolor=INK_MUT, fontsize=9, frameon=False)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "tm_star_acc.png")
    plt.close(fig)
    print("  ✓ tm_star_acc.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 7 — TM*(gc) trajectory per TN — calibrated table predictions
# Source: E8-nol2 predictor accuracy table
# Message: calibrated table gets 70/70 right; TM* shifts right as gc increases,
#          and the transition is sharper for larger TN
# ─────────────────────────────────────────────────────────────────────────────

def chart_tm_star_trajectory():
    GC = [15, 30, 38, 42, 47, 52, 57, 68, 74, 100, 250, 400]

    # Empirical TM* from E8-nol2 (= calibrated prediction, 70/70 match)
    TM_STAR = {
        4:  [12, 12, 12, 12, 12, 12, 12, 12, 96, 96, 96, 96],
        8:  [12, 12, 12, 12, 12, 12, 96, 96, 96, 96, 96, 96],
        16: [12, 12, 12, 12, 96, 96, 96, 96, 96, 96, 96, 96],
        32: [12, 12, 12, 64, 64, 64, 64, 64, 64, 64, 64, 64],
        64: [32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32],
    }
    COLORS = {
        4:  "#2a78d6",
        8:  "#1baf7a",
        16: "#eda100",
        32: "#4a3aa7",
        64: "#e34948",
    }

    fig, ax = plt.subplots(figsize=(8.0, 4.8))

    for tn, tm_vals in TM_STAR.items():
        ax.step(GC, tm_vals, where="post", color=COLORS[tn], lw=2.5,
                label=f"$T_N = {tn}$", zorder=3)
        ax.scatter(GC, tm_vals, color=COLORS[tn], s=40, zorder=4)

    # symlog: linear for gc ≤ 80, logarithmic beyond → spreads out the busy region
    ax.set_xscale("symlog", linthresh=80, linscale=0.8)

    # Clean tick labels aligned to interesting values
    xticks = [0, 20, 40, 60, 80, 150, 400]
    ax.set_xticks(xticks)
    ax.set_xticklabels([str(v) for v in xticks], fontsize=11)
    ax.xaxis.set_minor_locator(ticker.NullLocator())   # suppress symlog minor ticks

    ax.set_yticks([12, 32, 64, 96])
    ax.set_yticklabels(["12", "32", "64", "96"], fontsize=11)
    ax.set_ylim(4, 115)
    ax.set_xlim(0, 430)

    # Shade the "linear" region lightly so readers see the scale change
    ax.axvspan(0, 80, alpha=0.04, color=INK, zorder=0)

    ax.set_xlabel("B generation cost  $g_c$  (cycles / element)", labelpad=8, fontsize=12)
    ax.set_ylabel("Optimal $T_M^*$", labelpad=8, fontsize=12)
    ax.set_title(r"Calibrated $T_M^*$ vs $g_c$  —  L1-only", fontsize=13, pad=10)

    # Legend outside to the right — avoids the crowded transition region
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
              labelcolor=INK_MUT, fontsize=11, frameon=False)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "tm_star_trajectory.png", bbox_inches="tight")
    plt.close(fig)
    print("  ✓ tm_star_trajectory.png")


EXP = Path(__file__).parent.parent.parent / "experiments/v5-results/math-model-no-l2"


# ─────────────────────────────────────────────────────────────────────────────
# Chart 8 — α(TM, TN) heatmap: full 8×5 surface at gc=0, L1-only
# Source: E6-nol2
# ─────────────────────────────────────────────────────────────────────────────

def chart_alpha_heatmap():
    import json
    TM = [8, 12, 16, 24, 32, 48, 64, 96]
    TN = [4, 8, 16, 32, 64]

    raw = json.load(open(EXP / "e6-tn-independence/results.json"))
    table = {tm: {} for tm in TM}
    for v in raw.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0:
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        if tm in TM and tn in TN:
            table[tm][tn] = v["metrics"]["cycles"] / (ov["A_HEIGHT_DIM"] * 256 * 256)

    # build matrix (rows=TM, cols=TN); cap eviction values for color scale
    Z     = np.array([[table[tm].get(tn, np.nan) for tn in TN] for tm in TM])
    Z_cap = np.clip(Z, 0, 7.0)   # cap at 7 so eviction cells don't crush the scale

    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    im = ax.imshow(Z_cap, aspect="auto", cmap="YlOrRd", vmin=3.1, vmax=7.0,
                   origin="upper")

    # annotate each cell
    for i, tm in enumerate(TM):
        for j, tn in enumerate(TN):
            val = table[tm].get(tn, np.nan)
            if np.isnan(val):
                txt = "—"
            elif val > 7.0:
                txt = f"**{val:.1f}**"
            else:
                txt = f"{val:.2f}"
            color = "white" if (val > 5.5 or val > 7.0) else INK
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=9, color=color, fontweight="bold" if val > 7.0 else "normal")

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("α  (cycles / output element)", fontsize=11)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.text(1.5, 7.1, "eviction\n(>7)", transform=cbar.ax.get_yaxis_transform(),
                 ha="center", va="bottom", fontsize=8, color=INK_MUT)

    ax.set_xticks(range(len(TN)))
    ax.set_xticklabels([str(t) for t in TN], fontsize=11)
    ax.set_yticks(range(len(TM)))
    ax.set_yticklabels([str(t) for t in TM], fontsize=11)
    ax.set_xlabel("$T_N$", fontsize=13, labelpad=6)
    ax.set_ylabel("$T_M$", fontsize=13, labelpad=6)
    ax.set_title(r"$\alpha(T_M, T_N)$ surface at $g_c = 0$  —  L1-only", fontsize=13, pad=10)

    # Draw a line at the regime boundary (between TM=12 and TM=16)
    ax.axhline(1.5, color=BLUE, lw=1.5, ls="--", alpha=0.7)
    ax.text(len(TN) - 0.45, 1.35, "L1/DRAM boundary", color=BLUE,
            fontsize=8.5, ha="right", va="bottom")

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "alpha_heatmap.png")
    plt.close(fig)
    print("  ✓ alpha_heatmap.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 9 — FIFO-B vs Memory-B: side-by-side α per TN (absolute values)
# Source: E13-nol2 (Memory-B) + E8-nol2 gc=0 (FIFO-B)
# ─────────────────────────────────────────────────────────────────────────────

def chart_fifo_vs_mem_tn():
    TN       = [4,    8,    16,   32,   64   ]
    MEM_BEST = [7.3834, 5.2428, 4.1725, 3.7540, 3.6915]
    FIFO_GC0 = [3.3159, 3.3146, 3.3139, 3.3133, 3.3403]
    ADV_PCT  = [(m - f) / m * 100 for m, f in zip(MEM_BEST, FIFO_GC0)]

    x  = np.arange(len(TN))
    w  = 0.35
    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    bars_m = ax.bar(x - w/2, MEM_BEST, width=w, color=RED,   label="Memory-B (optimal $T_M^*$)", zorder=3)
    bars_f = ax.bar(x + w/2, FIFO_GC0, width=w, color=BLUE,  label="FIFO-B  ($g_c = 0$, optimal $T_M^*$)", zorder=3)

    # advantage label between bars
    for xi, (m, f, adv) in enumerate(zip(MEM_BEST, FIFO_GC0, ADV_PCT)):
        ax.text(xi, max(m, f) + 0.15, f"−{adv:.0f}%",
                ha="center", va="bottom", fontsize=10, color=INK,
                fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"$T_N = {t}$" for t in TN], fontsize=11)
    ax.set_ylabel("α*  (cycles / output element)", fontsize=12, labelpad=6)
    ax.set_title("FIFO-B vs Memory-B  —  L1-only, $g_c = 0$", fontsize=13, pad=10)
    ax.set_ylim(0, 9.5)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.tick_params(axis="y", labelsize=11)
    ax.legend(fontsize=11, labelcolor=INK_MUT, loc="upper right")
    ax.axhline(0, color=BASELINE, lw=0.8)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "fifo_vs_mem_tn.png")
    plt.close(fig)
    print("  ✓ fifo_vs_mem_tn.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 10 — Pipelining: best α vs gc for N=1,2,4 pipelined FIFO, TN=32
# Source: E14-nol2 (pipelined) + E8-nol2 (std) + E13-nol2 (Memory-B)
# ─────────────────────────────────────────────────────────────────────────────

def chart_pipelining():
    import json
    # Pipelined FIFO (E14): best α per (N, gc) at TN=32
    raw14 = json.load(open(EXP / "e14-pipelined-fifo-vs-mem/results.json"))
    MNK = 192 * 256 * 256
    from collections import defaultdict
    pipe = defaultdict(list)   # (prefill, gc) -> [alpha values]
    for v in raw14.values():
        ov = v["overrides"]
        if ov["TILE_N"] != 32:
            continue
        pipe[(ov["PRNG_FIFO_NUM_PREFILL"], ov["PRNG_FIFO_GEN_COST"])].append(
            v["metrics"]["cycles"] / MNK)

    GC14 = sorted({gc for _, gc in pipe})
    PREFILLS = [1, 2, 4]
    PIPE_COLORS = {1: "#2a78d6", 2: "#1baf7a", 4: "#eda100"}

    # Standard (non-pipelined) FIFO from E8-nol2, TN=32
    STD_GC    = [0,  15,   30,   38,   42,    47,    50,    52,    57,    68,    74,   100,    150,    250,   400]
    STD_ALPHA = [3.3133, 3.3155, 3.3179, 3.3192, 3.4861, 3.4862, 3.4863, 3.4864, 3.4865, 3.4869, 3.4871, 3.4879, 3.4894, 3.9931, 6.3368]
    MEM_ALPHA = 3.7540   # Memory-B at TN=32, TM*=64

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    # Memory-B baseline
    ax.axhline(MEM_ALPHA, color=RED, lw=2, ls="--", zorder=2, label="Memory-B")
    ax.text(2050, MEM_ALPHA + 0.08, "Memory-B", color=RED, fontsize=10, va="bottom", ha="left")

    # Standard FIFO (up to gc=400)
    ax.plot(STD_GC, STD_ALPHA, color=MUTED, lw=1.8, ls=":", marker="o", ms=5,
            zorder=3, label="FIFO-B  standard (N=1 tile)")

    # Pipelined FIFO
    for pf in PREFILLS:
        xs = sorted(gc for _, gc in pipe if _ == pf)
        ys = [min(pipe[(pf, gc)]) for gc in xs]
        ax.plot(xs, ys, color=PIPE_COLORS[pf], lw=2.2, marker="o", ms=6,
                zorder=4, label=f"FIFO-B  pipelined  $N={pf}$")

    # Shade FIFO-wins region (up to Memory-B line for N=4)
    ax.axvspan(0, 700, alpha=0.04, color=BLUE, zorder=0)

    ax.set_xlabel("B generation cost  $g_c$  (cycles / element)", labelpad=8, fontsize=12)
    ax.set_ylabel("α*  (cycles / output element)", labelpad=8, fontsize=12)
    ax.set_title(r"Pipelined FIFO-B vs Memory-B  —  L1-only, $T_N = 32$", fontsize=13, pad=10)
    ax.set_xlim(-30, 2100)
    ax.set_ylim(2.9, 12)
    ax.set_xticks([0, 250, 500, 750, 1000, 1250, 1500, 1750, 2000])
    ax.tick_params(labelsize=11)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(fontsize=11, labelcolor=INK_MUT, loc="upper left")

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "pipelining_gc.png")
    plt.close(fig)
    print("  ✓ pipelining_gc.png")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 11 — L1-size regime sweep: α(TM) shifts right with L1 size (TN=32)
# Source: e-l1size-regime
# ─────────────────────────────────────────────────────────────────────────────

def chart_l1size_regime():
    import json
    raw = json.load(open(EXP / "e-l1size-regime/results.json"))
    TM  = [8, 12, 16, 24, 32, 48, 64, 96]
    L1S = [8192, 16384, 32768, 65536]
    L1_LABELS = {8192: "8 KB", 16384: "16 KB", 32768: "32 KB", 65536: "64 KB"}
    COLORS_L1 = {8192: RED, 16384: BLUE, 32768: "#1baf7a", 65536: "#eda100"}

    table = {l1: {} for l1 in L1S}
    for v in raw.values():
        ov = v["overrides"]
        if ov["PRNG_FIFO_GEN_COST"] != 0 or ov["TILE_N"] != 32:
            continue
        l1, tm = ov["L1_SIZE_BYTES"], ov["TILE_M"]
        if l1 in L1S and tm in TM:
            table[l1][tm] = v["metrics"]["cycles"] / (ov["A_HEIGHT_DIM"] * 256 * 256)

    # L1 boundary TM_L1 = L1 / (256×4) = L1/1024
    L1_BOUNDARY = {l1: l1 // 1024 for l1 in L1S}

    fig, ax = plt.subplots(figsize=(7.5, 5.0))

    for l1 in L1S:
        xs = [tm for tm in TM if table[l1].get(tm)]
        ys = [table[l1][tm] for tm in xs]
        # cap eviction values for display
        ys_plot = [min(y, 10.5) for y in ys]
        ax.plot(xs, ys_plot, color=COLORS_L1[l1], lw=2.2, marker="o", ms=6,
                zorder=3, label=f"L1 = {L1_LABELS[l1]}")
        # vertical boundary line
        bnd = L1_BOUNDARY[l1]
        if bnd in TM or bnd < max(TM):
            ax.axvline(bnd, color=COLORS_L1[l1], lw=1, ls=":", alpha=0.5, zorder=1)

    ax.set_xlabel("Tile-M dimension ($T_M$)", labelpad=8, fontsize=12)
    ax.set_ylabel("α  (cycles / output element)", labelpad=8, fontsize=12)
    ax.set_title(r"$\alpha(T_M)$ at $g_c = 0$, $T_N = 32$  — regime boundary shifts with L1",
                 fontsize=13, pad=10)
    ax.set_xticks(TM)
    ax.set_xticklabels([str(t) for t in TM], fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_ylim(2.8, 11)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.legend(fontsize=11, labelcolor=INK_MUT, loc="upper left")
    ax.text(0.98, 0.97, "Dashed verticals: L1/DRAM boundary per L1 size",
            transform=ax.transAxes, ha="right", va="top", fontsize=9, color=MUTED)

    fig.tight_layout(pad=1.2)
    fig.savefig(OUT / "l1size_regime.png")
    plt.close(fig)
    print("  ✓ l1size_regime.png")


if __name__ == "__main__":
    print("Generating presentation charts...")
    chart_alpha_vs_tm()
    chart_fifo_vs_mem_gc()
    chart_fifo_adv_tn()
    chart_model_intuition()
    chart_tn_dependence()
    chart_tm_star_accuracy()
    chart_tm_star_trajectory()
    print("Generating experiment result charts...")
    chart_alpha_heatmap()
    chart_fifo_vs_mem_tn()
    chart_pipelining()
    chart_l1size_regime()
    print("Done. Output in", OUT)
