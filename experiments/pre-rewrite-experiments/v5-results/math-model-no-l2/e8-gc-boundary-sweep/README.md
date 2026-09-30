# E8-nol2: gc Boundary Sweep — TM* Transitions Across TN

**Config**: M=192, N=K=TK=256, A_P=4, L1=16KB, no-L2.  
**Sweep**: gc ∈ {15,30,38,42,47,50,52,57,68,74,100,150,250,400},
TM ∈ {8,12,16,24,32,48,64,96}, TN ∈ {4,8,16,32,64}.  
**Three predictors compared** at every (gc, TN):

| Label | Description |
|-------|-------------|
| Calib | Uses α(TM, TN) from the gc=0 sweep (E6-nol2 cache hits) |
| Formula | α_E3(TM) + C×(1/TN − 1/32), C=11.0 for DRAM regime, C=0 for L1 |
| E3 | TN-blind: uses α(TM) at TN=32 only — ignores TN dependence |

---

## Formula accuracy at gc=0

```
   TM      TN=4      TN=8     TN=16     TN=32     TN=64
    8   -0.12%    -0.05%    -0.02%    -0.00%    +0.00%
   12   -0.08%    -0.04%    -0.02%    -0.00%    -3.62%   ← boundary anomaly
   16   -1.07%    -0.60%    -0.24%    +0.00%    +0.15%
   24   -1.03%    -0.58%    -0.23%    +0.00%    +0.15%
   32   -1.01%    -0.57%    -0.23%    +0.00%    +0.16%
   48   -0.98%    -0.56%    -0.23%    +0.00%   -24.28%*  ← WS overflow
   64   -0.98%    -0.56%    -0.24%    +0.00%   -62.66%*  ← WS overflow
   96  +92.66%  +122.16%  +145.04%    -0.00%*   -0.16%*
```

`*` safe=False by WS formula (ws_lines ≥ 300).

For DRAM-regime tiles (TM=16–64) at safe points, error is < 1.1%. TN=32 is
the calibration anchor so error is always 0% there.

The large positive errors at TM=96, TN=4/8/16 reflect a bug in the formula's
α₀: ALPHA_E3[96]=9.033 was measured at TN=32 where WS overflow occurred, so it
encodes the wrong base cost. The actual α₀(96) in the DRAM regime is ~5.94.
See "Why the formula fails for TM=96" below.

---

## TM* trajectory

```
    gc    TN=4   TN=8  TN=16  TN=32  TN=64
    15      12     12     12     12     32
    30      12     12     12     12     32
    38      12     12     12     12     32
    42      12     12     12     64     32   ← TN=32 transition
    47      12     12     96     64     32   ← TN=16 transition
    52      12     12     96     64     32
    57      12     96     96     64     32   ← TN=8 transition
    68      12     96     96     64     32
    74      96     96     96     64     32   ← TN=4 transition
   100      96     96     96     64     32
   250      96     96     96     64     32
   400      96     96     96     64     32
```

TN=64 is fixed at TM*=32 because WS overflow excludes TM≥48 at TN=64
(ws_lines(48,64)=394 ≥ 300). TM=64 at TN=32 becomes optimal above gc≈40
because TM=96 is WS-overflow at TN=32.

---

## Transition gc* values

Predicted (from experiment.py docstring) vs. observed:

| TN | Predicted gc* | Observed bracket | Winner after |
|----|--------------|-----------------|-------------|
| 32 | ≈ 42 | [38, 42] | TM=64 (TM=96 overflow) |
| 16 | ≈ 46 | [42, 47] | TM=96 |
|  8 | ≈ 55 | [52, 57] | TM=96 |
|  4 | ≈ 71 | [68, 74] | TM=96 |

All four transitions land within the predicted range. The pattern is clear:
larger TN → smaller gc*, because the cold-fill penalty C/TN shrinks, making
large-TM DRAM tiles cheaper at a lower gc threshold.

---

## Predictor accuracy

```
    gc       TN=4         TN=8        TN=16        TN=32        TN=64
             emp C F E   emp C F E   emp C F E   emp C F E   emp C F E
    15        12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      32 ✓✗✗
    30        12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      32 ✓✗✗
    38        12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      12 ✓✓✓      32 ✓✗✗
    42        12 ✓✓✗      12 ✓✓✗      12 ✓✓✗      64 ✓✓✓      32 ✓✓✗
    47        12 ✓✓✗      12 ✓✓✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
    52        12 ✓✓✗      12 ✓✓✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
    57        12 ✓✓✗      96 ✓✗✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
    68        12 ✓✓✗      96 ✓✗✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
    74        96 ✓✗✗      96 ✓✗✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
   100        96 ✓✗✗      96 ✓✗✗      96 ✓✗✗      64 ✓✓✓      32 ✓✓✓
```

**Calibrated (C)**: perfect across all 70 (gc, TN) cells.

**Formula (F)**: correct when TM=96 is not the optimal tile. Fails whenever the
optimal tile is TM=96 at TN<32, because ALPHA_E3[96]=9.033 bakes in the WS
overflow penalty from TN=32 rather than the true DRAM-regime α₀≈5.94.
Also fails for TN=64 at moderate gc because it recommends TM≥48 which the
safe() filter excludes — the formula's TN=64 prediction for TM=96 (≈9.38) or
TM=64 (≈3.83) involves WS-overflow tiles, so the calibrated predictor picks
TM=32 correctly while the formula picks a forbidden tile.

**E3-blind (E)**: fails at gc≥42 for all TN except TN=32, because it ignores
that α(TM, TN) varies with TN and systematically picks tiles that were optimal
at TN=32 but not at the target TN.

---

## Why the formula fails for TM=96

ALPHA_E3[96] = 9.033 was measured in E3-nol2 at TN=32 where
ws_lines(96,32) = 406 >> 256 (L1/LINE) — a catastrophic WS overflow. This
inflated α is baked into ALPHA_E3 as if it were the true DRAM-regime base
cost. The formula then propagates this wrong α₀ to all TN:

```
formula(96, TN=4) = 9.033 + 11.0×(1/4 − 1/32) = 11.44   [error: +92%]
formula(96, TN=8) = 9.033 + 11.0×(1/8 − 1/32) = 10.07   [error: +122%]
```

The calibrated predictor avoids this by reading α(96, TN=4)≈5.94 and
α(96, TN=8)≈4.53 directly from the gc=0 sweep, where TN is small enough that
WS(96, TN) < 256 and no overflow occurs.

The fix would be to calibrate ALPHA_E3[96] at a TN where TM=96 is safe (TN≤8),
or to use the full 2-D calibration table.

---

## Summary

| Finding | Result |
|---------|--------|
| Calibrated predictor accuracy | ✓ Perfect (70/70 gc×TN cells) |
| Formula accuracy (safe tiles, TM≠96) | ✓ < 1.1% error |
| Formula for TM=96 at TN<32 | ✗ Fails: ALPHA_E3[96] bakes in WS overflow |
| E3-blind predictor | ✗ Fails whenever optimal TM depends on TN |
| Transition gc* values | ✓ All four within predicted bracket |
| gc* shifts with TN | ✓ Larger TN → smaller gc* (C/TN penalty shrinks) |
| TN=64 always TM*=32 | ✓ WS overflow excludes TM≥48 |
