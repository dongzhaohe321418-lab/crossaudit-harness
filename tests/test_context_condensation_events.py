"""Context shaping is visible as typed run events, never silent prompt loss."""
from __future__ import annotations


def test_run_loop_emits_each_kind_of_context_notice_once(
        science, cfg, transcripts, monkeypatch):
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    events = []

    def current_work(_cfg, _task, _findings, on_condense):
        for report in (
            {"reduction": "work_files", "outlined": ["experiments/large.md"],
             "stubbed": ["experiments/archive.txt"]},
            {"reduction": "tool_results", "labels": ["web.fetch"]},
            {"reduction": "compute_results", "labels": ["analysis-job"]},
            {"reduction": "owner_guidance", "condensed_bytes": 1200},
        ):
            on_condense(report)
        return {}

    def fake_generate(**_kwargs):
        return generator_mod.Work(
            summary="attempt", files={"experiments/demo/SUMMARY.md": "x\n"})

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_args, **_kwargs: object())
    monkeypatch.setattr(build_mod, "_current_work", current_work)
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "produce the experiment", on_event=events.append)

    notices = [event for event in events if event.kind == "context_condensed"]
    assert len(notices) == 5
    assert all(event.actor == "generator" for event in notices)
    assert any("file_read away" in event.text
               and event.detail == "experiments/large.md" for event in notices)
    assert any("briefly stubbed" in event.text for event in notices)
    assert any("rerun the tool" in event.text for event in notices)
    assert any("rerun compute" in event.text for event in notices)
    assert any("run record" in event.text for event in notices)

