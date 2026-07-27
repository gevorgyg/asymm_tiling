# paper-per-matrix-balance

Non-default config: m×n×k=128×128×128, L1 ways=256, L2 ways=1024, TILE_K=128

![per-matrix reads](per_matrix_reads_vs_model.png)

![balance](balance_B_over_A.png)

![writes](per_matrix_writes.png)


## B/A read balance at the predicted optimum (want ≈ 1)

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