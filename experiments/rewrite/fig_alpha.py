"""F2: alpha(TM, TN) at gc = 0 (the calibration), as alpha vs TM, one line
per TN. Default setup (harness Params: 192x256x256, 16 KB fully associative
L1, no L2). Tiles no longer have to divide the matrix, so TM is dense.

Non-dividing tiles make the curves non-monotone: alpha is the row-weighted
mix of the full tiles and the clipped edge tile.
  - M=192, TM=112 is 112 + 80 rows, and the 80-row tile still fits in L1,
    so TN=32 drops (verified: the mix predicts 2.975, measured 2.98).
  - The small dips at TM = 20, 36, 60, 92 are the tilings whose edge tile
    has <= 12 rows (192 = 9*20+12, 5*36+12, 3*60+12, 2*92+8): an A tile
    that small fits in L1.

SMALL=True runs a quick sample first (TM in steps of 8).

run:  .venv/bin/python experiments/rewrite/fig_alpha.py
"""

from collections import defaultdict
from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import legend_above, plt, save, series

NAME = "fig_alpha"
SMALL = False
TM = [4] + list(range(8, 129, 8)) if SMALL else list(range(4, 129, 4))
TN = [4, 8, 16, 32, 64]
MNK = 192 * 256 * 256


def main() -> None:
    base = Params(gen_cost=0, l1_assoc=-1)
    params = [replace(base, tile_h=tm, tile_w=tn) for tn in TN for tm in TM]
    stats = run_many(params, out_dir(NAME) / "results.json")

    alpha = defaultdict(dict)
    for p, s in zip(params, stats):
        alpha[p.tile_w][p.tile_h] = s["Simulation: Total cycles"] / MNK

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, tn in enumerate(TN):
        xs = sorted(alpha[tn])
        ax.plot(xs, [alpha[tn][x] for x in xs], label=f"$T_N = {tn}$", **series(i))

    ax.set_xlabel("$T_M$")
    ax.set_ylabel(r"$\alpha$ (cycles / MAC)")
    ax.set_xlim(0, max(TM) + 4)
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=len(TN))
    print(save(fig, "alpha", NAME + ("_small" if SMALL else "")))


if __name__ == "__main__":
    main()
