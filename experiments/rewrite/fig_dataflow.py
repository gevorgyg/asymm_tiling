"""F4: B-stationary vs C-stationary against gc, at the tile TM = 64,
TN = 32, default setup (16 KB fully associative L1, no L2).

  measured (solid + markers) and the model (thin dark dashed, on top; it
  coincides with the measurements) for both dataflows:
    B-stationary: max(alpha_B, gc * ceil(M/TM) / M)  (= gc/64 here)
    C-stationary: max(alpha_C, gc / R_M)              (B regenerated per
                                                       block of R_M = 4 rows)
  The FIFO startup term is negligible at this tile size.

C-stationary is faster only while gc / R_M < alpha_B, i.e. below the
crossover gc* = R_M * alpha_B (~4.6). B-stationary is not constant: it bends
upward at gc = TM * alpha_B (~73) with slope 1/64, 16x gentler than
C-stationary's 1/4. gc runs to 100 with the y-axis cut at 4 so both show.

SMALL=True runs a quick sample first (gc in steps of 2).

run:  .venv/bin/python experiments/rewrite/fig_dataflow.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "fig_dataflow"
SMALL = False
GC = list(range(0, 31, 2)) if SMALL else list(range(0, 101))
Y_MAX = 4   # C-stationary leaves the plot early; B-stationary bends at gc ~ 73
MODEL_LINES = False   # the user's choice: the report shows only the data here
TM, TN, M, R = 64, 32, 192, 4
MNK = 192 * 256 * 256
FLOWS = {"B-stationary": "weight", "C-stationary": "output"}

# best-vs-best (numbers for the text, not plotted): each dataflow at its own
# best tile over this grid
BEST_TM = [4] + list(range(8, 129, 8))
BEST_TN = [4, 8, 16, 32, 64]
BEST_GC = list(range(0, 31)) + list(range(35, 101, 5))


def main() -> None:
    base = Params(tile_h=TM, tile_w=TN, l1_assoc=-1)
    params = [replace(base, orientation=o, gen_cost=gc) for o in FLOWS.values() for gc in GC]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.orientation, p.gen_cost): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}

    alpha_b, alpha_c = t[("weight", 0)], t[("output", 0)]
    model = {
        "weight": lambda gc: max(alpha_b, gc * -(-M // TM) / M),
        "output": lambda gc: max(alpha_c, gc / R),
    }

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    dense = [g / 4 for g in range(0, 4 * GC[-1] + 1)]
    for i, (name, o) in enumerate(FLOWS.items()):
        ax.plot(GC, [t[(o, gc)] for gc in GC], label=name, markevery=5, **series(i))
    # the model coincides with the measurements; drawn only if MODEL_LINES (the
    # report's dataflow section comes before the model, so it shows data only)
    for j, o in enumerate(FLOWS.values() if MODEL_LINES else []):
        ax.plot(dense, [model[o](g) for g in dense], color=INK_2, linestyle="--",
                linewidth=1.0, zorder=5, label="model" if j == 0 else None)

    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("cycles / MAC")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(0, Y_MAX)
    legend_above(ax, ncols=3 if MODEL_LINES else 2)
    print(save(fig, "dataflow", NAME + ("_small" if SMALL else "")))

    cross = R * alpha_b
    print(f"alpha_B = {alpha_b:.3f}, alpha_C = {alpha_c:.3f}, model crossover gc* = R*alpha_B = {cross:.2f}")
    for gc in GC:
        b, c = t[("weight", gc)], t[("output", gc)]
        print(f"  gc={gc:>3}: B {b:.3f}  C {c:.3f}  -> " +
              (f"C {b / c:.2f}x faster" if c < b else f"B {c / b:.2f}x faster"))

    if not SMALL:
        best_vs_best()


def best_vs_best() -> None:
    base = Params(l1_assoc=-1)
    params = [replace(base, orientation=o, tile_h=tm, tile_w=tn, gen_cost=gc)
              for o in FLOWS.values() for gc in BEST_GC for tm in BEST_TM for tn in BEST_TN]
    stats = run_many(params, out_dir(NAME) / "results_best.json")
    best = {}
    for p, s in zip(params, stats):
        key = (p.orientation, p.gen_cost)
        cyc = s["Simulation: Total cycles"] / MNK
        if key not in best or cyc < best[key][0]:
            best[key] = (cyc, (p.tile_h, p.tile_w))

    # fig_dataflow_best: each dataflow at its own best tile, same axes as fig_dataflow
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, (name, o) in enumerate(FLOWS.items()):
        ax.plot(BEST_GC, [best[(o, gc)][0] for gc in BEST_GC], label=name + ", best tile",
                markevery=[j for j, gc in enumerate(BEST_GC) if gc % 10 == 0], **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("cycles / MAC")
    ax.set_xlim(0, BEST_GC[-1])
    ax.set_ylim(0, Y_MAX)
    legend_above(ax, ncols=2)
    print(save(fig, "dataflow", NAME + "_best"))

    lines = ["| gc | B-stationary best tile | C-stationary best tile | faster |",
             "|---|---|---|---|"]
    for gc in BEST_GC:
        (b, tb), (c, tc) = best[("weight", gc)], best[("output", gc)]
        faster = f"C {b / c:.2f}x" if c < b else f"B {c / b:.2f}x"
        lines.append(f"| {gc} | {tb}: {b:.3f} | {tc}: {c:.3f} | {faster} |")
    report = "# fig_dataflow: best tile of each dataflow vs gc\n\n" + "\n".join(lines) + "\n"
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
