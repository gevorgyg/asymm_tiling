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

## Slide 6 — Traffic Minimum at the Predicted Tile

We validated this against our cycle-accurate simulator. Each panel here sweeps the tile aspect ratio TN/TM on the x-axis and plots L1 read traffic. The dashed line is the paper's prediction for where the minimum should land.

For all four values of ρ, the empirical minimum falls exactly on the predicted aspect ratio. The simulation matches the formula to within about 2%.

---

## Slide 7 — B/A Balance: Exact Confirmation

We can look at this even more directly. Instead of plotting total traffic, this shows the ratio of B reads to A reads as the aspect ratio varies. At the paper's predicted optimum, the two inputs contribute equal traffic — so the ratio should cross 1.

And it does, exactly, for every ρ. The vertical dashed lines mark the predictions, and every curve crosses 1 right there. When ρ is 1/8, the traffic savings versus a square tile is 36%.

---

## Slide 8 — Traffic ≠ Time

So the paper's traffic model is solid. But here's the problem: minimizing bytes transferred is not the same as minimizing cycles. Cache latency, bandwidth limits, and prefetch behavior all break the proportionality.

We need a cycle-accurate model. And more importantly, we're working with a different hardware setup — one where B doesn't come from memory at all.

This is the PRNG FIFO. B elements are generated on-chip by a random number generator and streamed directly into the compute unit. B never touches the cache. B has no memory address. The B_P/TM traffic term simply vanishes — and instead, B introduces a new cost: on-chip generation time, which we call g_c cycles per element.

---

## Slide 9 — The PRNG FIFO: B Without Memory

Here's what the hardware looks like. A comes through the normal memory hierarchy — DRAM, L2, L1, registers. B takes a completely separate path: the PRNG generates it, the FIFO buffers it, and it goes straight to the MAC unit, bypassing the cache entirely.

This gives us two independent bottlenecks. One is A-loading from memory. The other is waiting for the PRNG to produce B at g_c cycles per element. The runtime is whichever one is slower — they can run in parallel.

---

## Slide 10 — Which Loop Order Fits the FIFO?

Now, the FIFO generates B elements in a fixed order — you can't skip or replay them. The loop order of your computation must match the generation order, or you pay a penalty.

There are three natural options. C-stationary row-major, C-stationary col-major, and B-stationary. The table here shows the key difference: their effective B generation cost per output element.

C-stationary row-major pays g_c times TN per element — badly wasteful. C-stationary col-major pays g_c. B-stationary pays g_c over TM. That factor of TM is the key, and I'll explain where it comes from.

---

## Slide 11 — C-Stationary Row-Major: Ghost Read Problem

Here's why C-stationary row-major is so bad. The C tile is fixed in registers. For each step in K, the FIFO generates B in row-major order — it produces all N/TN column groups before moving to the next K step.

But a given C tile at column j only needs the j-th group per K step. The FIFO has already generated groups 0 through j-1, which are useless. These are ghost reads — the hardware pulls elements out of the FIFO just to discard them.

The numbers show this clearly. At g_c=0, C-stationary is 2× faster than B-stationary because its α is lower. But at g_c=10 it's already 1.25× slower, and at g_c=100 it's 7.5× slower. The ghost read penalty grows with g_c.

---

## Slide 12 — C-Stationary Col-Major: Ghost Reads Gone, Problem Remains

The natural fix is to change the FIFO generation order to column-major. Generate all K values for column j before moving to column j+1. Now the loop can consume exactly the elements it needs, in order — no ghost reads.

That helps at moderate g_c — col-major is about 1.28× faster than row-major at g_c=10. But at g_c=100 it's still 7.5× slower than B-stationary.

So ghost reads were not the real bottleneck. The real problem is deeper: C-stationary has no TM-fold amortization. Each A-row requires new B elements from the FIFO. Compare that to B-stationary, where the loop order is B outer, A inner — one B block is fetched once, and all TM A-rows sweep through it. Each B element is used TM times, amortizing the generation cost by TM.

---

## Slide 13 — B-Stationary: TM-Fold Register Reuse

So in B-stationary, the generation cost per MAC is g_c times N_B divided by TM times N_B — the N_B cancels, and you get g_c over TM regardless of block size.

At TM=32 and g_c=100, that's about 3 cycles per MAC. C-stationary pays the full 100. That's where the 7.5× gap comes from at g_c=100.

The practical rule: use B-stationary for any g_c above about 20. C-stationary only wins at very low g_c, where its lower α compensates for the generation cost.

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

Two things stand out. First, small TN values like TN=4 cause α to spike at moderate TM — the A tile overflows L1 with few column groups to amortize against. Second, for large TN like TN=32, α stays flat around 3.5 out to TM=96, then shoots up to around 9 — that's where the A tile is finally too large for L1.

α decreases with TN because more column reuse means fewer A reloads per output. The cache boundary shifts with TM.

---

## Slide 19 — Using the α Table: Predicting the Optimal Tile

Once we have α measured, using it is straightforward. For any new g_c, we evaluate max{ α(TM, TN), g_c/TM } at every valid tile shape and take the argmin. No new experiments — just table lookup and arithmetic.

The diagram shows why this works geometrically. α is roughly flat in the A-load-bound region, then rises when the A tile overflows L1. g_c/TM is a decreasing curve. They cross at the optimal TM*. The optimal TN* is the one that minimizes α at that TM — typically the largest TN that still fits the FIFO.

---

## Slide 20 — Roofline Validation: Setup

Now the question is: does this actually work? We calibrate α once at g_c=0 — so we're committed to a fixed table — and then ask whether the model correctly predicts the best tile at new, unseen g_c values.

The methodology is: measure α at g_c=0; for each new g_c, compute the predicted best (TM*, TN*); run the simulator at that g_c empirically to find the true best; compare.

We ran this across two SRAM budgets — 64KB and 128KB — with 6 hardware splits each varying the L1/FIFO split, and 9 g_c values from 10 to 500. That's 108 test conditions total.

---

## Slide 21 — Roofline Validation: Results

The scatter plot shows predicted TM* on the y-axis against empirical TM* on the x-axis. All 70 points sit on the diagonal — 100% accuracy for TM* across all g_c values and all TN configurations.

TN* is correct up to about g_c=250, then starts to degrade. Overall, exact matches on the full (TM*, TN*) pair are 80% of test conditions. And when the model is wrong, the cycle gap is at most 4% — so it's wrong in a regime where it barely matters.

---

## Slide 22 — Why TN* Fails at High g_c: Gen-Bound Regime

Here's why. When g_c/TM is much larger than α for all TN values, the max collapses to just g_c/TM — which doesn't depend on TN at all. The model predicts the same cost for every TN, so it can't distinguish between them.

TM* is always right because g_c/TM still depends on TM — the model correctly identifies which row-tile size minimizes the gen-bound cost. It's only TN* that becomes arbitrary.

Empirically, TN=16 is best in the gen-bound regime due to register pipeline effects, but the model doesn't know that. The crossover point is roughly g_c equals TM times α — for TM=96 and α around 3.8, that's about g_c=370.

---

## Slide 23 — Impact of Tile Selection: Optimal vs. Square

So does choosing the right tile actually matter? This is the bottom line. The left panel compares the best asymmetric tile against the best square tile for each g_c. The right panel shows the percentage speedup.

At g_c=100, asymmetric tiling is 20 to 40% faster depending on TN. At g_c=250 it's around 75% faster. At g_c=400 it's up to 85% faster. The gain grows with g_c because the generation bottleneck is the one that the tile shape can most directly control.

The model we built tells you where that optimal shape is, from a single calibration run at g_c=0. Thanks for listening.

---
