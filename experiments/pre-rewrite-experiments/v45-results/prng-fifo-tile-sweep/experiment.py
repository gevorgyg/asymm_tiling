"""PRNG FIFO vs memory baseline: aspect sweep and tile-size sweep.

Two sub-experiments on a symmetric-precision (ρ=1) workload:

1. Aspect sweep — fixed C-tile area (~512–1024 words), T_N/T_M ∈ [1/8, 8].
   The paper predicts the mem optimum at T_N/T_M = 1/ρ = 1.  With prng_fifo
   B exits the cache; the A-load vs PRNG-generation bottleneck shifts the
   optimal aspect as a function of gen_cost.

2. Size sweep — fixed aspect T_N/T_M = 1 (ρ=1 optimum), C-tile budget
   log₂(C-tile bytes / L1) ∈ {−6,−4,−2, 0}.  With mem the model breaks at
   budget = 0 (C tile = L1); with prng_fifo the freed B-cache space lets the
   C tile grow further before performance degrades.

See WRITEUP.md for hypotheses and interpretation guidance.
"""

import math
from collections import defaultdict
from pathlib import Path

from matplotlib import colormaps
from matplotlib.colors import to_hex

from experiments.harness import (
    Cell, Flags, describe_changes, lineplot, plot_metric_family,
    run_grid_dual, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

M = N = K = 256
A_P = B_P = 4
LINE = 64
L1 = 16_384
L2 = 4 * L1

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
    "A_PRECISION_BYTES": A_P, "B_PRECISION_BYTES": B_P,
    "L1_SIZE_BYTES": L1,  "L1_LINE_SIZE_BYTES": LINE, "L1_ASSOC": L1 // LINE,
    "L2_SIZE_BYTES": L2,  "L2_LINE_SIZE_BYTES": LINE, "L2_ASSOC": L2 // LINE,
    "L2_ACCESS_CYCLES": 14,
    "TILE_K": K,
    "PRNG_FIFO_CAPACITY": 64,
}

# Aspect sweep: 7 tiles, log₂(T_N/T_M) ∈ {-3,-2,-1,0,+1,+2,+3}
# Area alternates between 512 and 1024 words to keep tiles reasonable.
ASPECT_TILES: list[tuple[int, int]] = [
    (64, 8),   # log₂ = -3, area = 512
    (64, 16),  # log₂ = -2, area = 1024
    (32, 16),  # log₂ = -1, area = 512
    (32, 32),  # log₂ =  0, area = 1024
    (16, 32),  # log₂ = +1, area = 512
    (16, 64),  # log₂ = +2, area = 1024
    (8,  64),  # log₂ = +3, area = 512
]

# Size sweep: square tiles (aspect = 1), log₂(C-tile bytes / L1) ∈ {-6,-4,-2,0}
SIZE_TILES: list[tuple[int, int]] = [(8, 8), (16, 16), (32, 32), (64, 64)]

# Optimal-aspect size sweep: tile ladders at each aspect found to be best in the
# aspect sweep.  Square (aspect=1) reuses SIZE_TILES; the others need new runs.
#   mem    → aspect 1/2  (32×16 was best)
#   gc≤64  → aspect 1    (32×32 was best) → SIZE_TILES
#   gc=128,256 → aspect 1/4  (64×16 was best)
#   gc=512 → aspect 1/8  (64×8 was best)
TILES_HALF    = [(16, 8), (32, 16), (64, 32), (128, 64)]   # TN/TM = 1/2
TILES_QUARTER = [(32, 8), (64, 16), (128, 32), (256, 64)]  # TN/TM = 1/4
TILES_EIGHTH  = [(32, 4), (64, 8),  (128, 16), (256, 32)]  # TN/TM = 1/8

# gc → tile ladder at its optimal aspect
OPTIMAL_TILES: dict[int | None, list[tuple[int, int]]] = {
    None: TILES_HALF,
    **{gc: SIZE_TILES for gc in [1, 2, 4, 8, 16, 32, 64]},
    128:  TILES_QUARTER,
    256:  TILES_QUARTER,
    512:  TILES_EIGHTH,
}

GEN_COSTS: list[int] = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

FLAGS_MEM  = Flags(b_source="mem",       stationary="C", three_d_reg=True, outer_products=True)
FLAGS_FIFO = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True, outer_products=True)

# Sequential blue→red (coolwarm) palette log-scaled across GEN_COSTS.
# Low gc (fast PRNG, no stalls) → blue; high gc (slow PRNG, bottlenecked) → red.
_cmap = colormaps["coolwarm"]
_log_gc = [math.log2(gc) for gc in GEN_COSTS]
_lo, _hi = _log_gc[0], _log_gc[-1]
PALETTE_GC: dict[int, str] = {
    gc: to_hex(_cmap((math.log2(gc) - _lo) / (_hi - _lo)))
    for gc in GEN_COSTS
}
_COLOR_MEM = "#444444"


def _colors() -> dict[str, str]:
    return {"mem": _COLOR_MEM,
            **{f"prng_fifo, gc={gc}": PALETTE_GC[gc] for gc in GEN_COSTS}}


def _label(r: dict) -> str:
    return "mem" if r["source"] == "mem" else f"prng_fifo, gc={r['gc']}"


def _aspect_x(r: dict) -> float:
    return math.log2(r["tn"] / r["tm"])


def _budget_x(r: dict) -> float:
    return math.log2(r["tm"] * r["tn"] * A_P / L1)


def _run_optimal_aspect_sweep(base: str) -> list[dict]:
    """Run each (source, gc) at its optimal-aspect tile ladder from the aspect sweep."""
    records: list[dict] = []

    print("\n--- mem (optimal aspect 1/2) ---")
    for tm, tn in TILES_HALF:
        duals = run_grid_dual(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**BASE_OVERRIDES, "TILE_M": tm, "TILE_N": tn},
            flags=FLAGS_MEM,
        )
        records.append({"source": "mem", "gc": None, "tm": tm, "tn": tn, "d": duals[0]})

    for gc in GEN_COSTS:
        tiles = OPTIMAL_TILES[gc]
        _label_map = {id(SIZE_TILES): "1", id(TILES_HALF): "1/2",
                      id(TILES_QUARTER): "1/4", id(TILES_EIGHTH): "1/8"}
        aspect_label = _label_map[id(tiles)]
        print(f"\n--- prng_fifo gc={gc} (optimal aspect {aspect_label}) ---")
        for tm, tn in tiles:
            duals = run_grid_dual(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={**BASE_OVERRIDES, "TILE_M": tm, "TILE_N": tn,
                                "PRNG_FIFO_GEN_COST": gc},
                flags=FLAGS_FIFO,
            )
            records.append({"source": "prng_fifo", "gc": gc,
                            "tm": tm, "tn": tn, "d": duals[0]})

    return records


def _run_tiles(base: str, tiles: list[tuple[int, int]]) -> list[dict]:
    """Run mem baseline and prng_fifo × GEN_COSTS for every tile."""
    records: list[dict] = []

    print("\n--- mem baseline ---")
    for tm, tn in tiles:
        duals = run_grid_dual(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**BASE_OVERRIDES, "TILE_M": tm, "TILE_N": tn},
            flags=FLAGS_MEM,
        )
        records.append({"source": "mem", "gc": None, "tm": tm, "tn": tn, "d": duals[0]})

    for gc in GEN_COSTS:
        print(f"\n--- prng_fifo gen_cost={gc} ---")
        for tm, tn in tiles:
            duals = run_grid_dual(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={
                    **BASE_OVERRIDES,
                    "TILE_M": tm, "TILE_N": tn,
                    "PRNG_FIFO_GEN_COST": gc,
                },
                flags=FLAGS_FIFO,
            )
            records.append({"source": "prng_fifo", "gc": gc,
                            "tm": tm, "tn": tn, "d": duals[0]})

    return records


def _plot_cycles(records: list[dict], x_fn, *, out_path: Path,
                 xlabel: str, title: str) -> None:
    series: dict[str, list] = defaultdict(list)
    for r in records:
        series[_label(r)].append((x_fn(r), r["d"].cycles.cycles))
    for v in series.values():
        v.sort()
    lineplot(dict(series), out_path=out_path,
             xlabel=xlabel, ylabel="total cycles (mulacc included)",
             title=title, colors=_colors())


def _plot_l1_traffic(records: list[dict], x_fn, *, out_path: Path,
                     xlabel: str, title: str) -> None:
    series: dict[str, list] = defaultdict(list)
    for r in records:
        series[_label(r)].append((x_fn(r), r["d"].traffic.l1.bytes_in))
    for v in series.values():
        v.sort()
    lineplot(dict(series), out_path=out_path,
             xlabel=xlabel, ylabel="L1 BytesIn",
             title=title, colors=_colors())


def _plot_cycles_zoomed(records: list[dict], x_fn, *, out_path: Path,
                        xlabel: str, title: str,
                        gc_max: int = 64) -> None:
    """Cycles plot restricted to gc ≤ gc_max + mem, to show the PRNG speedup clearly."""
    fast_costs = [gc for gc in GEN_COSTS if gc <= gc_max]
    filtered = [r for r in records if r["source"] == "mem" or (r["gc"] is not None and r["gc"] <= gc_max)]
    zoomed_colors = {"mem": _COLOR_MEM,
                     **{f"prng_fifo, gc={gc}": PALETTE_GC[gc] for gc in fast_costs}}
    series: dict[str, list] = defaultdict(list)
    for r in filtered:
        series[_label(r)].append((x_fn(r), r["d"].cycles.cycles))
    for v in series.values():
        v.sort()
    lineplot(dict(series), out_path=out_path,
             xlabel=xlabel, ylabel="total cycles (mulacc included)",
             title=title, colors=zoomed_colors)


def _plot_stall_fraction(records: list[dict], x_fn, *, out_path: Path,
                         xlabel: str, title: str) -> None:
    """Fraction of total cycles spent stalling on an empty FIFO (prng_fifo only)."""
    series: dict[str, list] = defaultdict(list)
    for r in records:
        if r["source"] != "prng_fifo":
            continue
        pf = r["d"].cycles.prng_fifo
        total = r["d"].cycles.cycles
        frac = (pf.stall_cycles / total) if (pf and total) else 0.0
        series[_label(r)].append((x_fn(r), frac))
    for v in series.values():
        v.sort()
    lineplot(dict(series), out_path=out_path,
             xlabel=xlabel, ylabel="stall cycles / total cycles",
             title=title,
             colors={f"prng_fifo, gc={gc}": PALETTE_GC[gc] for gc in GEN_COSTS})


def _cycles_table(records: list[dict], tiles: list[tuple[int, int]],
                  x_fn, x_label: str) -> str:
    lookup = {(_label(r), r["tm"], r["tn"]): r["d"].cycles.cycles for r in records}
    sources = ["mem"] + [f"prng_fifo, gc={gc}" for gc in GEN_COSTS]
    col_heads = [f"{tm}×{tn} ({x_label}={x_fn({'tm':tm,'tn':tn}):+.0f})"
                 for tm, tn in tiles]
    lines = ["| source | " + " | ".join(col_heads) + " |",
             "|---|" + "---|" * len(tiles)]
    for src in sources:
        row = [src] + [f"{lookup.get((src, tm, tn), '?'):,}"
                       if isinstance(lookup.get((src, tm, tn)), int) else "?"
                       for tm, tn in tiles]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    caption = describe_changes(
        {k: v for k, v in BASE_OVERRIDES.items()
         if k not in ("PRNG_FIFO_CAPACITY", "TILE_K")},
        base,
        extras={"TILE_K": K, "order": "outer products", "FIFO_cap": 64},
    )

    print("=" * 50)
    print("Aspect sweep")
    print("=" * 50)
    aspect_records = _run_tiles(base, ASPECT_TILES)

    print("\n" + "=" * 50)
    print("Size sweep")
    print("=" * 50)
    size_records = _run_tiles(base, SIZE_TILES)

    print("\n" + "=" * 50)
    print("Optimal-aspect size sweep")
    print("=" * 50)
    opt_records = _run_optimal_aspect_sweep(base)

    # --- Aspect sweep plots ---
    _plot_cycles(
        aspect_records, _aspect_x,
        out_path=EXPERIMENT_DIR / "aspect_cycles.png",
        xlabel="log₂(T_N / T_M)",
        title="Aspect sweep: total cycles vs tile shape (ρ=1 mem optimum at 0)\n" + caption,
    )
    _plot_l1_traffic(
        aspect_records, _aspect_x,
        out_path=EXPERIMENT_DIR / "aspect_l1_traffic.png",
        xlabel="log₂(T_N / T_M)",
        title="Aspect sweep: L1 BytesIn vs tile shape\n" + caption,
    )
    _plot_cycles_zoomed(
        aspect_records, _aspect_x,
        out_path=EXPERIMENT_DIR / "aspect_cycles_zoomed.png",
        xlabel="log₂(T_N / T_M)",
        title="Aspect sweep: cycles, gc ≤ 128 — PRNG speedup region\n" + caption,
        gc_max=128,
    )
    _plot_stall_fraction(
        aspect_records, _aspect_x,
        out_path=EXPERIMENT_DIR / "aspect_stall_fraction.png",
        xlabel="log₂(T_N / T_M)",
        title="Aspect sweep: FIFO stall fraction vs tile shape\n" + caption,
    )

    # Standard metric family for aspect sweep
    plot_metric_family(
        [Cell(x=_aspect_x(r), series=_label(r),
              traffic=r["d"].traffic, cycles=r["d"].cycles)
         for r in aspect_records],
        out_dir=EXPERIMENT_DIR, base_name="aspect_sweep",
        title="Aspect sweep — mem vs prng_fifo (ρ=1)",
        caption=caption, xlabel="log₂(T_N / T_M)",
        colors=_colors(),
        ref_vlines={"ρ=1 mem optimum": 0.0},
    )

    # --- Size sweep plots ---
    _plot_cycles(
        size_records, _budget_x,
        out_path=EXPERIMENT_DIR / "size_cycles.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Size sweep: total cycles vs C-tile budget (aspect=1)\n" + caption,
    )
    _plot_l1_traffic(
        size_records, _budget_x,
        out_path=EXPERIMENT_DIR / "size_l1_traffic.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Size sweep: L1 BytesIn vs C-tile budget (aspect=1)\n" + caption,
    )
    _plot_cycles_zoomed(
        size_records, _budget_x,
        out_path=EXPERIMENT_DIR / "size_cycles_zoomed.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Size sweep: cycles, gc ≤ 128 — PRNG speedup region\n" + caption,
        gc_max=128,
    )
    _plot_stall_fraction(
        size_records, _budget_x,
        out_path=EXPERIMENT_DIR / "size_stall_fraction.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Size sweep: FIFO stall fraction vs C-tile budget (aspect=1)\n" + caption,
    )

    # Standard metric family for size sweep
    plot_metric_family(
        [Cell(x=_budget_x(r), series=_label(r),
              traffic=r["d"].traffic, cycles=r["d"].cycles)
         for r in size_records],
        out_dir=EXPERIMENT_DIR, base_name="size_sweep",
        title="Size sweep — mem vs prng_fifo (aspect=1, ρ=1)",
        caption=caption, xlabel="log₂(C-tile bytes / L1 bytes)",
        colors=_colors(),
        ref_vlines={"C tile = L1 (predicted breakdown)": 0.0},
    )

    # --- Optimal-aspect size sweep plot ---
    _plot_cycles(
        opt_records, _budget_x,
        out_path=EXPERIMENT_DIR / "opt_aspect_cycles.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Optimal-aspect size sweep: each gc at its best tile shape\n" + caption,
    )
    _plot_cycles_zoomed(
        opt_records, _budget_x,
        out_path=EXPERIMENT_DIR / "opt_aspect_cycles_zoomed.png",
        xlabel="log₂(C-tile bytes / L1 bytes)",
        title="Optimal-aspect size sweep: gc ≤ 128 zoom\n" + caption,
        gc_max=128,
    )

    # --- README ---
    write_report(
        EXPERIMENT_DIR / "README.md",
        "prng-fifo-tile-sweep",
        [
            f"Non-default config: {caption}\n\n"
            "See [WRITEUP.md](WRITEUP.md) for hypotheses and interpretation.\n",

            "## Aspect sweep (fixed C-tile area, varying T_N/T_M)\n\n"
            "![cycles — full range](aspect_cycles.png)\n\n"
            "![cycles — gc ≤ 64 zoom](aspect_cycles_zoomed.png)\n\n"
            "![L1 traffic](aspect_l1_traffic.png)\n\n"
            "![stall fraction](aspect_stall_fraction.png)\n\n"
            + _cycles_table(aspect_records, ASPECT_TILES, _aspect_x, "log₂"),

            "## Size sweep (square tiles, aspect = 1)\n\n"
            "![cycles — full range](size_cycles.png)\n\n"
            "![cycles — gc ≤ 64 zoom](size_cycles_zoomed.png)\n\n"
            "![L1 traffic](size_l1_traffic.png)\n\n"
            "![stall fraction](size_stall_fraction.png)\n\n"
            + _cycles_table(size_records, SIZE_TILES, _budget_x, "budget"),

            "## Optimal-aspect size sweep (each gc at its best tile shape)\n\n"
            "Best aspects from aspect sweep: mem→1/2, gc≤64→1, gc=128,256→1/4, gc=512→1/8\n\n"
            "![cycles — full range](opt_aspect_cycles.png)\n\n"
            "![cycles — gc ≤ 128 zoom](opt_aspect_cycles_zoomed.png)\n",
        ],
    )
