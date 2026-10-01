# GENERAL
[x] - add fifo.  
[x] - add usage of fifo and seeds to the multiunit.  
[x] - add global clock for all components (total cycle tracker).  
[x] - add stat tracking to each componant -> each componant registers his stats to the registry.  
[x] - add print of all at the end of the run.  
[x] - add toml config file support.  
[x] - refractor the cache design to more layers.  
[x] - run verification tests.  
[ ] - reproduce presentation experiments.  
[ ] - plan and run new experiments.  
[ ] - finish report.  
[ ] - finish presentation.  

# NEW EXPERIMENTS
## SOFTWARE
[ ] - Can I pick the tile without autotuning? (no tuning runs)
[ ] - How much autotuning do I need?
[ ] - My matrices aren't 192×256×256: how does the best tile change with the shape?
[ ] - I don't know gc exactly. Which tile is safe?
[ ] - Which register block size should my kernel use? (R = 2, 4, 8)
[ ] - Does using smaller numbers for A and C help? (element size 2 / 4 / 8 bytes)

## HARDWARE
[ ] - How fast must my PRNG be?
[ ] - Spend area on a bigger L1 or a faster PRNG?
[ ] - How big does the FIFO need to be?
[ ] - Is a fully associative cache or scratchpad worth it over an 8- or 4-way cache?
[ ] - Does an L2 help? Does memory latency matter?
[ ] - "How many registers should the core have?



