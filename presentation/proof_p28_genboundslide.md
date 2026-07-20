# Proof Table — Page 28 (Gen-Bound: Globally Optimal Tile vs gc)

Source: `experiments/v5-results/math-model-no-l2/e8-gc-boundary-sweep/results.json`  
Setup: M=192, N=K=256, TK=256, L1=16KB (fully associative, no L2), A_P=B_P=4B

## Empirical globally optimal (TM*, TN*) per gc

| gc | TM* | TN* | emp cycles/MNK | Notes |
|----|-----|-----|----------------|-------|
| 15 | 12  | 32  | 3.3155         | Low gc: A-load bound, small L1 tile |
| 30 | 12  | 32  | 3.3179         |       |
| 38 | 12  | 32  | 3.3192         |       |
| 42 | 32  | 64  | 3.3415         | TN* jumps to 64 — TM* moves to DRAM regime |
| 47 | 32  | 64  | 3.3417         |       |
| 50 | 32  | 64  | 3.3418         |       |
| 52 | 32  | 64  | 3.3419         |       |
| 57 | 32  | 64  | 3.3420         |       |
| 68 | 32  | 64  | 3.3423         |       |
| 74 | 32  | 64  | 3.3425         |       |
| 100| 32  | 64  | 3.3433         |       |
| 150| 64  | 32  | 3.4894         | TM* shifts to 64; TN* drops back to 32 |
| 250| 96  | 16  | 3.8367         | Gen-bound regime: TM* maximized, TN* shrinks |
| 400| 96  | 16  | 4.2455         |       |

## TN* trajectory (matches slide caption "TN* drops 64→32→16 as gc grows")

- gc < 42: optimal TN*=32 (A-load bound, small tile regime)
- 42 ≤ gc ≤ 100: TN*=64 (TM shifts to DRAM regime; wider B tile reduces α penalty)
- gc=150: TN*=32 (TM*=64 is now optimal; TN=64 at TM=64 is unsafe — safe() fails)
- gc ≥ 250: TN*=16 (TM*=96; larger TN unsafe at TM=96; TN=16 minimizes α)

## Why TN* shrinks at high gc

At large TM (TM=96), the ws_lines constraint (tm*tn//8 + tm//4 - 2 < 300) limits TN.
This formula estimates L1 working-set cache lines for the C tile; exceeding ~300 causes C-tile eviction and α blowup:
- ws_lines(96, 32) = 406 > 300 → UNSAFE (α=9.03, broken)
- ws_lines(96, 16) = 214 < 300 → safe ✓ (α=3.827)
- ws_lines(96, 8)  = 118 < 300 → safe ✓, but α(96,8)=4.530 > α(96,16)=3.827

So TN=16 wins at TM=96 because it has the lowest α among safe TN values.

## Model prediction accuracy

All 14 gc values: model (TM*, TN*) = empirical (TM*, TN*). **100% correct.**

| gc  | model (TM,TN) | empirical (TM,TN) | match |
|-----|---------------|-------------------|-------|
| 15  | (12, 32)      | (12, 32)          | ✓     |
| 30  | (12, 32)      | (12, 32)          | ✓     |
| 38  | (12, 32)      | (12, 32)          | ✓     |
| 42  | (32, 64)      | (32, 64)          | ✓     |
| 47  | (32, 64)      | (32, 64)          | ✓     |
| 50  | (32, 64)      | (32, 64)          | ✓     |
| 52  | (32, 64)      | (32, 64)          | ✓     |
| 57  | (32, 64)      | (32, 64)          | ✓     |
| 68  | (32, 64)      | (32, 64)          | ✓     |
| 74  | (32, 64)      | (32, 64)          | ✓     |
| 100 | (32, 64)      | (32, 64)          | ✓     |
| 150 | (64, 32)      | (64, 32)          | ✓     |
| 250 | (96, 16)      | (96, 16)          | ✓     |
| 400 | (96, 16)      | (96, 16)          | ✓     |
