"""B-stationary α calibration (gc=0).

Measures α_calib(TM, TN) = cycles/MNK at gc=0 (pure memory-bound cost,
no generation stalls). Reads from the v55 B-stat cache — all gc=0 entries
are already computed there, so this runs as cache hits only.

Exported: get_alpha_table(base) → {l1: {(tm, tn): alpha}}
Used by multi-param-regression to supply the roofline calibration data.
"""

from pathlib import Path
from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent
V55_CACHE = (EXPERIMENT_DIR.parent
             / "b-stationry-vs-c-stationary"
             / "results.json")

M, N, K = 192, 256, 256
TK       = K
MNK      = M * N * K
A_P = B_P = 4
LINE      = 64

L1_SIZES = [16_384, 32_768, 65_536]
TM_SWEEP = [4, 8, 16, 24, 32, 48, 64, 96]
TN_SWEEP = [4, 8, 16, 32, 64]
FIFO_CAP = 16_384

FLAGS = Flags(b_source="prng_fifo", stationary="B",
              three_d_reg=True, mulac_norecord=True, no_l2=True)


def safe(tm: int, tn: int) -> bool:
    return tm * tn // 8 + tm // 4 - 2 < 300


def _run_safe_grid(base: str, over: dict) -> list:
    results = []
    for tn in TN_SWEEP:
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
        if not safe_tms:
            continue
        res = run_grid(experiment_dir=EXPERIMENT_DIR,
                       base_config_text=base,
                       base_overrides={**over, "TILE_N": tn},
                       sweep_axes={"TILE_M": safe_tms},
                       flags=FLAGS,
                       cache_path=V55_CACHE)
        results.extend(res)
    return results


def _base_overrides(l1: int) -> dict:
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
        "PRNG_FIFO_GEN_COST": 0,
    }


def get_alpha_table(base: str) -> dict:
    """Return {l1: {(tm, tn): alpha_calib}} for all L1 sizes."""
    tables = {}
    for l1 in L1_SIZES:
        results = _run_safe_grid(base, _base_overrides(l1))
        tables[l1] = {
            (r.overrides["TILE_M"], r.overrides["TILE_N"]): r.metrics.cycles / MNK
            for r in results
            if safe(r.overrides["TILE_M"], r.overrides["TILE_N"])
            and r.metrics.cycles > 0
        }
    return tables


def _print_table(alpha_map: dict, l1_kb: int) -> None:
    print(f"\n  α_calib(TM, TN) = cycles/MNK   [L1={l1_kb}KB, gc=0, B-stationary]")
    hdr = f"    {'TM\\TN':>6}" + "".join(f"  {tn:>8}" for tn in TN_SWEEP)
    print(hdr)
    print("    " + "─" * (len(hdr) - 4))
    for tm in TM_SWEEP:
        row = f"    {tm:>6}"
        for tn in TN_SWEEP:
            if not safe(tm, tn):
                row += f"  {'—':>8}"
            elif (tm, tn) in alpha_map:
                row += f"  {alpha_map[(tm, tn)]:>8.4f}"
            else:
                row += f"  {'?':>8}"
        print(row)


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    print("=" * 72)
    print("B-stationary α calibration (gc=0)")
    print("=" * 72)
    print(f"M={M}, N=K={N}, TK={TK}, A_P=B_P={A_P}B, FIFO_CAP={FIFO_CAP}")
    print("(reading from v55 B-stat cache — expect all cache hits)")

    tables = get_alpha_table(base)

    for l1, alpha_map in tables.items():
        l1_kb = l1 // 1024
        print(f"\n{'─'*72}")
        print(f"L1={l1_kb}KB")
        print(f"{'─'*72}")
        _print_table(alpha_map, l1_kb)

    print(f"\n{'═'*72}")
    print("Best α per L1  (argmin cycles/MNK at gc=0)")
    print(f"{'═'*72}")
    for l1, alpha_map in tables.items():
        if alpha_map:
            (tm, tn), alpha = min(alpha_map.items(), key=lambda x: x[1])
            print(f"  L1={l1//1024:>5}KB:  TM={tm:>2}, TN={tn:>2}  →  α={alpha:.4f}")


if __name__ == "__main__":
    run()
