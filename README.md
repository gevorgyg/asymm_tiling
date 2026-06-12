# Asymmetric Matrix Multiplication Sim
## Usage
```
./asymm <m> <n> <k> [--Bgenerated] [--config <file>] [--trace_file <file>] [--trace_level <0|1|2>]
```

### Flags:
- `--Bgenerated` - simulate generating B from a PRNG device (the default mode is
  that both A and B are stored in memory)
- `--config <file>` - configuration file with hardware parameters (see
  `default.config`); required
- `--trace_file <file>` - store the execution trace into a file
- `--trace_level <0|1|2>` - trace verbosity (only meaningful with
  `--trace_file`); each level includes everything from the levels above it.
  Default is 2.
  - `0` (instructions): one line per ISA instruction with its cycle total, e.g.
    `ltea (0x480, 8, 3, 24, 2), %rb    # 532 cy`
  - `1` (accesses): adds one indented line per element read/write, e.g.
    `  read  @0x480 (70 cy)`
  - `2` (actions): adds every device Action, e.g.
    `    L1 TagLookup @0x480 MISS (4 cy)` / `    PRNG Generate line @0x480 (64 cy)`

## TODO:
- block diagram.  
- Add logic for:

   ~~1. generating the seed by the generator.~~

    ~~2. saving the seed in an agreed apon memory area between the generator and CPU.~~

    ~~3. "using" the seed to generate the prng numbers (logically).~~ (although
    I'm not sure what is meant here...)

  4. For now the simulator only calculates cycle access to cache (I'm not even
       sure it calculates cycle cost of going to memory). We need to
       take into account cycle cost of calling the PRNG device. Maybe of
       something else? 

    ~~5. It would be nice if memory objects, like register file, caches, the
       memory, the PRNG device could be abstracted into a class, for clearness
       and ease of extension~~

    ~~6. The cache simulator itself is probably larger than necessary and it's workings are not totally clear, I
       think it can be simplified (especially for our purposes). Maybe there is
       more room for simplification.~~

## Code Map (WARNING! AI-GENERATED!)
```
                                    ./asymm [--Bgenerated] [--config f] [--trace_file f] <m> <n> <k>
                                                            │
                                                            v
  ┌──────────────────────────────────────────────────── main.cpp ────────────────────────────────────────────────────┐
  │                                                                                                                  │
  │   default.config ──> loadConfigFile() ──> g_config map ──> getConfig(key)                                        │
  │        │                                                                                                         │
  │        ├────────────> matrix dims/precisions ──────────────┐                                                     │
  │        └────────────> cache + mem + prng parameters ───────┼──────────────┐                                      │
  │                                                            │              │                                      │
  │   --Bgenerated ──> prng.window_bytes = B bytes (else 0) ───┘              │                                      │
  └───────────────────────────────────────────────────────────┼──────────────┼──────────────────────────────────────┘
                                                               │              │
                              ┌────────────────────────────────┘              │
                              v                                               v
                ┌── InstGenerator ──────────────┐                ┌── MemoryHierarchy ctor ──┐
                │ GhostMat A @0x0               │                │ builds devices, wires    │
                │ GhostMat B @A.bytes           │                │ the topology below       │
                │ GhostMat C @A.bytes+B.bytes   │                └──────────────────────────┘
                │                               │
                │ emitTrace(tile m,n,k):        │
                │   ltea / tmulac / tmov stream │      (stream is identical with and
                └───────────────┬───────────────┘       without PRNG -- routing is hardware)
                                v
                          matmul.matv  (text ISA)
                                │
                                v
  ┌─────────────────────────── Interpeter::run() ────────────────────────────────────────────────────────────────────┐
  │  readCmd() ── ltea ───> handleTload():  check PRNG tile-row % line_size == 0;                                     │
  │            │            set vec_reg; doRead() per element of tile                                                 │
  │            ├─ tmov ───> handleTmove():  set vec_reg; doWrite() per element                                        │
  │            └─ tmulac ─> handleMulAcc(): register-only -- validates tile shapes, no memory traffic                 │
  │                                                                                                                   │
  │  doRead/doWrite: Trace t; mem_.read/write(addr, elem_width, t);                                                   │
  │                  cpu_cycles_ += totalCycles(t);  buffered per instruction ──> --trace_file (per --trace_level)    │
  └───────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┘
                                      v
  ┌────────────────────────── MemoryHierarchy ───────────────────────────────────┐
  │                                                                              │
  │      read/write(addr)                                                        │
  │            │                                                                 │
  │            v                                                                 │
  │        ┌────────┐  hit: TagLookup, done                                      │
  │        │   L1   │ ───────────────────────────> Trace: [TagLookup]            │
  │        └───┬────┘                                                            │
  │            │ miss                                                            │
  │            v                                                                 │
  │      ┌────────────┐   addr in [B_base, B_end)?                               │
  │      │ AddrRouter │ ──────────────┬──────────────────┐                       │
  │      └────────────┘               │ yes               │ no                   │
  │                                   v                   v                      │
  │                            ┌────────────┐       ┌────────┐ miss  ┌─────────┐ │
  │                            │  PrngDev   │       │   L2   │ ────> │ MainMem │ │
  │                            │ IsGenerated│       └────────┘       └─────────┘ │
  │                            │ Generate   │                                    │
  │                            └────────────┘                                    │
  │                                   │                   │                      │
  │            ┌──────────────────────┴───────────────────┘                      │
  │            v                                                                 │
  │   back in L1: LineFill (+ Evict if set full)                                 │
  │   Trace: [TagLookup, IsGenerated, Generate, LineFill, Evict?]   (PRNG path)  │
  │   Trace: [TagLookup, TagLookup, MemoryAccess?, LineFill(s), …]  (mem path)   │
  └───────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      v
                    main: print L1/L2 stats, PRNG gen/regen, total cycles

```
## Q&A/Design Considerations:

**Q: What is the input? (m,n,k)**

**A: (Gosha) ** `m` is tile height of matrix A, `n` is tile width of matrix `B`, `k` is
tile width of A and tile height of B. Matrix C is generated by tiles of size `m
x n`.
By the way -- `k` is also called reduction depth/accumulation depth


**Q: WTF is "reduction depth"? (called `k` above)**

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

**Addition:** In the meantime, the precision of resulting matrix is just the
maximum of precisions. It should be fixed.


**Q: What is the interface for the PRNG device?**

**A: (Gosha)**  The device gets called by a command `startprng <magic_addr> <seed>` ISA command: it declares the `magic_addr` such that loading from
it tells the PRNG device to output data, and `seed` seeds the PRNG. For
generation purposes, seed of a tile is defined by *the initial seed and the number of loads from the generator*. 


In the implementation, our idea is for the seed to be stored in a register and
for the PRNG itself to track how many times it was called. In the simulator,
currently, this is dead state and may probably me removed. The seeding cost is
modeled in `PrngDevSim::reseed()` function.


There are alternative approaches but we haven't
researched it yet. 

**Q: What are the possible strategies to receive and store PRNG data?**

**Copy-pasted AI Answer:**
   There's a spectrum worth thinking about explicitly:

  - Register model (FIFO size 1). PRNG fills a single staging register; CPU pops; refill runs in parallel. Simplest. Same shape as current FIFO model with depth 1 — useful as a sanity baseline.
  - Scratchpad model. PRNG owns a small dedicated SRAM. startprng tells it "fill this region with the next tile of values." CPU reads from the scratchpad region as if it were memory, paying scratchpad
  access cost. Stall iff CPU outruns the fill. Cleaner than touching the cache; PRNG-generated data doesn't compete with A-data for cache capacity.
  - Cache-streaming model. PRNG behaves like a DMA engine that writes generated lines directly into L1 (or L2) at a configured address range. CPU then reads those lines through normal cache paths. This is
   the architecturally most interesting one for your asymmetric-cost project: PRNG data now competes with A-data for cache lines, evictions become consequential, and the tile-shape choice has visible
  second-order effects. It also raises a real question: if a generated line gets evicted, can you re-fetch it (PRNG would need to be re-seeded to the right offset), or do you mark them non-evictable /
  pinned? That decision is a hardware design choice worth modeling.

  The FIFO model you have now is essentially a 1D version of the scratchpad — it hides latency but doesn't interact with cache state. The cache-streaming model is what would actually expose the tradeoffs
  your simulator is built to study. Worth picking which one you want before sketching the PRNG class surface, because the interface differs significantly (pop() vs start_fill(region, seed) + normal reads
  through the hierarchy).


  **A (Gosha): ** 
  Alright there is all this stuff with FIFO that I'm not ready to think about
  yet, but in general the strategies boil down to:

  1) Reserve place for B and store low-size seed (e.g. a PRNG tile is 64B and a seed
  is 4B). The obvious advantage is that we can cache more seeds. We pay in
  entropy (we can only get `2^32` different tiles in contrast with `2^512` which
  possible ones). Does this matter for numerical linear algebra algorithms?
  Apparently not really, so this may be the best choice, actually.

  2) Reserve place in memory for B, use these addresses to index caches and to
  store there stale cachelines. The most obvious choice tbh.

  3) Use a B-stationary approach (instead of the default C-stationary): you
  generate a tile, compute everything with this tile, and then throw it away.
  Apparently, making the code B-stationary is not that hard (the
  generator-interpreter architecture allows us to do that pretty easily). Should
  try.

**Q: What does it mean a matrix is stationary?**

**Copy-pasted AI Answer:**

  What "stationary" means

  A stationary operand is one that stays in its register across the inner loop and gets reused while the other operands are reloaded. The chosen stationarity tells you which loop is innermost vs.
  outermost, which in turn decides how many times each tile gets loaded.

  The current generator (instgen.cpp:74-99) is C-stationary:
  for ti:                          // M outer
    for tj:                        // N middle
      load C[ti,tj]                // C stays put across k
      for tk:                      // K inner
        load A[ti,tk]
        load B[tk,tj]              // B reloaded every k step
        tmulac %ra,%rb,%rc         // C += A*B
      store C[ti,tj]
  C is loaded once per output tile, accumulated K_tiles times, stored once. A and B get reloaded K_tiles times per output tile.

  B-stationary flips it so B is the one held in the register across the inner loop:
  for tk:                          // K outer (so B-tile changes slowest)
    for tj:                        // N middle
      load B[tk,tj]                // B stays put across i
      for ti:                      // M inner
        load C[ti,tj]              // partial sum from prior k passes
        load A[ti,tk]
        tmulac %ra,%rb,%rc
        store C[ti,tj]             // must spill C every iteration
  Each B tile is loaded exactly once. The cost is that C is now loaded and stored on every inner iteration instead of staying in %rc across the k loop.

  Why this matters for your PRNG case

  The trade is asymmetric, which is exactly the project's point:
  - C-stationary + PRNG B: each B tile is regenerated M_tiles times → M_tiles · N_tiles · K_tiles PRNG-tile loads, each preceded by an expensive reseed().
  - B-stationary + PRNG B: each B tile is generated once → N_tiles · K_tiles PRNG-tile loads, and (if you order the k loop right) reseeds collapse to one per stream traversal.

  The cost you pay in exchange is M_tiles · N_tiles · K_tiles extra C loads+stores to L1. If B-generation cost > C cache traffic cost, B-stationary wins.

  Concrete trace example

  Take a 4×4 × 4×4 matmul with tile m=n=k=2 (so M_tiles=N_tiles=K_tiles=2), PRNG mode. C-stationary (what you emit today, abbreviated):

  strtrng 0xFFFFF000 0x1234
  ltea (C[0,0],...), %rc
  ltea (A[0,0],...), %ra
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #1 → B[0,0]
  tmulac %ra, %rb, %rc
  ltea (A[0,1],...), %ra
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #2 → B[1,0]
  tmulac %ra, %rb, %rc
  tmov (C[0,0],...), %rc

  ltea (C[0,1],...), %rc
  ltea (A[0,0],...), %ra
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #3 → B[0,1]  (must reseed back!)
  tmulac %ra, %rb, %rc
  ltea (A[0,1],...), %ra
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #4 → B[1,1]
  tmulac %ra, %rb, %rc
  tmov (C[0,1],...), %rc

  ; ... same for ti=1, two more C tiles, 4 more PRNG draws
  stprng
  Total: 8 PRNG draws, and the seed has to be reset between non-adjacent draws.

  B-stationary on the same problem:

  strtrng 0xFFFFF000 0x1234
  ; tk=0
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #1 → B[0,0]
    ltea (C[0,0],...), %rc
    ltea (A[0,0],...), %ra
    tmulac %ra, %rb, %rc
    tmov (C[0,0],...), %rc
    ltea (C[1,0],...), %rc
    ltea (A[1,0],...), %ra
    tmulac %ra, %rb, %rc
    tmov (C[1,0],...), %rc
  ltea (0xFFFFF000,...), %rb       ; PRNG draw #2 → B[0,1]
    ltea (C[0,1],...), %rc
    ltea (A[0,0],...), %ra
    tmulac %ra, %rb, %rc
    tmov (C[0,1],...), %rc
    ltea (C[1,1],...), %rc
    ltea (A[1,0],...), %ra
    tmulac %ra, %rb, %rc
    tmov (C[1,1],...), %rc
  ; tk=1: PRNG draws #3,#4 → B[1,0], B[1,1], same shape
  stprng
  Total: 4 PRNG draws, monotonically advancing — never need to reseed mid-stream. Cost paid back: 8 C-tile stores instead of 4, plus 8 C-tile loads instead of 4.
