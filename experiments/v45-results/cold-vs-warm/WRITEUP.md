# cold-vs-warm — Writeup

## Hypothesis

Every one-shot sweep in `v5-results` reports a *pooled* hit rate across the
entire matmul. That pooled number conflates two regimes:

- **Prologue.** Compulsory misses on every first-touch of any matrix line —
  unavoidable.
- **Steady state.** What the inner loop actually achieves once the working
  set is loaded.

For small matrices the prologue dominates the run; for large matrices the
steady state does. Without separating them we can't tell whether a tile
shape's apparent advantage is a real steady-state win or just a smaller
prologue.

**Method.** Run the same matmul `N` times back to back (concatenate the
assembly file). The simulator's state persists across the concatenated stream
because it's one `--assembler_input` call. Then:

```
   pooled_hit_rate(N)  ≈  prologue_hit_rate(1) · (1/N)   +   steady_hit_rate · ((N-1)/N)
```

Solve for `steady_hit_rate` from `N=1` and `N=large`. Plot pooled rate vs N;
plateau height is the steady-state hit rate.

## Setup

- **Workload.** `m = n = k = 96`, C-stationary, `--3dregisters`, REG = 4.
- **Cache.** Constrained, 16 KB L1 / 64 KB L2 — the interesting regime.
- **Sweep.** `N ∈ {1, 2, 4, 8, 16}` (how many copies of the assembly are
  concatenated). For each N, sweep four representative tile shapes:
  `(16, 16)` square, `(8, 32)` paper-ratio-4, `(48, 12)` paper-ratio-0.25,
  `(96, 96)` "fits-everything". Precisions: Asymmetric only.

The repeat is done by reading the `.matv` assembly file emitted by the
generator and concatenating it `N` times, then running with
`--assembler_input`.

## What we plot

`hit_rate_vs_repeats.png`: pooled L1 hit rate vs N for each tile shape.
The asymptote is the steady-state hit rate.

`prologue_vs_steady.png`: bar chart per tile shape: `prologue_hit_rate`
(N=1) and inferred `steady_hit_rate`. Side-by-side comparison lets the
reader see how much the small-matrix regime distorts the picture.

## Pass / fail criteria

- **Expected.** Pooled rate at N=1 is meaningfully lower than the
  asymptotic plateau (gap reflects prologue weight). Curves saturate by
  N=8 or so.
- **Surprise.** If the curves *don't* saturate (or saturate above 99 % for
  everything), the working set repeats but the simulator still treats every
  pass as cold somehow — sanity-check on the cache reset behavior.

## Reproduction

```sh
python3 -c "from experiments.v45_results.cold_vs_warm import experiment; experiment.run()"
```

Implementation note: the assembly-concat helper lives in `experiment.py`
itself, since this is the only experiment that needs it. If a second one
ever wants it, promote it to `harness/assembly.py`.
