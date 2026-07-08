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
| cycles | Symmetric Double | 32×32×32 | 3,806,800 |
| cycles | Asymmetric | 24×96×96 | 2,970,450 |
| cycles | Symmetric Single | 96×32×96 | 2,703,402 |
| cycles_nomulacc | Symmetric Double | 32×32×32 | 3,696,208 |
| cycles_nomulacc | Asymmetric | 24×96×96 | 2,859,858 |
| cycles_nomulacc | Symmetric Single | 96×32×96 | 2,592,810 |
| l1_traffic | Symmetric Double | 24×32×8 | 663,552 |
| l1_traffic | Asymmetric | 8×8×8 | 442,368 |
| l1_traffic | Symmetric Single | 32×48×8 | 258,048 |
| l2_traffic | Symmetric Double | 48×96×8 | 369,024 |
| l2_traffic | Asymmetric | 8×8×8 | 239,616 |
| l2_traffic | Symmetric Single | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 48×96×8 | 369,024 |
| dram_traffic | Asymmetric | 8×8×8 | 239,616 |
| dram_traffic | Symmetric Single | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 24×32×8 | 1,767,552 |
| total_traffic | Asymmetric | 8×8×8 | 921,600 |
| total_traffic | Symmetric Single | 48×32×16 | 628,224 |