"""Readiness facts shared by `init`, the CLI doctor and the app doctor.

Every entry here exists because two commands were deciding the same thing
separately and drifted. `init` printing "Ready" while the doctor run one
command later denied readiness was the second instance, and the fix is the
same as the first: one implementation, consumed twice, rather than two that
agree on the day they are written.
"""
from __future__ import annotations

from . import _selfid
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


def install_blocks(identity: dict | None = None) -> list[tuple[str, str]]:
    """What about THIS install stops the doctor calling the project ready.

    Returned as (check name, detail) so both consumers report the same reason in
    the same words. `init` used to derive readiness from credentials alone while
    the doctor also weighed this, so a keyed setup announced "Ready" and the very
    next command said otherwise — in the person's own language, with the second
    line being the true one.
    """
    ident = identity if identity is not None else _selfid.identity()
    blocks: list[tuple[str, str]] = []
    mode = ident.get("install_mode", "unknown")
    if mode == "unknown":
        blocks.append(("install", f"{mode}, so this build cannot identify itself"))
    if mode not in _selfid.ADMISSIBLE_MODES:
        blocks.append(("admission-capable",
                       f"install mode {mode} may verify but never admit"))
    return blocks
