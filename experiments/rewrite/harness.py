"""Run the rewritten simulator (build/sim) over parameter grids.

    from harness import Params, run_many
    stats = run_many([Params(tile_h=tm) for tm in (8, 16, 32)], "results.json")

Every run passes all options on the command line and runs in an empty temp
directory, so no config.toml is picked up. Results are cached in a JSON file
keyed by the parameters; the cache is dropped when build/sim changes (sha256 of
the binary), so a rebuild never mixes old and new numbers. Runs execute in
parallel, but only the calling thread writes the cache file.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "build" / "sim"
OUT = Path(__file__).resolve().parent / "out"


def out_dir(name: str) -> Path:
    """experiments/rewrite/out/<name>/, for results.json and README.md."""
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def pct(new: float, old: float) -> str:
    """Relative difference new vs old, e.g. '+1.25%'."""
    return f"{(new - old) / old:+.2%}" if old else "n/a"


@dataclass(frozen=True)
class Params:
    """One simulator run. Defaults reproduce the setup shared by the
    presentation experiments (pre-rewrite, math-model-no-l2 and v55):
    M=192, N=K=256, 4-byte A/B/C, 16 KB fully associative L1, no L2,
    L1 4 cycles, memory 180 cycles, mulacc not counted, write-back +
    write-allocate, FIFO read 2 cycles, 8-byte seeds."""

    orientation: str = "weight"   # weight (B-stationary) | output (C-stationary)
    b_source: str = "fifo"        # fifo | memory

    m: int = 192
    k: int = 256
    n: int = 256
    small_precision: int = 4      # B element bytes
    ratio: int = 1                # A and C element bytes = small_precision * ratio
    aligned: bool = False         # pad rows / bases to whole cache lines

    tile_h: int = 16              # TM
    tile_w: int = 32              # TN
    reg_dim: int = 4
    mulacc_cost: int = 0

    # cache as -c takes it: sizes and assoc log2, a size > 30 is bytes,
    # l2_size = 0 -> no L2, assoc -1 -> fully associative
    block_size: int = 6
    mem_cycles: int = 180
    l1_size: int = 14
    l1_cycles: int = 4
    l1_assoc: int = 8             # 2^8 = 256 ways = fully associative at 16 KB
    l2_size: int = 0
    l2_cycles: int = 14
    l2_assoc: int = 3
    write_alloc: bool = True
    policy: str = "lru"

    fifo_capacity: int = 16384    # elements
    gen_cost: int = 0
    fifo_access: int = 2          # cycles per pop
    seed_size: int = 8

    def args(self) -> list[str]:
        return [
            "-o", self.orientation, "-B", self.b_source,
            "-m", str(self.m), "-k", str(self.k), "-n", str(self.n),
            "-p", str(self.small_precision), "-r", str(self.ratio),
            *(["--aligned"] if self.aligned else []),
            "--th", str(self.tile_h), "--tw", str(self.tile_w),
            "--rd", str(self.reg_dim), "--mc", str(self.mulacc_cost),
            "-c", *map(str, (self.block_size, self.mem_cycles,
                             self.l1_size, self.l1_cycles, self.l1_assoc,
                             self.l2_size, self.l2_cycles, self.l2_assoc)),
            "--write-allocate" if self.write_alloc else "--no-write-allocate",
            "--policy", self.policy,
            "--fc", str(self.fifo_capacity), "--fg", str(self.gen_cost),
            "--fa", str(self.fifo_access), "-s", str(self.seed_size),
        ]

    def key(self) -> str:
        # aligned is left out while False so the keys of runs cached before
        # the option existed still match
        d = asdict(self)
        if not d["aligned"]:
            del d["aligned"]
        return json.dumps(d, sort_keys=True)

    def fully_assoc(self) -> Params:
        """Same L1 size, one set."""
        return replace(self, l1_assoc=-1)


def parse_stats(stdout: str) -> dict[str, float]:
    stats = {}
    for line in stdout.splitlines():
        name, sep, value = line.partition("|")
        if sep and name.strip() != "Metric":
            stats[name.strip()] = float(value)
    return stats


def run(params: Params, workdir: Path) -> dict[str, float]:
    env = {**os.environ, "HOME": str(workdir), "XDG_CONFIG_HOME": str(workdir)}
    proc = subprocess.run([str(SIM), *params.args()], cwd=workdir, env=env,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"sim failed for {params}:\n{proc.stderr}{proc.stdout}")
    return parse_stats(proc.stdout)


def sim_sha() -> str:
    return hashlib.sha256(SIM.read_bytes()).hexdigest()


def run_many(params: list[Params], cache_file: str | Path,
             jobs: int | None = None) -> list[dict[str, float]]:
    """Stats for every Params, in order. Cached runs are not repeated."""
    cache_file = Path(cache_file)
    sha = sim_sha()

    cache: dict[str, dict[str, float]] = {}
    if cache_file.exists():
        stored = json.loads(cache_file.read_text())
        if stored.get("sim_sha") == sha:
            cache = stored["results"]

    todo = list({p.key(): p for p in params if p.key() not in cache}.values())
    if todo:
        print(f"{cache_file.parent.name}: running {len(todo)} "
              f"({len(params) - len(todo)} cached)")
        with tempfile.TemporaryDirectory() as tmp, \
                ThreadPoolExecutor(max_workers=jobs or os.cpu_count()) as pool:
            for p, stats in zip(todo, pool.map(lambda p: run(p, Path(tmp)), todo)):
                cache[p.key()] = stats
        cache_file.write_text(json.dumps({"sim_sha": sha, "results": cache},
                                         indent=1))

    return [cache[p.key()] for p in params]
