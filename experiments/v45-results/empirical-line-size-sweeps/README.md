# Line-size sweep, best tile per line size (96³, C-stationary)

Non-default config: (all defaults)

Each x point takes the best (minimum) value over all tile shapes.

![cycles](line_size_sweep_cycles.png)

![cycles_nomulacc](line_size_sweep_cycles_nomulacc.png)

![l1_traffic](line_size_sweep_l1_traffic.png)

![l2_traffic](line_size_sweep_l2_traffic.png)

![dram_traffic](line_size_sweep_dram_traffic.png)

![total_traffic](line_size_sweep_total_traffic.png)


## Best cell per metric

| metric | precision | line | tile (M×N×K) | value |
|---|---|---|---|---|
| cycles | Symmetric Double | 128B | 24×32×8 | 3,745,560 |
| cycles | Asymmetric | 128B | 12×96×8 | 3,180,060 |
| cycles | Symmetric Single | 128B | 12×96×8 | 3,069,576 |
| cycles_nomulacc | Symmetric Double | 128B | 24×32×8 | 3,634,968 |
| cycles_nomulacc | Asymmetric | 128B | 12×96×8 | 3,069,468 |
| cycles_nomulacc | Symmetric Single | 128B | 12×96×8 | 2,958,984 |
| l1_traffic | Symmetric Double | 16B | 24×32×8 | 663,552 |
| l1_traffic | Asymmetric | 16B | 12×96×8 | 368,640 |
| l1_traffic | Symmetric Single | 16B | 32×48×8 | 258,048 |
| l2_traffic | Symmetric Double | 16B | 48×96×8 | 368,640 |
| l2_traffic | Asymmetric | 16B | 8×8×8 | 239,616 |
| l2_traffic | Symmetric Single | 16B | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 16B | 48×96×8 | 368,640 |
| dram_traffic | Asymmetric | 16B | 8×8×8 | 239,616 |
| dram_traffic | Symmetric Single | 16B | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 16B | 32×32×8 | 1,705,824 |
| total_traffic | Asymmetric | 16B | 12×96×8 | 848,832 |
| total_traffic | Symmetric Single | 16B | 48×32×8 | 630,784 |