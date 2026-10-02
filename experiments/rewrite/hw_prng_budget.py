"""H1 (hardware engineer): how fast must the PRNG be?

For each L1 size, the best tile at every gc (B-stationary, default setup
otherwise: 192x256x256, fully associative L1, no L2). The slowdown
T*(gc) / T*(0) says how much a generator of cost gc costs compared with free
generation. The budget is the largest gc with a slowdown <= 5 % (10 %).
A generator of cost gc delivers 1/gc elements per cycle, so k generators in
parallel behave like one of cost gc / k.

  hw_prng_budget:  slowdown vs gc, one line per L1 size.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_prng_budget.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "hw_prng_budget"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
L1 = {"8 KB": 13, "16 KB": 14, "32 KB": 15, "64 KB": 16}
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100]
else:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96, 128, 160, 192, 256]
    GC = list(range(0, 41)) + list(range(45, 101, 5))
LIMITS = [0.05, 0.10]


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(Params(l1_assoc=-1), l1_size=l1, tile_h=tm, tile_w=tn, gen_cost=gc)
              for l1 in L1.values() for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.l1_size, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    best = {(l1, gc): min((t[(l1, gc, *tl)], tl) for tl in tiles)
            for l1 in L1.values() for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for lim in LIMITS:
        ax.axhline(1 + lim, color=INK_2, linewidth=0.8, linestyle=":", zorder=1)
    for i, (name, l1) in enumerate(L1.items()):
        ax.plot(GC, [best[(l1, gc)][0] / best[(l1, 0)][0] for gc in GC], label=name,
                markevery=1 if SMALL else 5, **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("slowdown vs free generation")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(0.95, 2.0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}×"))
    legend_above(ax, ncols=len(L1))
    print(save(fig, "hardware/h1_prng_speed", NAME + ("_small" if SMALL else "")))

    lines = ["| L1 | T*(0) | best tile at gc 0 | " +
             " | ".join(f"budget {lim:.0%}: gc, tile" for lim in LIMITS) + " |",
             "|---" * (3 + len(LIMITS)) + "|"]
    for name, l1 in L1.items():
        t0, tile0 = best[(l1, 0)]
        cells = []
        for lim in LIMITS:
            ok = [gc for gc in GC if best[(l1, gc)][0] <= t0 * (1 + lim)]
            # the slowdown is monotone in gc, so the budget is the last gc that is within
            g = max(ok)
            cells.append(f"{g}, {best[(l1, g)][1]}")
        lines.append(f"| {name} | {t0:.3f} | {tile0} | " + " | ".join(cells) + " |")
    lines += ["", "## Slowdown per gc", "",
              "| gc | " + " | ".join(L1) + " |", "|---" * (1 + len(L1)) + "|"]
    for gc in GC:
        lines.append(f"| {gc} | " + " | ".join(
            f"{best[(l1, gc)][0] / best[(l1, 0)][0]:.3f} {best[(l1, gc)][1]}"
            for l1 in L1.values()) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: PRNG cost budget per L1 size\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(L1)} L1 sizes.\n\n" +
              "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
