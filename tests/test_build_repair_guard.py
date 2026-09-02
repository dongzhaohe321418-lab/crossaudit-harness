"""The build loop's repair guard, driven through run_loop (D148 slice D).

Round 1 commits an incomplete increment (no metadata), so the audit BLOCKS on
the deterministic tier and the next round is a repair round. What that round
is allowed to do is the subject here. Each test names its D10 mutation.
"""
from __future__ import annotations

import dataclasses

import pytest

from crossaudit.config import RepairPolicy
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_ESCALATED

from .conftest import git

SUMMARY = "experiments/demo/SUMMARY.md"
CALC = "experiments/demo/calc.py"
CALC_OK = "def run():\n    return compute()\n"
CALC_DEFENSIVE = ("def run():\n    try:\n        return compute()\n"
                  "    except Exception:\n        pass\n")
CALC_FIXED = "def run():\n    return compute(strict=True)\n"
ROUND_ONE = {SUMMARY: "attempt one\n", CALC: CALC_OK}


def _drive(cfg, science, monkeypatch, rounds, *, task="produce the experiment"):
    """Run the loop with a scripted generator; return (code, events, calls).

    Each call records what the generator was shown and what the tree looked
    like at that moment: the findings text, calc.py's bytes, and the staged
    paths — so a rollback can be asserted mid-run, not inferred afterwards.
    """
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    calls: list[dict] = []
    script = iter(rounds)

    def fake_generate(**kwargs):
        calc = science / CALC
        calls.append({
            "findings": kwargs.get("findings", ""),
            "calc": calc.read_text() if calc.exists() else None,
            "staged": git("diff", "--cached", "--name-only", cwd=science),
        })
        return generator_mod.Work(summary="revision", files=next(script))

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    events = []
    code = build_mod.run_loop(cfg, task, on_event=events.append)
    return code, events, calls


def _kinds(events) -> list[str]:
    return [e.kind for e in events]


def _cycle(cfg) -> dict:
    cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()["cycles"]
    assert len(cycles) == 1
    return next(iter(cycles.values()))


def test_a_defensive_repair_is_refused_rolled_back_and_explained(
        science, cfg, transcripts, monkeypatch):
    """(a) Mutation: comment out the guard call in run_loop -> the except
    Exception lands in git history and no repair_refused event is emitted."""
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])

    kinds = _kinds(events)
    assert kinds.count("repair_refused") == 1
    refused = next(e for e in events if e.kind == "repair_refused")
    assert "calc.py adds a catch-all `except`" in refused.detail
    # Files and index were rolled back before the generator was asked again.
    assert len(calls) == 3
    assert calls[2]["calc"] == CALC_OK and calls[2]["staged"] == ""
    # The next prompt reads as: what stopped, why, what happens next.
    third = calls[2]["findings"]
    assert third.startswith("[BLOCKER] The repair guard refused the last revision:")
    assert f"- {CALC} adds a catch-all `except` that swallows every error" in third
    assert "The previous attempt was rolled back; make a smaller change" in third
    # The defensive bytes never reached history; the honest round-3 fix did.
    log = git("log", "-p", cwd=science)
    assert "except Exception" not in log and "strict=True" in log
    assert code == EXIT_ESCALATED          # round budget spent on the DCL blocker
    assert _cycle(cfg).get("escalation_cause") != "repair_refused"


def test_a_second_refusal_stops_the_run_with_the_repair_refused_cause(
        science, cfg, transcripts, monkeypatch):
    """(b) One free retry, then a clear stop the Decision Center can explain.

    max_rounds is raised to 5 so the stop is provably the second refusal and
    not the round budget. Mutation: never set repair_refusal_used -> the loop
    burns all five rounds re-asking.
    """
    five = dataclasses.replace(cfg, max_rounds=5)
    code, events, calls = _drive(
        five, science, monkeypatch,
        [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_DEFENSIVE},
         {CALC: CALC_FIXED}, {CALC: CALC_FIXED}])

    assert code == EXIT_ESCALATED
    assert _kinds(events).count("repair_refused") == 2
    assert len(calls) == 3                 # round 4 was never asked for
    cycle = _cycle(five)
    assert cycle["status"] == "ESCALATED"
    assert cycle["escalation_cause"] == "repair_refused"
    assert cycle["escalation_kind"] == "audit"
    assert cycle["escalation_reason"].startswith(
        "the automatic repair was refused in round 3 because "
        f"{CALC} adds a catch-all `except`")
    # Nothing of the refused attempts survives in the tree, index or history.
    assert (science / CALC).read_text() == CALC_OK
    assert git("diff", "--cached", "--name-only", cwd=science) == ""
    assert "except Exception" not in git("log", "-p", cwd=science)


def test_a_docs_only_revision_using_the_word_fallback_is_not_refused(
        science, cfg, transcripts, monkeypatch):
    """(c) D121: honest prose is never reddened.

    Mutation: add ".md" to CODE_SUFFIXES -> this revision is refused.
    """
    prose = "We skip the retry and fallback to the plan.\n"
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {SUMMARY: prose}, {SUMMARY: "attempt three\n"}])
    assert "repair_refused" not in _kinds(events)
    assert prose.strip() in git("log", "-p", cwd=science)
    assert "revision (round 2)" in git("log", "--format=%s", cwd=science)


def test_repair_enabled_false_disables_the_guard(science, cfg, transcripts, monkeypatch):
    """(d) The dial is honoured. Mutation: ignore cfg.repair.enabled ->
    the defensive revision is refused here too."""
    off = dataclasses.replace(cfg, repair=RepairPolicy(enabled=False))
    code, events, calls = _drive(
        off, science, monkeypatch,
        [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])
    assert "repair_refused" not in _kinds(events)
    assert "except Exception" in git("log", "-p", cwd=science)


def test_an_honest_small_fix_passes_the_guard_and_commits(
        science, cfg, transcripts, monkeypatch):
    """(e) The guard exists to stop hiding, not to block honest edits."""
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {CALC: CALC_FIXED}, {SUMMARY: "attempt three\n"}])
    assert "repair_refused" not in _kinds(events)
    assert "strict=True" in git("log", "-p", cwd=science)
    assert "revision (round 2)" in git("log", "--format=%s", cwd=science)


def _report_naming(artifact: str) -> str:
    return ("# Audit Report\n\n## Deterministic findings\n\nNone.\n\n"
            "## Model findings\n\n"
            f"### [BLOCKER] CA-DATA-002 — {artifact}\n"
            "The requested correction is still absent.\n")


def test_a_repair_outside_the_named_artifacts_is_refused_by_name(
        science, cfg, transcripts, monkeypatch):
    """A model BLOCKER names SUMMARY.md; the repair edits calc.py instead.

    Mutation: derive revision_scope from DCL findings only -> a model-named
    scope is never enforced and calc.py commits.
    """
    from crossaudit.cli import build as build_mod
    monkeypatch.setattr(build_mod, "_last_report", lambda _cfg: _report_naming(SUMMARY))
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {CALC: CALC_FIXED}, {SUMMARY: "attempt three\n"}])
    refused = [e for e in events if e.kind == "repair_refused"]
    assert len(refused) == 1
    assert refused[0].detail == (
        f"{CALC} is outside what the last audit asked to change (allowed: {SUMMARY})")
    assert "strict=True" not in git("log", "-p", cwd=science)


def test_a_basename_only_model_artifact_still_admits_the_honest_edit(
        science, cfg, transcripts, monkeypatch):
    """D121: a model that writes "SUMMARY.md" for experiments/demo/SUMMARY.md
    must not get an honest edit of that file refused for its spelling.

    Mutation: make _resolve_scope exact-match only -> refused.
    """
    from crossaudit.cli import build as build_mod
    monkeypatch.setattr(build_mod, "_last_report", lambda _cfg: _report_naming("SUMMARY.md"))
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {SUMMARY: "attempt two\n"}, {SUMMARY: "attempt three\n"}])
    assert "repair_refused" not in _kinds(events)
    assert "revision (round 2)" in git("log", "--format=%s", cwd=science)


def test_round_one_is_never_a_repair_round(science, cfg, transcripts, monkeypatch):
    """The guard screens repairs of a BLOCKED audit, not first drafts.

    Mutation: initialise revision_scope to set() -> round 1 is refused.
    """
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [{SUMMARY: "attempt one\n", CALC: CALC_DEFENSIVE},
         {SUMMARY: "attempt two\n"}, {SUMMARY: "attempt three\n"}])
    assert _kinds(events).count("repair_refused") == 0
    assert "except Exception" in git("log", "-p", cwd=science)


def test_init_then_load_accepts_the_scaffolded_repair_block(tmp_path, monkeypatch):
    """The scaffold's repair: block is a key config knows.

    Mutation: drop "repair" from _ALLOWED_TOP -> load refuses its own template.
    """
    import argparse

    from crossaudit.cli import main
    from crossaudit.config import load

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5"))
    text = (project / "crossaudit.yml").read_text()
    assert "repair:\n  enabled: true\n  max_changed_lines: 200\n" in text
    assert load(project / "crossaudit.yml").repair == RepairPolicy(
        enabled=True, max_changed_lines=200)


# ------------------------------------------------------------ config knob

def _load_with(science, block: str):
    from crossaudit.config import load

    from .conftest import CONFIG
    (science / "crossaudit.yml").write_text(CONFIG + block)
    return load(science / "crossaudit.yml")


def test_repair_config_defaults_when_absent(cfg):
    assert cfg.repair == RepairPolicy(enabled=True, max_changed_lines=200)


def test_repair_config_reads_both_knobs(science):
    loaded = _load_with(science, "repair:\n  enabled: false\n  max_changed_lines: 50\n")
    assert loaded.repair == RepairPolicy(enabled=False, max_changed_lines=50)


@pytest.mark.parametrize("block,message", [
    ("repair: 3\n", "repair must be a mapping"),
    ("repair:\n  budget: 1\n", "repair: unknown keys ['budget']"),
    ("repair:\n  enabled: yes please\n", "repair.enabled must be true or false"),
    ("repair:\n  max_changed_lines: 0\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
    ("repair:\n  max_changed_lines: 10001\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
    ("repair:\n  max_changed_lines: true\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
    ("repair:\n  max_changed_lines: many\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
])
def test_repair_config_refuses_bad_values_with_the_config_error(science, block, message):
    """Mutation: accept bool for max_changed_lines -> `true` loads as 1."""
    from crossaudit.errors import ConfigDenial
    with pytest.raises(ConfigDenial) as exc:
        _load_with(science, block)
    assert message in exc.value.reason
