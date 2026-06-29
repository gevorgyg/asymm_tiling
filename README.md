# Asymmetric Matrix Multiplication Sim
## Compilation

Just do 

```
make
```

in the root directory of the project.
## Usage
```
./asymm [--Bsource <prng_fifo|prng_mem|mem>] [--stationary <B|C>] [--config <file:default.config>] [--trace_file <file:trace.log>] [--trace_level <0|1|2:0>] [--assembler_input <file>] --3dregisters --mulacc_norecord
```

### Flags:
- `--Bsource <prng_fifo|prng_mem|mem>` - how we assume to receive the matrix B.
  Default: `mem`:
    - `prng_fifo` - store only seeds of tiles, for each seed a tile will be generated and stored in a FIFO. FIFO size and cycle cost per element is configured in config file.
    - `prng_mem` - store B as a whole, generate parts of B on-demand and if it
      has been generated look for it in memory
    - `mem` - non-PRNG mode (B is simply stored in memory)
- `--stationary <B|C>` - accumulate either into B or C. Default: `C`
- `--config <file:default.config>` - configuration file with hardware parameters. Default: `default.config`
- `--trace_file <file:trace.log>` - store the execution trace into a file.
  Default: `trace.log`
- `--trace_level <0|1|2:0>` - trace verbosity. Default: `0`
  - `0` (instructions): one line per ISA instruction with its cycle total
  - `1` (accesses): adds one indented line per address (element) read/write
  - `2` (actions): adds every device Action (hits, misses, fills, evictions,
    generations)
- `--assembler_input <file>` - run the interpreter directly on an existing trace file instead of generating a new one
- `--3dregisters` - enable 3D registers, each one storing a part of a 3D tile (where
  the depth dimension is the common dimension between A and B)
- `--mulac_norecord` - do not log `MulAcc` action into the trace and do not
  count cycles performed by it towards total cycle count

---

## Memory Hierarchy Map (**AI GENERATED**)
 
```
                                      v
  ┌────────────────────────── MemoryHierarchy::access ────────────────────────────┐
  │                                                                              │
  │   access(addr, sz, is_write, trace)                                          │
  │            │                                                                 │
  │            v                                                                 │
  │      ┌────────────┐                                                          │
  │      │ MMIO check │  is addr in PrngFifoDev range? (the only L1 bypass)      │
  │      └─────┬──────┘                                                          │
  │            ├───────────────────────────> yes: PrngFifoDev::read/write        │
  │            │ no                                                              │
  │            v                                                                 │
  │        ┌────────┐  hit: probe() -> TagLookup, done                           │
  │        │   L1   │ ───────────────────────────> Trace: [TagLookup HIT]        │
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
  │   back in L1: fillLine() -> Evict (if set full, writeback if dirty) + LineFill │
  │   Trace: [TagLookup, IsGenerated, Generate, LineFill]            (PRNG path) │
  │   Trace: [TagLookup, TagLookup, MemoryAccess?, LineFill(s), …]   (mem path)  │
  └───────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      v
                    main: print L1/L2 stats, PRNG/PRNG FIFO stats, total cycles
```

## Trace

Every cycle-costing event in the simulator is a subclass of `Action` and is
logged. **If it's not in the trace, it didn't happen!** Some examples :

```

prefetch (0x6c0, 4, 4, 24, 8) (3184 cy) #LEVEL 0 ACTION#
  read  @0x6c0 (199 cy)                 #LEVEL 1 ACTION#
    L1 TagLookup @0x6c0 MISS (4 cy)     #LEVEL 2 ACTION#
    L2 TagLookup @0x6c0 MISS (15 cy)
    MemoryAccess @0x6c0 (180 cy)
    L2 LineFill @0x6c0
    L1 LineFill @0x6c0
  read  @0x6c8 (199 cy)
    L1 TagLookup @0x6c8 MISS (4 cy)
    L2 TagLookup @0x6c8 MISS (15 cy)
    MemoryAccess @0x6c8 (180 cy)
    L2 LineFill @0x6c8
    L1 LineFill @0x6c8
  read  @0x6d0 (199 cy)
    L1 TagLookup @0x6d0 MISS (4 cy)
    L2 TagLookup @0x6d0 MISS (15 cy)
    MemoryAccess @0x6d0 (180 cy)
    L2 LineFill @0x6d0
    L1 LineFill @0x6d0
  read  @0x6d8 (199 cy)
    L1 TagLookup @0x6d8 MISS (4 cy)
    L2 TagLookup @0x6d8 MISS (15 cy)
    MemoryAccess @0x6d8 (180 cy)
    L2 LineFill @0x6d8
    L1 LineFill @0x6d8

```
---

## Configuration

In the configuration file we can choose numerical parameters for the simulation
(with some constraints -- see below). Here is `default.config`:

```
# Matrix dimensions (elements)
A_HEIGHT_DIM=12
A_WIDTH_DIM=12
B_WIDTH_DIM=24

# Element widths (bytes)
A_PRECISION_BYTES=8
B_PRECISION_BYTES=2

# Cache tile dimensions (elements)
TILE_M=4
TILE_N=4
TILE_K=4

# L1 cache
L1_SIZE_BYTES=256
L1_LINE_SIZE_BYTES=8
L1_ASSOC=4
L1_ACCESS_CYCLES=4
L1_REPLACEMENT_POLICY=LRU
L1_WRITE_POLICY=WRITE_BACK

# L2 cache
L2_SIZE_BYTES=1024
L2_LINE_SIZE_BYTES=8
L2_ASSOC=8
L2_ACCESS_CYCLES=15
L2_REPLACEMENT_POLICY=LRU
L2_WRITE_POLICY=WRITE_BACK

# Main memory
MEM_ACCESS_CYCLES=180

# Used by: --Bsource prng_mem
# PRNG device (generates B's cache lines on demand)
PRNG_ACCESS_CYCLES=2
PRNG_GEN_COST_PER_LINE=64

# Used by: --Bsource prng_fifo
# PRNG FIFO device
PRNG_FIFO_CAPACITY=64
PRNG_FIFO_GEN_COST=10

# Used by: --3dreg
# Hardware register tile dimensions
REG_M=4
REG_N=4
REG_K=4

# Suppressed by: --mulac_norecord
# tmulac computation cycles per register tile multiply-accumulate
MULAC_CYCLES=8
```
### Constraints
- Tile dimensions must divide matrix dimensions: `m | A_HEIGHT_DIM`, `n | B_WIDTH_DIM`, `k | A_WIDTH_DIM`.
- With register tiling configured, register dimensions must divide cache tile dimensions: `REG_M | m`, `REG_N | n`, `REG_K | k`.
- With `--Bsource prng_fifo` or `--Bsource prng_mem`, a B tile row must be a whole number of cache lines: `n * B_PRECISION_BYTES` must be a multiple of `L1_LINE_SIZE_BYTES`.
- With `--Bsource prng_fifo` or `--Bsource prng_mem`, the PRNG window must be line-aligned: A's byte size and B's byte size must be multiples of `L1_LINE_SIZE_BYTES`.


## Completed Experiments & Architectural Findings

We evaluated five architectural sweeps on a $256 \times 256$ matrix multiply using the simulator:

### 1. C-Stationary vs. B-Stationary (Multi-Level Tiling)
* **Results:** C-Stationary outperforms B-Stationary by up to **200x** (e.g. 52M vs 9.9B cycles for Normal Mode).
* **Finding:** In C-Stationary, accumulation is kept resident in registers (`%rc`), only writing to cache once at the end of the reduction. B-Stationary must continuously load/store intermediate output tiles from cache to accumulate products, creating massive writeback traffic and thrashing the caches.

### 2. Physical Register Tiling vs. Scalar Mode
* **Results:** Register Tiling ($4 \times 4 \times 4$ size) achieves a **3.56x speedup** (saving 133.5M cycles) over scalar cache mode.
* **Finding:** Without physical register tiles, every multiply-accumulate must load operands directly from the L1 cache. Register tiles eliminate **12.6 million L1 cache tag lookups** and their associated port query latencies (4 cycles/lookup).

### 3. PRNG FIFO Streaming vs. Normal DRAM-Backed Mode
* **Results:** Normal mode (DRAM-backed B) is **10% to 27% slower** than PRNG FIFO mode.
* **Finding:** Normal mode incurs a heavy **180-cycle DRAM access penalty** on L2 cache misses for B. Furthermore, B accesses in Normal mode must query L1, whereas FIFO MMIO reads bypass L1 entirely, saving ~5.2 million L1 cache port lookups.

### 4. FIFO Capacity & CPU Compute Latency Interaction (Stall Sweep)
* **Results:** Increasing FIFO capacity from 4 to 32 elements reduces CPU stalls by **99.5%** (from 23.5M cycles down to 130,560 cycles under 2-cycle compute latency).
* **Finding (The Reservoir Effect):** A larger FIFO acts as a reservoir, allowing the background generator to run uninterrupted during CPU overhead periods (like prefetching A/C cache lines). A small FIFO (4 or 8) pauses the generator immediately when full, wasting background cycles and causing severe CPU stalls during bursts of reads.

### 5. Cache Replacement Policy: LRU vs. FIFO
* **Results:** In shapes **32x64x16**, **32x128x32**, and **64x256x64**, **FIFO replacement outperforms LRU by up to 3%** (saving 1.7M cycles).
* **Finding (LRU Cache Pollution):** Matrix B elements are read sequentially inside the innermost loop with no immediate temporal reuse. Under LRU, these recently read B lines are MRU-protected in the sets, forcing eviction of highly reused A and C lines. FIFO evicts B's lines first since they were inserted first, preserving C and A temporal reuse.

---

## Q&A/Design Considerations:
*(Historical Design Discussions)*

**Q: What is the input? (m,n,k)**
**A:** `m` is tile height of matrix A, `n` is tile width of matrix `B`, `k` is tile width of A and tile height of B. Matrix C is generated by tiles of size `m x n`.

**Q: What is "reduction depth"? (called `k` above)**
**A:** In a matrix multiply, each output element `C[i][j]` is a sum of `K` products. Summing `K` products can grow by up to `log2(K)` more bits before it overflows, so the accumulator needs roughly `2N + log2(K)` bits to be safe. int8×int8→int32 is standard for this reason.

**Q: What is the interface for the PRNG device?**
**A:** The device gets called by a command `startprng <magic_addr> <seed>` ISA command. In our implementation, we abstraction-layered this through `PrngDev` (on-demand cache model) and `PrngFifoDev` (MMIO control-driven queue model).

**Q: What are the possible strategies to receive and store PRNG data?**
**A:** (1) Register model (FIFO depth 1), (2) Scratchpad model, or (3) Cache-streaming model (which we modeled via `PrngDev` where B addresses query the generator instead of falling through to L2/DRAM).

**Q: What does it mean a matrix is stationary?**
**A:** A stationary operand stays in its register across the inner loop and gets reused while the other operands are reloaded. C-stationary holds the accumulator in registers during the reduction loop, while B-stationary keeps the weights resident in registers and streams partial products.
