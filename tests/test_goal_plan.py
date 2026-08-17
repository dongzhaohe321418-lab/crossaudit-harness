"""Slice C — the Goal record and the minimal plan surface (§12/§14/§40.2).

The Goal is derived deterministically from config + task (no model call), is
emitted durably as the run's first event, and cannot drift mid-run (the task is
fixed at start — §5.6). The plan surface shows the audited loop's own gates as
plan v1; nothing is fabricated when a record is missing.
"""
from __future__ import annotations

import json

from crossaudit.cli.build import derive_goal
from crossaudit.console.page import PAGE


def test_goal_derivation_is_deterministic_and_model_free(cfg):
    a = derive_goal(cfg, "improve the results section")
    b = derive_goal(cfg, "improve the results section")
    assert a == b                                        # same inputs, same goal
    assert a["task"] == "improve the results section"
    assert a["constraints"]["max_rounds"] == cfg.max_rounds
    assert a["constraints"]["scope_dirs"] == [str(d) for d in (cfg.scope_dirs or [])]
    assert a["constraints"]["writes_authorized"] is False   # default deny
    assert "the independent auditor returns PASS" in a["success_criteria"]
    assert any("audited work files" in o for o in a["desired_outputs"])


def test_goal_notices_a_requested_document(cfg):
    goal = derive_goal(cfg, "write the summary as a pdf report")
    assert any("PDF" in o for o in goal["desired_outputs"])


def test_goal_reflects_authorizations(cfg):
    from crossaudit.broker.approval import WORKSPACE_WRITES, AuthorizationStore
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)
    goal = derive_goal(cfg, "x")
    assert goal["constraints"]["writes_authorized"] is True


def test_run_loop_emits_the_goal_first(science, cfg, transcripts, monkeypatch):
    """The Goal is the run's first durable event, before any round starts."""
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    events = []

    def on_event(ev):
        events.append((ev.kind, ev.detail))

    def fake_generate(**_kwargs):
        return generator_mod.Work(summary="attempt",
                                  files={"experiments/demo/SUMMARY.md": "x\n"})

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "produce the experiment", on_event=on_event)

    kinds = [k for k, _ in events]
    assert kinds[0] == "goal"                            # stated before work
    assert kinds.index("goal") < kinds.index("round_started")
    goal = json.loads(dict(events)["goal"])
    assert goal["task"] == "produce the experiment"
    assert goal["constraints"]["max_rounds"] == cfg.max_rounds


def test_page_has_the_plan_tab_and_honest_fallbacks():
    assert 'data-view="plan"' in PAGE and "planView" in PAGE
    assert "Goal & plan" in PAGE
    assert "No plan yet — the plan appears when a task starts." in PAGE
    # Missing/corrupt goal record → honest fallback, never fabricated.
    assert "The structured goal record is not available for this run." in PAGE
    # Plan v1 is honestly labeled as the loop's own gates.
    assert "Plan v1 · the audited loop" in PAGE


def test_plan_strings_have_chinese_parity():
    for en in ("Goal & plan", "Desired outputs", "Success criteria",
               "Plan v1 · the audited loop",
               "No plan yet — the plan appears when a task starts."):
        assert f'"{en}"' in PAGE, en
