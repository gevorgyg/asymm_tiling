// ==========================================================
// Final presentation: the report (main.typ) without the text.
// Compile with `typst compile presentation.typ`
// ==========================================================

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
#import "@preview/cetz:0.3.4"

#let title = "Evaluating Matrix Tiling Multiplication For Asymmetric Data Cost"
#let author = "George Ginzburg, Areg Mkhitaryan"
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
#slide("Motivation: Random Matrices In Practice")[
  - *scikit-learn* random projections: data $times$ a random Gaussian or sparse matrix
  - *scikit-learn* PCA: randomized SVD, the default for large inputs
  - *PyTorch* `torch.svd_lowrank`: the same randomized SVD
  - *SciPy* `clarkson_woodruff_transform`: a random sketch for least squares
  - *scikit-learn* `RBFSampler`: random features for kernel methods
  - *Apache Spark*: random projections to find similar items
]

// ---------------- Animations: how tiling works, how a PRNG works ----------------
// Every frame of a sequence has the same title and layout, only the colors change,
// so paging through the frames looks like an animation.
#let an-a = rgb("#cfe0f5")
#let an-a2 = rgb("#6fa3e0")
#let an-b = rgb("#d3efe2")
#let an-b2 = rgb("#5dbb8d")
#let an-c = rgb("#f6d7b0")
#let an-c2 = rgb("#e39a4a")
#let an-done = rgb("#e2ddd5")
#let an-gen = rgb("#fbf1e6")
#let an-grid = rgb("#9aa7b6")

// a matrix of rows x cols cells; thick lines every tr rows / tc columns
#let an-mat(rows, cols, fill, tr: none, tc: none, s: 0.6cm) = grid(
  columns: (s,) * cols,
  rows: (s,) * rows,
  fill: fill,
  stroke: (x, y) => (
    left: if tc != none and calc.rem(x, tc) == 0 or x == 0 { 1.2pt + black } else { 0.4pt + an-grid },
    top: if tr != none and calc.rem(y, tr) == 0 or y == 0 { 1.2pt + black } else { 0.4pt + an-grid },
    right: if x == cols - 1 { 1.2pt + black } else { 0.4pt + an-grid },
    bottom: if y == rows - 1 { 1.2pt + black } else { 0.4pt + an-grid },
  ),
  ..range(rows * cols).map(_ => []),
)

// the list of steps on the left, the current one highlighted
#let an-steps(steps, cur) = {
  set text(size: 17pt)
  for (i, s) in steps.enumerate() {
    let now = i == cur
    block(above: 0.55em, below: 0em, grid(
      columns: (0.9em, 1fr),
      align: top,
      text(fill: if now { accent } else { rgb("#c0c7d0") }, weight: "bold", if now [▶] else [•]),
      text(fill: if i <= cur { black } else { rgb("#b5bcc5") }, weight: if now { "bold" } else { "regular" }, s),
    ))
  }
}

// C = A B with M = 8, K = 6, N = 8 and tiles of 4 x 4
#let tiling-steps = (
  [One element of $C$ = a row of $A$ × a column of $B$],
  [Tiling: compute $C$ one tile ($T_M times T_N$) at a time],
  [A tile needs a strip of $A$ and a panel of $B$],
  [Step $k$: a column of $A$ × a row of $B$ updates the whole tile],
  [Next step],
  [... until the last step, the tile is done],
  [Next tile: the *same* strip of $A$, a new panel of $B$],
  [Next row of tiles: a new strip of $A$, $B$ again from the left],
)
#let tiling-frame(n) = {
  let T = 4
  // what each frame shows
  let elem = if n == 0 { (1, 2) } else { none }
  let tile = (none, (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 1), (1, 0)).at(n)
  let done = ((), (), (), (), (), (), ((0, 0),), ((0, 0), (0, 1))).at(n)
  let strip = n >= 2
  let k = (none, none, none, 0, 1, 5, none, none).at(n)
  let in-tile(t, r, c) = t != none and calc.quo(r, T) == t.at(0) and calc.quo(c, T) == t.at(1)
  let a-fill(x, y) = {   // A: rows y, columns x (= k)
    if elem != none { if y == elem.at(0) { an-a2 } else { white } }
    else if strip and calc.quo(y, T) == tile.at(0) { if k != none and x == k { an-a2 } else { an-a } }
    else { white }
  }
  let b-fill(x, y) = {   // B: rows y (= k), columns x
    if elem != none { if x == elem.at(1) { an-b2 } else { white } }
    else if strip and calc.quo(x, T) == tile.at(1) { if k != none and y == k { an-b2 } else { an-b } }
    else { white }
  }
  let c-fill(x, y) = {
    if elem != none { if (y, x) == elem { an-c2 } else { white } }
    else if in-tile(tile, y, x) { if k != none { an-c2 } else { an-c } }
    else if done.any(t => in-tile(t, y, x)) { an-done }
    else { white }
  }
  slide("How Tiling Works", grid(
    columns: (1fr, auto),
    gutter: 1cm,
    align(horizon, an-steps(tiling-steps, n)),
    align(horizon, grid(
      columns: (auto, auto, auto),
      column-gutter: 0.25cm,
      row-gutter: 0.25cm,
      align: center + horizon,
      [], [], [*B* #h(0.3em) #text(size: 13pt, fill: muted)[$K times N$]],
      [], [], an-mat(6, 8, b-fill, tc: if n >= 1 { T } else { none }),
      [*A* \ #text(size: 13pt, fill: muted)[$M times K$]], an-mat(8, 6, a-fill, tr: if n >= 1 { T } else { none }),
      an-mat(8, 8, c-fill, tr: if n >= 1 { T } else { none }, tc: if n >= 1 { T } else { none }),
      [], [], [*C* #h(0.3em) #text(size: 13pt, fill: muted)[$M times N$]],
    )),
  ))
}
#for n in range(tiling-steps.len()) { tiling-frame(n) }

// a PRNG: a seed, a state that is updated every step, one number of B out per step
#let prng-values = (-0.99, 0.32, -0.78, 0.7, 0.75, -0.33, 0.73, 0.13, 0.45, -0.5, 0.39, 0.57,
  0.42, -0.48, -0.09, -0.49, -0.75, -0.98, 0.62, 0.26, 0.51, 0.13, 0.12, 0.14)   // xorshift32, seed 42
#let prng-steps = (
  [Load a seed],
  [Each step updates the state and gives one number of $B$, $g_c$ cycles],
  [The numbers fill $B$ in the order the core uses it],
  [The whole panel of $B$, nothing read from memory],
  [Same seed $=>$ same numbers: $B$ is made again for every row of tiles],
)
#let prng-frame(n) = {
  let shown = (0, 1, 8, 24, 24).at(n)
  let again = n == 4
  let hot = n == 0 or again
  let num(v) = box(width: 1.25cm, height: 0.62cm, stroke: 0.5pt + an-grid, fill: an-b,
    align(center + horizon, text(size: 11pt, str(v))))
  slide("How A PRNG Works", grid(
    columns: (1fr, auto),
    gutter: 1cm,
    align(horizon, an-steps(prng-steps, n)),
    align(horizon + center, {
      set text(size: 13pt)
      // seed -> generator
      grid(
        columns: (auto, auto, auto),
        column-gutter: 0.35cm,
        align: horizon,
        box(stroke: if hot { 1.6pt + accent } else { 0.7pt }, fill: an-gen, inset: 8pt, radius: 3pt)[*Seed* \ 42],
        text(size: 18pt)[→],
        box(stroke: 0.7pt, fill: an-gen, inset: 8pt, radius: 3pt, align(left)[
          *Generator* (xorshift) \
          #text(font: "Noto Sans Mono", size: 10pt)[x ^= x << 13 \ x ^= x >> 17 \ x ^= x << 5]
        ]),
      )
      v(0.3cm)
      text(size: 18pt)[↓]
      v(0.1cm)
      // the panel of B, filled row by row
      grid(
        columns: (1.25cm,) * 4,
        rows: (0.62cm,) * 6,
        ..range(24).map(i => if i < shown { num(prng-values.at(i)) } else {
          box(width: 1.25cm, height: 0.62cm, stroke: 0.5pt + an-grid)
        }),
      )
      v(0.15cm)
      text(fill: muted)[a panel of $B$ ($K times T_N$)]
      linebreak()
      // always takes its line, so the frames don't move
      let note = text(fill: accent, weight: "bold")[again, the same numbers]
      if again { note } else { hide(note) }
    }),
  ))
}
#for n in range(prng-steps.len()) { prng-frame(n) }

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
  // a datapath-style block diagram: square boxes, hollow block arrows for data buses,
  // thin lines for single signals, dashed lines for control, the MAC drawn as an ALU,
  // the FIFO as a queue of slots (the head, on the left, is popped first)
  #align(center, cetz.canvas(length: 1.2cm, {
    import cetz.draw: *
    let lbl(it) = text(size: 9pt, tracking: 0.04em, upper(it))
    let sub(it) = text(size: 7pt, fill: rgb("#555555"), it)
    let blk(a, b, name, extra: none, dash: false) = {
      rect(a, b, fill: white, stroke: if dash { (thickness: 0.8pt, dash: "dashed") } else { 0.8pt })
      let c = ((a.at(0) + b.at(0)) / 2, (a.at(1) + b.at(1)) / 2)
      content(c, align(center, stack(dir: ttb, spacing: 4pt, lbl(name), ..if extra != none { (sub(extra),) })))
    }
    // a hollow block arrow from a to b (axis aligned), with a head at one or both ends
    let barrow(a, b, both: false, w: 0.15, hw: 0.32, hl: 0.26) = {
      let (x1, y1) = a
      let (x2, y2) = b
      let L = calc.sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1))
      let (ux, uy) = ((x2 - x1) / L, (y2 - y1) / L)
      let P(t, s) = (x1 + ux * t - uy * s, y1 + uy * t + ux * s)
      let pts = if both {
        (P(0, 0), P(hl, hw), P(hl, w), P(L - hl, w), P(L - hl, hw), P(L, 0),
         P(L - hl, -hw), P(L - hl, -w), P(hl, -w), P(hl, -hw))
      } else {
        (P(0, w), P(L - hl, w), P(L - hl, hw), P(L, 0), P(L - hl, -hw), P(L - hl, -w), P(0, -w))
      }
      line(..pts, close: true, fill: white, stroke: 0.7pt)
    }
    let wire(..pts, dashed: false) = line(..pts, stroke: if dashed { (thickness: 0.6pt, dash: "dashed") } else { 0.6pt },
      mark: (end: ">", fill: black, scale: 0.6))
    let note(pos, it, anchor: "west") = content(pos, text(size: 7.5pt, it), anchor: anchor)

    // groups
    rect((0.6, -4.75), (12.75, -8.95), fill: rgb("#f4f7fb"), stroke: (thickness: 0.6pt, dash: "dotted"))
    content((0.75, -8.75), text(size: 8pt, weight: "bold")[IN-ORDER CORE], anchor: "west")
    rect((13.55, -1.4), (19.75, -6.4), fill: rgb("#fbf6ee"), stroke: (thickness: 0.6pt, dash: "dotted"))
    content((13.7, -1.6), text(size: 8pt, weight: "bold")[PRNG-FIFO], anchor: "west")

    // memory hierarchy (left column)
    blk((1, 0), (5, -1), [DRAM], extra: [$A$, $C$, seeds])
    blk((1, -1.7), (5, -2.7), [$L_2$ cache], extra: [optional], dash: true)
    blk((1, -3.4), (5, -4.4), [$L_1$ D-cache], extra: [64 B lines])
    blk((1, -5.1), (5, -6.1), [Load / store unit])
    barrow((3, -1), (3, -1.7), both: true)
    barrow((3, -2.7), (3, -3.4), both: true)
    barrow((3, -4.4), (3, -5.1), both: true)
    note((3.45, -4.75), [#step(1) #step(3) #step(5)])

    // core (center)
    blk((7, -5.1), (12, -6.1), [Register file], extra: [blocks of $A$, $B$, $C$])
    barrow((5, -5.6), (7, -5.6), both: true)
    // the MAC as an ALU
    line((7.6, -6.9), (11.4, -6.9), (10.6, -7.9), (8.4, -7.9), close: true, fill: white, stroke: 0.8pt)
    content((9.5, -7.4), align(center, stack(dir: ttb, spacing: 4pt, lbl[MAC array], sub[$R times R$])))
    barrow((8.6, -6.1), (8.6, -6.9))
    barrow((10.4, -6.1), (10.4, -6.9))
    note((8.75, -6.5), [$A$])
    note((10.55, -6.5), [$B$])
    note((11.25, -7.4), step(4))
    // the result goes back to the register file (accumulate C)
    line((9.5, -7.9), (9.5, -8.45), (7.3, -8.45), (7.3, -6.1), stroke: 0.6pt, mark: (end: ">", fill: black, scale: 0.6))
    note((7.4, -8.25), [$C$ (accumulate)])

    // PRNG-FIFO (right column)
    blk((14, -2.0), (18, -3.0), [Seed register])
    blk((14, -3.6), (18, -4.6), [Generator], extra: [1 element per $g_c$ cycles])
    rect((14, -5.1), (18, -6.1), fill: white, stroke: 0.8pt)
    content((16, -5.28), lbl[FIFO])
    for i in range(8) {
      let x = 14.25 + i * 0.44
      rect((x, -5.45), (x + 0.44, -5.95), fill: if i < 5 { rgb("#d9d9d9") } else { white }, stroke: 0.5pt)
      if i < 5 { content((x + 0.22, -5.7), text(size: 6.5pt, $b$)) }
    }
    wire((16, -3.0), (16, -3.6))                       // seed -> generator
    barrow((17.3, -4.6), (17.3, -5.1))                  // push at the tail
    note((16.95, -4.85), [push], anchor: "east")
    barrow((14, -5.6), (12, -5.6))                      // pop at the head
    note((12.25, -5.25), [#step(2) pop])
    // the core writes the seed
    wire((9.5, -5.1), (9.5, -2.5), (14, -2.5))
    note((9.65, -2.3), [#step(1) write seed])
    // control signals
    wire((18, -5.6), (18.9, -5.6), (18.9, -4.1), (18, -4.1), dashed: true)
    note((18.95, -4.85), [full])
    wire((16, -6.1), (16, -7.4), (12.75, -7.4), dashed: true)
    note((12.9, -7.2), [empty: stall])
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

#slide("Research Goals")[
  + Build a cycle-level simulator, and check it against the Bharadwaj results
  + Find what the best tile looks like, and how it changes with $g_c$
  + Build a model that predicts the best tile
  + Check how well the model chooses the tile, also for other matrices
  + Answer design questions for engineers who use or build such a system
  + Check the results on a more realistic core with gem5
]

// ---------------- Experiments ----------------
#section("Experiments And Results")

#slide("Previous Results By Bharadwaj And Demmel")[
  - Tiling keeps tiles in the cache so every loaded element is reused
  - All matrices cost the same $=>$ square tiles are optimal
  - $B$ cheaper to load (a fraction $rho$ of $A$) $=>$ the tile stretches along $B$:
    $ T_N / T_M = 1 / rho $
  #key(bold: false)[*Our question:* with a PRNG, $B$ costs *time*, not traffic, and it overlaps with the work on $A$ and $C$.
    How should we tile now, and how should the hardware be balanced?]
]

#fig-slide("Reproducing The Bharadwaj Model", "fig_paper", [
  - $B$ stored at lower precision, ratio $rho$
  - Minimum moves to $T_N slash T_M = 1 slash rho$
  - Savings vs square: 18% and 36% (predicted 20% and 37%)
])

#fig-slide("B-Stationary vs C-Stationary", "fig_dataflow_best", [
  - Each dataflow at its own best tile, for every $g_c$
  - $C$-stationary faster only for $g_c <= 3$
  - $B$-stationary shares each element of $B$ over $T_M$ rows instead of $R_M$
  #key[We use $B$-stationary]
], ratio: (1fr, 1.6fr))

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

#slide("The Bharadwaj Model")[
  - The cost of a tile is its memory traffic per MAC
  - An element of $A$ is reused by the $T_N$ columns of the tile, an element of $B$ by its $T_M$ rows
  - $B$ costs a fraction $rho$ of $A$
  #v(1em)
  #align(center, text(size: 26pt, {
    let tx(it) = text(font: "Noto Sans", size: 26pt, it)
    $ "traffic" / "MAC" = underbrace(1 / T_N, #tx[$A$]) + underbrace(rho / T_M, #tx[$B$]) $
  }))
  #v(0.4em)
  #align(center)[For a fixed tile area it is smallest at $T_N slash T_M = 1 slash rho$]
]

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

#fig-slide("The Best Tile", "fig_best_tile", [
  - $T_M$ grows to hide generation
  - $T_N$ grows, then shrinks to delay $C$ tile thrashing
  - For a very slow generator $=>$ the bigger the better.
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
    - every line of $C$ is loaded from memory once, a compulsory miss: $L_"mem"$ cycles for $E$ elements
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

#fig-slide("Bigger Cache Or Bigger FIFO?", "hw_sram_split", [
  - When too much goes to the cache $=>$ slightly slower runtime 
  - When too much goes to the FIFO $=>$ horrible performance
  - As soon as the FIFO is big enough the rest should go to the cache
])

#question[Does The Replacement \ Policy Matter?]

#fig-slide("Does The Replacement Policy Matter?", "hw_policy_alpha", [
  - Random smooths the cliffs
  - LRU evicts the line needed next in a loop
  - Random lets lines survive by chance
])

// ---------------- gem5 ----------------
#section("gem5 Simulation")

#slide("gem5 Setup")[
  - Our simulator charges every miss in full. On a real core misses overlap
  - gem5: the sizes of TI's C7x DSP (C7524), 1 GHz, 32 KB $L_1$D, 64 KB $L_2$, 256-bit vectors
  - gem5's in-order Arm core (`MinorCPU`) with SVE
  - Two sources of $B$ (int8): *$B$ in memory*, or the *PRNG-FIFO* between the core and $L_1$
  - $192 times 128 times 512$, 35 tiles, $g_c = 0$ first, then 1 to 128
]

#wide-slide([gem5: Cycles Per MAC ($g_c = 0$)], "gem5_cycles", height: 66%, [
  - With padding: best tile $64 times 64$ for both, 0.44 ($B$ in memory) and 0.41 (PRNG-FIFO) cycles per MAC
  - Without padding: set conflicts rule, only short tiles are good
])

#wide-slide("gem5: Cache Misses", "gem5_misses", height: 60%, [
  - The steps are capacity limits: the strip of $A$ stops fitting in $L_1$ at $T_M = 64$, in $L_2$ at $T_M = 192$
  - The prefetcher only helps at $T_M = 8$, where every load walks memory with a fixed 32-byte stride
])

#wide-slide("gem5: Speedup Of The PRNG-FIFO", "gem5_speedup", height: 60%, [
  - Same tile: 1.00$times$ to 1.96$times$, it follows the traffic of $B$ ($prop 1 slash T_M$)
  - Best tile against best tile: 8%, and 28% without padding
])

#slide("gem5: Branch Prediction And The FIFO")[
  - The core runs ahead after a mispredicted loop exit
  - A load of $B$ on that wrong path reaches the FIFO before the branch resolves
  - Counter PRNG-FIFO: the extra elements are thrown away, costs only generation time
  - Seeded PRNG-FIFO: the stream shifts, the rest of the tile gets the *wrong* $B$
  #block(fill: rgb("#f5f7fa"), stroke: 0.6pt + rgb("#d0d7e0"), radius: 4pt,
    inset: (x: 12pt, y: 9pt), width: 100%, above: 0.9em)[
    #show raw: set text(font: "Noto Sans Mono", size: 14pt)
    ```
    tile 1: seed1 -> b1 b2 b3 b4 b5 ...
      needs:  step 1: b1 b2   step 2: b3 b4
      gets:   step 1: b1 b2   (b3 on the wrong path)   step 2: b4 b5   <- wrong C
    tile 2: seed2 -> FIFO emptied and restarted, the shift does not carry over
    tile 3: seed3 -> ...
    ```
  ]
  #key[FIFO must pop only on reads that commit]
]

#wide-slide("gem5: A Slow Generator", "gem5_gencost_tiles", height: 58%, [
  - Up to $g_c = 16$ nothing changes: generation is hidden
  - From $g_c = 32$ the best tile grows taller: $96 times 16$, then $192 times 64$, then $192 times 16$
])

#fig-slide("gem5: Is The PRNG-FIFO Worth It?", "gem5_gencost_speedup", [
  - Against the best tile with $B$ in memory
  - Breaks even at $g_c approx 32$
  - Keeping the tile of $g_c = 0$: 3$times$ slower at $g_c = 128$
  - Our model $max(alpha, g_c slash T_M)$: within 3% of gem5, picks its best tile
], ratio: (1fr, 1.3fr))

#slide("gem5 Against Our Simulator")[
  #grid(
    columns: (1fr, auto),
    gutter: 1cm,
    align(horizon)[
      - Our simulator run on the gem5 setup
      - Its tile loses less than 1% in gem5 at 7 of 9 values of $g_c$
      - Off only at $g_c = 16$ and 32, where memory and generation are equal: ours charges misses in full, so it goes tall sooner
    ],
    align(horizon, {
      set text(size: 14pt)
      table(
        columns: 4,
        stroke: none,
        inset: (x: 8pt, y: 4pt),
        align: (right, center, center, right),
        table.hline(stroke: 0.6pt),
        [*$g_c$*], [*gem5 best*], [*ours*], [*loss*],
        table.hline(stroke: 0.4pt),
        [0], [$64 times 64$], [$48 times 16$], [0.5%],
        [1–4], [$64 times 64$], [$32 times 32$], [0.6%],
        [8], [$64 times 64$], [$64 times 64$], [0.0%],
        [16], [$64 times 64$], [$96 times 16$], [6.7%],
        [32], [$96 times 16$], [$192 times 64$], [18.6%],
        [64], [$192 times 64$], [$192 times 64$], [0.0%],
        [128], [$192 times 16$], [$192 times 64$], [0.2%],
        table.hline(stroke: 0.6pt),
      )
    }),
  )
]

// ---------------- Discussion and conclusion ----------------
#slide("Future Studies")[
  #section-name.update("Future Studies")
  - More matrices and cache sizes, to see how the thresholds move
  - Going in much further on every one of the experiments we showed
  - Researching the mathematical model further to achieve a deterministic model
  - Predict $alpha$ from the cache parameters instead of calibrating it for every new hardware
]

#section("Thank You", number: false)


