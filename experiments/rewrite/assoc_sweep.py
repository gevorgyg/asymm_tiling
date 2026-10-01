"""Associativity on the full model_sweep grid (confirms assoc_check.py).

Same grid as model_sweep (L1 8 / 16 / 32 KB x 6 matrix shapes x all tiles x
gc), with a fully associative, 8-way and 4-way L1. The fully associative runs
are read from model_sweep's cache. Per cache:
  - model accuracy, alpha calibrated on the SAME cache, with the corrected B
    term, plain max() and max() + startup S (as in overlap_fit.py);
  - what it costs to use the tile that is best on the fully associative
    cache (~ an accelerator scratchpad) on the set-associative one.

run:  .venv/bin/python experiments/rewrite/assoc_sweep.py
"""

import statistics
from dataclasses import replace

from harness import out_dir, run_many
from model_sweep import GC, MATRICES, configs
from overlap_fit import row, selection

NAME = "assoc_sweep"
ASSOC = {"fully assoc": -1, "8-way": 3, "4-way": 2}
REG = 4


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def main() -> None:
    cells = configs()
    base = [replace(p, gen_cost=gc) for gc in [0] + GC for _, _, p in cells]

    t = {}   # (assoc, l1, shape, tm, tn, gc) -> cycles / MNK
    for name, assoc in ASSOC.items():
        if assoc == -1:     # identical to model_sweep's runs, read from its cache
            params, cache = base, out_dir("model_sweep") / "results.json"
        else:
            params = [replace(p, l1_assoc=assoc) for p in base]
            cache = out_dir(NAME) / f"results_{name}.json"
        for p, s in zip(params, run_many(params, cache)):
            t[(assoc, p.l1_size, (p.m, p.k, p.n), p.tile_h, p.tile_w, p.gen_cost)] = \
                s["Simulation: Total cycles"] / (p.m * p.k * p.n)

    def runs(assoc: int) -> list[dict]:
        out = []
        for (a, l1, shape, tm, tn, gc), time in t.items():
            if a != assoc or gc == 0:
                continue
            m, k, n = shape
            out.append({"l1": l1, "shape": shape, "tile": (tm, tn), "gc": gc, "T": time,
                        "alpha": t[(a, l1, shape, tm, tn, 0)],
                        "B": gc * cdiv(m, tm) / m,
                        "S": cdiv(m, tm) * cdiv(n, tn) * REG * REG * gc / (m * n * k)})
        return out

    head = "| exact tile | TM* right | within 1 % | within 5 % | worst gap |"
    lines = [f"# {NAME}", "", __doc__.strip(), "",
             "## Model accuracy per cache (alpha calibrated on that cache)", "",
             "| cache | model " + head, "|---|---|---|---|---|---|---|"]
    for name, assoc in ASSOC.items():
        rs = runs(assoc)
        for v in ("max", "max+S"):
            lines.append(row(f"{name} | `{v}`", selection(rs, v, float("inf"))))

    lines += ["", "## Using the fully associative cache's best tile on the others", "",
              "Extra time = T(fully associative best tile) / T(best tile), both "
              "measured on the set-associative cache, over all gc.", "",
              "| cache | L1 | matrix | best tile differs | median extra | worst extra |",
              "|---|---|---|---|---|---|"]
    for name, assoc in ASSOC.items():
        if assoc == -1:
            continue
        for l1 in sorted({k[1] for k in t}):
            for shape in MATRICES:
                extra, differs = [], 0
                for gc in GC:
                    tiles = [(k[3], k[4]) for k in t
                             if k[0] == assoc and k[1] == l1 and k[2] == shape and k[5] == gc]
                    fa = min(tiles, key=lambda x: t[(-1, l1, shape, *x, gc)])
                    best = min(tiles, key=lambda x: t[(assoc, l1, shape, *x, gc)])
                    differs += fa != best
                    extra.append(t[(assoc, l1, shape, *fa, gc)] / t[(assoc, l1, shape, *best, gc)] - 1)
                lines.append(f"| {name} | {l1 // 1024} KB | {shape} | {differs}/{len(GC)} "
                             f"| {statistics.median(extra):.1%} | {max(extra):.1%} |")

    (out_dir(NAME) / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Model accuracy per cache (alpha calibrated on that cache)"):]))


if __name__ == "__main__":
    main()
