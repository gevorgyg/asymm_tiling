"""Compare LRU / FIFO / MRU / Random across tile shapes (see WRITEUP.md)."""

import json
from collections import Counter
from pathlib import Path

from experiments.harness import (
    Flags, PALETTE_POLICY, Result, grid_plot, run_grid,
    summarize_config, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "PRNG_FIFO_CAPACITY": 64, "PRNG_FIFO_GEN_COST": 10,
    "TILE_K": 96,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

POLICIES = ["LRU", "FIFO", "MRU", "Random"]
PRECISIONS = [
    ("Symmetric Double", {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 8}),
    ("Asymmetric",       {"A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2}),
]
STATIONARY = ["C", "B"]
B_SOURCE = ["mem", "prng_fifo"]
TILE_DIMS = [4, 8, 12, 16, 24, 32, 48, 96]


def _plot_scatter(by_axis: dict, out: Path) -> None:
    markers = {"C": "o", "B": "x"}

    def panel_fn(ax, key, records):
        for policy in POLICIES:
            for stat in STATIONARY:
                pts = [(r["l1_line_fills"], r["cycles"]) for r in records
                       if r["policy"] == policy and r["stationary"] == stat]
                if not pts:
                    continue
                xs, ys = zip(*pts)
                ax.scatter(xs, ys, c=PALETTE_POLICY[policy], marker=markers[stat],
                           s=18, alpha=0.55, label=f"{policy}/{stat}")
        ax.set_xlabel("L1 LineFills")
        ax.set_ylabel("Cycles")
        ax.set_title(str(key))
        ax.grid(True, ls=":", alpha=0.5)
        if "Symmetric Double" in str(key) and "mem" in str(key):
            ax.legend(fontsize=7, ncol=2)

    panels = {str(k): v for k, v in sorted(by_axis.items())}
    # policy is the swept axis; matrix + cache geometry is fixed
    summary = summarize_config(
        {k: v for k, v in BASE_OVERRIDES.items()
         if not k.endswith("_REPLACEMENT_POLICY")
         and k not in ("A_PRECISION_BYTES", "B_PRECISION_BYTES")}
    )
    grid_plot(panels, panel_fn=panel_fn, out_path=out, ncols=2,
              subplot_size=(7, 4),
              title=f"Pareto: cycles vs L1 LineFills, per (precision, B-source)\n{summary}")


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    all_records: list[dict] = []

    for prec_name, prec_over in PRECISIONS:
        for stat in STATIONARY:
            for bsrc in B_SOURCE:
                for policy in POLICIES:
                    print(f"\n--- {prec_name}/{stat}-stationary/{bsrc}/{policy} ---")
                    overrides = {
                        **BASE_OVERRIDES, **prec_over,
                        "L1_REPLACEMENT_POLICY": policy,
                        "L2_REPLACEMENT_POLICY": policy,
                    }
                    flags = Flags(b_source=bsrc, stationary=stat, three_d_reg=True)
                    results = run_grid(
                        experiment_dir=EXPERIMENT_DIR,
                        base_config_text=base,
                        base_overrides=overrides,
                        sweep_axes={"TILE_M": TILE_DIMS, "TILE_N": TILE_DIMS},
                        flags=flags,
                        cache_path=EXPERIMENT_DIR / f"results_{prec_name.replace(' ', '_')}_{stat}_{bsrc}_{policy}.json",
                    )
                    for r in results:
                        all_records.append({
                            "precision": prec_name,
                            "stationary": stat,
                            "b_source": bsrc,
                            "policy": policy,
                            "tile_m": int(r.overrides["TILE_M"]),
                            "tile_n": int(r.overrides["TILE_N"]),
                            "cycles": r.metrics.cycles,
                            "l1_line_fills": r.metrics.l1.line_fills,
                            "l1_hit_rate": r.metrics.l1.hit_rate,
                        })

    # group for scatter
    by_axis = {}
    for r in all_records:
        key = (r["precision"], r["b_source"])
        by_axis.setdefault(key, []).append(r)
    _plot_scatter(by_axis, EXPERIMENT_DIR / "pareto_scatter.png")

    # winners table: per (prec, stationary, b_source), count cells where each policy is cycle-min
    winners = Counter()
    by_cell = {}
    for r in all_records:
        cell_key = (r["precision"], r["stationary"], r["b_source"], r["tile_m"], r["tile_n"])
        if cell_key not in by_cell or r["cycles"] < by_cell[cell_key]["cycles"]:
            by_cell[cell_key] = r
    for r in by_cell.values():
        winners[(r["precision"], r["stationary"], r["b_source"], r["policy"])] += 1

    lines: list[str] = []
    lines.append("# policy-pareto\n")
    lines.append("![Pareto scatter](pareto_scatter.png)\n")
    lines.append("\n## Cycle-minimum policy per (precision / stationary / B-source) — count over 64 tile shapes\n")
    lines.append("| precision | stationary | B source | LRU | FIFO | MRU | Random |")
    lines.append("|---|---|---|---|---|---|---|")
    for prec, _ in PRECISIONS:
        for stat in STATIONARY:
            for bsrc in B_SOURCE:
                row = [winners.get((prec, stat, bsrc, p), 0) for p in POLICIES]
                lines.append(f"| {prec} | {stat} | {bsrc} | {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    write_report(EXPERIMENT_DIR / "README.md", "policy-pareto", lines)

    (EXPERIMENT_DIR / "records.json").write_text(json.dumps(all_records, indent=2))
