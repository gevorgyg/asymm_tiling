"""Invariants of the reference model that must hold for any trace.

The differential tests only show that the C++ cache and ref_cache agree. These
check ref_cache against facts that do not depend on how it is written, so a
mistake shared by both implementations still gets caught.
"""

import re

from hypothesis import given, strategies as st

from ref_cache import CacheConfig, LevelConfig, RefCache
from strategies import L1_CYC, MEM_CYC, config_and_trace, traces



def run(cfg: CacheConfig, trace):
    cache = RefCache(cfg)
    return cache, cache.run(trace)


def is_demand_mem_write(cfg: CacheConfig, op: str, record) -> bool:
    """A no-write-allocate write that missed everywhere."""
    return (op == "w" and not cfg.write_alloc
            and all(o == "M" for o in record.outcomes))


def dirty_lines(cache: RefCache) -> list[int]:
    """Every dirty copy in the hierarchy (a line may be dirty in two levels)."""
    return [line for lvl in cache.levels for s in lvl.sets
            for line, dirty in s.items() if dirty]


# -- counting ------------------------------------------------------------------

@given(config_and_trace("rrw"))
def test_counts_are_consistent(case):
    cfg, trace = case
    cache, records = run(cfg, trace)
    levels = [lvl.stats for lvl in cache.levels]

    for s in levels:
        assert s.hits + s.misses == s.accesses
    assert levels[0].accesses == len(trace)

    # every miss is exactly one demand access of the level below
    for upper, lower in zip(levels, levels[1:]):
        assert lower.accesses == upper.misses

    # ... and of memory, below the last level
    demand_writes = sum(is_demand_mem_write(cfg, op, r)
                        for (op, _), r in zip(trace, records))
    assert cache.mem_reads + demand_writes == levels[-1].misses


@given(config_and_trace("rrw"))
def test_each_access_follows_the_latency_table(case):
    cfg, trace = case
    _, records = run(cfg, trace)

    for (op, _), r in zip(trace, records):
        # misses down to the first hit, nothing reached below it
        assert re.fullmatch(r"M*(H-*)?", "".join(r.outcomes))

        missed_all = all(o == "M" for o in r.outcomes)
        expected = sum(lc.cycles for lc, o in zip(cfg.levels, r.outcomes)
                       if o != "-")
        expected += cfg.mem_cycles if missed_all else 0
        assert r.cycles == expected

        demand_write = is_demand_mem_write(cfg, op, r)
        assert r.mem_reads == int(missed_all and not demand_write)


@given(config_and_trace("rrw"))
def test_total_cycles_match_the_stats(case):
    """Writebacks are free: only demand accesses show up in the cycles."""
    cfg, trace = case
    cache, records = run(cfg, trace)

    demand_writes = sum(is_demand_mem_write(cfg, op, r)
                        for (op, _), r in zip(trace, records))
    from_stats = sum(lvl.stats.accesses * lvl.cycles for lvl in cache.levels)
    from_stats += (cache.mem_reads + demand_writes) * cfg.mem_cycles

    assert sum(r.cycles for r in records) == from_stats


@given(config_and_trace("r"))
def test_reads_never_dirty_anything(case):
    cfg, trace = case
    cache, _ = run(cfg, trace)

    assert dirty_lines(cache) == []
    assert all(lvl.stats.writebacks == 0 for lvl in cache.levels)
    assert cache.mem_writes == 0


# -- structure -----------------------------------------------------------------

@given(config_and_trace("rrw"))
def test_sets_hold_only_their_own_lines(case):
    cfg, trace = case
    cache, _ = run(cfg, trace)

    for lvl in cache.levels:
        for index, s in enumerate(lvl.sets):
            assert len(s) <= lvl.ways
            assert all(line % lvl.n_sets == index for line in s)


# -- dirty data ----------------------------------------------------------------

@given(config_and_trace("rrw"))
def test_no_write_is_lost(case):
    """After the last write to a line, the line is either still dirty
    somewhere or has been written to memory. Lines never written are never
    dirty and never written to memory."""
    cfg, trace = case
    cache = RefCache(cfg)
    last_write = {}      # line -> index of its last write access
    mem_writes_at = {}   # line -> indices of accesses that wrote it to memory

    for i, (op, addr) in enumerate(trace):
        logged = len(cache.mem_write_log)
        cache.access(op, addr)
        for line in cache.mem_write_log[logged:]:
            mem_writes_at.setdefault(line, []).append(i)
        if op == "w":
            last_write[addr >> cfg.block] = i

    dirty = set(dirty_lines(cache))
    for line, i in last_write.items():
        assert line in dirty or any(j >= i for j in mem_writes_at.get(line, [])), \
            f"write to line {line:#x} at access {i} was lost"

    assert dirty <= last_write.keys()
    assert mem_writes_at.keys() <= last_write.keys()


@given(config_and_trace("rrw"))
def test_dirty_data_is_never_duplicated(case):
    """Each write creates at most one dirty copy; writebacks only move or merge
    them. So memory writes + dirty copies left can't exceed the writes."""
    cfg, trace = case
    cache, _ = run(cfg, trace)

    n_writes = sum(op == "w" for op, _ in trace)
    assert cache.mem_writes + len(dirty_lines(cache)) <= n_writes


# -- LRU against an independent algorithm ----------------------------------------

@st.composite
def single_level_and_trace(draw):
    """One level, 1-8 sets x 1-8 ways, and a read-only trace."""
    block = 4
    sets_log = draw(st.integers(0, 3))
    ways_log = draw(st.integers(0, 3))
    cfg = CacheConfig(block, MEM_CYC,
                      (LevelConfig(block + sets_log + ways_log, L1_CYC, ways_log),),
                      write_alloc=True)
    return cfg, draw(traces(cfg, "r"))


def lru_hits_by_stack_distance(trace, block: int, n_sets: int, ways: int):
    """Mattson's stack algorithm: per set, keep every line ever seen ordered by
    recency (MRU first). An access hits iff its line is among the top `ways`.
    No eviction logic at all, unlike ref_cache."""
    stacks = [[] for _ in range(n_sets)]
    hits = []
    for _, addr in trace:
        line = addr >> block
        stack = stacks[line % n_sets]
        hits.append(line in stack and stack.index(line) < ways)
        if line in stack:
            stack.remove(line)
        stack.insert(0, line)
    return hits


@given(single_level_and_trace())
def test_lru_matches_stack_distance(case):
    cfg, trace = case
    cache, records = run(cfg, trace)
    lvl = cache.levels[0]

    expected = lru_hits_by_stack_distance(trace, cfg.block, lvl.n_sets, lvl.ways)
    assert [r.outcomes[0] == "H" for r in records] == expected


@given(single_level_and_trace())
def test_more_ways_never_miss_more(case):
    """LRU inclusion property: same sets, twice the ways -> no extra misses."""
    cfg, trace = case
    (lc,) = cfg.levels
    wider = CacheConfig(cfg.block, cfg.mem_cycles,
                        (LevelConfig(lc.size + 1, lc.cycles, lc.assoc + 1),),
                        cfg.write_alloc)

    small, _ = run(cfg, trace)
    big, _ = run(wider, trace)
    assert big.levels[0].stats.misses <= small.levels[0].stats.misses
