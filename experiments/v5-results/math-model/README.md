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

where `α(TM)` is a piecewise constant determined by which cache level holds A:

| A-tile size | α (gc=0, E3) | C_fill | dominant cost |
|-------------|--------------|--------|---------------|
| TM=8  (8 KB, L2)   | 3.400 | 13.60 | L2 fill latency / reg_n |
| TM=16 (16 KB, L2)  | 3.300 | 13.20 | L2 fill latency / reg_n |
| TM=24 (24 KB, L2)  | 3.259 | 13.04 | L2 fill latency / reg_n |
| TM=32 (32 KB, L2)  | 3.237 | 12.95 | L2 fill latency / reg_n |
| TM=48 (48 KB, L2)  | 3.255 | 13.02 | L2 fill latency / reg_n |
| TM=64 (64 KB=L2)   | 3.560 | 14.24 | borderline DRAM |
| TM=96 (96 KB, DRAM)  | 3.940 | 15.76 | DRAM latency / reg_n |
| TM=128 (128 KB, DRAM)| 3.936 | 15.75 | DRAM latency / reg_n |

**Optimal TM**: since T_A does not depend on TN, the only lever is TM.
T(TM) = MNK * max(α(TM), gc/TM) decreases as TM grows (B term falls) but α(TM)
rises once the L2 boundary is crossed. The crossover where B-dominated TM gets
better than staying at the L2 boundary depends on gc:

- gc < α * TM_L2 = 3.25 * 64 ≈ 208: A-dominated everywhere; TM ≈ 32-48 is optimal
- gc > 208: B-dominated; larger TM (even into DRAM) may win because gc/TM falls fast

**TN's role**: Since TN doesn't appear in T, it is a free parameter chosen to
saturate the L1 constraint: TN* = L1 / (TM * C_P). For TM=32: TN* = 16384/(32*4) = 128
(but that overflows L1 based on sub-sweep 2; in practice TN ≤ 64 is safe).

**What happened to the ratio rule?** The ratio ρ_t = C_B/C_A was derived assuming
C_A is a hardware constant. It is not — C_A encodes TN through the reuse factor R.
The correct fundamental parameter is α = C_fill/reg_n (≈ L2_lat/reg_n). The
ratio rule becomes: choose TM to satisfy TM = gc / α, but cap at the L2 boundary.

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
