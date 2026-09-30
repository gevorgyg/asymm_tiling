"""How often does the math model pick the best tile, on many more cases?

Model: T / MNK = max(alpha(TM, TN), gc * ceil(M/TM) / M), alpha calibrated
once at gc = 0 per (L1 size, matrix shape). Prediction: argmin over all
tiles, ties to the lower alpha (as the old roofline validation). Compared
with the empirically best tile at each gc.

The B term: B-stationary regenerates B once per row of tiles, so
ceil(M/TM) * K * N elements for M * N * K MACs. That is gc / TM only when TM
divides M (the presentation's model); for other tiles gc / TM underestimates
the cost (M=100: TM=64 and TM=50 both take 2 tile rows, cost gc/50). The old
gc / TM model is kept as a comparison row.

Setup (the model's assumptions): B-stationary, B from the FIFO, 4-byte
elements, fully associative L1, no L2, L1 4 / memory 180 cycles, mulacc not
counted, FIFO large enough never to fill (2 * K * 64). Tiles don't have to
divide the matrix (edge tiles are clipped) and no safe() filter is applied:
the calibrated alpha already includes eviction.

run:  .venv/bin/python experiments/rewrite/model_sweep.py
"""

import statistics
from collections import defaultdict
from dataclasses import replace

from harness import Params, out_dir, run_many

NAME = "model_sweep"
L1_SIZES = [8192, 16384, 32768]
MATRICES = [                      # (M, K, N)
    (192, 256, 256),              # the presentation's shape
    (100, 100, 100),
    (200, 300, 250),
    (384, 256, 512),
    (256, 512, 128),
    (150, 222, 190),              # not multiples of 4 either
]
TM = [4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128]
TN = [4, 8, 12, 16, 24, 32, 48, 64]
GC = [2, 5, 10, 15, 20, 30, 50, 75, 100, 200, 400]

# B-generation term per MAC, as a function of (gc, TM, M)
NEW = "gc*ceil(M/TM)/M"
OLD = "gc/TM"
MODELS = {
    NEW: lambda gc, tm, m: gc * -(-m // tm) / m,
    OLD: lambda gc, tm, _m: gc / tm,
}


def configs() -> list[tuple]:
    out = []
    for l1 in L1_SIZES:
        for m, k, n in MATRICES:
            base = Params(m=m, k=k, n=n, l1_size=l1, l1_assoc=-1,
                          fifo_capacity=2 * k * 64)
            for tm in TM:
                for tn in TN:
                    if tm <= m and tn <= n:
                        out.append((l1, (m, k, n), replace(base, tile_h=tm, tile_w=tn)))
    return out


def main() -> None:
    out = out_dir(NAME)
    cells = configs()
    params = [replace(p, gen_cost=gc) for gc in [0] + GC for _, _, p in cells]
    stats = run_many(params, out / "results.json")

    # alpha[(l1, shape)][gc][(tm, tn)]
    alpha = defaultdict(lambda: defaultdict(dict))
    for p, s in zip(params, stats):
        shape = (p.m, p.k, p.n)
        alpha[(p.l1_size, shape)][p.gen_cost][(p.tile_h, p.tile_w)] = \
            s["Simulation: Total cycles"] / (p.m * p.k * p.n)

    rows = []
    for (l1, shape), by_gc in sorted(alpha.items()):
        cal = by_gc[0]
        for gc in GC:
            meas = by_gc[gc]
            best = min(meas, key=meas.get)
            for model, b_cost in MODELS.items():
                pred = min(meas, key=lambda t: (max(cal[t], b_cost(gc, t[0], shape[0])),
                                                cal[t]))
                rows.append({"model": model, "l1": l1, "shape": shape, "gc": gc,
                             "pred": pred, "best": best,
                             "gap": meas[pred] / meas[best] - 1})

    def summary(rs: list[dict]) -> str:
        n = len(rs)
        exact = sum(r["pred"] == r["best"] for r in rs)
        tm_ok = sum(r["pred"][0] == r["best"][0] for r in rs)
        gaps = [r["gap"] for r in rs]
        return (f"| {exact}/{n} ({exact / n:.0%}) | {tm_ok}/{n} ({tm_ok / n:.0%}) "
                f"| {sum(g <= 0.01 for g in gaps) / n:.0%} "
                f"| {sum(g <= 0.05 for g in gaps) / n:.0%} "
                f"| {statistics.median(gaps):.2%} | {max(gaps):.1%} |")

    head = ("| model | exact tile | TM* right | within 1 % | within 5 % "
            "| median gap | worst gap |")
    sep = "|---|---|---|---|---|---|---|"
    n_cond = len(rows) // len(MODELS)
    lines = [f"# {NAME}", "", __doc__.strip(), "",
             f"{n_cond} conditions ({len(L1_SIZES)} L1 sizes x "
             f"{len(MATRICES)} matrices x {len(GC)} gc), "
             f"{len(params)} simulator runs. gap = cycles(predicted tile) / "
             f"cycles(best tile) - 1. Rows with `{OLD}` are the "
             f"presentation's term, for comparison.", "",
             "## Overall", "", head, sep]
    lines += [f"| `{m}` " + summary([r for r in rows if r["model"] == m])
              for m in MODELS]
    lines.append("")

    for title, key, values in (("L1 size", "l1", L1_SIZES),
                               ("matrix (M, K, N)", "shape", MATRICES),
                               ("gc", "gc", GC)):
        lines += [f"## By {title}", "", f"| {title} " + head, "|---" + sep]
        for v in values:
            label = f"{v // 1024} KB" if key == "l1" else str(v)
            for m in MODELS:
                lines.append(f"| {label} | `{m}` " + summary(
                    [r for r in rows if r[key] == v and r["model"] == m]))
        lines.append("")

    lines += [f"## Misses of `{NEW}` (predicted ≠ best), worst first", "",
              "| L1 | matrix | gc | predicted | best | gap |", "|---|---|---|---|---|---|"]
    misses = (r for r in rows if r["model"] == NEW and r["pred"] != r["best"])
    for r in sorted(misses, key=lambda r: -r["gap"]):
        lines.append(f"| {r['l1'] // 1024} KB | {r['shape']} | {r['gc']} "
                     f"| {r['pred']} | {r['best']} | {r['gap']:.2%} |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Overall"):lines.index("## By L1 size")]))


if __name__ == "__main__":
    main()
