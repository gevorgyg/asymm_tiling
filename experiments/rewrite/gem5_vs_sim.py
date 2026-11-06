"""Does our simulator choose the same tiles as gem5? (report: gem5 Simulation)

Runs asymm_tiling on the gem5 setup (192 x 128 x 512, A and C fp32, B int8,
32 KB L1, 64 KB L2, gem5's latencies, 8 x 8 register blocks, 2 KB FIFO) for
the 35 gem5 tiles and the g_c of the gem5 slow-generator sweep. Caches are
fully associative, matching the padded gem5 runs, which have no conflicts.

For every g_c it compares the tile each one ranks best, the rank correlation
over all 35 tiles, and the loss in gem5 of taking the simulator's tile
instead of gem5's own best.

run:  python3 experiments/rewrite/gem5_vs_sim.py   (after gem5_figs.py data)
"""

import csv
from dataclasses import replace
from pathlib import Path

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "gem5_vs_sim"
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2] / "gem5" / "asymm" / "exp"
M, K, N = 192, 128, 512
TM = [8, 16, 32, 48, 64, 96, 192]
TN = [8, 16, 32, 64, 128]

# Latencies as gem5 reports them: L1 and L2 hit 2 and 6 cycles (the
# config), and an L2 miss 66 cycles on average (overallAvgMissLatency of the
# runs), so 60 cycles beyond the L2.
BASE = Params(m=M, k=K, n=N, small_precision=1, ratio=4, reg_dim=8,
              l1_size=15, l1_assoc=-1, l1_cycles=2,
              l2_size=16, l2_assoc=-1, l2_cycles=6, mem_cycles=60,
              fifo_capacity=2048, fifo_access=1)


def gem5_rows():
    rows = []
    for name in ("tiles", "gencost"):
        p = EXP / name / "results.csv"
        if p.exists():
            rows += list(csv.DictReader(open(p)))
    return rows


def gem5_cpm(rows, mode, g):
    """(tm, tn) -> cycles per MAC, padding and prefetcher on."""
    out = {}
    for r in rows:
        if (int(r["mode"]) == mode and int(r["pad"]) == 16
                and int(r["prefetch"]) == 1
                and int(float(r["gen_cost"])) == g):
            out[(int(r["tm"]), int(r["tn"]))] = float(r["cycles_per_mac"])
    return out


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0] * len(v)
    for pos, i in enumerate(order):
        r[i] = pos
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return 1 - 6 * d2 / (n * (n * n - 1))


def main():
    rows = gem5_rows()
    gcs = sorted({int(float(r["gen_cost"])) for r in rows
                  if int(r["mode"]) == 2})
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(BASE, tile_h=tm, tile_w=tn, gen_cost=g)
              for g in gcs for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / "results.json")
    sim = {(p.gen_cost, p.tile_h, p.tile_w):
           s["Simulation: Total cycles"] / (M * K * N)
           for p, s in zip(params, stats)}

    lines = ["| $g_c$ | gem5 best | simulator best | loss in gem5 | "
             "rank correlation |", "|---|---|---|---|---|"]
    loss = []
    for g in gcs:
        g5 = gem5_cpm(rows, 2, g)
        common = [t for t in tiles if t in g5]
        a = [g5[t] for t in common]
        b = [sim[(g,) + t] for t in common]
        g5_best = min(common, key=lambda t: g5[t])
        sim_best = min(common, key=lambda t: sim[(g,) + t])
        lo = g5[sim_best] / g5[g5_best] - 1
        loss.append(100 * lo)
        lines.append("| %d | %d x %d | %d x %d | %.1f%% | %.2f |" % (
            g, *g5_best, *sim_best, 100 * lo, spearman(a, b)))
    table = "\n".join(lines)
    (out_dir(NAME) / "README.md").write_text(
        "# gem5 against our simulator\n\n" + table + "\n")
    print(table)

    fig, axs = plt.subplots(1, 2, figsize=(8, 3.4))
    for i, g in enumerate([gcs[0], gcs[-1]]):
        g5 = gem5_cpm(rows, 2, g)
        common = [t for t in tiles if t in g5]
        axs[i].scatter([sim[(g,) + t] for t in common],
                       [g5[t] for t in common], s=18,
                       color=series(i)["color"],
                       label="$g_c = %d$, one point per tile" % g)
        axs[i].set_xscale("log")
        axs[i].set_yscale("log")
        axs[i].set_xlabel("our simulator (cycles per MAC)")
        legend_above(axs[i], 1)
    axs[0].set_ylabel("gem5 (cycles per MAC)")
    fig.tight_layout()
    png = save(fig, "gem5", "gem5_vs_sim")
    print("wrote", png)


if __name__ == "__main__":
    main()
