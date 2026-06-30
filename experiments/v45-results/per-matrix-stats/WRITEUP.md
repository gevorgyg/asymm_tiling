# per-matrix-stats — Writeup

## Hypothesis

The aggregate `l1.hit_rate` reported by the simulator pools accesses across
A, B, and C. That makes asymmetric workloads invisible — a 90 % overall hit
rate could be (A: 99 %, B: 30 %, C: 99 %) or (A: 60 %, B: 90 %, C: 95 %),
and we can't tell. Per-matrix decomposition, derived from `--trace_level 2`
traces via `harness.trace_analysis`, surfaces the asymmetry.

Expected signature under **C-stationary**:

- **A.** Outer-loop reuse — the A tile is loaded once per outer step and
  used in the entire middle loop. Expect a very high L1 hit rate.
- **B.** Middle-loop reuse — B is loaded `N_tiles` times more often than A.
  Hit rate depends on whether B fits in L1 alongside A and C; usually
  meaningfully lower than A's.
- **C.** Inner-loop accumulator (resident across the K reduction). Expect
  near-100 % once the prologue compulsory miss is done; the only misses
  are when the C tile evicts itself.

This is the **precursor** to:
- the reuse-distance histogram you mentioned (same parser, finer-grained);
- the AM-GM balance check in
  [`paper-per-matrix-balance`](../paper-per-matrix-balance/) (same data,
  targeted to two specific cells per ρ);
- richer plots of cache pollution under different stationary modes.

## Setup

- **Workload.** `m = n = k = 96`, C-stationary, `--3dregisters`, REG = 4.
- **Cache.** Two regimes — *constrained* (L1 = 16 KB) for asymmetry to
  matter, and *roomy* (L1 = 64 KB) for comparison.
- **Sweep axes.** Precision ∈ {Symmetric Double, Asymmetric},
  `T_M, T_N ∈ {4, 8, 12, 16, 24, 32, 48}`, `T_K = 96` fixed.
  Total: `2 · 2 · 49 = 196` traced cells.
- **Trace.** Level 2; parsed via `harness.trace_analysis.parse_trace` with
  regions = `[A, B, C]` from the byte layout.

## What we plot

`hit_rate_per_matrix.png`: three curves (A, B, C) per `(regime, precision)`
panel; X axis = `log₂(T_N / T_M)`, Y axis = L1 hit rate.

`dram_share_per_matrix.png`: stacked area of `A / B / C` shares of total
DRAM bytes vs aspect ratio per `(regime, precision)`. Reveals where the
DRAM goes.

## Pass / fail criteria

- **Expected.** A and C hit rates are uniformly high (≥ 95 %) when the C
  tile fits. B hit rate is the variable one — drops sharply when B's
  per-step working set exceeds what L1 leaves over after A and C are
  pinned.
- **Surprise to watch for.** A hit rate < B hit rate would be backwards
  and suggests the generator's loop ordering doesn't actually do C-stationary
  (sanity check on the simulator).

## Reproduction

```sh
python3 -c "from experiments.v45_results.per_matrix_stats import experiment; experiment.run()"
```
