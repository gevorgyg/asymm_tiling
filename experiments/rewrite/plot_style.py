"""Shared style for the report figures.

Categorical colors are the dataviz skill's validated palette, assigned in
fixed order (never cycled). Three of them are below 3:1 contrast on white,
so series also get distinct markers. Figures are kept minimal (no titles or
in-plot text, per the user): the report caption explains them.

Figures are saved as PNG (to look at) and SVG (for the report) in
experiments/rewrite/figures/<topic>/, one directory per topic (alpha, model,
dataflow, ...).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent / "figures"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

INK = "#0b0b0b"         # titles
INK_2 = "#52514e"       # labels, ticks, legend text
GRID = "#e1e0d9"
SURFACE = "#ffffff"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "mathtext.fontset": "cm",
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "legend.frameon": False,
    "legend.labelcolor": INK_2,
    "lines.linewidth": 2.0,
    "lines.markersize": 5,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


def series(i: int) -> dict:
    """Line style for categorical slot i (fixed order)."""
    return {"color": SERIES[i], "marker": MARKERS[i],
            "markeredgecolor": SURFACE, "markeredgewidth": 0.8}


def legend_above(ax, ncols: int) -> None:
    """Compact one-row legend above the plot area, so it never covers data.
    Figures carry no titles or annotations; the report caption explains them."""
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncols=ncols,
              fontsize=9, handlelength=1.6, columnspacing=1.2, borderaxespad=0)


def save(fig, topic: str, name: str) -> Path:
    """Save to figures/<topic>/<name>.png and .svg. Figures about the same
    idea share a topic directory."""
    out = FIG_DIR / topic
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png")
    fig.savefig(out / f"{name}.svg")
    plt.close(fig)
    return out / f"{name}.png"
