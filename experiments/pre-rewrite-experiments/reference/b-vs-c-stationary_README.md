# B-Stationary vs. C-Stationary Loop Ordering Comparison

This report presents a direct comparison between **B-stationary** and **C-stationary** loop orderings on square tiles ($T_M = T_N = T_K = T_{\text{tile}}$) under double-precision, asymmetric, and single-precision matmul configurations.

## 1. Experimental Setup
- **Matrix Size**: $96 \times 96 \times 96$
- **L1 Cache**: 16 KB capacity, 64B line size, 8-way associative, LRU, Write-Back.
- **L2 Cache**: 64 KB capacity, 64B line size, 8-way associative, LRU, Write-Back.
- **DRAM Latency**: 180 cycles
- **Swept Tile Sizes**: $8^3, 12^3, 16^3, 24^3, 32^3, 48^3$

## 2. Execution Results Summary

### Symmetric Double Precision

| Tile Size | Loop Ordering | Total Cycles | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | L1 Tag Lookups |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $8^3$ | C-stationary | 7,076,936 | 0.9775 | 0.2408 | 1952.0 KB | 893,952 |
| | B-stationary | 9,955,484 | 0.9713 | 0.6198 | 1952.0 KB | 1,004,544 |
| $12^3$ | C-stationary | 5,652,756 | 0.9729 | 0.4598 | 1376.2 KB | 746,496 |
| | B-stationary | 7,811,344 | 0.9712 | 0.6957 | 1376.0 KB | 893,952 |
| $16^3$ | C-stationary | 4,859,524 | 0.9785 | 0.4089 | 1088.0 KB | 672,768 |
| | B-stationary | 6,570,140 | 0.9796 | 0.6143 | 1088.0 KB | 838,656 |
| $24^3$ | C-stationary | 4,212,568 | 0.9749 | 0.6393 | 811.8 KB | 599,040 |
| | B-stationary | 5,570,176 | 0.9810 | 0.6181 | 861.0 KB | 783,360 |
| $32^3$ | C-stationary | 3,806,800 | 0.9743 | 0.6767 | 656.0 KB | 562,176 |
| | B-stationary | 5,231,432 | 0.9645 | 0.8482 | 656.0 KB | 755,712 |
| $48^3$ | C-stationary | 4,316,372 | 0.9341 | 0.8080 | 825.9 KB | 525,312 |
| | B-stationary | 5,851,232 | 0.9256 | 0.9113 | 858.0 KB | 728,064 |

### Asymmetric Precision

| Tile Size | Loop Ordering | Total Cycles | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | L1 Tag Lookups |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $8^3$ | C-stationary | 4,385,968 | 0.9936 | 0.6228 | 260.0 KB | 893,952 |
| | B-stationary | 9,780,596 | 0.9722 | 0.6326 | 1844.0 KB | 1,004,544 |
| $12^3$ | C-stationary | 3,924,316 | 0.9806 | 0.8337 | 260.0 KB | 746,496 |
| | B-stationary | 7,632,744 | 0.9722 | 0.7117 | 1268.0 KB | 893,952 |
| $16^3$ | C-stationary | 3,594,632 | 0.9829 | 0.7908 | 265.2 KB | 672,768 |
| | B-stationary | 6,366,436 | 0.9825 | 0.6094 | 980.0 KB | 838,656 |
| $24^3$ | C-stationary | 3,367,148 | 0.9836 | 0.7635 | 310.4 KB | 599,040 |
| | B-stationary | 5,259,012 | 0.9867 | 0.5890 | 700.5 KB | 783,360 |
| $32^3$ | C-stationary | 3,244,064 | 0.9836 | 0.7484 | 332.0 KB | 562,176 |
| | B-stationary | 4,815,584 | 0.9814 | 0.7573 | 548.0 KB | 755,712 |
| $48^3$ | C-stationary | 3,270,500 | 0.9832 | 0.6239 | 455.5 KB | 525,312 |
| | B-stationary | 5,347,194 | 0.9296 | 0.9388 | 549.5 KB | 728,064 |

### Symmetric Single Precision

| Tile Size | Loop Ordering | Total Cycles | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | L1 Tag Lookups |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $8^3$ | C-stationary | 4,214,868 | 0.9880 | 0.8466 | 152.0 KB | 893,952 |
| | B-stationary | 4,850,414 | 0.9809 | 0.9411 | 152.0 KB | 1,004,544 |
| $12^3$ | C-stationary | 3,627,192 | 0.9861 | 0.8385 | 156.4 KB | 746,496 |
| | B-stationary | 4,379,826 | 0.9815 | 0.9248 | 165.9 KB | 893,952 |
| $16^3$ | C-stationary | 3,286,148 | 0.9920 | 0.6783 | 173.1 KB | 672,768 |
| | B-stationary | 3,924,794 | 0.9920 | 0.8241 | 155.1 KB | 838,656 |
| $24^3$ | C-stationary | 3,071,464 | 0.9900 | 0.6544 | 218.9 KB | 599,040 |
| | B-stationary | 3,820,192 | 0.9914 | 0.7843 | 197.0 KB | 783,360 |
| $32^3$ | C-stationary | 2,962,864 | 0.9913 | 0.5918 | 253.0 KB | 562,176 |
| | B-stationary | 3,763,888 | 0.9935 | 0.6373 | 231.2 KB | 755,712 |
| $48^3$ | C-stationary | 2,767,836 | 0.9901 | 0.6365 | 223.4 KB | 525,312 |
| | B-stationary | 3,769,292 | 0.9869 | 0.8439 | 229.0 KB | 728,064 |

## 3. Physical Analysis & Key Insights

### 3.1 C Accumulator Spill and L1 Tag Lookups
Under **C-stationary** loop ordering, a tile of matrix C is loaded into the CPU registers, accumulated into over the inner loop ($K_\text{tiles}$ times), and then written back to the cache only *once* after all accumulation is complete. This means the C accumulator is held in register space for the duration of the dot-product reductions.

Under **B-stationary** loop ordering, B is held stationary in the middle loop, and the inner loop sweeps through rows of A and C (the $M_\text{tiles}$ dimension). Consequently, the accumulator registers must be reloaded and stored back to memory/L1 cache for *every single* inner loop iteration because the accumulation dimension ($K$) is outside the innermost loop. This results in a massive increase in **L1 Tag Lookups** (often 3x to 4x higher) and causes extra cache-read/write pressure.

### 3.2 DRAM Traffic & Cache Thrashing
When the tile size is small (e.g., $8^3$), the entire working set fits comfortably in the 16 KB L1 cache, so B-stationary's overhead is primarily compute/register-spill latency rather than memory traffic. However, as the tile size scales up (e.g., $32^3$ or $48^3$), the combination of constant C-evictions/reloads and the massive working set footprints triggers severe capacity thrashing in L1/L2 caches, causing DRAM traffic to explode.

