# Running experiments

```
python -m experiments.run --list                 # list discovered experiments
python -m experiments.run <name> [<name> ...]    # run one or more by name
python -m experiments.run --all                  # run every discovered experiment
```

`run.py` will build `./asymm` on first invocation if it is missing.

# The experiments (v45-results)

Every experiment emits six views of its sweep — `cycles` (mulacc recorded),
`cycles_nomulacc`, `l1_traffic`, `l2_traffic`, `dram_traffic`,
`total_traffic` — plus its own analysis plots and a `README.md` report.
Plot captions list only config values that differ from `default.config`.

**empirical-tile-sweeps** — 96³ matmul, C-stationary; sweeps the full
`TILE_M × TILE_N × TILE_K` grid over three precision configs and plots each
metric against the C-tile aspect ratio (best value per ratio).

**empirical-tile-sweeps-96** — the same sweep with tile dims including 96,
so matrix-spanning strips (degenerate tiles) compete too.

**empirical-l1-size-sweeps** — best tile shape per L1 size (4K–64K):
how much cache the workload actually needs, per precision.

**empirical-assoc-sweeps** — best tile per associativity (1–16-way, L1=L2):
capacity misses vs conflict misses at fixed size.

**empirical-line-size-sweeps** — best tile per cache-line size (16–128 B):
spatial-locality payoff vs false-sharing of narrow tile rows.

**empirical-l1-size-sweeps-bstationary / empirical-assoc-sweeps-bstationary /
empirical-line-size-sweeps-bstationary** — the same three hardware sweeps
under B-stationary loop ordering.

**paper-traffic-model** — tests the read/write traffic formula of
`../Multiplication_by_a_Random_Matrix.pdf` at the L1 boundary: measured L1
bytes in/out vs the closed-form prediction across constant-area tile
families, ρ ∈ {1…1/8}, ideal (fully-assoc) vs realistic (8-way) caches,
with the paper's streaming order (`--outer_products`). Checks minimum
location `T_N/T_M = 1/ρ` and the savings-vs-square-tile ratios.

**paper-per-matrix-balance** — the mechanism behind the paper's optimum:
region-tagged traces decompose L1 traffic per matrix; the two input terms
must balance (A bytes = B bytes) exactly at the predicted optimum, and
writes must be C-only.

**paper-model-validity** — where the paper's "C block occupies fast memory"
idealization breaks on a real cache: traffic excess vs C-tile budget as a
fraction of L1, across sizes and associativities.

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

## `Flags(b_source, stationary, three_d_reg, mulac_norecord, outer_products, trace_level, trace_file, assembler_input)`

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
    l1: CacheStats          # hit_rate, tag_lookups, line_fills, evicts,
    l2: CacheStats          #   writebacks, bytes_in, bytes_out
    dram: DramStats         # bytes_read, bytes_written
    cycles: int
    prng: Optional[PrngStats]            # populated when --Bsource prng_mem
    prng_fifo: Optional[PrngFifoStats]   # populated when --Bsource prng_fifo
    unused_options: list[str]            # config keys ignored under current flags
```

## `run_grid_dual(...) -> list[DualResult]`

`run_grid` twice per cell — once with `--mulac_norecord` (the `traffic`
metrics) and once with mulacc recorded (the `cycles` metrics).

## `plot_metric_family(cells, *, out_dir, base_name, title, caption, xlabel) -> list[Path]`

Writes `<base_name>_<metric>.png` for the six standard metric views from a
list of `Cell(x, series, traffic, cycles)`.

## `describe_changes(overrides, default_text, *, extras={}) -> str`

Caption line listing only the config keys whose values differ from
`default.config`.

## `paper_model`

Closed-form traffic predictions from `Multiplication_by_a_Random_Matrix.pdf`
(word-granular and line-aware reads/writes, optimal ratio, savings).

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
