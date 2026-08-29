"""Context shaping is visible as typed run events, never silent prompt loss."""
from __future__ import annotations

import pytest

from crossaudit.broker.registry import ToolError
from crossaudit.errors import ProviderDenial


def test_run_loop_emits_each_kind_of_context_notice_once(
        science, cfg, transcripts, monkeypatch):
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod
    from crossaudit.console.progress import CONTEXT_CONDENSATION_ZH

    events = []

    def current_work(_cfg, _task, _findings, on_condense):
        for report in (
            {"reduction": "work_files", "outlined": ["experiments/large.md"],
             "stubbed": ["experiments/archive.txt"], "file_readable": []},
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
    assert all(event.text in CONTEXT_CONDENSATION_ZH for event in notices)
    assert any("not available to file_read" in event.text
               and event.detail == "experiments/large.md" for event in notices)
    assert any("briefly stubbed" in event.text for event in notices)
    assert any("rerun the tool" in event.text for event in notices)
    assert any("rerun compute" in event.text for event in notices)
    assert any("run record" in event.text for event in notices)


def test_notice_names_only_a_committed_path_as_file_read_recoverable(
        science, cfg, transcripts, monkeypatch):
    """Execute the promised recovery; uncommitted content is named separately."""
    from dataclasses import replace

    from crossaudit.broker.tools_readonly import file_read
    from crossaudit.cli import build as build_mod
    from crossaudit.gitio import git
    from crossaudit.policy.tokens import CapabilityToken

    committed_rel = "experiments/committed_big.md"
    working_rel = "experiments/uncommitted_big.md"
    committed_sentinel = "COMMITTED-SENTINEL"
    body = "large context line\n" * 7_000
    (science / committed_rel).write_text(
        committed_sentinel + "\n" + body, encoding="utf-8")
    git("add", "--", committed_rel, cwd=science)
    git("commit", "-q", "-m", "add committed large file", cwd=science)
    (science / working_rel).write_text(
        "WORKING-SENTINEL\n" + body, encoding="utf-8")
    cfg = replace(cfg, scope_dirs=["experiments"])

    events = []
    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_args, **_kwargs: object())

    def stop_after_context(**_kwargs):
        raise ProviderDenial("stop after context probe", category="budget")

    monkeypatch.setattr(build_mod.gen_mod, "generate", stop_after_context)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "review the large files", on_event=events.append)

    notices = [event for event in events if event.kind == "context_condensed"]
    recoverable = next(event for event in notices
                       if event.text.startswith("Tracked project files outlined"))
    working_only = next(event for event in notices
                        if event.text.startswith("Working-tree-only project files outlined"))
    assert committed_rel in recoverable.detail
    assert working_rel not in recoverable.detail
    assert working_rel in working_only.detail
    assert "not available to file_read" in working_only.text
    assert "committed version" in recoverable.text

    token = CapabilityToken(project_id="test", run_id="recovery",
                            tools=frozenset({"file_read"}),
                            paths=("experiments/**",))
    recovered = file_read(cfg, {"path": committed_rel}, token)
    assert committed_sentinel in recovered["content"]
    with pytest.raises(ToolError, match="not in the committed tree"):
        file_read(cfg, {"path": working_rel}, token)


def test_every_current_work_refresh_keeps_the_condensation_observer(
        science, cfg, transcripts, monkeypatch):
    """Initial, built-in-tool, MCP, and compute refreshes all narrate shaping."""
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    observed = []
    calls = 0

    def current_work(_cfg, _task, _findings, on_condense=None):
        observed.append(callable(on_condense))
        if len(observed) > 1:
            on_condense({"reduction": "owner_guidance",
                         "condensed_bytes": len(observed)})
        return {}

    outcomes = [
        generator_mod.ToolRequest({"server_id": build_mod.BROKER_SERVER_ID,
                                   "tool": "file_read", "args": {}}),
        generator_mod.ToolRequest({"server_id": "fixture-server",
                                   "tool": "lookup", "args": {}}),
        generator_mod.ComputeRequest({"host_id": "fixture-host", "name": "job"}),
    ]

    def generate(**_kwargs):
        nonlocal calls
        calls += 1
        if outcomes:
            return outcomes.pop(0)
        raise ProviderDenial("stop after refresh probes", category="budget")

    events = []
    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_args, **_kwargs: object())
    monkeypatch.setattr(build_mod, "_current_work", current_work)
    monkeypatch.setattr(build_mod.gen_mod, "generate", generate)
    monkeypatch.setattr(build_mod, "build_broker_and_token",
                        lambda *_args, **_kwargs: (object(), object()))
    monkeypatch.setattr(build_mod, "broker_tool_call",
                        lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(build_mod.mcp.MANAGER, "call_agent",
                        lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.setattr(build_mod.hpc.MANAGER, "run_agent",
                        lambda *_args, **_kwargs: {"status": "ok"})
    monkeypatch.chdir(science)

    build_mod.run_loop(cfg, "exercise refreshes", on_event=events.append)

    assert calls == 4
    assert observed == [True, True, True, True]
    assert any(event.kind == "context_condensed" for event in events)
