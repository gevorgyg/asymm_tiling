"""F4c: where do B-stationary and C-stationary cross, for other register
blocks and MAC costs? (report: B-Stationary Against C-Stationary)

C-stationary regenerates B for every register block of R_M rows, so its
generation cost per MAC is gc / R_M, while B-stationary's is gc / T_M. With
free generation both are limited by memory (alpha_B, alpha_C), so C-stationary
should stay faster only while gc / R_M < alpha_B:  gc* = R_M * alpha_B.

Tile 64 x 32 (as fig_dataflow), default setup otherwise (16 KB fully
associative L1, no L2, 192x256x256). mulacc_cost is charged per register-block
multiply (R^3 MACs), so the cost per MAC is mulacc_cost / R^3.

run:  .venv/bin/python experiments/rewrite/dataflow_crossover.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many

NAME = "dataflow_crossover"
TM, TN = 64, 32
MNK = 192 * 256 * 256
GC = list(range(0, 41))
CONFIGS = {   # name: (register block R, MAC cost per MAC)
    "R 2": (2, 0),
    "R 4": (4, 0),
    "R 8": (8, 0),
    "R 16": (16, 0),
    "R 4, 1 cycle / MAC": (4, 1),
}
FLOWS = {"B": "weight", "C": "output"}


def main() -> None:
    params = [replace(Params(l1_assoc=-1), tile_h=TM, tile_w=TN, reg_dim=r,
                      mulacc_cost=m * r ** 3, orientation=o, gen_cost=gc)
              for r, m in CONFIGS.values() for o in FLOWS.values() for gc in GC]
    stats = run_many(params, out_dir(NAME) / "results.json")
    t = {(p.reg_dim, p.mulacc_cost, p.orientation, p.gen_cost):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}

    lines = ["| config | alpha_B | alpha_C | predicted gc* = R alpha_B | measured crossover |",
             "|---|---|---|---|---|"]
    for name, (r, m) in CONFIGS.items():
        c = m * r ** 3
        b = {gc: t[(r, c, "weight", gc)] for gc in GC}
        cs = {gc: t[(r, c, "output", gc)] for gc in GC}
        cross = next((gc for gc in GC if cs[gc] > b[gc]), None)
        cross_txt = ("C faster at every gc" if cross is None else
                     "B faster from gc 0" if cross == 0 else f"between {cross - 1} and {cross}")
        lines.append(f"| {name} | {b[0]:.3f} | {cs[0]:.3f} | {r * b[0]:.1f} | {cross_txt} |")
    report = (f"# {NAME}: B- vs C-stationary crossover, tile {TM}x{TN}\n\n" +
              "\n".join(lines) + "\n")
    (out_dir(NAME) / "README.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
