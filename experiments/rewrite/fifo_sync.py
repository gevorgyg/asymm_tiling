"""fifo_sync: software RNG (Liang et al.) vs hardware PRNG-FIFO, each against
loading B from memory.

Liang, Murray, Buluc, Demmel, "Fast multiplication of random dense matrices
with sparse matrices" (arXiv 2310.15419) generate the random operand on the
CPU core: generation and memory traffic add up. The project's PRNG-FIFO
generates in the background: they overlap. The simulator does both:

  * hardware FIFO: capacity 16384, the generator fills the FIFO while the
    core loads A and C, so the cost is max(alpha, B term);
  * software RNG: capacity 0, nothing is generated ahead, every pop waits
    gc per element, so the cost is alpha + B term (the paper's additive
    model, dense limit).

Same device, grid, parameters and B-stationary dataflow as fifo_feasibility
(rho, lambda, gamma defined there). Each side takes its best (TM, TN).

run:  .venv/bin/python experiments/rewrite/fifo_sync.py
"""

from __future__ import annotations

import math
import statistics
from dataclasses import replace
from itertools import product

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from fifo_feasibility import (A_P, CYC, GAMMAS, K, L1, L1_CYC, LAMBDAS, LINE,  # noqa: E402
                              M, MNK, N, RHOS, TMS, TNS, b_bytes, base, gc_of)
from harness import out_dir, run_many  # noqa: E402

NAME = "fifo_sync"
HW, SW = "hardware FIFO", "software RNG"
CAPACITY = {HW: 16384, SW: 0}


def b_term(gc: int, tm: int) -> float:
    """Generation cycles per MAC: B is regenerated once per tile row."""
    return gc * math.ceil(M / tm) / M


def crossing(xs: list[float], ys: list[float]) -> float:
    """First x where ys falls through 1, log-interpolated in x and y.
    inf if it never does, 0 if it starts below 1."""
    if ys[0] < 1:
        return 0.0
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y0 >= 1 > y1:
            t = math.log(y0) / (math.log(y0) - math.log(y1))
            return math.exp(math.log(x0) + t * (math.log(x1) - math.log(x0)))
    return math.inf


def fmt(x: float, nd: int = 2) -> str:
    return "inf" if math.isinf(x) else f"{x:.{nd}f}"


def main() -> None:
    out = out_dir(NAME)

    grid: dict[tuple, object] = {}
    for rho, lam in product(RHOS, LAMBDAS):
        b = base(rho, lam)
        for tm, tn in product(TMS, TNS):
            grid[(rho, lam, "memory", None, tm, tn)] = replace(
                b, b_source="memory", tile_h=tm, tile_w=tn)
            for src, g in product((HW, SW), GAMMAS):
                grid[(rho, lam, src, g, tm, tn)] = replace(
                    b, b_source="fifo", tile_h=tm, tile_w=tn,
                    fifo_capacity=CAPACITY[src],
                    gen_cost=gc_of(g, b.mem_cycles, rho))
    keys = list(grid)
    res = dict(zip(keys, run_many([grid[k] for k in keys], out / "results.json")))
    cyc = {k: v[CYC] / MNK for k, v in res.items()}

    # ---- best vs best -------------------------------------------------------
    def best(rho, lam, src, g):
        return min((cyc[k], k[4], k[5]) for k in keys if k[:4] == (rho, lam, src, g))

    mem = {(r, l): best(r, l, "memory", None) for r, l in product(RHOS, LAMBDAS)}
    bst = {(r, l, s, g): best(r, l, s, g)
           for r, l, s, g in product(RHOS, LAMBDAS, (HW, SW), GAMMAS)}
    speedup = {(r, l, s): [mem[(r, l)][0] / bst[(r, l, s, g)][0] for g in GAMMAS]
               for r, l, s in product(RHOS, LAMBDAS, (HW, SW))}
    gains = {(r, l): [bst[(r, l, SW, g)][0] / bst[(r, l, HW, g)][0] for g in GAMMAS]
             for r, l in product(RHOS, LAMBDAS)}
    pos = [g for g in GAMMAS if g > 0]
    gstar = {(r, l, s): crossing(pos, speedup[(r, l, s)][1:])
             for r, l, s in product(RHOS, LAMBDAS, (HW, SW))}

    def l1_hits(gamma: float, lam: int, rho: float) -> float:
        """Generation cost per element in L1-hit times: gamma*lambda*B_P/64."""
        return gamma * lam * b_bytes(rho) / LINE

    # ---- model fit, every tile ----------------------------------------------
    fit = {HW: [], SW: []}             # (predicted, measured)
    for k in keys:
        rho, lam, src, g, tm, tn = k
        if src == "memory" or g == 0:
            continue
        alpha = cyc[(rho, lam, src, 0, tm, tn)]
        bt = b_term(grid[k].gen_cost, tm)
        pred = max(alpha, bt) if src == HW else alpha + bt
        fit[src].append((pred, cyc[k]))

    def fit_stats(pairs):
        err = [m / p - 1 for p, m in pairs]
        return (statistics.median(abs(e) for e in err), max(err), min(err),
                sum(abs(e) < 0.01 for e in err) / len(err))

    # ---- figures ------------------------------------------------------------
    xpos = list(range(len(GAMMAS)))
    colors = dict(zip(RHOS, plt.rcParams["axes.prop_cycle"].by_key()["color"]))

    fig, axes = plt.subplots(1, len(LAMBDAS), figsize=(5.5 * len(LAMBDAS), 4.2),
                             sharey=True)
    for ax, lam in zip(axes, LAMBDAS):
        for rho in RHOS:
            for src, ls in ((HW, "-"), (SW, "--")):
                ax.plot(xpos, speedup[(rho, lam, src)], ls=ls, marker="o", ms=4,
                        color=colors[rho],
                        label=f"rho = {rho:g}, {src}" if lam == LAMBDAS[0] else None)
        ax.axhline(1, color="k", lw=0.8)
        ax.set_xticks(xpos, [f"{g:g}" for g in GAMMAS])
        ax.set_yscale("log")
        ax.set_xlabel("gamma = generate a line of B / fetch it from DRAM")
        ax.set_title(f"lambda = {lam}")
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("best memory-B cycles / best generator cycles")
    axes[0].legend(fontsize=7)
    fig.suptitle("Generating B vs loading it, each at its best tile "
                 "(solid: hardware FIFO, dashed: software RNG; above 1 generating wins)")
    fig.tight_layout()
    fig.savefig(out / "speedup_vs_gamma.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, len(LAMBDAS), figsize=(5.5 * len(LAMBDAS), 4),
                             sharey=True)
    for ax, lam in zip(axes, LAMBDAS):
        for rho in RHOS:
            ax.plot(xpos, gains[(rho, lam)], marker="o", color=colors[rho],
                    label=f"rho = {rho:g}")
        ax.axhline(1, color="k", lw=0.8)
        ax.set_xticks(xpos, [f"{g:g}" for g in GAMMAS])
        ax.set_xlabel("gamma")
        ax.set_title(f"lambda = {lam}")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("best software-RNG cycles / best hardware-FIFO cycles")
    axes[0].legend()
    fig.suptitle("What overlapping generation with memory buys")
    fig.tight_layout()
    fig.savefig(out / "overlap_gain.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, (src, model) in zip(axes, ((HW, "max(alpha, B)"), (SW, "alpha + B"))):
        p, m = zip(*fit[src])
        ax.scatter(p, m, s=4, alpha=0.4)
        lo, hi = min(p + m), max(p + m)
        ax.plot([lo, hi], [lo, hi], color="k", lw=0.8)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(f"predicted cycles / MAC, {model}")
        ax.set_ylabel("measured cycles / MAC")
        med, worst_hi, worst_lo, within = fit_stats(fit[src])
        ax.set_title(f"{src}: {within:.0%} within 1 %, worst {worst_hi:+.1%}")
        ax.grid(alpha=0.3, which="both")
    fig.suptitle("alpha = same tile at gamma = 0, B = gc * ceil(M/TM) / M; "
                 f"{len(fit[HW])} runs per panel")
    fig.tight_layout()
    fig.savefig(out / "model_fit.png", dpi=130)
    plt.close(fig)

    # ---- README -------------------------------------------------------------
    L = [f"# {NAME}: software RNG vs hardware PRNG-FIFO", "",
         "Liang, Murray, Buluç, Demmel, *Fast multiplication of random dense "
         "matrices with sparse matrices* (arXiv 2310.15419) generate the random "
         "operand on the CPU core. Their cost model adds memory movement and "
         "generation, and their future work is \"specialized hardware for RNG\". "
         "This experiment runs both ways of generating B on the same device and "
         "compares each against loading B from memory:", "",
         f"- **{HW}** (FIFO capacity {CAPACITY[HW]}): the generator fills the FIFO "
         "while the core loads A and C, so generation overlaps memory work.",
         f"- **{SW}** (FIFO capacity {CAPACITY[SW]}): nothing is generated ahead; "
         "each pop waits g_c per element. This is the paper's additive model in "
         "its dense limit.", "",
         "The question: how much of the FIFO's advantage over memory-B comes from "
         "not loading B, and how much from generating asynchronously?", "",
         f"run: `.venv/bin/python experiments/rewrite/{NAME}.py`", "",
         "## How the paper maps onto the project", "",
         "Transpose their product to match ours: their Â = S·A is our "
         "Cᵀ = Bᵀ·Aᵀ.", "",
         "| Liang et al. | here |", "|---|---|",
         "| S, d×m, random, generated on the fly | B, K×N, from the generator |",
         "| A, m×n, sparse with density ρ | A, M×K, dense: their density-1 limit |",
         "| d, m, n | N, K, M |",
         "| block d1 × m1 × n1; Algorithm 1 does not block m | T_N × K × T_M; "
         "T_K = K |",
         "| h: cost to generate one number, in memory accesses | γ: generation "
         "cost per element over memory cost per element (a line fetch shared by "
         "64/B_P elements) |",
         "| cache holds the output block and the A block, S is never cached: "
         "d1·n1 + m1·n1·ρ ≤ M | C tile + A band ≤ L1, the f ≤ 1 of "
         "fifo_feasibility (which counts the C tile twice for LRU) |",
         "| generation per MAC h/n1 | g_c·⌈M/T_M⌉/M ≈ g_c/T_M |",
         "| cost = memory + generation | software RNG: α + B term. Hardware "
         "FIFO: max(α, B term) |",
         "| Algorithm 3 (regenerate per use) vs Algorithm 4 (reuse a generated "
         "column) | C-stationary vs B-stationary, see `dataflow.py` |", "",
         "Not carried over: sparsity (CSC/CSR, skipping empty rows), their "
         "√(hM) block-size result (it needs blocking of the inner dimension, "
         "and here T_K = K), multithreading and the least-squares application. "
         "The software mode serialises generation with blocking memory accesses; "
         "an out-of-order CPU overlaps some of it, so this is the worst case for "
         "software, not a model of their machines.", "",
         "## Setup", "",
         "Everything as in `fifo_feasibility` (its README defines ρ, λ, γ and f):",
         f"M, N, K = {M}, {N}, {K}; A_P = {A_P} B; L1 {L1 // 1024} KB fully "
         f"associative LRU, {LINE} B lines, no L2; L1 hit {L1_CYC} cycles; pop = "
         "one L1 hit; mulacc 0; 4×4 registers; B-stationary; `--aligned`. "
         "Swept: ρ ∈ {" + ", ".join(f"{r:g}" for r in RHOS) + "}, λ ∈ {"
         + ", ".join(map(str, LAMBDAS)) + "}, γ ∈ {" + ", ".join(f"{g:g}" for g in GAMMAS)
         + "}, T_M 4..96, T_N ∈ {" + ", ".join(map(str, TNS)) + "}. Each side "
         "takes its best (T_M, T_N).", "",
         "h = γ·λ·B_P/64 is the generation cost per element in L1-hit times.", "",
         f"{len(keys)} runs.", ""]

    L += ["## Results", "", "![speedup](speedup_vs_gamma.png)", "",
          "Break-even against memory-B (γ* where the speedup crosses 1, "
          "log-interpolated; `inf`: still winning at γ = 8), also in L1 hits "
          "per element:", "",
          f"| ρ | λ | γ* {HW} | γ* {SW} | h* {HW} | h* {SW} |",
          "|---|---|---|---|---|---|"]
    for rho, lam in product(RHOS, LAMBDAS):
        gh, gs = gstar[(rho, lam, HW)], gstar[(rho, lam, SW)]
        L.append(f"| {rho:g} | {lam} | {fmt(gh)} | {fmt(gs)} "
                 f"| {fmt(l1_hits(gh, lam, rho), 1)} | {fmt(l1_hits(gs, lam, rho), 1)} |")

    L += ["", "Speedup over memory-B at each γ (hardware / software):", "",
          "| ρ | λ | " + " | ".join(f"γ={g:g}" for g in GAMMAS) + " |",
          "|---|---|" + "---|" * len(GAMMAS)]
    for rho, lam in product(RHOS, LAMBDAS):
        cells = [f"{h:.2f} / {s:.2f}" for h, s in
                 zip(speedup[(rho, lam, HW)], speedup[(rho, lam, SW)])]
        L.append(f"| {rho:g} | {lam} | " + " | ".join(cells) + " |")

    L += ["", "![overlap](overlap_gain.png)", "",
          "Best software-RNG cycles / best hardware-FIFO cycles:", "",
          "| ρ | λ | " + " | ".join(f"γ={g:g}" for g in GAMMAS) + " |",
          "|---|---|" + "---|" * len(GAMMAS)]
    for rho, lam in product(RHOS, LAMBDAS):
        L.append(f"| {rho:g} | {lam} | "
                 + " | ".join(f"{x:.2f}" for x in gains[(rho, lam)]) + " |")

    L += ["", "Tiles picked (T_M×T_N) by the software RNG, for comparison with "
          "fifo_feasibility's hardware-FIFO table:", "",
          "| ρ | λ | memory | " + " | ".join(f"γ={g:g}" for g in GAMMAS) + " |",
          "|---|---|---|" + "---|" * len(GAMMAS)]
    for rho, lam in product(RHOS, LAMBDAS):
        row = [f"{rho:g}", str(lam), f"{mem[(rho, lam)][1]}x{mem[(rho, lam)][2]}"]
        row += [f"{bst[(rho, lam, SW, g)][1]}x{bst[(rho, lam, SW, g)][2]}" for g in GAMMAS]
        L.append("| " + " | ".join(row) + " |")

    L += ["", "![fit](model_fit.png)", "",
          "Each run against its model, with α measured at the same tile with "
          "γ = 0:", "",
          "| mode | model | runs | median abs. error | within 1 % | worst over | worst under |",
          "|---|---|---|---|---|---|---|"]
    for src, model in ((HW, "max(α, B)"), (SW, "α + B")):
        med, hi, lo, within = fit_stats(fit[src])
        L.append(f"| {src} | {model} | {len(fit[src])} | {med:.2%} | {within:.0%} "
                 f"| {hi:+.1%} | {lo:+.1%} |")

    sw = [gstar[(r, l, SW)] for r, l in product(RHOS, LAMBDAS)]
    hw = [x for x in (gstar[(r, l, HW)] for r, l in product(RHOS, LAMBDAS)) if not math.isinf(x)]
    hw_inf = sum(math.isinf(gstar[(r, l, HW)]) for r, l in product(RHOS, LAMBDAS))
    med, hi, _, within = fit_stats(fit[HW])
    s1 = {lam: (speedup[(1, lam, HW)][GAMMAS.index(0.5)],
                speedup[(1, lam, SW)][GAMMAS.index(0.5)]) for lam in LAMBDAS}
    L += ["", "## Reading the results", "", OBSERVATIONS.format(
        sw_lo=min(sw), sw_hi=max(sw), hw_lo=min(hw), hw_hi=max(hw), hw_inf=hw_inf,
        gain45=max(gains[(1, 45)]), gain100=max(gains[(1, 100)]),
        hw45=s1[45][0], sw45=s1[45][1], hw100=s1[100][0], sw100=s1[100][1],
        n=len(fit[SW]), med=med, within=within, worst=hi,
        cap=CAPACITY[HW], per_tile=K * max(TNS),
    ).strip(), ""]
    (out / "README.md").write_text("\n".join(L))
    print("\n".join(L[L.index("## Results"):]))


OBSERVATIONS = """
**A software RNG breaks even at γ ≈ 1; the hardware FIFO at γ ≈ 4 to 8 or
more.** Software γ* is {sw_lo:.2f} to {sw_hi:.2f} in all eight (ρ, λ) cases.
That is what the additive model predicts: at the same T_M, memory-B pays
mem·B_P/64 cycles per B element and the software RNG pays g_c, and γ is
exactly their ratio. The small excess over 1 is the L1 traffic memory-B also
spends on B. It is the paper's own condition for generating on the fly,
h < 1. The hardware FIFO breaks even at γ = {hw_lo:.2f} to {hw_hi:.2f} where
the grid reached it, and still wins at γ = 8 in {hw_inf} cases. So the FIFO's
tolerance beyond "generate faster than DRAM" comes entirely from overlapping
generation with memory work.

**Below γ = 1 software also beats memory-B, by less.** At γ = 0.5, ρ = 1:
{sw45:.2f}× against the hardware FIFO's {hw45:.2f}× at λ = 45, and
{sw100:.2f}× against {hw100:.2f}× at λ = 100.

**Overlap is worth up to {gain100:.2f}×.** Best software cycles over best
hardware cycles grow with γ to {gain45:.2f} (λ = 45) and {gain100:.2f}
(λ = 100), near 2, the most max(a, b) can save over a + b. The ratio is
(α + B) / max(α, B) at the tiles each mode picks, so it peaks where
generation and memory work take about the same time. At λ = 100 it
zigzags: when the best tile jumps from 48×16 to 96×64, α and the B term
move apart and the ratio drops before climbing again. The rows for
different ρ are the same numbers shifted one γ column per halving of B_P:
at fixed γ, g_c is proportional to B_P, and neither generator mode depends
on ρ otherwise. The gain is a function of g_c alone.

**Each cost model describes its own mode.** Software runs match α + B in all
{n} runs to within 0.0 %. Hardware runs match max(α, B) with a median error
of {med:.1%} and {within:.0%} within 1 %, but up to {worst:+.0%} near the
balance point, where the per-tile FIFO restart and bursty consumption cost
extra (see `overlap_fit`). The paper's additive model is right for a
generator that blocks the core, and max is right for a decoupled one: the
difference comes from the hardware, not the workload.

**Tile choice barely changes.** Software picks 48×16 until generation
dominates and then 96×64, one γ step earlier than the hardware FIFO at
λ = 45 and at the same step at λ = 100. Neither mode shows the paper's
√(hM) block growth, as expected without inner-dimension blocking: T_M jumps
from just below the L1 cliff to M/2.

**Caveats.** The software mode serialises generation with blocking memory
accesses, the pessimistic end for a CPU, where out-of-order execution and
prefetching hide some of each; a real software RNG sits between the two
curves. The hardware FIFO has {cap} elements, more than one tile consumes
(at most K·T_N = {per_tile}) and it is emptied at every tile, so its capacity
never binds. A FIFO small enough to bind gives results in between.
"""


if __name__ == "__main__":
    main()
