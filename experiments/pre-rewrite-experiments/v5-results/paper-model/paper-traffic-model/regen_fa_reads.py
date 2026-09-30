"""Regenerate results.json for the fully-associative regime only, then plot.

The full experiment.py also sweeps an 8-way-associative regime, but the
current ./asymm crashes on at least one 8-way tile under stationary="B"
(generated-instruction parse error), which aborts the whole run before any
results are written. The slide (fa_reads.png / fa_writes.png) only uses the
fully-associative regime, so this script sweeps just that, tolerates any
per-cell failure, writes results.json, and calls make_fa_plots.

Run from the repo root:
    PYTHONPATH=. .venv/bin/python \
        experiments/v5-results/paper-model/paper-traffic-model/regen_fa_reads.py
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.harness import Flags, render_config, run, workspace_root

HERE = Path(__file__).resolve().parent
M = N = K = 256
A_P = 8
RHOS = [(1.0, 8), (0.5, 4), (0.25, 2), (0.125, 1)]
FAMILIES = {
    1024: [(256, 4), (128, 8), (64, 16), (32, 32), (16, 64), (8, 128), (4, 256)],
    512:  [(128, 4), (64, 8), (32, 16), (16, 32), (8, 64), (4, 128)],
}
# stationary="B" = the paper's C-stationary rank-1 order (inverted naming).
FLAGS = Flags(b_source="mem", stationary="B", three_d_reg=True, mulac_norecord=True)


def main() -> None:
    base = (workspace_root() / "default.config").read_text()
    out: dict = {}
    fails: list = []
    for rho, bp in RHOS:
        for tiles in FAMILIES.values():
            for tm, tn in tiles:
                ov = {
                    "A_HEIGHT_DIM": M, "A_WIDTH_DIM": K, "B_WIDTH_DIM": N,
                    "A_PRECISION_BYTES": A_P, "B_PRECISION_BYTES": bp,
                    "L1_SIZE_BYTES": 16384, "L1_LINE_SIZE_BYTES": 64, "L1_ASSOC": 256,
                    "L2_SIZE_BYTES": 65536, "L2_LINE_SIZE_BYTES": 64,
                    "L2_ASSOC": 1024, "L2_ACCESS_CYCLES": 14,
                    "TILE_M": tm, "TILE_N": tn, "TILE_K": 256,
                }
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".conf", delete=False
                ) as f:
                    f.write(render_config(base, ov))
                    cfg = Path(f.name)
                try:
                    m = run(cfg, FLAGS)
                    key = hashlib.sha256(f"{rho}{tm}{tn}".encode()).hexdigest()
                    out[key] = {
                        "overrides": ov,
                        "metrics": {"l1": {
                            "bytes_in": m.l1.bytes_in, "bytes_out": m.l1.bytes_out,
                        }},
                    }
                    print(f"OK   rho={rho} {tm}x{tn} in={m.l1.bytes_in:,}", flush=True)
                except Exception as e:  # noqa: BLE001 - report and continue
                    fails.append((rho, f"{tm}x{tn}", str(e).splitlines()[-1][:60]))
                    print(f"FAIL rho={rho} {tm}x{tn}: {fails[-1][2]}", flush=True)
                finally:
                    cfg.unlink(missing_ok=True)

    (HERE / "results.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {HERE/'results.json'} ({len(out)} cells, {len(fails)} failures)")
    subprocess.run([sys.executable, str(HERE / "make_fa_plots.py")], check=True)


if __name__ == "__main__":
    main()
