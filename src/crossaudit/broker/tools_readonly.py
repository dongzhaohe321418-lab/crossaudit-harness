"""Phase 1 read-only tools (permission level 1).

Each reads the *committed* tree through ``gitio`` — inheriting its symlink and
submodule refusal, deterministic byte caps, and tree-as-source-of-truth
posture — or runs a read-only ``git``/doctor probe. None writes, opens a socket,
or executes arbitrary commands. Each also re-checks the token's path scope as
defense-in-depth even though the policy engine already decided; a tool never
trusts that it was called correctly.
"""
from __future__ import annotations

import hashlib

from .. import gitio
from ..config import Config
from ..policy.tokens import CapabilityToken
from .registry import ToolError, ToolRegistry, ToolSpec

#: Bounds so a single read/search can never blow up memory or the ledger.
_SEARCH_BYTES_PER_FILE = 512 * 1024
_MAX_SEARCH_HITS = 200
_MAX_STATUS_ROWS = 500


def _require_path(args: dict, token: CapabilityToken) -> str:
    rel = str(args.get("path", "") or "")
    if not rel:
        raise ToolError("this tool needs a 'path' argument")
    if not token.allows_path(rel):
        # Should have been denied by policy; refuse hard if the tool is misused.
        raise ToolError(f"path {rel!r} is outside the grant")
    return rel


def _blob_for(repo, sha: str, rel: str) -> str | None:
    for _mode, path, blob in gitio.entries(repo, sha, prefix=rel):
        if path == rel:
            return blob
    return None


def file_read(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Read one committed file's text + its content hash."""
    rel = _require_path(args, token)
    sha = gitio.resolve(cfg.root, "HEAD")[0]
    blob = _blob_for(cfg.root, sha, rel)
    if blob is None:
        raise ToolError(f"{rel!r} is not in the committed tree")
    data, truncated = gitio.read_blob(cfg.root, blob)
    return {
        "path": rel,
        "content": data.decode("utf-8", errors="replace"),
        "bytes": len(data),
        "truncated": bool(truncated),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def search(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Substring search over committed files within the grant's scope.

    Substring (not regex) by design — no attacker-supplied pattern can make the
    scan super-linear. Bounded per file and in total hits.
    """
    query = str(args.get("query", "") or "")
    if not query:
        raise ToolError("this tool needs a 'query' argument")
    prefix = str(args.get("path", "") or "")
    if prefix and not token.allows_path(prefix):
        raise ToolError(f"path {prefix!r} is outside the grant")
    sha = gitio.resolve(cfg.root, "HEAD")[0]
    hits: list[dict] = []
    truncated = False
    for _mode, path, blob in gitio.entries(cfg.root, sha, prefix=prefix):
        if not token.allows_path(path):
            continue
        data, _ = gitio.read_blob(cfg.root, blob, limit=_SEARCH_BYTES_PER_FILE)
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if query in line:
                hits.append({"path": path, "line": lineno, "text": line[:300]})
                if len(hits) >= _MAX_SEARCH_HITS:
                    truncated = True
                    break
        if truncated:
            break
    return {"query": query, "hits": hits, "count": len(hits), "truncated": truncated}


def git_status(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Working-tree status via a read-only ``git status --porcelain``."""
    out = gitio.git("status", "--porcelain=v1", cwd=cfg.root, check=False)
    rows = [ln for ln in out.splitlines() if ln.strip()]
    changes = [{"status": ln[:2].strip(), "path": ln[3:]} for ln in rows[:_MAX_STATUS_ROWS]]
    return {"clean": not rows, "count": len(rows), "changes": changes,
            "truncated": len(rows) > _MAX_STATUS_ROWS}


def doctor(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Read-only environment diagnostics (no repair, no network in Phase 1)."""
    from .. import app_doctor
    return app_doctor.collect(cfg, online=False)


def register_readonly(registry: ToolRegistry) -> ToolRegistry:
    """Register the four Level-1 read-only tools on ``registry``."""
    registry.register(ToolSpec(
        name="file_read", level=1, writes=False, needs_network=False,
        handler=file_read, path_args=("path",),
        summary="Read one committed file's text."))
    registry.register(ToolSpec(
        name="search", level=1, writes=False, needs_network=False,
        handler=search, path_args=("path",),
        summary="Substring-search committed files in scope."))
    registry.register(ToolSpec(
        name="git_status", level=1, writes=False, needs_network=False,
        handler=git_status, summary="Show working-tree git status."))
    registry.register(ToolSpec(
        name="doctor", level=1, writes=False, needs_network=False,
        handler=doctor, summary="Read-only environment diagnostics."))
    return registry
