"""H4 (hardware engineer): is a fully associative cache (or a scratchpad)
worth it over an 8- or 4-way cache?

Part 1 (no new runs): the model_sweep / assoc_sweep grid (3 L1 sizes x 6
matrices x 12 gc, fully associative / 8-way / 4-way). Per case, the best
runtime on each cache with the tile re-chosen for that cache.
Result: free on non-power-of-two shapes, 3-7x slower on power-of-two shapes
once gc >= 10.

Part 2: why, and the fix. With a power-of-two row stride (256 elements x 4 B =
1 KB = 16 lines) consecutive rows map to the same few sets: at 16 KB only 16
lines (2 sets x 8 ways, or 4 sets x 4 ways) can hold one column of a tile,
so tiles taller than ~12-16 rows thrash and generation cannot be amortized.
Padding the row to an odd number of lines spreads the rows over all sets.
The simulator has no leading-dimension parameter, so padding is emulated by
enlarging K and N: 192x256x256 (unpadded), 192x260x260 (16.25 lines, a
poor pad), 192x272x272 (17 lines, an odd pad).

  hw_assoc:  extra time of the best set-associative tile over the best fully
             associative tile vs gc, for 192 x K x N: 8-way / 4-way, unpadded
             (K = N = 256, solid) and padded (272, dashed).

run:  .venv/bin/python experiments/rewrite/hw_assoc.py
"""

import statistics
from dataclasses import replace

import model_sweep as ms
from harness import Params, out_dir, run_many
from plot_style import INK_2, SERIES, legend_above, plt, save, series

NAME = "hw_assoc"
ASSOC = {"fully assoc": -1, "4-way": 2, "8-way": 3, "16-way": 4, "32-way": 5}
SWEEP_ASSOC = {"8-way": 3, "4-way": 2}    # what the 6-matrix sweep (part 1) has
TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
GC = [0, 2, 5, 10, 15, 20, 30, 50, 75, 100, 200]
PAD = {256: "unpadded (256)", 260: "padded to 260 (16.25 lines)", 272: "padded to 272 (17 lines)"}


def sweep_part() -> list[str]:
    base = [replace(p, gen_cost=gc) for gc in [0] + ms.GC for _, _, p in ms.configs()]
    t = {}
    for a, cache in ((-1, out_dir("model_sweep") / "results.json"),
                     (3, out_dir("assoc_sweep") / "results_8-way.json"),
                     (2, out_dir("assoc_sweep") / "results_4-way.json")):
        params = [replace(p, l1_assoc=a) for p in base]
        for p, s in zip(params, run_many(params, cache)):
            key = (a, p.l1_size, (p.m, p.k, p.n), p.gen_cost)
            v = s["Simulation: Total cycles"] / (p.m * p.k * p.n)
            t[key] = min(t.get(key, v), v)
    cases = sorted({k[1:] for k in t})
    lines = ["## Part 1: the 3 L1 x 6 matrices x 12 gc grid", "",
             "Extra time of the best tile on the set-associative cache over the best "
             "tile on the fully associative one.", "",
             "| cache | matrix | median | max |", "|---|---|---|---|"]
    for name, a in SWEEP_ASSOC.items():
        for shape in ms.MATRICES:
            r = [t[(a, *c)] / t[(-1, *c)] - 1 for c in cases if c[1] == shape]
            lines.append(f"| {name} | {shape} | {statistics.median(r):.1%} | {max(r):.1%} |")
    return lines


def main() -> None:
    lines = sweep_part()

    best = {}
    for k in PAD:
        tn_list = [4, 8, 16, 32, 64, 128, k]
        params = [replace(Params(), k=k, n=k, l1_assoc=a, tile_h=tm, tile_w=tn, gen_cost=gc)
                  for a in ASSOC.values() for gc in GC for tm in TM for tn in tn_list]
        stats = run_many(params, out_dir(NAME) / "results.json")
        for p, s in zip(params, stats):
            key = (k, p.l1_assoc, p.gen_cost)
            v = s["Simulation: Total cycles"] / (p.m * p.k * p.n)
            if key not in best or v < best[key][0]:
                best[key] = (v, (p.tile_h, p.tile_w))

    def extra(k: int, a: int) -> list:
        return [best[(k, a, gc)][0] / best[(k, -1, gc)][0] - 1 for gc in GC]

    def finish(ax, name: str, ncols: int) -> None:
        ax.axhline(0, color=INK_2, linewidth=0.8, zorder=1)
        ax.set_yscale("symlog", linthresh=0.1, linscale=0.5)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{100 * v:g} %"))
        ax.set_ylim(-0.02, 8)
        ax.set_xlabel("$g_c$ (cycles / element)")
        ax.set_ylabel("extra time vs fully associative")
        legend_above(ax, ncols=ncols)
        print(save(fig, "hardware/h4_associativity", name))

    # how bad it is: our (unpadded) matrix on 4- to 32-way caches. 4-, 8- and
    # 16-way coincide (16 rows fit in all three), so they are drawn with
    # decreasing width, dashed on top of each other; 32-way fits 32 rows
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.plot(GC, extra(256, 2), label="4-way", **series(0))
    ax.plot(GC, extra(256, 3), color=SERIES[1], linestyle="--", linewidth=1.6, zorder=4,
            label="8-way")
    ax.plot(GC, extra(256, 4), color=SERIES[2], linestyle=":", linewidth=1.6, zorder=5,
            label="16-way")
    ax.plot(GC, extra(256, 5), label="32-way", **series(3))
    finish(ax, NAME + "_unpadded", 4)

    # what padding does: 8-way, rows of 256 (16 lines), 260 (16.25) and 272 (17)
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, (k, label) in enumerate(((256, "256 (16 lines)"), (260, "260 (16.25 lines)"),
                                    (272, "272 (17 lines)"))):
        ax.plot(GC, extra(k, 3), label=f"rows of {label}", **series(i))
    finish(ax, NAME + "_padded", 3)

    lines += ["", "## Part 2: padding, 192 x K x N, K = N, 16 KB",
              "", "Best runtime (tile) per cache; extra time over fully associative.", "",
              "| K = N | gc | " + " | ".join(ASSOC) + " |", "|---" * (2 + len(ASSOC)) + "|"]
    for k, label in PAD.items():
        for gc in GC:
            fa = best[(k, -1, gc)]
            cells = [f"{fa[0]:.3f} {fa[1]}"] + [
                f"{best[(k, a, gc)][0]:.3f} {best[(k, a, gc)][1]} "
                f"({100 * (best[(k, a, gc)][0] / fa[0] - 1):+.0f} %)"
                for a in list(ASSOC.values())[1:]]
            lines.append(f"| {label} | {gc} | " + " | ".join(cells) + " |")
    report = f"# {NAME}: fully associative vs set-associative L1\n\n" + "\n".join(lines) + "\n"
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
