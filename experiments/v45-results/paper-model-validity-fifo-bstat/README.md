# Model validity, FIFO B (B-stationary)

Non-default config: m×n×k=128×512×64, B_prec=8B, L1=4K, L2=16K, DRAM lat=160, PRNG_FIFO_GEN_COST=20, TILE_K=64
aspect=T_N/T_M = 4, B=FIFO, gen=fetch cost

B is FIFO-generated; per-element generation cost equals A's per-element DRAM cost (both 20 cycles). A and B share 8 B precision. Seed = 8 B per B tile.

![assoc excess](assoc_excess.png)

![fifo generations](fifo_generations.png)


![cycles](fifo_validity_cycles.png)

![cycles_nomulacc](fifo_validity_cycles_nomulacc.png)

![l1_traffic](fifo_validity_l1_traffic.png)

![l2_traffic](fifo_validity_l2_traffic.png)

![dram_traffic](fifo_validity_dram_traffic.png)

![total_traffic](fifo_validity_total_traffic.png)