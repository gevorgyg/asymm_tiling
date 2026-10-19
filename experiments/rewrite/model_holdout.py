"""Is the refined model overfitted? (report: 4.5.1, "Can Our Model Be Trusted")

The refined model has no fitted parameters, but it was developed on one
dataset (default hardware, 192x256x256, fig_best_tile). This checks it on
held-out runs it was never developed on: other L1 sizes, memory latencies,
register blocks and set-associative caches. Nothing is re-run: every number
comes from the cached runs of those experiments (coarse tile grids).

For each configuration: alpha is calibrated on its own gc = 0 runs, then the
refined model (startup on the memory side, as in fig_best_tile.model)
predicts all its gc > 0 runs. Reported, as in report 4.5.1:
  - the share of runs whose runtime is predicted within 1 % (and 0.1 %);
  - runs predicted too slow by more than 0.1 % (the model should not do it);
  - the worst pick: the model's tile against the true best, over all gc.

run:  .venv/bin/python experiments/rewrite/model_holdout.py
"""

from dataclasses import replace
import math

import hw_assoc
import hw_memory
import hw_prng_budget
import hw_registers
from harness import Params, out_dir, run_many

M = 192


def runtimes(params: list, file) -> dict:
    stats = run_many(params, file)
    return {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / (p.m * p.k * p.n)
            for p, s in zip(params, stats)}


def evaluate(t: dict, tiles: list, gcs: list, k: int, n: int, r: int) -> tuple:
    alpha = {tl: t[(0, *tl)] for tl in tiles}
    pure = {}
    for tm, tn in sorted(alpha):
        e = M % tm
        pure[(tm, tn)] = (M * alpha[(tm, tn)] - (e * pure[(e, tn)] if e else 0)) / (M - e)

    def predict(tm: int, tn: int, gc: int) -> float:
        s = gc * r * r * math.ceil(n / tn) / (k * n)
        full, e = divmod(M, tm)
        work = full * max(tm * pure[(tm, tn)] + s, gc)
        if e:
            work += max(e * pure[(e, tn)] + s, gc)
        return work / M

    errs, picks = [], []
    for gc in gcs:
        if gc == 0:
            continue
        pred = {tl: predict(*tl, gc) for tl in tiles}
        errs += [t[(gc, *tl)] / pred[tl] - 1 for tl in tiles]
        best = min(t[(gc, *tl)] for tl in tiles)
        pick = min(tiles, key=lambda tl: (pred[tl], alpha[tl]))
        picks.append(t[(gc, *pick)] / best - 1)
    a = [abs(x) for x in errs]
    return (sum(x <= 0.01 for x in a) / len(a), sum(x <= 0.001 for x in a) / len(a),
            sum(x < -0.001 for x in errs), max(picks), len(picks))


def main() -> None:
    rows = []
    tiles = [(tm, tn) for tm in hw_prng_budget.TM for tn in hw_prng_budget.TN]

    # L1 sizes (hw_prng_budget)
    params = [replace(Params(l1_assoc=-1), l1_size=l1, tile_h=tm, tile_w=tn, gen_cost=gc)
              for l1 in hw_prng_budget.L1.values() for gc in hw_prng_budget.GC for tm, tn in tiles]
    stats = run_many(params, out_dir(hw_prng_budget.NAME) / "results_small.json")
    for name, l1 in hw_prng_budget.L1.items():
        t = {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / (p.m * p.k * p.n)
             for p, s in zip(params, stats) if p.l1_size == l1}
        rows.append((f"L1 {name}", evaluate(t, tiles, hw_prng_budget.GC, 256, 256, 4)))

    # memory latency (hw_memory)
    for mem in hw_memory.MEM:
        params = [replace(Params(l1_assoc=-1), mem_cycles=mem, tile_h=tm, tile_w=tn, gen_cost=gc)
                  for gc in hw_memory.GC for tm, tn in tiles]
        t = runtimes(params, out_dir(hw_memory.NAME) / "results_small.json")
        rows.append((f"memory {mem} cycles", evaluate(t, tiles, hw_memory.GC, 256, 256, 4)))

    # register blocks (hw_registers, unlimited FIFO)
    for r in hw_registers.R:
        params = [replace(Params(l1_assoc=-1), reg_dim=r, fifo_capacity=16384, tile_h=tm,
                          tile_w=tn, gen_cost=gc) for gc in hw_registers.GC for tm, tn in tiles]
        t = runtimes(params, out_dir(hw_registers.NAME) / "results_small.json")
        rows.append((f"register block {r}x{r}", evaluate(t, tiles, hw_registers.GC, 256, 256, r)))

    # set-associative caches, unpadded and padded rows (hw_assoc part 2)
    for k in hw_assoc.PAD:
        atiles = [(tm, tn) for tm in hw_assoc.TM for tn in [4, 8, 16, 32, 64, 128, k]]
        for aname, a in hw_assoc.ASSOC.items():
            params = [replace(Params(), k=k, n=k, l1_assoc=a, tile_h=tm, tile_w=tn, gen_cost=gc)
                      for gc in hw_assoc.GC for tm, tn in atiles]
            t = runtimes(params, out_dir(hw_assoc.NAME) / "results.json")
            rows.append((f"{aname}, rows of {k}", evaluate(t, atiles, hw_assoc.GC, k, k, 4)))

    lines = ["| configuration | runtime within 1 % | within 0.1 % | predicted too slow (> 0.1 %) "
             "| worst pick |", "|---|---|---|---|---|"]
    for name, (w1, w01, slow, worst, ngc) in rows:
        lines.append(f"| {name} | {w1:.1%} | {w01:.1%} | {slow} | {worst:.2%} |")
    report = ("# model_holdout: the refined model on held-out configurations\n\n"
              "Each configuration calibrated on its own gc = 0 runs (coarse tile grids).\n\n" +
              "\n".join(lines) + "\n")
    (out_dir("model_holdout") / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
