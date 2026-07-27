# Tile-shape sweep incl. matrix-spanning tiles (96³, C-stationary)

Non-default config: (all defaults)

Points sharing an aspect ratio take the best (minimum) value.

![cycles](tile_sweep_96_cycles.png)

![cycles_nomulacc](tile_sweep_96_cycles_nomulacc.png)

![l1_traffic](tile_sweep_96_l1_traffic.png)

![l2_traffic](tile_sweep_96_l2_traffic.png)

![dram_traffic](tile_sweep_96_dram_traffic.png)

![total_traffic](tile_sweep_96_total_traffic.png)


## Best tile per metric

| metric | precision | tile (M×N×K) | value |
|---|---|---|---|
| cycles | Symmetric Double | 32×32×8 | 4,451,354 |
| cycles | Asymmetric | 12×96×8 | 3,522,132 |
| cycles | Symmetric Single | 12×96×8 | 3,300,984 |
| cycles_nomulacc | Symmetric Double | 32×32×8 | 4,340,762 |
| cycles_nomulacc | Asymmetric | 12×96×8 | 3,411,540 |
| cycles_nomulacc | Symmetric Single | 12×96×8 | 3,190,392 |
| l1_traffic | Symmetric Double | 24×32×8 | 663,552 |
| l1_traffic | Asymmetric | 12×96×8 | 368,640 |
| l1_traffic | Symmetric Single | 32×48×8 | 258,048 |
| l2_traffic | Symmetric Double | 48×96×8 | 368,640 |
| l2_traffic | Asymmetric | 8×8×8 | 239,616 |
| l2_traffic | Symmetric Single | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 48×96×8 | 368,640 |
| dram_traffic | Asymmetric | 8×8×8 | 239,616 |
| dram_traffic | Symmetric Single | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 24×32×8 | 1,775,232 |
| total_traffic | Asymmetric | 12×96×8 | 848,896 |
| total_traffic | Symmetric Single | 48×32×8 | 630,784 |