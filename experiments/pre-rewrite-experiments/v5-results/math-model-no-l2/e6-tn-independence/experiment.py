"""E6-nol2: Full α(TM, TN) surface and TM* shift in L1-only.

In L2 (E6): TN-independence held — C ≈ 0.625/TN was negligible → TM* = 48
for all TN regardless of TN value.

In L1-only: C ≈ 11.0/TN (from E3-nol2). At small TN the penalty on
DRAM-regime tiles is large enough to shift TM* toward L1-regime tiles.

Two parts mirror the L2 E6 structure:

  Part 1 — E3-nol2 α table (calibrated at TN=32, ignores TN dependence):
    Prediction: TM* = 64 for all TN  (α minimum at TN=32 is TM=64).
    Expected:   MISMATCH at small TN — model underestimates DRAM-tile α.

  Part 2 — α(TM, TN) calibrated per cell at gc=0 (measured here):
    Prediction: TM* follows the correctly penalized α → shifts at small TN.
    Expected:   MATCH for all safe (TM, TN) pairs.

gc = 50: α-dominated regime (TM=64 crossover gc* = α×TM ≈ 3.49×64 = 223 ≫ 50),
so TN's effect on α is the dominant factor in TM* selection.

Working-set overflow: some (TM, TN) pairs exceed L1 capacity.
  WS = TM×TN/8 + TM/4 − 2  lines between consecutive C[i,j] accesses.
  WS ≥ 256  → C lines evicted → α spikes (marked * in tables).
  WS ∈ [256, 300]: borderline — empirically tolerable (small eviction rate).
  WS > 300: catastrophic (TM=96, TN=32 is the canonical example, α=9.03).
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
A_P = C_P = 4
LINE      = 64
L1        = 16_384
L1_LAT    = 4
MEM_LAT   = 180
REG_N = REG_M = REG_K = 4
M = 192      # divisors include TM ∈ {4, 8, 12, 16, 24, 32, 48, 64, 96}
N = K = 256
TK        = K

MNK = M * N * K

L1_BOUNDARY_TM = L1 // (TK * A_P)   # = 16
C_FORMULA      = (MEM_LAT - L1_LAT) / (REG_M * REG_K)   # = 11.0

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True,
              mulac_norecord=True, no_l2=True)

_BASE: dict[str, object] = {
    "A_HEIGHT_DIM":       M,
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "TILE_K":             TK,
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,
}

TM_SWEEP = [8, 12, 16, 24, 32, 48, 64, 96]
TN_SWEEP  = [4, 8, 16, 32, 64]

# α(TM, TN=32) from E3-nol2 — used as the TN-blind baseline in Part 1
ALPHA_E3: dict[int, float] = {
    8:   3.3958,
    12:  3.3133,
    16:  3.5811,
    24:  3.5387,
    32:  3.5174,
    48:  3.4959,
    64:  3.4849,
    96:  9.0329,
}

GC = 50


def ws_lines(tm: int, tn: int) -> int:
    """Cache lines between consecutive accesses to the same C line."""
    return tm * tn // 8 + tm // 4 - 2


def overflow(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) >= L1 // LINE   # WS ≥ 256


def safe(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) < 300   # tolerable; excludes catastrophic overflow


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── gc=GC sweep ───────────────────────────────────────────────────────────
    print(f"\nRunning gc={GC} sweep: {len(TM_SWEEP)}×{len(TN_SWEEP)} grid …")
    grid_gc = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "PRNG_FIFO_GEN_COST": GC},
        sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    # ── gc=0 calibration sweep ────────────────────────────────────────────────
    print(f"\nRunning gc=0 calibration sweep: {len(TM_SWEEP)}×{len(TN_SWEEP)} grid …")
    grid_gc0 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "PRNG_FIFO_GEN_COST": 0},
        sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in grid_gc0:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        alpha_calib[tn][tm] = r.metrics.cycles / MNK

    # ── α(TM, TN) table ──────────────────────────────────────────────────────
    print(f"\n{'═'*76}")
    print("α(TM, TN) TABLE  (gc=0, no-l2)")
    print(f"{'═'*76}")
    print(f"  A L1 boundary: TM={L1_BOUNDARY_TM} (A tile = TM×{TK}×{A_P} = L1={L1//1024}KB)")
    print(f"  WS overflow formula: TM×TN/8 + TM/4 − 2 ≥ 256  →  marked (*)")
    print(f"  Catastrophic overflow (WS ≥ 300): marked (**)\n")

    header = f"{'TM':>5}  {'regime':>5}"
    for tn in TN_SWEEP:
        header += f"  {'TN='+str(tn):>9}"
    header += f"  {'E3(32)':>8}"
    print(header)
    print("-" * len(header))

    for tm in TM_SWEEP:
        regime = "L1" if tm * TK * A_P <= L1 else "DRAM"
        row = f"{tm:>5}  {regime:>5}"
        for tn in TN_SWEEP:
            a   = alpha_calib[tn].get(tm, float("nan"))
            ws  = ws_lines(tm, tn)
            if ws >= 300:
                flag = "**"
            elif ws >= 256:
                flag = "*"
            else:
                flag = ""
            row += f"  {a:>7.4f}{flag:<2}"
        row += f"  {ALPHA_E3.get(tm, float('nan')):>8.4f}"
        print(row)

    print("  (* WS ≥ 256 lines: borderline;  ** WS ≥ 300 lines: catastrophic)")

    # ── Cold-fill coefficient C per DRAM-regime TM ───────────────────────────
    print(f"\n{'═'*76}")
    print("COLD-FILL COEFFICIENT C  (DRAM-regime tiles, safe points only)")
    print(f"{'═'*76}")
    print(f"  Model: α(TM, TN) = α₀(TM) + C/TN")
    print(f"  Formula:  C = (MEM_lat − L1_lat) / (REG_M × REG_K)"
          f" = ({MEM_LAT}−{L1_LAT}) / {REG_M*REG_K} = {C_FORMULA:.1f}\n")
    print(f"  {'TM':>5}  {'safe pts':>8}  {'α₀':>8}  {'C (fit)':>9}  "
          f"{'C (formula)':>12}  {'err%':>7}")
    print("  " + "-" * 55)

    for tm in TM_SWEEP:
        if tm * TK * A_P <= L1:
            continue
        pts = [(tn, alpha_calib[tn][tm])
               for tn in TN_SWEEP if not overflow(tm, tn)]
        if len(pts) < 2:
            print(f"  {tm:>5}  {len(pts):>8}  (too few safe points)")
            continue
        n   = len(pts)
        x   = [1.0 / tn for tn, _ in pts]
        y   = [a         for _,  a in pts]
        xm  = sum(x) / n
        ym  = sum(y) / n
        cov = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, y))
        var = sum((xi - xm) ** 2          for xi     in x)
        c_fit = cov / var
        a0    = ym - c_fit * xm
        err   = 100 * (c_fit - C_FORMULA) / C_FORMULA
        print(f"  {tm:>5}  {n:>8}  {a0:>8.4f}  {c_fit:>9.4f}  "
              f"{C_FORMULA:>12.1f}  {err:>+7.2f}%")

    # ── Part 1: TN-blind model (E3-nol2 α at TN=32) ──────────────────────────
    print(f"\n{'═'*76}")
    print("PART 1 — TM* using E3-nol2 α (calibrated at TN=32 only)")
    print(f"  gc={GC}. Baseline: TM*=64 (α minimum at TN=32).")
    print(f"  Expectation: FAIL at small TN — DRAM-tile α is underestimated.")
    print("═" * 76)
    _print_analysis(grid_gc, TN_SWEEP, TM_SWEEP, MNK, GC,
                    alpha_fn=lambda tm, _: ALPHA_E3[tm],
                    label="E3-nol2 α")

    # ── Part 2: TN-aware calibrated α ────────────────────────────────────────
    print(f"\n{'═'*76}")
    print("PART 2 — TM* using calibrated α(TM, TN) from gc=0")
    print(f"  gc={GC}. TN-dependent α should predict the correct TM* shift.")
    print(f"  Expectation: MATCH for all TN.")
    print("═" * 76)
    _print_analysis(grid_gc, TN_SWEEP, TM_SWEEP, MNK, GC,
                    alpha_fn=lambda tm, tn: alpha_calib[tn][tm],
                    label="calib α")


def _print_analysis(
    grid_gc,
    tn_sweep: list[int],
    tm_sweep: list[int],
    mnk: int,
    gc: int,
    alpha_fn,
    label: str,
) -> None:
    summary: list[tuple[int, int, int, bool]] = []

    for tn in tn_sweep:
        rows = sorted(
            [(r.overrides["TILE_M"], r.metrics.cycles)
             for r in grid_gc if r.overrides["TILE_N"] == tn],
            key=lambda x: x[0],
        )
        safe_rows  = [(tm, cy) for tm, cy in rows if safe(tm, tn)]
        if not safe_rows:
            continue

        empirical  = min(safe_rows, key=lambda x: x[1])[0]
        cands      = [tm for tm in tm_sweep if safe(tm, tn)]
        predicted  = min(cands, key=lambda tm: max(alpha_fn(tm, tn), gc / tm))
        match      = empirical == predicted
        summary.append((tn, predicted, empirical, match))

        print(f"\n  TN={tn}  |  {label}: TM*={predicted}  |  "
              f"empirical TM*={empirical}  {'✓' if match else '✗ MISMATCH'}")
        print(f"  {'TM':>5}  {'WS':>5}  {'safe':>5}  {'T/MNK':>8}  "
              f"{'T_pred':>8}  {'err%':>7}")
        print("  " + "-" * 50)

        for tm, cy in rows:
            ws_  = ws_lines(tm, tn)
            s    = safe(tm, tn)
            t    = cy / mnk
            tp   = max(alpha_fn(tm, tn), gc / tm)
            err  = 100 * (t - tp) / tp
            flag = ""
            if tm == empirical:
                flag = "  ← best"
            elif not s:
                flag = "  ← overflow"
            print(f"  {tm:>5}  {ws_:>5}  {'✓' if s else '✗':>5}  {t:>8.4f}  "
                  f"{tp:>8.4f}  {err:>+7.2f}%{flag}")

    print(f"\n── {label} summary: TM* per TN (gc={gc}) ──")
    print(f"  {'TN':>4}  {'predicted':>9}  {'empirical':>9}  {'match':>5}")
    print("  " + "-" * 34)
    for tn, pred, emp, match in summary:
        print(f"  {tn:>4}  {pred:>9}  {emp:>9}  {'✓' if match else '✗':>5}")


if __name__ == "__main__":
    run()
