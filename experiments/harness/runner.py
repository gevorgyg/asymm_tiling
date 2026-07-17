"""Invoke ./asymm once and return parsed Metrics.

The Flags dataclass owns the CLI vocabulary: any flag added to README.md
should grow a field here, in the same shape, so callers never assemble
argv strings by hand.
"""

import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from . import parse
from ._workspace import asymm_binary, workspace_root


@dataclass
class Flags:
    b_source: str = "mem"          # "mem" | "prng_mem" | "prng_fifo"
    stationary: str = "B"          # "A" | "B" | "output"
    three_d_reg: bool = False
    mulac_norecord: bool = False
    no_l2: bool = False
    trace_level: int = 0
    trace_file: Optional[str] = None
    assembler_input: Optional[str] = None

    def to_argv(self) -> list[str]:
        argv = [
            "--Bsource", self.b_source,
            "--stationary", self.stationary,
            "--trace_level", str(self.trace_level),
        ]
        if self.three_d_reg:
            argv.append("--3dregisters")
        if self.mulac_norecord:
            argv.append("--mulac_norecord")
        if self.no_l2:
            argv.append("--no-l2")
        if self.trace_file is not None:
            argv += ["--trace_file", self.trace_file]
        if self.assembler_input is not None:
            argv += ["--assembler_input", self.assembler_input]
        return argv

    def to_dict(self) -> dict:
        return asdict(self)


def run(config_path: Path, flags: Flags = Flags()) -> parse.Metrics:
    cmd = [str(asymm_binary()), "--config", str(config_path), *flags.to_argv()]
    result = subprocess.run(
        cmd,
        cwd=str(workspace_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"asymm failed (rc={result.returncode}):\n"
            f"cmd:    {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return parse.parse_stdout(result.stdout)
