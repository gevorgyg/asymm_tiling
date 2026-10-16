"""S7a: rows of C that do not start on a cache line move the thrashing cliff
(report: Can One Calibration Serve Many Matrices?).

alpha (gc = 0) against T_M at T_N = 16 for 200 x 200 x N, N = 288, 300, 304.
288 and 304 are whole 64-byte lines (multiples of 16 elements), 300 is not.
In all three, C itself starts on a line (0x1000 + 4MK + 4KN is a multiple of
64), so only the row length differs. Default setup otherwise (16 KB fully
associative L1, no L2, B-stationary, R = 4).

run:  .venv/bin/python experiments/rewrite/sw_alignment.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "sw_alignment"
M, K, TN = 200, 200, 16
NS = [288, 300, 304]
TM = list(range(4, 193, 4))


def main() -> None:
    params = [replace(Params(l1_assoc=-1), m=M, k=K, n=n, tile_h=tm, tile_w=TN, gen_cost=0)
              for n in NS for tm in TM]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.n, p.tile_h): s["Simulation: Total cycles"] / (p.m * p.k * p.n)
         for p, s in zip(params, stats)}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, n in enumerate(NS):
        lines = n * 4 / 64
        style = series(i)
        if n == NS[-1]:   # identical to N = 288: drawn dashed on top so both stay visible
            style |= {"linestyle": "--", "zorder": 5}
        ax.plot(TM, [t[(n, tm)] for tm in TM], markevery=4,
                label=f"$N = {n}$ ({lines:g} lines per row)", **style)
    ax.set_xlabel("$T_M$")
    ax.set_ylabel(r"$\alpha$ (cycles / MAC)")
    ax.set_xlim(0, TM[-1] + 4)
    ax.set_ylim(0, 6)   # all three thrash completely from T_M = 132 on (alpha 16-22)
    legend_above(ax, ncols=len(NS))
    print(save(fig, "software/s7_templates", "sw_alignment"))
    for n in NS:
        cliff = next((tm for tm in TM if tm > 16 and t[(n, tm)] > 2), None)
        print(f"N = {n}: alpha first above 2 at T_M = {cliff}")


if __name__ == "__main__":
    main()
