// ==========================================================
// Minimal Project Report Template
// ==========================================================
// Usage: fill in the metadata below, then write your report
// in the body. Compile with `typst compile report-template.typ`
// ==========================================================

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

Firstly, it can afford to have lower precision. An element of $B$ can be stored in a single bit or byte, while $A$ and $C$ keep full precision. This is an asymmetric-precision matrix multiplication, which reduces cache traffic, as shown in the original analysis @notes-random-tiling @notes-asym-cost and in our experiments (@reproduce).

Secondly, the matrix can have no storage at all. $B$ can be generated on the fly from a small seed by a pseudo-random number
generator (PRNG), as the computation consumes it. $B$ then causes no memory traffic at all, only generation time. The only thing
we need to store are negligibly sized seeds.

Either way, accessing $B$ costs much less than accessing $A$ and $C$, which is the asymmetric-access-cost that this project studies.

= Research Goals And Outline <sec-goals>

Earlier analyses of a similar question to our project count the data moved between memory and the cache, and show that the best
tile is no longer square. Instead it stretches along the cheap matrix @notes-random-tiling @notes-asym-cost. With a hardware PRNG,
however, $B$ costs time rather than traffic, and its generation runs in parallel with the work on $A$ and $C$. Our goal is to
understand how this changes the way a matrix multiplication should be tiled, and to turn that understanding into something a
hardware and software engineer can use to their advantage.

To get there, we:

+ Build a cycle-level simulator of a core with a cache hierarchy and a PRNG-FIFO.
+ Check that it reproduces the results of the original analysis (@reproduce).
+ Choose the dataflow that suits a PRNG-FIFO best (@sec-dataflow).
+ Find the best tile by simulation, and follow how its shape changes with the cost of generation (@sec-tile).
+ Develop a simple model that explains these tiles and predicts the runtime of a tile when $B$ is created by FIFO generation,
  and refine it until it matches the simulator (@sec-simple-model).
+ Answer practical design questions: which tile a software engineer should choose, and how a hardware engineer should balance the cache, the FIFO and the generator.

= Methodology

== `asymm_tiling` Simulator

To evaluate matrix multiplication under asymmetric data access costs, we designed and implemented `asymm_tiling`, a modular, cycle-accurate architectural simulator written in C++20. The simulator models the execution of general matrix multiply operations across configurable multi-level cache hierarchies, comparing conventional DRAM-backed dataflows against hardware-accelerated on-the-fly streaming.

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
    [Element size], [4 bytes for $A$, $B$ and $C$ ($B$ varies in the paper reproduction)], [FP32 / INT32 are the most commonly used types.],
    [Register tile $R_M times R_N$], [$4 times 4$], [Modest and realistic choice],
    [$L_1$ cache], [16 KB, 64-byte lines, fully associative, LRU, write-back, write-allocate], [It's a common setup, in addition fully associative cache mimics a software-managed scratchpad.],
    [$L_1$ hit latency], [4 cycles], [Realistic $L_1$ latency @hennessy2017],
    [$L_2$ cache], [none], [Easier to analyze results because of less degrees of freedom.],
    [Memory latency], [180 cycles], [Realistic DRAM latency @hennessy2017],
    [PRNG generation cost $g_c$], [swept, 0 to 600 cycles per element], [from a fast dedicated generator to a slow or shared one],
    [FIFO capacity], [16384 elements], [large enough not to limit the overlap],
    [FIFO access], [2 cycles per register block],[comparable to an $L_1$ access and should be fast],
    [MAC cost], [0], [we assume negligible MAC cost],
  ),
  caption: [Default simulation parameters.],
) <tab-params>

= Experiments And Results
== Reproducing The Original Paper <reproduce>

Before adding a generator, we check that our simulator reproduces the original analysis @notes-random-tiling @notes-asym-cost, where $B$ is still a stored matrix, only in a lower precision. There, an element of $B$ costs a fraction $rho$ of an element of $A$ to bring into fast memory. With a tile of $C$ of $T_M times T_N$ elements, the traffic per MAC is $1 slash T_N$ for $A$ and $rho slash T_M$ for $B$, so for a fixed tile area the traffic is smallest when
$ T_N / T_M = 1 / rho. $
The cheaper $B$ is, the more the best tile stretches along it, and the more it saves compared with a square tile.

To reproduce this, $A$ and $C$ use 8 bytes per element and $B$ uses a varying 8, 4, 2 or 1, so $rho = 1, 1 slash 2, 1 slash 4, 1 slash 8$. $B$ is read from memory, there is no generator, and the matrices are $256 times 256 times 256$, with the default configuration otherwise (@tab-params). For tiles of a fixed area, we measure the traffic into $L_1$ against the aspect ratio $T_N slash T_M$.

#figure(
  image("./figures/fig_paper.svg", width: 100%),
  caption: [$L_1$ read traffic against the aspect ratio of the tile, for tiles of 512 (left) and 1024 (right) elements, relative to the lowest traffic of each line. The dashed lines are the theory, $1 slash T_N + rho slash T_M$.],
) <fig-paper>

@fig-paper reproduces the main result of the paper. We can clearly see that as $B$ gets cheaper, the minimum moves to wider tiles
(larger $T_N$), from a square tile at $rho = 1$ to tiles 8 times wider at $rho = 1 slash 8$. The measured minimum is at $1 slash
rho$ or one step away from it, where the values are almost equal. In addition the savings against the square tile are 18% and 36%
at $rho = 1 slash 4$ and $1 slash 8$ respectively, very close to the predicted 20% and 37%.

== $B$-Stationary Against $C$-Stationary <sec-dataflow>

For the upcoming experiments, we want to decide on which data flow we should use when the FIFO is involved. The main reason being,
that the two dataflows differ in how often they pop the queue to receive elements of $B$. The weight-stationary ($B$-stationary)
dataflow pops $B$ once per row of tiles, so each element is reused by $T_M$ rows of matrix $A$, meaning one pop from the FIFO is amortized across $T_M$ rows. 

The output-stationary ($C$-stationary) dataflow on the other hand keeps a register block of $C$ while $B$ streams past it, so $B$
is popped again and again for every register block of $R_M$ rows, meaning it is amortized across $R_M$ rows (fewer than $T_M$). @fig-dataflow compares them on the tile $T_M = 64$, $T_N = 32$, for every integer $g_c$ from 0 to 100, with otherwise the default configuration (@tab-params).

#figure(
  image("./figures/fig_dataflow.svg", width: 100%),
  caption: [Runtime of the two dataflows against $g_c$ on the tile $64 times 32$.],
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
  caption: [Runtime of $C$-stationary divided by the runtime of $B$-stationary against $g_c$, for $T_N = 32$ and six tile heights.],
) <fig-dataflow-ratio>

@fig-dataflow-ratio repeats the comparison for six tile heights ($T_M = 4, 8, 16, 32, 64, 128$) at $T_N = 32$, for every integer $g_c$ from 0 to 100. It can be clearly seen that for each configuration, every line follows the same pattern:

+ At $g_c = 0$, $C$-stationary is always faster. $T_M = 128$ gives $C$-stationary an even bigger edge because at that size the tile no longer fits in $L_1$, making every $C$ load and store much less forgiving.
+ The ratio crosses 1 at a small $g_c$, around 4 to 5 for most heights. Only $T_M = 128$ is the exception again, crossing only at about 12, showing that when the tile does not fit inside the cache, $C$-stationary keeps its edge for longer.
+ Once both dataflows are limited by generation, the ratio reaches an asymptote. That upper bound is how many more rows share each
  generated element in $B$-stationary than in $C$-stationary: $T_M slash R_M$.

One last thing is, we can see that for a tile height of $T_M = 4$, the performance is the same for both dataflows for all $g_c$
values seen in the figure. This makes sense because it's the same height as the register files, meaning the amoretization for
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
time if the generation time is hidden by a large $T_m$. Lets call the $B$-stationary cost with free generation $T_B$. This means $C$-stationary stays faster only while: $ g_c < R_M dot T_B, $
For our $64 times 32$ tile, $T_B approx 1.15$ and
$R_M = 4$, so the crossover is at $g_c approx 4.6$, matching the crossover in @fig-dataflow. To check that this holds on other hardware, we repeated the comparison with other register blocks and with a MAC cost of one cycle:

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
=== Moving From The Paper's Model To Ours <sec-simple-model>

The paper's model @notes-random-tiling @notes-asym-cost counts traffic for matrix multiplication where both matrices require
memory storage. Our $B$ is never moved nor stored, it is generated, so we have to turn this count into time. We do it in three steps.

*1. Moving from traffic to performance in cycles:* In a real cache, the performance of $A$ and $C$ is not directly proportional to the traffic. It depends on hits, misses and whether the tile fits in $L_1$. Modeling all of that can prove to be quite difficult, therefore instead of doing that, we define it as $alpha(T_M, T_N)$. This replaces the $1 slash T_N$ term.

*2. Moving From precision to generation cost for $B$:* $B$ lives in memory. With a PRNG, it completely bypasses memory. Instead it costs $g_c$ cycles to generate, and each generated element is reused by the $T_M$ rows of its tile (@sec-dataflow), so the $B$ term becomes $g_c slash T_M$.

*3. Replacing the Sum with a Max:* The paper adds the two costs, because both are serial loads from memory. Our FIFO on the other
hand, is asynchronous. The PRNG keeps generating in the background while the core works on $A$ and $C$. The two overlap, so only the slower one sets the runtime:

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
+ The wide tiles have a "sawtooth" shape at their second step. This is a phenomenon of enabling tiles that do not completely
  divide the matrix dimensions. Those tiles, include a residual tile that is smaller than the full one, causing *less* thrashing
  of the $L_1$ cache when the $C$ tile overflows. On the other hand, those tiles that *do divide* the matrix, have no residual
  tile, therefore reaching maximal thrashing.

=== Analyzing the Fromula with different $g_c$ values <sec-mem-vs-gen>

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
height of the matrix: $M = 192$, such as $T_M = 48$ and $64$. In addition, we can see that a few measurements are slower than both curves. Why the simple model misses these points, and how to fix it, is the subject of the next section.

=== Refining The Model <sec-refine>

Here we try to refine the model to address the points that miss the model previously. For that, three refinements are needed.

*1. $B$ is generated once per row of tiles:* The flat steps come from how often $B$ is generated. The core finishes a whole row of
tiles before moving down (a whole row tile of matirx A), and every row of tiles the entire matrix $B$. Meaning $B$ is generated
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
generation, and since the rows run one after the other, these waits add up. The simple model affectively takes the max of the
averages. That lets the full row's spare memory time "hide" the short row's generation explaining the shortfalls of the previous
figure. The fix is to take the max for each row of tiles and add them up instead:

$ T / (M N K) = 1 / M (floor(M / T_M) dot max(T_M dot alpha(T_M) + s, g_c) + max(e dot alpha(e) + s, g_c)), $

$ e = M mod T_M, quad s = (g_c dot R_M R_N dot ceil(N slash T_N)) / (K N) $

The first term is the $floor(M slash T_M)$ full rows of tiles, and the second is the short last row of height $e$, which
disappears when $T_M$ divides $M$. $alpha(r)$ is measured for a tile of height $r$ in the same $g_c = 0$ runs.

$s$ is the startup of one row of tiles: $g_c dot R_M R_N$ cycles at the start of each of its $ceil(N slash T_N)$ tiles, in the
same units as $T_M dot alpha(T_M)$ and $g_c$ (cycles divided by the $K N$ MACs that every row of the matrix does).

When $T_M$ divides $M$, the short row disappears, and the formula reduces to the simple model of @sec-simple-model. There are $M slash T_M$ full rows and no short row, and $alpha(T_M)$ is simply the measured $alpha(T_M, T_N)$:
$ 1 / M dot M / T_M dot max(T_M dot alpha + s, g_c) = max(alpha + s / T_M, g_c / T_M), $
where the last step moves the $1 slash T_M$ into the max, dividing both of its terms. Giving us exactly the simple model, with the
startup added to the memory cost.

@fig-model-refined shows the same measurements as @fig-model, now against the full refined model. Over all the points of the figure, the model is within 0.2% of the measurement.

#figure(
  image("./figures/fig_model_refined.svg", width: 100%),
  caption: [As @fig-model, with the full refined model (dashed): the max taken per row of tiles, with the startup term on the memory side.],
) <fig-model-refined>

== Software Focused Design Questions <sec-sw>

A software engineer gets the hardware as it is, and has to decide how to use it. For example which tile to choose for a given
generator and for the matrices at hand. Here we aim to help that engineer, so he'll use the best configuration possible for the
setup he has to work with.

=== Can Our Model Be Trusted To Choose The Tile? <sec-test-model>

Simulating every tile at every $g_c$ is expensive, so before anything else the engineer wants to know if our model can choose the
tile instead. To choose a tile shape, we need to do three steps:

+ *Calibration:* The long part. Run every candidate tile once with $g_c = 0$ and record its $alpha(T_M, T_N)$. This gives you a table.
+ *Prediction:* This is the fast part. For a given $g_c$, go over every pair $(T_M, T_N)$ in the table. Compute its generation cost $g_c slash T_M$, and
  take the max between it and $alpha(T_M, T_N)$ plus the small startup term. If $T_M$ does not divide $M$, use the per-row max of
  @sec-refine instead. The $alpha$ of the residual last row can be read from the same table.
+ *Choosing:* Pick the pair with the smallest result. If several pairs tie, pick the one with the smaller $alpha$, as it has more room before generation becomes the bottleneck.

With the table generated by the first step, the second and third steps can be done very fast with a simple script:

```python
maybe put script example here?
```

// ```python
// import math
//
//
// # alpha of a single row of tiles: take the short last row out of the mix
// def alpha_of_rows(alpha, M_cal):
//     row_alpha = {}
//     for tile in sorted(alpha):  # smallest heights first
//         T_M, T_N = tile
//         short_row = M_cal % T_M
//         total = M_cal * alpha[(T_M, T_N)]
//         if short_row > 0:
//             total = total - short_row * row_alpha[(short_row, T_N)]
//         row_alpha[(T_M, T_N)] = total / (M_cal - short_row)
//     return row_alpha
//
//
// # the refined model for one tile, in cycles per MAC
// def predict_runtime(row_alpha, T_M, T_N, M, N, K, gc, R):
//     # the startup of one row of tiles: every tile waits for its first
//     # register block, which only adds time on the memory side
//     startup = gc * R * R * math.ceil(N / T_N) / (K * N)
//
//     # every row takes the longer of its memory and its generation time:
//     # first the full rows of height T_M, then the short last row, if any
//     full_rows = M // T_M
//     short_row = M % T_M
//     full_row_time = max(T_M * row_alpha[(T_M, T_N)] + startup, gc)
//     work = full_rows * full_row_time
//     if short_row > 0:
//         short_memory = short_row * row_alpha[(short_row, T_N)] + startup
//         short_row_time = max(short_memory, gc)
//         work = work + short_row_time
//
//     return work / M
//
//
// # the fastest predicted tile; on a tie, the one with the smaller alpha
// # M_cal: the M the table was measured on, if it is not M
// def choose_tile(alpha, M, N, K, gc, R=4, M_cal=None):
//     if M_cal is None:
//         M_cal = M
//     row_alpha = alpha_of_rows(alpha, M_cal)
//
//     best_tile = None
//     best_time = None
//     for tile in alpha:
//         T_M, T_N = tile
//         time = predict_runtime(row_alpha, T_M, T_N, M, N, K, gc, R)
//         if best_tile is None or time < best_time:
//             best_tile = tile
//             best_time = time
//         elif time == best_time and alpha[tile] < alpha[best_tile]:
//             best_tile = tile
//     return best_tile
// ```

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
the choice itself takes a short script instead of a sweep over every tile and every $g_c$.

// TODO (later): redo fig_model_accuracy with the per-row max and decide whether to add it here

=== Can One Calibration Serve Many Matrices? <sec-sw-shapes>

All the results so far are for one matrix, and calibrating every new matrix again costs one simulation per candidate tile. A
software engineer would rather keep a few calibration tables, templates, and use them for every matrix he meets. So we want to
check if maybe a few premade calibration templates can serve many different matrices.

$M$ does not have to match at all. The table holds the $alpha$ of a single row of tiles, and how many rows there are is computed
by the model, not measured. $N$ changes $alpha$ only a little. $K$ is what matters: the tile of $A$ is $T_M times K$, so $K$
decides which tile heights still fit in $L_1$. We therefore keep one template for each of a few values of $K$, each calibrated
once on a $192 times K times 256$ matrix.

Before templates can work, there is one condition. Every row of $C$ has to start at the beginning of a cache line, which means
that the length of a row, $N$, has to be a whole number of 64-byte lines, a multiple of 16 elements. If it is not, a row of a tile
of $C$ starts in the middle of a line and touches one more line than it needs. The tile then takes more of the cache, and starts to
thrash at a smaller height. @fig-sw-alignment shows three matrices that differ only in $N$: with $N = 300$, which is 18.75 lines
per row, $alpha$ starts to climb at $T_M approx 80$ instead of 128.

#figure(
  image("./figures/sw_alignment.svg", width: 100%),
  caption: [The memory cost $alpha$ against $T_M$ ($T_N = 16$) for $200 times 200 times N$ with $N = 288$, 300 and 304. The lines of 288 and 304, whole numbers of cache lines per row, coincide. Above $T_M = 128$ all three thrash completely.],
) <fig-sw-alignment>

No template can predict this, because it depends on the exact length of the row. The fix is the same as in @sec-hw-assoc: store
every row of $C$ with a few unused elements at its end, up to a multiple of 16 elements (and start $C$ itself on a cache line,
which any aligned allocation does). In the experiment below we pad both $K$ and $N$ this way.

To test the templates, we calibrated seven of them, for $K$ from 128 to 1024, and picked 20 matrices whose sizes are not powers of
two, such as $150 times 304 times 208$ and $140 times 800 times 112$. For every matrix and six values of $g_c$ from 5 to 160, the
model chooses a tile from a template, with the matrix's own $M$, $N$ and $K$, and we compare its runtime with the best tile of
that matrix, found by simulating all of its tiles. A short last row whose height is not in the template uses the nearest height
that is. @fig-sw-templates compares several ways of choosing the template.

#figure(
  image("./figures/sw_templates.svg", width: 100%),
  caption: [How close the tile chosen with each kind of table is to the best tile, over 20 matrices and six values of $g_c$ (120 cases): the share of the cases within 1%, between 1% and 5%, and more than 5% slower, and the worst case. "Own table" calibrates every matrix itself; "same ratios" calibrates a matrix 1.5 times larger in every dimension.],
) <fig-sw-templates>

The template must not have a smaller $K$ than the matrix. A tile of $A$ that fits in $L_1$ with the template's $K$ may not fit
with the real, larger one, and the model then chooses a tile that thrashes. The template with the closest $K$ fails exactly this
way, up to 35% slower. Taking the next $K$ up avoids it: a tile that fits with a larger $K$ fits with the real one too, and the
worst that can happen is that the model passes over a few taller tiles that would have fit. With this rule, 98% of the cases are
within 5% of the best tile, and the worst is 8% slower. Four templates instead of seven are almost as good. A single table for all
matrices is up to 38% slower, and calibrating on a matrix with the same ratios brings nothing beyond a template with a larger $K$.

Our suggestion is to pad the rows of $C$ to a whole number of cache lines, keep a few templates for values of $K$ about a factor
of two apart, and for every new matrix run the script of @sec-test-model on the template with the next $K$ up. Only when the last
few percent matter is it worth calibrating the matrix itself, which in our runs always came within 2% of the best tile.

=== How Much Autotuning Is Needed? <sec-sw-autotune>

Finding the best tile means calibrating the model, one run per candidate tile (@sec-test-model). With the 1536 tiles of @sec-tile,
that is a lot of runs, so we want to check if a smaller set of candidates can do almost as well. We compare several sets: every tile in steps of 4, 8 or 16, only heights that divide $M$, only powers of two, only square tiles, and no tuning at all (the default $16 times 32$ tile). For each set, the model picks a tile at every $g_c$ from its candidates, and we measure how much slower it is than the best tile overall.

#figure(
  image("./figures/sw_autotune.svg", width: 100%),
  caption: [The worst extra time, over all $g_c$, of the tile picked from each candidate set compared with the best of all 1536 tiles, against the number of calibration runs the set needs. "No tuning" is drawn at one run.],
) <fig-sw-autotune>

@fig-sw-autotune shows that most of the gain comes cheaply. Not tuning at all can be six times slower than the best tile, and square tiles alone can be twice as slow. But a few dozen well-chosen candidates, such as heights that divide $M$ with power-of-two widths, already come within about 10% of the best tile, and usually find it exactly. The full grid only polishes the last few percent. The candidates should include tall and narrow tiles, which a set of square tiles misses entirely.

Our suggestion is to always tune, but start small. Calibrate the heights that divide $M$ with power-of-two widths first. for our
runs the tile it picks is within about 10% of the best at every $g_c$, and within 1% at most of them. If the last few percent
matter, add every width for the same heights. And only when even the last few tenths of a percent matter the full grid calibration needs to be done.

=== Does The Choice Of Tile Matter? <sec-sw-choice>

Finally, we wanted to check how much does the choice actaully matter. Is using the best tile shape actually better than just using
the convenient square? We found out that it depends. That sometimes it's significantly better and sometimes it's just as good, but
it's *never* worse. And the following figure shows it.

#figure(
  image("./figures/fig_vs_square.svg", width: 100%),
  caption: [Time saved by the best tile height over the square tile $T_M = T_N$, for four fixed tile widths $T_N$ (solid), and by the overall best tile over the best square tile of any size (dashed).],
) <fig-vs-square>

Square tiles are optimal when all matrices cost the same @hongkung1981. @fig-vs-square fixes the width $T_N$, and compares the best height $T_M$ with the square tile $T_M = T_N$. The gain is the time saved, $(T_"square" - T_"best") slash T_"square"$. We can observe the following:

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

Our suggestion, don't default to a square tile. A square is only safe when generation is almost free, or when it is so expensive that it dominates every tile. Everywhere in between, the best tile saves up to half of the runtime, and choosing it costs only the calibration and a short script (@sec-test-model).

== Hardware Focused Design Questions <sec-hw>

So far the hardware was fixed. A hardware engineer designing such a system has to decide on the hardware itself: how fast the
generator must be, how large the cache and the FIFO should be, and so on. We answer each question the same way: for every
configuration and every $g_c$, we simulate all the tiles and keep the fastest one, comparing configurations by their best tile.

=== How Fast Must The PRNG Be? <sec-hw-prng>

A faster PRNG costs area and power, so the engineer wants the slowest generator that does not slow the computation down. To find it, we take the best runtime at every $g_c$ and divide it by the best runtime with free generation ($g_c = 0$): this is the slowdown caused by the generator. We repeat this for four $L_1$ sizes, 8 to 64 KB, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_prng_budget.svg", width: 100%),
  caption: [Slowdown caused by the generator, the best runtime at $g_c$ divided by the best runtime at $g_c = 0$, for four $L_1$ sizes. The dotted lines mark 5% and 10%.],
) <fig-hw-prng>

@fig-hw-prng shows that all lines start at the same place, that makes sense, at those low $g_c$ values the generator is just fast
enough. At some $g_c$ the line starts climbing in steps, and a clear pattern can be seen, the bigger the cache, the longer it
takes for generation to be the limiting factor.
doubling of $L_1$.

A bigger cache allows the use of bigger tiles while also allowing for no thrashing of the cache. A taller tile (bigger $T_M$)
generates $B$ fewer times, creating dead time between generations, which in turn allows for higher generation times.

This experiment can help us understand if we should use a bigger cache or a faster generator. We see that doubling the cache gives the same runtime gains as halving the generation cost. This makes the two upgrades interchangeable. Halving $g_c$ can also be done with a second generator working in parallel, so the engineer can simply pick whichever upgrade is cheaper and more convenient.

For general hardware configurations, generation stays hidden as long as producing one element of $B$ takes no longer than the work
it is shared by. In the best tile, every element serves the $T_M$ rows of its tile (@sec-dataflow), and every row costs the core
$alpha$ cycles per MAC. So the generator is free up to: $ g_c approx T_M dot alpha, $
where $T_M$ is the tallest tile whose tile of $A$ still fits in $L_1$, and $alpha$ is the runtime per MAC with free generation.
This explains the doubling. A cache twice as large fits a tile of $A$ that is twice as tall. 

Lets look at a numerical example, in our default setup, $T_M = 12$ and $alpha approx 0.85$, so $g_c approx 10$, and for 8, 32 and 64 KB the rule gives about 3.5, 20 and 40, those are exactly the points in which lines of @fig-hw-prng start to climb.

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
- A MAC cost of a quarter of a cycle and of one cycle.
- Register blocks from $2 times 2$ to $16 times 16$, also together with these MAC costs.

For each, @tab-fifo-configs gives the worst slowdown over all $g_c$ for three sizes of the FIFO.

#figure(
  table(
    columns: 4,
    align: (left, center, center, center),
    table.header([*Configuration*], [*16 elements*], [*256 elements (1 KB)*], [*1024 elements (4 KB)*]),
    [Default (memory 180 cycles, 16 KB $L_1$, $4 times 4$)], [32%], [3%], [2%],
    [Memory 90 cycles], [24%], [2%], [0%],
    [Memory 360 cycles], [55%], [11%], [2%],
    [MAC $1 slash 4$ cycle], [33%], [3%], [0%],
    [MAC 1 cycle], [12%], [0%], [0%],
    [Register block $2 times 2$], [1%], [0%], [0%],
    [Register block $8 times 8$], [55%], [13%], [0%],
    [Register block $8 times 8$, MAC $1 slash 4$ cycle], [63%], [8%], [0%],
    [Register block $8 times 8$, MAC 1 cycle], [67%], [1%], [0%],
    [Register block $16 times 16$], [79%], [49%], [19%],
    [Register block $16 times 16$, MAC $1 slash 4$ cycle], [66%], [13%], [2%],
    [Register block $16 times 16$, MAC 1 cycle], [64%], [1%], [1%],
  ),
  caption: [The worst slowdown over all $g_c$ caused by a FIFO of 16, 256 and 1024 elements, compared with an unlimited FIFO, changing one or two parameters of the default configuration at a time. The MAC costs are per MAC. The rows with a MAC cost of one cycle or another register block are over $g_c = 5, 10, 20, 60, 200$.],
) <tab-fifo-configs>

The register block matters most by far. Every pop takes a whole register block of $R_M R_N$ size elements at once. With $2 times
2$ blocks even the smallest FIFO is enough, while $16 times 16$ blocks, 256 elements per pop, are still 19% slower with a
relatively large 4 KB capacity.

The memory latency is next in importance. The outcome it gives seems backwards, a slower memory makes the core slower, that goes
against intuition, because it should give the generator more time. The extra latency hardly changes $alpha$, but every miss now
stalls it twice as long, while between the misses, the hits run almost as fast as with the lower memory latency. During a stall
the generator keeps working, and on a miss, everything it produces has waits in the queue. Right after the miss, the core runs
much faster than the generator again, and quickly uses it up and stalling. Therefore A longer stall means we need more space to store more
data, so the FIFO needs to grow roughly in proportion to the latency. about 128 elements with 90 cycles, 256 with
180, and 512 to 1024 with 360.

For our $4 times 4$ blocks a quarter of a cycle per MAC changes little, but larger blocks make the core faster, and there the
speed of the compute unit matters. With $2 times 2$ blocks no FIFO is needed at any MAC cost. 
A slower compute unit needs a smaller FIFO. The time spent on arithmetic slows the pace at which the core takes elements from the
FIFO, so it runs ahead of the generator less. With one cycle per MAC, 1 KB is enough for every register block up to $16 times 16$.
What the FIFO has to cover is therefore not the register block alone, but how fast the core consumes $B$. large register blocks with fast arithmetic need the largest FIFO.

Our suggestion, size the FIFO by how fast the core is. With a slow compute unit, about one cycle per MAC, 1 KB is enough for any
register block. With a fast one, the FIFO has to grow with the register block. About 1 KB for our $4 times 4$ blocks, 2 KB for $8
times 8$ blocks, and more than 16 KB for $16 times 16$ blocks. The FIFO also grows roughly in proportion to the memory latency.
Twice the latency needs about twice the FIFO. A larger FIFO that that gains almost nothing, and as the next section shows, it can
even reduce performance because of the memory it takes away from the cache.

=== Should I use a bigger cache or a bigger FIFO? <sec-hw-split>
When we have a certain SRAM budget, we need to decide how much should go to the FIFO queue vs how much goes to the cache.  To see how to split it, we fix a budget of 16 KB or 32 KB and give the FIFO anything from 64 bytes to almost all of it, and the cache the rest.

#figure(
  image("./figures/hw_sram_split.svg", width: 100%),
  caption: [Best runtime when a fixed on-chip budget is split between the FIFO and the $L_1$ cache, one line per $g_c$. The horizontal axis is the FIFO's share of the budget, stretched at both ends; the cache gets the rest. Both axes are logarithmic.],
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
  caption: [Extra time of the best tile on a 4-, 8-, 16- and 32-way $L_1$ over the best tile on a fully associative $L_1$ (16 KB, our $192 times 256 times 256$ matrix). The 4-, 8- and 16-way lines coincide.],
) <fig-hw-assoc>

@fig-hw-assoc shows that the price of going set-associative is very high. As long as generation is not almost free, the
performance becomes two to six times worse with a set-associative cache. Adding ways barely helps: the 4-, 8- and 16-way caches
give exactly the same results, and only the 32-way cache does better but in a negligible amount.

A set-associative cache decides where a line goes by its address. line number $l$ can only go to set $l(mod S)$, where $S$ is the
number of sets, and each set holds only a few lines. Along a row, consecutive lines go to consecutive sets, $0, 1, 2, dots$. But a
tile does not strictly walk along a row. For our setup, at every step of the inner loop, the core needs the *same* column from
every row of the tile. In out case a row is 256 elements of 4 bytes, meaning 16 cache lines, so going down by one row down adds 16
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
rows are, without affectively changing the matrix. Specifically if we make the matrix hold rows with an *odd* number of cache
lines, that will allow the rows spread over all the sets. For example, with rows of 272 elements, 17 lines, the rows start at sets $0, 17, 2, 19, 4, dots$, and only repeat after all 32 sets have been used. In addition, the padding does not have to be read, so it only costs a little extra memory.

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
set. Our simulator missed a better option of because it is not part of our grid of tile size options.

Our suggestion, a fully associative cache or a scratchpad mostly protects against unpadded data, and making a set-associative
cache more associative or replacing it with a scratchpad is an expensive fix. Padding is nearly free. We therefore suggest an ordinary 8-way or even 4-way cache, together with software that pads the rows of its matrices to an odd number of cache lines.

=== How Fast Must The Compute Unit Be? <sec-hw-mac>

The last part of the hardware is the compute unit that does the MACs. A fast compute unit costs area and power, so how fast
does it really need to be? To check, we give every register block multiply ($R_M R_N$ elements over $R_M$ steps of $K$, 64 MACs)
a cost, from $1 slash 16$ of a cycle per MAC, roughly a 16-wide vector unit, up to one cycle per MAC, roughly a scalar core. At
every $g_c$ we compare the best runtime with the best runtime of a free MAC, with the default configuration otherwise
(@tab-params).

#figure(
  image("./figures/hw_compute_speed.svg", width: 100%),
  caption: [Slowdown caused by the compute unit: the best runtime with a MAC cost divided by the best runtime with a free MAC, for three costs of a MAC.],
) <fig-hw-mac>

When generation is cheap, every cycle counts. At a small $g_c$, the core does its arithmetic right after the memory access, and
since there is no wait for generation to hide it in, the cost of a MAC is simply added to the memory cost. A scalar unit can make the computation more than twice as slow, and even a quarter of a cycle per MAC costs almost 30% more.

On the other hand when generation is expensive, a slow compute unit has almost no effect. The generator keeps working in the
background while the core computes, so the time spent on arithmetic fills time in which the core would otherwise stall anyway. As long as memory plus arithmetic still take less time than generation, the arithmetic is hidden completely.

Our suggestion, the compute unit only has to be as fast as the generator lets it be. A system with a slow generator can save
area and power with a slower compute unit, almost for free, so in that case no need to spend more on better compute. The other way
around also holds. If you have a fast generator it must also come with a fast compute unit, or the performance would suffer immensely.

We can also predict how much slower the model will run, the model of @sec-refine provides the answer to this. The core does its
memory accesses and its arithmetic one after the other, so a MAC cost $c$ is simply added to the memory cost. Every tile now costs $alpha + c$ per MAC instead of $alpha$, and the rest of the model stays the same. With this one change, the model predicts the best runtime of every MAC cost and $g_c$ we simulated within 0.3%, and picks the best tile every time (@fig-hw-mac-model). For a single tile, the arithmetic is free as long as
$ alpha + c <= g_c dot ceil(M slash T_M) / M, $
that is, as long as memory and arithmetic together still take less time than generation. So the engineer can calibrate $alpha$ once with a free MAC, and then evaluate any compute unit by adding its cost per MAC to the table and rerunning the script of @sec-test-model.

#figure(
  image("./figures/hw_mac_model.svg", width: 100%),
  caption: [The best runtime against $g_c$ for four costs of a MAC: measured (markers), and predicted by the refined model with $alpha + c$ in place of $alpha$ (dashed), calibrated only on the runs with a free MAC and free generation.],
) <fig-hw-mac-model>

// TODO: replace the figure with the full-grid run (hw_mac_cost, SMALL = False) at the end

= Discussion

// TODO: what spans several experiments:
// - the three regimes: memory-bound (small tile that fits), balanced (T_M up, T_N down), generation-bound (fewest rows of tiles)
// - what an engineer should do: autotune alpha once at g_c = 0, then pick the tile per g_c with the model
// - limitations: simulator, not hardware; one matrix shape in most figures; partial overlap on thrashing tiles

= Conclusion

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

