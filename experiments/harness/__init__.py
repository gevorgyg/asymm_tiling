"""Test/sweep harness for the asymm simulator.

Public surface:
    Flags           -- typed CLI flag bundle
    Metrics         -- typed binary-output bundle
    run             -- invoke ./asymm once
    run_grid        -- sweep a Cartesian product of overrides, with caching
    workspace_root  -- path of the C++ project root
"""

from ._workspace import workspace_root
from .config import render_config
from .parse import (
    CacheStats,
    Metrics,
    PrngFifoStats,
    PrngStats,
    parse_stdout,
)
from .report import top_bottom_table, write_report
from .runner import Flags, run
from .sweep import Result, run_grid
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
    "Flags",
    "Metrics",
    "PrngFifoStats",
    "PrngStats",
    "Region",
    "RegionStats",
    "Result",
    "TraceStats",
    "matrix_regions",
    "num_l1_sets",
    "parse_stdout",
    "parse_trace",
    "render_config",
    "run",
    "run_grid",
    "run_with_trace",
    "top_bottom_table",
    "workspace_root",
    "write_report",
]
