"""Level-3 run_check: allowlisted, no-shell, bounded, secret-scrubbed, approval-gated.

The mechanism is proven directly (only allowlisted executables run, as argv with
no shell expansion, with a scrubbed environment); and via the broker it is never
auto-run — even a fully write-authorized project must give a per-call human yes
for a command, so command execution never happens silently.
"""
from __future__ import annotations

import hashlib
import sys

import pytest

from crossaudit.broker import ToolBroker
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.registry import ToolError, ToolRegistry
from crossaudit.broker.tools_command import register_command, run_check
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _tok():
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["run_check"],
        "paths": ["**"], "expires_at": "2100-01-01T00:00:00Z"})


def test_runs_an_allowlisted_command_and_hashes_output(cfg):
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    r = run_check(cfg, {"command": [sys.executable, "-c", "print('hi')"]}, _tok())
    assert r["exit_code"] == 0 and r["stdout_tail"] == "hi\n"
    assert r["stdout_sha256"] == hashlib.sha256(b"hi\n").hexdigest()
    assert r["command"][0] == sys.executable


def test_refuses_a_command_not_on_the_allowlist(cfg):
    AuthorizationStore(cfg).set_list("allowed_commands", ["only-this"])
    with pytest.raises(ToolError):
        run_check(cfg, {"command": ["/bin/echo", "hi"]}, _tok())   # never runs


def test_refuses_when_no_allowlist(cfg):
    with pytest.raises(ToolError):
        run_check(cfg, {"command": [sys.executable, "-c", "print(1)"]}, _tok())


def test_scrubs_secret_env_but_keeps_plain(cfg, monkeypatch):
    monkeypatch.setenv("MY_SECRET_KEY", "xyz")
    monkeypatch.setenv("MY_PLAIN", "ok")
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    r = run_check(cfg, {"command": [sys.executable, "-c",
                  "import os;print(os.environ.get('MY_SECRET_KEY','ABSENT'),"
                  "os.environ.get('MY_PLAIN','ABSENT'))"]}, _tok())
    assert "ABSENT ok" in r["stdout_tail"]     # secret dropped, plain preserved


def test_no_shell_expansion(cfg):
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    r = run_check(cfg, {"command": [sys.executable, "-c", "print('a;b|c')"]}, _tok())
    assert "a;b|c" in r["stdout_tail"]         # metacharacters are literal


def test_broker_never_auto_runs_level3(cfg, tmp_path):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)      # even fully authorized
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    broker = ToolBroker(register_command(ToolRegistry()),
                        EvidenceLedger(tmp_path / "ev.jsonl"))
    marker = cfg.root / "ran.txt"
    r = broker.execute(
        {"tool": "run_check", "args": {"command": [
            sys.executable, "-c", f"open({str(marker)!r},'w').write('x')"]}},
        _tok(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"        # command never ran
    assert not marker.exists()
