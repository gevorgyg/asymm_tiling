"""H7 (hardware engineer): does the MAC cost change the conclusions?

mulacc() charges mulacc_cost cycles once per register-block multiply (R^3
MACs; src/multi_unit.cpp), in series with the core's loads and stores while
the PRNG keeps generating in the background. Per MAC that is c / R^3 = c / 64
at R = 4.

  c = 0, 4, 16, 64 cycles per 4x4x4 block = 0, 1/16, 1/4, 1 cycle per MAC
  (memory only, ~16-wide vector unit, ~4-wide SIMD, scalar 1 MAC/cycle).

Best runtime over all tiles at every gc; 16 KB fully associative L1, no L2,
unlimited FIFO, 192x256x256 otherwise.

  hw_mac_cost:  slowdown vs free generation (own gc = 0) vs gc, one line per c.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_mac_cost.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "hw_mac_cost"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
MAC = [0, 4, 16, 64]
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
    params = [replace(Params(l1_assoc=-1), mulacc_cost=c, tile_h=tm, tile_w=tn, gen_cost=gc)
              for c in MAC for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.mulacc_cost, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(c, gc): min((t[(c, gc, *tl)], tl) for tl in tiles) for c in MAC for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.axhline(1.05, color=INK_2, linewidth=0.8, linestyle=":", zorder=1)
    for i, c in enumerate(MAC):
        ax.plot(GC, [best[(c, gc)][0] / best[(c, 0)][0] for gc in GC],
                label=f"{c / 64:g} cycles / MAC", **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("slowdown vs free generation")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_xlim(0, GC[-1])
    legend_above(ax, ncols=len(MAC))
    print(save(fig, "hardware/h7_mac_cost", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | " + " | ".join(f"c = {c} ({c / 64:g}/MAC)" for c in MAC) + " |",
             "|---" * (1 + len(MAC)) + "|"]
    for gc in GC:
        lines.append(f"| {gc} | " + " | ".join(
            f"{best[(c, gc)][0]:.3f} {best[(c, gc)][1]} ({best[(c, gc)][0] / best[(c, 0)][0]:.2f}×)"
            for c in MAC) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: MAC cost\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(MAC)} MAC costs (cycles per 4×4×4 "
              f"block). Cells: best runtime (tile) (slowdown vs its gc 0).\n\n" +
              "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
