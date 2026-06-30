# ws-cliff-and-conflict — Writeup

## Hypothesis

A capacity-bound cache exhibits a **sharp step function** in hit rate as L1
size crosses the workload's working set. A set-conflict-bound cache shows
a smear instead — some sets get pinned at full associativity while others
remain idle.

For a C-stationary matmul tile with shape `(T_M, T_N, T_K)`, the analytical
working set is

```
   WS  =  T_M·T_K·P_A  +  T_K·T_N·P_B  +  T_M·T_N·P_C
```

(A streamed, B streamed, C resident across the K reduction). This experiment
fixes a tile shape, sweeps `L1_SIZE_BYTES` finely from `0.5·WS` to `4·WS`,
and asks two questions:

- **Q1.** Is the hit-rate curve a step at `L1 = WS`?
- **Q2.** Right around `WS`, do all L1 sets see roughly equal pressure
  (capacity-bound), or do a few sets dominate the evict log (conflict-bound)?

Q2 is answered by counting `L1 Evict line=...` events per set (`line_addr %
num_sets`), parsed straight out of the level-2 trace by
`harness.trace_analysis.parse_trace`.

## Setup

- **Workload.** `m = n = k = 96`, C-stationary, `--3dregisters`, REG = 4.
- **Tile.** A "known good" middle-of-the-grid tile: `(T_M, T_N, T_K) =
  (16, 16, 96)` — Asymmetric precision. WS for that tile:
  `16·96·8 + 96·16·2 + 16·16·8 = 12288 + 3072 + 2048 = 17 408 bytes`.
- **Sweep.** `L1_SIZE_BYTES ∈ {x · WS / 16 for x in 8..64}` — 57 cells
  giving 0.5·WS to 4·WS in 1/16-WS increments. L1 line size 64 B, 8-way.
  Each cell traced at level 2.
- **L2.** Generous (4·WS) and fixed so it doesn't confound the L1 cliff.

## What we plot

`hit_rate_vs_L1.png`: L1 hit rate vs `L1_SIZE / WS`. Vertical at `L1/WS=1`.
If capacity-bound the curve hugs ~0 for L1<WS, jumps near WS, plateaus.
Smearing of the jump (over how many WS-units) is the
conflict-vs-capacity diagnostic.

`evicts_per_set_heatmap.png`: heatmap of `set_idx → evicts` at three points
on the sweep (well below WS, near WS, well above WS). If conflict-bound,
look for "hot stripes" — a few sets do all the work.

## Pass / fail criteria

- **Capacity-bound result (expected for this tile).** Sharp step within
  ±0.1·WS of L1 = WS; evict heatmap roughly uniform across sets.
- **Conflict-bound result.** Smear over several WS-units; a fraction of
  sets see 5×+ as many evicts as the median. That would be a real,
  reportable simulator finding — the set-mapping in this matmul setup
  isn't doing what naive analysis assumes.

## Reproduction

```sh
python3 -c "from experiments.v45_results.ws_cliff_and_conflict import experiment; experiment.run()"
```
