# Empirical Cache Line Size Tiling Sweeps

This directory contains the results of empirical tile sweeps for a **$96 \times 96 \times 96$ matrix** under **16 KB L1** and **64 KB L2** caches, sweeping cache line sizes $L \in \{16, 32, 64, 128\}$ bytes and tile dimensions $T_M, T_N, T_K \in \{8, 12, 16, 24, 32, 48\}$.

> [!NOTE]
> **Hardware Parameters:**
> * **Matrix Size:** $96 \times 96 \times 96$.
> * **L1 Cache:** 16 KB capacity, 8-way associativity, 4-cycle access, LRU replacement, Write-Back policy.
> * **L2 Cache:** 64 KB capacity, 8-way associativity, 14-cycle access, LRU replacement, Write-Back policy.
> * **DRAM Latency:** 180 cycles.
> * **Register Tile:** $4 \times 4 \times 4$ ($R_M \times R_N \times R_K$), 8-cycle compute (`tmulac`).

## 1. Summary of Optimal Tile Shapes by Cache Line Size

| Cache Line Size | Precision Config | Optimal Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 16B | Symmetric Double | 32x32x32 | 1.000 | 24.0 KB | 0.898 | 0.676 | 656.0 KB | 8,145,952 |
| 16B | Asymmetric | 12x48x48 | 4.000 | 13.5 KB | 0.952 | 0.711 | 260.0 KB | 5,355,272 |
| 16B | Symmetric Single | 16x16x48 | 1.000 | 7.0 KB | 0.963 | 0.731 | 156.6 KB | 4,390,160 |
| 32B | Symmetric Double | 32x32x32 | 1.000 | 24.0 KB | 0.949 | 0.676 | 656.0 KB | 5,252,624 |
| 32B | Asymmetric | 16x48x48 | 3.000 | 16.5 KB | 0.974 | 0.715 | 269.8 KB | 3,861,652 |
| 32B | Symmetric Single | 48x48x48 | 1.000 | 27.0 KB | 0.979 | 0.652 | 223.6 KB | 3,332,448 |
| 64B | Symmetric Double | 32x32x32 | 1.000 | 24.0 KB | 0.974 | 0.677 | 656.0 KB | 3,806,800 |
| 64B | Asymmetric | 32x48x48 | 1.500 | 28.5 KB | 0.983 | 0.720 | 327.8 KB | 3,107,514 |
| 64B | Symmetric Single | 48x48x48 | 1.000 | 27.0 KB | 0.990 | 0.636 | 223.4 KB | 2,767,836 |
| 128B | Symmetric Double | 32x32x32 | 1.000 | 24.0 KB | 0.987 | 0.679 | 656.0 KB | 3,083,888 |
| 128B | Asymmetric | 24x48x48 | 2.000 | 22.5 KB | 0.990 | 0.783 | 281.8 KB | 2,693,212 |
| 128B | Symmetric Single | 48x48x48 | 1.000 | 27.0 KB | 0.992 | 0.766 | 223.0 KB | 2,515,840 |

---

## 2. Details for Line Size = 16B

### Symmetric Double (16B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x32x32 | 1.000 | 24.0 KB | 0.898 | 0.676 | 656.0 KB | 8,145,952 |
| 2 | 48x16x32 | 0.333 | 22.0 KB | 0.881 | 0.739 | 610.2 KB | 8,167,328 |
| 3 | 32x24x32 | 0.750 | 20.0 KB | 0.891 | 0.696 | 656.0 KB | 8,249,400 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x48x48 | 6.000 | 24.0 KB | 0.737 | 0.628 | 1928.2 KB | 17,218,584 |
| 215 | 8x48x8 | 6.000 | 6.5 KB | 0.914 | 0.084 | 2041.3 KB | 17,223,744 |
| 216 | 8x8x8 | 1.000 | 1.5 KB | 0.910 | 0.240 | 1952.0 KB | 17,246,864 |

### Asymmetric (16B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 12x48x48 | 4.000 | 13.5 KB | 0.952 | 0.711 | 260.0 KB | 5,355,272 |
| 2 | 12x32x48 | 2.667 | 10.5 KB | 0.954 | 0.689 | 260.0 KB | 5,359,976 |
| 3 | 16x48x48 | 3.000 | 16.5 KB | 0.949 | 0.715 | 269.8 KB | 5,363,504 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x32x8 | 0.667 | 15.5 KB | 0.928 | 0.801 | 415.3 KB | 7,414,888 |
| 215 | 48x8x8 | 0.167 | 6.1 KB | 0.885 | 0.901 | 296.0 KB | 7,631,816 |
| 216 | 48x48x8 | 1.000 | 21.8 KB | 0.905 | 0.859 | 430.6 KB | 7,941,788 |

### Symmetric Single (16B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x16x48 | 1.000 | 7.0 KB | 0.963 | 0.731 | 156.6 KB | 4,390,160 |
| 2 | 16x32x48 | 2.000 | 11.0 KB | 0.959 | 0.721 | 176.3 KB | 4,410,620 |
| 3 | 16x16x32 | 1.000 | 5.0 KB | 0.968 | 0.677 | 159.5 KB | 4,417,796 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x8x8 | 0.167 | 3.2 KB | 0.957 | 0.749 | 224.0 KB | 5,713,152 |
| 215 | 32x12x8 | 0.375 | 2.9 KB | 0.971 | 0.566 | 271.3 KB | 5,731,308 |
| 216 | 32x8x8 | 0.250 | 2.2 KB | 0.971 | 0.572 | 274.5 KB | 5,904,670 |

---

## 2. Details for Line Size = 32B

### Symmetric Double (32B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x32x32 | 1.000 | 24.0 KB | 0.949 | 0.676 | 656.0 KB | 5,252,624 |
| 2 | 48x16x32 | 0.333 | 22.0 KB | 0.940 | 0.739 | 610.2 KB | 5,300,176 |
| 3 | 32x24x32 | 0.750 | 20.0 KB | 0.946 | 0.696 | 656.0 KB | 5,322,780 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x48x8 | 6.000 | 6.5 KB | 0.957 | 0.084 | 2041.3 KB | 10,270,752 |
| 215 | 8x12x8 | 1.500 | 2.0 KB | 0.954 | 0.233 | 1952.0 KB | 10,313,632 |
| 216 | 8x8x8 | 1.000 | 1.5 KB | 0.955 | 0.240 | 1952.0 KB | 10,466,632 |

### Asymmetric (32B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x48x48 | 3.000 | 16.5 KB | 0.974 | 0.715 | 269.8 KB | 3,861,652 |
| 2 | 12x48x48 | 4.000 | 13.5 KB | 0.976 | 0.712 | 260.0 KB | 3,894,876 |
| 3 | 16x32x48 | 2.000 | 13.0 KB | 0.975 | 0.714 | 268.9 KB | 3,896,420 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 24x8x8 | 0.333 | 3.1 KB | 0.958 | 0.830 | 326.4 KB | 5,330,532 |
| 215 | 48x48x8 | 1.000 | 21.8 KB | 0.953 | 0.859 | 430.6 KB | 5,445,544 |
| 216 | 48x8x8 | 0.167 | 6.1 KB | 0.941 | 0.904 | 296.0 KB | 5,498,860 |

### Symmetric Single (32B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x48x48 | 1.000 | 27.0 KB | 0.979 | 0.652 | 223.6 KB | 3,332,448 |
| 2 | 48x32x48 | 0.667 | 21.0 KB | 0.978 | 0.668 | 224.0 KB | 3,381,638 |
| 3 | 16x32x48 | 2.000 | 11.0 KB | 0.979 | 0.721 | 176.7 KB | 3,405,412 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x12x8 | 1.500 | 1.0 KB | 0.979 | 0.823 | 152.0 KB | 4,551,852 |
| 215 | 32x8x8 | 0.250 | 2.2 KB | 0.986 | 0.572 | 274.5 KB | 4,629,710 |
| 216 | 8x8x8 | 1.000 | 0.8 KB | 0.982 | 0.802 | 152.0 KB | 4,669,560 |

---

## 2. Details for Line Size = 64B

### Symmetric Double (64B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x32x32 | 1.000 | 24.0 KB | 0.974 | 0.677 | 656.0 KB | 3,806,800 |
| 2 | 32x24x32 | 0.750 | 20.0 KB | 0.973 | 0.697 | 656.0 KB | 3,860,604 |
| 3 | 48x16x32 | 0.333 | 22.0 KB | 0.970 | 0.739 | 610.5 KB | 3,866,960 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x16x8 | 2.000 | 2.5 KB | 0.976 | 0.227 | 1952.0 KB | 6,850,376 |
| 215 | 8x12x8 | 1.500 | 2.0 KB | 0.970 | 0.393 | 1952.0 KB | 7,003,904 |
| 216 | 8x8x8 | 1.000 | 1.5 KB | 0.977 | 0.241 | 1952.0 KB | 7,076,936 |

### Asymmetric (64B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x48x48 | 1.500 | 28.5 KB | 0.983 | 0.720 | 327.8 KB | 3,107,514 |
| 2 | 16x48x48 | 3.000 | 16.5 KB | 0.985 | 0.748 | 266.8 KB | 3,122,368 |
| 3 | 24x48x48 | 2.000 | 22.5 KB | 0.984 | 0.727 | 318.0 KB | 3,130,992 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x12x8 | 0.250 | 7.7 KB | 0.970 | 0.889 | 369.6 KB | 4,387,352 |
| 215 | 16x8x8 | 0.500 | 2.1 KB | 0.975 | 0.884 | 263.0 KB | 4,394,656 |
| 216 | 48x8x8 | 0.167 | 6.1 KB | 0.969 | 0.906 | 302.1 KB | 4,438,724 |

### Symmetric Single (64B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x48x48 | 1.000 | 27.0 KB | 0.990 | 0.636 | 223.4 KB | 2,767,836 |
| 2 | 48x32x48 | 0.667 | 21.0 KB | 0.989 | 0.668 | 224.0 KB | 2,815,360 |
| 3 | 48x48x32 | 1.000 | 21.0 KB | 0.991 | 0.639 | 226.1 KB | 2,846,952 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x12x8 | 1.500 | 1.0 KB | 0.987 | 0.848 | 152.0 KB | 4,069,344 |
| 215 | 12x8x8 | 0.667 | 1.0 KB | 0.988 | 0.838 | 157.9 KB | 4,071,668 |
| 216 | 8x8x8 | 1.000 | 0.8 KB | 0.988 | 0.847 | 152.0 KB | 4,214,868 |

---

## 2. Details for Line Size = 128B

### Symmetric Double (128B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x32x32 | 1.000 | 24.0 KB | 0.987 | 0.679 | 656.0 KB | 3,083,888 |
| 2 | 32x32x48 | 1.000 | 32.0 KB | 0.976 | 0.790 | 686.0 KB | 3,110,854 |
| 3 | 48x32x32 | 0.667 | 32.0 KB | 0.988 | 0.622 | 749.0 KB | 3,114,704 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x8x12 | 1.000 | 2.0 KB | 0.978 | 0.573 | 1952.0 KB | 5,202,592 |
| 215 | 8x12x8 | 1.500 | 2.0 KB | 0.979 | 0.572 | 1952.0 KB | 5,349,376 |
| 216 | 8x8x8 | 1.000 | 1.5 KB | 0.979 | 0.575 | 1952.0 KB | 5,498,344 |

### Asymmetric (128B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 24x48x48 | 2.000 | 22.5 KB | 0.990 | 0.783 | 281.8 KB | 2,693,212 |
| 2 | 32x48x48 | 1.500 | 28.5 KB | 0.990 | 0.726 | 361.5 KB | 2,714,060 |
| 3 | 32x32x48 | 1.000 | 23.0 KB | 0.989 | 0.774 | 329.5 KB | 2,738,202 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x12x8 | 0.250 | 7.7 KB | 0.969 | 0.910 | 676.8 KB | 4,247,052 |
| 215 | 8x8x8 | 1.000 | 1.1 KB | 0.978 | 0.937 | 260.0 KB | 4,278,320 |
| 216 | 48x8x8 | 0.167 | 6.1 KB | 0.967 | 0.936 | 503.8 KB | 4,308,444 |

### Symmetric Single (128B)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x48x48 | 1.000 | 27.0 KB | 0.992 | 0.766 | 223.0 KB | 2,515,840 |
| 2 | 48x32x48 | 0.667 | 21.0 KB | 0.993 | 0.729 | 224.0 KB | 2,543,312 |
| 3 | 32x48x48 | 1.500 | 21.0 KB | 0.992 | 0.765 | 244.0 KB | 2,572,750 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 12x8x8 | 0.667 | 1.0 KB | 0.990 | 0.902 | 155.0 KB | 3,851,008 |
| 215 | 8x12x8 | 1.500 | 1.0 KB | 0.988 | 0.917 | 152.0 KB | 3,870,342 |
| 216 | 8x8x8 | 1.000 | 0.8 KB | 0.992 | 0.889 | 152.0 KB | 3,979,962 |

---

## 3. Aspect Ratio Sensitivity vs. Cache Line Size
The plot below details how the cache line size affects both execution cycles and the shape aspect ratio trend.

![Line Size Aspect Ratio Sweeps](line_size_empirical.png)
