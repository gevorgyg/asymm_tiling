# fifo_vs_mem: rewrite vs pre-rewrite

Re-run of pre-rewrite v5-results/math-model-no-l2/e13-fifo-vs-mem (with the
FIFO side from e8-gc-boundary-sweep).

Slides/charts: fifo_vs_mem_gc ("FIFO beats memory up to gc* ~ 200", TN=32),
fifo_adv_tn / fifo_vs_mem_tn (FIFO speedup over memory-B at gc=0 per TN).
M=192, N=K=256, 4-byte elements, fully associative 16 KB L1, no L2, mulacc
not counted. FIFO side: best TM per TN, B-stationary.

NOT a like-for-like re-run of the memory side: the old memory-B baseline was
A-register-stationary (pre-3b03ded "C" with B from memory), a dataflow the
rewrite doesn't have. The rewrite's baseline here is B-stationary with B from
memory on the same TM x TN grid. Compare the conclusions, not the numbers.

run:  .venv/bin/python experiments/rewrite/fifo_vs_mem.py

## FIFO advantage over memory-B at gc = 0, per TN (fifo_adv_tn)

| TN | old mem (A-stat) | old FIFO | old advantage | new mem (B-stat) | new FIFO | new advantage |
|---|---|---|---|---|---|---|
| 4 | 7.383 | 3.316 | 55% | 4.086 | 0.850 | 79% |
| 8 | 5.243 | 3.315 | 37% | 2.445 | 0.849 | 65% |
| 16 | 4.172 | 3.314 | 21% | 1.625 | 0.849 | 48% |
| 32 | 3.754 | 3.313 | 12% | 1.399 | 0.848 | 39% |
| 64 | 3.692 | 3.340 | 10% | 1.353 | 0.854 | 37% |

## Crossover gc* at TN = 32 (fifo_vs_mem_gc; slide: ≈ 200)

- **old**: memory-B alpha 3.754, crossover ≈ 203 (between 150 and 250)
- **new**: memory-B alpha 1.399, crossover ≈ 89 (between 80 and 100)

### Best FIFO alpha vs gc at TN = 32

| gc | old | new |
|---|---|---|
| 0 | 3.313 | 0.848 |
| 5 | · | 0.849 |
| 10 | · | 0.875 |
| 15 | 3.315 | 1.148 |
| 20 | · | 1.148 |
| 30 | 3.318 | 1.149 |
| 38 | 3.319 | · |
| 40 | · | 1.149 |
| 42 | 3.486 | · |
| 47 | 3.486 | · |
| 50 | 3.486 | 1.149 |
| 52 | 3.486 | · |
| 57 | 3.487 | · |
| 60 | · | 1.150 |
| 68 | 3.487 | · |
| 74 | 3.487 | · |
| 80 | · | 1.252 |
| 100 | 3.488 | 1.564 |
| 150 | 3.489 | 2.346 |
| 200 | · | 3.127 |
| 250 | 3.993 | 3.908 |
| 300 | · | 3.922 |
| 400 | 6.337 | 4.170 |
