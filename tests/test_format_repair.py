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
# Genuinely unrecoverable: an opening marker with NO path attribute (a missing
# END marker is now recovered, so it no longer exercises the repair path).
MALFORMED = ('<<<CROSSAUDIT-OUTPUT-FILE>>>\n'
             "hello but there is no path and no end marker")
# A plain conversational reply (no file envelope, not JSON): the generator
# answering a request it cannot turn into an audited deliverable — e.g. the
# thing asked for is not in the project.
PROSE = ("I could not find anything called 'eled' in this project. The files "
         "here are report.md and data.csv — did you mean the report?")
# The screenshot case: the generator narrates its intent in prose AND emits a
# tool envelope, so the reply parses as neither pure prose nor a clean tool call
# ("the ... envelope must be the entire reply"). The message is still a real
# answer and must surface as one, not as a cryptic refusal.
PROSE_WITH_TOOL = (
    "I need to read the repository before I can write a detailed review, but no "
    "MCP tool is configured for that here. Point me at the files to review and I "
    "will go through them.\n"
    "<<<CROSSAUDIT-MCP-TOOL>>>\n"
    '{"tool": "read_repo", "args": {}}\n'
    "<<<END-CROSSAUDIT-MCP-TOOL>>>")


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


def test_persistent_prose_becomes_a_conversational_answer_not_a_format_failure():
    # The user asked to review something that does not exist. The generator
    # answers in prose; after the one repair it answers in prose again — so it is
    # surfaced as a conversational reply (a useful answer), not a hard format stop.
    calls = []
    with pytest.raises(ProviderDenial) as exc:
        gen.generate(task="review the eled", constitution="rules", current={},
                     complete=_complete_seq([PROSE, PROSE], calls),
                     allowed_dirs=["experiments"])
    assert exc.value.detail.get("conversational") is True
    assert exc.value.detail.get("category") == "conversational"
    assert "eled" in exc.value.reason           # the generator's own answer, verbatim
    assert len(calls) == 2                       # one repair re-ask, then surfaced


def test_prose_wrapping_a_tool_envelope_surfaces_as_an_answer():
    # The exact reported failure: "write a detailed review" of a thing that needs
    # a tool the run does not have. The generator explains this in prose beside a
    # tool envelope, so the reply "envelope must be the entire reply". After the
    # one repair it does the same — surface the explanation, not a bare refusal.
    calls = []
    with pytest.raises(ProviderDenial) as exc:
        gen.generate(task="write a detailed review", constitution="rules",
                     current={}, mcp_servers=[{"name": "repo", "tools": []}],
                     complete=_complete_seq([PROSE_WITH_TOOL, PROSE_WITH_TOOL],
                                            calls),
                     allowed_dirs=["experiments"])
    assert exc.value.detail.get("conversational") is True
    assert exc.value.detail.get("category") == "conversational"
    assert "review" in exc.value.reason              # the generator's own words
    assert "CROSSAUDIT-MCP-TOOL" not in exc.value.reason   # scaffolding stripped
    assert len(calls) == 2                            # one repair, then surfaced


def test_a_one_off_prose_slip_is_still_repaired_to_work():
    # A single prose reply that then produces valid work is a format slip, NOT a
    # conversational answer — it must still repair, not surface as a reply.
    calls = []
    work = gen.generate(task="write it", constitution="rules", current={},
                        complete=_complete_seq([PROSE, VALID], calls),
                        allowed_dirs=["experiments"])
    assert isinstance(work, gen.Work)


def test_the_decision_center_renders_the_answered_cause():
    assert "row.cause==='answered'" in PAGE
    assert "CrossAudit answered" in PAGE


def test_a_malformed_reply_is_repaired_once_and_the_round_succeeds():
    calls, repairs = [], []
    work = gen.generate(
        task="write it", constitution="rules", current={},
        complete=_complete_seq([MALFORMED, VALID], calls),
        allowed_dirs=["experiments"], on_repair=repairs.append)
    assert isinstance(work, gen.Work) and "experiments/demo/SUMMARY.md" in work.files
    assert len(calls) == 2                                # exactly one re-ask
    assert len(repairs) == 1 and "malformed file blocks" in repairs[0]
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
            "the generator returned malformed file blocks: the opening file "
            "marker is missing its path",
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


# ---- no-progress self-heal (the second dead-end class the user hit) ----
def test_unchanged_round_gets_one_corrective_retry_then_succeeds(
        science, cfg, transcripts, monkeypatch):
    """Round 1 reproduces committed bytes → the loop re-asks once with the
    exact correction; a real revision on the retry continues normally."""
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    (science / "experiments" / "demo" / "SUMMARY.md").write_text("same\n")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=science, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "-m", "prior work"], cwd=science, check=True)

    prompts, events = [], []

    def fake_generate(**kwargs):
        prompts.append(kwargs.get("findings", ""))
        text = "same\n" if len(prompts) == 1 else "improved\n"
        return generator_mod.Work(summary="attempt",
                                  files={"experiments/demo/SUMMARY.md": text})

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *a, **k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "improve the summary",
                       on_event=lambda ev: events.append(ev.kind))

    assert len(prompts) >= 2                       # the retry actually re-asked
    assert "byte-identical" in prompts[1]          # with the exact correction
    assert "revision_retry" in events              # visibly recorded
    # The healed round produced a real revision that reached the audit path —
    # the retry did its job (later rounds may still stop honestly).
    assert "audit_started" in events
    assert events.index("audit_started") > events.index("revision_retry")


def test_two_unchanged_rounds_escalate_with_no_progress_cause(
        science, cfg, transcripts, monkeypatch):
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod
    from crossaudit.controller import StateStore

    (science / "experiments" / "demo" / "SUMMARY.md").write_text("same\n")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=science, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "-m", "prior work"], cwd=science, check=True)

    def fake_generate(**kwargs):
        return generator_mod.Work(summary="attempt",
                                  files={"experiments/demo/SUMMARY.md": "same\n"})

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *a, **k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    build_mod.run_loop(cfg, "improve the summary")

    cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()["cycles"]
    row = next(iter(cycles.values()))
    assert row["status"] == "ESCALATED"
    assert row.get("escalation_cause") == "no_progress"


def test_page_renders_the_no_progress_cause():
    from crossaudit.console.page import PAGE
    assert "The generator repeated the existing work" in PAGE
    assert "Nothing new to audit" in PAGE
    assert '"Nothing new to audit"' in PAGE        # zh parity entry exists


# ---- tolerant parser: recover the common "missing END marker" case ----
# The screenshot bug: the model wrote the whole review but omitted the closing
# <<<END-CROSSAUDIT-OUTPUT-FILE>>>, so the strict parser failed twice and
# escalated. The content was all there — recover it instead of wasting the round.
def test_missing_end_marker_is_recovered_not_escalated():
    from crossaudit.generator import parse_work_reply
    reply = ('SUMMARY: photocatalysis review\n'
             '<<<CROSSAUDIT-OUTPUT-FILE path="experiments/demo/review.md">>>\n'
             '# Photocatalysis\n\nA thorough review [1][2].\nNOTES: done')
    work = parse_work_reply(reply)
    assert work.summary == "photocatalysis review"
    body = work.files["experiments/demo/review.md"]
    assert body.startswith("# Photocatalysis") and "[1][2]" in body
    assert "END-CROSSAUDIT-OUTPUT-FILE" not in body    # no marker bled in
    assert work.notes == "done"                        # NOTES still bounds it


def test_second_file_missing_end_is_not_dropped():
    from crossaudit.generator import parse_work_reply
    reply = ('<<<CROSSAUDIT-OUTPUT-FILE path="a.md">>>\nAAA\n'
             '<<<END-CROSSAUDIT-OUTPUT-FILE>>>\n'
             '<<<CROSSAUDIT-OUTPUT-FILE path="b.md">>>\nBBB')
    work = parse_work_reply(reply)
    assert work.files == {"a.md": "AAA", "b.md": "BBB"}   # both, not just the first


def test_recovery_never_bypasses_the_path_escape_guard(tmp_path):
    from crossaudit.generator import bind_file_identities, parse_work_reply
    from crossaudit.errors import ProviderDenial
    # A marker with no END that also escapes scope must still be refused when
    # validated — recovery reads the path only from the marker, never invents it.
    work = parse_work_reply('<<<CROSSAUDIT-OUTPUT-FILE path="../evil.md">>>\nx')
    with pytest.raises(ProviderDenial, match="escapes the project"):
        bind_file_identities(work, tmp_path, ["experiments"])


def test_conflicting_duplicate_still_fails_closed_after_recovery():
    from crossaudit.generator import parse_work_reply
    from crossaudit.errors import ProviderDenial
    reply = ('<<<CROSSAUDIT-OUTPUT-FILE path="a.md">>>\nONE\n'
             '<<<END-CROSSAUDIT-OUTPUT-FILE>>>\n'
             '<<<CROSSAUDIT-OUTPUT-FILE path="a.md">>>\nTWO')
    with pytest.raises(ProviderDenial, match="duplicate file request"):
        parse_work_reply(reply)
