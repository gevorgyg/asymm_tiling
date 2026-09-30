"""E12: Non-linear α(TM, TN) model.

E11 fitted α = a + b/TN (linear in 1/TN). It worked well for TM=16,24,32
(R²=1.0) but failed for TM=48 (R²=0.13) because α is U-shaped: it decreases
as TN grows (fewer cold A fills per MNK) but rises again at large TN as the
C tile crowds L1 and evicts A lines.

Two competing effects:
  b/TN — cold-fill overhead, decreases with TN (more A reuse per session)
  c×TN — C-tile eviction pressure, increases with TN (∝ C-tile size = TM×TN×C_P)

E12 fits:
    α(TM, TN) = a(TM) + b(TM)/TN + c(TM)×TN

by OLS with 3 parameters on the same 5-point E8 calibration data.

Physical consequence: differentiating and setting to 0 gives an optimal TN:
    TN*(TM) = sqrt(b(TM) / c(TM))       [ignoring the hard L1 constraint]

This is the TN where cold-fill savings are exactly offset by C-tile pressure.
If TN*(TM) < L1/(TM×C_P), it's achievable without overflow.

We compare 3-param accuracy vs 2-param (E11) and calibrated, and re-run the
E8 TM* prediction table.
"""

from pathlib import Path
import json
import math

EXPERIMENT_DIR = Path(__file__).resolve().parent
E8_RESULTS = (EXPERIMENT_DIR.parent / "e8-gc-boundary-sweep" / "results.json")

# ── Constants ─────────────────────────────────────────────────────────────────
A_P = C_P = 4
L1  = 16_384
L2  = 4 * L1
REG_M = REG_N = REG_K = 4
L1_LAT = 4
L2_LAT = 14

TN_CALIB = [4, 8, 16, 32, 64]
TM_ALL   = [8, 16, 24, 32, 48, 64, 96, 128]
GC_SWEEP = [64, 100, 104, 108, 130, 165, 171, 175, 230, 248, 252, 256, 380, 600]

ALPHA_E3: dict[int, float] = {
    8:3.3996, 16:3.2995, 24:3.2587, 32:3.2369, 48:3.2550,
    64:3.5604, 96:3.9398, 128:3.9363,
}


# ── Linear algebra: 3×3 OLS in pure Python ───────────────────────────────────

def _solve3(A: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve 3×3 system Ax=rhs by Gaussian elimination with partial pivoting."""
    M = [[A[i][j] for j in range(3)] + [rhs[i]] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(M[r][col]))
        M[col], M[pivot] = M[pivot], M[col]
        if abs(M[col][col]) < 1e-14:
            raise ValueError("Singular normal matrix")
        for row in range(col + 1, 3):
            f = M[row][col] / M[col][col]
            for j in range(col, 4):
                M[row][j] -= f * M[col][j]
    x = [0.0] * 3
    for i in range(2, -1, -1):
        x[i] = M[i][3] - sum(M[i][j] * x[j] for j in range(i + 1, 3))
        x[i] /= M[i][i]
    return x


def ols2(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """OLS for y = a + b*x. Returns (a, b, r2)."""
    n = len(xs)
    sx = sum(xs); sy = sum(ys); sxx = sum(x*x for x in xs); sxy = sum(x*y for x,y in zip(xs,ys))
    denom = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    y_mean = sy / n
    ss_tot = sum((y - y_mean)**2 for y in ys)
    ss_res = sum((y - (a + b*x))**2 for y,x in zip(ys,xs))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return a, b, r2


def ols3(x1s: list[float], x2s: list[float], ys: list[float]
         ) -> tuple[float, float, float, float]:
    """OLS for y = a + b*x1 + c*x2. Returns (a, b, c, r2)."""
    n = len(ys)
    sx1  = sum(x1s);  sx2  = sum(x2s);  sy   = sum(ys)
    sx1x1 = sum(x*x for x in x1s)
    sx2x2 = sum(x*x for x in x2s)
    sx1x2 = sum(x1*x2 for x1,x2 in zip(x1s,x2s))
    sx1y  = sum(x*y for x,y in zip(x1s,ys))
    sx2y  = sum(x*y for x,y in zip(x2s,ys))

    A = [
        [float(n), sx1,   sx2],
        [sx1,      sx1x1, sx1x2],
        [sx2,      sx1x2, sx2x2],
    ]
    a, b, c = _solve3(A, [sy, sx1y, sx2y])
    y_mean = sy / n
    ss_tot = sum((y - y_mean)**2 for y in ys)
    ss_res = sum((y - (a + b*x1 + c*x2))**2 for y,x1,x2 in zip(ys,x1s,x2s))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return a, b, c, r2


# ── Load E8 calibration data ──────────────────────────────────────────────────

def load_e8() -> tuple[dict, dict]:
    with open(E8_RESULTS) as f:
        cache = json.load(f)
    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_CALIB}
    gc_results:  dict[int, list]             = {gc: [] for gc in GC_SWEEP}
    for entry in cache.values():
        ov = entry["overrides"]
        tm = ov["TILE_M"]; tn = ov["TILE_N"]
        gc = ov["PRNG_FIFO_GEN_COST"]; m = ov["A_HEIGHT_DIM"]
        cy = entry["metrics"]["cycles"]
        if gc == 0 and tn in TN_CALIB and tm in TM_ALL:
            alpha_calib[tn][tm] = cy / (m * 256 * 256)
        if gc in GC_SWEEP and tn in TN_CALIB and tm in TM_ALL:
            gc_results[gc].append((tm, m, cy, tn))
    return alpha_calib, gc_results


def mnk(m: int) -> int:
    return m * 256 * 256


def run() -> None:
    alpha_calib, gc_results = load_e8()

    x1s = [1 / tn for tn in TN_CALIB]          # cold-fill axis (1/TN)
    x2s = [float(tn) for tn in TN_CALIB]        # pressure axis (TN)

    # ── Fit both models per TM ────────────────────────────────────────────────
    reg2: dict[int, tuple] = {}   # tm → (a, b, r2)
    reg3: dict[int, tuple] = {}   # tm → (a, b, c, r2)
    for tm in TM_ALL:
        ys = [alpha_calib[tn][tm] for tn in TN_CALIB]
        reg2[tm] = ols2(x1s, ys)
        reg3[tm] = ols3(x1s, x2s, ys)

    # ── Coefficient table ─────────────────────────────────────────────────────
    print("── 3-param regression coefficients: α = a + b/TN + c×TN ──")
    print(f"{'TM':>5}  {'a':>8}  {'b':>8}  {'c':>9}  {'R²(3p)':>7}  "
          f"{'R²(2p)':>7}  {'TN*':>6}  note")
    print("─" * 80)
    for tm in TM_ALL:
        a2, b2, r2_2 = reg2[tm]
        a3, b3, c3, r2_3 = reg3[tm]
        tn_star = math.sqrt(b3 / c3) if c3 > 1e-6 else float('inf')
        l1_limit = L1 / (tm * C_P)
        note = ""
        if tn_star < l1_limit:
            note = f"TN*={tn_star:.1f} < L1-limit={l1_limit:.0f}"
        elif c3 < 1e-6:
            note = "c≈0 (no pressure)"
        else:
            note = f"TN*={tn_star:.1f} ≥ L1-limit={l1_limit:.0f} (constrained)"
        dr2 = r2_3 - r2_2
        dr_str = f"{dr2:+.4f}" if abs(dr2) > 5e-5 else "   —"
        print(f"{tm:>5}  {a3:>8.4f}  {b3:>8.4f}  {c3:>9.5f}  {r2_3:>7.4f}  "
              f"{r2_2:>7.4f}  {dr_str:>7}  {note}")

    # ── α accuracy: 3-param vs 2-param vs calibrated ─────────────────────────
    print()
    print("── |α error| vs calibrated ──")
    print(f"  {'TM':>4}  3-param  2-param")
    print("  " + "─" * 22)
    max3 = max2 = 0.0
    for tm in TM_ALL:
        a3, b3, c3, _ = reg3[tm]
        a2, b2, _     = reg2[tm]
        errs3 = [abs(100*(a3 + b3/tn + c3*tn - alpha_calib[tn][tm])/alpha_calib[tn][tm])
                 for tn in TN_CALIB]
        errs2 = [abs(100*(a2 + b2/tn           - alpha_calib[tn][tm])/alpha_calib[tn][tm])
                 for tn in TN_CALIB]
        me3 = max(errs3); me2 = max(errs2)
        max3 = max(max3, me3); max2 = max(max2, me2)
        flag = "  ←" if abs(me3 - me2) > 0.5 else ""
        print(f"  {tm:>4}  {me3:>6.2f}%  {me2:>6.2f}%{flag}")
    print(f"\n  Overall max: 3-param={max3:.2f}%  2-param={max2:.2f}%")

    # ── TM* prediction comparison ─────────────────────────────────────────────
    def alpha2(tm, tn):
        a, b, _ = reg2[tm]; return a + b / tn
    def alpha3(tm, tn):
        a, b, c, _ = reg3[tm]; return a + b / tn + c * tn
    def tm_star(gc, tn, afn):
        return min(TM_ALL, key=lambda tm: max(afn(tm, tn), gc / tm))

    print()
    print("═" * 100)
    print("TM* PREDICTION — 3-param (3) vs 2-param (2) vs calibrated (C) vs E3 (E)")
    print("═" * 100)
    header = f"  {'gc':>5}" + "".join(f"  {'TN='+str(tn):>12}" for tn in TN_CALIB) + "  E3-pred"
    sub    = f"  {'':>5}" + "".join(f"  {'emp 3 2 C E':>12}" for tn in TN_CALIB)
    print(header); print(sub)
    print("  " + "─" * (len(header) - 2))

    t3 = t2 = tc = total = 0
    for gc in GC_SWEEP:
        e3 = min(TM_ALL, key=lambda tm: max(ALPHA_E3[tm], gc / tm))
        row = f"  {gc:>5}"
        for tn in TN_CALIB:
            entries   = [(tm, m, cy) for tm, m, cy, t in gc_results[gc] if t == tn]
            empirical = min(entries, key=lambda x: x[2] / mnk(x[1]))[0]
            p3 = tm_star(gc, tn, alpha3)
            p2 = tm_star(gc, tn, alpha2)
            pc = min(TM_ALL, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
            ok3 = "✓" if empirical == p3 else "✗"
            ok2 = "✓" if empirical == p2 else "✗"
            okc = "✓" if empirical == pc else "✗"
            oke = "✓" if empirical == e3 else "✗"
            row += f"  {empirical:>3} {ok3}{ok2}{okc}{oke}"
            t3 += empirical == p3
            t2 += empirical == p2
            tc += empirical == pc
            total += 1
        row += f"  {e3:>8}"
        print(row)

    print()
    print(f"  Accuracy:  3-param={t3}/{total} ({100*t3/total:.0f}%)   "
          f"2-param={t2}/{total} ({100*t2/total:.0f}%)   "
          f"calibrated={tc}/{total} ({100*tc/total:.0f}%)")

    # ── Physical interpretation ───────────────────────────────────────────────
    print()
    print("── Physical interpretation ──")
    print("  TN*(TM) = sqrt(b/c) is the optimal TN balancing cold-fill vs C-tile pressure.")
    print("  Below TN*: cold-fill cost dominates (gain from larger TN outweighs pressure).")
    print("  Above TN*: C-tile pressure dominates (cost from larger C tile exceeds gain).")
    print()
    print(f"  {'TM':>5}  {'b(TM)':>7}  {'c(TM)':>8}  {'TN*':>6}  {'L1-limit':>9}  "
          f"{'TN* vs L1':>12}")
    print("  " + "─" * 60)
    for tm in TM_ALL:
        a3, b3, c3, _ = reg3[tm]
        l1_lim = L1 / (tm * C_P)
        if c3 > 1e-6:
            tn_opt = math.sqrt(b3 / c3)
            rel = f"{'INSIDE' if tn_opt < l1_lim else 'beyond'}"
        else:
            tn_opt = float('inf')
            rel = "c≈0, no optimum"
        tn_str = f"{tn_opt:.1f}" if tn_opt < 1e4 else "∞"
        print(f"  {tm:>5}  {b3:>7.4f}  {c3:>8.5f}  {tn_str:>6}  {l1_lim:>9.0f}  {rel:>12}")

    # ── Improvement detail for key cases ─────────────────────────────────────
    print()
    print("── Case studies: where 3-param fixes vs breaks 2-param ──")
    KEY_CASES = [(64, 4), (64, 8), (64, 16), (171, 32), (230, 8), (248, 32)]
    for gc, tn in KEY_CASES:
        entries   = [(tm, m, cy) for tm, m, cy, t in gc_results[gc] if t == tn]
        empirical = min(entries, key=lambda x: x[2] / mnk(x[1]))[0]
        p3 = tm_star(gc, tn, alpha3)
        p2 = tm_star(gc, tn, alpha2)
        pc = min(TM_ALL, key=lambda tm: max(alpha_calib[tn][tm], gc / tm))
        # Show α values at the competing TMs
        cands = sorted({empirical, p3, p2, pc})
        print(f"\n  gc={gc}, TN={tn}  empirical={empirical}  3p={p3}  2p={p2}  calib={pc}")
        print(f"  {'TM':>5}  {'α_3p':>8}  {'α_2p':>8}  {'α_cal':>8}  "
              f"  {'cost_3p':>8}  {'cost_2p':>8}  {'cost_cal':>9}")
        for tm in cands:
            a3, b3, c3, _ = reg3[tm]
            a2, b2, _     = reg2[tm]
            v3  = a3 + b3/tn + c3*tn
            v2  = a2 + b2/tn
            vc  = alpha_calib[tn][tm]
            print(f"  {tm:>5}  {v3:>8.4f}  {v2:>8.4f}  {vc:>8.4f}  "
                  f"  {max(v3,gc/tm):>8.4f}  {max(v2,gc/tm):>8.4f}  {max(vc,gc/tm):>9.4f}")


if __name__ == "__main__":
    run()
