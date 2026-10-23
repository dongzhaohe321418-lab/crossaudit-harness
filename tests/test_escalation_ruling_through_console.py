"""The escalation ruling, close and reopen, end to end through the console (D169, F5).

mypy reported `store.resolve_escalation` at console/server.py (the
/api/escalation branch of do_POST) as a call on `AuthorizationStore`, which
has no such method. Investigated: a false positive from name reuse. `store` is
bound to an `AuthorizationStore` in the /api/authorization branch of the same
method and rebound to a `StateStore` at the top of the /api/escalation
branch; every branch returns, so one request never reaches both. The
variable is now `state_store`, and these tests execute the line through the
tokened HTTP boundary -- after an /api/authorization request on the same
server, the sequence the name reuse was suspected of breaking -- and record
which class actually answered.

Review 2026-10-23, finding 1: these tests asserted only the controller
state, which is what hid that the console's ruling wrote no
`cycles/rulings.jsonl` row and no ledger commit. They now assert the
committed row, the commit carrying the reason and `status --json`, for close,
reopen and the provider retry's reopen, and that a rejected commit refuses
the ruling over HTTP with the cycle still ESCALATED (finding 2).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossaudit.broker.approval import AuthorizationStore
from crossaudit.cli import main
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_OK
from crossaudit.gitio import git

from .test_admission_and_console import console, fetch, post_json_to, rejected  # noqa: F401


def _store(console_url: str) -> StateStore:
    _status, body, _headers = fetch(console_url.replace("/?t=", "/api/state?t="))
    return StateStore(Path(json.loads(body)["root"]) / ".crossaudit" / "state.json")


@pytest.fixture()
def answered_by(monkeypatch):
    """The class of every object the ruling transaction is called on."""
    seen: list[type] = []
    real = StateStore.rule_escalation

    def recording(self, *args, **kwargs):
        seen.append(type(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(StateStore, "rule_escalation", recording)
    return seen


REASON = "A person read the report and ruled."


def _root(store: StateStore) -> Path:
    return store.path.parent.parent


def _rows(root: Path) -> list[dict]:
    log = root / "cycles" / "rulings.jsonl"
    return [json.loads(line) for line in log.read_text().split("\n") if line]


def _status_rulings(root: Path, cid: str, monkeypatch, capsys) -> list[dict]:
    monkeypatch.chdir(root)
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    doc = json.loads(capsys.readouterr().out)
    return next(r for r in doc["cycles"] if r["cycle_id"] == cid).get("rulings", [])


def _assert_committed(root: Path, cid: str, action: str, reason: str,
                      monkeypatch, capsys) -> None:
    """The ruling is in the ledger: one row, one commit carrying the reason
    and touching only the log, nothing left dirty, and `status` shows it."""
    rows = _rows(root)
    assert [(r["cycle_id"], r["action"], r["reason"]) for r in rows] == [
        (cid, action, reason)]
    assert rows[0]["status_after"] == {"close": "BLOCKED", "reopen": "OPEN"}[action]
    assert git("log", "-1", "--format=%s", cwd=root).startswith(f"ruling {cid} {action}")
    assert reason in git("log", "-1", "--format=%B", cwd=root)
    assert git("show", "--name-only", "--format=", "HEAD", cwd=root).split() == [
        "cycles/rulings.jsonl"]
    assert git("status", "--porcelain", "--", "cycles", cwd=root) == ""
    shown = _status_rulings(root, cid, monkeypatch, capsys)
    assert [(r["action"], r["reason"]) for r in shown] == [(action, reason)]


def test_the_authorization_store_has_no_resolve_escalation():
    assert not hasattr(AuthorizationStore, "resolve_escalation")


@pytest.mark.parametrize("action,status", [("close", "BLOCKED"), ("reopen", "OPEN")])
def test_a_ruling_after_an_authorization_toggle_reaches_the_state_store(
        console, answered_by, action, status, monkeypatch, capsys):  # noqa: F811
    """Mutation caught (finding 1): the console calling
    `StateStore.resolve_escalation` directly -- `answered_by` stays empty, and
    `cycles/rulings.jsonl`, the commit and `status`'s ruling are absent."""
    store = _store(console)
    cycle = store.open_or_advance("t/p", "d" * 40, None)
    store.escalate(cycle["cycle_id"], "round budget spent")

    code, granted, _h = post_json_to(console, "/api/authorization", {"enabled": True})
    assert code == 200 and granted == {"workspace_writes": True}

    code, result, _h = post_json_to(console, "/api/escalation", {
        "cycle_id": cycle["cycle_id"], "action": action,
        "reason": "A person read the report and ruled."})

    assert code == 200
    assert result == {"cycle_id": cycle["cycle_id"], "status": status,
                      "round": cycle["round"]}
    assert answered_by == [StateStore]
    row = store.cycle(cycle["cycle_id"])
    assert row["status"] == status
    if action == "close":
        assert row["closed_by_human"] is True
    else:
        assert row["human_reopened"] is True
    resolution = [h for h in store.snapshot()["history"]
                  if h.get("event") == "human_resolution"]
    assert resolution and resolution[-1]["action"] == action
    assert resolution[-1]["reason"] == "A person read the report and ruled."
    _assert_committed(_root(store), cycle["cycle_id"], action, REASON,
                      monkeypatch, capsys)


def test_a_ruling_without_a_reason_or_with_an_unknown_action_is_refused(
        console, answered_by):  # noqa: F811
    store = _store(console)
    cycle = store.open_or_advance("t/p", "e" * 40, None)
    store.escalate(cycle["cycle_id"], "round budget spent")

    for payload in ({"action": "close", "reason": "  "},
                    {"action": "approve", "reason": "because"}):
        code, _raw, _h = rejected(lambda payload=payload: post_json_to(
            console, "/api/escalation", {"cycle_id": cycle["cycle_id"], **payload}))
        assert 400 <= code < 500
    assert answered_by == [StateStore, StateStore]
    assert store.cycle(cycle["cycle_id"])["status"] == "ESCALATED"
    assert not (_root(store) / "cycles" / "rulings.jsonl").exists()


def _provider_stop(store: StateStore, sha: str) -> dict:
    return store.record_build_escalation(
        "t/p", sha * 40,
        "generator provider failure in round 1: subscription unavailable", 1,
        "history", "Create one accurate review")


def test_the_provider_retry_records_a_reopen_ruling_before_it_starts(
        console, answered_by, monkeypatch, capsys):  # noqa: F811
    """Mutation caught (finding 1): the retry branch reopening through
    `resolve_escalation` -- no row, no commit, and the build would start on
    a reopen the ledger never heard of."""
    from crossaudit.console import server as server_mod

    store = _store(console)
    stopped = _provider_stop(store, "c")
    root = _root(store)
    seen = {}

    def start(_cfg, task, **kwargs):
        # The ruling is already committed when the build is asked to start.
        seen.update(task=task, rows=len(_rows(root)), **kwargs)
        return {"started": True, "task": task, "attachments": []}

    monkeypatch.setattr(server_mod, "start_build", start)
    code, result, _h = post_json_to(console, "/api/escalation", {
        "cycle_id": stopped["cycle_id"], "action": "retry_provider", "reason": ""})
    assert code == 200 and result["retrying"] is True and result["status"] == "OPEN"
    assert answered_by == [StateStore]
    assert seen["rows"] == 1 and seen["continuation_cycle"] == stopped["cycle_id"]
    _assert_committed(root, stopped["cycle_id"], "reopen",
                      "Retry after reviewing the provider connection.",
                      monkeypatch, capsys)


# ------------------------------------------------- failure atomicity (finding 2)
from .test_resolve_commits_the_ruling import (  # noqa: E402
    REFUSING_HOOK, install_hook)


def _assert_refused_and_unchanged(console, store, cid, payload, head_before):
    code, raw, _h = rejected(lambda: post_json_to(
        console, "/api/escalation", {"cycle_id": cid, **payload}))
    assert 400 <= code < 500
    body = json.loads(raw)
    assert body["reason"] == (
        f"the ruling on cycle {cid} could not be committed to the ledger "
        f"(pre-commit: refused by policy); the cycle stays ESCALATED and "
        f"nothing was recorded")
    assert body["reason_zh"].startswith(f"周期 {cid} 的裁决未能提交到账本")
    root = _root(store)
    assert store.cycle(cid)["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution"
                   for h in store.snapshot()["history"])
    assert not (root / "cycles" / "rulings.jsonl").exists()
    assert git("status", "--porcelain", cwd=root) == head_before


@pytest.mark.parametrize("action", ["close", "reopen"])
def test_a_rejected_commit_refuses_the_console_ruling_and_changes_nothing(
        console, action):  # noqa: F811
    """Mutation caught (finding 2): the state changed before the commit, or
    the failed append left in the log or staged."""
    store = _store(console)
    cycle = store.open_or_advance("t/p", "f" * 40, None)
    store.escalate(cycle["cycle_id"], "round budget spent")
    root = _root(store)
    install_hook(root, REFUSING_HOOK)
    before = git("status", "--porcelain", cwd=root)
    _assert_refused_and_unchanged(console, store, cycle["cycle_id"],
                                  {"action": action, "reason": REASON}, before)


def test_a_rejected_commit_refuses_the_provider_retry_before_any_build(
        console, monkeypatch):  # noqa: F811
    """Mutation caught (finding 2): the retry reopening (or starting its
    build) although the reopen ruling was never committed."""
    from crossaudit.console import server as server_mod

    store = _store(console)
    stopped = _provider_stop(store, "9")
    started = []
    monkeypatch.setattr(server_mod, "start_build",
                        lambda *a, **k: started.append(a) or {"started": True})
    root = _root(store)
    install_hook(root, REFUSING_HOOK)
    before = git("status", "--porcelain", cwd=root)
    _assert_refused_and_unchanged(console, store, stopped["cycle_id"],
                                  {"action": "retry_provider", "reason": ""}, before)
    assert started == []
