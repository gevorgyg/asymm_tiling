"""E3-nol2: Measure α(TM) and C_fill(TM) cleanly at gc=0, L1-only.

L1-only (--no-l2): L1 fallthrough goes directly to DRAM (180 cy).
No L2 in the hierarchy.

C_fill(TM) = cycles per A register-tile load.
α(TM)      = C_fill(TM) / reg_n   = T_gc0 / MNK   (exact at gc=0).

L1 overflow threshold for A tile:
    TM_L1 = L1 / (TK × A_P) = 16384 / (256 × 4) = 16
    TM ≤ 16: A tile fits in L1    → C_fill ≈ L1_lat? or DRAM_lat?
    TM >  16: A tile overflows     → C_fill ≈ DRAM_lat (180 cy)

This is the primary calibration experiment.  All subsequent no-l2
experiments (E8-nol2, E13-nol2) depend on the α table produced here.

Three sub-sweeps:

  S1 — TM sweep (TN=32, gc=0):
       Measures α(TM) across the L1 regime boundary at TM=16.
       TM ∈ {4, 8, 12, 16, 24, 32, 48, 64, 96} with M=192,
       TM=128 with M=256 (requires M divisible by 128).

  S2 — TN sweep at TM=8 (A fits in L1, gc=0, M=256):
       Tests TN-independence when A stays within L1.
       Key question: is C_fill ≈ L1_lat (warm L1 hits) or DRAM_lat (eviction)?

  S3 — TN sweep at TM=32 (A overflows L1, gc=0, M=256):
       Tests TN-independence in the DRAM regime.
       Expected: C_fill ≈ DRAM_lat regardless of TN.

Comparing S2 vs S3 reveals the regime-jump magnitude.
"""

from pathlib import Path

from experiments.harness import Flags, lineplot, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
N = K     = 256
A_P       = 4
C_P       = 4
LINE      = 64
L1        = 16_384
L1_LAT    = 4
DRAM_LAT  = 180
REG_N     = 4
TK        = K

M1        = 192    # allows TM=4,8,12,16,24,32,48,64,96 as divisors
M2        = 256

MNK1      = M1 * N * K
MNK2      = M2 * N * K

L1_BOUNDARY_TM = L1 // (TK * A_P)   # = 16

TM_SWEEP_M192 = [4, 8, 12, 16, 24, 32, 48, 64, 96]
TM_SWEEP_M256 = [128]
TN_SWEEP      = [4, 8, 16, 32, 64]

TM_IN_L1   = 8    # A = 8 KB < L1 = 16 KB
TM_IN_DRAM = 32   # A = 32 KB > L1 = 16 KB

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True,
              mulac_norecord=True, no_l2=True)

# No L2 keys — they are unused (and stripped from cache key) when no_l2=True.
_BASE: dict[str, object] = {
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "TILE_K":             TK,
    "PRNG_FIFO_GEN_COST": 0,
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,
}


def cfill(cycles: int, mnk: int) -> float:
    return cycles * REG_N / mnk


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── S1: TM sweep, TN=32, gc=0 ────────────────────────────────────────────
    TN_FIXED = 32
    print(f"\n=== S1a: TM sweep (gc=0, TN={TN_FIXED}, M={M1}, no-l2) ===")

    s1a = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M1, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_M": TM_SWEEP_M192},
        flags=FLAGS,
    )

    print(f"\n=== S1b: TM=128 (gc=0, TN={TN_FIXED}, M={M2}, no-l2) ===")

    s1b = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M2, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_M": TM_SWEEP_M256},
        flags=FLAGS,
    )

    s1_entries = (
        [(r.overrides["TILE_M"], cfill(r.metrics.cycles, MNK1), r.metrics.cycles)
         for r in s1a] +
        [(r.overrides["TILE_M"], cfill(r.metrics.cycles, MNK2), r.metrics.cycles)
         for r in s1b]
    )

    tm_vals  = [e[0] for e in s1_entries]
    cfill_tm = [e[1] for e in s1_entries]
    alpha_tm = [cf / REG_N for cf in cfill_tm]

    print(f"\n{'TM':>6}  {'A-tile':>10}  {'regime':>4}  {'cycles':>14}  "
          f"{'C_fill':>8}  {'α':>8}")
    print("-" * 70)
    for tm, cf, alpha, (_, _, cyc) in zip(tm_vals, cfill_tm, alpha_tm, s1_entries):
        regime = "DRAM" if tm * TK * A_P > L1 else "L1  "
        marker = "  ← L1 overflow" if tm * TK * A_P > L1 and \
                  (tm - 1) * TK * A_P <= L1 else ""
        if tm == L1_BOUNDARY_TM:
            marker = "  ← L1 boundary"
        print(f"{tm:>6}  {tm * TK * A_P // 1024:>8}KB  {regime}  {cyc:>14,}  "
              f"{cf:>8.3f}  {alpha:>8.4f}{marker}")

    lineplot(
        {"α(TM) = C_fill / reg_n": list(zip(tm_vals, alpha_tm))},
        out_path=EXPERIMENT_DIR / "alpha_vs_tm.png",
        vlines={f"L1 boundary (TM={L1_BOUNDARY_TM})": float(L1_BOUNDARY_TM)},
        xlabel=f"TM  (gc=0, TN={TN_FIXED}, no-l2)",
        ylabel="α = T / MNK  (cycles per A element)",
        title=f"α(TM) in L1-only: clean A-cost calibration\nN=K={N}, TK={TK}",
        colors={"α(TM) = C_fill / reg_n": "#C03000"},
    )

    # ── S2: TN sweep, TM=8 (A fits in L1) ────────────────────────────────────
    print(f"\n=== S2: TN sweep (gc=0, TM={TM_IN_L1} [A in L1], M={M2}) ===")

    s2 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M2, "TILE_M": TM_IN_L1},
        sweep_axes={"TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    tn_vals_s2  = [r.overrides["TILE_N"] for r in s2]
    cfill_s2    = [cfill(r.metrics.cycles, MNK2) for r in s2]
    alpha_s2    = [cf / REG_N for cf in cfill_s2]

    print(f"\n{'TN':>6}  {'R=TN/4':>8}  {'cycles':>14}  "
          f"{'C_fill':>8}  {'α':>8}  {'C_fill/R':>10}")
    print("-" * 68)
    for tn, cf, alpha, r in zip(tn_vals_s2, cfill_s2, alpha_s2, s2):
        R = tn // REG_N
        print(f"{tn:>6}  {R:>8}  {r.metrics.cycles:>14,}  "
              f"{cf:>8.3f}  {alpha:>8.4f}  {cf/R:>10.3f}")

    print(f"\n  TM={TM_IN_L1} (A={TM_IN_L1*TK*A_P//1024}KB fit in L1={L1//1024}KB):")
    print(f"  If C_fill/R ≈ {L1_LAT}   → warm L1 hits dominate")
    print(f"  If C_fill/R ≈ {DRAM_LAT} → DRAM eviction dominates")

    # ── S3: TN sweep, TM=32 (A overflows L1) ─────────────────────────────────
    print(f"\n=== S3: TN sweep (gc=0, TM={TM_IN_DRAM} [A in DRAM], M={M2}) ===")

    s3 = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M2, "TILE_M": TM_IN_DRAM},
        sweep_axes={"TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    tn_vals_s3  = [r.overrides["TILE_N"] for r in s3]
    cfill_s3    = [cfill(r.metrics.cycles, MNK2) for r in s3]
    alpha_s3    = [cf / REG_N for cf in cfill_s3]

    print(f"\n{'TN':>6}  {'R=TN/4':>8}  {'cycles':>14}  "
          f"{'C_fill':>8}  {'α':>8}  {'C_fill/R':>10}")
    print("-" * 68)
    for tn, cf, alpha, r in zip(tn_vals_s3, cfill_s3, alpha_s3, s3):
        R = tn // REG_N
        print(f"{tn:>6}  {R:>8}  {r.metrics.cycles:>14,}  "
              f"{cf:>8.3f}  {alpha:>8.4f}  {cf/R:>10.3f}")

    print(f"\n  TM={TM_IN_DRAM} (A={TM_IN_DRAM*TK*A_P//1024}KB > L1={L1//1024}KB):")
    print(f"  Expected C_fill/R ≈ {DRAM_LAT} (DRAM dominates)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("SUMMARY: α(TM) table (no-l2, gc=0, TN=32)")
    print(f"{'═'*72}")
    print(f"  L1 boundary at TM={L1_BOUNDARY_TM}  "
          f"(A tile = {L1_BOUNDARY_TM*TK*A_P//1024}KB = L1 = {L1//1024}KB)")
    print(f"  L1_lat={L1_LAT} cy,  DRAM_lat={DRAM_LAT} cy")
    print()
    print(f"  {'TM':>4}  {'A-tile':>8}  {'regime':>4}  {'α(TM)':>8}  {'C_fill':>8}")
    print("  " + "-" * 44)
    for tm, alpha, cf in zip(tm_vals, alpha_tm, cfill_tm):
        a_kb = tm * TK * A_P // 1024
        regime = "DRAM" if tm * TK * A_P > L1 else "L1  "
        print(f"  {tm:>4}  {a_kb:>6}KB  {regime}  {alpha:>8.4f}  {cf:>8.3f}")

    print()
    cf_s2_ref = cfill_s2[tn_vals_s2.index(32)] if 32 in tn_vals_s2 else cfill_s2[-1]
    cf_s3_ref = cfill_s3[tn_vals_s3.index(32)] if 32 in tn_vals_s3 else cfill_s3[-1]
    print(f"  TN sweep at TM={TM_IN_L1} (in-L1):   C_fill/R = {cf_s2_ref/8:.3f} "
          f"(R=8, TN=32)")
    print(f"  TN sweep at TM={TM_IN_DRAM} (in-DRAM): C_fill/R = {cf_s3_ref/8:.3f} "
          f"(R=8, TN=32)")
    print(f"  Ratio DRAM/L1 C_fill per load: "
          f"{cf_s3_ref / cf_s2_ref:.2f}×  "
          f"(theoretical: {DRAM_LAT}/{L1_LAT}={DRAM_LAT//L1_LAT}×)")


if __name__ == "__main__":
    run()
