"""E13-nol2: FIFO-B vs memory-B — fair head-to-head in L1-only hierarchy.

All prior experiments used B from a PRNG FIFO (--Bsource prng_fifo), which
avoids any B memory traffic but costs gc cycles per element to generate on-chip.

This experiment asks: is FIFO actually better than reading B from memory, and by
how much?  Without L2, Memory-B goes directly to DRAM on every miss.

  FIFO-B:   --Bsource prng_fifo, gc ∈ GC_SWEEP, results loaded from E8-nol2 cache.
  Memory-B: --Bsource mem, B_PRECISION_BYTES=4 (= A_P, symmetric case).

The comparison is made at every TN ∈ {4,8,16,32,64} because TN has a large
effect on FIFO-B cost (C=11.0 cold-fill penalty per 1/TN) but a different
effect on Memory-B cost (smaller B tile → more L1 reuse at small TN).

Fair comparison rules:
  - Same A and B element precision (4 bytes each).
  - Each mode evaluated at its own optimal TM* for that (gc, TN).
  - Memory-B is measured once per (TM, TN) — no gc parameter.
  - FIFO-B TM* and T/MNK come from E8-nol2 results.json cache.

Expected result: Memory-B α is much higher than in the L2 case because B goes
to DRAM (180 cy) on every miss with no L2 buffer.  FIFO wins over a wide gc
range; crossover gc* is predicted much lower than in the L2 case (~234 at
TN=32 vs ~465 in L2).

Crossover condition per TN:
  min_TM max(α_FIFO(TM,TN), gc/TM)  ≥  min_TM α_mem(TM,TN)
"""

from pathlib import Path
import json

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
A_P  = C_P = 4
LINE = 64
L1   = 16_384
L1_LAT  = 4
MEM_LAT = 180
REG_M = REG_N = REG_K = 4
M = 192
N = K = 256
TK = K

MNK = M * N * K

FLAGS_FIFO = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True,
                   mulac_norecord=True, no_l2=True)
FLAGS_MEM  = Flags(b_source="mem",       stationary="A", three_d_reg=True,
                   mulac_norecord=True, no_l2=True)

_BASE: dict[str, object] = {
    "A_HEIGHT_DIM":       M,
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,        # symmetric: same width as A
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "TILE_K":             TK,
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,
}

TM_SWEEP = [8, 12, 16, 24, 32, 48, 64, 96]
TN_SWEEP = [4, 8, 16, 32, 64]

E8_RESULTS = EXPERIMENT_DIR.parent / "e8-gc-boundary-sweep" / "results.json"


def ws_lines(tm: int, tn: int) -> int:
    return tm * tn // 8 + tm // 4 - 2


def safe(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) < 300


def load_e8_fifo() -> tuple[list[int], dict[int, dict[int, dict[int, float]]]]:
    """Load FIFO T/MNK from E8-nol2 cache.

    Returns (gc_list, fifo_t) where fifo_t[gc][tn][tm] = T/MNK.
    gc_list is sorted list of all gc values found (including gc=0).
    """
    with open(E8_RESULTS) as f:
        cache = json.load(f)

    fifo_t: dict[int, dict[int, dict[int, float]]] = {}
    for entry in cache.values():
        ov = entry["overrides"]
        tm = ov["TILE_M"]
        tn = ov["TILE_N"]
        gc = ov["PRNG_FIFO_GEN_COST"]
        cy = entry["metrics"]["cycles"]
        t  = cy / MNK
        fifo_t.setdefault(gc, {}).setdefault(tn, {})[tm] = t

    gc_list = sorted(fifo_t)
    return gc_list, fifo_t


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Memory-B baseline: measure α_mem(TM, TN) ─────────────────────────────
    print("Running Memory-B baseline (TM × TN grid) …")
    mem_grid = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=_BASE,
        sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
        flags=FLAGS_MEM,
    )

    mem_t: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in mem_grid:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        mem_t[tn][tm] = r.metrics.cycles / MNK

    # ── Load FIFO results from E8-nol2 cache ─────────────────────────────────
    print("Loading FIFO-B results from E8-nol2 cache …")
    gc_list, fifo_t = load_e8_fifo()
    gc_list_nonzero = [gc for gc in gc_list if gc > 0]

    # ── Memory-B α table by TN ────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("Memory-B α(TM, TN)  (--Bsource mem, L1-only, no L2)")
    print(f"{'═'*72}")
    header = f"{'TM':>5}  {'safe':>5}"
    for tn in TN_SWEEP:
        header += f"  {'TN='+str(tn):>9}"
    print(header)
    print("─" * len(header))
    for tm in TM_SWEEP:
        row = f"{tm:>5}  {'✓' if safe(tm,32) else '✗':>5}"
        for tn in TN_SWEEP:
            a = mem_t[tn].get(tm, float("nan"))
            flag = "" if safe(tm, tn) else "*"
            row += f"  {a:>8.4f}{flag:<1}"
        print(row)
    print("  (* WS unsafe, ws_lines ≥ 300)")

    # ── Per-TN optimal Memory-B tile ─────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("Memory-B optimal TM* per TN")
    print(f"{'═'*72}")
    mem_best: dict[int, tuple[int, float]] = {}
    for tn in TN_SWEEP:
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
        tm_star  = min(safe_tms, key=lambda tm: mem_t[tn][tm])
        t_star   = mem_t[tn][tm_star]
        mem_best[tn] = (tm_star, t_star)
        print(f"  TN={tn:>2}:  TM*_mem={tm_star:>3},  α_mem={t_star:.4f}")

    # ── FIFO-B α table at gc=0 by TN ─────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("FIFO-B α(TM, TN) at gc=0  (from E8-nol2 cache)")
    print(f"{'═'*72}")
    alpha0 = fifo_t.get(0, {})
    header = f"{'TM':>5}"
    for tn in TN_SWEEP:
        header += f"  {'TN='+str(tn):>9}"
    print(header)
    print("─" * len(header))
    for tm in TM_SWEEP:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            a = alpha0.get(tn, {}).get(tm, float("nan"))
            flag = "" if safe(tm, tn) else "*"
            row += f"  {a:>8.4f}{flag:<1}"
        print(row)

    # ── FIFO-B vs Memory-B comparison per TN ─────────────────────────────────
    print(f"\n{'═'*72}")
    print("FIFO-B vs Memory-B — head-to-head at optimal TM*")
    print(f"{'═'*72}")

    for tn in TN_SWEEP:
        tm_star_mem, t_mem = mem_best[tn]
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]

        # FIFO best per gc
        fifo_best: dict[int, tuple[int, float]] = {}
        for gc in gc_list_nonzero:
            gc_tn = fifo_t[gc].get(tn, {})
            if not gc_tn:
                continue
            tm_star = min(safe_tms, key=lambda tm: gc_tn.get(tm, float("inf")))
            fifo_best[gc] = (tm_star, gc_tn[tm_star])

        print(f"\n{'━'*68}")
        print(f"  TN = {tn}   |   Memory-B baseline: TM*={tm_star_mem}, α_mem={t_mem:.4f}")
        print(f"{'━'*68}")
        print(f"  {'gc':>5}  {'TM*_F':>6}  {'T_FIFO':>8}  {'T_mem':>7}  "
              f"{'speedup':>8}  {'winner':>6}")
        print("  " + "─" * 52)

        crossover = None
        for gc in gc_list_nonzero:
            if gc not in fifo_best:
                continue
            tm_f, t_f = fifo_best[gc]
            speedup = t_mem / t_f
            winner  = "FIFO" if speedup >= 1.0 else "mem"
            if crossover is None and speedup < 1.0:
                crossover = gc
            print(f"  {gc:>5}  {tm_f:>6}  {t_f:>8.4f}  {t_mem:>7.4f}  "
                  f"{speedup:>8.4f}  {winner}")

        fifo_wins = sum(1 for gc, (tm, t) in fifo_best.items() if t < t_mem)
        total     = len(fifo_best)
        print(f"\n  FIFO wins: {fifo_wins}/{total} gc values")
        if crossover is not None:
            prev = [gc for gc in gc_list_nonzero if gc < crossover and gc in fifo_best]
            bracket_lo = prev[-1] if prev else "?"
            print(f"  Crossover gc* ∈ ({bracket_lo}, {crossover}]")
        else:
            print(f"  FIFO wins at all tested gc values")

    # ── Per-TN summary ────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("SUMMARY — crossover gc* and FIFO advantage at low gc")
    print(f"{'═'*72}")
    print(f"  {'TN':>4}  {'α_mem(TM*)':>11}  {'α_FIFO(gc=0)':>13}  "
          f"{'FIFO adv (%)':>13}  {'crossover gc*':>14}")
    print("  " + "─" * 62)

    for tn in TN_SWEEP:
        tm_star_mem, t_mem = mem_best[tn]
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
        # FIFO at gc=0: find best safe TM
        alpha0_tn = alpha0.get(tn, {})
        if alpha0_tn:
            tm_star_f0 = min(safe_tms, key=lambda tm: alpha0_tn.get(tm, float("inf")))
            t_f0       = alpha0_tn[tm_star_f0]
            adv        = 100 * (t_mem - t_f0) / t_mem
        else:
            t_f0 = float("nan")
            adv  = float("nan")

        # crossover
        crossover_str = "—"
        prev_gc = None
        for gc in gc_list_nonzero:
            gc_tn = fifo_t[gc].get(tn, {})
            if not gc_tn:
                continue
            tm_f = min(safe_tms, key=lambda tm: gc_tn.get(tm, float("inf")))
            t_f  = gc_tn[tm_f]
            if t_f >= t_mem:
                lo = prev_gc if prev_gc is not None else "?"
                crossover_str = f"({lo}, {gc}]"
                break
            prev_gc = gc

        print(f"  {tn:>4}  {t_mem:>11.4f}  {t_f0:>13.4f}  "
              f"{adv:>12.1f}%  {crossover_str:>14}")

    # ── Physical interpretation ───────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("Physical interpretation")
    print(f"{'═'*72}")
    print()
    print(f"  L1-only hierarchy: L1={L1//1024}KB → DRAM ({MEM_LAT} cy).  No L2 buffer.")
    print()
    print("  Memory-B: each B element loaded from DRAM on first access within a")
    print("  tile pass.  The B tile (TK×TN×4 bytes) fits in L1 only at small TN:")
    for tn in TN_SWEEP:
        b_kb = TK * tn * A_P // 1024
        fits = "fits in L1" if TK * tn * A_P <= L1 else "DRAM-bound"
        print(f"    TN={tn:>2}: B tile = {b_kb:>2} KB  → {fits}")
    print()
    print("  FIFO-B: B never touches L1; A and C compete only with each other.")
    print("  Cold-fill penalty C = (MEM_LAT − L1_LAT) / (REG_M × REG_K)")
    print(f"                      = ({MEM_LAT} − {L1_LAT}) / {REG_M * REG_K} = "
          f"{(MEM_LAT - L1_LAT) / (REG_M * REG_K):.1f} cycles/FMA × (1/TN)")


if __name__ == "__main__":
    run()
