# paper-model-validity — Writeup

The paper's derivation assumes a fast memory of exactly `M` words that holds
one C block while single subrows/subcolumns of the inputs stream through —
i.e. the C block can occupy essentially *all* of fast memory. A real cache
is neither fully associative nor scheduled; streams evict resident data. This
experiment measures how much of L1 the C tile can actually claim before the
paper's traffic prediction stops holding.

## Claim under test

With the aspect fixed at the predicted optimum (`T_N/T_M = 1/ρ = 4`), the
measured L1 BytesIn should equal the line-aware paper formula (excess = 1)
while the C tile + stream slices fit in L1, and peel away as the C-tile
budget approaches the L1 size. The paper implicitly claims validity up to
budget ≈ 1; the interesting output is the *actual* usable fraction.

## Setup

m = n = k = 256, ρ = 1/4 (A/C 8 B, B 2 B), TILE_K = k, `--outer_products`.
Tiles (4×16 … 64×256) grow the C tile from 512 B to 128 K at constant
aspect 4; L1 ∈ {16 K, 64 K} (L2 = 4×L1) × {fully-assoc, 8-way}. Plot
`measured/predicted` vs `log₂(C-tile bytes / L1 bytes)`: curves for the two
L1 sizes should collapse onto one universal curve per associativity if the
budget fraction is the controlling variable.

## Expected result

Fully-assoc: excess ≈ 1 up to a fraction somewhat below 1 (streams need room
for one A subcolumn slice + one B subrow), then a sharp knee. 8-way: excess
above 1 much earlier — power-of-two strides alias tile columns into single
sets, so the effective capacity is far below nominal. The knee position is
the experiment's headline number.
