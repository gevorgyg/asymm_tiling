# overlap_regdim

Does the fitted overlap parameter p depend on the FIFO startup / burst size?

The register tile size reg_dim sets both: every tile starts by waiting for
one reg_dim x reg_dim block from an empty FIFO (startup S = tiles * reg^2 *
gc / MNK), and B is consumed reg^2 elements per pop. Sweep reg_dim in
{2, 4, 8} on a small subset and, per reg_dim:
  - check that S still explains the median excess over max(alpha, B);
  - fit p for the smooth max, with and without S (see overlap_fit.py);
  - compare tile selection.

Subset (fast): 16 KB fully associative L1, shapes 192x256x256 and 100^3,
TM 8..96, TN 8..64, gc 0..200. Otherwise the model_sweep setup.

run:  .venv/bin/python experiments/rewrite/overlap_regdim.py

1728 simulator runs.

## Per register size

| reg_dim | runs | median excess / S | p (smooth) | p (smooth+S) |
|---|---|---|---|---|
| 2 | 512 | 1.00 | 10.5 | 11.5 |
| 4 | 512 | 1.00 | 5.5 | 6.5 |
| 8 | 512 | 0.99 | 4 | 6 |

## Tile selection

| reg_dim | variant | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|---|
| 2 | `max` (p=inf) | 13/16 (81%) | 13/16 (81%) | 88% | 88% | 23.8% |
| 2 | `max+S` (p=inf) | 13/16 (81%) | 13/16 (81%) | 88% | 88% | 23.8% |
| 2 | `smooth` (p=10.5) | 14/16 (88%) | 14/16 (88%) | 94% | 94% | 10.6% |
| 2 | `smooth+S` (p=11.5) | 14/16 (88%) | 14/16 (88%) | 94% | 94% | 10.6% |
| 4 | `max` (p=inf) | 15/16 (94%) | 15/16 (94%) | 94% | 100% | 1.3% |
| 4 | `max+S` (p=inf) | 14/16 (88%) | 15/16 (94%) | 88% | 94% | 13.9% |
| 4 | `smooth` (p=5.5) | 14/16 (88%) | 14/16 (88%) | 88% | 100% | 1.3% |
| 4 | `smooth+S` (p=6.5) | 14/16 (88%) | 14/16 (88%) | 88% | 100% | 1.3% |
| 8 | `max` (p=inf) | 16/16 (100%) | 16/16 (100%) | 100% | 100% | 0.0% |
| 8 | `max+S` (p=inf) | 13/16 (81%) | 16/16 (100%) | 94% | 94% | 16.4% |
| 8 | `smooth` (p=4) | 15/16 (94%) | 15/16 (94%) | 94% | 100% | 3.3% |
| 8 | `smooth+S` (p=6) | 15/16 (94%) | 16/16 (100%) | 100% | 100% | 0.2% |
