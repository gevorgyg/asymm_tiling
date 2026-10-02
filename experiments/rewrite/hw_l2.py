"""H5a (hardware engineer): does an L2 help?

Best runtime over all tiles at every gc for
  no L2 / 32, 64, 128, 256, 512 KB fully associative / 64 KB 8-way L2
  (14 cycles),
with a 16 KB fully associative L1 (4 cycles), memory 180 cycles,
192x256x256 otherwise. The fully associative L2s keep the row-stride
conflicts (H4) out of the comparison; the 8-way one shows them.

  hw_l2:  best runtime vs gc, one line per L2.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_l2.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "hw_l2"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
L2 = {"no L2": (0, 3), "32 KB": (15, -1), "64 KB": (16, -1), "128 KB": (17, -1),
      "256 KB": (18, -1), "512 KB": (19, -1), "64 KB 8-way": (16, 3)}
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
    params = [replace(Params(l1_assoc=-1), l2_size=l2, l2_assoc=a, tile_h=tm, tile_w=tn,
                      gen_cost=gc)
              for l2, a in L2.values() for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.l2_size, p.l2_assoc, p.gen_cost, p.tile_h, p.tile_w):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
    best = {(c, gc): min((t[(*c, gc, *tl)], tl) for tl in tiles) for c in L2.values() for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, (label, c) in enumerate(L2.items()):
        ax.plot(GC, [best[(c, gc)][0] for gc in GC], label=label, **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime (cycles / MAC)")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=4)
    print(save(fig, "hardware/h5a_l2", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | " + " | ".join(L2) + " |", "|---" * (1 + len(L2)) + "|"]
    for gc in GC:
        lines.append(f"| {gc} | " + " | ".join(
            f"{best[(c, gc)][0]:.3f} {best[(c, gc)][1]} "
            f"({best[(c, gc)][0] / best[(L2['no L2'], gc)][0] - 1:+.0%} vs no L2)"
            for c in L2.values()) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: does an L2 help?\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(L2)} L2 configurations. "
              f"Cells: best runtime (tile).\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
