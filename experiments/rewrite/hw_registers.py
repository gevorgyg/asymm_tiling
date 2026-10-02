"""H6 (hardware engineer): how many registers should the core have?

The register block is R x R: the B-stationary core holds an R x R block of A,
B and C, about 3 R^2 elements of registers (R = 2: 12, 4: 48, 8: 192,
16: 768). Best runtime over all tiles at every gc, for R = 2, 4, 8, 16, with
an unlimited FIFO (16384 elements, isolates the registers) and a 1 KB FIFO
(256 elements, the realistic size from H3). 16 KB fully associative L1, no
L2, 192x256x256 otherwise. MAC cost 0: the runtime is data movement only.

  hw_registers:  best runtime vs gc, one color per R; solid = unlimited
                 FIFO, dashed = 256 elements.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_registers.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import SERIES, legend_above, plt, save

NAME = "hw_registers"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
R = [2, 4, 8, 16]
FIFO = {"unlimited FIFO": 16384, "1 KB FIFO": 256}
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
    params = [replace(Params(l1_assoc=-1), reg_dim=r, fifo_capacity=cap, tile_h=tm,
                      tile_w=tn, gen_cost=gc)
              for r in R for cap in FIFO.values() for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.reg_dim, p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
    best = {(r, cap, gc): min((t[(r, cap, gc, *tl)], tl) for tl in tiles)
            for r in R for cap in FIFO.values() for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, r in enumerate(R):
        for fifo, cap in FIFO.items():
            unlimited = cap == FIFO["unlimited FIFO"]
            ax.plot(GC, [best[(r, cap, gc)][0] for gc in GC], color=SERIES[i],
                    linestyle="-" if unlimited else "--", linewidth=2.0 if unlimited else 1.2,
                    marker="osD^"[i] if unlimited else None, markeredgecolor="white",
                    markeredgewidth=0.8, label=f"$R = {r}$" if unlimited else None)
    ax.plot([], [], color="0.4", linestyle="--", linewidth=1.2, label="1 KB FIFO")
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime (cycles / MAC)")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=len(R) + 1)
    print(save(fig, "hardware/h6_registers", NAME + ("_small" if SMALL else "")))

    lines = []
    for fifo, cap in FIFO.items():
        lines += [f"## {fifo} ({cap} elements)", "",
                  "| gc | " + " | ".join(f"R = {r} (~{3 * r * r} regs)" for r in R) + " |",
                  "|---" * (1 + len(R)) + "|"]
        for gc in GC:
            lines.append(f"| {gc} | " + " | ".join(
                f"{best[(r, cap, gc)][0]:.3f} {best[(r, cap, gc)][1]}" for r in R) + " |")
        lines.append("")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: register block size\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(R)} R × {len(FIFO)} FIFO sizes. "
              f"Cells: best runtime (tile).\n\n" + "\n".join(lines))
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
