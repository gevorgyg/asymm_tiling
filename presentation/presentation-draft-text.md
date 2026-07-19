flow:

1. Matrix tiling basics — what are tile dimensions, why tile?
2. Square tiles — the default assumption
3. Paper: asymmetric tiling — ρ = B_P/A_P, optimal at TN/TM = 1/ρ
* to validate and run simulations we built a cycle accurate cache sim and our own specialized instruction set to feed it specific matmul instructions.
4. Paper validation → matches their traffic formula
5. Bridge: traffic ≠ time; and with FIFO, B doesn't take up space in cache, so we can use symmetric precision, and the A_p and B_p values don't matter anymore, we need a different model.
6. FIFO hardware: what it is, how it works, what "random matmul" means, the gc parameter.

--- NEW SECTION: Dataflow Comparison ---

7. Which loop order to use with the FIFO?
   - three candidates: C-stationary row-major, C-stationary col-major, B-stationary
   - short table showing: what is "stationary" (what tile stays in registers), how B is consumed from the FIFO
   - C-stationary: C tile in register file, iterate over K → stream A rows and B columns
   - B-stationary: B sub-tile in register file, iterate over M rows → stream A rows, B reused across all M rows
   - question: does it matter? yes — because the FIFO has a fixed generation order, and the loop order must match it or pay a penalty

8. C-stationary row-major: the ghost read problem
   - diagram: C tile fixed in registers; for each column of K, the FIFO generates B in row-major order (one row of B at a time)
   - to compute C[i,j] for a given k, we need B[k, j] — but the FIFO has already generated B[k, 0], B[k, 1], ..., B[k, j-1] (unused ghost elements)
   - each useful FIFO read is preceded by N_reg-1 ghost reads that just discard data
   - effective FIFO traffic multiplied by N_reg = TN; gc cost scales as gc × TN (instead of gc × 1)
   - result: empirically 1.25× slower than B-stat at gc=10; 7.5× slower at gc=100 (fully broken)
   - note: at gc=0 C-stat wins 2× because α is lower — the ghost-read penalty is only in the generation cost

9. C-stationary col-major: fixes ghost reads, but not register reuse
   - idea: change FIFO generation order to col-major — generate all K values for column j before moving to column j+1
   - now the loop can consume FIFO elements as they arrive: no ghost reads
   - result at gc=0: C-stat col-maj wins ~2× over B-stat (same as row-major, ghost reads weren't the issue at gc=0)
   - result at gc=10: col-maj wins 1.25–1.30× over B-stat (better than row-major's 1.2×, the fix helped)
   - result at gc=100: still 7.5× slower than B-stat! — ghost reads are gone, so what went wrong?
   - root cause: B-stationary holds the B sub-tile in registers and reuses it across all TM A-rows. Effective generation cost = gc / TM (amortized). C-stationary has no such reuse — each A-row requires the FIFO to produce new B values. Generation cost = gc per output element (not gc/TM).
   - ratio of costs: at TM=32, B-stat pays gc/32 while C-stat pays gc → 32× cheaper. At gc=100 and α≈3.3, B-stat total ≈ 3.3 cy/elem, C-stat ≈ 25 cy/elem → 7.5× gap.

10. B-stationary: TM-fold register reuse of B
    - B sub-tile (TN elements per K step) lives in registers for the full sweep over TM rows
    - generation cost paid once, amortized over TM useful outputs → gc/TM per output element
    - this is the only dataflow where B-generation and A-loading are both optimally amortized
    - summary table: B-stat best at any gc ≥ ~20; C-stat col-maj wins only at very low gc (≤ 10)
    - practical takeaway: for any realistic PRNG cost, use B-stationary

--- (model derivation now proceeds for B-stationary) ---

11. The naive model: T = MNK × ( C_A/TN + C_B/TM ), where C_A and C_B are cycle costs (not bytes) — apply the same reuse argument but in cycles. C_B = gc since B is generated, not loaded. Still a sum because we naively assume the two costs add.
12. But the FIFO is ASYNC — A loading and B generation run in parallel. So the runtime is whichever finishes last, not their sum. Visual: two parallel timelines (A-load, B-gen), runtime = max. This gives T = MNK × max{ C_A/TN, gc/TM }.
13. But C_A/TN turns out to be wrong — cycles ≠ bytes × latency, and α(TM,TN) is richer than a simple ratio. We replace C_A/TN with measured α(TM,TN): T = MNK × max{ α(TM,TN), gc/TM }.
14. We fully control gc. If we set gc = 0, B is free and the only cost is A loading → T/MNK = α(TM,TN). That lets us isolate and measure α directly.
15. Calibration: sweep all (TM, TN) pairs at gc = 0, record T/MNK → build an α table. No formula assumed.
16. Using the table: for any gc, α(TM,TN) is already known, and gc/TM is analytic. Just read off which (TM,TN) minimizes max{ α, gc/TM }.

--- NEW SECTION: Roofline Validation ---

17. Roofline validation setup
    - question: if we calibrate α once (at gc=0), does the model predict the best tile correctly at any new gc?
    - methodology: for each hardware split (L1 size, FIFO capacity), measure α at gc=0, then predict best (TM,TN) for gc ∈ {10, 100, 250, 280, 300, 310, 325, 350, 500}; compare prediction to empirical best.
    - total: 12 hardware splits × 9 gc values = 108 test conditions across two SRAM budgets (64KB, 128KB)

18. Roofline validation: results
    - graph or table: per-gc accuracy (% exact match), showing 100% at gc ≤ 250–280, then degradation at higher gc
    - key numbers: 86/108 (80%) overall exact match; when wrong, median gap only 0.25%, worst case 4.1%
    - key finding: TM* is always correct; only TN* fails in certain high-gc conditions
    - note: both budgets (64KB and 128KB) show same pattern

19. Why the model breaks at high gc — the gen-bound regime
    - when gc/TM > α_calib(TM,TN), the hardware is B-generation-bound
    - in the gen-bound regime, all TN values give the same predicted cost: MNK × gc/TM (TN-independent)
    - so the model can't distinguish TN — it picks arbitrarily, empirically TN=16 is best due to register pipeline effects
    - crossover gc* = TM × α_calib(TM,TN_best); example: TM=96, α≈3.83 → gc* ≈ 367 (most splits)
    - TM is always correct because gc/TM is TM-dependent — the model still picks the right row-tile size
    - diagram: the two lines gc/TM and α(TM,TN) crossing, with the gen-bound region shaded

--- NEW SECTION: L1 vs FIFO Budget Split ---

20. Hardware question: how should we split the SRAM budget?
    - fixed total SRAM budget (64KB or 128KB) split between L1 cache and FIFO buffer
    - more L1 → bigger A-tile fits in cache, lower α; more FIFO → supports larger TN, more pre-generated B
    - question: is there an optimal split, or does one resource always dominate?
    - experimental setup: sweep L1 ∈ {8, 24, 40, 56}KB (64KB budget) or {8, 24, ..., 120}KB (128KB), FIFO gets the rest

21. L1 vs FIFO: 64KB budget results
    - graph: cycles vs L1 size (x-axis), one line per gc value
    - key data: more L1 monotonically better for gc ≤ 100 (no exception)
      - gc=10: L1=8KB is +10.3% slower than L1=56KB; L1=40KB is only +0.6%
      - gc=100: L1=8KB is +10.0% slower; L1=40KB is +2.3%
    - at gc=250+: the picture is mixed — L1=56KB has FIFO=2048 which is too small for TN>8, so the very-high-L1 split actually loses back at medium gc
    - winner at gc ≤ 100: give as much to L1 as possible (until FIFO can still hold the B sub-tile)

22. L1 vs FIFO: 128KB budget results
    - graph: same structure; now 8 splits from L1=8KB to L1=120KB
    - key data:
      - gc=10: L1=8KB is +7.6% slower than L1=120KB; improvement is smooth and monotonic
      - gc=100: L1=8KB is +11.1% slower; L1=120KB is clearly best
      - gc=250: L1=120KB is 20–26% faster than L1=8–104KB splits — big win because A-tile fits entirely in L1 at TM=96
      - gc≥350: splits converge again (gen-bound, A-tile cost less important)
    - key structure: at medium gc (250–350), having enough L1 for the A-tile (≈ TM×K×A_P = 96×256×4 = 96KB) pays off massively

23. L1 vs FIFO: key insight and recommendation
    - core finding: within a fixed SRAM budget, allocate to L1 over FIFO
    - FIFO needs enough capacity to hold one B sub-tile (TK × TN × B_P bytes); beyond that, extra FIFO gives little gain
    - diminishing returns: going from L1=8→24KB saves ~8%, L1=24→40KB saves ~1–2%, L1=40→56KB saves <1%
    - practical threshold: FIFO_CAP ≥ TK × TN_max (e.g., 256×16=4096 elements minimum); rest to L1
    - diagram: annotated crossover showing the "FIFO floor" and "L1 wins zone"

--- Conclusions ---

24. Conclusions
    - paper model: asymmetric precision → asymmetric tiles (TN*/TM* = 1/ρ); confirmed experimentally
    - cycle model: T = MNK × max{ α(TM,TN), gc/TM } — A-loading and B-generation are parallel bottlenecks
    - dataflow: B-stationary is the right choice for FIFO; C-stationary variants don't amortize generation cost
    - calibration: one gc=0 sweep builds an α table; no formula needed; 100% TM* accuracy for gc ≤ ~280
    - model validity: TM always predicted correctly; TN fails only in the gen-bound regime (gc ≳ 300), with ≤ 1% cycle gap in most cases
    - SRAM budget: more L1 wins over more FIFO; FIFO only needs enough capacity for the B sub-tile
    - open questions: two-level cache (L1+L2), pipelining across tiles, real PRNG characterization

* note: keep slides NOT VERBOSE.
