"""Differential tests: C++ CacheUnit (via build/cache_driver) vs ref_cache.

Every access is compared (cycles, per-level H/M/-, memory accesses) and the
first divergence is reported. Hypothesis shrinks failing traces to a minimal
reproducer.

run:  .venv/bin/python -m pytest tests/
"""

import subprocess
from pathlib import Path

import pytest
from hypothesis import given

from ref_cache import POLICIES, CacheConfig, LevelConfig, RefCache
from strategies import (GEOMETRIES, L1_CYC, L2_CYC, MEM_CYC, config_and_trace,
                        make_config)

DRIVER = Path(__file__).resolve().parent.parent / "build" / "cache_driver"

pytestmark = pytest.mark.skipif(
    not DRIVER.exists(), reason="build/cache_driver not built (run ./compbuild)")

def run_driver(cfg: CacheConfig, trace) -> list[tuple]:
    stdin = "".join(f"{op} {addr:x}\n" for op, addr in trace)
    out = subprocess.run([str(DRIVER), *cfg.driver_args()], input=stdin,
                         capture_output=True, text=True, check=True).stdout
    records = []
    for line in out.splitlines():
        cycles, *outcomes, mem = line.split()
        records.append((int(cycles), tuple(outcomes), int(mem)))
    return records


def run_ref(cfg: CacheConfig, trace) -> list[tuple]:
    return [(r.cycles, r.outcomes, r.mem) for r in RefCache(cfg).run(trace)]


def assert_same(cfg: CacheConfig, trace) -> None:
    ref = run_ref(cfg, trace)
    sim = run_driver(cfg, trace)
    assert len(sim) == len(ref), "driver produced a different number of records"

    for i, (r, s) in enumerate(zip(ref, sim)):
        if r != s:
            op, addr = trace[i]
            line = addr >> cfg.block
            sets = ", ".join(
                f"L{j + 1} set {line % lc.sets(cfg.block)}"
                for j, lc in enumerate(cfg.levels))
            history = "\n".join(
                f"  [{j}] {o} {a:#x}  ref={ref[j]}"
                for j, (o, a) in enumerate(trace[max(0, i - 8):i + 1],
                                           start=max(0, i - 8)))
            pytest.fail(
                f"first divergence at access {i}: {op} {addr:#x} "
                f"(line {line:#x}; {sets})\n"
                f"  expected (ref) : {r}\n"
                f"  got (cachesim) : {s}\n"
                f"  format: (cycles, (L1, L2), mem accesses)\n"
                f"recent accesses:\n{history}")


# -- tests -------------------------------------------------------------------

@given(config_and_trace("r"))
def test_read_only(case):
    cfg, trace = case
    assert_same(cfg, trace)


@given(config_and_trace("rrw"))
def test_reads_and_writes(case):
    cfg, trace = case
    assert_same(cfg, trace)


@pytest.mark.parametrize("geometry", list(GEOMETRIES))
@pytest.mark.parametrize("write_alloc", [False, True])
@pytest.mark.parametrize("policy", POLICIES)
def test_sequential_sweep(geometry, write_alloc, policy):
    """Two passes over 2x L2 capacity, 4-byte stride, every 4th a write."""
    cfg = make_config(geometry, write_alloc, policy)
    span = 2 * cfg.levels[-1].bytes()
    trace = [("w" if (a // 4) % 4 == 3 else "r", a)
             for _ in range(2) for a in range(0, span, 4)]
    assert_same(cfg, trace)


# L1 and L2 both 1 set x 2 ways (16 B lines), so L2 can evict lines L1 keeps.
# Traces from test_ref_cache.py, for writeback paths random traces rarely hit.
TINY_NINE = CacheConfig(4, MEM_CYC,
                        (LevelConfig(5, L1_CYC, 1), LevelConfig(5, L2_CYC, 1)),
                        write_alloc=True)


@pytest.mark.parametrize("trace", [
    # dirty L1 victim absent from L2 -> installed in L2, then re-read from L2
    [("w", 0x00), ("r", 0x10), ("r", 0x10), ("r", 0x20), ("r", 0x00)],
    # dirty line travels L1 -> L2 -> memory (free writeback)
    [("w", 0x00), ("r", 0x10), ("r", 0x20), ("r", 0x30), ("r", 0x40)],
], ids=["writeback-installs-in-l2", "writeback-reaches-memory"])
def test_writeback_scenarios(trace):
    assert_same(TINY_NINE, trace)
