# C-Stationary vs. B-Stationary Cache Performance Analysis

This document analyzes the architectural tradeoffs between **C-Stationary** (output stationary) and **B-Stationary** (weight stationary) loop orderings in the asymmetric tiled matrix multiplication cache simulator.

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

## Experimental Setup
* **Matrix Size**: $A$ ($12 \times 12$ elements, 8-byte precision) | $B$ ($12 \times 24$ elements, 2-byte precision)
* **Tile Size**: $4 \times 8 \times 4$
* **Tile Count**: $M_{\text{tiles}} = 3$ | $N_{\text{tiles}} = 3$ | $K_{\text{tiles}} = 3$
* **Cache Setup**: 8 KB L1 (LRU) | 32 KB L2 (LRU)
* **Memory Policy**: Write-through, no-allocate

---

## Simulation Results

### 1. Normal Mode (Memory-backed B Matrix)
| Metric | C-Stationary | B-Stationary | Comparison |
| :--- | :---: | :---: | :---: |
| **L1 Hit Rate** | 34.6% | 44.1% | +9.5% for B-Stationary |
| **L2 Hit Rate** | 35.3% | 38.7% | +3.4% for B-Stationary |
| **L1 Tag Lookups** | 1,872 | 2,448 | +30.8% for B-Stationary |
| **Total Cycles** | **220,248** | **445,032** | **2.02x slower** for B-Stationary |

### 2. PRNG Mode (On-the-Fly B Generation)
| Metric | C-Stationary | B-Stationary | Comparison |
| :--- | :---: | :---: | :---: |
| **L1 Hit Rate** | 34.6% | 44.1% | +9.5% for B-Stationary |
| **L2 Hit Rate** | 57.1% | 40.0% | -17.1% for B-Stationary |
| **PRNG Generations** | 28 | 36 | +28.5% for B-Stationary |
| **PRNG Regenerations** | **188** | **36** | **5.2x fewer** for B-Stationary |
| **Total Cycles** | **166,464** | **435,744** | **2.62x slower** for B-Stationary |

---

## Analysis & Architectural Conclusions

### Why B-Stationary succeeded in its goal:
In the standard C-stationary mode under PRNG generation, B elements are evicted from L1 and must be re-generated constantly because B tiles are loaded repeatedly across M-tiles. This causes a massive **188 regenerations** on the PRNG device.
Under B-stationary mode, since a B tile is kept stationary in the register file, we only load it once. The PRNG regenerations drop down to **36** (a 5.2x reduction), proving the weight-stationary approach holds B in the register file exactly as intended.

### Why B-Stationary performed worse overall:
Despite the reduction in PRNG regenerations and better L1 hit rates, B-stationary takes **more than double the clock cycles**. This is due to the interaction of two factors:
1. **Partial Sum Traffic**: C-stationary reads and writes each tile of $C$ exactly once ($2 \times M_{\text{tiles}} \times N_{\text{tiles}} = 18$ tile accesses). B-stationary must read and write $C$ at *every* outer $K$-step to accumulate the partial sums, resulting in $2 \times M_{\text{tiles}} \times N_{\text{tiles}} \times K_{\text{tiles}} = 54$ tile accesses (a 3x increase in $C$ memory traffic).
2. **Write-Through Penalty**: Because matrix $C$ is stored with 8-byte precision and the cache uses a write-through policy, every store of $C$ must traverse to L2 and Main Memory. The latency of these high-frequency writes completely dominates the execution time, eclipsing any benefits from PRNG generation savings.

### Design Recommendation:
For architectures with write-through/no-allocate policies and high-precision output matrices, **Output-Stationary (C-Stationary)** loop nesting is superior due to its minimization of write-traffic. B-Stationary would only become viable if:
* The cache used a **write-back** policy (absorbing partial sum updates locally in L1/L2).
* Matrix $C$ had lower precision than Matrix $B$.
* PRNG regeneration cost was extremely high (e.g. $> 500$ cycles per line).
