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
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossaudit.broker.approval import AuthorizationStore
from crossaudit.controller import StateStore

from .test_admission_and_console import console, fetch, post_json_to, rejected  # noqa: F401


def _store(console_url: str) -> StateStore:
    _status, body, _headers = fetch(console_url.replace("/?t=", "/api/state?t="))
    return StateStore(Path(json.loads(body)["root"]) / ".crossaudit" / "state.json")


@pytest.fixture()
def answered_by(monkeypatch):
    """The class of every object `resolve_escalation` is called on."""
    seen: list[type] = []
    real = StateStore.resolve_escalation

    def recording(self, *args, **kwargs):
        seen.append(type(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(StateStore, "resolve_escalation", recording)
    return seen


def test_the_authorization_store_has_no_resolve_escalation():
    assert not hasattr(AuthorizationStore, "resolve_escalation")


@pytest.mark.parametrize("action,status", [("close", "BLOCKED"), ("reopen", "OPEN")])
def test_a_ruling_after_an_authorization_toggle_reaches_the_state_store(
        console, answered_by, action, status):  # noqa: F811
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
