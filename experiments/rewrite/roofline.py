"""Re-run of pre-rewrite v55-results/best-fifo-order-fifo-cap-vs-l1-size.

Slide "Roofline Validation: Results": (TM*, TN*) predicted exactly in
108/108 conditions. 12 hardware configs (a 64 KB or 128 KB SRAM budget split
between a fully associative L1 of 8, 24, 40 ... KB and the FIFO) x 9 gc
values. B-stationary, FIFO, M=192, N=K=256, 4-byte elements, no L2,
mulacc not counted.

Per config: calibrate alpha(TM, TN) at gc = 0, predict
argmin max(alpha, gc/TM) over the safe tiles (ties to the lower alpha, as
the old validation did), and compare with the empirically best safe tile. safe = old ws_lines < 300 and K*TN <= FIFO
capacity (as in the old experiment).

run:  .venv/bin/python experiments/rewrite/roofline.py
"""

from collections import defaultdict

from harness import out_dir, run_many
from old_results import load

NAME = "roofline"
OLD = "v55-results/best-fifo-order-fifo-cap-vs-l1-size"
K = 256


def safe(tm: int, tn: int, fifo_cap: int) -> bool:
    return tm * tn // 8 + tm // 4 - 2 < 300 and K * tn <= fifo_cap


def validate(cyc: dict) -> dict:
    """cyc[(l1, cap)][gc][(tm, tn)] -> cycles. Per-condition results."""
    out = {}
    for split, by_gc in cyc.items():
        cal = by_gc[0]
        for gc, tiles in by_gc.items():
            if gc == 0:
                continue
            cands = [t for t in tiles if t in cal and safe(*t, split[1])]
            # ties (gc/TM dominating for several TN at the same TM) go to the
            # lower alpha, i.e. less residual A-load cost, as in the old
            # validate_roofline
            pred = min(cands, key=lambda t: (max(cal[t], gc / t[0]), cal[t]))
            best = min(cands, key=lambda t: tiles[t])
            out[(split, gc)] = (pred, best, tiles[pred] / tiles[best] - 1, len(cands))
    return out


def main() -> None:
    out = out_dir(NAME)
    cells = load(OLD)
    assert all(c.params for c in cells), {c.unsupported for c in cells}
    new = run_many([c.params for c in cells], out / "results.json")

    mnk = 192 * 256 * K
    cyc = {"old": defaultdict(lambda: defaultdict(dict)),
           "new": defaultdict(lambda: defaultdict(dict))}
    for c, s in zip(cells, new):
        o = c.overrides
        split = (o["L1_SIZE_BYTES"] // 1024, o["PRNG_FIFO_CAPACITY"])
        tile = (o["TILE_M"], o["TILE_N"])
        gc = o["PRNG_FIFO_GEN_COST"]
        cyc["old"][split][gc][tile] = c.metrics["cycles"] / mnk
        cyc["new"][split][gc][tile] = s["Simulation: Total cycles"] / mnk

    res = {v: validate(cyc[v]) for v in ("old", "new")}

    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), "", "## Summary", ""]
    for v in ("old", "new"):
        r = res[v]
        exact = sum(p == b for p, b, _, _ in r.values())
        tm_ok = sum(p[0] == b[0] for p, b, _, _ in r.values())
        gaps = [g for p, b, g, _ in r.values() if p != b]
        distinct = len({b for _, b, _, _ in r.values()})
        lines.append(
            f"- **{v}**: (TM*, TN*) exact {exact}/{len(r)}, TM* right {tm_ok}/{len(r)}"
            + (f", worst gap when wrong {max(gaps):.2%}" if gaps else "")
            + f"; {distinct} distinct optimal tiles")

    lines += ["", "## Per condition (predicted / empirical best; ✓ = exact)", "",
              "| L1 KB | FIFO | gc | old | new |", "|---|---|---|---|---|"]
    for key in sorted(res["old"]):
        (l1, cap), gc = key
        cols = []
        for v in ("old", "new"):
            p, b, g, _ = res[v][key]
            cols.append(f"{p} ✓" if p == b else f"{p} / {b} (+{g:.1%})")
        lines.append(f"| {l1} | {cap} | {gc} | {cols[0]} | {cols[1]} |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## Summary"):lines.index("## Summary") + 4]))


if __name__ == "__main__":
    main()
