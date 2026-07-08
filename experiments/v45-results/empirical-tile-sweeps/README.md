# Tile-shape sweep (96³, C-stationary)

Non-default config: (all defaults)

Points sharing an aspect ratio take the best (minimum) value.

![cycles](tile_sweep_cycles.png)

![cycles_nomulacc](tile_sweep_cycles_nomulacc.png)

![l1_traffic](tile_sweep_l1_traffic.png)

![l2_traffic](tile_sweep_l2_traffic.png)

![dram_traffic](tile_sweep_dram_traffic.png)

![total_traffic](tile_sweep_total_traffic.png)


## Best tile per metric

| metric | precision | tile (M×N×K) | value |
|---|---|---|---|
| cycles | Symmetric Double | 32×32×32 | 3,806,800 |
| cycles | Asymmetric | 32×48×48 | 3,107,514 |
| cycles | Symmetric Single | 48×48×48 | 2,767,836 |
| cycles_nomulacc | Symmetric Double | 32×32×32 | 3,696,208 |
| cycles_nomulacc | Asymmetric | 32×48×48 | 2,996,922 |
| cycles_nomulacc | Symmetric Single | 48×48×48 | 2,657,244 |
| l1_traffic | Symmetric Double | 24×32×8 | 663,552 |
| l1_traffic | Asymmetric | 8×8×8 | 442,368 |
| l1_traffic | Symmetric Single | 32×48×8 | 258,048 |
| l2_traffic | Symmetric Double | 48×16×32 | 419,072 |
| l2_traffic | Asymmetric | 8×8×8 | 239,616 |
| l2_traffic | Symmetric Single | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | 48×16×32 | 419,072 |
| dram_traffic | Asymmetric | 8×8×8 | 239,616 |
| dram_traffic | Symmetric Single | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | 24×32×8 | 1,767,552 |
| total_traffic | Asymmetric | 8×8×8 | 921,600 |
| total_traffic | Symmetric Single | 48×32×16 | 628,224 |