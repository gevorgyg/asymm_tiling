"""E7: TN independence of optimal TM across all gc values.

E6 tested TN independence at gc=130 only.  Here we sweep
gc ∈ {64, 130, 230, 380} × TN ∈ {4, 16, 32, 64} and ask:

  - Does TM* (empirical argmin) match the E3 prediction for every (gc, TN)?
  - If not, does the per-(TM,TN) calibrated α correctly predict the shift?

The interesting case is gc=230 where the E3-predicted TM*=64 sits at the
L2/DRAM boundary.  At TN=4, α(64, TN=4) ≈ 6.22 (from E6 calibration), so
the calibrated prediction could be TM=48 instead.  We test empirically.

For gc=380, TM*=128 requires M=256 (TM must divide M).
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
    "L2_ACCESS_CYCLES":    14,
    "PRNG_FIFO_CAPACITY":  2 * 256 * 32,
    "TILE_K":              256,
}
_BASE_256 = {**_BASE_192, "A_HEIGHT_DIM": 256}

TM_M192 = [8, 16, 24, 32, 48, 64, 96]
TM_M256 = [128]
TN_SWEEP = [4, 16, 32, 64]
GC_SWEEP = [64, 130, 230, 380]

# α(TM) from E3 (gc=0, TN=32) — TN-independent baseline
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

# Predicted TM* per gc using E3 α (from E5 results)
PREDICTED_TM_STAR: dict[int, int] = {64: 32, 130: 48, 230: 64, 380: 128}


def mnk(m: int) -> int:
    return m * 256 * 256


def c_tile_bytes(tm: int, tn: int) -> int:
    return tm * tn * C_P


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    all_tm = TM_M192 + TM_M256

    # ── gc=0 calibration ──────────────────────────────────────────────────────
    print("Running gc=0 calibration: M=192 grid (TM ≤ 96) …")
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

    # Build α(TM, TN) table from gc=0 runs
    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in calib_192 + calib_256:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        m  = r.overrides["A_HEIGHT_DIM"]
        alpha_calib[tn][tm] = r.metrics.cycles / mnk(m)

    # ── Print calibrated α(TM, TN) table ──────────────────────────────────────
    print("\n── Calibrated α(TM, TN) table (gc=0 runs) ──")
    header = f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP) + "  E3(TN=32)"
    print(header)
    print("-" * len(header))
    for tm in all_tm:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            row += f"  {alpha_calib[tn][tm]:>8.4f}"
        row += f"  {ALPHA_E3[tm]:>10.4f}"
        print(row)

    # ── Run gc sweeps ─────────────────────────────────────────────────────────
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

    # ── Detailed per-(gc, TN) analysis ────────────────────────────────────────
    print("\n" + "═" * 78)
    print("DETAILED ANALYSIS — T/MNK per (gc, TN, TM)")
    print("═" * 78)

    for gc in GC_SWEEP:
        e3_pred = PREDICTED_TM_STAR[gc]
        print(f"\n{'━'*78}")
        print(f"  gc = {gc}   |   E3-predicted TM* = {e3_pred}")
        print(f"{'━'*78}")

        for tn in TN_SWEEP:
            rows = [
                (r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                for r in all_gc_results[gc]
                if r.overrides["TILE_N"] == tn
            ]
            rows.sort(key=lambda x: x[0])

            empirical = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            calib_pred = min(all_tm,
                             key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            e3_match   = "✓" if empirical == e3_pred else "✗"
            cal_match  = "✓" if empirical == calib_pred else "✗"
            overflow   = "  [C overflows L1!]" if c_tile_bytes(tn, 64) >= L1 else ""

            print(f"\n  TN={tn}  |  empirical TM*={empirical}  "
                  f"E3-pred={e3_pred}{e3_match}  calib-pred={calib_pred}{cal_match}{overflow}")
            print(f"  {'TM':>5}  {'L1?':>4}  {'T/MNK':>8}  "
                  f"{'E3-pred':>9}  {'E3-err%':>8}  {'cal-pred':>9}  {'cal-err%':>8}")
            print("  " + "-" * 64)

            for tm, m_h, cy in rows:
                t_per  = cy / mnk(m_h)
                tp_e3  = max(ALPHA_E3[tm], gc / tm)
                tp_cal = max(alpha_calib[tn][tm], gc / tm)
                err_e3  = 100 * (t_per - tp_e3)  / tp_e3
                err_cal = 100 * (t_per - tp_cal) / tp_cal
                l1_ok   = "✓" if c_tile_bytes(tm, tn) < L1 else "✗"
                marker  = "  ← min" if tm == empirical else ""
                print(f"  {tm:>5}  {l1_ok:>4}  {t_per:>8.4f}  "
                      f"{tp_e3:>9.4f}  {err_e3:>+8.2f}%  "
                      f"{tp_cal:>9.4f}  {err_cal:>+8.2f}%{marker}")

    # ── Summary table ────────────────────────────────────────────────────────
    print("\n" + "═" * 78)
    print("SUMMARY — empirical TM* for all (gc, TN)  [E3-pred in rightmost col]")
    print("═" * 78)
    header = f"  {'gc':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP) + "  E3-pred"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for gc in GC_SWEEP:
        e3_pred = PREDICTED_TM_STAR[gc]
        row = f"  {gc:>5}"
        any_mismatch = False
        for tn in TN_SWEEP:
            rows = [
                (r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                for r in all_gc_results[gc]
                if r.overrides["TILE_N"] == tn
            ]
            empirical = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            marker = "✓" if empirical == e3_pred else "✗"
            if empirical != e3_pred:
                any_mismatch = True
            row += f"  {empirical:>4}{marker}"
        row += f"  {e3_pred:>8}"
        if any_mismatch:
            row += "  ← TM* shifted!"
        print(row)


if __name__ == "__main__":
    run()
