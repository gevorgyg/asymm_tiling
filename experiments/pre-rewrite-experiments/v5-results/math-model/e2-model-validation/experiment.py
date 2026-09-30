"""E2: Validate the revised model T = MNK * max(alpha(TM), gc/TM).

E1b showed that C_A scales linearly with TN (C_A ≈ 13.5 * TN/reg_n), so TN
cancels out of the formula T = MNK * max(C_A/TN, gc/TM):

    T  =  MNK * max(alpha(TM),  gc/TM)
    alpha(TM)  =  T_A / MNK   (measured from gc=1 baseline, constant in TN)

Two predictions are tested:

  Prediction 1 — TN independence:
      At fixed TM=32 and gc, total T does not depend on TN (within L1 bounds).
      Sub-sweep: TN ∈ {8,16,32,64}, gc ∈ {1, 64, 256, 512}.

  Prediction 2 — TM model fit:
      T = MNK * max(alpha(TM), gc/TM) matches measured T across (TM, gc).
      Sub-sweep: TM ∈ {8,16,32,64,128}, gc ∈ {1, 64, 256, 512}.
      Key prediction: at gc=512, TM=64 is ~2× faster than TM=32.

Both sub-sweeps use M=N=K=256, TK=K, 3D registers, mulac_norecord=True.
"""

from pathlib import Path

from experiments.harness import Flags, lineplot, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Constants ─────────────────────────────────────────────────────────────────
M = N = K = 256
A_P = B_P = C_P = 4
LINE = 64
L1 = 16_384
L2 = 4 * L1
REG_N = 4
TK = K   # one k-slice per tile step

# Prediction 1: TN independence
TM_FIXED     = 32
TN_SWEEP_P1  = [8, 16, 32, 64]          # TM×TN×C_P ≤ 8KB < L1 for all

# Prediction 2: TM model fit  (all TM values divide M=256)
TN_FIXED     = 32
TM_SWEEP_P2  = [8, 16, 32, 64, 128]

GC_SWEEP     = [1, 64, 256, 512]

MNK = M * N * K

FLAGS = Flags(b_source="prng_fifo", stationary="B", three_d_reg=True, mulac_norecord=True)

_BASE: dict[str, object] = {
    "A_HEIGHT_DIM":       M,
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  B_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "L2_SIZE_BYTES":      L2,
    "L2_LINE_SIZE_BYTES": LINE,
    "L2_ASSOC":           L2 // LINE,
    "L2_ACCESS_CYCLES":   14,
    "TILE_K":             TK,
}


def _t_predicted(alpha: float, gc: int, tm: int) -> float:
    return MNK * max(alpha, gc / tm)


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Prediction 1: TN independence ─────────────────────────────────────────
    print("\n=== Prediction 1: TN independence (TM=32 fixed) ===")

    p1_overrides: dict[str, object] = {
        **_BASE,
        "TILE_M":            TM_FIXED,
        "PRNG_FIFO_CAPACITY": 2 * TK * max(TN_SWEEP_P1),
    }

    p1_results = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=p1_overrides,
        sweep_axes={"TILE_N": TN_SWEEP_P1, "PRNG_FIFO_GEN_COST": GC_SWEEP},
        flags=FLAGS,
    )

    # Group by gc; within each gc show T across TN values
    from collections import defaultdict
    p1_by_gc: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for r in p1_results:
        tn = r.overrides["TILE_N"]
        gc = r.overrides["PRNG_FIFO_GEN_COST"]
        p1_by_gc[gc].append((tn, r.metrics.cycles))

    print(f"\n{'TN':>6}", end="")
    for gc in GC_SWEEP:
        print(f"  {'gc=' + str(gc):>14}", end="")
    print()
    print("-" * (6 + 16 * len(GC_SWEEP)))

    for tn in TN_SWEEP_P1:
        print(f"{tn:>6}", end="")
        for gc in GC_SWEEP:
            t = next(t for (n, t) in p1_by_gc[gc] if n == tn)
            print(f"  {t:>14,}", end="")
        print()

    print("\n[Model: all rows within each gc column should be equal]")

    # Plot: T vs TN for each gc
    p1_series = {
        f"gc={gc}": sorted(p1_by_gc[gc]) for gc in GC_SWEEP
    }
    lineplot(
        p1_series,
        out_path=EXPERIMENT_DIR / "p1_tn_independence.png",
        xlabel=f"TN  (TM={TM_FIXED} fixed)",
        ylabel="total cycles",
        title=f"Prediction 1: T independent of TN?\n"
              f"M=N=K={M}, TM={TM_FIXED}, TK={TK}",
    )

    # ── Prediction 2: TM model fit ────────────────────────────────────────────
    print(f"\n=== Prediction 2: TM model fit (TN={TN_FIXED} fixed) ===")

    p2_overrides: dict[str, object] = {
        **_BASE,
        "TILE_N":             TN_FIXED,
        "PRNG_FIFO_CAPACITY": 2 * TK * TN_FIXED,
    }

    p2_results = run_grid(
        experiment_dir=EXPERIMENT_DIR,
        base_config_text=base,
        base_overrides=p2_overrides,
        sweep_axes={"TILE_M": TM_SWEEP_P2, "PRNG_FIFO_GEN_COST": GC_SWEEP},
        flags=FLAGS,
    )

    # Build {(tm, gc): cycles} lookup
    p2_measured: dict[tuple[int, int], int] = {}
    for r in p2_results:
        tm = r.overrides["TILE_M"]
        gc = r.overrides["PRNG_FIFO_GEN_COST"]
        p2_measured[(tm, gc)] = r.metrics.cycles

    # Derive alpha(TM) from the gc=1 row
    alpha: dict[int, float] = {
        tm: p2_measured[(tm, 1)] / MNK
        for tm in TM_SWEEP_P2
    }

    print(f"\n{'TM':>6}  {'alpha':>8}  {'A-tile':>10}", end="")
    for gc in GC_SWEEP:
        print(f"  {'gc=' + str(gc):>10}", end="")
    print()
    print("-" * (28 + 12 * len(GC_SWEEP)))

    for tm in TM_SWEEP_P2:
        a = alpha[tm]
        a_bytes = tm * TK * A_P
        regime = "DRAM" if a_bytes > L2 else "L2"
        print(f"{tm:>6}  {a:>8.3f}  {a_bytes//1024:>7}KB/{regime}", end="")
        for gc in GC_SWEEP:
            meas = p2_measured[(tm, gc)]
            pred = _t_predicted(a, gc, tm)
            err  = (meas - pred) / pred * 100
            print(f"  {meas // 1_000_000:>3d}M ({err:+.0f}%)", end="")
        print()

    print("\nTable: measured total cycles in millions + model error %")

    # ── Plots ─────────────────────────────────────────────────────────────────
    # Plot 2a: measured T vs TM for each gc
    meas_series = {
        f"gc={gc} (measured)": sorted((tm, p2_measured[(tm, gc)]) for tm in TM_SWEEP_P2)
        for gc in GC_SWEEP
    }
    pred_series = {
        f"gc={gc} (predicted)": sorted((tm, _t_predicted(alpha[tm], gc, tm)) for tm in TM_SWEEP_P2)
        for gc in GC_SWEEP
    }
    lineplot(
        {**meas_series, **pred_series},
        out_path=EXPERIMENT_DIR / "p2_tm_model_fit.png",
        vlines={"L2 boundary (TM=64)": 64.0},
        xlabel=f"TM  (TN={TN_FIXED} fixed)",
        ylabel="total cycles",
        title=f"Prediction 2: T = MNK × max(α(TM), gc/TM) vs measured\n"
              f"M=N=K={M}, TK={TK}",
    )

    # Plot 2b: speedup of TM=64 over TM=32 per gc (model vs measured)
    speedup_meas = [(gc, p2_measured[(32, gc)] / p2_measured[(64, gc)]) for gc in GC_SWEEP]
    speedup_pred = [(gc, _t_predicted(alpha[32], gc, 32) / _t_predicted(alpha[64], gc, 64))
                    for gc in GC_SWEEP]
    lineplot(
        {"measured speedup (TM=64 / TM=32)":   speedup_meas,
         "predicted speedup (TM=64 / TM=32)":  speedup_pred},
        out_path=EXPERIMENT_DIR / "p2_tm64_vs_tm32_speedup.png",
        xlabel="gen_cost (gc)",
        ylabel="speedup  TM=32 cycles / TM=64 cycles",
        title=f"TM=64 speedup over TM=32: model vs measured\n"
              f"M=N=K={M}, TN={TN_FIXED}",
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n── Alpha values (T_A / MNK, gc=1 baseline) ──")
    for tm in TM_SWEEP_P2:
        a_kb = tm * TK * A_P // 1024
        regime = "DRAM" if a_kb * 1024 > L2 else "L2 "
        print(f"  TM={tm:>3d} ({regime}, A={a_kb:>3d}KB): α = {alpha[tm]:.3f}")

    print(f"\n── TM=64 speedup over TM=32 at gc=512 ──")
    sp_m = p2_measured[(32, 512)] / p2_measured[(64, 512)]
    sp_p = _t_predicted(alpha[32], 512, 32) / _t_predicted(alpha[64], 512, 64)
    print(f"  Predicted: {sp_p:.2f}×")
    print(f"  Measured:  {sp_m:.2f}×")

    print(f"\nPlots written to {EXPERIMENT_DIR}")


if __name__ == "__main__":
    run()
