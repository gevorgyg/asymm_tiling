"""E6: TN independence of the optimal TM.

The model T = MNK × max(α(TM), gc/TM) has no TN term, so TM* should not
shift when TN changes (as long as the C tile stays in L1).

Part 1 (original): use the global α(TM) table from E3 (calibrated at TN=32).
  Prediction: TM*=48 for all TN.  Previously confirmed.

Part 2 (recalibrated): measure α(TM, TN) at gc=0 for each (TM, TN) pair,
  then re-predict TM* using the TN-specific α.
  Question: does the optimal TM shift when using the correctly calibrated α?
  Expected: TM* stays at 48 for all TN (since the α minimum is still at TM=48
  within the L2 regime, even though DRAM-regime α values change with TN).
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
M = 192
N = K = 256

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True, mulac_norecord=True)

_BASE: dict[str, object] = {
    "A_HEIGHT_DIM":        M,
    "A_WIDTH_DIM":         K,
    "B_WIDTH_DIM":         N,
    "A_PRECISION_BYTES":   A_P,
    "B_PRECISION_BYTES":   A_P,
    "L1_SIZE_BYTES":       L1,
    "L1_LINE_SIZE_BYTES":  LINE,
    "L1_ASSOC":            L1 // LINE,
    "L2_SIZE_BYTES":       L2,
    "L2_LINE_SIZE_BYTES":  LINE,
    "L2_ASSOC":            L2 // LINE,
    "L2_ACCESS_CYCLES":    14,
    "PRNG_FIFO_CAPACITY":  2 * K * 32,
    "TILE_K":              256,
}

MNK = M * N * K

TM_SWEEP = [8, 16, 24, 32, 48, 64, 96]
TN_SWEEP  = [4, 16, 32, 64]

# α(TM) from E3 at TN=32 — baseline prediction
ALPHA_E3: dict[int, float] = {
    8:   3.3996,
    16:  3.2995,
    24:  3.2587,
    32:  3.2369,
    48:  3.2550,
    64:  3.5604,
    96:  3.9398,
}

GC = 130
PREDICTED_TM_STAR = 48


def c_tile_bytes(tm: int, tn: int) -> int:
    return tm * tn * C_P


def in_l1(tm: int, tn: int) -> bool:
    return c_tile_bytes(tm, tn) < L1


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── gc=130 sweep (E6 main) ────────────────────────────────────────────────
    print(f"Running gc={GC} sweep: TM × TN …")
    grid_gc = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "PRNG_FIFO_GEN_COST": GC},
        sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    # ── gc=0 calibration sweep ────────────────────────────────────────────────
    print(f"\nRunning gc=0 calibration sweep: TM × TN (measuring α(TM, TN)) …")
    grid_gc0 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "PRNG_FIFO_GEN_COST": 0},
        sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    # Build α(TM, TN) table from gc=0 runs
    alpha_calib: dict[int, dict[int, float]] = {tn: {} for tn in TN_SWEEP}
    for r in grid_gc0:
        tm = r.overrides["TILE_M"]
        tn = r.overrides["TILE_N"]
        alpha_calib[tn][tm] = r.metrics.cycles / MNK

    # ── Part 1: E3 α table (original) ────────────────────────────────────────
    print("\n" + "═" * 72)
    print("PART 1 — predictions using E3 α table (calibrated at TN=32)")
    print("═" * 72)

    _print_analysis(grid_gc, TN_SWEEP, TM_SWEEP,
                    alpha_fn=lambda tm, tn: ALPHA_E3[tm],
                    label="E3 α")

    # ── Part 2: TN-specific calibrated α ─────────────────────────────────────
    print("\n" + "═" * 72)
    print("PART 2 — predictions using gc=0 α calibrated per (TM, TN)")
    print("═" * 72)

    _print_analysis(grid_gc, TN_SWEEP, TM_SWEEP,
                    alpha_fn=lambda tm, tn: alpha_calib[tn][tm],
                    label="calib α")

    # ── α(TM, TN) table ──────────────────────────────────────────────────────
    print("\n── Calibrated α(TM, TN) table (from gc=0 runs) ──")
    header = f"{'TM':>5}" + "".join(f"  TN={tn:>3}" for tn in TN_SWEEP) + "  (E3 TN=32)"
    print(header)
    print("-" * len(header))
    for tm in TM_SWEEP:
        row = f"{tm:>5}"
        for tn in TN_SWEEP:
            row += f"  {alpha_calib[tn][tm]:>8.4f}"
        row += f"  {ALPHA_E3[tm]:>10.4f}"
        print(row)


def _print_analysis(
    grid_gc,
    tn_sweep: list[int],
    tm_sweep: list[int],
    alpha_fn,
    label: str,
) -> None:
    """Print per-TN tables and summary using the given α function."""

    for tn in tn_sweep:
        rows_gc = [(r.overrides["TILE_M"], r.metrics.cycles)
                   for r in grid_gc if r.overrides["TILE_N"] == tn]
        rows_gc.sort(key=lambda x: x[0])

        empirical_best = min(rows_gc, key=lambda x: x[1])[0]

        # predicted TM* using this α
        pred_best = min(tm_sweep,
                        key=lambda tm: max(alpha_fn(tm, tn), GC / tm))
        match = empirical_best == pred_best

        print(f"\n  TN={tn}  |  {label} predicted TM*={pred_best}  |  "
              f"empirical TM*={empirical_best}  {'✓' if match else '✗ MISMATCH'}")
        print(f"  {'TM':>5}  {'L1?':>5}  {'T/MNK':>8}  "
              f"{'T_pred ({label})':>18}  {'err%':>7}")
        print("  " + "-" * 55)

        for tm, cy in rows_gc:
            fits  = in_l1(tm, tn)
            t_per = cy / MNK
            tp    = max(alpha_fn(tm, tn), GC / tm)
            err   = 100 * (t_per - tp) / tp
            flag  = "  ← overflow" if not fits else \
                    ("  ← min" if tm == empirical_best else "")
            print(f"  {tm:>5}  {'✓' if fits else '✗':>5}  {t_per:>8.4f}  "
                  f"{tp:>18.4f}  {err:>+7.2f}%{flag}")

    print(f"\n── {label} summary: argmin TM per TN ──")
    print(f"  {'TN':>4}  {'pred TM*':>9}  {'empirical TM*':>14}  {'match':>6}")
    print("  " + "-" * 40)
    for tn in tn_sweep:
        rows_gc = [(r.overrides["TILE_M"], r.metrics.cycles)
                   for r in grid_gc if r.overrides["TILE_N"] == tn]
        empirical = min(rows_gc, key=lambda x: x[1])[0]
        predicted = min(tm_sweep,
                        key=lambda tm: max(alpha_fn(tm, tn), GC / tm))
        print(f"  {tn:>4}  {predicted:>9}  {empirical:>14}  "
              f"{'✓' if empirical == predicted else '✗':>6}")


if __name__ == "__main__":
    run()
