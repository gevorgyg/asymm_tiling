# Associativity sweep, best tile per assoc (96³, B-stationary)

Non-default config: (all defaults)

Each x point takes the best (minimum) value over all tile shapes.

![cycles](assoc_sweep_bstat_cycles.png)

![cycles_nomulacc](assoc_sweep_bstat_cycles_nomulacc.png)

![l1_traffic](assoc_sweep_bstat_l1_traffic.png)

![l2_traffic](assoc_sweep_bstat_l2_traffic.png)

![dram_traffic](assoc_sweep_bstat_dram_traffic.png)

![total_traffic](assoc_sweep_bstat_total_traffic.png)


## Best cell per metric

| metric | precision | assoc | tile (M×N×K) | value |
|---|---|---|---|---|
| cycles | Symmetric Double | 16-way | 8×32×8 | 6,376,496 |
| cycles | Asymmetric | 16-way | 8×32×8 | 6,196,142 |
| cycles | Symmetric Single | 2-way | 8×16×8 | 4,326,272 |
| cycles_nomulacc | Symmetric Double | 16-way | 8×32×8 | 6,265,904 |
| cycles_nomulacc | Asymmetric | 16-way | 8×32×8 | 6,085,550 |
| cycles_nomulacc | Symmetric Single | 2-way | 8×16×8 | 4,215,680 |
| l1_traffic | Symmetric Double | 1-way | 8×32×8 | 8,585,280 |
| l1_traffic | Asymmetric | 1-way | 8×32×8 | 8,389,504 |
| l1_traffic | Symmetric Single | 1-way | 8×16×8 | 4,413,888 |
| l2_traffic | Symmetric Double | 16-way | 8×32×8 | 443,008 |
| l2_traffic | Asymmetric | 16-way | 8×32×8 | 387,200 |
| l2_traffic | Symmetric Single | 8-way | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 16-way | 8×32×8 | 443,008 |
| dram_traffic | Asymmetric | 16-way | 8×32×8 | 387,200 |
| dram_traffic | Symmetric Single | 8-way | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 16-way | 8×32×8 | 11,694,080 |
| total_traffic | Asymmetric | 16-way | 8×32×8 | 11,475,328 |
| total_traffic | Symmetric Single | 2-way | 8×16×8 | 5,177,088 |