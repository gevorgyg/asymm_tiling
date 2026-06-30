# paper-rho-continuum-unconstrained — Writeup

## Hypothesis (H1)

For a C-stationary matmul `C = A·B` with one cheap input matrix, the analysis
in §4.3 of [arxiv 1702.02017](https://arxiv.org/pdf/1702.02017.pdf), extended
to mixed precision, predicts that the optimal C-tile aspect ratio is

```
   T_N / T_M  =  1 / ρ,            ρ = bits(cheap) / bits(expensive)
```

with total DRAM traffic `mnk · 2√(ρ/M) + mn` and speedup vs square tiles

```
   speedup(square -> opt)  =  (1 + ρ) / (2√ρ).
```

We claim: **when the C tile fits comfortably in L1 (the "unconstrained"
regime that isolates the analytical claim from cache-reload artifacts), the
empirical DRAM minimum sits at `T_N / T_M = 1/ρ` for every `ρ` we sweep, and
the measured speedup vs square matches the analytical formula within a few
percent.**

This is the *clean* validation. The companion experiment
[`paper-rho-shift-constrained`](../paper-rho-shift-constrained/) measures
the leftward shift introduced by cache pressure; the orthogonal
[`paper-per-matrix-balance`](../paper-per-matrix-balance/) verifies *how* the
optimum balances `A` and `B` traffic term by term using traces.

## Setup

- **Workload.** `m = n = k = 512`, `T_K = 64` fixed, C-stationary.
- **Compute.** `--3dregisters` with `REG_M = REG_N = REG_K = 4`; B source =
  `mem` (no PRNG alignment to worry about for cheap `B`).
- **Cache.** L1 = 256 KB, L2 = 512 KB, both with 64 B lines, 8-way LRU,
  write-back. `M = L1 / sizeof(C_entry) = 32 K` C-entries; `mn = 262 144`,
  so `mn / M = 8` — the C tile fits in fast memory comfortably, but the
  whole matrix does not, so the per-block analysis bites.
- **Precisions.** `A_PRECISION_BYTES = 8` fixed;
  `B_PRECISION_BYTES ∈ {8, 4, 2, 1}` → `ρ ∈ {1, 1/2, 1/4, 1/8}`.
- **Tile grid.** `T_M, T_N ∈ {4, 8, 16, 32, 64, 128, 256}` — divisors of
  512 that are also multiples of `REG_M = 4`. 49 pairs × 4 ρ = 196 cells.

## What we plot

`dram_vs_aspect_ratio.png`: one curve per ρ. X axis = `log₂(T_N / T_M)`.
Y axis = DRAM bytes (`l2.line_fills · L2_LINE_SIZE`). At each ratio, take the
minimum over (T_M, T_N) pairs that share that ratio. Vertical dashed line per
ρ at `log₂(1/ρ)` — the predicted optimum.

`speedup_table.md`: for each ρ, the empirical
`dram(square) / dram(opt)` vs the analytical `(1+ρ) / (2√ρ)`.

## Pass / fail criteria

- **Pass.** Each curve's minimum sits within one tile-grid step of the
  predicted vertical, and the measured speedup is within ±5 % of analytical.
- **Fail interpretation.** If the minima are not at `1/ρ`, either the
  unconstrained assumption is itself violated (compulsory misses or write
  amplification dominate), or `T_K = 96` is too small (the per-block
  analysis assumes `k → ∞`).
