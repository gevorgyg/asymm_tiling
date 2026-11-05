// ==========================================================
// Final presentation: the report (main.typ) without the text.
// Compile with `typst compile presentation.typ`
// ==========================================================

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#let title = "Evaluating Matrix Tiling Multiplication For Asymmetric Data Cost"
#let author = "Regev Ginzburg, Areg Mkhitaryan"
#let course = "Project Aleph Spring 2026"
#let date = datetime.today().display("[month repr:long] [day], [year]")

#let accent = rgb("#5a95db")
#let accent-light = rgb("#e3eefa")
#let key-fill = rgb("#e8f0fa")
#let muted = rgb("#666666")

// the current section, shown in the footer
#let section-name = state("section-name", "Introduction")
#let section-count = counter("section")
#let question-count = counter("question")

#let margin-x = 1.5cm
#let margin-top = 2.6cm
#let bar-h = 1.9cm

#set page(
  paper: "presentation-16-9",
  margin: (x: margin-x, top: margin-top, bottom: 1.1cm),
  footer: context {
    set text(size: 11pt, fill: muted)
    section-name.get()
    h(1fr)
    [#counter(page).display() / #counter(page).final().first()]
  },
  // progress bar along the bottom edge
  background: context {
    let frac = counter(page).get().first() / counter(page).final().first()
    place(bottom + left, rect(width: 100% * frac, height: 5pt, fill: accent, stroke: none))
  },
)
#set text(font: "Noto Sans", size: 19pt)
#set par(justify: false)
#set list(spacing: 0.75em, marker: text(fill: accent, sym.bullet))
#set enum(spacing: 0.75em, numbering: n => text(fill: accent, weight: "bold", str(n) + "."))

// ---------------- Slide helpers ----------------
// a slide with its title on a blue bar across the top
// centers its body vertically in the space under the title bar
#let centered(body) = block(width: 100%, height: 100%, { v(1fr); body; v(1fr) })

#let slide(title, body) = {
  pagebreak(weak: true)
  place(top + left, dx: -margin-x, dy: -margin-top, block(
    width: 100% + 2 * margin-x, height: bar-h, fill: accent, inset: (x: margin-x),
    align(horizon, text(size: 26pt, weight: "bold", fill: white, title)),
  ))
  centered(body)
}

// a takeaway, in a soft box
#let key(body, bold: true) = block(
  fill: key-fill, stroke: (left: 4pt + accent), radius: (right: 4pt),
  inset: (x: 12pt, y: 9pt), width: 100%, above: 0.9em,
  if bold { text(weight: "bold", body) } else { body },
)

// a section divider: a full blue page, numbered unless number: false
#let section(title, number: true) = page(
  fill: accent, margin: (x: 2.2cm), footer: none, background: none,
  {
    if number { section-count.step() }
    section-name.update(title)
    question-count.update(0)
    set text(fill: white)
    align(left + horizon, {
      if number {
        context text(size: 26pt, weight: "bold", fill: accent-light,
          numbering("01", section-count.get().first()))
        v(0.2cm)
      }
      text(size: 38pt, weight: "bold", title)
      v(0.3cm)
      line(length: 5cm, stroke: 2pt + accent-light)
    })
  },
)

// a design question on its own page, before the slides that answer it;
// numbered within its section
#let question(q) = {
  pagebreak(weak: true)
  question-count.step()
  centered(align(center, {
    context text(size: 16pt, weight: "bold", fill: accent, tracking: 0.08em,
      upper[Question #question-count.display()])
    v(0.4cm)
    block(width: 20cm, text(size: 34pt, weight: "bold", fill: rgb("#1b2430"), q))
    v(0.3cm)
    line(length: 4cm, stroke: 2pt + accent)
  }))
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

// ---------------- Title ----------------
#page(fill: accent, margin: (x: 2.2cm), footer: none, background: none)[
  #set text(fill: white)
  #align(left + horizon)[
    #text(size: 34pt, weight: "bold", title)
    #v(0.2cm)
    #line(length: 5cm, stroke: 2pt + accent-light)
    #v(0.5cm)
    #text(size: 20pt, author)
    #v(0.1cm)
    #text(size: 16pt, fill: accent-light)[#course #h(0.6em) | #h(0.6em) #date]
  ]
]

// ---------------- Introduction ----------------
#slide("Motivation")[
  - Multiplying by a random matrix $B$ is a core building block of RandNLA
    - sketching, low-rank approximation, least squares, random features
  - $B$ carries no information of its own, so it is cheap to provide
    - lower precision: one bit or byte per element
    - or no storage at all: generated on the fly by a PRNG from a seed
  - an *asymmetric access cost*: $B$ is much cheaper than $A$ and $C$
]

#slide("Previous Results By Bharadwaj And Demmel")[
  - Tiling keeps tiles in the cache so every loaded element is reused
  - All matrices cost the same $=>$ square tiles are optimal
  - $B$ cheaper to load (a fraction $rho$ of $A$) $=>$ the tile stretches along $B$:
    $ T_N / T_M = 1 / rho $
  #key(bold: false)[*Our question:* with a PRNG, $B$ costs *time*, not traffic, and it overlaps with the work on $A$ and $C$.
    How should we tile now, and how should the hardware be balanced?]
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
// a numbered circle; the digit is placed, so every circle sits at the same height
#let num-circle(n, d, size, stroke) = box(width: d, height: d, radius: d / 2, stroke: stroke,
  baseline: 0.19 * d, place(center + horizon, text(size: size, fill: black, str(n))))
#let step(n) = num-circle(n, 8.4pt, 6pt, 0.5pt)
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
        edge(<fifo>, <regs>, "-|>", small[empty: stall], bend: 40deg, stroke: ctrl, label-side: left, label-pos: 0.35),
      )
    }))
  #v(0.2em)
  #set text(size: 16pt)
  #let big-step(n) = num-circle(n, 16pt, 11pt, 0.8pt)
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
  #section-name.update("Methodology")
  - Cycle accurate cache simulator built in C++20
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
      [*FIFO*], [$2^14$ elements, 2 cycles per pop],
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
])

#fig-slide("A Fairer Comparison: Each At Its Best Tile", "fig_dataflow_best", [
  - Each dataflow at its own best tile, for every $g_c$
  - $C$-stationary faster only for $g_c <= 3$
  - Then $B$-stationary wins by a growing margin
], ratio: (1fr, 1.6fr))

#fig-slide("Other Tiles, Other Hardware", "fig_dataflow_ratio", [
  - Same pattern for every height
  - Crossover at $g_c approx R_M dot T_B$
  - Ratio levels off at $T_M slash R_M$
  #key[We use $B$-stationary]
])

#fig-slide("The Best Tile", "fig_best_tile", [
  - $T_M$ grows to hide generation
  - $T_N$ grows, then shrinks to delay $C$ tile trashing
  - For a very slow generator $=>$ the bigger the better.
])

#section("The Model")

// the changed part of the formula, in the accent color
#let hl(it) = text(fill: accent, it)
#let before-after(before, after) = align(center, {
  set text(size: 26pt)
  grid(
    columns: 2,
    column-gutter: 1.2cm,
    row-gutter: 1.2em,
    align: (right + horizon, left + horizon),
    text(fill: muted)[Before:], math.equation(math.display(before.body)),
    text(fill: muted)[After:], math.equation(math.display(after.body)),
  )
})

#slide("Change 1: Traffic To Cycles")[
  - A real cache has hits, misses, tiles that fit or don't
  - Too hard to count, so we measure it
  - $alpha(T_M, T_N)$: cycles per MAC for $A$ and $C$, at $g_c = 0$
  #v(1.2em)
  #before-after(
    $1 / T_N + rho / T_M$,
    $hl(alpha(T_M, T_N)) + rho / T_M$,
  )
]

#slide("Change 2: Precision To Generation")[
  - $B$ is never stored, it is generated
  - $g_c$ cycles per element, shared by the $T_M$ rows of the tile
  #v(1.2em)
  #before-after(
    $alpha(T_M, T_N) + rho / T_M$,
    $alpha(T_M, T_N) + hl(g_c / T_M)$,
  )
]

#slide("Change 3: Sum To Max")[
  - The generator runs in the background
  - Generation overlaps with the work on $A$ and $C$
  - Only the slower one sets the runtime
  #v(1.2em)
  #before-after(
    $alpha(T_M, T_N) + g_c / T_M$,
    $hl(max)(alpha(T_M, T_N), g_c / T_M)$,
  )
]

#slide([Measuring α: Set $g_c = 0$])[
  - With $g_c = 0$ the generator is free: $B$ is always waiting in the FIFO
  - The generation side of the max disappears
  - So the runtime we measure is $alpha$ itself
  #v(1.2em)
  #align(center, text(size: 26pt, $ g_c = 0 quad arrow.r.double quad
    T / (M N K) = max(alpha(T_M, T_N), hl(0 / T_M)) = alpha(T_M, T_N) $))
  #v(0.8em)
  - One simulation per tile gives a table of $alpha$
  - The same table then serves every other $g_c$
]

#fig-slide("The Memory Cost α", "fig_alpha", [
  - A step function
  - Tile of $A$ fits: cheap
  - Strip of $A$ doesn't fit: wider tiles are cheaper
  - Tile of $C$ overflows: second cliff
])

#fig-slide("It's a Simple Model", "fig_model_simple", [
  - Runtime follows the higher curve
  - Best tile at the crossing
  - Misses heights that don't divide $M$
])

#fig-slide("Refinement 1: B Per Row Of Tiles", "fig_model", [
  - $B$ is generated once per row of tiles
  - Generation cost:\ $g_c dot ceil(M slash T_M) slash M$
  - Giving us a staircase
])

// matrix C cut into tiles, with a short last row and a narrow last tile
#let tile-fill = rgb("#eef3fa")
#let rest-fill = rgb("#f6d7b0")
#let c-tiles(row: false, col: false) = {
  set text(size: 14pt)
  let u = 1.5cm
  let heights = if row { (1, 1, 1, 0.4) } else { (1, 1, 1) }
  let widths = if col { (1, 1, 1, 1, 0.4) } else { (1, 1, 1, 1) }
  let last-r = heights.len()
  let last-c = widths.len()
  grid(
    columns: (auto,) + widths.map(w => w * u),
    rows: (auto,) + heights.map(h => h * u * 0.8),
    align: center + horizon,
    inset: 3pt,
    stroke: (x, y) => if x > 0 and y > 0 { 0.6pt },
    fill: (x, y) => if x == 0 or y == 0 { none }
      else if (row and y == last-r) or (col and x == last-c) { rest-fill }
      else { tile-fill },
    [], ..range(1, last-c + 1).map(x => if col and x == last-c { $e_N$ } else { $T_N$ }),
    ..for y in range(1, last-r + 1) {
      (if y == 1 { $T_M$ } else if y == last-r and row { $e$ } else { [] },)
      range(last-c).map(_ => [])
    },
  )
}

#slide("Refinement 2: Startup")[
  - Each tile loads its own seed, the FIFO starts empty
  - The core waits for the first block of $B$: $g_c R_M R_N$ cycles per tile
  - Only hurts when memory is the bottleneck $=>$ memory side of the max
  #v(1.2em)
  #before-after(
    $max(alpha(T_M, T_N), g_c / T_M)$,
    $max(alpha(T_M, T_N) + hl(s / T_M), g_c / T_M)$,
  )
  #v(0.4em)
  #align(center, text(size: 22pt, $ s = (g_c R_M R_N dot ceil(N slash T_N)) / (K N) $))
  #align(center, text(size: 15pt, fill: muted)[the wait of one tile, times the tiles in a row of tiles, spread over the $K N$ MACs of one row of $C$])
]

#slide("Refinement 3: The Short Last Row (M)")[
  #grid(
    columns: (1.3fr, 1fr),
    gutter: 1cm,
    align(horizon)[
      - $T_M$ doesn't divide $M$ $=>$ a short last row, height $e = M mod T_M$
      - Every row of tiles generates all of $B$
      - Full rows wait for memory, the short row waits for generation
      - The waits add up $=>$ max per row
    ],
    align(center + horizon, c-tiles(row: true)),
  )
  #v(0.6em)
  #set text(size: 18pt)
  $ T / (M N K) = 1 / M (floor(M / T_M) dot max(T_M dot overline(alpha)(T_M, T_N) + s, g_c)
    + hl(max(e dot overline(alpha)(e, T_N) + s, g_c))) $
]

#slide("Refinement 3: The Narrow Last Tile (N)")[
  #grid(
    columns: (1.3fr, 1fr),
    gutter: 1cm,
    align(horizon)[
      - $T_N$ doesn't divide $N$ $=>$ a narrow last tile, width $e_N = N mod T_N$
      - It has its own $alpha$
      - $overline(alpha)$: the average over the row, weighted by width
    ],
    align(center + horizon, c-tiles(col: true)),
  )
  #v(0.6em)
  #set text(size: 20pt)
  $ overline(alpha)(r, T_N) = (floor(N / T_N) dot T_N dot alpha(r, T_N) + hl(e_N dot alpha(r, e_N))) / N $
]

#fig-slide("The Refined Model", "fig_model_refined", [
  - Startup on the memory side
  - Max per row, short last row separately
  - Within 0.2% of the measurements
  - Tiles divide the matrix $=>$ back to the simple model
])

#fig-slide("Refinement 4: Generalizing for many matrices", "sw_kmodel_alpha", [
  - $alpha$ was measured at one $K$
  - $M$ and $N$ are in the formula, $K$ isn't
  - Every $K$: the same two levels
  - Only the first cliff moves
], ratio: (1fr, 1.6fr))

// L1 as a bar of cache lines, for a row of tiles of height 16 and T_N = 16
#let a-fill = rgb("#cfe0f5")
#let a-ink = rgb("#2c6db5")
#let c-ink = rgb("#c46a12")
#let l1-bars = {
  set text(size: 14pt)
  let lw = 0.045cm
  let h = 1cm
  let lab = 3cm
  let gap = 0.5cm
  let seg(n, fill, body) = box(width: n * lw, height: h, fill: fill, stroke: 0.6pt,
    align(center + horizon, body))
  let bar(k, verdict) = grid(
    columns: (lab, auto, auto),
    column-gutter: (0cm, 0.4cm),
    align: horizon,
    [$K = #k$],
    stack(dir: ltr, seg(k, a-fill)[strip of $A$], seg(16, rest-fill, $C$), seg(16, rest-fill, $C$)),
    verdict,
  )
  block(inset: (top: 0.9cm), {
    set align(left)
    stack(spacing: gap,
      bar(128, text(fill: rgb("#2e7d32"))[fits]),
      bar(256, text(fill: rgb("#c62828"))[doesn't fit]),
    )
    place(top + left, dx: lab + 256 * lw, dy: -0.25cm,
      line(angle: 90deg, length: 2 * h + gap + 0.5cm, stroke: (dash: "dashed", thickness: 1.2pt)))
    place(top + left, dx: lab + 256 * lw - 1.6cm, dy: -0.9cm, text(size: 13pt)[$L_1$: 256 lines])
  })
}

#slide("Refinement 4: Why The Cliff Moves")[
  - A line of $A$ is used in one tile, and again in the next tile
  - In between: the rest of the strip of $A$, this tile of $C$ and the next tile of $C$
  - All of it has to fit in $L_1$
  #v(0.4em)
  #align(center, l1-bars)
  #v(0.2em)
  #align(center, text(size: 15pt, fill: muted)[a row of tiles of height $r = 16$, $T_N = 16$])
  $ r dot (text(fill: #a-ink, ceil(K / E)) + text(fill: #c-ink, 2 ceil(T_N / E))) < |L_(1 "lines")| $
  #align(center, text(size: 15pt, fill: muted)[$E$: elements per cache line (16) #h(1.2em) $|L_(1 "lines")|$: lines in $L_1$ (256)])
]

#slide("Refinement 4: A Small Drift In K")[
  - Inside each level, $alpha$ still drifts a little with $K$
  - The reason is $C$:
    - every line of $C$ is loaded from memory once: $L_"mem"$ cycles for $E$ elements
    - every element of $C$ is used by $K$ MACs
  #v(1em)
  #set text(size: 22pt)
  #let tx(it) = text(font: "Noto Sans", size: 22pt, it)
  $ underbrace(L_"mem" / E, #tx[per element of $C$]) dot underbrace(1 / K, #tx[$K$ MACs share it])
    = hl(L_"mem" / (E K)) #text(font: "Noto Sans")[ cycles per MAC] $
  #v(0.3em)
  #align(center, text(size: 15pt, fill: muted)[$L_"mem"$: memory latency (180 cycles)])
]

#slide("Refinement 4: The Formula")[
  - Two levels $=>$ two tables, one calibration each
  - Plus the drift in $K$
  #v(1em)
  #before-after(
    $alpha(r, T_N)$,
    $hl(cases(alpha_"fits" (r, T_N) & #text(font: "Noto Sans")[if the row fits], alpha_"no fit" (r, T_N) & #text(font: "Noto Sans")[otherwise])) + hl(L_"mem" / (E K))$,
  )
]

#let flow-node(pos, body, name, fill: tile-fill) = node(pos, body, name: name, fill: fill)

#slide("Refinement 4: The Whole Process")[
  #align(center, scale(104%, reflow: true, {
    set text(size: 14pt, hyphenate: false)
    diagram(
      spacing: (9mm, 9mm),
      node-stroke: 0.6pt,
      node-corner-radius: 3pt,
      node-inset: 7pt,
      edge-stroke: 0.8pt,
      flow-node((0, 0), [Simulate \ small $K$, $g_c = 0$], <cs>),
      flow-node((0, 1.4), [Simulate \ large $K$, $g_c = 0$], <cl>),
      flow-node((1, 0), [$alpha_"fits"$ table], <tf>, fill: a-fill),
      flow-node((1, 1.4), [$alpha_"no fit"$ table], <tn>, fill: a-fill),
      node(enclose: (<cs>, <cl>, <tf>, <tn>), name: <once>, stroke: (dash: "dashed", thickness: 0.6pt), inset: 10pt),
      flow-node((2, 0.7), [Fit test \ picks a table], <fit>, fill: rest-fill),
      flow-node((3, 0.7), [$+ L_"mem" slash (E K)$], <k>, fill: rest-fill),
      flow-node((4, 0.7), [Refined model \ (max per row)], <model>, fill: rest-fill),
      flow-node((5, 0.7), [Fastest tile], <best>, fill: white),
      node(enclose: (<fit>, <k>, <model>), name: <every>, stroke: (dash: "dashed", thickness: 0.6pt), inset: 10pt),
      node((0.5, -0.75), text(fill: muted)[once], stroke: none),
      node((3, -0.2), text(fill: muted)[every tile of \ a new matrix], stroke: none),
      edge(<cs>, <tf>, "-|>"),
      edge(<cl>, <tn>, "-|>"),
      edge(<tf>, <fit>, "-|>"),
      edge(<tn>, <fit>, "-|>"),
      edge(<fit>, <k>, "-|>"),
      edge(<k>, <model>, "-|>"),
      edge(<model>, <best>, "-|>"),
    )
  }))
]

// ---------------- Software ----------------
#section("Software Focused Design Questions")

#question[Can Our Model Be Trusted To Choose The Tile?]

#fig-slide("Can The Model Choose The Tile?", "fig_model_validation", [
  + Calibrate $alpha$ once at:\ $g_c = 0$
  + Predict every tile
  + Pick the fastest
  results:
  - Within 1% in 96% of runs
  - Picked tile at most 0.1% slower
])

#question[Does The Model Work \ For Other Matrices?]

#fig-slide("Other Matrices: Pad The Rows", "sw_alignment", [
  - Rows of $C$ that not whole cache lines cause earlier thrashing
  - Solution: Pad every row to whole lines
])

#slide("Other Matrices: Two Calibrations")[
  #align(center, image("./figures/sw_kmodel.svg", width: 92%))
  #v(0.4em)
  #grid(
    columns: (1fr, 1fr),
    gutter: 1cm,
    [
      - Within 1% in 96%
    ],
    [
      - Works for $K$ outside the calibrations
    ],
  )
]

#question[How Much Autotuning \ Is Needed?]

#fig-slide("How Much Autotuning?", "sw_autotune", [
  - Square tiles alone: up to 2$times$ slower
  - Heights dividing $M$, power-of-two widths: within 10%
  #key[Start small, add candidates if needed]
])

#question[Does The Choice Of Tile Matter?]

#fig-slide("Does The Choice Matter?", "fig_vs_square", [
  - Never worse than a square
  - Saves up to half of the runtime
  - Even when a square is best, the model tells which square
])

// ---------------- Hardware ----------------
#section("Hardware Focused Design Questions")

#question[How Fast Must \ The Generator Be?]

#fig-slide("How Fast Must The Generator Be?", "hw_prng_budget", [
  - Generation is as good as free up to $g_c approx T_M dot alpha$
  - Doubling the \ cache $approx$ halving $g_c$
])

#question[How Big Must The FIFO Be?]

#fig-slide("How Big Must The FIFO Be?", "hw_fifo_size", [
    - Less slowdown as capacity grows
    - Slower generation can sometimes afford a smaller FIFO
])

#wide-slide("FIFO Size On Other Hardware", "hw_fifo_configs", height: 62%, [
  - Grows with the register block and the memory latency, shrinks with a slower compute unit
  #key[Size the FIFO by how fast the core consumes $B$]
])

#question[Should We Use A Bigger Cache Or A Bigger FIFO?]

#fig-slide("Bigger Cache Or Bigger FIFO?", "hw_sram_split", [
  - When too much goes to the cache $=>$ sligtly slower runtime 
  - When too much goes to the FIFO $=>$ horrible performance
  - As soon as the FIFO is big enough the rest should go to the cache
])

#question[Does The Cache Need \ To Be Fully Associative?]

#fig-slide("Does The Cache Need To Be Fully Associative?", "hw_assoc_unpadded", [
  - more than 2$times$ slower
  - More ways barely help
  - Rows of $2^k$ lines land in the same sets
])

// where the rows of one tile column land in a 16 KB 8-way L1 (32 sets x 8 ways):
// row r starts at line r * stride, so it goes to set (r * stride) mod 32.
// Cells above the 8 ways are rows that want that set but don't fit.
#let miss-fill = rgb("#f6d0cc")
#let miss-ink = rgb("#c62828")
#let set-map(stride, nrows: 24, ways: 8, over: 4) = {
  let sets = range(32).map(s => range(nrows).filter(r => calc.rem(r * stride, 32) == s))
  let cell(body, fill, stroke) = box(width: 100%, height: 100%, fill: fill, stroke: stroke,
    align(center + horizon, text(size: 7.5pt, body)))
  grid(
    columns: (0.72cm,) * 32,
    rows: (0.33cm,) * (over + ways) + (auto,),
    ..for level in range(over + ways) {
      let slot = over + ways - 1 - level          // 0 = the bottom way
      range(32).map(s => {
        let rows = sets.at(s)
        let has = slot < rows.len()
        if slot < ways {
          cell(if has [#rows.at(slot)], if has { a-fill } else { white }, 0.4pt + rgb("#9aa7b6"))
        } else if has {
          cell(text(fill: miss-ink)[#rows.at(slot)], miss-fill, 0.4pt + miss-ink)
        } else { [] }
      })
    },
    ..range(32).map(s => align(center, text(size: 7pt, fill: muted, str(s)))),
  )
}

#slide("Why Padding Works: Where The Rows Land")[
  #set text(size: 16pt)
  - 16 KB 8-way $L_1$ = 32 sets $times$ 8 lines. Row $r$ goes to set $(r dot "lines per row") mod 32$
  - One step touches the same column of every row of the tile, here 24 rows
  #v(0.2em)
  #grid(
    columns: (auto, 1fr),
    column-gutter: 0.6cm,
    row-gutter: (0.4em, 1.1em, 0.4em),
    align: (right + horizon, left + horizon),
    [*Rows of 256* \ #text(size: 13pt, fill: muted)[16 lines, no padding]], set-map(16),
    [], text(size: 13pt)[Every row lands on set 0 or 16. Only 16 rows fit, the other #text(fill: miss-ink)[8 thrash]],
    [*Rows of 272* \ #text(size: 13pt, fill: muted)[17 lines, padded]], set-map(17, over: 0),
    [], text(size: 13pt)[The rows spread over all the sets, one line each, and all 24 fit],
  )
]

#fig-slide("Padding Fixes It", "hw_assoc_padded", [
  - Odd number of lines per row
  - 8-way $approx$ fully associative
  #key[Ordinary 4- or 8-way cache + padding]
])

// the lines of one tile of C in the 32 sets of a 16 KB 8-way L1, rows of 17 lines:
// line j of row r goes to set (17 r + j) mod 32. A set with 8 lines of C has no room for A.
#let tile-sets(h, w, stride: 17, ways: 8) = {
  let sets = range(32).map(s => {
    let rows = ()
    for r in range(h) { for j in range(w) { if calc.rem(stride * r + j, 32) == s { rows.push(r) } } }
    rows
  })
  let cell(body, fill, stroke) = box(width: 100%, height: 100%, fill: fill, stroke: stroke,
    align(center + horizon, text(size: 7pt, body)))
  grid(
    columns: (0.72cm,) * 32,
    rows: (0.33cm,) * ways + (auto,),
    ..for level in range(ways) {
      let slot = ways - 1 - level
      range(32).map(s => {
        let rows = sets.at(s)
        let full = rows.len() >= ways
        if slot < rows.len() {
          cell([#rows.at(slot)], rest-fill, if full { 0.9pt + miss-ink } else { 0.4pt + rgb("#9aa7b6") })
        } else { cell([], white, 0.4pt + rgb("#9aa7b6")) }
      })
    },
    ..range(32).map(s => {
      let full = sets.at(s).len() >= ways
      align(center, text(size: 7pt, fill: if full { miss-ink } else { muted }, weight: if full { "bold" } else { "regular" }, str(s)))
    }),
  )
}

#slide("The Small Spike: A Wide Tile Of C")[
  #set text(size: 16pt)
  - At $g_c approx 15$–$20$ the best tile is 24 × 128: its tile of $C$ alone is 192 lines
  #v(0.2em)
  #grid(
    columns: (auto, 1fr),
    column-gutter: 0.6cm,
    row-gutter: (0.4em, 1.1em, 0.4em),
    align: (right + horizon, left + horizon),
    [*24 × 128* \ #text(size: 13pt, fill: muted)[$g_c approx 15$–$20$]], tile-sets(24, 8),
    [], text(size: 13pt)[4 to 8 lines of $C$ per set. #text(fill: miss-ink)[Sets 6, 7, 8 and 23 are full], so the lines of $A$ there thrash],
    [*32 × 64* \ #text(size: 13pt, fill: muted)[$g_c approx 30$]], tile-sets(32, 4),
    [], text(size: 13pt)[Exactly 4 lines of $C$ in every set, room for $A$ everywhere, same as fully associative],
  )
]

#question[Does The Replacement \ Policy Matter?]

#fig-slide("Does The Replacement Policy Matter?", "hw_policy_alpha", [
  - Random smooths the cliffs
  - LRU evicts the line needed next in a loop
  - Random lets lines survive by chance
])

#fig-slide("LRU Or Random?", "hw_policy_slow", [
  - For normal generator, random up to 28% slower
  - Only extremely slow generators make random worth it
])

#question[How Fast Must The \ Compute Unit Be?]

#fig-slide("How Fast Must The Compute Unit Be?", "hw_compute_speed", [
  - Fast generator: compute cost adds directly
  - Slow generator: compute is hidden
  - Model: $alpha + c$
  #key[As fast as the generator lets it be]
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

#wide-slide("gem5: Cycles Per MAC", "gem5_cycles", height: 76%, [
  - Without padding, set conflicts dominate. With padding, the best tile is $48$–$64 times 64$
])

#wide-slide("gem5: Cache Misses", "gem5_misses", height: 64%, [
  - The steps are capacity limits
  - $T_M = 64$: the strip of $A$ no longer fits in $L_1$ (24 KB at $T_M = 48$)
  - $T_M = 192$: the strip of $A$ (96 KB) no longer fits in $L_2$
])

#wide-slide("gem5: Speedup Of The PRNG-FIFO", "gem5_speedup", height: 62%, [
  - No prefetcher: up to 1.33$times$
  - With prefetcher: memory $B$ is almost free
])

#fig-slide("gem5: Wrong-Path Reads", "gem5_mispredict", [
  - Mispredicted loop exits read the FIFO
  - Free with a free generator
  - Costly with a slow one
], ratio: (1fr, 1.6fr))

// ---------------- Discussion and conclusion ----------------
#slide("Discussion")[
  #section-name.update("Discussion And Conclusion")
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

#section("Thank You", number: false)


