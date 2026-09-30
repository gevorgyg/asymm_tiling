"""Re-run of pre-rewrite v5-results/math-model-no-l2/e8-gc-boundary-sweep.

Slides: "Calibrated TM* vs gc" (tm_star_trajectory), "Impact of Tile
Selection" (best_shape_per_gc, optimal_vs_square and the 20-65% / ~85% /
up to 90% speedups). B-stationary, FIFO, M=192, N=K=256, 4-byte elements,
fully associative 16 KB L1, no L2, mulacc not counted, FIFO capacity
2*K*32. alpha = cycles / MNK. Each part uses the old definition:

  1. TM*(TN, gc): best safe TM (safe = old ws_lines < 300), and whether
     the gc=0 calibration predicts it with T = max(alpha(TM,TN), gc/TM).
  2. Globally best (TM, TN) per gc, over all tiles (plot_all.py).
  3. Optimal vs square per TN in {8,16,32,64}: best TM over all tiles vs
     TM = TN, speedup = (square - optimal) / square (plot_all.py).

The rewrite's alpha is ~4x smaller (cache hits charged per line, not per
element) while gc/TM is unchanged, so every gc threshold is expected to move
down. EXTRA_GC are run in the rewrite only, to locate its transitions.

run:  .venv/bin/python experiments/rewrite/gc_sweep.py
"""

from collections import defaultdict
from dataclasses import replace

from alpha_surface import safe
from harness import out_dir, run_many
from old_results import load

NAME = "gc_sweep"
OLD = "v5-results/math-model-no-l2/e8-gc-boundary-sweep"
EXTRA_GC = [2, 4, 6, 8, 10, 12, 20, 25]
SQUARE_TN = [8, 16, 32, 64]
SLIDE_SPEEDUP_GC = [100, 250, 400]


def main() -> None:
    out = out_dir(NAME)
    cells = load(OLD)
    assert all(c.params for c in cells), {c.unsupported for c in cells}
    mnk = 192 * 256 * 256

    old_gcs = sorted({c.overrides["PRNG_FIFO_GEN_COST"] for c in cells})
    base = [c for c in cells if c.overrides["PRNG_FIFO_GEN_COST"] == 0]
    extra = [replace(c.params, gen_cost=gc) for gc in EXTRA_GC for c in base]
    new = run_many([c.params for c in cells] + extra, out / "results.json")

    # alpha[version][gc][(tm, tn)]
    alpha = {"old": defaultdict(dict), "new": defaultdict(dict)}
    for c, s in zip(cells, new):
        o = c.overrides
        key = (o["TILE_M"], o["TILE_N"])
        alpha["old"][o["PRNG_FIFO_GEN_COST"]][key] = c.metrics["cycles"] / mnk
        alpha["new"][o["PRNG_FIFO_GEN_COST"]][key] = s["Simulation: Total cycles"] / mnk
    for p, s in zip(extra, new[len(cells):]):
        alpha["new"][p.gen_cost][(p.tile_h, p.tile_w)] = s["Simulation: Total cycles"] / mnk

    tms = sorted({k[0] for k in alpha["old"][0]})
    tns = sorted({k[1] for k in alpha["old"][0]})
    new_gcs = sorted(alpha["new"])

    def tm_star(v: str, gc: int, tn: int) -> int:
        a = alpha[v][gc]
        return min((tm for tm in tms if safe(tm, tn)), key=lambda tm: a[(tm, tn)])

    def tm_pred(v: str, gc: int, tn: int) -> int:
        a0 = alpha[v][0]
        return min((tm for tm in tms if safe(tm, tn)),
                   key=lambda tm: max(a0[(tm, tn)], gc / tm))

    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), ""]

    # 1. prediction accuracy + trajectory
    lines += ["## 1. Calibrated prediction of TM* (the 70/70 claim)", ""]
    for v, gcs in (("old", old_gcs), ("new", old_gcs), ("new", new_gcs)):
        gcs = [g for g in gcs if g]
        hits = sum(tm_pred(v, g, tn) == tm_star(v, g, tn) for g in gcs for tn in tns)
        label = "old gc grid" if gcs == [g for g in old_gcs if g] else "old + extra gc"
        lines.append(f"- **{v}** ({label}): {hits}/{len(gcs) * len(tns)} correct")
    lines += ["", "### Empirical TM* per (TN, gc): old / new", "",
              "| gc | " + " | ".join(f"TN={tn}" for tn in tns) + " |",
              "|---|" + "---|" * len(tns)]
    for g in sorted(set(old_gcs) | set(new_gcs)):
        if not g:
            continue
        vals = []
        for tn in tns:
            o = tm_star("old", g, tn) if g in alpha["old"] else "·"
            n = tm_star("new", g, tn)
            vals.append(f"{o} / {n}" if o != n else f"{n}")
        lines.append(f"| {g} | " + " | ".join(vals) + " |")
    lines += ["", "(single value = same in both; · = gc not run in the old sim)"]

    # 2. global best tile per gc
    lines += ["", "## 2. Globally best (TM, TN) per gc (best_shape_per_gc)", "",
              "| gc | old | new |", "|---|---|---|"]
    for g in sorted(set(old_gcs) | set(new_gcs)):
        if not g:
            continue
        o = min(alpha["old"][g], key=alpha["old"][g].get) if g in alpha["old"] else "·"
        n = min(alpha["new"][g], key=alpha["new"][g].get)
        lines.append(f"| {g} | {o} | {n} |")

    # 3. optimal vs square
    lines += ["", "## 3. Speedup of optimal TM over square TM = TN (optimal_vs_square)", "",
              "Slide: gc=100 20-65%, gc=250 ~85%, gc=400 up to 90%.", "",
              "| gc | " + " | ".join(f"TN={tn} old → new" for tn in SQUARE_TN) + " |",
              "|---|" + "---|" * len(SQUARE_TN)]
    for g in sorted(set(old_gcs) | set(new_gcs)):
        if not g:
            continue
        vals = []
        for tn in SQUARE_TN:
            sp = {}
            for v in ("old", "new"):
                a = alpha[v].get(g)
                if not a:
                    continue
                col = {tm: a[(tm, tn)] for tm in tms}
                sp[v] = (col[tn] - min(col.values())) / col[tn]
            vals.append(" → ".join(f"{sp[v]:.0%}" for v in ("old", "new") if v in sp))
        mark = " **(slide)**" if g in SLIDE_SPEEDUP_GC else ""
        lines.append(f"| {g}{mark} | " + " | ".join(vals) + " |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## 1. Calibrated prediction of TM* (the 70/70 claim)"):]))


if __name__ == "__main__":
    main()
