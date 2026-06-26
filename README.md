# Asymmetric Matrix Multiplication Sim
## 1. Building the Simulator

The project contains a `makefile` to automate building and testing. 

* **Compile the simulator:**
  ```bash
  make
  ```
  This creates the `./asymm` executable.

* **Run all tests (Unit & Integration):**
  ```bash
  make test
  ```

---

## 2. Command Line Syntax

To run a simulation, use the following syntax:
```bash
./asymm [options] <m> <n> <k>
```

### Positional Arguments
* **`<m>`**: Tile height dimension of Matrix A (and Matrix C).
* **`<n>`**: Tile width dimension of Matrix B (and Matrix C).
* **`<k>`**: Reduction depth (Tile width of A, Tile height of B).

> [!NOTE]
> The tiles must be square or rectangular. To run with square tiles (e.g., of size 32), specify `32 32 32`.

---

## 3. Command Line Options

| Option / Flag | Description |
| :--- | :--- |
| **`--config <file>`** | Path to the hardware and matrix configuration file. If omitted, defaults to `default.config` in the current working directory. If the file does not exist at the specified path, the simulator will automatically create a default configuration file there. |
| **`--Bgenerated`** | Simulates generating B elements on-demand at cache-line granularity using a PRNG device. Bypasses normal DRAM loads. |
| **`--Bfifo`** | Simulates streaming B elements on-demand through the cycle-accurate **PRNG FIFO** device using control/data MMIO registers. |
| **`--Bstationary`** | Force B-stationary loop tiling (keeps a B tile in the register file while scanning through A and C tiles). If omitted, C-stationary loop order is used. |
| **`--scratchpad`** | Simulates using scratchpad memory for tile storage instead of the standard cache hierarchy. |
| **`--trace_file <file>`** | Saves the step-by-step simulator execution trace into the specified file. |
| **`--trace_level <0\|1\|2>`** | Verbosity of the trace file (default is 2):<br>• **`0` (instructions):** Cycle count per ISA instruction.<br>• **`1` (accesses):** Adds memory read/write details.<br>• **`2` (actions):** Adds individual device actions (e.g., L1 hit/miss, PRNG generation). |
| **`--stat_file <file>`** | Saves the final simulation statistics in a markdown table format to the specified file (can also be specified as `--stat-file <file>`). |
| **`--trace_input <file>`** | Load and execute a pre-generated assembly instruction trace (`.matv`) directly instead of generating one dynamically. |

---

## 4. Configuration File Variables

The configuration file passed via `--config` specifies the dimensions and hardware characteristics. Example:

```ini
# Matrix dimensions (elements)
A_HEIGHT_DIM=256
A_WIDTH_DIM=256
B_WIDTH_DIM=256

# Element precisions (bytes)
A_PRECISION_BYTES=8
B_PRECISION_BYTES=2

# L1 Cache Parameters
L1_SIZE_BYTES=32768
L1_LINE_SIZE_BYTES=64
L1_ASSOC=8
L1_ACCESS_CYCLES=4
L1_REPLACEMENT_POLICY=LRU
L1_WRITE_POLICY=WRITE_BACK

# L2 Cache Parameters
L2_SIZE_BYTES=262144
L2_LINE_SIZE_BYTES=64
L2_ASSOC=8
L2_ACCESS_CYCLES=14
L2_REPLACEMENT_POLICY=LRU
L2_WRITE_POLICY=WRITE_BACK

# DRAM Latency (cycles)
MEM_ACCESS_CYCLES=180

# PRNG Device (on-demand line generation)
PRNG_ACCESS_CYCLES=2
# Cycles penalty to generate one cache line
PRNG_GEN_COST_PER_LINE=64

# PRNG FIFO Device (MMIO streaming)
PRNG_FIFO_CAPACITY=64
PRNG_FIFO_GEN_COST=10
```

---

## 5. Execution Constraints

To run a simulation successfully, the input parameters must satisfy the following alignment rules:

1. **Divisibility:** The tile dimensions (`m`, `n`, `k`) must divide the configured matrix dimensions exactly:
   * $\text{A\_HEIGHT\_DIM} \pmod m == 0$
   * $\text{B\_WIDTH\_DIM} \pmod n == 0$
   * $\text{A\_WIDTH\_DIM} \pmod k == 0$
2. **Register Tiling Alignment:** When register tiling is configured, register dimensions must divide the cache tile dimensions:
   * $m \pmod{\text{REG\_M}} == 0$
   * $n \pmod{\text{REG\_N}} == 0$
   * $k \pmod{\text{REG\_K}} == 0$
3. **PRNG Cache Line Alignment:** In `--Bgenerated` or `--Bfifo` modes:
   * The byte size of a tile row of B must be a multiple of the cache line size:
     $$(n \times \text{B\_PRECISION\_BYTES}) \pmod{\text{L1\_LINE\_SIZE\_BYTES}} == 0$$
     For example, with `B_PRECISION_BYTES=2` and `L1_LINE_SIZE_BYTES=64`, the tile width `n` must be a multiple of 32.
   * The PRNG window must be line-aligned: A's byte size and B's byte size must be multiples of `L1_LINE_SIZE_BYTES`.

---

## 6. Execution Examples

### Example A: Normal Matrix Multiplication
Loads Matrix B from standard memory (DRAM).
```bash
./asymm --config default.config 20 20 20
```

### Example B: PRNG On-Demand Line Generation
Generates B's cache lines dynamically to bypass memory delays.
```bash
./asymm --config default.config --Bgenerated 32 32 32
```

### Example C: PRNG FIFO Streaming with B-Stationary Loop Policy
Uses the MMIO FIFO device to stream B elements and registers a trace file.
```bash
./asymm --config default.config --Bfifo --Bstationary --trace_file run.trace --trace_level 2 32 32 32
```

### Example D: Scratchpad Memory Mode
Simulates using a scratchpad memory instead of L1/L2 caches for tile storage.
```bash
./asymm --config default.config --scratchpad 16 64 16
```

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
