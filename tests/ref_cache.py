"""Reference cache model: the spec the C++ CacheUnit is tested against.

Deliberately simple: one OrderedDict per set, keyed by the full line address
(addr >> block), so it shares no tag/set arithmetic with the C++ code.

Semantics
---------
Geometry
    All sizes are log2 (as in config.toml): line = 2^block bytes,
    ways = 2^assoc, sets = 2^(size - assoc - block).
    set index = line_addr mod sets.

Replacement
    LRU per set. Only demand accesses (a hit, or the fill after a miss)
    update recency. A newly filled line is MRU. Free (invalid) ways are used
    before anything is evicted.

What counts as an access
    Reads and writes both count as accesses (and hits/misses) at every level
    they reach. A level is reached only if every level above it missed.

Latency (serial lookup, identical for reads and writes)
    hit in L1          -> l1
    miss L1, hit L2    -> l1 + l2
    miss everywhere    -> l1 + l2 + mem
    i.e. the sum of the cycles of every level reached, plus mem if all missed.

Write policy: write-back at every level (per-level dirty bits).
    write-allocate:    a write is handled exactly like a read (same fills,
                       same latency), then the L1 line is marked dirty.
    no-write-allocate: the write goes down level by level; the first level
                       that hits marks its line dirty. If every level misses,
                       it is one memory write. Nothing is allocated anywhere.

Inclusion: NINE (non-inclusive, non-exclusive)
    miss            -> the line is filled into every level that missed,
                       lowest level first (L2, then L1).
    L2 eviction     -> no back-invalidation; L1 may keep the line.
    dirty eviction from level i:
        line present in level i+1 -> mark it dirty in place (no LRU update)
        line absent in level i+1  -> install it there dirty, as MRU, without
                                     fetching it from memory (the whole line is
                                     written). That install may itself evict.
        i is the last level       -> one memory write.

Writebacks
    Free: they add no cycles and do not count as accesses of the level they
    go to. They are counted as writebacks (and as memory writes when they
    reach memory).

End of run
    No flush. Dirty lines left in the cache are not written back.
"""

from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class LevelConfig:
    size: int  # log2 bytes
    cycles: int
    assoc: int  # log2 ways


@dataclass(frozen=True)
class CacheConfig:
    block: int  # log2 bytes
    mem_cycles: int
    levels: tuple[LevelConfig, ...]
    write_alloc: bool

    def driver_args(self) -> list[str]:
        """Arguments for tests/cache_driver.cpp (two levels only)."""
        assert len(self.levels) == 2
        l1, l2 = self.levels
        return [str(v) for v in (self.block, self.mem_cycles,
                                 l1.size, l1.cycles, l1.assoc,
                                 l2.size, l2.cycles, l2.assoc,
                                 int(self.write_alloc))]


@dataclass
class LevelStats:
    accesses: int = 0
    hits: int = 0
    misses: int = 0
    writebacks: int = 0  # dirty lines this level evicted


@dataclass(frozen=True)
class Record:
    """Outcome of one access. `outcomes` holds H / M / - per level."""
    cycles: int
    outcomes: tuple[str, ...]
    mem_reads: int
    mem_writes: int

    @property
    def mem(self) -> int:
        return self.mem_reads + self.mem_writes


class Level:
    def __init__(self, cfg: LevelConfig, block: int):
        self.cycles = cfg.cycles
        self.ways = 1 << cfg.assoc
        self.n_sets = 1 << (cfg.size - cfg.assoc - block)
        assert self.n_sets >= 1, "cache smaller than one set"
        # line_addr -> dirty; first item is LRU, last is MRU
        self.sets = [OrderedDict() for _ in range(self.n_sets)]
        self.stats = LevelStats()

    def _set(self, line: int) -> OrderedDict:
        return self.sets[line % self.n_sets]

    def contains(self, line: int) -> bool:
        """Presence check that does not touch LRU."""
        return line in self._set(line)

    def lookup(self, line: int) -> bool:
        """Demand lookup: counts the access and updates LRU on a hit."""
        self.stats.accesses += 1
        s = self._set(line)
        if line in s:
            s.move_to_end(line)
            self.stats.hits += 1
            return True
        self.stats.misses += 1
        return False

    def fill(self, line: int, dirty: bool) -> tuple[int, bool] | None:
        """Insert a line that is not present as MRU; return the victim."""
        s = self._set(line)
        assert line not in s
        victim = s.popitem(last=False) if len(s) == self.ways else None
        s[line] = dirty
        return victim

    def mark_dirty(self, line: int) -> None:
        s = self._set(line)
        assert line in s
        s[line] = True


class RefCache:
    def __init__(self, cfg: CacheConfig):
        self.cfg = cfg
        self.levels = [Level(lc, cfg.block) for lc in cfg.levels]
        self.mem_reads = 0
        self.mem_writes = 0
        self.mem_write_log: list[int] = []  # line of every memory write, in order

    # -- public -------------------------------------------------------------

    def access(self, op: str, addr: int) -> Record:
        reads0, writes0 = self.mem_reads, self.mem_writes
        line = addr >> self.cfg.block

        if op == "r":
            cycles, outcomes = self._read(line)
        elif op == "w" and self.cfg.write_alloc:
            cycles, outcomes = self._read(line)
            self.levels[0].mark_dirty(line)
        elif op == "w":
            cycles, outcomes = self._write_no_alloc(line)
        else:
            raise ValueError(f"unknown op {op!r}")

        return Record(cycles, tuple(outcomes),
                      self.mem_reads - reads0, self.mem_writes - writes0)

    def run(self, trace: list[tuple[str, int]]) -> list[Record]:
        return [self.access(op, addr) for op, addr in trace]

    # -- internals ----------------------------------------------------------

    def _probe(self, line: int) -> tuple[int, int, list[str]]:
        """Walk the levels until a hit. Returns (hit level or len(levels),
        cycles, outcomes)."""
        outcomes = ["-"] * len(self.levels)
        cycles = 0
        for i, lvl in enumerate(self.levels):
            cycles += lvl.cycles
            if lvl.lookup(line):
                outcomes[i] = "H"
                return i, cycles, outcomes
            outcomes[i] = "M"
        return len(self.levels), cycles + self.cfg.mem_cycles, outcomes

    def _read(self, line: int) -> tuple[int, list[str]]:
        hit_level, cycles, outcomes = self._probe(line)
        if hit_level == len(self.levels):
            self.mem_reads += 1
        # fill every level that missed, lowest first
        for i in reversed(range(hit_level)):
            self._evicted(i, self.levels[i].fill(line, dirty=False))
        return cycles, outcomes

    def _write_no_alloc(self, line: int) -> tuple[int, list[str]]:
        hit_level, cycles, outcomes = self._probe(line)
        if hit_level == len(self.levels):
            self._mem_write(line)
        else:
            self.levels[hit_level].mark_dirty(line)
        return cycles, outcomes

    def _evicted(self, level: int, victim: tuple[int, bool] | None) -> None:
        if victim is None:
            return
        line, dirty = victim
        if dirty:
            self.levels[level].stats.writebacks += 1
            self._writeback(level + 1, line)

    def _writeback(self, level: int, line: int) -> None:
        if level == len(self.levels):
            self._mem_write(line)
            return
        lvl = self.levels[level]
        if lvl.contains(line):
            lvl.mark_dirty(line)
        else:
            self._evicted(level, lvl.fill(line, dirty=True))

    def _mem_write(self, line: int) -> None:
        self.mem_writes += 1
        self.mem_write_log.append(line)
