"""Pipelined B-stationary vs pipelined C-stationary col-major FIFO.

For each (L1 size, generation cost): sweep TM×TN for both pipelined modes,
find the empirical best (TM*, TN*), and compare minimum achievable cycles.

B-stat pipelined:      Same as B-stat but the FIFO pre-generates the next
                       B sub-tile in the background (SWAP instead of START).
                       B register reuse slows consumption, giving the device
                       more time to generate ahead.

C-stat col-maj pipe:   Same as col-major but pipelined — SWAP per rti, device
                       generates the next full B tile in the background.
                       No register reuse of B means the device must generate
                       TK×TN elements in the same time the CPU consumes them.

This experiment shows whether pipelining closes the gap between the two
output-stationary and B-stationary approaches, and which mode benefits more.
"""

from pathlib import Path

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Constants ─────────────────────────────────────────────────────────────────
M, N, K = 192, 256, 256
TK       = K
MNK      = M * N * K
A_P = B_P = 4
LINE      = 64

L1_SIZES = [16_384, 32_768, 65_536]
TM_SWEEP = [4, 8, 16, 24, 32, 48, 64, 96]
TN_SWEEP = [4, 8, 16, 32, 64]
GC_SWEEP = [0, 10, 100]
FIFO_CAP = 16_384

FLAGS_B = Flags(b_source="prng_fifo_pipelined", stationary="B",
                three_d_reg=True, mulac_norecord=True, no_l2=True)
FLAGS_C = Flags(b_source="prng_fifo_pipelined", stationary="output",
                three_d_reg=True, mulac_norecord=True, no_l2=True,
                col_major_fifo=True)

LABEL_B = "B-stat pipelined"
LABEL_C = "C-cmaj pipelined"


def safe(tm: int, tn: int) -> bool:
    return tm * tn // 8 + tm // 4 - 2 < 300


def find_best(results) -> tuple[int, int, int]:
    safe_r = [r for r in results
              if safe(r.overrides["TILE_M"], r.overrides["TILE_N"])
              and r.metrics.cycles > 0]
    if not safe_r:
        return 0, 0, 0
    r = min(safe_r, key=lambda x: x.metrics.cycles)
    return r.overrides["TILE_M"], r.overrides["TILE_N"], r.metrics.cycles


def print_grid(results, label: str) -> None:
    cyc_map = {(r.overrides["TILE_M"], r.overrides["TILE_N"]): r.metrics.cycles
               for r in results
               if safe(r.overrides["TILE_M"], r.overrides["TILE_N"])
               and r.metrics.cycles > 0}
    min_cy = min(cyc_map.values()) if cyc_map else 0

    print(f"  {label}")
    hdr = f"    {'TM\\TN':>6}" + "".join(f"  {tn:>8}" for tn in TN_SWEEP)
    print(hdr)
    print("    " + "─" * (len(hdr) - 4))
    for tm in TM_SWEEP:
        row = f"    {tm:>6}"
        for tn in TN_SWEEP:
            if not safe(tm, tn):
                row += f"  {'—':>8}"
            elif (tm, tn) in cyc_map:
                cy = cyc_map[(tm, tn)]
                flag = "*" if cy == min_cy else " "
                row += f"  {cy:>7,}{flag}"
            else:
                row += f"  {'?':>8}"
        print(row)

    tm_s, tn_s, cy_s = find_best(results)
    print(f"    Best: TM={tm_s}, TN={tn_s}  →  {cy_s:,} cycles  (T/MNK={cy_s/MNK:.4f})")
    print()


def run_safe_grid(experiment_dir, base, over, flags):
    """Sweep TM×TN, skipping unsafe pairs by looping over TN with filtered TM."""
    results = []
    for tn in TN_SWEEP:
        safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
        if not safe_tms:
            continue
        res = run_grid(experiment_dir=experiment_dir,
                       base_config_text=base,
                       base_overrides={**over, "TILE_N": tn},
                       sweep_axes={"TILE_M": safe_tms},
                       flags=flags)
        results.extend(res)
    return results


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    print("=" * 72)
    print("Pipelined B-stationary vs pipelined C-stationary col-major FIFO")
    print("Empirical TM×TN sweep — L1 size and generation cost")
    print("=" * 72)
    print(f"M={M}, N=K={N}, TK={TK}, A_P=B_P={A_P}B, LINE={LINE}B, FIFO_CAP={FIFO_CAP}")

    summary: dict = {}

    for gc in GC_SWEEP:
        summary[gc] = {}
        for l1 in L1_SIZES:
            l1_kb = l1 // 1024
            over = {
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

            print(f"\n{'─'*72}")
            print(f"gc={gc} cy/elem   L1={l1_kb}KB")
            print(f"{'─'*72}\n")

            print(f"  Running {LABEL_B}…")
            res_b = run_safe_grid(EXPERIMENT_DIR, base, over, FLAGS_B)

            print(f"  Running {LABEL_C}…")
            res_c = run_safe_grid(EXPERIMENT_DIR, base, over, FLAGS_C)
            print()

            print_grid(res_b, LABEL_B)
            print_grid(res_c, LABEL_C)

            tm_b, tn_b, cy_b = find_best(res_b)
            tm_c, tn_c, cy_c = find_best(res_c)
            summary[gc][l1] = (tm_b, tn_b, cy_b, tm_c, tn_c, cy_c)

            if cy_b and cy_c:
                winner = LABEL_B if cy_b <= cy_c else LABEL_C
                ratio  = max(cy_b, cy_c) / min(cy_b, cy_c)
                print(f"  ▶ Winner: {winner}  ({ratio:.3f}× faster)\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print("SUMMARY — winner and speedup at each (L1, gc)")
    print(f"{'═'*72}")
    col = 24
    print(f"  {'L1':>6}", end="")
    for gc in GC_SWEEP:
        print(f"  {'gc='+str(gc):>{col}}", end="")
    print()
    print("  " + "─" * (8 + len(GC_SWEEP) * (col + 2)))
    for l1 in L1_SIZES:
        l1_kb = l1 // 1024
        print(f"  {l1_kb:>5}KB", end="")
        for gc in GC_SWEEP:
            tm_b, tn_b, cy_b, tm_c, tn_c, cy_c = summary[gc][l1]
            if cy_b and cy_c:
                if cy_b <= cy_c:
                    ratio = cy_c / cy_b
                    cell  = f"B-pipe {ratio:.2f}× TM={tm_b},TN={tn_b}"
                else:
                    ratio = cy_b / cy_c
                    cell  = f"C-pipe {ratio:.2f}× TM={tm_c},TN={tn_c}"
                print(f"  {cell:>{col}}", end="")
            else:
                print(f"  {'—':>{col}}", end="")
        print()


if __name__ == "__main__":
    run()
