"""The Approval Service — turns a policy ``needs_approval`` into a real decision.

The policy engine deliberately flags every write/command (level >= 2) as needing
approval; it never loosens that on its own. Approval comes from here, and only
from an *explicit, inspectable* source:

* a per-project authorization the user turned on (``workspace_writes``) grants
  standing approval for Level-2 *recoverable* workspace writes — the "project
  level authorization, like Claude Code" model the user chose;
* everything else — level 3 commands, and every level 4+ network / high-impact /
  destructive action — always needs a per-call human approval it cannot inherit.

So a write still requires: a writable capability token (scope), a recovery point,
an evidence-ledger record, an Auditor review — AND this standing authorization
the user explicitly granted. Absent the authorization, the broker surfaces the
proposal for a per-call decision; it never writes silently.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..config import Config

#: Authorization key: the user allowed recoverable file edits in this project.
WORKSPACE_WRITES = "workspace_writes"

#: Authorization key: a list of tool names the user approved "for this project"
#: from a per-call approval card (e.g. ``run_check``, ``git_commit``). Only tools
#: below Level 4 may be added — Level 4+ is always per-call and never persisted.
APPROVED_TOOLS = "approved_tools"

AUTHORIZATIONS_FILE = "authorizations.json"


@dataclass(frozen=True)
class Approval:
    granted: bool
    reason: str


@dataclass
class AuthorizationStore:
    """Per-project standing authorizations the user has explicitly granted."""

    cfg: Config

    @property
    def path(self) -> Path:
        return self.cfg.root / self.cfg.state_dir / AUTHORIZATIONS_FILE

    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, ValueError):
            return {}

    def authorized(self, key: str) -> bool:
        return bool(self.load().get(key))

    def _persist(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".tmp{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def set(self, key: str, value: bool) -> None:
        """Record a user's explicit grant/revoke (called by the settings UI)."""
        data = self.load()
        data[str(key)] = bool(value)
        self._persist(data)

    def set_list(self, key: str, values) -> None:
        """Record a per-project string list the user approved (e.g. check commands)."""
        data = self.load()
        data[str(key)] = [str(v) for v in values]
        self._persist(data)

    def authorized_tool(self, tool: str) -> bool:
        """Whether the user approved this tool "for this project" from a card."""
        value = self.load().get(APPROVED_TOOLS)
        return isinstance(value, list) and str(tool) in value

    def add_tool(self, tool: str) -> None:
        """Persist a tool the user approved "for this project" (idempotent)."""
        data = self.load()
        current = data.get(APPROVED_TOOLS)
        current = [str(v) for v in current] if isinstance(current, list) else []
        if str(tool) not in current:
            current.append(str(tool))
        data[APPROVED_TOOLS] = current
        self._persist(data)


def approve(proposal: dict, decision, cfg: Config) -> Approval:
    """Decide a proposal the policy engine flagged ``requires_approval``.

    Only a Level-2 *recoverable write*, in a project whose user turned on
    ``workspace_writes``, is granted standing approval. Level 3+ and every
    Level 4+ action is never auto-approved here — it needs a per-call human yes.
    """
    level = int(getattr(decision, "level", proposal.get("level", 0)) or 0)
    if (level == 2 and bool(proposal.get("writes"))
            and AuthorizationStore(cfg).authorized(WORKSPACE_WRITES)):
        return Approval(True, "project authorized recoverable workspace writes")
    if level >= 4:
        return Approval(False, "high-impact action requires explicit per-call approval")
    return Approval(False, "no standing authorization; needs explicit approval")
