# v55 Experiments: FIFO Dataflow Mode Comparison

## Goal

These experiments generate empirical data to help a customer configure their
system when using a PRNG-FIFO to generate the B matrix on-chip.  The customer
needs to know:

- Which register dataflow mode (B-stationary vs output-stationary) to use?
- What tile shape (TM, TN) is best for their L1 cache size?
- Does a column-major output-stationary mode change the picture?
- Does pipelining help, and if so in which mode?

All experiments sweep TM × TN empirically for each configuration and report
the best achievable performance — no model, no formula, just measured data.

## Experiments

### 1. `b-stationry-vs-c-stationary`

Compares **B-stationary** vs **C-stationary row-major** FIFO.

B-stationary holds each B sub-tile in the register file while all A rows
iterate over it, giving M_reg-fold register reuse of B.  C-stationary
(row-major) holds C in the accumulator register across all K, but must
consume the entire B tile in row-major order for each output column —
wasting (N_reg − 1) reads per useful read as ghost reads.

### 2. `b-stationary-vs-c-stationry-col-major`

Compares **B-stationary** vs **C-stationary col-major** FIFO.

Col-major output-stationary eliminates the ghost reads: the FIFO generates
one full B tile in column-major order per rti, so all elements are actually
used.  The cost is M_reg restarts per output tile instead of B-stat's shared
register reuse.  This experiment shows whether removing the waste closes the
gap with B-stationary.

### 3. `b-stationary-vs-c-stationry-col-major-pipelined`

Compares **pipelined B-stationary** vs **pipelined C-stationary col-major**.

The pipelined FIFO device pre-generates the next tile in the background while
the current one is being consumed.  This experiment asks whether pipelining
helps C-stat col-major enough to compete with pipelined B-stat, given that
C-stat consumes B elements faster (no register-level reuse of B).

## Shared Setup

```
Matrix:  M=192, N=K=256, A_P=B_P=4B, TK=256 (full K in one pass)
L1:      16KB / 32KB / 64KB  (fully associative, no L2)
TM:      {4, 8, 16, 24, 32, 48, 64, 96}
TN:      {4, 8, 16, 32, 64}
gc:      {0, 10, 100}  cycles per FIFO element generated
FIFO cap: 16384 elements  (= 1 full B tile at TN=64; capacity is not the variable here)
```

Unsafe tile combinations (register file overflow, ws_lines ≥ 300) are
excluded from the best-tile search and shown as "—" in the grids.

## Separate Customer Questions (future experiments)

- **L1 vs FIFO capacity tradeoff**: given a fixed silicon budget, is it
  better to spend it on more L1 or a larger FIFO buffer?
