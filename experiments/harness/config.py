"""Render a config file by overlaying overrides onto a base template."""

from pathlib import Path
from typing import Mapping


def render_config(base_text: str, overrides: Mapping[str, object]) -> str:
    """Replace `KEY=value` lines in `base_text` with values from `overrides`.

    Keys present in overrides but missing from base are appended at the end.
    Keys in base but not in overrides keep their original value.
    Comments and blank lines are preserved.
    """
    out_lines: list[str] = []
    seen: set[str] = set()
    for raw in base_text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in overrides:
            out_lines.append(f"{key}={overrides[key]}")
            seen.add(key)
        else:
            out_lines.append(line)

    extras = [k for k in overrides if k not in seen]
    if extras:
        out_lines.append("")
        out_lines.append("# --- overrides appended by harness ---")
        for k in extras:
            out_lines.append(f"{k}={overrides[k]}")

    return "\n".join(out_lines) + "\n"


def load_base(path: Path) -> str:
    return path.read_text()
