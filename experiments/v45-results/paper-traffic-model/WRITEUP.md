# paper-traffic-model — Writeup

Tests the central quantitative claims of
`Multiplication_by_a_Random_Matrix.pdf` (§2), which analyzes C-stationary
matmul `C = A·B` with one cheap input in a two-level memory model: a fast
memory of `M` words holds one `z × M/z` block of C while chunks of the
inputs stream through; every word crossing the fast-memory boundary is
counted ("reads" in, "writes" out).

## Mapping paper → simulator

The paper's cheap matrix is A; in this simulator the cheap matrix is B, so
the stretched tile dimension is the *column* one:

| paper | here |
|---|---|
| fast memory of M words | L1 (fully associative for the model regime) |
| reads | L1 BytesIn |
| writes | L1 BytesOut (with mandatory end-of-run flush) |
| `z × M/z` C block | `TILE_M × TILE_N`, `M = TILE_M·TILE_N` C words |
| ρ | `B_PRECISION / A_PRECISION` |
| streaming subrows/subcols | `--outer_products` instruction order |

## Claims under test

1. **Reads formula.** Total reads `= mnk·(A_p/T_N + B_p/T_M) + mn·C_p` bytes
   (the paper's `(mnk/M)(ρz + M/z) + mn` in words). Tested by sweeping tile
   aspect at constant area and overlaying the closed-form curve.
2. **Writes = mn·C_p**, one write per C element, independent of tile shape.
3. **Optimum at `T_N/T_M = 1/ρ`**; square tiles degenerate for ρ = 1.
4. **Savings vs square** `→ 2√ρ/(1+ρ)` (the paper's 90%/75%/58% list for
   ρ = 1/2, 1/4, 1/8).

The word model ignores cache lines. A "line-aware" variant (each row-segment
touch rounded up to whole lines) is overlaid where tile rows are narrower
than a 64 B line; deviations of the measured points from the *word* curve at
extreme aspects are expected and quantified by the line-aware curve instead.

## Setup

m = n = k = 256, A/C at 8 B, B ∈ {8, 4, 2, 1} B (ρ = 1 … 1/8), TILE_K = k,
register tile 4³, `--outer_products`. Two constant-area families (512- and
1024-word C tiles = 4 K/8 K of a 16 K L1). Two regimes: **ideal**
(fully-associative L1/L2, the paper's model) and **realistic 8-way** — at
power-of-two matrix strides the row stride aliases entire tile columns into
one set, a pathology the paper's model cannot see.

## Pilot validation: the model regime is exact

One pilot cell, worked end to end. Config: m = n = k = 256, A/C at 8 B,
B at 2 B (ρ = 1/4), tile 32×32, TILE_K = 256, `--outer_products`,
fully-associative 16 K L1.

Reads formula, term by term (mnk = 256³ = 16,777,216):

```
A:  mnk · A_p/T_N  =  16,777,216 · 8/32  =  4,194,304 B
B:  mnk · B_p/T_M  =  16,777,216 · 2/32  =  1,048,576 B
C:  mn  · C_p      =  65,536 · 8         =    524,288 B
                                   total =  5,767,168 B
```

Measured L1 BytesIn: **5,767,168 — equal to the byte.** Measured L1
BytesOut: **524,288 = mn·C_p, also exact** (the end-of-run flush makes the
last C tile's writeback visible). Exactness is possible because every row
segment at this tile is whole lines: A rows 2048 B = 32 lines, B rows
64 B = 1 line, C rows 256 B = 4 lines, so the line-aware and word models
coincide.

The same cell with a realistic 8-way L1 moves **43,523,072 B in (7.5×) and
33,554,432 B out (64×)**. The mechanism is stride aliasing: 16 K / 64 B /
8-way gives 32 sets, so the set span is 32·64 = 2048 B — exactly the A/C
row stride of 256·8 B. Every row of a C-tile column-of-lines therefore maps
to the *same* set: 32 lines fighting over 8 ways. The C tile can never stay
resident, so each of its 8192 lines is re-fetched and written back on every
one of the k/REG_K = 64 rank-1 steps: 8192 · 64 = 524,288 writebacks =
33,554,432 B — matching the measurement exactly. (B fares little better:
stride 512 B advances the set index by 8 per row, so B cycles through only
4 of the 32 sets.)

## Expected result

In the ideal regime the measured points sit *on* the line-aware curve, the
argmin sits at `1/ρ` up to grid discreteness, and writes are flat at
`mn·C_p`. The 8-way regime sits far above the model with the gap widening
at large C tiles — quantifying how much of the paper's promise a real
set-associative cache actually delivers at power-of-two strides.
