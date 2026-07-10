"""E4: Probe why C_fill ≈ L2_lat and under what conditions it breaks.

Hypothesis from E3 analysis:
  C_fill ≈ L2_lat is NOT "each A load costs L2_lat."  It emerges from two
  contributions:
    (a) C reg-tile loads/stores are warm dirty-L1 hits (L1_lat × 2 × reg_m×reg_n
        cycles per reg-tile pair), dominant because TK is large (63/64 warm).
    (b) A cold fills (one per 4-rtk spatial group per rti, L2 hit) add the rest.
  The resulting C_fill ≈ 13 happens to be close to L2_lat=14 for our parameters.

Three sub-sweeps test the three assumptions:

  E4a — TK sweep (gc=0, TM=32, TN=32):
    As TK shrinks, the warm-C fraction (TK/reg_k - 1)/(TK/reg_k) → 0.
    At TK=4 (only 1 rtk iteration) ALL C accesses are cold → C_fill should spike.
    At TK=256, C is 98% warm → current baseline.

  E4b — L2_ACCESS_CYCLES sweep (gc=0, TM=32, TN=32, TK=256):
    If cold fills set the scale, C_fill ∝ L2_lat.
    If warm-L1 dominates, C_fill is almost independent of L2_lat.

  E4c — TN overflow (gc=0, TM=32, TK=256):
    C tile = TM × TN × C_P bytes.  At TN=128: C tile = 16 KB = L1.
    L1 can no longer hold both C and A → warm-C assumption breaks.
    Expect C_fill to jump when C tile ≥ L1.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
M = N = K = 256
A_P = C_P = 4
LINE = 64
L1   = 16_384
L2   = 4 * L1
REG_N = REG_M = REG_K = 4

FLAGS = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True, mulac_norecord=True)

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
    "PRNG_FIFO_GEN_COST":  0,
    "PRNG_FIFO_CAPACITY":  2 * K * 32,
}

MNK = M * N * K


def cfill(cycles: int) -> float:
    return cycles * REG_N / MNK


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── E4a: TK sweep ─────────────────────────────────────────────────────────
    # Prediction: C_fill rises sharply as TK decreases, because warm-C fraction
    # = (TK/reg_k - 1)/(TK/reg_k) → 0 as TK → reg_k.
    TM_FIXED = 32
    TN_FIXED = 32
    TK_SWEEP = [4, 8, 16, 32, 64, 128, 256]
    print(f"\n=== E4a: TK sweep (gc=0, TM={TM_FIXED}, TN={TN_FIXED}) ===")
    print(f"  Prediction: C_fill spikes at small TK (C goes cold)")

    e4a = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "TILE_M": TM_FIXED, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_K": TK_SWEEP},
        flags=FLAGS,
    )

    warm_c_frac = [(tk // REG_K - 1) / (tk // REG_K) if tk >= REG_K else 0 for tk in TK_SWEEP]

    print(f"\n{'TK':>5}  {'warm-C%':>8}  {'cycles':>14}  {'C_fill':>10}")
    print("-" * 50)
    for r, wf in zip(e4a, warm_c_frac):
        tk = r.overrides["TILE_K"]
        cf = cfill(r.metrics.cycles)
        print(f"{tk:>5}  {100*wf:>7.1f}%  {r.metrics.cycles:>14,}  {cf:>10.3f}")

    # ── E4b: L2_ACCESS_CYCLES sweep ───────────────────────────────────────────
    # Prediction: if cold fills dominate, C_fill ∝ L2_lat.
    # If warm-L1 dominates, C_fill is roughly constant across L2 values.
    # Reality is a mix: expect partial proportionality.
    L2_CY_SWEEP = [7, 10, 14, 20, 28]
    print(f"\n=== E4b: L2_ACCESS_CYCLES sweep (gc=0, TM={TM_FIXED}, TN={TN_FIXED}, TK=256) ===")
    print(f"  Prediction: partial slope (warm-L1 term is constant, cold-fill term scales)")

    e4b = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "TILE_M": TM_FIXED, "TILE_N": TN_FIXED,
                        "TILE_K": 256},
        sweep_axes={"L2_ACCESS_CYCLES": L2_CY_SWEEP},
        flags=FLAGS,
    )

    # Find baseline at L2=14
    cf14 = next(cfill(r.metrics.cycles) for r in e4b
                if r.overrides["L2_ACCESS_CYCLES"] == 14)

    print(f"\n{'L2_lat':>7}  {'cycles':>14}  {'C_fill':>10}  {'cf/cf(14)':>10}")
    print("-" * 55)
    for r in e4b:
        l2 = r.overrides["L2_ACCESS_CYCLES"]
        cf = cfill(r.metrics.cycles)
        print(f"{l2:>7}  {r.metrics.cycles:>14,}  {cf:>10.3f}  {cf/cf14:>10.3f}")

    # ── E4c: TN overflow ──────────────────────────────────────────────────────
    # C tile size = TM × TN × C_P bytes.  Overflow at TN = L1 / (TM × C_P) = 128.
    # Prediction: C_fill is flat for TN ≤ 64, then jumps at TN=128.
    TN_OVERFLOW = [16, 32, 64, 128, 256]
    print(f"\n=== E4c: TN overflow (gc=0, TM={TM_FIXED}, TK=256) ===")
    print(f"  C-tile overflow at TN=128: {TM_FIXED}×128×{C_P}={TM_FIXED*128*C_P} = L1={L1} bytes")

    e4c = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "TILE_M": TM_FIXED, "TILE_K": 256},
        sweep_axes={"TILE_N": TN_OVERFLOW},
        flags=FLAGS,
    )

    print(f"\n{'TN':>5}  {'C-tile':>10}  {'regime':>10}  {'cycles':>14}  {'C_fill':>10}")
    print("-" * 60)
    for r in e4c:
        tn = r.overrides["TILE_N"]
        c_tile = TM_FIXED * tn * C_P
        regime = "overflow" if c_tile >= L1 else "fits"
        cf = cfill(r.metrics.cycles)
        marker = "  ← OVERFLOW" if c_tile >= L1 else ""
        print(f"{tn:>5}  {c_tile:>8}B  {regime:>10}  {r.metrics.cycles:>14,}  {cf:>10.3f}{marker}")

    # ── Cross-check: predict C_fill from warm-C model ─────────────────────────
    print("\n── Model prediction for C_fill ──")
    print("  C_fill = (T_C_warm + T_A) × reg_n / MNK")
    print("  T_C_warm ≈ MNK/64 × 128cy × (TK/reg_k - 1)/(TK/reg_k) × 2  [load+store]")
    print("  T_A_cold ≈ MNK × (1/4 cold-rtk-groups) × 120cy / 64         [per reg-tile]")
    print("  TK=256: warm_frac=63/64")
    # 128 cy per C reg tile pair (load + store, both L1 warm)
    t_c_warm_v2 = MNK / 64 * 128 * (63 / 64)
    t_a_cold    = MNK * (1 / 4) * 120 / 64
    t_warm_a    = MNK * (3 / 4) * 64 / 64   # warm hits within same spatial group
    t_pred = t_c_warm_v2 + t_a_cold + t_warm_a
    cf_pred = t_pred * REG_N / MNK
    print(f"  T_C_warm = {t_c_warm_v2/1e6:.1f}M cy")
    print(f"  T_A_cold = {t_a_cold/1e6:.1f}M cy")
    print(f"  T_A_warm = {t_warm_a/1e6:.1f}M cy")
    print(f"  T_pred   = {t_pred/1e6:.1f}M cy  (measured ≈ 54.3M)")
    print(f"  C_fill_pred = {cf_pred:.3f}  (measured ≈ 12.95)")


if __name__ == "__main__":
    run()
