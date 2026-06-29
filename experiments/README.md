# Running experiments

```
python -m experiments.run --list                 # list discovered experiments
python -m experiments.run <name> [<name> ...]    # run one or more by name
python -m experiments.run --all                  # run every discovered experiment
```

`run.py` will build `./asymm` on first invocation if it is missing.

Each experiment writes:
- `<experiment-dir>/results.json` — on-disk cache, one entry per sweep cell
- `<experiment-dir>/README.md` — the markdown report

Rerunning an experiment after a cache hit is fast: cells whose effective
config + flags hash matches an existing entry are skipped. See
[Caching](#caching) below for what counts as "the same cell."

---

# Writing a new experiment

The whole template is ~50 lines. Copy any existing
`v45-results/*/experiment.py` and edit the four declarations at the top.

```python
"""One-line description of the sweep."""

from pathlib import Path
from experiments.harness import (
    Flags, Result, run_grid, top_bottom_table, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# Hardware + workload constants -- everything that does NOT vary across cells.
# This is the only place this experiment touches matrix shape / cache geometry.
BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
}

# Optional: per-experiment precision configs. Drop if a single precision suffices.
PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
]

DIMS = [8, 16, 32]


def run() -> None:
    base_config = (workspace_root() / "default.config").read_text()
    flags = Flags(b_source="mem", stationary="C", three_d_reg=True)

    blocks: list[str] = []
    for prec_name, prec_over in PRECISIONS:
        print(f"\n--- {prec_name} ---")
        results: list[Result] = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base_config,
            base_overrides={**BASE_OVERRIDES, **prec_over},
            sweep_axes={"TILE_M": DIMS, "TILE_N": DIMS, "TILE_K": DIMS},
            flags=flags,
        )
        blocks.append(top_bottom_table(
            title=prec_name,
            results=results,
            axis_keys=["TILE_M", "TILE_N", "TILE_K"],
        ))

    write_report(
        EXPERIMENT_DIR / "README.md",
        title="Your experiment title",
        blocks=blocks,
    )
```

Every experiment script must define a top-level `run()`; the dispatcher
invokes it.

---

# Harness API

## `Flags(b_source, stationary, three_d_reg, mulac_norecord, trace_level, trace_file, assembler_input)`

Mirrors the C++ CLI surface (see the top-level `README.md` for option
semantics). Any new flag added there must grow a `Flags` field here too;
this is the only place Python code knows the CLI vocabulary.

## `run(config_path, flags=Flags()) -> Metrics`

Runs `./asymm --config <path> <flags>` once and returns parsed metrics.
Raises `RuntimeError` on non-zero exit.

## `run_grid(*, experiment_dir, base_config_text, base_overrides, sweep_axes, flags, cache_path=None) -> list[Result]`

Runs one simulation per Cartesian-product cell of `sweep_axes`. Returns a
list of `Result(overrides=dict, metrics=Metrics)`. Cells already in the
cache are skipped.

## `render_config(base_text, overrides) -> str`

Returns a config-file string with `overrides` substituted into a base
template. Comments and unspecified keys are preserved; keys not present
in the base are appended at the end.

## `top_bottom_table(title, results, *, axis_keys, sort_by=..., top_n=5, bottom_n=3) -> str`

Returns a markdown block with a `## title` heading and top-N / bottom-N
tables sorted by `sort_by` (default: cycles ascending). `axis_keys` are the
override keys to pull into the first columns of the table. Caller can
provide a custom `columns` callable for non-default metric columns.

## `write_report(out_path, title, blocks)`

Writes `# title` plus the concatenation of markdown blocks to `out_path`.

## `Metrics`

```python
@dataclass
class Metrics:
    l1: CacheStats          # hit_rate, tag_lookups, line_fills, evicts
    l2: CacheStats
    cycles: int
    prng: Optional[PrngStats]            # populated when --Bsource prng_mem
    prng_fifo: Optional[PrngFifoStats]   # populated when --Bsource prng_fifo
    unused_options: list[str]            # config keys ignored under current flags
```

---

# Caching

`run_grid` persists every cell to `<experiment_dir>/results.json`. The
cache key is `sha256(canonical_config + flags_json)` where
`canonical_config` is the rendered config with two normalizations:

1. **Sorted lines** — comment/order edits don't bust the cache.
2. **Unused keys stripped** — changing e.g. `PRNG_FIFO_CAPACITY` while
   running `--Bsource mem` does not invalidate the cache. The same logic
   lives in `main.cpp::unusedConfigKeys` and prints under the
   `--- UNUSED OPTIONS ---` header at runtime.

To force a clean run, delete `results.json` in the experiment directory.

---

# Reusing the harness from ad-hoc scripts

```python
from pathlib import Path
from experiments.harness import Flags, run

m = run(
    Path("default.config"),
    Flags(b_source="prng_fifo", three_d_reg=True),
)
print(m.cycles, m.l1.hit_rate, m.prng_fifo.stalls)
```

The harness is plain Python; nothing requires running through the
dispatcher.
