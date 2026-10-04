"""H3b (hardware engineer): with a fixed on-chip budget, a bigger cache or a
bigger FIFO?

The L1 and the FIFO share a budget of 16 KB or 32 KB. The FIFO gets
64 B (one 4x4 register block of 4-byte elements) up to 8 KB, the L1 the rest
(fully associative, so any size works). For each split and gc, the best
runtime over all tiles; 192x256x256, no L2, default setup otherwise.

  hw_sram_split:  best runtime vs FIFO share of the budget, one line per gc,
                  one panel per budget.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_sram_split.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "hw_sram_split"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
ELEM = 4                                   # bytes per element of B
BUDGET = {"16 KB": 16 * 1024, "32 KB": 32 * 1024}
_KB = 1024
# FIFO shares per budget, up to almost all of it: the L1 keeps at least 512 B
# (with no L2 the simulator needs a cache level)
FIFO_BYTES = {
    16 * _KB: [64, 256, _KB, 2 * _KB, 4 * _KB, 8 * _KB, 12 * _KB, 14 * _KB, 15 * _KB,
               15 * _KB + 512],
    32 * _KB: [64, 256, _KB, 2 * _KB, 4 * _KB, 8 * _KB, 16 * _KB, 24 * _KB, 28 * _KB,
               30 * _KB, 31 * _KB, 31 * _KB + 512],
}
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [5, 10, 20, 30, 60, 100, 200]
else:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
    GC = [2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    splits = [(b, f) for b in BUDGET.values() for f in FIFO_BYTES[b]]
    params = [replace(Params(l1_assoc=-1), l1_size=b - f, fifo_capacity=f // ELEM,
                      tile_h=tm, tile_w=tn, gen_cost=gc)
              for b, f in splits for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.l1_size, p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
    best = {(b, f, gc): min((t[(b - f, f // ELEM, gc, *tl)], tl) for tl in tiles)
            for b, f in splits for gc in GC}

    fig, axes = plt.subplots(1, len(BUDGET), figsize=(7.0, 3.6), sharey=True)
    for ax, (name, b) in zip(axes, BUDGET.items()):
        # x = FIFO share of the budget on a logit scale, which stretches both
        # ends (FIFO too small, cache too small); y on a log scale (up to 23)
        share = [f / b for f in FIFO_BYTES[b]]
        for i, gc in enumerate(GC):
            ax.plot(share, [best[(b, f, gc)][0] for f in FIFO_BYTES[b]],
                    label=f"$g_c = {gc}$", **series(i))
        ax.set_xscale("logit")
        ax.set_xticks([0.01, 0.1, 0.5, 0.9, 0.99])
        ax.xaxis.set_minor_formatter(plt.NullFormatter())
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{100 * v:g} %"))
        ax.set_xlim(0.0015, 0.995)
        ax.set_xlabel(f"FIFO share of a {name} budget")
        ax.set_yscale("log")
        ax.set_yticks([1, 2, 5, 10, 20])
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    axes[0].set_ylabel("best runtime (cycles / MAC)")
    legend_above(axes[0], ncols=len(GC))
    print(save(fig, "hardware/h3_fifo_size", NAME + ("_small" if SMALL else "")))

    lines = []
    for name, b in BUDGET.items():
        lines += [f"## {name} budget", "",
                  "| gc | " + " | ".join(f"FIFO {f} B / L1 {(b - f) / 1024:g} KB"
                                        for f in FIFO_BYTES[b]) + " | best split |",
                  "|---" * (2 + len(FIFO_BYTES[b])) + "|"]
        for gc in GC:
            row = [best[(b, f, gc)] for f in FIFO_BYTES[b]]
            winner = FIFO_BYTES[b][min(range(len(row)), key=lambda j: row[j][0])]
            lines.append(f"| {gc} | " + " | ".join(f"{v:.3f} {tl}" for v, tl in row) +
                         f" | FIFO {winner} B |")
        lines.append("")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: L1 vs FIFO in a fixed budget\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(splits)} splits. "
              f"Cells: best runtime (tile).\n\n" + "\n".join(lines))
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
