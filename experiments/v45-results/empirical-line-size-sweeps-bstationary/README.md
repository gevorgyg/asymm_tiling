# Line-size sweep, best tile per line size (96³, B-stationary)

Non-default config: (all defaults)

Each x point takes the best (minimum) value over all tile shapes.

![cycles](line_size_sweep_bstat_cycles.png)

![cycles_nomulacc](line_size_sweep_bstat_cycles_nomulacc.png)

![l1_traffic](line_size_sweep_bstat_l1_traffic.png)

![l2_traffic](line_size_sweep_bstat_l2_traffic.png)

![dram_traffic](line_size_sweep_bstat_dram_traffic.png)

![total_traffic](line_size_sweep_bstat_total_traffic.png)


## Best cell per metric

| metric | precision | line | tile (M×N×K) | value |
|---|---|---|---|---|
| cycles | Symmetric Double | 128B | 8×32×8 | 5,787,312 |
| cycles | Asymmetric | 128B | 8×32×8 | 5,724,160 |
| cycles | Symmetric Single | 32B | 8×16×8 | 4,362,068 |
| cycles_nomulacc | Symmetric Double | 128B | 8×32×8 | 5,676,720 |
| cycles_nomulacc | Asymmetric | 128B | 8×32×8 | 5,613,568 |
| cycles_nomulacc | Symmetric Single | 32B | 8×16×8 | 4,251,476 |
| l1_traffic | Symmetric Double | 16B | 8×8×8 | 5,419,008 |
| l1_traffic | Asymmetric | 16B | 8×8×8 | 5,334,336 |
| l1_traffic | Symmetric Single | 16B | 8×32×8 | 754,304 |
| l2_traffic | Symmetric Double | 16B | 8×32×8 | 442,880 |
| l2_traffic | Asymmetric | 16B | 8×32×8 | 387,264 |
| l2_traffic | Symmetric Single | 16B | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 16B | 8×32×8 | 442,880 |
| dram_traffic | Asymmetric | 16B | 8×32×8 | 387,264 |
| dram_traffic | Symmetric Single | 16B | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 16B | 8×32×8 | 6,308,224 |
| total_traffic | Asymmetric | 16B | 8×32×8 | 6,118,800 |
| total_traffic | Symmetric Single | 16B | 8×16×8 | 1,131,008 |