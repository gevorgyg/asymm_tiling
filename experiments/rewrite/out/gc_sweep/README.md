# gc_sweep: rewrite vs pre-rewrite

Re-run of pre-rewrite v5-results/math-model-no-l2/e8-gc-boundary-sweep.

Slides: "Calibrated TM* vs gc" (tm_star_trajectory), "Impact of Tile
Selection" (best_shape_per_gc, optimal_vs_square and the 20-65% / ~85% /
up to 90% speedups). B-stationary, FIFO, M=192, N=K=256, 4-byte elements,
fully associative 16 KB L1, no L2, mulacc not counted, FIFO capacity
2*K*32. alpha = cycles / MNK. Each part uses the old definition:

  1. TM*(TN, gc): best safe TM (safe = old ws_lines < 300), and whether
     the gc=0 calibration predicts it with T = max(alpha(TM,TN), gc/TM).
  2. Globally best (TM, TN) per gc, over all tiles (plot_all.py).
  3. Optimal vs square per TN in {8,16,32,64}: best TM over all tiles vs
     TM = TN, speedup = (square - optimal) / square (plot_all.py).

The rewrite's alpha is ~4x smaller (cache hits charged per line, not per
element) while gc/TM is unchanged, so every gc threshold is expected to move
down. EXTRA_GC are run in the rewrite only, to locate its transitions.

run:  .venv/bin/python experiments/rewrite/gc_sweep.py

## 1. Calibrated prediction of TM* (the 70/70 claim)

- **old** (old gc grid): 70/70 correct
- **new** (old gc grid): 70/70 correct
- **new** (old + extra gc): 110/110 correct

### Empirical TM* per (TN, gc): old / new

| gc | TN=4 | TN=8 | TN=16 | TN=32 | TN=64 |
|---|---|---|---|---|---|
| 2 | · / 12 | · / 12 | · / 12 | · / 12 | · / 8 |
| 4 | · / 12 | · / 12 | · / 12 | · / 12 | · / 8 |
| 6 | · / 12 | · / 12 | · / 12 | · / 12 | · / 8 |
| 8 | · / 12 | · / 12 | · / 12 | · / 12 | · / 12 |
| 10 | · / 12 | · / 12 | · / 12 | · / 12 | · / 12 |
| 12 | · / 12 | · / 12 | · / 12 | · / 12 | · / 32 |
| 15 | 12 | 12 | 12 | 12 / 64 | 32 |
| 20 | · / 12 | · / 12 | · / 96 | · / 64 | · / 32 |
| 25 | · / 12 | · / 12 | · / 96 | · / 64 | · / 32 |
| 30 | 12 | 12 / 96 | 12 / 96 | 12 / 64 | 32 |
| 38 | 12 | 12 / 96 | 12 / 96 | 12 / 64 | 32 |
| 42 | 12 | 12 / 96 | 12 / 96 | 64 | 32 |
| 47 | 12 / 96 | 12 / 96 | 96 | 64 | 32 |
| 50 | 12 / 96 | 12 / 96 | 96 | 64 | 32 |
| 52 | 12 / 96 | 12 / 96 | 96 | 64 | 32 |
| 57 | 12 / 96 | 96 | 96 | 64 | 32 |
| 68 | 12 / 96 | 96 | 96 | 64 | 32 |
| 74 | 96 | 96 | 96 | 64 | 32 |
| 100 | 96 | 96 | 96 | 64 | 32 |
| 150 | 96 | 96 | 96 | 64 | 32 |
| 250 | 96 | 96 | 96 | 64 | 32 |
| 400 | 96 | 96 | 96 | 64 | 32 |

(single value = same in both; · = gc not run in the old sim)

## 2. Globally best (TM, TN) per gc (best_shape_per_gc)

| gc | old | new |
|---|---|---|
| 2 | · | (12, 32) |
| 4 | · | (12, 32) |
| 6 | · | (12, 32) |
| 8 | · | (12, 32) |
| 10 | · | (12, 32) |
| 12 | · | (32, 64) |
| 15 | (12, 32) | (32, 64) |
| 20 | · | (32, 64) |
| 25 | · | (32, 64) |
| 30 | (12, 32) | (32, 64) |
| 38 | (12, 32) | (64, 32) |
| 42 | (32, 64) | (64, 32) |
| 47 | (32, 64) | (64, 32) |
| 50 | (32, 64) | (64, 32) |
| 52 | (32, 64) | (64, 32) |
| 57 | (32, 64) | (64, 32) |
| 68 | (32, 64) | (64, 32) |
| 74 | (32, 64) | (64, 32) |
| 100 | (32, 64) | (96, 16) |
| 150 | (64, 32) | (96, 16) |
| 250 | (96, 16) | (96, 16) |
| 400 | (96, 16) | (96, 64) |

## 3. Speedup of optimal TM over square TM = TN (optimal_vs_square)

Slide: gc=100 20-65%, gc=250 ~85%, gc=400 up to 90%.

| gc | TN=8 old → new | TN=16 old → new | TN=32 old → new | TN=64 old → new |
|---|---|---|---|---|
| 2 | 1% | 44% | 26% | 77% |
| 4 | 1% | 44% | 26% | 77% |
| 6 | 1% | 44% | 26% | 77% |
| 8 | 18% | 44% | 26% | 74% |
| 10 | 31% | 42% | 24% | 74% |
| 12 | 32% | 31% | 11% | 74% |
| 15 | 3% → 32% | 16% → 16% | 6% → 0% | 62% → 74% |
| 20 | 33% | 1% | 0% | 74% |
| 25 | 33% | 4% | 0% | 74% |
| 30 | 15% → 41% | 16% → 20% | 6% → 0% | 62% → 74% |
| 38 | 32% → 54% | 16% → 37% | 6% → 3% | 62% → 68% |
| 42 | 32% → 58% | 8% → 43% | 1% → 13% | 62% → 65% |
| 47 | 32% → 63% | 3% → 49% | 1% → 22% | 62% → 61% |
| 50 | 32% → 65% | 3% → 52% | 1% → 27% | 62% → 60% |
| 52 | 32% → 66% | 3% → 54% | 1% → 29% | 62% → 60% |
| 57 | 37% → 69% | 3% → 58% | 1% → 36% | 62% → 60% |
| 68 | 47% → 74% | 11% → 65% | 1% → 46% | 62% → 60% |
| 74 | 51% → 76% | 19% → 68% | 1% → 50% | 62% → 59% |
| 100 **(slide)** | 64% → 82% | 39% → 76% | 1% → 50% | 62% → 44% |
| 150 | 76% → 88% | 59% → 83% | 27% → 50% | 51% → 16% |
| 250 **(slide)** | 85% → 92% | 76% → 83% | 49% → 50% | 40% → 4% |
| 400 **(slide)** | 91% → 92% | 83% → 83% | 50% → 67% | 5% → 33% |
