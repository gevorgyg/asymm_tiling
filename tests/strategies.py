"""Cache geometries and Hypothesis trace generators shared by the tests."""

from hypothesis import strategies as st

from ref_cache import POLICIES, CacheConfig, LevelConfig

# distinct latencies so every path (L1 / L2 / mem) has a unique cycle count
L1_CYC, L2_CYC, MEM_CYC = 4, 20, 100

# (block, l1_size, l1_assoc, l2_size, l2_assoc), all log2
GEOMETRIES = {
    "direct-mapped":  (4, 7, 0, 9, 0),   # L1: 8 sets x 1 way,  L2: 32 x 1
    "small-assoc":    (4, 8, 1, 10, 2),  # L1: 8 sets x 2 ways, L2: 16 x 4
    "fully-assoc-l1": (4, 6, 2, 8, 2),   # L1: 1 set  x 4 ways, L2: 4 x 4
    "default":        (6, 14, 3, 16, 3),  # config.toml geometry
}


def make_config(geometry: str, write_alloc: bool,
                policy: str = "lru") -> CacheConfig:
    block, l1s, l1a, l2s, l2a = GEOMETRIES[geometry]
    return CacheConfig(block, MEM_CYC,
                       (LevelConfig(l1s, L1_CYC, l1a),
                        LevelConfig(l2s, L2_CYC, l2a)),
                       write_alloc, policy)


@st.composite
def traces(draw, cfg: CacheConfig, ops: str):
    """Traces over a small address window so sets actually conflict."""
    last = cfg.levels[-1]
    last_lines = 1 << (last.size - cfg.block)
    # working set: fits, just over capacity (where LRU and eviction bugs
    # show), well over capacity
    n_lines = draw(st.sampled_from([
        max(1, last_lines // 2), last_lines + max(1, last_lines // 4),
        last_lines * 2, last_lines * 4]))
    base = draw(st.sampled_from([0, 0x7F3A_1000_0000]))  # exercise high tag bits
    line_bytes = 1 << cfg.block

    access = st.tuples(
        st.sampled_from(ops),
        st.builds(lambda l, off: base + l * line_bytes + off,
                  st.integers(0, n_lines - 1),
                  st.integers(0, line_bytes - 1)))
    # Hypothesis favours short lists; force long traces often enough for
    # multi-step eviction chains to happen (still shrinks toward 1)
    min_size = draw(st.sampled_from([1, 100, 300]))
    return draw(st.lists(access, min_size=min_size, max_size=400))


def config_and_trace(ops: str):
    """A two-level config from GEOMETRIES (any write and replacement
    policy) + a trace."""
    return st.builds(
        make_config, st.sampled_from(list(GEOMETRIES)), st.booleans(),
        st.sampled_from(POLICIES),
    ).flatmap(lambda cfg: st.tuples(st.just(cfg), traces(cfg, ops)))
