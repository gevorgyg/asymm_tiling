"""Load pre-rewrite results.json files and map each cell to rewrite Params.

    cells = load("v5-results/math-model-no-l2/e6-tn-independence")
    for c in cells:
        c.params           # rewrite Params for the same experiment, or None
        c.unsupported      # why it can't be mapped (when params is None)
        c.metrics["l1"]["line_fills"], c.metrics["cycles"], ...

Paths are relative to experiments/pre-rewrite-experiments/.

What maps 1:1: matrix dims, precisions, tiles, L1/L2 geometry, latencies,
FIFO capacity / gen cost / seed size, write-back + write-allocate, LRU,
no_l2 (-> l2_size 0), mulac_norecord (-> mulacc_cost 0).

What differs by construction (so compare traffic, and conclusions for cycles):
  - old charged one cache access per ELEMENT of a register tile, the rewrite
    one per cache line per register row;
  - old FIFO reads cost PRNG_ACCESS_CYCLES per element, rewrite per pop;
  - old writebacks cost cycles, rewrite writebacks are free.

Not mappable (params = None): b_source other than prng_fifo / mem, the
pipelined FIFO, A-stationary (including every pre-3b03ded "C" run with B from
memory, e.g. the E13 memory-B baseline), the row-major C-stationary FIFO (the rewrite's
C-stationary FIFO consumes only the needed B elements, like the old
col_major_fifo variant), TILE_K != K, a way count that is neither a power of
two nor fully associative. Cache sizes that aren't a power of two map to
bytes (the rewrite reads sizes > 30 as bytes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from harness import Params

OLD_ROOT = Path(__file__).resolve().parents[1] / "pre-rewrite-experiments"

# values of the pre-rewrite default.config (commit b949248^) that the
# experiments build on; overrides replace them per cell
OLD_DEFAULTS: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2,
    "TILE_M": 16, "TILE_N": 32, "TILE_K": 16,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4,
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14,
    "MEM_ACCESS_CYCLES": 180,
    "PRNG_ACCESS_CYCLES": 2,
    "PRNG_FIFO_CAPACITY": 64, "PRNG_FIFO_GEN_COST": 10,
    "PRNG_FIFO_SEED_BYTES": 8,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}


class Unsupported(Exception):
    pass


@dataclass
class OldCell:
    overrides: dict
    flags: dict
    metrics: dict
    params: Params | None
    unsupported: str | None


def _log2(value: int, what: str) -> int:
    if value <= 0 or value & (value - 1):
        raise Unsupported(f"{what}={value} is not a power of two")
    return value.bit_length() - 1


def _size(size: int, what: str) -> int:
    """Cache size as the rewrite's config writes it: log2 when it's a power of
    two, bytes (always > 30) otherwise."""
    if size > 0 and not size & (size - 1):
        return _log2(size, what)
    return size


def _assoc(ways: int, size: int, line: int, what: str) -> int:
    """log2 ways, or -1 (fully associative) for a way count that isn't a
    power of two but covers the whole cache."""
    if ways > 0 and not ways & (ways - 1):
        return _log2(ways, what)
    if ways == size // line:
        return -1
    raise Unsupported(f"{what}={ways} ways is not a power of two")


def to_params(overrides: dict, flags: dict) -> Params:
    c = {**OLD_DEFAULTS, **overrides}

    b_source = {"prng_fifo": "fifo", "mem": "memory"}.get(flags.get("b_source"))
    if b_source is None:
        raise Unsupported(f"b_source={flags.get('b_source')}")

    # Before commit 3b03ded (Jul 17, all v5 results) the flag was "C" and it
    # meant B-register-stationary with the FIFO but A-register-stationary
    # with B from memory (see that commit's message). Afterwards "B" / "output".
    stationary = flags.get("stationary")
    if stationary == "C":
        if b_source != "fifo":
            raise Unsupported("A-stationary (pre-3b03ded 'C' with memory B)")
        stationary = "B"

    if stationary == "B":
        orientation = "weight"
    elif stationary == "output":
        orientation = "output"
        if b_source == "fifo" and not flags.get("col_major_fifo"):
            raise Unsupported("row-major C-stationary FIFO (ghost reads)")
    else:
        raise Unsupported(f"stationary={stationary}")

    if not flags.get("three_d_reg"):
        raise Unsupported("three_d_reg off")
    if not (c["REG_M"] == c["REG_N"] == c["REG_K"]):
        raise Unsupported("non-square register tile")
    if c["TILE_K"] != c["A_WIDTH_DIM"]:
        raise Unsupported(f"TILE_K={c['TILE_K']} != K={c['A_WIDTH_DIM']}")
    if c["L1_LINE_SIZE_BYTES"] != c["L2_LINE_SIZE_BYTES"]:
        raise Unsupported("different L1 / L2 line sizes")

    a_p, b_p = c["A_PRECISION_BYTES"], c["B_PRECISION_BYTES"]
    if a_p % b_p:
        raise Unsupported(f"A_P={a_p} not a multiple of B_P={b_p}")

    line = c["L1_LINE_SIZE_BYTES"]
    return Params(
        orientation=orientation, b_source=b_source,
        m=c["A_HEIGHT_DIM"], k=c["A_WIDTH_DIM"], n=c["B_WIDTH_DIM"],
        small_precision=b_p, ratio=a_p // b_p,
        tile_h=c["TILE_M"], tile_w=c["TILE_N"], reg_dim=c["REG_M"],
        mulacc_cost=0 if flags.get("mulac_norecord") else c["MULAC_CYCLES"],
        block_size=_log2(line, "line size"),
        mem_cycles=c["MEM_ACCESS_CYCLES"],
        l1_size=_size(c["L1_SIZE_BYTES"], "L1 size"),
        l1_cycles=c["L1_ACCESS_CYCLES"],
        l1_assoc=_assoc(c["L1_ASSOC"], c["L1_SIZE_BYTES"], line, "L1 assoc"),
        l2_size=0 if flags.get("no_l2") else _size(c["L2_SIZE_BYTES"], "L2 size"),
        l2_cycles=c["L2_ACCESS_CYCLES"],
        l2_assoc=_assoc(c["L2_ASSOC"], c["L2_SIZE_BYTES"], line, "L2 assoc"),
        write_alloc=True, policy="lru",
        fifo_capacity=c["PRNG_FIFO_CAPACITY"],
        gen_cost=c["PRNG_FIFO_GEN_COST"],
        fifo_access=c["PRNG_ACCESS_CYCLES"],
        seed_size=c["PRNG_FIFO_SEED_BYTES"],
    )


def load(experiment: str, default_flags: dict | None = None) -> list[OldCell]:
    """Cells of an old experiment. default_flags fills in for results files
    that don't store flags (some paper-model results)."""
    raw = json.loads((OLD_ROOT / experiment / "results.json").read_text())
    cells = []
    for v in raw.values():
        flags = v.get("flags") or default_flags
        if flags is None:
            raise ValueError(f"{experiment}: cell without flags, pass default_flags")
        try:
            params, why = to_params(v["overrides"], flags), None
        except Unsupported as e:
            params, why = None, str(e)
        cells.append(OldCell(v["overrides"], flags, v["metrics"], params, why))
    return cells
