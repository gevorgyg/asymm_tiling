# E4-nol2: Why α ≈ 3.4 in L1-only, and Why α Jumps at TM=96

Probes the mechanism behind the two E3-nol2 surprises:
1. α ≈ 3.4 for TM=4..64, nearly identical to the L2 case.
2. α jumps sharply to ≈9.0 at TM=96, not at TM=16 (A's L1 overflow boundary).

**Hardware constants**: L1=16KB, L1_lat=4 cy, DRAM_lat=180 cy, no L2.

---

## E4a: TK sweep (TM=32, TN=32)

In the L2 case, warm-C fraction determines the TK sensitivity.

| TK | warm-C% | cycles | α |
|----|---------|--------|---|
| 4   | 0.0%   | 59,781,888  | 3.5633 |
| 8   | 50.0%  | 59,392,768  | 3.5401 |
| 16  | 75.0%  | 59,198,208  | 3.5285 |
| 32  | 87.5%  | 59,100,928  | 3.5227 |
| 64  | 93.8%  | 59,052,288  | 3.5198 |
| 128 | 96.9%  | 59,027,968  | 3.5183 |
| 256 | 98.4%  | 59,015,808  | 3.5176 |

**α barely changes with TK: only 0.045 across 0%→98% warm-C fraction.**

Reason: the working set between consecutive accesses to the same C line is small
enough that **C stays warm in L1 regardless of TK**. At TK=4 (100% "cold" by
the warm-C formula), there is only 1 rtk pass per C line, so "warm" vs "cold" is
moot — but the same C line is revisited across rtk chunk iterations and stays in
L1 each time. The actual number of cold DRAM fills for C is always 64 (one per
unique C line per session), contributing only 0.044 to α.

---

## E4b: L1_ACCESS_CYCLES sweep (TM=8 and TM=32, TN=32, MEM=180 fixed)

| L1_lat | α (TM=8) | α (TM=32) |
|--------|----------|-----------|
| 2  | 1.8884 | 2.0098 |
| 4  | 3.3963 | 3.5176 |
| 6  | 4.9041 | 5.0254 |
| 8  | 6.4119 | 6.5333 |
| 12 | 9.4276 | 9.5489 |
| 16 | 12.4433 | 12.5645 |

**Linear fit: α = m × L1_lat + b**

| TM | slope m | intercept b |
|----|---------|-------------|
| 8  | **0.7539** | 0.381 |
| 32 | **0.7539** | 0.502 |

**Finding: α is nearly perfectly proportional to L1_lat, with identical slope for
TM=8 and TM=32.** The dominant cost driver is **warm L1 accesses** — C
loads/stores and B FIFO loads that hit L1. These accesses do not depend on whether
A is in L1 (TM=8) or DRAM (TM=32), which is why the slope is TM-independent.

The intercept difference (0.502 vs 0.381) captures the extra DRAM cost for A
at TM=32.

The L1 contribution at the default L1_lat=4: **α_L1 = 0.7539 × 4 = 3.016** out
of total α ≈ 3.4. **L1 warm hits account for ≈89% of total α.**

---

## E4c: MEM_ACCESS_CYCLES sweep (TM=8 and TM=32, TN=32, L1=4 fixed)

| MEM_lat | α (TM=8) | α (TM=32) |
|---------|----------|-----------|
| 45  | 3.2984 | 3.1880 |
| 90  | 3.3310 | 3.2979 |
| 135 | 3.3636 | 3.4078 |
| 180 | 3.3963 | 3.5176 |
| 270 | 3.4615 | 3.7373 |
| 360 | 3.5267 | 3.9571 |

**Linear fit: α = m × MEM_lat + b**

| TM | slope m | intercept b |
|----|---------|-------------|
| 8  | 0.000725 | 3.266 |
| 32 | 0.002441 | 3.078 |

**Finding: α is nearly flat with respect to MEM_lat.** At TM=8, an 8× increase
in DRAM latency (45→360) changes α by only 7%. DRAM contributes **≈11% of α**
at the default MEM=180, L1=4. This confirms warm L1 hits dominate.

**L1 slope is 0.754 / 0.000725 = 1040× more impactful per cycle than MEM slope
at TM=8.** Each cycle of L1 latency matters 1040× more than each cycle of DRAM
latency.

The extra MEM sensitivity at TM=32 vs TM=8: Δslope = 0.002441 - 0.000725 = 0.00172.
This matches the A cold-fill contribution: A_loads/MNK = 32,768/16,777,216 = 0.00195.
**The additional DRAM slope at TM=32 is almost entirely from A cold fills to DRAM.**

---

## E4d: TN sweep at TM=96 (the α-jump regime)

| TN | C tile (lines) | Working set | cycles | α |
|----|----------------|-------------|--------|---|
| 4  | 24  | 70  (<256) | 74,709,888 | **5.9374** |
| 8  | 48  | 118 (<256) | 57,003,008 | **4.5302** |
| 16 | 96  | 214 (<256) | 48,149,568 | **3.8266** |
| 32 | 192 | 406 (>256) | 113,660,768 | **9.0329** |

Working set = lines accessed between consecutive accesses to the same C line:
**WS ≈ TM×TN/8 + TM/4 − 2** (C lines + B lines + A lines in the inner-loop cycle).

At TN=16, TM=96: WS=214 < L1=256. **C stays in L1 → α≈3.83 (normal).**  
At TN=32, TM=96: WS=406 > L1=256. **C evicted to DRAM → α=9.03 (spike).**

**The α jump is caused by C line eviction.** When WS > 256, L1 can no longer
hold all the data accessed between C reuses. C lines are evicted to DRAM (180 cy)
before each reuse — since C is accessed TK/REG_K=64 times per unique line, each
eviction is catastrophically expensive.

**Formula for TN=4,8,16 at TM=96 (non-overflow regime):**
α(TM=96, TN) ≈ 3.123 + **11.26/TN**

The coefficient 11.26 matches E3-nol2 S3 (TM=32: C=11.27) exactly. The cold-fill
correction term is universal: **C ≈ (DRAM_lat − L1_lat) / (REG_M × REG_K) = (180−4)/16 = 11.0**.

---

## Grand mechanism summary

**α in L1-only follows a two-parameter model:**

```
α(TM, TN) ≈ 0.754 × L1_lat  +  α_DRAM(TM, TN)
```

where:
- **0.754 × L1_lat** = warm L1 accesses (C loads/stores + FIFO B + warm A if in L1).
  This term dominates: at L1_lat=4, it contributes 3.02 out of α≈3.4 (89%).
  It is TM-independent (driven by C and B, not A).

- **α_DRAM(TM, TN)** = DRAM cold-fill contribution:
  - In-L1 regime (TM ≤ 16): small constant (A warm in L1)
  - DRAM regime (TM > 16): ≈ α₀(TM) + 11.0/TN from A cold fills
  - Overflow regime (WS > L1/LINE): large spike when C is evicted (avoid this regime!)

**Why α ≈ 3.4 is similar to the L2 case:**  
Removing L2 barely changes α because almost all accesses are warm L1 hits.
DRAM cold fills (FIFO B and A overflows) contribute only ≈11% of cycles at
typical operating points. The L2 case had the same warm L1 dominance; the
"C_fill ≈ L2_lat" coincidence of E4 (L2) was not because A misses to L2 dominate,
but because the formula C_fill = T×reg_n/MNK happened to equal L2_lat numerically.

**Why α jumps at TM=96 (not TM=16):**  
The jump is not triggered by A leaving L1 (TM=16 boundary). It is triggered when
the **C tile working set overflows L1**, evicting hot C lines to DRAM. For TN=32,
this happens between TM=64 (WS=270, overflow by 14 lines → tolerable) and TM=96
(WS=406, overflow by 150 lines → catastrophic).

**Practical implication:** TM ≥ 96 with TN=32 should be avoided. For TM=96, use
TN ≤ 16 if needed. For TM ≤ 64, any TN ≤ 64 is safe (WS stays below 256).
