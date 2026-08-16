"""Phase 5 MCP tools — the existing mcp.MANAGER, behind the broker.

Calling an owner-approved MCP tool can write or reach the network, so ``mcp_call``
is Level 4 and always ``needs_approval``; the broker never auto-invokes an
external MCP server, and the build never calls one. The ledger records only the
call's result hash — never the raw tool output.
"""
from __future__ import annotations

from .. import mcp
from ..config import Config
from ..policy.tokens import CapabilityToken
from .registry import ToolError, ToolRegistry, ToolSpec


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
