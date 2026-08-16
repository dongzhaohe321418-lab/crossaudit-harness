"""The deterministic capability decision.

``decide`` is the one place that says yes or no to a proposed action, and it
consults only the proposal and the token — never a model. It fails closed: an
expired grant, an unlisted tool, an out-of-scope path, a write under a
read-only grant, an unlisted network host, or a ceiling breach is denied with a
specific reason. Actions above the auto-run tier (level >= 2) are permitted by
scope but flagged ``requires_approval`` so the broker routes them to the
Approval Service before anything runs; Phase 1 issues only level 0-1 (read-only)
grants, so that path stays dormant until Phase 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tokens import CapabilityToken

#: Permission levels (guide §4): 0 inference · 1 read-only · 2 recoverable
#: workspace edit · 3 local command · 4 network/external · 5 high-impact ·
#: 6 destructive. Level >= this needs explicit human approval per call.
APPROVAL_MIN_LEVEL = 2


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    level: int = 0
    requires_approval: bool = False

    @property
    def auto(self) -> bool:
        """Runnable now with no human in the loop."""
        return self.allow and not self.requires_approval


def _deny(reason: str, level: int) -> Decision:
    return Decision(allow=False, reason=reason, level=level, requires_approval=False)


def decide(proposal: Any, token: CapabilityToken, *, now_epoch: float) -> Decision:
    """Decide one proposed action against a capability token.

    ``proposal`` is a normalized dict from the broker/registry:
    ``{tool, level, writes, paths[], host, estimated_cost_usd, estimated_bytes}``.
    """
    if not isinstance(proposal, dict):
        return _deny("proposal must be a mapping", 0)
    tool = str(proposal.get("tool", ""))
    level = int(proposal.get("level", 0) or 0)

    if token.expired(now_epoch):
        return _deny("the capability grant has expired", level)
    if not token.allows_tool(tool):
        return _deny(f"tool {tool!r} is not in this grant", level)
    if bool(proposal.get("writes")) and not token.writable:
        return _deny(f"tool {tool!r} would write, but this grant is read-only", level)
    for p in proposal.get("paths", []) or []:
        if not token.allows_path(str(p)):
            return _deny(f"path {str(p)!r} is outside this grant's scope", level)
    host = str(proposal.get("host", "") or "")
    if host:
        if not token.network_allowed():
            return _deny("this grant permits no network access", level)
        if not token.allows_host(host):
            return _deny(f"host {host!r} is not in this grant", level)
    if not token.within_cost(float(proposal.get("estimated_cost_usd", 0) or 0)):
        return _deny("estimated cost exceeds this grant's ceiling", level)
    if not token.within_bytes(int(proposal.get("estimated_bytes", 0) or 0)):
        return _deny("estimated transfer exceeds this grant's ceiling", level)

    requires_approval = level >= APPROVAL_MIN_LEVEL
    reason = ("within grant; needs approval before running"
              if requires_approval else "within grant; auto-approved")
    return Decision(allow=True, reason=reason, level=level,
                    requires_approval=requires_approval)
