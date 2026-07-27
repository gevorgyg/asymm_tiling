# L1-size sweep, best tile per size (96³, B-stationary)

Non-default config: (all defaults)

Each x point takes the best (minimum) value over all tile shapes.

![cycles](l1_size_sweep_bstat_cycles.png)

![cycles_nomulacc](l1_size_sweep_bstat_cycles_nomulacc.png)

![l1_traffic](l1_size_sweep_bstat_l1_traffic.png)

![l2_traffic](l1_size_sweep_bstat_l2_traffic.png)

![dram_traffic](l1_size_sweep_bstat_dram_traffic.png)

![total_traffic](l1_size_sweep_bstat_total_traffic.png)


## Best cell per metric

| metric | precision | L1 | tile (M×N×K) | value |
|---|---|---|---|---|
| cycles | Symmetric Double | L1=64K | 8×32×8 | 4,222,140 |
| cycles | Asymmetric | L1=64K | 8×32×8 | 4,035,804 |
| cycles | Symmetric Single | L1=64K | 8×96×8 | 3,173,760 |
| cycles_nomulacc | Symmetric Double | L1=64K | 8×32×8 | 4,111,548 |
| cycles_nomulacc | Asymmetric | L1=64K | 8×32×8 | 3,925,212 |
| cycles_nomulacc | Symmetric Single | L1=64K | 8×96×8 | 3,063,168 |
| l1_traffic | Symmetric Double | L1=64K | 8×32×8 | 442,368 |
| l1_traffic | Asymmetric | L1=64K | 8×32×8 | 387,072 |
| l1_traffic | Symmetric Single | L1=64K | 8×8×8 | 147,456 |
| l2_traffic | Symmetric Double | L1=4K | 8×32×8 | 442,368 |
| l2_traffic | Asymmetric | L1=4K | 8×32×8 | 387,072 |
| l2_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | L1=4K | 8×32×8 | 442,368 |
| dram_traffic | Asymmetric | L1=4K | 8×32×8 | 387,072 |
| dram_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | L1=64K | 8×32×8 | 1,474,560 |
| total_traffic | Asymmetric | L1=64K | 8×32×8 | 1,308,672 |
| total_traffic | Symmetric Single | L1=64K | 8×8×96 | 442,368 |