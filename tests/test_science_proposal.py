"""The science inference is a proposal with its grounds (SPEC 3 §3.5).

The walkthrough's harm was a laboratory contract arriving unasked and surfacing
later as a BLOCKER about `metadata.yml` — the point at which the audit stopped
reading as a second opinion and started reading as obstruction. Batch 2 removed
that by always defaulting to the general pack, which is right for a prose review
and silently wrong for real science: the rules get drafted from the person's own
description, and the machine checks that would verify those very rules never run.

So the inference is made and shown, with reasons the person can read and refuse.

Every test here executes the real code. The pure inference is exercised
directly; the screen and the wiring through to `crossaudit.yml` are exercised by
running the real `crossaudit init` on a real pty. The only substitution anywhere
is the network transport, which becomes the `replay` provider that already ships
for this purpose — `constitution.distil`, `parse_json_reply`, `Draft.from_json`,
`infer_check_pack` and every wizard screen all execute for real.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import select
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from crossaudit.cli import main, wizard
from crossaudit.constitution import DISTIL_SYSTEM, Draft, Rule


def _rule(rid, title, criterion, from_user=""):
    return Rule(id=rid, severity="BLOCKER", title=title, criterion=criterion,
                from_user=from_user)


def _draft(rules):
    return Draft(project_summary="a study", domain="data analysis", rules=rules)


# --------------------------------------------------------- the pure inference
_PROSE = [_rule("CA-CONTENT-001", "It does what was asked.", "the deliverable "
                "answers the task"),
          _rule("CA-CONTENT-002", "Nothing is left unfinished.", "no TODO text")]
_ONE = [*_PROSE, _rule("CA-D-001", "Quantities carry a unit.", "unit present")]
_TWO = [*_ONE, _rule("CA-D-002", "Convergence is real.", "converged above threshold")]
_ALL = [*_TWO,
        _rule("CA-D-003", "results.json parses.", "metadata.yml and results.json parse"),
        _rule("CA-D-004", "Sources are traceable.", "each source names a revision")]


@pytest.mark.parametrize("rules,chosen,expected", [
    (None, "general", None),                       # keyless: nothing was drafted
    ([], "general", None),
    (_PROSE, "general", None),                     # a prose review stays prose
    (_ONE, "general", None),                       # one match is not a shape
    (_TWO, "general", "science"),
    (_ALL, "general", "science"),
    (_ALL, "science", None),                       # already chosen; not ours to revisit
    (_ALL, "own", None),                           # an explicit --profile wins
])
def test_the_pack_is_proposed_only_when_the_rules_supply_the_reasons(
        rules, chosen, expected):
    drafted = None if rules is None else _draft(rules) if rules else None
    if rules == []:
        drafted = Draft(project_summary="s", domain="d", rules=[])
    proposal = wizard.infer_check_pack(drafted, chosen)
    assert (proposal.key if proposal else None) == expected


def test_the_grounds_are_the_persons_own_rules_and_never_invented():
    """Each grounding rule appears once, names what it grounds, and is quoted
    back only where the drafting model actually attributed it."""
    drafted = _draft([
        _rule("CA-D-001", "Every quantity carries a unit.",
              "each entry in results.json has a unit", "every number needs a unit"),
        _rule("CA-D-002", "Convergence is real.", "converged above threshold"),
    ])
    proposal = wizard.infer_check_pack(drafted, "general")
    assert proposal is not None
    ids = [row[0] for row in proposal.grounds]
    assert ids == sorted(set(ids)), "a rule that grounds two checks is listed twice"

    grounded = {row[0]: row for row in proposal.grounds}
    # One rule can honestly ground two checks; it says so once.
    assert set(grounded["CA-D-001"][3]) == {"schema", "units"}
    assert grounded["CA-D-001"][2] == "every number needs a unit"
    # The model attributed nothing to the person for this one, so nothing is
    # quoted. An invented reason for a real choice is the §1.5 failure this
    # slice exists to remove.
    assert grounded["CA-D-002"][2] == ""
    assert proposal.checks == ("schema", "units", "convergence", "provenance")
    assert proposal.instead_of == ("parseable", "declared", "internal", "complete")


# ------------------------------------------------- the real wizard, on a pty
_DESCRIPTION = ("a photovoltaic efficiency study; every reported number must "
                "carry a unit and trace back to the run that produced it, and "
                "nothing counts as converged unless it met its threshold")

_DRAFT_REPLY = {
    "project_summary": "A photovoltaic efficiency study.",
    "domain": "experimental photovoltaics",
    "rules": [
        {"id": "CA-DATA-001", "severity": "BLOCKER",
         "title": "Every reported quantity carries a unit.",
         "criterion": "Each entry in results.json has a non-empty unit field.",
         "from_user": "every reported number must carry a unit"},
        {"id": "CA-DATA-002", "severity": "BLOCKER",
         "title": "Every result traces to the run that produced it.",
         "criterion": "Each quantity names inputs and a code revision.",
         "from_user": "trace back to the run that produced it"},
        {"id": "CA-DATA-003", "severity": "BLOCKER",
         "title": "Nothing is converged unless it met its threshold.",
         "criterion": "Where convergence is claimed, achieved meets threshold.",
         "from_user": "nothing counts as converged unless it met its threshold"},
    ]}


#: These drive the real `crossaudit init` over a real terminal, which needs
#: `pty` — POSIX only. There is no Windows equivalent to point them at.
needs_a_pty = pytest.mark.skipif(
    not hasattr(os, "openpty"),
    reason="a real pty; the `pty` module is POSIX-only")


def _init_on_a_pty(tmp_path, monkeypatch, *, answers, name="pvstudy"):
    """Run the real `crossaudit init` on a real terminal.

    `answers` maps a prompt marker to the keystroke sent once that marker has
    been drawn. Feeding on the PROMPT rather than on a timer is what makes this
    deterministic: an earlier attempt keyed on quiet time and silently fed the
    description into the API-key prompt, which produced a run that looked like a
    pass and had never drafted anything.
    """
    import pty
    import tty
    from crossaudit.providers import registry, replay

    project = tmp_path / name
    project.mkdir()
    transcripts = tmp_path / f"transcripts-{name}"
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{name}"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    monkeypatch.setenv("CROSSAUDIT_REPLAY_DIR", str(transcripts))
    # `input()` rather than `getpass`, so the key prompts read this pty.
    monkeypatch.setenv("CROSSAUDIT_SHOW_KEYS", "1")
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    replay.record(transcripts, system=DISTIL_SYSTEM,
                  prompt=f"The project owner says:\n\n{_DESCRIPTION.strip()}",
                  text=json.dumps(_DRAFT_REPLY))
    provider = wizard.VENDORS["anthropic"][0]
    monkeypatch.setitem(registry._PROVIDERS, provider, replay.complete)
    monkeypatch.chdir(project)

    master, slave = pty.openpty()
    tty.setraw(slave)
    drawn: list[bytes] = []
    stop = threading.Event()

    def drain():
        # Polled rather than blocking: on macOS `os.close(master)` does not
        # return while another thread is parked in `os.read(master)`, so a
        # blocking drainer turns any failure in here into a hung suite instead
        # of a reported one. Found exactly that way.
        while not stop.is_set():
            if not select.select([master], [], [], 0.05)[0]:
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                return
            if not chunk:
                return
            drawn.append(chunk)

    drainer = threading.Thread(target=drain, daemon=True)
    drainer.start()
    saved = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = os.fdopen(slave, "r", buffering=1)
    # write_through, not line buffering: `input()` writes its prompt WITHOUT a
    # trailing newline, so a line-buffered stream holds it and the feeder below
    # waits forever for a marker that has been produced but not yet flushed.
    sys.stdout = io.TextIOWrapper(open(os.dup(slave), "wb", buffering=0),
                                  write_through=True, errors="replace")
    sys.stderr = sys.stdout
    finished: list[object] = []

    def go():
        try:
            main.cmd_init(argparse.Namespace(
                path=str(project), github=False, force=True, no_console=True,
                json=False, auditor_vendor="anthropic",
                auditor_model="claude-opus-4", generator_vendor="openai",
                generator_model="gpt-5", profile=None))
        except BaseException as exc:                # reported below
            finished.append(exc)
        finished.append("done")

    def plain() -> str:
        return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "",
                      b"".join(drawn).decode("utf-8", "replace"))

    worker = threading.Thread(target=go, daemon=True)
    try:
        worker.start()
        # Raw mode means no CR->LF translation, so every line answer ends in LF.
        for marker, stroke in answers:
            deadline = time.monotonic() + 20
            while marker not in plain() and not finished:
                if time.monotonic() > deadline:
                    raise AssertionError(
                        f"setup never asked for {marker!r}. It drew:\n{plain()}")
                time.sleep(0.02)
            if finished:
                break
            os.write(master, stroke)
            time.sleep(0.08)
        worker.join(timeout=30)
        assert not worker.is_alive(), f"init never returned. It drew:\n{plain()}"
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved
        stop.set()
        drainer.join(timeout=2)
        os.close(master)
    for item in finished:
        if isinstance(item, BaseException):
            raise item
    return project, plain()


_TO_THE_PROPOSAL = [
    ("key — the auditor", b"\n"),
    ("key — the generator", b"\n"),
    ("your project, in a sentence", _DESCRIPTION.encode() + b"\n"),
    ("These rules:", b"1"),
]
_AFTER = [("Project name", b"\n")]


def _checks_line(project: Path) -> str:
    return next(line for line in
                (project / "crossaudit.yml").read_text().splitlines()
                if line.startswith("checks:"))


@needs_a_pty
def test_the_inference_is_shown_as_a_proposal_with_its_grounds(
        tmp_path, monkeypatch):
    project, out = _init_on_a_pty(
        tmp_path, monkeypatch, name="accept",
        answers=[*_TO_THE_PROPOSAL, ("Automatic checks:", b"1"), *_AFTER])
    flat = re.sub(r"\s+", " ", out)

    # It is a proposal, and the reasons are the person's own rules and words.
    assert "Your rules ask for things CrossAudit can check mechanically" in flat
    assert "CA-DATA-001 Every reported quantity carries a unit → schema, units" in flat
    assert 'from what you said: "every reported number must carry a unit"' in flat
    # Both outcomes are named before either is taken.
    assert "Use the Science & data checks" in flat
    assert "Keep the General checks" in flat
    # And it never claims to be changing the rules, which are already theirs.
    assert "they never change what your rules say" in flat

    # Accepting it reaches the file that decides what actually runs.
    assert _checks_line(project) == "checks: [schema, units, convergence, provenance]"
    rules = (project / "AUDIT_RULES.md").read_text()
    assert "CA-DATA-001" in rules and "<PROJECT>" not in rules


@needs_a_pty
def test_the_proposal_can_be_refused_and_refusing_it_changes_the_file(
        tmp_path, monkeypatch):
    """Refusal is the half that makes it a proposal rather than an announcement."""
    project, out = _init_on_a_pty(
        tmp_path, monkeypatch, name="decline",
        answers=[*_TO_THE_PROPOSAL, ("Automatic checks:", b"2"), *_AFTER])
    assert "chose 2) Keep the General checks" in re.sub(r"\s+", " ", out)
    assert _checks_line(project) == "checks: [parseable, declared, internal, complete]"
    # The drafted rules are still the person's; only the machine checks differ.
    assert "CA-DATA-001" in (project / "AUDIT_RULES.md").read_text()


@needs_a_pty
def test_a_prose_project_is_never_asked_at_all(tmp_path, monkeypatch):
    """No grounds, no proposal — the walkthrough's project must see nothing."""
    from crossaudit.providers import replay
    prose = ("a review of the PV industry for a general audience; it should read "
             "clearly and not contradict its sources")
    reply = {"project_summary": "An industry review.", "domain": "prose review",
             "rules": [{"id": "CA-CONTENT-001", "severity": "BLOCKER",
                        "title": "It does what was asked.",
                        "criterion": "the review answers the brief",
                        "from_user": "a review of the PV industry"}]}

    real_record = replay.record

    def record_prose(directory, *, system, prompt, text):
        return real_record(directory, system=system,
                           prompt=f"The project owner says:\n\n{prose}",
                           text=json.dumps(reply))

    monkeypatch.setattr(replay, "record", record_prose)
    project, out = _init_on_a_pty(
        tmp_path, monkeypatch, name="prose",
        answers=[("key — the auditor", b"\n"), ("key — the generator", b"\n"),
                 ("your project, in a sentence", prose.encode() + b"\n"),
                 ("These rules:", b"1"), *_AFTER])
    assert "Automatic checks:" not in out
    assert "check mechanically" not in out
    assert _checks_line(project) == "checks: [parseable, declared, internal, complete]"


def test_silence_still_never_selects_the_laboratory_contract(
        tmp_path, monkeypatch, capsys):
    """With no terminal there is nobody to propose to, so nothing is proposed.

    A default taken by a pipe is not a decision. This is batch 2's rule, and it
    is why the proposal is gated on `tui.interactive()` rather than merely
    defaulting to the general pack.
    """
    from crossaudit.providers import registry, replay
    project = tmp_path / "quiet"
    project.mkdir()
    transcripts = tmp_path / "transcripts-quiet"
    monkeypatch.setenv("HOME", str(tmp_path / "home-quiet"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / "keys-quiet.env"))
    monkeypatch.setenv("CROSSAUDIT_REPLAY_DIR", str(transcripts))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    replay.record(transcripts, system=DISTIL_SYSTEM,
                  prompt=f"The project owner says:\n\n{_DESCRIPTION.strip()}",
                  text=json.dumps(_DRAFT_REPLY))
    monkeypatch.setitem(registry._PROVIDERS,
                        wizard.VENDORS["anthropic"][0], replay.complete)
    spoken = wizard.tui.text
    monkeypatch.setattr(wizard.tui, "text", lambda prompt, default="", **kw: (
        _DESCRIPTION if "your project" in prompt else spoken(prompt, default, **kw)))
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5", profile=None))
    out = capsys.readouterr().out
    # The draft happened — otherwise this asserts over the wrong situation.
    assert "Rules drafted from what you said" in re.sub(r"\s+", " ", out)
    assert "Automatic checks:" not in out
    assert _checks_line(project) == "checks: [parseable, declared, internal, complete]"


# ------------------------------------------- D10: demonstrate the guards fail
@needs_a_pty
def test_the_proposal_guards_fail_when_the_pack_is_taken_without_asking(
        tmp_path, monkeypatch):
    """Mutate the real product back to the behaviour that caused the harm.

    Mutation: `_propose_check_pack` applies the inferred pack and shows nothing —
    which is what the CLI did before batch 2, and what the walkthrough met as a
    BLOCKER about `metadata.yml` it had never agreed to. Checked against a live
    unmutated run in the same session rather than a recorded snapshot (D10).
    """
    project, honest = _init_on_a_pty(
        tmp_path, monkeypatch, name="base",
        answers=[*_TO_THE_PROPOSAL, ("Automatic checks:", b"2"), *_AFTER])
    assert "Automatic checks:" in honest
    assert _checks_line(project) == "checks: [parseable, declared, internal, complete]"

    def silently_apply(drafted, chosen):
        proposal = wizard.infer_check_pack(drafted, chosen)
        return proposal.key if proposal else chosen

    monkeypatch.setattr(wizard, "_propose_check_pack", silently_apply)
    mutated, out = _init_on_a_pty(
        tmp_path, monkeypatch, name="silent",
        answers=[*_TO_THE_PROPOSAL, *_AFTER])
    assert "Automatic checks:" not in out, (
        "the mutation did not take; this demonstration proves nothing")
    assert _checks_line(mutated) == "checks: [schema, units, convergence, provenance]", (
        "the mutation did not take; this demonstration proves nothing")


def test_the_grounds_guard_fails_when_the_inference_stops_needing_reasons(
        tmp_path, monkeypatch):
    """Mutation: propose on a single incidental match instead of a shape."""
    drafted = _draft(_ONE)
    assert wizard.infer_check_pack(drafted, "general") is None

    monkeypatch.setattr(wizard, "SCIENCE_GROUNDS_REQUIRED", 1)
    assert wizard.infer_check_pack(drafted, "general") is not None, (
        "the mutation did not take; this demonstration proves nothing")
