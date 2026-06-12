# C-Stationary vs. B-Stationary Cache Performance Analysis

This document analyzes the architectural tradeoffs between **C-Stationary** (output stationary) and **B-Stationary** (weight stationary) loop orderings in the asymmetric tiled matrix multiplication cache simulator, under both **Write-Through** and **Write-Back** policies.

---

## The Two Approaches

### 1. C-Stationary (Default)
In this approach, the innermost loop runs along the **K-direction** (reduction tiles). A tile of the output matrix $C$ is loaded into register `%rc` once, accumulated into locally via multiple $A \times B$ products, and stored back to memory only at the end.

* **Loop Order**: $M \rightarrow N \rightarrow K$
* **Loop Nesting**:
  ```cpp
  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      load(C[ti, tj]);
      for (uint tk = 0; tk < K_tiles; ++tk) {
        load(A[ti, tk]);
        load(B[tk, tj]);
        tmulac(A, B, C);
      }
      store(C[ti, tj]);
    }
  }
  ```

### 2. B-Stationary (Weight Stationary)
In this approach, the innermost loop runs along the **M-direction** (matrix A height tiles). A tile of the B matrix is loaded into register `%rb` once and kept stationary. Tiles of $A$ are loaded, and the corresponding tiles of $C$ are loaded, accumulated into, and immediately stored back to memory.

* **Loop Order**: $K \rightarrow N \rightarrow M$
* **Loop Nesting**:
  ```cpp
  for (uint tk = 0; tk < K_tiles; ++tk) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      load(B[tk, tj]);
      for (uint ti = 0; ti < M_tiles; ++ti) {
        load(A[ti, tk]);
        load(C[ti, tj]);  // Load current partial sum
        tmulac(A, B, C);
        store(C[ti, tj]); // Store updated partial sum
      }
    }
  }
  ```

---

## Simulation Results ($16 \times 16$ Matrix, $4 \times 4 \times 4$ Tiles, Large Cache)
To isolate the effects of the write policies without capacity issues, we evaluated both loop orderings using:
* **Matrix Size**: $A$ ($16 \times 16$, 8B precision) | $B$ ($16 \times 16$, 2B precision)
* **Tile Size**: $4 \times 4 \times 4$
* **Cache Setup**: 8 KB L1 (LRU) | 32 KB L2 (LRU)

### 1. Memory-backed B Matrix (Normal Mode)
| Policy | Loop Ordering | Total L1 Lookups | Total Cycles | Comparison |
| :--- | :--- | :---: | :---: | :---: |
| **Write-Through** | C-Stationary | 1,152 | **172,480** | Baseline |
| **Write-Through** | B-Stationary | 1,440 | **325,312** | **1.89x slower** |
| **Write-Back** | C-Stationary | 1,856 | **122,560** | **1.41x speedup** |
| **Write-Back** | B-Stationary | 2,176 | **125,632** | **2.59x speedup** (Almost matches C-Stationary) |

### 2. On-the-Fly B Generation (PRNG Mode)
| Policy | Loop Ordering | PRNG Regenerations | Total Cycles | Comparison |
| :--- | :--- | :---: | :---: | :---: |
| **Write-Through** | C-Stationary | 64 | **164,224** | Baseline |
| **Write-Through** | B-Stationary | 16 | **317,056** | **1.93x slower** (Despite 4x fewer regenerations) |
| **Write-Back** | C-Stationary | 64 | **114,304** | **1.44x speedup** |
| **Write-Back** | B-Stationary | 16 | **117,376** | **2.70x speedup** (Almost matches C-Stationary) |

---

## Analysis & Architectural Conclusions

### 1. The Write-Through Bottleneck in B-Stationary
Under a **Write-Through** policy, B-Stationary performs poorly because it writes Matrix $C$'s partial sums to memory at every innermost loop step (64 writes vs. 1 write per tile in C-Stationary). Since $C$ has high precision (8 bytes) and writes always propagate to main memory, the write latency dominates the execution time, making B-Stationary nearly **2x slower** than C-Stationary.

### 2. The Write-Back Solution
When we enable a **Write-Back + Write-Allocate** policy:
* Writes to $C$ are cached in L1 and marked as dirty. They do **not** generate write traffic to L2 or Main Memory until the line is evicted.
* Since the tile footprint fits in the 8 KB L1 cache, L1 absorbs all write traffic.
* This resolves the write bottleneck of B-Stationary, causing its cycle count to drop from **317,056 to 117,376** (a **2.7x performance speedup**).

### 3. Why B-Stationary is still slightly slower under Write-Back
Even when all accesses are L1 cache hits, B-Stationary requires **272 instructions** to process the tiles (due to loading/storing $C$ inside the innermost loops) whereas C-Stationary only requires **194 instructions** (since $C$ stays stationary in a register). The extra 78 instructions add a small overhead of ~3,000 clock cycles.

### Summary
* Use **C-Stationary** if the hardware has a **Write-Through** cache to minimize write traffic.
* If the hardware supports a **Write-Back** cache, **B-Stationary** becomes highly competitive and is the superior choice if B-matrix generations are exceptionally expensive.
