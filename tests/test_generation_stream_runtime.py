"""The runtime half of D4: typed, durable, incrementally delivered drafts."""
from __future__ import annotations

import sqlite3

import pytest

from crossaudit.errors import ProviderDenial
from crossaudit.runtime import RunEvent, RunJournal, RunState


def _chunk(stream_id: str, seq: int, text: str = "draft", *,
           done: bool = False, outcome: str | None = None) -> RunEvent:
    stream = {"id": stream_id, "seq": seq, "done": done}
    if outcome is not None:
        stream["outcome"] = outcome
    return RunEvent(kind="generation_chunk", actor="generator", text=text,
                    detail="", state=RunState.GENERATING, round_no=1,
                    round_limit=3, stream=stream)


@pytest.mark.parametrize("change", [
    {"stream": None},
    {"actor": "auditor"},
    {"state": RunState.AUDITING},
    {"text": b"not decoded"},
    {"detail": "control in prose"},
    {"waiting_reason": {"kind": "provider"}},
    {"stream": {"id": "s", "seq": -1, "done": False}},
    {"stream": {"id": "s", "seq": True, "done": False}},
    {"stream": {"id": "s", "seq": 0, "done": "false"}},
    {"stream": {"id": "s", "seq": 0, "done": False,
                "outcome": "complete"}},
    {"stream": {"id": "s", "seq": 0, "done": True}},
    {"stream": {"id": "s", "seq": 0, "done": True,
                "outcome": "invented"}},
    {"stream": {"id": "s", "seq": 0, "done": False, "extra": 1}},
    {"text": ""},
    {"text": "界" * 2731},
])
def test_generation_chunk_contract_rejects_invalid_shapes(change):
    values = dict(kind="generation_chunk", actor="generator", text="draft",
                  detail="", state=RunState.GENERATING,
                  stream={"id": "s", "seq": 0, "done": False})
    values.update(change)

    with pytest.raises(ValueError):
        RunEvent(**values)


def test_stream_metadata_is_forbidden_on_ordinary_events():
    with pytest.raises(ValueError, match="only valid"):
        RunEvent(kind="activity", actor="generator", text="writing",
                 state=RunState.GENERATING,
                 stream={"id": "s", "seq": 0, "done": False})


def test_journal_revalidates_mutable_stream_metadata_at_the_write_boundary(
        tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("stream it")
    event = _chunk("s", 0)
    event.stream["extra"] = "added after construction"

    with pytest.raises(ValueError, match="unknown fields"):
        journal.append(run_id, event)

    assert journal.generation_events(run_id) == []


def test_journal_keeps_chunks_lossless_and_out_of_ordinary_snapshots(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("stream it")
    sentinel = "界" * 2700                 # 8,100 UTF-8 bytes; over 400 chars
    event_id = journal.append(run_id, _chunk("stream-a", 0, sentinel))

    row = journal.latest()
    assert all(step["kind"] != "generation_chunk" for step in row["steps"])
    assert sentinel not in repr(row)
    assert row["last_event_id"] < event_id
    rows = journal.generation_events(run_id)
    assert len(rows) == 1
    observed = dict(rows[0])
    assert isinstance(observed.pop("t"), float)
    assert observed == {
        "event_id": event_id, "kind": "generation_chunk",
        "actor": "generator", "text": sentinel, "state": "GENERATING",
        "round_no": 1, "round_limit": 3,
        "stream": {"done": False, "id": "stream-a", "seq": 0},
    }
    with sqlite3.connect(journal.path) as db:
        stored = db.execute(
            "SELECT text,stream_json FROM run_events WHERE sequence=?",
            (event_id,),
        ).fetchone()
    assert stored[0] == sentinel and '"stream-a"' in stored[1]


def test_journal_enforces_contiguous_non_interleaved_streams(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("stream it")

    with pytest.raises(RuntimeError, match="begin at sequence 0"):
        journal.append(run_id, _chunk("a", 1))
    journal.append(run_id, _chunk("a", 0, "first"))
    with pytest.raises(RuntimeError, match="cannot interleave"):
        journal.append(run_id, _chunk("b", 0))
    with pytest.raises(RuntimeError, match="not contiguous"):
        journal.append(run_id, _chunk("a", 2))
    journal.append(run_id, _chunk(
        "a", 1, "last", done=True, outcome="complete"))
    with pytest.raises(RuntimeError, match="terminal"):
        journal.append(run_id, _chunk("a", 2))
    journal.append(run_id, _chunk("b", 0, "retry"))
    journal.append(run_id, _chunk(
        "b", 1, "", done=True, outcome="aborted"))
    with pytest.raises(RuntimeError, match="cannot be reused"):
        journal.append(run_id, _chunk("a", 0, "reused"))

    rows = journal.generation_events(run_id)
    assert [(row["stream"]["id"], row["stream"]["seq"])
            for row in rows] == [("a", 0), ("a", 1), ("b", 0), ("b", 1)]
    assert journal.generation_events(
        run_id, after_sequence=rows[1]["event_id"])[0]["stream"]["id"] == "b"


def test_run_loop_bridges_provider_chunks_without_entering_other_payloads(
        science, cfg, monkeypatch):
    from crossaudit.cli import build as build_mod

    events = []
    bridge = {}

    def complete_factory(_cfg, _allow_custom, on_event=None, _heartbeat=None,
                         usage_context=None, **_kw):
        # The loop also hands its live usage attribution (billing slice);
        # a factory refusing the fifth argument turns it into a TypeError.
        bridge["provider"] = on_event
        return object()

    def stop_after_chunk(**_kwargs):
        bridge["provider"].on_chunk(
            "STREAM-ONLY-SENTINEL",
            {"id": "provider-attempt", "seq": 0, "done": False})
        assert "STREAM-ONLY-SENTINEL" not in repr(_kwargs["tool_results"])
        bridge["provider"].on_chunk(
            "", {"id": "provider-attempt", "seq": 1, "done": True,
                 "outcome": "aborted"})
        raise ProviderDenial("stop after stream probe", category="budget")

    monkeypatch.setattr(build_mod, "_generator_complete", complete_factory)
    monkeypatch.setattr(build_mod.gen_mod, "generate", stop_after_chunk)
    monkeypatch.chdir(science)

    build_mod.run_loop(cfg, "exercise streaming", on_event=events.append)

    chunks = [event for event in events if event.kind == "generation_chunk"]
    assert [event.text for event in chunks] == ["STREAM-ONLY-SENTINEL", ""]
    assert [event.stream["seq"] for event in chunks] == [0, 1]
    assert all(event.detail == "" and event.state == RunState.GENERATING
               for event in chunks)
