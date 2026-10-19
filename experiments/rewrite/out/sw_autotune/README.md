# sw_autotune: how much autotuning?

Over 41 values of gc > 0 (fig_best_tile grid). Extra time = picked tile vs the best of all 1536 tiles.

| strategy | calibration runs | worst extra time | median | gc within 1 % |
|---|---|---|---|---|
| full grid (step 4) | 1536 | 0.1% | 0.00% | 100% |
| step 8 | 384 | 5.8% | 0.00% | 90% |
| step 16 | 96 | 6.8% | 0.06% | 63% |
| heights dividing M | 320 | 6.8% | 0.00% | 95% |
| heights dividing M, widths $2^k$ | 60 | 10.2% | 0.00% | 83% |
| powers of two | 36 | 15.1% | 0.60% | 54% |
| square tiles | 32 | 110.3% | 10.23% | 41% |
| no tuning ($16 \times 32$) | 0 | 500.1% | 165.15% | 0% |
