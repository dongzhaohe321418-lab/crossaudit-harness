"""The Tool Broker — the one seam every model-proposed action passes through.

Nothing the model asks for runs directly. ``ToolBroker.execute`` records the
proposal, asks the deterministic policy engine to decide against the run's
capability token, records the decision, and only then — if it is allowed and
needs no human approval — runs the registered tool and records its result. Every
step is written to the append-only Evidence Ledger, so the Auditor later reviews
what actually ran, under which grant, with which content hashes, and no tool can
report a success the broker did not record.

Phase 1 registers only Level-1 read-only tools; an action that policy flags as
needing approval is refused (never auto-run) until the Phase-2 Approval Service.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..ledger import EvidenceLedger
from ..policy import CapabilityToken, decide
from ..receipt.schema import digest
from .approval import approve
from .registry import ToolError, ToolRegistry, ToolSpec
from .selfimprove import register_self_improve
from .tools_git import register_git_actions, register_git_read
from .tools_hpc import register_hpc
from .tools_mcp import register_mcp
from .tools_readonly import register_readonly
from .tools_write import register_write

__all__ = ["ToolBroker", "ToolResult", "ToolRegistry", "ToolSpec", "ToolError",
           "default_registry", "register_write", "write_registry", "full_registry"]


def default_registry() -> ToolRegistry:
    """Read-only tools: file/search/git-status/doctor + git diff/log (auto)."""
    return register_git_read(register_readonly(ToolRegistry()))


def write_registry() -> ToolRegistry:
    """Read-only tools + the gated action tools (file_write L2; git commit L3;
    git push / repo create L5). The extra levels are approval-gated by policy —
    registering them only makes them proposable, never auto-run."""
    registry = register_git_read(register_readonly(ToolRegistry()))
    register_write(registry)
    register_git_actions(registry)
    return registry


def full_registry() -> ToolRegistry:
    """Every governed tool, incl. HPC (submit L5), MCP (call L4), and the L6
    self_install boundary. Every L3+ stays approval-gated; self_install is
    additionally always refused, so the model can never modify the running app."""
    registry = write_registry()
    register_hpc(registry)
    register_mcp(registry)
    register_self_improve(registry)
    return registry


@dataclass(frozen=True)
class ToolResult:
    #: succeeded | failed | refused | needs_approval
    status: str
    output: dict = field(default_factory=dict)
    reason: str = ""
    result_sha256: str = ""
    tool: str = ""
    #: ledger digests appended for this call, oldest first (call, decision, result).
    evidence: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "succeeded"


@dataclass
class ToolBroker:
    registry: ToolRegistry
    ledger: EvidenceLedger

    def execute(self, request: dict, token: CapabilityToken, *,
                cfg: Config, run_id: str, now_epoch: float) -> ToolResult:
        tool = str((request or {}).get("tool", ""))
        args = (request or {}).get("args", {}) or {}
        if not isinstance(args, dict):
            args = {}
        args_sha = digest({"tool": tool, "args": args})
        appended: list[str] = []
        appended.append(self.ledger.append(
            "tool_call", run_id=run_id,
            payload={"tool": tool, "args_sha256": args_sha}))

        spec = self.registry.get(tool)
        if spec is None:
            appended.append(self.ledger.append(
                "decision", run_id=run_id,
                payload={"tool": tool, "allow": False, "level": None,
                         "reason": "tool is not registered"}))
            return ToolResult("refused", reason=f"unknown tool {tool!r}",
                              tool=tool, evidence=tuple(appended))

        proposal = {
            "tool": tool, "level": spec.level, "writes": spec.writes,
            "paths": [str(args[k]) for k in spec.path_args if args.get(k)],
            "host": (str(args.get(spec.host_arg, "")) if spec.host_arg else ""),
            "estimated_cost_usd": spec.est_cost_usd,
            "estimated_bytes": spec.est_bytes,
        }
        d = decide(proposal, token, now_epoch=now_epoch)
        appended.append(self.ledger.append(
            "decision", run_id=run_id,
            payload={"tool": tool, "allow": d.allow, "level": d.level,
                     "requires_approval": d.requires_approval, "reason": d.reason,
                     "run_id": run_id, "project_id": token.project_id}))
        if not d.allow:
            return ToolResult("refused", reason=d.reason, tool=tool,
                              evidence=tuple(appended))
        if d.requires_approval:
            # Policy flagged this for approval; the Approval Service decides from
            # an explicit, user-granted authorization (never a loosened policy).
            approval = approve(proposal, d, cfg)
            appended.append(self.ledger.append(
                "approval", run_id=run_id,
                payload={"tool": tool, "granted": approval.granted,
                         "reason": approval.reason, "level": d.level}))
            if not approval.granted:
                return ToolResult("needs_approval", reason=approval.reason,
                                  tool=tool, evidence=tuple(appended))
            # Granted by a standing project authorization → proceed to execute.

        try:
            output = spec.handler(cfg, args, token)
            if not isinstance(output, dict):
                output = {"value": output}
            status, reason = "succeeded", "ok"
        except ToolError as exc:
            output, status, reason = {"error": exc.reason}, "failed", exc.reason
        except Exception as exc:  # noqa: BLE001 -- a tool bug must not crash the broker
            output = {"error": f"tool raised {type(exc).__name__}"}
            status, reason = "failed", str(exc)[:200]
        result_sha = digest(output)
        # Only the tool's declared safe fields (hashes/metadata) enter the
        # ledger — a write's before/after hashes become auditable, a read's raw
        # bytes never do.
        safe = {k: output[k] for k in spec.evidence_fields if k in output}
        appended.append(self.ledger.append(
            "tool_result", run_id=run_id,
            payload={"tool": tool, "status": status, "result_sha256": result_sha,
                     **safe}))
        return ToolResult(status, output=output, reason=reason,
                          result_sha256=result_sha, tool=tool,
                          evidence=tuple(appended))
