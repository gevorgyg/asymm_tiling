"""shared plotting helpers; matplotlib is optional (returns None if missing)"""

from pathlib import Path
from typing import Mapping, Optional, Sequence


def _bytes(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n // (1024 * 1024)}M"
    if n >= 1024:
        return f"{n // 1024}K"
    return f"{n}"


def summarize_config(overrides: Mapping[str, object], *,
                     extras: Mapping[str, object] = {}) -> str:
    """One-line summary of matrix + cache geometry for plot titles/captions.

    Skips fields that aren't present so callers can pass partial overrides.
    Pass `extras` (e.g. {"ρ": 0.25, "Tile": "8x32x64"}) to add sweep-cell info.
    """
    parts: list[str] = []
    if all(k in overrides for k in ("A_HEIGHT_DIM", "A_WIDTH_DIM", "B_WIDTH_DIM")):
        parts.append(f"m×n×k={overrides['A_HEIGHT_DIM']}×{overrides['B_WIDTH_DIM']}×{overrides['A_WIDTH_DIM']}")
    if all(k in overrides for k in ("A_PRECISION_BYTES", "B_PRECISION_BYTES")):
        parts.append(f"A/B={overrides['A_PRECISION_BYTES']}/{overrides['B_PRECISION_BYTES']}B")
    if all(k in overrides for k in ("L1_SIZE_BYTES", "L1_LINE_SIZE_BYTES", "L1_ASSOC")):
        pol = overrides.get("L1_REPLACEMENT_POLICY", "")
        parts.append(
            f"L1={_bytes(int(overrides['L1_SIZE_BYTES']))}/"
            f"{int(overrides['L1_LINE_SIZE_BYTES'])}B/"
            f"{int(overrides['L1_ASSOC'])}w"
            + (f" {pol}" if pol else "")
        )
    if all(k in overrides for k in ("L2_SIZE_BYTES", "L2_LINE_SIZE_BYTES", "L2_ASSOC")):
        pol = overrides.get("L2_REPLACEMENT_POLICY", "")
        parts.append(
            f"L2={_bytes(int(overrides['L2_SIZE_BYTES']))}/"
            f"{int(overrides['L2_LINE_SIZE_BYTES'])}B/"
            f"{int(overrides['L2_ASSOC'])}w"
            + (f" {pol}" if pol else "")
        )
    if all(k in overrides for k in ("REG_M", "REG_N", "REG_K")):
        parts.append(f"reg={overrides['REG_M']}×{overrides['REG_N']}×{overrides['REG_K']}")
    parts.extend(f"{k}={v}" for k, v in extras.items())
    return ", ".join(parts)


def describe_changes(overrides: Mapping[str, object], default_text: str, *,
                     extras: Mapping[str, object] = {}) -> str:
    """Caption line listing only what differs from default.config.

    Byte-valued keys are humanized (16384 -> 16K). Wraps at ~100 chars so it
    stays readable as a plot subtitle.
    """
    from .config import changed_from_default
    changed = changed_from_default(overrides, default_text)
    parts = []
    for k in sorted(changed):
        v = changed[k]
        if k.endswith("_BYTES") and str(v).isdigit():
            v = _bytes(int(v))
        parts.append(f"{k}={v}")
    parts.extend(f"{k}={v}" for k, v in extras.items())

    lines: list[str] = [""]
    for p in parts:
        cand = p if not lines[-1] else f"{lines[-1]}, {p}"
        if len(cand) > 100 and lines[-1]:
            lines.append(p)
        else:
            lines[-1] = cand
    return "\n".join(lines)


# Palettes consistent across experiments; experiments can pass their own colors arg too.
PALETTE_RHO = {
    1.0:   "#636EFA",
    0.5:   "#00CC96",
    0.25:  "#EF553B",
    0.125: "#AB63FA",
}
PALETTE_PRECISION = {
    "Symmetric Double": "#636EFA",
    "Asymmetric":       "#EF553B",
    "Symmetric Single": "#00CC96",
}
PALETTE_REGION = {"A": "#636EFA", "B": "#EF553B", "C": "#00CC96"}
PALETTE_POLICY = {"LRU": "#636EFA", "FIFO": "#00CC96", "MRU": "#EF553B", "Random": "#AB63FA"}


def _mpl():
    """Lazy import. Returns (matplotlib, pyplot) or (None, None) if missing."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return matplotlib, plt
    except ImportError:
        print("matplotlib not available; skipping plot")
        return None, None


def lineplot(
    series: Mapping[str, Sequence[tuple[float, float]]],
    *,
    out_path: Path,
    vlines: Optional[Mapping[str, float]] = None,
    colors: Optional[Mapping[str, str]] = None,
    xlabel: str = "",
    ylabel: str = "",
    title: str = "",
    figsize: tuple[float, float] = (10, 6),
    marker: str = "o",
) -> Optional[Path]:
    """Line plot, one curve per series; optional dashed vertical per series key."""
    _, plt = _mpl()
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=140)
    for label, points in series.items():
        if not points:
            continue
        xs, ys = zip(*points)
        c = (colors or {}).get(label)
        ax.plot(xs, ys, marker=marker, color=c, label=str(label))
        if vlines and label in vlines:
            ax.axvline(vlines[label], color=c, linestyle="--", alpha=0.4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, ls=":", alpha=0.5)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def stacked_bars(
    groups: Sequence[str],
    components: Mapping[str, Sequence[float]],
    *,
    out_path: Path,
    colors: Optional[Mapping[str, str]] = None,
    xlabel: str = "",
    ylabel: str = "",
    title: str = "",
    figsize: tuple[float, float] = (10, 6),
    rotation: int = 0,
) -> Optional[Path]:
    """One stacked bar per group; component dict maps name -> per-group value list."""
    _, plt = _mpl()
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=140)
    xs = list(range(len(groups)))
    bottoms = [0.0] * len(groups)
    for name, vals in components.items():
        c = (colors or {}).get(name)
        ax.bar(xs, vals, bottom=bottoms, color=c, label=name)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_xticks(xs)
    ax.set_xticklabels(groups, rotation=rotation, fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def grid_plot(
    panels: Mapping[str, dict],
    *,
    panel_fn,
    out_path: Path,
    ncols: int = 2,
    subplot_size: tuple[float, float] = (6, 4),
    title: str = "",
    sharey: bool = False,
) -> Optional[Path]:
    """Multi-panel grid; `panel_fn(ax, key, payload)` populates each cell."""
    _, plt = _mpl()
    if plt is None:
        return None
    keys = list(panels)
    nrows = (len(keys) + ncols - 1) // ncols
    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(subplot_size[0] * ncols, subplot_size[1] * nrows),
        dpi=140, squeeze=False, sharey=sharey,
    )
    flat = axes.flatten()
    for ax, key in zip(flat, keys):
        panel_fn(ax, key, panels[key])
    # hide unused axes
    for ax in flat[len(keys):]:
        ax.set_visible(False)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
