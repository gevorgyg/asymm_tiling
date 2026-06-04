# Asymmetric Matrix Multiplication Sim

## TODO:
- block diagram.  
- Add logic for:
    1. generating the seed by the generator.
    2. saving the seed in an agreed apon memory area between the generator and CPU.
    3. "using" the seed to generate the prng numbers (logically).


## Q&A/Design Considerations:

**Q: If matrix of precision `M` and a matrix of precision `N` get multiplied, what
should be the precision of the resulting matrix?**

**Copy-pasted AI Answer:**   
General arithmetic / hardware multipliers: the natural result of multiplying an `N`-bit by an `M`-bit value is `N+M` bits — that's what a full integer multiplier produces (e.g. x86 `MUL` gives a `2N`-bit result
  in `RDX:RAX`). Same for fixed-point DSP. Floats are an exception: `float * float → float` because the format itself rounds.

  Matrix multiply / accumulators (your case): the convention is wider than the inputs but not literally the sum, because you also accumulate many products. ML accelerators standardize on:
  - `int8 × int8 → int32` accumulator
  - `fp16 × fp16 → fp32` accumulator
  - `bf16 × bf16 → fp32` accumulator

  So accumulator width covers `product_bits + log2(K)` headroom, where `K` is the reduction depth.

  Looking at your `instgen.cpp:29`, `c_elem_width = std::max(a_elem_width, b_elem_width)` — that's narrower than either of the conventions above. For a tile-MAC pipeline you'd more typically want `a_elem_width + b_elem_width` at minimum, or jump straight to a fixed wider accumulator (e.g. always 4 bytes regardless of input widths). Worth deciding which model your `TILE_MUL_ACC` is supposed to follow.

**Q: WTF is "reduction depth"? (called `K` above)**
**Copy-pasted AI Answer:**
In a matrix multiply, each output element `C[i][j]` is a sum of `K` products:

  `C[i][j] = A[i][0]*B[0][j] + A[i][1]*B[1][j] + ... + A[i][K-1]*B[K-1][j]`

  That `K` — the inner-dimension length you sum across — is the reduction depth (the "reduce" step of map-reduce: many products collapsing into one sum). In your code it's `A.width` (== `B.height`).

  Why it matters for accumulator width:

  - One product of two `N`-bit values fits in `2N` bits.
  - Summing `K` such products can grow by up to `log2(K)` more bits before it overflows.
  - So the accumulator needs roughly `2N + log2(K)` bits to be safe in the worst case.

  Example: `int8 × int8` with `K=512`.
  - Each product: up to 16 bits.
  - Worst-case sum of 512 products: up to `16 + log2(512) = 16 + 9 = 25` bits.
  - `int32` covers this with comfortable headroom — which is exactly why `int8×int8→int32` is the standard choice on TPUs/tensor cores.

  In your tiled kernel, the relevant `K` for one `tmulac` chain is the number of inner iterations — `A.width / t_k` accumulations into the same `C` tile. That's the depth your `C`-tile accumulator has to survive
  without overflow.
