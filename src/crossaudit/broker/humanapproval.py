"""Per-call human approval — the real-time gate that makes Level 3+ usable.

The policy engine flags every write/command (level >= 2) as ``needs_approval``,
and the standing project authorization (``approval.approve``) grants only Level-2
*recoverable* workspace writes. Every Level 3+ action — a local command, and every
Level 4+ network / high-impact action — still needs an explicit human yes.

This module is that seam. While a build is live, a flagged proposal PAUSES in
place: a pending-action card appears in the thread (what / why / scope /
reversibility / cost), the worker keeps its run alive (heartbeating), and the
user's decision — recorded to the evidence ledger as the grant — either lets the
*same* worker continue immediately or refuses the action. This is the
"like Claude Code" real-time approval the user chose.

Invariants preserved:

* **Deny-by-default.** No decision, a walked-away user past the wait window, or a
  cancelled run all resolve to *deny* — the action does not run.
* **Permission comes from the human, never the model.** The gate reads a decision
  the user made in the UI; the model cannot mint or widen it.
* **Level 4+ is always per-call.** "Allow this run" / "Allow this project" are
  offered only up to Level 3; a Level 4+ action re-prompts every single call, so
  a high-impact action can never be granted standing approval.
* **Level 6 (self-install) is refused without even prompting** — the handler also
  always refuses, so the model can never modify the running app.

The inbox is process-global and thread-safe: the build worker thread blocks in
``wait`` while the console's HTTP thread calls ``resolve`` from the approval
endpoint. Both share one ``threading.Condition``.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from ..config import Config
from .approval import Approval, AuthorizationStore, approve

#: Decision scopes a user may pick for a pending action.
ONCE = "once"
RUN = "run"
PROJECT = "project"
DENY = "deny"
_SCOPES = frozenset({ONCE, RUN, PROJECT, DENY})

#: Above this level a grant can never be standing: every call re-prompts, so
#: "allow this run" / "allow this project" are not offered and are ignored if
#: forged. (Level 3 local commands may be granted for a run/project; Level 4+
#: network / high-impact / destructive may not.)
PER_CALL_ONLY_LEVEL = 4

#: A worker will not block forever for a human who walked away: after this many
#: seconds with no decision the action is denied (deny-by-default) and the build
#: continues without it. Generous because approval is interactive.
DEFAULT_WAIT_SECONDS = 1800.0
#: How often the blocked worker wakes to heartbeat its run and re-check cancel.
POLL_SECONDS = 1.0


def reversibility(level: int, writes: bool) -> str:
    """A short, human phrase describing how reversible a proposed action is."""
    if level <= 1 and not writes:
        return "no change — reads only"
    if level == 2:
        return "reversible — a recovery point is saved before the edit"
    if level == 3:
        return "runs a local command; effects are not automatically undone"
    if level == 4:
        return "reaches the network; may have off-machine effects"
    if level == 5:
        return "high-impact — not easily reversible"
    return "destructive / forbidden"


@dataclass(frozen=True)
class PendingApproval:
    """One flagged action awaiting the user's decision, for the pending card."""
    run_id: str
    tool: str
    level: int
    writes: bool
    paths: tuple[str, ...] = ()
    host: str = ""
    cost_usd: float = 0.0
    bytes: int = 0
    reason: str = ""
    #: a bounded, human-readable preview of the action (diff/command/message),
    #: shown on the card only — never logged or ledgered.
    preview: str = ""
    created: float = 0.0

    @property
    def per_call_only(self) -> bool:
        return self.level >= PER_CALL_ONLY_LEVEL

    def scopes(self) -> list[str]:
        """The decision buttons to offer (run/project hidden for Level 4+)."""
        if self.per_call_only:
            return [ONCE, DENY]
        return [ONCE, RUN, PROJECT, DENY]

    def to_view(self) -> dict:
        return {
            "run_id": self.run_id,
            "tool": self.tool,
            "level": self.level,
            "writes": self.writes,
            "paths": list(self.paths),
            "host": self.host,
            "cost_usd": self.cost_usd,
            "bytes": self.bytes,
            "reason": self.reason,
            "preview": self.preview,
            "reversibility": reversibility(self.level, self.writes),
            "created": self.created,
            "scopes": self.scopes(),
        }


@dataclass
class _Resolved:
    scope: str
    reason: str


class ApprovalInbox:
    """Process-global registry of pending approvals + their decisions.

    Thread-safe. The build worker registers a pending action and blocks in
    ``wait``; the HTTP thread delivers the user's choice through ``resolve``.
    A per-run grant remembers a tool approved "for this run" so a second
    proposal of the same tool in the same run does not re-prompt.
    """

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._cond = threading.Condition()
        self._pending: dict[str, PendingApproval] = {}
        self._decisions: dict[str, _Resolved] = {}
        self._run_grants: set[tuple[str, str]] = set()

    def now(self) -> float:
        """The inbox's clock (injectable), for stamping a pending action."""
        return self._clock()

    # -- worker side ----------------------------------------------------------
    def run_granted(self, run_id: str, tool: str) -> bool:
        with self._cond:
            return (run_id, tool) in self._run_grants

    def grant_run(self, run_id: str, tool: str) -> None:
        with self._cond:
            self._run_grants.add((run_id, tool))

    def open(self, pending: PendingApproval) -> None:
        """Register a pending action so the UI can render its card."""
        with self._cond:
            self._decisions.pop(pending.run_id, None)
            self._pending[pending.run_id] = pending
            self._cond.notify_all()

    def wait(self, run_id: str, *,
             heartbeat: Callable[[], None] | None = None,
             is_cancelled: Callable[[], bool] | None = None,
             timeout: float = DEFAULT_WAIT_SECONDS,
             poll: float = POLL_SECONDS) -> _Resolved:
        """Block until the user decides, the run is cancelled, or the wait
        window elapses. Deny-by-default on cancel/timeout."""
        deadline = self._clock() + max(0.0, float(timeout))
        try:
            while True:
                if is_cancelled is not None and is_cancelled():
                    return _Resolved(DENY, "the run was stopped before approval")
                with self._cond:
                    decided = self._decisions.pop(run_id, None)
                    if decided is not None:
                        self._pending.pop(run_id, None)
                        return decided
                    if self._clock() >= deadline:
                        self._pending.pop(run_id, None)
                        return _Resolved(
                            DENY, "no approval was given within the wait window")
                    self._cond.wait(min(float(poll), max(0.0, deadline - self._clock())))
                if heartbeat is not None:
                    heartbeat()
        finally:
            with self._cond:
                self._pending.pop(run_id, None)

    # -- HTTP side ------------------------------------------------------------
    def resolve(self, run_id: str, scope: str, *, reason: str = "") -> bool:
        """Deliver the user's decision to the waiting worker. Returns whether a
        matching pending action was resolved."""
        scope = str(scope)
        if scope not in _SCOPES:
            return False
        with self._cond:
            if run_id not in self._pending:
                return False
            self._decisions[run_id] = _Resolved(scope, reason or f"user chose {scope}")
            self._cond.notify_all()
            return True

    def cancel(self, run_id: str) -> None:
        """Drop any pending action for a run (e.g. it was stopped)."""
        with self._cond:
            self._pending.pop(run_id, None)
            self._decisions[run_id] = _Resolved(DENY, "the run was stopped")
            self._cond.notify_all()

    def pending(self, run_id: str) -> dict | None:
        with self._cond:
            p = self._pending.get(run_id)
            return p.to_view() if p is not None else None

    def pending_any(self) -> dict | None:
        with self._cond:
            for p in self._pending.values():
                return p.to_view()
            return None


#: The one inbox the live build worker and the HTTP endpoint share.
INBOX = ApprovalInbox()


@dataclass
class HumanApprovalGate:
    """The broker's approver for a live build: standing authorization first, then
    a real-time human decision for anything still flagged.

    Bound per-run so it can heartbeat the run and observe cancellation while it
    blocks. Injecting ``inbox`` (and, in tests, ``heartbeat``/``is_cancelled``)
    keeps this deterministic without real threads.
    """
    inbox: ApprovalInbox = field(default_factory=lambda: INBOX)
    heartbeat: Callable[[], None] | None = None
    is_cancelled: Callable[[], bool] | None = None
    wait_seconds: float = DEFAULT_WAIT_SECONDS

    def __call__(self, proposal: dict, decision, cfg: Config,
                 run_id: str) -> Approval:
        # 1) A standing project authorization (e.g. Level-2 recoverable writes)
        #    grants without prompting — existing behavior, unchanged.
        standing = approve(proposal, decision, cfg)
        if standing.granted:
            return standing

        level = int(getattr(decision, "level", proposal.get("level", 0)) or 0)
        tool = str(proposal.get("tool", ""))

        # 2) Level 6 (self-install) is refused outright — never prompt. The
        #    handler also always refuses, so the app can never self-modify.
        if level >= 6:
            return Approval(False, "installing/replacing the running app is forbidden")

        # 3) A grant the user already made — for this run, or standing for this
        #    project — short-circuits (never for Level 4+, which are per-call).
        if level < PER_CALL_ONLY_LEVEL:
            if self.inbox.run_granted(run_id, tool):
                return Approval(True, "approved for this run by the user")
            if AuthorizationStore(cfg).authorized_tool(tool):
                return Approval(True, "approved for this project by the user")

        # 4) Otherwise, pause and ask the user in real time.
        pending = PendingApproval(
            run_id=run_id, tool=tool, level=level,
            writes=bool(proposal.get("writes")),
            paths=tuple(str(p) for p in (proposal.get("paths") or ())),
            host=str(proposal.get("host", "") or ""),
            cost_usd=float(proposal.get("estimated_cost_usd", 0.0) or 0.0),
            bytes=int(proposal.get("estimated_bytes", 0) or 0),
            reason=str(getattr(decision, "reason", "") or ""),
            preview=str(proposal.get("preview", "") or ""),
            created=self.inbox.now(),
        )
        self.inbox.open(pending)
        decided = self.inbox.wait(
            run_id, heartbeat=self.heartbeat, is_cancelled=self.is_cancelled,
            timeout=self.wait_seconds)

        if decided.scope == DENY:
            return Approval(False, decided.reason)
        # Record standing grants the user asked for. Level 4+ never persists a
        # scope: even if the payload says run/project, it is treated as once.
        if level < PER_CALL_ONLY_LEVEL:
            if decided.scope == RUN:
                self.inbox.grant_run(run_id, tool)
            elif decided.scope == PROJECT:
                AuthorizationStore(cfg).add_tool(tool)
        return Approval(True, decided.reason)
