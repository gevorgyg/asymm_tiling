"""Re-run of pre-rewrite v5-results/paper-model/paper-traffic-model.

Slides "Traffic Minimum at the Predicted Tile" and the savings table of
"B/A Balance": L1 read traffic vs tile aspect ratio at constant C-tile area,
m = n = k = 256, A/C 8 B, B 8/4/2/1 B (rho = 1 .. 1/8), fully associative
16 KB L1 and 64 KB L2, B from memory, B-stationary (the old "B" order; the
rewrite's weight-stationary reproduces its reads, output-stationary does not).

reads  = L1 misses * 64 B   (old: L1 BytesIn)
writes = L1 writebacks * 64 (old: L1 BytesOut, which included an end-of-run
         flush of dirty lines; the rewrite doesn't flush)

run:  .venv/bin/python experiments/rewrite/paper_traffic.py
"""

import math

from harness import out_dir, pct, run_many
from old_results import load

NAME = "paper_traffic"
OLD = "v5-results/paper-model/paper-traffic-model"
FLAGS = {"b_source": "mem", "stationary": "B", "three_d_reg": True}  # not stored
LINE = 64
M = N = K = 256
A_P = 8
SLIDE_SAVING = {1.0: 0.00, 0.5: 0.00, 0.25: 0.18, 0.125: 0.36}  # empirical, slide


def main() -> None:
    out = out_dir(NAME)
    cells = load(OLD, default_flags=FLAGS)
    assert all(c.params for c in cells), {c.unsupported for c in cells}
    new = run_many([c.params for c in cells], out / "results.json")

    rows = []
    for c, s in zip(cells, new):
        o = c.overrides
        tm, tn, b_p = o["TILE_M"], o["TILE_N"], o["B_PRECISION_BYTES"]
        rows.append({
            "rho": b_p / A_P, "area": tm * tn, "tm": tm, "tn": tn,
            "old_r": c.metrics["l1"]["bytes_in"],
            "new_r": s["CacheUnit: L1 misses"] * LINE,
            "old_w": c.metrics["l1"]["bytes_out"],
            "new_w": s["CacheUnit: L1 writebacks"] * LINE,
        })
    rhos = sorted({r["rho"] for r in rows}, reverse=True)
    areas = sorted({r["area"] for r in rows}, reverse=True)

    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), ""]

    exact = sum(r["old_r"] == r["new_r"] for r in rows)
    worst = max(rows, key=lambda r: abs(r["new_r"] / r["old_r"] - 1))
    lines += ["## Summary", "",
              f"- reads identical in **{exact}/{len(rows)}** cells; worst "
              f"{pct(worst['new_r'], worst['old_r'])} "
              f"(rho={worst['rho']:g}, {worst['tm']}x{worst['tn']})", ""]

    # optimum aspect ratio
    lines += ["## Optimal aspect ratio T_N/T_M (argmin of reads per family)", "",
              "| rho | area | old | new | predicted 1/rho |", "|---|---|---|---|---|"]
    for rho in rhos:
        for area in areas:
            fam = [r for r in rows if r["rho"] == rho and r["area"] == area]
            ob = min(fam, key=lambda r: r["old_r"])
            nb = min(fam, key=lambda r: r["new_r"])
            lines.append(f"| {rho:g} | {area} | {ob['tn'] / ob['tm']:g} "
                         f"| {nb['tn'] / nb['tm']:g} | {1 / rho:g} |")

    # savings vs square, 1024-word family (the slide's table)
    lines += ["", "## Saving vs square 32x32 tile (1024-word family): the slide table", "",
              "| rho | slide (empirical) | old recomputed | new | theory 1-2sqrt(rho)/(1+rho) |",
              "|---|---|---|---|---|"]
    for rho in rhos:
        fam = [r for r in rows if r["rho"] == rho and r["area"] == 1024]
        sq = next(r for r in fam if r["tm"] == r["tn"] == 32)
        old_s = 1 - min(r["old_r"] for r in fam) / sq["old_r"]
        new_s = 1 - min(r["new_r"] for r in fam) / sq["new_r"]
        theory = 1 - 2 * math.sqrt(rho) / (1 + rho)
        lines.append(f"| {rho:g} | {SLIDE_SAVING[rho]:.0%} | {old_s:.1%} "
                     f"| {new_s:.1%} | {theory:.1%} |")

    # every cell
    lines += ["", "## All cells", "",
              "| rho | TM x TN | old reads | new reads | diff | old writes | new writes | diff |",
              "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (-r["rho"], -r["area"], -r["tm"])):
        lines.append(f"| {r['rho']:g} | {r['tm']}x{r['tn']} | {r['old_r']:,} "
                     f"| {r['new_r']:,.0f} | {pct(r['new_r'], r['old_r'])} "
                     f"| {r['old_w']:,} | {r['new_w']:,.0f} | {pct(r['new_w'], r['old_w'])} |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
