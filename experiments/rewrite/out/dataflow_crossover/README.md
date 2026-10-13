# dataflow_crossover: B- vs C-stationary crossover, tile 64x32

| config | alpha_B | alpha_C | predicted gc* = R alpha_B | measured crossover |
|---|---|---|---|---|
| R 2 | 3.404 | 1.661 | 6.8 | between 6 and 7 |
| R 4 | 1.148 | 0.685 | 4.6 | between 4 and 5 |
| R 8 | 0.584 | 0.466 | 4.7 | between 4 and 5 |
| R 16 | 0.443 | 0.809 | 7.1 | B faster from gc 0 |
| R 4, 1 cycle / MAC | 2.148 | 1.685 | 8.6 | between 8 and 9 |
