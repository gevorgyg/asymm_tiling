"""E5: Validate that the model-predicted optimal TM is actually optimal.

Model: T = MNK × max(α(TM), gc/TM)

Predicted TM* per gc (from the α(TM) table in E3):
  gc=64  → TM*=32  (A-bottleneck everywhere ≥ TM=24; argmin α = 32)
  gc=130 → TM*=48  (crossover falls between TM=32 (B) and TM=48 (A))
  gc=230 → TM*=64  (crossover near TM=64, just barely B-bottlenecked)
  gc=380 → TM*=128 (crossover between TM=96 (barely B) and TM=128 (A))

For each gc value we sweep all valid TM and find the empirical minimum.
We also print the predicted T = MNK × max(α(TM), gc/TM) and the error.
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

FLAGS = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True, mulac_norecord=True)

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
    "TILE_N":              32,
    "TILE_K":              256,
}

_BASE_256 = {**_BASE_192, "A_HEIGHT_DIM": 256}

# α(TM) measured at gc=0, TN=32 (E3 values)
ALPHA_MEASURED: dict[int, float] = {
    8:   3.3996,
    16:  3.2995,
    24:  3.2587,
    32:  3.2369,
    48:  3.2550,
    64:  3.5604,
    96:  3.9398,
    128: 3.9363,
}

# TM values: M=192 supports {8,16,24,32,48,64,96}; TM=128 needs M=256
TM_M192 = [8, 16, 24, 32, 48, 64, 96]
TM_M256 = [128]

GC_SWEEP = [64, 130, 230, 380]

# Predicted TM* per gc (derived analytically from ALPHA_MEASURED above)
PREDICTED_TM_STAR: dict[int, int] = {64: 32, 130: 48, 230: 64, 380: 128}


def mnk(m: int) -> int:
    return m * 256 * 256


def t_pred(tm: int, gc: int) -> float:
    """Model prediction: T/MNK = max(α(TM), gc/TM)."""
    return max(ALPHA_MEASURED[tm], gc / tm)


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Run grids ─────────────────────────────────────────────────────────────
    print("Running M=192 grid (TM ∈ {8,16,24,32,48,64,96}) × gc sweep …")
    grid_192 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=_BASE_192,
        sweep_axes={"TILE_M": TM_M192, "PRNG_FIFO_GEN_COST": GC_SWEEP},
        flags=FLAGS,
    )

    print("Running M=256 grid (TM=128 only) × gc sweep …")
    grid_256 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=_BASE_256,
        sweep_axes={"TILE_M": TM_M256, "PRNG_FIFO_GEN_COST": GC_SWEEP},
        flags=FLAGS,
    )

    all_results = grid_192 + grid_256

    # ── Print results per gc ──────────────────────────────────────────────────
    for gc in GC_SWEEP:
        # Store (tm, m_height, cycles) — keep m_height separate from mnk
        rows = [
            (r.overrides["TILE_M"],
             r.overrides["A_HEIGHT_DIM"],
             r.metrics.cycles)
            for r in all_results
            if r.overrides["PRNG_FIFO_GEN_COST"] == gc
        ]
        rows.sort(key=lambda x: x[0])

        # Compare T/MNK (not raw cycles) so M=192 and M=256 rows are comparable
        best_tm = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
        pred_star = PREDICTED_TM_STAR[gc]

        print(f"\n=== E5: gc={gc}  |  predicted TM*={pred_star}  |  empirical TM*={best_tm} "
              f"{'✓' if best_tm == pred_star else '✗ MISMATCH'} ===")
        print(f"\n{'TM':>5}  {'M':>5}  {'T (cy)':>14}  {'T/MNK':>8}  "
              f"{'T_pred/MNK':>12}  {'err%':>7}  {'btlnk':>6}")
        print("-" * 68)

        for tm, m_h, cy in rows:
            t_per_mnk  = cy / mnk(m_h)
            tp         = t_pred(tm, gc)
            err        = 100 * (t_per_mnk - tp) / tp
            btlnk      = "B" if gc / tm > ALPHA_MEASURED[tm] else "A"
            marker     = "  ← min" if tm == best_tm else ""
            print(f"{tm:>5}  {m_h:>5}  {cy:>14,}  {t_per_mnk:>8.4f}  "
                  f"{tp:>12.4f}  {err:>+7.2f}%  {btlnk:>6}{marker}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n── Summary ──")
    print(f"{'gc':>5}  {'pred TM*':>9}  {'empirical TM*':>14}  {'match':>6}")
    print("-" * 42)
    for gc in GC_SWEEP:
        rows = [(r.overrides["TILE_M"],
                 r.overrides["A_HEIGHT_DIM"],
                 r.metrics.cycles)
                for r in all_results if r.overrides["PRNG_FIFO_GEN_COST"] == gc]
        best = min(rows, key=lambda x: x[2] / mnk(x[1]))[0]
        pred = PREDICTED_TM_STAR[gc]
        print(f"{gc:>5}  {pred:>9}  {best:>14}  {'✓' if best == pred else '✗':>6}")


if __name__ == "__main__":
    run()
