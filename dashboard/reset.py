"""Deletion scope for an explicitly reset, caller-owned console workspace."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

_FILES = {
    "events.sqlite3",
    "events.sqlite3-wal",
    "events.sqlite3-shm",
    "benchmark.json",
    "measured-runs.json",
    "runs.csv",
    "recall.png",
    "phase1-gate.json",
    "judge.json",
    "manual-review.json",
    "checkpoint.json",
    "frozen-config.json",
    "frozen-truth.json",
    "source-manifest.json",
}
_DIRECTORIES = {"memory", "benchmark", "frozen-source"}
_RUN = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
_TARGET = re.compile(r"targets-[a-z0-9_]{8}")


def cleanup_plan(output: Path, active_targets: Path) -> list[Path]:
    """Preflight every deletion before changing data; never follow a symlink."""
    if output.is_symlink():
        raise ValueError("workspace root is a symlink")
    root = output.resolve()
    source = Path(__file__).resolve().parent.parent
    forbidden = {Path("/"), Path.home().resolve(), Path(tempfile.gettempdir()).resolve()}
    if root in forbidden or (
        root.is_relative_to(source) and not root.is_relative_to(source / "artifacts")
    ):
        raise ValueError("reset requires an artifact workspace, not a source directory")
    active = active_targets.resolve()
    if active.parent != root or active_targets.is_symlink():
        raise ValueError("targets are not owned by this workspace")
    plan = []
    for path in root.iterdir():
        recognized = (
            path.name in _FILES | _DIRECTORIES
            or _RUN.fullmatch(path.name)
            or _TARGET.fullmatch(path.name)
        )
        if not recognized or path == active:
            continue
        if path.is_symlink() or any(p.is_symlink() for p in path.rglob("*")):
            raise ValueError("generated artifact contains a symlink")
        if path.is_dir() and path.name in _FILES:
            raise ValueError("generated file path is a directory")
        if path.is_file() and path.name not in _FILES:
            raise ValueError("generated directory path is a file")
        plan.append(path)
    # The active targets are reset through their database/process owners, not rmtree.
    if any(p.is_symlink() for p in active_targets.rglob("*")):
        raise ValueError("active target contains a symlink")
    return plan


def clear_artifacts(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
