"""E8: Dense gc sweep across TM* transition boundaries, plus α formula test.

The E3 model (TN-independent) predicts TM* transitions at:
  gc ≈ 103.6  →  TM* shifts  32 → 48   [α(32)×32  = 3.237×32]
  gc ≈ 170.9  →  TM* shifts  48 → 64   [α(64)×48  = 3.560×48]
  gc ≈ 251.9  →  TM* shifts  64 → 128  [α(128)×64 = 3.936×64]

For each boundary we test gc values just below and just above.  We also
include "deep regime" values far from any boundary (gc=64,130,230,380,600)
and extend the TN sweep to {4,8,16,32,64} — adding TN=8 (R=2) not in E7.

Two predictions are compared for every (gc, TN):
  E3 prediction: uses α(TM) calibrated at TN=32 only — TN-independent.
  Calibrated:    uses α(TM, TN) from a fresh gc=0 sweep — per-(TM,TN).

Additionally we test an ANALYTICAL α formula (no calibration required):
  α_formula(TM, TN) ≈ α_E3(TM) + C(TM) × (1/TN − 1/32)
where C(TM) = (L_cache(TM) − L1_lat) / (reg_m × reg_k):
  C ≈ 0.625  in L2 regime   (TM ≤ 48, L_cache = L2_lat = 14 cy)
  C ≈ 12.0   in DRAM regime (TM ≥ 64, effective L_cache ≈ 198 cy back-estimated from E6)

The formula captures the cold-fill correction from A-tile L2/DRAM misses on
the first rtj pass of each session.  It should work within ~2% for TN ≤ 32;
we test whether it also predicts TM* correctly.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
A_P = C_P = 4
LINE = 64
L1   = 16_384
L2   = 4 * L1
REG_N = REG_M = REG_K = 4
L1_LAT = 4
L2_LAT = 14

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True, mulac_norecord=True)

_BASE_192: dict[str, object] = {
    "A_HEIGHT_DIM":        192,
    "A_WIDTH_DIM":         256,
    "B_WIDTH_DIM":         256,
    "A_PRECISION_BYTES":   A_P,
    "B_PRECISION_BYTES":   A_P,
    "L1_SIZE_BYTES":       L1,
    "L1_LINE_SIZE_BYTES":  LINE,
    "L1_ASSOC":            L1 // LINE,
    "L2_SIZE_BYTES":       L2,
    "L2_LINE_SIZE_BYTES":  LINE,
    "L2_ASSOC":            L2 // LINE,
    "L2_ACCESS_CYCLES":    L2_LAT,
    "PRNG_FIFO_CAPACITY":  2 * 256 * 32,
    "TILE_K":              256,
}
_BASE_256 = {**_BASE_192, "A_HEIGHT_DIM": 256}

TM_M192 = [8, 16, 24, 32, 48, 64, 96]
TM_M256 = [128]
TN_SWEEP = [4, 8, 16, 32, 64]

# ── gc sweep ──────────────────────────────────────────────────────────────────
# Boundary 32→48 at gc≈103.6:  below(100), at(104), above(108)
# Boundary 48→64 at gc≈170.9:  below(165), at(171), above(175)
# Boundary 64→128 at gc≈251.9: below(248), at(252), above(256)
# Deep-regime anchors: 64 (TM*=32), 130 (TM*=48), 230 (TM*=64), 380 (TM*=128), 600
GC_SWEEP = [64, 100, 104, 108, 130, 165, 171, 175, 230, 248, 252, 256, 380, 600]

# E3 α table (calibrated at gc=0, TN=32)
ALPHA_E3: dict[int, float] = {
    8:   3.3996,
    16:  3.2995,
    24:  3.2587,
    32:  3.2369,
    48:  3.2550,
    64:  3.5604,
    96:  3.9398,
    128: 3.9363,
}

# Analytical α formula correction coefficient per regime
# C(TM) = (L_cache(TM) − L1_lat) / (reg_m × reg_k)
# L2 regime: C = (14−4)/16 = 0.625
# DRAM regime: C ≈ (198−4)/16 ≈ 12.1  (effective DRAM_lat ≈ 198 cy from E6 back-estimate)
_C_L2   = (L2_LAT - L1_LAT) / (REG_M * REG_K)     # 0.625
_C_DRAM = 12.0                                       # estimated from E6 calibration

def alpha_formula(tm: int, tn: int) -> float:
    """Analytical prediction: α_E3(TM) + C(TM) × (1/TN − 1/32)."""
    c = _C_L2 if tm <= 48 else _C_DRAM
    return ALPHA_E3[tm] + c * (1 / tn - 1 / 32)

def tm_star_formula(gc: int, tn: int, valid_tms: list[int]) -> int:
    """TM* from analytical formula (no calibration)."""
    return min(valid_tms, key=lambda tm: max(alpha_formula(tm, tn), gc / tm))

def mnk(m: int) -> int:
    return m * 256 * 256

def c_tile_bytes(tm: int, tn: int) -> int:
    return tm * tn * C_P


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    all_tm = TM_M192 + TM_M256

    # ── gc=0 calibration for all TN (including new TN=8) ─────────────────────
    print("Running gc=0 calibration: M=192 grid …")
    calib_192 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE_192, "PRNG_FIFO_GEN_COST": 0},
        sweep_axes={"TILE_M": TM_M192, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )
    print("Running gc=0 calibration: M=256 grid (TM=128) …")
    calib_256 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE_256, "PRNG_FIFO_GEN_COST": 0},
        sweep_axes={"TILE_M": TM_M256, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    # Build α_calib[tn][tm] table
    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in calib_192 + calib_256:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        m  = r.overrides["A_HEIGHT_DIM"]
        alpha_calib[tn][tm] = r.metrics.cycles / mnk(m)

    # ── Print calibrated α table ──────────────────────────────────────────────
    print("\n── Calibrated α(TM, TN) table (gc=0 sweep) ──")
    header = f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP) + "  formula(TN=8)"
    print(header)
    print("-" * len(header))
    for tm in all_tm:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            f_alpha = alpha_formula(tm, tn)
            meas    = alpha_calib[tn][tm]
            err     = 100 * (f_alpha - meas) / meas
            row    += f"  {meas:>8.4f}"
        row += f"  {alpha_formula(tm, 8):>14.4f}"
        print(row)

    print("\n── Formula accuracy vs calibrated α (% error) ──")
    print(f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP))
    print("-" * (5 + 9 * len(TN_SWEEP)))
    for tm in all_tm:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            meas  = alpha_calib[tn][tm]
            pred  = alpha_formula(tm, tn)
            err   = 100 * (pred - meas) / meas
            row  += f"  {err:>+7.2f}%"
        print(row)

    # ── Run gc sweep ──────────────────────────────────────────────────────────
    all_gc_results: dict[int, list] = {}
    for gc in GC_SWEEP:
        print(f"\nRunning gc={gc}: M=192 grid …")
        g192 = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**_BASE_192, "PRNG_FIFO_GEN_COST": gc},
            sweep_axes={"TILE_M": TM_M192, "TILE_N": TN_SWEEP},
            flags=FLAGS,
        )
        print(f"Running gc={gc}: M=256 grid (TM=128) …")
        g256 = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**_BASE_256, "PRNG_FIFO_GEN_COST": gc},
            sweep_axes={"TILE_M": TM_M256, "TILE_N": TN_SWEEP},
            flags=FLAGS,
        )
        all_gc_results[gc] = g192 + g256

    # ── E3 transition predictions ─────────────────────────────────────────────
    def e3_pred(gc: int) -> int:
        return min(all_tm, key=lambda tm: max(ALPHA_E3[tm], gc / tm))

    # ── Summary table: empirical TM* vs three predictions ────────────────────
    print("\n" + "═" * 90)
    print("SUMMARY — empirical TM* vs predictions  [C=calib  F=formula  E=E3]")
    print("═" * 90)
    header = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>12}" for tn in TN_SWEEP) + "  E3-pred"
    sub    = f"  {'':>5}" + "".join(f"  {'emp C F E':>12}" for tn in TN_SWEEP)
    print(header)
    print(sub)
    print("  " + "─" * (len(header) - 2))

    for gc in GC_SWEEP:
        e3 = e3_pred(gc)
        row = f"  {gc:>5}"
        for tn in TN_SWEEP:
            rows = [
                (r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                for r in all_gc_results[gc]
                if r.overrides["TILE_N"] == tn
            ]
            empirical  = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            cal_pred   = min(all_tm, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            form_pred  = tm_star_formula(gc, tn, all_tm)
            c_ok = "✓" if empirical == cal_pred  else "✗"
            f_ok = "✓" if empirical == form_pred else "✗"
            e_ok = "✓" if empirical == e3        else "✗"
            row += f"  {empirical:>3} {c_ok}{f_ok}{e_ok}"
        row += f"  {e3:>8}"
        print(row)

    # ── Per-gc detailed view (near boundary cases) ────────────────────────────
    BOUNDARY_GC = [100, 104, 108, 165, 171, 175, 248, 252, 256]
    print("\n" + "═" * 90)
    print("BOUNDARY DETAIL — T/MNK per TM at crossing gc values")
    print("═" * 90)

    for gc in BOUNDARY_GC:
        e3 = e3_pred(gc)
        print(f"\n{'━'*70}")
        print(f"  gc = {gc}   |   E3-predicted TM* = {e3}")
        print(f"{'━'*70}")
        for tn in TN_SWEEP:
            rows = sorted(
                [(r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                 for r in all_gc_results[gc] if r.overrides["TILE_N"] == tn],
                key=lambda x: x[0],
            )
            empirical = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            cal_pred  = min(all_tm, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            form_pred = tm_star_formula(gc, tn, all_tm)
            print(f"\n  TN={tn}  empirical={empirical}  E3={e3}  calib={cal_pred}  formula={form_pred}")
            print(f"  {'TM':>5}  {'T/MNK':>8}  {'E3-pred':>9}  {'cal-pred':>9}  {'form-pred':>10}")
            print("  " + "─" * 52)
            for tm, m_h, cy in rows:
                t_per  = cy / mnk(m_h)
                tp_e3  = max(ALPHA_E3[tm], gc / tm)
                tp_cal = max(alpha_calib[tn][tm], gc / tm)
                tp_frm = max(alpha_formula(tm, tn), gc / tm)
                mark   = "  ← min" if tm == empirical else ""
                print(f"  {tm:>5}  {t_per:>8.4f}  {tp_e3:>9.4f}  {tp_cal:>9.4f}  {tp_frm:>10.4f}{mark}")


if __name__ == "__main__":
    run()
