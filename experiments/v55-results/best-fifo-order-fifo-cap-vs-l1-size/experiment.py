"""FIFO capacity vs L1 size — fixed SRAM budget split.

For a fixed total SRAM budget (L1 bytes + FIFO bytes), sweeps how the budget
is split between L1 cache and FIFO buffer. At each split, finds the empirical
best (TM, TN) for B-stationary mode and reports performance.

B-stationary is used because at non-zero gc it is the winner from experiments
1–3, and its TM-fold register reuse of B makes the FIFO/L1 tradeoff non-trivial:
more L1 helps A-tile residency, more FIFO helps pre-generation at high gc.

The key question: is there an optimal split, or does one resource always dominate?
"""

from pathlib import Path
from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

M, N, K = 192, 256, 256
TK       = K
MNK      = M * N * K
A_P = B_P = 4
LINE      = 64

# Budgets in bytes; each split: FIFO_bytes = budget - L1_bytes
BUDGETS    = [65_536, 131_072]   # 64 KB, 128 KB
GC_SWEEP   = [10, 100, 250, 280, 300, 310, 325, 350, 500]
TM_SWEEP   = [4, 8, 16, 24, 32, 48, 64, 96]
TN_SWEEP   = [4, 8, 16, 32, 64]
L1_STEP    = 16_384              # 16 KB steps between splits

FLAGS = Flags(b_source="prng_fifo", stationary="B",
              three_d_reg=True, mulac_norecord=True, no_l2=True)


def safe(tm: int, tn: int, fifo_cap: int) -> bool:
    reg_ok  = tm * tn // 8 + tm // 4 - 2 < 300
    fifo_ok = TK * tn <= fifo_cap
    return reg_ok and fifo_ok


def splits_for_budget(budget: int) -> list[tuple[int, int]]:
    """Return (l1_bytes, fifo_cap_elements) pairs for a fixed budget."""
    result = []
    l1 = 8_192
    while True:
        fifo_bytes = budget - l1
        fifo_cap   = fifo_bytes // B_P
        if fifo_cap < TK * min(TN_SWEEP):   # can't fit even smallest B sub-tile
            break
        result.append((l1, fifo_cap))
        l1 += L1_STEP
    return result


def _overrides(l1: int, fifo_cap: int, gc: int) -> dict:
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
        "PRNG_FIFO_CAPACITY": fifo_cap,
        "PRNG_FIFO_GEN_COST": gc,
    }


def run_safe_grid(base: str, over: dict, fifo_cap: int) -> list:
    results = []
    for tn in TN_SWEEP:
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn, fifo_cap)]
        if not safe_tms:
            continue
        res = run_grid(experiment_dir=EXPERIMENT_DIR,
                       base_config_text=base,
                       base_overrides={**over, "TILE_N": tn},
                       sweep_axes={"TILE_M": safe_tms},
                       flags=FLAGS)
        results.extend(res)
    return results


def _grid_to_map(results, fifo_cap: int) -> dict:
    """Return {(tm, tn): cycles} filtering unsafe and zero-cycle entries."""
    return {
        (r.overrides["TILE_M"], r.overrides["TILE_N"]): r.metrics.cycles
        for r in results
        if safe(r.overrides["TILE_M"], r.overrides["TILE_N"], fifo_cap)
        and r.metrics.cycles > 0
    }


def validate_roofline(base: str) -> None:
    """Roofline validation across all (budget, split) combinations.

    For each split:
      1. Calibrate α_calib(TM,TN) at gc=0 (new simulations).
      2. Predict best tile: argmin MNK × max(α_calib, gc/TM).
      3. Load empirical best at gc ∈ {10, 100} (cache hits from main run).
      4. Report exact-match rate and cycle gap when wrong.
    """
    print("\n" + "=" * 72)
    print("Roofline validation — varying FIFO cap × L1 budget split")
    print("Model: predicted = argmin_{TM,TN} MNK × max(α_calib(TM,TN), gc/TM)")
    print("       α_calib measured at gc=0 per (L1, FIFO_CAP) split")
    print("=" * 72)

    grand_total = 0
    grand_exact = 0
    grand_gaps: list[float] = []

    for budget in BUDGETS:
        budget_kb = budget // 1024
        splits    = splits_for_budget(budget)

        print(f"\n{'═'*72}")
        print(f"Budget = {budget_kb}KB  ({len(splits)} splits × {len(GC_SWEEP)} gc values"
              f" = {len(splits)*len(GC_SWEEP)} conditions)")
        print(f"{'═'*72}")
        print(f"  {'condition':>32}  {'pred (TM,TN)':>14}  {'emp (TM,TN)':>12}"
              f"  {'✓':>4}  {'gap':>7}")
        print("  " + "─" * 74)

        b_total = 0
        b_exact = 0
        b_gaps:  list[float] = []

        for l1, fifo_cap in splits:
            l1_kb = l1 // 1024

            # --- calibrate at gc=0 (new sims) ---
            cal_results = run_safe_grid(base, _overrides(l1, fifo_cap, 0), fifo_cap)
            alpha = {k: v / MNK for k, v in _grid_to_map(cal_results, fifo_cap).items()}
            if not alpha:
                continue

            for gc in GC_SWEEP:
                # --- roofline prediction ---
                pred_map = {k: MNK * max(a, gc / k[0]) for k, a in alpha.items()}
                (tm_p, tn_p), _ = min(pred_map.items(), key=lambda x: x[1])

                # --- empirical best (cache hit) ---
                emp_results = run_safe_grid(base, _overrides(l1, fifo_cap, gc), fifo_cap)
                emp_map     = _grid_to_map(emp_results, fifo_cap)
                if not emp_map:
                    continue
                (tm_e, tn_e), cy_e = min(emp_map.items(), key=lambda x: x[1])

                cy_at_pred = emp_map.get((tm_p, tn_p))
                if cy_at_pred is not None:
                    gap_pct = (cy_at_pred / cy_e - 1) * 100
                else:
                    gap_pct = float("nan")

                match = (tm_p == tm_e and tn_p == tn_e)
                b_total += 1
                if match:
                    b_exact += 1
                if not match and gap_pct == gap_pct:  # not NaN
                    b_gaps.append(gap_pct)

                match_str = "✓" if match else "✗"
                gap_str   = f"{gap_pct:+.2f}%" if gap_pct == gap_pct else "n/a"
                cond = f"L1={l1_kb:>3}KB FIFO={fifo_cap:>6} gc={gc:>3}"
                print(f"  {cond:>32}  ({tm_p:>2},{tn_p:>2})            "
                      f"({tm_e:>2},{tn_e:>2})    {match_str:>4}  {gap_str:>7}")

                # show bottleneck for the predicted pair
                a_pred = alpha.get((tm_p, tn_p), float("nan"))
                gen    = gc / tm_p
                neck   = "mem-bound" if a_pred >= gen else "gen-bound"
                print(f"    α_calib={a_pred:.4f}  gc/TM={gen:.4f}  → {neck}")

        pct = 100 * b_exact / b_total if b_total else 0
        print(f"\n  Budget {budget_kb}KB — exact match: {b_exact}/{b_total} ({pct:.0f}%)")
        if b_gaps:
            med = sorted(b_gaps)[len(b_gaps) // 2]
            print(f"    When wrong: median gap {med:+.2f}%,  worst {max(b_gaps):+.2f}%")

        grand_total += b_total
        grand_exact += b_exact
        grand_gaps.extend(b_gaps)

    print(f"\n{'═'*72}")
    pct = 100 * grand_exact / grand_total if grand_total else 0
    print(f"Overall exact match: {grand_exact}/{grand_total} ({pct:.0f}%)")
    if grand_gaps:
        med = sorted(grand_gaps)[len(grand_gaps) // 2]
        print(f"When wrong: median gap {med:+.2f}%,  worst {max(grand_gaps):+.2f}%")
    else:
        print("When wrong: — (no wrong predictions)")
    print("=" * 72)


def find_best(results, fifo_cap: int) -> tuple[int, int, int]:
    valid = [r for r in results
             if safe(r.overrides["TILE_M"], r.overrides["TILE_N"], fifo_cap)
             and r.metrics.cycles > 0]
    if not valid:
        return 0, 0, 0
    r = min(valid, key=lambda x: x.metrics.cycles)
    return r.overrides["TILE_M"], r.overrides["TILE_N"], r.metrics.cycles


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    print("=" * 72)
    print("B-stationary: FIFO capacity vs L1 size (fixed SRAM budget)")
    print("=" * 72)
    print(f"M={M}, N=K={N}, TK={TK}, A_P=B_P={A_P}B, LINE={LINE}B")
    print(f"Budgets: {[b//1024 for b in BUDGETS]} KB")
    print(f"gc sweep: {GC_SWEEP}")

    for budget in BUDGETS:
        budget_kb = budget // 1024
        splits = splits_for_budget(budget)

        print(f"\n{'═'*72}")
        print(f"Total SRAM budget = {budget_kb}KB")
        print(f"{'═'*72}")
        print(f"  Splits: L1 ∈ "
              f"{[s[0]//1024 for s in splits]}KB, "
              f"FIFO ∈ {[s[1] for s in splits]} elems")

        # summary[gc][split_idx] = (l1, fifo_cap, tm, tn, cycles)
        summary: dict = {}

        for gc in GC_SWEEP:
            summary[gc] = []
            print(f"\n{'─'*72}")
            print(f"gc={gc} cy/elem")
            print(f"{'─'*72}")

            for l1, fifo_cap in splits:
                l1_kb  = l1 // 1024
                max_tn = fifo_cap // TK
                print(f"\n  L1={l1_kb}KB, FIFO={fifo_cap} elems (max TN={max_tn})")
                results = run_safe_grid(base, _overrides(l1, fifo_cap, gc), fifo_cap)
                tm, tn, cy = find_best(results, fifo_cap)
                alpha = cy / MNK if cy else float("nan")
                print(f"  Best: TM={tm}, TN={tn}  →  {cy:,} cycles  (α={alpha:.4f})")
                summary[gc].append((l1, fifo_cap, tm, tn, cy))

        # Summary table for this budget
        print(f"\n{'─'*72}")
        print(f"Summary: best cycles at each split  (budget={budget_kb}KB)")
        print(f"{'─'*72}")
        col = 22
        print(f"  {'L1':>6}  {'FIFO':>8}", end="")
        for gc in GC_SWEEP:
            print(f"  {'gc='+str(gc):>{col}}", end="")
        print()
        print("  " + "─" * (16 + len(GC_SWEEP) * (col + 2)))

        for i, (l1, fifo_cap) in enumerate(splits):
            print(f"  {l1//1024:>5}KB  {fifo_cap:>8}", end="")
            for gc in GC_SWEEP:
                _, _, tm, tn, cy = summary[gc][i]
                if cy:
                    cell = f"{cy//1000}K cy TM={tm},TN={tn}"
                else:
                    cell = "—"
                print(f"  {cell:>{col}}", end="")
            print()

        # Per-gc: show relative performance vs best split
        print()
        for gc in GC_SWEEP:
            entries = [(cy, l1, tm, tn) for l1, _, tm, tn, cy in summary[gc] if cy]
            if not entries:
                continue
            best_cy, best_l1, best_tm, best_tn = min(entries)
            print(f"  gc={gc}: best split L1={best_l1//1024}KB "
                  f"(TM={best_tm},TN={best_tn})  →  {best_cy:,} cycles")
            for cy, l1, tm, tn in sorted(entries, key=lambda x: x[1]):
                pct = (cy / best_cy - 1) * 100
                bar = "+" if pct > 0 else ""
                print(f"    L1={l1//1024:>5}KB  {cy:>12,}  ({bar}{pct:+.1f}%)")

    validate_roofline(base)


if __name__ == "__main__":
    run()
