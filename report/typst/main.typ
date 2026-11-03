// ==========================================================
// Minimal Project Report Template
// ==========================================================
// Usage: fill in the metadata below, then write your report
// in the body. Compile with `typst compile report-template.typ`
// ==========================================================

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#let title = "Evaluating Matrix Tiling
Multiplication For Asymmetric Data Cost"
#let author = "Regev Ginzburg, Areg Mkhitaryan"
#let course = "Project Aleph Spring 2026"
#let date = datetime.today().display("[month repr:long] [day], [year]")

// ---------------- Page & text setup ----------------
#set page(
  paper: "a4",
  margin: (top: 3cm, bottom: 3cm, left: 2.5cm, right: 2.5cm),
  numbering: "1",
  number-align: center,
)

#set text(
  font: "New Computer Modern",
  size: 11pt,
  lang: "en",
)

#set par(
  justify: true,
  leading: 0.65em,
  first-line-indent: 0pt,
)

#set heading(numbering: "1.1")

// Heading styles
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(0.5em)
  text(size: 18pt, weight: "bold", it)
  v(0.8em)
}

#show heading.where(level: 2): it => {
  v(0.6em)
  text(size: 14pt, weight: "bold", it)
  v(0.4em)
}

#show heading.where(level: 3): it => {
  v(0.4em)
  text(size: 12pt, weight: "bold", style: "italic", it)
  v(0.2em)
}

// Code block style
#show raw.where(block: true): it => block(
  width: 100%,
  fill: rgb("#f5f5f5"),
  inset: 10pt,
  radius: 4pt,
  it,
)

// Figure caption style
#show figure.caption: it => {
  text(size: 9.5pt, style: "italic", it)
}

// Link style
#show link: it => text(fill: rgb("#1a4f8b"), it)

// ---------------- Title page ----------------
#align(center)[
  #v(4cm)
  #text(size: 24pt, weight: "bold", title)
  #v(0.5cm)
  #text(size: 13pt, fill: rgb("#555555"), course)
  #v(3cm)
  #text(size: 13pt, author)
  #v(0.3cm)
  #text(size: 11pt, fill: rgb("#555555"), date)
]

#pagebreak()

// ---------------- Table of contents ----------------
#outline(
  title: "Contents",
  indent: auto,
)

#pagebreak()

// ---------------- Body ----------------
#set page(numbering: "1")
#counter(page).update(1)

= Introduction

== Background: Caches, Memory, Matrix Multiplication

A processor computes much faster than main memory (DRAM) can deliver data. Small, fast caches close to the core hold recently used data, so that repeated uses of the same data are served quickly @hennessy2017.

Caches are also widely used for high performance matrix computation. Computing $C = A dot B$ with $A in RR^(M times K)$ and $B in
RR^(K times N)$ takes $M N K$ multiply-accumulates (MACs). A straightforward loop nest streams through the matrices and, once they no longer fit in the cache, loads each element from memory over and over. *Tiling* splits the computation into tiles small enough to stay in the cache, so that a loaded element is reused many times before it is evicted.

We know that when all matrices cost the same to access, square tiles are optimal @notes-random-tiling. This project researches when and why
rectangular tiles can perform better than the well known square tiles.

== Motivation: The Importance Of An Asymmetric Data Access Model <sec-importance>

Multiplying data by a random matrix is a core building block of randomized numerical linear algebra (RandNLA) @halko2011
@woodruff2014 @martinsson2020 @murray2023. A random projection (or sketch), compresses a large matrix into a much smaller one
while approximately preserving most of its geometry. Sketching underlies fast algorithms for low-rank approximation and least-squares problems. In machine learning, random features approximate kernel methods by a multiplication with a random matrix @rahimi2007.

In all of these algorithms the random matrix $B$ carries no information of its own, making it much cheaper to provide than the
data it multiplies, in a couple of ways.

Firstly, it can afford to have lower precision. An element of $B$ can be stored in a single bit or byte @achlioptas2003, while $A$ and $C$ keep full precision. This is an asymmetric-precision matrix multiplication, which reduces cache traffic, as shown by Bharadwaj and Demmel @notes-random-tiling @notes-asym-cost and in our experiments (@reproduce).

Secondly, the matrix can have no storage at all. $B$ can be generated on the fly from a small seed by a pseudo-random number
generator (PRNG), as the computation consumes it. $B$ then causes no memory traffic at all, only generation time. The only thing
we need to store are negligibly sized seeds.

Either way, accessing $B$ costs much less than accessing $A$ and $C$, which is the asymmetric-access-cost that this project studies.

== Hardware Background: Matrix Multiply Accelerators And PRNGs <sec-hw-background>

Matrix multiplication dominates machine learning and much of scientific computing, so many processors add special hardware dedicated to
it specifically. Google's TPU multiplies matrices on a $256 times 256$ systolic array of MAC units, fed from a large on-chip memory
@jouppi2017tpu, and NVIDIA's tensor cores multiply small blocks of matrices in hardware @markidis2018tensor.

These designs share a hierarchy that feeds a fast compute unit. A small block of each matrix sits in registers next to the MAC
units, larger tiles sit in a cache or a scratchpad, and the full matrices sit in DRAM. The compute unit is so fast that
performance is decided by moving data through this hierarchy, and a common way to describe a design is by which matrix stays in
place while the others stream past its dataflow @chen2016eyeriss.

A PRNG produces a long sequence of numbers that looks random from a short seed. Most classic generators keep a state and update it
for every number. A linear feedback shift register (LFSR) shifts its state by one bit and feeds back an XOR of a few of its bits
@golomb1967shift, which in hardware costs only a register and a few gates. Xorshift generators @marsaglia2003xorshift apply the
same idea with shifts and XORs of whole words, and the Mersenne Twister @matsumoto1998mt keeps a much larger state for a longer
period and better statistics. On FPGAs, generators built from shift registers and XORs produce a new number every cycle, with a
quality comparable to good software generators @thomas2013lutsr. All of these produce their numbers in a fixed order, so the
$i$-th number can only be reached by producing every number before it. Either kind of generator can sit next to the core and feed it it's $B$ matrix.
A stateful generator fits a FIFO that the core reads in order, restarted from a seed for every tile. For the tiling, what matters is not which generator is used,
but how many cycles it needs for each element of $B$, which we call the generation cost $g_c$.

= Research Goals And Outline <sec-goals>

Earlier work on a similar question by Bharadwaj and Demmel counts the data moved between memory and the cache, and shows that the best
tile is no longer square. Instead it stretches along the cheap matrix @notes-random-tiling @notes-asym-cost. With a hardware PRNG,
however, $B$ costs time rather than traffic, and its generation runs in parallel with the work on $A$ and $C$. Our goal is to
understand how this changes the way a matrix multiplication should be tiled, and to turn that understanding into something a
hardware and software engineer can use to their advantage.

To get there, we:

+ Build a cycle-level simulator of a core with a cache hierarchy and a PRNG-FIFO.
+ Check that it reproduces the previous results of Bharadwaj and Demmel (@reproduce).
+ Choose the dataflow that suits a PRNG-FIFO best (@sec-dataflow).
+ Find the best tile by simulation, and follow how its shape changes with the cost of generation (@sec-tile).
+ Develop a simple model that explains these tiles and predicts the runtime of a tile when $B$ is generated by the PRNG-FIFO,
  and refine it until it matches the simulator (@sec-simple-model).
+ Answer practical design questions: which tile a software engineer should choose, and how a hardware engineer should balance the cache, the FIFO and the generator.

== Notation <sec-notation>

@tab-notation lists the symbols used throughout the report, as a reference for the reader. Each one is also explained where it
first appears.

#figure(
  table(
    columns: 3,
    align: (center, left, left),
    table.header([*Symbol*], [*Meaning*], [*Unit or default*]),
    table.cell(colspan: 3)[_Matrices and tiles_],
    [$A, B, C$], [$C = A dot B$, where $B$ is the random matrix], [],
    [$M, K, N$], [$A$ is $M times K$, $B$ is $K times N$, $C$ is $M times N$], [$192 times 256 times 256$],
    [MAC], [one multiply-accumulate, the whole product takes $M N K$ of them], [],
    [$T_M, T_N$], [tile height and width: a tile computes $T_M times T_N$ elements of $C$, over all of $K$], [elements],
    [row of tiles], [the tiles that share the same $T_M$ rows of $A$, computed one after the other along $N$], [],
    [$r$], [the height of a row of tiles: $T_M$, or $e$ for the short last row], [elements],
    [$e, e_N$], [what is left at the edge: $e = M mod T_M$ (short last row), $e_N = N mod T_N$ (narrow last tile)], [elements],
    [$R_M, R_N, R_K$], [register block: the core loads $R_M times R_N$ blocks, and one block multiply is $R_M R_N R_K$ MACs], [$4 times 4$ ($R_K = 4$)],
    table.cell(colspan: 3)[_Hardware_],
    [$L_1, L_2$], [the first and second cache levels], [16 KB $L_1$, no $L_2$],
    [$E$], [elements in one cache line: line size divided by element size], [$64 slash 4 = 16$],
    [$L_"mem"$], [memory (DRAM) latency], [180 cycles],
    [$g_c$], [generation cost: the time the generator takes to produce one element of $B$], [cycles per element],
    [$c$], [the cost of one MAC: the inverse of the compute unit's throughput], [cycles per MAC (default 0)],
    [$rho$], [in the reproduction of the Bharadwaj model only: the cost of bringing an element of $B$ into the cache, relative to one of $A$], [],
    table.cell(colspan: 3)[_Model_],
    [$T$], [runtime, and $T slash (M N K)$ is the runtime per MAC], [cycles],
    [$alpha$], [memory cost: the runtime per MAC when generation is free ($g_c = 0$)], [cycles per MAC],
    [$overline(alpha)$], [the average $alpha$ over a row of tiles whose last tile is narrower], [cycles per MAC],
    [$alpha_"fits", alpha_"no fit"$], [the two levels of $alpha$: the strip of $A$ of a row of tiles stays in $L_1$ or not], [cycles per MAC],
    [$s$], [the startup of one row of tiles: the FIFO starts empty at every tile], [same units as $g_c$],
  ),
  caption: [The symbols used throughout the report.],
) <tab-notation>

= The Hardware System <sec-system>

The system we study is a single core that computes $C = C + A dot B$ (@fig-system). $A$ and $C$ are ordinary data. They live in
DRAM and reach the core through a cache hierarchy, an $L_1$ data cache and possibly an $L_2$. $B$ is never stored. A PRNG next to
the core, the generator, produces it from a seed, one element every $g_c$ cycles, into a FIFO, and the core reads $B$ only from
this FIFO.

#let box-fill = rgb("#eef3fa")
#let gen-fill = rgb("#fbf1e6")
#let small(it) = text(size: 7.5pt, fill: rgb("#444444"), it)
// a numbered step of the flow of a tile, as in the list below the figure
#let step(n) = box(baseline: 25%, circle(radius: 4.2pt, stroke: 0.5pt, inset: 0pt,
  align(center + horizon, text(size: 6pt, fill: black, str(n)))))
#let ctrl = (dash: "dashed", thickness: 0.6pt)

#figure(
  {
  set par(justify: false)
  set text(size: 9pt, hyphenate: false)
  diagram(
    spacing: (10mm, 12mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 6pt,
    edge-stroke: 0.7pt,
    // memory hierarchy: A and C live here, B never does
    node((0, 0), [*DRAM* \ #small[$A$, $C$, seeds of $B$]], name: <dram>, fill: box-fill, width: 25mm),
    node((1.2, 0), [*$L_2$* \ #small[optional]], name: <l2>, fill: box-fill, stroke: (dash: "dashed", thickness: 0.6pt), width: 16mm),
    node((2.4, 0), [*$L_1$ data cache*], name: <l1>, fill: box-fill, width: 27mm),
    // the core
    node((4, 0), [*Load/store unit*], name: <lsu>, fill: white, width: 24mm),
    node((4, 1.2), [*Register file* \ #small[blocks of $A$, $B$, $C$]], name: <regs>, fill: white, width: 28mm),
    node((5.2, 1.2), [*MAC unit*], name: <mac>, fill: white, width: 16mm),
    node(enclose: (<lsu>, <regs>, <mac>), name: <core>, fill: box-fill, stroke: 0.8pt, inset: 7pt, corner-radius: 5pt),
    node((5.2, 0), [*Core*], stroke: none, fill: none),
    // the PRNG-FIFO: B is generated on the fly, never stored
    node((1.2, 1.2), [*Generator* \ #small[one element of $B$] \ #small[every $g_c$ cycles]], name: <gen>, fill: gen-fill, width: 27mm),
    node((2.4, 1.2), [*FIFO*], name: <fifo>, fill: gen-fill, width: 16mm),
    node((1.2, 2.2), [*Seed register*], name: <seed>, fill: gen-fill, width: 27mm),
    node(enclose: (<gen>, <fifo>, <seed>), name: <pf>, stroke: 0.8pt, inset: 7pt, corner-radius: 5pt),
    node((2.3, 2.2), [*PRNG-FIFO*], stroke: none, fill: none),
    // data paths, numbered by the step of a tile that uses them
    edge(<dram>, <l2>, "<|-|>"),
    edge(<l2>, <l1>, "<|-|>"),
    edge(<l1>, <lsu>, "<|-|>", [#step(1) #step(3) #step(5)], label-side: left, label-pos: 0.4),
    edge(<lsu>, <regs>, "<|-|>"),
    edge(<regs>, (4, 2.75), (1.2, 2.75), <seed>, "-|>", [#step(1) #small[seed]], label-side: left, label-pos: 0.45),
    edge(<seed>, <gen>, "-|>"),
    edge(<gen>, <fifo>, "-|>", small[$B$], label-side: left),
    edge(<fifo>, <regs>, "-|>", [#step(2) #small[pop $B$]], label-side: right),
    edge(<regs>, <mac>, "<|-|>", step(4), label-side: left),
    // control signals
    edge(<fifo>, <gen>, "-|>", small[full: pause], bend: -50deg, stroke: ctrl, label-side: right),
    edge(<fifo>, <regs>, "-|>", small[empty: stall], bend: 40deg, stroke: ctrl, label-side: left),
  )
  },
  caption: [The hardware system we study. $A$ and $C$ come from memory through the cache hierarchy, and $B$ is generated on the fly into the FIFO, from a seed that is loaded once per tile. The numbers are the steps of a tile listed below, and the dashed arrows are control signals. The sizes and latencies we simulate are in @tab-params.],
) <fig-system>

The core works on register blocks. It holds a block of each matrix in its registers, $R_M times R_K$ of $A$, $R_K times R_N$ of
$B$ and $R_M times R_N$ of $C$, and its MAC unit multiplies the blocks of $A$ and $B$ and adds the result into the block of $C$,
$R_M R_N R_K$ MACs in all.

The computation is tiled. A tile computes $T_M times T_N$ elements of $C$ over the whole inner dimension $K$, and the tiles are
computed one row of tiles at a time, from left to right. Inside a tile, the core keeps a block of $B$ in its registers and uses it
for every row block of the tile before it moves on, which is the $B$-stationary dataflow (@sec-dataflow explains this choice). A
tile runs as follows:

+ At the start of the tile, the core reads the tile's seed through the cache and loads it into the generator. The generator
  restarts from this seed with an empty FIFO. The tiles below it use the same seed, so $B$ is generated again for every row of
  tiles.
+ For every step of $R_K$ along $K$ and every column block of the tile, the core pops the next block of $B$ from the FIFO, which
  takes 2 cycles. If the FIFO holds less than a block, the core waits until the generator has produced the rest.
+ For every row block of the tile, the core loads the block of $A$ and the block of $C$ from $L_1$. A row of a block that is in
  $L_1$ takes 4 cycles, and one that misses also pays the latency of the next level, 180 more cycles when it comes from memory.
+ The MAC unit multiplies the blocks of $A$ and $B$ and adds the result into the block of $C$, at $c$ cycles per MAC, which is
  free by default.
+ The core stores the block of $C$ back to $L_1$.

The core is in order. It waits for every access to finish before it starts the next one, and the only thing that works in
parallel with it is the generator, which keeps producing elements while the FIFO has room and pauses when it is full. Over the
whole tile the runtime is therefore set by the slower of the two, the core's accesses to $A$ and $C$, or the generator producing
$B$. The rest of this report studies this trade-off: which tile balances the two best, and how a hardware engineer should split
the hardware between the generator, the FIFO and the cache.

= Methodology

== `asymm_tiling` Simulator

To evaluate matrix multiplication under asymmetric data access costs, we designed and implemented `asymm_tiling`, a modular, cycle-accurate architectural simulator written in C++20. The simulator models the execution of general matrix multiply operations across configurable multi-level cache hierarchies, comparing conventional DRAM-backed dataflows against hardware-accelerated on-the-fly streaming.

It simulates the system of @sec-system cycle by cycle, following the flow described there.

=== Architecture

The simulator is structured into decoupled, modular subsystems synchronized by a centralized event clock:

- *`MultiUnit` (Compute & Tiling Engine):* The 3D loop nest $(M, K, N)$ partitioned into tiles of $T_M times T_N$ outputs and
  register tiles. It supports both *Output-Stationary* and *Weight-Stationary* dataflows. The matrices $A$, $B$ and $C$ are laid
  out back to back from a fixed base address, so every run can be deterministic.
- *`PrngFifo` (PRNG-FIFO Hardware Accelerator):* Asynchronous generator in front of a FIFO queue of finite element capacity. The
  generator produces one element of $B$ every $g_c$ cycles and pauses while the queue is full. The compute core pops one
  register block ($R_M R_N$ elements) at a time. If the queue currently holds fewer elements than the register block can handle,
  the core stalls until the missing ones are generated. Each tile generation starts by loading its seed, which restarts the
  generator with an empty queue.
- *`CacheUnit` (Multi-Level Cache Controller):* Coordinates an extensible Chain-of-Responsibility hierarchy of arbitrary depth
  ($L_1, L_2, dots, L_k$, DRAM). The configuration currently describes an $L_1$ and an optional $L_2$ as we haven't yet needed
  more cache levels for our research.
  - Our cache follows these rules:
    - *Accesses:* Reads and writes both count as accesses at every level they reach.
    - *Latency:* Lookups are serial and reads and writes cost the same.
    - *Write policy:* All levels are write-back, with a dirty bit per level.
    - *Inclusion:* The hierarchy is non-inclusive non-exclusive (NINE).
    - *Writebacks:* Writebacks are handled in the background as with a write buffer therefore they cost no cycles.
- *`Clock` (Cycle Synchronization):* A centralized simulation clock (`Clock`) that advances monotonically.
- *`Registry` (Statistics Collection):* A centralized metrics registry (`Registry`) that records and computes dynamic simulation statistics.
- *`Config` and `MyOptions` (Configuration & Parameter Management):* Implements a two-tiered parameterization system. `Config` loads baseline architectural profiles from declarative TOML files (`config.toml`), while `MyOptions` parses command-line arguments to dynamically override parameters on the fly, enabling scripted parametric sweeps without recompiling the simulator.

The relationship between these subsystems is illustrated in the UML class diagram in @fig-uml.

#figure(
  image("./figures/architecture.svg", width: 100%),
  caption: [UML class diagram of the `asymm_tiling` simulator, illustrating the separation of the computation engine (`MultiUnit`), accelerator pipeline (`PrngFifo`), modular cache hierarchy (`CacheUnit`), and eviction policies.],
) <fig-uml>

=== Correctness

Building your own simulator comes with the cost of making sure its numbers are correct. We cannot truly guarantee
correctness, as the famous saying goes, "All models are wrong, but some of them are useful". But we can still make our model useful
and at least increase the likelihood of its data being correct. For that we did the following:

*Created a Simple Python Reference Cache:* We implemented a second cache simulator, a very simple one in python. To connect between the C++ simulator and the python simulator, we created a driver program. The driver feeds the C++ `CacheUnit` a trace of reads and writes and prints relevant statistics which we cross-verify with the simple python model.

*Diff-Testing Against the Python Simulator:* The C++ cache and the reference model run the same traces and are compared access by
access. As soon as there is a difference between them, we know that there's a problem, and the test reports the first access where they
disagree. From there we can analyze the problem and fix it if needed. The traces we fed for testing were created with the Python testing library `Hypothesis`.

*Invariant Testing:* These tests are like sanity checks, these properties must always hold no matter what trace was fed into the simulator. Here we test the following:

- $"Hits"(L_k) + "Misses"(L_k) = "Accesses"(L_k)$

- $"Misses"(L_k) = "Accesses"(L_(k+1))$

- Total cycles equal $sum_k "Accesses"(L_k) dot "latency"(L_k) + "DramLat" dot "DramAccesses"$

- That a Set cannot hold more lines than it has ways.

*Hypothesis Testing:* Here we tested our simulator, by simply looking at the results. We run simulations, with different
configurations, and we can infer how the results would vary. Of course this cannot allow us to test how cycle accurate our
simulator is, but it allows us to see if the results make sense as a whole, and we've found and fixed the most bugs with this method.

== Default Simulation Parameters <sec-params>

Unless stated otherwise, every experiment uses the configuration in @tab-params, which is also the simulator's default `config.toml`. Experiments that vary a parameter say so.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header([*Parameter*], [*Value*], [*Reasoning*]),
    [Matrices $M times K times N$], [$192 times 256 times 256$], [This size allowed us to run thousands of experiments quickly, while also being large enough so that it won't fit in $L_1$.],
    [Element size], [4 bytes for $A$, $B$ and $C$ ($B$ varies in the reproduction of the Bharadwaj model)], [FP32 / INT32 are the most commonly used types.],
    [Register tile $R_M times R_N$], [$4 times 4$], [Modest and realistic choice],
    [$L_1$ cache], [16 KB, 64-byte lines, fully associative, LRU, write-back, write-allocate], [It's a common setup, in addition fully associative cache mimics a software-managed scratchpad.],
    [$L_1$ hit latency], [4 cycles], [Realistic $L_1$ latency],
    [$L_2$ cache], [none], [Easier to analyze results because of less degrees of freedom.],
    [Memory latency], [180 cycles], [Realistic DRAM latency],
    [Generation cost $g_c$], [swept, 0 to 600 cycles per element], [from a fast dedicated generator to a slow or shared one],
    [FIFO capacity], [16384 elements], [large enough not to limit the overlap],
    [FIFO access], [2 cycles per register block],[comparable to an $L_1$ access and should be fast],
    [Compute unit], [free (MAC cost $c = 0$)], [we assume negligible MAC cost],
  ),
  caption: [Default simulation parameters.],
) <tab-params>

In all the line plots of this report, every marker is a simulated point, and the line between two markers only connects them.
Nothing between two markers was simulated. Lines without markers are either computed from a formula or mark a reference level,
and their captions say which.

= Experiments And Results
== Previous Results By Bharadwaj And Demmel <reproduce>

Our project starts from earlier, unpublished work by Bharadwaj and Demmel on tiling for multiplication by a random matrix
@notes-random-tiling @notes-asym-cost. We call its model of the cost of a tile the Bharadwaj model. It asks how to tile $C = A dot B$ when $B$ is cheaper to access than $A$, for example because it is stored in a lower precision,
and it measures the cost of a tile by its traffic. For every step of $K$, a tile of $C$ of $T_M times T_N$ elements needs $T_M$
elements of $A$ and $T_N$ elements of $B$, while the tile of $C$ itself stays in the cache for the whole of the inner dimension
$K$, and it does $T_M T_N$ MACs with them. When all elements cost the same, this traffic is smallest for a square tile. But when $B$ is cheaper, the best tile is no longer square.

Before adding a generator, we check that our simulator reproduces the Bharadwaj model, where $B$ is still a stored matrix, only in a lower precision. There, an element of $B$ costs a fraction $rho$ of an element of $A$ to bring into the cache. With a tile of $C$ of $T_M times T_N$ elements, the traffic per MAC is $1 slash T_N$ for $A$ and $rho slash T_M$ for $B$, so for a fixed tile area the traffic is smallest when
$ T_N / T_M = 1 / rho. $
The cheaper $B$ is, the more the best tile stretches along it, and the more it saves compared with a square tile.

To reproduce this, $A$ and $C$ use 8 bytes per element and $B$ uses a varying 8, 4, 2 or 1, so $rho = 1, 1 slash 2, 1 slash 4, 1 slash 8$. $B$ is read from memory, there is no generator, and the matrices are $256 times 256 times 256$, with the default configuration otherwise (@tab-params). For tiles of a fixed area, we measure the traffic into $L_1$ against the aspect ratio $T_N slash T_M$.

#figure(
  image("./figures/fig_paper.svg", width: 100%),
  caption: [$L_1$ read traffic against the aspect ratio of the tile, for tiles of 512 (left) and 1024 (right) elements, relative to the lowest traffic of each line. The dashed lines are the theory, $1 slash T_N + rho slash T_M$.],
) <fig-paper>

@fig-paper reproduces the main result of the Bharadwaj model. We can clearly see that as $B$ gets cheaper, the minimum moves to wider tiles
(larger $T_N$), from a square tile at $rho = 1$ to tiles 8 times wider at $rho = 1 slash 8$. The measured minimum is at $1 slash
rho$ or one step away from it, where the values are almost equal. In addition the savings against the square tile are 18% and 36%
at $rho = 1 slash 4$ and $1 slash 8$ respectively, very close to the predicted 20% and 37%.

== $B$-Stationary Against $C$-Stationary <sec-dataflow>

For the upcoming experiments, we want to decide on which data flow we should use when $B$ comes from the PRNG-FIFO. The main reason being,
that the two dataflows differ in how often they pop the queue to receive elements of $B$. The weight-stationary ($B$-stationary)
dataflow pops $B$ once per row of tiles, so each element is reused by $T_M$ rows of matrix $A$, meaning one pop from the FIFO is amortized across $T_M$ rows. 

The output-stationary ($C$-stationary) dataflow on the other hand keeps a register block of $C$ while $B$ streams past it, so $B$
is popped again and again for every register block of $R_M$ rows, meaning it is amortized across $R_M$ rows (fewer than $T_M$). @fig-dataflow compares them on the tile $T_M = 64$, $T_N = 32$, for every integer $g_c$ from 0 to 100, with otherwise the default configuration (@tab-params).

#figure(
  image("./figures/fig_dataflow.svg", width: 100%),
  caption: [Runtime of the two dataflows against $g_c$ on the tile $64 times 32$, simulated at every integer $g_c$.],
) <fig-dataflow>

From the figure we can learn a couple of things. *$C$-stationary is faster only when generation is almost free.* At $g_c <= 2$ it
is $1.68$ times faster. From $g_c = 3$ onwards its runtime grows as $g_c slash 4$, because every generated element serves only 4
rows, and the two dataflows cross between $g_c = 4$ and $g_c = 5$. Beyond that $B$-stationary is always faster. A modest $1.31$
times at $g_c = 6$ and up to $16$ times faster from $g_c = 80$ on.

In addition, *$B$-stationary is not constant.* Although it seems like it at first, if we look at a wide enough $g_c$ scale, its
runtime starts to grow at $g_c approx 73$. Each generated element is shared by the 64 rows of the tile, so generating $B$ costs
only $g_c slash 64$ per MAC, and until about $g_c = 73$ this is less than the time the core spends on memory accesses (It's memory
bound), therefore the generation hides behind them. Beyond that point, generation becomes the bottleneck and the runtime grows
slowly, with a slope $64 slash 4 = 16$ times more gentle than $C$-stationary, because each generated element serves 64 rows instead of 4.

With all of that, *$C$-stationary still wins at $g_c = 0$ though.* $B$-stationary loads and stores the register block of $C$ at
every step of the inner dimension $K$. $C$-stationary keeps it in the registers for the whole of $K$ and only loads $A$, saving
the store for the end of the loop. This gives $C$-stationary a clear edge when $B$ elements are essentially *free*. But as we've seen, as soon as the generation cost grows above a small threshold, this edge disappears, and $B$-stationary dominates.

=== Does this carry over to differently sized tiles?

#figure(
  image("./figures/fig_dataflow_ratio.svg", width: 100%),
  caption: [Runtime of $C$-stationary divided by the runtime of $B$-stationary against $g_c$, for $T_N = 32$ and six tile heights, simulated at every integer $g_c$.],
) <fig-dataflow-ratio>

@fig-dataflow-ratio repeats the comparison for six tile heights ($T_M = 4, 8, 16, 32, 64, 128$) at $T_N = 32$, for every integer $g_c$ from 0 to 100. It can be clearly seen that for each configuration, every line follows the same pattern:

+ At $g_c = 0$, $C$-stationary is always faster. $T_M = 128$ gives $C$-stationary an even bigger edge because at that size the tile no longer fits in $L_1$, making every $C$ load and store much less forgiving.
+ The ratio crosses 1 at a small $g_c$, around 4 to 5 for most heights. Only $T_M = 128$ is the exception again, crossing only at about 12, showing that when the tile does not fit inside the cache, $C$-stationary keeps its edge for longer.
+ Once both dataflows are limited by generation, the ratio reaches an asymptote. That upper bound is how many more rows share each
  generated element in $B$-stationary than in $C$-stationary: $T_M slash R_M$.

One last thing is, we can see that for a tile height of $T_M = 4$, the performance is the same for both dataflows for all $g_c$
values seen in the figure. This makes sense because it's the same height as the register files, meaning the amortization for
$B$-stationary is the same as for $C$-stationary.

=== A more fair comparison
We decided to also compare each dataflow at its own best tile at each $g_c$ for a more fair comparison. @fig-dataflow-best shows
the same picture, $C$-stationary is faster only while $g_c <= 3$, and from there on $B$-stationary wins by a growing margin. The crossover is again at a small $g_c$, between 3 and 4.

#figure(
  image("./figures/fig_dataflow_best.svg", width: 100%),
  caption: [Runtime of each dataflow at its own best tile against $g_c$.],
) <fig-dataflow-best>

=== Does this depend on the hardware?
$C$-stationary pays $g_c slash R_M$ per MAC for generation, while $B$-stationary pays $g_c slash T_M$ or just the memory access
time if the generation time is hidden by a large $T_M$. Let's call the $B$-stationary cost with free generation $T_B$. This means $C$-stationary stays faster only while: $ g_c < R_M dot T_B, $
For our $64 times 32$ tile, $T_B approx 1.15$ and
$R_M = 4$, so the crossover is at $g_c approx 4.6$, matching the crossover in @fig-dataflow. To check that this holds on other hardware, we repeated the comparison with other register blocks and with a compute unit of one MAC per cycle:

#align(center, table(
  columns: 3,
  align: (left, center, center),
  table.header([*Configuration*], [*Predicted, $R_M dot T_B$*], [*Measured crossover*]),
  [$2 times 2$ register blocks], [6.8], [between 6 and 7],
  [$4 times 4$ (default)], [4.6], [between 4 and 5],
  [$8 times 8$ register blocks], [4.7], [between 4 and 5],
))

For the rest of this report we use the $B$-stationary dataflow since $C$-stationary wins only when generating an element costs
less than a few cycles.

== Looking at the Best Tile Sizes <sec-tile>
We start by *finding the Empirically Best Tiles*. To find the best tile at each generation cost, we simulated every tile with $T_M$ from 4 to 192 and $T_N$ from 4 to 128, both in steps of 4 (1536 tiles), at 42 values of $g_c$ from 0 to 600, with the default configuration otherwise (@tab-params). @fig-best-tile shows the measured best tile $(T_M^*, T_N^*)$.

#figure(
  image("./figures/fig_best_tile.svg", width: 100%),
  caption: [The best tile against $g_c$: its height $T_M^*$ and width $T_N^*$.],
) <fig-best-tile>

The figure shows an interesting phenomenon. At first as $g_c$ grows, the best tile gets taller and wider, but after $g_c$ passes 20,
the best tile still keeps growing taller, but it now prefers becoming narrower. This continues until a point in which a tall and wide tile is preferred again. The figure raises some interesting questions, and these are our attempts to answer them:

- Why does $T_M$ grow? So that generation stays hidden. Each generated element of $B$ is shared by the $T_M$ rows of its tile
  (@sec-dataflow), so a taller tile spreads the generation cost over more rows. As $g_c$ grows, we need a bigger $T_M$ to keep
  generation hidden behind the memory accesses.
- Why does $T_N$ first grow and then suddenly start shrinking? So that the tile still fits in $L_1$. At first, once the tile of
  $A$ no longer fits in $L_1$ (at $T_M >= 16$), $T_N$ grows, because a wider tile allows for reloading $A$ tiles fewer times.
  This is true up to a second cliff in the cost of memory, which we analyze in @sec-alpha. Passing that second cliff is
  horrible for performance. We arrive at that cliff later when $T_N$ is smaller, therefore causing the best tile to start
  lowering $T_N$ for the purpose of delaying that inevitable second cliff.
- Why does it turn wide again at very high $g_c$? From $g_c = 400$ on, generation dominates *every* good tile, so the width no longer matters either. Up to 263 tiles are within 1% of the best performing shape.

Finding these tiles took a simulation of every tile at every $g_c$. To explain them properly, and to find the best tile without
such a sweep, we need a model of the runtime, which the next section develops.

== Developing our Mathematical Model
=== Moving From The Bharadwaj Model To Ours <sec-simple-model>

The Bharadwaj model counts traffic for matrix multiplication where both matrices require
memory storage. Our $B$ is never moved nor stored, it is generated, so we have to turn this count into time. We do it in three steps.

*1. Moving from traffic to performance in cycles:* In a real cache, the performance of $A$ and $C$ is not directly proportional to the traffic. It depends on hits, misses and whether the tile fits in $L_1$. Modeling all of that can prove to be quite difficult, therefore instead of doing that, we define it as $alpha(T_M, T_N)$. This replaces the $1 slash T_N$ term.

*2. Moving From precision to generation cost for $B$:* $B$ lives in memory. With the PRNG-FIFO, it completely bypasses memory. Instead it costs $g_c$ cycles to generate, and each generated element is reused by the $T_M$ rows of its tile (@sec-dataflow), so the $B$ term becomes $g_c slash T_M$.

*3. Replacing the Sum with a Max:* The Bharadwaj model adds the two costs, because both are serial loads from memory. Our PRNG-FIFO on the other
hand, is asynchronous. The generator keeps generating in the background while the core works on $A$ and $C$. The two overlap, so only the slower one sets the runtime:

$ T / (M N K) = max(alpha(T_M, T_N), g_c / T_M) $

A brief look at the units, the left side is the runtime $T$ in cycles, divided by the MACs ($M N K$), giving Cycles per MAC. 

$alpha$ is measured the same way, the runtime with free generation divided by the MACs, so it is also in cycles per MAC.

$g_c$ is in cycles per element of $B$, and every generated element is used by $T_M$ MACs, one for each row of its tile. So $g_c
slash T_M$ is cycles per element divided by MACs per element, giving cycles per MAC.

This is a simple model. It assumes that the overlap is perfect and that the tiles divide the matrix. @sec-refine shows where these assumptions break, and how to fix them.

=== The Memory Cost $alpha$ <sec-alpha>

With $g_c = 0$, generating $B$ is free, and the runtime per MAC is the memory cost $alpha(T_M, T_N)$ alone. This is very
convenient and it allows us to analyze and study the behaviour of $alpha(T_M, T_N)$. Plugging in $g_c = 0$, we measured it for every $T_M$ from 4 to 128 in steps of 4 and $T_N in {4, 8, 16, 32, 64}$, with the default parameters (@tab-params).

#figure(
  image("./figures/fig_alpha.svg", width: 100%),
  caption: [The memory cost $alpha$ against the tile height $T_M$, one line per tile width $T_N$ ($g_c = 0$, $16$ KB fully associative $L_1$).],
) <fig-alpha>

@fig-alpha shows that $alpha$ takes only a few levels, separated by sharp cliffs, similar to a step function:
+ For $T_M <= 12$, $alpha approx 0.85$ for *every* $T_N$, that is because the A tile size depends only on $T_M$ and $K$, and at this $T_M$ the $A$ tile fits entirely in $L_1$. 
+ From $T_M = 16$ on, $alpha$ steps up to a height that clearly depends on $T_N$: $3.6$, $2.2$, $1.5$, $1.15$ and $0.97$ for $T_N
  = 4, 8, 16, 32, 64$ respectively. This is because wider tiles are cheaper. At $T_M = 16$ the $A$ tile doesn't fit in $L_1$
  anymore meaning every time we need the same tile again, it has to be reloaded from memory. Each $A$ tile row is reused $N
  slash T_N$ times. A wider tile (bigger $T_N$), reduces the amount of times the same $A$ tile row needs to be reloaded, increasing performance. The next point shows that this performance comes at a cost.
+ All tiles hit a second step, to $alpha approx 3.7$--$3.9$: $T_N = 64$ at $T_M approx 48$--$52$, $T_N = 32$ at $T_M approx
  64$--$88$. The narrower tiles ($T_N <= 16$) do not reach the second step in this figure's range. The wider tiles reach this
  step "sooner". This step is due to the combination of $T_N$ and $T_M$ giving a tile that causes the overflow of tile $C$ from
  $L_1$, destroying performance.
+ The wide tiles have an "oscillating" shape at their second step. This is a phenomenon of enabling tiles that do not completely
  divide the matrix dimensions. Those tiles, include a residual tile that is smaller than the full one, causing *less* thrashing
  of the $L_1$ cache when the $C$ tile overflows. On the other hand, those tiles that *do divide* the matrix, have no residual
  tile, therefore reaching maximal thrashing.
+ The narrow tiles have a "sawtooth" shape: small dips at some points. The reason is similar to the previous point. After the
  first step, these heights leave a very short residual row of tiles, short enough for its tile of $A$ to fit in $L_1$, so it is
  cheap and pulls the *average* $alpha$ down.

=== Analyzing the Formula with different $g_c$ values <sec-mem-vs-gen>

At the moment that generating $B$ costs time, the simple model predicts the runtime as the larger of two costs, which pull the tile height in opposite directions:

+ the memory cost $alpha$, whose behaviour we've analyzed in the previous section.
+ the generation cost $g_c slash T_M$, which *falls* with $T_M$.

@fig-model-simple shows both for $T_N = 32$ and $T_M$ from 4 to 128 in steps of 4, together with the runtime measured at $g_c = 30$, $100$ and $200$, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/fig_model_simple.svg", width: 100%),
  caption: [The two costs of the simple model against $T_M$ ($T_N = 32$): the memory cost $alpha$ measured at $g_c = 0$ (solid), the generation cost $g_c slash T_M$ (dashed), and the measured runtime (markers) at $g_c = 30$, $100$ and $200$.],
) <fig-model-simple>

Trying to understand the formula intuitively, the runtime always follows the higher of the two curves. The *best tile* is therefore the *lowest point* of that
upper curve, "the minimum of the maximum". For a rising and a falling curve this minimum is located at their crossing point. To
the left, generation dominates and a taller tile helps. To the right, memory dominates and a taller tile hurts.

We can see that most of the points don't actually follow the curves. At $g_c = 30$ generation is cheap, and the measured runtime sits on the higher curve almost everywhere. At $g_c = 100$ and $200$ it clearly does not. Instead it follows a decreasing step shape above the generation curve.

Analysing the points that do touch the curve shows that those are the points that have tiles at heights that divide the
height of the matrix ($M = 192$), such as $T_M = 48$ and $64$. In addition, we can see that a few measurements are slower than both curves. Why the simple model misses these points, and how to fix it, is the subject of the next section.

=== Refining The Model <sec-refine>

Here we try to refine the model to address the points that miss the model previously. For that, three refinements are needed, and a fourth adds $K$ to the model.

*1. $B$ is generated once per row of tiles:* The flat steps come from how often $B$ is generated. The core finishes a whole row of
tiles before moving down (a whole row tile of matrix A), and every row of tiles needs the entire matrix $B$. Meaning $B$ is generated
once per row of tiles, or $ceil(M slash T_M)$ times total, giving it a cost per MAC of: $ g_c dot ceil(M slash T_M) / M. $

Interestingly when $T_M$ divides $M$ this is exactly $g_c slash T_M$, which is why the measurements touched the simple curve only there.

@fig-model shows that with this staircase, the measurements follow the model again.

#figure(
  image("./figures/fig_model.svg", width: 100%),
  caption: [As @fig-model-simple, with the generation cost of the refined model $g_c dot ceil(M slash T_M) slash M$ (dashed).],
) <fig-model>

*2. The startup term:* Each tile loads its own seed, so the FIFO starts empty, and the first register block of $B$ must be
generated before the core can start. This wait only adds time when memory is the bottleneck, and the generator would otherwise be
idle. When generation is the bottleneck, the generator is busy all the time anyway, and the wait is already part of the
generation time. So the startup belongs on the memory side of the max. It adds $g_c dot R_M R_N$ cycles per tile. It is small for
large tiles, but its effect grows with the number of tiles.

*3. The max is taken per row of tiles:* A few heights are still slower than both curves. The reason for this is the extra row that
appears when the tile height does not divide the matrix height. Each row of tiles generates all of $B$, but the short residual row
has a lot less memory work to hide behind (because its $T_M$ is smaller). This causes an effect such that the full rows wait for memory, the short row waits for
generation, and since the rows run one after the other, these waits add up. The simple model effectively takes the max of the
averages because it doesn't really differentiate between the two. That lets the full row's spare memory time "hide" the short
row's generation explaining why the model's predictions predict faster performance than the reality. The simple fix is to account
for this effect, and to take the max for each row of tiles and add the residual row separately:

$ T / (M N K) = 1 / M (floor(M / T_M) dot max(T_M dot overline(alpha)(T_M, T_N) + s, g_c) + max(e dot overline(alpha)(e, T_N) + s, g_c)), $

$ e = M mod T_M, quad s = (g_c dot R_M R_N dot ceil(N slash T_N)) / (K N) $

The first term is the $floor(M slash T_M)$ full rows of tiles, and the second is the short last row of height $e$, which
disappears when $T_M$ divides $M$. $overline(alpha)(r, T_N)$ is the $alpha$ of a row of tiles of height $r$ (below). When $T_N$ divides $N$ it is simply
$alpha(r, T_N)$, measured for a tile of height $r$ and width $T_N$ in the same $g_c = 0$ runs.

The same effect holds along the width. If $T_N$ does not divide $N$, every row of tiles ends with a narrower tile of width
$e_N = N mod T_N$, which has its own $alpha$, so $overline(alpha)$ is the average over the row, weighted by width:
$ overline(alpha)(r, T_N) = (floor(N slash T_N) dot T_N dot alpha(r, T_N) + e_N dot alpha(r, e_N)) / N. $

$s$ is the startup of one row of tiles, $g_c dot R_M R_N$ cycles at the start of each of its $ceil(N slash T_N)$ tiles, in the
same units as $T_M dot overline(alpha)(T_M, T_N)$ and $g_c$ (cycles divided by the $K N$ MACs that occur in each of the $M$ rows).

We can also derive the simple model directly from the refined one. When $T_M$ divides $M$, the short row disappears, and the formula reduces to the simple model of @sec-simple-model. There are $M slash T_M$ full rows and no short row:
$ 1 / M dot M / T_M dot max(T_M dot alpha + s, g_c) = max(alpha + s / T_M, g_c / T_M), $

where the last step moves the $1 slash T_M$ into the max, dividing both of its terms. Giving us exactly the simple model, with the
startup added to the memory cost.

@fig-model-refined shows the same measurements as @fig-model, now against the full refined model. Over all the points of the figure, the model is within 0.2% of the measurement.

#figure(
  image("./figures/fig_model_refined.svg", width: 100%),
  caption: [As @fig-model, with the full refined model (dashed): the max taken per row of tiles, with the startup term on the memory side.],
) <fig-model-refined>

*4. $K$ and the strip of $A$:* So far $alpha$ was measured on one matrix with the same $M N K$ dimensions. $M$ and $N$ are already
part of the model, but $K$ isn't, with this refinement we aim to also introduce $K$ into the model. A different $K$ changes $alpha$
in one way, it changes the max height of the tile at which a strip of $A$ can stay in cache. The strip of $A$ that a row of
tiles needs is $T_M times K$ elements, so $K$ decides whether it stays in $L_1$ from one tile to the next in the GEMM operation.
@fig-kmodel-alpha shows this, for every $K$, $alpha$ takes the same two levels, and only the height at which it jumps
from one to the other moves.

#figure(
  image("./figures/sw_kmodel_alpha.svg", width: 100%),
  caption: [The memory cost $alpha$ against $T_M$ ($T_N = 16$, $192 times K times 256$) for four values of $K$, with the first cliff predicted for each $K$ (dotted).],
) <fig-kmodel-alpha>

Because of the operation structure of the $B$-stationary dataflow, the strip of $A$ stays in $L_1$ while it fits next to the tile
of $C$ that is being finished in addition to the next $C$ tile coming in. Counting in cache lines of $E$ elements, where $E$ is the size of a cache line divided by the size of an element (64 / 4 = 16 in our
setup), a row of tiles of height $r$ fits in the $L_1$ cache when:
$ r dot (ceil(K slash E) + 2 ceil(T_N slash E)) < |L_(1 "lines")| $

where $|L_(1 "lines")|$ is the number of lines $L_1$ holds (256 in our setup). The term $r dot (ceil(K slash E)$ is a strip of
$A$. $r$ rows of $K$ elements, $ceil(K slash E)$ lines each. The term $2 ceil(T_N slash E))$ is *two* tiles of $C$, each $r$ rows
of $ceil(T_N slash E)$ lines. There are two because a line of $A$ is used at some step of one tile, and again at the same step of
the next tile. In between, the core touches the rest of the strip of $A$, *all* of the current tile of $C$, and *all*
of the next tile of $C$. LRU keeps the line of $A$ only if all of this fits in $L_1$. The dotted lines in @fig-kmodel-alpha are
exactly this prediction. This creates two levels, a level in which the $A$ strip still fits, and one in which it doesn't, and this refinement takes this distinction into account.

This is not all though, within each of these two levels, $alpha$ still drifts a little with $K$ because of $C$ itself. Every
element of $C$ is loaded from memory once, a line for every $E$ elements, and that cost is shared by the $K$ MACs of the element.
This adds $L_"mem" slash (E K)$ cycles per MAC, where $L_"mem"$ is the memory latency. Together, the $alpha$ of a row of tiles at
any $K$ is:

$ alpha(r, T_N, K) & = cases(
  alpha_"fits" (r, T_N) & "if the row fits",
  alpha_"no fit" (r, T_N) & "otherwise",
) + L_"mem" / (E K) \
& = (1 - H(Delta)) dot alpha_"fits" (r, T_N) + H(Delta) dot alpha_"no fit" (r, T_N) + L_"mem" / (E K), $

with $Delta = r dot (ceil(K slash E) + 2 ceil(T_N slash E)) - |L_(1 "lines")|$, and $H(Delta) = 1$ if $Delta >= 0$ and $0$
otherwise.

$alpha_"fits"$ and $alpha_"no fit"$ are the calibrated $alpha$'s of the two different levels, each has a table of its own,
generated at $g_c = 0$, meaning we need a total of two calibrations. $alpha_"fits"$ is calibrated on a matrix with a small enough
$K$, where the $A$ strip fits in with the $C$ tile, and $alpha_"no fit"$ is calibrated on a matrix with a large $K$ where it
doesn't fit. Each calibration table computation needs to also subtract its own $L_"mem" slash (E K)$. This $alpha$ is what the
formula of refinement 3 uses. This allows for accurate performance predictions for matrices of any size with $K$ values even
outside the range of the $K$ used for creating the table.

== Software Focused Design Questions <sec-sw>

A software engineer gets the hardware as it is, and has to decide how to use it. For example which tile to choose for a given
generator and for the matrices at hand. Here we aim to help that engineer, so he'll use the best configuration possible for the
setup he has to work with.

=== Can Our Model Be Trusted To Choose The Tile? <sec-test-model>

Simulating every tile at every $g_c$ is expensive, so before anything else the engineer wants to know if our model can choose the
tile instead. To choose a tile shape, we need to do three steps:

+ *Calibration:* The long part. Run every candidate tile once with $g_c = 0$ and record its $alpha(T_M, T_N)$. This gives you a table. If $T_M$ does not divide $M$, the measurement also contains the short last row, so take it out by solving the formula of @sec-refine for $alpha(T_M, T_N)$, starting from the smallest heights.
+ *Prediction:* This is the fast part. For a given $g_c$, go over every pair $(T_M, T_N)$ in the table. Compute its generation cost $g_c slash T_M$, and
  take the max between it and $alpha(T_M, T_N)$ plus the small startup term. If $T_M$ does not divide $M$, use the per-row max of
  @sec-refine instead. The $alpha$ of the residual last row can be read from the same table.
+ *Choosing:* Pick the pair with the smallest result. If several pairs tie, pick the one with the smaller $alpha$, as it has more room before generation becomes the bottleneck.

With the table generated by the first step, the second and third steps can be done very fast.

Now that we know how to predict the best tile, we shall check how good the predictions are. We simulated every tile with $T_M$ from 4 to 192 and $T_N$ from 4 to 128, both in steps of 4 (1536 tiles), at 41 values of $g_c$ from 1 to 600. The refined model predicts the runtime within 1% in 96% of the runs, and the tile it picks is never more than 0.1% slower than the best one.

@fig-model-validation shows this for every run. A perfect model would put every point on the diagonal. The simple model
underestimates many runs. The refined model puts almost all of them on the line.

#figure(
  image("./figures/fig_model_validation.svg", width: 100%),
  caption: [Measured against predicted runtime for every tile and $g_c > 0$, for the simple model of @sec-simple-model (left) and the refined model (right). Points on the dashed diagonal are predicted exactly.],
) <fig-model-validation>

The further the dots are from the diagonal line, the worse the prediction is. From this, we can easily see a significant advantage
to using the refined model. But even so, even the refined one misses at some points.

The misses are always in the same *direction*. The measured runtime is *higher* than predicted.
The reason for this most likely stems from the use of a max term in our model. It assumes that generation and memory overlap
perfectly, which is only true in the best case. The misses we see in the figure gather where the memory and generation costs are
about equal, on the other hand, when one of them clearly dominates, the other hides behind it completely and the model is almost
always exact. 

When they are equal, there is less room for error, so every short moment in which the core runs faster than the generator turns
into a wait for the FIFO, and adds directly to the runtime. This extra runtime is what our model missed.

All in all, a software engineer can trust the model to choose the tile. The calibration runs are the only simulations needed, and
the choice itself takes a short computation instead of a sweep over every tile and every $g_c$.

// TODO (later): redo fig_model_accuracy with the per-row max and decide whether to add it here

=== Does The Model Work For Other Matrices? <sec-sw-shapes>

All the results so far are for one matrix, and calibrating every new matrix again costs one simulation per candidate tile. With
$M$, $N$ and $K$ in the model (refinements 3 and 4 of @sec-refine), two calibrations should be enough for any matrix.

Before this can work, there is one condition. Every row of $C$ has to start at the beginning of a cache line, which means
that the length of a row, $N$, has to be a multiple of the number of elements in one cache line in the configuration that is used.
Let's assume that it does not, then a row of a tile of $C$ will start in the middle of a line and therefore touch one more line
than it actually needs. The tile then takes more of the cache, and starts to thrash at a smaller height. @fig-sw-alignment shows three matrices that differ only in $N$: with $N = 300$, which is 18.75 lines per row, $alpha$ starts to climb at $T_M approx 80$ instead of 128.

#figure(
  image("./figures/sw_alignment.svg", width: 100%),
  caption: [The memory cost $alpha$ against $T_M$ ($T_N = 16$) for $200 times 200 times N$ with $N = 288$, 300 and 304. The lines of 288 and 304, whole numbers of cache lines per row, coincide. Above $T_M = 128$ all three thrash completely.],
) <fig-sw-alignment>

No calibration can predict this, because the model doesn't take this effect into account. The fix is the same as in @sec-hw-assoc,
pad every row of $C$ with a few unused elements, up to a multiple of 16 elements. In the experiment below we pad both $K$ and $N$ this way.

To test the model, we calibrated it only twice, on $192 times 128 times 256$ and $192 times 1024 times 256$, and picked 130
matrices, 20 were picked by hand, 100 at random, with $M$ from 64 to 384, $K$ from 128 to 1024 and $N$ from 96 to 512, and 10
more at random with $K$ from 1280 to 4096, above the large calibration. For every matrix and six values of $g_c$ from 5 to 160, the model chooses a tile with the matrix's own $M$, $N$ and $K$, and we compare its runtime with
the best tile of that matrix, found by simulating all of its tiles. A short last row whose height was not calibrated uses the
nearest height that was. @fig-sw-kmodel compares this with calibrating every matrix itself, and with using one calibration for all
of them.

#figure(
  image("./figures/sw_kmodel.svg", width: 100%),
  caption: [How close the chosen tile is to the best tile, over 130 matrices and six values of $g_c$ (780 cases): the share of the cases within 1%, between 1% and 5%, and more than 5% slower, and the worst case. "K model" uses the two calibrations and refinement 4, "own table" calibrates every matrix itself, and "one table" uses the calibration of $192 times 256 times 256$ for all.],
) <fig-sw-kmodel>

With $K$ in the model, the two calibrations choose a tile within 1% of the best one in 96% of the cases, and within 5% in all but
two of them (the worst is 6%). That is almost as good as calibrating every matrix itself, which is never more than 2% off. Without
the $1 slash K$ term the worst case is 12%, and one calibration for all matrices, which ignores $K$, is up to 40% slower.

The matrices with $K$ larger than the $K$ used for the calibration of the second level, all get a tile within 1% of the best one.
Showing that $K$ does not have to lie between the two $K$'s used for the two calibrations. All that matters is that each
calibration covers the two modes, one with a small $K$, where the strip of $A$ fits, and one with a large $K$, where it does not.

Our suggestion, pad every row of the matrices to whole cache lines, and calibrate the model only twice, once on a matrix with the
smallest $K$ the engineer expects, and once with a $K$ large enough that no row of tiles fits. Then let the model choose the tile
for every other matrix. Two calibrations replace one per matrix, and the chosen tile is almost always within 1% of the best one.

=== How Much Autotuning Is Needed? <sec-sw-autotune>

Finding the best tile means calibrating the model, one run per candidate tile (@sec-test-model). With the 1536 tiles of @sec-tile,
that is a lot of runs, so we want to check if a smaller set of candidates can do almost as well. We compare several sets: every tile in steps of 4, 8 or 16, only heights that divide $M$, only powers of two, only square tiles, and no tuning at all (the default $16 times 32$ tile). For each set, the model picks a tile at every $g_c$ from its candidates, and we measure how much slower it is than the best tile overall.

#figure(
  image("./figures/sw_autotune.svg", width: 100%),
  caption: [The worst extra time, over all $g_c$, of the tile picked from each candidate set compared with the best of all 1536 tiles, against the number of calibration runs the set needs. "No tuning" is drawn at one run.],
) <fig-sw-autotune>

@fig-sw-autotune shows that most of the gain comes cheaply. Not tuning at all can be six times slower than the best tile, and square tiles alone can be twice as slow. But a few dozen well-chosen candidates, such as heights that divide $M$ with power-of-two widths, already come within about 10% of the best tile, and usually find it exactly. The full grid only polishes the last few percent. The candidates should include tall and narrow tiles, which a set of square tiles misses entirely.

Our suggestion is to always tune, but start small. Calibrate the heights that divide $M$ with power-of-two widths first. For our
runs the tile it picks is within about 10% of the best at every $g_c$, and within 1% at most of them. If the last few percent
matter, add every width for the same heights. And only when even the last few tenths of a percent matter the full grid calibration needs to be done.

=== Does The Choice Of Tile Matter? <sec-sw-choice>

Finally, we wanted to check how much does the choice actually matter. Is using the best tile shape actually better than just using
the convenient square? We found out that it depends. That sometimes it's significantly better and sometimes it's just as good, but
it's *never* worse. And the following figure shows it.

#figure(
  image("./figures/fig_vs_square.svg", width: 100%),
  caption: [Time saved by the best tile height over the square tile $T_M = T_N$, for four fixed tile widths $T_N$ (solid), and by the overall best tile over the best square tile of any size (dashed).],
) <fig-vs-square>

Square tiles are optimal when all matrices cost the same. @fig-vs-square fixes the width $T_N$, and compares the best height $T_M$ with the square tile $T_M = T_N$. The gain is the time saved, $(T_"square" - T_"best") slash T_"square"$. We can observe the following:

- *Small $g_c$:* The generation cost is hardly a factor so $T_M$ can afford to be quite low and the limiting factor is the memory,
  therefore the gain is proportional to how *badly* the square tile fits in $L_1$. A $64 times 64$ tile thrashes the $L_1$ cache
  ($alpha = 3.74$), while the optimal tile that has the freedom to change its $T_M$, has the dimensions of $8 times 64$ and
  costs $0.85$, achieving a gain of 77%. Similarly, but to the other extreme, an $8 times 8$ tile already fits even as a square,
  and the gain is only at about 1%.
- *Large $g_c$:* At a large $g_c$, generation is by far the limiting factor for both tiles, so both runtimes grow in proportion to $g_c$. The gain tends to one minus the ratio of their generation costs, $1 - ceil(M slash T_"best") slash ceil(M slash T_N)$, which only depends on the tile ratios, and is why each line in @fig-vs-square flattens.
- *In between,* this is a more interesting area. The gain drops to zero in some places and just flattens in others. At those $g_c$
 values, the runtime is decided by the memory cost $alpha$. Let's recall the $alpha$ step function, at those $g_c$ the alpha of
 the square and the best tile are both in between the first and second cliff and the height of both is enough to hide the
 generation cost. Beyond that, the square's generation starts to
 show, and the gain rises again, because the height of the square cannot keep up with the $g_c$ values and can't hide it any
 longer.

Looking at the best square tile of any size (black dashed line), we compare the best tile overall with the best square tile of any size.
The net gains are smaller, and the line has two hills, with no gain at the ends and in between the hills. 

This exact phenomenon can be seen in the section about the path of the best tile overall in @fig-best-tile. There we see that the best tile starts short and wide, passes through a square around $g_c = 45$, and ends tall and narrow up until it turns wide again at extremely high $g_c$ values. This same pattern of behaviour can be seen in @fig-vs-square as well.

Our suggestion, don't default to a square tile. A square is only safe when generation is almost free, or when it is so expensive that it dominates every tile. Everywhere in between, the best tile saves up to half of the runtime, and choosing it costs only the calibration and a short computation (@sec-test-model).

== Hardware Focused Design Questions <sec-hw>

So far the hardware was fixed. A hardware engineer designing such a system has to decide on the hardware itself: how fast the
generator must be, how large the cache and the FIFO should be, and so on. We answer each question the same way: for every
configuration and every $g_c$, we simulate all the tiles and keep the fastest one, comparing configurations by their best tile.

=== How Fast Must The Generator Be? <sec-hw-prng>

A faster generator costs area and power, so the engineer wants the slowest generator that does not slow the computation down. To find it, we take the best runtime at every $g_c$ and divide it by the best runtime with free generation ($g_c = 0$): this is the slowdown caused by the generator. We repeat this for four $L_1$ sizes, 8 to 64 KB, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_prng_budget.svg", width: 100%),
  caption: [Slowdown caused by the generator, the best runtime at $g_c$ divided by the best runtime at $g_c = 0$, for four $L_1$ sizes. The dotted lines mark 5% and 10%.],
) <fig-hw-prng>

@fig-hw-prng shows that all lines start at the same place, that makes sense, at those low $g_c$ values the generator is just fast
enough. At some $g_c$ the line starts climbing in steps, and a clear pattern can be seen, the bigger the cache, the longer it
takes for generation to be the limiting factor. The $g_c$ at which a line starts to climb roughly doubles with every
doubling of $L_1$.

A bigger cache allows the use of bigger tiles while also allowing for no thrashing of the cache. A taller tile (bigger $T_M$)
generates $B$ fewer times, creating dead time between generations, which in turn allows for higher generation times.

This experiment can help us understand if we should use a bigger cache or a faster generator. We see that doubling the cache gives the same runtime gains as halving the generation cost. This makes the two upgrades interchangeable. Halving $g_c$ can also be done with a second generator working in parallel, so the engineer can simply pick whichever upgrade is cheaper and more convenient.

For general hardware configurations, generation stays hidden as long as producing one element of $B$ takes no longer than the work
it is shared by. In the best tile, every element serves the $T_M$ rows of its tile (@sec-dataflow), and every row costs the core
$alpha$ cycles per MAC. So the generator is free up to: $ g_c approx T_M dot alpha, $
where $T_M$ is the tallest tile whose tile of $A$ still fits in $L_1$, and $alpha$ is the runtime per MAC with free generation.
This explains the doubling. A cache twice as large fits a tile of $A$ that is twice as tall. 

Let's look at a numerical example, in our default setup, $T_M = 12$ and $alpha approx 0.85$, so $g_c approx 10$, and for 8, 32 and 64 KB the rule gives about 3.5, 20 and 40, those are exactly the points in which lines of @fig-hw-prng start to climb.

Our suggestion, measure $alpha$ once with free generation, find the tallest tile whose tile of $A$ fits in $L_1$, and choose the
slowest generator with $g_c$ below $T_M dot alpha$. A generator slower than that is not catastrophic, *up to* about twice this $g_c$
the slowdown in our simulations stays around 5%.

// TODO: replace the figure with the full-grid run (hw_prng_budget, SMALL = False) at the end

=== How Big Must The FIFO Be? <sec-hw-fifo>

The FIFO takes on-chip memory that could otherwise go to the cache, so we would want the smallest FIFO that still gives the best performance possible. Our default FIFO is so large that it never fills. We now shrink it, from one register block (16 elements) up to the default, and compare the best runtime at each size with the best runtime of the "unlimited" FIFO, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_fifo_size.svg", width: 100%),
  caption: [Slowdown caused by a small FIFO: the best runtime with a FIFO of the given size divided by the best runtime with an unlimited FIFO, one line per $g_c$. The dotted line marks 1%.],
) <fig-hw-fifo>

@fig-hw-fifo shows that the FIFO size does matter. A FIFO that holds only one register block can make the computation up to a
third slower. But on the other hand, even a relatively small FIFO is usually enough. Even a few hundred elements, about 1 KB, bring almost every line to within 1% of the "unlimited" FIFO. In addition, for a small enough $g_c$ even the smallest FIFO is already as good as an "unlimited" one.

Looking at the graph, we can observe an unintuitive phenomenon. $g_c = 40$ needs a smaller capacity than $g_c = 20$. Intuitively
we would expect the opposite, so what's going on? At $g_c = 40$ generation is expensive, so the best tile is tall ($64 times 32$),
therefore the core spends long enough on each block of $B$ for the generator to keep up. At $g_c = 20$ on the other hand, the best
tile is only $24$ rows tall, therefore the core finishes faster than the generator produces, meaning that a small FIFO affects it
more. From this we can see that the size of the FIFO does not depend on $g_c$ alone, but on the tile size as well.

We shall check if this is also true for other hardware, the FIFO lets the generator work ahead while the core is stalled on a
cache miss, and lets the core catch up when it runs on hits. So the size it needs should follow how long the core's slow stretches
are, and how many elements it takes at once. We repeated the same experiment with one change at a time:

- A faster and a slower memory.
- A compute unit of 4 MACs and of one MAC per cycle, with $16 times 16$ blocks.
- Register blocks from $2 times 2$ to $16 times 16$.

For each, @fig-fifo-configs shows the worst slowdown over all $g_c$ against the size of the FIFO.

#figure(
  image("./figures/hw_fifo_configs.svg", width: 100%),
  caption: [The worst slowdown over $g_c = 5, 10, 20, 60, 200$ caused by a FIFO of a given size, compared with an unlimited FIFO, changing one parameter of the default configuration at a time: the register block (left), the memory latency (middle), and the throughput of the compute unit with $16 times 16$ blocks (right).],
) <fig-fifo-configs>

The register block matters most by far. Every pop takes a whole register block of $R_M R_N$ size elements at once. With $2 times
2$ blocks even the smallest FIFO is enough, while $16 times 16$ blocks, 256 elements per pop, are still 19% slower with a
relatively large 4 KB capacity.

The memory latency is next in importance. The outcome it gives seems backwards, a slower memory makes the core slower, that goes
against intuition, because it should give the generator more time. The extra latency hardly changes $alpha$, but every miss now
stalls it twice as long, while between the misses, the hits run almost as fast as with the lower memory latency. During a stall
the generator keeps working, and on a miss, everything it produces waits in the queue. Right after the miss, the core runs
much faster than the generator again, and quickly uses it up and stalling. Therefore a longer stall means we need more space to store more
data, so the FIFO needs to grow roughly in proportion to the latency. About 128 elements with 90 cycles, 256 with
180, and 512 to 1024 with 360.

Large blocks make the core fast, and there the speed of the compute unit matters.
A slower compute unit needs a smaller FIFO. The time spent on arithmetic slows the pace at which the core takes elements from the
FIFO, so it runs ahead of the generator less. With one MAC per cycle, 1 KB is enough even for $16 times 16$ blocks.
What the FIFO has to cover is therefore not the register block alone, but how fast the core consumes $B$. Large register blocks with fast arithmetic need the largest FIFO.

Our suggestion, size the FIFO by how fast the core is. With a slow compute unit, about one MAC per cycle, 1 KB is enough for any
register block. With a fast one, the FIFO has to grow with the register block. About 1 KB for our $4 times 4$ blocks, 2 KB for $8
times 8$ blocks, and more than 16 KB for $16 times 16$ blocks. The FIFO also grows roughly in proportion to the memory latency.
Twice the latency needs about twice the FIFO. A larger FIFO than that gains almost nothing, and as the next section shows, it can
even reduce performance because of the memory it takes away from the cache.

=== Should I use a bigger cache or a bigger FIFO? <sec-hw-split>
When we have a certain SRAM budget, we need to decide how much should go to the FIFO queue vs how much goes to the cache.  To see how to split it, we fix a budget of 16 KB or 32 KB and give the FIFO anything from 64 bytes to almost all of it, and the cache the rest.

#figure(
  image("./figures/hw_sram_split.svg", width: 100%),
  caption: [Best runtime when a fixed on-chip budget is split between the FIFO and the $L_1$ cache, one line per $g_c$. The horizontal axis is the FIFO's share of the budget, stretched at both ends, and the cache gets the rest. Both axes are logarithmic.],
) <fig-hw-split>

@fig-hw-split shows that with a FIFO that is too small, the generator cannot work ahead, and the computation slows down. But a
minimum can be seen at around 10% FIFO budget share, while a FIFO share above 50% quickly turns catastrophic in terms of performance. 
Therefore our suggestion is that once the FIFO is large enough (about 1 KB in our setup, @sec-hw-fifo gives the size for other hardware) every additional byte should go to the cache.

// TODO: replace the figures with the full-grid runs (hw_fifo_size and hw_sram_split, SMALL = False) at the end

=== Does The Cache Need To Be Fully Associative? <sec-hw-assoc>

So far the cache was fully associative, which mimics the behavior of a software-managed scratchpad. Non scratchpad caches are
usually 8-way or 4-way set-associative though, which carries with it the main advantage of being automatic when it comes to memory
allocation. We wanted to test how much performance we need to pay if we decide to go with the cheaper build. We repeat the search for the best tile on a 16 KB 4-, 8-, 16- and 32-way $L_1$, and compare their best runtime with the fully associative one.

#figure(
  image("./figures/hw_assoc_unpadded.svg", width: 100%),
  caption: [Extra time of the best tile on a 4-, 8-, 16- and 32-way $L_1$ over the best tile on a fully associative $L_1$ (16 KB, our $192 times 256 times 256$ matrix). The 4-, 8- and 16-way lines coincide, so their markers are drawn one around the other.],
) <fig-hw-assoc>

@fig-hw-assoc shows that the price of going set-associative is very high. As long as generation is not almost free, the
performance becomes two to six times worse with a set-associative cache. Adding ways barely helps: the 4-, 8- and 16-way caches
give exactly the same results, and only the 32-way cache does better but in a negligible amount.

A set-associative cache decides where a line goes by its address. Line number $l$ can only go to set $l(mod S)$, where $S$ is the
number of sets, and each set holds only a few lines. Along a row, consecutive lines go to consecutive sets, $0, 1, 2, dots$. But a
tile does not strictly walk along a row. For our setup, at every step of the inner loop, the core needs the *same* column from
every row of the tile. In our case a row is 256 elements of 4 bytes, meaning 16 cache lines, so going down by one row adds 16
to the line number, we can see the effect in the table below:

#align(center, table(
  columns: 6,
  align: center,
  table.header([row], [0], [1], [2], [3], [4]),
  [first line], [0], [16], [32], [48], [64],
  [set ($mod 32$)], [0], [16], [0], [16], [0],
))

Adding 16 twice is a full turn of 32, so all the rows of a tile column land on the same two sets. Two sets of 8 ways hold only 16
rows, so any tile taller than that thrashes the cache, even though there's still plenty of room. The 4-way cache has twice the sets but half the ways, which again leaves exactly 16 rows, and so does the 16-way cache, where the whole column lands in a single set of 16 ways.

Fortunately, there's a fix. The problem is not the cache, but the fact that the length of a row and the number of sets are both
powers of two. Therefore if we can just pad the matrix with a few extra elements to every row, it will change how far apart the
rows are, without effectively changing the matrix. Specifically if we make the matrix hold rows with an *odd* number of cache
lines, that will allow the rows to spread over all the sets. For example, with rows of 272 elements, 17 lines, the rows start at sets $0, 17, 2, 19, 4, dots$, and only repeat after all 32 sets have been used. In addition, the padding does not have to be read, so it only costs a little extra memory.

#figure(
  image("./figures/hw_assoc_padded.svg", width: 100%),
  caption: [Extra time of the best tile on an 8-way $L_1$ over a fully associative one, for rows of 256 elements (unpadded), 260 and 272 (padded).],
) <fig-hw-assoc-padded>

@fig-hw-assoc-padded shows the effects of padding. With rows of 17 lines, the 8-way cache is almost exactly as good as the fully
associative one. The padding has to give an *odd* number of lines. A row of 260 elements is 16.25 lines, so the rows still
alternate between two sets and only move on to the next pair every four rows. This spreads them slowly and unevenly, it's still
better than rows with power of two size, but worse than giving it a little extra padding so the rows will have an odd number of
lines.

The small peak of the 17-line rows around $g_c = 15$ to $20$ comes from the best tile there, $24 times 128$. It nearly fills the
cache, and padding spreads its rows well but not perfectly evenly, so one set has to hold 9 lines instead of the max of 8 for that
set. Our simulator missed a better option because it is not part of our grid of tile size options.

Our suggestion, a fully associative cache or a scratchpad mostly protects against unpadded data, and making a set-associative
cache more associative or replacing it with a scratchpad is an expensive fix. Padding is nearly free. We therefore suggest an ordinary 8-way or even 4-way cache, together with software that pads the rows of its matrices to an odd number of cache lines.

=== Does The Replacement Policy Matter? <sec-hw-policy>

So far the cache always evicted the least recently used line (LRU). In our case LRU sometimes evicts the strip of $A$ that we know
we will use in the future, causing the misses that cause the first cliff we see in the $alpha$ analysis. Our thought was, a random
replacement policy will not do that to the same extent. Instead it evicts a random line, so part of the loop can survive by
chance, and the hit rate should fall gradually instead of collapsing. Random replacement could therefore make tall tiles usable past
the cliff, just where hiding a slow generator needs those tall tiles most. To check, we compare LRU and random replacement on the default 16 KB fully associative $L_1$, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_policy_alpha.svg", width: 100%),
  caption: [The memory cost $alpha$ against $T_M$ ($T_N = 16$) for two replacement policies of a 16 KB fully associative $L_1$, on a taller $384 times 256 times 256$ matrix so that the tiles can grow past $T_M = 200$. The vertical axis is logarithmic.],
) <fig-hw-policy-alpha>

@fig-hw-policy-alpha shows that random replacement does exactly that, it smooths out the cliffs, in addition, just past a cliff it
is cheaper than LRU, this can be seen just past the first cliff in the figure. At $T_M = 16$ the strip of $A$ just
misses fitting in $L_1$, LRU loses all of it, while random keeps most of it. Interestingly above $T_M = 128$ the same phenomenon
happens but Random Replacement keeps winning past the cliff as well, showing that when thrashing is inevitable, random replacement
might just be a better choice. Everywhere else though, as intuition would hold, random is more expensive, because it sometimes evicts a line that is still needed, where LRU keeps everything.

Why does random keep its advantage for so long past the second cliff? Past $T_M = 128$, every step along $K$ walks over the
same lines of $A$ and $C$ in the same order, and there are more of them than $L_1$ can hold. LRU always evicts the line that was
used longest ago, which in a loop is exactly the line that is needed next. So as soon as the loop is even slightly too long, LRU
misses on every access. Random replacement has no such bad luck. It evicts lines by chance, so many lines survive until the loop
comes back to them. The longer the loop, the more misses happen before a line is needed again, and the smaller its chance to
survive, but this chance shrinks slowly. With a loop one and a half times the size of the cache, almost half of the accesses still
hit, and only with a loop about three times the cache, at $T_M = 384$, does almost every access miss, which is where the two curves
finally meet. The flat stretch from $T_M = 192$ to 252 is caused by the short last row of @sec-refine, there the matrix has a taller row of
tiles and a shorter one, both past the cliff, and their average hardly changes. At $T_M = 260$ the short row fits again, which is
also why LRU drops there.

Whether random replacement is worth it therefore depends on whether the best tile is past a cliff. @fig-hw-policy-slow compares
the best tile over all tiles with each policy, from fast to extremely slow generators ($g_c$ from 5 to 6400), on the default
configuration. 

#figure(
  image("./figures/hw_policy_slow.svg", width: 100%),
  caption: [The best runtime over all tiles with random replacement, compared with LRU, against $g_c$ (logarithmic), on the default configuration. The marker shows whether the best tile with random fits below the cliff ($T_M <= 128$) or is past it ($T_M = 192$).],
) <fig-hw-policy-slow>

We can see that it splits to three ranges:

+ Up to $g_c = 200$, random is 7% to 28% slower. Here the best tile sits just below a cliff, where LRU keeps everything the tile
  needs, so the advantage of random past the cliffs never helps.
+ From $g_c = 300$ to 1200, both are the same. The generation is so slow that it hides the memory completely. The runtime is then
  $g_c slash T_M$ no matter what the cache does.
+ From $g_c = 1400$ to 4000, random is faster, by up to 37% at $g_c = 2400$. Here even the 96 tall tile waits too long for
  generation, and the only way to generate $B$ fewer times is a tile as tall as the matrix, $T_M = M = 192$. That tile is past the
  second cliff, but the random policy manages to keep some of the needed memory cached while the LRU policy always gets rid of it
  and thrashes. Only once generation is slow enough to hide even that effect, from $g_c approx 4800$, both policies are the same again.

So random only wins when the generator is extremely slow, here about 1400 to 4000 cycles per element, far slower than in the rest
of our experiments. The range moves with the size of the matrix and of the cache, but the reason stays the same, random can only
help when the best option is a tile past a cliff.

Our suggestion is to keep LRU and choose a tile that fits. Tiling already makes the access pattern of the best tile LRU-friendly,
and for any realistic generator random replacement costs up to 28% more cycles. Only a system whose generator is too slow for any tile below the cliff to hide it would gain from random replacement.

=== How Fast Must The Compute Unit Be? <sec-hw-mac>

The last part of the hardware is the compute unit that does the MACs. A fast compute unit costs area and power, so how fast
does it really need to be? To check, we give the compute unit a throughput, from 16 MACs per cycle, roughly a 16-wide vector
unit, down to one MAC per cycle, roughly a scalar core. A register block multiply ($R_M R_N$ elements over $R_K$ steps of $K$, 64
MACs) then takes from 4 to 64 cycles. At every $g_c$ we compare the best runtime with the best runtime of a free MAC, with the
default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_compute_speed.svg", width: 100%),
  caption: [Slowdown caused by the compute unit: the best runtime with a compute unit of the given throughput divided by the best runtime with a free MAC.],
) <fig-hw-mac>

When generation is cheap, every cycle counts. At a small $g_c$, the core does its arithmetic right after the memory access, and
since there is no wait for generation to hide it in, the cost of a MAC is simply added to the memory cost. A scalar unit can make the computation more than twice as slow, and even 4 MACs per cycle cost almost 30% more.

On the other hand when generation is expensive, a slow compute unit has almost no effect. The generator keeps working in the
background while the core computes, so the time spent on arithmetic fills time in which the core would otherwise stall anyway. As long as memory plus arithmetic still take less time than generation, the arithmetic is hidden completely.

Our suggestion, the compute unit only has to be as fast as the generator lets it be. A system with a slow generator can save
area and power with a slower compute unit, almost for free, so in that case no need to spend more on better compute. The other way
around also holds. If you have a fast generator it must also come with a fast compute unit, or the performance would suffer immensely.

We can also predict how much slower the model will run, the model of @sec-refine provides the answer to this. The core does its
memory accesses and its arithmetic one after the other. In the model we describe the compute unit by the inverse of its
throughput, the cost of a MAC $c$ in cycles per MAC, so 16 MACs per cycle is $c = 1 slash 16$. Every other term of the model is
already in cycles per MAC, so $c$ is simply added to the memory cost. Every tile now costs $alpha + c$ per MAC instead of $alpha$, and the rest of the model stays the same. With this one change, the model predicts the best runtime of every MAC cost and $g_c$ we simulated within 0.3%, and picks the best tile every time. For a single tile, the arithmetic is free as long as
$ alpha + c <= g_c dot ceil(M slash T_M) / M, $

that is, as long as memory and arithmetic together still take less time than generation. So the engineer can calibrate $alpha$ once with a free MAC, and then evaluate any compute unit by adding its cost per MAC to the table and letting the model of @sec-test-model choose again.

// TODO: replace the figure with the full-grid run (hw_mac_cost, SMALL = False) at the end

== gem5 Simulation <sec-gem5>

Our simulator charges every cache miss in full before the next access can start, while the generator keeps working in the
background. This favors the PRNG-FIFO. On real hardware several misses are in flight at once and the core overlaps them with
computation, so reading $B$ from memory costs less than our simulator says. To see how much of the PRNG-FIFO's advantage is left on
a more realistic core, we repeated the main experiment in gem5 @lowepower2020gem5, a cycle-level simulator of real cores and memory
systems.

=== Configuration

Every gem5 run compares two sources of $B$. The baseline is the conventional system of @reproduce: $B$ is a stored matrix in
DRAM, in int8, and the core reads it through the caches like $A$ and $C$. We call this "$B$ in memory". Against it we run the
same kernel with $B$ coming from the PRNG-FIFO, which takes the place of memory as the source of $B$. In both cases $B$ is int8
because that is its stored precision in the asymmetric-precision setting of @sec-importance. The time to generate an element is
a separate parameter, $g_c$, which is zero until @sec-gem5-gencost.

To model an accelerated system that is somewhat close to reality, we chose the C7x DSP accelerator of TI's J722S, the C7524,
and took the sizes of the system from it: a 1 GHz clock, a 32 KB $L_1$ data cache and a 64 KB $L_2$ @ti-j722s-sdk, and 256-bit
vectors @ti-spruiv4. gem5 has no model of the C7x itself, so the core that runs with these sizes is gem5's in-order Arm core,
`MinorCPU`, with SVE vectors of the same width. The results therefore describe an in-order core with the C7524's memory sizes.

The PRNG-FIFO is a new gem5 component that sits between the core's data port and the $L_1$ data cache, where @fig-system puts
it. It owns a window of addresses. A read inside the window is answered by the generator and never reaches the cache, and every
other access passes through to the cache unchanged. The kernel therefore reads $B$ with ordinary load instructions, and the
core treats them like any other load: it can issue them early, and it can issue them on a mispredicted path, which matters in
@sec-gem5-branch.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header([*Parameter*], [*gem5 setting*], [*C7524*]),
    [Core], [in-order Arm (`MinorCPU`), 4-wide issue, 2 vector FP units with 4-cycle latency], [C7x, in-order],
    [Vector width], [256 bits (SVE)], [256 bits],
    [Clock], [1 GHz], [1 GHz],
    [$L_1$ instruction cache], [32 KB, 4-way], [32 KB],
    [$L_1$ data cache], [32 KB, 8-way, 64-byte lines, 2-cycle tag and data, 8 MSHRs], [32 KB],
    [$L_2$ cache], [64 KB, 8-way, 6-cycle tag and data, 16 MSHRs], [64 KB],
    [Prefetcher], [stride, degree 4 on $L_1$D and 8 on $L_2$, on or off per run], [our choice],
    [Memory], [DDR4-2400, 66 cycles per $L_2$ miss on average], [our choice],
    [Memory accesses in flight from the core], [2 (gem5 default for this core)], [our choice],
    [Branch predictor], [tournament (gem5 default)], [our choice],
  ),
  caption: [The simulated system. The right column lists what we matched to the C7524 and what we chose ourselves.],
) <tab-gem5-system>

Two things in gem5 change the comparison. First, memory work overlaps with computation. The caches keep serving hits while misses
are outstanding, the core can have two memory accesses in flight, the prefetcher fetches ahead, and DRAM has a bandwidth instead
of a fixed latency. Reading $B$ from memory now overlaps too, where our simulator only let the generator overlap. Second, the core
predicts branches. After a mispredicted branch it runs ahead on the wrong path and throws that work away when the branch
resolves, but a read it sent to the FIFO on that path has already advanced the FIFO.

The kernel is written with SVE intrinsics and computes $C = C + A B$, with $A$ and $C$ in fp32 and $B$ in int8, converted to
fp32 when it is loaded. From the outside in, its loops run over row bands of $T_M$ rows, tiles of $T_N$ columns, steps of 8 along
$K$ (we call one such step a k-step), the $T_N slash 8$ column blocks of the tile, and the $T_M slash 8$ row blocks. Each
$8 times 8$ block of $B$ is loaded into registers once and used by all the row blocks, which is the $B$-stationary dataflow of
@sec-dataflow; a row block updates an $8 times 8$ block of $C$ held in eight registers.

#figure(
  table(
    columns: 2,
    align: (left, left),
    table.header([*Parameter*], [*Value*]),
    [Matrices $M times K times N$], [$192 times 128 times 512$ (12.6 M MACs)],
    [Element types], [$A$ and $C$ fp32, $B$ int8],
    [Tiles], [$T_M in {8, 16, 32, 48, 64, 96, 192}$, $T_N in {8, 16, 32, 64, 128}$ (35 tiles)],
    [Source of $B$], [memory, seeded PRNG-FIFO or counter PRNG-FIFO (@sec-gem5-fifo)],
    [Settings], [no padding with prefetcher, padding without prefetcher, padding with prefetcher (@sec-gem5-pad)],
    [FIFO capacity], [2 KB],
    [FIFO read latency], [1 cycle],
    [Generation cost $g_c$], [0 in @sec-gem5-results and @sec-gem5-branch, 1 to 128 in @sec-gem5-gencost],
  ),
  caption: [Workload and FIFO parameters of the gem5 runs.],
) <tab-gem5-kernel>

==== Row padding <sec-gem5-pad>

Our gem5 caches are 8-way, so there are set conflicts like those of @sec-hw-assoc. A row of $C$ is 512 floats, 2048 bytes or 32
lines, so all the rows of a column of $C$ land in 2 of the 64 sets of $L_1$ and 4 of the 128 sets of $L_2$. That leaves room for
16 rows in $L_1$ and 32 in $L_2$. Padding every row of $A$ and $C$ with 16 floats (64 bytes) makes a row of $C$ 33 lines long, an
odd number, and the rows spread over all the sets. We ran every tile with and without padding.

==== Seeded and counter PRNG-FIFO <sec-gem5-fifo>

The seeded PRNG-FIFO is the one of @sec-system. Before each tile the kernel writes the tile's seed to the FIFO, which empties it
and restarts the generator from that seed, and the tile then reads $B$ as a stream, in order, from the start of the FIFO's window.
A read returns the next elements of the stream, whatever its address.

The counter PRNG-FIFO has no seed. Each element of $B$ is a function of its own index, and the kernel reads $B$ at its address in
a fixed window. It is the same component with the same timing; only what a read returns differs.

The two run in the same number of cycles, within 0.1% on every tile, so the figures below show the counter PRNG-FIFO. The seeded
one appears only in @sec-gem5-branch, where the two differ in what the core computes.

=== Results with a free generator <sec-gem5-results>

#figure(
  image("./figures/gem5_cycles.svg", width: 100%),
  caption: [Cycles per MAC for every tile with a free generator ($g_c = 0$). Top row: $B$ in memory. Bottom row: counter PRNG-FIFO. Columns: the three settings. The box marks the best tile of each panel. Lower is better.],
) <fig-gem5-cycles>

With padding, both sources of $B$ have the same best tile, $64 times 64$, at 0.44 cycles per MAC with $B$ in memory and 0.41
with the PRNG-FIFO. The shape of the grid is the one our simulator gave. Going down a column, the runtime falls while the strip
of $A$ ($T_M times K$ floats, 4 KB per 8 rows) fits in $L_1$, and climbs once it does not, from $T_M = 64$ (32 KB) and again at
$T_M = 192$, where the 96 KB strip is larger than $L_2$. Going right along a row, the runtime falls because a wider tile reloads
$A$ fewer times (a row band has $N slash T_N$ tiles), until the tile of $C$ pushes $A$ out of the cache, at $T_N = 128$.

Without padding the grid is ruled by set conflicts (@sec-gem5-pad). Every tile with $T_M >= 32$ runs at 0.65 to 2 cycles per
MAC with either source of $B$, and the best tiles are the short ones. The PRNG-FIFO changes little here, since the conflicts are
between rows of $A$ and $C$.

#figure(
  image("./figures/gem5_misses.svg", width: 100%),
  caption: [$L_1$ data cache misses (left) and $L_2$ misses (right) against $T_M$, at $T_N = 16$ with padding. Solid lines: prefetcher off. Dashed: counter PRNG-FIFO with the prefetcher on. With $B$ in memory the prefetcher also changes the misses only at $T_M = 8$ (not drawn).],
) <fig-gem5-misses>

The steps in @fig-gem5-misses are the capacity limits. The strip of $A$ is 24 KB at $T_M = 48$ and 32 KB at $T_M = 64$, where
it no longer fits in $L_1$ next to the tile of $C$, so $A$ is read again for every tile and the $L_1$ misses jump sevenfold.
$L_2$ has the same step at $T_M = 192$. With $B$ in memory the $L_1$ misses first fall as $T_M$ grows, because every row band
reads all of $B$ and there are $M slash T_M$ row bands, and then climb the same step.

The prefetcher only does something at $T_M = 8$, where it removes 95% of the $L_1$ misses. There, a tile has one row block, and
every load instruction of the kernel walks memory with one fixed stride of 32 bytes. In a taller tile, each load instruction
steps from one row block to the next, 4.6 KB along $A$ and 16.9 KB along $C$ with padding, which is past the end of the 4 KB
page, and gem5's stride prefetcher does not prefetch across pages: at $T_M = 64$ it identifies 221 thousand candidates and
issues none. For every tile with $T_M >= 16$ the runs with and without the prefetcher agree within 0.1%. What makes memory
cheaper here than in our simulator is the overlap of misses with computation and with each other, and the prefetcher has
almost no part in it.

#figure(
  image("./figures/gem5_speedup.svg", width: 100%),
  caption: [Speedup of the counter PRNG-FIFO over $B$ in memory on the same tile: cycles with $B$ in memory divided by cycles with the PRNG-FIFO. Blue means the PRNG-FIFO is faster.],
) <fig-gem5-speedup>

On the same tile the PRNG-FIFO is faster everywhere, from 1.00 at $T_M = 192$ to 1.96 at $8 times 8$, and the gain follows the
traffic of $B$. With $B$ in memory every row band reads all of $B$, so the traffic of $B$ per MAC is proportional to $1 slash
T_M$, and the PRNG-FIFO removes exactly this traffic. The prefetcher does not move the ratio; the conflicts of the unpadded runs
shrink it on the tall tiles, where both sources of $B$ wait on the same conflict misses. The best tile with $B$ in memory is
already tall, though, so best against best the gain is 8% (0.44 against 0.41 cycles per MAC), and 28% without padding (0.56
against 0.44), where the conflicts rule out the tall tiles for $B$ in memory.

=== Branch prediction and the FIFO <sec-gem5-branch>

The core of our simulator is in order and never speculates, so every read of the FIFO belongs to the computation. gem5's core
predicts branches and runs ahead on the predicted path. When the prediction turns out wrong it throws that work away, but a
load it issued on the wrong path has already gone to memory. For a cache this is harmless, since reading a line changes
nothing, but a read advances a FIFO.

The loops of our kernel are predictable, so the predictor is only wrong at loop exits. When it misses the exit of the loop over
the column blocks of a tile, the core starts a column block that does not exist. A column block begins by loading its block of
$B$, and that load reaches the FIFO before the branch resolves. We see these wrong-path reads in gem5 as FIFO reads beyond what
the kernel needs.

In the counter PRNG-FIFO the data is a function of the address, so a wrong-path read only takes elements that the core throws
away. With a free generator this costs nothing, and with a slow one it costs generation time. In the seeded PRNG-FIFO a read
returns the next elements of the stream, so a wrong-path read shifts the stream, and every later read of the tile gets the
wrong elements of $B$ until the next seed. In our runs the tiles where this happens compute a wrong $C$.

A FIFO that is read as a stream therefore cannot sit behind a speculating core as it is. Either the data must depend on the
address, as in the counter PRNG-FIFO, or the FIFO must advance only on reads that commit, which the core has to tell it. The
compiler causes the same problem on a smaller scale. The loads of a block of $B$ must stay in order for a stream, and gcc
reordered them in our kernel until we put a barrier between them, in all modes.

=== A slow generator <sec-gem5-gencost>

Everything above has $g_c = 0$, so it measures the cost of everything except generation. The trade-off at the center of this
report is between memory and generation, so we ran the counter PRNG-FIFO with $g_c$ from 1 to 128 cycles per element, with
padding and the prefetcher on.

#figure(
  image("./figures/gem5_gencost_tiles.svg", width: 100%),
  caption: [Cycles per MAC of the counter PRNG-FIFO for every tile, one panel per $g_c$. The panels of $g_c = 1$ to 16 are the same as $g_c = 0$ and are left out. The box marks the best tile.],
) <fig-gem5-gencost>

Up to $g_c = 16$ the grid does not change. Each element of $B$ is used by the $T_M$ rows of its tile, so generation costs
$g_c slash T_M$ cycles per MAC, and at $g_c = 16$ that is 0.25 for the $64 times 64$ tile, below its memory cost of 0.41. From
$g_c = 32$ the short tiles are generation bound at exactly $g_c slash T_M$ (1.0, 2.0 and 4.0 cycles per MAC at $T_M = 32$, 16
and 8), and the best tile moves up: $96 times 16$ at $g_c = 32$, $192 times 64$ at 64, $192 times 16$ at 128. This is the
picture of @sec-mem-vs-gen and @sec-hw-prng on a real core: the best tile grows taller with the generation cost.

#figure(
  image("./figures/gem5_gencost_speedup.svg", width: 70%),
  caption: [Speedup of the counter PRNG-FIFO over the best tile with $B$ in memory ($64 times 64$, 0.44 cycles per MAC) as $g_c$ grows. Blue: the best tile for each $g_c$. Orange: the best tile of $g_c = 0$, $64 times 64$, kept for every $g_c$. Above the dashed line the PRNG-FIFO is faster.],
) <fig-gem5-gencost-speedup>

Against the best tile with $B$ in memory, the PRNG-FIFO breaks even at about $g_c = 32$ on this core, if the tile is chosen
again for each $g_c$. Keeping the tile of $g_c = 0$ instead costs three times the runtime at $g_c = 128$ (0.22 against 0.68 of
the runtime with $B$ in memory), which is the point of @sec-sw-choice on a real core.

The model of @sec-refine holds as well. With $alpha$ the cycles per MAC of a tile at $g_c = 0$, taken from gem5 itself,
$max(alpha, g_c slash T_M)$ is within 3% of every gem5 run, and the tile it ranks best is gem5's best tile at all nine values
of $g_c$. gem5 is a little faster than the model at large $g_c$, because the counter FIFO starts full (a head start of $2048
g_c$ cycles) and because the core's reads wait for the generator while the caches keep working, so memory and generation
overlap more completely than in our simulator.

=== gem5 against our simulator <sec-gem5-vs-sim>

Finally, we ran our simulator on the gem5 setup: the same matrices and element sizes, a 32 KB $L_1$ and a 64 KB $L_2$ with
gem5's latencies (2 and 6 cycles, and 60 more for a miss to memory, gem5's average), $8 times 8$ register blocks, a 2 KB FIFO
read in one cycle, and fully associative caches, since the padded gem5 runs have no conflicts. @tab-gem5-vs-sim compares, for
every $g_c$, the tile each simulator ranks best and how much the tile our simulator picks loses in gem5.

#figure(
  table(
    columns: 4,
    align: (right, center, center, right),
    table.header([*$g_c$*], [*gem5 best*], [*our simulator's best*], [*its loss in gem5*]),
    [0], [$64 times 64$], [$48 times 16$], [0.5%],
    [1], [$64 times 64$], [$32 times 32$], [0.6%],
    [2], [$64 times 64$], [$32 times 32$], [0.6%],
    [4], [$64 times 64$], [$32 times 32$], [0.6%],
    [8], [$64 times 64$], [$64 times 64$], [0.0%],
    [16], [$64 times 64$], [$96 times 16$], [6.7%],
    [32], [$96 times 16$], [$192 times 64$], [18.6%],
    [64], [$192 times 64$], [$192 times 64$], [0.0%],
    [128], [$192 times 16$], [$192 times 64$], [0.2%],
  ),
  caption: [The tile each simulator ranks best for every $g_c$ (counter PRNG-FIFO, padding, prefetcher on), and the runtime our simulator's choice costs in gem5 over gem5's own best tile.],
) <tab-gem5-vs-sim>

The two agree on the shape: the tile our simulator picks costs less than 1% in gem5 at seven of the nine values of $g_c$. The exceptions are $g_c = 16$ and
32, where memory and generation are about equal and the two simulators place the crossover at a different $T_M$: ours charges
every miss in full, so it finds memory more expensive and moves to tall tiles sooner. The absolute cycle counts differ, since
our simulator has no compute cost and a simpler cache; what it is built to do is rank tiles.

=== Takeaway <sec-gem5-takeaway>

On an in-order core whose misses overlap, with a free generator, the PRNG-FIFO removes the traffic of $B$ and gains 8% at the
best tile and up to 2$times$ on short tiles that read $B$ many times. Padding is as necessary as in @sec-hw-assoc, and the
prefetcher is nearly irrelevant to tiled code on this core. With a slow generator the picture of the report repeats on gem5:
the best tile grows taller with $g_c$, the PRNG-FIFO pays off up to about $g_c = 32$ on this cache, and the model of
@sec-refine, calibrated once at $g_c = 0$, predicts gem5's runtime within 3% and chooses its best tile. gem5 also shows one
thing our simulator cannot: a speculating core reads the FIFO on the wrong path, which a stream FIFO does not survive, so the
generator must be addressable by the core, or the FIFO must pop only on reads that commit.

= Discussion

Across all the experiments, the runtime of a tile comes down to two costs that pull its height in opposite directions. Memory
wants the tile of $A$ to stay in $L_1$, which keeps $T_M$ small, and generation wants every element of $B$ to be shared by as
many rows as possible, which pushes $T_M$ up. Which of the two wins depends on $g_c$, and this gives three regimes. When
generation is cheap, the tile is memory bound and the best tile is short and wide, as in the Bharadwaj model. As $g_c$ grows,
the tile gets taller to keep generation hidden, and narrower so that it still fits in $L_1$. When generation is so slow that no
tile can hide it, only the number of rows of tiles matters, and the best tile is as tall as the matrix allows.

The model follows the same picture. A table of $alpha$, measured once with free generation, together with the larger of memory and
generation for every row of tiles, predicts the runtime well enough to choose the tile, and with the fit test of refinement 4 it
does so for other matrices too. It misses mostly where memory and generation are about equal, because there they don't overlap
perfectly, and it can't predict rows that are not whole cache lines, which padding fixes.

The hardware questions come back to $alpha$ as well. The generator only has to be fast enough for the tallest tile that fits, the
FIFO only has to cover the memory latency of the register blocks in flight, and every byte beyond that is better spent on the
cache. Associativity and the replacement policy matter mostly for tiles past a cliff, which a good choice of tile avoids anyway,
and the compute unit only has to keep up with the generator.

The gem5 runs (@sec-gem5) show how much of this carries over to a more realistic core. There, misses overlap with computation,
so with a free generator the PRNG-FIFO gains 8% at the best tile, and up to 2$times$ on short tiles that read $B$ many times.
With a slow generator the best tile grows taller, the PRNG-FIFO breaks even with $B$ in memory at about $g_c = 32$ on that
cache, and the model, calibrated once in gem5 at $g_c = 0$, predicts gem5's runtime within 3% and picks its best tile. The
capacity cliffs and the need for padding show up in gem5 too, at the sizes of its own caches, and the prefetcher does nearly
nothing for tiled code. gem5 also shows a cost that our simulator has no notion of: a core that speculates reads the FIFO on a
wrong path, which costs generation time with a counter PRNG-FIFO and corrupts $B$ with a seeded one.

Our results have some limits. Our simulator charges every miss in full and has no prefetcher, which favors the PRNG-FIFO. Most of the
figures use one matrix and one cache size, so the exact thresholds move with them, even though the reasons behind them don't.
The model has to be calibrated again for every new hardware. The gem5 runs cover one core and one matrix, and their PRNG-FIFO
pops on every read that reaches it. A FIFO that only advances on reads that commit, which a speculating core needs for a seeded
generator, is the natural next step.

= Conclusion

This project asked how to tile a multiplication by a random matrix when the random matrix is not stored at all, but generated
next to the core by a PRNG-FIFO. $B$ then costs time instead of memory traffic, and its generation overlaps with the work on $A$
and $C$. When $B$ is only cheaper to load, the Bharadwaj model shows that the best tile stretches along $B$. We asked what
changes when $B$ is generated, and how the cache, the FIFO and the generator around it should be balanced. We studied this on a
cycle-level simulator of such a system, after checking that it reproduces the Bharadwaj model.

The main conclusion is that the best tile is a balance between two costs that pull its height in opposite directions. Memory
wants the tile of $A$ to stay in the cache, which keeps the tile short, and generation wants every element of $B$ to be shared by
as many rows as possible, which makes it tall. The height of the best tile follows the generator and its width follows the cache.
For this to work, $B$ must stay in the registers while the rows of the tile pass by it, so the $B$-stationary dataflow is the one
to use, unless generation costs only a few cycles.

The runtime of a tile is well described by the larger of the two costs. The memory cost, measured once with free generation,
and the generation cost of each row of tiles. A model built on this explains the best tiles we found, and chooses a tile within
1% of the best in almost every case we tested, from only two calibrations.

For a software engineer, this means padding the rows of the matrices to whole cache lines, calibrating the model twice, and
letting it choose the tile instead of defaulting to a square, which can cost up to half of the runtime. For a hardware engineer,
it means a generator just fast enough for the tallest tile that fits in $L_1$, a FIFO about as large as the memory latency
requires, with the rest of the memory spent on the cache, and an ordinary set-associative LRU cache, as long as the software pads
its matrices.

#bibliography("refs.bib", title: "Bibliography", style: "ieee")

#pagebreak()
= Appendix <sec-appendix>

== Implementation & Build Environment <sec-appendix-impl>

The full simulator source code, build configuration, and experiment reproduction scripts are available on GitHub:
#align(center)[
  #link("https://github.com/gevorgyg/asymm_tiling")
]

The simulator is built with CMake (version $>= 3.16$) targeting the C++20 language standard. The implementation avoids heavy runtime frameworks and utilizes header-only libraries:
- *CLI11:* Provides command-line option parsing with automatic type conversion and validation.
- *toml++:* Parses TOML configuration files (`config.toml`), allowing experiment parameters to be specified declaratively without recompilation.
- *fmt & spdlog:* High-performance structured logging library used to log cycle events and format aligned metrics tables.

