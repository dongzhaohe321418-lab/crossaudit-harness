"""run_check reports orthogonal command outcomes (DeepSeek defensive-pattern R1).

A command can exit cleanly, be killed by a signal, or time out — each is its own
independent fact (`exit_code` / `signal` / `timed_out`), never collapsed into
another. This keeps the generator and the audit from reading a signal-kill or a
cut-short run as a plain exit code.
"""
from __future__ import annotations

from types import SimpleNamespace

from crossaudit.broker import tools_command


def _run(monkeypatch, tmp_path, argv, *, timeout=None):
    monkeypatch.setattr(tools_command, "command_allowlist", lambda cfg: [argv[0]])
    if timeout is not None:
        monkeypatch.setattr(tools_command, "MAX_RUNTIME_S", timeout)
    cfg = SimpleNamespace(root=tmp_path)
    return tools_command.run_check(cfg, {"command": argv}, None)


def test_clean_nonzero_exit_reports_exit_code_only(monkeypatch, tmp_path):
    r = _run(monkeypatch, tmp_path, ["sh", "-c", "exit 3"])
    assert r["exit_code"] == 3
    assert r["signal"] is None
    assert r["timed_out"] is False


def test_signal_kill_reports_signal_not_a_bogus_exit_code(monkeypatch, tmp_path):
    r = _run(monkeypatch, tmp_path, ["sh", "-c", "kill -9 $$"])
    assert r["signal"] == 9          # surfaced as a signal, not exit_code -9
    assert r["exit_code"] is None
    assert r["timed_out"] is False


def test_timeout_is_a_structured_outcome_not_an_opaque_error(monkeypatch, tmp_path):
    r = _run(monkeypatch, tmp_path, ["sh", "-c", "sleep 5"], timeout=1)
    assert r["timed_out"] is True    # a real, auditable outcome — not a raise
    assert r["exit_code"] is None
    assert r["signal"] is None
    # still hashes whatever partial output there was
    assert len(r["stdout_sha256"]) == 64


def test_evidence_fields_carry_the_orthogonal_outcomes(monkeypatch, tmp_path):
    # The audit ledger must record the outcome facts, not just an exit code.
    from crossaudit.broker.registry import ToolRegistry
    reg = tools_command.register_command(ToolRegistry())
    spec = reg.get("run_check")
    for field in ("exit_code", "signal", "timed_out"):
        assert field in spec.evidence_fields
