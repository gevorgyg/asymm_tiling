"""H2 (hardware engineer): spend area on a bigger L1 or a faster PRNG?

Reuses the runs of hw_prng_budget (same grid, same cache file): for every
L1 size and gc, the best runtime T*(L1, gc) over all tiles.

At a design point (L1, gc) the two upgrades are
  - doubling the L1:      speedup T*(L1, gc) / T*(2 L1, gc),
  - halving gc (a PRNG twice as fast, or a second generator):
                          speedup T*(L1, gc) / T*(L1, gc / 2).
Finding: they are the same. T*(2 L1, gc) = T*(L1, gc / 2), because doubling
L1 lets a tile with twice the rows fit at the same width and the same alpha,
which halves the rows of tiles and so the generation per MAC. The best tile
at (2 L1, gc) is the best tile at (L1, gc / 2) with twice the height.

No figure (the user's choice): hw_prng_budget's figure answers both
questions. On its linear gc axis each L1 doubling stretches the curve to
twice the width. This script only writes the numeric check to the README.

run:  .venv/bin/python experiments/rewrite/hw_l1_vs_prng.py
"""

from dataclasses import replace

import hw_prng_budget as h
from harness import Params, out_dir, run_many

NAME = "hw_l1_vs_prng"


def main() -> None:
    tiles = [(tm, tn) for tm in h.TM for tn in h.TN]
    params = [replace(Params(l1_assoc=-1), l1_size=l1, tile_h=tm, tile_w=tn, gen_cost=gc)
              for l1 in h.L1.values() for gc in h.GC for tm, tn in tiles]
    stats = run_many(params, out_dir(h.NAME) / f"results{'_small' if h.SMALL else ''}.json")
    t = {(p.l1_size, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / h.MNK
         for p, s in zip(params, stats)}
    best = {(l1, gc): min((t[(l1, gc, *tl)], tl) for tl in tiles)
            for l1 in h.L1.values() for gc in h.GC}

    gcs = [gc for gc in h.GC if gc > 0]
    names = list(h.L1)
    lines = ["| from | gc | doubling L1 | halving gc | T*(2 L1, gc) / T*(L1, gc/2) | "
             "best tile (2 L1, gc) | best tile (L1, gc/2) |", "|---" * 7 + "|"]
    for j, l1 in enumerate(list(h.L1.values())[:-1]):
        for gc in gcs:
            if gc % 2 or gc // 2 not in h.GC:
                continue
            (big, t_big), (fast, t_fast) = best[(l1 + 1, gc)], best[(l1, gc // 2)]
            here = best[(l1, gc)][0]
            lines.append(f"| {names[j]} | {gc} | {here / big:.2f}× | {here / fast:.2f}× | "
                         f"{100 * (big / fast - 1):+.1f} % | {t_big} | {t_fast} |")
    report = (f"# {NAME}{' (small)' if h.SMALL else ''}: bigger L1 or faster PRNG\n\n"
              f"From the {h.NAME} runs ({len(tiles)} tiles × {len(h.GC)} gc × "
              f"{len(h.L1)} L1 sizes).\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if h.SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
