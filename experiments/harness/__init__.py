"""Test/sweep harness for the asymm simulator.

Public surface:
    Flags           -- typed CLI flag bundle
    Metrics         -- typed binary-output bundle
    run             -- invoke ./asymm once
    run_grid        -- sweep a Cartesian product of overrides, with caching
    workspace_root  -- path of the C++ project root
"""

from ._workspace import workspace_root
from .config import changed_from_default, parse_config, render_config
from . import paper_model
from .metric_views import METRICS, Cell, plot_metric_family
from .parse import (
    CacheStats,
    DramStats,
    Metrics,
    PrngFifoStats,
    PrngStats,
    parse_stdout,
)
from .plots import (
    PALETTE_POLICY,
    PALETTE_PRECISION,
    PALETTE_REGION,
    PALETTE_RHO,
    describe_changes,
    grid_plot,
    lineplot,
    stacked_bars,
    summarize_config,
)
from .report import top_bottom_table, write_report
from .runner import Flags, run
from .sweep import DualResult, Result, run_grid, run_grid_dual
from .trace_analysis import (
    Region,
    RegionStats,
    TraceStats,
    matrix_regions,
    num_l1_sets,
    parse_trace,
    run_with_trace,
)

__all__ = [
    "CacheStats",
    "Cell",
    "DramStats",
    "DualResult",
    "Flags",
    "METRICS",
    "Metrics",
    "changed_from_default",
    "describe_changes",
    "paper_model",
    "parse_config",
    "plot_metric_family",
    "run_grid_dual",
    "PALETTE_POLICY",
    "PALETTE_PRECISION",
    "PALETTE_REGION",
    "PALETTE_RHO",
    "PrngFifoStats",
    "PrngStats",
    "Region",
    "RegionStats",
    "Result",
    "TraceStats",
    "grid_plot",
    "lineplot",
    "matrix_regions",
    "num_l1_sets",
    "parse_stdout",
    "parse_trace",
    "render_config",
    "run",
    "run_grid",
    "run_with_trace",
    "stacked_bars",
    "summarize_config",
    "top_bottom_table",
    "workspace_root",
    "write_report",
]
