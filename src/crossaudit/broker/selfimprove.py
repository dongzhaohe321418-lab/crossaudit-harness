"""Phase 6 controlled self-improvement — isolation, and a hard install ban.

CrossAudit may help improve itself, but only in an isolated candidate worktree
that never touches the running application, and it may NEVER install or replace
the running app — that is the user's action alone. ``self_install`` is registered
so the boundary is explicit, and its handler always refuses; the tool is also
Level 6, so the broker gates it before the handler is even reached. Both together
guarantee the model cannot modify the running application.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import Config
from ..policy.tokens import CapabilityToken
from .registry import ToolError, ToolRegistry, ToolSpec

CANDIDATE_DIRNAME = "candidate"


def self_install(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Always refused: the model may never install or modify the running app."""
    raise ToolError(
        "self-installation is not permitted; a candidate build is reviewed by "
        "the independent auditor and installed only by the user")


def candidate_worktree(cfg: Config, ref: str = "HEAD") -> Path:
    """Create an isolated git worktree for a self-improvement candidate.

    The candidate lives under the project's state dir, entirely separate from the
    running application's files, so building/auditing a candidate can never mutate
    what is currently installed.
    """
    target = cfg.root / cfg.state_dir / CANDIDATE_DIRNAME
    if target.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(target)],
                       cwd=str(cfg.root), capture_output=True, check=False)
    subprocess.run(["git", "worktree", "add", "--detach", str(target), ref],
                   cwd=str(cfg.root), capture_output=True, text=True, check=True)
    return target


def register_self_improve(registry: ToolRegistry) -> ToolRegistry:
    registry.register(ToolSpec(
        name="self_install", level=6, writes=True, needs_network=False,
        handler=self_install,
        summary="(forbidden) install/replace the running app — always refused."))
    return registry
