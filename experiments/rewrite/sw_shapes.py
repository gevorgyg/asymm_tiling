"""S3 (software engineer): my matrices aren't 192x256x256. How does the best
tile change with the shape?

One dimension at a time is varied around 192x256x256, the others stay:
  K in {128, 256, 512, 1024}, M in {96, 192, 384, 768}, N in {128, 256, 512, 1024}.
For each shape and gc, the best tile over the grid (default setup otherwise:
16 KB fully associative L1, no L2, B-stationary).

Expectations from the alpha mechanism (report 3.3.2):
  - K: the A tile is TM x K elements, so a larger K stops it fitting in L1 at
    a smaller TM -> the first cliff and the best tiles move;
  - M: through the generation staircase ceil(M / TM);
  - N: hardly (only TN <= N and a small 1/(16N) term).

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/sw_shapes.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import SERIES, legend_above, plt, save

NAME = "sw_shapes"
SMALL = True
BASE = (192, 256, 256)       # M, K, N
VARY = {"K": [128, 256, 512, 1024], "M": [96, 192, 384, 768], "N": [128, 256, 512, 1024]}
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 384]
    TN = [4, 8, 16, 32, 64, 128, 256, 512]
    GC = [0, 5, 10, 20, 30, 50, 100, 200]
else:
    TM = [4] + list(range(8, 385, 8))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512]
    GC = [0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]


def shapes() -> list[tuple[int, int, int]]:
    out = []
    for dim, values in VARY.items():
        for v in values:
            m, k, n = BASE
            shape = {"M": (v, k, n), "K": (m, v, n), "N": (m, k, v)}[dim]
            if shape not in out:
                out.append(shape)
    return out


def main() -> None:
    params = [replace(Params(l1_assoc=-1), m=m, k=k, n=n, tile_h=tm, tile_w=tn, gen_cost=gc)
              for m, k, n in shapes() for gc in GC for tm in TM for tn in TN
              if tm <= m and tn <= n]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    best = {}
    for p, s in zip(params, stats):
        key = ((p.m, p.k, p.n), p.gen_cost)
        v = s["Simulation: Total cycles"] / (p.m * p.k * p.n)
        if key not in best or v < best[key][0]:
            best[key] = (v, (p.tile_h, p.tile_w))

    # figure: best TM and TN against gc, one line per K (they overlap)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.6), sharey=True)
    styles = ["-", "--", "-.", ":"]
    for ax, i, label in ((axes[0], 0, "$T_M^*$"), (axes[1], 1, "$T_N^*$")):
        for j, k in enumerate(VARY["K"]):
            shape = (BASE[0], k, BASE[2])
            xs = GC + [GC[-1] * 1.25]
            ys = [best[(shape, gc)][1][i] for gc in GC] + [best[(shape, GC[-1])][1][i]]
            ax.plot(xs, ys, drawstyle="steps-post", linestyle=styles[j],
                    linewidth=2.4 - 0.4 * j, label=f"$K = {k}$",
                    marker="osD^"[j], markevery=list(range(len(GC))),
                    color=SERIES[j], markeredgecolor="white", markeredgewidth=0.8)
        ax.set_xscale("symlog", linthresh=10, linscale=0.5)
        ax.set_xticks([0, 10, 30, 100, 200])
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlim(0, GC[-1])
        ax.set_yscale("log", base=2)
        ax.set_yticks([8, 12, 16, 24, 32, 48, 64, 96, 128, 256])
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel(f"$g_c$ (cycles / element), best {label}")
    axes[0].set_ylabel("tile dimension")
    legend_above(axes[0], ncols=len(VARY["K"]))
    print(save(fig, "software/s3_shapes", NAME + "_K" + ("_small" if SMALL else "")))

    lines = []
    for dim, values in VARY.items():
        lines += [f"## Varying {dim}", "", "| gc | " + " | ".join(
            str({"M": (v, BASE[1], BASE[2]), "K": (BASE[0], v, BASE[2]),
                 "N": (BASE[0], BASE[1], v)}[dim]) for v in values) + " |",
                  "|---" * (1 + len(values)) + "|"]
        for gc in GC:
            cells = []
            for v in values:
                shape = {"M": (v, BASE[1], BASE[2]), "K": (BASE[0], v, BASE[2]),
                         "N": (BASE[0], BASE[1], v)}[dim]
                t, tile = best[(shape, gc)]
                cells.append(f"{tile[0]}×{tile[1]}: {t:.3f}")
            lines.append(f"| {gc} | " + " | ".join(cells) + " |")
        lines.append("")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: best tile per matrix shape\n\n"
              f"Cells: best tile and its runtime (cycles / MAC).\n\n" + "\n".join(lines))
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
