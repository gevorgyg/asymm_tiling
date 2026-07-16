"""E8-nol2: Dense gc sweep across TM* transition boundaries.

In the L2 case (E8), there were three TM* transitions at TN=32:
  gc ≈ 104  →  TM* shifts  32 → 48
  gc ≈ 171  →  TM* shifts  48 → 64
  gc ≈ 252  →  TM* shifts  64 → 128
All three were within the DRAM regime (TM > 64 was safe in L2).

In L1-only the structure is fundamentally different:
  - TM=96 is overflow at TN=32 (WS=406 >> 256) → no high-TM tiles available.
  - The only transition at TN=32 is:
      gc ≈ 42:  TM* shifts  12 (L1 regime) → 64 (DRAM regime)
    After this, TM=64 is optimal for all gc.

The transition shifts with TN (because α(TM, TN) depends on TN in DRAM regime):
  TN= 4:  gc* ≈ 71  (TM=12 → TM=96, A-penalty = 11/4  = 2.75)
  TN= 8:  gc* ≈ 55  (TM=12 → TM=96, A-penalty = 11/8  = 1.38)
  TN=16:  gc* ≈ 46  (TM=12 → TM=96, A-penalty = 11/16 = 0.69)
  TN=32:  gc* ≈ 42  (TM=12 → TM=64, TM=96 overflow)
  TN=64:  no L1→DRAM transition (TM=32 wins for all gc at TN=64)

GC_SWEEP is dense near each boundary and sparse elsewhere:
  Deep low:          15, 30
  Near TN=32 (gc≈42): 38, 42, 47
  Near TN=16 (gc≈46): covered by 42, 47
  Near TN=8  (gc≈55): 52, 57
  Near TN=4  (gc≈71): 68, 74
  High gc:           100, 150, 250, 400

Three predictions are compared for every (gc, TN):
  E3-nol2 α:  uses α(TM) from E3-nol2 at TN=32 — TN-blind.
  Calibrated:  uses α(TM, TN) from gc=0 sweep (cache hits from E6-nol2).
  Formula:     α_E3(TM) + C × (1/TN − 1/32), C = 11.0  — analytic, no calibration.
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
M = 192
N = K = 256
TK        = K

MNK = M * N * K

L1_BOUNDARY_TM = L1 // (TK * A_P)   # = 16

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

# Dense near each TN-specific boundary; sparse elsewhere.
# gc=0 and gc=50 are cache hits from E6-nol2 and are included at no extra cost.
GC_SWEEP = [15, 30, 38, 42, 47, 50, 52, 57, 68, 74, 100, 150, 250, 400]

# α(TM, TN=32) from E3-nol2 — the TN-blind baseline
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

# Analytical formula: α(TM, TN) ≈ α_E3(TM) + C × (1/TN − 1/32)
# C = 0 for L1-regime (TM ≤ 12), C = 11.0 for DRAM-regime (TM ≥ 16)
_C_L1   = 0.0
_C_DRAM = (MEM_LAT - L1_LAT) / (REG_M * REG_K)   # = 11.0


def alpha_formula(tm: int, tn: int) -> float:
    c = _C_L1 if tm <= 12 else _C_DRAM
    return ALPHA_E3[tm] + c * (1 / tn - 1 / 32)


def ws_lines(tm: int, tn: int) -> int:
    return tm * tn // 8 + tm // 4 - 2


def safe(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) < 300


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── gc=0 calibration (all cache hits from E6-nol2) ────────────────────────
    print("\nRunning gc=0 calibration (expect all cache hits from E6-nol2) …")
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

    # ── Formula accuracy check ────────────────────────────────────────────────
    print("\n── Formula accuracy vs calibrated α (% error) ──")
    header = f"{'TM':>5}" + "".join(f"  {'TN='+str(tn):>8}" for tn in TN_SWEEP)
    print(header)
    print("-" * len(header))
    for tm in TM_SWEEP:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            meas = alpha_calib[tn].get(tm, float("nan"))
            pred = alpha_formula(tm, tn)
            err  = 100 * (pred - meas) / meas
            flag = " " if safe(tm, tn) else "*"
            row += f"  {err:>+6.2f}%{flag}"
        print(row)

    # ── gc sweep ──────────────────────────────────────────────────────────────
    print(f"\nRunning {len(GC_SWEEP)} gc values × {len(TM_SWEEP)}×{len(TN_SWEEP)} grid …")
    all_gc_results: dict[int, list] = {}
    for gc in GC_SWEEP:
        results = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**_BASE, "PRNG_FIFO_GEN_COST": gc},
            sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
            flags=FLAGS,
        )
        all_gc_results[gc] = results

    # ── Summary table ─────────────────────────────────────────────────────────
    def e3_pred(gc: int, tn: int) -> int:
        cands = [tm for tm in TM_SWEEP if safe(tm, tn)]
        return min(cands, key=lambda tm: max(ALPHA_E3[tm], gc / tm))

    print("\n" + "═" * 96)
    print("SUMMARY — empirical TM* vs three predictions  [C=calib  F=formula  E=E3-nol2]")
    print("═" * 96)
    header = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>14}" for tn in TN_SWEEP)
    sub    = f"  {'':>5}" + f"  {'emp C F E':>14}" * len(TN_SWEEP)
    print(header)
    print(sub)
    print("  " + "─" * (len(header) - 2))

    for gc in GC_SWEEP:
        row = f"  {gc:>5}"
        for tn in TN_SWEEP:
            safe_rows = [
                (r.overrides["TILE_M"], r.metrics.cycles)
                for r in all_gc_results[gc]
                if r.overrides["TILE_N"] == tn and safe(r.overrides["TILE_M"], tn)
            ]
            if not safe_rows:
                row += f"  {'---':>14}"
                continue
            empirical  = min(safe_rows, key=lambda x: x[1])[0]
            safe_tms   = [tm for tm in TM_SWEEP if safe(tm, tn)]
            cal_pred   = min(safe_tms, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            form_pred  = min(safe_tms, key=lambda tm: max(alpha_formula(tm, tn), gc / tm))
            e3_p       = e3_pred(gc, tn)
            c_ok = "✓" if empirical == cal_pred  else "✗"
            f_ok = "✓" if empirical == form_pred else "✗"
            e_ok = "✓" if empirical == e3_p      else "✗"
            row += f"  {empirical:>3} {c_ok}{f_ok}{e_ok}{'':>6}"
        print(row)

    # ── TM* trajectory per TN ────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("TM* vs gc trajectory (empirical best safe tile)")
    print("═" * 72)
    header2 = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>8}" for tn in TN_SWEEP)
    print(header2)
    print("  " + "─" * (len(header2) - 2))
    for gc in GC_SWEEP:
        row = f"  {gc:>5}"
        for tn in TN_SWEEP:
            safe_rows = [
                (r.overrides["TILE_M"], r.metrics.cycles)
                for r in all_gc_results[gc]
                if r.overrides["TILE_N"] == tn and safe(r.overrides["TILE_M"], tn)
            ]
            if not safe_rows:
                row += f"  {'---':>8}"
                continue
            best = min(safe_rows, key=lambda x: x[1])[0]
            row += f"  {best:>8}"
        print(row)

    # ── Detailed view at boundary gc values ──────────────────────────────────
    BOUNDARY_GC = [38, 42, 47, 52, 57, 68, 74]
    print(f"\n{'═'*72}")
    print("BOUNDARY DETAIL — T/MNK per TM at transition gc values  (TN=32 focus)")
    print("═" * 72)

    for gc in BOUNDARY_GC:
        print(f"\n{'━'*60}")
        print(f"  gc = {gc}")
        print("━" * 60)
        for tn in [32, 16, 8, 4]:
            rows = sorted(
                [(r.overrides["TILE_M"], r.metrics.cycles)
                 for r in all_gc_results[gc] if r.overrides["TILE_N"] == tn],
                key=lambda x: x[0],
            )
            safe_rows  = [(tm, cy) for tm, cy in rows if safe(tm, tn)]
            if not safe_rows:
                continue
            empirical  = min(safe_rows, key=lambda x: x[1])[0]
            cal_pred   = min(
                [tm for tm in TM_SWEEP if safe(tm, tn)],
                key=lambda tm: max(alpha_calib[tn][tm], gc / tm),
            )
            form_pred  = min(
                [tm for tm in TM_SWEEP if safe(tm, tn)],
                key=lambda tm: max(alpha_formula(tm, tn), gc / tm),
            )
            e3_p = e3_pred(gc, tn)
            print(f"\n  TN={tn}  emp={empirical}  calib={cal_pred}  "
                  f"formula={form_pred}  E3={e3_p}")
            print(f"  {'TM':>5}  {'T/MNK':>8}  {'calib':>9}  {'formula':>9}  "
                  f"{'E3':>9}  {'safe':>5}")
            print("  " + "─" * 55)
            for tm, cy in rows:
                t    = cy / MNK
                tc   = max(alpha_calib[tn][tm], gc / tm)
                tf   = max(alpha_formula(tm, tn), gc / tm)
                te   = max(ALPHA_E3[tm], gc / tm)
                s    = safe(tm, tn)
                flag = "  ← best" if tm == empirical else \
                       ("  ← OVF" if not s else "")
                print(f"  {tm:>5}  {t:>8.4f}  {tc:>9.4f}  {tf:>9.4f}  "
                      f"{te:>9.4f}  {'✓' if s else '✗':>5}{flag}")


if __name__ == "__main__":
    run()
