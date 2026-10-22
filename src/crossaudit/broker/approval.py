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
import secrets
import threading
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

#: Serialises every load -> modify -> persist of an authorizations file in this
#: process (D169). Without it a build thread approving a tool "for this
#: project" and the settings UI revoking `workspace_writes` each read the old
#: file and the later write erased the earlier one -- a lost revoke is
#: fail-open. One lock for every project: writes are rare and tiny, and a
#: per-path lock table would be one more thing to get wrong.
_LOCK = threading.Lock()


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
        # A random temp name per write (as mcp._write does): the old
        # `.tmp<pid>` was shared by every thread of the process, so one
        # thread's os.replace consumed another's file mid-write.
        tmp = self.path.with_name(f"{self.path.name}.tmp{secrets.token_hex(8)}")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def _update(self, change) -> None:
        """Apply ``change(data)`` to the stored mapping under the module lock."""
        with _LOCK:
            data = self.load()
            change(data)
            self._persist(data)

    def set(self, key: str, value: bool) -> None:
        """Record a user's explicit grant/revoke (called by the settings UI)."""
        self._update(lambda data: data.__setitem__(str(key), bool(value)))

    def set_list(self, key: str, values) -> None:
        """Record a per-project string list the user approved (e.g. check commands)."""
        items = [str(v) for v in values]
        self._update(lambda data: data.__setitem__(str(key), items))

    def authorized_tool(self, tool: str) -> bool:
        """Whether the user approved this tool "for this project" from a card."""
        value = self.load().get(APPROVED_TOOLS)
        return isinstance(value, list) and str(tool) in value

    def add_tool(self, tool: str) -> None:
        """Persist a tool the user approved "for this project" (idempotent)."""
        def change(data: dict) -> None:
            current = data.get(APPROVED_TOOLS)
            current = [str(v) for v in current] if isinstance(current, list) else []
            if str(tool) not in current:
                current.append(str(tool))
            data[APPROVED_TOOLS] = current

        self._update(change)


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
