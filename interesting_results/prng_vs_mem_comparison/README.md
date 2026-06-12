# PRNG vs. Non-PRNG (Memory-Mapped B) Comparison Report

This report compares execution cycles and L1 cache hit rates between the **PRNG Mode** (where Matrix B elements are generated on-demand at a cost of 64 cycles per cache line) and the **Non-PRNG Mode** (where Matrix B elements are fetched directly from main memory at a cost of 180 cycles per access).

The experiment is conducted under **C-Stationary** loop ordering with a Write-Back cache policy.

---

## 1. Experimental Results

### A. Tile Shape: Standard ($16 \times 16 \times 16$)
| B Precision | PRNG Cycles | Non-PRNG Cycles | PRNG Speedup | L1 Cache Hit Rate |
| :---: | :---: | :---: | :---: | :---: |
| **1 Byte (8-bit)**  | 6.841M | 7.781M  | **1.14x** | 0.375 |
| **2 Bytes (16-bit)** | 7.300M | 9.223M  | **1.26x** | 0.321 |
| **4 Bytes (32-bit)** | 8.219M | 11.963M | **1.46x** | 0.214 |
| **8 Bytes (64-bit)** | 10.028M| 21.294M | **2.12x** | 0.000 |

### B. Tile Shape: Best Sweep ($16 \times 48 \times 16$)
*This shape yielded the absolute lowest cycle counts for 1B and 2B in the single-dimension sweeps.*
| B Precision | PRNG Cycles | Non-PRNG Cycles | PRNG Speedup | L1 Cache Hit Rate |
| :---: | :---: | :---: | :---: | :---: |
| **1 Byte (8-bit)**  | 6.066M | 7.179M  | **1.18x** | 0.525 |
| **2 Bytes (16-bit)** | 6.523M | 9.662M  | **1.48x** | 0.450 |
| **4 Bytes (32-bit)** | 7.435M | 14.288M | **1.92x** | 0.300 |
| **8 Bytes (64-bit)** | 9.260M | 19.987M | **2.16x** | 0.000 |

### C. Tile Shape: Combined ($24 \times 48 \times 16$)
*Combining the best M and N sweep parameters.*
| B Precision | PRNG Cycles | Non-PRNG Cycles | PRNG Speedup | L1 Cache Hit Rate |
| :---: | :---: | :---: | :---: | :---: |
| **1 Byte (8-bit)**  | 7.749M | 9.318M  | **1.20x** | 0.438 |
| **2 Bytes (16-bit)** | 8.326M | 10.675M | **1.28x** | 0.375 |
| **4 Bytes (32-bit)** | 8.352M | 12.642M | **1.51x** | 0.250 |
| **8 Bytes (64-bit)** | 9.569M | 16.248M | **1.70x** | 0.000 |

---

## 2. Analysis & Key Insights

### 1. Indistinguishable Cache Tag Traversal
* The **L1 Cache Hit Rates are 100% identical** between PRNG and Non-PRNG modes for every precision and tile shape.
* **Why?** The sequence of memory address requests sent to the cache tag lookups is identical. The only difference is that a cache miss on Matrix B in Non-PRNG mode accesses Main Memory (180 cycles latency), whereas in PRNG mode, it accesses the PRNG device (which generates cache lines on-demand at 64 cycles/line, and subsequent hits cost only 2 cycles).

### 2. PRNG Speedup Scales with Precision
* As B precision increases, the PRNG speedup grows significantly:
  * At **1 Byte**, B is compact, so spatial reuse in cache lines is high. This keeps the number of B cache misses relatively low, yielding a **1.14x to 1.20x** speedup.
  * At **8 Bytes**, B elements are double-precision, which means zero spatial reuse (only 1 element fits per cache line). This triggers a massive number of cache misses on B. In Non-PRNG mode, each miss costs 180 cycles. In PRNG mode, we only pay the 64-cycle line generation cost once, and subsequent hits cost 2 cycles. This results in a massive **1.70x to 2.16x** speedup (saving up to 11.2 million cycles!).

### 3. Tiling footprint bottleneck in Combined (24x48x16)
* Even though $M=24$ and $N=48$ were the best individual sweep coordinates, combining them to $24 \times 48 \times 16$ is actually slower than the $16 \times 48 \times 16$ shape (e.g. 7.749M vs 6.066M cycles for 1B PRNG).
* **Why?** The active working footprint of $24 \times 48 \times 16$ is $12.75$ KB, which exceeds the L1 Cache capacity (8 KB), causing capacity thrashing of the double-precision output matrix C (9 KB tile footprint). The $16 \times 48 \times 16$ shape has a footprint of $8.75$ KB, fitting much better in the L1 Cache. Thus, **$16 \times 48 \times 16$** is the overall optimal tile shape.
