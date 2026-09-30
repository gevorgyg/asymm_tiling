"""Discovery + dispatcher for experiment scripts.

Usage:
    python -m experiments.run <name>...      # run named experiments
    python -m experiments.run --all          # run every discovered experiment
    python -m experiments.run --list         # list discovered experiments

Each experiment lives at experiments/v45-results/<name>/experiment.py and
must define a top-level `run()` callable.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

from .harness import workspace_root


def _v45_root() -> Path:
    return Path(__file__).resolve().parent / "v45-results"


def discover() -> list[str]:
    root = _v45_root()
    if not root.is_dir():
        return []
    return sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and (d / "experiment.py").is_file()
    )


def _load(name: str):
    path = _v45_root() / name / "experiment.py"
    if not path.is_file():
        raise SystemExit(f"no such experiment: {name} (expected {path})")
    spec = importlib.util.spec_from_file_location(f"experiments.v45.{name}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise SystemExit(f"{name}/experiment.py must define a top-level run()")
    return mod


def _ensure_binary_built() -> None:
    if (workspace_root() / "asymm").is_file():
        return
    print("(building ./asymm — first run)")
    subprocess.run(["make"], cwd=str(workspace_root()), check=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="experiments.run")
    p.add_argument("names", nargs="*", help="experiment names")
    p.add_argument("--all", action="store_true", help="run every discovered experiment")
    p.add_argument("--list", action="store_true", help="list and exit")
    args = p.parse_args()

    available = discover()

    if args.list:
        for name in available:
            print(name)
        return

    if args.all:
        names = available
        if not names:
            print("no experiments found under experiments/v45-results/")
            return
    elif args.names:
        names = args.names
    else:
        print("usage: python -m experiments.run <name>... | --all | --list")
        print("\navailable:")
        for name in available:
            print(f"  {name}")
        sys.exit(2)

    _ensure_binary_built()

    for name in names:
        print(f"\n=== {name} ===")
        mod = _load(name)
        mod.run()


if __name__ == "__main__":
    main()
