# overlap_fit

Replace max() in the math model: how do alpha and B generation combine?

Data: the cached model_sweep runs (22176, 3 L1 sizes x 6 matrix shapes, gc 0
... 400). For every tile and gc > 0: alpha = T(gc = 0) / MNK (calibration),
B = gc * ceil(M/TM) / M (B generation per MAC), T = measured / MNK.

Findings that motivate the variants:
  - T / max(alpha, B) is ~1.000 when one term dominates, and peaks when
    alpha ~ B (median 1.05, p90 1.25, max 1.47 at B/alpha 0.9 - 1.0):
    max() assumes perfect overlap, which fails when the rates balance.
  - Over all runs, the cycles above max() equal one FIFO startup per tile
    at the median: the FIFO restarts empty every tile (load_seed), so its
    first register block waits 16 * gc cycles with nothing to overlap.

Variants (per MAC; S = startup = tiles * reg_dim^2 * gc / MNK):
  max          max(alpha, B)                     (the presentation's model)
  max+S        max(alpha, B) + S                 (no fitted parameter)
  smooth       (alpha^p + B^p)^(1/p)             (p fitted)
  smooth+S     (alpha^p + B^p)^(1/p) + S         (p fitted)

p is fitted on the prediction error of T (mean |log(T_pred / T)|), not on
tile-selection accuracy, which is then an honest check. Cross-validation:
fit p on 5 matrix shapes, evaluate on the 6th, for each shape.

run:  .venv/bin/python experiments/rewrite/overlap_fit.py

20328 runs with gc > 0.

## Fit of T (all runs)

| variant | p | mean abs log error | median abs rel error | p90 | worst |
|---|---|---|---|---|---|
| `max` | inf | 0.0124 | 0.09% | 3.52% | 32.0% |
| `max+S` | inf | 0.0119 | 0.09% | 3.23% | 31.3% |
| `smooth` | 9.5 | 0.0115 | 0.08% | 3.40% | 28.5% |
| `smooth+S` | 12.5 | 0.0115 | 0.12% | 3.16% | 29.3% |

## Tile selection (p fitted on all shapes)

| variant | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|
| `max` (p=inf) | 150/198 (76%) | 169/198 (85%) | 88% | 93% | 15.8% |
| `max+S` (p=inf) | 165/198 (83%) | 172/198 (87%) | 86% | 91% | 21.0% |
| `smooth` (p=9.5) | 150/198 (76%) | 168/198 (85%) | 88% | 95% | 13.0% |
| `smooth+S` (p=12.5) | 167/198 (84%) | 174/198 (88%) | 89% | 95% | 13.9% |

## Cross-validation: fit p without one shape, test on it

| variant | held-out shape | p fitted on the other 5 | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|---|---|
| `max` | (192, 256, 256) | inf 28/33 (85%) | 32/33 (97%) | 97% | 100% | 1.6% |
| `max` | (100, 100, 100) | inf 22/33 (67%) | 27/33 (82%) | 76% | 79% | 13.0% |
| `max` | (200, 300, 250) | inf 21/33 (64%) | 24/33 (73%) | 76% | 91% | 15.4% |
| `max` | (384, 256, 512) | inf 27/33 (82%) | 29/33 (88%) | 91% | 100% | 2.8% |
| `max` | (256, 512, 128) | inf 28/33 (85%) | 30/33 (91%) | 94% | 97% | 6.0% |
| `max` | (150, 222, 190) | inf 24/33 (73%) | 27/33 (82%) | 94% | 94% | 15.8% |
| `max+S` | (192, 256, 256) | inf 32/33 (97%) | 32/33 (97%) | 97% | 100% | 1.6% |
| `max+S` | (100, 100, 100) | inf 26/33 (79%) | 28/33 (85%) | 85% | 85% | 13.9% |
| `max+S` | (200, 300, 250) | inf 25/33 (76%) | 27/33 (82%) | 76% | 85% | 21.0% |
| `max+S` | (384, 256, 512) | inf 29/33 (88%) | 29/33 (88%) | 91% | 100% | 2.8% |
| `max+S` | (256, 512, 128) | inf 29/33 (88%) | 30/33 (91%) | 91% | 94% | 6.0% |
| `max+S` | (150, 222, 190) | inf 24/33 (73%) | 26/33 (79%) | 79% | 85% | 15.8% |
| `smooth` | (192, 256, 256) | 8.5 27/33 (82%) | 31/33 (94%) | 94% | 100% | 2.1% |
| `smooth` | (100, 100, 100) | 12 22/33 (67%) | 27/33 (82%) | 76% | 82% | 13.0% |
| `smooth` | (200, 300, 250) | 10 22/33 (67%) | 24/33 (73%) | 79% | 91% | 10.4% |
| `smooth` | (384, 256, 512) | 8 26/33 (79%) | 28/33 (85%) | 88% | 100% | 3.2% |
| `smooth` | (256, 512, 128) | 8.5 27/33 (82%) | 29/33 (88%) | 91% | 97% | 6.0% |
| `smooth` | (150, 222, 190) | 11 26/33 (79%) | 29/33 (88%) | 100% | 100% | 0.4% |
| `smooth+S` | (192, 256, 256) | 10.5 29/33 (88%) | 31/33 (94%) | 94% | 100% | 2.1% |
| `smooth+S` | (100, 100, 100) | 17 25/33 (76%) | 27/33 (82%) | 82% | 82% | 13.9% |
| `smooth+S` | (200, 300, 250) | 13.5 25/33 (76%) | 28/33 (85%) | 82% | 94% | 10.4% |
| `smooth+S` | (384, 256, 512) | 10 28/33 (85%) | 28/33 (85%) | 88% | 100% | 3.2% |
| `smooth+S` | (256, 512, 128) | 11 29/33 (88%) | 29/33 (88%) | 91% | 97% | 6.0% |
| `smooth+S` | (150, 222, 190) | 15.5 27/33 (82%) | 27/33 (82%) | 88% | 91% | 13.6% |

### Cross-validation totals (each shape predicted with p fitted on the others)

| variant | exact tile | TM* right | within 1 % | within 5 % | worst gap |
|---|---|---|---|---|---|
| `max` | 150/198 (76%) | 169/198 (85%) | 88% | 93% | 15.8% |
| `max+S` | 165/198 (83%) | 172/198 (87%) | 86% | 91% | 21.0% |
| `smooth` | 150/198 (76%) | 168/198 (85%) | 88% | 95% | 13.0% |
| `smooth+S` | 163/198 (82%) | 170/198 (86%) | 87% | 94% | 13.9% |
