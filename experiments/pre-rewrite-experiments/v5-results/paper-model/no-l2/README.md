# paper-model-no-l2

No-L2 paper-model experiment: tests whether removing L2 aligns the
cycle-optimal tile with the paper's traffic-predicted optimum.

With L2, large T_M causes the A tile to overflow L2; each A miss then
pays L2 latency + DRAM. This asymmetry shifts the cycle optimum away
from T_N/T_M = 1/ρ. Without L2 all L1 misses cost only DRAM latency,
so cycles ∝ L1 BytesIn and the cycle optimum should match 1/ρ.

## Conclusions

The hypothesis is **partially confirmed**.

**Per-matrix balance (Part 2) is exact:** B/A read ratio = 1.000 at every
predicted optimum for all ρ. The AM-GM mechanism is exact and unaffected
by memory hierarchy depth.

**Cycle-optimal aligns with traffic-optimal in 4/8 cases:**

| ρ | area | Matches? | Explanation of mismatch |
|---|---|---|---|
| 1.0 | 1024 | yes | |
| 0.25 | 1024 | yes | |
| 0.5 | 512 | yes | |
| 0.125 | 512 | yes | |
| 1.0 | 512 | no | Tie by symmetry — at ρ=1 (A_P=B_P), a tile and its transpose have equal traffic; line-alignment noise breaks the tie differently for cycles vs bytes |
| 0.5 | 1024 | no | Line-rounding equalises (32,32) and (16,64) traffic; cycles drift to the B-heavy side |
| 0.25 | 512 | no | Paper's continuous optimum (T_N/T_M=4) falls between grid points; discrete winner differs between traffic and cycles |
| 0.125 | 1024 | no | Same grid issue; C is also evicted from L1 at extreme aspect ratios (see writes check below) |

The remaining mismatches are **not** caused by the L2 asymmetry that motivated
this experiment. They are inherent to the discrete tile grid and to C eviction
at extreme aspect ratios — both also present with L2.

**Writes check reveals C eviction at extreme tiles:** The writes check measures
how closely L1 BytesOut tracks mn·C_p (the paper's prediction that C leaves fast
memory exactly once). The worst tile in every ρ group is (T_M=256, T_N=4):

| ρ | max |writes − mn·C_p| / mn·C_p over all tiles | worst tile |
|---|---|---|
| all | 127× | (256, 4) |

For T_M=256, T_N=4: the A strip = T_M×K×A_p = 256×256×8 = 512 KB >> L1 = 16 KB.
A streams through L1 and repeatedly evicts dirty C lines directly to DRAM (no L2
to absorb them). The measured L1 BytesOut is 128× the expected mn·C_p, confirming
C is **not stationary** for this tile. This is a precondition for the paper's
traffic model to hold, and it fails at these extreme aspect ratios with or without L2.

For the tiles where C does stay stationary (T_M ≤ 64 in the 1024-word family),
the writes check matches mn·C_p exactly.


## Part 1: Traffic model validation (M=N=K=256)

Config: m×n×k=256×256×256, L1 ways=256, TILE_K=256, no_l2=True

![reads](traffic_reads_vs_model.png)

![writes](traffic_writes_vs_model.png)


## Cycle-optimal vs traffic-optimal tile

With no L2, every L1 miss costs DRAM latency (uniform). Expected: argmin(cycles) = argmin(L1 BytesIn) = paper's 1/ρ.

| ρ | area | traffic argmin T_N/T_M | cycle argmin T_N/T_M | match? | predicted 1/ρ |
|---|---|---|---|---|---|
| 1 | 1024 | 1 | 1 | yes | 1 |
| 1 | 512 | 0.5 | 2 | no | 1 |
| 0.5 | 1024 | 1 | 4 | no | 2 |
| 0.5 | 512 | 2 | 2 | yes | 2 |
| 0.25 | 1024 | 4 | 4 | yes | 4 |
| 0.25 | 512 | 2 | 8 | no | 4 |
| 0.125 | 1024 | 4 | 16 | no | 8 |
| 0.125 | 512 | 8 | 8 | yes | 8 |

## Savings vs square tile (1024-word family, measured reads)

| ρ | reads(best)/reads(32×32) | paper asymptotic 2√ρ/(1+ρ) |
|---|---|---|
| 1 | 1.000 | 1.000 |
| 0.5 | 1.000 | 0.943 |
| 0.25 | 0.818 | 0.800 |
| 0.125 | 0.636 | 0.629 |

## Writes = mn·C_p check

| ρ | max |writes − mn·C_p| / mn·C_p over all tiles |
|---|---|
| 1 | 127.0000 |
| 0.5 | 127.0000 |
| 0.25 | 127.0000 |
| 0.125 | 127.0000 |

Worst tile in every case: (T_M=256, T_N=4). See Conclusions above.

![cycles](traffic_model_cycles.png)

![cycles_nomulacc](traffic_model_cycles_nomulacc.png)

![l1_traffic](traffic_model_l1_traffic.png)

![l2_traffic](traffic_model_l2_traffic.png)

![dram_traffic](traffic_model_dram_traffic.png)

![total_traffic](traffic_model_total_traffic.png)

## Part 2: Per-matrix balance (M=N=K=128)

Config: m×n×k=128×128×128, L1 ways=256, TILE_K=128, no_l2=True

![per-matrix reads](per_matrix_reads_vs_model.png)

![balance](balance_B_over_A.png)

![writes](per_matrix_writes.png)


## B/A balance at the predicted optimum (want ≈ 1)

| ρ | tile | measured B/A | word-model B/A |
|---|---|---|---|
| 1 | 32×32 | 1.000 | 1 |
| 0.5 | 16×32 | 1.000 | 1 |
| 0.25 | 16×64 | 1.000 | 1 |
| 0.125 | 8×64 | 1.000 | 1 |

![cycles](per_matrix_balance_cycles.png)

![cycles_nomulacc](per_matrix_balance_cycles_nomulacc.png)

![l1_traffic](per_matrix_balance_l1_traffic.png)

![l2_traffic](per_matrix_balance_l2_traffic.png)

![dram_traffic](per_matrix_balance_dram_traffic.png)

![total_traffic](per_matrix_balance_total_traffic.png)
