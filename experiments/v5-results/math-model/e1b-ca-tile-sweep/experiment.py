"""E1b: Measure C_A as a function of tile shape.

Model under test:
    T = MNK * max(C_A / TN,  C_B / TM)

C_A is the effective cost per A-element inter-session access — it bundles the
L1/L2/DRAM miss cost plus the L1 reuse structure inside a session.  We isolate
it by running with gen_cost=1 (B cost negligible) and --mulac_norecord:

    C_A(TM, TN)  =  T_measured * TN / (M * N * K)

Two sub-sweeps separate the two effects that control C_A:

  Sub-sweep 1 — L2 boundary (TN=32 fixed, vary TM)
      R = TN / reg_n = 8  stays constant; only the A-tile size changes.
      Theory: C_A is flat while A tile fits in L2, then jumps when it spills.
      L2 threshold: TM * TK * A_P = L2_SIZE  ->  TM = 64.
      Note: M=192 here (not 256) so TM=48 is a valid divisor, giving a
      data point between the safe zone (TM=32) and the overflow (TM=64).
      M=256 only has powers-of-2 as divisors; no TM between 32 and 64 exists.

  Sub-sweep 2 — L1 reuse factor (TM=32 fixed, vary TN)
      A-tile bytes = TM*TK*A_P = 32 KB, always fits in L2; only R changes.
      Theory: C_A falls as TN grows (more L1 hits per cold fill).
      L1 threshold for C tile: TM * TN * C_P = L1_SIZE  ->  TN = 128.
      M=N=256 here (standard workload).
"""

from pathlib import Path

from experiments.harness import Flags, lineplot, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware and workload constants ──────────────────────────────────────────
N = K     = 256
A_P       = B_P = 4    # bytes per element
C_P       = 4
LINE      = 64          # cache-line bytes
L1        = 16_384
L2        = 4 * L1      # 65 536 bytes
REG_N     = 4           # must match REG_N in config

TK        = K           # one k-slice covers the full K dimension

# Sub-sweep 1 uses M=192 so that TM=48 (between 32 and 64) is a valid divisor.
# 256 only has powers-of-2 divisors; 192 = 64×3 adds multiples of 3.
M1 = 192   # for sub-sweep 1
M2 = 256   # for sub-sweep 2 (standard)

# L2 boundary (sub-sweep 1): A tile overflows L2 when TM > this
L2_BOUNDARY_TM = L2 // (TK * A_P)          # = 64

# L1 boundary (sub-sweep 2): C tile overflows L1 when TN > this
L1_BOUNDARY_TN = L1 // (32 * C_P)          # = 128  (TM=32 fixed)

# ── Sweep axes ───────────────────────────────────────────────────────────────
# All TM values must divide M1=192: valid choices are {8,16,24,32,48,64,96,192}
TM_SWEEP  = [8, 16, 24, 32, 48, 64, 96]    # TN=32 fixed; M=192
TN_FIXED  = 32

# All TN values must divide N=256: powers of 2 up to 256
TN_SWEEP  = [4, 8, 16, 32, 64, 128, 256]   # TM=32 fixed; M=256
TM_FIXED  = 32

# ── Config / flags shared by every cell ─────────────────────────────────────
_BASE: dict[str, object] = {
    "A_WIDTH_DIM":       K,
    "B_WIDTH_DIM":       N,
    "A_PRECISION_BYTES": A_P,
    "B_PRECISION_BYTES": B_P,
    "L1_SIZE_BYTES":     L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":          L1 // LINE,
    "L2_SIZE_BYTES":     L2,
    "L2_LINE_SIZE_BYTES": LINE,
    "L2_ASSOC":          L2 // LINE,
    "L2_ACCESS_CYCLES":  14,
    "TILE_K":            TK,
    "PRNG_FIFO_GEN_COST": 1,                         # B cost ≈ 0
}

BASE_S1: dict[str, object] = {
    **_BASE,
    "A_HEIGHT_DIM":       M1,
    "PRNG_FIFO_CAPACITY": 2 * TK * TN_FIXED,
}

BASE_S2: dict[str, object] = {
    **_BASE,
    "A_HEIGHT_DIM":       M2,
    "PRNG_FIFO_CAPACITY": 2 * TK * max(TN_SWEEP),
}

# gc=1 traffic run: no MULAC, B source is prng_fifo
FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True, mulac_norecord=True)


def _ca(cycles: int, tn: int, mnk: int) -> float:
    """Derive C_A from a measured cycle count and TN."""
    return cycles * tn / mnk


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Sub-sweep 1: TM sweep, TN=TN_FIXED, M=M1=192 ────────────────────────
    print(f"\n=== Sub-sweep 1: TM sweep (TN={TN_FIXED} fixed, M={M1}) ===")
    MNK1 = M1 * N * K
    tm_results = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**BASE_S1, "TILE_N": TN_FIXED},
        sweep_axes={"TILE_M": TM_SWEEP},
        flags=FLAGS,
    )

    tm_vals = [r.overrides["TILE_M"] for r in tm_results]
    ca_tm   = [_ca(r.metrics.cycles, TN_FIXED, MNK1) for r in tm_results]
    a_bytes = [tm * TK * A_P for tm in tm_vals]

    print(f"\n{'TM':>6}  {'TN':>6}  {'A-tile':>10}  {'cycles':>14}  {'C_A':>10}")
    print("-" * 55)
    for tm, ca, ab, r in zip(tm_vals, ca_tm, a_bytes, tm_results):
        flag = "  ← L2 overflow" if ab > L2 else ""
        print(f"{tm:>6}  {TN_FIXED:>6}  {ab//1024:>8}KB  {r.metrics.cycles:>14,}  {ca:>10.1f}{flag}")

    lineplot(
        {"C_A (cycles/A-access)": list(zip(tm_vals, ca_tm))},
        out_path=EXPERIMENT_DIR / "ca_vs_tm.png",
        vlines={"L2 boundary (TM=64)": float(L2_BOUNDARY_TM)},
        xlabel=f"TM  (TN={TN_FIXED} fixed, R={TN_FIXED//REG_N} fixed, M={M1})",
        ylabel="C_A = T × TN / MNK  (cycles per A-element access)",
        title=f"C_A vs TM: isolating the L2 boundary\n"
              f"M={M1}, N=K={N}, TK={TK}, A_P={A_P}B, L2={L2//1024}KB",
        colors={"C_A (cycles/A-access)": "#1A50B0"},
    )

    # ── Sub-sweep 2: TN sweep, TM=TM_FIXED, M=M2=256 ────────────────────────
    print(f"\n=== Sub-sweep 2: TN sweep (TM={TM_FIXED} fixed, M={M2}) ===")
    MNK2 = M2 * N * K
    tn_results = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides={**BASE_S2, "TILE_M": TM_FIXED},
        sweep_axes={"TILE_N": TN_SWEEP},
        flags=FLAGS,
    )

    tn_vals = [r.overrides["TILE_N"] for r in tn_results]
    ca_tn   = [_ca(r.metrics.cycles, tn, MNK2) for tn, r in zip(tn_vals, tn_results)]
    r_vals  = [tn // REG_N for tn in tn_vals]
    c_bytes = [TM_FIXED * tn * C_P for tn in tn_vals]

    print(f"\n{'TM':>6}  {'TN':>6}  {'R':>6}  {'C-tile':>10}  {'cycles':>14}  {'C_A':>10}")
    print("-" * 60)
    for tn, r_val, cb, ca, res in zip(tn_vals, r_vals, c_bytes, ca_tn, tn_results):
        flag = "  ← C overflows L1" if cb > L1 else ""
        print(f"{TM_FIXED:>6}  {tn:>6}  {r_val:>6}  {cb//1024:>8}KB  {res.metrics.cycles:>14,}  {ca:>10.1f}{flag}")

    lineplot(
        {"C_A (cycles/A-access)": list(zip(tn_vals, ca_tn))},
        out_path=EXPERIMENT_DIR / "ca_vs_tn.png",
        vlines={f"L1 boundary for C (TN={L1_BOUNDARY_TN})": float(L1_BOUNDARY_TN)},
        xlabel=f"TN  (TM={TM_FIXED} fixed, A tile={TM_FIXED*TK*A_P//1024}KB constant)",
        ylabel="C_A = T × TN / MNK  (cycles per A-element access)",
        title=f"C_A vs TN: L1 reuse factor R = TN / reg_n\n"
              f"M=N=K={M2}, TK={TK}, A_P={A_P}B, L2={L2//1024}KB",
        colors={"C_A (cycles/A-access)": "#B04000"},
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    ca_s2_baseline = _ca(
        next(r.metrics.cycles for r in tn_results if r.overrides["TILE_N"] == TN_FIXED),
        TN_FIXED, MNK2,
    )
    print(f"\n── Summary ──")
    print(f"C_A at TM={TM_FIXED}, TN={TN_FIXED} (standard config, M={M2}): {ca_s2_baseline:.1f} cycles/A-access")
    print(f"L2 boundary: TM={L2_BOUNDARY_TM} (A tile = {L2_BOUNDARY_TM*TK*A_P//1024}KB = L2 size)")
    print(f"L1 boundary for C: TN={L1_BOUNDARY_TN} (C tile = {TM_FIXED*L1_BOUNDARY_TN*C_P//1024}KB = L1 size)")
    print(f"Plots written to {EXPERIMENT_DIR}")


if __name__ == "__main__":
    run()
