"""P13 — the live tool catalog: what the model is offered always matches what its
token can grant, and Level-3 command / HPC exposure is gated by explicit opt-in.

The invariant fixed here: a tool is never *advertised* to the model yet refused
as "not in this grant". The build token's tools ARE the live registry's tools,
so every offered tool is grantable and then approval-gated. Command execution
(run_check) appears only once the user allowlists a command; HPC only once a
compute host is configured.
"""
from __future__ import annotations

import sys

from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.routing import (
    build_broker_and_token, build_catalog, live_catalog,
    run_commands_authorized)

_READONLY = {"file_read", "search", "git_status", "doctor", "git_diff", "git_log",
             # Slice B: research retrieval is read-only and ALWAYS per-call
             # approval-gated (L4 never auto-runs), so it is proposable by default.
             "paper_search", "web_fetch"}


def _names(cfg):
    return {t["name"] for t in build_catalog(cfg)}


def test_default_project_is_read_only(cfg):
    assert _names(cfg) == _READONLY
    _, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    assert not tok.writable
    for t in ("file_write", "git_commit", "run_check"):
        assert not tok.allows_tool(t)


def test_advertised_write_tools_are_all_grantable_then_gated(cfg):
    # The latent bug this fixes: git_commit used to be advertised but absent from
    # the token, so it was refused as "not in this grant" instead of gated.
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    names = _names(cfg)
    assert {"file_write", "git_commit", "git_push", "repo_create"} <= names
    broker, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    for name in names:
        assert tok.allows_tool(name)                 # every advertised tool is granted
    # git_commit is grantable → the broker gates it (needs_approval), never
    # refuses it as out-of-grant. No approver injected → standing service denies L3.
    r = broker.execute({"tool": "git_commit", "args": {"message": "x"}},
                       tok, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"


def test_run_check_appears_only_after_a_command_is_allowlisted(cfg):
    assert "run_check" not in _names(cfg)
    assert not run_commands_authorized(cfg)
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    assert run_commands_authorized(cfg)
    assert "run_check" in _names(cfg)
    broker, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    assert tok.allows_tool("run_check")
    # Reachable now, but still per-call approval-gated (never auto-runs).
    r = broker.execute(
        {"tool": "run_check", "args": {"command": [sys.executable, "-c", "print(1)"]}},
        tok, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"


def test_live_catalog_matches_the_token_tools(cfg):
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    AuthorizationStore(cfg).set_list("allowed_commands", [sys.executable])
    catalog_names = {t["name"] for t in live_catalog(cfg)}
    _, tok = build_broker_and_token(cfg, run_id="r", now_epoch=0)
    assert catalog_names == set(tok.tools)           # single source of truth
