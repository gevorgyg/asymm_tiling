"""Hand-computed checks of the reference model itself (the oracle)."""

from ref_cache import CacheConfig, LevelConfig, RefCache

L1, L2, MEM = 4, 20, 100


def cache(write_alloc=False, l1=(6, 0), l2=(8, 1), block=4):
    """Default: 16B lines, L1 = 4 sets x 1 way, L2 = 8 sets x 2 ways."""
    return RefCache(CacheConfig(block, MEM,
                                (LevelConfig(l1[0], L1, l1[1]),
                                 LevelConfig(l2[0], L2, l2[1])),
                                write_alloc))


def test_cold_then_warm():
    c = cache()
    r = c.access("r", 0x100)
    assert (r.cycles, r.outcomes, r.mem_reads) == (L1 + L2 + MEM, ("M", "M"), 1)
    r = c.access("r", 0x10F)  # same line
    assert (r.cycles, r.outcomes, r.mem) == (L1, ("H", "-"), 0)


def test_l2_hit_after_l1_conflict():
    c = cache()
    c.access("r", 0x000)
    c.access("r", 0x040)  # same L1 set (4 sets x 16B), evicts 0x000 from L1
    r = c.access("r", 0x000)
    assert (r.cycles, r.outcomes, r.mem) == (L1 + L2, ("M", "H"), 0)


def test_lru_thrash_vs_fit():
    # fully associative L1 with 4 ways; L2 direct-mapped and big
    c = cache(l1=(6, 2), l2=(12, 0))
    lines = [i * 0x10 for i in range(4)]
    for a in lines:
        c.access("r", a)
    assert all(c.access("r", a).outcomes[0] == "H" for a in lines)

    c = cache(l1=(6, 2), l2=(12, 0))
    lines = [i * 0x10 for i in range(5)]  # one more than the ways
    for a in lines:
        c.access("r", a)
    assert all(c.access("r", a).outcomes[0] == "M" for a in lines)


def test_lru_hit_refreshes():
    c = cache(l1=(5, 1), l2=(12, 0))  # L1: 1 set x 2 ways
    c.access("r", 0x00)
    c.access("r", 0x10)
    c.access("r", 0x00)  # 0x10 is now LRU
    c.access("r", 0x20)  # evicts 0x10
    assert c.access("r", 0x00).outcomes[0] == "H"
    assert c.access("r", 0x10).outcomes[0] == "M"


def test_write_hit_costs_l1_and_is_counted():
    c = cache()
    c.access("r", 0x100)
    r = c.access("w", 0x100)
    assert (r.cycles, r.outcomes) == (L1, ("H", "-"))
    assert c.levels[0].stats.accesses == 2


def test_write_no_alloc_miss_goes_to_memory_and_does_not_allocate():
    c = cache(write_alloc=False)
    r = c.access("w", 0x100)
    assert (r.cycles, r.outcomes, r.mem_writes, r.mem_reads) == \
        (L1 + L2 + MEM, ("M", "M"), 1, 0)
    assert c.access("r", 0x100).outcomes == ("M", "M")


def test_write_no_alloc_hit_in_l2_marks_l2_dirty():
    c = cache(write_alloc=False)
    c.access("r", 0x000)
    c.access("r", 0x040)  # 0x000 leaves L1, stays in L2
    r = c.access("w", 0x000)
    assert (r.cycles, r.outcomes, r.mem) == (L1 + L2, ("M", "H"), 0)
    assert c.levels[1].sets[0][0x000 >> 4] is True
    assert not c.levels[0].contains(0x000 >> 4)


def test_write_alloc_miss_fills_and_dirties_l1():
    c = cache(write_alloc=True)
    r = c.access("w", 0x100)
    assert (r.cycles, r.outcomes, r.mem_reads) == (L1 + L2 + MEM, ("M", "M"), 1)
    assert c.access("r", 0x100).outcomes == ("H", "-")
    assert c.levels[0].sets[(0x100 >> 4) % 4][0x100 >> 4] is True


def test_dirty_l1_eviction_updates_l2_in_place_for_free():
    c = cache(write_alloc=True)
    c.access("w", 0x000)
    r = c.access("r", 0x040)  # evicts dirty 0x000 from L1 into L2 (present)
    assert (r.cycles, r.mem_writes) == (L1 + L2 + MEM, 0)
    assert c.levels[0].stats.writebacks == 1
    assert c.levels[1].stats.accesses == 2  # the writeback is not an access
    assert c.levels[1].sets[0][0x000 >> 4] is True


def test_dirty_l1_eviction_installs_in_l2_when_absent():
    # L1: 1 set x 2 ways, L2: 1 set x 2 ways -> L2 can lose lines L1 keeps
    c = cache(write_alloc=True, l1=(5, 1), l2=(5, 1))
    c.access("w", 0x00)  # L1 {00*}, L2 {00}
    c.access("r", 0x10)  # L1 {00*,10}, L2 {00,10}
    c.access("r", 0x10)  # L1 hit; L2 LRU is still 00
    c.access("r", 0x20)  # L2 evicts 00 (clean) -> L2 {10,20}; L1 evicts 00*
    # the dirty L1 victim 00 is absent from L2: installed dirty, evicting 10
    l2 = c.levels[1].sets[0]
    assert list(l2.items()) == [(0x2, False), (0x0, True)]
    assert c.mem_writes == 0
    r = c.access("r", 0x00)
    assert r.outcomes == ("M", "H")


def test_dirty_l2_eviction_is_one_free_memory_write():
    c = cache(write_alloc=True, l1=(5, 1), l2=(5, 1))
    c.access("w", 0x00)  # L1 {00*},    L2 {00}
    c.access("r", 0x10)  # L1 {00*,10}, L2 {00,10}
    c.access("r", 0x20)  # L2 evicts 00 -> {10,20}; L1 evicts 00* -> L2 {20,00*}
    c.access("r", 0x30)  # L2 evicts 20 -> {00*,30}
    assert c.mem_writes == 0
    r = c.access("r", 0x40)  # L2 evicts 00* -> memory
    assert (r.cycles, r.mem_reads, r.mem_writes) == (L1 + L2 + MEM, 1, 1)
    assert c.levels[1].stats.writebacks == 1
