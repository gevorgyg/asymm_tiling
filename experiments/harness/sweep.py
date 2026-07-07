"""Grid sweeps with on-disk caching.

run_grid takes a Cartesian product of overrides, runs ./asymm for each cell,
and caches results in `<experiment_dir>/results.json` keyed by the effective
config text + CLI flags. Reruns skip cells already cached.
"""

import hashlib
import itertools
import json
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from . import config as config_mod
from . import parse, runner


# Mirrors main.cpp's unusedConfigKeys(): keys whose values do not influence
# the simulation under a given flag combination. Stripping them before hashing
# means the cache survives edits to truly-irrelevant config lines.
def _unused_keys(flags: runner.Flags) -> set[str]:
    u: set[str] = set()
    if flags.b_source != "prng_mem":
        u.update({"PRNG_ACCESS_CYCLES", "PRNG_GEN_COST_PER_LINE"})
    if flags.b_source != "prng_fifo":
        u.update({"PRNG_FIFO_CAPACITY", "PRNG_FIFO_GEN_COST"})
    if not flags.three_d_reg:
        u.update({"REG_M", "REG_N", "REG_K"})
    if flags.mulac_norecord:
        u.add("MULAC_CYCLES")
    return u


def _canonical_config(text: str, flags: runner.Flags) -> str:
    """Sort + filter `KEY=value` lines so cosmetic edits don't bust the cache."""
    unused = _unused_keys(flags)
    kvs: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key in unused:
            continue
        kvs.append(s)
    return "\n".join(sorted(kvs))


def _cache_key(config_text: str, flags: runner.Flags) -> str:
    canonical = _canonical_config(config_text, flags)
    flag_blob = json.dumps(flags.to_dict(), sort_keys=True)
    h = hashlib.sha256()
    h.update(canonical.encode())
    h.update(b"\n--FLAGS--\n")
    h.update(flag_blob.encode())
    return h.hexdigest()


@dataclass
class Result:
    overrides: dict
    metrics: parse.Metrics


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Corrupt cache: start fresh; the caller will fully rebuild.
        return {}


def _save_cache(path: Path, cache: dict) -> None:
    path.write_text(json.dumps(cache, indent=2))


def run_grid(
    *,
    experiment_dir: Path,
    base_config_text: str,
    base_overrides: Mapping[str, object] = {},
    sweep_axes: Mapping[str, Sequence[object]] = {},
    flags: runner.Flags = runner.Flags(),
    cache_path: Path | None = None,
    progress: bool = True,
) -> list[Result]:
    """Run one simulation per Cartesian-product cell of `sweep_axes`.

    base_overrides applies to every cell. sweep_axes is the cell-varying
    part: dict[KEY -> list of values]. Results are cached at
    `experiment_dir/results.json` unless `cache_path` is given.
    """
    cache_path = cache_path or (experiment_dir / "results.json")
    cache = _load_cache(cache_path)

    axis_keys = list(sweep_axes.keys())
    axis_values = list(sweep_axes.values())
    combos = list(itertools.product(*axis_values)) if axis_keys else [()]

    results: list[Result] = []
    misses = 0
    for idx, combo in enumerate(combos, 1):
        overrides = {**base_overrides, **dict(zip(axis_keys, combo))}
        config_text = config_mod.render_config(base_config_text, overrides)
        key = _cache_key(config_text, flags)

        if key in cache:
            metrics = parse.Metrics.from_dict(cache[key]["metrics"])
            if progress:
                print(f"  [{idx}/{len(combos)}] cache hit  {dict(zip(axis_keys, combo))}")
        else:
            misses += 1
            if progress:
                print(f"  [{idx}/{len(combos)}] running    {dict(zip(axis_keys, combo))}")
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".conf", delete=False
            ) as f:
                f.write(config_text)
                tmp_path = Path(f.name)
            try:
                metrics = runner.run(tmp_path, flags=flags)
            finally:
                tmp_path.unlink(missing_ok=True)
            cache[key] = {
                "overrides": overrides,
                "flags": flags.to_dict(),
                "metrics": metrics.to_dict(),
            }
            _save_cache(cache_path, cache)

        results.append(Result(overrides=dict(overrides), metrics=metrics))

    if progress:
        print(f"  done: {len(combos) - misses} cached, {misses} ran")
    return results


@dataclass
class DualResult:
    overrides: dict
    traffic: parse.Metrics   # --mulac_norecord run: feeds all traffic views
    cycles: parse.Metrics    # mulacc-recorded run: feeds the cycles view


def run_grid_dual(
    *,
    experiment_dir: Path,
    base_config_text: str,
    base_overrides: Mapping[str, object] = {},
    sweep_axes: Mapping[str, Sequence[object]] = {},
    flags: runner.Flags = runner.Flags(),
    cache_path: Path | None = None,
    progress: bool = True,
) -> list[DualResult]:
    """run_grid twice per cell: once without mulacc, once with (cycles only)."""
    def _go(f: runner.Flags) -> list[Result]:
        return run_grid(
            experiment_dir=experiment_dir,
            base_config_text=base_config_text,
            base_overrides=base_overrides,
            sweep_axes=sweep_axes,
            flags=f,
            cache_path=cache_path,
            progress=progress,
        )

    traffic = _go(replace(flags, mulac_norecord=True))
    cycles = _go(replace(flags, mulac_norecord=False))
    return [
        DualResult(overrides=t.overrides, traffic=t.metrics, cycles=c.metrics)
        for t, c in zip(traffic, cycles)
    ]
