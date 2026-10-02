"""H3 (hardware engineer): how big does the FIFO need to be?

The generator runs ahead of the core only until the FIFO is full; then it
pauses (src/prngfifo.cpp). A bigger FIFO lets it bank elements while the core
is slowed by cache misses. Every tile restarts with an empty FIFO.

For each gc and FIFO capacity (elements of B, 4 bytes each), the best runtime
over all tiles, divided by the best runtime with the default 16384-element
FIFO (which never fills). The answer is the smallest capacity within 1 %.
Default setup otherwise (16 KB fully associative L1, no L2, 192x256x256).

  hw_fifo_size:  slowdown vs FIFO capacity (log2 axis), one line per gc.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_fifo_size.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "hw_fifo_size"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
CAP = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 16384]
REF = 16384
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [5, 10, 20, 30, 40, 60, 100, 200]
else:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
    GC = [2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]
LIMIT = 0.01


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(Params(l1_assoc=-1), fifo_capacity=cap, tile_h=tm, tile_w=tn,
                      gen_cost=gc)
              for cap in CAP for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(cap, gc): min((t[(cap, gc, *tl)], tl) for tl in tiles) for cap in CAP for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.axhline(1 + LIMIT, color=INK_2, linewidth=0.8, linestyle=":", zorder=1)
    for i, gc in enumerate(GC):
        ax.plot(CAP, [best[(cap, gc)][0] / best[(REF, gc)][0] for cap in CAP],
                label=f"$g_c = {gc}$", **series(i))
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_xlabel("FIFO capacity (elements of $B$)")
    ax.set_ylabel("slowdown vs an unlimited FIFO")
    legend_above(ax, ncols=4)
    print(save(fig, "hardware/h3_fifo_size", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | best at 16384 | smallest capacity within 1 % | " +
             " | ".join(str(c) for c in CAP) + " |", "|---" * (3 + len(CAP)) + "|"]
    for gc in GC:
        ref, ref_tile = best[(REF, gc)]
        enough = min(c for c in CAP if all(best[(d, gc)][0] <= ref * (1 + LIMIT)
                                           for d in CAP if d >= c))
        lines.append(f"| {gc} | {ref:.3f} {ref_tile} | {enough} | " + " | ".join(
            f"{best[(c, gc)][0] / ref:.3f} {best[(c, gc)][1]}" for c in CAP) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: FIFO capacity needed\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(CAP)} capacities. Cells: best "
              f"runtime / best at {REF}, and the best tile.\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
