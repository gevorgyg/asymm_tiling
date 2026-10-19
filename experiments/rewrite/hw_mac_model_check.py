"""Check for report 4.6.5 ("How slow exactly?"): a MAC cost c (cycles per
MAC) simply adds to alpha in the refined model. Nothing is re-run: all
numbers come from the hw_mac_cost runs (77 tiles x 8 gc x 4 MAC costs).

1. With free generation (gc = 0), every tile's runtime grows by exactly c:
   mulacc() is a plain Clock::tick(mulacc_cost) in series with the loads and
   stores (src/multi_unit.cpp), and every tile does the same MNK / R^3
   register-block multiplies.
2. The refined model with alpha + c, calibrated only on the free-MAC gc = 0
   runs, predicts the measured runtime of every tile and gc, and picks the
   best tile.

  hw_mac_model:  best runtime against gc, measured (markers) and predicted by
                 the model with alpha + c (dashed), one color per MAC cost.

run:  .venv/bin/python experiments/rewrite/hw_mac_model_check.py
"""

from dataclasses import replace
import math

import hw_mac_cost as H
from harness import Params, out_dir, run_many
from plot_style import INK_2, SERIES, legend_above, plt, save, series

M, N, K, R = 192, 256, 256, 4
MACS_PER_BLOCK = R ** 3


def main() -> None:
    tiles = [(tm, tn) for tm in H.TM for tn in H.TN]
    params = [replace(Params(l1_assoc=-1), mulacc_cost=c, tile_h=tm, tile_w=tn, gen_cost=gc)
              for c in H.MAC for gc in H.GC for tm, tn in tiles]
    stats = run_many(params, out_dir(H.NAME) / "results_small.json")
    t = {(p.mulacc_cost, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / H.MNK
         for p, s in zip(params, stats)}

    # 1. at gc = 0 the MAC cost adds exactly c per MAC to every tile
    print("1. gc = 0: measured runtime with a MAC cost minus the free-MAC runtime, per tile")
    for c in H.MAC[1:]:
        per_mac = c / MACS_PER_BLOCK
        diffs = [t[(c, 0, *tl)] - t[(0, 0, *tl)] for tl in tiles]
        print(f"   c = {per_mac:g} cycle/MAC: difference min {min(diffs):.6f}, max {max(diffs):.6f}"
              f"  (expected exactly {per_mac:g}, over {len(tiles)} tiles)")

    # 2. the refined model with alpha + c, calibrated on the free-MAC gc = 0 runs only
    alpha = {tl: t[(0, 0, *tl)] for tl in tiles}
    pure = {}   # alpha of a row of exactly tm rows: take the short last row out of the mix
    for tm, tn in sorted(alpha):
        e = M % tm
        pure[(tm, tn)] = (M * alpha[(tm, tn)] - (e * pure[(e, tn)] if e else 0)) / (M - e)

    def predict(tm: int, tn: int, gc: int, c: float) -> float:
        rows = [tm] * (M // tm) + ([M % tm] if M % tm else [])
        s = gc * R * R * math.ceil(N / tn) / (K * N)   # startup of one row of tiles, memory side
        return sum(max(r * (pure[(r, tn)] + c) + s, gc) for r in rows) / M

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, c in enumerate(H.MAC):
        per_mac = c / MACS_PER_BLOCK
        label = "free" if c == 0 else ("1" if c == MACS_PER_BLOCK else f"1/{MACS_PER_BLOCK // c}")
        label += " cycle / MAC" if c else " MAC"
        ax.plot(H.GC, [min(predict(*tl, gc, per_mac) for tl in tiles) for gc in H.GC],
                color=SERIES[i], linestyle="--", linewidth=1.4)
        ax.plot(H.GC, [min(t[(c, gc, *tl)] for tl in tiles) for gc in H.GC], linestyle="none",
                label=label, **series(i))
    ax.plot([], [], color=INK_2, linestyle="--", linewidth=1.4, label="model")
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime (cycles / MAC)")
    ax.set_xlim(0, H.GC[-1])
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=len(H.MAC) + 1)
    print(save(fig, "hardware/h7_mac_cost", "hw_mac_model"))

    print("\n2. refined model with alpha + c vs measured (cycles per MAC)")
    print("   MAC cost | gc | best measured | best predicted | error | model's tile | its excess"
          " | worst tile error")
    for c in H.MAC[1:]:
        per_mac = c / MACS_PER_BLOCK
        for gc in H.GC:
            meas = {tl: t[(c, gc, *tl)] for tl in tiles}
            pred = {tl: predict(*tl, gc, per_mac) for tl in tiles}
            best = min(meas.values())
            pick = min(tiles, key=lambda tl: (pred[tl], alpha[tl]))
            worst = max(abs(meas[tl] / pred[tl] - 1) for tl in tiles)
            print(f"   {per_mac:>8g} | {gc:>3} | {best:.3f} | {min(pred.values()):.3f} | "
                  f"{min(pred.values()) / best - 1:+.2%} | {pick} | {meas[pick] / best - 1:+.2%} | "
                  f"{worst:.1%}")


if __name__ == "__main__":
    main()
