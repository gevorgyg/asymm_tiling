"""S2 (software engineer): how much autotuning do I need?

A tuning strategy is a set of candidate tiles. Its cost is one calibration run
per candidate at gc = 0 (the alpha table). Its result is the tile the model
picks from those candidates at each gc, measured against the true best of all
1536 tiles of the fig_best_tile grid (192x256x256, default setup).
No new runs: everything comes from the fig_best_tile cache.

The model is the refined one (report 3.3.4): per row of tiles
max(r alpha(r), gc) plus the startup term, alpha read straight from the
candidates' table. If the short last row's height is not a candidate, the
candidate's own alpha is used for it (no extra runs).

  sw_autotune:  worst extra time over the true best (over all gc > 0) against
                the number of calibration runs, one marker per strategy.

run:  .venv/bin/python experiments/rewrite/sw_autotune.py
"""

import statistics
from dataclasses import replace

import fig_best_tile as fbt
from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "sw_autotune"
M, K, N, R = fbt.M, fbt.K, fbt.N, fbt.R
MNK = M * K * N
POW2 = [4, 8, 16, 32, 64, 128]
DIV = [t for t in fbt.TM if M % t == 0]


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


STRATEGIES = {
    "full grid (step 4)": [(m, n) for m in fbt.TM for n in fbt.TN],
    "step 8": [(m, n) for m in fbt.TM if m % 8 == 0 for n in fbt.TN if n % 8 == 0],
    "step 16": [(m, n) for m in fbt.TM if m % 16 == 0 for n in fbt.TN if n % 16 == 0],
    "heights dividing M": [(m, n) for m in DIV for n in fbt.TN],
    "heights dividing M, widths $2^k$": [(m, n) for m in DIV for n in POW2],
    "powers of two": [(m, n) for m in POW2 for n in POW2],
    "square tiles": [(s, s) for s in fbt.TN if s in fbt.TM],
    r"no tuning ($16 \times 32$)": [(16, 32)],
}


def main() -> None:
    params = [replace(Params(l1_assoc=-1), tile_h=tm, tile_w=tn, gen_cost=gc)
              for gc in fbt.GC for tm in fbt.TM for tn in fbt.TN]
    stats = run_many(params, out_dir(fbt.NAME) / "results.json")
    t = {(p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    gcs = [gc for gc in fbt.GC if gc > 0]
    true_best = {gc: min(t[(gc, m, n)] for m in fbt.TM for n in fbt.TN) for gc in gcs}

    def predict(cands: set, tile: tuple, gc: int) -> float:
        tm, tn = tile
        alpha = lambda r: t[(0, r, tn)] if (r, tn) in cands else t[(0, tm, tn)]
        full, e = divmod(M, tm)
        rows = [tm] * full + ([e] if e else [])
        startup = gc * R * R * cdiv(M, tm) * cdiv(N, tn) / MNK
        return sum(max(r * alpha(r), gc) for r in rows) / M + startup

    results = {}
    for name, cands in STRATEGIES.items():
        cset = set(cands)
        loss = []
        for gc in gcs:
            pick = min(cands, key=lambda x: (predict(cset, x, gc), t[(0, *x)]))
            loss.append(t[(gc, *pick)] / true_best[gc] - 1)
        runs = 0 if name.startswith("no tuning") else len(cands)
        results[name] = (runs, max(loss), statistics.median(loss),
                         sum(l <= 0.01 for l in loss) / len(loss))

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, (name, (runs, worst, _, _)) in enumerate(results.items()):
        ax.plot([max(runs, 1)], [100 * worst], linestyle="none", markersize=9, label=name,
                **series(i))
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_ylim(0.8, 1000)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g} %"))
    ax.set_xlabel("calibration runs ($g_c = 0$, one per candidate tile)")
    ax.set_ylabel("worst extra time over the best tile")
    legend_above(ax, ncols=3)
    print(save(fig, "software/s2_autotune", NAME))

    lines = ["| strategy | calibration runs | worst extra time | median | gc within 1 % |",
             "|---|---|---|---|---|"]
    for name, (runs, worst, med, w1) in results.items():
        lines.append(f"| {name} | {runs} | {worst:.1%} | {med:.2%} | {w1:.0%} |")
    report = (f"# {NAME}: how much autotuning?\n\nOver {len(gcs)} values of gc > 0 "
              f"(fig_best_tile grid). Extra time = picked tile vs the best of all 1536 "
              f"tiles.\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
