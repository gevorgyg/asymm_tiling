* Using same size elements. But we bring it in way quicker. That's the idea with the fifo.
* The cost in cache goes to zero.
* The non fifo saves space in the L2 only.
* Percision is the same.

* Questions:
    1. can we increase the C tile with FIFO.
    2. depending on elements per cycle, does it effect the tile size of C. And how much does it effect the end to end time.

* Now the ratio will be the amount of bytes per cycle of A to The time of creating the B element with the prng. series of ratios depending on how many cycles to bring in an element of A.
* We want to check this because it can increase the tile size of C, and that is better for performance.


#### prompt:
  ok listen. We talked to the supervisor. Basically, this is all fine and good. We validated the theory. Now we want
  to get our take on this.

  our take is using the prng and prng fifo.
  the notes from the talk where:

  [Pasted text #1 +11 lines]

  this is very important, cause this tells us what we need to continue with from now on. Let's think about this
  together, what do you think about this? how do you think we should move forward with this in mind?


#### a elements per cycle and b elements per cycle:

This is the core performance model of the paper. Let me lay out what I understand:

The two rates

In the outer-products ordering, per C-tile session you consume:
- 8,192 A elements (TM × TK = 32 × 256)
- 8,192 B elements (TN × TK = 32 × 256)

So they're consumed at a 1:1 ratio. Define:

- a = cycles per A element consumed (determined by the memory hierarchy — cache hit rates, DRAM latency, tile shape)
- g = cycles per B element generated (= PRNG_FIFO_GEN_COST, a hardware property)

The crossover condition

The FIFO stalls when it generates slower than the CPU consumes:

stalls when g > a
no stalls when g ≤ a

We measured a ≈ 107 cycles/element (= 56.4M cycles ÷ 64 sessions ÷ 8192 elements). That's exactly the crossover we see — gc=64 has nearly no stalls, gc=128 starts stalling.

Why this framing matters

a isn't a constant — it's a function of tile shape, matrix size, and the memory hierarchy:
- If A tiles fit in L1: each A element is mostly an L1 hit (cheap a)
- If not: cold misses go to L2/DRAM (expensive a)
- The outer-products ordering reuses each A sub-tile TN/reg_n = 8 times across the B dimension, so L1 reuse is critical

The paper's analytical model should express a(TM, TN, TK, L1_size, L2_size, ...) and then the interesting design questions become:
1. What tile shape minimizes a?
2. Given a target g, what a do you need to avoid stalls?
3. The pipelined device effectively halves the required g by pre-generating during the previous session — so it doubles the range of g values that are stall-free

idea:
A 2D plot of (a, g) with a diagonal g = a crossover line. Below the line: B generation keeps up, A is the bottleneck. Above: B generation stalls. The pipelined device shifts the effective stall boundary from g = a toward g = 2a (for 1 stage), giving twice the headroom.

mathmatical model:
    https://claude.ai/code/artifact/ad59305a-f5b5-49ba-b061-f9ef55b56319


#### why TN changes C_fill less:
Here's what E3 S2 actually measured — TN is not flat, it just has a much smaller effect than TM:

S2 — TN sweep at TM=32 (already measured)

┌─────┬────────┬───────┐
│ TN  │ C_fill │   α   │
├─────┼────────┼───────┤
│ 4   │ 13.726 │ 3.432 │
├─────┼────────┼───────┤
│ 8   │ 13.285 │ 3.321 │
├─────┼────────┼───────┤
│ 16  │ 13.065 │ 3.266 │
├─────┼────────┼───────┤
│ 32  │ 12.955 │ 3.239 │
├─────┼────────┼───────┤
│ 64  │ 12.900 │ 3.225 │
└─────┴────────┴───────┘

S1 — TM sweep at TN=32

┌─────┬────────┬───────┐
│ TM  │ C_fill │   α   │
├─────┼────────┼───────┤
│ 8   │ 13.598 │ 3.400 │
├─────┼────────┼───────┤
│ 32  │ 12.955 │ 3.239 │
├─────┼────────┼───────┤
│ 64  │ 14.242 │ 3.560 │
├─────┼────────┼───────┤
│ 96  │ 15.759 │ 3.940 │
└─────┴────────┴───────┘

---
Why TN has a small but real effect:

As TN grows, A[rti,:] gets reused more rtj times within one tile_n (the loop iterates over rtj before moving to the next rti, so A stays warm in L1 for all TN/REG_N rtj passes). Larger TN → cold fraction = 1/(TN/REG_N) shrinks → fewer cold A fills. TN=4 has 100% cold A fills per rti; TN=64 has 6.25% cold A fills. But since cold fills are ~1% of total time (E4b confirmed this), even going from 100% cold to 6% cold only shifts the total by ~1 percentage point. That's the 6.4% we see across 16× TN range.

Why TM matters so much more:

The TM effect is not from A-reuse — it's from A-tile overflow:
- A-tile footprint = TM × TK × A_P = TM × 256 × 4
  - TM=8: 8KB — fits in L1
  - TM=32: 32KB — fits in L2
  - TM=64: 64KB = L2 exactly → A starts spilling to DRAM
  - TM=96: 96KB > L2 → DRAM

The big jump at TM=64 (C_fill: 13.0→14.2) and TM=96 (→15.8) is from A cold fills now costing DRAM latency instead of L2 latency. TN can't trigger this because A has no N dimension — adding more TN columns to the tile doesn't increase A's cache footprint at all.

Where TN does matter:

E4c already showed this: C-tile = TM×TN×C_P. At TM=32, TN=128 → 16KB = L1 → C overflows L1, warm C reads become L2 reads → C_fill jumps 14%. So TN has a threshold effect on C just like TM has a threshold effect on A.

---
So the cleaner statement of the model is:

- α(TM) is piecewise in TM because TM controls the A-tile regime (L1 / L2 / DRAM)
- α is flat in TN only while the C-tile fits in L1 (TN < L1/(TM×C_P))
- Both dimensions have a small secondary effect through cold-fill fraction (~6% across 16× range), which is too small to matter for the model


#### opetimal Tm 
The full time function from our model:

T = MNK × max( α(TM),  gc / TM )

Two terms competing:
- MNK × α(TM) — A-side memory time, depends only on TM (through cache regime)
- MNK × gc / TM — B generation time, decreasing in TM

TN is completely absent. So there is no optimal TM/TN ratio to derive — the original ratio rule TM*/TN* = ρ_t from the naive model is invalidated entirely.

---
Finding optimal TM analytically:

The two terms cross at the balance point:

α(TM*) = gc / TM*   →   TM* = gc / α(TM*)

Since α is piecewise constant per cache regeach piece:

L2 regime (TM ≤ 48, α ≈ 3.24):
TM* = gc / 3.24       (valid only if result ≤ 48)

DRAM regime (TM ≥ 64, α ≈ 3.94):
TM* = gc / 3.94       (valid only if result

The boundary is TM_L2 = 64. So:

┌──────────────┬────────────────────────────────────┐
│   gc range   │         optimal TM*         │              regime               │
├──────────────┼────────────────────────────────────┤
│ gc < 155     │ gc / 3.24, capped at 48     │ L2 — A-bottleneck if TM* < result │
├──────────────┼────────────────────────────────────┤
│ gc ≈ 155–252 │ boundary region (TM=48..64) │ evaluate both                     │
├──────────────┼────────────────────────────────────┤
│ gc > 252     │ gc / 3.94                          │
└──────────────┴────────────────────────────────────┘

If gc / α < TM_L2, the balance is in the L2the result lands past 64, use α_DRAM. The gap
between 48 and 64 is a discontinuity — you TM=64 and pick whichever is lower.

---
What to do with TN:

TN has no cost role as long as the C tile s

TN ≤ L1 / (TM × C_P) = 16384 / (TM × 4)

For TM=32: TN ≤ 128. Beyond that, C overflo4c). Within that bound, pick TN freely —largest power-of-2 that divides N and satisfies the constraint is fine.

---Bottom line: the optimization is now a 1D s problem. For a given gc you compute onecrossover point, check which regime it land is a free parameter subject to a cache-sizeceiling, not a tuning knob.


#### example of calculating the optimal Tm
The model is T = MNK × max(α(TM), gc/TM). Since MNK is just a constant multiplier, minimizing T is the same as minimizing the quantity inside:

f(TM) = max( α(TM),  gc/TM )
This is a function of a discrete variable (TM must divide M), and α(TM) is piecewise — so there's no calculus. The "analytical" work is understanding the shape of f(TM) and then evaluating it at each candidate.

---
The shape of f(TM)

Two terms:
- gc/TM — strictly decreasing: as TM doubles, this halves. B-generation is amortized over more elements.
- α(TM) — piecewise, mostly flat within L2, jumps at the L2 boundary (TM=64), then flat again in DRAM.

For small TM, gc/TM is large and dominates (gc/TM falls until it drops below α(TM). Pastthat crossover, α(TM) dominates (A-bottleneck). The minimum of max(A,B) is always at or near that crossover.

---
The algorithm (evaluate all candidates)

For each valid TM:
1. Compute gc/TM
2. Look up α(TM) from the table
3. Take max of the two → this is T/MNK at that TM
4. Pick the TM with the smallest result

That's it. Four arithmetic operations per TMalues from E5 by hand.

---
Example 1: gc = 64

┌─────┬───────┬───────────────┬───────┬────────────┐
│ TM  │ α(TM) │ gc/TM = 64/TM │  max  │ bott
├─────┼───────┼───────────────┼───────┼────────────┤
│ 8   │ 3.400 │ 8.000         │ 8.000 │ B
├─────┼───────┼───────────────┼───────┼────────────┤
│ 16  │ 3.300 │ 4.000         │ 4.000 │ B
├─────┼───────┼───────────────┼───────┼────────────┤
│ 24  │ 3.259 │ 2.667         │ 3.259 │ A
├─────┼───────┼───────────────┼───────┼────────────┤
│ 32  │ 3.237 │ 2.000         │ 3.237 │ A ←
├─────┼───────┼───────────────┼───────┼────────────┤
│ 48  │ 3.255 │ 1.333         │ 3.255 │ A
├─────┼───────┼───────────────┼───────┼────────────┤
│ 64  │ 3.560 │ 1.000         │ 3.560 │ A
├─────┼───────┼───────────────┼───────┼────────────┤
│ 96  │ 3.940 │ 0.667         │ 3.940 │ A
├─────┼───────┼───────────────┼───────┼────────────┤
│ 128 │ 3.936 │ 0.500         │ 3.936 │ A
└─────┴───────┴───────────────┴───────┴────────────┘

Crossover is between TM=16 (B-dominated, cost 4.000) and TM=24 (A-dominated, cost 3.259). Once we're in A-dominated territory, the cost equals α(TM), so you just want the TM with the smallest α. That's TM=32 (α=3.237).

TM = 32, T/MNK = 3.237*

---
Example 2: gc = 130

┌─────┬───────┬────────────────┬────────┬────────────┐
│ TM  │ α(TM) │ gc/TM = 130/TM │  max   │ bottleneck │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 8   │ 3.400 │ 16.250         │ 16.250 │ B          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 16  │ 3.300 │ 8.125          │ 8.125  │ B          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 24  │ 3.259 │ 5.417          │ 5.417  │ B          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 32  │ 3.237 │ 4.063          │ 4.063  │ B          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 48  │ 3.255 │ 2.708          │ 3.255  │ A ← min    │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 64  │ 3.560 │ 2.031          │ 3.560  │ A          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 96  │ 3.940 │ 1.354          │ 3.940  │ A          │
├─────┼───────┼────────────────┼────────┼────────────┤
│ 128 │ 3.936 │ 1.016          │ 3.936  │ A          │
└─────┴───────┴────────────────┴────────┴────────────┘

Crossover between TM=32 (B, cost 4.063) and TM=48 (A, cost 3.255). At TM=48 we're A-dominated so the cost is α(48)=3.255. At TM=64 we'd pay α(64)=3.560 — worse. So the minimum is TM=48.

TM = 48, T/MNK = 3.255*

Key thing to notice: TM=32 is B-dominated here (gc/32 = 4.063 > α(32)=3.237), so even though TM=32 has a lower α than TM=48, it doesn't help — the B-side is still the bottleneck there. You have to keep growing TM until gc/TM drops below α.

---
Example 3: gc = 230

┌─────┬───────┬────────────────┬────────┬──────────────────┐
│ TM  │ α(TM) │ gc/TM = 230/TM │  max   │    bottleneck    │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 8   │ 3.400 │ 28.750         │ 28.750 │ B                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 16  │ 3.300 │ 14.375         │ 14.375 │ B                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 24  │ 3.259 │ 9.583          │ 9.583  │ B                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 32  │ 3.237 │ 7.188          │ 7.188  │ B                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 48  │ 3.255 │ 4.792          │ 4.792  │ B                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 64  │ 3.560 │ 3.594          │ 3.594  │ B (barely) ← min │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 96  │ 3.940 │ 2.396          │ 3.940  │ A                │
├─────┼───────┼────────────────┼────────┼──────────────────┤
│ 128 │ 3.936 │ 1.797          │ 3.936  │ A                │
└─────┴───────┴────────────────┴────────┴──────────────────┘

Crossover is between TM=64 and TM=96. At TM=64: gc/TM = 3.594 > α(64) = 3.560 — still B-dominated, cost = 3.594. At TM=96: cost jumps to 3.940 because now A is the bottleneck and α(96) = 3.940.

So TM=64 costs 3.594 and TM=96 costs 3.940. TM=64 wins.

TM = 64, T/MNK = 3.594*

This is the interesting case — TM=64 is the winner even though it sits right at the L2/DRAM boundary and has higher α than TM=32 or 48. The B savings from going from TM=48 to TM=64 (4.792 → 3.594) outweigh the penalty. But going further to TM=96 overshoots — the B savings (3.594 → 2.396) don't compensate for the large α jump (3.560 → 3.940).

---
Example 4: gc = 380

┌─────┬───────┬────────────────┬────────┬───────────────────┐
│ TM  │ α(TM) │ gc/TM = 380/TM │  max   │    bottleneck     │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 8   │ 3.400 │ 47.500         │ 47.500 │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 16  │ 3.300 │ 23.750         │ 23.750 │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 24  │ 3.259 │ 15.833         │ 15.833 │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 32  │ 3.237 │ 11.875         │ 11.875 │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 48  │ 3.255 │ 7.917          │ 7.917  │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 64  │ 3.560 │ 5.938          │ 5.938  │ B                 │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 96  │ 3.940 │ 3.958          │ 3.958  │ B (3.958 > 3.940) │
├─────┼───────┼────────────────┼────────┼───────────────────┤
│ 128 │ 3.936 │ 2.969          │ 3.936  │ A ← min           │
└─────┴───────┴────────────────┴────────┴───────────────────┘

At TM=96: gc/96 = 3.958, α(96) = 3.940. gc/TM is just above α — still B-dominated by a hair (0.5%). At TM=128: gc/128 = 2.969 < α(128) = 3.936, so A-dominated. Cost = 3.936, which is better than 3.958 at TM=96.

TM = 128, T/MNK = 3.936*

---
The rule of thumb (no table lookup needed)

If you just want to estimate TM* without the full table:

1. Compute the crossover TM assuming you stay in the L2 regime: set α_L2 ≈ 3.25 and solve gc/TM = α_L2 → TM_cross = gc / 3.25
2. If TM_cross ≤ 48 (still in L2): TM* is the first valid TM ≥ TM_cross. Since gc/TM < α once you cross, the minimum α in that range wins — usually TM=32 or TM=48.
3. If TM_cross > 48: the crossover pushes past L2. You then compare the cost of TM=64 (B-dominated: gc/64) against the cost of TM=128 (A-dominated: α_DRAM ≈ 3.94). If gc/64 < 3.94, i.e., gc < 252, TM=64 wins. If gc ≥ 252, TM=128wins.


#### next plan
Here's the plan.

---
E8 — Dense gc sweep across TM* transition points

Motivation: E7 used only 4 gc values. The model has three exact transition points where TM* changes (derived from the α table):

┌──────────────┬───────────────────────────────────────┐
│  Transition  │          Exact gc crossover           │
├──────────────┼───────────────────────────────────────┤
│ TM* 32 → 48  │ gc = α(32) × 32 = 3.237 × 32 ≈ 103.6  │
├──────────────┼───────────────────────────
│ TM* 48 → 64  │ gc = α(64) × 48 = 3.560 × 48 ≈ 170.9  │
├──────────────┼───────────────────────────
│ TM* 64 → 128 │ gc = α(128) × 64 = 3.936 × 64 ≈ 251.9 │
└──────────────┴───────────────────────────

We want to test gc values on both sides of gh resolution to see where the E3 modelstarts failing for small TN.

gc values to test (14 total):

┌─────┬──────────────────────────────────────────────┐
│ gc  │                     Why




#### alpha plan
Plan: analytical α formula — regression-based approach

Goal: Instead of using the theoretical C(TM) constant (which breaks in DRAM regime), fit α(TM, 1/TN) empirically using linear regression on the calibration data already collected in E8 (TN ∈ {4,8,16,32,64} for each TM).

Experiment E11 — Regression α formula

Step 1 — Fit the model.

For each TM, we have 5 measured α values at x = 1/TN ∈ {1/4, 1/8, 1/16, 1/32, 1/64}. The model is:

α(TM, TN) = a(TM) + b(TM) × (1/TN)
Fit by ordinary least squares (numpy or scipy, 2 parameters per TM). This gives:
- a(TM) — the TN→∞ intercept (the "purely warm-L1" α)
- b(TM) — the empirical cold-fill slope

Step 2 — Compare to the theoretical formula.

The theoretical formula predicts b(TM) = C(TM) where C = 0.625 in L2 and C = 12.0 in DRAM. The regression will give the actual C(TM) per TM, and we can see how close the theory is and whether the DRAM regime has a consistent value.

Step 3 — Test accuracy.

Same setup as E8's formula accuracy table, but using the regression coefficients instead of the theoretical ones. Measure % error vs calibrated α over the same TM × TN grid.

Step 4 — Test TM* prediction accuracy.

Re-run the E8 summary table substituting the regression formula for the theoretical one. How many of the 70 (gc, TN) combinations does it get right vs the theoretical formula?

Expected outcome: The regression should:
- Match calibrated α within ~1% across all TN ≤ 64 (vs the formula's 0-10% error)
- Correctly predict TM* in nearly all cases (vs formula failing at DRAM regime TN=4,8)
- Give physically interpretable b(TM) values: ~0.6 for L2 regime, ~10.4 for TM=96,128

Implementation: extend experiment.py in e11-regression-alpha/, loading the E8 results.json for the calibration data (no new simulator runs needed). The regression itself is ~15 lines of numpy. Output a comparison table: theoretical vs regression formula, both vs calibrated, both vs empirical TM*.

This is entirely CPU-side analysis — no new simulator runs needed if we load E8's cached results.
