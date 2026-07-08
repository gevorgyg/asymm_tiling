# paper-per-matrix-balance — Writeup

Tests the *mechanism* behind the optimum in
`Multiplication_by_a_Random_Matrix.pdf`: the per-C-block reads decompose as
`ρzk` (cheap input) `+ k·M/z` (expensive input) `+ M` (the C block), and the
AM-GM step of the derivation makes the two *input* terms equal exactly at the
optimal shape. §3's intuition — "as ρ gets lower, z gets higher, so we
perform more loads of the cheaper matrix in comparison to the expensive one"
— is this balance restated.

## Claims under test (bytes, our convention: B is cheap)

1. `A_in = blocks·T_M·lines(k·A_p)` — falls as tiles widen (∝ 1/T_N).
2. `B_in = blocks·k·lines(T_N·B_p)` — falls as tiles grow tall (∝ 1/T_M).
3. `C_in ≈ mn·C_p` — flat.
4. **Balance:** `B_in/A_in = ρ·(T_N/T_M)` (word model), crossing **1** at the
   predicted optimum `T_N/T_M = 1/ρ`.
5. **Writes are C-only:** dirty L1 evictions belong to the C region almost
   exclusively; A and B are read-only.

Measured via region-tagged level-2 traces (per-matrix L1 line fills and
dirty evictions). Note the end-of-run flush is not part of the trace, so
per-matrix write bytes undercount by the dirty lines still resident at exit
(≤ L1 size ≪ mn·C_p).

## Setup

m = n = k = 128, TILE_K = k, fully-associative 16 K L1 (the model regime),
C-stationary, ρ ∈ {1, 1/2, 1/4, 1/8} via B precision {8, 4, 2, 1} B,
two constant-area tile families (512/1024 words). The earlier version of
this experiment measured per-matrix *DRAM* bytes under the cache-tiled
instruction order and found B ≫ A everywhere; measuring at the paper's own
boundary (L1) under the paper's own loop order is the honest test of the
AM-GM claim.

## Expected result

Log-scale per-matrix curves matching the three analytic terms; the B/A curve
a straight line of slope ρ (in log-log) crossing 1 at `log₂(1/ρ)`; the
writes bar chart ~100 % C at every ρ.
