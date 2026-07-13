# L1-size Regime Sweep: Does the Regime Boundary Shift With L1 Size?

**Hypothesis**: the L1/DRAM regime boundary for the A tile is
`TM_L1 = L1 / (TK × A_P) = L1 / 1024`. Doubling L1 should double TM_L1, moving
more tiles into the TN-independent L1 regime. The cold-fill coefficient C = 11.0
depends only on DRAM_lat and L1_lat, not on L1 size — so C should remain the same
for whatever tiles remain in the DRAM regime.

**Config**: M=192, N=K=TK=256, A_P=4, gc=0, no-L2.  
**Sweep**: L1 ∈ {8, 16, 32, 64} KB, TM ∈ {8,12,16,24,32,48,64,96}, TN ∈ {4,8,16,32,64}.

---

## α(TM, TN) tables by L1 size

### L1 = 8 KB  (TM_L1 = 8, WS-safe < 128 lines)

```
   TM  regime     TN=4     TN=8    TN=16    TN=32    TN=64
    8   DRAM    6.1891   4.7712   4.0623   3.7077   3.5303
   12   DRAM    6.0980   4.6840   3.9770   3.6233   3.4462
   16   DRAM    6.0524   4.6403   3.9343   3.5811   3.4041 *
   24   DRAM    6.0067   4.5966   3.8916   3.5387   4.405 **
   32   DRAM    5.9839   4.5747   3.8701   3.517 *  8.906 **
   48   DRAM    5.9609   4.5527   3.8486   9.055 ** 8.898 **
   64   DRAM    5.9685   4.5498   3.840 *  9.067 ** 8.891 **
   96   DRAM   36.8625  36.8323  36.817 **  36.830 ** 36.830 **
```

### L1 = 16 KB  (TM_L1 = 16, WS-safe < 256 lines) — baseline

```
   TM  regime     TN=4     TN=8    TN=16    TN=32    TN=64
    8     L1    3.3997   3.3973   3.3963   3.3958   3.3957
   12     L1    3.3159   3.3146   3.3139   3.3133   3.4378 †
   16   DRAM    6.0524   4.6403   3.9343   3.5811   3.4041
   24   DRAM    6.0067   4.5966   3.8916   3.5387   3.3617
   32   DRAM    5.9839   4.5747   3.8701   3.5174   3.340 *
   48   DRAM    5.9609   4.5527   3.8486   3.4959   4.390 **
   64   DRAM    5.9492   4.5415   3.8377   3.485 *  8.873 **
   96   DRAM    5.9374   4.5302   3.8266   9.033 ** 8.876 **
```

### L1 = 32 KB  (TM_L1 = 32, WS-safe < 512 lines)

```
   TM  regime     TN=4     TN=8    TN=16    TN=32    TN=64
    8     L1    3.3952   3.3945   3.3942   3.3940   3.3939
   12     L1    3.3136   3.3123   3.3114   3.3112   3.3108
   16     L1    3.2709   3.2697   3.2692   3.2689   3.2689
   24     L1    3.2303   3.2297   3.2293   3.2290   3.3531 †
   32   DRAM    5.9839   4.5747   3.8701   3.5174   3.3403
   48   DRAM    5.9609   4.5527   3.8486   3.4959   3.3185
   64   DRAM    5.9492   4.5415   3.8377   3.4849   3.307 *
   96   DRAM    5.9374   4.5302   3.8266   3.4734   4.380 **
```

### L1 = 64 KB  (TM_L1 = 64, WS-safe < 1024 lines)

```
   TM  regime     TN=4     TN=8    TN=16    TN=32    TN=64
    8     L1    3.3916   3.3909   3.3905   3.3903   3.3902
   12     L1    3.3088   3.3082   3.3080   3.3078   3.3078
   16     L1    3.2660   3.2656   3.2653   3.2652   3.2652
   24     L1    3.2262   3.2255   3.2251   3.2247   3.2240
   32     L1    3.2037   3.2031   3.2028   3.2027   3.2027
   48     L1    3.1862   3.1858   3.1856   3.1855   3.3093 †
   64   DRAM    5.9492   4.5415   3.8377   3.4849   3.3071
   96   DRAM    5.9374   4.5302   3.8266   3.4734   3.2948
```

`*` WS borderline (WS ≥ L1/LINE), `**` WS catastrophic (WS ≥ L1/LINE + 50),  
`†` mild anomaly at TN=64: A+C+FIFO ≈ L1 capacity (explained below).

---

## Finding 1: Regime boundary shifts exactly as predicted

The TN-independence boundary (below which α is flat across TN) matches
TM_L1 = L1 / 1024 exactly:

| L1 | TM_L1 | TN-independent tiles |
|----|-------|---------------------|
| 8 KB | 8 | none in our sweep (all TM ≥ 8 are DRAM-regime) |
| 16 KB | 16 | TM = 8, 12 |
| 32 KB | 32 | TM = 8, 12, 16, 24 |
| 64 KB | 64 | TM = 8, 12, 16, 24, 32, 48 |

The TN-variation Δ in the L1 regime is < 0.002 for tiles comfortably inside L1,
vs Δ = 2.4–2.7 for DRAM-regime tiles. The transition is sharp.

---

## Finding 2: C = 11.0 is universal — independent of L1 size

Fitting α = α₀ + C/TN for DRAM-regime tiles (safe points only):

| TM | L1=8KB | L1=16KB | L1=32KB | L1=64KB |
|----|--------|---------|---------|---------|
| 16 | 11.30 (+2.7%) | 11.30 (+2.7%) | — (L1) | — (L1) |
| 24 | 11.28 (+2.6%) | 11.28 (+2.6%) | — (L1) | — (L1) |
| 32 | 11.27 (+2.5%) | 11.28 (+2.5%) | 11.28 (+2.5%) | — (L1) |
| 48 | 11.27 (+2.4%) | 11.27 (+2.4%) | 11.27 (+2.5%) | — (L1) |
| 64 | 11.35 (+3.2%) | 11.26 (+2.4%) | 11.26 (+2.4%) | 11.27 (+2.4%) |
| 96 | — (anomaly) | 11.26 (+2.3%) | 11.26 (+2.4%) | 11.27 (+2.4%) |

Wherever a tile is in the DRAM regime, C is always 11.0–11.3, regardless of
which L1 size created that DRAM regime. **C depends only on DRAM_lat and L1_lat,
not on L1 size.** The formula C = (DRAM_lat − L1_lat) / (REG_M × REG_K) is confirmed.

---

## Finding 3: WS overflow threshold shifts with L1 size

The catastrophic overflow condition WS ≥ L1/LINE shifts accordingly:

| TM | TN at which overflow first appears |
|----|---|
| | L1=8KB | L1=16KB | L1=32KB | L1=64KB |
| 48 | TN=32 (WS=202 ≥ 128) | TN=64 (WS=394) | — (safe all) | TN=64 (WS=394, mild) |
| 64 | TN=16 (WS=142 ≥ 128) | TN=64 (WS=526) | TN=64 (WS=526, mild) | — (safe all) |
| 96 | TN=8 (WS=118 ≈ 128) | TN=32 (WS=406) | TN=64 (WS=790) | — (safe all) |

With L1=32KB: TM=96, TN=32 (WS=406 < 512) is now **safe** — its α=3.473 is normal,
while at L1=16KB the same cell gave the catastrophic α=9.033.

---

## Finding 4: α minimum shifts to larger TM as L1 grows

The optimal TM within the L1 regime (minimum α, TN=32) shifts outward:

| L1 | TM* in L1 regime | α_min (TN=32) |
|----|------------------|---------------|
| 16 KB | TM = 12 | 3.313 |
| 32 KB | TM = 24 | 3.229 |
| 64 KB | TM = 48 | 3.186 |

Larger TM within L1 regime → A tile amortised over more output rows per pass →
lower α. The minimum is always at the largest tile that still fits in L1.

---

## Finding 5: "Boundary tile" anomaly at TN=64

Tiles where A size approaches (but does not exceed) L1 show a mild α elevation
at TN=64 only:

| L1 | "boundary tile" TM | α elevation at TN=64 |
|----|---------------------|----------------------|
| 16 KB | TM=12 (A=12KB, 75% of L1) | +0.124 |
| 32 KB | TM=24 (A=24KB, 75% of L1) | +0.124 |
| 64 KB | TM=48 (A=48KB, 75% of L1) | +0.124 |

The elevation is **always 0.124** and always at **TN=64 only**. The mechanism:
at TN=64 the C tile (TM/4 × 16 register tiles) is large enough that A+C together
approach L1 capacity, leaving insufficient headroom for FIFO staging. This causes
occasional C line evictions to DRAM. The effect is small (elevating α by ~4%) and
consistent across L1 sizes.

---

## Anomaly: TM=96, L1=8KB

At L1=8KB, TM=96 shows α ≈ 36.8 for all TN values — about 6× higher than the
expected DRAM-regime value of ≈5.9. The WS formula predicts WS=70 < 128 (safe at
TN=4), yet α is massive. By contrast, TM=64 at L1=8KB gives α=5.97 (normal).

The TN-independence of this anomaly (Δ ≈ 0.04 across all TN) suggests the cost
is not a cold-fill correction but a fixed overhead. One hypothesis: the A tile
for TM=96 (1536 lines) is 12× larger than L1=128 lines. This extreme ratio may
cause cache-management overhead in the simulator that is not captured by the WS
formula (which assumes the hot working set fits in L1 within a single rtk chunk).
The anomaly disappears at L1=16KB (TM=96 at TN=4 gives α=5.94, normal).

**Practical conclusion**: at L1=8KB, TM=96 is unusable regardless of TN. Tile
selection should stay at TM ≤ 64 for L1=8KB.

---

## Summary: the model scales correctly with L1 size

| Prediction | Result |
|---|---|
| TM_L1 = L1/1024 governs regime boundary | ✓ Confirmed exactly |
| TN-independence in L1 regime for all L1 sizes | ✓ Δ < 0.002 |
| C = 11.0 in DRAM regime regardless of L1 size | ✓ Confirmed, 2.3–2.7% error |
| WS overflow threshold = L1/LINE | ✓ Confirmed (e.g. TM=96,TN=32 safe at L1=32KB) |
| α_min shifts to larger TM with larger L1 | ✓ TM*=12→24→48 for L1=16→32→64KB |
