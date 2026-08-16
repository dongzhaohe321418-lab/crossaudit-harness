"""Recovery points + safe write primitives for Level-2 workspace edits.

Every governed write is reversible: before a file is changed, its prior state
(content, or its absence) is snapshotted content-addressed under the project's
state dir, so ``restore`` can put it back exactly — or delete a file the tool
created. Writes are atomic (temp + rename) and can never land outside the
project root: ``resolve_in_root`` refuses absolute paths, ``..`` traversal, and
symlinks that resolve outside the workspace.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..errors import ConfigDenial

RECOVERY_DIRNAME = "recovery"


def resolve_in_root(root: Path, rel: str) -> Path | None:
    """Absolute path for a project-relative ``rel``, or None if it escapes root.

    Defense-in-depth on top of the capability token's own path scoping: even a
    symlink whose target leaves the workspace is refused, because the *resolved*
    path must sit strictly inside the resolved root.
    """
    if not rel or not isinstance(rel, str) or rel.startswith("/") or "\x00" in rel:
        return None
    if rel.startswith("~"):
        return None
    candidate = root / rel
    try:
        resolved = candidate.resolve()
        root_resolved = root.resolve()
    except OSError:
        return None
    if resolved == root_resolved or root_resolved not in resolved.parents:
        return None
    return candidate


def atomic_write(target: Path, data: bytes) -> None:
    """Write ``data`` to ``target`` atomically (temp file + rename + fsync)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp{os.getpid()}")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


@dataclass
class RecoveryStore:
    """Content-addressed pre-write snapshots for one project, under its state dir."""

    cfg: Config

    @property
    def _dir(self) -> Path:
        return self.cfg.root / self.cfg.state_dir / RECOVERY_DIRNAME

    def snapshot(self, rel: str) -> dict:
        """Record the current state of ``rel`` so a later write can be undone.

        Returns a small, serialisable record: the path, whether it existed, and
        its pre-write content hash (``""`` when the file is new).
        """
        target = self.cfg.root / rel
        existed = target.is_file()
        if not existed:
            return {"path": rel, "existed": False, "pre_sha256": ""}
        data = target.read_bytes()
        pre_sha = hashlib.sha256(data).hexdigest()
        self._dir.mkdir(parents=True, exist_ok=True)
        blob = self._dir / f"{pre_sha}.bak"
        if not blob.exists():                     # content-addressed: dedup
            atomic_write(blob, data)
        return {"path": rel, "existed": True, "pre_sha256": pre_sha}

    def restore(self, record: dict) -> None:
        """Undo a write: put back the snapshotted content, or delete a new file."""
        target = self.cfg.root / str(record.get("path", ""))
        if record.get("existed"):
            blob = self._dir / f"{record.get('pre_sha256', '')}.bak"
            if not blob.is_file():
                raise ConfigDenial("recovery snapshot is missing; cannot restore")
            atomic_write(target, blob.read_bytes())
        else:
            target.unlink(missing_ok=True)
