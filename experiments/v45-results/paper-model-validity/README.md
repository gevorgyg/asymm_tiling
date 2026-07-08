# paper-model-validity

Non-default config: m×n×k=256×256×256, TILE_K=256, aspect=T_N/T_M = 4 (predicted optimum), order=outer products, flags: --outer_products

Prediction = line-aware paper formula; excess of 1.0 means the two-level model holds exactly.

![excess](excess_vs_budget.png)


## Traffic excess (measured / predicted L1 BytesIn)

| regime | 4×16 (512B C tile) | 8×32 (2K C tile) | 16×64 (8K C tile) | 32×128 (32K C tile) | 64×256 (128K C tile) |
|---|---|---|---|---|---|
| 8-way, L1=16K | 0.76 | 1.48 | 8.56 | 14.24 | 22.81 |
| 8-way, L1=64K | 0.73 | 0.66 | 0.83 | 4.70 | 22.67 |
| fully-assoc, L1=16K | 1.00 | 1.00 | 1.00 | 14.20 | 22.67 |
| fully-assoc, L1=64K | 0.37 | 0.59 | 1.00 | 1.00 | 22.67 |

![cycles](model_validity_cycles.png)

![cycles_nomulacc](model_validity_cycles_nomulacc.png)

![l1_traffic](model_validity_l1_traffic.png)

![l2_traffic](model_validity_l2_traffic.png)

![dram_traffic](model_validity_dram_traffic.png)

![total_traffic](model_validity_total_traffic.png)