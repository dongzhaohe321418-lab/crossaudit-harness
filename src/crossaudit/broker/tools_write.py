"""Phase 2 write tools (permission level 2) — recoverable workspace edits.

A write only happens after the capability token proves it is writable and in
scope (the policy engine), the path is re-checked to be inside the workspace
(defense-in-depth), and a recovery point is taken. The tool returns the before
and after content hashes — the diff the broker records to the Evidence Ledger,
so the Auditor can review exactly what changed without the raw bytes.
"""
from __future__ import annotations

import difflib
import hashlib

from ..config import Config
from ..policy.tokens import CapabilityToken
from . import secretscan
from .recovery import RecoveryStore, atomic_write, resolve_in_root
from .registry import ToolError, ToolRegistry, ToolSpec
from .tools_readonly import register_readonly

#: A single governed write is capped so one call can never dump an unbounded blob.
MAX_WRITE_BYTES = 1_048_576  # 1 MiB


def file_write(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Write one file inside the workspace, reversibly, and report the diff."""
    rel = str(args.get("path", "") or "")
    if not rel:
        raise ToolError("file_write needs a 'path' argument")
    if not token.allows_path(rel):
        raise ToolError(f"path {rel!r} is outside the grant")
    content = args.get("content", "")
    if not isinstance(content, str):
        raise ToolError("file_write 'content' must be a string")
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        raise ToolError(f"content exceeds the {MAX_WRITE_BYTES}-byte write limit")
    target = resolve_in_root(cfg.root, rel)
    if target is None:
        raise ToolError(f"path {rel!r} escapes the workspace")

    recovery = RecoveryStore(cfg)
    record = recovery.snapshot(rel)          # recovery point BEFORE the write
    atomic_write(target, data)
    # A workspace write is recoverable, so a credential-shaped value does not
    # block it — but the KIND (never the value) is recorded so the Auditor and
    # the commit gate both see it. The real leak (into git history) is refused
    # at git_commit; here it is surfaced early.
    flagged = secretscan.first_finding(content, [rel])
    return {
        "path": rel,
        "existed_before": record["existed"],
        "pre_sha256": record["pre_sha256"],
        "post_sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "secret_flagged": flagged,
        "recoverable": True,
    }


def file_write_preview(cfg: Config, args: dict) -> str:
    """A unified diff of the current file vs the proposed content, for the card."""
    rel = str(args.get("path", "") or "")
    content = args.get("content", "")
    if not rel or not isinstance(content, str):
        return ""
    target = resolve_in_root(cfg.root, rel)
    old, existed = "", False
    if target is not None and target.is_file():
        try:
            old, existed = target.read_text(encoding="utf-8", errors="replace"), True
        except OSError:
            old = ""
    header = f"write {rel}" + ("" if existed else "  (new file)")
    diff = list(difflib.unified_diff(
        old.splitlines(), content.splitlines(),
        fromfile=(rel if existed else "/dev/null"), tofile=rel, lineterm=""))
    body = "\n".join(diff[:200])
    return f"{header}\n{body}" if body else f"{header}\n(no textual change)"


def register_write(registry: ToolRegistry) -> ToolRegistry:
    """Register the Level-2 write tools (recoverable workspace edits)."""
    registry.register(ToolSpec(
        name="file_write", level=2, writes=True, needs_network=False,
        handler=file_write, path_args=("path",),
        evidence_fields=("path", "existed_before", "pre_sha256", "post_sha256",
                         "bytes", "secret_flagged"),
        preview=file_write_preview,
        summary="Write a file (recoverable) inside your allowed directories."))
    return registry


def write_registry() -> ToolRegistry:
    """A registry with the read-only tools AND the Level-2 write tools.

    Kept separate from ``default_registry`` (read-only): writing is only offered
    where the runtime has decided to issue a writable grant.
    """
    return register_write(register_readonly(ToolRegistry()))
