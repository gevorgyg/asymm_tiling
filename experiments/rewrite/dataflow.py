"""Re-run of pre-rewrite v55-results/b-stationary-vs-c-stationry-col-major.

Slide "B-Stationary: TM-Fold Register Reuse": the table "C-stationary 1.7x
faster (gc=0), 1.4x faster (gc=10), 7.1x slower (gc=100)", which is this
experiment at the fixed tile TM=64, TN=32 (recomputed: 1.75 / 1.36 / 7.19).
FIFO, M=192, N=K=256, 4-byte elements, fully associative 16 KB L1, no L2,
mulacc not counted.

The old C-stationary FIFO here is the col_major_fifo variant (B regenerated
per register row block, no discarded elements). The rewrite's output-
stationary FIFO pops exactly the elements it uses, so it generates the same
number of B elements per tile.

run:  .venv/bin/python experiments/rewrite/dataflow.py
"""

from harness import out_dir, run_many
from old_results import load

NAME = "dataflow"
OLD = "v55-results/b-stationary-vs-c-stationry-col-major"
SLIDE_TILE = (64, 32)
SLIDE = {0: "1.7x faster", 10: "1.4x faster", 100: "7.1x slower"}


def ratio_text(b: float, c: float) -> str:
    """How C-stationary compares to B-stationary."""
    return f"{b / c:.2f}x faster" if c < b else f"{c / b:.2f}x slower"


def main() -> None:
    out = out_dir(NAME)
    cells = [c for c in load(OLD) if c.params]
    new = run_many([c.params for c in cells], out / "results.json")

    cyc = {}      # (version, l1 KB, mode, gc, tm, tn) -> cycles
    fills = []    # (l1 KB, mode, old, new) L1 traffic
    for c, s in zip(cells, new):
        o = c.overrides
        mode = "B" if c.flags["stationary"] == "B" else "C"
        l1 = o["L1_SIZE_BYTES"] // 1024
        key = (l1, mode, o["PRNG_FIFO_GEN_COST"], o["TILE_M"], o["TILE_N"])
        assert ("old",) + key not in cyc, key
        cyc[("old",) + key] = c.metrics["cycles"]
        cyc[("new",) + key] = s["Simulation: Total cycles"]
        fills.append((l1, mode, c.metrics["l1"]["line_fills"], s["CacheUnit: L1 misses"]))

    l1s = sorted({k[1] for k in cyc})
    gcs = sorted({k[3] for k in cyc})
    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), "",
             "The experiment also sweeps the L1 size (16 / 32 / 64 KB, fully "
             "associative); every table is per L1 size.", "", "## Traffic", "",
             "| L1 | dataflow | L1 misses identical | worst diff |", "|---|---|---|---|"]
    for l1 in l1s:
        for mode in ("B", "C"):
            f = [(o, n) for s, m, o, n in fills if s == l1 and m == mode]
            exact = sum(o == n for o, n in f)
            worst = max(abs(n / o - 1) for o, n in f)
            lines.append(f"| {l1} KB | {mode}-stationary | {exact}/{len(f)} | {worst:.2%} |")

    tm, tn = SLIDE_TILE
    lines += ["", f"## The slide table (fixed tile TM={tm}, TN={tn})", "",
              "| L1 | gc | slide | old recomputed | new |", "|---|---|---|---|---|"]
    for l1 in l1s:
        for gc in gcs:
            vals = [ratio_text(cyc[(v, l1, "B", gc, tm, tn)], cyc[(v, l1, "C", gc, tm, tn)])
                    for v in ("old", "new")]
            lines.append(f"| {l1} KB | {gc} | {SLIDE.get(gc, '')} | {vals[0]} | {vals[1]} |")

    lines += ["", "## Best tile of each dataflow vs best tile of the other", "",
              "| L1 | gc | old: best B / best C | old C vs B | new: best B / best C | new C vs B |",
              "|---|---|---|---|---|---|"]
    for l1 in l1s:
        for gc in gcs:
            row = [f"{l1} KB", str(gc)]
            for v in ("old", "new"):
                best = {}
                for mode in ("B", "C"):
                    ks = [k for k in cyc if k[:4] == (v, l1, mode, gc)]
                    best[mode] = min(ks, key=lambda k: cyc[k])
                row += [f"{best['B'][4:]} / {best['C'][4:]}",
                        ratio_text(cyc[best["B"]], cyc[best["C"]])]
            lines.append("| " + " | ".join(row) + " |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Traffic"):]))


if __name__ == "__main__":
    main()
