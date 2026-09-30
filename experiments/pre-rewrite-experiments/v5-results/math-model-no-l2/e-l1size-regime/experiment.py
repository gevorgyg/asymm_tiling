"""L1-size regime sweep: does the regime boundary shift with L1 size?

The L1/DRAM regime boundary for the A tile is:

    TM_L1 = L1 / (TK × A_P) = L1 / 1024

At the baseline L1=16KB: TM_L1=16 → effective boundary TM≤12.
Prediction for other L1 sizes:

  L1= 8KB:  TM_L1 = 8   → only TM=4 is firmly L1-regime; TM=8 is boundary
  L1=16KB:  TM_L1 = 16  → TM≤12 L1-regime       (baseline)
  L1=32KB:  TM_L1 = 32  → TM≤24 should be L1-regime (TN-independent)
  L1=64KB:  TM_L1 = 64  → TM≤48 should be L1-regime (TN-independent)

The cold-fill coefficient C = (DRAM_lat − L1_lat) / (REG_M × REG_K) = 11.0
does NOT depend on L1 size. Tiles that remain in DRAM regime should still
follow α(TM, TN) = α₀(TM) + 11.0/TN regardless of L1 size.

The WS overflow threshold also shifts: safe if WS < L1/LINE.
  L1= 8KB: safe for WS <  128  → TM=32,TN=32 (WS=270) is catastrophic!
  L1=16KB: safe for WS <  256  → TM=64,TN=32 (WS=270) is borderline
  L1=32KB: safe for WS <  512  → TM=96,TN=32 (WS=406) now safe!
  L1=64KB: safe for WS < 1024  → TM=96,TN=64 (WS=790) now safe!

What we measure: α(TM, TN) at gc=0 for each L1 size.
What we check:
  1. TN-independence threshold shifts with TM_L1 as predicted.
  2. C = 11.0 in whatever remains of the DRAM regime (invariant).
  3. WS overflow boundary shifts with L1/LINE.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Fixed hardware constants ──────────────────────────────────────────────────
A_P = C_P = 4
LINE      = 64
L1_LAT    = 4
MEM_LAT   = 180
REG_N = REG_M = REG_K = 4
M = 192
N = K = 256
TK        = K

MNK = M * N * K

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True,
              mulac_norecord=True, no_l2=True)

# L1 sizes to sweep (all must be multiples of LINE=64)
L1_SIZES = [8_192, 16_384, 32_768, 65_536]   # 8, 16, 32, 64 KB

TM_SWEEP = [8, 12, 16, 24, 32, 48, 64, 96]
TN_SWEEP  = [4, 8, 16, 32, 64]

C_FORMULA = (MEM_LAT - L1_LAT) / (REG_M * REG_K)   # = 11.0  (L1-size independent)


def tm_boundary(l1: int) -> int:
    """Theoretical A-tile L1 overflow boundary."""
    return l1 // (TK * A_P)


def ws_lines(tm: int, tn: int) -> int:
    return tm * tn // 8 + tm // 4 - 2


def overflow(tm: int, tn: int, l1: int) -> bool:
    return ws_lines(tm, tn) >= l1 // LINE


def catastrophic(tm: int, tn: int, l1: int) -> bool:
    return ws_lines(tm, tn) >= l1 // LINE + 50   # >10% over capacity


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Run gc=0 sweep for each L1 size ──────────────────────────────────────
    results_by_l1: dict[int, dict[int, dict[int, float]]] = {}

    for l1 in L1_SIZES:
        l1_kb = l1 // 1024
        print(f"\nRunning gc=0 sweep for L1={l1_kb}KB …")
        grid = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={
                "A_HEIGHT_DIM":       M,
                "A_WIDTH_DIM":        K,
                "B_WIDTH_DIM":        N,
                "A_PRECISION_BYTES":  A_P,
                "B_PRECISION_BYTES":  A_P,
                "L1_SIZE_BYTES":      l1,
                "L1_LINE_SIZE_BYTES": LINE,
                "L1_ASSOC":           l1 // LINE,
                "TILE_K":             TK,
                "PRNG_FIFO_GEN_COST": 0,
                "PRNG_FIFO_CAPACITY": 2 * TK * 32,
            },
            sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
            flags=FLAGS,
        )
        alpha: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
        for r in grid:
            tm = r.overrides["TILE_M"]
            tn = r.overrides["TILE_N"]
            alpha[tn][tm] = r.metrics.cycles / MNK
        results_by_l1[l1] = alpha

    # ── α(TM, TN) table for each L1 size ─────────────────────────────────────
    for l1 in L1_SIZES:
        l1_kb    = l1 // 1024
        boundary = tm_boundary(l1)
        alpha    = results_by_l1[l1]

        print(f"\n{'═'*76}")
        print(f"L1 = {l1_kb} KB   |   TM_L1 = {boundary}   |   "
              f"WS-safe threshold = {l1//LINE} lines")
        print(f"  A tile is L1-regime for TM < {boundary}  "
              f"(A tile = TM×{TK}×{A_P} ≤ {l1_kb}KB)")
        print("═" * 76)

        header = f"{'TM':>5}  {'regime':>5}"
        for tn in TN_SWEEP:
            header += f"  {'TN='+str(tn):>9}"
        print(header)
        print("-" * len(header))

        for tm in TM_SWEEP:
            a_bytes = tm * TK * A_P
            regime  = "L1" if a_bytes < l1 else "DRAM"
            row     = f"{tm:>5}  {regime:>5}"
            for tn in TN_SWEEP:
                a = alpha[tn].get(tm, float("nan"))
                ws = ws_lines(tm, tn)
                if ws >= l1 // LINE + 50:
                    flag = "**"
                elif ws >= l1 // LINE:
                    flag = "*"
                else:
                    flag = ""
                row += f"  {a:>7.4f}{flag:<2}"
            print(row)

        print("  (* WS borderline, ** catastrophic overflow)")

    # ── TN-independence test: does the boundary shift as predicted? ───────────
    print(f"\n{'═'*76}")
    print("TN-INDEPENDENCE CHECK: max α variation across TN (safe points only)")
    print(f"  C formula = (DRAM_lat − L1_lat) / (REG_M × REG_K)"
          f" = ({MEM_LAT}−{L1_LAT}) / {REG_M*REG_K} = {C_FORMULA:.1f}")
    print("  TM is TN-independent if variation < 0.01 (L1-regime).")
    print("  TM is TN-dependent with C≈11 if in DRAM regime.")
    print("═" * 76)

    header = f"{'TM':>5}"
    for l1 in L1_SIZES:
        header += f"  {'L1='+str(l1//1024)+'KB':>12}"
    print(header)
    print("-" * len(header))

    for tm in TM_SWEEP:
        row = f"{tm:>5}"
        for l1 in L1_SIZES:
            alpha = results_by_l1[l1]
            a_bytes = tm * TK * A_P
            safe_pts = [(tn, alpha[tn][tm]) for tn in TN_SWEEP
                        if not overflow(tm, tn, l1)]
            if len(safe_pts) < 2:
                row += f"  {'(overflow)':>12}"
                continue
            a_vals = [a for _, a in safe_pts]
            variation = max(a_vals) - min(a_vals)
            regime    = "L1" if a_bytes < l1 else "DRAM"
            marker    = " (indep)" if variation < 0.015 else f" (Δ={variation:.3f})"
            row += f"  [{regime}]{variation:>6.4f}{marker[:6]}"
        print(row)

    # ── C(TM) fit for DRAM-regime tiles at each L1 size ──────────────────────
    print(f"\n{'═'*76}")
    print("COLD-FILL COEFFICIENT C  (fit α = α₀ + C/TN, DRAM-regime, safe points)")
    print(f"  Prediction: C ≈ {C_FORMULA:.1f}  for all L1 sizes (L1-size independent)")
    print("═" * 76)

    header = f"{'TM':>5}  {'regime':>5}"
    for l1 in L1_SIZES:
        header += f"  {'L1='+str(l1//1024)+'KB (C)':>14}"
    print(header)
    print("-" * len(header))

    for tm in TM_SWEEP:
        row = f"{tm:>5}"
        for l1 in L1_SIZES:
            alpha   = results_by_l1[l1]
            a_bytes = tm * TK * A_P
            if a_bytes < l1:
                row += f"  {'[L1 regime]':>19}"
                continue
            pts = [(tn, alpha[tn][tm]) for tn in TN_SWEEP
                   if not overflow(tm, tn, l1)]
            if len(pts) < 2:
                row += f"  {'(no safe pts)':>19}"
                continue
            n   = len(pts)
            x   = [1.0 / tn for tn, _ in pts]
            y   = [a         for _,  a in pts]
            xm  = sum(x) / n;  ym = sum(y) / n
            cov = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, y))
            var = sum((xi - xm) ** 2         for xi     in x)
            c_fit = cov / var if var > 0 else float("nan")
            err   = 100 * (c_fit - C_FORMULA) / C_FORMULA
            row  += f"  {c_fit:>7.3f} ({err:>+5.1f}%)"
        print(row)


if __name__ == "__main__":
    run()
