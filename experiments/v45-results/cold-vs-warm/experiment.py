"""Repeat matmul assembly N times; separate prologue from steady state."""

import json
import subprocess
import tempfile
from pathlib import Path

from experiments.harness import (
    Flags, grid_plot, lineplot, parse_stdout, render_config,
    stacked_bars, summarize_config, workspace_root, write_report,
)

EXPERIMENT_DIR = Path(__file__).resolve().parent

BASE_OVERRIDES: dict[str, object] = {
    "A_HEIGHT_DIM": 96, "A_WIDTH_DIM": 96, "B_WIDTH_DIM": 96,
    "A_PRECISION_BYTES": 8, "B_PRECISION_BYTES": 2,
    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 8,
    "L1_ACCESS_CYCLES": 4, "L1_REPLACEMENT_POLICY": "LRU", "L1_WRITE_POLICY": "WRITE_BACK",
    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64, "L2_ASSOC": 8,
    "L2_ACCESS_CYCLES": 14, "L2_REPLACEMENT_POLICY": "LRU", "L2_WRITE_POLICY": "WRITE_BACK",
    "MEM_ACCESS_CYCLES": 180,
    "TILE_K": 96,
    "REG_M": 4, "REG_N": 4, "REG_K": 4,
    "MULAC_CYCLES": 8,
}

TILES = [(16, 16), (8, 32), (48, 12), (96, 96)]
REPEATS = [1, 2, 4, 8, 16]


def _generate_assembly(config_text: str) -> Path:
    """Run ./asymm once with the given config to emit ./matmul.matv, then copy it out."""
    workspace = workspace_root()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(config_text)
        cfg_path = Path(f.name)
    try:
        # Just run with the config; the generator writes ./matmul.matv as a side effect
        subprocess.run(
            [str(workspace / "asymm"), "--config", str(cfg_path),
             "--Bsource", "mem", "--stationary", "C", "--3dregisters",
             "--trace_level", "0"],
            cwd=str(workspace), capture_output=True, check=True,
        )
    finally:
        cfg_path.unlink(missing_ok=True)

    matv = workspace / "matmul.matv"
    out = Path(tempfile.mkstemp(suffix=".matv")[1])
    out.write_bytes(matv.read_bytes())
    return out


def _concat_n(asm_path: Path, n: int) -> Path:
    body = asm_path.read_text()
    out = Path(tempfile.mkstemp(suffix=f"_x{n}.matv")[1])
    out.write_text(body * n)
    return out


def _run_with_assembly(config_text: str, asm_path: Path) -> "Metrics":
    workspace = workspace_root()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(config_text)
        cfg_path = Path(f.name)
    try:
        res = subprocess.run(
            [str(workspace / "asymm"), "--config", str(cfg_path),
             "--Bsource", "mem", "--stationary", "C", "--3dregisters",
             "--assembler_input", str(asm_path), "--trace_level", "0"],
            cwd=str(workspace), capture_output=True, text=True, check=True,
        )
    finally:
        cfg_path.unlink(missing_ok=True)
    return parse_stdout(res.stdout)


def _plot_curves(records: list[dict], out: Path) -> None:
    by_tile: dict[str, list] = {}
    for r in records:
        by_tile.setdefault(f"{r['tile_m']}x{r['tile_n']}", []).append(r)
    series = {}
    for label, rows in by_tile.items():
        rows.sort(key=lambda r: r["n"])
        series[label] = [(r["n"], r["l1_hit_rate"]) for r in rows]
    lineplot(
        series, out_path=out,
        xlabel="repeats N", ylabel="L1 hit rate (pooled)",
        title=("Cold vs warm: pooled hit rate vs repeat count\n"
               + summarize_config(BASE_OVERRIDES)),
    )


def _plot_bars(steady_records: list[dict], out: Path) -> None:
    # two side-by-side bars per tile: prologue & steady (stacked_bars stacks, so use side-by-side via lineplot? Use grid_plot)
    groups = [r["tile"] for r in steady_records]
    components = {
        "prologue (N=1)":    [r["prologue"] for r in steady_records],
        "steady (inferred)": [r["steady"]   for r in steady_records],
    }
    # stacked is fine here: shows how steady "tops up" the prologue baseline
    stacked_bars(
        groups, components, out_path=out,
        colors={"prologue (N=1)": "#EF553B", "steady (inferred)": "#636EFA"},
        ylabel="L1 hit rate (stacked)",
        title=("Prologue vs steady-state L1 hit rate per tile shape\n"
               + summarize_config(BASE_OVERRIDES)),
    )


def run() -> None:
    base = (workspace_root() / "default.config").read_text()

    cache_p = EXPERIMENT_DIR / "results.json"
    cache: dict = {}
    if cache_p.exists():
        try:
            cache = json.loads(cache_p.read_text())
        except json.JSONDecodeError:
            cache = {}

    records: list[dict] = []
    for tm, tn in TILES:
        cfg_text = render_config(base, {**BASE_OVERRIDES, "TILE_M": tm, "TILE_N": tn})
        asm_path = None
        for n in REPEATS:
            key = f"{tm}x{tn}|N={n}"
            if key in cache:
                rec = cache[key]
                print(f"  cache hit  {key}")
            else:
                if asm_path is None:
                    asm_path = _generate_assembly(cfg_text)
                concat = _concat_n(asm_path, n)
                try:
                    metrics = _run_with_assembly(cfg_text, concat)
                finally:
                    concat.unlink(missing_ok=True)
                rec = {
                    "tile_m": tm, "tile_n": tn, "n": n,
                    "l1_hit_rate": metrics.l1.hit_rate,
                    "cycles": metrics.cycles,
                }
                cache[key] = rec
                cache_p.write_text(json.dumps(cache, indent=2))
                print(f"  ran        {key}  hr={metrics.l1.hit_rate:.3f}")
            records.append(rec)
        if asm_path is not None:
            asm_path.unlink(missing_ok=True)

    # Infer steady-state hit rate from N=1 and max-N for each tile
    steady_records: list[dict] = []
    for tm, tn in TILES:
        rs = [r for r in records if r["tile_m"] == tm and r["tile_n"] == tn]
        rs.sort(key=lambda r: r["n"])
        if len(rs) < 2:
            continue
        p1, pN = rs[0], rs[-1]
        # pooled(N) = p1/N + steady*(N-1)/N → steady = (pooled(N)*N - p1) / (N-1)
        steady = (pN["l1_hit_rate"] * pN["n"] - p1["l1_hit_rate"]) / (pN["n"] - 1)
        steady_records.append({
            "tile": f"{tm}x{tn}",
            "prologue": p1["l1_hit_rate"],
            "steady":   max(0.0, min(1.0, steady)),
        })

    _plot_curves(records, EXPERIMENT_DIR / "hit_rate_vs_repeats.png")
    _plot_bars(steady_records, EXPERIMENT_DIR / "prologue_vs_steady.png")

    lines: list[str] = []
    lines.append("# cold-vs-warm\n")
    lines.append("![Hit rate vs N](hit_rate_vs_repeats.png)\n")
    lines.append("![Prologue vs steady](prologue_vs_steady.png)\n")
    lines.append("\n## Inferred steady-state vs prologue\n")
    lines.append("| tile | prologue (N=1) | steady (inferred) |")
    lines.append("|---|---|---|")
    for r in steady_records:
        lines.append(f"| {r['tile']} | {r['prologue']:.3f} | {r['steady']:.3f} |")
    write_report(EXPERIMENT_DIR / "README.md", "cold-vs-warm", lines)
