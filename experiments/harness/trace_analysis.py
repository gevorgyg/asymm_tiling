"""stream-parse a level-2 simulator trace; tag events by matrix region"""

import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping, Optional

from . import parse
from . import runner
from ._workspace import asymm_binary, workspace_root


@dataclass
class Region:
    name: str
    start: int   # byte addr, inclusive
    end: int     # byte addr, exclusive

    def contains(self, addr: int) -> bool:
        return self.start <= addr < self.end


@dataclass
class RegionStats:
    l1_lookups: int = 0
    l1_hits:    int = 0
    l2_lookups: int = 0
    l2_hits:    int = 0
    dram_accesses: int = 0
    line_fills_l1: int = 0
    line_fills_l2: int = 0
    evicts_l1_dirty: int = 0
    evicts_l1_clean: int = 0
    evicts_l2_dirty: int = 0
    evicts_l2_clean: int = 0


@dataclass
class TraceStats:
    regions: dict[str, RegionStats] = field(default_factory=dict)
    l1_evicts_per_set: dict[int, int] = field(default_factory=dict)


# matches L1/L2 events emitted by cache_actions.cpp at trace_level=2
_RE_TAGLOOKUP = re.compile(r"^\s{4}(L1|L2) TagLookup @0x([0-9a-fA-F]+) (HIT|MISS)")
_RE_MEMORY    = re.compile(r"^\s{4}MemoryAccess @0x([0-9a-fA-F]+)")
_RE_LINEFILL  = re.compile(r"^\s{4}(L1|L2) LineFill @0x([0-9a-fA-F]+)")
_RE_EVICT     = re.compile(r"^\s{4}(L1|L2) Evict line=0x([0-9a-fA-F]+) \((dirty|clean)\)")


def _region_for(regions: list[Region], addr: int) -> Optional[Region]:
    for r in regions:
        if r.contains(addr):
            return r
    return None


def parse_trace(path: Path, regions: list[Region], *,
                num_l1_sets: int = 0,
                l1_line_bytes: int = 0,
                l2_line_bytes: int = 0) -> TraceStats:
    out = TraceStats(regions={r.name: RegionStats() for r in regions})

    def _bump(addr: int, attr: str) -> None:
        r = _region_for(regions, addr)
        if r is None:
            return
        cur = getattr(out.regions[r.name], attr)
        setattr(out.regions[r.name], attr, cur + 1)

    with path.open() as f:
        for line in f:
            m = _RE_TAGLOOKUP.match(line)
            if m:
                level, addr_hex, status = m.group(1), m.group(2), m.group(3)
                addr = int(addr_hex, 16)
                if level == "L1":
                    _bump(addr, "l1_lookups")
                    if status == "HIT":
                        _bump(addr, "l1_hits")
                else:
                    _bump(addr, "l2_lookups")
                    if status == "HIT":
                        _bump(addr, "l2_hits")
                continue

            m = _RE_MEMORY.match(line)
            if m:
                _bump(int(m.group(1), 16), "dram_accesses")
                continue

            m = _RE_LINEFILL.match(line)
            if m:
                level, addr_hex = m.group(1), m.group(2)
                _bump(int(addr_hex, 16),
                      "line_fills_l1" if level == "L1" else "line_fills_l2")
                continue

            m = _RE_EVICT.match(line)
            if m:
                level, line_addr_hex, dirt = m.group(1), m.group(2), m.group(3)
                line_addr = int(line_addr_hex, 16)
                # evict carries a *line* address; convert to byte for region tag
                line_bytes = l1_line_bytes if level == "L1" else l2_line_bytes
                byte_addr = line_addr * line_bytes if line_bytes else line_addr
                _bump(byte_addr, f"evicts_{level.lower()}_{dirt}")
                if level == "L1" and num_l1_sets > 0:
                    s = line_addr % num_l1_sets
                    out.l1_evicts_per_set[s] = out.l1_evicts_per_set.get(s, 0) + 1

    return out


def matrix_regions(cfg: Mapping[str, object]) -> list[Region]:
    a_h = int(cfg["A_HEIGHT_DIM"]); a_w = int(cfg["A_WIDTH_DIM"]); b_w = int(cfg["B_WIDTH_DIM"])
    a_p = int(cfg["A_PRECISION_BYTES"]); b_p = int(cfg["B_PRECISION_BYTES"])
    c_p = max(a_p, b_p)
    a_bytes = a_h * a_w * a_p
    b_bytes = a_w * b_w * b_p
    c_bytes = a_h * b_w * c_p
    return [
        Region("A", 0, a_bytes),
        Region("B", a_bytes, a_bytes + b_bytes),
        Region("C", a_bytes + b_bytes, a_bytes + b_bytes + c_bytes),
    ]


def num_l1_sets(cfg: Mapping[str, object]) -> int:
    size = int(cfg["L1_SIZE_BYTES"])
    line = int(cfg["L1_LINE_SIZE_BYTES"])
    assoc = int(cfg["L1_ASSOC"])
    return size // (line * assoc)


def run_with_trace(config_path: Path, flags: runner.Flags,
                   cfg_for_regions: Mapping[str, object]
                   ) -> tuple[parse.Metrics, TraceStats]:
    """run ./asymm with trace_level=2 + temp file, return (metrics, region_stats)"""
    fd, tmp = tempfile.mkstemp(suffix=".trace")
    import os
    os.close(fd)
    trace_path = Path(tmp)
    flags_with_trace = replace(flags, trace_level=2, trace_file=str(trace_path))
    try:
        metrics = runner.run(config_path, flags=flags_with_trace)
        stats = parse_trace(
            trace_path,
            matrix_regions(cfg_for_regions),
            num_l1_sets=num_l1_sets(cfg_for_regions),
            l1_line_bytes=int(cfg_for_regions["L1_LINE_SIZE_BYTES"]),
            l2_line_bytes=int(cfg_for_regions["L2_LINE_SIZE_BYTES"]),
        )
    finally:
        trace_path.unlink(missing_ok=True)
    return metrics, stats
