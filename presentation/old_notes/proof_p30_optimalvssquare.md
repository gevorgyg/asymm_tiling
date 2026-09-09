# Proof Table — Page 30 (Optimal Asymmetric vs Square Tile)

Source: `experiments/v5-results/math-model-no-l2/e8-gc-boundary-sweep/results.json`  
Setup: M=192, N=K=256, TK=256, L1=16KB (fully associative, no L2), A_P=B_P=4B  
Comparison: for each TN, best TM* empirically vs square TM=TN

## Speedup of optimal TM* over square TM=TN (per TN)

| gc  | TN=8: opt/sq, spd% | TN=16: opt/sq, spd% | TN=32: opt/sq, spd% | TN=64: opt/sq, spd% |
|-----|---------------------|----------------------|----------------------|----------------------|
| 15  | TM=12/8, **2.6%**   | TM=12/16, **15.7%**  | TM=12/32, **5.8%**   | TM=32/64, **62.4%**  |
| 30  | TM=12/8, **14.7%**  | TM=12/16, **15.7%**  | TM=12/32, **5.7%**   | TM=32/64, **62.3%**  |
| 38  | TM=12/8, **31.5%**  | TM=12/16, **15.7%**  | TM=12/32, **5.7%**   | TM=32/64, **62.3%**  |
| 42  | TM=12/8, **31.7%**  | TM=12/16, **7.8%**   | TM=64/32, **1.0%**   | TM=32/64, **62.3%**  |
| 47  | TM=12/8, **31.9%**  | TM=96/16, **3.0%**   | TM=64/32, **1.0%**   | TM=32/64, **62.3%**  |
| 57  | TM=96/8, **37.2%**  | TM=96/16, **3.0%**   | TM=64/32, **1.0%**   | TM=32/64, **62.3%**  |
| 100 | TM=96/8, **64.0%**  | TM=96/16, **39.4%**  | TM=64/32, **1.0%**   | TM=32/64, **62.3%**  |
| 150 | TM=96/8, **75.9%**  | TM=96/16, **59.4%**  | TM=64/32, **26.6%**  | TM=48/64, **50.5%**  |
| 250 | TM=96/8, **85.5%**  | TM=96/16, **75.6%**  | TM=64/32, **49.3%**  | TM=48/64, **40.2%**  |
| 400 | TM=96/8, **90.9%**  | TM=96/16, **83.1%**  | TM=64/32, **49.6%**  | TM=48/64, **5.2%**   |

## Slide text claims verification (page 29)

The slide says: gc=100: 20–40% faster, gc=250: ~75% faster, gc=400: up to 85% faster.

- **gc=100**: TN=16 gives 39.4%, TN=8 gives 64%, TN=32 gives 1%. The "20–40%" range roughly matches TN=16. TN=8 is much higher (64%). The claim is accurate only for TN=16; the range is more like 1–64%.
- **gc=250**: TN=16 gives 75.6% → "~75%" is accurate for TN=16.
- **gc=400**: TN=16 gives 83.1%, TN=8 gives 90.9%. "up to 85%" is correct for TN=16 but actually TN=8 exceeds it.

**Recommendation**: Update page 29 to say "20–90% faster" at gc=100, or make it TN-specific.

## Explanations for page 30 graph behaviors (for script notes)

### 1. Why TN=64 (red) is a flat line in performance and its speedup DROPS at high gc

**Left panel (performance):**
- Square TM=64,TN=64: C tile = 64×64×4 = 16384 bytes = exactly L1 size. The C tile saturates L1 entirely, causing constant A-eviction on every new K iteration. Cost ≈ 8.9 cycles throughout — independent of gc.
- Optimal TM* for TN=64: starts at TM=32 (cost ≈ 3.3 at low gc) and rises. But TN=64 tiles have tight register constraints — only TM ≤ 48 is feasible. So the optimal can't grow TM large enough to amortize high gc.

**Right panel (speedup):**
- At low gc: optimal=3.3, square≈8.9 → large 62% speedup (free lunch from choosing smaller TM that avoids L1 overflow)
- As gc rises: the optimal tile for TN=64 (TM=48 at high gc) becomes gen-bound (g_c/TM = 400/48 ≈ 8.3 ≈ square cost). The gap shrinks → speedup drops to ~5% at gc=400.
- TN=64 is a poor choice at high gc precisely because it can't use large TM.

### 2. Why some TN lines show ~0% speedup at low/mid gc then jump (the "cliff")

The cliff is the **square tile transitioning from A-load bound to gen-bound**:

- When gc is small: for the square tile (TM=TN), g_c/TM = g_c/TN is small → square is A-load bound. Optimal TM* is also A-load bound (just at a different α). The gap is small → speedup ≈ 0–few%.
- **Cliff point**: When g_c/TN > α(TN, TN), the square tile enters gen-bound territory. Its cost = g_c/TN starts growing linearly with gc. The optimal tile (at larger TM*) stays A-load bound longer.
- After cliff: square cost rises fast (∝ g_c), optimal stays flat → speedup grows rapidly.

**For TN=32**: cliff at g_c ≈ TN × α(32,32) ≈ 32 × 3.52 ≈ 113.  
Between gc=42 and gc=100, speedup is ≈1% (flat). At gc=150 it jumps to 26.6%. This matches exactly.

**For TN=16**: cliff at g_c ≈ 16 × α(16,16) ≈ 16 × 6.3 ≈ 101.  
Speedup dips to ~3% around gc=47–57, then climbs back to 75%+ at gc=250.

**For TN=8**: cliff is very early (g_c ≈ 8 × α(8,8) ≈ small). Speedup starts growing from gc≈30 onward.
