# paper-rho-shift-constrained — Writeup

## Hypothesis (H2)

Same setup as the unconstrained companion experiment, but with a small L1
that does **not** trivially hold the C tile. Under C-stationary outer loop
ordering, `B` is reloaded `N_tiles` times more often than `A` (B is in the
middle loop, A in the outer one). The paper's analysis ignores this reload
penalty — it assumes infinite reuse from fast memory. So at small L1 we
expect the empirical optimum to sit **left of** the predicted `T_N/T_M = 1/ρ`
(more rows / fewer cols → smaller B chunk → less B reload damage).

We claim: **the shift between predicted and empirical optimum, measured in
log₂ steps, is monotone in `ρ` — the smaller `ρ` (more asymmetric workload),
the larger the shift.**

Companion to:
- [`paper-rho-continuum-unconstrained`](../paper-rho-continuum-unconstrained/) (H1, baseline);
- [`paper-per-matrix-balance`](../paper-per-matrix-balance/) (H3, mechanism).

## Setup

Identical to the unconstrained experiment (m = n = k = 512, T_K = 64) except
L1 = 16 KB / L2 = 64 KB. `M = 16 K / 8 = 2 K` C-entries; `mn / M = 128`,
deep in the "matrix doesn't fit, reload penalty matters" regime.

The v5 directory `experiments/v5-results/empirical-tile-sweeps` already
shows the `ρ = 1/4` data point (predicted ratio 4 collapses to empirical 1.0
at this cache size). This experiment is the *continuum* version — sweeps ρ
to extract the shift as a curve.

## What we plot

`shift_vs_rho.png`: scatter+line of `log₂(empirical_opt) − log₂(1/ρ)` (a
**signed** displacement; negative means leftward as predicted) vs ρ on a
log axis. Expected: monotone, more negative at smaller ρ.

`dram_vs_aspect_ratio.png`: same per-ρ curve plot as the unconstrained
companion; useful for side-by-side visual comparison.

## Pass / fail criteria

- **Pass.** Shift is monotone-non-positive in ρ, and its magnitude scales
  with `log(1/ρ)` (i.e., shrinking ρ shifts more).
- **Fail interpretation.** Constant shift across ρ would mean the
  bottleneck is geometric (line-size aliasing, set conflicts) rather than
  reload-driven. A zero shift would mean either the C tile actually still
  fits effectively at 16 KB or the v5 finding doesn't reproduce.
