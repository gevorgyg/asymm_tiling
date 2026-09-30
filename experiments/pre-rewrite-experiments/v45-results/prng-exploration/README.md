# prng-exploration

Non-default config: m×n×k=128×512×64, B_prec=8B, L1=4K, L2=16K, DRAM lat=160, PRNG_FIFO_GEN_COST=20, tile=32×128×64
B=FIFO

Parity baseline: A DRAM cost = B generation cost = 20 cyc/element. Each knob swept alone; both loop orders shown.


### sweep MEM_ACCESS_CYCLES

![MEM_ACCESS_CYCLES cycles](knob_MEM_ACCESS_CYCLES_cycles.png)

![MEM_ACCESS_CYCLES cycles_nomulacc](knob_MEM_ACCESS_CYCLES_cycles_nomulacc.png)

![MEM_ACCESS_CYCLES l1_traffic](knob_MEM_ACCESS_CYCLES_l1_traffic.png)

![MEM_ACCESS_CYCLES l2_traffic](knob_MEM_ACCESS_CYCLES_l2_traffic.png)

![MEM_ACCESS_CYCLES dram_traffic](knob_MEM_ACCESS_CYCLES_dram_traffic.png)

![MEM_ACCESS_CYCLES total_traffic](knob_MEM_ACCESS_CYCLES_total_traffic.png)


### sweep PRNG_FIFO_GEN_COST

![PRNG_FIFO_GEN_COST cycles](knob_PRNG_FIFO_GEN_COST_cycles.png)

![PRNG_FIFO_GEN_COST cycles_nomulacc](knob_PRNG_FIFO_GEN_COST_cycles_nomulacc.png)

![PRNG_FIFO_GEN_COST l1_traffic](knob_PRNG_FIFO_GEN_COST_l1_traffic.png)

![PRNG_FIFO_GEN_COST l2_traffic](knob_PRNG_FIFO_GEN_COST_l2_traffic.png)

![PRNG_FIFO_GEN_COST dram_traffic](knob_PRNG_FIFO_GEN_COST_dram_traffic.png)

![PRNG_FIFO_GEN_COST total_traffic](knob_PRNG_FIFO_GEN_COST_total_traffic.png)


### sweep PRNG_FIFO_SEED_BYTES

![PRNG_FIFO_SEED_BYTES cycles](knob_PRNG_FIFO_SEED_BYTES_cycles.png)

![PRNG_FIFO_SEED_BYTES cycles_nomulacc](knob_PRNG_FIFO_SEED_BYTES_cycles_nomulacc.png)

![PRNG_FIFO_SEED_BYTES l1_traffic](knob_PRNG_FIFO_SEED_BYTES_l1_traffic.png)

![PRNG_FIFO_SEED_BYTES l2_traffic](knob_PRNG_FIFO_SEED_BYTES_l2_traffic.png)

![PRNG_FIFO_SEED_BYTES dram_traffic](knob_PRNG_FIFO_SEED_BYTES_dram_traffic.png)

![PRNG_FIFO_SEED_BYTES total_traffic](knob_PRNG_FIFO_SEED_BYTES_total_traffic.png)


### sweep PRNG_FIFO_CAPACITY

![PRNG_FIFO_CAPACITY cycles](knob_PRNG_FIFO_CAPACITY_cycles.png)

![PRNG_FIFO_CAPACITY cycles_nomulacc](knob_PRNG_FIFO_CAPACITY_cycles_nomulacc.png)

![PRNG_FIFO_CAPACITY l1_traffic](knob_PRNG_FIFO_CAPACITY_l1_traffic.png)

![PRNG_FIFO_CAPACITY l2_traffic](knob_PRNG_FIFO_CAPACITY_l2_traffic.png)

![PRNG_FIFO_CAPACITY dram_traffic](knob_PRNG_FIFO_CAPACITY_dram_traffic.png)

![PRNG_FIFO_CAPACITY total_traffic](knob_PRNG_FIFO_CAPACITY_total_traffic.png)


### FIFO stalls vs capacity

![stalls](fifo_stall_cycles_vs_capacity.png)
