# L1-only Math Model: Concepts, Terms, and Experiment Results

This document explains every term used in the no-L2 experiment series,
then summarises the findings from each completed experiment.

---

## Part 1: The hardware being modelled

### The memory hierarchy

The simulator models a chip with a small cache (L1) and main memory (DRAM).
In the `--no-l2` mode that all these experiments use, there is only one cache
level:

```
CPU ─→ L1 cache (16 KB, 4-cycle latency)
             │ miss
             ▼
          DRAM (unlimited, 180-cycle latency)
```

A **cache hit** means the data was already in L1 → costs 4 cycles.  
A **cache miss** means data must be fetched from DRAM → costs 180 cycles.

The ratio 180/4 = **45×** is the key penalty for any cache miss in this environment.

### The matrix multiply (GEMM) kernel

The kernel computes: **C = A × B**, where A is M×K, B is K×N, C is M×N.

In all these experiments: M=192 (or 256), N=K=256, element size = 4 bytes.

The total number of multiply-accumulate operations is **MNK = M×N×K** (e.g.,
192×256×256 = 12,582,912).

### Tiles

The kernel does not operate on the full matrices at once. It breaks them into
rectangular *tiles* that fit in registers or cache.

- **TM, TN, TK**: the tile dimensions in the M, N, K directions. For these
  experiments TK=256 (equal to K, so there is only one K chunk per tile).
  TM and TN are the dimensions we sweep over.
- **A tile**: TM × TK elements × 4 bytes. Represents a horizontal strip of A.
- **B tile**: TK × TN elements × 4 bytes. Represents a vertical strip of B.
- **C tile**: TM × TN elements × 4 bytes. Represents one output block.

### Register tiles and inner-loop structure

Inside each (TM, TN) macro tile, the computation is done in tiny **register
tiles** of size REG_M × REG_N = 4×4 elements (each a 64-byte cache line).

The innermost loops iterate over:
- **rti** = 0 … TM/4−1 (register tiles in the M direction, TM/REG_M of them)
- **rtj** = 0 … TN/4−1 (register tiles in the N direction, TN/REG_N of them)  
- **rtk** = 0 … TK/4−1 = 63 (register tiles in the K direction)

For every (rti, rtj, rtk) triple: load A[rti, rtk], load B[rtk, rtj], accumulate
into C[rti, rtj].

**C-stationary** means: the C register tile C[rti, rtj] is kept in a register
buffer across all rtk iterations (rather than being written back to memory after
each rtk step). It is only written to memory once per (rti, rtj) pair.

**three_d_reg=True** enables a 3D register file — a fast on-chip buffer that
stores all (TM/4)×(TN/4) C register tiles simultaneously, so C does not need
to be moved in and out of L1 during computation.

**mulac_norecord=True** suppresses recording of C back to memory (used only for
clean α measurement — we want to measure A/B access cost, not C writeback cost).

---

## Part 2: The math model

### What α (alpha) is

α is defined as: **α = total simulation cycles / MNK**

It is the "normalised cost" of the computation — how many cycles per
multiply-accumulate operation, on average. If α=3.5, the kernel takes
3.5 cycles per FMA.

At gc=0 (explained below), α captures *only* the cost of loading A and B
tiles (and the fixed C register overhead). It is measured by running with
no FIFO generation cost.

### The model equation

```
T = MNK × max(α(TM, TN),  gc / TM)
```

- **T**: total simulated cycles for the full GEMM.
- **α(TM, TN)**: the cost per operation when B is free (gc=0). Measured
  from simulation. Encodes the A-loading and warm-C overhead.
- **gc / TM**: the FIFO B generation cost, amortised over the TM rows that
  share each B column. At large TM the FIFO cost per operation goes down.
- **max(...)**: the kernel is bottlenecked by whichever cost is larger —
  either the A/C access overhead (α) or the B generation overhead (gc/TM).

### What gc is

**gc** = PRNG_FIFO_GEN_COST = the number of cycles it takes the PRNG hardware
to generate each B element for the FIFO.

- gc=0: B elements arrive instantly (free). Used for calibration only.
- gc=50: each B element costs 50 cycles to generate. Moderate cost.
- gc=130: high cost, similar to a typical use case.

At gc=0 the model reduces to T = MNK × α, so simulating at gc=0 directly
measures α.

### What TM* is

**TM**(gc) = the optimal tile height — the TM that minimises T for a given gc.

There is a tradeoff:
- Large TM → fewer tile iterations in the M direction → lower gc/TM (FIFO cost
  is amortised over more rows). But large TM may overflow L1, increasing α.
- Small TM → higher gc/TM (FIFO overhead per operation). But A fits in L1,
  giving lower α.

The model predicts TM* by finding the TM that minimises max(α(TM, TN), gc/TM).

### C_fill and its relation to α

**C_fill(TM)** = cycles per A register-tile load.

```
α(TM) = C_fill(TM) / REG_N
```

REG_N = 4, so α = C_fill / 4. We often work directly with α.

---

## Part 3: The two B sources

### FIFO-B (b_source="prng_fifo")

B elements are generated on-chip by a pseudo-random number generator (PRNG)
and fed through a FIFO buffer to the kernel. B never comes from DRAM in this
mode — it is "produced" instead of "loaded". The cost per element is gc cycles.

At gc=0: B is free. Used for all calibration (α measurement) experiments.

### Memory-B (b_source="memory")

B elements are read from DRAM every time they are needed. The B tile
(TK × TN × 4 = 256 × TN × 4 bytes) is much larger than L1 (for TN=32:
256×32×4 = 32 KB >> 16 KB), so every B access is a DRAM miss (180 cycles).

Memory-B is the reference for E13 (the FIFO vs Memory-B comparison).

---

## Part 4: Regime terminology

### "L1 regime" vs "DRAM regime" (for the A tile)

This refers to whether the **A tile** fits in L1:

```
A tile size = TM × TK × A_P = TM × 256 × 4 bytes
L1 boundary: A tile = L1 → TM = 16384 / (256 × 4) = 16
```

- **L1 regime**: TM ≤ 12. A tile (≤ 12 KB) fits in L1. A lines can stay
  warm between consecutive accesses → re-loads cost L1_lat = 4 cycles.
- **DRAM regime**: TM ≥ 16. A tile (≥ 16 KB) does not fit in L1 (the
  boundary tile TM=16 exactly fills L1 but gets evicted by other traffic).
  A lines must be re-fetched from DRAM (180 cycles) on each new TN pass.

Why does this matter? Each time a new N-column block (rtj pass) starts, the
A lines must be re-read. If A is in L1 they are warm (cheap). If A is in
DRAM they are cold (expensive). This is what causes the 1/TN correction in α.

### "C eviction" / "WS overflow" regime

The simulation keeps all C register tiles in L1 simultaneously. If the
combined working set of C + A + B exceeds L1 capacity (256 cache lines),
C lines start getting evicted to DRAM between accesses — which is catastrophic
because each C line is accessed TK/REG_K = 64 times.

Working set formula:
```
WS = TM×TN/8 + TM/4 − 2   (lines accessed between two C[i,j] accesses)
```
- WS < 256: safe — all C lines stay in L1.
- WS ≥ 256: some C lines get evicted. Small overflows (< 5%) are tolerable.
- WS ≥ 300: catastrophic — α spikes to ≈ 9.

The danger zone at TN=32 starts around TM=96 (WS=406). At TN=64 it starts
at TM=48 (WS=394).

---

## Part 5: The cold-fill correction term C

α(TM, TN) has a TN dependence in the DRAM regime because of **cold fills**.

When the first rtj pass (rtj=0) begins for a new rtk chunk, A lines are not
yet in L1 (cold). They must be loaded from the next level. In L1-only: DRAM
(180 cycles). In subsequent rtj passes (rtj=1, 2, …): A lines are warm in L1
(4 cycles).

The correction per FMA operation averages out to:

```
α(TM, TN) = α₀(TM)  +  C(TM) / TN
```

where:
```
C = (next_level_latency − L1_latency) / (REG_M × REG_K)
```

| Hierarchy | next_level_latency | C |
|---|---|---|
| L1-only | DRAM = 180 cy | (180−4)/16 = **11.0** |
| L1 + L2 | L2 = 14 cy | (14−4)/16 = **0.625** |

The factor 1/TN appears because the cold fill cost is paid once per A tile
(at the start of TN processing), and TN is the number of N-columns in the tile.
Larger TN → cost amortised over more columns → smaller per-operation penalty.

**In the L1 regime (TM ≤ 12):** A stays warm in L1 across TN passes → no cold
fill. C ≈ 0 and α is independent of TN.

**In the DRAM regime (TM ≥ 16):** A is evicted between TN passes → C = 11.0.

**The analytical formula (no calibration needed):**
```
α(TM, TN) ≈ α_E3(TM) + C × (1/TN − 1/32)
```
where α_E3(TM) is the E3-nol2 measured value at TN=32, and C = 11.0.
At TN=32 the formula reduces to α_E3(TM) exactly.

---

## Part 6: Experiment results

### E3-nol2: α calibration at gc=0

**What it does**: measures α(TM) at TN=32 (the reference operating point)
and α(TM, TN) at two representative TM values (TM=8 in L1, TM=32 in DRAM).

**α(TM) table at TN=32:**

| TM | A tile | regime | α(TM) | note |
|----|--------|--------|-------|------|
| 4  | 4 KB  | L1   | 3.6460 |  |
| 8  | 8 KB  | L1   | 3.3958 |  |
| 12 | 12 KB | L1   | **3.3133** | min in L1 regime |
| 16 | 16 KB | DRAM | 3.5811 | L1 boundary, functionally DRAM |
| 24 | 24 KB | DRAM | 3.5387 |  |
| 32 | 32 KB | DRAM | 3.5174 |  |
| 48 | 48 KB | DRAM | 3.4959 |  |
| 64 | 64 KB | DRAM | **3.4849** | min in DRAM regime |
| 96 | 96 KB | DRAM | 9.0329 | **avoid**: C eviction at TN=32 |

**Key surprises:**
1. α ≈ 3.4 for TM=4..64 — **nearly identical to the L2 case**, despite no L2
   and a 45× larger DRAM penalty. The dominant cost is warm L1 hits (C
   tile loading/storing), not A cache misses.
2. The α jump happens at TM=96 (not TM=16). TM=16 being the A-tile L1
   overflow boundary has almost no visible effect. The jump at TM=96 is
   from C-tile eviction.
3. **TN-independence breaks for TM=32 (DRAM regime)**:
   α(TM=32, TN) = 3.166 + 11.27/TN — C=11.27 ≈ formula value 11.0.
4. **TN-independence holds for TM=8 (L1 regime)**: α = 3.396 ± 0.002.

---

### E4-nol2: why α ≈ 3.4 (mechanism)

**What it does**: identifies what fraction of α comes from L1 warm hits vs
DRAM cold fills, by sweeping L1_lat and DRAM_lat independently.

**E4a (TK sweep):** α varies only 0.045 across TK=4..256. C tiles stay warm
in L1 regardless of TK — the "warm-C fraction" formula does not govern α here.

**E4b (L1_lat sweep at TM=8 and TM=32):**

| L1_lat | α (TM=8) | α (TM=32) |
|--------|----------|-----------|
| 2  | 1.888 | 2.010 |
| 4  | 3.396 | 3.518 |
| 8  | 6.412 | 6.533 |
| 16 | 12.44 | 12.56 |

Slope = **0.7539** for both TM=8 and TM=32 (identical).
→ α scales linearly with L1_lat, and the slope does not depend on whether A
is in L1 or DRAM. This means the dominant cost is **warm L1 accesses** that
do not involve A at all (C tile + FIFO B staging).

**L1 latency contribution at default L1_lat=4:**
0.7539 × 4 = **3.016** out of α ≈ 3.4 → L1 warm hits account for **89%** of α.

**E4c (DRAM_lat sweep at TM=8 and TM=32):**

| DRAM_lat | α (TM=8) | α (TM=32) |
|----------|----------|-----------|
| 45  | 3.298 | 3.188 |
| 180 | 3.396 | 3.518 |
| 360 | 3.527 | 3.957 |

Slopes: 0.000725 (TM=8) and 0.002441 (TM=32).
**L1_lat slope is 1040× more impactful per cycle than DRAM_lat** at TM=8.
DRAM contributes only ~11% of α at typical operating conditions.

**E4d (TN sweep at TM=96):**
Reducing TN from 32 to 16 drops α from 9.03 to 3.83 — confirming the TM=96
spike is C-tile eviction (WS overflow), not an intrinsic TM=96 penalty.

**Grand conclusion:**
```
α(TM, TN) ≈  0.754 × L1_lat  +  α_DRAM(TM, TN)
                    ↑                    ↑
              warm L1 hits (89%)   DRAM cold fills (11%)
              TM-independent       C/TN correction
```

---

### E6-nol2: full α(TM, TN) surface

**What it does**: measures α at every (TM, TN) pair in an 8×5 grid, and tests
whether the model predicts TM*(gc) correctly when TN varies.

**Full α(TM, TN) table (gc=0):**

```
   TM  regime    TN=4     TN=8    TN=16    TN=32    TN=64
    8    L1     3.3997   3.3973   3.3963   3.3958   3.3957
   12    L1     3.3159   3.3146   3.3139   3.3133   3.438†
   16   DRAM    6.0524   4.6403   3.9343   3.5811   3.4041
   24   DRAM    6.0067   4.5966   3.8916   3.5387   3.3617
   32   DRAM    5.9839   4.5747   3.8701   3.5174   3.340 *
   48   DRAM    5.9609   4.5527   3.8486   3.4959   4.390 **
   64   DRAM    5.9492   4.5415   3.8377   3.485 *  8.873 **
   96   DRAM    5.9374   4.5302   3.8266   9.033 ** 8.876 **
```
`*` WS borderline (WS ≥ 256), `**` WS catastrophic (WS ≥ 300), `†` mild overflow.

**Key findings:**

**1. C = 11.26 ≈ 11.0 — universal across all DRAM tiles.**

Fitting α = α₀ + C/TN using safe (TN, α) pairs:

| TM | C (measured) | formula | error |
|----|-------------|---------|-------|
| 24 | 11.284 | 11.0 | +2.6% |
| 32 | 11.275 | 11.0 | +2.5% |
| 48 | 11.268 | 11.0 | +2.4% |
| 64 | 11.262 | 11.0 | +2.4% |
| 96 | 11.258 | 11.0 | +2.3% |

**2. TM=16 is DRAM-regime despite A fitting exactly.**
TM=16 fills L1 exactly (16 KB), leaving no room for C tile or FIFO data.
A lines get evicted immediately → C ≈ 11.3 (same as DRAM tiles).
The true L1-regime boundary is **TM ≤ 12**, not TM ≤ 16.

**3. TM* shifts dramatically with TN — unlike the L2 case.**

At gc=50 (α-dominated regime), TM* by TN:

| TN | TM* (empirical) | TM* (TN-blind E3 model) | match? |
|----|-----------------|-------------------------|--------|
| 4  | **12** | 64 | ✗ |
| 8  | **12** | 64 | ✗ |
| 16 | **96** | 64 | ✗ |
| 32 | **64** | 64 | ✓ |
| 64 | **32** | 32 | ✓ |

The TN-blind model fails 3/5 cases. The TN-aware model (calibrated α per cell)
matches all 5/5 with < 1% prediction error.

**Why TM*=12 at TN=4:** the 11/4=2.75 α penalty on all DRAM tiles makes TM=12
(L1 regime, no penalty, α=3.313) competitive despite its high gc/TM=4.17.

**Why TM*=96 at TN=16:** all DRAM tiles have nearly equal α≈3.83 at TN=16 (the
1/16 penalty is small but equal for all). Among them, the largest safe TM (TM=96,
WS=214 < 256) has the lowest gc/TM=0.52 → wins.

**Why TM*=32 at TN=64:** overflow rules out TM=48+ at TN=64. Among safe tiles,
TM=32 has the lowest α=3.340 AND the largest TM → wins.

**Global α minimum in the safe region: TM=32, TN=64 (α=3.340).** For the standard
TN=32 operating point: TM=64 (α=3.485).

---

## Part 7: What comes next

### E8-nol2: dense gc sweep across TM* transitions

Maps out T/MNK as a function of gc for all (TM, TN) pairs. Locates the precise gc
values where TM* transitions occur. Tests the analytical formula.

**Predicted transition boundaries (at TN=32):**
- gc ≈ 42: TM* shifts from 12 (L1) → 64 (DRAM). Above this, TM=64 wins for all gc
  (TM=96 is overflow at TN=32, so there are no further transitions).

Compare to the L2 case: three transitions at gc≈104, 171, 252 (all within DRAM tiles).
In L1-only there is only ONE transition at TN=32 (at a much lower gc value), because
TM=96+ is unusable at TN=32, and the L1-tile minimum (TM=12) competes earlier.

**TN-dependent transition boundaries:**

| TN | predicted gc* |
|----|--------------|
| 4  | ≈ 71 (TM=12 → TM=96) |
| 8  | ≈ 55 (TM=12 → TM=96) |
| 16 | ≈ 46 (TM=12 → TM=96) |
| 32 | ≈ 42 (TM=12 → TM=64) |
| 64 | — (TM=32 wins for all gc) |

### E13-nol2: FIFO vs Memory-B (the main goal)

Measures the Memory-B α table and finds the crossover gc* where FIFO and Memory-B
perform equally. In L1-only, Memory-B must go to DRAM for every B access (no L2
buffer) → α_mem is expected to be much larger than in the L2 case.
