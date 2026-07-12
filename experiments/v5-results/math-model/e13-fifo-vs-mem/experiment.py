"""E13: FIFO-B vs memory-B — fair head-to-head comparison.

All prior experiments used B from a PRNG FIFO (--Bsource prng_fifo).  This
avoids any B memory traffic, but requires an on-chip B generator with a
hardware gen_cost (gc) per element.

This experiment asks: is FIFO actually better than reading B from memory,
and by how much?  We compare:

  FIFO-B:   --Bsource prng_fifo, gc ∈ GC_SWEEP, TN=32, best TM per gc
  Memory-B: --Bsource mem,       B_PRECISION_BYTES=4 (= A_P, "square"),
             TN=32, best TM for memory mode

Fair comparison rules:
  - Same A and B element precision (4 bytes each) — symmetric case.
  - Same TN=32 (standard default for both).
  - Each mode is evaluated at its own optimal TM*.
  - Memory-B is measured once (no gc parameter — bandwidth cost is fixed).
  - FIFO-B TM* and performance come from the E8 results.json cache.

Expected result: Memory-B has higher α (B competes with A in L2/DRAM), so
FIFO wins for low-to-moderate gc.  At some crossover gc, memory-B becomes
competitive (or wins) because the FIFO generation cost is too high.

The crossover condition approximates:
  max(α_FIFO(TM*_FIFO), gc / TM*_FIFO) ≥ α_mem(TM*_mem)
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
A_P = C_P = 4
LINE = 64
L1   = 16_384
L2   = 4 * L1
L2_LAT = 14

# TN=32 is the standard default used throughout E3–E12
TN = 32

TM_M192 = [8, 16, 24, 32, 48, 64, 96]
TM_M256 = [128]
TM_ALL  = TM_M192 + TM_M256

GC_SWEEP = [64, 100, 104, 108, 130, 165, 171, 175, 230, 248, 252, 256,
            380, 400, 420, 440, 460, 465, 470, 475, 478, 480, 490, 500, 600]

FLAGS_FIFO = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True,
                   mulac_norecord=True)
FLAGS_MEM  = Flags(b_source="mem",       stationary="C", three_d_reg=True,
                   mulac_norecord=True)

_BASE_192: dict[str, object] = {
    "A_HEIGHT_DIM":        192,
    "A_WIDTH_DIM":         256,
    "B_WIDTH_DIM":         256,
    "A_PRECISION_BYTES":   A_P,
    "B_PRECISION_BYTES":   A_P,       # fair: same precision as A
    "L1_SIZE_BYTES":       L1,
    "L1_LINE_SIZE_BYTES":  LINE,
    "L1_ASSOC":            L1 // LINE,
    "L2_SIZE_BYTES":       L2,
    "L2_LINE_SIZE_BYTES":  LINE,
    "L2_ASSOC":            L2 // LINE,
    "L2_ACCESS_CYCLES":    L2_LAT,
    "PRNG_FIFO_CAPACITY":  2 * 256 * 32,
    "TILE_K":              256,
    "TILE_N":              TN,
}
_BASE_256 = {**_BASE_192, "A_HEIGHT_DIM": 256}

E8_RESULTS = EXPERIMENT_DIR.parent / "e8-gc-boundary-sweep" / "results.json"


def mnk(m: int) -> int:
    return m * 256 * 256


def load_fifo_results() -> tuple[dict[int, dict[int, float]], dict[int, float]]:
    """Return (fifo_t, alpha_fifo).

    fifo_t[gc][tm]  = T/MNK from E8 results (TN=32 only)
    alpha_fifo[tm]  = T/MNK at gc=0, TN=32 (pure α, no gc cost)
    """
    import json
    with open(E8_RESULTS) as f:
        cache = json.load(f)

    result:      dict[int, dict[int, float]] = {gc: {} for gc in GC_SWEEP}
    alpha_fifo:  dict[int, float] = {}
    for entry in cache.values():
        ov = entry["overrides"]
        tm = ov["TILE_M"]
        tn = ov["TILE_N"]
        gc = ov["PRNG_FIFO_GEN_COST"]
        m  = ov["A_HEIGHT_DIM"]
        cy = entry["metrics"]["cycles"]

        if gc in GC_SWEEP and tn == TN and tm in TM_ALL:
            result[gc][tm] = cy / mnk(m)
        if gc == 0 and tn == TN and tm in TM_ALL:
            alpha_fifo[tm] = cy / mnk(m)

    return result, alpha_fifo


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Run memory-B baseline (B_PRECISION_BYTES=4, no gc) ───────────────────
    print("Running memory-B baseline: M=192 grid (TN=32) …")
    mem_192 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=_BASE_192,
        sweep_axes={"TILE_M": TM_M192},
        flags=FLAGS_MEM,
    )
    print("Running memory-B baseline: M=256 grid (TM=128) …")
    mem_256 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=_BASE_256,
        sweep_axes={"TILE_M": TM_M256},
        flags=FLAGS_MEM,
    )

    # Build mem_t[tm] = T/MNK table
    mem_t: dict[int, float] = {}
    for r in mem_192 + mem_256:
        tm = r.overrides["TILE_M"]
        m  = r.overrides["A_HEIGHT_DIM"]
        mem_t[tm] = r.metrics.cycles / mnk(m)

    # ── Load FIFO results from E8 cache ───────────────────────────────────────
    fifo_t, alpha_fifo = load_fifo_results()

    # ── Memory-B T/MNK sweep and TM* ─────────────────────────────────────────
    tm_star_mem = min(TM_ALL, key=lambda tm: mem_t[tm])
    t_mem_best  = mem_t[tm_star_mem]

    print("\n── Memory-B T/MNK per TM (TN=32, B_P=A_P=4) ──")
    print(f"{'TM':>5}  {'T/MNK':>8}  {'note':}")
    print("─" * 30)
    for tm in TM_ALL:
        note = "← TM*" if tm == tm_star_mem else ""
        print(f"{tm:>5}  {mem_t[tm]:>8.4f}  {note}")
    print(f"\n  TM*_mem = {tm_star_mem},  T/MNK = {t_mem_best:.4f}")

    # ── Compute FIFO best per gc ──────────────────────────────────────────────
    fifo_best: dict[int, tuple[int, float]] = {}  # gc → (TM*, T/MNK)
    for gc in GC_SWEEP:
        tm_star = min(TM_ALL, key=lambda tm: fifo_t[gc][tm])
        fifo_best[gc] = (tm_star, fifo_t[gc][tm_star])

    # ── Comparison table ──────────────────────────────────────────────────────
    print("\n" + "═" * 82)
    print("FIFO-B vs Memory-B — head-to-head at optimal TM*  (TN=32, A_P=B_P=4)")
    print("═" * 82)
    print(f"  Memory-B baseline:  TM*={tm_star_mem},  T/MNK={t_mem_best:.4f}")
    print()
    print(f"  {'gc':>5}  {'TM*_FIFO':>9}  {'T_FIFO':>8}  {'T_mem':>7}  "
          f"{'speedup':>8}  {'winner':>8}  note")
    print("  " + "─" * 68)

    for gc in GC_SWEEP:
        tm_f, t_f = fifo_best[gc]
        speedup = t_mem_best / t_f   # >1 means FIFO is faster
        winner  = "FIFO  " if speedup >= 1 else "mem   "
        delta   = abs(speedup - 1) * 100
        note    = f"{delta:.1f}% {'faster' if speedup >= 1 else 'slower'}"
        print(f"  {gc:>5}  {tm_f:>9}  {t_f:>8.4f}  {t_mem_best:>7.4f}  "
              f"{speedup:>8.4f}  {winner}  {note}")

    # ── Speedup summary ───────────────────────────────────────────────────────
    fifo_wins = sum(1 for gc in GC_SWEEP if fifo_best[gc][1] < t_mem_best)
    mem_wins  = len(GC_SWEEP) - fifo_wins
    print()
    print(f"  FIFO wins: {fifo_wins}/{len(GC_SWEEP)} gc values tested")
    print(f"  mem  wins: {mem_wins}/{len(GC_SWEEP)} gc values tested")

    crossover_gcs = [gc for gc in GC_SWEEP if fifo_best[gc][1] >= t_mem_best]
    if crossover_gcs:
        print(f"  First gc where FIFO ≥ mem: gc={crossover_gcs[0]}")
    else:
        print("  FIFO wins at all tested gc values")

    # ── Physical interpretation ───────────────────────────────────────────────
    print()
    print("── Physical interpretation ──")
    print(f"  Memory-B (no gc, B from DRAM):  α_mem(TM*={tm_star_mem}) = {t_mem_best:.4f}")
    print("  Memory-B α is higher because B competes with A for L2 cache.")
    print("  FIFO-B removes B entirely from cache — lower α, but adds gc/TM cost.")
    print()
    print("  Per-gc binding analysis (α from gc=0 calibration):")
    print(f"  {'gc':>5}  {'TM*':>4}  {'α_FIFO':>7}  {'gc/TM*':>7}  {'T/MNK':>7}  binding")
    print("  " + "─" * 52)
    for gc in GC_SWEEP:
        tm_f, t_f = fifo_best[gc]
        a_f       = alpha_fifo[tm_f]
        gc_per_tm = gc / tm_f
        binding   = "gc-bound" if gc_per_tm > a_f else "α-bound "
        print(f"  {gc:>5}  {tm_f:>4}  {a_f:>7.4f}  {gc_per_tm:>7.4f}  {t_f:>7.4f}  {binding}")


if __name__ == "__main__":
    run()
