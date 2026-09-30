"""Differential tests: C++ CacheUnit (via build/cache_driver) vs ref_cache.

Every access is compared (cycles, per-level H/M/-, memory accesses) and the
first divergence is reported. Hypothesis shrinks failing traces to a minimal
reproducer.

run:  .venv/bin/python -m pytest tests/
"""

import subprocess
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ref_cache import CacheConfig, LevelConfig, RefCache

DRIVER = Path(__file__).resolve().parent.parent / "build" / "cache_driver"

pytestmark = pytest.mark.skipif(
    not DRIVER.exists(), reason="build/cache_driver not built (run ./compbuild)")

# distinct latencies so every path (L1 / L2 / mem) has a unique cycle count
L1_CYC, L2_CYC, MEM_CYC = 4, 20, 100

# (block, l1_size, l1_assoc, l2_size, l2_assoc), all log2
GEOMETRIES = {
    "direct-mapped":  (4, 7, 0, 9, 0),   # L1: 8 sets x 1 way,  L2: 32 x 1
    "small-assoc":    (4, 8, 1, 10, 2),  # L1: 8 sets x 2 ways, L2: 16 x 4
    "fully-assoc-l1": (4, 6, 2, 8, 2),   # L1: 1 set  x 4 ways, L2: 4 x 4
    "default":        (6, 14, 3, 16, 3),  # config.toml geometry
}


def make_config(geometry: str, write_alloc: bool) -> CacheConfig:
    block, l1s, l1a, l2s, l2a = GEOMETRIES[geometry]
    return CacheConfig(block, MEM_CYC,
                       (LevelConfig(l1s, L1_CYC, l1a),
                        LevelConfig(l2s, L2_CYC, l2a)),
                       write_alloc)


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
                f"L{j + 1} set {line % (1 << (lc.size - lc.assoc - cfg.block))}"
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


# -- trace generation --------------------------------------------------------

@st.composite
def traces(draw, cfg: CacheConfig, ops: str):
    """Traces over a small address window so sets actually conflict."""
    l2 = cfg.levels[-1]
    l2_lines = 1 << (l2.size - cfg.block)
    n_lines = draw(st.sampled_from([l2_lines // 2, l2_lines * 2, l2_lines * 4]))
    base = draw(st.sampled_from([0, 0x7F3A_1000_0000]))  # exercise high tag bits
    line_bytes = 1 << cfg.block

    access = st.tuples(
        st.sampled_from(ops),
        st.builds(lambda l, off: base + l * line_bytes + off,
                  st.integers(0, n_lines - 1),
                  st.integers(0, line_bytes - 1)))
    return draw(st.lists(access, min_size=1, max_size=400))


def config_and_trace(ops: str):
    return st.builds(
        lambda g, wa: make_config(g, wa),
        st.sampled_from(list(GEOMETRIES)), st.booleans(),
    ).flatmap(lambda cfg: st.tuples(st.just(cfg), traces(cfg, ops)))


# -- tests -------------------------------------------------------------------

@settings(max_examples=300, deadline=None)
@given(config_and_trace("r"))
def test_read_only(case):
    cfg, trace = case
    assert_same(cfg, trace)


@settings(max_examples=300, deadline=None)
@given(config_and_trace("rrw"))
def test_reads_and_writes(case):
    cfg, trace = case
    assert_same(cfg, trace)


@pytest.mark.parametrize("geometry", list(GEOMETRIES))
@pytest.mark.parametrize("write_alloc", [False, True])
def test_sequential_sweep(geometry, write_alloc):
    """Two passes over 2x L2 capacity, 4-byte stride, every 4th a write."""
    cfg = make_config(geometry, write_alloc)
    span = 2 << cfg.levels[-1].size
    trace = [("w" if (a // 4) % 4 == 3 else "r", a)
             for _ in range(2) for a in range(0, span, 4)]
    assert_same(cfg, trace)
