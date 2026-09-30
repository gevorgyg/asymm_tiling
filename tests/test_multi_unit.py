"""Integration tests: the whole simulator (build/sim) on matrices small enough
that every miss is compulsory, so the cache stats follow from the matrix
layout alone.

Setup: M = K = N = 16, 1-byte B, 4-byte A and C, 8x8 tiles, 4x4 registers,
16 KB L1, 64 KB L2. A, C = 1024 B each, B = 256 B, laid out back to back:
2304 B = 36 lines. A starts at 0x1000 (line aligned): A at 0x1000, B at
0x1400, C at 0x1500.
"""

import os
import subprocess
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parent.parent / "build" / "sim"

pytestmark = pytest.mark.skipif(
    not SIM.exists(), reason="build/sim not built (run ./compbuild)")

DIM, TILE, REG, MULACC_COST = 16, 8, 4, 4
N_TILES = (DIM // TILE) ** 2
REGS_PER_TILE_SIDE = TILE // REG   # register blocks along a tile's rows / cols
REGS_ALONG_K = DIM // REG          # register blocks along the inner dimension

MACS = N_TILES * REGS_PER_TILE_SIDE ** 2 * REGS_ALONG_K  # mulacc() calls
LINES_A, LINES_B, LINES_C = 16, 4, 16


# block mem l1_size l1_cyc l1_assoc l2_size l2_cyc l2_assoc
DEFAULT_CACHE = ["6", "100", "14", "4", "3", "16", "20", "3"]
NO_L2_CACHE = ["6", "100", "14", "4", "3", "0", "20", "3"]


def run_sim(orientation: str, b_source: str, write_alloc: bool,
            tmp_path: Path, policy: str = "lru", cache=DEFAULT_CACHE,
            fifo_capacity: int = 16384) -> dict[str, float]:
    args = [
        str(SIM), "-o", orientation, "-B", b_source,
        "-m", str(DIM), "-k", str(DIM), "-n", str(DIM), "-p", "1", "-r", "4",
        "--th", str(TILE), "--tw", str(TILE), "--rd", str(REG),
        "--mc", str(MULACC_COST),
        "-c", *cache,
        "--fc", str(fifo_capacity), "--fg", "10", "--fa", "2", "-s", "1",
        "--write-allocate" if write_alloc else "--no-write-allocate",
        "--policy", policy,
    ]
    # run where no config.toml can be found, so only the flags above count
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path)}
    out = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True,
                         text=True, check=True).stdout

    stats = {}
    for line in out.splitlines():
        name, sep, value = line.partition("|")
        if sep and name.strip() != "Metric":
            stats[name.strip()] = float(value)
    return stats


@pytest.mark.parametrize("orientation", ["output", "weight"])
@pytest.mark.parametrize("write_alloc", [False, True])
@pytest.mark.parametrize("policy", ["lru", "fifo", "mru", "random"])
def test_everything_fits_only_compulsory_misses(orientation, write_alloc,
                                                policy, tmp_path):
    """Nothing is evicted, so the policy must not matter."""
    s = run_sim(orientation, "memory", write_alloc, tmp_path, policy)

    # each line of A, B and C is fetched from memory exactly once
    assert s["CacheUnit: L1 misses"] == LINES_A + LINES_B + LINES_C
    assert s["CacheUnit: L2 accesses"] == s["CacheUnit: L1 misses"]
    assert s["CacheUnit: L2 misses"] == s["CacheUnit: L1 misses"]
    assert s["CacheUnit: mem reads"] == s["CacheUnit: L1 misses"]
    assert s["CacheUnit: L1 hits"] + s["CacheUnit: L1 misses"] == \
        s["CacheUnit: L1 accesses"]

    # nothing is ever evicted, so nothing is written back
    assert s["CacheUnit: L1 writebacks"] == 0
    assert s["CacheUnit: L2 writebacks"] == 0
    assert s["CacheUnit: mem writes"] == 0

    # with B from memory the only cycles outside the cache are the MACs
    assert s["Simulation: Total cycles"] == \
        s["CacheUnit: total access cycles"] + MACS * MULACC_COST
    assert s["PrngFifo: pops"] == 0


@pytest.mark.parametrize("orientation, b_loads", [
    # output stationary: B is loaded for every (row, col, k) register step
    ("output", N_TILES * REGS_PER_TILE_SIDE ** 2 * REGS_ALONG_K),
    # weight stationary: once per (k, col), reused across the rows
    ("weight", N_TILES * REGS_PER_TILE_SIDE * REGS_ALONG_K),
])
def test_fifo_b_bypasses_the_cache(orientation, b_loads, tmp_path):
    s = run_sim(orientation, "fifo", False, tmp_path)

    # every B register load is a FIFO pop instead of a cache access
    assert s["PrngFifo: pops"] == b_loads

    # the cache sees only A, C and the seed reads, which all fall in the first
    # line of B
    assert s["CacheUnit: L1 misses"] == LINES_A + LINES_C + 1
    assert s["CacheUnit: mem reads"] == s["CacheUnit: L1 misses"]
    assert s["CacheUnit: L1 writebacks"] == 0


# -- invalid cache geometry ------------------------------------------------------

def run_sim_raw(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path)}
    return subprocess.run([str(SIM), *args], cwd=tmp_path, env=env,
                          capture_output=True, text=True)


@pytest.mark.parametrize("cache, message", [
    # block mem l1_size l1_cyc l1_assoc l2_size l2_cyc l2_assoc
    (["6", "100", "8", "4", "3", "16", "20", "3"],
     "L1: 4 lines (256 B) don't split into whole sets of 8 ways"),
    (["6", "100", "14", "4", "3", "8", "20", "3"],
     "L2: 4 lines (256 B) don't split into whole sets of 8 ways"),
    (["6", "100", "14", "4", "3", "16", "20", "-2"], "or -1 for fully associative"),
    (["6", "100", "1000", "4", "-1", "0", "20", "3"],
     "L1: size 1000 B is not a whole number of 64 B lines"),
    (["6", "100", "24576", "4", "3", "0", "20", "3"],
     "L1: 24576 B / (8 ways x 64 B) = 48 sets, which is not a power of two"),
    (["25", "100", "30", "4", "3", "0", "20", "3"], "too large"),
], ids=["l1-zero-sets", "l2-zero-sets", "assoc-below-minus-one",
        "not-whole-lines", "sets-not-power-of-two", "block-too-large"])
def test_invalid_cache_from_cli_is_rejected(cache, message, tmp_path):
    r = run_sim_raw(["-c", *cache], tmp_path)
    assert r.returncode != 0
    assert message in r.stderr + r.stdout
    assert "SIMULATION STATS" not in r.stdout


def test_invalid_cache_from_config_is_rejected(tmp_path):
    (tmp_path / "config.toml").write_text(
        "[cache]\nblock_size = 6\nl1_size = 8\nl1_assoc = 3\n")
    r = run_sim_raw([], tmp_path)
    assert r.returncode != 0
    assert "L1: 4 lines (256 B) don't split into whole sets of 8 ways" \
        in r.stderr + r.stdout


# -- sizes > 30 are bytes, assoc -1 is fully associative -------------------------

def test_assoc_minus_one_is_fully_associative(tmp_path):
    """16 KB with -1 must behave exactly like 16 KB with 2^8 = 256 ways."""
    full = run_sim("weight", "memory", False, tmp_path,
                   cache=["6", "100", "14", "4", "-1", "0", "20", "3"])
    ways = run_sim("weight", "memory", False, tmp_path,
                   cache=["6", "100", "14", "4", "8", "0", "20", "3"])
    assert full == ways


def test_size_in_bytes_equals_log2_size(tmp_path):
    """16384 (bytes) and 14 (log2) are the same cache."""
    log2 = run_sim("output", "memory", True, tmp_path, cache=DEFAULT_CACHE)
    byts = run_sim("output", "memory", True, tmp_path,
                   cache=["6", "100", "16384", "4", "3", "65536", "20", "3"])
    assert log2 == byts


def test_non_power_of_two_fully_assoc_from_config(tmp_path):
    """A 24 KB fully associative L1 (384 ways, one set), as in the roofline
    experiment's L1/FIFO splits."""
    (tmp_path / "config.toml").write_text(
        "[cache]\nblock_size = 6\nl1_size = 24576\nl1_assoc = -1\nl2_size = 0\n")
    r = run_sim_raw([], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "SIMULATION STATS" in r.stdout


def test_minimal_valid_cache_is_accepted(tmp_path):
    """size == assoc + block: exactly one set, the smallest legal cache."""
    r = run_sim_raw(["-m", "8", "-k", "8", "-n", "8", "--th", "4", "--tw", "4",
                     "-B", "memory", "-c", "6", "100", "9", "4", "3", "9", "20", "3"],
                    tmp_path)
    assert r.returncode == 0, r.stderr
    assert "SIMULATION STATS" in r.stdout


def test_unknown_policy_from_cli_is_rejected(tmp_path):
    r = run_sim_raw(["--policy", "plru"], tmp_path)
    assert r.returncode != 0
    assert "plru" in r.stderr + r.stdout


def test_unknown_policy_from_config_is_rejected(tmp_path):
    (tmp_path / "config.toml").write_text('[cache]\npolicy = "lur"\n')
    r = run_sim_raw([], tmp_path)
    assert r.returncode != 0
    assert 'unknown cache policy "lur"' in r.stderr + r.stdout


# -- L1 only (l2_size = 0) ---------------------------------------------------------

@pytest.mark.parametrize("orientation", ["output", "weight"])
def test_l2_size_zero_means_l1_only(orientation, tmp_path):
    s = run_sim(orientation, "memory", False, tmp_path, cache=NO_L2_CACHE)

    assert not any(name.startswith("CacheUnit: L2") for name in s)
    # every L1 miss goes straight to memory
    assert s["CacheUnit: L1 misses"] == LINES_A + LINES_B + LINES_C
    assert s["CacheUnit: mem reads"] == s["CacheUnit: L1 misses"]
    # L1 hit latency 4, memory 100, nothing in between
    assert s["CacheUnit: total access cycles"] == \
        s["CacheUnit: L1 accesses"] * 4 + s["CacheUnit: mem reads"] * 100


def test_l1_size_zero_is_rejected(tmp_path):
    r = run_sim_raw(["-c", "6", "100", "0", "4", "3", "16", "20", "3"], tmp_path)
    assert r.returncode != 0
    assert "L1: size can't be 0, L1 must exist" in r.stderr + r.stdout


# -- FIFO capacity in elements ---------------------------------------------------

def test_fifo_capacity_is_in_elements(tmp_path):
    """A tile's B block is K x TILE = 128 elements. 16384 and 20000 (not a power
    of two) never fill up; 16 elements (one register) makes the consumer wait
    on generation much more. In log2 units 16 would be 65536 and change
    nothing, so this also pins the unit."""
    big = run_sim("weight", "fifo", False, tmp_path, fifo_capacity=16384)
    odd = run_sim("weight", "fifo", False, tmp_path, fifo_capacity=20000)
    tiny = run_sim("weight", "fifo", False, tmp_path, fifo_capacity=16)

    assert odd["PrngFifo: stall_cycles"] == big["PrngFifo: stall_cycles"]
    assert tiny["PrngFifo: stall_cycles"] > big["PrngFifo: stall_cycles"]
