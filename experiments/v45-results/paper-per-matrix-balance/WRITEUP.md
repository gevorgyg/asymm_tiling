# paper-per-matrix-balance — Writeup

## Hypothesis (H3)

The paper's analysis minimizes `T_M + ρ·T_N` subject to `T_M·T_N = M`. By
AM–GM the minimum occurs when **both terms are equal**:

```
   T_M  =  ρ · T_N      ⇒      T_M = √(M·ρ),  T_N = √(M/ρ).
```

In DRAM-traffic terms, this is the statement that the cheap-matrix traffic
`ρ · k · T_N` and the expensive-matrix traffic `k · T_M` are equal at the
optimum. So if we decompose the total DRAM bytes into per-matrix bytes,

```
   dram_A ≈ dram_B           (at the predicted optimum T_N/T_M = 1/ρ)
   dram_A > dram_B           (at square tiles T_M = T_N — the expensive
                              matrix dominates; cheap one underused)
```

This is the *mechanism* by which the paper's tiling beats square tiling — it
re-balances the read budget so the cheap matrix soaks up the extra traffic
that the expensive matrix would have paid for. The first
[`paper-rho-continuum-unconstrained`](../paper-rho-continuum-unconstrained/)
experiment validates *that* the optimum is at `1/ρ`; this one validates *why*
by going one level deeper.

Companion experiments are in the same directory family.

## Setup

Same workload as the H1/H2 experiments (`m = n = k = 512`, `T_K = 64`,
C-stationary, `--3dregisters`, B source `mem`). Two cache regimes —
unconstrained (L1 = 256 KB) and constrained (L1 = 16 KB) — so we can also
see the H2 shift *through the trace lens*.

For each `(regime, ρ)` we run **two targeted cells**:

- The **predicted optimum** tile, i.e. the (T_M, T_N) pair from the 96 grid
  whose ratio is closest to `1/ρ`, with the smallest area among such pairs
  (so the constrained-regime cell fits).
- The **square** baseline, `T_M = T_N`, at the closest matching area.

Each cell runs at `--trace_level 2`. The level-2 trace is post-processed by
`harness.trace_analysis.parse_trace` to count `MemoryAccess` events per
matrix region (`A`, `B`, `C` regions are computed from the byte layout via
`harness.trace_analysis.matrix_regions`).

## What we plot

`per_matrix_dram.png`: a 2×4 grid of stacked-bar plots (rows = regime, cols
= `ρ`). For each cell, two bars: predicted optimum and square. Each bar
shows `A_bytes`, `B_bytes`, `C_bytes` stacked.

`balance_table.md`: numerical view —

| regime | ρ | tile | A bytes | B bytes | C bytes | A : B |

## Pass / fail criteria

- **H3 pass (unconstrained).** At the predicted optimum the ratio
  `A_bytes / B_bytes` is within ±15 % of 1. At square tiles `A_bytes` is
  meaningfully larger than `B_bytes` (cheap matrix coasts).
- **H3 pass (constrained).** At the predicted *paper* optimum, `B_bytes`
  visibly dominates `A_bytes` — the reload-amplified contribution from B
  swamps the analysis. This is the *mechanism* behind H2: the optimum
  shifts left because B traffic is what we're really paying for at small
  caches.
- **Fail interpretation.** If the balance is off in both regimes, the
  generator's loop ordering doesn't actually make `A` the outer-load matrix
  (sanity check on the simulator). If the balance is right but H1 still
  fails, the paper's assumption of `k → ∞` is more violated than we
  thought.

## Reproduction

```sh
# from project root
python3 -c "from experiments.v45_results.paper_per_matrix_balance \
            import experiment; experiment.run()"
```
