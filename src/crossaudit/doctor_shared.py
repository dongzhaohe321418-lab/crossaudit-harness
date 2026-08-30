"""Shared constitution readiness check for CLI and native-app doctors."""
from __future__ import annotations

from .gitio import git

CONSTITUTION_READY_SENTENCE = "audits cite the commit that versioned the rules (I3)"


def constitution_state(cfg) -> tuple[str, str]:
    tracked = bool(git("log", "-1", "--format=%H", "--", cfg.constitution,
                       cwd=cfg.root, check=False))
    dirty = bool(git("status", "--porcelain", "--", cfg.constitution,
                     cwd=cfg.root, check=False).strip())
    if not tracked:
        return "missing", f"{cfg.constitution} is not tracked by git"
    if dirty:
        return "drifted", (f"{cfg.constitution} has uncommitted changes; an audit "
                            "would cite the committed version, not what is on disk")
    return "ready", CONSTITUTION_READY_SENTENCE
