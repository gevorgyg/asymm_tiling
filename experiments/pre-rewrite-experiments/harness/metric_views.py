"""Render one figure per y-metric: cycles and per-level traffic.

Every experiment publishes the same six views of its sweep:

    cycles           -- from the mulacc-recorded run (compute included)
    cycles_nomulacc  -- from the --mulac_norecord run (memory system only)
    l1_traffic       -- L1 bytes in + out   (fast-memory boundary)
    l2_traffic       -- L2 bytes in + out
    dram_traffic     -- DRAM bytes read + written
    total_traffic    -- sum of the three levels

All views except `cycles` come from `--mulac_norecord` runs, keeping compute
accounting out of the memory-side numbers.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from .parse import Metrics
from .plots import lineplot


def _l1(m: Metrics) -> float:
    return m.l1.bytes_in + m.l1.bytes_out


def _l2(m: Metrics) -> float:
    return m.l2.bytes_in + m.l2.bytes_out


def _dram(m: Metrics) -> float:
    return m.dram.bytes_read + m.dram.bytes_written


# metric key -> (axis label, extractor)
METRICS: dict[str, tuple[str, Callable[[Metrics], float]]] = {
    "cycles":          ("cycles (mulacc recorded)",   lambda m: m.cycles),
    "cycles_nomulacc": ("cycles (no mulacc)",         lambda m: m.cycles),
    "l1_traffic":    ("L1 traffic (bytes in+out)",    _l1),
    "l2_traffic":    ("L2 traffic (bytes in+out)",    _l2),
    "dram_traffic":  ("DRAM traffic (bytes)",         _dram),
    "total_traffic": ("total traffic (bytes, L1+L2+DRAM)",
                      lambda m: _l1(m) + _l2(m) + _dram(m)),
}


@dataclass
class Cell:
    """One sweep cell: an x position on some axis, a legend entry, two runs."""
    x: float
    series: str
    traffic: Metrics   # --mulac_norecord run
    cycles: Metrics    # mulacc-recorded run


def plot_metric_family(
    cells: Sequence[Cell],
    *,
    out_dir: Path,
    base_name: str,
    title: str,
    caption: str = "",
    xlabel: str = "",
    colors: Optional[Mapping[str, str]] = None,
    vlines: Optional[Mapping[str, float]] = None,
    ref_vlines: Optional[Mapping[str, float]] = None,
    agg=min,
) -> list[Path]:
    """Write `<base_name>_<metric>.png` for each metric in METRICS.

    Cells sharing (series, x) are reduced with `agg` (default min: the best
    achievable value at that x, e.g. best tile shape). `vlines` marks a
    per-series theoretical optimum; `ref_vlines` marks a shared threshold.
    """
    written: list[Path] = []
    for key, (ylabel, extract) in METRICS.items():
        grouped: dict[str, dict[float, list[float]]] = {}
        for c in cells:
            m = c.cycles if key == "cycles" else c.traffic
            grouped.setdefault(c.series, {}).setdefault(c.x, []).append(extract(m))
        series = {
            name: sorted((x, agg(vals)) for x, vals in by_x.items())
            for name, by_x in grouped.items()
        }
        full_title = f"{title} — {ylabel}" + (f"\n{caption}" if caption else "")
        out = lineplot(
            series, out_path=out_dir / f"{base_name}_{key}.png",
            xlabel=xlabel, ylabel=ylabel, title=full_title,
            colors=colors, vlines=vlines, ref_vlines=ref_vlines,
        )
        if out is not None:
            written.append(out)
    return written
