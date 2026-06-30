# policy-pareto — Writeup

## Hypothesis

LRU and FIFO bracket the "useful" replacement-policy space for matmul; MRU
is wrong almost everywhere; Random is a sanity baseline. Concretely:

- **LRU and FIFO cluster.** They differ only in whether hits are promoted to
  MRU. For matmul the lines that *aren't* reused inside an inner loop are
  predictable (B under C-stationary, A under B-stationary), so LRU's
  MRU-protection bug ("recently touched B pollutes the set") only matters
  in a narrow regime.
- **MRU is catastrophic on the reused matrix.** Promoting on hit and then
  evicting the MRU is exactly wrong for A and C (high reuse) under
  C-stationary. So MRU should be uniformly dominated, *except possibly*
  when B is FIFO-sourced (no cache reuse of B at all) and the workload's
  whole working set is reused per-block — in that regime, evicting the most
  recently used line of B (which won't come back) might match FIFO.
- **Random sits between** depending on associativity.

The interesting question this experiment can decide: **is there any
configuration (tile, B source, stationary mode, precision) where MRU or
Random *beats* both LRU and FIFO?** If yes, we have a counterintuitive
finding worth reporting. If no, the codebase's existing LRU vs FIFO finding
(see top-level `README.md`) is the whole story.

## Setup

- **Workload.** `m = n = k = 96`, A=8 B=2 *Asymmetric* + A=8 B=8 *Symmetric*
  for contrast. `TILE_K = 96` fixed.
- **Compute.** `--3dregisters`, `REG = 4`.
- **Cache.** L1 = 16 KB / L2 = 64 KB, 64 B lines, 8-way. Realistic
  constrained regime where the policy actually matters.
- **Sweep axes.** policy ∈ {LRU, FIFO, MRU, Random} ×
  `TILE_M, TILE_N ∈ {4, 8, 12, 16, 24, 32, 48, 96}` (64 pairs) ×
  precision ∈ {Symmetric, Asymmetric} ×
  stationary ∈ {C, B} ×
  B-source ∈ {mem, prng_fifo}.
- **Total.** 4 · 64 · 2 · 2 · 2 = **2048 cells**.

The set is large but every cell is fast (each is one ~ms run + a result
cache hit on rerun).

## What we plot

`pareto_scatter.png`: scatter of `cycles` vs `l1.line_fills`, one point per
cell. Color = policy; marker = stationary; subplot grid = (B-source, precision).
Pareto front per policy overlaid.

`policy_winners.md`: count, per `(precision, stationary, B-source)`
configuration, how often each policy is the cycle-minimum over all 64 tile
shapes. The MRU/Random win count is the interesting number.

`policy_dispersion.png`: violin plot of `cycles` per policy in each
configuration — shows how much variance the policy choice adds vs the tile
shape.

## Pass / fail criteria

- **Expected dominant finding.** LRU and FIFO each win some configs; MRU
  never wins; Random rarely wins. Median cycle gap between LRU and FIFO is
  ≲ 5 % in symmetric configurations and a few × that under prng_fifo +
  asymmetric (the regime where the v5 README claims FIFO beats LRU by ~3 %).
- **Surprise finding to look for.** If MRU wins any config, dig into the
  specific tile shape and stationary mode — that's a real result.
- **Failure modes.** All four policies producing identical numbers would
  indicate the workload is too easy (everything fits) or the cache size is
  too generous; bump L1 down.

## Reproduction

```sh
python3 -c "from experiments.v45_results.policy_pareto import experiment; experiment.run()"
```

No new C++ — the `Set` refactor (see commit `4a7b272`) routes
`L1_REPLACEMENT_POLICY` / `L2_REPLACEMENT_POLICY` directly into Set's
policy field, dispatching internally.
