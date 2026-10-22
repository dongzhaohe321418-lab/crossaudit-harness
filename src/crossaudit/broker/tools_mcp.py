"""MCP tools behind the broker: the one place an MCP call is ledgered.

There are two ways an MCP tool can be reached, and both are recorded here.

* The Generator's tool requests during a build (``cli/build.py``) and every
  console chat (which runs the same build loop) go through ``governed_mcp_call``.
  Their approval is the owner's: a person registered the server, approved the
  exact local command, and selected each allowed tool; ``mcp.Manager`` enforces
  that allowlist and the per-task call budget. Before the call runs, the
  evidence ledger receives a ``tool_call`` entry (server, tool, argument hash,
  allowlist state, budget position); after it, a ``tool_result`` entry
  (status, result hash, byte count, truncation, duration). If the ledger
  refuses either append, the call fails closed with its ``IntegrityDenial``:
  the first refusal means the tool never runs, the second means its result is
  never handed back to the Generator (D174).
* ``mcp_call`` is a registered broker tool (Level 4, ``needs_approval``) in
  ``full_registry`` only. No build offers it; the broker never auto-invokes an
  external MCP server, and a call through it needs a per-call human approval.

The ledger records only hashes and metadata — never the arguments or the raw
tool output, which reach only the Generator (bounded) and, for the request the
Generator streamed, the project-private run journal.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from .. import mcp
from ..config import Config
from ..errors import ConfigDenial, Denial
from ..policy.tokens import CapabilityToken
from .registry import ToolError, ToolRegistry, ToolSpec

#: The ledger's ``tool`` value for every MCP call, so the audit panel and the
#: Auditor's evidence view group them with the registered broker tool.
LEDGER_TOOL = "mcp_call"
#: The approval a build-path call carries: the owner's per-tool allowlist.
OWNER_ALLOWLIST = "owner_allowlist"


def mcp_call(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    request = args.get("request") if isinstance(args.get("request"), dict) else args
    if not isinstance(request, dict) or not request.get("server_id") or not request.get("tool"):
        raise ToolError("mcp_call needs a request with 'server_id' and 'tool'")
    return mcp.MANAGER.call_agent(cfg, request)


def register_mcp(registry: ToolRegistry) -> ToolRegistry:
    registry.register(ToolSpec(
        name="mcp_call", level=4, writes=True, needs_network=True,
        handler=mcp_call,
        summary="Call an owner-approved MCP tool (always needs approval)."))
    return registry


def _safe_ids(request) -> tuple[str, str]:
    """The server id and tool name, only when they have the registered shapes;
    a model-supplied string that does not is recorded as empty, not copied."""
    req = request if isinstance(request, dict) else {}
    server_id = str(req.get("server_id", ""))
    tool = str(req.get("tool", ""))
    return (server_id if mcp.SERVER_ID.fullmatch(server_id) else "",
            tool if mcp.TOOL_NAME.fullmatch(tool) else "")


def governed_mcp_call(cfg: Config, request: dict, *, ledger, run_id: str,
                      chat_id: str = "", ordinal: int = 1,
                      notify: Callable[[str, str], None] | None = None) -> dict:
    """Run one Generator MCP request under the owner's policy, ledgered.

    Returns what ``mcp.Manager.call_agent`` returns. Raises its ``ConfigDenial``
    for a refused or failed call (after recording it), and the ledger's
    ``IntegrityDenial`` if an append is refused — which a caller must not
    soften into a refused tool result.
    """
    try:
        grant = mcp.MANAGER.authorize(cfg, request, ordinal=ordinal)
    except ConfigDenial as exc:
        server_id, tool = _safe_ids(request)
        ledger.append("tool_call", run_id=run_id, payload={
            "tool": LEDGER_TOOL, "server_id": server_id, "mcp_tool": tool,
            "args_sha256": "", "approval": OWNER_ALLOWLIST, "allowlisted": False,
            "call_ordinal": int(ordinal), "call_budget": None})
        # The reason is the policy's own sentence (no tool ran, so it carries
        # no tool output).
        ledger.append("tool_result", run_id=run_id, payload={
            "tool": LEDGER_TOOL, "server_id": server_id, "mcp_tool": tool,
            "status": "refused", "reason": exc.reason[:300], "result_sha256": "",
            "bytes": 0, "truncated": False, "duration_ms": 0})
        raise
    server_id, tool = grant["server"]["id"], grant["tool"]
    ledger.append("tool_call", run_id=run_id, payload={
        "tool": LEDGER_TOOL, "server_id": server_id, "mcp_tool": tool,
        "args_sha256": grant["arguments_sha256"], "approval": OWNER_ALLOWLIST,
        "allowlisted": True, "allowlist_sha256": grant["allowlist_sha256"],
        "call_ordinal": grant["call_ordinal"], "call_budget": grant["call_budget"]})
    started = time.monotonic()
    try:
        result = mcp.MANAGER.call_agent(cfg, request, chat_id=chat_id,
                                        ordinal=ordinal, notify=notify)
    except Denial:
        # A transport or protocol failure: its reason can quote the server's
        # stderr, so only the status is recorded.
        ledger.append("tool_result", run_id=run_id, payload={
            "tool": LEDGER_TOOL, "server_id": server_id, "mcp_tool": tool,
            "status": "failed", "result_sha256": "", "bytes": 0,
            "truncated": False,
            "duration_ms": int((time.monotonic() - started) * 1000)})
        raise
    facts = mcp.result_evidence(result)
    ledger.append("tool_result", run_id=run_id, payload={
        "tool": LEDGER_TOOL, "server_id": server_id, "mcp_tool": tool,
        "call_id": str(result.get("call_id", "")),
        "status": str(result.get("status", "")), **facts,
        "duration_ms": int((time.monotonic() - started) * 1000)})
    return result
