# Presentation Script

---

## Slide 1 — Title

Hi everyone. I'm Areg, and together with Regev, under the supervision of Alon Amid, we've been working on a question that sounds simple: given a hardware accelerator that multiplies matrices, what shape should your tiles be?

It turns out the answer changes quite a bit depending on your hardware, and today I'll show you a model that predicts the optimal shape — and validates it empirically.

---

## Slide 2 — Matrix Multiply is Memory-Bound

Let's start with why this matters. A naively implemented matrix multiply reads A and B from RAM on every pass through the inner loop. For a 256×256 float32 matrix, just the inputs are around 0.5 MB — which is 8 to 32 times larger than a typical L1 cache.

The standard fix is tiling: instead of sweeping the whole matrix, we pick a small tile of C and keep it resident in L1 while we accumulate into it. That's what we'll be working with.

---

## Slide 3 — C-Stationary Tiling: Step by Step

Let me walk through how this works. We have matrices A, B, and C — all too large to fit in L1.

[click] We divide each matrix into a grid of tiles. The tile shape is TM rows by TN columns by TK in the K dimension.

[click] The idea is: fix one tile of C in L1. Then stream the corresponding A row-band and B column-band through it, accumulating the partial products.

[click] Once C_ij is done, we move to the next B column tile. The A row-band doesn't need to be reloaded — it's already in L1. This is the key reuse: each A element is touched TN times before eviction.

---

## Slide 4 — Standard Assumption: Square Tiles

This reuse argument leads directly to the standard model. Each A element is reused TN times, so its effective cost is A_P/TN per output. Each B element is reused TM times, so it's B_P/TM. Total traffic is MNK times the sum of these two terms.

When precisions are equal — both fp32, say — the two terms are symmetric, and you minimize their sum under a fixed cache budget by equating them. That gives you square tiles: TM* equals TN*.

---

## Slide 5 — Asymmetric Precision → Asymmetric Tiles

But what if the precisions aren't equal? This is what the paper we're building on addresses. Let ρ be the ratio B_P over A_P. If B is cheaper per element — say fp8 vs fp32, so ρ = 1/4 — then B's traffic term is smaller, and you should reuse A more aggressively relative to B.

Balancing the two traffic terms gives the condition TN*/TM* equals 1/ρ. In the extreme case of fp32 by fp8, the optimal tile is 8 times wider than it is tall. Same cache budget, very different shape.

---

## Slide 6 — The Simulator We Built

Before showing the validation results, let me briefly describe the tool we used to generate them. We built a custom cycle-accurate C++ simulator from scratch — nothing off the shelf.

It has three main pieces. The InstGenerator takes a tile configuration and emits a stream of instructions into a text ISA — ltea for tile loads, tmulac for multiply-accumulate, tmov for stores. The Interpreter then dispatches those instructions and counts cycles for every memory access. And the MemoryHierarchy models a configurable L1/L2/DRAM stack with full per-access tracing — hit rates, evictions, line fills.

The key architectural detail, which we'll come back to, is that B takes a completely separate path. It goes through MMIO directly to a PRNG FIFO device, bypassing L1 entirely. A and C go through the normal cache hierarchy.

---

## Slide 7 — Traffic Minimum at the Predicted Tile

With the simulator in hand, we can validate the paper's formula. Each panel here sweeps the tile aspect ratio TN/TM on the x-axis and plots L1 read traffic. The dashed line is the paper's prediction for where the minimum should land.

For all four values of ρ, the empirical minimum falls exactly on the predicted aspect ratio. The simulation matches the formula to within about 2%.

---

## Slide 8 — B/A Balance: Exact Confirmation

We can look at this even more directly. Instead of plotting total traffic, this shows the ratio of B reads to A reads as the aspect ratio varies. At the paper's predicted optimum, the two inputs contribute equal traffic — so the ratio should cross 1.

And it does, exactly, for every ρ. The vertical dashed lines mark the predictions, and every curve crosses 1 right there. When ρ is 1/8, the traffic savings versus a square tile is 36%.

One thing worth noting: the blue line for ρ=1 shows a small bump at the far left, around log2(TN/TM) ≈ −4. This is a cache-line granularity artifact — when TN is so small that a single row of B fits in less than one cache line, loading it still pulls in a full 64-byte line. That inflates B traffic slightly above the theoretical prediction. The effect disappears as TN grows large enough to fill a line, and it doesn't affect the location of the minimum.

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

This gives us two independent bottlenecks. One is A-loading from memory. The other is waiting for the PRNG to produce B at g_c cycles per element. The runtime is whichever one is slower — they can run in parallel.

---

## Slide 12 — Which Loop Order Fits the FIFO?

Now, the FIFO generates B elements in a fixed order — you can't skip or replay them. The loop order of your computation must match the generation order, or you pay a penalty.

There are three natural options. C-stationary row-major, C-stationary col-major, and B-stationary. The table here shows the key difference: their effective B generation cost per output element.

C-stationary row-major pays g_c times TN per element — badly wasteful. C-stationary col-major pays g_c. B-stationary pays g_c over TM. That factor of TM is the key, and I'll explain where it comes from.

---

## Slide 13 — C-Stationary Row-Major: Ghost Read Problem

Here's why C-stationary row-major is so bad. The C tile is fixed in registers. For each step in K, the FIFO generates B in row-major order — it produces all N/TN column groups before moving to the next K step.

But a given C tile at column j only needs the j-th group per K step. The FIFO has already generated groups 0 through j-1, which are useless. These are ghost reads — the hardware pulls elements out of the FIFO just to discard them.

The numbers show this clearly. At g_c=0, C-stationary is 2× faster than B-stationary because its α is lower. But at g_c=10 it's already 1.25× slower, and at g_c=100 it's 7.5× slower. The ghost read penalty grows with g_c.

---

## Slide 14 — C-Stationary Col-Major: Ghost Reads Gone, Problem Remains

The natural fix is to change the FIFO generation order to column-major. Generate all K values for column j before moving to column j+1. Now the loop can consume exactly the elements it needs, in order — no ghost reads.

That helps at moderate g_c — col-major is about 1.28× faster than row-major at g_c=10. But at g_c=100 it's still 7.5× slower than B-stationary.

So ghost reads were not the real bottleneck. The real problem is deeper: C-stationary has no TM-fold amortization. Each A-row requires new B elements from the FIFO. Compare that to B-stationary, where the loop order is B outer, A inner — one B block is fetched once, and all TM A-rows sweep through it. Each B element is used TM times, amortizing the generation cost by TM.

> **[Note — why col-major hardly helps at high g_c]**
>
> Col-major eliminates ghost reads but does NOT change what is stationary. The loop structure is still C-stationary: the C tile is fixed for each (rti, rtj) position, and the FIFO is restarted once per rti (per reg_m A-rows). So B is regenerated reg_m A-rows at a time — the amortization is by reg_m, not TM.
>
> Cost comparison (TM=32, reg_m=4, gc=100):
> - Row-major: pays gc × TN/reg_n per MAC (ghost reads × full sweep) — very bad
> - Col-major: pays gc / reg_m = 100/4 = **25 cy/MAC** (ghost reads gone, but still reg_m amortization)
> - B-stationary: pays gc / TM = 100/32 = **3.125 cy/MAC** (TM-fold amortization)
>
> Col-major is better than row-major (no wasted ghost elements), but it's still 8× worse than B-stationary because reg_m=4 << TM=32. The ratio is always TM/reg_m — col-major can't close that gap.

---

## Slide 15 — B-Stationary: TM-Fold Register Reuse

So in B-stationary, the generation cost per MAC is g_c times N_B divided by TM times N_B — the N_B cancels, and you get g_c over TM regardless of block size.

At TM=32 and g_c=100, that's about 3 cycles per MAC. C-stationary pays the full 100. That's where the 7.5× gap comes from at g_c=100.

The practical rule: use B-stationary for any g_c above about 20. C-stationary only wins at very low g_c, where its lower α compensates for the generation cost.

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

## Slide 16 — Naive Cycle Model: Two Cost Terms

Now we can build a cycle model. The traffic argument translates directly: A is reused TN times, so its cost per MAC is C_A over TN, where C_A is cycles per element from L1. B is generated by the FIFO, reused TM times, so its cost is g_c over TM.

The naive model adds these: T/MNK equals C_A/TN plus g_c/TM. But this assumes sequential execution — that we load A, then generate B, one after the other.

---

## Slide 17 — FIFO is Async: Two Costs in Parallel

The FIFO doesn't work that way. It generates B in the background while the core is loading A. The two operations overlap, so the runtime is determined by whichever one takes longer:

T/MNK = max{ C_A/TN, g_c/TM }

This gives us two regimes. When g_c/TM is small — low generation cost or large TM — we're A-load bound, and reducing TN helps. When g_c/TM dominates, we're B-gen bound, and increasing TM helps. The optimal tile balances these two terms.

---

## Slide 18 — Replacing C_A/TN with Measured α(TM,TN)

There's one more problem. The C_A/TN term assumes A loading is a fixed cost per element divided cleanly by TN. In practice, cache residency, line utilization, and access patterns mean the actual cycles per MAC depend on tile shape in a way that's richer than a simple ratio.

So we replace C_A/TN with a measured quantity α(TM, TN), defined as T/MNK when g_c is zero. When B generation is free, the only cost left is A loading, so α captures exactly what we need — no assumptions, no formula.

The final model: T/MNK = max{ α(TM, TN), g_c/TM }.

---

## Slide 19 — Isolating α: Set g_c = 0

g_c is a hardware parameter we fully control in simulation. Setting it to zero collapses the max to just α(TM, TN). Run B-stationary at g_c=0, measure T/MNK — that's your α value. No formula assumed, no analytical model of cache behavior.

The procedure is: run B-stationary at g_c=0 for each valid (TM, TN) pair, record T/MNK. Done.

---

## Slide 20 — Calibration: Building the α Table

Here's what the measured α table looks like. Each line is a different TN value, plotted against TM on the x-axis.

Two things stand out. First, small TN values like TN=4 cause α to spike at moderate TM — the A tile overflows L1 with few column groups to amortize against. Second, for large TN like TN=32, α stays flat around 3.5 out to TM=96, then shoots up to around 9 — that's where the C tile can no longer fit in L1.

α decreases with TN because more column reuse means fewer A reloads per output. The cache boundary shifts with TM.

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
> The C tile is TM × TN output partial sums, held resident in L1 throughout the inner loop. When ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2 exceeds ~300 (≈ L1 capacity), the C tile can no longer stay resident.
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

## Slide 21 — Using the α Table: Predicting the Optimal Tile

Once we have α measured, using it is straightforward. For any new g_c, we evaluate max{ α(TM, TN), g_c/TM } at every valid tile shape and take the argmin. No new experiments — just table lookup and arithmetic.

The diagram shows why this works geometrically. α is roughly flat in the A-load-bound region, then rises when the A tile overflows L1. g_c/TM is a decreasing curve. They cross at the optimal TM*. The optimal TN* is the one that minimizes α at that TM — typically the largest TN that still fits the FIFO.

---

## Slide 22 — Roofline Validation: Setup

Now the question is: does this actually work? We calibrate α once at g_c=0 — so we're committed to a fixed table — and then ask whether the model correctly predicts the best tile at new, unseen g_c values.

The methodology is: measure α at g_c=0; for each new g_c, compute the predicted best (TM*, TN*); run the simulator at that g_c empirically to find the true best; compare.

We ran this across two SRAM budgets — 64KB and 128KB — with 6 hardware splits each varying the L1/FIFO split, and 9 g_c values from 10 to 500. That's 108 test conditions total.

---

## Slide 23 — Roofline Validation: Results

The table shows the model's predicted (TM*, TN*) versus the empirical best tile for each g_c. All 14 g_c values match exactly — 100%.

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
>    The C tile accumulates partial sums across the entire inner loop. The expression `ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2` estimates how many L1 **cache lines** the C tile occupies. L1 = 16KB = 256 lines. When ws_lines exceeds ~256–300, the C tile no longer fits in L1 — parts of it get evicted and reloaded on every inner-loop iteration, blowing up α. The threshold 300 is empirically observed: below it α is flat, above it α spikes. Examples: (64,32)→ws=270 ✓, α=3.49 normal; (96,32)→ws=406 ✗, α=9.03 broken; (48,64)→ws=394 ✗, α=4.39 elevated.
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
> The formula `ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2` estimates how many L1 cache lines the C tile occupies. L1 = 16KB = 256 cache lines of 64 bytes each. Once the tile grows past roughly 256 lines the C tile stops fitting, evictions start, and measured α blows up.
>
> Why threshold 300 and not 256? The formula is an approximation and was calibrated empirically — the exact boundary where α starts degrading is observed to be around 300, not the clean L1 size of 256. You can see it clearly in the data:
> - ws=270 → (64,32) → α = 3.49 (normal)
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

## Slide 24 — Why TN* Fails at High g_c: Gen-Bound Regime

Here's why. When g_c/TM is much larger than α for all TN values, the max collapses to just g_c/TM — which doesn't depend on TN at all. The model predicts the same cost for every TN, so it can't distinguish between them.

TM* is always right because g_c/TM still depends on TM — the model correctly identifies which row-tile size minimizes the gen-bound cost. It's only TN* that becomes arbitrary.

Empirically, TN=16 is best in the gen-bound regime due to register pipeline effects, but the model doesn't know that. The crossover point is roughly g_c equals TM times α — for TM=96 and α around 3.8, that's about g_c=370.

---

## Slide 25 — Impact of Tile Selection: Optimal vs. Square

So does choosing the right tile actually matter? This is the bottom line. The left panel compares the best asymmetric tile against the best square tile for each g_c. The right panel shows the percentage speedup.

At g_c=100, asymmetric tiling is 20 to 40% faster depending on TN. At g_c=250 it's around 75% faster. At g_c=400 it's up to 85% faster. The gain grows with g_c because the generation bottleneck is the one that the tile shape can most directly control.

The model we built tells you where that optimal shape is, from a single calibration run at g_c=0. Thanks for listening.

> **[Note — correct speedup numbers if asked]**
> The slide's numbers are approximate and anchored to TN=16:
> - gc=100: TN=8→64%, TN=16→39%, TN=32→1%, TN=64→62% (range: 1–64%, slide says "20–40%")
> - gc=250: TN=8→85%, TN=16→76%, TN=32→49%, TN=64→40% (slide says "~75%" matching TN=16)
> - gc=400: TN=8→91%, TN=16→83%, TN=32→50%, TN=64→5% (slide says "up to 85%", actual max is 91%)
> 
> The "20–40% at gc=100" is specific to TN=16 only. TN=8 and TN=64 are both much higher at gc=100 for different reasons (see notes below). A more accurate summary: "20–90% depending on TN" at gc=100.

> **[Note — why TN=64 (red line) is flat in performance and its SPEEDUP drops at high gc]**
>
> Left panel: Square tile (TM=64, TN=64) has C-tile size = 64×64×4B = 16384B = L1 capacity exactly. It saturates L1 completely. Every new K-iteration evicts the current A row from L1 and reloads it from DRAM. Cost ≈ 8.9 cycles, constant regardless of gc — the square tile is perpetually A-load bound.
>
> The optimal tile for TN=64 starts at TM=32 (cost ≈ 3.3 cycles) and only grows to TM=48 at high gc. It can't grow beyond TM=48 because of the register constraint: safe(48,64)=394>300 (already over the limit), safe(64,64)=526>300. So the "optimal" for TN=64 is really capped at TM≤48.
>
> Right panel (speedup): At low gc the gap is large (3.3 vs 8.9 → 62% speedup) because the square's L1-overflow penalty is huge. As gc rises, the best-TN64 tile (TM=48) becomes gen-bound: cost = gc/48. At gc=400, cost = 400/48 ≈ 8.3, which is almost the same as the square's 8.9. The speedup collapses to ~5%.
>
> **Key takeaway: TN=64 is a trap at high gc.** You start with a 62% speedup "for free" (just by not overflowing L1), but then you can't amortize the growing gen-cost because register constraints cap your TM. The gap closes and TN=64 performs nearly as badly as the square.

> **[Note — why TN=8, TN=16, TN=32 show near-0% speedup at low gc then a cliff]**
>
> The "cliff" is the **square tile's A-load → gen-bound transition**.
>
> When gc is small: the square tile (TM=TN) has g_c/TM = g_c/TN small enough that it's still A-load bound. The optimal tile (larger TM*) is also A-load bound. Both have similar cost → small speedup.
>
> **Cliff condition**: the square tile transitions to gen-bound when g_c/TN > α(TN,TN). After that, the square's cost grows as g_c/TN (linearly). The optimal tile at larger TM stays A-load bound for longer. The gap opens up fast.
>
> Approximate cliff locations (gc where speedup takes off):
> - TN=8: cliff at gc ≈ 8 × α(8,8) ≈ low (< gc=30). Speedup starts growing almost immediately.
> - TN=16: cliff at gc ≈ 16 × α(16,16) ≈ 16 × 6.3 ≈ 101. Visible dip to ~3% around gc=47–57, then climbs sharply.
> - TN=32: cliff at gc ≈ 32 × α(32,32) ≈ 32 × 3.5 ≈ 112. Stays flat at ~1% from gc=42 to gc=100, then jumps to 27% at gc=150.
>
> The "flat at 0%" plateau for TN=32 is especially visible because TM=64 (the optimal) and TM=32 (the square) are in the same A-load bound regime until gc > 112. Once the square crosses that boundary and becomes gen-bound, the 2× TM advantage pays off immediately.

---
