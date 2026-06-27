# Empirical Cache Associativity Tiling Sweeps (16B Lines)

This directory contains the results of empirical tile sweeps for a **$96 \times 96 \times 96$ matrix** under a fixed **16B cache line size**, sweeping Cache Associativity $A \in \{1, 2, 4, 8, 16\}$-way and tile dimensions $T_M, T_N, T_K \in \{8, 12, 16, 24, 32, 48\}$.

> [!NOTE]
> **Hardware Parameters:**
> * **Matrix Size:** $96 \times 96 \times 96$.
> * **Cache Line Size:** 16B for both L1 and L2 caches.
> * **L1 Cache:** 16 KB capacity, swept associativity, 4-cycle access, LRU replacement, Write-Back policy.
> * **L2 Cache:** 64 KB capacity, swept associativity, 14-cycle access, LRU replacement, Write-Back policy.
> * **DRAM Latency:** 180 cycles.
> * **Register Tile:** $4 \times 4 \times 4$ ($R_M \times R_N \times R_K$), 8-cycle compute (`tmulac`).

## 1. Summary of Optimal Tile Shapes by Cache Associativity

| Associativity | Precision Config | Optimal Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1-way | Symmetric Double | 24x32x16 | 1.333 | 13.0 KB | 0.851 | 0.713 | 945.9 KB | 10,913,040 |
| 1-way | Asymmetric | 32x32x24 | 1.000 | 15.5 KB | 0.925 | 0.713 | 435.4 KB | 6,811,154 |
| 1-way | Symmetric Single | 16x48x32 | 3.000 | 11.0 KB | 0.939 | 0.751 | 251.8 KB | 5,253,740 |
| 2-way | Symmetric Double | 48x32x32 | 0.667 | 32.0 KB | 0.871 | 0.702 | 728.5 KB | 8,852,960 |
| 2-way | Asymmetric | 8x24x48 | 3.000 | 6.8 KB | 0.955 | 0.686 | 273.7 KB | 5,541,730 |
| 2-way | Symmetric Single | 48x32x48 | 0.667 | 21.0 KB | 0.950 | 0.708 | 218.5 KB | 4,541,506 |
| 4-way | Symmetric Double | 48x32x32 | 0.667 | 32.0 KB | 0.900 | 0.665 | 656.0 KB | 8,124,928 |
| 4-way | Asymmetric | 12x48x48 | 4.000 | 13.5 KB | 0.952 | 0.703 | 264.4 KB | 5,373,780 |
| 4-way | Symmetric Single | 16x32x48 | 2.000 | 11.0 KB | 0.958 | 0.729 | 171.8 KB | 4,374,128 |
| 8-way | Symmetric Double | 32x32x32 | 1.000 | 24.0 KB | 0.898 | 0.676 | 656.0 KB | 8,145,952 |
| 8-way | Asymmetric | 12x48x48 | 4.000 | 13.5 KB | 0.952 | 0.711 | 260.0 KB | 5,355,272 |
| 8-way | Symmetric Single | 16x16x48 | 1.000 | 7.0 KB | 0.963 | 0.731 | 156.6 KB | 4,390,160 |
| 16-way | Symmetric Double | 48x16x32 | 0.333 | 22.0 KB | 0.881 | 0.777 | 512.0 KB | 7,601,408 |
| 16-way | Asymmetric | 16x48x48 | 3.000 | 16.5 KB | 0.948 | 0.728 | 260.0 KB | 5,327,792 |
| 16-way | Symmetric Single | 16x48x48 | 3.000 | 15.0 KB | 0.954 | 0.769 | 152.0 KB | 4,261,208 |

---

## 2. Details for Associativity = 1-way

### Symmetric Double (1-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 24x32x16 | 1.333 | 13.0 KB | 0.851 | 0.713 | 945.9 KB | 10,913,040 |
| 2 | 24x32x12 | 1.333 | 11.2 KB | 0.861 | 0.721 | 920.3 KB | 10,931,128 |
| 3 | 24x32x24 | 1.333 | 16.5 KB | 0.839 | 0.697 | 987.8 KB | 10,957,216 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x48x32 | 6.000 | 17.0 KB | 0.766 | 0.710 | 1406.1 KB | 14,426,300 |
| 215 | 8x48x8 | 6.000 | 6.5 KB | 0.840 | 0.715 | 1313.2 KB | 14,661,300 |
| 216 | 8x48x48 | 6.000 | 24.0 KB | 0.728 | 0.721 | 1482.0 KB | 14,939,920 |

### Asymmetric (1-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 32x32x24 | 1.000 | 15.5 KB | 0.925 | 0.713 | 435.4 KB | 6,811,154 |
| 2 | 32x32x32 | 1.000 | 18.0 KB | 0.920 | 0.705 | 451.6 KB | 6,824,106 |
| 3 | 32x32x16 | 1.000 | 13.0 KB | 0.932 | 0.720 | 420.3 KB | 6,877,834 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x8x12 | 0.167 | 7.7 KB | 0.883 | 0.802 | 572.0 KB | 9,170,862 |
| 215 | 48x12x8 | 0.250 | 7.7 KB | 0.910 | 0.755 | 607.4 KB | 9,360,746 |
| 216 | 48x8x8 | 0.167 | 6.1 KB | 0.894 | 0.804 | 568.7 KB | 9,470,524 |

### Symmetric Single (1-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x48x32 | 3.000 | 11.0 KB | 0.939 | 0.751 | 251.8 KB | 5,253,740 |
| 2 | 16x48x48 | 3.000 | 15.0 KB | 0.928 | 0.769 | 258.2 KB | 5,266,912 |
| 3 | 12x48x32 | 4.000 | 9.8 KB | 0.934 | 0.782 | 239.6 KB | 5,285,194 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x8x12 | 0.167 | 4.1 KB | 0.953 | 0.618 | 438.8 KB | 7,228,818 |
| 215 | 48x12x8 | 0.250 | 4.1 KB | 0.958 | 0.602 | 433.6 KB | 7,331,846 |
| 216 | 48x8x8 | 0.167 | 3.2 KB | 0.957 | 0.620 | 439.9 KB | 7,560,332 |

---

## 2. Details for Associativity = 2-way

### Symmetric Double (2-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x32x32 | 0.667 | 32.0 KB | 0.871 | 0.702 | 728.5 KB | 8,852,960 |
| 2 | 48x32x24 | 0.667 | 27.0 KB | 0.880 | 0.711 | 717.0 KB | 8,862,096 |
| 3 | 48x24x32 | 0.500 | 27.0 KB | 0.867 | 0.712 | 733.1 KB | 8,969,232 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x8x48 | 1.000 | 6.5 KB | 0.815 | 0.629 | 1559.2 KB | 15,012,292 |
| 215 | 8x8x8 | 1.000 | 1.5 KB | 0.903 | 0.442 | 1571.1 KB | 15,193,164 |
| 216 | 8x48x48 | 6.000 | 24.0 KB | 0.723 | 0.711 | 1563.7 KB | 15,329,536 |

### Asymmetric (2-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 8x24x48 | 3.000 | 6.8 KB | 0.955 | 0.686 | 273.7 KB | 5,541,730 |
| 2 | 8x32x48 | 4.000 | 8.0 KB | 0.952 | 0.701 | 276.0 KB | 5,545,558 |
| 3 | 8x48x48 | 6.000 | 10.5 KB | 0.949 | 0.717 | 279.0 KB | 5,560,188 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x12x8 | 0.250 | 7.7 KB | 0.909 | 0.840 | 395.3 KB | 7,710,570 |
| 215 | 48x48x8 | 1.000 | 21.8 KB | 0.910 | 0.858 | 412.8 KB | 7,832,372 |
| 216 | 48x8x8 | 0.167 | 6.1 KB | 0.892 | 0.870 | 373.9 KB | 7,954,538 |

### Symmetric Single (2-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x32x48 | 0.667 | 21.0 KB | 0.950 | 0.708 | 218.5 KB | 4,541,506 |
| 2 | 48x32x32 | 0.667 | 16.0 KB | 0.957 | 0.699 | 218.5 KB | 4,593,672 |
| 3 | 48x24x48 | 0.500 | 18.0 KB | 0.947 | 0.729 | 216.3 KB | 4,599,334 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x16x8 | 2.000 | 1.2 KB | 0.956 | 0.788 | 201.6 KB | 5,917,150 |
| 215 | 8x12x8 | 1.500 | 1.0 KB | 0.957 | 0.787 | 202.7 KB | 5,996,824 |
| 216 | 8x8x8 | 1.000 | 0.8 KB | 0.958 | 0.786 | 203.9 KB | 6,151,750 |

---

## 2. Details for Associativity = 4-way

### Symmetric Double (4-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x32x32 | 0.667 | 32.0 KB | 0.900 | 0.665 | 656.0 KB | 8,124,928 |
| 2 | 48x24x32 | 0.500 | 27.0 KB | 0.893 | 0.687 | 654.8 KB | 8,220,000 |
| 3 | 48x16x32 | 0.333 | 22.0 KB | 0.881 | 0.732 | 629.5 KB | 8,278,208 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x8x48 | 1.000 | 6.5 KB | 0.831 | 0.540 | 1787.9 KB | 16,191,552 |
| 215 | 8x8x8 | 1.000 | 1.5 KB | 0.910 | 0.304 | 1785.1 KB | 16,293,296 |
| 216 | 8x48x48 | 6.000 | 24.0 KB | 0.724 | 0.680 | 1737.1 KB | 16,320,880 |

### Asymmetric (4-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 12x48x48 | 4.000 | 13.5 KB | 0.952 | 0.703 | 264.4 KB | 5,373,780 |
| 2 | 12x32x48 | 2.667 | 10.5 KB | 0.955 | 0.677 | 264.4 KB | 5,377,704 |
| 3 | 12x24x48 | 2.000 | 9.0 KB | 0.958 | 0.661 | 263.7 KB | 5,385,514 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x12x8 | 0.250 | 7.7 KB | 0.905 | 0.869 | 332.2 KB | 7,406,176 |
| 215 | 48x8x8 | 0.167 | 6.1 KB | 0.888 | 0.894 | 312.4 KB | 7,677,964 |
| 216 | 48x48x8 | 1.000 | 21.8 KB | 0.907 | 0.864 | 406.6 KB | 7,770,044 |

### Symmetric Single (4-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x32x48 | 2.000 | 11.0 KB | 0.958 | 0.729 | 171.8 KB | 4,374,128 |
| 2 | 12x32x48 | 2.667 | 9.8 KB | 0.954 | 0.768 | 158.9 KB | 4,414,026 |
| 3 | 16x32x32 | 2.000 | 8.0 KB | 0.961 | 0.707 | 171.2 KB | 4,414,736 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x8x8 | 0.167 | 3.2 KB | 0.962 | 0.732 | 221.2 KB | 5,645,140 |
| 215 | 8x8x8 | 1.000 | 0.8 KB | 0.963 | 0.804 | 152.1 KB | 5,654,704 |
| 216 | 32x8x8 | 0.250 | 2.2 KB | 0.973 | 0.590 | 247.0 KB | 5,746,222 |

---

## 2. Details for Associativity = 8-way

### Symmetric Double (8-way)

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

### Asymmetric (8-way)

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

### Symmetric Single (8-way)

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

## 2. Details for Associativity = 16-way

### Symmetric Double (16-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 48x16x32 | 0.333 | 22.0 KB | 0.881 | 0.777 | 512.0 KB | 7,601,408 |
| 2 | 48x12x32 | 0.250 | 19.5 KB | 0.869 | 0.800 | 512.0 KB | 7,804,608 |
| 3 | 32x32x32 | 1.000 | 24.0 KB | 0.896 | 0.679 | 657.8 KB | 8,169,136 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 8x48x8 | 6.000 | 6.5 KB | 0.914 | 0.085 | 2038.9 KB | 17,220,144 |
| 215 | 8x8x8 | 1.000 | 1.5 KB | 0.910 | 0.240 | 1952.0 KB | 17,247,872 |
| 216 | 8x48x48 | 6.000 | 24.0 KB | 0.735 | 0.627 | 1952.0 KB | 17,373,056 |

### Asymmetric (16-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x48x48 | 3.000 | 16.5 KB | 0.948 | 0.728 | 260.0 KB | 5,327,792 |
| 2 | 16x32x32 | 2.000 | 10.0 KB | 0.957 | 0.651 | 260.0 KB | 5,327,872 |
| 3 | 16x32x48 | 2.000 | 13.0 KB | 0.949 | 0.718 | 260.0 KB | 5,352,928 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 48x32x8 | 0.667 | 15.5 KB | 0.927 | 0.799 | 431.1 KB | 7,516,264 |
| 215 | 48x8x8 | 0.167 | 6.1 KB | 0.884 | 0.903 | 296.0 KB | 7,648,184 |
| 216 | 48x48x8 | 1.000 | 21.8 KB | 0.905 | 0.857 | 440.0 KB | 8,012,272 |

### Symmetric Single (16-way)

#### Top 3 Optimal Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 16x48x48 | 3.000 | 15.0 KB | 0.954 | 0.769 | 152.0 KB | 4,261,208 |
| 2 | 16x32x48 | 2.000 | 11.0 KB | 0.959 | 0.750 | 152.0 KB | 4,272,464 |
| 3 | 16x32x32 | 2.000 | 8.0 KB | 0.962 | 0.722 | 152.0 KB | 4,299,548 |

#### Bottom 3 Worst Tile Shapes

| Rank | Tile Shape ($T_M \times T_N \times T_K$) | Ratio ($T_N/T_M$) | Footprint (KB) | L1 Hit Rate | L2 Hit Rate | DRAM Traffic (KB) | Total Cycles |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 214 | 24x8x8 | 0.333 | 1.8 KB | 0.973 | 0.578 | 251.6 KB | 5,812,532 |
| 215 | 32x12x8 | 0.375 | 2.9 KB | 0.970 | 0.542 | 293.5 KB | 5,846,376 |
| 216 | 32x8x8 | 0.250 | 2.2 KB | 0.971 | 0.551 | 295.0 KB | 6,010,816 |

---

## 3. Aspect Ratio Sensitivity vs. Associativity
The plot below details how the cache associativity affects both execution cycles and the shape aspect ratio trend.

![Cache Associativity Aspect Ratio Sweeps](assoc_empirical.png)
