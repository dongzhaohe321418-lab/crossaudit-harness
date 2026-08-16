"""Phase 3 git tools: read-only auto, commit/push/repo approval-gated & never fired.

git_diff/git_log auto-run like git_status. git_commit (L3), git_push and
repo_create (L5) are never auto-run — the broker returns needs_approval, so no
commit, push, or repo creation happens without an explicit human yes. Deleting a
repo is not offered at all.
"""
from __future__ import annotations

import subprocess

from crossaudit.broker import ToolBroker, default_registry, write_registry
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.tools_git import git_commit
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _tok(tools, writable=False):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": list(tools),
        "paths": ["**"], "writable": writable, "expires_at": "2100-01-01T00:00:00Z"})


def _broker(reg, tmp_path):
    return ToolBroker(reg, EvidenceLedger(tmp_path / "ev.jsonl"))


def _head(cfg):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg.root,
                          capture_output=True, text=True).stdout.strip()


def test_readonly_git_tools_are_registered_and_auto(cfg, tmp_path):
    names = default_registry().names()
    assert "git_diff" in names and "git_log" in names
    b = _broker(default_registry(), tmp_path)
    r = b.execute({"tool": "git_log", "args": {"limit": 5}}, _tok(["git_log"]),
                  cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "succeeded" and isinstance(r.output["log"], list)


def test_git_commit_direct_makes_a_local_commit(cfg):
    (cfg.root / "experiments" / "new.txt").write_text("x")
    r = git_commit(cfg, {"message": "add new"}, _tok(["git_commit"], writable=True))
    assert len(r["commit"]) == 40 and r["message"] == "add new"


def test_git_commit_never_auto_runs_via_broker(cfg, tmp_path):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)   # even fully authorized
    (cfg.root / "experiments" / "z.txt").write_text("z")
    before = _head(cfg)
    b = _broker(write_registry(), tmp_path)
    r = b.execute({"tool": "git_commit", "args": {"message": "nope"}},
                  _tok(["git_commit"], writable=True), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert _head(cfg) == before                          # nothing was committed


def test_push_and_repo_create_never_auto_run(cfg, tmp_path):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    b = _broker(write_registry(), tmp_path)
    tok = _tok(["git_push", "repo_create"], writable=True)
    for req in ({"tool": "git_push", "args": {"remote": "origin", "branch": "main"}},
                {"tool": "repo_create", "args": {"name": "should-not-exist"}}):
        r = b.execute(req, tok, cfg=cfg, run_id="r", now_epoch=0)
        assert r.status == "needs_approval"              # handler (gh/push) never fired


def test_repo_delete_is_permanently_not_offered():
    assert "repo_delete" not in write_registry().names()
    assert "repo_delete" not in default_registry().names()
