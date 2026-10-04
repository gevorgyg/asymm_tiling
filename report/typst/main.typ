// ==========================================================
// Minimal Project Report Template
// ==========================================================
// Usage: fill in the metadata below, then write your report
// in the body. Compile with `typst compile report-template.typ`
// ==========================================================

#let title = "Evaluating Matrix Tiling 
Multiplication For Asymmetric Data Cost"
#let author = "Regev Ginzburg, Areg Mikhtyrian"
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

Caches are also widely used for high performance matrix computation. Computing $C = A dot B$ with $A in RR^(M times K)$ and $B in RR^(K times N)$ takes $M N K$ multiply-accumulates (MACs) over only $M K + K N + M N$ elements: every element of $A$ is used $N$ times and every element of $B$ is used $M$ times. A straightforward loop nest streams through the matrices and, once they no longer fit in the cache, loads each element from memory over and over. *Tiling* splits the computation into tiles small enough to stay in the cache, so that a loaded element is reused many times before it is evicted.

When all matrices cost the same to access, square tiles are optimal, and no schedule can move fewer than on the order of $M N K slash sqrt(S)$ elements for a fast memory of $S$ elements @hongkung1981. In addition, Tiling is applied at two levels: cache tiles of $T_M times T_N$ output elements, and within them register tiles of $R_M times R_N$ elements.

== Importance Of An Asymmetric Data Access Model <sec-importance>

Multiplying data by a random matrix is a core building block of randomized numerical linear algebra (RandNLA) @halko2011 @woodruff2014 @martinsson2020 @murray2023. A random projection, or *sketch*, compresses a large matrix into a much smaller one while approximately preserving its geometry. By the Johnson--Lindenstrauss lemma @johnson1984, distances between $n$ points survive a random projection to only $O(log n)$ dimensions. Sketching underlies fast algorithms for low-rank approximation and least-squares problems @halko2011 @woodruff2014 @martinsson2020. In machine learning, random features approximate kernel methods by a multiplication with a random matrix @rahimi2007.

In all of these algorithms the random matrix $B$ carries no information of its own: any matrix drawn from the right distribution works. This makes it much cheaper to provide than the data it multiplies, in two ways:
+ *Low precision:* Random matrices with entries of only $plus.minus 1$ already give Johnson--Lindenstrauss guarantees @achlioptas2003. An element of $B$ can be stored in a single bit or byte, while $A$ and $C$ keep full precision. This is an asymmetric-precision matrix multiplication, which reduces cache traffic, as shown in the original analysis @notes-random-tiling @notes-asym-cost and in our experiments (@reproduce).
+ *No storage at all:* $B$ can be generated on the fly from a small seed by a pseudo-random number generator (PRNG), as the computation consumes it. $B$ then causes no memory traffic at all, only generation time.

Either way, accessing $B$ costs much less than accessing $A$ and $C$, which is the asymmetric-access-cost setting this report studies. The second option, a hardware PRNG streaming $B$ through a FIFO, is the focus of our model and experiments.

= Research Goals And Outline <sec-goals>

Earlier analyses of this setting count the words moved between memory and the cache, and show that the best tile is no longer square: it stretches along the cheap matrix @notes-random-tiling @notes-asym-cost. With a hardware PRNG, however, $B$ costs time rather than traffic, and its generation runs in parallel with the work on $A$ and $C$. Our goal is to understand how this changes the way a matrix multiplication should be tiled, and to turn that understanding into something an engineer can use.

To get there, we:
+ build a cycle-level simulator of a core with a cache hierarchy and a PRNG-FIFO.
+ check that it reproduces the results of the original analysis (@reproduce);
+ develop a simple model that predicts the runtime of a tile from that is created by FIFO generation, and refine it until it matches the simulator (@sec-simple-model);
+ use the model to find the best tile, and follow how its shape changes with the cost of generation (@sec-tile);
+ answer practical design questions: which tile a software engineer should choose, and how a hardware engineer should balance the cache, the FIFO and the generator.

The end goal is a simple recipe: measure the memory cost of each tile once, and the model gives the best tile for any generator speed.


= Methodology

== `asymm_tiling` Simulator

To evaluate matrix multiplication under asymmetric data access costs, we designed and implemented `asymm_tiling`, a modular, cycle-accurate architectural simulator written in C++20. The simulator models the execution of General Matrix Multiply (GEMM) operations across configurable multi-level cache hierarchies, comparing conventional DRAM-backed dataflows against hardware-accelerated on-the-fly streaming.

=== Architecture

The simulator is structured into decoupled, modular subsystems synchronized by a centralized event clock:

- *`MultiUnit` (Compute & Tiling Engine):* The 3D loop nest $(M, K, N)$ partitioned into tiles of $T_M times T_N$ outputs and register tiles. It supports both *Output-Stationary* and *Weight-Stationary* dataflows. The matrices $A$, $B$ and $C$ are laid out back to back from a fixed base address, so every run is deterministic.
- *`PrngFifo` (PRNG-FIFO Hardware Accelerator):* Asynchronous generator in front of a FIFO of finite element capacity. The generator produces one element of $B$ every $g_c$ cycles and pauses while the FIFO is full. The compute core pops one register block ($R_M R_N$ elements) at a time: if the FIFO holds fewer elements, the core stalls until the missing ones are generated. Each tile generation starts by loading its seed, which restarts the generator with an empty FIFO.
- *`CacheUnit` (Multi-Level Cache Controller):* Coordinates an extensible Chain-of-Responsibility hierarchy of arbitrary depth ($L_1, L_2, dots, L_k$, DRAM). The configuration currently describes an $L_1$ and an optional $L_2$.
  - *`CacheLevel`:* Manages tag/index/offset address translation, hit latency accounting, and recursive backfill on misses. Any size that splits into a power-of-two number of sets is supported, including fully associative caches.
  - *`Set` (replacement):* Every line carries an age stamp, and the replacement policy (LRU, FIFO, MRU or Random). Random replacement uses a fixed per-set seed, so runs are reproducible.

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

Building your own simulator comes with the cost of making sure it's numbers are correct. To assure that, we did the following:

*Created a Simple Python Reference Cache:* We implemented a second cache simulator, a very simple one in python. To connect between the C++ simulator and the python simulator, we created a driver program. The driver feeds the C++ `CacheUnit` a trace of reads and writes and prints relevant statistics which we cross-verify with the simple python model.

*Diff-Testing Against the Python Simulator:* The C++ cache and the reference model run the same traces and are compared access by access. As soon as there is a difference between them, we know that there's a problem. reporting the first access where they disagree. From there we can analize the problem and fix it if needed. The races we fed for testing where created with the Python testing library `Hypothesis`.

*Invariant Testing:* These tests are like sanity checks, these proparties must always hold no matter what trace was fed into the simulator. Here we test the following:

- $"Hits"(L_k) + "Misses"(L_k) = "Accesses"(L_k)$

- $"Misses"(L_k) = "Accesses"(L_(k+1))$

- Total cycles equal $sum_k "Accesses"(L_k) dot "latency"(L_k) + "DramLat" dot "DramAccesses"$

- That a Set cannot hold more lines than he has ways.

*Hypothesis Testing:* Here we test our simulator, by looking at the results. We run simulations, with different configurations, and we can inffer how the results would vary. Off course this cannot allow us to test how cycle accurate our simulator is, but it allows us to see if the results make sense as a whole, and we've found tnd fixed the most amount of bugs with this method.

*The previous simulator:* Finally, we compared the new simulator with the previous version of our simulator. During our research we've written two simulators, and we've decided to use the more effiecient one. The two were written independently from each other. On the experiments that both simulators where able to express, the results where very similar, with minor differences, corroborating that our results are somewhat accurate.

== Default Simulation Parameters:<sec-params>

Unless stated otherwise, every experiment uses the configuration in @tab-params, which is also the simulator's default `config.toml`. Experiments that vary a parameter say so.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header([*Parameter*], [*Value*], [*Why?*]),
    [Matrices $M times K times N$], [$192 times 256 times 256$], [This size allowed us to run thousands of experiments quickly, while also being large enough so that it won't fit in $L_1$.],
    [Element size], [4 bytes for $A$, $B$ and $C$ ($B$ varies in the paper reproduction)], [FP32 / INT32 are the most commonly used types.],
    [Register tile $R_M times R_N$], [$4 times 4$], [Modest and realistic choise],
    [$L_1$ cache], [16 KB, 64-byte lines, fully associative, LRU, write-back, write-allocate], [It's a common setup, in addition fully associative cache mimics the scratchpad of software-managed scratchpads.],
    [$L_1$ hit latency], [4 cycles], [Realistic $L_1$ latency @hennessy2017],
    [$L_2$ cache], [none], [Easier to analize results because of less degrees of freedom.],
    [Memory latency], [180 cycles], [Realistic DRAM latency @hennessy2017],
    [PRNG generation cost $g_c$], [swept, 0 to 600 cycles per element], [from a fast dedicated generator to a slow or shared one],
    [FIFO capacity], [16384 elements], [large enough not to limit the overlap],
    [FIFO access], [2 cycles per register block],[comparable to an $L_1$ access and should be fast],
    [MAC cost], [0], [most accelerators have negligible MAC cost],
  ),
  caption: [Default simulation parameters.],
) <tab-params>

= Experiments And Results
== Reproducing The Original Paper <reproduce>

== $B$-Stationary Against $C$-Stationary <sec-dataflow>

For the upcoming experiments, we want to decide on which data flow we should use when the FIFO is envolved. Why does it matter? Well the two dataflows differ in how often they generate $B$. The weight-stationary ($B$-stationary) dataflow generates $B$ once per row of tiles, so each element is reused by $T_M$ rows of matrix $A$, meaning one pop from the FIFO is amoratized across $T_M$ elements. The output-stationary ($C$-stationary) dataflow on the other hand keeps a register block of $C$ while $B$ streams past it, so $B$ is generated again for every register block of $R_M$ rows, meaning it is amoratized across $R_M$ elements (smaller than $T_M$). @fig-dataflow compares them on the tile $T_M = 64$, $T_N = 32$, for every integer $g_c$ from 0 to 100, with otherwise the default configuration (@tab-params). The dashed lines are the model of each dataflow: $max(alpha_B, g_c slash 64)$ and $max(alpha_C, g_c slash 4)$, with $alpha_B$ and $alpha_C$ measured at $g_c = 0$.

#figure(
  image("./figures/fig_dataflow.svg", width: 100%),
  caption: [Runtime of the two dataflows against $g_c$ on the tile $64 times 32$, measured (solid) and predicted by the model (dashed).],
) <fig-dataflow>

*$C$-stationary is faster only when generation is almost free.* At $g_c <= 2$ it is $1.68 times$ faster ($0.685$ against $1.148$ cycles per MAC). From $g_c = 3$ on its runtime grows as $g_c slash 4$, and the two dataflows cross between $g_c = 4$ and $g_c = 5$. The model places the crossover where $g_c slash R_M = alpha_B$, at $g_c^* = R_M dot alpha_B = 4.59$. Beyond it $B$-stationary is faster: $1.31 times$ at $g_c = 6$, $6.5 times$ at $g_c = 30$ and $16 times$ from $g_c = 80$ on. The model matches both dataflows within $0.2%$ at every $g_c$.

From analysing the graph we can observe a couple of interesting findings:

*$B$-stationary is not constant.* Altough it seems like it at first, if we look at a wide enough $g_c$ scale, Its generation cost $g_c slash 64$ is hidden behind $alpha_B$ up to $g_c approx 73$ which equals $T_M dot alpha_B$ (when $alpha_B$ is $"cycles" slash "MAC"$ at $g_c = 0$) Beyond it the runtime finally grows. This can be observed directly from the mathmatical model:

Using a simplfied version of the model, because the tile dimantions divide the matrix dimantions, we get:

$ T / (M N K) = max(alpha_B, g_c / T_M) $

when $g_c >= T_M dot alpha_B$ the process starts to become generation bound.

In addition $B$-Stationary has a slope $64 slash 4 = 16$ times more gentle than $C$-stationary, because each generated element serves 64 rows instead of 4.

*$C$-stationary wins at $g_c = 0$.* $B$-stationary loads and stores the register block of $C$ at every step of the inner dimantion $K$. $C$-stationary keeps it in the registers for the whole of $K$ and only loads $A$, saving the store for the end of the loop. This give $C$-stationary a clear edge when $B$ elements are essentialy free. But as we've seen, as soon as the generation cost grows above a small threshhold, this edge dissapears, and $B$-stationary dominates.

=== does this carry over to differently sized tiles?

#figure(
  image("./figures/fig_dataflow_ratio.svg", width: 100%),
  caption: [Runtime of $C$-stationary divided by the runtime of $B$-stationary against $g_c$, for $T_N = 32$ and six tile heights.],
) <fig-dataflow-ratio>

@fig-dataflow-ratio repeats the comparison for six tile heights ($T_M = 4, 8, 16, 32, 64, 128$) at $T_N = 32$, for every integer $g_c$ from 0 to 100. It can be clearly seen that for each configuration, every line follows the same pattern:
+ At $g_c = 0$, $C$-stationary is always faster: the ratio is $0.23$--$0.6$. $T_M = 128$ gives $C$-stationary an even bigger edge because at that size the tile no longer fits in $L_1$, making every $C$ load and store much less forgiving.
+ The ratio crosses 1 at $g_c^* approx R_M dot alpha_B$. only  $T_M = 128$ is the exception again, showing that if your configuration doesn't allow for tiles small enough to fit inside the cache, a $C$-stationry approach might be a good call.
+ Once both dataflows are limited by generation ($g_c >= T_M dot alpha_B$), the ratio reaches an asymptote, equal to their respective generation costs: $ (g_c slash R_M) / (g_c slash T_M) = T_M / R_M $

=== A more fair comparison
We decided to also compare each dataflow at its own best tile at each $g_c$ for a more fair comparison. @fig-dataflow-best shows the same picture: $C$-stationary is faster only while $g_c <= 3$, and from there on $B$-stationary wins by a growing margin. The crossover again follows $R_M dot alpha_B$, now with the $alpha_B$ of $B$-stationary's best tile.

#figure(
  image("./figures/fig_dataflow_best.svg", width: 100%),
  caption: [Runtime of each dataflow at its own best tile against $g_c$.],
) <fig-dataflow-best>

Since $C$-stationary wins only when generating an element costs less than about 4 cycles, the rest of this report uses the $B$-stationary dataflow.

== Reseaching our  Mathmatical Model
=== Moving From The Paper's Model To Ours <sec-simple-model>

The paper's model @notes-random-tiling @notes-asym-cost counts words moved: per MAC, $1 slash T_N$ for $A$ and $rho slash T_M$ for the cheap matrix $B$. Our $B$ is never moved, it is generated, so we have to turn this count into time. We do it in three steps.

*1. Moving from traffic to performance in cycles:* In a real cache, the performance of $A$ and $C$ is not directly preportional to the traffic. It depends on hits, misses and whether the tile fits in $L_1$. Modeling all of that can prove to be quite difficult, therefore instead of doing that, we define it as $alpha(T_M, T_N)$. This replcaes the $P_A slash T_N$ term.

*2. Moving From precision to generation cost for $B$:* $B$ lives in memory. With a PRNG, it completely bypasses memory. Instead it costs $g_c$ cycles to generate, and each generated element is reused by the $T_M$ rows of its tile (@sec-dataflow), so the $B$ term becomes $g_c slash T_M$.

*3. Replacing the Sum with a Max:* The paper adds the two costs, because both are loads from memory, one after the other. Our FIFO on the other hand, is asynchronous: the PRNG keeps generating in the background while the core works on $A$ and $C$. The two overlap, so only the slower one sets the runtime:

$ T / (M N K) = max(alpha(T_M, T_N), g_c / T_M) $

This simple model assumes that the overlap is perfect and that the tiles divide the matrix. @sec-refine shows where these assumptions break, and how to fix them.

=== The Memory Cost $alpha$ <sec-alpha>

With $g_c = 0$, generating $B$ is free, and the runtime per MAC is the memory cost $alpha(T_M, T_N)$ alone. This is very convenient and it allows us to analyis and study the behaviour of $alpha(T_M, T_N)$. Plugging in $g_c = 0$, we measured it for every $T_M$ from 4 to 128 in steps of 4 and $T_N in {4, 8, 16, 32, 64}$, with the default parameters (@tab-params).

#figure(
  image("./figures/fig_alpha.svg", width: 100%),
  caption: [The memory cost $alpha$ against the tile height $T_M$, one line per tile width $T_N$ ($g_c = 0$, $16$ KB fully associative $L_1$).],
) <fig-alpha>

@fig-alpha shows that $alpha$ takes only a few levels, separated by sharp cliffs, simillar to a step function:
+ For $T_M <= 12$, $alpha approx 0.85$ for *every* $T_N$, at this $T_M$ the $A$ tile fits entirly in $L_1$.
+ From $T_M = 16$ on, $alpha$ steps up to a height that clearly depends on $T_N$: $3.6$, $2.2$, $1.5$, $1.15$ and $0.97$ for $T_N = 4, 8, 16, 32, 64$ respectivly. This is because wider tiles are cheaper. At $T_M = 16$ the $A$ tile doesn't fit in $L_1$ anymore meaning every time we need the same tile again, it has to be reloaded from memory. Each $A$ tile row is reused $N slash T_N$. A wider tile (bigger $T_N$), reduces the amount of times the same $A$ tile row needs to be loaded from memory, increasing performance. The next point shows that this performance comes at a cost.
+ All tiles hit a second step, to $alpha approx 3.7$--$3.9$: $T_N = 64$ at $T_M approx 48$--$52$, $T_N = 32$ at $T_M approx 64$--$88$. The narrower tiles ($T_N <= 16$) do not reach the second step in this graphs range, but the wider tiles reach this step "sooner". This step is due to the combination of $T_N$ and $T_M$ giving a tile that causes the overflow of tile $C$ from $L_1$.
+ The wide tiles have a "sawthooth" shape at their second step. This is a phenomenon of enabling tiles that do not completely divide the matrix dimantions. Those tiles, include a residual tile that is smaller then the full one, allowing for less threshing of the $L_1$ cache. Those tiles that do divide the matrix on the other hand, have no residual smaller tile, and they reach a maximal amount of threshing.

=== Intuition behind the Formula <sec-mem-vs-gen>

Once generating $B$ costs time, the simple model predicts the runtime as the larger of two costs, which pull the tile height in opposite directions:
+ the memory cost $alpha$, which we've analyzed it's behaviour in the previous section.
+ the generation cost $g_c slash T_M$, which *falls* with $T_M$.

@fig-model-simple shows both for $T_N = 32$ and $T_M$ from 4 to 128 in steps of 4, together with the runtime measured at $g_c = 30$, $100$ and $200$, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/fig_model_simple.svg", width: 100%),
  caption: [The two costs of the simple model against $T_M$ ($T_N = 32$): the memory cost $alpha$ measured at $g_c = 0$ (solid), the generation cost $g_c slash T_M$ (dashed), and the measured runtime (markers) at $g_c = 30$, $100$ and $200$.],
) <fig-model-simple>

*Intuition:* The runtime always follows the higher of the two curves. The *best tile* is therefore the *lowest point* of that upper curve, "the minimum of the maximum". For a rising and a falling curve this is where they cross: to the left, generation dominates and a taller tile helps; to the right, memory dominates and a taller tile hurts.

*Why don't the points follows the curves?* At $g_c = 30$ generation is cheap, and the measured runtime sits on the higher curve almost everywhere. At $g_c = 100$ and $200$ it does not: instead of falling smoothly with $T_M$, it moves in flat steps above the generation curve. The measured results only touche it at heights that divide $M = 192$, such as $T_M = 48$ and $64$. In addition, we can see that a few measurements are slower than both curves. Why the simple model misses these points, and how to fix it, is the subject of the next section.

=== Refining The Model <sec-refine>

#highlight[TODO Improve this section]

The simple model misses some points of @fig-model-simple. Three refinements explain them.

*1. $B$ is generated once per row of tiles.* The flat steps come from how often $B$ is generated. The core finishes a whole row of tiles before moving down, and every row of tiles needs all of $B$ again. So $B$ is generated once per row of tiles, $ceil(M slash T_M)$ times in total, and its cost per MAC is
$ g_c dot ceil(M slash T_M) / M. $
This cost only changes when the number of rows of tiles changes. With $M = 192$, every height from 48 to 63 needs four rows, so they all generate $B$ four times: a taller tile in this range only makes the last row shorter. When $T_M$ divides $M$ this is exactly $g_c slash T_M$, which is why the measurements touched the simple curve only there. @fig-model shows that with this staircase, the measurements follow the model again.

#figure(
  image("./figures/fig_model.svg", width: 100%),
  caption: [As @fig-model-simple, with the generation cost of the refined model $g_c dot ceil(M slash T_M) slash M$ (dashed).],
) <fig-model>

*2. The FIFO starts empty at every tile.* Each tile loads its own seed, so the FIFO starts empty, and the first register block of $B$ must be generated before the core can start. Nothing overlaps with this wait, so it is added on top of the max: $g_c dot R_M R_N$ cycles per tile. It is small for large tiles, but grows with the number of tiles.

*3. The max is taken per row of tiles.* A few heights are still slower than both curves, for example $T_M = 88$ at $g_c = 200$. Here $192 = 88 + 88 + 16$: two full rows of tiles and a short last row of 16. Each row of tiles generates all of $B$, but the short row has very little memory work to hide it behind. The full rows wait for memory, the short row waits for generation, and since the rows run one after the other, these waits add up. Taking the max of the averages, as the simple model does, lets the full rows' spare memory time hide the short row's generation, which cannot happen. The fix is to take the max for each row of tiles and add them up:
$ T / (M N K) = 1 / M sum_"rows" max(r dot alpha(r), g_c) + "startup", $
$ "startup" = (g_c dot R_M R_N dot ceil(M slash T_M) dot ceil(N slash T_N)) / (M N K) $
where $r$ is the height of the row and $alpha(r)$ is measured for a tile of that height in the same $g_c = 0$ runs. The startup term is the wait from step 2, $g_c dot R_M R_N$ cycles at the start of every tile, multiplied by the number of tiles and spread over all the MACs. When $T_M$ divides $M$, all the rows are the same, and the formula reduces to the simple model of @sec-simple-model plus the startup term.

*Do the units make sense?* Every term must be in cycles per MAC, like $alpha$. A row of tiles of height $r$ does $r K N$ MACs and generates all of $B$, $K N$ elements, once:
- its memory time is $r K N$ MACs times $alpha(r)$ cycles per MAC, which is cycles;
- its generation time is $K N$ elements times $g_c$ cycles per element, which is also cycles.
Both are cycles, so taking their max makes sense. Dividing the sum over all rows by the $M N K$ MACs cancels the common $K N$ and leaves the $1 slash M$ in front: cycles per MAC. The startup term works the same way: $g_c$ cycles per element, times $R_M R_N$ elements per tile, times the number of tiles, divided by $M N K$.

=== Testing The Refined Model <sec-test-model>

We can use our model to pick the best tile for the job. A tile can be chosen in three steps:

+ *Calibration:* Run every candidate tile once with $g_c = 0$ and record its $alpha(T_M, T_N)$. This gives you a table.
+ *Prediction:* For a given $g_c$, go over every pair $(T_M, T_N)$ in the table. Compute its generation cost $g_c slash T_M$, take the max between it and $alpha(T_M, T_N)$, and add the small startup term. If $T_M$ does not divide $M$, use the per-row max of @sec-refine instead; the $alpha$ of the short last row can be read from the same table.
+ *Choosing:* Pick the pair with the smallest result. If several pairs tie, pick the one with the smaller $alpha$: it has more room before generation becomes the bottleneck.

This begs the question: *How good is the refined model?* Over all 1536 tiles and 41 values of $g_c$ of @sec-tile, the refined model predicts the runtime within 1% in 96% of the runs, and the tile it picks is never more than 1.5% slower than the best one.

@fig-model-validation shows this for every run. A perfect model would put every point on the diagonal. The simple model underestimates many runs, mostly the tiles with a short last row of tiles; the refined model puts almost all of them on the line.

#figure(
  image("./figures/fig_model_validation.svg", width: 100%),
  caption: [Measured against predicted runtime for every tile and $g_c > 0$ of @sec-tile, for the simple model of @sec-simple-model (left) and the refined model (right). Points on the dashed diagonal are predicted exactly.],
) <fig-model-validation>

// TODO (later): redo fig_model_accuracy with the per-row max and decide whether to add it here

== Looking at the Best Tile Sizes <sec-tile>
=== Finding the Imperically Best Tiles
To find the best tile at each generation cost, we simulated every tile with $T_M$ from 4 to 192 and $T_N$ from 4 to 128, both in steps of 4 (1536 tiles), at 42 values of $g_c$ from 0 to 600 (every integer up to 10, then increasingly coarser steps), with the default configuration otherwise (@tab-params). @fig-best-tile shows the measured best tile $(T_M^*, T_N^*)$ and the tile the model picks, using $alpha$ from the $g_c = 0$ runs.

#figure(
  image("./figures/fig_best_tile.svg", width: 100%),
  caption: [The best tile against $g_c$: its height $T_M^*$ and width $T_N^*$, measured (solid) and picked by the model (dashed).],
) <fig-best-tile>

The figure shows an interesting phenomenon, At first as $g_c$ grows, the best tile gets taller and wider, but after gc passes 10, the best tile keeps growing taller, but it becomes narrower. This continues until a point in which the a tall and wide tile is preferred again. The figure raises some interesting questions, and these are our attempts to answer them:

- *Why does $T_M$ grow?* So that generation stays hidden. Lets remind that the generation cost is $g_c dot ceil(M slash T_M) slash M$, that value must stay below $alpha$, which is about 1 cycle per MAC for good tiles, need a bigger $T_M$ as $g_c$ grows.
- *Why does $T_N$ shrink?* So that the tile still fits in $L_1$. Once the tile of $A$ no longer fits ($T_M >= 16$), a wider tile reads $A$ fewer times (@sec-alpha) and is cheaper, up to the second cliff, where the tile of $C$ and a line of $A$ per row no longer fit. A taller tile reaches that second cliff at a smaller width. 
- *Why does it become more square at high $g_c$?* From $g_c = 400$ on, generation dominates *every* good tile, so the width no longer matters either. Up to 263 tiles are within 1% of the best performing shape.

=== How much does the choice matter?
The question is, "How much better is this best shape compared to just using the default square tile?", The answer is, it depends. But sometimes it's significantly better. And the following figure shows it.

#figure(
  image("./figures/fig_vs_square.svg", width: 100%),
  caption: [Time saved by the best tile height over the square tile $T_M = T_N$, for four fixed tile widths $T_N$ (solid), and by the overall best tile over the best square tile of any size (dashed).],
) <fig-vs-square>

Square tiles are optimal when all matrices cost the same @hongkung1981. @fig-vs-square fixes the width $T_N$, and compares the best height $T_M$ with the square tile $T_M = T_N$. The gain is the time saved, $(T_"square" - T_"best") slash T_"square"$. We can observe the following:

- *Small $g_c$:* The generation cost is hardly a factor, so the limiting factor is the memory, therefore the gain is proportional to how *badly* the square tile fits in $L_1$. A $64 times 64$ tile threshes the $L_1$ cache ($alpha = 3.74$), while the optimal $8 times 64$ costs $0.85$, achiving a gain of 77%. Simillarly, but to the other extreme, A $8 times 8$ tile already fits, and the gain is about 1%.
- *Large $g_c$:* At a large $g_c$, generation is by far the limiting factor for both tiles, so both runtimes grow in proportion to $g_c$. The gain tends to one minus the ratio of their generation costs, $1 - ceil(M slash T_"best") slash ceil(M slash T_N)$, which only depends on the tile ratios, and is why each line in @fig-vs-square flattens.
- *In between,* the gain drops to zero where the square tile happens to cost as much as the best height, for example $32 times 32$ for $g_c$ from 14 to 35, where it sits on the same plateau of $alpha$ as the best height, 64.

*Against the best square tile of any size* (dashed line), shows the gains of the best asymmetric tile against the best square tile. For those, the grains are smaller, but still large at some areas. A square tile is *at least* as good when generation is cheap, when the best tile happens to be square, and when generation dominates everything. 

In between on the other hand, the best tile saves up to half of the runtime, for the reason that a square tile cannot be tall, to generate $B$ a fewer amount of times, and narrow, to fit in $L_1$, at the same time.

== Hardware Focused Design Questions <sec-hw>

So far the hardware was fixed. A hardware engineer designing such a system has to decide on the hardware itself: how fast the generator must be, how large the cache and the FIFO should be, and so on. We answer each question the same way: for every configuration and every $g_c$, we simulate all the tiles and keep the fastest one. Comparing configurations by their best tile is fair, because the software will choose its tile for the hardware it runs on.

=== How Fast Must The PRNG Be? <sec-hw-prng>

A faster PRNG costs area and power, so the engineer wants the slowest generator that does not slow the computation down. To find it, we take the best runtime at every $g_c$ and divide it by the best runtime with free generation ($g_c = 0$): this is the slowdown caused by the generator. We repeat this for four $L_1$ sizes, 8 to 64 KB, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_prng_budget.svg", width: 100%),
  caption: [Slowdown caused by the generator, the best runtime at $g_c$ divided by the best runtime at $g_c = 0$, for four $L_1$ sizes. The dotted lines mark 5% and 10%.],
) <fig-hw-prng>

@fig-hw-prng shows that every line starts flat: while the generator is fast enough, its work hides completely behind the memory accesses, and it costs nothing. At some $g_c$ the line starts climbing in steps. The bigger the cache, the longer it takes for generation to be the limiting factor. An interesting observation is that the $g_c$ *doubles* with every doubling of $L_1$, as can be seen in the graph.

A bigger cache allows the use of bigger tiles, without treshing it. A taller tile (Bigger $T_M$) generates $B$ fewer times, allowing dead time between generations, which in turn delays the point at which the generation time becomes the limiting factor. The best tile is therefore the talles tile that the cache allows.

*Should I use a bigger cache or a faster generator?* We see that doubling the cache gives the same runtime gains as halving the generation cost. This makes the two upgrades interchangeable. Halving $g_c$ can also be done with a second generator working in parallel, so the engineer can simply pick whichever upgrade is cheaper and convenient.

// TODO: replace the figure with the full-grid run (hw_prng_budget, SMALL = False) at the end

=== How Big Must The FIFO Be? <sec-hw-fifo>

The FIFO takes on-chip memory that could otherwise go to the cache, so we would want the smallest FIFO that still gives the best performance possible. Our default FIFO is so large that it never fills. We now shrink it, from one register block (16 elements) up to the default, and compare the best runtime at each size with the best runtime of the "unlimited" FIFO, with the default configuration otherwise (@tab-params).

#figure(
  image("./figures/hw_fifo_size.svg", width: 100%),
  caption: [Slowdown caused by a small FIFO: the best runtime with a FIFO of the given size divided by the best runtime with an unlimited FIFO, one line per $g_c$. The dotted line marks 1%.],
) <fig-hw-fifo>

@fig-hw-fifo shows that the FIFO size does matters. A FIFO that holds only one register block can make the computation up to a third slower. But on the other hand, even a relatively small FIFO is usually enough. Even a few hundred elements, about 1 KB, bring almost every line to within 1% of the "unlimited" FIFO. In addition, for a small enough $g_c$ even the smallest FIFO is already as good as an "unlimited" one.

Looking at the graph, we can observe a unintuitive phanomanon. $g_c = 40$ needs a smaller capacity than $g_c = 20$. Intuitivaly we would expect the opposite, so what's going on? At $g_c = 40$ generation is expensive, so the best tile is tall ($64 times 32$), therefore the core spends long enough on each block of $B$ for the generator to keep up. At $g_c = 20$ on the other hand, the best tile is only $24$ rows tall, therefore the core finishes faster than the generator produces, meaning that a small FIFO affects it more. From this we can see that the size does not depend on $g_c$ alone, but on the tile size as well.

All in all, we can derive a simple rule for sizing the FIFO. In our runs, a FIFO of a few hundred elements (about 1 KB) is within 1% of an "unlimited" FIFO at almost every $g_c$, so we suggest a FIFO of about this size, because a larger FIFO gains almost nothing, and as the next section shows, can reduce performance because it takes memory away from the cache.

=== Should I use a bigger cache or a bigger FIFO? <sec-hw-fifo>
When we have a certain SRAM budget, we need to decide how much should go to the FIFO queue vs how much goes to the cache.  To see how to split it, we fix a budget of 16 KB or 32 KB and give the FIFO anything from 64 bytes to almost all of it, and the cache the rest.

#figure(
  image("./figures/hw_sram_split.svg", width: 100%),
  caption: [Best runtime when a fixed on-chip budget is split between the FIFO and the $L_1$ cache, one line per $g_c$. The horizontal axis is the FIFO's share of the budget, stretched at both ends; the cache gets the rest. Both axes are logarithmic.],
) <fig-hw-split>

@fig-hw-split With a FIFO that is too small, the generator cannot work ahead, and the computation slows down. But a clear minima is seen at around 10% FIFO budget share. While a FIFO share above 50% quickly turns catastrophic in terms of performance. Therefore we can suggest that once the FIFO holds a few register blocks (about 1 KB) every additional should go to the cache.

// TODO: replace the figures with the full-grid runs (hw_fifo_size and hw_sram_split, SMALL = False) at the end

=== Does The Cache Need To Be Fully Associative? <sec-hw-assoc>

So far the cache was fully associative, which behaves like the software-managed scratchpad of an accelerator. Real caches are usually 8-way or 4-way set-associative, which carries with it the main advantage of being cheaper to build. Therefore we wanted to test how much performance we need to pay if we decide to go with the cheaper build. we repeat the search for the best tile on a 16 KB 8-way and 4-way $L_1$, and compare their best runtime with the fully associative one.

#figure(
  image("./figures/hw_assoc_unpadded.svg", width: 100%),
  caption: [Extra time of the best tile on a 4-, 8-, 16- and 32-way $L_1$ over the best tile on a fully associative $L_1$ (16 KB, our $192 times 256 times 256$ matrix). The 4-, 8- and 16-way lines coincide.],
) <fig-hw-assoc>

@fig-hw-assoc shows that the price is very high. As long as generation is almost free, the set-associative caches lose almost nothing. But once generation costs rise even a little, the performance become two times worse. Even with their own best tile. Adding ways barely helps: the 4-, 8- and 16-way caches give exactly the same results, and only the 32-way cache does somewhat better.

*Why is it so bad?* A set-associative cache decides where a line goes by its address: line number $l$ can only go to set $l mod S$, where $S$ is the number of sets (32 here), and each set holds only a few lines. Along a row, consecutive lines go to consecutive sets, $0, 1, 2, dots$. But a tile does not walk along a row: at every step of the inner loop, it needs the *same* column from every row of the tile. A row of our matrices is 256 elements of 4 bytes, exactly 16 cache lines, so going one row down adds 16 to the line number:

#align(center, table(
  columns: 6,
  align: center,
  table.header([row], [0], [1], [2], [3], [4]),
  [first line], [0], [16], [32], [48], [64],
  [set ($mod 32$)], [0], [16], [0], [16], [0],
))

Adding 16 twice is a full turn of 32, so all the rows of a tile column land on the same two sets, while the other 30 sets hold lines the tile does not need right now. Two sets of 8 ways hold only 16 rows, so any tile taller than that thrashes, even though the cache as a whole has plenty of room. The 4-way cache has twice the sets but half the ways, which again leaves exactly 16 rows, and so does the 16-way cache, where the whole column lands in a single set of 16 ways. Only beyond that point do more ways help: the 32-way cache also puts the whole column into one set, but that set holds 32 lines. Without tall tiles, every generated element of $B$ is shared by only a few rows, and the generation cost cannot be hidden.

*The fix: padding.* The problem is not the cache, but that the length of a row is a power of two, like the number of sets. Storing every row with a few unused elements at its end changes how far apart the rows are, without changing the matrix. If a row takes an *odd* number of cache lines, the rows spread over all the sets: with rows of 272 elements, 17 lines, the rows start at sets $0, 17, 2, 19, 4, dots$, and only repeat after all 32 sets have been used. The padding is never read, so it only costs a little memory. (Our simulator has no separate row length, so we emulate the padding by enlarging the matrix to $192 times 272 times 272$.)

#figure(
  image("./figures/hw_assoc_padded.svg", width: 100%),
  caption: [Extra time of the best tile on an 8-way $L_1$ over a fully associative one, for rows of 256 elements (unpadded), 260 and 272 (padded).],
) <fig-hw-assoc-padded>

@fig-hw-assoc-padded shows the effect. With rows of 17 lines, the 8-way cache is almost exactly as good as the fully associative one. The padding has to give an *odd* number of lines, though: a row of 260 elements is 16.25 lines, so the rows still alternate between two sets and only move on to the next pair every four rows. This spreads them slowly and unevenly, and the cache still loses a lot.

*Our suggestion.* A fully associative cache or a scratchpad mostly protects against unpadded data, and making a set-associative cache more associative is an expensive fix: here it would need more ways than a row has lines before it helps at all. Padding is nearly free. We therefore suggest an ordinary 8-way or even 4-way cache, together with software that pads the rows of its matrices to an odd number of cache lines. Matrices whose rows are not a power of two long already suffer much less from this.

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

