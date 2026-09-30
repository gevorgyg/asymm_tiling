# E3-nol2: α(TM) Calibration — L1-only

**Config**: M=N=K=256 (or M=192 where TM requires it), TK=256, A_P=4,
3D registers, C-stationary, `--no-l2`.  
**Sweep**: gc=0 (exact T = MNK × α, no B-cost contamination).

---

## Setup

- L1 = 16 KB = 256 cache lines of 64 B, fully associative.
- L2 bypassed — all L1 misses go directly to DRAM (180 cy).
- L1 latency = 4 cy; DRAM latency = 180 cy.
- A-tile L1 overflow threshold: TM × TK × A_P = L1 → **TM_L1 = 16**.

---

## S1: α(TM) at TN=32

| TM | A-tile | regime | cycles | C_fill | α(TM) |
|----|--------|--------|--------|--------|-------|
| 4  | 4 KB   | L1  | 45,876,840  | 14.584 | 3.6460 |
| 8  | 8 KB   | L1  | 42,729,192  | 13.583 | 3.3958 |
| 12 | 12 KB  | L1  | 41,691,496  | 13.253 | 3.3133 ← min in L1 range |
| 16 | 16 KB  | L1  | 45,060,288  | 14.324 | 3.5811 ← L1 boundary |
| 24 | 24 KB  | DRAM | 44,527,040 | 14.155 | 3.5387 |
| 32 | 32 KB  | DRAM | 44,258,976 | 14.070 | 3.5174 |
| 48 | 48 KB  | DRAM | 43,988,032 | 13.983 | 3.4959 |
| 64 | 64 KB  | DRAM | 43,849,680 | 13.939 | 3.4849 ← min in DRAM range |
| 96 | 96 KB  | DRAM | 113,660,768 | 36.132 | **9.0329** ← large jump |
| 128 | 128 KB | DRAM | 151,843,296 | 36.202 | **9.0506** |

---

## S2: TN sweep at TM=8 (A in L1)

| TN | R=TN/4 | cycles | α | C_fill/R |
|----|--------|--------|---|----------|
| 4  | 1  | 57,044,896 | 3.4001 | 13.601 |
| 8  | 2  | 57,005,316 | 3.3978 | 6.796  |
| 16 | 4  | 56,988,316 | 3.3968 | 3.397  |
| 32 | 8  | 56,979,816 | 3.3963 | 1.698  |
| 64 | 16 | 56,978,536 | 3.3962 | 0.849  |

**α = 3.396 ± 0.002 across all TN — perfect TN-independence.**

---

## S3: TN sweep at TM=32 (A overflows L1)

| TN | R=TN/4 | cycles | α | C_fill/R |
|----|--------|--------|---|----------|
| 4  | 1   | 100,394,368 | 5.9840 | 23.936 |
| 8  | 2   | 76,752,768  | 4.5748 | 9.150  |
| 16 | 4   | 64,931,968  | 3.8702 | 3.870  |
| 32 | 8   | 59,015,808  | 3.5176 | 1.759  |
| 64 | 16  | 56,049,088  | 3.3408 | 0.835  |

**α varies 3.34–5.98: TN-independence BREAKS for TM=32 in L1-only.**

Fit: α(TM=32, TN) ≈ **3.166 + 11.27/TN** (< 0.03% error across all TN).  
Coefficient 11.27 ≈ (DRAM_lat − L1_lat) / (REG_M × REG_K) = (180−4)/16 = **11.0**.

---

## Key findings

### 1. α in L1-only is ≈ 3.4 for TM ≤ 64 — nearly identical to the L2 case

Expected prediction: α ≈ 1 (L1-warm) or α ≈ 45 (DRAM every load). Actual: α ≈
3.4, same as with L2. The cost driver is **not A cache-miss latency** but rather
the structural overhead of C loads/stores and FIFO B staging — these dominate
regardless of where A lives in the hierarchy.

The L1-only and L2-present α tables are:

| TM | α — with L2 | α — no L2 (TN=32) |
|----|-------------|-------------------|
| 8  | 3.400       | 3.396             |
| 16 | 3.300       | 3.581             |
| 32 | 3.237       | 3.517             |
| 48 | 3.255       | 3.496             |
| 64 | 3.560       | 3.485             |
| 96 | 3.940       | **9.033**         |
| 128 | 3.936      | **9.051**         |

Below TM=96 the values are nearly interchangeable. Above TM=64, they diverge sharply.

### 2. The α threshold is at TM≈80, not at TM=16

The A-tile L1 overflow (at TM=16) causes no α jump — the large jump is between
TM=64 (α=3.48) and TM=96 (α=9.03). This corresponds to the **C tile approaching
L1 capacity**: at TM=96, TN=32, the C tile = 96×32×4 = 12 KB = 192 cache lines,
consuming 75% of L1. The combined working set (C + A per-rti + B) exceeds L1,
causing C evictions to DRAM. This is the "C eviction regime," not the "A DRAM
regime" that was predicted.

### 3. TN independence holds for TM ≤ 64, breaks for TM=32

- **TM=8 (S2)**: α = 3.396 ± 0.002 — essentially flat. TN is free.
- **TM=32 (S3)**: α follows α₀ + C/TN with C ≈ 11.3. TN matters significantly.

The formula α(TM, TN) = α₀(TM) + C(TM)/TN from the L2 experiments carries over
to L1-only, but the **coefficient C is much larger**: in the L2 case C ≈ 0.625
(L2 regime), here C ≈ 11.0 = (DRAM_lat − L1_lat)/(REG_M × REG_K). The physical
reason: cold A fills now go to DRAM (180 cy) instead of L2 (14 cy).

**Implication**: for TM ≤ 16 (A in L1), C ≈ 0 and TN-independence holds tightly.
For 16 < TM ≤ 64, C ≈ 11.0 and the model T = MNK × max(α, gc/TM) with fixed
TN=32 is still usable as a calibration point, but TN is no longer truly free.
For TM ≥ 96, α is large (≈9) and those tiles are not competitive anyway.

### 4. Good news for E13-nol2 (FIFO vs Memory-B)

The "safe operating range" (TM ≤ 64, TN=32) has α ≈ 3.5, similar to the L2 case.
This means the FIFO advantage in L1-only is similar in scale to the L2 case.
The key question (crossover gc*) will be answered by E13-nol2 once we measure
the Memory-B α table in L1-only.

---

## α table for use in subsequent experiments

Use TN=32 as the calibration reference (α(TM) = α at TN=32):

| TM | α(TM, TN=32) | safe? |
|----|--------------|-------|
| 4  | 3.6460       | yes (L1) |
| 8  | 3.3958       | yes (L1) |
| 12 | 3.3133       | yes (L1, minimum) |
| 16 | 3.5811       | yes (L1 edge) |
| 24 | 3.5387       | yes (DRAM) |
| 32 | 3.5174       | yes (DRAM) |
| 48 | 3.4959       | yes (DRAM) |
| 64 | 3.4849       | yes (DRAM, minimum) |
| 96 | 9.0329       | **avoid** (C eviction) |
| 128 | 9.0506      | **avoid** (C eviction) |

Overall minimum α at TN=32: **TM=12 (α=3.313)** in L1 regime, **TM=64 (α=3.485)**
in DRAM regime.

---

## Implications for TM* selection (FIFO mode, gc=0)

TM* = argmin α(TM) = TM=12 (global min, but requires M divisible by 12).
For M=256: TM* = 64 (lowest α among {8,16,32,64,128} that divide 256).

For gc > 0: TM* shifts towards larger TM as gc grows (FIFO cost amortization),
until crossing the TM=64→96 cliff, after which TM > 64 is never competitive.
TM=96 (α=9.03) is always dominated by TM=64 (α=3.48) for any gc.
