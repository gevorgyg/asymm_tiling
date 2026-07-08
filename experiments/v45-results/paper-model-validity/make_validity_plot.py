"""Regenerate excess_vs_budget plot including the L1=32K series."""

import json, math
from pathlib import Path
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent

M = N = K = 256
A_P, B_P = 8, 2
LINE = 64

# line-aware prediction (same as paper_model.reads_bytes_line_aware)
def reads_line_aware(m, n, k, tm, tn, ap, bp, cp, line):
    def rl(seg): return line * math.ceil(seg / line)
    blocks = (m // tm) * (n // tn)
    return blocks * (tm * rl(k * ap) + k * rl(tn * bp) + tm * rl(tn * cp))


def load_records():
    with open(HERE / "results.json") as f:
        raw = json.load(f)
    records = []
    for entry in raw.values():
        ov = entry["overrides"]
        if ov.get("A_PRECISION_BYTES") != A_P or ov.get("B_PRECISION_BYTES") != B_P:
            continue
        l1 = ov["L1_SIZE_BYTES"]
        if l1 not in (16384, 65536):
            continue
        tm, tn = ov["TILE_M"], ov["TILE_N"]
        assoc = ov["L1_ASSOC"]
        regime_type = "fully-assoc" if assoc == l1 // LINE else "8-way"
        predicted = reads_line_aware(M, N, K, tm, tn, A_P, B_P, A_P, LINE)
        records.append({
            "regime_type": regime_type,
            "l1_kb": l1 // 1024,
            "label": f"{regime_type}, L1={l1//1024}K",
            "budget": math.log2(tm * tn * A_P / l1),
            "excess": entry["metrics"]["l1"]["bytes_in"] / predicted,
        })
    return records


def make_plot(records):
    # group by label, sort by budget
    by_label = defaultdict(list)
    for r in records:
        by_label[r["label"]].append((r["budget"], r["excess"]))
    for k in by_label:
        by_label[k].sort()

    # style: color = L1 size, linestyle = regime
    l1_colors = {16: "#1f77b4", 32: "#ff7f0e", 64: "#2ca02c"}
    regime_ls  = {"fully-assoc": "-", "8-way": "--"}
    regime_marker = {"fully-assoc": "o", "8-way": "s"}

    fig, ax = plt.subplots(figsize=(9, 5.5))

    for label in sorted(by_label):
        pts = by_label[label]
        xs, ys = zip(*pts)
        # parse label
        regime_type = "fully-assoc" if "fully-assoc" in label else "8-way"
        l1_kb = int(label.split("L1=")[1].replace("K", ""))
        ax.plot(xs, ys,
                linestyle=regime_ls[regime_type],
                marker=regime_marker[regime_type],
                ms=7, lw=1.8,
                color=l1_colors[l1_kb],
                label=label,
                zorder=3)

    ax.axhline(1.0, color="#555555", ls="--", lw=1.3,
               label="paper model exact (excess = 1)", zorder=2)
    ax.axvline(0.0, color="#888888", ls="-.", lw=1.3,
               label="C tile = L1 (predicted breakdown)", zorder=2)

    ax.set_xlabel("log₂(C-tile bytes / L1 bytes)", fontsize=11)
    ax.set_ylabel("measured / predicted L1 BytesIn", fontsize=11)
    ax.set_title(
        "Fast-memory model validity: traffic excess vs C-tile budget\n"
        "m=n=k=256, ρ=¼, aspect T_N/T_M=4 (predicted optimum), outer-products order",
        fontsize=10,
    )
    ax.tick_params(labelsize=9)
    ax.grid(True, ls=":", alpha=0.4)
    ax.legend(fontsize=8.5, loc="upper left", framealpha=0.9)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    out = HERE / "excess_vs_budget.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    make_plot(load_records())
