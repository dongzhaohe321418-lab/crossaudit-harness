"""Mid-run steering — add information any time; it queues and joins the work.

Like Codex/Claude Code: a message sent while a build runs is queued durably in
order, read exactly once at the next round boundary, injected as OWNER GUIDANCE
in the generator prompt (never the auditor's — P2), recorded as a visible run
event, and it never changes the recorded goal/task (§5.6).
"""
from __future__ import annotations

import pytest

from crossaudit.console.page import PAGE
from crossaudit.runtime.runs import (
    MAX_STEER_MESSAGE_BYTES, MAX_STEER_QUEUE, RunJournal,
)


def _journal(tmp_path):
    return RunJournal(tmp_path / "runtime.sqlite3")


def _start(journal):
    return journal.start("steerable task", chat_id="history")


# ------------------------------------------------------------------ the queue
def test_enqueue_orders_and_drains_exactly_once(tmp_path):
    j = _journal(tmp_path)
    rid = _start(j)
    assert j.enqueue_message(rid, "first") == 1
    assert j.enqueue_message(rid, "second") == 2
    assert j.queued_messages(rid) == 2
    assert j.drain_messages(rid) == ["first", "second"]   # oldest first
    assert j.drain_messages(rid) == []                    # consume-once
    assert j.queued_messages(rid) == 0


def test_queue_survives_a_journal_reopen(tmp_path):
    j = _journal(tmp_path)
    rid = _start(j)
    j.enqueue_message(rid, "durable note")
    fresh = _journal(tmp_path)                            # new connection/process
    assert fresh.drain_messages(rid) == ["durable note"]


def test_enqueue_refuses_dead_runs_empty_oversize_and_overflow(tmp_path):
    j = _journal(tmp_path)
    with pytest.raises(ValueError, match="no live run"):
        j.enqueue_message("ghost", "hello")
    rid = _start(j)
    with pytest.raises(ValueError, match="empty"):
        j.enqueue_message(rid, "   ")
    with pytest.raises(ValueError, match="too long"):
        j.enqueue_message(rid, "x" * (MAX_STEER_MESSAGE_BYTES + 1))
    for i in range(MAX_STEER_QUEUE):
        j.enqueue_message(rid, f"m{i}")
    with pytest.raises(ValueError, match="full"):
        j.enqueue_message(rid, "one too many")


def test_enqueue_is_visible_as_a_run_event_and_count(tmp_path):
    j = _journal(tmp_path)
    rid = _start(j)
    j.enqueue_message(rid, "please add a figure")
    row = j.latest()
    assert row["queued"] == 1
    kinds = [s["kind"] for s in row["steps"]]
    assert "guidance_queued" in kinds


# --------------------------------------------------------------- loop consumption
def _run_with_guidance(science, cfg, monkeypatch, queue_rounds):
    """Drive run_loop with a drain handle that feeds guidance per round."""
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    prompts, events = [], []
    calls = {"n": 0}

    def fake_generate(**kwargs):
        prompts.append(kwargs.get("owner_guidance", ""))
        calls["n"] += 1
        return generator_mod.Work(
            summary=f"attempt {calls['n']}",
            files={"experiments/demo/SUMMARY.md": f"v{calls['n']}\n"})

    def on_event(ev):
        events.append(ev)

    drained = list(queue_rounds)

    def drain():
        return drained.pop(0) if drained else []

    on_event.drain_guidance = drain
    monkeypatch.setattr(build_mod, "_generator_complete", lambda *a, **k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "produce the experiment", on_event=on_event)
    return prompts, events


def test_guidance_joins_the_next_round_in_order(science, cfg, transcripts,
                                                monkeypatch):
    prompts, events = _run_with_guidance(
        science, cfg, monkeypatch,
        queue_rounds=[["用中文写", "加一张图表"], [], []])
    assert prompts[0] == "用中文写\n\n加一张图表"          # ordered, joined
    kinds = [ev.kind for ev in events]
    assert "guidance_received" in kinds
    received = next(ev for ev in events if ev.kind == "guidance_received")
    assert "2 owner message" in received.text


def test_guidance_accumulates_but_never_reinjects_duplicates(
        science, cfg, transcripts, monkeypatch):
    prompts, _ = _run_with_guidance(
        science, cfg, monkeypatch,
        queue_rounds=[["first note"], ["second note"], []])
    # Round 1 sees the first note; round 2 sees both (cumulative), and the
    # drain returned the second note only once (consume-once by contract).
    assert prompts[0] == "first note"
    if len(prompts) > 1:
        assert prompts[1] == "first note\n\nsecond note"


def test_goal_and_task_stay_fixed_under_steering(science, cfg, transcripts,
                                                 monkeypatch):
    import json
    prompts, events = _run_with_guidance(
        science, cfg, monkeypatch, queue_rounds=[["改成中文"], [], []])
    goal_ev = next(ev for ev in events if ev.kind == "goal")
    goal = json.loads(goal_ev.detail)
    assert goal["task"] == "produce the experiment"       # §5.6: no drift
    assert "改成中文" not in goal_ev.detail


def test_auditor_prompt_never_sees_guidance(cfg):
    """P2: OWNER GUIDANCE is a generator prompt section only."""
    import inspect

    from crossaudit.auditor import prompt as auditor_prompt
    source = inspect.getsource(auditor_prompt)
    assert "OWNER GUIDANCE" not in source
    assert "owner_guidance" not in source


# ------------------------------------------------------------------ say() path
def test_say_queues_for_a_live_run_instead_of_refusing(cfg, monkeypatch):
    from crossaudit import router as router_mod
    from crossaudit.cli import talk as talk_mod
    from crossaudit.console import server as server_mod

    routing = router_mod.Routing(
        utterance="加一个对比实验", lane="generator", confidence=0.95,
        reasoning="work", restated="加一个对比实验", t=1, chat_id="a" * 16)
    monkeypatch.setattr(router_mod, "route_addressed", lambda *a, **k: routing)
    monkeypatch.setattr(talk_mod, "_record_routing", lambda *a, **k: None)
    from types import SimpleNamespace
    monkeypatch.setattr(server_mod, "TRACKER", SimpleNamespace(
        running=True, snapshot=lambda: {"run_id": "r9", "finished": False}))

    class FakeJournal:
        def __init__(self, _path): pass
        def enqueue_message(self, run_id, text):
            assert run_id == "r9" and text == "加一个对比实验"
            return 3

    monkeypatch.setattr(server_mod, "RunJournal", FakeJournal)
    monkeypatch.setattr(server_mod, "start_build",
                        lambda *a, **k: pytest.fail("steering must not build"))
    result = server_mod.say(cfg, "加一个对比实验", chat_id="history")
    assert result["queued"] is True and result["position"] == 3
    assert "queued as owner guidance" in result["executed"]


def test_say_full_queue_is_a_polite_refusal(cfg, monkeypatch):
    from crossaudit import router as router_mod
    from crossaudit.cli import talk as talk_mod
    from crossaudit.console import server as server_mod

    routing = router_mod.Routing(
        utterance="x", lane="generator", confidence=0.95,
        reasoning="work", restated="x", t=1, chat_id="a" * 16)
    monkeypatch.setattr(router_mod, "route_addressed", lambda *a, **k: routing)
    monkeypatch.setattr(talk_mod, "_record_routing", lambda *a, **k: None)
    from types import SimpleNamespace
    monkeypatch.setattr(server_mod, "TRACKER", SimpleNamespace(
        running=True, snapshot=lambda: {"run_id": "r9", "finished": False}))

    class FullJournal:
        def __init__(self, _path): pass
        def enqueue_message(self, run_id, text):
            raise ValueError("the guidance queue is full; the run will read "
                             "it at the next round")

    monkeypatch.setattr(server_mod, "RunJournal", FullJournal)
    result = server_mod.say(cfg, "x", chat_id="history")
    assert result.get("queued") is None
    assert result["executed"].startswith("refused — the guidance queue is full")


# ------------------------------------------------------------------ PAGE contracts
def test_page_supports_steering():
    assert "send.hidden=false" in PAGE                     # composer stays usable
    assert "Queued — read at next round" in PAGE
    assert "Send guidance to the running task" in PAGE
    assert "guidance" in PAGE and "queued" in PAGE
    for en in ("Queued.", "Will be read at the next generator round",
               "Queued — read at next round",
               "Send guidance to the running task"):
        assert f'"{en}"' in PAGE, en                       # zh parity entries


def test_steering_refused_on_a_stopping_run(tmp_path):
    """A CANCELLING run has no further round to read guidance — refuse, not queue."""
    j = _journal(tmp_path)
    rid = _start(j)
    j.request_cancel(rid)                                  # → CANCELLING
    with pytest.raises(ValueError, match="no live run"):
        j.enqueue_message(rid, "too late")


def test_a_queued_event_does_not_double_stall_note(tmp_path):
    """A guidance_queued event after a stall note must not reset stall dedup."""
    import time as _t
    j = _journal(tmp_path)
    rid = _start(j)
    old = _t.time() - 10_000
    with j._connect() as db:                               # backdate heartbeat+lease
        db.execute("UPDATE runs SET heartbeat_at=?, lease_expires_at=? "
                   "WHERE run_id=?", (old, old, rid))
        db.commit()
    alive = lambda _pid: True                              # owner lives → stall note
    j.mark_stalled_runs(alive=alive)
    j.enqueue_message(rid, "a note")                       # inserts guidance_queued
    j.mark_stalled_runs(alive=alive)                       # must NOT add a 2nd stall
    with j._connect() as db:
        n = db.execute("SELECT COUNT(*) AS n FROM run_events WHERE run_id=? "
                       "AND kind='run_stalled'", (rid,)).fetchone()["n"]
    assert n == 1
