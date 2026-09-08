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

## Slide 5 — The Simulator We Built

Before showing the validation results, let me briefly describe the tool we used to generate them. We built a custom cycle-accurate C++ simulator from scratch — nothing off the shelf.

It has three main pieces. The InstGenerator takes a tile configuration and emits a stream of instructions into a text ISA — ltea for tile loads, tmulac for multiply-accumulate, tmov for stores. The Interpreter then dispatches those instructions and counts cycles for every memory access. And the MemoryHierarchy models a configurable L1/L2/DRAM stack with full per-access tracing — hit rates, evictions, line fills.

The key architectural detail, which we'll come back to, is that B takes a completely separate path. It goes through MMIO directly to a PRNG FIFO device, bypassing L1 entirely. A and C go through the normal cache hierarchy.

---

## Slide 6 — Traffic Minimum at the Predicted Tile

With the simulator in hand, we can validate the paper's formula. Each panel here sweeps the tile aspect ratio TN/TM on the x-axis and plots L1 read traffic. The dashed line is the paper's prediction for where the minimum should land.

For all four values of ρ, the empirical minimum falls exactly on the predicted aspect ratio. The simulation matches the formula to within about 2%.

> **[Config — fa_reads.png]**
> Source: `experiments/v5-results/paper-model/paper-traffic-model/`
> M=N=K=256, A_P=8B (fp64), B_P varies by ρ: 8B(ρ=1), 4B(ρ=0.5), 2B(ρ=0.25), 1B(ρ=0.125)
> L1=16KB, fully associative, no L2. C-stationary, B from memory (no FIFO).
> x-axis: log2(TN/TM) at constant tile area (TM×TN fixed word count).

---

## Slide 7 — B/A Balance: Exact Confirmation

We can look at this even more directly. Instead of plotting total traffic, this shows the ratio of B reads to A reads as the aspect ratio varies. At the paper's predicted optimum, the two inputs contribute equal traffic — so the ratio should cross 1.

And it does, exactly, for every ρ. The vertical dashed lines mark the predictions, and every curve crosses 1 right there. When ρ is 1/8, the traffic savings versus a square tile is 36%.

One thing worth noting: the blue line for ρ=1 shows a small bump at the far left, around log2(TN/TM) ≈ −4. This is a cache-line granularity artifact — when TN is so small that a single row of B fits in less than one cache line, loading it still pulls in a full 64-byte line. That inflates B traffic slightly above the theoretical prediction. The effect disappears as TN grows large enough to fill a line, and it doesn't affect the location of the minimum.

> **[Config — fa_balance.png]**
> Source: `experiments/v5-results/paper-model/paper-per-matrix-balance/`
> M=N=K=128, A_P=8B (fp64), B_P varies by ρ: same four values as slide 6.
> L1=16KB, fully associative, no L2. C-stationary, B from memory (no FIFO).
> Note: different matrix size from slide 6 (128 vs 256) — same hardware setup.

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

## Slide 8 — Traffic ≠ Time

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

## Slide 9 — Enter the PRNG FIFO

This is the PRNG FIFO. B elements are generated on-chip by a random number generator and streamed directly into the compute unit. B never touches the cache. B has no memory address.

This completely changes the model. The B_P/TM traffic term simply vanishes — there are no B cache misses to count. Instead, B introduces a new cost: on-chip generation time, g_c cycles per element. Our model must account for g_c, not B_P.

---

## Slide 10 — The PRNG FIFO: B Without Memory

Here's what the hardware looks like. A comes through the normal memory hierarchy — DRAM, L2, L1, registers. B takes a completely separate path: the PRNG generates it, the FIFO buffers it, and it goes straight to the MAC unit, bypassing the cache entirely.

Two independent bottlenecks: A-loading from memory, and waiting for the PRNG at g_c cycles per element.

---

## Slide 11 — Runtime = ?

[Pause. Let the question land.]

---

## Slide 12 — Runtime = whichever is slower

They run in parallel. The runtime is determined by whichever finishes last: A-loading or B-generation. This is the key insight the whole model rests on.

---

## Slide 13 — Which Loop Order Fits the FIFO?

Now, the FIFO generates B elements in a fixed order — you can't skip or replay them. The loop order of your computation must match the generation order, or you pay a penalty.

There are three natural options. C-stationary row-major, C-stationary col-major, and B-stationary. The table here shows the key difference: their effective B generation cost per output element.

C-stationary row-major pays g_c times TN per element — badly wasteful. C-stationary col-major pays g_c. B-stationary pays g_c over TM. That factor of TM is the key, and I'll explain where it comes from.

---

## Slide 14 — B-Stationary: TM-Fold Register Reuse

Loop order: B outer, A inner. One B block is fetched once, then all TM A-rows sweep through it. Each B element is reused TM times — generation cost amortized to g_c/TM per MAC.

The table on the slide shows the numbers directly. At g_c=0, C-stationary col-major is about 1.9× faster than B-stationary — it has a lower α and pays nothing for B. But that advantage is gone by g_c=10, and by g_c=100 it is 7.7× *slower*. Row-major is worse still: already slower than B-stationary at g_c=0, and 61× slower at g_c=100. The crossover happens fast because the amortization penalty scales linearly with g_c.

> **[Note — the measured numbers, TM=32, TN=32]**
> Source: `v55-results/b-stationry-vs-c-stationary/` and `.../b-stationary-vs-c-stationry-col-major/`, cycles/MNK.
>
> | mode | gen cost / MAC | g_c=0 | g_c=10 | g_c=100 |
> |---|---|---|---|---|
> | **B-stationary** | `g_c/TM` = g_c/32 | 3.203 | 3.203 | **3.263** |
> | C col-major | `g_c/reg_m` = g_c/4 | 1.672 | 2.572 | 25.07 |
> | C row-major | `g_c·TN/(reg_n·reg_m)` = 2·g_c | 5.174 | 20.10 | 200.1 |
>
> Relative to B-stationary: col-major is 1.9× faster / 1.25× faster / **7.7× slower**; row-major is 1.6× slower / 6.3× slower / **61× slower**.
>
> The formulas are exact — check: col-major at g_c=100 → 100/4 = 25 (measured 25.07); row-major → 100×32/16 = 200 (measured 200.1); B-stat → 100/32 = 3.1 but α=3.2 dominates, so it stays memory-bound at 3.263.
>
> **⚠ If asked about g_c=0:** col-major genuinely beats B-stationary there (1.672 vs 3.203). It has no ghost reads *and* a better C-access pattern. B-stationary's whole case rests on g_c > 0 — which is the regime this hardware actually operates in.

> **[Note — why B-stationary wins by such a large margin]**
>
> The fundamental difference is what the inner loop sweeps over:
> - **C-stationary**: C tile is fixed. Inner loop generates new B for each rti (reg_m A-rows). B amortized over **reg_m = 4** rows.
> - **B-stationary**: ONE B register sub-tile is fixed in %rb. Inner loop sweeps ALL TM/reg_m A sub-tiles through it. B amortized over **TM = 32** rows.
>
> Since TM ≫ reg_m, B-stationary reuses each B element 8× more at TM=32. Row-major is worse than col-major by a further factor of TN/reg_n = 8, because it consumes the whole B tile per C sub-tile and discards all but one column group (ghost reads).
>
> The TM-fold amortization is the entire point. It doesn't matter how large the B block is — the N_B factor cancels in both numerator and denominator. What matters is how many A-rows share each B element: reg_m in C-stationary, TM in B-stationary.

---

## Slide 15 — Naive Cycle Model: Two Cost Terms

Now we can build a cycle model. The traffic argument translates directly: A is reused TN times, so its cost per MAC is C_A over TN, where C_A is cycles per element from L1. B is generated by the FIFO, reused TM times, so its cost is g_c over TM.

The naive model adds these: T/MNK equals C_A/TN plus g_c/TM. But this assumes sequential execution — that we load A, then generate B, one after the other.

---

## Slide 16 — FIFO is Async: Two Costs in Parallel

The FIFO doesn't work that way. It generates B in the background while the core is loading A. The two operations overlap, so the runtime is determined by whichever one takes longer:

T/MNK = max{ C_A/TN, g_c/TM }

This gives us two regimes. When g_c/TM is small — low generation cost or large TM — we're A-load bound, and reducing TN helps. When g_c/TM dominates, we're B-gen bound, and increasing TM helps. The optimal tile balances these two terms.

> **[Note — `g_c* = TM × α`, the one formula behind every number in this talk]**
>
> A tile flips memory-bound → gen-bound exactly where the two terms are equal:
> ```
> α = g_c/TM   →   g_c* = TM × α
> ```
> Below `g_c*` the PRNG finishes before the core does, so generation is **completely hidden and costs nothing**. Above it the core stalls waiting for B. Think of `TM × α` as the tile's **g_c budget** — how much generation cost it can swallow unnoticed.
>
> Worked, TM=12 with α=3.32 (budget = 40):
> ```
> g_c=24 → PRNG 24/12 = 2.00/MAC < 3.32   fully hidden, cost 3.32 (same as g_c=0)
> g_c=40 → PRNG 40/12 = 3.33/MAC ≈ 3.32   exactly saturated ← the budget
> g_c=60 → PRNG 60/12 = 5.00/MAC > 3.32   exposed, cost 5.00 (waiting 1.68/MAC)
> ```
> Bigger TM buys a bigger budget via the TM-fold reuse: TM=96 with α=4.53 hides g_c up to **435**, ~11× more than TM=12 — even though its α is *worse*. That trade (cheaper tile vs. more g_c-tolerant tile) is the entire story of why TM* rises with g_c.

> **[Note — gen-bound is a real stall, not a modelling abstraction]**
> The simulator counts it. TM=12, TN=8 (α=3.315, so g_c*=40) — `prng_fifo.stall_cycles`:
>
> | g_c | g_c/TM | vs α | cost | FIFO stall cycles |
> |---|---|---|---|---|
> | 38 | 3.17 | core slower | 3.338 | 294,912 |
> | **42** | **3.50** | **PRNG slower** | **3.661** | **4,359,168** ← 15× jump |
> | 400 | 33.33 | PRNG slower | 33.453 | 379,223,864 |
>
> Below `g_c*` the small residual stalls are just FIFO startup priming. The moment `g_c/TM` passes α the stalls explode and cost tracks `g_c/TM` almost exactly (400/12 = 33.33 vs 33.453 measured). "Gen-bound" literally means the MAC unit is idle waiting on the random number generator.

---

## Slide 17 — Replacing C_A/TN with Measured α(TM,TN)

There's one more problem. The C_A/TN term assumes A loading is a fixed cost per element divided cleanly by TN. In practice, cache residency, line utilization, and access patterns mean the actual cycles per MAC depend on tile shape in a way that's richer than a simple ratio.

So we replace C_A/TN with a measured quantity α(TM, TN), defined as T/MNK when g_c is zero. When B generation is free, the only cost left is A loading, so α captures exactly what we need — no assumptions, no formula.

The final model: T/MNK = max{ α(TM, TN), g_c/TM }.

---

## Slide 18 — Isolating α: Set g_c = 0

g_c is a hardware parameter we fully control in simulation. Setting it to zero collapses the max to just α(TM, TN). Run B-stationary at g_c=0, measure T/MNK — that's your α value. No formula assumed, no analytical model of cache behavior.

The procedure is: run B-stationary at g_c=0 for each valid (TM, TN) pair, record T/MNK. Done.

---

## Slide 19 — Calibration: Building the α Table

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
> **Why the plateau is flat in TM — the TM cancellation.** Total A traffic is `M·N·K/(16·TN)`, with **no TM in it**. Intuition: you always read the *whole A matrix* once per output column block; TM only decides how that matrix is *sliced*, not how much data it is.
> - TM=16: 12 row-blocks × 256 lines = 3,072 lines (the whole of A)
> - TM=96: 2 row-blocks × 1,536 lines = 3,072 lines (the whole of A)
>
> Verified in `l1.line_fills` at TN=16: the A tile grows **6×** from TM=16→96 while total fills stay flat (49,344 → 49,184; predicted 49,152). The gentle downward drift in α (3.934 → 3.827 ≈ 0.10) is *not* traffic — fills move only 0.3% — it is the `2.0/TM` FIFO-read term (see slide 20 note).
>
> **Why the cliff height depends on TN.** A's index in `instgen.cpp:162` contains no `tj`, but `tj` is an outer loop — so for each `ti` the entire A tile is re-traversed **once per output column block**, i.e. `N/TN` times (64/32/16/8/4 for TN=4/8/16/32/64).
> - A fits in L1 → 1 DRAM read of A, the other `N/TN − 1` sweeps hit L1
> - A evicted → all `N/TN` sweeps go to DRAM
>
> So the cliff is a jump from 1 to `N/TN` DRAM reads → penalty `176/(16·TN) = 11.3/TN`. Measured jumps (TM 12→16): TN=4 → **+2.74** (predicted 2.75 — one *fully un-amortized* miss, 176/64 MACs, since TN=4 gives exactly one `rtj` pass), TN=8 → +1.33, TN=16 → +0.62, TN=32 → +0.27, TN=64 → ~0.
>
> Confirmed in `line_fills`: at TM=12 they are ~6,200 **flat across all TN**; at TM=16 they scale as `N/TN` (200,448 / 101,760 / 52,416 / 27,744 / 15,408). Net of the constant ~3,072-line C floor, the A-only ratio is **exactly N/TN**: 62, 31, 16, 8.
>
> **Second cliff (big, at high TM): C-tile overflows L1.**
> The C tile is TM × TN output partial sums, held resident in L1 throughout the inner loop. ws_lines(TM,TN) = TM×TN/8 + TM/4 − 2 is the **reuse distance**: how many line-accesses happen between two consecutive touches of the same C line. L1 holds 256 lines; once the reuse distance exceeds that, C lines are evicted before they are reused. (Full derivation in the slide 23 note; 300 is a tolerance band above the true 256 capacity.)
> - TN=32: cliff at TM=96, ws=406 → α jumps from 3.48 to 9.03
> - TN=64: cliff at TM=48, ws=394 → α jumps from 3.34 to 4.39, then at TM=64 (ws=526) → 8.87
> - TN=8, TN=16: ws stays below 300 at all tested TM → NO second cliff visible
>
> **Why the second cliff costs ~5.6 cycles/MAC** (do *not* say "every MAC pays 2× DRAM latency" — that would give α≈360, not 9). Eviction happens once per C sub-tile per `rtk` boundary, not per MAC:
> - `rtk` boundaries per block: K/reg_k = 64
> - C sub-tiles: (TM/4)(TN/4) = TM·TN/16
> - each eviction costs a dirty writeback + a write-allocate refill = 2 × 180 = 360 cy
>
> `64 × (TM·TN/16) × 360 / (TM·TN·256)` = **5.6 cy/MAC** — and **TM and TN cancel**, so every broken tile lands at the same place: 3.4 + 5.6 ≈ **9.0**. That is exactly what the data shows — (96,32)→9.03, (64,64)→8.87, (96,64)→8.88, despite very different shapes.
>
> **Summary of the three regimes:**
> 1. **L1 regime** (TM ≤ 12): A fits in L1, all TN lines cluster near α ≈ 3.3
> 2. **DRAM-A regime** (16 ≤ TM ≤ ~64): A from DRAM, C still in L1. α ≈ flat per TN (lower TN = higher α)
> 3. **DRAM-AC regime** (TM large, TN large): both A and C from DRAM. α → ~9

> **[Note — the whole α surface in one formula]**
>
> ```
> α(TM, TN) ≈ 3.10  +  2.0/TM   +  11.3/TN · [A tile > L1]
>              floor   FIFO read    A cold-fill from DRAM
> ```
> Fits the measured table to ~0.005. Spot-checks: α(96,16) → 3.10+0.021+0.706 = 3.827 vs **3.827** measured; α(32,4) → 3.10+0.063+2.825 = 5.988 vs **5.984**.
>
> - **`3.10` floor** — compute plus L1 traffic; the irreducible cost.
> - **`2.0/TM`** — the `ltea` B-tile FIFO *transfer*, which survives even at g_c=0 (generation is free; moving 16 elements into `%rb` is not). `ltea` sits outside the `rti` loop, so MACs per `ltea` = TM·reg_n·reg_k = 16·TM → matching 2.0/TM gives **≈32 cycles per B register tile**. Same 1/TM shape as g_c/TM, and reg_m cancels identically.
> - **`11.3/TN`** — switches on only once the A tile exceeds L1.
>
> **Why all five curves collapse at TM=8 and 12:** the third term is absent (A is resident), and the measured spread across TN=4…64 at TM=8 is literally **0.00**. TN only ever mattered as a divisor on a DRAM cost — remove the DRAM access and TN has nothing to do.
>
> Read the cold-fill coefficient straight off successive TN differences at TM=32: 1.409 = C/8, 0.705 = C/16, 0.353 = C/32, 0.177 = C/64 → **C ≈ 11.3** every time (theory: (180−4)/(REG_M·REG_K) = 176/16 = 11.0). At TM=8 the same subtraction gives C ≈ 0.02.
>
> ⚠ The constants `/16` (elements per 64B line) and `/8` are **precision-specific** — they assume 4-byte elements. At fp64 they change.

---

## Slide 20 — Using the α Table: Predicting the Optimal Tile

Once we have α measured, using it is straightforward. For any new g_c, we evaluate max{ α(TM, TN), g_c/TM } at every valid tile shape and take the argmin. No new experiments — just table lookup and arithmetic.

The diagram shows why this works geometrically. α is roughly flat in the A-load-bound region, then rises when the A tile overflows L1. g_c/TM is a decreasing curve. They cross at the optimal TM*. The optimal TN* is the one that minimizes α at that TM — typically the largest TN that still fits the FIFO.

> **[Config — model_intuition.png]**
> Source: `presentation/graphs/gen_charts.py` → α data from E6-nol2, TN=32 slice.
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, no L2. TN=32 fixed.
> α(TM) curve measured at gc=0. Two gc/TM hyperbolas shown: gc=50 and gc=200.
> Hardcoded α values (`gen_charts.py:245`): TM = 4/8/12/16/24/32/48/64/96/128 → α = 3.646 / 3.396 / 3.313 / 3.581 / 3.539 / 3.518 / 3.496 / 3.485 / 9.033 / 9.051.

> **[Note — the small "bowl" at the left of the red α curve (TM=4→16)]**
>
> The α curve dips before it climbs. The left wall is exactly a `2.0/TM` term:
>
> | TM | α measured | 3.146 + 2.0/TM |
> |---|---|---|
> | 4 | 3.646 | **3.646** ✓ |
> | 8 | 3.396 | **3.396** ✓ |
> | 12 | 3.313 | **3.313** ✓ |
>
> **Left wall (TM=4→12):** the `ltea` B-tile load sits *outside* the `rti` loop, so its fixed ~32-cycle cost is amortized over `TM/reg_m` passes. At TM=4 the `rti` loop runs exactly **once** — you pay it with no reuse at all.
> **Bottom (TM=12):** B-tile overhead already amortized 3×, and A still fits in L1.
> **Right wall (TM=12→16):** A tile hits 16KB, the `11.3/TN` cold-fill switches on (+0.35 at TN=32), swamping the further 0.04 you'd gain from `2/TM`. α jumps 3.313 → 3.581.
> **After (TM≥16):** the gentle decline 3.581 → 3.485 is just `2/TM` continuing to shrink (0.125 → 0.031), until the C-tile cliff at TM=96.
>
> The bowl is shallow (~10%) but it is why **TM\*=12 is the optimum at low g_c** on the next slide.

> **[Note — the winner is usually memory-bound, and why]**
>
> Across the 108 validation conditions the winning tile is memory-bound in **81/108 (75%)**; in E8 it is 13 of 14. Median `(g_c/TM)/α` at the winner is 0.84 — just on the memory side of balance.
>
> The two states are **not symmetric**:
> - **Gen-bound is escapable.** Its cost `g_c/TM` depends only on TM, and α is nearly flat in TM in the DRAM regime (4.64 → 4.53 across TM=16→96 at TN=8). So you can almost always escape by growing TM, at negligible α cost.
> - **Memory-bound is where you stop.** Growing TM further gains nothing, and eventually `ws_lines` forces TN down and α back up.
>
> So the optimizer pushes TM up until it escapes gen-bound, then stops. You stay gen-bound only when (a) **you run out of TM** — at g_c=400 even 400/96 = 4.17 > α = 3.83 — or (b) **escaping costs more α than the stall**, e.g. TN=8 at g_c=42–52, where staying gen-bound at 3.50 beats crossing the L1 cliff to α=4.53.
>
> Landing at 0.84 rather than a perfectly balanced 1.0 is **TM quantization**: TM only comes in {4,8,12,16,24,32,48,64,96}, so escaping gen-bound overshoots. E8 at g_c=38 sits at ratio 0.96 (nearly perfect), then the winner jumps TM=12→32 at g_c=42 and the ratio drops to 0.39.

---

## Slide 21 — Roofline Validation: Setup

Now the question is: does this actually work? We calibrate α once at g_c=0 — so we're committed to a fixed table — and then ask whether the model correctly predicts the best tile at new, unseen g_c values.

The methodology is: measure α at g_c=0; for each new g_c, compute the predicted best (TM*, TN*); run the simulator at that g_c empirically to find the true best; compare.

We ran this across two SRAM budgets — 64KB and 128KB. For each budget we swept how the budget is split between L1 and FIFO: 4 splits for 64KB, 8 splits for 128KB, 12 hardware configurations total. Nine g_c values from 10 to 500. That's 108 test conditions.

> **⚠ [These numbers are SPOKEN ONLY — the slide shows just the question.]**
> The test-conditions table was removed from the slide, so you have to say them. The full list if pressed: SRAM budgets 64KB and 128KB; L1/FIFO splits 4 + 8 = 12 configs; g_c values 10, 100, 250, 280, 300, 310, 325, 350, 500; total 12 × 9 = 108.

---

## Slide 22 — Roofline Validation: Results

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

> **[Note — "Max perf. gap 0%" on the slide is tautological — say so if challenged]**
> gap = cycles(predicted tile) / cycles(optimal tile) − 1. Since the prediction **is** the optimum in all 108 conditions, the gap is 0 by construction. It carries no information beyond the exact-match row above it. Not wrong, but it is not independent evidence, and a sharp examiner may say so. It would only be informative if some predictions were wrong.

> **[Note — why TN* could still degrade at extreme g_c]**
> When g_c/TM ≫ α for *every* valid TN, the model collapses to max(α, g_c/TM) ≈ g_c/TM, which does not depend on TN — so all TN at the best TM tie exactly. This is real and visible: at g_c=250 every TM=12 tile predicts 20.833 and every TM=32 tile predicts 7.812, regardless of TN.
>
> We handle it explicitly with the α tie-break (see the argmin note above), which resolves every tie correctly at the g_c values tested. It is not luck — α is a strictly better tie-break than iteration order. But the *margin* between tied tiles shrinks with g_c, so at sufficiently extreme g_c the ranking could become sensitive to measurement noise in α.

> **[Note — the scope of the 108/108 claim, and its one real limitation]**
>
> **State it precisely:** *for each hardware configuration, one calibration at g_c=0 predicts the optimal tile correctly at every g_c we tested.* The code runs a **separate** g_c=0 calibration per split — 12 calibrations, each predicting 9 g_c values. Not "one calibration covers all hardware."
>
> **The task was genuinely hard** (lead with this): 12 distinct optimal tiles across the 108 conditions; the optimum **moves with g_c in 11 of the 12** configs; the model chose among 16–36 candidates each time, so random guessing scores ≈3.7%. There were also **zero empirical ties**, so 100% is not a tie-breaking artifact.
>
> **⚠ The limitation to volunteer rather than be caught by.** `safe()` compares against a hardcoded `ws_lines < 300` calibrated for L1=16KB. It does **not** scale with L1 — but in this sweep L1 ranges from 8KB (128 lines) to 120KB (1920 lines). At the large-L1 splits it excludes tiles that would fit comfortably. We simulated them:
>
> | L1 | gc | excluded tile | measured α | safe() winner | its α | gap |
> |---|---|---|---|---|---|---|
> | 40KB | 250 | (96,32) ws=406 | **3.478** | (96,16) | 3.837 | **9.3% faster** |
> | 56KB | 250 | (96,64) ws=790 | **3.297** | (96,16) | 3.837 | **14.1% faster** |
>
> 28 of 36 conditions across the four large-L1 splits have a better excluded tile (~26% of the 108). **This does not invalidate the model** — prediction and ground truth used the same filter, and the roofline *predicted these excluded tiles to within 0.15%* (3.473 vs 3.478; 3.295 vs 3.297). The limitation is the **candidate filter, not the model**. The fix is to scale the threshold: `ws_lines < 1.17 × (L1/LINE)`, preserving the 300/256 ratio validated at 16KB.

---

## Slide 23 — Why TN* Fails at High g_c: Gen-Bound Regime

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

## Slide 24 — Impact of Tile Selection: Numbers

Does choosing the right tile actually matter? The numbers:
- At g_c=100: 20–65% faster depending on TN.
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

## Slide 25 — Impact of Tile Selection: Graph

The model we built tells you where that optimal shape is, from a single calibration run at g_c=0. Thanks for listening.

> **[Config — optimal_vs_square.png]**
> Source: same `e8-gc-boundary-sweep/results.json` via `plot_all.py:plot_e8_vs_square()`
> M=192, N=K=256, A_P=B_P=4B (fp32). L1=16KB, fully associative, no L2. B-stationary. FIFO_CAP=16384 elements.
> Four TN values plotted: 8, 16, 32, 64 (TN=4 excluded). Same gc sweep as slide 23.
> Left panel: cycles/MNK for optimal TM* vs square TM=TN, per (TN, gc). Right panel: speedup %.

> **[Note — why TN=64 (red line) is flat in performance and its SPEEDUP drops at high gc]**
>
> Left panel: the square tile (TM=64, TN=64) has `ws_lines = 526`, far past 300 — its **C tile** is evicted (not its A row), giving α = 8.87 from g_c=0 onward. It stays flat because its gen crossover is `g_c* = TM × α = 64 × 8.87 = 568`, which is **beyond the g_c=400 end of the sweep**. So it never becomes gen-bound anywhere on this graph and never moves off 8.87.
>
> The irony worth saying out loud: it is *so bad at memory* that generation never gets to be its problem. A huge α is a huge g_c budget. Consequence — it goes from the **worst** square at g_c=15 to the **best** square at g_c=400 (8.87 vs 50.0 / 25.0 / 12.5 for TN=8/16/32, all of which went gen-bound long before).
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

> **[Note — THE THREE RULES that explain every feature of this graph]**
>
> First, define the term: **"the square"** is the baseline tile with **TM = TN** — the naive symmetric choice. Each coloured curve has its own square, fixed by its TN (TN=8 → tile (8,8); TN=32 → tile (32,32)). "The square's TM" just means TN.
>
> **RULE 1 — everything comes from `g_c* = TM × α`** (the gen-bound crossover):
>
> | tile | α | `g_c*` | role |
> |---|---|---|---|
> | (8,8) TN=8's square | 3.40 | **27** | dies earliest — tiny TM |
> | (12,·) the A-resident optimum | ~3.32 | **40** | when the cache advantage expires — *same for every TN* |
> | (16,16) TN=16's square | 3.93 | **63** | |
> | (32,32) TN=32's square | 3.52 | **112** | |
> | (64,64) TN=64's square | 8.87 | **568** | past the sweep — never gen-bound |
>
> **RULE 2 — the speedup only moves when one side is rising and the other is frozen:**
>
> | square | optimal | speedup |
> |---|---|---|
> | gen-bound (rising) | memory-bound (frozen) | **climbs** |
> | gen-bound (rising) | gen-bound (rising) | **flat** at `1 − TM_sq/TM_opt` — g_c cancels |
> | both memory-bound | | small and flat |
>
> **RULE 3 — a dip is the window between two `g_c*` crossings.** The left edge is always ≈40 (the A-resident tile is TM=12 regardless of TN); only the right edge moves:
> ```
> TN=8:   square dies at 27, BEFORE 40  → advantages overlap → NO dip
> TN=16:  40 → 63    = 23 wide
> TN=32:  40 → 112   = 72 wide   ← why blue's dead zone is so long
> ```
>
> **Asymptote = `1 − TN/TM_opt`.** (Optimal cost on top — easy to invert by accident.) Both gen-bound, g_c cancels:
> ```
> TN=8:  1 − 8/96  = 92%     TN=16: 1 − 16/96 = 83%     TN=32: 1 − 32/64 = 50%
> ```
> Blue asymptotes at only 50% because 64 is merely **twice** 32. Large TN loses at both ends: the square's TM is already large *and* `ws_lines(96,32)=406` caps TM_opt at 64.

> **[Note — walking the green (TN=8) curve, with the bound-state of each tile]**
>
> Square = (8,8), α=3.397. Optimum is TM=12 (α=3.315) then TM=96 (α=4.530).
>
> | gc | square TM=8 | TM=12 | TM=96 | best | speedup |
> |---|---|---|---|---|---|
> | 15 | 3.397 **mem** | 3.315 **mem** | 4.530 mem | 12 | 2.4% |
> | 38 | 4.750 **GEN** | 3.315 **mem** | 4.530 mem | 12 | 30.2% |
> | 42–52 | 5.25→6.50 **GEN** | 3.50→4.33 **GEN** | 4.530 mem | 12 | **33.3% flat** |
> | 57 | 7.125 **GEN** | 4.750 GEN | 4.530 **mem** | **96** | 36.4% |
> | 400 | 50.0 **GEN** | 33.3 GEN | 4.530 **mem** | 96 | 90.9% |
>
> - **Starts at only 2.4%** because the square TM=8 gives an 8KB A tile that *fits* in L1 — it's a decent tile. (Contrast TN=16, whose square sits exactly *on* the cliff, hence its 16% gap.) The 0.08 difference is just `2/8 − 2/12`.
> - **No dip**, because the square dies at g_c=27 *before* TM=12 dies at 40.
> - **The 33.3% plateau** is Rule 2: both gen-bound, so `1 − 8/12 = 33.3%` with g_c cancelling. Costs rise 5.25→6.50 and 3.50→4.33 — the same ×1.238 — so the *gap* is frozen.
> - **It resumes climbing at g_c≈54** because the *optimal tile changes*. TM=12's cost `g_c/12` finally exceeds TM=96's α of 4.530 (crossover `12 × 4.530 = 54.4`), so the optimum switches to TM=96 — which is **memory-bound again** (its own `g_c*` is 435). Frozen optimal + rising square = the gap reopens, toward the `1 − 8/96 = 92%` ceiling.
>
> If asked *"if both are gen-bound, how does it ever start rising again?"* — the answer is that "the optimal" is not a fixed tile. It is whichever tile is best at that g_c, and at g_c≈54 that becomes a tile with 11× the g_c budget.

---
