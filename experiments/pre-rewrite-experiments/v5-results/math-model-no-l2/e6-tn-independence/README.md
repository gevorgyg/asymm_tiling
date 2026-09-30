# E6-nol2: Full α(TM, TN) Surface and TM* Shift in L1-only

**Goal**: measure the complete 8×5 α(TM, TN) grid at gc=0, then test whether
the TM*-vs-TN prediction (Part 1: TN-blind E3 table; Part 2: TN-aware
calibrated α) matches the empirical optimal.

**Config**: M=192, N=K=TK=256, TM ∈ {8,12,16,24,32,48,64,96}, TN ∈ {4,8,16,32,64},
gc=50 (α-dominated, gc* ≈ 220 at TM=64), no-L2.

---

## α(TM, TN) table (gc=0)

```
   TM  regime       TN=4       TN=8      TN=16      TN=32      TN=64    E3(32)
    8     L1   3.3997     3.3973     3.3963     3.3958     3.3957      3.3958
   12     L1   3.3159     3.3146     3.3139     3.3133     3.4378†     3.3133
   16     L1   6.0524     4.6403     3.9343     3.5811     3.4041      3.5811
   24   DRAM   6.0067     4.5966     3.8916     3.5387     3.3617      3.5387
   32   DRAM   5.9839     4.5747     3.8701     3.5174     3.3403 *    3.5174
   48   DRAM   5.9609     4.5527     3.8486     3.4959     4.3896 **   3.4959
   64   DRAM   5.9492     4.5415     3.8377     3.4849 *   8.8731 **   3.4849
   96   DRAM   5.9374     4.5302     3.8266     9.0329 **  8.8756 **   9.0329
```
`*` WS ≥ 256 lines (borderline), `**` WS ≥ 300 lines (catastrophic C eviction).  
`†` mild overflow: A+C+FIFO≈256 lines at TM=12, TN=64.

---

## Finding 1: C = 11.26 ≈ 11.0 — universal across all DRAM-regime TMs

Fit α(TM, TN) = α₀(TM) + C/TN using only safe (WS < 256) points:

| TM | safe pts | α₀(TM) | C (fit) | C (formula) | err% |
|----|----------|---------|---------|-------------|------|
| 24 | 5 | 3.1859 | **11.284** | 11.0 | +2.58% |
| 32 | 4 | 3.1653 | **11.275** | 11.0 | +2.50% |
| 48 | 4 | 3.1441 | **11.268** | 11.0 | +2.43% |
| 64 | 3 | 3.1339 | **11.262** | 11.0 | +2.38% |
| 96 | 3 | 3.1230 | **11.258** | 11.0 | +2.34% |

The coefficient C = (DRAM_lat − L1_lat) / (REG_M × REG_K) = (180−4)/16 = 11.0
is confirmed empirically at +2.3–2.6% across all tile sizes. This matches the
accuracy from E3-nol2 (TM=32: C=11.27) and E4d (TM=96: C=11.26). Universal.

---

## Finding 2: TM=8 and TM=12 (L1 tiles) are TN-independent — TM=16 is not

TM=8: α varies 3.3957–3.3997 across TN=4..64. Variation = 0.004. C ≈ 0. ✓  
TM=12: α varies 3.3133–3.3159 for TN=4..32. Variation = 0.003. C ≈ 0. ✓

**TM=16 shows large TN dependence**: α = 3.404 (TN=64) to 6.052 (TN=4).  
Fit gives C ≈ 11.3 — same as the DRAM-regime tiles.

This is because TM=16 fills L1 exactly (16×256×4 = 16,384 bytes = L1). Other
data in L1 (FIFO staging, C tile) evicts A lines immediately on each pass.
**TM=16 is functionally in the DRAM regime**, not the L1 regime. The safe
boundary for TN-independence is **TM ≤ 12**, not TM ≤ 16.

---

## Finding 3: TM* shifts dramatically with TN (unlike L2 case)

Part 1 and Part 2 summary at gc=50:

| TN | Part 1 (E3-nol2 TN=32 α) predicts | empirical TM* | Part 2 (calib α) predicts | match? |
|----|-------------------------------------|---------------|---------------------------|--------|
| 4  | 64 | **12** | 12 | ✓ |
| 8  | 64 | **12** | 12 | ✓ |
| 16 | 64 | **96** | 96 | ✓ |
| 32 | 64 | **64** | 64 | ✓ |
| 64 | 32 | **32** | 32 | ✓ |

**Part 1 fails 3/5 TN values.** The TN-blind model (using E3-nol2 α calibrated
at TN=32 only) systematically underestimates α for DRAM-regime tiles at small
TN. It predicts TM*=64 for all TN, when in reality TM* varies by 8× (from 12
to 96) across the TN range.

**Part 2 matches perfectly (5/5).** Using the TN-specific calibrated α, prediction
errors are < 1% across all safe tiles — the model T = MNK × max(α(TM,TN), gc/TM)
is correct once the TN argument is properly included.

### Why TM* = 12 at TN = 4 and 8

At TN=4: all DRAM tiles get α ≈ 3.15 + 11/4 = 5.90–6.05. At gc=50: for each DRAM tile,
max(α, gc/TM) = α (since gc/TM ≤ 50/24 = 2.08). So T/MNK ≈ 5.9+ for all DRAM tiles.
For TM=12 (L1, C≈0): max(3.31, 50/12=4.17) = 4.17 ← best. For TM=8: max(3.40, 6.25) = 6.25.
**The 11/4 = 2.75 penalty on DRAM tiles makes the L1 tile TM=12 dominant.**

### Why TM* = 96 at TN = 16

At TN=16: DRAM-tile penalty = 11/16 = 0.69. All DRAM tiles have α ≈ 3.14+0.69 = 3.83.
Among them, TM=96 has the smallest gc/TM = 50/96 = 0.52, so max(3.83, 0.52) = 3.83.
TM=64: max(3.84, 0.78) = 3.84. The α surface is nearly flat among DRAM tiles at TN=16,
so the largest DRAM tile (TM=96) wins by minimizing the gc/TM term. TM=96 at TN=16
has WS=214 < 256 → safe (no C eviction).

### Why TM* = 32 at TN = 64

C-tile overflow limits larger tiles: TM=48, TN=64 has WS=394 (**), TM=64, TN=64 has
WS=526 (**). Both show catastrophic α spike (4.39 and 8.87 respectively). The largest
safe tile at TN=64 is TM=32 (WS=262, borderline * but empirically fine, α=3.340).

---

## Safe operating region summary

| TN | largest safe TM | α at that tile | WS |
|----|-----------------|----------------|----|
| 4  | 96 | 5.937 | 70 |
| 8  | 96 | 4.530 | 118 |
| 16 | 96 | 3.827 | 214 |
| 32 | 64 (96=overflow) | 3.485 | 270 |
| 64 | 32 (48+=overflow) | 3.340 | 262 |

For TN=32: the globally preferred operating point is **TM=64** (minimum α for
the DRAM regime). For TN=64: **TM=32** is the safe maximum.

The **global α minimum** in the full safe grid is **TM=32, TN=64 (α=3.340)**
followed by TM=24, TN=64 (α=3.362). These are only useful when TN=64 can be
used, i.e., when N is divisible by 64. For N=256: valid.

---

## Implication for E8-nol2 and E13-nol2

The equation T = MNK × max(α(TM, TN), gc/TM) is correct, but **TN is no longer
a free parameter** in L1-only: it enters α directly through the 11/TN correction.

For E13-nol2 (FIFO vs Memory-B comparison):
- Use TN=32 as the canonical operating point (same as L2 experiments).
- Calibrate α(TM, TN=32) from E3-nol2 — the TN-blind table is valid at TN=32.
- At TN=32, TM*=64 for α-dominated gc, shifting to smaller TM as gc grows.
- Tiles TM=96 and larger are unsafe at TN=32 → excluded from comparison.

The TN-aware model α(TM, TN) = α₀(TM) + 11.26/TN is the correct formula for
arbitrary TN. For TN=32: α(TM, 32) = α₀(TM) + 0.352 ≈ α₀(TM) + 0.35 — this
matches the E3-nol2 table within < 0.03%.
