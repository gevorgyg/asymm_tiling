"""H5b (hardware engineer): does memory latency matter?

Best runtime over all tiles at every gc for memory latencies of 100, 180,
300 and 400 cycles, with a 16 KB fully associative L1 (4 cycles), no L2,
192x256x256 otherwise.

Finding: a slower memory makes the PRNG matter more. Generation forces taller
tiles, taller tiles miss more (A is re-read N/T_N times), and each miss costs
the memory latency: alpha = 0.75 + latency * misses/MAC + FIFO term.

  hw_memory:  best runtime vs gc, one line per memory latency.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_memory.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "hw_memory"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
MEM = [100, 180, 300, 400]
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [0, 5, 10, 20, 30, 50, 100, 200]
else:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
    GC = [0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(Params(l1_assoc=-1), mem_cycles=mem, tile_h=tm, tile_w=tn, gen_cost=gc)
              for mem in MEM for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.mem_cycles, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(mem, gc): min((t[(mem, gc, *tl)], tl) for tl in tiles) for mem in MEM for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, mem in enumerate(MEM):
        ax.plot(GC, [best[(mem, gc)][0] for gc in GC], label=f"{mem} cycles", **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime (cycles / MAC)")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=len(MEM))
    print(save(fig, "hardware/h5b_memory", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | " + " | ".join(f"{m} cycles" for m in MEM) + " |",
             "|---" * (1 + len(MEM)) + "|"]
    for gc in GC:
        lines.append(f"| {gc} | " + " | ".join(
            f"{best[(m, gc)][0]:.3f} {best[(m, gc)][1]} "
            f"({best[(m, gc)][0] / best[(m, 0)][0]:.2f}× its gc 0)" for m in MEM) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: does memory latency matter?\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(MEM)} latencies. "
              f"Cells: best runtime (tile).\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
