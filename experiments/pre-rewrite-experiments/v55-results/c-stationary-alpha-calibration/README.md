# C-Stationary α Calibration

## Purpose

Measure the memory-bound cost α_calib(TM, TN) for C-stationary (col-major) mode
at gc=0. These values are the input to the roofline model in
`../multi-param-regression`.

Use the col-major variant — col-major eliminates ghost reads, so the calibrated
α reflects the true memory cost of output-stationary dataflow without the
row-major waste inflating the numbers. Run this after experiments 1–3 confirm
that col-major is the better C-stationary variant.

## How α_calib differs from B-stationary

In C-stationary col-major:
- C (output tile) is held in the accumulator across all K — no C traffic
- B is consumed in col-major order with no register reuse across A rows
- Each FIFO fill covers one full B tile (TK × TN elements)
- Cost: M_reg restarts per output tile (vs B-stat's shared B register)

So α_calib here captures the cost of M_reg restarts and the lack of B register
reuse, at gc=0 (no stall penalty). The roofline crossover with gc/TM will
therefore happen at a different point than for B-stationary.

Note: the generation term in the roofline is still `gc/TM` because the number
of FIFO elements generated per MNK is the same — TM register reuse of B happens
at the tile level in both modes. (Each B tile is generated once and consumed
by TM A rows, whether through register file in B-stat or through re-reads from
the FIFO in C-stat col-major with pipelining.)

## Setup

```
Matrix:  M=192, N=K=256, A_P=B_P=4B, TK=256, no_l2, mulac_norecord, 3dregisters
Mode:    output-stationary, col_major_fifo=True
gc:      0  (instantaneous generation — pure memory measurement)
L1:      {16KB, 32KB, 64KB}
TM:      {4, 8, 16, 24, 32, 48, 64, 96}
TN:      {4, 8, 16, 32, 64}
FIFO_CAP: 16384
```

Unsafe (TM, TN) pairs where ws_lines ≥ 300 are excluded.

## Output

One α_calib table per L1 size — a TM×TN grid of α values.
These tables feed directly into `../multi-param-regression`.
