# Asymmetric Matrix Multiplication Sim
## Usage
```
./asymm <m> <n> <k> [--Bgenerated | --Bfifo] [--Bstationary] [--config <file>] [--trace_file <file>] [--trace_level <0|1|2>] [--trace_input <file>]
```

### Flags:
- `--Bgenerated` - simulate generating B from an on-demand PRNG device (mutually exclusive with `--Bfifo`).
- `--Bfifo` - simulate streaming B from a cycle-accurate MMIO PRNG FIFO device (mutually exclusive with `--Bgenerated`).
- `--Bstationary` - use the B-stationary loop tiling policy instead of the default C-stationary policy.
- `--config <file>` - configuration file with hardware parameters (see `default.config`).
- `--trace_file <file>` - store the execution trace into a file.
- `--trace_level <0|1|2>` - trace verbosity (only meaningful with `--trace_file`).
  - `0` (instructions): one line per ISA instruction with its cycle total.
  - `1` (accesses): adds one indented line per element read/write.
  - `2` (actions): adds every device Action (hits, misses, fills, evictions).
- `--trace_input <file>` - run the interpreter directly on an existing trace file instead of generating a new one.

### Input constraints:
- Tile dimensions must divide matrix dimensions: `m | A_HEIGHT_DIM`, `n | B_WIDTH_DIM`, `k | A_WIDTH_DIM`.
- With register tiling configured, register dimensions must divide cache tile dimensions: `REG_M | m`, `REG_N | n`, `REG_K | k`.
- With `--Bgenerated`/`--Bfifo`, a B tile row must be a whole number of cache lines: `n * B_PRECISION_BYTES` must be a multiple of `L1_LINE_SIZE_BYTES`.
- With `--Bgenerated`/`--Bfifo`, the PRNG window must be line-aligned: A's byte size and B's byte size must be multiples of `L1_LINE_SIZE_BYTES`.

---

## Code Map

```
                                ./asymm [--Bgenerated | --Bfifo] [--Bstationary] [--config f] <m> <n> <k>
                                                             │
                                                             v
  ┌──────────────────────────────────────────────────── main.cpp ────────────────────────────────────────────────────┐
  │                                                                                                                  │
  │   default.config ──> loadConfig(path) ──> Config (typed struct, see config.h)                                    │
  │        │                                                                                                         │
  │        ├────────────> matrix dims/precisions ──────────────┐                                                     │
  │        └────────────> cache + mem + prng + fifo parameters ┼──────────────┐                                      │
  │                                                            │              │                                      │
  │   --Bgenerated ──> prng.window_bytes = B bytes (else 0) ───┘              │                                      │
  │   --Bfifo      ──> prng_fifo.fifo_capacity = cfg val (else 0) ─────────────┤                                      │
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
                 │   ltea / tmulac / tmov stream │      (stream is adapted for Bfifo
                 └───────────────┬───────────────┘       MMIO writes to control registers)
                                 v
                           matmul.matv  (text ISA)
                                 │
                                 v
  ┌─────────────────────────── Interpreter::run() ───────────────────────────────────────────────────────────────────┐
  │  handleCmd() dispatches via op-table { "ltea", "tmov", "prefetch", "tmulac" } -> member function:                 │
  │     ltea     -> handleTload():    parseTileParams + validateRegShape; set vec_reg; doRead per element            │
  │     tmov     -> handleTmove():    parseTileParams + validateRegShape; doWrite per element                        │
  │     prefetch -> handlePrefetch(): parseTileParams; doRead per element                                            │
  │     tmulac   -> handleMulAcc():   reg-only path; scalar element loads if reg_m_ == 0; pushes MulAcc Action       │
  │                                                                                                                  │
  │  doRead/doWrite: Trace t; mem_.access(addr, sz, is_write, t);                                                    │
  │                  cpu_cycles_ += totalCycles(t);  buffered per instruction ──> --trace_file (per --trace_level)   │
  └───────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┘
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

### Action model

Every cycle-costing event in the simulator is a subclass of `Action`
(`memory-system/action.h`). Each device's `read`/`write` (or, for compute,
the interpreter's `handleMulAcc`) does all the state mutation and then
appends a pure-data witness:

| Action          | Where it lives                                  |
| --------------- | ----------------------------------------------- |
| `TagLookup`     | `memory-system/cache/cache_actions.h`           |
| `LineFill`      | same                                            |
| `Evict`         | same                                            |
| `MemoryAccess`  | `memory-system/mainmem/mainmem_actions.h`       |
| `IsGenerated`   | `memory-system/prng/prng_actions.h`             |
| `Generate`      | same                                            |
| `Fifo*` (5x)    | `memory-system/prng_fifo/prng_fifo_actions.h`   |
| `MulAcc`        | `interpreter/matmul/matmul_actions.h`           |

A `Trace = std::vector<std::unique_ptr<Action>>` carries one request's
witnesses; `totalCycles(trace)` sums their `cyclesToPerform()`.

---

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
