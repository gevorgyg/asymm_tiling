"""Does the math model work as well with a set-associative L1?

Same procedure as model_sweep (alpha calibrated at gc = 0 on the SAME cache,
predict argmin max(alpha, gc*ceil(M/TM)/M), ties to lower alpha), on a small
subset, for a fully associative, 8-way and 4-way 16 KB L1 (64 B lines).
Also: how much it costs to use the tile that is best for the fully
associative cache on the set-associative one.

192x256x256 has power-of-two row strides (1 KB): in the 8-way 16 KB L1 (32
sets) a tile column's rows all map to 2 sets. 100^3 and 200x300x250 don't
alias like that.

run:  .venv/bin/python experiments/rewrite/assoc_check.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from overlap_fit import row, selection

NAME = "assoc_check"
# fully associative ~ an accelerator's scratchpad, 8-way ~ a CPU L1D,
# 4-way ~ a mobile-class L1D
ASSOC = {"fully assoc": -1, "8-way": 3, "4-way": 2}
MATRICES = [(192, 256, 256), (100, 100, 100), (200, 300, 250)]
TM = [8, 16, 24, 32, 48, 64, 80, 96]
TN = [8, 16, 32, 64]
GC = [5, 10, 20, 30, 50, 75, 100, 200]
L1 = 16384
REG = 4


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def main() -> None:
    params = []
    for assoc in ASSOC.values():
        for m, k, n in MATRICES:
            base = Params(m=m, k=k, n=n, l1_size=L1, l1_assoc=assoc,
                          fifo_capacity=2 * k * 64)
            params += [replace(base, tile_h=tm, tile_w=tn, gen_cost=gc)
                       for tm in TM for tn in TN if tm <= m and tn <= n
                       for gc in [0] + GC]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.l1_assoc, (p.m, p.k, p.n), p.tile_h, p.tile_w, p.gen_cost):
         s["Simulation: Total cycles"] / (p.m * p.k * p.n) for p, s in zip(params, stats)}

    def runs_for(assoc: int, shapes) -> list[dict]:
        out = []
        for (a, shape, tm, tn, gc), time in t.items():
            if a != assoc or gc == 0 or shape not in shapes:
                continue
            m, k, n = shape
            out.append({"l1": L1, "shape": shape, "tile": (tm, tn), "gc": gc, "T": time,
                        "alpha": t[(a, shape, tm, tn, 0)],
                        "B": gc * cdiv(m, tm) / m,
                        "S": cdiv(m, tm) * cdiv(n, tn) * REG * REG * gc / (m * n * k)})
        return out

    head = "| exact tile | TM* right | within 1 % | within 5 % | worst gap |"
    lines = [f"# {NAME}", "", __doc__.strip(), "", f"{len(params)} simulator runs.", "",
             "## Model accuracy per cache", "",
             "| cache | shapes | model " + head, "|---|---|---|---|---|---|---|---|"]
    for name, assoc in ASSOC.items():
        for label, shapes in (("all 3", MATRICES),) + tuple((str(s), [s]) for s in MATRICES):
            rs = runs_for(assoc, shapes)
            for v in ("max", "max+S"):
                lines.append(row(f"{name} | {label} | `{v}`", selection(rs, v, float("inf"))))

    # using the fully-associative best tile on the set-associative cache
    lines += ["", "## Using the fully associative cache's best tile on the others", "",
              "| cache | shape | best tile differs | median extra time | worst extra time |",
              "|---|---|---|---|---|"]
    fa = ASSOC["fully assoc"]
    for name, assoc in ASSOC.items():
        if assoc == fa:
            continue
        for shape in MATRICES:
            extra, differs = [], 0
            for gc in GC:
                tiles = [(tm, tn) for (a, s, tm, tn, g) in t if a == assoc and s == shape and g == gc]
                fa_best = min(tiles, key=lambda x: t[(fa, shape, *x, gc)])
                best = min(tiles, key=lambda x: t[(assoc, shape, *x, gc)])
                differs += fa_best != best
                extra.append(t[(assoc, shape, *fa_best, gc)] / t[(assoc, shape, *best, gc)] - 1)
            extra.sort()
            lines.append(f"| {name} | {shape} | {differs}/{len(GC)} "
                         f"| {extra[len(extra) // 2]:.1%} | {extra[-1]:.1%} |")

    (out_dir(NAME) / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Model accuracy per cache"):]))


if __name__ == "__main__":
    main()
