# sw_templates_padded_small: calibration templates by K

Excess = measured runtime of the picked tile / best measured tile - 1, over gc [5, 10, 20, 40, 80, 160]. K and N padded to a multiple of 16.

| shape | nearest template K | own: worst | nearest: worst | default (K 256): worst |
|---|---|---|---|---|
| 150×304×208 | 256 | 0.0% | 35.3% | 35.3% |
| 200×208×304 | 256 | 1.6% | 4.1% | 4.1% |
| 100×512×160 | 512 | 0.2% | 0.2% | 22.6% |
| 300×128×256 | 128 | 0.0% | 0.0% | 3.9% |
| 250×400×112 | 512 | 0.0% | 8.3% | 31.4% |
| 180×352×192 | 256 | 0.0% | 34.7% | 34.7% |
| 120×704×128 | 512 | 0.0% | 0.0% | 31.4% |
| 400×160×208 | 128 | 0.0% | 70.6% | 2.4% |
| 160×608×144 | 512 | 0.0% | 4.6% | 4.6% |
| 240×272×208 | 256 | 0.0% | 0.0% | 0.0% |

| table | median excess | cases within 1 % | within 5 % | worst |
|---|---|---|---|---|
| own | 0.00% | 98% | 100% | 1.6% |
| nearest | 0.00% | 78% | 87% | 70.6% |
| default | 0.00% | 68% | 83% | 35.3% |
