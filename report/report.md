---
title: "Tiling For Random Matrices With Asymmetric Precision"
subtitle: "Project Aleph Final Report"
author: "Areg Mikhatyrian, George Ginzburg"
date: "date"
lang: en
toc: true
toc-depth: 3
numbersections: true
geometry: margin=1in
header-includes:
  - \usepackage{graphicx}
  - \usepackage{float}
---

\newpage
# Introduction
why asymmetric precision and a randomly generated B change the tiling problem, in both memory traffic and cycle count

## Tiled Matrix Multiplication
C-stationary tiling: keep a C tile in L1 and stream an A row-band and a B col-band through it

## Reasons To Study Random Matrices
why random matmul with asymmetric precision is interesting, bring examples of randomized algos 

# Simulator
## Architecture


## Methodology
hardware config, workload sizes, modeling assumptions, matrix registers, matmul, T_k = A_width = B_height. also L1 should be tuned to be fully associative and we should be able to see exactly where on graphs L1 
overflow happens

# Optimal Tiling
## Traffic-Optimal Tiling
validate the traffic-optimal asymmetric tile (1/rho)

- experiment: `v5-results/paper-model/paper-traffic-model`

- experiment: `v5-results/paper-model/paper-per-matrix-balance`

## PRNG-FIFO
explain how prng-fifo works, the fact that it works in parallel with memory accesses, mention negligible seed traffic
- experiment: not sure there is experiment, but need to sweep over g_c for b-stationary and c-stationary modes and check cycle count. **!important! g_c needs to be measured not just in cycles, but has to be compared to some other cycle cost in the simulation.** for example: plot how much cycles it costs to bring an element of A vs how much it costs to bring an element of B (i.e. sweeping over g_c / T_m)

### Choosing a Dataflow
b-stationary vs c-stationary, fifo streams B in fixed order, b-stationary reuses each B element T_M times

- experiment: `v55-results/b-stationry-vs-c-stationary`

- experiment: `v55-results/b-stationary-vs-c-stationry-col-major` (maybe?? i dont get totally what this does)

### Generating B vs Loading B
when does FIFO generation beat bringing B from memory

- experiment: `v5-results/math-model-no-l2/e13-fifo-vs-mem` 

## Traffic-Optimal vs Cycle-Optimal
minimizing traffic != minimizing cycles, why the old model doesn't work, new formula. put graphs that show that it's true

- experiment: `v5-results/prng-fifo-pipelined-sweep` 

- experiment: `v5-results/math-model-no-l2/e14-pipelined-fifo-vs-mem` 

## Calibrating $\alpha$
- experiment: `v5-results/math-model-no-l2/e6-tn-independence`. **important!** have to tie Tile-M dimension to some size in the simulation, probably to the size of L1

- experiment: `experiments/v5-results/math-model-no-l2/e3-alpha-calibration`. same notion

### Is This Correct? Yes
if we calibrate $\alpha$ once for g_c=0, we will find that it's optimal for g_c > 0

- experiment: `v5-results/math-model-no-l2/e8-gc-boundary-sweep` 

### Optimal Tile Shape vs g_c
measured best tile per g_c (not model prediction). maybe need a longer x-axis sweep? need to understand the results

- experiment: `v5-results/math-model-no-l2/e8-gc-boundary-sweep` (`best_shape_per_gc.png`)

# Impact of Tile Selection
## Optimal vs Square Tiles
we have a speedup. the y-axis needs to be better formulated

- experiment: `v5-results/math-model-no-l2/e8-gc-boundary-sweep` (`optimal_vs_square.png`)

- experiment: `v5-results/math-model-no-l2/e8-gc-boundary-sweep` + `e13-fifo-vs-mem` (`fifo_vs_mem_square.png`)


# Conclusion
asymmetric tile beats square in both traffic and cycles, one-shot $\alpha$ calibration predicts the best tile


\newpage
