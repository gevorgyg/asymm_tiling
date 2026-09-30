"""Replace max() in the math model: how do alpha and B generation combine?

Data: the cached model_sweep runs (22176, 3 L1 sizes x 6 matrix shapes, gc 0
... 400). For every tile and gc > 0: alpha = T(gc = 0) / MNK (calibration),
B = gc * ceil(M/TM) / M (B generation per MAC), T = measured / MNK.

Findings that motivate the variants:
  - T / max(alpha, B) is ~1.000 when one term dominates, and peaks when
    alpha ~ B (median 1.05, p90 1.25, max 1.47 at B/alpha 0.9 - 1.0):
    max() assumes perfect overlap, which fails when the rates balance.
  - Over all runs, the cycles above max() equal one FIFO startup per tile
    at the median: the FIFO restarts empty every tile (load_seed), so its
    first register block waits 16 * gc cycles with nothing to overlap.

Variants (per MAC; S = startup = tiles * reg_dim^2 * gc / MNK):
  max          max(alpha, B)                     (the presentation's model)
  max+S        max(alpha, B) + S                 (no fitted parameter)
  smooth       (alpha^p + B^p)^(1/p)             (p fitted)
  smooth+S     (alpha^p + B^p)^(1/p) + S         (p fitted)

p is fitted on the prediction error of T (mean |log(T_pred / T)|), not on
tile-selection accuracy, which is then an honest check. Cross-validation:
fit p on 5 matrix shapes, evaluate on the 6th, for each shape.

run:  .venv/bin/python experiments/rewrite/overlap_fit.py
"""

import math
import statistics
from collections import defaultdict
from dataclasses import replace

from harness import out_dir, run_many
from model_sweep import GC, MATRICES, configs

NAME = "overlap_fit"
REG = 4
P_GRID = [x / 2 for x in range(2, 81)]   # 1.0 ... 40.0


def cdiv(a: int, b: int) -> int:
    return -(-a // b)


def load() -> list[dict]:
    cells = configs()
    params = [replace(p, gen_cost=gc) for gc in [0] + GC for _, _, p in cells]
    stats = run_many(params, out_dir("model_sweep") / "results.json")   # cached
    t = {}
    for p, s in zip(params, stats):
        t[(p.l1_size, (p.m, p.k, p.n), p.tile_h, p.tile_w, p.gen_cost)] = \
            s["Simulation: Total cycles"] / (p.m * p.k * p.n)
    runs = []
    for (l1, shape, tm, tn, gc), time in t.items():
        if gc == 0:
            continue
        m, k, n = shape
        runs.append({
            "l1": l1, "shape": shape, "tile": (tm, tn), "gc": gc, "T": time,
            "alpha": t[(l1, shape, tm, tn, 0)],
            "B": gc * cdiv(m, tm) / m,
            "S": cdiv(m, tm) * cdiv(n, tn) * REG * REG * gc / (m * n * k),
        })
    return runs


def predict(r: dict, variant: str, p: float) -> float:
    a, b = r["alpha"], r["B"]
    if variant.startswith("max"):
        base = max(a, b)
    else:
        hi = max(a, b)                      # scaled to avoid overflow at big p
        base = hi * ((a / hi) ** p + (b / hi) ** p) ** (1 / p)
    return base + (r["S"] if variant.endswith("+S") else 0.0)


def log_err(runs: list[dict], variant: str, p: float) -> float:
    return statistics.fmean(abs(math.log(predict(r, variant, p) / r["T"])) for r in runs)


def fit_p(runs: list[dict], variant: str) -> float:
    if variant.startswith("max"):
        return math.inf
    return min(P_GRID, key=lambda p: log_err(runs, variant, p))


def selection(runs: list[dict], variant: str, p: float) -> dict:
    """Pick the tile with the lowest predicted T per condition (ties to the
    lower alpha) and compare with the measured best."""
    cond = defaultdict(list)
    for r in runs:
        cond[(r["l1"], r["shape"], r["gc"])].append(r)
    gaps, exact, tm_ok = [], 0, 0
    for rs in cond.values():
        pred = min(rs, key=lambda r: (predict(r, variant, p), r["alpha"]))
        best = min(rs, key=lambda r: r["T"])
        gaps.append(pred["T"] / best["T"] - 1)
        exact += pred["tile"] == best["tile"]
        tm_ok += pred["tile"][0] == best["tile"][0]
    n = len(gaps)
    return {"n": n, "exact": exact, "tm": tm_ok,
            "w1": sum(g <= 0.01 for g in gaps), "w5": sum(g <= 0.05 for g in gaps),
            "worst": max(gaps)}


def row(label: str, s: dict) -> str:
    n = s["n"]
    return (f"| {label} | {s['exact']}/{n} ({s['exact'] / n:.0%}) "
            f"| {s['tm']}/{n} ({s['tm'] / n:.0%}) | {s['w1'] / n:.0%} "
            f"| {s['w5'] / n:.0%} | {s['worst']:.1%} |")


def main() -> None:
    runs = load()
    variants = ["max", "max+S", "smooth", "smooth+S"]

    lines = [f"# {NAME}", "", __doc__.strip(), "",
             f"{len(runs)} runs with gc > 0.", "",
             "## Fit of T (all runs)", "",
             "| variant | p | mean abs log error | median abs rel error | p90 | worst |",
             "|---|---|---|---|---|---|"]
    fitted = {}
    for v in variants:
        p = fit_p(runs, v)
        fitted[v] = p
        errs = sorted(abs(predict(r, v, p) / r["T"] - 1) for r in runs)
        lines.append(f"| `{v}` | {p:g} | {log_err(runs, v, p):.4f} "
                     f"| {statistics.median(errs):.2%} | {errs[9 * len(errs) // 10]:.2%} "
                     f"| {errs[-1]:.1%} |")

    head = ("| exact tile | TM* right | within 1 % | within 5 % | worst gap |")
    lines += ["", "## Tile selection (p fitted on all shapes)", "",
              "| variant " + head, "|---|---|---|---|---|---|"]
    for v in variants:
        lines.append(row(f"`{v}` (p={fitted[v]:g})", selection(runs, v, fitted[v])))

    lines += ["", "## Cross-validation: fit p without one shape, test on it", "",
              "| variant | held-out shape | p fitted on the other 5 " + head,
              "|---|---|---|---|---|---|---|---|"]
    totals = {}
    for v in variants:
        agg = {"n": 0, "exact": 0, "tm": 0, "w1": 0, "w5": 0, "worst": 0.0}
        for shape in MATRICES:
            train = [r for r in runs if r["shape"] != shape]
            test = [r for r in runs if r["shape"] == shape]
            p = fit_p(train, v)
            s = selection(test, v, p)
            for key in ("n", "exact", "tm", "w1", "w5"):
                agg[key] += s[key]
            agg["worst"] = max(agg["worst"], s["worst"])
            lines.append(f"| `{v}` | {shape} | {p:g} "
                         + row("", s).split("| ", 2)[2])
        totals[v] = agg
    lines += ["", "### Cross-validation totals (each shape predicted with p fitted "
              "on the others)", "", "| variant " + head, "|---|---|---|---|---|---|"]
    for v in variants:
        lines.append(row(f"`{v}`", totals[v]))

    (out_dir(NAME) / "README.md").write_text("\n".join(lines) + "\n")
    start = lines.index("## Fit of T (all runs)")
    end = lines.index("## Cross-validation: fit p without one shape, test on it")
    print("\n".join(lines[start:end]))
    print("\n".join(lines[lines.index("### Cross-validation totals (each shape predicted with p fitted on the others)"):]))


if __name__ == "__main__":
    main()
