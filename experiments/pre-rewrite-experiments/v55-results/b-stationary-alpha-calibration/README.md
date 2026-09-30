# B-Stationary α Calibration

## Purpose

Measure the memory-bound cost α_calib(TM, TN) for B-stationary mode at gc=0.
These values are the input to the roofline model in `../multi-param-regression`.

Setting gc=0 means the FIFO generates elements instantly — no stall cycles.
The simulator then measures pure L1/memory behavior, giving the true memory-bound
α without any generation interference.

## What α_calib captures

For each (TM, TN) pair:

```
α_calib(TM, TN) = cycles / MNK      (at gc=0)
```

This is the cost per output element due to L1 misses, cache line fills, and
register-tile reuse patterns. It depends on:
- Whether the A tile fits in L1 (TM × TK × A_P ≤ L1) — sharp drop when it does
- Whether the B tile fits in L1 (TN × TK × B_P ≤ L1)
- The register reuse structure of the emitter

## Setup

```
Matrix:  M=192, N=K=256, A_P=B_P=4B, TK=256, no_l2, mulac_norecord, 3dregisters
gc:      0  (instantaneous generation — pure memory measurement)
L1:      {16KB, 32KB, 64KB}  (one calibration table per L1 size)
TM:      {4, 8, 16, 24, 32, 48, 64, 96}
TN:      {4, 8, 16, 32, 64}
FIFO_CAP: 16384
```

Unsafe (TM, TN) pairs where ws_lines ≥ 300 are excluded.

## Output

One α_calib table per L1 size — a TM×TN grid of α values.
These tables feed directly into `../multi-param-regression`.
