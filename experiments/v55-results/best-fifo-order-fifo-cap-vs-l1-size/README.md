# Best FIFO Order: FIFO Capacity vs L1 Size

## Customer Question

Given a fixed SRAM budget (total on-chip memory for both L1 cache and FIFO buffer),
is it better to spend the budget on a larger L1 or a larger FIFO?

This is a hardware design tradeoff: L1 reduces A-matrix traffic by keeping A tiles
resident; a larger FIFO gives the generation device more slack to pre-fill without
stalling. The question is where the marginal transistor is better spent.

## Approach

**Mode**: use whichever FIFO ordering wins in the v55 experiments 1–3 (run first).
We only run the best mode here — the goal is the L1/FIFO split, not mode comparison.

**Fixed total budgets**: pick 2–3 total SRAM sizes (e.g. 64KB, 96KB, 128KB).
For each budget, sweep how it is split:

```
total = L1_bytes + FIFO_bytes
FIFO_bytes = FIFO_cap × B_PRECISION_BYTES   (B_P = 4)

Example, total = 96 KB:
  L1=16KB  FIFO_cap=20480 (80KB)
  L1=32KB  FIFO_cap=16384 (64KB)
  L1=48KB  FIFO_cap=12288 (48KB)
  L1=64KB  FIFO_cap= 8192 (32KB)
  L1=80KB  FIFO_cap= 4096 (16KB)
```

At each split, run a TM×TN empirical sweep (same ranges as v55 base experiments)
and record the best achievable cycles. Plot best cycles vs L1 fraction of budget.

**Generation costs**: run gc ∈ {0, 10, 100} as before — gc changes how much FIFO
slack matters, so the optimal split may shift with gc.

## Shared Setup

```
Matrix:  M=192, N=K=256, A_P=B_P=4B, TK=256, no_l2, mulac_norecord, 3dregisters
TM:      {4, 8, 16, 24, 32, 48, 64, 96}
TN:      {4, 8, 16, 32, 64}
gc:      {0, 10, 100}
Budgets: {65536, 98304, 131072}  (64KB, 96KB, 128KB)
Splits:  ~5–6 points per budget (L1 steps of 16KB)
```

## Expected Output

For each (budget, gc): a curve of best_cycles vs L1_fraction.
Summary table: optimal L1/FIFO split at each (budget, gc).

Key question: does the curve have a clear minimum (optimal split), or is it
monotone in one direction (L1 always wins, or FIFO always wins)?
