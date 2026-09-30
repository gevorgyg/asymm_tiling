"""E9: TN into the L1-overflow regime.

E6 and E7 stayed within TN ≤ 64 where the C tile is ≤ 16 KB (= L1 at TM ≤ 64).
Here we push TN into overflow territory: TN=128 and TN=256.

C-tile sizes at TN=128 and TN=256 (C_P=4 bytes/element):
  TM=8,  TN=128: 8×128×4 =   4096 B  (fits in L1=16384)
  TM=16, TN=128: 16384 B = L1        (exactly full)
  TM=32, TN=128: 32768 B > L1        (overflows by 2×)
  TM=8,  TN=256: 8192 B               (fits)
  TM=16, TN=256: 32768 B > L1        (overflows)
  TM=32, TN=256: 65536 B = L2        (fills L2!)

Key questions:
  1. Does the calibrated model still correctly predict TM* when C overflows L1?
  2. Does TM* shift due to the increased α in overflow cells?
  3. Does the analytical α formula break down as expected at large TN?

We also include TN=64 (reference from E7) for continuity.
gc ∈ {64, 130, 230, 380} — same four gc values as E5/E7.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

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

# TN=64 is reference (from E7); TN=128 and TN=256 are the new overflow cases
TN_SWEEP = [64, 128, 256]
GC_SWEEP = [64, 130, 230, 380]

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

_C_L2   = (L2_LAT - L1_LAT) / (REG_M * REG_K)
_C_DRAM = 12.0

def alpha_formula(tm: int, tn: int) -> float:
    c = _C_L2 if tm <= 48 else _C_DRAM
    return ALPHA_E3[tm] + c * (1 / tn - 1 / 32)

def mnk(m: int) -> int:
    return m * 256 * 256

def c_tile_bytes(tm: int, tn: int) -> int:
    return tm * tn * C_P

def overflow_label(tm: int, tn: int) -> str:
    b = c_tile_bytes(tm, tn)
    if b < L1:
        return f"L1:{b//1024}K"
    elif b == L1:
        return "=L1"
    elif b < L2:
        return f">{L1//1024}K"
    else:
        return "≥L2"


def run() -> None:
    base = (workspace_root() / "default.config").read_text()
    all_tm = TM_M192 + TM_M256

    # ── gc=0 calibration for new TN values ───────────────────────────────────
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

    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in calib_192 + calib_256:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        m  = r.overrides["A_HEIGHT_DIM"]
        alpha_calib[tn][tm] = r.metrics.cycles / mnk(m)

    # ── Print calibrated α table with overflow annotations ───────────────────
    print("\n── Calibrated α(TM, TN) — overflow regime ──")
    print(f"  C-tile overflow at L1={L1//1024}KB: TM×TN×4 > {L1}")
    print()
    header = f"{'TM':>5}  {'C-tile':>8}" + "".join(
        f"  {'TN='+str(tn):>10}" for tn in TN_SWEEP
    ) + "  formula(TN=128)"
    print(header)
    print("-" * len(header))
    for tm in all_tm:
        ctile = c_tile_bytes(tm, TN_SWEEP[-1])
        row = f"{tm:>5}  {ctile:>8}"
        for tn in TN_SWEEP:
            meas = alpha_calib[tn][tm]
            flag = "!" if c_tile_bytes(tm, tn) >= L1 else " "
            row += f"  {meas:>8.4f}{flag:>2}"
        row += f"  {alpha_formula(tm, 128):>16.4f}"
        print(row)

    print("\n── Formula error at overflow TN values ──")
    print(f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP))
    print("-" * (5 + 9 * len(TN_SWEEP)))
    for tm in all_tm:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            meas  = alpha_calib[tn][tm]
            pred  = alpha_formula(tm, tn)
            err   = 100 * (pred - meas) / meas
            flag  = "*" if c_tile_bytes(tm, tn) >= L1 else " "
            row  += f"  {err:>+6.2f}%{flag}"
        print(row)
    print("  (* = C tile overflows L1)")

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

    def e3_pred(gc: int) -> int:
        return min(all_tm, key=lambda tm: max(ALPHA_E3[tm], gc / tm))

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n" + "═" * 80)
    print("SUMMARY — empirical TM* for all (gc, TN)  [C=calib  E=E3]")
    print("  '!' marks cells where C tile overflows L1 at empirical TM*")
    print("═" * 80)
    header = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>11}" for tn in TN_SWEEP) + "  E3-pred"
    sub    = f"  {'':>5}" + "".join(f"  {'emp C E':>11}" for tn in TN_SWEEP)
    print(header)
    print(sub)
    print("  " + "─" * (len(header) - 2))

    for gc in GC_SWEEP:
        e3 = e3_pred(gc)
        row = f"  {gc:>5}"
        for tn in TN_SWEEP:
            rows = [
                (r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                for r in all_gc_results[gc] if r.overrides["TILE_N"] == tn
            ]
            empirical = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            cal_pred  = min(all_tm, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            c_ok = "✓" if empirical == cal_pred else "✗"
            e_ok = "✓" if empirical == e3       else "✗"
            overflow = "!" if c_tile_bytes(empirical, tn) >= L1 else " "
            row += f"  {empirical:>3}{overflow}{c_ok}{e_ok}"
        row += f"  {e3:>8}"
        print(row)

    # ── Detailed per-(gc, TN) breakdown ──────────────────────────────────────
    print("\n" + "═" * 80)
    print("DETAILED — T/MNK per TM, showing α comparison in overflow regime")
    print("═" * 80)

    for gc in GC_SWEEP:
        e3 = e3_pred(gc)
        print(f"\n{'━'*70}")
        print(f"  gc = {gc}  |  E3-pred TM* = {e3}")
        print(f"{'━'*70}")
        for tn in TN_SWEEP:
            rows = sorted(
                [(r.overrides["TILE_M"], r.overrides["A_HEIGHT_DIM"], r.metrics.cycles)
                 for r in all_gc_results[gc] if r.overrides["TILE_N"] == tn],
                key=lambda x: x[0],
            )
            empirical = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
            cal_pred  = min(all_tm, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            print(f"\n  TN={tn}  empirical={empirical}  E3={e3}  calib={cal_pred}")
            print(f"  {'TM':>5}  {'C-tile':>8}  {'T/MNK':>8}  "
                  f"{'E3-pred':>9}  {'cal-pred':>9}  {'α_meas':>8}  {'α_E3':>8}")
            print("  " + "─" * 66)
            for tm, m_h, cy in rows:
                t_per  = cy / mnk(m_h)
                tp_e3  = max(ALPHA_E3[tm], gc / tm)
                tp_cal = max(alpha_calib[tn][tm], gc / tm)
                ctile  = overflow_label(tm, tn)
                mark   = "  ← min" if tm == empirical else ""
                print(f"  {tm:>5}  {ctile:>8}  {t_per:>8.4f}  "
                      f"{tp_e3:>9.4f}  {tp_cal:>9.4f}  "
                      f"{alpha_calib[tn][tm]:>8.4f}  {ALPHA_E3[tm]:>8.4f}{mark}")


if __name__ == "__main__":
    run()
