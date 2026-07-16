"""E3: Measure C_fill(TM) cleanly using gc=0.

C_fill(TM) is the cost per A register-tile load at a given TM.  It is the
fundamental hardware constant in the revised model:

    T  =  MNK * max(alpha(TM),  gc/TM)
    alpha(TM)  =  C_fill(TM) / reg_n

With gc=0 (B generation is instantaneous):
    T_measured  =  T_A  exactly  (zero B-cost contamination)
    C_fill(TM)  =  T_measured * reg_n / MNK

Previous experiments used gc=1 which introduced a small B-cost bias
(~1% at TM=32).  gc=0 eliminates this entirely.

Two sub-sweeps:
  S1 — vary TM (TN fixed at 32): measures C_fill(TM) across cache regimes
       TM in {8, 16, 24, 32, 48, 64, 96, 128}
       M=192 to allow TM=24, 48, 96 as valid divisors.

  S2 — vary TN (TM fixed at 32): confirms TN-independence at gc=0
       TN in {4, 8, 16, 32, 64}
       C_fill should be constant across all TN values.
"""

from pathlib import Path

from experiments.harness import Flags, lineplot, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
N = K    = 256
A_P      = 4
C_P      = 4
LINE     = 64
L1       = 16_384
L2       = 4 * L1
REG_N    = 4
TK       = K

M1       = 192   # allows TM=24,48,96 as divisors
M2       = 256

MNK1     = M1 * N * K
MNK2     = M2 * N * K

TM_SWEEP_M192 = [8, 16, 24, 32, 48, 64, 96]   # S1a — M=192 (allows non-power-of-2)
TM_SWEEP_M256 = [128]                          # S1b — M=256 (TM=128 needs M divisible by 128)
TN_SWEEP = [4, 8, 16, 32, 64]                  # S2 — M=256, TM=32

L2_BOUNDARY_TM = L2 // (TK * A_P)   # = 64

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True, mulac_norecord=True)

_BASE: dict[str, object] = {
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "L2_SIZE_BYTES":      L2,
    "L2_LINE_SIZE_BYTES": LINE,
    "L2_ASSOC":           L2 // LINE,
    "L2_ACCESS_CYCLES":   14,
    "TILE_K":             TK,
    "PRNG_FIFO_GEN_COST": 0,            # exact zero: no B-cost bias
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,  # generous; stalls impossible at gc=0
}


def cfill(cycles: int, mnk: int) -> float:
    return cycles * REG_N / mnk


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── S1: TM sweep, TN=32 ──────────────────────────────────────────────────
    # S1a: TM ≤ 96 with M=192 (allows TM=24,48,96 as divisors of 192)
    # S1b: TM=128 with M=256 (128 divides 256 but not 192)
    TN_FIXED = 32
    print(f"\n=== S1a: TM sweep (gc=0, TN={TN_FIXED}, M={M1}) ===")

    s1a = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M1, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_M": TM_SWEEP_M192},
        flags=FLAGS,
    )

    print(f"\n=== S1b: TM=128 (gc=0, TN={TN_FIXED}, M={M2}) ===")

    s1b = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M2, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_M": TM_SWEEP_M256},
        flags=FLAGS,
    )

    # Combine, computing C_fill with the correct MNK for each M
    s1_entries = (
        [(r.overrides["TILE_M"], cfill(r.metrics.cycles, MNK1), r.metrics.cycles) for r in s1a] +
        [(r.overrides["TILE_M"], cfill(r.metrics.cycles, MNK2), r.metrics.cycles) for r in s1b]
    )

    tm_vals  = [e[0] for e in s1_entries]
    cfill_tm = [e[1] for e in s1_entries]
    a_bytes  = [tm * TK * A_P for tm in tm_vals]

    print(f"\n{'TM':>6}  {'A-tile':>10}  {'regime':>6}  {'cycles':>14}  {'C_fill':>10}")
    print("-" * 60)
    for tm, cf, ab, (_, _, cyc) in zip(tm_vals, cfill_tm, a_bytes, s1_entries):
        regime = "DRAM" if ab > L2 else "L2  "
        marker = "  ← L2 overflow" if ab > L2 else ""
        print(f"{tm:>6}  {ab//1024:>8}KB  {regime}  {cyc:>14,}  {cf:>10.3f}{marker}")

    lineplot(
        {"C_fill (cycles/A-reg-tile load)": list(zip(tm_vals, cfill_tm))},
        out_path=EXPERIMENT_DIR / "cfill_vs_tm.png",
        vlines={"L2 boundary (TM=64)": float(L2_BOUNDARY_TM)},
        xlabel=f"TM  (gc=0, TN={TN_FIXED})",
        ylabel="C_fill = T × reg_n / MNK  (cycles per A register-tile load)",
        title=f"C_fill(TM) at gc=0: exact A-load cost\nN=K={N}, TK={TK}",
        colors={"C_fill (cycles/A-reg-tile load)": "#1A50B0"},
    )

    # ── S2: TN sweep, TM=32, M=256 ───────────────────────────────────────────
    TM_FIXED = 32
    print(f"\n=== S2: TN sweep (gc=0, TM={TM_FIXED} fixed, M={M2}) ===")

    s2_results = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**_BASE, "A_HEIGHT_DIM": M2, "TILE_M": TM_FIXED},
        sweep_axes={"TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    tn_vals   = [r.overrides["TILE_N"] for r in s2_results]
    cfill_tn  = [cfill(r.metrics.cycles, MNK2) for r in s2_results]

    print(f"\n{'TN':>6}  {'R=TN/4':>8}  {'cycles':>14}  {'C_fill':>10}")
    print("-" * 48)
    for tn, cf, r in zip(tn_vals, cfill_tn, s2_results):
        print(f"{tn:>6}  {tn//REG_N:>8}  {r.metrics.cycles:>14,}  {cf:>10.3f}")

    print("\n[C_fill should be constant across all TN — if so, TN-independence is confirmed at gc=0]")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n── C_fill(TM) summary (gc=0, no B-cost bias) ──")
    for tm, cf, ab in zip(tm_vals, cfill_tm, a_bytes):
        regime = "DRAM" if ab > L2 else "L2  "
        print(f"  TM={tm:>3d} ({regime}, A={ab//1024:>3d}KB): "
              f"C_fill = {cf:.3f}  α = {cf/REG_N:.4f}")

    cf32 = next(cf for tm, cf in zip(tm_vals, cfill_tm) if tm == 32)
    print(f"\n  Reference: C_fill(TM=32) = {cf32:.3f} cycles  "
          f"(L2_ACCESS_CYCLES = 14)")


if __name__ == "__main__":
    run()
