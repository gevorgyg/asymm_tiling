"""Generate fully-associative-only reads and writes plots for the presentation."""

import json, math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

HERE = Path(__file__).resolve().parent

M = N = K = 256
A_P = 8
LINE = 64
FAMILIES = {
    1024: [(256, 4), (128, 8), (64, 16), (32, 32), (16, 64), (8, 128), (4, 256)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
RHOS = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
PALETTE = {1.0: "#636EFA", 0.5: "#00CC96", 0.25: "#EF553B", 0.125: "#AB63FA"}
FAMILY_MARKERS = {1024: "o", 512: "s"}
FA_ASSOC = 16384 // LINE  # 256 ways

def reads_word(m, n, k, tm, tn, ap, bp, cp):
    return m * n * k * (ap / tn + bp / tm) + m * n * cp

def reads_line_aware(m, n, k, tm, tn, ap, bp, cp, line):
    def rl(seg): return line * math.ceil(seg / line)
    blocks = (m // tm) * (n // tn)
    return blocks * (tm * rl(k * ap) + k * rl(tn * bp) + tm * rl(tn * cp))

def writes_word(m, n, cp): return m * n * cp

def writes_line_aware(m, n, tm, tn, cp, line):
    def rl(seg): return line * math.ceil(seg / line)
    return (m // tm) * (n // tn) * tm * rl(tn * cp)


def load_records():
    with open(HERE / "results.json") as f:
        raw = json.load(f)
    records = []
    for entry in raw.values():
        ov = entry["overrides"]
        if ov.get("L1_ASSOC", 0) != FA_ASSOC:
            continue
        tm = ov["TILE_M"]
        tn = ov["TILE_N"]
        bp = ov["B_PRECISION_BYTES"]
        rho = bp / A_P
        area = tm * tn
        if area not in FAMILIES:
            continue
        records.append({
            "rho": rho, "bp": bp, "area": area, "tm": tm, "tn": tn,
            "ratio": math.log2(tn / tm),
            "bytes_in":  entry["metrics"]["l1"]["bytes_in"],
            "bytes_out": entry["metrics"]["l1"]["bytes_out"],
        })
    return records


def make_panel(ax, records, rho, bp, metric):
    color = PALETTE[rho]

    for area, tiles in FAMILIES.items():
        pts = sorted(
            (r["ratio"], r[metric])
            for r in records if r["rho"] == rho and r["area"] == area
        )
        if not pts:
            continue
        xs, ys = zip(*pts)
        ms = 6 if area == 1024 else 5
        label = f"measured — {area}w C tile"
        ax.plot(xs, [y / 1e6 for y in ys],
                FAMILY_MARKERS[area], ms=ms, color=color,
                label=label, zorder=3)

        # continuous word-model curve
        x0, x1 = xs[0], xs[-1]
        cx = [x0 + i * (x1 - x0) / 200 for i in range(201)]
        if metric == "bytes_in":
            wm = [reads_word(M, N, K,
                             math.sqrt(area / 2**x), math.sqrt(area * 2**x),
                             A_P, bp, A_P) / 1e6 for x in cx]
        else:
            wm = [writes_word(M, N, A_P) / 1e6 for _ in cx]
        lbl_w = f"word model" if area == 1024 else None
        ax.plot(cx, wm, "--", lw=1.3, color=color, alpha=0.65, label=lbl_w)

        # line-aware model at grid points
        if metric == "bytes_in":
            law = sorted(
                (math.log2(tn / tm),
                 reads_line_aware(M, N, K, tm, tn, A_P, bp, A_P, LINE) / 1e6)
                for tm, tn in tiles
            )
        else:
            law = sorted(
                (math.log2(tn / tm),
                 writes_line_aware(M, N, tm, tn, A_P, LINE) / 1e6)
                for tm, tn in tiles
            )
        lbl_la = f"line-aware" if area == 1024 else None
        ax.plot([p[0] for p in law], [p[1] for p in law],
                ":", lw=1.4, color="#555555", label=lbl_la)

    opt = math.log2(1.0 / rho)
    ax.axvline(opt, color="#888888", ls="-.", lw=1.2,
               label=f"predicted opt = {1/rho:g}")

    ax.set_yscale("log")
    ax.set_title(f"ρ = {rho:g}", fontsize=11, fontweight="bold")
    ax.set_xlabel("log₂(T_N / T_M)", fontsize=9)
    ax.set_ylabel("MB", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, ls=":", alpha=0.4)
    ax.legend(fontsize=6.5, loc="upper center", ncol=2, framealpha=0.85)


def make_figure(records, metric, ylabel_long, fname):
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5))
    axes = axes.flatten()
    for i, (rho, bp) in enumerate(RHOS):
        make_panel(axes[i], records, rho, bp, metric)

    fig.suptitle(
        f"L1 {ylabel_long} vs paper prediction — fully-associative cache\n"
        f"m=n=k=256, T_K=256, outer-products order",
        fontsize=11, y=1.01,
    )
    fig.tight_layout()
    out = HERE / fname
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    records = load_records()
    print(f"loaded {len(records)} fully-assoc records")
    make_figure(records, "bytes_in",  "reads (BytesIn)",   "fa_reads.png")
    make_figure(records, "bytes_out", "writes (BytesOut)", "fa_writes.png")
