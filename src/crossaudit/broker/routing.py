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

from .. import hpc
from ..config import Config
from ..errors import IntegrityDenial
from ..ledger import EvidenceLedger
from ..policy import CapabilityToken
from . import ToolBroker, ToolRegistry, default_registry, write_registry
from .approval import WORKSPACE_WRITES, AuthorizationStore
from .tools_command import command_allowlist, register_command
from .tools_git import register_git_actions, register_git_read
from .tools_hpc import register_hpc
from .tools_readonly import register_readonly
from .tools_research import register_research
from .tools_write import register_write

#: A tool request whose server_id is this is a built-in, brokered tool (not MCP).
BROKER_SERVER_ID = "crossaudit"
#: Phase-1 read-only tool names a per-run grant may carry.
READONLY_TOOLS = ("file_read", "search", "git_status", "doctor")
#: Default life of a per-run read-only grant (a build that outlives it re-scopes).
DEFAULT_TTL_SECONDS = 3600
EVIDENCE_FILE = "evidence.jsonl"


def evidence_path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / EVIDENCE_FILE


def broker_for(cfg: Config, *, registry: ToolRegistry | None = None,
               approver: object = None) -> ToolBroker:
    return ToolBroker(registry or default_registry(),
                      EvidenceLedger(evidence_path(cfg)), approver=approver)


def readonly_catalog() -> list[dict]:
    """The read-only tools the model may propose (name/level/scope hints)."""
    return default_registry().catalog()


#: The ONLY payload fields the Auditor's evidence view may expose. Hashes and
#: policy decisions — never raw tool output — so reviewing evidence cannot
#: influence the Auditor's context. Anything not listed is dropped.
_EVIDENCE_VIEW_FIELDS = ("tool", "args_sha256", "result_sha256", "status",
                         "allow", "granted", "requires_approval", "level", "reason",
                         "run_id", "path", "existed_before", "pre_sha256",
                         "post_sha256", "bytes", "secret_flagged")


def evidence_view(cfg: Config) -> list[dict]:
    """A read-only, allowlisted projection of the evidence ledger for the Auditor.

    Fail-safe: an absent or empty optional ledger yields ``[]``. A present
    ledger whose hash chain is broken raises an integrity denial, so corrupted
    evidence cannot be projected into the auditor input as if it were absent.
    """
    try:
        led = EvidenceLedger(cfg.root / cfg.state_dir / EVIDENCE_FILE)
        if led.path.exists():
            report = led.verify()
            if not report.ok:
                raise IntegrityDenial(
                    f"evidence ledger cannot be shown to the Auditor: {report.error}")
        rows: list[dict] = []
        for entry in led.entries():
            payload = entry.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            safe = {k: payload[k] for k in _EVIDENCE_VIEW_FIELDS if k in payload}
            rows.append({"seq": entry.get("seq"), "kind": entry.get("kind"), **safe})
        return rows
    except IntegrityDenial:
        # A present but broken chain is not equivalent to an empty ledger: the
        # Auditor must never be given a silently laundered evidence view.
        raise
    except Exception:  # noqa: BLE001 -- absent/unreadable optional ledger stays empty
        return []


#: How many recent governed actions the audit panel shows (bounded so a long
#: ledger cannot bloat a snapshot frame).
GOVERNED_ACTIONS_LIMIT = 60


def governed_actions(cfg: Config, *, limit: int = GOVERNED_ACTIONS_LIMIT) -> list[dict]:
    """A human-facing projection of the evidence ledger for the audit panel.

    Walks the allowlisted ``evidence_view`` (hashes / decisions / approvals /
    statuses — never raw output) and folds each ``tool_call → decision →
    [approval] → tool_result`` run into one action row, so the user can see every
    governed action the agent took, under which grant, approved how, and whether
    it ran. Most-recent first, bounded. Nothing here is raw content — only what
    the Auditor's evidence view already exposes.
    """
    rows = evidence_view(cfg)
    actions: list[dict] = []
    cur: dict | None = None
    for r in rows:
        kind = r.get("kind")
        if kind == "tool_call":
            cur = {"seq": r.get("seq"), "tool": r.get("tool"),
                   "args_sha256": r.get("args_sha256"), "level": None,
                   "decision": None, "requires_approval": None,
                   "approval": None, "status": None, "reason": None,
                   "path": None, "pre_sha256": None, "post_sha256": None,
                   "result_sha256": None, "bytes": None, "secret_flagged": None,
                   "run_id": r.get("run_id")}
            actions.append(cur)
        elif cur is None:
            continue
        elif kind == "decision":
            cur["level"] = r.get("level")
            cur["decision"] = "allow" if r.get("allow") else "deny"
            cur["requires_approval"] = r.get("requires_approval")
            cur["reason"] = r.get("reason")
            if r.get("run_id"):
                cur["run_id"] = r.get("run_id")
        elif kind == "approval":
            cur["approval"] = "granted" if r.get("granted") else "denied"
            if r.get("reason"):
                cur["reason"] = r.get("reason")
        elif kind == "tool_result":
            cur["status"] = r.get("status")
            cur["result_sha256"] = r.get("result_sha256")
            for f in ("path", "pre_sha256", "post_sha256", "bytes", "secret_flagged"):
                if r.get(f) is not None:
                    cur[f] = r.get(f)
    # A display outcome: the tool_result status if it ran, else why it did not.
    for a in actions:
        if a["status"]:
            a["outcome"] = a["status"]
        elif a["approval"] == "denied":
            a["outcome"] = "needs_approval"
        elif a["decision"] == "deny":
            a["outcome"] = "refused"
        else:
            a["outcome"] = "recorded"
    return list(reversed(actions))[:max(1, int(limit))]


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
        tools=frozenset(READONLY_TOOLS + ("file_write", "file_edit")),
        paths=paths,
        writable=True,
        expires_at=_iso_utc(now_epoch + ttl_seconds),
    )


def writes_authorized(cfg: Config) -> bool:
    """Whether the user turned on recoverable file edits for this project."""
    return AuthorizationStore(cfg).authorized(WORKSPACE_WRITES)


def run_commands_authorized(cfg: Config) -> bool:
    """Whether the user allowlisted any commands — the explicit opt-in that makes
    the Level-3 ``run_check`` tool reachable (each command is still allowlisted by
    name AND per-call approval-gated before it runs)."""
    return len(command_allowlist(cfg)) > 0


def compute_authorized(cfg: Config) -> bool:
    """Whether this project has an agent-enabled HPC host configured — the
    explicit opt-in that makes the HPC tools reachable (submit stays L5, always
    per-call approval-gated)."""
    try:
        return bool(hpc.MANAGER.agent_context(cfg))
    except Exception:  # noqa: BLE001 -- catalog composition must never fail hard
        return False


def live_registry(cfg: Config) -> ToolRegistry:
    """The tools this project actually offers a build, composed from what the
    user authorized: always read-only; + recoverable writes & git actions when
    writes are authorized; + ``run_check`` when commands are allowlisted; + HPC
    when a compute host is configured. Everything above Level 1 is still
    approval-gated by the broker — authorization only makes a tool *proposable*."""
    registry = register_git_read(register_readonly(ToolRegistry()))
    # Research retrieval is read-only and Level 4 — proposable everywhere, but
    # every call still stops at the per-call approval gate (never auto-runs).
    register_research(registry)
    if writes_authorized(cfg):
        register_write(registry)
        register_git_actions(registry)
    if run_commands_authorized(cfg):
        register_command(registry)
    if compute_authorized(cfg):
        register_hpc(registry)
    return registry


def live_catalog(cfg: Config) -> list[dict]:
    """The catalog for the generator — exactly the live registry's tools, so what
    the model is told it may propose always matches what its token can grant."""
    return live_registry(cfg).catalog()


def write_catalog() -> list[dict]:
    """The read-only + write tool catalog (offered when writes are authorized)."""
    return write_registry().catalog()


def build_catalog(cfg: Config) -> list[dict]:
    """The tool catalog the generator is offered for this project — the live
    registry, gated by what the user authorized (read-only by default)."""
    return live_catalog(cfg)


def _scoped_paths(cfg: Config) -> tuple[str, ...]:
    scope = tuple(cfg.scope_dirs or ())
    return tuple(f"{str(d).strip('/')}/**" for d in scope if str(d).strip()) or ("**",)


def build_broker_and_token(cfg: Config, *, run_id: str, now_epoch: float,
                           approver: object = None
                           ) -> tuple[ToolBroker, CapabilityToken]:
    """A broker + capability token for a build.

    The token's tools ARE the live registry's tools (single source of truth), so
    every advertised tool is grantable and then approval-gated — never advertised
    yet refused as "not in this grant". The grant is writable exactly when the
    live registry contains a writing tool (i.e. the project authorized one), and
    scoped to the project's directories.

    ``approver`` is the real-time per-call approval gate a live build injects
    (HumanApprovalGate); absent one, the broker falls back to the standing
    Approval Service, which never auto-grants Level 3+ (deny-by-default)."""
    registry = live_registry(cfg)
    catalog = registry.catalog()
    token = CapabilityToken(
        project_id=str(cfg.root),
        run_id=run_id or "run",
        tools=frozenset(registry.names()),
        paths=_scoped_paths(cfg),
        writable=any(bool(t.get("writes")) for t in catalog),
        expires_at=_iso_utc(now_epoch + DEFAULT_TTL_SECONDS),
    )
    return broker_for(cfg, registry=registry, approver=approver), token


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
