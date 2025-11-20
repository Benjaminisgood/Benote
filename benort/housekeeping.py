"""Lightweight cleanup helpers to keep the repo tidy during runtime."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TRANSIENT_DIRS = [
    "build",
    "benort.egg-info",
    ".pytest_cache",
]


def _remove(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def clean_transient_paths(root: Path | None = None) -> None:
    """Remove build/test artifacts so the repo stays clean."""

    base = Path(root) if root else ROOT
    for rel in TRANSIENT_DIRS:
        target = base / rel
        if target.exists():
            _remove(target)

    for pycache in base.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)


def auto_clean_on_import() -> None:
    if os.environ.get("BENORT_DISABLE_AUTO_CLEAN"):
        return
    clean_transient_paths()


auto_clean_on_import()

