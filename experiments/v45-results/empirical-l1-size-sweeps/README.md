# L1-size sweep, best tile per size (96³, C-stationary)

Non-default config: (all defaults)

Each x point takes the best (minimum) value over all tile shapes.

![cycles](l1_size_sweep_cycles.png)

![cycles_nomulacc](l1_size_sweep_cycles_nomulacc.png)

![l1_traffic](l1_size_sweep_l1_traffic.png)

![l2_traffic](l1_size_sweep_l2_traffic.png)

![dram_traffic](l1_size_sweep_dram_traffic.png)

![total_traffic](l1_size_sweep_total_traffic.png)


## Best cell per metric

| metric | precision | L1 | tile (M×N×K) | value |
|---|---|---|---|---|
| cycles | Symmetric Double | L1=64K | 32×32×96 | 3,577,752 |
| cycles | Asymmetric | L1=64K | 24×96×96 | 2,886,564 |
| cycles | Symmetric Single | L1=64K | 32×96×96 | 2,537,386 |
| cycles_nomulacc | Symmetric Double | L1=64K | 32×32×96 | 3,467,160 |
| cycles_nomulacc | Asymmetric | L1=64K | 24×96×96 | 2,775,972 |
| cycles_nomulacc | Symmetric Single | L1=64K | 32×96×96 | 2,426,794 |
| l1_traffic | Symmetric Double | L1=64K | 32×8×8 | 442,368 |
| l1_traffic | Asymmetric | L1=64K | 8×8×8 | 239,616 |
| l1_traffic | Symmetric Single | L1=64K | 8×8×8 | 147,456 |
| l2_traffic | Symmetric Double | L1=16K | 48×96×8 | 369,024 |
| l2_traffic | Asymmetric | L1=4K | 8×8×8 | 239,616 |
| l2_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| dram_traffic | Symmetric Double | L1=16K | 48×96×8 | 369,024 |
| dram_traffic | Asymmetric | L1=4K | 8×8×8 | 239,616 |
| dram_traffic | Symmetric Single | L1=4K | 8×8×8 | 147,456 |
| total_traffic | Symmetric Double | L1=64K | 32×8×96 | 1,359,872 |
| total_traffic | Asymmetric | L1=64K | 16×8×48 | 731,392 |
| total_traffic | Symmetric Single | L1=64K | 8×8×8 | 443,392 |