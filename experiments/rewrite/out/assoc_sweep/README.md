# assoc_sweep

Associativity on the full model_sweep grid (confirms assoc_check.py).

Same grid as model_sweep (L1 8 / 16 / 32 KB x 6 matrix shapes x all tiles x
gc), with a fully associative, 8-way and 4-way L1. The fully associative runs
are read from model_sweep's cache. Per cache:
  - model accuracy, alpha calibrated on the SAME cache, with the corrected B
    term, plain max() and max() + startup S (as in overlap_fit.py);
  - what it costs to use the tile that is best on the fully associative
    cache (~ an accelerator scratchpad) on the set-associative one.

run:  .venv/bin/python experiments/rewrite/assoc_sweep.py

## Model accuracy per cache (alpha calibrated on that cache)

| cache | model | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|---|
| fully assoc | `max` | 150/198 (76%) | 169/198 (85%) | 88% | 93% | 15.8% |
| fully assoc | `max+S` | 165/198 (83%) | 172/198 (87%) | 86% | 91% | 21.0% |
| 8-way | `max` | 102/198 (52%) | 166/198 (84%) | 76% | 94% | 15.0% |
| 8-way | `max+S` | 147/198 (74%) | 167/198 (84%) | 81% | 91% | 21.0% |
| 4-way | `max` | 97/198 (49%) | 161/198 (81%) | 73% | 94% | 16.5% |
| 4-way | `max+S` | 139/198 (70%) | 167/198 (84%) | 78% | 90% | 20.7% |

## Using the fully associative cache's best tile on the others

Extra time = T(fully associative best tile) / T(best tile), both measured on the set-associative cache, over all gc.

| cache | L1 | matrix | best tile differs | median extra | worst extra |
|---|---|---|---|---|---|
| 8-way | 8 KB | (192, 256, 256) | 10/11 | 269.2% | 1758.3% |
| 8-way | 8 KB | (100, 100, 100) | 3/11 | 0.0% | 21.6% |
| 8-way | 8 KB | (200, 300, 250) | 9/11 | 29.4% | 201.1% |
| 8-way | 8 KB | (384, 256, 512) | 10/11 | 269.2% | 1758.5% |
| 8-way | 8 KB | (256, 512, 128) | 11/11 | 502.3% | 2204.7% |
| 8-way | 8 KB | (150, 222, 190) | 8/11 | 18.5% | 66.0% |
| 8-way | 16 KB | (192, 256, 256) | 10/11 | 268.6% | 1139.4% |
| 8-way | 16 KB | (100, 100, 100) | 5/11 | 0.0% | 49.3% |
| 8-way | 16 KB | (200, 300, 250) | 10/11 | 25.3% | 36.9% |
| 8-way | 16 KB | (384, 256, 512) | 11/11 | 507.0% | 1370.5% |
| 8-way | 16 KB | (256, 512, 128) | 10/11 | 224.9% | 1705.4% |
| 8-way | 16 KB | (150, 222, 190) | 10/11 | 9.8% | 53.7% |
| 8-way | 32 KB | (192, 256, 256) | 11/11 | 177.9% | 1139.5% |
| 8-way | 32 KB | (100, 100, 100) | 6/11 | 0.0% | 12.7% |
| 8-way | 32 KB | (200, 300, 250) | 8/11 | 8.7% | 31.8% |
| 8-way | 32 KB | (384, 256, 512) | 11/11 | 563.6% | 1396.4% |
| 8-way | 32 KB | (256, 512, 128) | 8/11 | 271.5% | 861.2% |
| 8-way | 32 KB | (150, 222, 190) | 10/11 | 6.0% | 12.5% |
| 4-way | 8 KB | (192, 256, 256) | 10/11 | 269.2% | 1758.3% |
| 4-way | 8 KB | (100, 100, 100) | 9/11 | 6.2% | 52.8% |
| 4-way | 8 KB | (200, 300, 250) | 9/11 | 18.0% | 195.4% |
| 4-way | 8 KB | (384, 256, 512) | 11/11 | 86.6% | 1014.9% |
| 4-way | 8 KB | (256, 512, 128) | 11/11 | 209.7% | 726.3% |
| 4-way | 8 KB | (150, 222, 190) | 10/11 | 16.7% | 63.7% |
| 4-way | 16 KB | (192, 256, 256) | 10/11 | 268.6% | 1139.4% |
| 4-way | 16 KB | (100, 100, 100) | 3/11 | 0.0% | 41.4% |
| 4-way | 16 KB | (200, 300, 250) | 10/11 | 21.3% | 29.5% |
| 4-way | 16 KB | (384, 256, 512) | 11/11 | 507.0% | 1370.5% |
| 4-way | 16 KB | (256, 512, 128) | 10/11 | 226.7% | 1705.4% |
| 4-way | 16 KB | (150, 222, 190) | 10/11 | 14.8% | 44.9% |
| 4-way | 32 KB | (192, 256, 256) | 11/11 | 174.6% | 1139.5% |
| 4-way | 32 KB | (100, 100, 100) | 6/11 | 0.0% | 28.2% |
| 4-way | 32 KB | (200, 300, 250) | 10/11 | 18.8% | 67.0% |
| 4-way | 32 KB | (384, 256, 512) | 11/11 | 615.7% | 1396.4% |
| 4-way | 32 KB | (256, 512, 128) | 8/11 | 271.5% | 861.2% |
| 4-way | 32 KB | (150, 222, 190) | 9/11 | 22.8% | 61.9% |
