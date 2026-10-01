# fig_model_accuracy

Model: max(alpha, gc·⌈M/TM⌉/M) + S, ties to the lower alpha.

| cases | n | exact tile | TM* right | within 1 % | within 5 % | worst | misses > 1 % with 0.5 < B/alpha < 2 |
|---|---|---|---|---|---|---|---|
| 6 matrices × 3 L1 sizes, fully assoc | 198 | 83% | 87% | 86% | 91% | 21.0% | 27/27 |
| 6 matrices × 3 L1 sizes, 8-way | 198 | 74% | 84% | 81% | 91% | 21.0% | 36/38 |
| 6 matrices × 3 L1 sizes, 4-way | 198 | 70% | 84% | 78% | 90% | 20.7% | 42/43 |
| default setup, all tiles | 41 | 85% | 85% | 95% | 95% | 29.0% | 2/2 |
| all | 635 | 77% | 85% | 83% | 91% | 29.0% | 107/110 |

## Worst 15

| cases | config | gc | model | best | excess | B/alpha |
|---|---|---|---|---|---|---|
| default setup, all tiles | default | 300 | (128, 48) | (96, 16) | 29.0% | 1.04 |
| 6 matrices × 3 L1 sizes, fully assoc | (32768, (200, 300, 250)) | 400 | (128, 64) | (128, 24) | 21.0% | 1.24 |
| 6 matrices × 3 L1 sizes, 8-way | (32768, (200, 300, 250)) | 400 | (128, 64) | (128, 24) | 21.0% | 1.21 |
| 6 matrices × 3 L1 sizes, 4-way | (32768, (200, 300, 250)) | 400 | (128, 64) | (128, 32) | 20.7% | 1.17 |
| 6 matrices × 3 L1 sizes, 8-way | (32768, (200, 300, 250)) | 200 | (128, 32) | (128, 24) | 17.9% | 1.10 |
| 6 matrices × 3 L1 sizes, 4-way | (16384, (200, 300, 250)) | 200 | (80, 24) | (80, 12) | 17.5% | 1.08 |
| 6 matrices × 3 L1 sizes, 8-way | (8192, (100, 100, 100)) | 100 | (40, 24) | (40, 16) | 17.0% | 1.05 |
| 6 matrices × 3 L1 sizes, 4-way | (16384, (100, 100, 100)) | 75 | (80, 12) | (64, 16) | 16.5% | 0.87 |
| 6 matrices × 3 L1 sizes, fully assoc | (32768, (150, 222, 190)) | 50 | (64, 64) | (80, 64) | 15.8% | 0.93 |
| 6 matrices × 3 L1 sizes, 4-way | (32768, (200, 300, 250)) | 50 | (64, 32) | (80, 32) | 15.8% | 0.83 |
| 6 matrices × 3 L1 sizes, fully assoc | (32768, (200, 300, 250)) | 50 | (64, 64) | (80, 64) | 15.4% | 0.96 |
| 6 matrices × 3 L1 sizes, 8-way | (32768, (200, 300, 250)) | 50 | (64, 48) | (80, 48) | 15.0% | 0.89 |
| 6 matrices × 3 L1 sizes, 4-way | (32768, (150, 222, 190)) | 50 | (64, 48) | (80, 48) | 14.2% | 0.88 |
| 6 matrices × 3 L1 sizes, fully assoc | (16384, (100, 100, 100)) | 200 | (64, 64) | (64, 32) | 13.9% | 1.34 |
| 6 matrices × 3 L1 sizes, 4-way | (16384, (200, 300, 250)) | 75 | (64, 16) | (40, 32) | 13.7% | 0.84 |
