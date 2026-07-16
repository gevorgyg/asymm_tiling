"""E14-nol2: Pipelined FIFO-B vs Memory-B in L1-only hierarchy.

E13-nol2 showed that non-pipelined FIFO-B (--Bsource prng_fifo) beats
Memory-B at TN=32 up to gc ≈ 200.  The crossover is set by the stall-free
condition for the standard FIFO:

  gc ≤ α(TM, TN) × TM   (non-pipelined: 1 tile of overlap)

Pipelined FIFO (--Bsource prng_fifo_pipelined) with N=PRNG_FIFO_NUM_PREFILL
buffers pre-generates N tiles ahead in parallel, extending the stall-free
condition N-fold:

  gc ≤ N × α(TM, TN) × TM   (N-buffer pipelined FIFO)

At TM=64, TN=32: α≈3.49, so:
  N=1 → stall-free for gc ≤ 223
  N=2 → stall-free for gc ≤ 447
  N=4 → stall-free for gc ≤ 893

Memory-B at TN=32 has α_mem=3.754 (crossover gc*≈200 for non-pipelined).
Pipelined FIFO should beat Memory-B up to gc ≈ N × 200.

Data sources:
  Memory-B   — E13-nol2 results.json (loaded; no new mem runs)
  FIFO std   — E8-nol2  results.json (non-pipelined; gc≤400)
  FIFO pipe  — this experiment; gc ∈ GC_SWEEP, NUM_PREFILL ∈ PREFILL_SWEEP
"""

from pathlib import Path
import json

from experiments.harness import Flags, run_grid, workspace_root

EXPERIMENT_DIR = Path(__file__).resolve().parent

# ── Hardware constants ────────────────────────────────────────────────────────
A_P  = C_P = 4
LINE = 64
L1   = 16_384
L1_LAT  = 4
MEM_LAT = 180
REG_M = REG_N = REG_K = 4
M = 192
N = K = 256
TK = K

MNK = M * N * K

FLAGS_PIPE = Flags(b_source="prng_fifo_pipelined", stationary="B",
                   three_d_reg=True, mulac_norecord=True, no_l2=True)

_BASE: dict[str, object] = {
    "A_HEIGHT_DIM":       M,
    "A_WIDTH_DIM":        K,
    "B_WIDTH_DIM":        N,
    "A_PRECISION_BYTES":  A_P,
    "B_PRECISION_BYTES":  A_P,
    "L1_SIZE_BYTES":      L1,
    "L1_LINE_SIZE_BYTES": LINE,
    "L1_ASSOC":           L1 // LINE,
    "TILE_K":             TK,
    # capacity ≥ TK×TN per slot; 2×TK×32=16384 covers all TN≤64
    "PRNG_FIFO_CAPACITY": 2 * TK * 32,
}

TM_SWEEP     = [8, 12, 16, 24, 32, 48, 64, 96]
TN_SWEEP     = [4, 8, 16, 32, 64]
# gc sweep chosen to bracket crossovers for all N and TN combinations:
#   TN=64 N=1: ~107  TN=32 N=1: ~223  TN=16 N=1: ~368
#   TN=64 N=2: ~214  TN=32 N=2: ~447  TN=16 N=2: ~736
#   TN=64 N=4: ~428  TN=32 N=4: ~893  TN=16 N=4: >1400
GC_SWEEP     = [150, 250, 400, 700, 1200, 2000]
PREFILL_SWEEP = [1, 2, 4]

E8_RESULTS  = EXPERIMENT_DIR.parent / "e8-gc-boundary-sweep"  / "results.json"
E13_RESULTS = EXPERIMENT_DIR.parent / "e13-fifo-vs-mem"       / "results.json"


def ws_lines(tm: int, tn: int) -> int:
    return tm * tn // 8 + tm // 4 - 2


def safe(tm: int, tn: int) -> bool:
    return ws_lines(tm, tn) < 300


def load_mem_results() -> dict[int, dict[int, float]]:
    """Load Memory-B α from E13-nol2.  Returns mem_t[tn][tm] = T/MNK."""
    with open(E13_RESULTS) as f:
        cache = json.load(f)
    mem_t: dict[int, dict[int, float]] = {}
    for entry in cache.values():
        ov  = entry["overrides"]
        tm  = ov["TILE_M"]
        tn  = ov["TILE_N"]
        t   = entry["metrics"]["cycles"] / MNK
        mem_t.setdefault(tn, {})[tm] = t
    return mem_t


def load_e8_fifo() -> tuple[list[int], dict[int, dict[int, dict[int, float]]]]:
    """Load non-pipelined FIFO T/MNK from E8-nol2.
    Returns (gc_list, fifo_t) where fifo_t[gc][tn][tm] = T/MNK."""
    with open(E8_RESULTS) as f:
        cache = json.load(f)
    fifo_t: dict[int, dict[int, dict[int, float]]] = {}
    for entry in cache.values():
        ov = entry["overrides"]
        tm = ov["TILE_M"]
        tn = ov["TILE_N"]
        gc = ov["PRNG_FIFO_GEN_COST"]
        t  = entry["metrics"]["cycles"] / MNK
        fifo_t.setdefault(gc, {}).setdefault(tn, {})[tm] = t
    return sorted(fifo_t), fifo_t


def best_safe(t_map: dict[int, float], tn: int) -> tuple[int, float]:
    """Return (TM*, T*) minimizing T over safe TM values."""
    safe_tms = [tm for tm in TM_SWEEP if safe(tm, tn)]
    tm_star  = min(safe_tms, key=lambda tm: t_map.get(tm, float("inf")))
    return tm_star, t_map[tm_star]


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    # ── Load cached baselines ─────────────────────────────────────────────────
    print("Loading Memory-B results from E13-nol2 …")
    mem_t = load_mem_results()

    print("Loading non-pipelined FIFO results from E8-nol2 …")
    e8_gc_list, e8_fifo_t = load_e8_fifo()

    # ── Run pipelined FIFO sweep ──────────────────────────────────────────────
    # pipe_t[num_prefill][gc][tn][tm] = T/MNK
    pipe_t: dict[int, dict[int, dict[int, dict[int, float]]]] = {}

    for num_prefill in PREFILL_SWEEP:
        pipe_t[num_prefill] = {}
        for gc in GC_SWEEP:
            print(f"  pipelined N={num_prefill}, gc={gc} …")
            grid = run_grid(
                experiment_dir=EXPERIMENT_DIR,
                base_config_text=base,
                base_overrides={**_BASE,
                                "PRNG_FIFO_GEN_COST":   gc,
                                "PRNG_FIFO_NUM_PREFILL": num_prefill},
                sweep_axes={"TILE_M": TM_SWEEP, "TILE_N": TN_SWEEP},
                flags=FLAGS_PIPE,
            )
            gc_entry: dict[int, dict[int, float]] = {}
            for r in grid:
                tm = r.overrides["TILE_M"]
                tn = r.overrides["TILE_N"]
                t  = r.metrics.cycles / MNK
                gc_entry.setdefault(tn, {})[tm] = t
            pipe_t[num_prefill][gc] = gc_entry

    # ── Table 1: pipelined FIFO α at each (N, gc, TN) — TM* only ────────────
    print(f"\n{'═'*72}")
    print("Pipelined FIFO T/MNK at TM* (best safe tile) per (N, TN, gc)")
    print(f"{'═'*72}")

    for tn in TN_SWEEP:
        print(f"\n  TN={tn}   Memory-B TM*: ", end="")
        tm_m, t_m = best_safe(mem_t.get(tn, {}), tn)
        print(f"TM={tm_m}, α_mem={t_m:.4f}")
        print(f"  {'gc':>6}  {'N=std':>8}", end="")
        for np_ in PREFILL_SWEEP:
            print(f"  {'N='+str(np_):>8}", end="")
        print(f"  {'mem':>8}  {'N=std':>7}  {'N=1':>7}  {'N=2':>7}  {'N=4':>7}")
        print("  " + "─" * (6 + 10 + 10 * len(PREFILL_SWEEP) + 10 + 36))

        all_gc = sorted(set(GC_SWEEP) | {g for g in e8_gc_list
                                          if g in {100, 150, 250, 400}})

        for gc in all_gc:
            # Non-pipelined (E8)
            e8_tn = e8_fifo_t.get(gc, {}).get(tn, {})
            if e8_tn:
                _, t_std = best_safe(e8_tn, tn)
                std_str = f"{t_std:.4f}"
                w_std   = "F" if t_std < t_m else "."
            else:
                std_str = "      —"
                w_std   = "?"

            cols = [f"  {std_str:>8}"]
            winners = [w_std]
            for np_ in PREFILL_SWEEP:
                gc_data = pipe_t[np_].get(gc, {}).get(tn, {})
                if gc_data:
                    _, t_p = best_safe(gc_data, tn)
                    cols.append(f"  {t_p:.4f}")
                    winners.append("F" if t_p < t_m else ".")
                else:
                    cols.append(f"  {'—':>8}")
                    winners.append("?")

            win_str = "  " + "".join(winners)
            print(f"  {gc:>6}{''.join(cols)}  {t_m:.4f}{win_str}")

        print(f"    (F = FIFO wins, . = mem wins)")

    # ── Table 2: crossover gc* per (TN, N) ───────────────────────────────────
    print(f"\n{'═'*72}")
    print("Crossover gc* per (TN, num_prefill)")
    print("(first gc where pipelined FIFO loses to Memory-B at TM*)")
    print(f"{'═'*72}")
    print(f"  {'TN':>4}  {'std':>14}", end="")
    for np_ in PREFILL_SWEEP:
        print(f"  {'N='+str(np_):>14}", end="")
    print()
    print("  " + "─" * (4 + 16 + 16 * len(PREFILL_SWEEP)))

    for tn in TN_SWEEP:
        tm_m, t_m = best_safe(mem_t.get(tn, {}), tn)

        # Non-pipelined crossover from E8 data
        std_cross = "—"
        prev_g    = None
        for gc in sorted(e8_gc_list):
            e8_tn = e8_fifo_t.get(gc, {}).get(tn, {})
            if e8_tn:
                _, t_s = best_safe(e8_tn, tn)
                if t_s >= t_m:
                    lo = prev_g if prev_g is not None else "?"
                    std_cross = f"({lo}, {gc}]"
                    break
                prev_g = gc
        if std_cross == "—":
            std_cross = f"> {sorted(e8_gc_list)[-1]}"

        print(f"  {tn:>4}  {std_cross:>14}", end="")

        for np_ in PREFILL_SWEEP:
            cross = "—"
            prev_g = None
            # Combine E8 gc≤400 (as non-pipelined baseline to compare shape)
            # and pipelined gc values
            for gc in sorted(GC_SWEEP):
                gc_data = pipe_t[np_].get(gc, {}).get(tn, {})
                if not gc_data:
                    continue
                _, t_p = best_safe(gc_data, tn)
                if t_p >= t_m:
                    lo = prev_g if prev_g is not None else "?"
                    cross = f"({lo}, {gc}]"
                    break
                prev_g = gc
            if cross == "—":
                cross = f"> {GC_SWEEP[-1]}"
            print(f"  {cross:>14}", end="")
        print()

    # ── Table 3: stall-free threshold prediction ──────────────────────────────
    print(f"\n{'═'*72}")
    print("Predicted stall-free gc* threshold: N × TM* × α(TM*, TN)")
    print("(uses pipelined TM* at gc=150 as proxy for α)")
    print(f"{'═'*72}")
    print(f"  {'TN':>4}  {'TM*':>4}  {'α_FIFO':>8}", end="")
    for np_ in PREFILL_SWEEP:
        print(f"  {'N='+str(np_)+' thresh':>12}", end="")
    print()
    print("  " + "─" * (4 + 4 + 8 + 12 * len(PREFILL_SWEEP) + 6))

    for tn in TN_SWEEP:
        # Use N=1, gc=150 (should be stall-free) to get α proxy
        gc_150 = pipe_t[1].get(150, {}).get(tn, {})
        if gc_150:
            tm_star, alpha = best_safe(gc_150, tn)
            print(f"  {tn:>4}  {tm_star:>4}  {alpha:.4f}", end="")
            for np_ in PREFILL_SWEEP:
                thresh = np_ * tm_star * alpha
                print(f"  {thresh:>12.0f}", end="")
            print()
        else:
            print(f"  {tn:>4}  —")


if __name__ == "__main__":
    run()
