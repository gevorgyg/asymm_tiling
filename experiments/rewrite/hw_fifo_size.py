"""H3 (hardware engineer): how big does the FIFO need to be?

The generator runs ahead of the core only until the FIFO is full; then it
pauses (src/prngfifo.cpp). A bigger FIFO lets it bank elements while the core
is slowed by cache misses. Every tile restarts with an empty FIFO.

For each gc and FIFO capacity (elements of B, 4 bytes each), the best runtime
over all tiles, divided by the best runtime with the default 16384-element
FIFO (which never fills). The answer is the smallest capacity within 1 %.
Default setup otherwise (16 KB fully associative L1, no L2, 192x256x256).

  hw_fifo_size:  slowdown vs FIFO capacity (log2 axis), one line per gc.

SMALL=True runs a coarse tile grid first.

run:  .venv/bin/python experiments/rewrite/hw_fifo_size.py
"""

from dataclasses import replace

from harness import Params, out_dir, run_many
from plot_style import INK_2, legend_above, plt, save, series

NAME = "hw_fifo_size"
SMALL = True
M, K, N = 192, 256, 256
MNK = M * K * N
CAP = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 16384]
REF = 16384
if SMALL:
    TM = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192]
    TN = [4, 8, 16, 32, 64, 128, 256]
    GC = [5, 10, 20, 30, 40, 60, 100, 200]
else:
    TM = [4] + list(range(8, M + 1, 8))
    TN = [4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
    GC = [2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200]
LIMIT = 0.01


def main() -> None:
    tiles = [(tm, tn) for tm in TM for tn in TN]
    params = [replace(Params(l1_assoc=-1), fifo_capacity=cap, tile_h=tm, tile_w=tn,
                      gen_cost=gc)
              for cap in CAP for gc in GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / f"results{'_small' if SMALL else ''}.json")
    t = {(p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w): s["Simulation: Total cycles"] / MNK
         for p, s in zip(params, stats)}
    best = {(cap, gc): min((t[(cap, gc, *tl)], tl) for tl in tiles) for cap in CAP for gc in GC}

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.axhline(1 + LIMIT, color=INK_2, linewidth=0.8, linestyle=":", zorder=1)
    for i, gc in enumerate(GC):
        ax.plot(CAP, [best[(cap, gc)][0] / best[(REF, gc)][0] for cap in CAP],
                label=f"$g_c = {gc}$", **series(i))
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_xlabel("FIFO capacity (elements of $B$)")
    ax.set_ylabel("slowdown vs an unlimited FIFO")
    legend_above(ax, ncols=4)
    print(save(fig, "hardware/h3_fifo_size", NAME + ("_small" if SMALL else "")))

    lines = ["| gc | best at 16384 | smallest capacity within 1 % | " +
             " | ".join(str(c) for c in CAP) + " |", "|---" * (3 + len(CAP)) + "|"]
    for gc in GC:
        ref, ref_tile = best[(REF, gc)]
        enough = min(c for c in CAP if all(best[(d, gc)][0] <= ref * (1 + LIMIT)
                                           for d in CAP if d >= c))
        lines.append(f"| {gc} | {ref:.3f} {ref_tile} | {enough} | " + " | ".join(
            f"{best[(c, gc)][0] / ref:.3f} {best[(c, gc)][1]}" for c in CAP) + " |")
    report = (f"# {NAME}{' (small)' if SMALL else ''}: FIFO capacity needed\n\n"
              f"{len(tiles)} tiles × {len(GC)} gc × {len(CAP)} capacities. Cells: best "
              f"runtime / best at {REF}, and the best tile.\n\n" + "\n".join(lines) + "\n")
    (out_dir(NAME) / f"README{'_small' if SMALL else ''}.md").write_text(report)
    print(report)
    register_blocks(tiles)
    other_configs(tiles, t)
    register_blocks_mac(tiles)
    configs_figure(tiles)


# does the FIFO a register block needs depend on the MAC cost? mulacc_cost is
# charged per register-block multiply (R^3 MACs), so it is scaled by R^3 to
# keep the cost per MAC the same for every R
MAC_PER_MAC = {"free": 0, "1/4": 0.25, "1": 1}


def register_blocks_mac(tiles: list) -> None:
    caps = [16, 64, 256, 1024, 4096, 16384]
    params = [replace(Params(l1_assoc=-1), reg_dim=r, mulacc_cost=int(m * r ** 3),
                      fifo_capacity=cap, tile_h=tm, tile_w=tn, gen_cost=gc)
              for r in REG for m in MAC_PER_MAC.values() for cap in caps
              for gc in REG_GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / "results_regmac_small.json")
    t = {(p.reg_dim, p.mulacc_cost, p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
    rows = []
    for r in REG:
        for name, m in MAC_PER_MAC.items():
            c = int(m * r ** 3)
            best = {(cap, gc): min(t[(r, c, cap, gc, *tl)] for tl in tiles)
                    for cap in caps for gc in REG_GC}
            worst = [max(best[(cap, gc)] / best[(REF, gc)] for gc in REG_GC) - 1 for cap in caps]
            rows.append(f"| {r}×{r} | {name} | " + " | ".join(f"{w:.0%}" for w in worst) + " |")
    report = (f"# {NAME} (small): FIFO size vs register block and MAC cost\n\n"
              f"Worst slowdown over gc {REG_GC} with a FIFO of the given capacity "
              f"(elements), vs an unlimited FIFO. MAC cost per MAC (scaled by R^3 per "
              f"block multiply).\n\n| R | MAC | " + " | ".join(map(str, caps)) + " |\n" +
              "|---" * (2 + len(caps)) + "|\n" + "\n".join(rows) + "\n")
    (out_dir(NAME) / "README_regmac_small.md").write_text(report)
    print(report)


# when does the capacity stop mattering on other hardware? The smallest
# capacity within 1 % of an unlimited FIFO, per configuration and gc. One
# change from the default at a time; the register block sweep is above.
CONFIGS = {
    "default": {},
    "memory 90 cycles": {"mem_cycles": 90},
    "memory 360 cycles": {"mem_cycles": 360},
    "L1 8 KB": {"l1_size": 13},
    "L1 32 KB": {"l1_size": 15},
    "MAC 1/4 cycle": {"mulacc_cost": 16},
}


def enough_capacity(best: dict, gc: int) -> int:
    ref = best[(REF, gc)]
    return min(c for c in CAP if all(best[(d, gc)] <= ref * (1 + LIMIT) for d in CAP if d >= c))


def other_configs(tiles: list, default: dict) -> None:
    rows = []
    for name, change in CONFIGS.items():
        if change:
            params = [replace(Params(l1_assoc=-1), **change, fifo_capacity=cap, tile_h=tm,
                              tile_w=tn, gen_cost=gc)
                      for cap in CAP for gc in GC for tm, tn in tiles]
            stats = run_many(params, out_dir(NAME) / "results_configs_small.json")
            t = {(p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w):
                 s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
        else:
            t = default
        best = {(cap, gc): min(t[(cap, gc, *tl)] for tl in tiles) for cap in CAP for gc in GC}
        rows.append(f"| {name} | " + " | ".join(str(enough_capacity(best, gc)) for gc in GC) +
                    " | " + " | ".join(f"{best[(16, gc)] / best[(REF, gc)]:.2f}" for gc in GC) + " |")
    report = (f"# {NAME} (small): smallest capacity within 1 % per configuration\n\n"
              f"Left: smallest capacity (elements) within 1 % of an unlimited FIFO, per gc. "
              f"Right: slowdown with the smallest FIFO (16 elements).\n\n"
              "| config | " + " | ".join(f"gc {gc}" for gc in GC) + " | " +
              " | ".join(f"16 el. gc {gc}" for gc in GC) + " |\n" +
              "|---" * (1 + 2 * len(GC)) + "|\n" + "\n".join(rows) + "\n")
    (out_dir(NAME) / "README_configs_small.md").write_text(report)
    print(report)


# larger register blocks need a larger FIFO: the same slowdown, one line per
# register block size R (each pop takes R^2 elements, the work between two
# pops does not grow with R)
# powers of two only (the user's choice): 6 and 12 were also run (cached) but
# don't divide the tiles, so their blocks are clipped and the trend is irregular
REG = [2, 4, 8, 16]
REG_GC = [5, 10, 20, 60, 200]     # what the R sweep ran
REG_PLOT_GC = [20, 60]            # gc 10 has an unexplained anomaly, at gc 200 R 4 = R 8


def register_blocks(tiles: list) -> None:
    params = [replace(Params(l1_assoc=-1), reg_dim=r, fifo_capacity=cap, tile_h=tm,
                      tile_w=tn, gen_cost=gc)
              for r in REG for cap in CAP for gc in REG_GC for tm, tn in tiles]
    stats = run_many(params, out_dir(NAME) / "results_regdim_small.json")
    t = {(p.reg_dim, p.fifo_capacity, p.gen_cost, p.tile_h, p.tile_w):
         s["Simulation: Total cycles"] / MNK for p, s in zip(params, stats)}
    best = {(r, cap, gc): min(t[(r, cap, gc, *tl)] for tl in tiles)
            for r in REG for cap in CAP for gc in REG_PLOT_GC}

    fig, axes = plt.subplots(1, len(REG_PLOT_GC), figsize=(7.0, 3.6), sharey=True)
    for ax, gc in zip(axes, REG_PLOT_GC):
        ax.axhline(1 + LIMIT, color=INK_2, linewidth=0.8, linestyle=":", zorder=1)
        for i, r in enumerate(REG):
            ax.plot(CAP, [best[(r, cap, gc)] / best[(r, REF, gc)] for cap in CAP],
                    label=rf"${r} \times {r}$", **series(i))
        ax.set_xscale("log", base=2)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel(f"FIFO capacity (elements), $g_c = {gc}$")
    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}×"))
    axes[0].set_ylabel("slowdown vs an unlimited FIFO")
    legend_above(axes[0], ncols=len(REG))
    print(save(fig, "hardware/h3_fifo_size", NAME + "_registers_small"))


# hw_fifo_configs: the report's configuration table as a figure (the user asked,
# 2026-10-21): worst slowdown over REG_GC against the FIFO capacity, one panel
# per changed parameter. All from the cached runs above; each line is compared
# with an unlimited FIFO on its own configuration. The default (4 x 4, 180
# cycles) has the same colour in the first two panels, and 16 x 16 with a free
# MAC in the first and the last.
def configs_figure(tiles: list) -> None:
    def worst(t: dict, key, caps: list) -> list:
        best = {(cap, gc): min(t[key(cap, gc, tl)] for tl in tiles) for cap in caps for gc in REG_GC}
        return [100 * (max(best[(cap, gc)] / best[(REF, gc)] for gc in REG_GC) - 1) for cap in caps]

    def cycles(params: list, file: str) -> dict:
        return {p: s["Simulation: Total cycles"] / MNK
                for p, s in zip(params, run_many(params, out_dir(NAME) / file))}

    base = Params(l1_assoc=-1)
    reg = cycles([replace(base, reg_dim=r, fifo_capacity=cap, tile_h=tm, tile_w=tn, gen_cost=gc)
                  for r in REG for cap in CAP for gc in REG_GC for tm, tn in tiles],
                 "results_regdim_small.json")
    mem = cycles([replace(base, mem_cycles=lat, fifo_capacity=cap, tile_h=tm, tile_w=tn, gen_cost=gc)
                  for lat in (90, 360) for cap in CAP for gc in REG_GC for tm, tn in tiles],
                 "results_configs_small.json")
    mac_caps = [16, 64, 256, 1024, 4096, 16384]
    mac = cycles([replace(base, reg_dim=16, mulacc_cost=int(m * 16 ** 3), fifo_capacity=cap,
                          tile_h=tm, tile_w=tn, gen_cost=gc)
                  for m in MAC_PER_MAC.values() for cap in mac_caps for gc in REG_GC
                  for tm, tn in tiles], "results_regmac_small.json")
    tile = lambda tl: dict(tile_h=tl[0], tile_w=tl[1])

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.0), sharey=True)
    panels = [
        ("register block", [(rf"${r} \times {r}$" + (" (default)" if r == 4 else ""), i,
                             worst(reg, lambda cap, gc, tl, r=r: replace(
                                 base, reg_dim=r, fifo_capacity=cap, gen_cost=gc, **tile(tl)), CAP), CAP)
                            for i, r in enumerate(REG)]),
        (r"memory latency ($4 \times 4$)",
         [("90 cycles", 4, worst(mem, lambda cap, gc, tl: replace(
             base, mem_cycles=90, fifo_capacity=cap, gen_cost=gc, **tile(tl)), CAP), CAP),
          ("180 (default)", 1, worst(reg, lambda cap, gc, tl: replace(
              base, reg_dim=4, fifo_capacity=cap, gen_cost=gc, **tile(tl)), CAP), CAP),
          ("360 cycles", 5, worst(mem, lambda cap, gc, tl: replace(
              base, mem_cycles=360, fifo_capacity=cap, gen_cost=gc, **tile(tl)), CAP), CAP)]),
        (r"MAC cost ($16 \times 16$)",
         [(f"{name}" + (" cycle" if name != "free" else ""), i, worst(mac, lambda cap, gc, tl, m=m: replace(
             base, reg_dim=16, mulacc_cost=int(m * 16 ** 3), fifo_capacity=cap, gen_cost=gc,
             **tile(tl)), mac_caps), mac_caps)
          for (name, m), i in zip(MAC_PER_MAC.items(), (3, 6, 7))]),
    ]
    for ax, (title, lines) in zip(axes, panels):
        for label, i, ys, caps in lines:
            ax.plot(caps, ys, label=label, **series(i))
        ax.set_title(title, fontsize=10)
        ax.set_xscale("log", base=2)
        ax.set_xticks([16, 256, 4096])
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.legend(loc="upper right", fontsize=8, frameon=False)
    axes[1].set_xlabel("FIFO capacity (elements of $B$)")
    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}%"))
    axes[0].set_ylabel("worst slowdown vs\nan unlimited FIFO")
    axes[0].set_ylim(0, 118)              # room for the legends above the lines
    axes[0].set_yticks(range(0, 81, 20))
    print(save(fig, "hardware/h3_fifo_size", "hw_fifo_configs"))


if __name__ == "__main__":
    main()
