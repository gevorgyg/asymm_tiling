# Simulator Execution Guide

This guide provides instructions on how to build, configure, and run the asymmetric matrix multiplication simulator.

---

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
> The tiles must be square or rectangular. To run with square tiles (e.g., of size 20), specify `20 20 20`.

---

## 3. Command Line Options

| Option / Flag | Description |
| :--- | :--- |
| **`--config <file>`** | Path to the hardware and matrix configuration file. If omitted, defaults to `default.config` in the current working directory. If the file does not exist at the specified path, the simulator will automatically create a default configuration file there. |
| **`--Bgenerated`** | Simulates generating B elements on-demand at cache-line granularity using a PRNG device. Bypasses normal DRAM loads. |
| **`--Bfifo`** | Simulates streaming B elements on-demand through the cycle-accurate **PRNG FIFO** device using control/data MMIO registers. |
| **`--Bstationary`** | Force B-stationary loop tiling (keeps a B tile in the register file while scanning through A and C tiles). If omitted, C-stationary loop order is used. |
| **`--trace_file <file>`** | Saves the step-by-step simulator execution trace into the specified file. |
| **`--trace_level <0\|1\|2>`** | Verbosity of the trace file (default is 2):<br>• **`0` (instructions):** Cycle count per instruction.<br>• **`1` (accesses):** Adds memory read/write details.<br>• **`2` (actions):** Adds individual device actions (e.g., L1 hit/miss, PRNG generation). |
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
PRNG_GEN_COST_PER_LINE=64

# PRNG FIFO Device (MMIO streaming)
PRNG_FIFO_CAPACITY=64
PRNG_FIFO_GEN_COST=10
```

---

## 5. Execution Constraints

To run a simulation successfully, the input parameters must satisfy the following alignment rules:

1. **Divisibility:** The tile dimensions (`m`, `n`, `k`) must divide the configured matrix dimensions exactly:
   $$\text{A\_HEIGHT\_DIM} \pmod m == 0$$
   $$\text{B\_WIDTH\_DIM} \pmod n == 0$$
   $$\text{A\_WIDTH\_DIM} \pmod k == 0$$
2. **PRNG Cache Line Alignment:** In `--Bgenerated` or `--Bfifo` modes:
   * The byte size of a tile row of B must be a multiple of the cache line size:
     $$(n \times \text{B\_PRECISION\_BYTES}) \pmod{\text{L1\_LINE\_SIZE\_BYTES}} == 0$$
   * For example, with `B_PRECISION_BYTES=2` and `L1_LINE_SIZE_BYTES=64`, the tile width `n` must be a multiple of 32.

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
./asymm --config default.config --Bgenerated 20 20 20
```

### Example C: PRNG FIFO Streaming with B-Stationary Loop Policy
Uses the MMIO FIFO device to stream B elements and registers a trace file.
```bash
./asymm --config default.config --Bfifo --Bstationary --trace_file run.trace --trace_level 2 32 32 32
```
