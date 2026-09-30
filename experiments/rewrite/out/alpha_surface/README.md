# alpha_surface: rewrite vs pre-rewrite

Re-run of the alpha experiments (pre-rewrite, math-model-no-l2):
e6-tn-independence, e3-alpha-calibration, e-l1size-regime.

Slides "Calibration: Building the alpha Table", the alpha heatmap / TN
dependence charts and the L1-size regime chart. B-stationary, B from the
FIFO, M=192, N=K=256, 4-byte elements, fully associative L1, no L2, mulacc
not counted. alpha = cycles / MNK.

Absolute alpha can't match: the old sim charged cache latency per element,
the rewrite per line (see old_results.py). So this compares
  - L1 traffic (old line_fills vs new L1 misses), which should match;
  - the shape of alpha: the cliff position per TN / per L1 size and the
    rank correlation of all cells;
  - E6's own check: does the gc=0 alpha table predict the best TM at gc=50
    (T = max(alpha, gc/TM), same safe() filter as the old experiment)?

run:  .venv/bin/python experiments/rewrite/alpha_surface.py

## Traffic

- **e6**: L1 misses identical in 70/80 cells, worst |diff| 4.30%
- **e3**: L1 misses identical in 17/20 cells, worst |diff| 1.37%
- **l1size**: L1 misses identical in 138/160 cells, worst |diff| 4.30%

## Shape of alpha (gc = 0)

- Spearman rank correlation old vs new over all 220 gc=0 cells: **0.986**
- new/old alpha ratio: min 0.24, median 0.33, max 0.63

### Cliff position per TN (e6, first TM with alpha > 1.5x the row minimum)

| TN | old cliff TM | new cliff TM |
|---|---|---|
| 4 | 16 | 16 |
| 8 | none | 16 |
| 16 | none | 16 |
| 32 | 96 | 96 |
| 64 | 64 | 48 |

### Cliff position per L1 size (l1size, TN = 32)

| L1 | old cliff TM | new cliff TM |
|---|---|---|
| 8 KB | 48 | 48 |
| 16 KB | 96 | 96 |
| 32 KB | none | none |
| 64 KB | none | none |

## E6: does the gc=0 table predict TM* at gc=50?

| TN | old predicted | old empirical | new predicted | new empirical |
|---|---|---|---|---|
| 4 | 12 | 12 | 96 | 96 |
| 8 | 12 | 12 | 96 | 96 |
| 16 | 96 | 96 | 96 | 96 |
| 32 | 64 | 64 | 64 | 64 |
| 64 | 32 | 32 | 32 | 32 |

Prediction correct: old 5/5, new 5/5.

## alpha(TM, TN) at gc = 0 (e6): old → new (ratio)

| TM \ TN | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|
| 8 | 3.40 → 0.86 (0.25×) | 3.40 → 0.85 (0.25×) | 3.40 → 0.85 (0.25×) | 3.40 → 0.85 (0.25×) | 3.40 → 0.85 (0.25×) |
| 12 | 3.32 → 0.85 (0.26×) | 3.31 → 0.85 (0.26×) | 3.31 → 0.85 (0.26×) | 3.31 → 0.85 (0.26×) | 3.44 → 0.96 (0.28×) |
| 16 | 6.05 → 3.63 (0.60×) | 4.64 → 2.21 (0.48×) | 3.93 → 1.51 (0.38×) | 3.58 → 1.15 (0.32×) | 3.40 → 0.98 (0.29×) |
| 24 | 6.01 → 3.62 (0.60×) | 4.60 → 2.21 (0.48×) | 3.89 → 1.50 (0.39×) | 3.54 → 1.15 (0.33×) | 3.36 → 0.98 (0.29×) |
| 32 | 5.98 → 3.62 (0.60×) | 4.57 → 2.21 (0.48×) | 3.87 → 1.50 (0.39×) | 3.52 → 1.15 (0.33×) | 3.34 → 0.97 (0.29×) |
| 48 | 5.96 → 3.61 (0.61×) | 4.55 → 2.20 (0.48×) | 3.85 → 1.50 (0.39×) | 3.50 → 1.15 (0.33×) | 4.39 → 1.51 (0.34×) |
| 64 | 5.95 → 3.61 (0.61×) | 4.54 → 2.20 (0.49×) | 3.84 → 1.50 (0.39×) | 3.48 → 1.15 (0.33×) | 8.87 → 3.74 (0.42×) |
| 96 | 5.94 → 3.61 (0.61×) | 4.53 → 2.20 (0.49×) | 3.83 → 1.50 (0.39×) | 9.03 → 3.92 (0.43×) | 8.88 → 3.74 (0.42×) |
