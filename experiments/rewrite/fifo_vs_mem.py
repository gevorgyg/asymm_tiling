"""Re-run of pre-rewrite v5-results/math-model-no-l2/e13-fifo-vs-mem (with the
FIFO side from e8-gc-boundary-sweep).

Slides/charts: fifo_vs_mem_gc ("FIFO beats memory up to gc* ~ 200", TN=32),
fifo_adv_tn / fifo_vs_mem_tn (FIFO speedup over memory-B at gc=0 per TN).
M=192, N=K=256, 4-byte elements, fully associative 16 KB L1, no L2, mulacc
not counted. FIFO side: best TM per TN, B-stationary.

NOT a like-for-like re-run of the memory side: the old memory-B baseline was
A-register-stationary (pre-3b03ded "C" with B from memory), a dataflow the
rewrite doesn't have. The rewrite's baseline here is B-stationary with B from
memory on the same TM x TN grid. Compare the conclusions, not the numbers.

run:  .venv/bin/python experiments/rewrite/fifo_vs_mem.py
"""

from dataclasses import replace

from harness import out_dir, run_many
from old_results import load, to_params

NAME = "fifo_vs_mem"
OLD_MEM = "v5-results/math-model-no-l2/e13-fifo-vs-mem"
OLD_FIFO = "v5-results/math-model-no-l2/e8-gc-boundary-sweep"
MEM_FLAGS = {"b_source": "mem", "stationary": "B", "three_d_reg": True,
             "mulac_norecord": True, "no_l2": True}
FIFO_GC = [0, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 250, 300, 400]
TN_GC = 32   # the gc-sweep chart is at TN = 32
MNK = 192 * 256 * 256


def crossover(fifo: dict[int, float], mem: float) -> str:
    """First gc at which the best FIFO tile is slower than memory-B."""
    gcs = sorted(fifo)
    for lo, hi in zip(gcs, gcs[1:]):
        if fifo[lo] <= mem < fifo[hi]:
            g = lo + (mem - fifo[lo]) / (fifo[hi] - fifo[lo]) * (hi - lo)
            return f"≈ {g:.0f} (between {lo} and {hi})"
    return "none in range" if fifo[gcs[-1]] <= mem else f"< {gcs[0]}"


def main() -> None:
    out = out_dir(NAME)
    mem_cells = load(OLD_MEM)
    fifo_cells = [c for c in load(OLD_FIFO) if c.overrides["PRNG_FIFO_GEN_COST"] == 0]

    mem_params = [to_params(c.overrides, MEM_FLAGS) for c in mem_cells]
    fifo_params = [replace(c.params, gen_cost=g) for g in FIFO_GC for c in fifo_cells]
    res = run_many(mem_params + fifo_params, out / "results.json")

    tns = sorted({c.overrides["TILE_N"] for c in mem_cells})

    # memory-B: best alpha per TN (old A-stationary, new B-stationary)
    mem = {"old": {}, "new": {}}
    for c, p, s in zip(mem_cells, mem_params, res):
        tn = c.overrides["TILE_N"]
        for v, a in (("old", c.metrics["cycles"] / MNK),
                     ("new", s["Simulation: Total cycles"] / MNK)):
            mem[v][tn] = min(mem[v].get(tn, a), a)

    # FIFO: best alpha per (TN, gc); old from the e8 results, new from the runs
    fifo = {"old": {}, "new": {}}
    for c in load(OLD_FIFO):
        key = (c.overrides["TILE_N"], c.overrides["PRNG_FIFO_GEN_COST"])
        a = c.metrics["cycles"] / MNK
        fifo["old"][key] = min(fifo["old"].get(key, a), a)
    for p, s in zip(fifo_params, res[len(mem_params):]):
        key, a = (p.tile_w, p.gen_cost), s["Simulation: Total cycles"] / MNK
        fifo["new"][key] = min(fifo["new"].get(key, a), a)

    lines = [f"# {NAME}: rewrite vs pre-rewrite", "", __doc__.strip(), "",
             "## FIFO advantage over memory-B at gc = 0, per TN (fifo_adv_tn)", "",
             "| TN | old mem (A-stat) | old FIFO | old advantage | new mem (B-stat) "
             "| new FIFO | new advantage |", "|---|---|---|---|---|---|---|"]
    for tn in tns:
        row = [str(tn)]
        for v in ("old", "new"):
            m, f = mem[v][tn], fifo[v][(tn, 0)]
            row += [f"{m:.3f}", f"{f:.3f}", f"{(m - f) / m:.0%}"]
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", f"## Crossover gc* at TN = {TN_GC} (fifo_vs_mem_gc; slide: ≈ 200)", ""]
    for v in ("old", "new"):
        f = {g: a for (tn, g), a in fifo[v].items() if tn == TN_GC}
        lines.append(f"- **{v}**: memory-B alpha {mem[v][TN_GC]:.3f}, crossover "
                     f"{crossover(f, mem[v][TN_GC])}")
    lines += ["", f"### Best FIFO alpha vs gc at TN = {TN_GC}", "",
              "| gc | old | new |", "|---|---|---|"]
    for g in sorted({g for (_, g) in fifo["old"]} | set(FIFO_GC)):
        o = fifo["old"].get((TN_GC, g))
        n = fifo["new"].get((TN_GC, g))
        lines.append(f"| {g} | {'·' if o is None else f'{o:.3f}'} "
                     f"| {'·' if n is None else f'{n:.3f}'} |")

    (out / "README.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("## FIFO advantage over memory-B at gc = 0, per TN (fifo_adv_tn)"):]))


if __name__ == "__main__":
    main()
