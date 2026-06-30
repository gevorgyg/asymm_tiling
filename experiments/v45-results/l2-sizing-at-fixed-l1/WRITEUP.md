# l2-sizing-at-fixed-l1 — Writeup

## Hypothesis

Every v5 cache sweep co-varies L1 and L2 (L2 is always a fixed multiple of
L1). That conflates two different things: capacity for the working set, and
capacity for the writeback / spillover stream. Holding L1 fixed and sweeping
L2 independently teaches us which of the two is the bottleneck.

Specifically: under C-stationary matmul, the working set of one
`(T_M, T_N, T_K)` tile is dominated by the C-tile (which is held across the
K-reduction), with A and B streamed past. If the C-tile fits in L1 already,
L2 only catches:

- dirty C-tile writebacks (the C-tile being evicted before its write-out);
- compulsory misses (cold A/B/C lines that DRAM still has to serve once);
- A/B lines that *did* fit in L2 briefly but didn't fit in L1.

So we expect the **`cycles`-vs-`L2/L1`-ratio curve to bend** at the
smallest L2 that holds everything L1 can't, i.e. the working set minus the
C tile. Beyond that, adding L2 gives diminishing returns.

## Setup

- **Workload.** `m = n = k = 96`, C-stationary, `--3dregisters`, REG = 4.
- **L1 fixed at three values.** `L1 ∈ {8 KB, 16 KB, 32 KB}`. For each, sweep
  `L2 / L1 ∈ {1, 2, 4, 8, 16, 64}`.
- **Tile shapes.** Sweep `T_M, T_N ∈ {4, 8, 12, 16, 24, 32, 48}` (drop 96 so
  the working set actually pressures the cache at the smaller L1s);
  `T_K = 96` fixed.
- **Precisions.** Symmetric Double + Asymmetric, for contrast.
- **Total cells.** `3 · 6 · 49 · 2 ≈ 1764`.

## What we plot

`cycles_vs_l2.png`: one curve per `(L1_size, precision)`. X axis =
`log₂(L2 / L1)`. Y axis = cycles at the **best tile shape under that
(L1, L2) combination** (so we're tracking the achievable minimum, not a
fixed tile).

`dram_vs_l2.png`: same X axis; Y = DRAM bytes at the best tile. The
inflection here is the structural one — it tells you when L2 stops moving
DRAM bytes regardless of compute cost.

`elbow_table.md`: per `(L1, precision)`, the L2/L1 ratio above which adding
L2 saves less than 5 % of cycles. That's the "elbow" — the smallest L2 you
actually need.

## Pass / fail criteria

- **Expected.** The elbow is at a small L2/L1 ratio (probably 2-4) for
  smaller L1s and shrinks (gets closer to ratio 1) as L1 grows. Past the
  elbow the curve is flat to within ~1 %.
- **Surprise to watch for.** A *non-monotone* curve would mean L2 is hurting
  for some sizes (an unlikely but possible aliasing artifact). A flat curve
  across all L2 sizes would mean L2 is doing nothing — i.e., even at the
  smallest L2, everything that misses L1 also misses L2.

## Reproduction

```sh
python3 -c "from experiments.v45_results.l2_sizing_at_fixed_l1 import experiment; experiment.run()"
```
