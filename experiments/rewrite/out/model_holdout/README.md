# model_holdout: the refined model on held-out configurations

Each configuration calibrated on its own gc = 0 runs (coarse tile grids).

| configuration | runtime within 1 % | within 0.1 % | predicted too slow (> 0.1 %) | worst pick |
|---|---|---|---|---|
| L1 8 KB | 98.9% | 90.0% | 0 | 0.00% |
| L1 16 KB | 97.2% | 89.2% | 0 | 0.00% |
| L1 32 KB | 95.1% | 87.7% | 0 | 0.00% |
| L1 64 KB | 93.0% | 85.6% | 0 | 0.00% |
| memory 100 cycles | 98.3% | 83.5% | 0 | 0.00% |
| memory 180 cycles | 97.2% | 85.7% | 0 | 0.00% |
| memory 300 cycles | 95.9% | 86.6% | 0 | 0.00% |
| memory 400 cycles | 95.9% | 87.4% | 0 | 0.00% |
| register block 2x2 | 99.6% | 94.8% | 0 | 0.00% |
| register block 4x4 | 97.2% | 85.7% | 0 | 0.00% |
| register block 8x8 | 93.3% | 70.7% | 41 | 0.12% |
| register block 16x16 | 77.6% | 52.7% | 91 | 0.00% |
| fully assoc, rows of 256 | 97.4% | 87.0% | 0 | 0.00% |
| 4-way, rows of 256 | 90.6% | 83.6% | 0 | 14.61% |
| 8-way, rows of 256 | 90.9% | 83.6% | 0 | 14.61% |
| 16-way, rows of 256 | 91.0% | 83.6% | 0 | 14.61% |
| 32-way, rows of 256 | 93.1% | 84.8% | 0 | 0.00% |
| fully assoc, rows of 260 | 93.0% | 83.4% | 0 | 0.00% |
| 4-way, rows of 260 | 94.5% | 83.4% | 0 | 0.05% |
| 8-way, rows of 260 | 94.5% | 83.6% | 0 | 0.05% |
| 16-way, rows of 260 | 93.9% | 83.2% | 0 | 0.00% |
| 32-way, rows of 260 | 92.7% | 83.2% | 0 | 0.00% |
| fully assoc, rows of 272 | 95.7% | 84.3% | 0 | 0.01% |
| 4-way, rows of 272 | 96.4% | 83.8% | 0 | 0.00% |
| 8-way, rows of 272 | 96.1% | 83.9% | 0 | 0.00% |
| 16-way, rows of 272 | 96.1% | 84.5% | 0 | 0.00% |
| 32-way, rows of 272 | 96.0% | 84.3% | 0 | 0.00% |
