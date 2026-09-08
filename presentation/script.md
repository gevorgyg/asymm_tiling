# Presentation Script

---

## Slide 1 — Title

Hi everyone. I'm Areg, and together with Regev, under the supervision of Alon Amid, we've been working on a question that sounds simple: given a hardware accelerator that multiplies matrices, what shape should your tiles be?

It turns out the answer changes quite a bit depending on your hardware, and today I'll show you a model that predicts the optimal shape — and validates it empirically.

---

## Slide 2 — Matrix Multiply is Memory-Bound

Let's start with why this matters. A naively implemented matrix multiply reads A and B from RAM on every pass through the inner loop. For a 256×256 fp64 matrix, one input is around 0.5 MB — which is 8 to 32 times larger than a typical L1 cache.

> **[Note — slide says fp64]** The slide uses fp64 as the example (256×256×8B = 0.5MB). Script was originally written with float32 (which would be 0.25MB per matrix). Stick with fp64 when presenting.

The standard fix is tiling: instead of sweeping the whole matrix, we pick a small tile of C and keep it resident in L1 while we accumulate into it. That's what we'll be working with.

---

## Slide 3 — C-Stationary Tiling: Step by Step

Let me walk through how this works. We have matrices A, B, and C — all too large to fit in L1.

[click] We divide each matrix into a grid of tiles. The tile shape is TM rows by TN columns by TK in the K dimension.

[click] The idea is: fix one tile of C in L1. Then stream the corresponding A row-band and B column-band through it, accumulating the partial products.

[click] Once C_ij is done, we move to the next B column tile. The A row-band doesn't need to be reloaded — it's already in L1. This is the key reuse: each A element is touched TN times before eviction.

---

## ~~Slide 4 — Standard Assumption: Square Tiles~~ [REMOVED]

> This slide was cut from the presentation. The Asymmetric Precision slide now presents the general formula directly without the symmetric warm-up. If asked why square tiles are the standard, point back to slide 3: the C-stationary tiling step shows A reused TN times and B reused TM times — equal precisions means equal costs, balanced by equal tile dimensions.

---

## Slide 4 — Asymmetric Precision → Asymmetric Tiles

The slide shows the general traffic formula: T = MNK × (A_P/TN + B_P/TM). A is reused TN times, B is reused TM times. Setting the two terms equal gives TN*/TM* = A_P/B_P = 1/ρ.

When ρ=1 (equal precisions) you get a square tile. When ρ=1/4 — fp32 input, fp8 weights — the optimal tile is 4× wider than tall. The diagram shows both. Same cache budget, very different shape.

---

## Slide 6 — The Simulator We Built

Before showing the validation results, let me briefly describe the tool we used to generate them. We built a custom cycle-accurate C++ simulator from scratch — nothing off the shelf.

It has three main pieces. The InstGenerator takes a tile configuration and emits a stream of instructions into a text ISA — ltea for tile loads, tmulac for multiply-accumulate, tmov for stores. The Interpreter then dispatches those instructions and counts cycles for every memory access. And the MemoryHierarchy models a configurable L1/L2/DRAM stack with full per-access tracing — hit rates, evictions, line fills.

The key architectural detail, which we'll come back to, is that B takes a completely separate path. It goes through MMIO directly to a PRNG FIFO device, bypassing L1 entirely. A and C go through the normal cache hierarchy.

---

## Slide 7 — Traffic Minimum at the Predicted Tile

With the simulator in hand, we can validate the paper's formula. Each panel here sweeps the tile aspect ratio TN/TM on the x-axis and plots L1 read traffic. The dashed line is the paper's prediction for where the minimum should land.

For all four values of ρ, the empirical minimum falls exactly on the predicted aspect ratio. The simulation matches the formula to within about 2%.

> **[Config — fa_reads.png]**
> Source: `experiments/v5-results/paper-model/paper-traffic-model/`
> M=N=K=256, A_P=8B (fp64), B_P varies by ρ: 8B(ρ=1), 4B(ρ=0.5), 2B(ρ=0.25), 1B(ρ=0.125)
> L1=16KB, fully associative, no L2. C-stationary, B from memory (no FIFO).
> x-axis: log2(TN/TM) at constant tile area (TM×TN fixed word count).

---

## Slide 8 — B/A Balance: Exact Confirmation

We can look at this even more directly. Instead of plotting total traffic, this shows the ratio of B reads to A reads as the aspect ratio varies. At the paper's predicted optimum, the two inputs contribute equal traffic — so the ratio should cross 1.

And it does, exactly, for every ρ. The vertical dashed lines mark the predictions, and every curve crosses 1 right there. When ρ is 1/8, the traffic savings versus a square tile is 36%.

One thing worth noting: the blue line for ρ=1 shows a small bump at the far left, around log2(TN/TM) ≈ −4. This is a cache-line granularity artifact — when TN is so small that a single row of B fits in less than one cache line, loading it still pulls in a full 64-byte line. That inflates B traffic slightly above the theoretical prediction. The effect disappears as TN grows large enough to fill a line, and it doesn't affect the location of the minimum.

> **[Config — fa_balance.png]**
> Source: `experiments/v5-results/paper-model/paper-per-matrix-balance/`
> M=N=K=128, A_P=8B (fp64), B_P varies by ρ: same four values as slide 7.
> L1=16KB, fully associative, no L2. C-stationary, B from memory (no FIFO).
> Note: different matrix size from slide 7 (128 vs 256) — same hardware setup.

> **[Note — why the bump appears at the left of the graph]**
>
> The theoretical model assumes B traffic = TN × B_P bytes per A-row (you load exactly the B elements you need). But the memory system loads in units of cache lines (64 bytes). When TN is very small, one row of B fits in less than one full cache line — but loading a single element still pulls in the entire 64-byte line.
>
> The threshold: cache-line granularity matters when TN × B_P < 64 bytes.
> - With B_P = 4 bytes (fp32, ρ=1): kicks in when TN < 16. So at TN=8 you load 64 bytes to get 32 bytes of B — 2× more than the model predicts. At TN=4 it's 4×.
> - With B_P = 0.5 bytes (fp4-equivalent, ρ=0.125): kicks in when TN < 128. So the purple line shows the bump over a wider range of TN values.
>
> This is why the blue (ρ=1) curve rises slightly at log2(TN/TM) ≈ −4 instead of continuing to fall: the extra cache-line padding artificially inflates measured B traffic above the theoretical line. Once TN grows large enough that a row spans one or more full cache lines, the bump disappears and the ratio falls cleanly.
>
> It does not shift the minimum: the minimum is where B/A = 1, and at that TN the tile is large enough that cache-line rounding is negligible.

---

## Slide 9 — Traffic ≠ Time

So the paper's traffic model is solid. But here's the problem: minimizing bytes transferred is not the same as minimizing cycles. Cache latency, bandwidth limits, and prefetch behavior all break the simple proportionality between traffic and runtime — a tile that loads 10% fewer bytes doesn't necessarily run 10% faster.

We need a cycle-accurate model. And on top of that, we're working with a different hardware setup — one where B doesn't come from memory at all.

> **[Note — why cycles ≠ bytes]**
> Several effects break the proportionality:
> - **Latency vs. bandwidth**: an L1 hit costs ~4 cycles, L2 ~12, DRAM ~200+. The same byte count at different hit rates yields wildly different runtimes.
> - **Cache-line granularity**: loading even a single element evicts a full 64-byte line. A tile with low *element* traffic may still cause many line fills if spatial locality is poor.
> - **Bandwidth saturation**: if outstanding misses pile up and exceed the memory bus width, you stall regardless of total bytes.
> - **Prefetch hiding**: hardware prefetchers can overlap memory and compute for regular access patterns — an amortized-cost-per-byte model hides whether this overlap is happening.
> - **Pipeline stalls**: the CPU/accelerator stalls until the load completes if the next instruction depends on the result. A single long-latency miss serializes the pipeline even if total traffic is small.

---

## Slide 10 — Enter the PRNG FIFO

This is the PRNG FIFO. B elements are generated on-chip by a random number generator and streamed directly into the compute unit. B never touches the cache. B has no memory address.

This completely changes the model. The B_P/TM traffic term simply vanishes — there are no B cache misses to count. Instead, B introduces a new cost: on-chip generation time, g_c cycles per element. Our model must account for g_c, not B_P.

---

## Slide 11 — The PRNG FIFO: B Without Memory

Here's what the hardware looks like. A comes through the normal memory hierarchy — DRAM, L2, L1, registers. B takes a completely separate path: the PRNG generates it, the FIFO buffers it, and it goes straight to the MAC unit, bypassing the cache entirely.

Two independent bottlenecks: A-loading from memory, and waiting for the PRNG at g_c cycles per element.

---

## Slide 11b — Runtime = ?

[Pause. Let the question land.]

---

## Slide 11c — Runtime = whichever is slower

They run in parallel. The runtime is determined by whichever finishes last: A-loading or B-generation. This is the key insight the whole model rests on.

---

## Slide 12 — Which Loop Order Fits the FIFO?

Now, the FIFO generates B elements in a fixed order — you can't skip or replay them. The loop order of your computation must match the generation order, or you pay a penalty.

There are three natural options. C-stationary row-major, C-stationary col-major, and B-stationary. The table here shows the key difference: their effective B generation cost per output element.

C-stationary row-major pays g_c times TN per element — badly wasteful. C-stationary col-major pays g_c. B-stationary pays g_c over TM. That factor of TM is the key, and I'll explain where it comes from.

---

## Slide 13 — B-Stationary: TM-Fold Register Reuse

Loop order: B outer, A inner. One B block is fetched once, then all TM A-rows sweep through it. Each B element is reused TM times — generation cost amortized to g_c/TM per MAC.

The table on the slide shows the numbers directly: at g_c=0 C-stationary is 2× faster (lower α, no B cost). By g_c=10 C-stationary is already 1.25-1.28× slower. At g_c=100 it's 7.5× slower. The crossover happens fast because the ghost-read and lack-of-amortization penalties scale with g_c.

> **[Note — why B-stationary wins by such a large margin]**
>
> The fundamental difference is what the inner loop sweeps over:
> - **C-stationary**: C tile is fixed. Inner loop generates new B for each rti (reg_m A-rows). B amortized over reg_m rows.
> - **B-stationary**: ONE B register sub-tile is fixed in %rb. Inner loop sweeps ALL TM/reg_m A sub-tiles through it. B amortized over TM rows.
>
> Since TM >> reg_m (e.g., 32 vs 4), B-stationary reuses each B element 8× more. The per-MAC gen cost is:
>
> | Mode        | gen cost / MAC     | at gc=100, TM=32 |
> |-------------|-------------------|------------------|
> | row-major   | gc × TN / reg_m   | >> 100 cy        |
> | col-major   | gc / reg_m = gc/4 | 25 cy            |
> | B-stationary| gc / TM = gc/32   | **3.1 cy**       |
>
> The TM-fold amortization is the entire point. It doesn't matter how large the B block is — the N_B factor cancels in both numerator and denominator. What matters is how many A-rows share each B element: reg_m in C-stationary, TM in B-stationary.

---

## Slide 14 — Naive Cycle Model: Two Cost Terms

Now we can build a cycle model. The traffic argument translates directly: A is reused TN times, so its cost per MAC is C_A over TN, where C_A is cycles per element from L1. B is generated by the FIFO, reused TM times, so its cost is g_c over TM.

The naive model adds these: T/MNK equals C_A/TN plus g_c/TM. But this assumes sequential execution — that we load A, then generate B, one after the other.

---

## Slide 15 — FIFO is Async: Two Costs in Parallel

The FIFO doesn't work that way. It generates B in the background while the core is loading A. The two operations overlap, so the runtime is determined by whichever one takes longer:

T/MNK = max{ C_A/TN, g_c/TM }

This gives us two regimes. When g_c/TM is small — low generation cost or large TM — we're A-load bound, and reducing TN helps. When g_c/TM dominates, we're B-gen bound, and increasing TM helps. The optimal tile balances these two terms.

---

## Slide 16 — Replacing C_A/TN with Measured α(TM,TN)

There's one more problem. The C_A/TN term assumes A loading is a fixed cost per element divided cleanly by TN. In practice, cache residency, line utilization, and access patterns mean the actual cycles per MAC depend on tile shape in a way that's richer than a simple ratio.

So we replace C_A/TN with a measured quantity α(TM, TN), defined as T/MNK when g_c is zero. When B generation is free, the only cost left is A loading, so α captures exactly what we need — no assumptions, no formula.

The final model: T/MNK = max{ α(TM, TN), g_c/TM }.

---

## Slide 17 — Isolating α: Set g_c = 0

g_c is a hardware parameter we fully control in simulation. Setting it to zero collapses the max to just α(TM, TN). Run B-stationary at g_c=0, measure T/MNK — that's your α value. No formula assumed, no analytical model of cache behavior.

The procedure is: run B-stationary at g_c=0 for each valid (TM, TN) pair, record T/MNK. Done.

---

## Slide 18 — Calibration: Building the α Table

Here's what the measured α table looks like. Each line is a different TN value, plotted against TM on the x-axis.

Two things stand out. First, small TN values like TN=4 cause α to spike at moderate TM — the A tile overflows L1 with few column groups to amortize against. Second, for large TN like TN=32, α stays flat around 3.5 out to TM=96, then shoots up to around 9 — that's where the C tile can no longer fit in L1.

α decreases with TN because more column reuse means fewer A reloads per output. The cache boundary shifts with TM.

> **[Config — alpha_vs_tm.png]**
> Source: `presentation/graphs/gen_charts.py` → data from E6-nol2 (`experiments/v5-results/math-model-no-l2/e6-tn-independence/results.json`)
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, no L2. B-stationary, gc=0.
> TM swept: 8, 12, 16, 24, 32, 48, 64, 96. Five TN curves: 4, 8, 16, 32, 64.
> Dashed segments = C-tile eviction zone (ws_lines ≥ 300).

> **[Note — why the graph has two cliffs]**
>
> The three regimes in the graph correspond to what fits in L1. There are two transitions:
>
> **First cliff (small, at TM ≈ 12 → 16): A-tile overflows L1.**
> The A sub-tile is TM rows × TK columns × 4 bytes. L1 = 16KB.
> - TM=12: 12 × 256 × 4 = 12,288 B → fits in L1 ✓
> - TM=16: 16 × 256 × 4 = 16,384 B = exactly L1 → A starts evicting other data
> - TM ≥ 24: 24 KB+ → A sub-tile fully overflows L1, must reload from DRAM each pass
>
> After this cliff, α is roughly flat ("goes to a constant") — you're in the DRAM regime for A. Increasing TM doesn't help because A keeps coming from DRAM regardless.
>
> The cliff height depends on TN: in B-stationary, A is reused TN times per DRAM load (once per B column block). With TN=8 the jump is large (3.31→4.64) because each DRAM load buys only 8 reuses. With TN=32 the jump is small (3.31→3.58) because each load buys 32 reuses, making the DRAM cost affordable.
>
> **Second cliff (big, at high TM): C-tile overflows L1.**
> The C tile is TM × TN output partial sums, held resident in L1 throughout the inner loop. ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2 is the **reuse distance**: how many line-accesses happen between two consecutive touches of the same C line. L1 holds 256 lines; once the reuse distance exceeds that, C lines are evicted before they are reused. (Full derivation in the slide 22 note; 300 is a tolerance band above the true 256 capacity.)
> - TN=32: cliff at TM=96, ws=406 → α jumps from 3.48 to 9.03
> - TN=64: cliff at TM=48, ws=394 → α jumps from 3.34 to 4.39, then at TM=64 (ws=526) → 8.87
> - TN=8, TN=16: ws stays below 300 at all tested TM → NO second cliff visible
>
> The second cliff is much larger than the first because C is accessed on every single MAC (load + store, read-modify-write), not just once per B block like A. When C spills to DRAM, every MAC operation pays 2 × DRAM latency. That's why α jumps from ~3.5 to ~9 — roughly a 2.6× penalty.
>
> **Summary of the three regimes:**
> 1. **L1 regime** (TM ≤ 12): A fits in L1, all TN lines cluster near α ≈ 3.3
> 2. **DRAM-A regime** (16 ≤ TM ≤ ~64): A from DRAM, C still in L1. α ≈ flat per TN (lower TN = higher α)
> 3. **DRAM-AC regime** (TM large, TN large): both A and C from DRAM. α → ~9

---

## Slide 19 — Using the α Table: Predicting the Optimal Tile

Once we have α measured, using it is straightforward. For any new g_c, we evaluate max{ α(TM, TN), g_c/TM } at every valid tile shape and take the argmin. No new experiments — just table lookup and arithmetic.

The diagram shows why this works geometrically. α is roughly flat in the A-load-bound region, then rises when the A tile overflows L1. g_c/TM is a decreasing curve. They cross at the optimal TM*. The optimal TN* is the one that minimizes α at that TM — typically the largest TN that still fits the FIFO.

> **[Config — model_intuition.png]**
> Source: `presentation/graphs/gen_charts.py` → α data from E6-nol2, TN=32 slice.
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, no L2. TN=32 fixed.
> α(TM) curve measured at gc=0. Two gc/TM hyperbolas shown: gc=50 and gc=200.

---

## Slide 20 — Roofline Validation: Setup

Now the question is: does this actually work? We calibrate α once at g_c=0 — so we're committed to a fixed table — and then ask whether the model correctly predicts the best tile at new, unseen g_c values.

The methodology is: measure α at g_c=0; for each new g_c, compute the predicted best (TM*, TN*); run the simulator at that g_c empirically to find the true best; compare.

We ran this across two SRAM budgets — 64KB and 128KB. For each budget we swept how the budget is split between L1 and FIFO: 4 splits for 64KB, 8 splits for 128KB, 12 hardware configurations total. Nine g_c values from 10 to 500. That's 108 test conditions.

---

## Slide 21 — Roofline Validation: Results

108 out of 108 — exact match across all hardware configurations and all g_c values.

> **[Note — the argmin fix that gets us to 100%]**
>
> The original implementation had a tie-breaking bug. When multiple TN values at the same TM all enter the gen-bound regime (gc/TM > α for all valid TN), the roofline predicts identical cost (gc/TM) for each of them. Python's `min()` returns the first encountered, which in iteration order is the smallest TN. But empirically, larger TN is always slightly better because lower α means less residual A-load cost even inside gen-bound.
>
> Fix: break ties by α as a secondary key.
> - Old: `min(pred_map, key=lambda t: cost(t))`
> - New: `min(pred_map, key=lambda t: (cost(t), alpha[t]))`
>
> This selects the smallest predicted cost first, then among ties picks lowest α = largest TN. Result: 86/108 → 108/108.
>
> The tie only arises at gc ≥ 300 because that's when TM*=64 crosses fully into gen-bound (gc/TM = 300/64 = 4.69 > α(64,16) = 3.84). Below gc=300 every tile is still A-load bound and costs differ by TN — no tie possible.
>
> The patch was applied to `experiment.py` line 144 in best-fifo-order and line 125 in multi-param-regression.

> **[Note — how the model tile sizes are computed]**
>
> The model is: T/MNK = max( α(TM, TN), g_c/TM )
>
> **Step 1 — build the α table (done once at g_c = 0).**
> Run B-stationary with g_c=0 for every valid (TM, TN) pair. Record T/MNK. That measurement IS α(TM, TN) — no formula assumed. At g_c=0 the FIFO costs nothing, so the only cost left is A-loading from cache/DRAM.
>
> **Step 2 — for each new g_c, evaluate cost over all valid pairs.**
> cost(TM, TN) = max( α(TM, TN), g_c/TM )
> Then: (TM*, TN*) = argmin_{valid (TM,TN)} cost(TM, TN)
>
> **Subject to (what makes a pair "valid"):**
> 1. **L1 working-set constraint** — `TM × TN // 8 + TM // 4 − 2 < 300`
>    The C tile accumulates partial sums across the entire inner loop. `ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2` is the **reuse distance** — line-accesses between two consecutive touches of the same C line — not the C footprint. Terms: 2×(TM×TN/16) for C (load+store per line), TM/4 for A (1 line per sub-tile), −2 for the measured line itself. L1 = 16KB = 256 lines is the true capacity; 300 is a tolerance band, since a small overflow does not measurably hurt α. Examples: (64,32)→ws=270 ✓, α=3.49 normal *(over 256, still fine)*; (96,32)→ws=406 ✗, α=9.03 broken; (48,64)→ws=394 ✗, α=4.39 elevated.
> 2. **FIFO capacity** — `TK × TN ≤ FIFO_CAP`
>    This is a performance constraint, not a correctness one. The FIFO has hardware back-pressure: when full the PRNG pauses, when empty the consumer stalls, so TK×TN > FIFO_CAP still produces correct results. The constraint ensures the PRNG can pre-buffer one complete B block (TK×TN elements) before the MAC loop starts, so the two fully overlap. If FIFO_CAP < TK×TN the FIFO caps mid-fill, the MAC loop eventually stalls waiting for more elements, and the gc/TM cost model becomes less accurate. The experiments stay in the regime where the pre-buffer fits. With TK=256, FIFO_CAP=16384: TN ≤ 64 (TN=64 fills it exactly).
> 3. **Clean tiling** — TM divides M, TN divides N.
>    No partial boundary tiles. With M=192, valid TM ∈ {4,6,8,12,16,24,32,48,64,96}. With N=256, valid TN ∈ {4,8,16,32,64}.
>
> **Worked example — gc = 150:**
>
> | (TM, TN) | α      | g_c/TM | cost = max(α, g_c/TM) | safe? |
> |----------|--------|--------|------------------------|-------|
> | (64, 32) | 3.4849 | 2.344  | **3.485** ← winner     | ✓     |
> | (48, 32) | 3.4959 | 3.125  | 3.496                  | ✓     |
> | (96, 16) | 3.8266 | 1.562  | 3.827                  | ✓     |
> | (32, 64) | 3.3403 | 4.688  | 4.688 (gen-bound)      | ✓     |
> | (96, 32) | 9.033  | 1.562  | 9.033                  | ✗ reg |
> | (48, 64) | 4.3896 | 3.125  | 4.390                  | ✗ reg |
>
> (32,64) has the lowest α but its g_c/TM = 4.69 dominates — it's gen-bound. (64,32) stays A-load bound (g_c/TM=2.34 < α=3.48) and wins.
> Model prediction: (64, 32). Empirical best: (64, 32). ✓

> **[Note — why the L1 working-set constraint exists]**
>
> In B-stationary, the C tile (TM rows × TN columns of partial sums) lives in L1 throughout the entire inner loop. Every iteration of the inner loop loads a small A sub-tile, does a multiply-accumulate into the C sub-tile, and stores it back. The C tile must stay resident in L1 the whole time — if any part of it gets evicted, the next iteration has to reload it from DRAM, paying the full DRAM latency each time.
>
> The formula `ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2` measures the **reuse distance**: line-accesses between two consecutive touches of the same C line (2×TM×TN/16 for C's load+store, TM/4 for A, −2 for the line itself). L1 = 16KB = 256 cache lines of 64 bytes each. Once the reuse distance passes 256, a C line is evicted before you get back to it — and since each C line is touched TK/REG_K = 64 times, every eviction costs a full DRAM round trip.
>
> Why threshold 300 and not 256? 256 *is* the true capacity — 300 is a deliberate tolerance band. A small overflow evicts few enough lines that α does not move measurably; safe() picks 300 to exclude the blowups while keeping harmless borderline tiles. The data shows the band directly:
> - ws=270 → (64,32) → α = 3.49 (normal — note this is already *over* 256 and still fine)
> - ws=406 → (96,32) → α = 9.03 (completely broken — evictions on every inner iteration)
>
> This is why the "unsafe" tile (96,32) appears in the E8 data with an inflated α: it was run without the safe() guard, and its α reflects the eviction penalty, not a model breakdown.

> **[Note — why the FIFO capacity constraint exists]**
>
> In B-stationary, the PRNG generates B elements into the FIFO in the background while the MAC loop computes. The goal is to have the PRNG running ahead of the compute so they fully overlap: by the time the MAC needs the next B element, it's already in the FIFO. This is the source of the "gc/TM in parallel with A-loading" model.
>
> For one B column block (TK rows × TN columns = 256×TN elements in this setup), the PRNG needs to pre-buffer the entire block before the inner A-sweep starts. FIFO_CAP = 16384 elements, so TK×TN = 256×TN ≤ 16384 → TN ≤ 64.
>
> Is this a correctness constraint? **No.** The FIFO has back-pressure: when full the PRNG pauses, when empty the MAC stalls. TK×TN > FIFO_CAP still produces correct results — the FIFO just fills up partway, the MAC starts consuming while the PRNG resumes. The computation completes correctly.
>
> It's a **model accuracy** constraint. If the FIFO can't pre-buffer a full block, the PRNG and MAC partially overlap instead of fully overlap. The simple "both run in parallel, runtime = max(A-load, B-gen)" model becomes less accurate because now there are stall points mid-block. The experiments stay in the full-overlap regime so the model's predictions hold.

> **[Note — what "cycle gap ≤ 4%" means]**
> The cycle gap answers: *if the model picks the "wrong" tile, how much performance do you actually lose?*
> Formally: gap = cycles(predicted tile) / cycles(optimal tile) − 1.
> A gap of 0% means the predicted tile is just as fast as the optimal. A gap of 4% means you run 4% slower than you could.
> In the high-g_c gen-bound regime, many (TM, TN) combinations give the same predicted cost (g_c/TM doesn't depend on TN), so TN* is ambiguous. Even if the model picks a suboptimal TN, all TN choices with the same TM give nearly the same actual cycles — hence the ≤4% bound.

> **[Note — why TN* could degrade at very high g_c]**
> When g_c/TM >> α(TM, TN) for every valid TN, the roofline model collapses to max(α, g_c/TM) ≈ g_c/TM for all TN. Since g_c/TM doesn't depend on TN, the model predicts identical cost for all TN values at the best TM. TN* becomes arbitrary — the model has no information to choose between TN values. In practice, small differences in α(TM, TN) (from cache-line utilization and register pressure) still break the tie correctly at the g_c values we tested, so the model remains 100% accurate. But at sufficiently extreme g_c, this margin could disappear.

---

## Slide 22 — Why TN* Fails at High g_c: Gen-Bound Regime

[This slide — best_shape_per_gc.png — shows TM* and TN* as step functions of g_c.]

> **[Config — best_shape_per_gc.png]**
> Source: `experiments/v5-results/math-model-no-l2/e8-gc-boundary-sweep/results.json` via `plot_all.py:plot_e8_best_shape()`
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, fully associative, no L2. B-stationary. FIFO_CAP=16384 elements.
> gc swept: 15, 30, 38, 42, 47, 50, 52, 57, 68, 74, 100, 150, 250, 400.
> TM range: 8–96. TN range: 4–64. Empirical globally best (TM*,TN*) at each gc — no safe() filter needed; broken tiles naturally lose.

The graph shows the model's globally optimal (TM*, TN*) trajectory as g_c increases. TM* steps up (12 → 32 → 64 → 96) and TN* steps down (32 → 64 → 32 → 16).

> **[Note — the safe() C-tile constraint and why the threshold is 300]**
>
> The constraint is `ws_lines(TM, TN) = TM×TN/8 + TM/4 − 2 < 300`.
>
> **What ws_lines counts — it is a REUSE DISTANCE, not a footprint.** Source: `math-model-no-l2/GUIDE.md:189` — "lines accessed between two C[i,j] accesses". It measures how much other data streams through L1 between one touch of a C line and the next touch of that same line. If more than a cacheful passes by in between, that C line has been evicted when you come back to it.
>
> Setup: REG_M=REG_N=REG_K=4, elements are 4B, lines are 64B → 16 elements/line. L1 = 16KB = **256 lines**.
> The inner loop is rtk → rtj → rti, and C[rti,rtj] is re-touched one full rtk step later. In that interval you sweep every (rtj, rti) pair exactly once, touching:
>
> | Term | What | Derivation |
> |---|---|---|
> | **TM×TN/8** | C | C tile = TM×TN×4B / 64 = TM×TN/16 lines, each touched **twice** (`load C → %rc` … `store C`) → 2 × TM×TN/16 |
> | **TM/4** | A | one A sub-tile = REG_M×REG_K = 4×4 elems × 4B = 64B = **exactly 1 line**; TM/REG_M = TM/4 of them per rtk step, loaded once |
> | **− 2** | self | the C line being measured doesn't count against its own reuse distance — subtract its own load+store |
>
> B contributes nothing: it comes from the PRNG FIFO and bypasses the cache entirely.
>
> The 2× on C is confirmed by `e4-cfill-mechanism/README.md:100`, which tabulates the C footprint separately — at TM=96 it is 24/48/96/192 lines for TN=4/8/16/32, exactly TM×TN/16, i.e. **half** the formula's first term. Check TM=96,TN=32: 2×192 + 24 − 2 = 406 ✓
>
> **Why the threshold is 300 and not 256.** The true capacity is 256 lines (`e-l1size-regime/experiment.py:71` tests `ws_lines >= l1 // LINE`). 300 is a **tolerance band**, not a capacity:
> - WS < 256 — fits, no eviction
> - WS 256–300 — over capacity, but the eviction rate is too small to show in α. **(64,32) → WS=270 > 256 yet α=3.49, perfectly normal.** This is exactly why safe() uses 300, not 256.
> - WS ≥ 300 — catastrophic. (`catastrophic()` uses `L1/LINE + 50`, ">10% over capacity".)
>
> Supporting α data:
> - (64, 32): ws=270 → α=3.49 ✓ normal
> - (96, 32): ws=406 → α=9.03 ✗ broken (C tile evicted on every MAC iteration)
> - (48, 64): ws=394 → α=4.39 ✗ elevated
> - (64, 64): ws=526 → α=8.87 ✗ severely broken
>
> Below ~300 the C tile stays resident; above it, parts get evicted and reloaded on every inner-loop step, blowing up α by 2–3×. Each unique C line is accessed TK/REG_K = 64 times, so an eviction before reuse costs a full DRAM round trip (180 cy) on a line you were about to touch again — that is why the penalty is so violent.
>
> **[If pushed — the known limitation of this formula]**
> ws_lines assumes each C sub-tile sits on 1 cache line. It doesn't: C is row-major with row stride N, so a 4×4 sub-tile spans 4 different rows = 4 lines. `e-l1size-regime/README.md:213` says this outright and gives a corrected formula for the **TM-overflow** regime that ws_lines misses: `(TM/4 − 1)×8 + 4 < L1/LINE` (the 8 = 4 lines for A + 4 for C per rti sub-tile). At L1=16KB every tile in our sweep passes it, so it never bites here. At L1=8KB it does: TM=96 gives 188 > 128 → unusable regardless of TN.

> **[Note — why TM* goes up and TN* goes down as g_c increases — and why TN* goes UP first]**
>
> **TM* goes up:** The model cost is max(α(TM,TN), g_c/TM). The gen-bound term g_c/TM grows with g_c. To stay A-load bound (or minimize gen-cost), we want TM as large as possible. The breakeven is at α ≈ g_c/TM → TM* ≈ g_c/α. As g_c doubles, TM* roughly doubles too.
>
> **Why TN* goes UP from 32 to 64 at the TM*=12→32 transition:**
> At TM*=12, the globally optimal TN is 32 (empirically). When gc increases past ~42 and TM* jumps to 32, the ws_lines constraint is still loose at TM=32: ws_lines(32,64) = 32×64/8 + 32/4 − 2 = 262 < 300. TN=64 is safe, and larger TN always gives lower α (more A-row reuse in L1). So the model picks TN=64 — it's now both feasible and gives the best possible α at TM=32.
>
> **Why TN* then comes back down:**
> As TM* keeps growing, the ws_lines constraint tightens — a fixed TN limit no longer fits:
> - TM*=64: ws_lines(64,64) = 526 > 300 → TN=64 **unsafe** → TN* forced to 32
> - TM*=96: ws_lines(96,32) = 406 > 300 → TN=32 **unsafe** → TN* forced to 16
>
> Max safe TN ≈ 2400/TM (approximately). As TM grows, the maximum affordable TN shrinks. TN* tracks the largest safe option that minimizes α — it can only go up when TM* moves to a "sweet spot" where the constraint is still loose enough.

---

## Slide 23 — Impact of Tile Selection: Numbers

Does choosing the right tile actually matter? The numbers:
- At g_c=100: 20–60% faster depending on TN.
- At g_c=250: ~85% faster.
- At g_c=400: up to 90% faster.

The gain grows with g_c because the generation bottleneck is what the tile shape can most directly control — larger TM amortizes g_c, and the model tells you exactly which TM to use.

> **[Note — per-TN actual numbers if asked]**
> - gc=100: TN=8→64%, TN=16→39%, TN=32→1%, TN=64→62%
> - gc=250: TN=8→85.5%, TN=16→75.6%, TN=32→49.3%, TN=64→40.2%
> - gc=400: TN=8→90.9%, TN=16→83.1%, TN=32→49.6%, TN=64→5.2%
>
> The slide's "20–60%" at gc=100 covers TN=16 (39%) through TN=8 (64%). TN=32 is nearly 0% (square is also DRAM-bound at low gc). TN=64 is 62% because the square tile (TM=64,TN=64) already overflows L1 even without gc pressure.

---

## Slide 24 — Impact of Tile Selection: Graph

The model we built tells you where that optimal shape is, from a single calibration run at g_c=0. Thanks for listening.

> **[Config — optimal_vs_square.png]**
> Source: same `e8-gc-boundary-sweep/results.json` via `plot_all.py:plot_e8_vs_square()`
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, fully associative, no L2. B-stationary. FIFO_CAP=16384 elements.
> Four TN values plotted: 8, 16, 32, 64 (TN=4 excluded). Same gc sweep as slide 24.
> Left panel: cycles/MNK for optimal TM* vs square TM=TN, per (TN, gc). Right panel: speedup %.

> **[Note — why TN=64 (red line) is flat in performance and its SPEEDUP drops at high gc]**
>
> Left panel: Square tile (TM=64, TN=64) has C-tile size = 64×64×4B = 16384B = L1 capacity exactly. It saturates L1 completely. Every new K-iteration evicts the current A row from L1 and reloads it from DRAM. Cost ≈ 8.9 cycles, constant regardless of gc — the square tile is perpetually A-load bound.
>
> The optimal tile for TN=64 starts at TM=32 (cost ≈ 3.3 cycles) and only grows to TM=48 at high gc. It can't grow beyond TM=48 because of the register constraint: safe(48,64)=394>300 (already over the limit), safe(64,64)=526>300. So the "optimal" for TN=64 is really capped at TM≤48.
>
> Right panel (speedup): At low gc the gap is large (3.3 vs 8.9 → 62% speedup) because the square's L1-overflow penalty is huge. As gc rises, the best-TN64 tile (TM=48) becomes gen-bound: cost = gc/48. At gc=400, cost = 400/48 ≈ 8.3, which is almost the same as the square's 8.9. The speedup collapses to ~5%.
>
> **Key takeaway: TN=64 is a trap at high gc.** You start with a 62% speedup "for free" (just by not overflowing L1), but then you can't amortize the growing gen-cost because register constraints cap your TM. The gap closes and TN=64 performs nearly as badly as the square.

> **[Note — the dips and cliffs: data-driven explanation per TN line]**
>
> **TN=8 (green) — starts near 0%, jumps at gc≈27, then keeps climbing:**
>
> At gc=15: square (TM=8) α=3.41, optimal (TM=12) α=3.32. Only 2.6% gap — both are memory-bound with nearly the same α.
> The square (TM=8) goes gen-bound when gc/8 > α(8,8) ≈ 3.41 → at gc≈27. After that the square's cost rises as gc/8. The optimal (TM=12) stays memory-bound until gc≈40. The gap opens fast — that's the jump.
> At gc=38: square=4.87, optimal=3.34 → 31.5%. At gc=250: square=31.3, optimal=4.55 → 85.5%.
>
> **TN=16 (orange) — the dip at gc=42-57 (from 16% down to 3%, then climbs):**
>
> This is a regime hand-off, not a cliff. Here's what happens step by step (all measured values):
>
> | gc | optimal TM | optimal α | square (TM=16) α | speedup |
> |---|---|---|---|---|
> | 15–38 | **12** | 3.33 | 3.94 | **16%** |
> | 42    | 12 | 3.64 | 3.94 | 7.8% |
> | 47–57 | **96** | 3.83 | 3.94 | **3%** |
> | 68+   | 96 | 3.83 | rising (gen-bound) | climbing |
>
> At gc<42: TM=12 wins because its A tile (12×256×4B = 12KB) fits in L1 → very low α=3.33. The square (TM=16) is right at the L1 cliff (A tile = 16KB = exactly L1) → α=3.94. That 16% gap is the L1 residency advantage.
>
> At gc≈42: TM=12 crosses gen-bound (gc/12=3.5 ≈ α(12)=3.33). Cost rises to 3.64. Still beats TM=96 (3.83) at gc=42, but just barely.
>
> At gc≈47: TM=12 fully gen-bound (cost=4.03 > TM=96's 3.83). Optimal switches to TM=96 — but TM=96 in the DRAM regime gives α=3.83, which is only 3% better than the square's 3.94. Speedup collapses.
>
> At gc≥68: the square (TM=16) goes gen-bound (gc/16 > 3.94 at gc≈63). Square cost rises fast. TM=96 stays memory-bound (gen-bound only at gc = 96×3.83 ≈ 368). Gap opens again.
>
> The dip is because the L1 advantage of TM=12 disappears at gc≈42, and the next best option (TM=96 in DRAM regime) is very close to the square in absolute performance.
>
> **TN=32 (blue) — flat ~0% until gc≈100, then steps to 50% and stays:**
>
> Square (TM=32, TN=32): ws=134, α≈3.50. Optimal: TM=64, α≈3.49 (almost identical at low gc). Tiny speedup until the square goes gen-bound at gc ≈ 32×3.50 = 112.
> After that: square cost = gc/32 (rising). Optimal (TM=64) gen-bound at gc ≈ 64×3.49 = 223. After both are gen-bound: cost ratio = (gc/32)/(gc/64) = 2. Speedup = 50%. Flat forever. The 2× TM ratio is the permanent advantage.

---
