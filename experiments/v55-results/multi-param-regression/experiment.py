"""Roofline model validation.

For each mode (B-stat, C-stat col-maj), at each (gc, L1):
  1. Load α_calib(TM, TN) measured at gc=0 (pure memory-bound cost).
  2. Apply roofline:
       predicted_cycles(TM, TN) = MNK × max(α_calib(TM, TN),  gc / TM)
     The gc/TM term is the generation-bound cost: each B sub-tile (TK×TN elements)
     is reused across TM A-rows, so the effective FIFO cost per output element
     is gc × (1/TM).
  3. Find (TM*, TN*)_pred  = argmin over (TM, TN) of predicted_cycles.
  4. Load actual cycles from the v55 caches at gc ∈ {10, 100}.
  5. Find (TM*, TN*)_emp   = argmin over (TM, TN) of actual_cycles.
  6. Report exact match rate and cycle gap when the prediction is wrong.

The cycle gap is the practically important metric: picking a pair 1% slower
than optimal is fine; 15% slower is not.

Note on C-stat: the gc/TM formula assumes TM-fold reuse per FIFO element, which
holds when each B element is used by TM A-rows before the next is fetched. In
C-stat col-major the device restarts M_reg times per output tile, so effective
reuse per FIFO read is reg_m (< TM). The roofline will underestimate C-stat's
generation cost; residuals show the correction needed.
"""

from pathlib import Path
from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent
V55_B_CACHE    = EXPERIMENT_DIR.parent / "b-stationry-vs-c-stationary"    / "results.json"
V55_C_CACHE    = EXPERIMENT_DIR.parent / "b-stationary-vs-c-stationry-col-major" / "results.json"

M, N, K = 192, 256, 256
TK       = K
MNK      = M * N * K
A_P = B_P = 4
LINE      = 64

L1_SIZES   = [16_384, 32_768, 65_536]
TM_SWEEP   = [4, 8, 16, 24, 32, 48, 64, 96]
TN_SWEEP   = [4, 8, 16, 32, 64]
GC_SWEEP   = [10, 100]
FIFO_CAP   = 16_384

FLAGS_B = Flags(b_source="prng_fifo", stationary="B",
                three_d_reg=True, mulac_norecord=True, no_l2=True)
FLAGS_C = Flags(b_source="prng_fifo", stationary="output",
                three_d_reg=True, mulac_norecord=True, no_l2=True,
                col_major_fifo=True)


def safe(tm: int, tn: int) -> bool:
    return tm * tn // 8 + tm // 4 - 2 < 300


def _base_overrides(l1: int, gc: int) -> dict:
    return {
        "A_HEIGHT_DIM":       M,
        "A_WIDTH_DIM":        K,
        "B_WIDTH_DIM":        N,
        "A_PRECISION_BYTES":  A_P,
        "B_PRECISION_BYTES":  B_P,
        "L1_SIZE_BYTES":      l1,
        "L1_LINE_SIZE_BYTES": LINE,
        "L1_ASSOC":           l1 // LINE,
        "TILE_K":             TK,
        "PRNG_FIFO_CAPACITY": FIFO_CAP,
        "PRNG_FIFO_GEN_COST": gc,
    }


def _load_grid(base: str, l1: int, gc: int, flags: Flags, cache: Path) -> dict:
    """Return {(tm, tn): cycles} from v55 cache (all cache hits)."""
    results = []
    for tn in TN_SWEEP:
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
        if not safe_tms:
            continue
        res = run_grid(experiment_dir=EXPERIMENT_DIR,
                       base_config_text=base,
                       base_overrides={**_base_overrides(l1, gc), "TILE_N": tn},
                       sweep_axes={"TILE_M": safe_tms},
                       flags=flags,
                       cache_path=cache)
        results.extend(res)
    return {
        (r.overrides["TILE_M"], r.overrides["TILE_N"]): r.metrics.cycles
        for r in results
        if safe(r.overrides["TILE_M"], r.overrides["TILE_N"])
        and r.metrics.cycles > 0
    }


def _validate(label: str, flags: Flags, cache: Path, base: str) -> None:
    print(f"\n{'═'*72}")
    print(f"Roofline validation — {label}")
    print(f"{'═'*72}")
    print("  predicted best = argmin_{TM,TN} MNK × max(α_calib, gc/TM)")
    print()

    # Load gc=0 calibration (alpha table)
    alpha_tables: dict = {}
    for l1 in L1_SIZES:
        cyc_map = _load_grid(base, l1, 0, flags, cache)
        alpha_tables[l1] = {k: v / MNK for k, v in cyc_map.items()}

    total_conditions = 0
    exact_matches    = 0
    gap_pcts: list[float] = []

    print(f"  {'condition':>26}  {'pred (TM,TN)':>14}  {'emp (TM,TN)':>12}  "
          f"{'match':>5}  {'gap %':>7}")
    print("  " + "─" * 76)

    for gc in GC_SWEEP:
        for l1 in L1_SIZES:
            alpha = alpha_tables[l1]
            if not alpha:
                continue

            # Predicted best via roofline
            pred_map = {
                (tm, tn): MNK * max(a, gc / tm)
                for (tm, tn), a in alpha.items()
            }
            # tiebreak by alpha: when gc/TM dominates for multiple TN values,
            # prefer lower alpha (= larger TN) to minimize residual A-load cost
            (tm_p, tn_p), _ = min(pred_map.items(), key=lambda x: (x[1], alpha[x[0]]))

            # Empirical best from v55 cache
            emp_map = _load_grid(base, l1, gc, flags, cache)
            if not emp_map:
                continue
            (tm_e, tn_e), cy_e = min(emp_map.items(), key=lambda x: x[1])

            # Cycle gap: how much worse is the predicted pair vs true best?
            cy_at_pred = emp_map.get((tm_p, tn_p), None)
            if cy_at_pred is None:
                gap_pct = float("nan")
            else:
                gap_pct = (cy_at_pred / cy_e - 1) * 100

            match = (tm_p == tm_e and tn_p == tn_e)
            total_conditions += 1
            if match:
                exact_matches += 1
            if not match and not (gap_pct != gap_pct):  # skip NaN
                gap_pcts.append(gap_pct)

            match_str = "✓" if match else "✗"
            gap_str   = f"{gap_pct:+.1f}%" if not (gap_pct != gap_pct) else "n/a"
            cond      = f"gc={gc:>3}, L1={l1//1024:>2}KB"
            print(f"  {cond:>26}  "
                  f"({tm_p:>2},{tn_p:>2})          "
                  f"({tm_e:>2},{tn_e:>2})      "
                  f"{match_str:>5}  {gap_str:>7}")

            # Print alpha and roofline values for the predicted pair
            alpha_at_pred = alpha.get((tm_p, tn_p), float("nan"))
            gen_cost      = gc / tm_p if tm_p else float("nan")
            bottleneck    = "compute/mem" if alpha_at_pred >= gen_cost else "gen-bound"
            print(f"    α_calib={alpha_at_pred:.4f}  gc/TM={gen_cost:.4f}  "
                  f"→ {bottleneck}")

    print()
    print(f"  Exact match rate : {exact_matches}/{total_conditions} "
          f"({100*exact_matches/total_conditions:.0f}%)")
    if gap_pcts:
        median_gap = sorted(gap_pcts)[len(gap_pcts)//2]
        max_gap    = max(gap_pcts)
        print(f"  When wrong       : median gap {median_gap:+.1f}%,  "
              f"worst {max_gap:+.1f}%")
    else:
        print("  When wrong       : — (no wrong predictions)")


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    print("=" * 72)
    print("Roofline model validation")
    print("=" * 72)
    print(f"M={M}, N=K={N}, TK={TK}, A_P=B_P={A_P}B, FIFO_CAP={FIFO_CAP}")
    print("Model: predicted_cycles = MNK × max(α_calib(TM,TN),  gc/TM)")
    print("Data:  α_calib from gc=0; validation at gc ∈ {10, 100}")
    print("(reading from v55 caches — expect all cache hits)")

    _validate("B-stationary", FLAGS_B, V55_B_CACHE, base)
    _validate("C-stat col-major", FLAGS_C, V55_C_CACHE, base)


if __name__ == "__main__":
    run()
