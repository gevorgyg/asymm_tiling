"""Recreate the B/A balance plot with a true log y-scale."""

import json, math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

HERE = Path(__file__).resolve().parent

PALETTE = {1.0: "#636EFA", 0.5: "#00CC96", 0.25: "#EF553B", 0.125: "#AB63FA"}
RHOS = [1.0, 0.5, 0.25, 0.125]


def load():
    with open(HERE / "trace_results.json") as f:
        raw = json.load(f)
    records = []
    for key, v in raw.items():
        # key format: "rho=X|TMxTN"
        rho_part, tile_part = key.split("|")
        rho = float(rho_part.split("=")[1])
        tm, tn = [int(x) for x in tile_part.split("x")]
        a_in = v["A"]["bytes_in"]
        b_in = v["B"]["bytes_in"]
        records.append({
            "rho": rho, "tm": tm, "tn": tn,
            "ratio_log2": math.log2(tn / tm),
            "b_over_a": b_in / a_in,
        })
    return records


def make_plot(records):
    fig, ax = plt.subplots(figsize=(8, 5))

    for rho in RHOS:
        pts = sorted(
            (r["ratio_log2"], r["b_over_a"])
            for r in records if r["rho"] == rho
        )
        xs, ys = zip(*pts)
        ax.plot(xs, ys, "o-", color=PALETTE[rho], ms=7, lw=1.8,
                label=f"ρ = {rho:g}", zorder=3)

        # vertical line at predicted optimum
        opt = math.log2(1.0 / rho)
        ax.axvline(opt, color=PALETTE[rho], ls="--", lw=1.0, alpha=0.55, zorder=1)

    # B = A reference
    ax.axhline(1.0, color="#888888", ls="-", lw=1.4, label="B = A", zorder=2)

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(
        lambda y, _: f"{y:g}" if y >= 1 else f"1/{int(round(1/y))}" if abs(1/y - round(1/y)) < 0.01 else f"{y:.3f}"
    ))

    ax.set_xlabel("log₂(T_N / T_M)", fontsize=11)
    ax.set_ylabel("B BytesIn / A BytesIn", fontsize=11)
    ax.set_title(
        "AM-GM balance: input traffic ratio, crossing 1 at the predicted optimum\n"
        "m=n=k=128, T_K=128, fully-associative, outer-products order",
        fontsize=10,
    )
    ax.tick_params(labelsize=9)
    ax.grid(True, which="both", ls=":", alpha=0.4)
    ax.legend(fontsize=10, loc="upper left", framealpha=0.9)

    fig.tight_layout()
    out = HERE / "fa_balance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    make_plot(load())
