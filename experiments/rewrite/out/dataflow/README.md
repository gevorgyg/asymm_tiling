# dataflow: rewrite vs pre-rewrite

Re-run of pre-rewrite v55-results/b-stationary-vs-c-stationry-col-major.

Slide "B-Stationary: TM-Fold Register Reuse": the table "C-stationary 1.7x
faster (gc=0), 1.4x faster (gc=10), 7.1x slower (gc=100)", which is this
experiment at the fixed tile TM=64, TN=32 (recomputed: 1.75 / 1.36 / 7.19).
FIFO, M=192, N=K=256, 4-byte elements, fully associative 16 KB L1, no L2,
mulacc not counted.

The old C-stationary FIFO here is the col_major_fifo variant (B regenerated
per register row block, no discarded elements). The rewrite's output-
stationary FIFO pops exactly the elements it uses, so it generates the same
number of B elements per tile.

run:  .venv/bin/python experiments/rewrite/dataflow.py

The experiment also sweeps the L1 size (16 / 32 / 64 KB, fully associative); every table is per L1 size.

## Traffic

| L1 | dataflow | L1 misses identical | worst diff |
|---|---|---|---|
| 16 KB | B-stationary | 106/109 | 0.36% |
| 16 KB | C-stationary | 27/108 | 13.27% |
| 32 KB | B-stationary | 102/108 | 4.10% |
| 32 KB | C-stationary | 54/108 | 50.00% |
| 64 KB | B-stationary | 105/108 | 0.08% |
| 64 KB | C-stationary | 75/108 | 4.00% |

## The slide table (fixed tile TM=64, TN=32)

| L1 | gc | slide | old recomputed | new |
|---|---|---|---|---|
| 16 KB | 0 | 1.7x faster | 1.72x faster | 1.68x faster |
| 16 KB | 10 | 1.4x faster | 1.36x faster | 2.18x slower |
| 16 KB | 100 | 7.1x slower | 7.19x slower | 15.98x slower |
| 32 KB | 0 | 1.7x faster | 1.73x faster | 1.68x faster |
| 32 KB | 10 | 1.4x faster | 1.36x faster | 2.18x slower |
| 32 KB | 100 | 7.1x slower | 7.19x slower | 15.98x slower |
| 64 KB | 0 | 1.7x faster | 1.75x faster | 1.68x faster |
| 64 KB | 10 | 1.4x faster | 1.36x faster | 2.18x slower |
| 64 KB | 100 | 7.1x slower | 7.19x slower | 15.98x slower |

## Best tile of each dataflow vs best tile of the other

| L1 | gc | old: best B / best C | old C vs B | new: best B / best C | new C vs B |
|---|---|---|---|---|---|
| 16 KB | 0 | (32, 64) / (4, 64) | 1.99x faster | (8, 64) / (8, 64) | 2.26x faster |
| 16 KB | 10 | (32, 64) / (16, 32) | 1.30x faster | (32, 64) / (8, 64) | 2.57x slower |
| 16 KB | 100 | (32, 64) / (16, 32) | 7.50x slower | (96, 16) / (32, 64) | 16.63x slower |
| 32 KB | 0 | (24, 32) / (4, 64) | 1.93x faster | (24, 32) / (24, 64) | 2.24x faster |
| 32 KB | 10 | (24, 32) / (64, 32) | 1.26x faster | (24, 32) / (24, 64) | 2.96x slower |
| 32 KB | 100 | (32, 64) / (64, 32) | 7.50x slower | (96, 16) / (24, 64) | 16.63x slower |
| 64 KB | 0 | (48, 32) / (4, 64) | 1.91x faster | (48, 32) / (32, 64) | 2.23x faster |
| 64 KB | 10 | (48, 32) / (64, 32) | 1.24x faster | (48, 32) / (32, 64) | 2.97x slower |
| 64 KB | 100 | (48, 32) / (64, 32) | 7.86x slower | (96, 16) / (48, 32) | 16.63x slower |
