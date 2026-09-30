# paper-model-validity-fifo-bstat — Writeup

Identical to [`paper-model-validity-fifo`](../paper-model-validity-fifo/) —
FIFO-generated B, A/B cost parity (20 cycles per element each way), equal 8 B
precision, 8 B seed per tile — but **B-stationary**.

## Why run both

Under the FIFO device you cannot re-read B for free; you regenerate it. The
loop order therefore decides the recompute bill:

- **C-stationary** holds the C tile and streams B → B is regenerated on every
  pass through the M dimension.
- **B-stationary** holds each B subtile and streams A while C accumulates → B
  is generated **once** per subtile and reused across the whole M stream.

A direct sanity check on the default workload showed C-stationary generating
~227k B elements versus ~10k for B-stationary — a ~22× reduction. This
experiment measures the same tradeoff across the C-tile budget sweep, and the
cost it exposes: B-stationary stops holding C resident, so C is
read-modify-written across k and L1 traffic (and the cache-pressure story)
shifts onto C instead of onto B generation.

## Setup

Same as the companion: m = 128, n = 512, k = 64, TILE_K = k, aspect 4,
`--Bsource prng_fifo --stationary B`, fully-assoc vs 8-way, budget -3..7. The
budget axis (C-tile / L1) is kept for one-to-one comparison even though C is
the streamed, not the resident, matrix here.

## Expected result

`fifo_generations` far below the C-stationary companion (the amortization);
the metric-family cycles dominated by C traffic rather than B generation; and
the associativity excess driven by C streaming rather than by a resident tile.
