# prng-fifo-tile-sweep — Writeup

Investigates what happens when B is replaced by a cycle-accurate PRNG FIFO
(`--Bsource prng_fifo`) instead of loaded from memory.  The key architectural
change is that B *never touches the cache*: elements arrive from the FIFO
device at a configurable generation cost and are consumed directly.  This
frees all of L1 for A streaming and the resident C tile, which changes both
the optimal tile shape and the maximum usable C-tile size.

The workload is symmetric (ρ = A_P/B_P = 1, both 4 B) so that the mem
baseline has its predicted optimum at T_N/T_M = 1.  Any shift in the
prng_fifo optimal aspect is therefore unambiguously caused by the new
A-vs-PRNG bottleneck, not a pre-existing asymmetry.

## Two sub-experiments

### 1. Aspect sweep

**What we check.** Fix the C-tile area at roughly 512–1024 words and sweep
the tile aspect T_N/T_M across log₂ ∈ {−3,−2,−1, 0,+1,+2,+3}.  For each
aspect we run two sources:

- **mem**: B is loaded from cache in the normal way.
- **prng_fifo**: B elements are generated at a configurable cost
  `gen_cost` ∈ {1, 2, 4, 8, 16} cycles/element; the FIFO runs in the
  background and stalls the CPU only when it is empty.

**Hypothesis.**

*mem*: optimal at log₂(T_N/T_M) = 0 (= 1/ρ = 1), matching the AM-GM balance
derived in the paper.

*prng_fifo*: B exits the cache entirely, so the only L1 traffic is A (falling
with wider tiles) and C (roughly flat, from dirty-evict writebacks).  The new
bottleneck is A-load time vs. PRNG generation time.  Increasing T_N makes the
FIFO generate more elements per tile step, so the optimal aspect should shift
*right* (larger T_N/T_M) as gen_cost increases — the FIFO becomes the
bottleneck for wide tiles, pushing the optimum toward taller tiles (larger T_M,
smaller T_N).  At gen_cost = 1 (fast PRNG), cycles should be nearly flat
across aspects and significantly lower than mem.

**Stall fraction.** A separate panel shows the fraction of total cycles spent
waiting on an empty FIFO.  At the FIFO-bottleneck side of each curve this
fraction should climb sharply, making the bottleneck transition visible.

### 2. Size sweep

**What we check.** Fix the tile aspect at T_N/T_M = 1 (the predicted ρ=1
optimum for mem) and grow the square tile from budget = −6 to budget = 0,
where *budget* = log₂(C-tile bytes / L1 bytes).  Budget = 0 is the
`paper-model-validity` breakdown point: the C tile alone fills L1, leaving no
room for streaming.

- (8 × 8):   budget = −6 (C tile = L1/64 = 256 B)
- (16 × 16): budget = −4 (C tile = L1/16 = 1 KB)
- (32 × 32): budget = −2 (C tile = L1/4  = 4 KB)
- (64 × 64): budget =  0 (C tile = L1    = 16 KB)

**Hypothesis.**

*mem*: matches the `paper-model-validity` experiment — the model holds and
cycles are low while the C tile fits well below L1, then performance collapses
as budget → 0 because A-streaming evicts C lines.

*prng_fifo*: with B absent from the cache, L1 is shared only by A (streaming)
and C (resident).  The A stream is a single column slice per outer-product step
(TM × A_P = 32 B for the square 8×8 case, up to 256 B for 64×64), which is
much smaller than B's TN-row slice.  The expectation is that **prng_fifo can
sustain a larger C tile before performance degrades**, and that the degradation
at budget = 0 is less severe — or arrives later — than for mem.  The
quantitative question: does doubling the C tile improve end-to-end time for
prng_fifo in the budget ∈ [−2, 0] range where mem has already broken?

## Setup

m = n = k = 256, TK = k, A_P = B_P = 4 B, fully-associative 16 K L1 (L2 = 64 K),
`--outer_products` (C-stationary, rank-1 streaming loop order as in the paper),
PRNG FIFO capacity = 64 elements (large enough to decouple producer and
consumer timing in most configurations).
