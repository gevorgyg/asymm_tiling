"""E10: Matrix-size scaling validation.

The model T = MNK × max(α(TM), gc/TM) predicts T/MNK is constant regardless
of M, N, K — it depends only on tile shape (TM, TN) and gc.  This is the
asymptotic assumption: no per-session fixed overhead, pure MNK scaling.

We hold N=K=256 and vary M ∈ {128, 192, 256, 384} over all valid (TM, gc)
combinations, then check whether T/MNK is constant across M.

Valid TM values per M (must divide M; hardware set = {8,16,24,32,48,64,96,128}):
  M=128:  8 16 32 64 128
  M=192:  8 16 24 32 48 64 96
  M=256:  8 16 32 64 128
  M=384:  8 16 24 32 48 64 96 128

The "common" set — valid for all four M values: {8, 16, 32, 64}.
gc ∈ {130, 230} — near-optimal gc values from E5.
TN = 32 (standard calibration TN).

Expected: T/MNK is flat across M for each (TM, gc) pair.
Any systematic trend with M would indicate fixed-cost overhead (e.g., cache
warm-up, FIFO initialization) that the model ignores.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

A_P = C_P = 4
LINE = 64
L1   = 16_384
L2   = 4 * L1

FLAGS = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True, mulac_norecord=True)

def _base(m: int) -> dict[str, object]:
    return {
        "A_HEIGHT_DIM":        m,
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

HW_TM = [8, 16, 24, 32, 48, 64, 96, 128]

def valid_tm(m: int) -> list[int]:
    return [tm for tm in HW_TM if m % tm == 0]

M_SWEEP = [128, 192, 256, 384]
GC_SWEEP = [130, 230]
TN = 32

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

def mnk(m: int) -> int:
    return m * 256 * 256


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Valid TM sets ─────────────────────────────────────────────────────────
    tm_sets = {m: valid_tm(m) for m in M_SWEEP}
    common_tm = [tm for tm in HW_TM if all(m % tm == 0 for m in M_SWEEP)]
    print("TM sets per M:")
    for m in M_SWEEP:
        print(f"  M={m}: {tm_sets[m]}")
    print(f"Common TM (valid for all M): {common_tm}")

    # ── Run sweeps ────────────────────────────────────────────────────────────
    results: dict[tuple[int, int], list] = {}   # (m, gc) → list of RunResult
    for m in M_SWEEP:
        for gc in GC_SWEEP:
            print(f"\nRunning M={m}, gc={gc} …")
            res = run_grid(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={**_base(m), "PRNG_FIFO_GEN_COST": gc, "TILE_N": TN},
                sweep_axes={"TILE_M": tm_sets[m]},
                flags=FLAGS,
            )
            results[(m, gc)] = res

    # ── Analysis: T/MNK per (TM, gc) across M ────────────────────────────────
    for gc in GC_SWEEP:
        print(f"\n{'═'*80}")
        print(f"T/MNK scaling with M — gc={gc}, TN={TN}")
        print(f"{'═'*80}")
        print("  Expected: values flat across M (MNK-asymptotic model)")
        print()

        # Only show TM in common_tm for side-by-side comparison
        header = f"  {'TM':>5}" + "".join(f"  {'M='+str(m):>10}" for m in M_SWEEP) + \
                 f"  {'E3-pred':>9}  {'max_Δ%':>8}"
        print(header)
        print("  " + "─" * (len(header) - 2))

        for tm in common_tm:
            vals = []
            for m in M_SWEEP:
                r = next(
                    r for r in results[(m, gc)]
                    if r.overrides["TILE_M"] == tm
                )
                vals.append(r.metrics.cycles / mnk(m))

            e3 = max(ALPHA_E3[tm], gc / tm)
            max_delta = 100 * (max(vals) - min(vals)) / min(vals)
            row = f"  {tm:>5}" + "".join(f"  {v:>10.4f}" for v in vals) + \
                  f"  {e3:>9.4f}  {max_delta:>7.2f}%"
            flag = "  ← varies!" if max_delta > 2.0 else ""
            print(row + flag)

        # ── Show TM* per M ────────────────────────────────────────────────────
        print()
        print(f"  TM* per M (empirical min T/MNK):")
        e3_star = min(common_tm, key=lambda tm: max(ALPHA_E3[tm], gc / tm))
        for m in M_SWEEP:
            all_vals = {
                r.overrides["TILE_M"]: r.metrics.cycles / mnk(m)
                for r in results[(m, gc)]
            }
            emp_star = min(all_vals, key=all_vals.__getitem__)
            match = "✓" if emp_star == e3_star else f"✗(E3={e3_star})"
            print(f"    M={m:>4}: TM*={emp_star}  E3={e3_star} {match}"
                  f"  (T/MNK={all_vals[emp_star]:.4f})")

    # ── Full T/MNK tables per M (all valid TM, not just common) ──────────────
    print("\n" + "═" * 80)
    print("FULL T/MNK TABLES — all valid TM per M")
    print("═" * 80)
    for m in M_SWEEP:
        for gc in GC_SWEEP:
            print(f"\n  M={m}, gc={gc}")
            print(f"  {'TM':>5}  {'T/MNK':>8}  {'E3-pred':>9}  {'err%':>7}")
            print("  " + "─" * 38)
            rows = sorted(results[(m, gc)], key=lambda r: r.overrides["TILE_M"])
            star_row = min(rows, key=lambda r: r.metrics.cycles / mnk(m))
            star_tm  = star_row.overrides["TILE_M"]
            for r in rows:
                tm   = r.overrides["TILE_M"]
                tper = r.metrics.cycles / mnk(m)
                e3   = max(ALPHA_E3[tm], gc / tm)
                err  = 100 * (tper - e3) / e3
                mark = "  ← min" if tm == star_tm else ""
                print(f"  {tm:>5}  {tper:>8.4f}  {e3:>9.4f}  {err:>+6.2f}%{mark}")


if __name__ == "__main__":
    run()
