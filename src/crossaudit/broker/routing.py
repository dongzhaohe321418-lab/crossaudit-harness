"""Wiring the Tool Broker into a project + the build loop.

Kept free of any ``cli`` import so both ``cli.build`` and ``appservice`` can use
it without an import cycle. It owns: where a project's evidence ledger lives, how
to build a broker for a project, the reserved ``server_id`` that marks a built-in
(brokered) tool request, the per-run read-only capability token, and the adapter
that turns a model's tool-request envelope into a brokered, evidence-recorded
call whose result is fed back to the generator as untrusted context.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..config import Config
from ..ledger import EvidenceLedger
from ..policy import CapabilityToken
from . import ToolBroker, ToolRegistry, default_registry, write_registry
from .approval import WORKSPACE_WRITES, AuthorizationStore

#: A tool request whose server_id is this is a built-in, brokered tool (not MCP).
BROKER_SERVER_ID = "crossaudit"
#: Phase-1 read-only tool names a per-run grant may carry.
READONLY_TOOLS = ("file_read", "search", "git_status", "doctor")
#: Default life of a per-run read-only grant (a build that outlives it re-scopes).
DEFAULT_TTL_SECONDS = 3600
EVIDENCE_FILE = "evidence.jsonl"


def evidence_path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / EVIDENCE_FILE


def broker_for(cfg: Config, *, registry: ToolRegistry | None = None) -> ToolBroker:
    return ToolBroker(registry or default_registry(), EvidenceLedger(evidence_path(cfg)))


def readonly_catalog() -> list[dict]:
    """The read-only tools the model may propose (name/level/scope hints)."""
    return default_registry().catalog()


#: The ONLY payload fields the Auditor's evidence view may expose. Hashes and
#: policy decisions — never raw tool output — so reviewing evidence cannot
#: influence the Auditor's context. Anything not listed is dropped.
_EVIDENCE_VIEW_FIELDS = ("tool", "args_sha256", "result_sha256", "status",
                         "allow", "granted", "requires_approval", "level", "reason",
                         "run_id", "path", "existed_before", "pre_sha256",
                         "post_sha256", "bytes")


def evidence_view(cfg: Config) -> list[dict]:
    """A read-only, allowlisted projection of the evidence ledger for the Auditor.

    Fail-safe: an absent, empty, or unreadable ledger yields ``[]`` so the audit
    prompt is unchanged when no governed tools ran.
    """
    try:
        led = EvidenceLedger(cfg.root / cfg.state_dir / EVIDENCE_FILE)
        rows: list[dict] = []
        for entry in led.entries():
            payload = entry.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            safe = {k: payload[k] for k in _EVIDENCE_VIEW_FIELDS if k in payload}
            rows.append({"seq": entry.get("seq"), "kind": entry.get("kind"), **safe})
        return rows
    except Exception:  # noqa: BLE001 -- an evidence view must never break the audit
        return []


def _iso_utc(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def readonly_token(cfg: Config, *, run_id: str, now_epoch: float,
                   ttl_seconds: int = DEFAULT_TTL_SECONDS) -> CapabilityToken:
    """A read-only grant scoped to the project's configured directories."""
    scope = tuple(cfg.scope_dirs or ())
    paths = tuple(f"{str(d).strip('/')}/**" for d in scope if str(d).strip()) or ("**",)
    return CapabilityToken(
        project_id=str(cfg.root),
        run_id=run_id or "run",
        tools=frozenset(READONLY_TOOLS),
        paths=paths,
        writable=False,
        expires_at=_iso_utc(now_epoch + ttl_seconds),
    )


def writable_token(cfg: Config, *, run_id: str, now_epoch: float,
                   ttl_seconds: int = DEFAULT_TTL_SECONDS) -> CapabilityToken:
    """A read+write grant scoped to the project's directories.

    Issued only for a project whose user turned on ``workspace_writes``; the
    Approval Service still gates each write, and every write is recoverable and
    ledgered.
    """
    scope = tuple(cfg.scope_dirs or ())
    paths = tuple(f"{str(d).strip('/')}/**" for d in scope if str(d).strip()) or ("**",)
    return CapabilityToken(
        project_id=str(cfg.root),
        run_id=run_id or "run",
        tools=frozenset(READONLY_TOOLS + ("file_write",)),
        paths=paths,
        writable=True,
        expires_at=_iso_utc(now_epoch + ttl_seconds),
    )


def writes_authorized(cfg: Config) -> bool:
    """Whether the user turned on recoverable file edits for this project."""
    return AuthorizationStore(cfg).authorized(WORKSPACE_WRITES)


def write_catalog() -> list[dict]:
    """The read-only + write tool catalog (offered when writes are authorized)."""
    return write_registry().catalog()


def build_catalog(cfg: Config) -> list[dict]:
    """The tool catalog the generator is offered for this project: read-only, or
    read+write when the project authorized recoverable edits."""
    return write_catalog() if writes_authorized(cfg) else readonly_catalog()


def build_broker_and_token(cfg: Config, *, run_id: str,
                           now_epoch: float) -> tuple[ToolBroker, CapabilityToken]:
    """A broker + capability token for a build. Writable iff the project is
    authorized; otherwise read-only — so writes happen only after the user's
    explicit per-project opt-in."""
    if writes_authorized(cfg):
        return (broker_for(cfg, registry=write_registry()),
                writable_token(cfg, run_id=run_id, now_epoch=now_epoch))
    return (broker_for(cfg), readonly_token(cfg, run_id=run_id, now_epoch=now_epoch))


def broker_tool_call(cfg: Config, request: dict, token: CapabilityToken, *,
                     run_id: str, now_epoch: float,
                     broker: ToolBroker | None = None) -> dict:
    """Run one model tool-request through the broker; shape the result for feedback.

    The returned dict mirrors an MCP result the loop already knows how to feed
    back to the generator as untrusted context — it carries the tool, status,
    output, and the content hash the ledger recorded, never raw authority.
    """
    broker = broker or broker_for(cfg)
    req = request or {}
    tool = str(req.get("tool", ""))
    args = req.get("arguments") or req.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    result = broker.execute({"tool": tool, "args": args}, token,
                            cfg=cfg, run_id=run_id, now_epoch=now_epoch)
    return {
        "status": result.status,
        "server_id": BROKER_SERVER_ID,
        "tool": tool,
        "output": result.output,
        "reason": result.reason,
        "result_sha256": result.result_sha256,
    }
