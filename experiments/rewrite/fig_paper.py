"""F1: reproducing the original analysis (report: Reproducing The Original
Paper). B is a stored matrix in a lower precision (no PRNG): A and C 8 bytes
per element, B 8 / 4 / 2 / 1 bytes, so rho = 1, 1/2, 1/4, 1/8.

The theory counts words moved into fast memory, per MAC 1/T_N for A and
rho/T_M for B, so at a fixed C-tile area T_M T_N the traffic is minimal at the
aspect ratio T_N / T_M = 1 / rho: the tile stretches along the cheap matrix.

Measured: L1 read traffic = L1 misses x 64 bytes, for C tiles of a fixed area
and aspect ratios T_N / T_M from 1/64 to 64. 256x256x256, B-stationary, B from
memory, 16 KB fully associative L1, no L2 (an L2 does not change L1 traffic).

  fig_paper:  L1 read traffic relative to the square tile against T_N / T_M,
              one line per rho, one panel per C-tile area; the predicted
              optimum 1/rho is where the theory curve (dashed) is lowest.

run:  .venv/bin/python experiments/rewrite/fig_paper.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "fig_paper"
M = K = N = 256
LINE = 64
A_BYTES = 8
B_BYTES = [8, 4, 2, 1]                  # rho = B_BYTES / A_BYTES
AREAS = [512, 1024]                     # C-tile area T_M * T_N (elements)
SQUARE = {512: None, 1024: 32}          # 512 has no square power-of-two tile


def tiles(area: int) -> list[tuple[int, int]]:
    out, tm = [], 256
    while tm >= 4:
        tn = area // tm
        if 4 <= tn <= 256 and tm * tn == area:
            out.append((tm, tn))
        tm //= 2
    return out


def main() -> None:
    params = [replace(Params(l1_assoc=-1), m=M, k=K, n=N, b_source="memory",
                      small_precision=b, ratio=A_BYTES // b, tile_h=tm, tile_w=tn)
              for b in B_BYTES for area in AREAS for tm, tn in tiles(area)]
    stats = run_many(params, out_dir(NAME) / "results.json")
    reads = {(p.small_precision, p.tile_h, p.tile_w): s["CacheUnit: L1 misses"] * LINE
             for p, s in zip(params, stats)}

    fig, axes = plt.subplots(1, len(AREAS), figsize=(7.0, 3.6), sharey=True)
    lines = []
    for ax, area in zip(axes, AREAS):
        ts = tiles(area)
        ratio = [tn / tm for tm, tn in ts]
        for i, b in enumerate(B_BYTES):
            rho = b / A_BYTES
            # normalise by the best tile of the line, so every line has its minimum at 1
            best = min(reads[(b, tm, tn)] for tm, tn in ts)
            ax.plot(ratio, [reads[(b, tm, tn)] / best for tm, tn in ts],
                    label=f"$rho = {rho:g}$".replace("rho", r"\rho"), **series(i))
            theory = [1 / tn + rho / tm for tm, tn in ts]
            ax.plot(ratio, [q / min(theory) for q in theory], color=series(i)["color"],
                    linestyle="--", linewidth=1.0)
            arg = min(ts, key=lambda x: reads[(b, *x)])
            sq = (32, 32) if area == 1024 else None
            lines.append(f"| {area} | {rho:g} | {arg[1] / arg[0]:g} | {1 / rho:g} | " +
                         (f"{1 - best / reads[(b, *sq)]:.1%}" if sq else "–") + " |")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log", base=2)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(
            lambda v, _: f"{v:g}" if v >= 1 else f"1/{1 / v:g}"))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_ylim(0.9, 8)
        ax.set_xlabel(f"aspect ratio $T_N / T_M$ ($T_M T_N = {area}$)")
    axes[0].set_ylabel("L1 read traffic / minimum")
    axes[0].plot([], [], color=INK_2, linestyle="--", linewidth=1.0, label="theory")
    legend_above(axes[0], ncols=5)
    print(save(fig, "paper", NAME))

    report = ("# fig_paper: traffic minimum vs aspect ratio\n\n"
              "| area | rho | measured best T_N/T_M | predicted 1/rho | saving vs 32×32 |\n"
              "|---|---|---|---|---|\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
