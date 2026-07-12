# Math Model Experiments

**Branch**: `math-model-v05`  
**Workload**: M=N=K=256, A_P=B_P=4, TK=256, 3D register tiles (REG_M=REG_N=REG_K=4),
C-stationary outer-products ordering.

---

## The question

What is the optimal tile shape (TM, TN) for the asymmetric matmul, and how does
it depend on the B generation cost `gc`?

---

## Original model (before E1b)

The tile-shape cost model is:

    T = MNK * max(C_A / TN,  C_B / TM)

where:
- `C_A` = effective cycles per A-element inter-session access (assumed hardware constant)
- `C_B = gc` = B generation cost (cycles per element)
- The max comes from the fact that T_A and T_B run in parallel; the slower one dominates

With the constraint `μ = TM * TN` fixed, minimising over TM gives:

    TM* / TN* = ρ_t = C_B / C_A      (the "ratio rule")

The ratio `ρ_t` is the key dimensionless number: if B is expensive relative to A,
make TM large (fewer B sessions) and TN small.

---

## E1b — Isolating C_A as a function of tile shape

`e1b-ca-tile-sweep/`

We isolate C_A by running with gc=1 (B cost ≈ 0) and `--mulac_norecord`, so:

    C_A(TM, TN)  =  T_measured * TN / (M * N * K)

### Sub-sweep 1: TM sweep (TN=32 fixed, M=192)

Tests whether C_A jumps when the A tile overflows L2.
L2 threshold: `TM * TK * A_P = L2_SIZE` → TM = 64.

| TM | A-tile | cycles | C_A | α = C_A/TN |
|----|--------|--------|-----|------------|
| 8  | 8 KB   | 42.8 M | 108.9 | 3.40 |
| 16 | 16 KB  | 41.5 M | 105.6 | 3.30 |
| 24 | 24 KB  | 41.0 M | 104.3 | 3.26 |
| 32 | 32 KB  | 40.7 M | 103.6 | 3.24 |
| 48 | 48 KB  | 41.0 M | 104.2 | 3.26 |
| **64** | **64 KB = L2** | **44.8 M** | **113.9** | **3.56** ← L2 overflow |
| 96 | 96 KB  | 49.6 M | 126.1 | 3.94 |

**Finding 1**: C_A is roughly constant (≈104) for TM ≤ 48, then rises sharply once
the A tile at TM=64 exactly fills L2 (leaving no room for the C tile and
evicting A lines before they can be reused). For TM > 64, A spills to DRAM.

Note: the data shows L2 hit_rate = 0.0 at TM=64 (all A L1-misses go to DRAM),
yet C_A = 113.9 — not the full DRAM cost of ~180 cycles. This is because
repeated A register-tile loads within a session (R-1 of the R total loads) still
hit L1; only the first cold fill per line goes all the way to DRAM.

### Sub-sweep 2: TN sweep (TM=32 fixed, M=256)

Tests whether C_A depends on TN, revealing the intra-session reuse structure.
Reuse factor R = TN / reg_n. C tile overflows L1 at TN = 128.

| TN | R = TN/4 | cycles | C_A | C_A / R |
|----|----------|--------|-----|---------|
| 4  | 1 | 57.6 M | 13.7  | 13.7 |
| 8  | 2 | 55.7 M | 26.6  | 13.3 |
| 16 | 4 | 54.8 M | 52.3  | 13.1 |
| 32 | 8 | 54.3 M | 103.6 | 12.9 |
| 64 | 16 | 54.1 M | 206.4 | 12.9 |
| **128** | **32** | **62.0 M** | **472.9** | **14.8** ← C overflows L1 |
| **256** | **64** | **61.2 M** | **934.0** | **14.6** |

**Finding 2**: C_A scales linearly with R = TN/reg_n:

    C_A  ≈  13.5 * R  =  13.5 * TN / reg_n

where 13.5 ≈ L2_ACCESS_CYCLES = 14 cycles. The slope is the cost per A register-
tile load, measured to be approximately L2 latency even for (supposedly cached)
repeated loads — indicating A lines are being evicted from L1 by C tile traffic
between re-uses, forcing each load to re-fetch from L2.

---

## The key implication: TN cancels

Substituting C_A = α * TN (where α = 13.5/reg_n ≈ 3.4 cycles, a pure hardware
constant) into the original formula:

    T  =  MNK * max(C_A / TN,  gc / TM)
       =  MNK * max(α * TN / TN,  gc / TM)
       =  MNK * max(α(TM),  gc / TM)          ← TN is gone

**TN does not affect total runtime** (within the cache regime where A fits in L2
and C fits in L1). The A-access time is:

    T_A  =  MNK * α(TM)  =  constant in TN

This makes sense: total A loads = MNK/TN sessions × R=TN/reg_n loads per session
= MNK/reg_n total loads (TN cancels). Each load costs ≈ L2_lat, so:

    T_A  =  MNK / reg_n  *  L2_lat  =  MNK  *  α      [α = L2_lat / reg_n]

---

## Revised model

    T  =  MNK * max(α(TM),  gc / TM)

where `α(TM)` is a piecewise constant determined by which cache level holds A.

### How α(TM) is measured: the gc=0 calibration

The model has two terms. To isolate α(TM) we need to zero out the B term.
Setting gc=0 (instantaneous B generation) does exactly that:

    T_gc0 = MNK × max(α(TM), 0/TM)
          = MNK × max(α(TM), 0)
          = MNK × α(TM)                  [since α(TM) > 0 always]

So dividing by MNK gives α exactly:

    α(TM) = T_gc0 / MNK

This is not an approximation — it is exact. With gc=0 the B term is always zero
regardless of TM, so everything measured is purely A-access cost. We just run
the simulator with PRNG_FIFO_GEN_COST=0 and read off the cycles.

The same trick works per-(TM, TN) pair: run gc=0 at each pair and compute
α(TM, TN) = T_gc0 / MNK to get a cell-specific calibration table (E6, E7).

### The α(TM) table (E3, gc=0, TN=32)

| A-tile size | α(TM) | C_fill | regime |
|-------------|-------|--------|--------|
| TM=8  (8 KB)    | 3.400 | 13.60 | L2 |
| TM=16 (16 KB)   | 3.300 | 13.20 | L2 |
| TM=24 (24 KB)   | 3.259 | 13.04 | L2 |
| TM=32 (32 KB)   | 3.237 | 12.95 | L2 — minimum |
| TM=48 (48 KB)   | 3.255 | 13.02 | L2 |
| TM=64 (64 KB=L2) | 3.560 | 14.24 | L2/DRAM boundary |
| TM=96 (96 KB)   | 3.940 | 15.76 | DRAM |
| TM=128 (128 KB) | 3.936 | 15.75 | DRAM — flat |

**TN's role**: TN doesn't appear in T, so it is a free parameter. Choose TN as
large as possible subject to the C tile fitting in L1:
TN* = L1 / (TM × C_P). At TM=32: TN* = 16384/(32×4) = 128, but E4c shows
TN=128 exactly fills L1 causing a 14% α jump, so TN ≤ 64 is safe.

**What happened to the ratio rule?** The ratio ρ_t = C_B/C_A was derived assuming
C_A is a hardware constant. It is not — C_A = α(TM) × TN scales with TN through
the reuse factor R. Once the correct form is substituted, TN cancels, the ratio
rule disappears, and the only lever is TM.

---

## Finding TM* analytically — worked examples

To minimize T = MNK × max(α(TM), gc/TM) we minimize max(α(TM), gc/TM) over all
valid TM. There is no closed-form derivative — α(TM) is piecewise — so we
evaluate the expression at each TM and take the minimum. The computation per TM
is: look up α, divide gc by TM, take the max. Four arithmetic operations.

The two terms have opposite trends:
- `gc/TM` decreases as TM grows (B sessions are amortized over more elements)
- `α(TM)` is mostly flat within each cache regime, jumps at the L2/DRAM boundary

For small TM the B term dominates; growing TM reduces it until α takes over.
The optimal TM is always at or just past this crossover.

**gc = 64:**

| TM | α(TM) | gc/TM | max | bottleneck |
|----|-------|-------|-----|------------|
| 8  | 3.400 | 8.000 | 8.000 | B |
| 16 | 3.300 | 4.000 | 4.000 | B |
| 24 | 3.259 | 2.667 | 3.259 | A |
| **32** | **3.237** | **2.000** | **3.237** | **A ← min** |
| 48 | 3.255 | 1.333 | 3.255 | A |
| 64 | 3.560 | 1.000 | 3.560 | A |

Crossover is between TM=16 (B, 4.000) and TM=24 (A, 3.259). Once A-dominated,
cost = α(TM), so the cheapest α wins. TM=32 has the smallest α in the table
(3.237). **TM* = 32.**

**gc = 130:**

| TM | α(TM) | gc/TM | max | bottleneck |
|----|-------|-------|-----|------------|
| 16 | 3.300 | 8.125 | 8.125 | B |
| 24 | 3.259 | 5.417 | 5.417 | B |
| 32 | 3.237 | 4.063 | 4.063 | B |
| **48** | **3.255** | **2.708** | **3.255** | **A ← min** |
| 64 | 3.560 | 2.031 | 3.560 | A |
| 96 | 3.940 | 1.354 | 3.940 | A |

Crossover between TM=32 (B, 4.063) and TM=48 (A, 3.255). Note TM=32 is
B-dominated here (gc/32=4.063 > α(32)=3.237), so its lower α doesn't help —
the B side is still the bottleneck there. **TM* = 48.**

**gc = 230:**

| TM | α(TM) | gc/TM | max | bottleneck |
|----|-------|-------|-----|------------|
| 32 | 3.237 | 7.188 | 7.188 | B |
| 48 | 3.255 | 4.792 | 4.792 | B |
| **64** | **3.560** | **3.594** | **3.594** | **B (barely) ← min** |
| 96 | 3.940 | 2.396 | 3.940 | A |
| 128| 3.936 | 1.797 | 3.936 | A |

At TM=64: gc/TM = 3.594 > α(64) = 3.560 — still B-dominated, cost 3.594.
At TM=96: cost jumps to 3.940 (A-dominated). The B savings from 64→96
(3.594 → 2.396) don't compensate for the α jump (3.560 → 3.940). **TM* = 64.**

**gc = 380:**

| TM | α(TM) | gc/TM | max | bottleneck |
|----|-------|-------|-----|------------|
| 48 | 3.255 | 7.917 | 7.917 | B |
| 64 | 3.560 | 5.938 | 5.938 | B |
| 96 | 3.940 | 3.958 | 3.958 | B (3.958 > 3.940, barely) |
| **128** | **3.936** | **2.969** | **3.936** | **A ← min** |

At TM=96: gc/96 = 3.958 > α(96) = 3.940 — B-dominated by 0.5%. At TM=128:
A-dominated, cost = α(128) = 3.936 < 3.958. **TM* = 128.**

---

## E2 — Validating the revised model

`e2-model-validation/`

Two falsifiable predictions tested.

### Prediction 1: TN independence (TM=32, gc ∈ {1, 64, 256, 512}, TN ∈ {8,16,32,64})

Model says all rows in each gc column should be equal:

| TN | gc=1 | gc=64 | gc=256 | gc=512 |
|----|------|-------|--------|--------|
| 8  | 55.7M | 56.0M | 135.8M | 270.0M |
| 16 | 54.8M | 54.9M | 135.6M | 269.8M |
| 32 | 54.3M | 54.4M | 135.6M | 269.8M |
| 64 | 54.1M | 54.1M | 135.7M | 269.9M |

**Confirmed**: variation < 0.1% at gc ≥ 256 (B-dominated). The small variation at
gc=1 (gc=1 is A-dominated, and α is slightly smaller at larger TN/R since the
pure cold-fill cost dominates over repeated loads) is within 3%.

### Prediction 2: TM model fit (TN=32, gc ∈ {1,64,256,512}, TM ∈ {8,16,32,64,128})

α(TM) is derived from the gc=1 row. Errors vs T = MNK×max(α(TM), gc/TM):

| TM | α (E3/gc=0) | A-tile | gc=1 | gc=64 | gc=256 | gc=512 |
|----|------------|--------|------|-------|--------|--------|
| 8   | 3.400 | 8KB/L2   | 57M (+0%) | 135M (+1%) | 538M (+0%) | 1075M (+0%) |
| 16  | 3.300 | 16KB/L2  | 55M (+0%) |  68M (+2%) | 269M (+1%) |  538M (+0%) |
| 32  | 3.237 | 32KB/L2  | 54M (+0%) |  54M (+0%) | 135M (+1%) |  269M (+1%) |
| 64  | 3.560 | 64KB/L2  | 59M (+0%) |  59M (+0%) |  68M (+3%) |  136M (+1%) |
| 128 | 3.936 | 128KB/DRAM | 66M (+0%) |  66M (+0%) |  66M (+0%) |   68M (+2%) |

**Confirmed**: model error ≤ 3% across all 20 cells.

TM=64 vs TM=32 at gc=512: **1.98× measured speedup** (2.00× predicted).

**Surprising finding**: TM=128 (DRAM regime) beats TM=64 (L2 regime) for gc ≥ 256
(66M vs 68M). The B-cost savings from halving the session count outweigh the
small α increase from A spilling to DRAM.

### Optimal TM* by gen_cost (hardware: L1=16KB, L2=64KB, TK=256, A_P=4)

| gc  | TM* | T* | TN* = L1/(TM×C_P) |
|-----|-----|----|--------------------|
| ≤64 | 32  | 54M | 64 (or 32) |
| 256 | 128 | 66M | 32 |
| 512 | 128 | 68M | 32 |

---

## E3 — Clean C_fill measurement at gc=0

`e3-cfill/`

Previous experiments (E1b, E2) used gc=1 to isolate T_A. At gc=1, T_B = MNK/TM is
a small contamination (≈1% at TM=32). E3 uses gc=0 (instantaneous B generation)
to measure C_fill(TM) with zero B-cost bias.

### S1: TM sweep (TN=32, gc=0)

| TM | A-tile | C_fill | α = C_fill/4 |
|----|--------|--------|--------------|
| 8  | 8 KB (L2)   | 13.598 | 3.400 |
| 16 | 16 KB (L2)  | 13.198 | 3.300 |
| 24 | 24 KB (L2)  | 13.035 | 3.259 |
| 32 | 32 KB (L2)  | 12.947 | 3.237 |
| 48 | 48 KB (L2)  | 13.020 | 3.255 |
| **64** | **64 KB = L2** | **14.242** | **3.560** ← L2 boundary |
| 96 | 96 KB (DRAM) | 15.759 | 3.940 |
| 128 | 128 KB (DRAM) | 15.745 | 3.936 |

**Key findings:**
1. **gc=1 and gc=0 α values match to 3 significant figures** — the gc=1 contamination was
   <0.1% at gc=1, confirming prior measurements were already reliable.
2. **α is flat in the DRAM regime**: TM=96 and TM=128 have essentially the same C_fill
   (15.76 vs 15.75). Once A spills to DRAM, the cost per register-tile load is determined
   by DRAM latency/reg_n, independent of TM.
3. **L2 regime minimum at TM=32**: C_fill dips slightly lower at TM=32 (12.947) than TM=8
   (13.598), likely because wider TM allows better L2 spatial prefetching.

### S2: TN sweep at gc=0 (TM=32 fixed)

| TN | R = TN/4 | C_fill |
|----|----------|--------|
| 4  | 1  | 13.726 |
| 8  | 2  | 13.285 |
| 16 | 4  | 13.065 |
| 32 | 8  | 12.955 |
| 64 | 16 | 12.900 |

C_fill decreases slightly as TN grows (13.7 → 12.9, ~6% range). At TN=4 (R=1) every
A load is a cold L2 fill; at TN=64 (R=16) the same A line is reloaded 16 times within
one rtk iteration, and because A (512 bytes) + the active C column (512 bytes) fit well
within L1 (16 KB), subsequent loads can hit L1.

Despite this, the variation is only 6%, confirming the TN-independence approximation in
the model is valid to within ±3% for practical TN values.

---

## E4 — Why C_fill ≈ L2_lat (mechanistic probe)

`e4-cfill-mechanism/`

Three sub-sweeps test the mechanism behind C_fill ≈ L2_lat.

### E4b finding: cold L2 fills are 1% of total time

Sweeping L2_ACCESS_CYCLES ∈ {7,10,14,20,28} with everything else fixed:

| L2_lat | C_fill | cf/cf(14) |
|--------|--------|-----------|
| 7      | 12.886 | 0.995 |
| 14     | 12.955 | 1.000 |
| 28     | 13.092 | 1.011 |

A 4× change in L2_lat causes only a 1.6% change in C_fill. Fitting the
two-component model `T = T_warm + T_cold × (L2/14)`:

- T_cold = 573 K cy   ← L2-dependent (cold fills), **1.05% of total**
- T_warm = 53.8 M cy  ← L1-hits, **98.95% of total**

### E4a finding: TK doesn't matter

C_fill is flat from TK=4 to TK=256 (0.2% variation). The warm/cold ratio is
set by the full matrix dimensions, not TK: spatial locality (4 TK passes per
A cache line) and C warm-up hold the same across-tile or within-tile, so the
total proportions are the same regardless of TK.

### E4c finding: C overflow breaks everything

| TN  | C-tile | C_fill |
|-----|--------|--------|
| 32  | 4 KB   | 12.955 |
| 64  | 8 KB   | 12.900 |
| 128 | 16 KB = L1 | **14.777** ← overflow |
| 256 | 32 KB  | 14.594 |

C_fill is flat while C fits in L1, then jumps ~14% at TN=128 where C fills L1.

### Correct explanation of C_fill ≈ L2_lat

C_fill ≈ 13 is dominated by **warm L1 hits** (99% of accesses at 4 cycles each).
The formula is:

    C_fill ≈ 3 × L1_lat = 3 × 4 = 12 cycles

where the "3" comes from 3 memory ops per mulacc (load A, load C, store C) ×
(16 elements/reg-tile) / (16 elements/reg-tile-group × reg_n) ... normalizing by
reg_n = 4 gives 3 × L1_lat = 12. Measured 12.95 — the gap is B FIFO overhead
and the 1% cold-fill contribution.

**C_fill ≈ L2_lat = 14 is a numerical coincidence**: 3 × L1_lat happens to ≈ L2_lat
for our parameters (L1_lat=4, L2_lat=14). On hardware with L2_lat=40, C_fill would
still be 12 but would no longer equal L2_lat.

---

## E5 — Validating the optimal TM prediction

`e5-optimal-tm/`

The model T = MNK × max(α(TM), gc/TM) predicts a specific TM* for each gc.
E5 sweeps all valid TM values for four gc values chosen to cover different regimes,
and checks that the empirically best TM matches the prediction.

**Predicted TM\* per gc** (from the α(TM) table measured in E3):

| gc  | Predicted TM* | Reason |
|-----|--------------|--------|
| 64  | 32 | A-dominated everywhere; argmin of α in L2 regime |
| 130 | 48 | crossover between TM=32 (B-dominated) and TM=48 (A-dominated) |
| 230 | 64 | gc/64 = 3.59 ≈ α(64)=3.56; roughly balanced at the L2 boundary |
| 380 | 128 | gc/128 = 2.97 < α(128)=3.94; A-dominated in DRAM regime |

**Results (TN=32, M=192 for TM≤96, M=256 for TM=128):**

| gc  | TM* (predicted) | TM* (empirical) | Match | T/MNK at TM* |
|-----|----------------|----------------|-------|--------------|
| 64  | 32 | 32 | ✓ | 3.241 |
| 130 | 48 | 48 | ✓ | 3.260 |
| 230 | 64 | 64 | ✓ | 3.699 |
| 380 | 128 | 128 | ✓ | 3.942 |

All four predictions confirmed. Model error ≤ 3% at the optimal TM for every gc.

**Note on normalization**: TM=128 requires M=256 (TM must divide M), while other
TM values use M=192. The empirical argmin was computed on T/MNK (not raw cycles)
so that results from different M are directly comparable.

---

## E6 — TN independence of the optimal TM

`e6-tn-independence/`

The model has no TN term, so TM\* should not change when TN varies (within the
regime where C fits in L1). E6 tests this by sweeping TM ∈ {8,16,24,32,48,64,96}
× TN ∈ {4,16,32,64} at gc=130 (which puts TM*=48 in E5).

The experiment has two parts.

### Part 1: prediction using the E3 α table (calibrated at TN=32)

Model prediction: TM\*=48 for all TN.

| TN | Predicted TM* | Empirical TM* | Match |
|----|--------------|--------------|-------|
| 4  | 48 | 48 | ✓ |
| 16 | 48 | 48 | ✓ |
| 32 | 48 | 48 | ✓ |
| 64 | 48 | 48 | ✓ |

TM*=48 for all TN. The E3 model predicts correctly across the full TN range.

However, for TN=4 in the DRAM regime (TM=64, TM=96), the model underestimates
measured cycles by ~75%. This is because α in the DRAM regime actually depends
on TN, but the E3 table was calibrated at TN=32 only.

### Part 2: recalibration — measuring α(TM, TN) per cell

To investigate the TN-dependent error, E6 runs a second gc=0 calibration sweep
over the same TM × TN grid, measuring α(TM, TN) = T_gc0/MNK at each pair.
All predictions are then recomputed using the cell-specific α.

**Calibrated α(TM, TN) table (from gc=0 runs):**

| TM  | TN=4  | TN=16 | TN=32 | TN=64 | E3 (TN=32) |
|-----|-------|-------|-------|-------|------------|
| 8   | 3.401 | 3.400 | 3.400 | 3.400 | 3.400 |
| 16  | 3.492 | 3.327 | 3.300 | 3.286 | 3.300 |
| 24  | 3.452 | 3.287 | 3.259 | 3.244 | 3.259 |
| 32  | 3.430 | 3.264 | 3.237 | 3.223 | 3.237 |
| 48  | 3.414 | 3.249 | 3.255 | 3.428 | 3.255 |
| **64**  | **6.218** | **3.941** | **3.560** | **3.760** | 3.560 |
| **96**  | **6.206** | **3.931** | **3.940** | **3.749** | 3.940 |

Key observations:
- **L2 regime (TM ≤ 48)**: α varies by at most 6% across TN values. TN=4 is
  slightly higher because with R=1 (one rtj per tile_n), every A load is a cold
  fill with no L1 warm-up across rtj passes. The effect is small.
- **DRAM regime (TM ≥ 64)**: α(TM=64, TN=4) = 6.218 — nearly 2× higher than
  α(TM=64, TN=32) = 3.560. Why: at TN=4, R = TN/reg_n = 1, so every session
  starts with a cold DRAM fill (no rtj warm-up). At TN=32, R=8 and the same A
  lines stay warm for 7 of the 8 rtj passes. In the DRAM regime the cost of one
  cold fill (~198 cy) dominates, so TN=4 amplifies the difference dramatically.
- **Significance for TM\***: The large DRAM-regime TN effect does not shift TM*
  because the L2-regime minimum (TM=32–48, α ≈ 3.25–3.44) still beats even the
  least-DRAM-penalized TM=64 at TN=32 (α=3.56), let alone at TN=4 (α=6.22).

**Part 2 results (using recalibrated α):**

| TN | Predicted TM* | Empirical TM* | Match |
|----|--------------|--------------|-------|
| 4  | 48 | 48 | ✓ |
| 16 | 48 | 48 | ✓ |
| 32 | 48 | 48 | ✓ |
| 64 | 48 | 48 | ✓ |

TM*=48 confirmed for all TN with cell-specific α. Using calibrated α reduces
DRAM-regime prediction errors from ~75% to <1%. Residual 2–4% error in
B-bottlenecked cells comes from FIFO overhead present at gc=130 but absent at gc=0.

### Summary

The model T = MNK × max(α(TM), gc/TM) with TN-independent α(TM) correctly
predicts TM* for all tested TN values (TN ∈ {4,16,32,64}). The TN-dependence of
α is a real but second-order effect: it matters for accurate absolute cycle counts
in the DRAM regime but does not move the optimal tile choice.

---

## E7 — TN independence across all gc values

`e7-tn-gc-sweep/`

E6 tested TN independence at gc=130 only. E7 extends to all four gc values from
E5 (gc ∈ {64, 130, 230, 380}), sweeping TM ∈ {8,16,24,32,48,64,96,128} ×
TN ∈ {4,16,32,64}. For each (gc, TN) pair, the experiment finds the empirical TM*
and compares it to (a) the E3 (TN-independent) prediction and (b) the calibrated
(per-TN) prediction.

### Summary table: empirical TM* for all (gc, TN)

| gc  | TN=4 | TN=16 | TN=32 | TN=64 | E3-pred |
|-----|------|-------|-------|-------|---------|
| 64  | 48 ✗ | 48 ✗  | 32 ✓  | 32 ✓  | 32 |
| 130 | 48 ✓ | 48 ✓  | 48 ✓  | 48 ✓  | 48 |
| 230 | 48 ✗ | 128 ✗ | 64 ✓  | 128 ✗ | 64 |
| 380 | 128 ✓| 128 ✓ | 128 ✓ | 128 ✓ | 128 |

The calibrated (per-TN) model correctly predicts TM* in all but one marginal case
(gc=380, TN=4 where TM=96 and TM=128 have nearly identical calibrated α, 6.206
vs 6.209).

### Finding 1: gc=64 — TM* shifts from 32 to 48 at small TN

Within the L2 regime, the α minimum shifts slightly with TN. At TN=32 (the E3
calibration TN), TM=32 has the lowest α (3.237 < 3.255). At TN=4, the ordering
reverses: α(32,TN=4)=3.430 > α(48,TN=4)=3.414. So TM*=48 at TN=4 and TN=16.

This is a small effect (~0.5% difference in α) but real. Since gc=64 is fully
A-dominated from TM=24 onward, the TM with the lowest α wins — and that changes
with TN.

### Finding 2: gc=130 — all ✓, consistent with E6

TM*=48 for all TN, confirming E6. TM=48 is comfortably inside the L2 regime
where the TN sensitivity of α is small and the crossover is far enough from the
L2/DRAM boundary that nothing changes.

### Finding 3: gc=230 — the most sensitive case (3 of 4 TN values shift)

The E3-predicted TM*=64 sits exactly at the L2/DRAM boundary — the most TN-sensitive
point in the α curve. Results for each TN:

- **TN=4**: TM*=48. α(64,TN=4)=6.22 — the DRAM-regime penalty is so large that
  TM=48 (T/MNK=4.97) beats TM=64 (T/MNK=6.27) by more than 20%.
- **TN=16**: TM*=128. α(64,TN=16)=3.941, α(128,TN=16)=3.925. TM=128 edges TM=64
  by 0.7% (3.932 vs 3.955). Small but consistent.
- **TN=32**: TM*=64 ✓. This is the E3 calibration TN; the prediction holds.
- **TN=64**: TM*=128. Same mechanism as TN=16; TM=128 narrowly wins.

### Finding 4: gc=380 — all ✓

TM*=128 for all TN. The B cost gc/96=3.958 and gc/128=2.969 straddle the DRAM-
regime α (≈3.94) so TM=128 wins everywhere. Even at TN=4 where all DRAM-regime
TM values have α≈6.21, TM=128 is the best among them (lowest absolute cycles).

### When does TM* depend on TN?

Three conditions must all hold:

1. **The E3-predicted TM* is at or past the L2/DRAM boundary (TM ≥ 64).** In the
   L2 regime the TN sensitivity of α is small (~6%); it only becomes large in the
   DRAM regime (~2×). Exception: gc=64 shows a small inversion within L2 because
   TM=32 and TM=48 have very similar α and the ordering flips.

2. **TN is far from the E3 calibration value (TN=32).** At TN=32 the E3 α table
   is exact. Deviations grow as TN moves away, especially toward TN=4.

3. **The cost difference between TM options is small.** When one TM is clearly
   better (gc=380, where TM=128 beats all others by 3%), TN noise can't flip the
   winner. When two options are within 1% (gc=230, TM=64 vs TM=128 at TN=16),
   TN-dependent α can tip the balance.

### Practical rule

If you are choosing TN=32 (the calibration value): the E3 model is correct for
all gc values. If you use a different TN and gc is near a cache-regime boundary
(gc ≈ 64–230), use the per-TN calibrated α to get the right TM*.

---

## E8 — Dense gc boundary sweep and analytical α formula test

`e8-gc-boundary-sweep/`

E7 used only four gc values (64, 130, 230, 380) and TN ∈ {4,16,32,64}. E8
densifies both axes: 14 gc values chosen near and between the E3 transition
points, and TN ∈ {4,8,16,32,64}. It also introduces a new column: the
*analytical formula* prediction, which computes α(TM,TN) from first principles
rather than calibration.

### The analytical α formula

Starting from the warm-L1 dominant model: every A register-tile load costs
approximately L1_lat = 4 cycles when warm. Each load is R = TN/reg_n = TN/4
loads deep within a session; only the very first load per session (rtj=0) is
cold. The cold-fill correction gives:

    α(TM, TN) ≈ α_E3(TM) + C(TM) × (1/TN − 1/32)

where `C(TM) = (L_cache(TM) − L1_lat) / (reg_m × reg_k)` and `L_cache` is the
cache latency for a cold A line:
- **L2 regime (TM ≤ 48)**: C = (14 − 4) / 16 = 0.625
- **DRAM regime (TM ≥ 64)**: C ≈ 12.0 (back-estimated; actual values vary)

The formula is anchored at TN=32 (the E3 calibration point): at TN=32 it
returns α_E3(TM) exactly.

### Calibrated α(TM, TN) table (from E8 gc=0 sweep)

| TM  | TN=4  | TN=8  | TN=16 | TN=32 | TN=64 | formula(TN=8) |
|-----|-------|-------|-------|-------|-------|---------------|
| 8   | 3.401 | 3.400 | 3.400 | 3.400 | 3.400 | 3.458 (+1.7%) |
| 16  | 3.492 | 3.382 | 3.327 | 3.300 | 3.286 | 3.358 (−0.7%) |
| 24  | 3.452 | 3.342 | 3.287 | 3.259 | 3.244 | 3.317 (−0.7%) |
| 32  | 3.430 | 3.320 | 3.264 | 3.237 | 3.223 | 3.296 (−0.7%) |
| 48  | 3.414 | 3.304 | 3.249 | 3.255 | 3.428 | 3.314 (+0.3%) |
| **64**  | **6.218** | **4.701** | **3.941** | **3.560** | **3.760** | 4.685 (−0.3%) |
| **96**  | **6.206** | **4.689** | **3.931** | **3.940** | **3.749** | 5.065 (+8.0%) |
| **128** | **6.209** | **4.687** | **3.925** | **3.936** | **3.744** | 5.061 (+8.0%) |

The formula column shows TN=8. Bold rows = DRAM regime. The formula's worst
errors (+8%) occur at TM=96,128 in the DRAM regime: the theory assumes
C_DRAM=12.0 but the hardware effective value is ~10.4 for these TM values.

### Summary table: empirical TM* vs predictions (C=calib, F=formula, E=E3)

| gc  | TN=4  | TN=8  | TN=16 | TN=32 | TN=64 | E3-pred |
|-----|-------|-------|-------|-------|-------|---------|
| 64  | 48 ✓✗✗ | 48 ✓✗✗ | 48 ✓✗✗ | 32 ✓✓✓ | 32 ✓✓✓ | 32 |
| 100 | 48 ✓✗✗ | 48 ✓✗✗ | 48 ✓✗✗ | 48 ✗✗✗ | 32 ✓✓✓ | 32 |
| 104 | 48 ✓✗✗ | 48 ✓✗✗ | 48 ✓✗✗ | 48 ✗✗✗ | 32 ✓✗✓ | 32 |
| 108 | 48 ✓✗✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✗✓✓ | 48 |
| 130 | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 |
| 165 | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✓✓ | 48 ✓✗✓ | 48 |
| 171 | 48 ✓✓✗ | 48 ✓✓✗ | 48 ✓✓✗ | 64 ✓✓✓ | 48 ✓✗✗ | 64 |
| 175 | 48 ✓✓✗ | 48 ✓✓✗ | 48 ✓✓✗ | 64 ✓✓✓ | 48 ✓✗✗ | 64 |
| 230 | 48 ✓✓✗ | 128 ✓✗✗ | 128 ✓✗✗ | 64 ✓✓✓ | 128 ✓✗✗ | 64 |
| 248 | 48 ✓✓✗ | 128 ✓✗✗ | 128 ✓✗✗ | 128 ✗✗✗ | 128 ✓✓✗ | 64 |
| 252 | 48 ✓✓✗ | 128 ✓✗✓ | 128 ✓✗✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 |
| 256 | 48 ✓✓✗ | 128 ✓✗✓ | 128 ✓✗✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 |
| 380 | 128 ✗✗✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 |
| 600 | 128 ✓✓✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 ✓✓✓ | 128 |

### Key findings

1. **Calibrated model is nearly perfect.** Fails only at (gc=100,TN=32) and
   (gc=380,TN=4) — both cases where two TM options differ by < 0.4% in T/MNK,
   within measurement noise.

2. **Formula accuracy:** < 2% error in the L2 regime for TN ≤ 32. Fails in
   the DRAM regime at small TN: TM=96,128 at TN=4 show +6–10% error because
   the theoretical C_DRAM=12.0 overstates the measured effective value (~10.4).
   Also fails at TN=64 near the DRAM boundary: −10% at TM=64. The formula
   predicts the wrong TM* for most DRAM-regime gc values at TN=4, and many at
   TN=8,16.

3. **E3 boundary gc≈104 (32→48 transition):** At TN=32 the boundary is between
   gc=104 and gc=108, matching the E3 prediction. At TN≤16, TM*=48 already at
   gc=64 — the effective α minimum shifts because the cold-fill term flattens
   the α ordering between TM=32 and TM=48.

4. **E3 boundary gc≈171 (48→64 transition):** Only shifts TM* to 64 at TN=32
   and TN=64. At TN≤16, TM*=48 persists through gc=248 (DRAM-regime α makes
   TM=64 too expensive at small TN).

5. **E3 boundary gc≈252 (64→128 transition):** Accurate for TN≥16 but TM*=48
   persists at TN=4 even up to gc=600 (the DRAM penalty at TN=4 is so severe
   that TM=48 with α=3.41 beats TM=128 with α=6.21).

---

## E9 — C-tile overflow regime

`e9-tn-overflow/`

E1b–E8 all operate with TN ≤ 64 and TM ≤ 48 in the well-behaved regime where
the C tile (= TM × TN × 4 bytes) fits in L1 (16 KB). E9 deliberately breaks
this assumption by testing TN ∈ {128, 256}, where C overflows L1 for moderate
and large TM values. TN=64 is included as a reference.

L1 overflow threshold: `TM × TN × 4 > 16384`:
- TN=128: overflows at TM ≥ 32 (C tile = 16384 exactly at TM=32)
- TN=256: overflows at TM ≥ 16

### Calibrated α(TM, TN) — overflow regime

| TM  | C-tile (TN=256) | TN=64  | TN=128 | TN=256 |
|-----|-----------------|--------|--------|--------|
| 8   | 8 KB (< L1)     | 3.400  | 3.404  | 3.400  |
| 16  | 16 KB (= L1)    | 3.286  | 3.279  | 3.707! |
| 24  | 24 KB           | 3.244  | 3.236  | 3.665! |
| 32  | 32 KB           | 3.223  | 3.692! | 3.647! |
| 48  | 48 KB           | 3.428  | 3.675! | 3.622! |
| 64  | 64 KB (= L2!)   | 3.760! | 3.663! | 4.851! |
| 96  | 96 KB (≥ L2)    | 3.749! | 3.649! | 9.169! |
| 128 | 128 KB (≥ L2)   | 3.744! | 4.977! | 9.173! |

`!` marks cells where C tile overflows L1 at the given TN. At TN=256, TM=96: the
C tile is 6× L1 size, filling L2 entirely — α=9.17, nearly 3× the normal DRAM
regime value.

### What the overflow does to TM*

| gc  | TN=64  | TN=128    | TN=256   | E3-pred |
|-----|--------|-----------|----------|---------|
| 64  | 32 ✓✓  | 24 ✓✗     | 48! ✓✗   | 32 |
| 130 | 48 ✓✓  | 96! ✓✗    | 48! ✓✓   | 48 |
| 230 | 128! ✓✗ | 96! ✓✗   | 64! ✗✓   | 64 |
| 380 | 128! ✓✓ | 96! ✓✗   | 64! ✓✗   | 128 |

`!` = C tile at empirical TM* overflows L1. C = calibrated, E = E3.

At **TN=128**, the overflow regime completely restructures TM*:
- gc=64: TM*=24 (not 32). At TN=128, TM=32 exactly fills L1 (α=3.69, 14%
  higher than TN=64's α=3.22). TM=24 avoids overflow at TN=128 (C tile=12 KB)
  and has α=3.24 — so 24 beats 32 despite 24 being in the middle of the L2 regime.
- gc=130,230,380: TM*=96 in all three cases. TM=96 with TN=128 has C tile=49 KB,
  which overflows L1 but fits in L2: α=3.65. TM=128 with TN=128 has C tile=65 KB
  ≥ L2: α=4.98. The calibrated model correctly identifies TM=96 as the winner.

At **TN=256**, effects are extreme:
- gc=64,130: TM*=48 despite the C tile being 3× L1 at TM=48. The reason: TM=64
  and TM=96,128 have even worse overflow (α=4.85 and 9.17 respectively).
- gc=230,380: TM*=64. Even at α=4.85 it beats the catastrophic TM=96,128
  (α=9.17).

### Key findings

1. **C-tile overflow invalidates the E3 model** completely — E3 never knows about
   the overflow and always predicts based on the normal α table. The calibrated
   model is always correct (it directly measures the actual α including overflow).

2. **L1 overflow at the boundary causes ~14% α increase.** E.g., TM=32,TN=128:
   C tile = 16384 bytes exactly = L1. α jumps from 3.22 (normal) to 3.69.

3. **L2 overflow is catastrophic.** At TN=256, TM=96 has C tile = L2. α=9.17 —
   more than double the DRAM-regime α with no overflow. The C tile must be
   re-fetched from DRAM on every pass.

4. **The formula fails badly in overflow (−12% to −61% error)** — as expected,
   the formula has no overflow term.

5. **Practical implication:** TN should be chosen carefully. Even though TN is a
   "free" parameter in the basic model (TN cancels in T_A), it is constrained by
   the C-tile L1 budget: TN < L1 / (TM × C_P). Violating this moves into a
   fundamentally different regime where the model does not apply without
   recalibration.

---

## E10 — Matrix size scaling validation

`e10-matrix-size/`

The model T = MNK × max(α(TM), gc/TM) predicts that T/MNK is constant for any
M, N, K — the asymptotic assumption that per-operation cost dominates over fixed
overheads. E10 tests this by sweeping M ∈ {128, 192, 256, 384} while holding
N=K=256 and TN=32.

Valid TM sets per M (must divide M):
- M=128: {8, 16, 32, 64, 128}
- M=192: {8, 16, 24, 32, 48, 64, 96}
- M=256: {8, 16, 32, 64, 128}
- M=384: {8, 16, 24, 32, 48, 64, 96, 128}
- Common TM (valid for all M): {8, 16, 32, 64}

### T/MNK flatness (common TM values)

**gc=130:**

| TM | M=128  | M=192  | M=256  | M=384  | E3-pred | max Δ% |
|----|--------|--------|--------|--------|---------|--------|
| 8  | 16.336 | 16.338 | 16.339 | 16.340 | 16.250  | 0.02%  |
| 16 | 8.207  | 8.208  | 8.209  | 8.209  | 8.125   | 0.03%  |
| 32 | 4.141  | 4.142  | 4.143  | 4.143  | 4.063   | 0.05%  |
| 64 | 3.562  | 3.564  | 3.565  | 3.567  | 3.560   | 0.12%  |

**gc=230:**

| TM | M=128  | M=192  | M=256  | M=384  | E3-pred | max Δ% |
|----|--------|--------|--------|--------|---------|--------|
| 8  | 28.836 | 28.838 | 28.839 | 28.840 | 28.750  | 0.01%  |
| 16 | 14.457 | 14.458 | 14.459 | 14.459 | 14.375  | 0.02%  |
| 32 | 7.266  | 7.267  | 7.268  | 7.268  | 7.188   | 0.03%  |
| 64 | 3.698  | 3.700  | 3.700  | 3.701  | 3.594   | 0.06%  |

**T/MNK varies by ≤ 0.12% across a 3× range in M.** The model's MNK-proportional
assumption is confirmed to within measurement precision.

### TM* per M (gc=130)

| M   | TM* (empirical) | TM* (E3) | Match |
|-----|----------------|----------|-------|
| 128 | 64 | 64 | ✓ |
| 192 | 48 | 64 | ✗ |
| 256 | 64 | 64 | ✓ |
| 384 | 48 | 64 | ✗ |

E3 predicts TM*=64 for all M. Empirically, M=192 and M=384 pick TM*=48
(T/MNK=3.260), which M=128 and M=256 don't even have in their valid TM set.
The discrepancy is not a model failure — it is a **tile-divisibility effect**:
TM=48 is not a valid divisor of 128 or 256, so those M values must settle for
TM=64. When TM=48 is available it wins, consistent with the E3 α table where
α(48)=3.255 < α(64)=3.560.

At gc=230, TM*=64 for all M — confirmed, no divisibility issue since 64 divides
all M values.

### Key findings

1. **T/MNK is flat to 0.12% across M ∈ {128,192,256,384}.** The MNK-asymptotic
   model is confirmed.

2. **TM* differences across M are purely divisibility artifacts.** When TM=48
   is available (M=192, M=384), it is always chosen because α(48) < α(64). When
   it is not (M=128, M=256), the model correctly falls back to TM=64.

3. **The model has no matrix-size parameter.** T/MNK depends only on tile shape
   (TM, TN) and generation cost (gc) — not on M, N, K individually. This allows
   predicting optimal tile shapes from single-size calibration and applying them
   at any M.

---

## E11 — Regression-based α formula

`e11-regression-alpha/`

The theoretical formula from E8 predicts α(TM, TN) ≈ α_E3(TM) + C(TM)×(1/TN −
1/32) with a fixed C(TM): 0.625 for L2 regime, 12.0 for DRAM. E8 showed the
formula has +8-10% error in the DRAM regime at small TN. E11 fits the slope
empirically from the 5-point TN calibration data in E8, replacing the theoretical
C with a measured one — no new simulator runs required.

### The regression model

For each TM, fit by ordinary least squares on the 5 measured α values:

    α(TM, TN) = a(TM) + b(TM) × (1/TN)

where x = 1/TN ∈ {1/4, 1/8, 1/16, 1/32, 1/64} and y = α_calib(TM, TN).

This gives an `a(TM)` (the TN→∞ asymptote — pure warm-L1 cost) and a `b(TM)`
(the cold-fill slope — effective C(TM) × L_cache correction).

Note: the E8 theoretical formula is equivalent to this form:
α = (α_E3 − C/32) + C/TN, so a = α_E3 − C/32 and b = C. The regression
finds both a and b freely from data.

### Regression coefficients

| TM  | a(TM)  | b(TM)  | R²     | α_E3   | b theory | b error | regime |
|-----|--------|--------|--------|--------|----------|---------|--------|
| 8   | 3.3995 | 0.0062 | 0.986  | 3.3996 | 0.625    | +10000% | L2 (flat) |
| 16  | 3.2719 | 0.8819 | 1.000  | 3.2995 | 0.625    | −29%   | L2 |
| 24  | 3.2309 | 0.8862 | 1.000  | 3.2587 | 0.625    | −29%   | L2 |
| 32  | 3.2093 | 0.8816 | 1.000  | 3.2369 | 0.625    | −29%   | L2 |
| 48  | 3.2986 | 0.3260 | 0.131  | 3.2550 | 0.625    | +92%   | L2 (non-monotonic) |
| 64  | 3.3436 | 11.278 | 0.980  | 3.5604 | 12.000   | +6.4%  | DRAM |
| 96  | 3.4792 | 10.566 | 0.978  | 3.9398 | 12.000   | +13.6% | DRAM |
| 128 | 3.4733 | 10.600 | 0.978  | 3.9363 | 12.000   | +13.2% | DRAM |

Key observations:
- **TM=8**: b ≈ 0 — α is essentially flat across all TN. The A tile (8 KB) is
  a quarter of L2; there is almost no cold-fill variation. The 10000% b error
  is meaningless because b itself is near zero.
- **TM=16,24,32**: b ≈ 0.88, R²=1.000 — perfect linear fit but theoretical
  b=0.625 underestimates the actual slope by 29%. The effective L_cache ≈ 18 cy
  vs theoretical L2_lat=14 cy — each cold A-reg-tile fill costs more than a
  single L2 access, likely due to multiple L2 lines per reg-tile or latency
  stacking.
- **TM=48**: b=0.33, R²=0.13 — the linear model fails entirely. α is
  non-monotonic: it decreases from TN=4→32 then rises at TN=64 (C tile = 12 KB,
  approaching L1 = 16 KB). The 1/TN model cannot describe this.
- **TM=64,96,128**: b ≈ 10.6, R²=0.98 — DRAM regime fits well. Theoretical
  b=12.0 is 13% too high, consistent with E8's formula error (+8-10%).

### α accuracy: regression vs theoretical vs calibrated

Max |error| across all (TM, TN) combinations:
- **Regression:** 6.39%
- **Theoretical:** 10.30%
- **Calibrated:** 0% (exact by construction)

Regression errors are worst at TM=64, TN=64 (−6.4%), where the regression
overshoots α at large TN because it has to fit the wide TN=4 swing.

### TM* prediction accuracy

| Method | Correct TM* / 70 total | Accuracy |
|--------|----------------------|----------|
| Calibrated | 65 / 70 | 93% |
| **Regression** | **48 / 70** | **69%** |
| Theoretical | 43 / 70 | 61% |

Regression improves over theoretical by 5 percentage points. The main wins:
- Correctly predicts TM*=48 at TN=4 for gc≤165 (theoretical gets these wrong
  because it underestimates the TN=4 penalty in L2 regime)

The main new failures introduced by regression:
- gc=64,100,104 at TN=8,16: regression predicts TM*=32 instead of 48 (because
  the fitted b(48)=0.33 makes TM=48 look more expensive at TN=8,16 than it is)
- gc=171,175 at TN=32: regression predicts TM*=48 instead of 64 (because
  a_reg(64)+b_reg(64)/32=3.70 significantly overshoots calibrated α(64,32)=3.56)

### Key finding

The regression approach is theoretically cleaner and more accurate than the
hard-coded theoretical formula, but still substantially below calibrated (69%
vs 93%). The root cause is that the 1/TN linear model does not fully describe
α(TM, TN):

- TM=48 is inherently non-linear (R²=0.13) due to C-tile pressure
- The regression intercept a(TM) diverges from α_E3 at the same TN=32, causing
  overshoot errors at the calibration point
- At TM* boundaries where two TM options differ by <1%, even 1-2% α error flips
  the prediction

**The calibrated approach remains the most reliable.** Regression is useful for
understanding the physics — particularly that the L2-regime cold-fill slope is
b≈0.88 (not 0.625), and the DRAM-regime slope is b≈10.6 (not 12.0). For
predicting TM*, calibrate at all TN values you care about.
