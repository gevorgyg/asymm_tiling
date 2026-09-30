# Math Model — L1-Only Experiments

**Branch**: `v0.5`  
**Flag**: `--no-l2` (L1 fallthrough routes directly to DRAM, bypassing L2)  
**Workload**: M=N=K=256 (or M=192 where noted), A_P=B_P=4, TK=256, 3D register tiles
(REG_M=REG_N=REG_K=4), C-stationary outer-products ordering.

Mirror of `math-model/` (E1b–E13) in an L1-only memory hierarchy.
The goal is to validate the math model in the environment used for the FIFO vs
Memory-B comparison — L1-only is the "fair" arena where neither B source has a
structural cache advantage from L2.

---

## Why L1-only for the FIFO vs Memory-B comparison

With L2 present, **Memory-B tiles** gain a free structural advantage: the B tile
(256 × TN × 4 bytes, 32 KB for TN=32) overflows L1 but can land in L2 (64 KB),
getting cheap L2-latency re-reads across the M dimension.  FIFO-B data is never
cached at all — it is generated on-chip and consumed once.

Without L2, **both sources pay DRAM latency for every L1 miss**.  The comparison
becomes: on-chip B generation cost (gc cycles/element for FIFO) vs. DRAM transfer
cost (fixed bandwidth for Memory-B).  That is the clean head-to-head.

---

## Key hardware parameters

| Parameter | Value |
|---|---|
| L1 size | 16 384 B |
| L1 line | 64 B |
| L1 associativity | 256 (fully associative) |
| L1 latency | 4 cycles |
| L2 | bypassed (`--no-l2`) |
| DRAM latency | 180 cycles |
| REG_M = REG_N = REG_K | 4 |

---

## Critical threshold: L1 overflow for A tile

```
TM_L1 = L1 / (TK × A_P) = 16 384 / (256 × 4) = 16
```

- TM ≤ 16: A tile (TM×256×4 bytes) fits entirely within L1.
- TM > 16: A tile overflows L1; every A cache-line miss goes directly to DRAM.

Compare to the L2 case where the boundary was TM=64 (L2=64 KB).  The L1-only
boundary is **4× earlier** in TM.

---

## The math model (unchanged form)

```
T = MNK × max(α(TM),  gc / TM)
```

- `α(TM)` = cycles per A element = C_fill(TM) / reg_n
- `C_fill(TM)` = cycles per A register-tile load (measured at gc=0)
- `gc` = B generation cost (FIFO) or effective B access cost (Memory-B)
- TN does **not** appear: T_A = (MNK/TN) × (TN/reg_n) × C_fill = MNK × α. TN cancels.

The model form is the same.  What changes is the α table — both the regime
boundary (TM=16, not 64) and the α values themselves.

---

## Predicted α structure in L1-only

**In-L1 regime (TM ≤ 16):**

With no L2 as a backstop, the cost of an A cache-line miss is DRAM (180 cy), not
L2 (14 cy).  Whether A stays warm in L1 is the critical empirical question.  Two
sub-cases:

- Sub-case A: A is evicted from L1 (by B/C traffic within a session) → C_fill ≈ DRAM_lat.
  → α ≈ 180/4 = **45** — much larger than the L2-era value of 3.24.
- Sub-case B: A stays warm in L1 (no eviction) → C_fill ≈ L1_lat = 4 cycles.
  → α ≈ 4/4 = **1.0** — much smaller, very fast.

The L2 experiments showed C_fill ≈ L2_lat even for small TM, suggesting eviction
does occur (sub-case A applies in the L2 world).  With DRAM as the only backstop,
sub-case A would make L1-only **very slow for any TM**.

E4-nol2 (C_fill mechanism) will determine which sub-case applies.

**DRAM regime (TM > 16):**

Every A cold fill is a DRAM access (180 cy).  C_fill ≈ DRAM_lat = 180.
→ α ≈ 45.  Much larger than the L2-era DRAM regime (α ≈ 3.94).

**TN independence:**

The argument `T_A = MNK/reg_n × C_fill` is independent of TN regardless of which
cache level holds A.  TN independence is expected to hold at least as well as in
the L2 case, and possibly better (there is only one cost per A line miss, no
interplay between L2 latency and DRAM latency).

---

## Experiment series

### E1-nol2: C_A isolation as a function of tile shape

Mirrors `e1b-ca-tile-sweep/`.

**S1 — TM sweep (TN=32 fixed, gc=1):**
- M=192: TM ∈ {4, 8, 12, 16, 24, 32, 48, 64, 96}
- M=256: TM ∈ {128}
- Mark L1 overflow at TM=16 (instead of L2 overflow at TM=64).
- Expect: sharp α jump at TM=16.

**S2 — TN sweep (TM=8 fixed, A in L1, gc=1, M=256):**
- TN ∈ {4, 8, 16, 32, 64}
- With TM=8 (A=8 KB < L1), A nominally fits. Does C_A/R still ≈ constant?
- Compare the per-load cost: is it ≈ L1_lat (4 cy) or ≈ DRAM_lat (180 cy)?

**S3 — TN sweep (TM=32 fixed, A overflows L1, gc=1, M=256):**
- TN ∈ {4, 8, 16, 32, 64}
- TM=32: A=32 KB > L1. Every cold fill → DRAM.
- Expect C_A/R ≈ DRAM_lat.
- Contrast with S2 to measure the regime jump.

---

### E2-nol2: Model validation

Mirrors `e2-model-validation/`.

Validate `T = MNK × max(α(TM), gc/TM)` against simulated cycles across a
(TM, gc) grid.  Use the α table from E3-nol2.  Both FIFO and Memory-B modes.

---

### E3-nol2: Clean α(TM) measurement at gc=0

Mirrors `e3-cfill/`.  This is the calibration experiment — all later predictions
depend on it.

**S1 — TM sweep (TN=32, gc=0):**
- Covers TM ∈ {4, 8, 12, 16, 24, 32, 48, 64, 96, 128}
- gc=0 makes T = MNK × α(TM) exactly.
- Reports α table with L1 boundary annotation at TM=16.

**S2 — TN sweep (two TM values: 8 and 32):**
- Confirms TN independence in each regime separately.
- Key check: is C_fill constant across TN for TM=8 (in-L1) and TM=32 (DRAM)?

**Expected α table** (to be filled in by experiment):

| TM | A-tile | regime | α(TM) predicted | α(TM) measured |
|----|--------|--------|-----------------|----------------|
| 4  | 4 KB   | L1     | ≈ 1.0 or ≈ 45   | TBD |
| 8  | 8 KB   | L1     | ≈ 1.0 or ≈ 45   | TBD |
| 12 | 12 KB  | L1     | ≈ 1.0 or ≈ 45   | TBD |
| 16 | 16 KB  | L1 edge | TBD             | TBD |
| 24 | 24 KB  | DRAM   | ≈ 45             | TBD |
| 32 | 32 KB  | DRAM   | ≈ 45             | TBD |
| 48 | 48 KB  | DRAM   | ≈ 45             | TBD |
| 64 | 64 KB  | DRAM   | ≈ 45             | TBD |
| 96 | 96 KB  | DRAM   | ≈ 45             | TBD |
| 128| 128 KB | DRAM   | ≈ 45             | TBD |

---

### E4-nol2: What drives C_fill?

Mirrors `e4-cfill-mechanism/`.  The most important diagnostic experiment.

**S1 — L1_ACCESS_CYCLES sweep (TM=8, A in L1):**
- Vary L1_lat ∈ {1, 2, 4, 8, 16} while keeping DRAM fixed at 180.
- If C_fill ∝ L1_lat → warm L1 hits dominate (A stays in L1, sub-case B).
- If C_fill does not depend on L1_lat → something else drives cost.

**S2 — L1_ACCESS_CYCLES sweep (TM=32, A overflows L1):**
- Same sweep; expected: C_fill independent of L1_lat (DRAM dominates).

**S3 — DRAM_LATENCY sweep (TM=32, A overflows):**
- Vary DRAM_lat ∈ {45, 90, 135, 180, 360} while keeping L1_lat=4 fixed.
- Expect C_fill ∝ DRAM_lat (confirms DRAM-regime mechanism).

**S4 — DRAM_LATENCY sweep (TM=8, A fits in L1):**
- If C_fill also scales with DRAM_lat for TM=8 → A is being evicted to DRAM
  even when it nominally fits (sub-case A confirmed for L1-only).

---

### E5-nol2: Validate optimal TM prediction

Mirrors `e5-optimal-tm/`.

Using the α table from E3-nol2, compute:
```
T(TM, gc) = MNK × max(α(TM), gc/TM)
```
predict TM*(gc) analytically and verify against simulated T(TM, gc).  Key: if α
is large (sub-case A), the gc range where TM > 16 is A-dominated shifts
dramatically.

---

### E6-nol2: Full (TM, TN) α map at gc=0

Mirrors `e6-tn-independence/`.

Run gc=0 at every (TM, TN) pair in the grid:
- TM ∈ {4, 8, 12, 16, 24, 32, 48, 64, 96, 128}
- TN ∈ {4, 8, 16, 32, 64}

Report α(TM, TN) = T_gc0 / MNK.  Key question: **is α more constant across TN in
L1-only than it was in the L2 case?**

In the L2 case, α had a weak TN dependence (captured by the cold-fill correction
term `C(TM) × (1/TN − 1/32)`).  Without L2, the cold-fill cost is DRAM-flat, so
the 1/TN variation might simplify or disappear — or might be even larger if DRAM
latency amplifies the cold-fill term.

---

### E7-nol2: TN independence across all gc values

Mirrors `e7-tn-gc-sweep/`.

Full (TM, TN, gc) grid.  Check: for fixed gc, does TM*(gc) depend on TN?  The
model predicts no; verify this in the L1-only hardware.

---

### E8-nol2: Dense gc boundary sweep + formula test

Mirrors `e8-gc-boundary-sweep/`.

The TM* transition boundaries shift because α(TM) changes:

```
TM* shifts when gc/TM_old = α(TM_new)  →  gc = α(TM_new) × TM_old
```

These boundaries will be very different from the L2 case and will be computed
after E3-nol2 produces the α table.

Additionally test an analytical α formula analogous to the L2 formula:
```
α_formula(TM, TN) = α_E3-nol2(TM) + C_nol2(TM) × (1/TN − 1/TN_ref)
```
where C_nol2(TM) is to be determined from E6-nol2.

---

### E9-nol2: C-tile overflow

Mirrors `e9-tn-overflow/`.

C tile overflows L1 when: TM × TN × C_P > L1
```
TN_max(TM) = L1 / (TM × C_P) = 16384 / (TM × 4) = 4096 / TM
```

| TM | TN_max |
|----|--------|
| 8  | 512    |
| 16 | 256    |
| 32 | 128    |
| 64 | 64     |
| 128| 32     |

Without L2, dirty C evictions go **directly to DRAM** (no L2 buffer to absorb
them).  The cost penalty for C overflow will be larger than in the L2 case.
TN should stay well below TN_max in all normal experiments.

---

### E10-nol2: Matrix size scaling

Mirrors `e10-matrix-size/`.

Test whether `T = MNK × α(TM)` scales correctly when M, N, K change (e.g.,
M=N=K=128, 512).  The α table should be size-independent if the cache regime
doesn't change.

---

### E11-nol2 / E12-nol2: α regression

Mirrors `e11-regression-alpha/` and `e12-nonlinear-alpha/`.

Derive a compact analytical formula for α(TM, TN) from E6-nol2 data using linear
and if needed nonlinear regression.  In the L2 case the formula was:

```
α(TM, TN) ≈ α_E3(TM) + C(TM) × (1/TN − 1/32)
```

The L1-only formula may differ in structure.  If TN independence holds more
cleanly (C_nol2 ≈ 0), the formula simplifies to just α_E3-nol2(TM).

---

### E13-nol2: FIFO-B vs Memory-B — the main comparison

Mirrors `e13-fifo-vs-mem/`.  This is the reason for the entire L1-only series.

**Memory-B configuration:**
- B comes from DRAM → L1 (no L2 buffer)
- B tile = TK × TN × B_P = 256 × TN × 4 bytes
  - TN=32: B = 32 KB >> L1=16 KB — B always overflows L1
- Every B line miss → 180-cycle DRAM access (no L2 hit)

**FIFO-B configuration:**
- B generated on-chip at gc cycles/element
- No B memory traffic; FIFO data may use L1 for staging

**Expected change from L2 case:**

With L2 removed, Memory-B loses the L2 buffer that previously absorbed B tile
reuse at 14-cycle cost.  Memory-B is therefore **worse** in L1-only than with L2.
FIFO-B is roughly the same (B was never cached anyway).  The crossover gc* (where
Memory-B becomes competitive) should be **larger** than the L2 case value of
gc*=476 — FIFO needs a higher gc before Memory-B catches up.

The quantitative crossover condition is:
```
max(α_FIFO(TM*_FIFO), gc* / TM*_FIFO) = α_mem_nol2(TM*_mem_nol2)
```

where α_mem_nol2 is the Memory-B α in L1-only (expected to be larger than
α_mem_L2 because B can no longer be buffered in L2).

**What this experiment produces:**
1. Memory-B α table in L1-only (no gc parameter — fixed by bandwidth)
2. FIFO-B performance from E8-nol2 results cache (reuse pattern from E8-nol2)
3. Head-to-head comparison table: FIFO wins for gc ≤ gc*, Memory-B wins above
4. gc* — the key number that drives the hardware design decision

---

## Execution plan

Run experiments in this order (later ones depend on earlier α tables):

| Priority | Experiment | Dependency | Expected runs |
|---|---|---|---|
| 1 | E3-nol2 | none | ~60 |
| 2 | E4-nol2 | E3 (to pick interesting TM values) | ~40 |
| 3 | E1-nol2 | none | ~30 |
| 4 | E6-nol2 | E3 (for grid design) | ~50 |
| 5 | E8-nol2 | E3+E6 (for boundary gc values) | ~200 |
| 6 | E13-nol2 | E8-nol2 results cache | ~20 new runs |
| 7 | E5-nol2 | E3 | ~50 |
| 8 | E7-nol2 | E6 | ~200 |
| 9 | E2-nol2 | E3 | ~100 |
| 10 | E9-nol2 | E3 | ~30 |
| 11 | E10-nol2 | E3 | ~60 |
| 12 | E11-nol2 | E6 | analytic |
| 13 | E12-nol2 | E6 | analytic |

---

## Key open questions

1. **Is α large or small in the L1 regime?**  Does A stay warm in L1 for TM ≤ 16
   (giving α ≈ 1), or is it evicted to DRAM (giving α ≈ 45)?  E4-nol2 answers this.

2. **Is TN independence cleaner?**  With one uniform DRAM latency for all L1 misses,
   the 1/TN correction term (which came from L2 cold-fill latency) might vanish or
   simplify.  E6-nol2 answers this.

3. **How large is gc*?**  The L2 crossover was gc*=476.  In L1-only, Memory-B is
   weaker (no L2 buffer), so gc* should be larger.  E13-nol2 quantifies this.

4. **What is the optimal TM for Memory-B in L1-only?**  Without L2 to buffer B,
   the Memory-B α(TM) might have a different shape than the L2 case.  E13-nol2
   measures this directly.
