"""Phase 2 Level-3 command tool — run an allowed project check, safely.

``run_check`` runs ONLY a command whose executable the user put on this
project's allowlist, as an argv list (never a shell string, so metacharacters
can't chain or expand), in the project root, with a wall-time and output cap and
a secret-scrubbed environment. It is Level 3: the Approval Service never
auto-grants it (project write-authorization covers Level-2 writes only), so the
broker returns ``needs_approval`` until a per-call human yes. Only the command,
exit code, and output hashes are recorded as evidence — never the raw output.
"""
from __future__ import annotations

import hashlib
import os
import subprocess

from ..config import Config
from ..policy.tokens import CapabilityToken
from .approval import AuthorizationStore
from .registry import ToolError, ToolRegistry, ToolSpec

MAX_RUNTIME_S = 120
MAX_OUTPUT_BYTES = 256 * 1024
_TAIL = 4000
#: Env var name fragments whose values are stripped before a command runs.
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CRED", "PASSWD")
ALLOWED_COMMANDS_KEY = "allowed_commands"


def command_allowlist(cfg: Config) -> list[str]:
    """Executables (argv[0]) the user approved for this project (default none)."""
    value = AuthorizationStore(cfg).load().get(ALLOWED_COMMANDS_KEY)
    return [str(c) for c in value if isinstance(c, str)] if isinstance(value, list) else []


def _scrubbed_env() -> dict:
    return {k: v for k, v in os.environ.items()
            if not any(h in k.upper() for h in _SECRET_HINTS)}


def run_check(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    """Run one allowlisted check command (argv list, no shell) and hash its output."""
    argv = args.get("command")
    if (not isinstance(argv, list) or not argv
            or not all(isinstance(a, str) and a for a in argv)):
        raise ToolError("run_check needs 'command' as a non-empty list of argv strings")
    if argv[0] not in command_allowlist(cfg):
        raise ToolError(f"command {argv[0]!r} is not in this project's allowed commands")
    try:
        proc = subprocess.run(                       # a LIST → shell=False, no expansion
            argv, cwd=str(cfg.root), env=_scrubbed_env(),
            capture_output=True, text=True, timeout=MAX_RUNTIME_S)
    except subprocess.TimeoutExpired:
        raise ToolError(f"command exceeded the {MAX_RUNTIME_S}s time limit")
    except OSError as exc:
        raise ToolError(f"command could not run: {exc}")
    out = (proc.stdout or "")[:MAX_OUTPUT_BYTES]
    err = (proc.stderr or "")[:MAX_OUTPUT_BYTES]
    return {
        "command": argv,
        "exit_code": proc.returncode,
        "stdout_sha256": hashlib.sha256(out.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(err.encode("utf-8")).hexdigest(),
        # bounded tails go back to the generator as untrusted context, not the ledger
        "stdout_tail": out[-_TAIL:],
        "stderr_tail": err[-_TAIL:],
    }


def run_check_preview(cfg: Config, args: dict) -> str:
    """The exact command line that would run, for the approval card."""
    argv = args.get("command")
    if isinstance(argv, list) and argv:
        return "run: " + " ".join(str(a) for a in argv)
    return "run: (invalid command)"


def register_command(registry: ToolRegistry) -> ToolRegistry:
    """Register the Level-3 run_check tool (always per-call approval-gated)."""
    registry.register(ToolSpec(
        name="run_check", level=3, writes=False, needs_network=False,
        handler=run_check,
        evidence_fields=("command", "exit_code", "stdout_sha256", "stderr_sha256"),
        preview=run_check_preview,
        summary="Run an approved project check command (test/build/format). Needs approval."))
    return registry
