from pathlib import Path


def workspace_root() -> Path:
    """Walk up from this file until a directory containing `makefile` is found.

    The harness is part of the source tree; finding the project root by
    structural means avoids `../../..` constants that break the moment any
    directory is moved.
    """
    here = Path(__file__).resolve()
    for d in (here, *here.parents):
        if (d / "makefile").is_file():
            return d
    raise RuntimeError(
        "could not locate project root (no `makefile` in any ancestor of "
        f"{here})"
    )


def asymm_binary() -> Path:
    return workspace_root() / "asymm"
