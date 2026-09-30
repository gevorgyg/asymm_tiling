# assoc_check

Does the math model work as well with a set-associative L1?

Same procedure as model_sweep (alpha calibrated at gc = 0 on the SAME cache,
predict argmin max(alpha, gc*ceil(M/TM)/M), ties to lower alpha), on a small
subset, for a fully associative, 8-way and 4-way 16 KB L1 (64 B lines).
Also: how much it costs to use the tile that is best for the fully
associative cache on the set-associative one.

192x256x256 has power-of-two row strides (1 KB): in the 8-way 16 KB L1 (32
sets) a tile column's rows all map to 2 sets. 100^3 and 200x300x250 don't
alias like that.

run:  .venv/bin/python experiments/rewrite/assoc_check.py

2592 simulator runs.

## Model accuracy per cache

| cache | shapes | model | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|---|---|
| fully assoc | all 3 | `max` | 22/24 (92%) | 22/24 (92%) | 92% | 96% | 15.3% |
| fully assoc | all 3 | `max+S` | 21/24 (88%) | 22/24 (92%) | 88% | 92% | 15.3% |
| fully assoc | (192, 256, 256) | `max` | 8/8 (100%) | 8/8 (100%) | 100% | 100% | 0.0% |
| fully assoc | (192, 256, 256) | `max+S` | 8/8 (100%) | 8/8 (100%) | 100% | 100% | 0.0% |
| fully assoc | (100, 100, 100) | `max` | 7/8 (88%) | 7/8 (88%) | 88% | 100% | 1.3% |
| fully assoc | (100, 100, 100) | `max+S` | 6/8 (75%) | 7/8 (88%) | 75% | 88% | 13.9% |
| fully assoc | (200, 300, 250) | `max` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 15.3% |
| fully assoc | (200, 300, 250) | `max+S` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 15.3% |
| 8-way | all 3 | `max` | 17/24 (71%) | 22/24 (92%) | 79% | 92% | 11.2% |
| 8-way | all 3 | `max+S` | 21/24 (88%) | 22/24 (92%) | 88% | 88% | 11.2% |
| 8-way | (192, 256, 256) | `max` | 4/8 (50%) | 8/8 (100%) | 62% | 100% | 1.5% |
| 8-way | (192, 256, 256) | `max+S` | 8/8 (100%) | 8/8 (100%) | 100% | 100% | 0.0% |
| 8-way | (100, 100, 100) | `max` | 6/8 (75%) | 7/8 (88%) | 88% | 88% | 6.5% |
| 8-way | (100, 100, 100) | `max+S` | 6/8 (75%) | 7/8 (88%) | 75% | 75% | 11.1% |
| 8-way | (200, 300, 250) | `max` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 11.2% |
| 8-way | (200, 300, 250) | `max+S` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 11.2% |
| 4-way | all 3 | `max` | 15/24 (62%) | 22/24 (92%) | 79% | 92% | 13.7% |
| 4-way | all 3 | `max+S` | 21/24 (88%) | 22/24 (92%) | 88% | 88% | 13.7% |
| 4-way | (192, 256, 256) | `max` | 4/8 (50%) | 8/8 (100%) | 62% | 100% | 1.5% |
| 4-way | (192, 256, 256) | `max+S` | 8/8 (100%) | 8/8 (100%) | 100% | 100% | 0.0% |
| 4-way | (100, 100, 100) | `max` | 4/8 (50%) | 7/8 (88%) | 88% | 88% | 6.4% |
| 4-way | (100, 100, 100) | `max+S` | 6/8 (75%) | 7/8 (88%) | 75% | 75% | 8.7% |
| 4-way | (200, 300, 250) | `max` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 13.7% |
| 4-way | (200, 300, 250) | `max+S` | 7/8 (88%) | 7/8 (88%) | 88% | 88% | 13.7% |

## Using the fully associative cache's best tile on the others

| cache | shape | best tile differs | median extra time | worst extra time |
|---|---|---|---|---|
| 8-way | (192, 256, 256) | 7/8 | 567.5% | 1758.6% |
| 8-way | (100, 100, 100) | 5/8 | 27.2% | 60.9% |
| 8-way | (200, 300, 250) | 5/8 | 9.6% | 25.3% |
| 4-way | (192, 256, 256) | 7/8 | 567.5% | 1758.6% |
| 4-way | (100, 100, 100) | 5/8 | 18.0% | 52.2% |
| 4-way | (200, 300, 250) | 6/8 | 6.7% | 21.9% |
