# paper-model-validity — Writeup

The paper's derivation assumes a fast memory of exactly `M` words that holds
one C block while single subrows/subcolumns of the inputs stream through —
i.e. the C block can occupy essentially *all* of fast memory. A real cache
is neither fully associative nor scheduled; streams evict resident data. This
experiment measures how much of L1 the C tile can actually claim before the
paper's traffic prediction stops holding.

## The two axes, defined

- **budget fraction** (x-axis) = `C-tile bytes / L1 bytes` = how much of L1 the
  resident C block demands. At budget = 1 the tile alone would fill L1, so the
  paper's "C block sits in fast memory *and* inputs stream past it" assumption
  cannot hold beyond there — that is the **predicted breakdown** vertical.
- **excess** (y-axis) = `measured L1 BytesIn / predicted L1 BytesIn`, the
  prediction being the line-aware paper formula. **excess = 1** means the
  simulator moved exactly the traffic the paper predicts — the model holds.
  **excess > 1** means the cache re-fetched lines the paper assumed stayed
  resident — the model has broken. This reference sits on the plot as a grey
  horizontal at 1.

## Claim under test

With the aspect fixed at the predicted optimum (`T_N/T_M = 1/ρ = 4`), excess
should stay pinned at 1 while the C tile fits, then climb away from 1 as the
budget fraction approaches (and passes) the predicted-breakdown vertical. The
headline output is *where* excess leaves 1 — the true usable fraction of L1,
which is below the paper's implicit budget ≈ 1.

## Setup

m = 256, n = 1024, k = 128 (wide n so the largest tile still fits),
ρ = 1/4 (A/C 8 B, B 2 B), TILE_K = k, C-stationary. Tiles (4×16 … 256×1024)
grow the C tile from 512 B to 2 MB at constant aspect 4, so
`log₂(C-tile / 16 K L1)` runs from -5 to 7; L1 ∈ {16 K, 64 K} (L2 = 4×L1) ×
{fully-assoc, 8-way}. Plot `measured/predicted` vs
`log₂(C-tile bytes / L1 bytes)`: curves for the two L1 sizes should collapse
onto one universal curve per associativity if the budget fraction is the
controlling variable.

## Expected result

Fully-assoc: excess ≈ 1 up to a fraction somewhat below 1 (streams need room
for one A subcolumn slice + one B subrow), then a sharp knee. 8-way: excess
above 1 much earlier — power-of-two strides alias tile columns into single
sets, so the effective capacity is far below nominal. The knee position is
the experiment's headline number.
