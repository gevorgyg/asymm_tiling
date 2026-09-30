"""Does the fitted overlap parameter p depend on the FIFO startup / burst size?

The register tile size reg_dim sets both: every tile starts by waiting for
one reg_dim x reg_dim block from an empty FIFO (startup S = tiles * reg^2 *
gc / MNK), and B is consumed reg^2 elements per pop. Sweep reg_dim in
{2, 4, 8} on a small subset and, per reg_dim:
  - check that S still explains the median excess over max(alpha, B);
  - fit p for the smooth max, with and without S (see overlap_fit.py);
  - compare tile selection.

Subset (fast): 16 KB fully associative L1, shapes 192x256x256 and 100^3,
TM 8..96, TN 8..64, gc 0..200. Otherwise the model_sweep setup.

run:  .venv/bin/python experiments/rewrite/overlap_regdim.py
"""

import statistics
from dataclasses import replace

from harness import Params, out_dir, run_many
from overlap_fit import fit_p, row, selection

NAME = "overlap_regdim"
REG_DIMS = [2, 4, 8]
MATRICES = [(192, 256, 256), (100, 100, 100)]
TM = [8, 16, 24, 32, 48, 64, 80, 96]
TN = [8, 16, 32, 64]
GC = [5, 10, 20, 30, 50, 75, 100, 200]
L1 = 16384


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def main() -> None:
    params = []
    for reg in REG_DIMS:
        for m, k, n in MATRICES:
            base = Params(m=m, k=k, n=n, l1_size=L1, l1_assoc=-1, reg_dim=reg,
                          fifo_capacity=2 * k * 64)
            for tm in TM:
                for tn in TN:
                    if tm <= m and tn <= n:
                        for gc in [0] + GC:
                            params.append(replace(base, tile_h=tm, tile_w=tn, gen_cost=gc))
    stats = run_many(params, out_dir(NAME) / "results.json")

    t = {(p.reg_dim, (p.m, p.k, p.n), p.tile_h, p.tile_w, p.gen_cost):
         s["Simulation: Total cycles"] / (p.m * p.k * p.n) for p, s in zip(params, stats)}

    lines = [f"# {NAME}", "", __doc__.strip(), "", f"{len(params)} simulator runs.", "",
             "## Per register size", "",
             "| reg_dim | runs | median excess / S | p (smooth) | p (smooth+S) |",
             "|---|---|---|---|---|"]
    sel = []
    for reg in REG_DIMS:
        runs = []
        for (r, shape, tm, tn, gc), time in t.items():
            if r != reg or gc == 0:
                continue
            m, k, n = shape
            runs.append({
                "l1": L1, "shape": shape, "tile": (tm, tn), "gc": gc, "T": time,
                "alpha": t[(reg, shape, tm, tn, 0)],
                "B": gc * cdiv(m, tm) / m,
                "S": cdiv(m, tm) * cdiv(n, tn) * reg * reg * gc / (m * n * k),
            })
        excess = statistics.median((r["T"] - max(r["alpha"], r["B"])) / r["S"] for r in runs)
        p_s, p_ss = fit_p(runs, "smooth"), fit_p(runs, "smooth+S")
        lines.append(f"| {reg} | {len(runs)} | {excess:.2f} | {p_s:g} | {p_ss:g} |")
        for v, p in (("max", float("inf")), ("max+S", float("inf")),
                     ("smooth", p_s), ("smooth+S", p_ss)):
            sel.append(row(f"{reg} | `{v}` (p={p:g})", selection(runs, v, p)))

    lines += ["", "## Tile selection", "",
              "| reg_dim | variant | exact tile | TM* right | within 1 % | within 5 % | worst gap |",
              "|---|---|---|---|---|---|---|"] + sel

    (out_dir(NAME) / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Per register size"):]))


if __name__ == "__main__":
    main()
