# Roofline Model Validation for Optimal Tile Shape

## Model

Performance for any (TM, TN, gc) configuration is predicted by a roofline:

```
cycles(TM, TN, gc) = MNK × max( α_calib(TM, TN),  gc / TM )
```

- `α_calib(TM, TN)` — memory-bound cost per MNK, calibrated empirically at gc=0
  (no generation stalls, so the simulator measures pure L1/memory behavior).
- `gc / TM` — generation-bound cost per MNK. The FIFO generates MNK/TM total
  elements across the whole computation (TM-fold register reuse of B amortizes
  the cost), each taking gc cycles. So the generation cost per output element
  is gc/TM.
- The `max` captures which bottleneck dominates: below the crossover point the
  hardware is memory-bound; above it the FIFO device is the bottleneck.

The globally optimal tile shape for any gc is then:

```
(TM*, TN*) = argmin_{TM, TN}  max( α_calib(TM, TN),  gc / TM )
```

This requires no regression and no formula approximation — just the calibrated
α table and one arithmetic expression per (TM, TN) pair.

## Key Assumption to Validate

The model assumes α_calib(TM, TN) measured at gc=0 remains valid at gc > 0.
At gc=0 the FIFO generates instantly, so α_calib reflects pure memory cost
with no stall interference. At high gc, stall cycles could in principle perturb
cache access patterns and shift the effective α.

If this assumption holds, the roofline model predicts the optimal tile shape
for any gc using only gc=0 calibration data. If it breaks down, correction
terms are needed (see Extensions below).

## Data Sources

- **`b-stationary-alpha-calibration`** — α_calib(TM, TN) at gc=0 for B-stationary.
- **`c-stationary-alpha-calibration`** — α_calib(TM, TN) at gc=0 for C-stationary
  (col-major, the best C-stat variant from experiments 1–3).
- **`b-stationry-vs-c-stationary` / `*-col-major` / `*-pipelined`** — full grids
  at gc ∈ {0, 10, 100} used as ground truth to evaluate the predictions.

## Validation Protocol

For each mode, at each (gc, L1) condition:

1. Load α_calib(TM, TN) from the gc=0 calibration.
2. Compute `max(α_calib(TM, TN), gc/TM)` for all (TM, TN) pairs.
3. Pick the predicted best pair `(TM*, TN*)_pred`.
4. Compare to the empirically best pair `(TM*, TN*)_empirical` from the v55 grids.

Report:

- **Exact match rate** — fraction of (gc, L1) conditions where the predicted
  best pair equals the empirical best.
- **Cycle gap when wrong** — when the prediction is off, how many percent worse
  is the predicted pair vs the true best? A formula that picks a tile shape
  within 2% of optimal is practically useful even if the exact pair differs.
- **α drift** — at each (TM, TN), plot α_calib(gc=0) vs the effective α
  observed at gc=10 and gc=100. If the values stay close, the assumption holds.

The cycle gap is the practically important metric: the customer cares about
not leaving performance on the table, not about matching exact tile dimensions.

## Extensions (only if validation shows the model is insufficient)

If α drifts significantly with gc, add a correction term fit by regression:

```
α_eff(TM, TN, gc) = α_calib(TM, TN) + f(TM, TN, gc)
```

Candidate correction terms in order of complexity:
1. `+ c × gc` — flat gc shift
2. `+ c × gc/TN` — gc interacts with TN (larger TN amortizes FIFO starts)
3. `+ c × in_l1(TM, L1)` — L1 regime offset (cycles drop when A tile fits in L1)

Each term is fit by OLS on the residuals `α_observed(gc>0) − α_calib(gc=0)`.

## Expected Output

| Condition | Exact match rate | Median cycle gap |
|-----------|-----------------|-----------------|
| gc=10, L1=16KB | … | … |
| gc=10, L1=32KB | … | … |
| gc=10, L1=64KB | … | … |
| gc=100, L1=16KB | … | … |
| gc=100, L1=32KB | … | … |
| gc=100, L1=64KB | … | … |

If the roofline model achieves >90% exact match rate and <3% median cycle gap
across all conditions, no regression correction is needed.
