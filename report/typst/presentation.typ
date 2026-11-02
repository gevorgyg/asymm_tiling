// ==========================================================
// Final presentation: the report (main.typ) without the text.
// Compile with `typst compile presentation.typ`
// ==========================================================

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#let title = "Evaluating Matrix Tiling Multiplication For Asymmetric Data Cost"
#let author = "Regev Ginzburg, Areg Mkhitaryan"
#let course = "Project Aleph Spring 2026"
#let date = datetime.today().display("[month repr:long] [day], [year]")

#let accent = rgb("#1a4f8b")
#let muted = rgb("#666666")

#set page(
  paper: "presentation-16-9",
  margin: (x: 1.5cm, top: 1.3cm, bottom: 1.1cm),
  footer: context {
    set text(size: 11pt, fill: muted)
    if counter(page).get().first() > 1 [#h(1fr) #counter(page).display()]
  },
)
#set text(font: "Noto Sans", size: 19pt)
#set par(justify: false)
#set list(spacing: 0.75em)
#set enum(spacing: 0.75em)

// ---------------- Slide helpers ----------------
#let slide(title, body) = {
  pagebreak(weak: true)
  text(size: 26pt, weight: "bold", fill: accent, title)
  v(0.5em)
  body
}

// points on the left, a figure on the right
#let fig-slide(title, img, points, ratio: (1fr, 2fr)) = slide(title, grid(
  columns: ratio,
  gutter: 1cm,
  align(horizon, points),
  align(horizon, image("./figures/" + img + ".svg", width: 100%)),
))

// a wide figure with a line or two under it
#let wide-slide(title, img, points, height: 66%) = slide(title, {
  align(center, image("./figures/" + img + ".svg", height: height))
  v(0.3em)
  points
})

#let section(title) = {
  pagebreak(weak: true)
  align(center + horizon, text(size: 34pt, weight: "bold", fill: accent, title))
}

// ---------------- Title ----------------
#align(center + horizon)[
  #text(size: 32pt, weight: "bold", fill: accent, title)
  #v(0.8cm)
  #text(size: 20pt, author)
  #v(0.3cm)
  #text(size: 16pt, fill: muted)[#course #h(0.6em) | #h(0.6em) #date]
]

// ---------------- Introduction ----------------
#slide("Motivation")[
  - Multiplying by a random matrix $B$ is a core building block of RandNLA
    - sketching, low-rank approximation, least squares, random features
  - $B$ carries no information of its own, so it is cheap to provide
    - lower precision: one bit or byte per element
    - or no storage at all: generated on the fly by a PRNG from a seed
  - $=>$ an *asymmetric access cost*: $B$ is much cheaper than $A$ and $C$
]

#slide("Previous Results By Bharadwaj And Demmel")[
  - Tiling keeps tiles in the cache so every loaded element is reused
  - All matrices cost the same $=>$ square tiles are optimal
  - $B$ cheaper to load (a fraction $rho$ of $A$) $=>$ the tile stretches along $B$:
    $ T_N / T_M = 1 / rho $
  - *Our question:* with a PRNG, $B$ costs *time*, not traffic, and it overlaps with the work on $A$ and $C$.
    How should we tile now, and how should the hardware be balanced?
]

#slide("Hardware Background")[
  #grid(
    columns: (1fr, 1fr),
    gutter: 1.2cm,
    [
      *Matrix multiply accelerators*
      - TPU: $256 times 256$ systolic array
      - Tensor cores: small blocks in hardware
      - Registers $->$ cache $->$ DRAM
      - Dataflow: which matrix stays in place
    ],
    [
      *PRNGs*
      - Stateful: LFSR, xorshift, Mersenne Twister
        - cheap, but a fixed order
      - Counter-based: Philox
        - any element, any order, more work
      - For tiling only one number matters: $g_c$, cycles per element
    ],
  )
]

// ---------------- The hardware system ----------------
#let box-fill = rgb("#eef3fa")
#let gen-fill = rgb("#fbf1e6")
#let small(it) = text(size: 7.5pt, fill: rgb("#444444"), it)
#let step(n) = box(baseline: 25%, circle(radius: 4.2pt, stroke: 0.5pt, inset: 0pt,
  align(center + horizon, text(size: 6pt, fill: black, str(n)))))
#let ctrl = (dash: "dashed", thickness: 0.6pt)

#slide("The Hardware System")[
  #align(center, scale(132%, reflow: true, {
      set text(size: 9pt, hyphenate: false)
      diagram(
        spacing: (10mm, 12mm),
        node-stroke: 0.6pt,
        node-corner-radius: 3pt,
        node-inset: 6pt,
        edge-stroke: 0.7pt,
        node((0, 0), [*DRAM* \ #small[$A$, $C$, seeds of $B$]], name: <dram>, fill: box-fill, width: 25mm),
        node((1.2, 0), [*$L_2$* \ #small[optional]], name: <l2>, fill: box-fill, stroke: (dash: "dashed", thickness: 0.6pt), width: 16mm),
        node((2.4, 0), [*$L_1$ data cache*], name: <l1>, fill: box-fill, width: 27mm),
        node((4, 0), [*Load/store unit*], name: <lsu>, fill: white, width: 24mm),
        node((4, 1.2), [*Register file* \ #small[blocks of $A$, $B$, $C$]], name: <regs>, fill: white, width: 28mm),
        node((5.2, 1.2), [*MAC unit*], name: <mac>, fill: white, width: 16mm),
        node(enclose: (<lsu>, <regs>, <mac>), name: <core>, fill: box-fill, stroke: 0.8pt, inset: 7pt, corner-radius: 5pt),
        node((5.2, 0), [*Core*], stroke: none, fill: none),
        node((1.2, 1.2), [*Generator* \ #small[one element of $B$] \ #small[every $g_c$ cycles]], name: <gen>, fill: gen-fill, width: 27mm),
        node((2.4, 1.2), [*FIFO*], name: <fifo>, fill: gen-fill, width: 16mm),
        node((1.2, 2.2), [*Seed register*], name: <seed>, fill: gen-fill, width: 27mm),
        node(enclose: (<gen>, <fifo>, <seed>), name: <pf>, stroke: 0.8pt, inset: 7pt, corner-radius: 5pt),
        node((2.3, 2.2), [*PRNG-FIFO*], stroke: none, fill: none),
        edge(<dram>, <l2>, "<|-|>"),
        edge(<l2>, <l1>, "<|-|>"),
        edge(<l1>, <lsu>, "<|-|>", [#step(1) #step(3) #step(5)], label-side: left, label-pos: 0.4),
        edge(<lsu>, <regs>, "<|-|>"),
        edge(<regs>, (4, 2.75), (1.2, 2.75), <seed>, "-|>", [#step(1) #small[seed]], label-side: left, label-pos: 0.45),
        edge(<seed>, <gen>, "-|>"),
        edge(<gen>, <fifo>, "-|>", small[$B$], label-side: left),
        edge(<fifo>, <regs>, "-|>", [#step(2) #small[pop $B$]], label-side: right),
        edge(<regs>, <mac>, "<|-|>", step(4), label-side: left),
        edge(<fifo>, <gen>, "-|>", small[full: pause], bend: -50deg, stroke: ctrl, label-side: right),
        edge(<fifo>, <regs>, "-|>", small[empty: stall], bend: 40deg, stroke: ctrl, label-side: left),
      )
    }))
  #v(0.2em)
  #set text(size: 16pt)
  #let big-step(n) = box(baseline: 22%, circle(radius: 8pt, stroke: 0.8pt, inset: 0pt,
    align(center + horizon, text(size: 11pt, str(n)))))
  #align(center)[
    #big-step(1) seed #h(0.8em) #big-step(2) pop $B$ (wait if empty) #h(0.8em) #big-step(3) load $A$, $C$ #h(0.8em)
    #big-step(4) multiply #h(0.8em) #big-step(5) store $C$ \
    #text(fill: muted)[In-order core, only the generator runs in parallel]
  ]
]

#slide("Research Goals")[
  + Build a cycle-level simulator of a core, a cache hierarchy and a PRNG-FIFO
  + Reproduce the Bharadwaj model
  + Choose the dataflow that suits a PRNG-FIFO
  + Find the best tile, and how it changes with $g_c$
  + Build a model that explains and predicts it
  + Answer design questions for software and hardware engineers
]

// ---------------- Methodology ----------------
#fig-slide("The asymm_tiling Simulator", "architecture", [
  - Cycle-level, C++20
  - Tiles, dataflows, PRNG-FIFO, multi-level cache
  - Correctness:
    - diff-tested against a Python reference cache
    - Hypothesis traces, invariants
], ratio: (1fr, 1.5fr))

#slide("Default Parameters")[
  #set text(size: 17pt)
  #align(center, table(
    columns: 2,
    stroke: none,
    inset: (x: 14pt, y: 7pt),
    align: (left, left),
    table.hline(stroke: 0.6pt),
    [*Matrices* $M times K times N$], [$192 times 256 times 256$, 4-byte elements],
    [*Register block*], [$4 times 4$],
    [*$L_1$*], [16 KB, 64-byte lines, fully associative, LRU, 4 cycles],
    [*Memory latency*], [180 cycles],
    [*Generation cost* $g_c$], [swept, 0 to 600 cycles per element],
    [*FIFO*], [16384 elements, 2 cycles per pop],
    [*Compute unit*], [free],
    table.hline(stroke: 0.6pt),
  ))
  #v(0.4em)
  #align(center, text(fill: muted)[Every marker in a plot is a simulated point])
]

// ---------------- Experiments ----------------
#section("Experiments And Results")

#fig-slide("Reproducing The Bharadwaj Model", "fig_paper", [
  - $B$ stored at lower precision, ratio $rho$
  - Minimum moves to $T_N slash T_M = 1 slash rho$
  - Savings vs square: 18% and 36% (predicted 20% and 37%)
])

#fig-slide("B-Stationary vs C-Stationary", "fig_dataflow", [
  - $C$-stationary wins only for $g_c <= 4$
  - $B$-stationary shares each element of $B$ over $T_M$ rows instead of $R_M$
  - Up to 16$times$ faster
])

#fig-slide("Other Tiles, Other Hardware", "fig_dataflow_ratio", [
  - Same pattern for every height
  - Crossover at $g_c approx R_M dot T_B$
  - Ratio levels off at $T_M slash R_M$
  - $=>$ we use $B$-stationary
])

#fig-slide("The Best Tile", "fig_best_tile", [
  - $T_M$ grows to hide generation
  - $T_N$ grows, then shrinks to stay before the second cliff
  - Very slow generator: wide again, width no longer matters
])

#section("The Model")

#slide("From The Bharadwaj Model To Ours")[
  + Traffic $->$ cycles: measure the memory cost $alpha(T_M, T_N)$
  + Precision $->$ generation: $B$ costs $g_c slash T_M$ per MAC
  + Sum $->$ max: generation overlaps with memory
  #v(0.6em)
  $ T / (M N K) = max(alpha(T_M, T_N), g_c / T_M) $
]

#fig-slide("The Memory Cost α", "fig_alpha", [
  - A step function
  - Tile of $A$ fits: cheap
  - Strip of $A$ doesn't fit: wider tiles are cheaper
  - Tile of $C$ overflows: second cliff
])

#fig-slide("The Simple Model", "fig_model_simple", [
  - Runtime follows the higher curve
  - Best tile at the crossing
  - Misses heights that don't divide $M$
])

#fig-slide("Refinement 1: B Per Row Of Tiles", "fig_model", [
  - $B$ is generated once per row of tiles
  - Generation cost $g_c dot ceil(M slash T_M) slash M$
  - A staircase
])

#fig-slide("Refinements 2 And 3", "fig_model_refined", [
  - Startup: the FIFO starts empty
  - Max per row of tiles, short last row separately
  - Within 0.2% of the measurements
])

#fig-slide("Refinement 4: K", "sw_kmodel_alpha", [
  - $K$ only moves the first cliff
  - Fit test: $r(ceil(K slash E) + 2 ceil(T_N slash E)) < 256$
  - Two calibrations: one fits, one doesn't
])

// ---------------- Software ----------------
#section("Software Focused Design Questions")

#fig-slide("Can The Model Choose The Tile?", "fig_model_validation", [
  + Calibrate $alpha$ once at $g_c = 0$
  + Predict every tile
  + Pick the fastest
  - Within 1% in 96% of runs
  - Picked tile at most 0.1% slower
])

#fig-slide("Other Matrices: Pad The Rows", "sw_alignment", [
  - Rows of $C$ not whole cache lines $=>$ earlier thrashing
  - Pad every row to whole lines
])

#fig-slide("Other Matrices: Two Calibrations", "sw_kmodel", [
  - 130 matrices, 780 cases
  - Within 1% in 96%
  - Works for $K$ outside the calibrations
  - *Pad, calibrate twice, let the model choose*
])

#fig-slide("How Much Autotuning?", "sw_autotune", [
  - Square tiles alone: up to 2$times$ slower
  - Heights dividing $M$, power-of-two widths: within 10%
  - *Start small, add candidates if needed*
])

#fig-slide("Does The Choice Matter?", "fig_vs_square", [
  - Never worse than a square
  - Saves up to half of the runtime
  - *Don't default to a square tile*
])

// ---------------- Hardware ----------------
#section("Hardware Focused Design Questions")

#fig-slide("How Fast Must The Generator Be?", "hw_prng_budget", [
  - Free up to $g_c approx T_M dot alpha$
  - Doubling the cache $approx$ halving $g_c$
  - Up to $2 times$ that: \~5% slower
])

#fig-slide("How Big Must The FIFO Be?", "hw_fifo_size", [
  - One register block: up to a third slower
  - About 1 KB is enough
])

#wide-slide("FIFO Size On Other Hardware", "hw_fifo_configs", height: 56%, [
  - Grows with the register block and the memory latency, shrinks with a slower compute unit
  - *Size the FIFO by how fast the core consumes $B$*
])

#fig-slide("Bigger Cache Or Bigger FIFO?", "hw_sram_split", [
  - Too small a FIFO: slower
  - More than half the budget: catastrophic
  - *\~1 KB FIFO, the rest to the cache*
])

#fig-slide("Does The Cache Need To Be Fully Associative?", "hw_assoc_unpadded", [
  - Rows of $2^k$ lines land in the same sets
  - 2–6$times$ slower
  - More ways barely help
])

#fig-slide("Padding Fixes It", "hw_assoc_padded", [
  - Odd number of lines per row
  - 8-way $approx$ fully associative
  - *Ordinary 4- or 8-way cache + padding*
])

#fig-slide("Does The Replacement Policy Matter?", "hw_policy_alpha", [
  - Random smooths the cliffs
  - LRU evicts the line needed next in a loop
  - Random lets lines survive by chance
])

#fig-slide("LRU Or Random?", "hw_policy_slow", [
  - Normal generators: random up to 28% slower
  - Only extremely slow generators gain
  - *Keep LRU, choose a tile that fits*
])

#fig-slide("How Fast Must The Compute Unit Be?", "hw_compute_speed", [
  - Fast generator: compute cost adds directly
  - Slow generator: compute is hidden
  - Model: $alpha + c$
  - *As fast as the generator lets it be*
])

// ---------------- gem5 ----------------
#section("gem5 Simulation")

#slide("gem5 Setup")[
  - Modeled on TI's C7x DSP (C7524): 1 GHz, 32 KB $L_1$D, 64 KB $L_2$, 256-bit vectors
  - In-order Arm core with SVE
  - PRNG-FIFO as a new component between the core and $L_1$
  - Overlapping misses, prefetcher, branch prediction
  - $192 times 128 times 512$, free generator
]

#wide-slide("gem5: Cycles Per MAC", "gem5_cycles", [
  - Without padding, set conflicts dominate. With padding, the best tile is $48$–$64 times 64$
])

#fig-slide("gem5: Speedup Of The PRNG-FIFO", "gem5_speedup", [
  - No prefetcher: up to 1.33$times$
  - With prefetcher: memory $B$ is almost free
], ratio: (1fr, 2.2fr))

#fig-slide("gem5: Wrong-Path Reads", "gem5_mispredict", [
  - Mispredicted loop exits read the FIFO
  - Free with a free generator
  - Costly with a slow one
], ratio: (1fr, 1.6fr))

// ---------------- Discussion and conclusion ----------------
#slide("Discussion")[
  - Two costs pull the tile height in opposite directions
    - memory: keep it short, generation: make it tall
  - Hardware answers come back to $alpha$
  - Limits:
    - our simulator charges every miss in full, no prefetcher
    - mostly one matrix and one cache size
    - gem5 only with a free generator
]

#slide("Conclusion")[
  - Height of the best tile follows the generator, width follows the cache
  - $B$-stationary, unless generation costs a few cycles
  - A max of memory and generation per row of tiles predicts the best tile within 1%, from two calibrations
  #v(0.4em)
  - *Software:* pad, calibrate twice, let the model choose
  - *Hardware:* generator just fast enough, \~1 KB FIFO, the rest to an ordinary LRU cache
]

#section("Thank You")
