"""H8 (hardware engineer): does the cache replacement policy matter?
(the user's idea, 2026-10-20: random replacement could be unintuitively good)

LRU fails completely on a cyclic access pattern that is slightly larger than
the cache: every line is evicted just before it is needed again (the "third
cliff", T_M > 128 in the default setup, alpha 17-23). Random replacement
keeps a random part of the loop, so its hit rate should fall gradually
instead; MRU keeps the start of the loop. The simulator's policies
(src/cachesim.h): lru, fifo, mru, random (xorshift, fixed seed:
deterministic).

Default setup otherwise (192x256x256, 16 KB fully associative L1, no L2,
B-stationary, R = 4).

  hw_policy_alpha:  alpha (gc = 0) against T_M at T_N = 16, one line per policy.
  hw_policy:        best runtime over all tiles against gc, one line per policy.

SMALL=True: the coarse 77-tile grid of the hardware sections.

run:  .venv/bin/python experiments/rewrite/hw_policy.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, SERIES, legend_above, plt, save, series

NAME = "hw_policy"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
POLICIES = ["lru", "fifo", "mru", "random"]
SHOWN = ["lru", "random"]   # in the figures: MRU (about 32 cycles/MAC everywhere) is left out, and FIFO (the user, 2026-10-21: not relevant there)
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [0, 5, 10, 20, 30, 50, 100, 200]
else:
    TM = list(range(4, M + 1, 4))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
    GC = [0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]
ALPHA_TN = 16
ALPHA_M = 384                       # hw_policy_alpha only: 384 x 256 x 256
ALPHA_TM = list(range(4, ALPHA_M + 1, 4))


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(Params(l1_assoc=-1), policy=pol, tile_h=tm, tile_w=tn, gen_cost=gc)
              for pol in POLICIES for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.policy, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(pol, gc): min((t[(pol, gc, *tl)], tl) for tl in tiles) for pol in POLICIES for gc in GC}

    # alpha against T_M, one line per policy, on a taller matrix so the tiles
    # go past T_M = 200 (the user asked, 2026-10-21: "show some past T_M 200")
    params = [replace(Params(l1_assoc=-1), m=ALPHA_M, policy=pol, tile_h=tm, tile_w=ALPHA_TN, gen_cost=0)
              for pol in SHOWN for tm in ALPHA_TM]
    ta = {(p.policy, p.tile_h): s["Simulation: Total cycles"] / (ALPHA_M * K * N)
          for p, s in zip(params, run_many(params, out_dir(NAME) / "results_alpha_tall.json"))}
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, pol in enumerate(SHOWN):
        ax.plot(ALPHA_TM, [ta[(pol, tm)] for tm in ALPHA_TM], markevery=4,
                label=pol.upper() if pol != "random" else "random", **series(i))
    ax.set_xlabel("$T_M$")
    ax.set_ylabel(r"$\alpha$ (cycles / MAC)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    legend_above(ax, ncols=len(SHOWN))
    print(save(fig, "hardware/h8_policy", NAME + "_alpha" + ("_small" if SMALL else "")))

    # the best runtime against gc, one line per policy
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for i, pol in enumerate(SHOWN):
        ax.plot(GC, [best[(pol, gc)][0] for gc in GC], label=pol.upper() if pol != "random" else "random", **series(i))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime (cycles / MAC)")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(bottom=0)
    legend_above(ax, ncols=len(SHOWN))
    print(save(fig, "hardware/h8_policy", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | " + " | ".join(POLICIES) + " |", "|---" * (1 + len(POLICIES)) + "|"]
    for gc in GC:
        lines.append(f"| {gc} | " + " | ".join(
            f"{best[(pol, gc)][0]:.3f} {best[(pol, gc)][1]} ({best[(pol, gc)][0] / best[('lru', gc)][0] - 1:+.0%})"
            for pol in POLICIES) + " |")
    alpha_lines = ["", f"## alpha at T_N = {ALPHA_TN}", "", "| T_M | " + " | ".join(POLICIES) + " |",
                   "|---" * (1 + len(POLICIES)) + "|"]
    for tm in TM:
        alpha_lines.append(f"| {tm} | " + " | ".join(f"{t[(pol, 0, tm, ALPHA_TN)]:.2f}"
                                                     for pol in POLICIES) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: replacement policy\n\n"
              f"Best runtime (tile) per policy and gc, and its change vs LRU.\n\n" +
              "\n".join(lines + alpha_lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


# the set-associative cache (the user asked, 2026-10-20): with unpadded rows the
# whole tile column falls into one or two sets (report: associativity), where
# LRU meets exactly its cyclic worst case. Random replacement may keep part of
# the column. 8-way vs fully associative, rows of 256 (unpadded) and 272
# (padded to 17 lines), as in hw_assoc.
SET_K = {256: "unpadded (256)", 272: "padded (272)"}
SET_CACHES = {"fully assoc, LRU": (-1, "lru"), "8-way, LRU": (3, "lru"),
              "8-way, random": (3, "random")}


def set_associative() -> None:
    rows, best = [], {}
    for k in SET_K:
        tiles = [(tm, tn) for tm in TM for tn in [4, 8, 16, 32, 64, 128, k]]
        params = [replace(Params(), k=k, n=k, l1_assoc=a, policy=pol, tile_h=tm, tile_w=tn,
                          gen_cost=gc)
                  for a, pol in SET_CACHES.values() for gc in GC for tm, tn in tiles]
        stats = run_many(params, out_dir(NAME) / f"results_8way{'_small' if SMALL else ''}.json")
        t = {(p.l1_assoc, p.policy, p.gen_cost, p.tile_h, p.tile_w):
             s["Simulation: Total cycles"] / (p.m * p.k * p.n) for p, s in zip(params, stats)}
        for name, (a, pol) in SET_CACHES.items():
            for gc in GC:
                best[(k, name, gc)] = min((t[(a, pol, gc, *tl)], tl) for tl in tiles)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    i = 0
    for k, kname in SET_K.items():
        for name in ["8-way, LRU", "8-way, random"]:
            ref = {gc: best[(k, "fully assoc, LRU", gc)][0] for gc in GC}
            style = series(i) | ({"linestyle": "--"} if k == 272 else {})
            ax.plot(GC, [100 * (best[(k, name, gc)][0] / ref[gc] - 1) for gc in GC],
                    label=f"{name}, {kname}", **style)
            i += 1
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("extra time over fully associative LRU (%)")
    ax.set_xlim(0, GC[-1])
    ax.set_ylim(bottom=-5)
    legend_above(ax, ncols=2)
    print(save(fig, "hardware/h8_policy", NAME + "_8way" + ("_small" if SMALL else "")))

    lines = ["| rows | gc | " + " | ".join(SET_CACHES) + " |", "|---" * (2 + len(SET_CACHES)) + "|"]
    for k, kname in SET_K.items():
        for gc in GC:
            ref = best[(k, "fully assoc, LRU", gc)][0]
            lines.append(f"| {kname} | {gc} | " + " | ".join(
                f"{best[(k, n, gc)][0]:.3f} {best[(k, n, gc)][1]} ({best[(k, n, gc)][0] / ref - 1:+.0%})"
                for n in SET_CACHES) + " |")
    report = (f"# {NAME} (8-way): LRU vs random on a set-associative L1\n\n"
              "Best runtime (tile) and the extra time over fully associative LRU.\n\n" +
              "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README_8way{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


# slow generators (the user asked, 2026-10-21: past the cliff random is better,
# does it ever win?): the best tile with random against the best with LRU, for
# g_c up to 6400. Random can only win once a tile past the cliff is needed,
# i.e. when even the tallest tile below the cliff is generation-bound.
GC_SLOW = [300, 400, 600, 800, 1000, 1200, 1400, 1600, 2000, 2400, 2800, 3200, 4000, 4800, 6400]
CLIFF_TM = 128                      # 2 tiles of C (T_M lines each at T_N <= 16) fill the 256 lines


def slow_generators() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    gcs = [gc for gc in GC if gc > 0] + GC_SLOW
    params = [replace(Params(l1_assoc=-1), policy=pol, tile_h=tm, tile_w=tn, gen_cost=gc)
              for pol in SHOWN for gc in gcs for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.policy, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(pol, gc): min((t[(pol, gc, *tl)], tl) for tl in tiles) for pol in SHOWN for gc in gcs}
    diff = [100 * (best[("random", gc)][0] / best[("lru", gc)][0] - 1) for gc in gcs]
    past = [best[("random", gc)][1][0] > CLIFF_TM for gc in gcs]

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.axhline(0, color=INK_2, linewidth=0.8, zorder=1)
    ax.plot(gcs, diff, color=SERIES[1], linewidth=2, zorder=2)
    for flag, label, i in ((False, rf"best random tile fits ($T_M \leq {CLIFF_TM}$)", 0),
                           (True, rf"best random tile past the cliff ($T_M = {M}$)", 3)):
        xs = [gc for gc, p in zip(gcs, past) if p == flag]
        ys = [d for d, p in zip(diff, past) if p == flag]
        ax.plot(xs, ys, label=label, zorder=3, **(series(i) | {"linestyle": "none"}))
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+g}%" if v else "0%"))
    ax.set_xlabel("$g_c$ (cycles / element)")
    ax.set_ylabel("best runtime with random\nvs with LRU")
    legend_above(ax, ncols=2)
    print(save(fig, "hardware/h8_policy", NAME + "_slow" + ("_small" if SMALL else "")))

    lines = ["| gc | LRU | random | random vs LRU |", "|---|---|---|---|"]
    for gc, d in zip(gcs, diff):
        lines.append(f"| {gc} | {best[('lru', gc)][0]:.2f} {best[('lru', gc)][1]} | "
                     f"{best[('random', gc)][0]:.2f} {best[('random', gc)][1]} | {d:+.0f}% |")
    report = (f"# {NAME} (slow generators): best tile, random vs LRU\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README_slow{'_small' if SMALL else ''}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
    set_associative()
    slow_generators()
