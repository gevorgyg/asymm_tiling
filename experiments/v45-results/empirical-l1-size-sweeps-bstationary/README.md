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
| cycles | Symmetric Double | L1=64K | 16×32×96 | 4,462,464 |
| cycles | Asymmetric | L1=64K | 16×96×96 | 3,779,326 |
| cycles | Symmetric Single | L1=64K | 96×96×32 | 3,349,992 |
| cycles_nomulacc | Symmetric Double | L1=64K | 16×32×96 | 4,351,872 |
| cycles_nomulacc | Asymmetric | L1=64K | 16×96×96 | 3,668,734 |
| cycles_nomulacc | Symmetric Single | L1=64K | 96×96×32 | 3,239,400 |
| l1_traffic | Symmetric Double | L1=64K | 8×32×96 | 442,368 |
| l1_traffic | Asymmetric | L1=64K | 8×96×96 | 239,616 |
| l1_traffic | Symmetric Single | L1=64K | 8×8×8 | 147,456 |
| l2_traffic | Symmetric Double | L1=4K | 8×32×96 | 442,368 |
| l2_traffic | Asymmetric | L1=4K | 8×96×96 | 239,616 |
| l2_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | L1=4K | 8×32×96 | 442,368 |
| dram_traffic | Asymmetric | L1=4K | 8×96×96 | 239,616 |
| dram_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | L1=64K | 8×32×96 | 1,335,296 |
| total_traffic | Asymmetric | L1=64K | 12×96×96 | 764,928 |
| total_traffic | Symmetric Single | L1=64K | 8×8×96 | 442,368 |