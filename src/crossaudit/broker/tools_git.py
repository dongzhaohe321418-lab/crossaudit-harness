"""Phase 3 Git / GitHub brokered tools.

Read-only inspection (``git_diff``/``git_log``) is Level 1 and auto-runs like
``git_status``. Local ``git_commit`` is Level 3 (never auto — a per-call yes).
``git_push`` and ``repo_create`` are Level 5: the broker always returns
``needs_approval`` for them, so they never fire without an explicit human
decision. Deleting a repository is intentionally NOT offered — per the guide,
destructive remote deletion is permanently off-limits for the model to initiate.

The handlers run only after an approval the runtime does not yet grant, so during
the build they are exercised solely through the broker's approval gate; no push
or repo creation happens.
"""
from __future__ import annotations

import os
import subprocess

from .. import gitio
from ..config import Config
from ..policy.tokens import CapabilityToken
from .registry import ToolError, ToolRegistry, ToolSpec

MAX_GIT_OUTPUT = 64 * 1024


# ---- Level 1 read-only (auto) ----
def git_diff(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    rel = str(args.get("path", "") or "")
    argv = ["diff", "--stat", "--no-color"]
    if rel:
        if not token.allows_path(rel):
            raise ToolError(f"path {rel!r} is outside the grant")
        argv += ["--", rel]
    out = gitio.git(*argv, cwd=cfg.root, check=False)
    return {"diff_stat": out[:MAX_GIT_OUTPUT]}


def git_log(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    n = max(1, min(int(args.get("limit", 20) or 20), 100))
    out = gitio.git("log", f"-n{n}", "--oneline", "--no-color", cwd=cfg.root, check=False)
    rows = out.splitlines()[:n]
    return {"log": rows, "count": len(rows)}


# ---- Level 3 local commit (approval-gated) ----
def git_commit(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    msg = str(args.get("message", "")).strip()[:1000]
    if not msg:
        raise ToolError("git_commit needs a non-empty 'message'")
    gitio.git("add", "-A", cwd=cfg.root)
    gitio.git("-c", "user.name=CrossAudit Agent",
              "-c", "user.email=agent@crossaudit.local",
              "commit", "-m", msg, cwd=cfg.root)
    sha = gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip()
    return {"commit": sha, "message": msg}


# ---- Level 5 remote actions (always approval-gated; never fired in the build) ----
def git_push(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    remote = str(args.get("remote", "origin"))[:100]
    branch = str(args.get("branch", "HEAD"))[:200]
    gitio.git("push", remote, branch, cwd=cfg.root)
    return {"remote": remote, "branch": branch, "pushed": True}


def repo_create(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    name = str(args.get("name", "")).strip()[:200]
    if not name:
        raise ToolError("repo_create needs a 'name'")
    gh = os.environ.get("CROSSAUDIT_BUNDLED_GH") or "gh"
    subprocess.run([gh, "repo", "create", name, "--private"], cwd=str(cfg.root),
                   check=True, capture_output=True, text=True, timeout=60)
    return {"repo": name, "created": True}


def register_git_read(registry: ToolRegistry) -> ToolRegistry:
    """Level-1 read-only git tools (auto)."""
    registry.register(ToolSpec(
        name="git_diff", level=1, writes=False, needs_network=False,
        handler=git_diff, path_args=("path",), summary="Show the working-tree diff stat."))
    registry.register(ToolSpec(
        name="git_log", level=1, writes=False, needs_network=False,
        handler=git_log, summary="Show recent commits (bounded)."))
    return registry


def register_git_actions(registry: ToolRegistry) -> ToolRegistry:
    """Commit (L3) + push/repo-create (L5) — all approval-gated, never auto."""
    registry.register(ToolSpec(
        name="git_commit", level=3, writes=True, needs_network=False,
        handler=git_commit, evidence_fields=("commit", "message"),
        summary="Commit the current changes in this project (needs approval)."))
    registry.register(ToolSpec(
        name="git_push", level=5, writes=True, needs_network=True, host_arg=None,
        handler=git_push, evidence_fields=("remote", "branch", "pushed"),
        summary="Push commits to a remote (always needs explicit approval)."))
    registry.register(ToolSpec(
        name="repo_create", level=5, writes=True, needs_network=True,
        handler=repo_create, evidence_fields=("repo", "created"),
        summary="Create a new private GitHub repository (always needs approval)."))
    return registry
