"""Re-run of the alpha experiments (pre-rewrite, math-model-no-l2):
e6-tn-independence, e3-alpha-calibration, e-l1size-regime.

Slides "Calibration: Building the alpha Table", the alpha heatmap / TN
dependence charts and the L1-size regime chart. B-stationary, B from the
FIFO, M=192, N=K=256, 4-byte elements, fully associative L1, no L2, mulacc
not counted. alpha = cycles / MNK.

Absolute alpha can't match: the old sim charged cache latency per element,
the rewrite per line (see old_results.py). So this compares
  - L1 traffic (old line_fills vs new L1 misses), which should match;
  - the shape of alpha: the cliff position per TN / per L1 size and the
    rank correlation of all cells;
  - E6's own check: does the gc=0 alpha table predict the best TM at gc=50
    (T = max(alpha, gc/TM), same safe() filter as the old experiment)?

run:  .venv/bin/python experiments/rewrite/alpha_surface.py
"""

import statistics

from harness import out_dir, run_many
from old_results import load

NAME = "alpha_surface"
EXPERIMENTS = {
    "e6": "v5-results/math-model-no-l2/e6-tn-independence",
    "e3": "v5-results/math-model-no-l2/e3-alpha-calibration",
    "l1size": "v5-results/math-model-no-l2/e-l1size-regime",
}
CLIFF = 1.5   # alpha > CLIFF x (min alpha of the row) counts as over the cliff


def ws_lines(tm: int, tn: int) -> int:
    """Reuse distance of a C line in L1 lines (old experiments' safe())."""
    return tm * tn // 8 + tm // 4 - 2


def safe(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) < 300


def ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):                       # average ranks for ties
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5


def cliff(alpha_by_tm: dict[int, float]) -> int | None:
    """Smallest TM whose alpha is past the cliff (> CLIFF x row minimum)."""
    lo = min(alpha_by_tm.values())
    over = [tm for tm, a in sorted(alpha_by_tm.items()) if a > CLIFF * lo]
    return over[0] if over else None


def collect(key: str) -> list[dict]:
    cells = load(EXPERIMENTS[key])
    assert all(c.params for c in cells), {c.unsupported for c in cells}
    new = run_many([c.params for c in cells], out_dir(NAME) / f"results_{key}.json")
    rows = []
    for c, s in zip(cells, new):
        o = c.overrides
        mnk = o["A_HEIGHT_DIM"] * o["A_WIDTH_DIM"] * o["B_WIDTH_DIM"]
        rows.append({
            "tm": o["TILE_M"], "tn": o["TILE_N"], "gc": o["PRNG_FIFO_GEN_COST"],
            "l1": o["L1_SIZE_BYTES"],
            "old_a": c.metrics["cycles"] / mnk,
            "new_a": s["Simulation: Total cycles"] / mnk,
            "old_f": c.metrics["l1"]["line_fills"],
            "new_f": s["CacheUnit: L1 misses"],
        })
    return rows


def traffic_line(key: str, rows: list[dict]) -> str:
    exact = sum(r["old_f"] == r["new_f"] for r in rows)
    worst = max(abs(r["new_f"] / r["old_f"] - 1) for r in rows)
    return (f"- **{key}**: L1 misses identical in {exact}/{len(rows)} cells, "
            f"worst |diff| {worst:.2%}")


def alpha_table(rows: list[dict], tms: list[int], tns: list[int]) -> list[str]:
    lines = ["| TM \\ TN | " + " | ".join(f"{tn}" for tn in tns) + " |",
             "|---|" + "---|" * len(tns)]
    cell = {(r["tm"], r["tn"]): r for r in rows}
    for tm in tms:
        vals = []
        for tn in tns:
            r = cell.get((tm, tn))
            vals.append("—" if r is None else
                        f"{r['old_a']:.2f} → {r['new_a']:.2f} ({r['new_a'] / r['old_a']:.2f}×)")
        lines.append(f"| {tm} | " + " | ".join(vals) + " |")
    return lines


def predict_section(rows: list[dict], gc: int) -> list[str]:
    """E6 part 2: calibrated alpha(TM,TN) at gc=0 -> TM* at gc, per TN."""
    lines = [f"| TN | old predicted | old empirical | new predicted | new empirical |",
             "|---|---|---|---|---|"]
    tns = sorted({r["tn"] for r in rows})
    hits = {"old": 0, "new": 0}
    for tn in tns:
        cal = {r["tm"]: r for r in rows if r["tn"] == tn and r["gc"] == 0}
        run = {r["tm"]: r for r in rows if r["tn"] == tn and r["gc"] == gc}
        cands = [tm for tm in cal if tm in run and safe(tm, tn)]
        res = []
        for v in ("old", "new"):
            pred = min(cands, key=lambda tm: max(cal[tm][f"{v}_a"], gc / tm))
            emp = min(cands, key=lambda tm: run[tm][f"{v}_a"])
            hits[v] += pred == emp
            res += [pred, emp]
        lines.append(f"| {tn} | {res[0]} | {res[1]} | {res[2]} | {res[3]} |")
    lines += ["", f"Prediction correct: old {hits['old']}/{len(tns)}, "
                  f"new {hits['new']}/{len(tns)}."]
    return lines


def main() -> None:
    data = {key: collect(key) for key in EXPERIMENTS}
    e6 = data["e6"]
    e6_0 = [r for r in e6 if r["gc"] == 0]
    tms = sorted({r["tm"] for r in e6})
    tns = sorted({r["tn"] for r in e6})

    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), "",
             "## Traffic", ""]
    lines += [traffic_line(k, v) for k, v in data.items()]

    all_0 = [r for k in data for r in data[k] if r["gc"] == 0]
    rho = spearman([r["old_a"] for r in all_0], [r["new_a"] for r in all_0])
    ratios = [r["new_a"] / r["old_a"] for r in all_0]
    lines += ["", "## Shape of alpha (gc = 0)", "",
              f"- Spearman rank correlation old vs new over all {len(all_0)} "
              f"gc=0 cells: **{rho:.3f}**",
              f"- new/old alpha ratio: min {min(ratios):.2f}, median "
              f"{statistics.median(ratios):.2f}, max {max(ratios):.2f}", ""]

    lines += ["### Cliff position per TN (e6, first TM with alpha > "
              f"{CLIFF}x the row minimum)", "",
              "| TN | old cliff TM | new cliff TM |", "|---|---|---|"]
    for tn in tns:
        row = [r for r in e6_0 if r["tn"] == tn]
        oc = cliff({r["tm"]: r["old_a"] for r in row})
        nc = cliff({r["tm"]: r["new_a"] for r in row})
        lines.append(f"| {tn} | {oc or 'none'} | {nc or 'none'} |")

    l1 = [r for r in data["l1size"] if r["gc"] == 0 and r["tn"] == 32]
    lines += ["", "### Cliff position per L1 size (l1size, TN = 32)", "",
              "| L1 | old cliff TM | new cliff TM |", "|---|---|---|"]
    for size in sorted({r["l1"] for r in l1}):
        row = [r for r in l1 if r["l1"] == size]
        oc = cliff({r["tm"]: r["old_a"] for r in row})
        nc = cliff({r["tm"]: r["new_a"] for r in row})
        lines.append(f"| {size // 1024} KB | {oc or 'none'} | {nc or 'none'} |")

    lines += ["", "## E6: does the gc=0 table predict TM* at gc=50?", ""]
    lines += predict_section(e6, 50)

    lines += ["", "## alpha(TM, TN) at gc = 0 (e6): old → new (ratio)", ""]
    lines += alpha_table(e6_0, tms, tns)

    (out_dir(NAME) / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Traffic"):]))


if __name__ == "__main__":
    main()
