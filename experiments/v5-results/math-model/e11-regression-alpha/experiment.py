"""E11: Regression-based α(TM, TN) formula.

The theoretical formula from E8 is:
    α(TM, TN) ≈ α_E3(TM) + C(TM) × (1/TN − 1/32)

It uses a hard-coded C(TM): 0.625 for L2 regime, 12.0 for DRAM.  The DRAM
value overshoots by ~15% (actual effective C ≈ 10.4 for TM=96,128), causing
+8-10% α errors at small TN.

E11 fits the model empirically:
    α(TM, TN) = a(TM) + b(TM) × (1/TN)

using ordinary least squares on the 5-point calibration data from E8
(TN ∈ {4, 8, 16, 32, 64}).  No new simulator runs needed.

This gives:
  a(TM) — the TN→∞ intercept (pure warm-L1 cost, no cold-fill contribution)
  b(TM) — the empirical cold-fill slope (= effective C(TM) × reg_m × reg_k × L_cache / ...)

We then:
  1. Compare regression accuracy vs theoretical formula (both vs calibrated α).
  2. Re-run the E8 TM* prediction table, substituting regression formula for theoretical.
  3. Interpret b(TM) physically — compare to C_L2 and C_DRAM expectations.
"""

from pathlib import Path
import json

EXPERIMENT_DIR = Path(__file__).resolve().parent
E8_RESULTS = (EXPERIMENT_DIR.parent / "e8-gc-boundary-sweep" / "results.json")

# ── Hardware / experiment constants ───────────────────────────────────────────
A_P = C_P = 4
L1  = 16_384
L2  = 4 * L1
REG_M = REG_N = REG_K = 4
L1_LAT = 4
L2_LAT = 14
_C_L2   = (L2_LAT - L1_LAT) / (REG_M * REG_K)   # 0.625
_C_DRAM = 12.0

TN_CALIB = [4, 8, 16, 32, 64]
TM_ALL   = [8, 16, 24, 32, 48, 64, 96, 128]
GC_SWEEP = [64, 100, 104, 108, 130, 165, 171, 175, 230, 248, 252, 256, 380, 600]

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


# ── Pure-Python OLS for α = a + b × (1/TN) ───────────────────────────────────

def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Return (a, b, r2) for y = a + b*x by OLS."""
    n = len(xs)
    sx  = sum(xs)
    sy  = sum(ys)
    sxx = sum(x*x for x in xs)
    sxy = sum(x*y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    y_mean = sy / n
    ss_tot = sum((y - y_mean)**2 for y in ys)
    ss_res = sum((y - (a + b*x))**2 for y, x in zip(ys, xs))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return a, b, r2


def alpha_theoretical(tm: int, tn: int) -> float:
    c = _C_L2 if tm <= 48 else _C_DRAM
    return ALPHA_E3[tm] + c * (1 / tn - 1 / 32)


def mnk(m: int) -> int:
    return m * 256 * 256


# ── Load E8 calibration data ──────────────────────────────────────────────────

def load_e8() -> tuple[dict, dict]:
    """Return (alpha_calib, gc_results).

    alpha_calib[tn][tm] = measured α at gc=0
    gc_results[gc]      = list of (tm, m, cycles, tn)
    """
    with open(E8_RESULTS) as f:
        cache = json.load(f)

    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_CALIB}
    gc_results:  dict[int, list] = {gc: [] for gc in GC_SWEEP}

    for entry in cache.values():
        ov = entry["overrides"]
        tm = ov["TILE_M"]
        tn = ov["TILE_N"]
        gc = ov["PRNG_FIFO_GEN_COST"]
        m  = ov["A_HEIGHT_DIM"]
        cy = entry["metrics"]["cycles"]

        if gc == 0 and tn in TN_CALIB and tm in TM_ALL:
            alpha_calib[tn][tm] = cy / mnk(m)

        if gc in GC_SWEEP and tn in TN_CALIB and tm in TM_ALL:
            gc_results[gc].append((tm, m, cy, tn))

    return alpha_calib, gc_results


def run() -> None:
    alpha_calib, gc_results = load_e8()

    # ── Fit regression per TM ─────────────────────────────────────────────────
    xs = [1 / tn for tn in TN_CALIB]
    reg: dict[int, tuple[float, float, float]] = {}  # tm → (a, b, r2)
    for tm in TM_ALL:
        ys = [alpha_calib[tn][tm] for tn in TN_CALIB]
        reg[tm] = ols(xs, ys)

    # ── Print regression coefficients ────────────────────────────────────────
    print("── Regression coefficients: α(TM, TN) = a(TM) + b(TM)/TN ──")
    print(f"{'TM':>5}  {'a(TM)':>8}  {'b(TM)':>8}  {'R²':>6}  "
          f"{'α_E3(TM)':>9}  {'b theory':>9}  {'b error%':>9}  regime")
    print("─" * 80)
    for tm in TM_ALL:
        a, b, r2 = reg[tm]
        theory_b = _C_L2 if tm <= 48 else _C_DRAM
        b_err = 100 * (theory_b - b) / b if b != 0 else 0.0
        regime = "L2" if tm <= 48 else "DRAM"
        print(f"{tm:>5}  {a:>8.4f}  {b:>8.4f}  {r2:>6.4f}  "
              f"{ALPHA_E3[tm]:>9.4f}  {theory_b:>9.4f}  {b_err:>+8.2f}%  {regime}")

    # ── α accuracy: regression vs theoretical vs calibrated ──────────────────
    print()
    print("── α error vs calibrated: regression vs theoretical formula ──")
    print(f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_CALIB))
    print("  (reg% / theo%)  — positive = overestimates calibrated α")
    print("─" * (5 + 13 * len(TN_CALIB)))
    for tm in TM_ALL:
        a, b, _ = reg[tm]
        row = f"{tm:>5}"
        for tn in TN_CALIB:
            calib = alpha_calib[tn][tm]
            pred_reg  = a + b / tn
            pred_theo = alpha_theoretical(tm, tn)
            err_reg   = 100 * (pred_reg  - calib) / calib
            err_theo  = 100 * (pred_theo - calib) / calib
            row += f"  {err_reg:>+5.2f}/{err_theo:>+5.2f}%"
        print(row)

    # ── Max abs error summary ─────────────────────────────────────────────────
    max_reg  = max(
        abs(100 * ((reg[tm][0] + reg[tm][1] / tn) - alpha_calib[tn][tm]) / alpha_calib[tn][tm])
        for tm in TM_ALL for tn in TN_CALIB
    )
    max_theo = max(
        abs(100 * (alpha_theoretical(tm, tn) - alpha_calib[tn][tm]) / alpha_calib[tn][tm])
        for tm in TM_ALL for tn in TN_CALIB
    )
    print(f"\n  Max |error| — regression: {max_reg:.2f}%   theoretical: {max_theo:.2f}%")

    # ── TM* prediction: regression vs theoretical (same as E8 summary table) ──
    def tm_star(gc: int, tn: int, alpha_fn) -> int:
        return min(TM_ALL, key=lambda tm: max(alpha_fn(tm, tn), gc / tm))

    def alpha_reg(tm: int, tn: int) -> float:
        a, b, _ = reg[tm]
        return a + b / tn

    print()
    print("═" * 96)
    print("TM* PREDICTION — regression (R) vs theoretical formula (F) vs calibrated (C) vs E3 (E)")
    print("═" * 96)
    header = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>12}" for tn in TN_CALIB) + "  E3-pred"
    sub    = f"  {'':>5}" + "".join(f"  {'emp R F C E':>12}" for tn in TN_CALIB)
    print(header)
    print(sub)
    print("  " + "─" * (len(header) - 2))

    r_total = f_total = c_total = total = 0
    for gc in GC_SWEEP:
        e3 = min(TM_ALL, key=lambda tm: max(ALPHA_E3[tm], gc / tm))
        row = f"  {gc:>5}"
        for tn in TN_CALIB:
            entries = [(tm, m, cy) for tm, m, cy, t in gc_results[gc] if t == tn]
            empirical = min(entries, key=lambda x: x[2] / mnk(x[1]))[0]
            pred_r = tm_star(gc, tn, alpha_reg)
            pred_f = tm_star(gc, tn, alpha_theoretical)
            pred_c = min(TM_ALL, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            r_ok = "✓" if empirical == pred_r else "✗"
            f_ok = "✓" if empirical == pred_f else "✗"
            c_ok = "✓" if empirical == pred_c else "✗"
            e_ok = "✓" if empirical == e3 else "✗"
            row += f"  {empirical:>3} {r_ok}{f_ok}{c_ok}{e_ok}"
            r_total += empirical == pred_r
            f_total += empirical == pred_f
            c_total += empirical == pred_c
            total   += 1
        row += f"  {e3:>8}"
        print(row)

    print()
    print(f"  Accuracy:  regression={r_total}/{total} ({100*r_total/total:.0f}%)   "
          f"theoretical={f_total}/{total} ({100*f_total/total:.0f}%)   "
          f"calibrated={c_total}/{total} ({100*c_total/total:.0f}%)")

    # ── Physical interpretation of b(TM) ─────────────────────────────────────
    print()
    print("── Physical interpretation of b(TM) = effective C(TM) ──")
    print("  b(TM) is the cold-fill slope.  Theory: b = (L_cache − L1_lat)/(reg_m × reg_k)")
    print(f"  L2  theory: b = ({L2_LAT} − {L1_LAT}) / {REG_M*REG_K} = {_C_L2:.3f}")
    print(f"  DRAM theory: b = 12.0  (effective L_DRAM ≈ 196 cy)")
    print()
    print(f"  {'TM':>5}  {'b_reg':>7}  {'eff L_cache':>11}  {'theory b':>9}  note")
    print("  " + "─" * 55)
    for tm in TM_ALL:
        _, b, _ = reg[tm]
        eff_l = b * REG_M * REG_K + L1_LAT   # back-solve: b = (L_eff - L1_lat)/(reg_m*reg_k)
        theory_b = _C_L2 if tm <= 48 else _C_DRAM
        note = ""
        if tm <= 48 and abs(b - _C_L2) < 0.05:
            note = "≈ L2 theory ✓"
        elif tm > 48 and abs(b - theory_b) / theory_b < 0.05:
            note = "≈ DRAM theory ✓"
        elif tm > 48:
            note = f"theory off by {100*(theory_b-b)/b:+.1f}%"
        print(f"  {tm:>5}  {b:>7.4f}  {eff_l:>11.1f}  {theory_b:>9.4f}  {note}")


if __name__ == "__main__":
    run()
