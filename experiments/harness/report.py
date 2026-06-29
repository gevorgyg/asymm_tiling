"""Markdown report helpers. Strictly generic -- nothing here bakes in matrix
shape, cache topology, or precision conventions. Caller supplies which sweep
keys to include and how to sort."""

from pathlib import Path
from typing import Callable, Iterable, Sequence

from .sweep import Result


def _row(cells: Sequence[object]) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _hdr(headers: Sequence[str]) -> list[str]:
    return [_row(headers), _row(["---"] * len(headers))]


def metrics_columns(r: Result) -> dict[str, object]:
    """Default metric columns surfaced in reports. Caller can build their own."""
    m = r.metrics
    return {
        "L1 hit":      f"{m.l1.hit_rate:.3f}",
        "L2 hit":      f"{m.l2.hit_rate:.3f}",
        "L1 LineFill": m.l1.line_fills,
        "DRAM bytes":  m.l2.line_fills * 64,  # only valid for fixed line size
        "Cycles":      f"{m.cycles:,}",
    }


def top_bottom_table(
    title: str,
    results: list[Result],
    *,
    axis_keys: Sequence[str],
    sort_by: Callable[[Result], float] = lambda r: r.metrics.cycles,
    top_n: int = 5,
    bottom_n: int = 3,
    columns: Callable[[Result], dict[str, object]] = metrics_columns,
) -> str:
    """Return a markdown block with a `## title` heading + top-N and bottom-N
    tables ranked by `sort_by` (ascending). axis_keys are the override keys
    pulled into the first columns to identify each row."""
    ranked = sorted(results, key=sort_by)
    out: list[str] = [f"## {title}\n"]
    sample_cols = list(columns(ranked[0]).keys()) if ranked else []
    headers = ["Rank", *axis_keys, *sample_cols]

    def render_block(label: str, rows: Iterable[Result], start: int):
        out.append(f"\n### {label}\n")
        out.extend(_hdr(headers))
        for i, r in enumerate(rows, start):
            ax_vals = [r.overrides.get(k, "") for k in axis_keys]
            col_vals = list(columns(r).values())
            out.append(_row([i, *ax_vals, *col_vals]))

    render_block(f"Top {min(top_n, len(ranked))}", ranked[:top_n], 1)
    if bottom_n > 0 and len(ranked) > top_n:
        render_block(f"Bottom {min(bottom_n, len(ranked))}",
                     ranked[-bottom_n:], len(ranked) - bottom_n + 1)
    return "\n".join(out) + "\n"


def write_report(out_path: Path, title: str, blocks: Iterable[str]) -> None:
    body = f"# {title}\n\n" + "\n".join(blocks)
    out_path.write_text(body)
