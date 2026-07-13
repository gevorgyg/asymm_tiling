"""E4-nol2: Why is α ≈ 3.4 in L1-only, and why does it jump at TM=96?

E3-nol2 found two surprising results:
  (1) α ≈ 3.4 for TM=4..64, nearly the same as the L2 case — despite L2 being
      absent and DRAM_lat being 45× L1_lat.
  (2) α jumps sharply to ≈9.0 at TM=96, not at TM=16 (A's L1 overflow boundary).

This experiment probes the mechanisms behind both observations.

Hardware parameters under test:
  L1_ACCESS_CYCLES (default 4)  — warm cache hits
  MEM_ACCESS_CYCLES (default 180) — all L1 misses in no-l2 mode

Four sub-sweeps:

  E4a — TK sweep (TM=32, TN=32):
    As TK shrinks, warm-C fraction (TK/reg_k - 1)/(TK/reg_k) → 0.
    Same structure as the L2 experiment's E4a.
    Confirms warm C hits are still the baseline cost driver.

  E4b — L1_ACCESS_CYCLES sweep (TM=8 and TM=32, TN=32, MEM=180 fixed):
    If C load/store warm L1 hits dominate α, then α ∝ L1_lat.
    If DRAM (B or A) cold fills dominate, α is nearly flat vs L1_lat.
    Slope of α vs L1_lat ≈ 2 × (sessions × TM/4 × TK/4 × TN/4) / MNK
    For TM=32, TN=32: theoretical warm-C slope ≈ 2/(REG_N) = 0.5/4 per cycle.
    For TM=8:  same formula = same slope.

  E4c — MEM_ACCESS_CYCLES sweep (TM=8 and TM=32, TN=32, L1=4 fixed):
    If B FIFO data (which overflows L1) dominates, α ∝ MEM_lat.
    Expected slope ≈ (B_load_count + A_miss_count) / MNK.
    For TM=8:  A is mostly L1-warm (small slope component from A).
    For TM=32: A is always DRAM (larger slope than TM=8).

  E4d — TN sweep at TM=96 (α=9.03 at TN=32):
    TM=96, TN=32: C tile = 192 lines (75% of L1). C might be getting evicted.
    At TN=4: C tile = 24 lines (fits easily). If α drops to ≈3.4, C eviction
    is the cause. If α stays high, TM=96 itself is pathological for A/B.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
N = K    = 256
A_P = C_P = 4
LINE      = 64
L1        = 16_384
L1_LAT    = 4
MEM_LAT   = 180
REG_N = REG_M = REG_K = 4
TK        = K

M1        = 192   # supports TM=96 as divisor
M2        = 256

MNK1      = M1 * N * K   # 12,582,912
MNK2      = M2 * N * K   # 16,777,216

L1_BOUNDARY_TM = L1 // (TK * A_P)   # = 16

FLAGS = Flags(b_source="prng_fifo", stationary="C", three_d_reg=True,
              mulac_norecord=True, no_l2=True)

_BASE192: dict[str, object] = {
    "A_HEIGHT_DIM":       M1,
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "L1_ACCESS_CYCLES":   L1_LAT,
    "MEM_ACCESS_CYCLES":  MEM_LAT,
    "TILE_K":             TK,
    "PRNG_FIFO_GEN_COST": 0,
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,
}
_BASE256 = {**_BASE192, "A_HEIGHT_DIM": M2}


def alpha(cycles: int, mnk: int) -> float:
    return cycles / mnk


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── E4a: TK sweep (TM=32, TN=32) ─────────────────────────────────────────
    TM_A = 32
    TN_A = 32
    TK_SWEEP = [4, 8, 16, 32, 64, 128, 256]

    print(f"\n=== E4a: TK sweep (TM={TM_A}, TN={TN_A}, no-l2, gc=0) ===")
    print("  Warm-C fraction = (TK/4-1)/(TK/4). Spike expected at small TK.")

    e4a = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE256, "TILE_M": TM_A, "TILE_N": TN_A},
        sweep_axes={"TILE_K": TK_SWEEP},
        flags=FLAGS,
    )

    print(f"\n{'TK':>5}  {'warm-C%':>8}  {'cycles':>14}  {'α':>8}")
    print("-" * 42)
    for r in e4a:
        tk = r.overrides["TILE_K"]
        wf = (tk // REG_K - 1) / (tk // REG_K) if tk >= REG_K else 0
        a  = alpha(r.metrics.cycles, MNK2)
        print(f"{tk:>5}  {100*wf:>7.1f}%  {r.metrics.cycles:>14,}  {a:>8.4f}")

    # ── E4b: L1_ACCESS_CYCLES sweep ───────────────────────────────────────────
    L1_CY_SWEEP = [2, 4, 6, 8, 12, 16]

    for tm_b, base_b, mnk_b in [(8, _BASE256, MNK2), (32, _BASE256, MNK2)]:
        TN_B = 32
        print(f"\n=== E4b: L1_ACCESS_CYCLES sweep (TM={tm_b}, TN={TN_B}, MEM=180 fixed) ===")
        print("  If α ∝ L1_lat: warm L1 (C or A) dominates.")
        print("  If α flat: DRAM cold fills (B, or A for TM=32) dominate.")

        results = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**base_b, "TILE_M": tm_b, "TILE_N": TN_B,
                            "MEM_ACCESS_CYCLES": MEM_LAT},
            sweep_axes={"L1_ACCESS_CYCLES": L1_CY_SWEEP},
            flags=FLAGS,
        )

        a_ref = alpha(next(r.metrics.cycles for r in results
                           if r.overrides["L1_ACCESS_CYCLES"] == L1_LAT), mnk_b)

        print(f"\n{'L1_lat':>7}  {'cycles':>14}  {'α':>8}  {'α/α(4)':>8}")
        print("-" * 50)
        for r in results:
            l1 = r.overrides["L1_ACCESS_CYCLES"]
            a  = alpha(r.metrics.cycles, mnk_b)
            print(f"{l1:>7}  {r.metrics.cycles:>14,}  {a:>8.4f}  {a/a_ref:>8.4f}")

    # ── E4c: MEM_ACCESS_CYCLES sweep ──────────────────────────────────────────
    MEM_CY_SWEEP = [45, 90, 135, 180, 270, 360]

    for tm_c, base_c, mnk_c in [(8, _BASE256, MNK2), (32, _BASE256, MNK2)]:
        TN_C = 32
        print(f"\n=== E4c: MEM_ACCESS_CYCLES sweep (TM={tm_c}, TN={TN_C}, L1=4 fixed) ===")
        print("  If α ∝ MEM_lat: DRAM cold fills (B FIFO data, or A for TM=32) dominate.")

        results = run_grid(
            experiment_dir=EXPERIMENT_DIR,
            base_config_text=base,
            base_overrides={**base_c, "TILE_M": tm_c, "TILE_N": TN_C,
                            "L1_ACCESS_CYCLES": L1_LAT},
            sweep_axes={"MEM_ACCESS_CYCLES": MEM_CY_SWEEP},
            flags=FLAGS,
        )

        a_ref = alpha(next(r.metrics.cycles for r in results
                           if r.overrides["MEM_ACCESS_CYCLES"] == MEM_LAT), mnk_c)

        print(f"\n{'MEM_lat':>8}  {'cycles':>14}  {'α':>8}  {'α/α(180)':>10}")
        print("-" * 54)
        for r in results:
            mem = r.overrides["MEM_ACCESS_CYCLES"]
            a   = alpha(r.metrics.cycles, mnk_c)
            print(f"{mem:>8}  {r.metrics.cycles:>14,}  {a:>8.4f}  {a/a_ref:>10.4f}")

    # ── E4d: TN sweep at TM=96 (α jump regime) ───────────────────────────────
    TM_D = 96
    TN_D_SWEEP = [4, 8, 16, 32]
    print(f"\n=== E4d: TN sweep at TM={TM_D} (α=9.03 at TN=32 in E3-nol2) ===")
    print(f"  C tile = TM×TN×C_P lines: TN=4→{TM_D*4*C_P//LINE}, TN=32→{TM_D*32*C_P//LINE}")
    print(f"  If α drops to ≈3.4 at small TN: C tile overflow drives the jump.")
    print(f"  If α stays high even at TN=4: TM=96 is intrinsically expensive for A/B.")

    e4d = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE192, "TILE_M": TM_D},
        sweep_axes={"TILE_N": TN_D_SWEEP},
        flags=FLAGS,
    )

    print(f"\n{'TN':>5}  {'C lines':>8}  {'C+A fit?':>10}  {'cycles':>14}  {'α':>8}")
    print("-" * 60)
    for r in e4d:
        tn = r.overrides["TILE_N"]
        c_lines = TM_D * tn * C_P // LINE
        a_lines = TM_D * TK * A_P // LINE   # total A lines per session
        fits = "fits" if c_lines + a_lines <= L1 // LINE else "overflow"
        a = alpha(r.metrics.cycles, MNK1)
        print(f"{tn:>5}  {c_lines:>8}  {fits:>10}  {r.metrics.cycles:>14,}  {a:>8.4f}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print("SUMMARY: mechanism of α in L1-only")
    print(f"{'═'*65}")
    print("  E4a (TK sweep):   does warm-C fraction drive α?")
    print("  E4b (L1_lat):     slope of α vs L1_lat → warm L1 contribution")
    print("  E4c (MEM_lat):    slope of α vs MEM_lat → DRAM contribution")
    print("  E4d (TN@TM=96):   does reducing TN (shrinking C tile) rescue α?")
    print()
    print("  Key predictions (from B-DRAM-dominance hypothesis):")
    print(f"  E4b slope (α per L1_lat cy):   ≈ {2 * MNK2 / (REG_N * MNK2):.4f} (warm C only)")
    print(f"  E4c slope (α per MEM_lat cy):  ≈ {262144 / MNK2:.4f} (B count / MNK, TM=8)")
    print(f"  E4c TM=32 vs TM=8 slope diff:  ≈ {32768 / MNK2:.4f} (extra DRAM-A / MNK)")


if __name__ == "__main__":
    run()
