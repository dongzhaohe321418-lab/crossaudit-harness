"""Self-healing format repair + human-actionable escalation.

Principle (the user's, verbatim in product terms): the break-down screen may
only appear when the problem is clear AND user-actionable; everything else the
system fixes itself. A malformed generator reply now gets exactly ONE corrective
re-ask before anything escalates — and when it still fails, the escalation
carries a structured cause the Decision Center renders as plain guidance.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from crossaudit import generator as gen
from crossaudit.console.page import PAGE
from crossaudit.errors import ProviderDenial

VALID = (
    "SUMMARY: fix\n"
    '<<<CROSSAUDIT-OUTPUT-FILE path="experiments/demo/SUMMARY.md">>>\n'
    "hello\n"
    "<<<END-CROSSAUDIT-OUTPUT-FILE>>>\n"
    "NOTES:")
MALFORMED = ('<<<CROSSAUDIT-OUTPUT-FILE path="experiments/demo/SUMMARY.md">>>\n'
             "hello but the end marker never comes")


@dataclass
class Reply:
    text: str


def _complete_seq(replies, calls):
    seq = list(replies)

    def complete(*, system, prompt):
        calls.append(prompt)
        # Repeat the last reply once the sequence is spent: an integration run
        # may take several rounds, and the interesting part is the first two.
        return Reply(seq[len(calls) - 1] if len(calls) <= len(seq) else seq[-1])

    return complete


def test_a_malformed_reply_is_repaired_once_and_the_round_succeeds():
    calls, repairs = [], []
    work = gen.generate(
        task="write it", constitution="rules", current={},
        complete=_complete_seq([MALFORMED, VALID], calls),
        allowed_dirs=["experiments"], on_repair=repairs.append)
    assert isinstance(work, gen.Work) and "experiments/demo/SUMMARY.md" in work.files
    assert len(calls) == 2                                # exactly one re-ask
    assert len(repairs) == 1 and "END-CROSSAUDIT-OUTPUT-FILE" in repairs[0]
    # The corrective re-ask names the error and restates the envelope contract.
    assert "COULD NOT BE PARSED" in calls[1]
    assert '<<<CROSSAUDIT-OUTPUT-FILE path="relative/path.md">>>' in calls[1]


def test_a_twice_malformed_reply_escalates_with_repair_attempted():
    calls = []
    with pytest.raises(ProviderDenial) as excinfo:
        gen.generate(task="write it", constitution="rules", current={},
                     complete=_complete_seq([MALFORMED, MALFORMED], calls),
                     allowed_dirs=["experiments"])
    assert len(calls) == 2                                # bounded: never a loop
    assert excinfo.value.detail.get("category") == "format"
    assert excinfo.value.detail.get("repair_attempted") is True


def test_prose_instead_of_envelope_is_also_repaired():
    calls = []
    work = gen.generate(
        task="write it", constitution="rules", current={},
        complete=_complete_seq(["Sure! What would you like me to do?", VALID],
                               calls),
        allowed_dirs=["experiments"])
    assert isinstance(work, gen.Work) and len(calls) == 2


def test_path_refusals_are_never_retried():
    escape = ("SUMMARY: bad\n"
              '<<<CROSSAUDIT-OUTPUT-FILE path="../outside.md">>>\n'
              "x\n<<<END-CROSSAUDIT-OUTPUT-FILE>>>\nNOTES:")
    calls = []
    with pytest.raises(ProviderDenial, match="escapes the project"):
        gen.generate(task="write it", constitution="rules", current={},
                     complete=_complete_seq([escape, VALID], calls),
                     allowed_dirs=["experiments"])
    assert len(calls) == 1                 # a refusal, not a typo: no second ask


def test_build_loop_records_the_structured_cause(science, cfg, transcripts,
                                                 monkeypatch):
    from crossaudit.cli import build as build_mod
    from crossaudit.controller import StateStore

    events = []

    def fake_generate(**_kwargs):
        raise ProviderDenial(
            "the generator returned malformed file blocks: the closing "
            "<<<END-CROSSAUDIT-OUTPUT-FILE>>> marker is missing",
            category="format", repair_attempted=True)

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "produce the experiment",
                       on_event=lambda ev: events.append(ev.kind))

    cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()["cycles"]
    row = next(iter(cycles.values()))
    assert row["status"] == "ESCALATED"
    assert row["escalation_cause"] == "generator_format"   # structured cause
    assert "generation_refused" in events


def test_the_retry_is_visible_as_a_run_event(science, cfg, transcripts,
                                             monkeypatch):
    """run_loop wires on_repair to a generation_retried event (§24.1: an
    automatic adjustment is recorded, never invisible)."""
    from crossaudit.cli import build as build_mod

    events = []
    calls = []

    def fake_gen_complete(*_a, **_k):
        return _complete_seq([MALFORMED, VALID], calls)

    monkeypatch.setattr(build_mod, "_generator_complete", fake_gen_complete)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "produce the experiment",
                       on_event=lambda ev: events.append(ev.kind))
    assert "generation_retried" in events
    # First call was malformed, second is the corrective re-ask; later rounds
    # may call again — the invariant is the repair happened exactly once.
    assert len(calls) >= 2 and "COULD NOT BE PARSED" in calls[1]
    assert sum("COULD NOT BE PARSED" in c for c in calls) == 1


def test_decision_center_renders_the_format_cause_humanely():
    assert "generator_format" in PAGE
    assert "The generator could not produce auditable work" in PAGE
    assert "Rewrite the task as one concrete instruction" in PAGE
    # Old records without a cause still render (generic fallback intact).
    assert "No structured findings were recorded." in PAGE


def test_new_strings_have_chinese_parity():
    for en in ("Generator reply format problem",
               "The generator could not produce auditable work",
               "What happened", "correcting a malformed reply"):
        assert f'"{en}"' in PAGE, en
