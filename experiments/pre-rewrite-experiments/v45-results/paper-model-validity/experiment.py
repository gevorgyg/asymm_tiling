"""Where does the paper's fast-memory abstraction break on a real cache?

The paper assumes a fast memory of M words that holds the whole C block
while A/B stream through. On a real cache this works only while the C tile
(plus stream slices) fits; past that, traffic explodes. Fixing the aspect at
the predicted optimum (T_N/T_M = 1/ρ = 4) and growing the C-tile budget
across two L1 sizes and two associativities shows the breakdown point as
measured/predicted L1 BytesIn peeling away from 1.
"""

import math
from pathlib import Path

from experiments.harness import (
    Cell, Flags, METRICS, describe_changes, lineplot, paper_model,
    plot_metric_family, run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

# Wide N so the largest aspect-4 C tile (256×1024 = 2 MB) still fits the matrix
# and reaches log2(C-tile / 16K L1) = 7.
M, N, K = 256, 1024, 128
A_P, B_P = 8, 2          # rho = 1/4, predicted optimal aspect = 4
LINE = 64

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": A_P, "B_PRECISION_BYTES": B_P,
    "L1_LINE_SIZE_BYTES": LINE, "L2_LINE_SIZE_BYTES": LINE,
    "L2_ACCESS_CYCLES": 14,
    "TILE_K": K,
}

# aspect 4 throughout; C-tile bytes = T_M*T_N*8 → log2(bytes/16K) runs -5..7
TILES = [(4, 16), (8, 32), (16, 64), (32, 128), (64, 256), (128, 512), (256, 1024)]
L1_SIZES = [16384, 65536]                                     # L2 = 4×L1

FLAGS = Flags(b_source="mem", stationary="C", three_d_reg=True)


def _regimes(l1: int) -> list[tuple[str, dict]]:
    l2 = 4 * l1
    common = {"L1_SIZE_BYTES": l1, "L2_SIZE_BYTES": l2}
    return [
        (f"fully-assoc, L1={l1 // 1024}K",
         {**common, "L1_ASSOC": l1 // LINE, "L2_ASSOC": l2 // LINE}),
        (f"8-way, L1={l1 // 1024}K",
         {**common, "L1_ASSOC": 8, "L2_ASSOC": 8}),
    ]


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    records: list[dict] = []
    for l1 in L1_SIZES:
        for regime, regime_over in _regimes(l1):
            print(f"\n--- {regime} ---")
            for tm, tn in TILES:
                duals = run_grid_dual(
                    experiment_dir=EXPERIMENT_DIR,
                    base_config_text=base,
                    base_overrides={**BASE_OVERRIDES, **regime_over,
                                    "TILE_M": tm, "TILE_N": tn},
                    flags=FLAGS,
                )
                d = duals[0]
                predicted = paper_model.reads_bytes_line_aware(
                    M, N, K, tm, tn, A_P, B_P, A_P, LINE)
                records.append({
                    "regime": regime, "l1": l1, "tm": tm, "tn": tn,
                    "budget_frac": tm * tn * A_P / l1,
                    "excess": d.traffic.l1.bytes_in / predicted,
                    "d": d,
                })

    caption = describe_changes(
        {k: v for k, v in BASE_OVERRIDES.items() if k != "TILE_K"}, base,
        extras={"TILE_K": K, "aspect": "T_N/T_M = 4 (predicted optimum)"},
    )

    series = {
        regime: sorted((math.log2(r["budget_frac"]), r["excess"])
                       for r in records if r["regime"] == regime)
        for regime in {r["regime"] for r in records}
    }
    lineplot(
        dict(sorted(series.items())),
        out_path=EXPERIMENT_DIR / "excess_vs_budget.png",
        hlines={"paper model exact (excess = 1)": 1.0},
        ref_vlines={"C tile = L1 (predicted breakdown)": 0.0},
        xlabel="log₂(C-tile bytes / L1 bytes)",
        ylabel="measured / predicted L1 BytesIn",
        title="Fast-memory model validity: traffic excess vs C-tile budget\n" + caption,
    )

    cells = [Cell(x=math.log2(r["budget_frac"]), series=r["regime"],
                  traffic=r["d"].traffic, cycles=r["d"].cycles)
             for r in records]
    plot_metric_family(
        cells, out_dir=EXPERIMENT_DIR, base_name="model_validity",
        title="Model-validity sweep (aspect fixed at predicted optimum)",
        caption=caption, xlabel="log₂(C-tile bytes / L1 bytes)",
        ref_vlines={"C tile = L1 (predicted breakdown)": 0.0},
    )

    lines = [f"Non-default config: {caption}\n",
             "Prediction = line-aware paper formula; excess of 1.0 means the "
             "two-level model holds exactly.\n",
             "![excess](excess_vs_budget.png)\n"]
    lines.append("\n## Traffic excess (measured / predicted L1 BytesIn)\n")
    lines.append("| regime | " + " | ".join(
        f"{tm}×{tn} ({tm * tn * A_P // 1024 or tm * tn * A_P}"
        f"{'K' if tm * tn * A_P >= 1024 else 'B'} C tile)"
        for tm, tn in TILES) + " |")
    lines.append("|---|" + "---|" * len(TILES))
    for regime in sorted({r["regime"] for r in records}):
        rs = {(r["tm"], r["tn"]): r["excess"] for r in records
              if r["regime"] == regime}
        lines.append(f"| {regime} | " + " | ".join(
            f"{rs[t]:.2f}" for t in TILES) + " |")
    for k in METRICS:
        lines.append(f"\n![{k}](model_validity_{k}.png)")
    write_report(EXPERIMENT_DIR / "README.md",
                 "paper-model-validity", ["\n".join(lines)])
