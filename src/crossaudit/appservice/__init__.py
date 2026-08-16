"""The neutral Application Service.

Phase 0 found the console reaching *up* into ``cli.*`` (``server.py`` imported
``cli.build``/``cli.talk`` directly), so the CLI and UI shared execution by
coincidence, not by contract. This module is the single seam both call into: it
re-exports the one build loop (never a second copy) and surfaces the Tool Broker
wiring (which lives in ``broker.routing`` so this seam and ``cli.build`` share it
without an import cycle), so every entry point governs tool use the same way.

Phase 1 keeps ``run_loop`` living in ``cli.build`` and re-exports it here to fix
the *direction* of the dependency (console → appservice, not console → cli); the
full move of ``run_loop`` into this layer is a Phase-2 refactor tracked in
docs/AGENTIC_RUNTIME_PROGRESS.md.
"""
from __future__ import annotations

from ..broker import default_registry
# Broker/ledger wiring — cli-free, so cli.build imports the same helpers.
from ..broker.routing import (  # noqa: F401
    BROKER_SERVER_ID, READONLY_TOOLS, broker_for, broker_tool_call,
    evidence_path, readonly_token)
# The one build loop + task helpers, surfaced as the shared service API. Both
# cli and console import these from here so neither owns a private copy.
from ..cli.build import preflight, resolve_task, run_loop  # noqa: E402,F401
from ..cli import talk  # noqa: E402,F401  (module re-export)

__all__ = [
    "preflight", "resolve_task", "run_loop", "talk",
    "evidence_path", "broker_for", "readonly_tool_catalog",
    "BROKER_SERVER_ID", "READONLY_TOOLS", "broker_tool_call", "readonly_token",
]


def readonly_tool_catalog() -> list[dict]:
    """The read-only tools the model may propose in Phase 1 (name/level/scope)."""
    return default_registry().catalog()
