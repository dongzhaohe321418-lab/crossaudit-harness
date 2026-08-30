"""S4 — when earlier turns are folded, the person is told.

**The class, not just the widget.** A sweep of what our instruments cannot see
named absence-of-event defects as the worst blind mode: no artifact, consumer or
identity exists to inspect while the person experiences unexplained silence. The
founding defect of this workstream was exactly that — a send that failed while
the interface showed nothing.

`_conversation_context` computed the fact and kept it. When a chat outgrew its
six-turn window it wrote `(+N earlier turn(s) in this chat, not shown)` **into
the generator's prompt** and emitted nothing. Every other reduction on this path
raises a `context_condensed` notice: work_files, tool_results, compute_results,
owner_guidance. Earlier turns was the one that did not, so the console had
nothing to show because nothing was sent.

**Producer-side, and that was a finding rather than a preference.** The consumer
already existed and was complete — `streams.context_stream` projects the notice,
`page.py` renders it from `summary_i18n`, `progress.py` holds the catalogue. So
the client needed nothing invented, and specifically no client-side inference of
when condensation happened: a page that guesses that is a page that will
eventually guess wrong.

**The property, and why it needs three states.** Condensed-and-announced,
condensed-silently and not-condensed must all be distinguishable. The trap is
that the last two look IDENTICAL from the console — no notice either way — so a
guard that only checks "is there a notice" cannot tell a healthy short chat from
a silent regression. Every assertion below therefore establishes that
condensation OCCURRED, independently of the notice, and only then asks whether
the person was told.

Assertions are over what the notice CONTAINS, never over how many exist. Eight
empty regions prove wiring, not speech.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from crossaudit.cli.build import EARLIER_TURNS_NOTICE, _conversation_context
from crossaudit.config import load
from crossaudit.console import progress, streams
from crossaudit.runtime.events import RunEvent
from crossaudit.runtime.runs import RunJournal, RunState, journal_path

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")

# Read FROM THE PRODUCT at call time, never restated here and never bound at
# import. A guard that asserts on the wording the test author picked is not a
# guard on what the product says — the defect that survived a whole audit round
# on the send path. Binding it at import has the same effect under a mutation:
# the constant would still be the unmutated one.
def _notice() -> str:
    import crossaudit.cli.build as build_module
    return build_module.EARLIER_TURNS_NOTICE


#: The source the wiring claim reads. A module attribute so the mutation runner
#: can hand it the MUTATED text; reading the file directly would always see the
#: unmutated one and the mutation would survive for the harness's reason.
_SOURCE: str | None = None


def _build_source() -> str:
    import crossaudit.cli.build as build_module
    return _SOURCE if _SOURCE is not None else Path(build_module.__file__).read_text()
# The marker the generator's prompt carries. Reading it is how these tests know
# condensation happened WITHOUT asking the thing under test.
FOLDED = "earlier turn(s) in this chat, not shown"


@pytest.fixture()
def project(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    return load(root / "crossaudit.yml")


def _chat_of(cfg, turns: int) -> RunJournal:
    """A chat with `turns` finished runs, through the real journal."""
    path = journal_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    journal = RunJournal(path)
    for index in range(turns):
        run_id = journal.start(f"turn number {index}", chat_id="history")
        journal.append(run_id, RunEvent(actor="controller", text="done",
                                        kind="build_progress",
                                        state=RunState.PASSED))
    return journal


def _drive(cfg, turns: int):
    """Return (prompt, reports) — what the generator was shown, and what the
    person would be told. Both, because the defect is the gap between them."""
    _chat_of(cfg, turns)
    reports: list[dict] = []
    prompt = _conversation_context(cfg, "history", "no-such-run",
                                   on_condense=reports.append)
    return prompt, reports


# ---------------------------------------------------- the three states
def test_a_short_chat_is_not_condensed_and_says_nothing(project):
    prompt, reports = _drive(project, 3)
    assert FOLDED not in prompt, "the fixture must not condense, or it proves nothing"
    assert reports == [], (
        "a chat that was never condensed announced a condensation")


def test_a_condensed_chat_tells_the_person_it_happened(project):
    prompt, reports = _drive(project, 12)
    # Condensation OCCURRED — established from the prompt, not from the notice.
    assert FOLDED in prompt, "the fixture did not condense, so this proves nothing"
    assert len(reports) == 1, (
        "earlier turns were folded and nothing was announced — the person is "
        "not told that context was condensed")
    assert reports[0]["reduction"] == "earlier_turns"
    assert reports[0]["earlier"] > 0


def test_the_silent_state_is_distinguishable_from_the_quiet_one(project):
    """The two that look identical from the console. What separates them is
    whether condensation happened at all, so the guard reads the prompt."""
    short_prompt, short_reports = _drive(project, 3)
    assert (FOLDED in short_prompt, bool(short_reports)) == (False, False)


def test_the_condensed_state_is_distinguishable_from_both(project):
    long_prompt, long_reports = _drive(project, 12)
    assert (FOLDED in long_prompt, bool(long_reports)) == (True, True)


# ------------------------------------------------ what the notice CONTAINS
def test_the_notice_says_what_was_folded_and_that_nothing_is_gone(project):
    """"+N" alone is a number. The point is that the transcript is intact, and
    a person cannot act on a count they think represents loss."""
    _, reports = _drive(project, 12)
    detail = f"{int(reports[0]['earlier'])} turns"
    step = progress._project_context_step({
        "kind": "context_condensed", "text": _notice(), "detail": detail})

    english = step["text_i18n"]["en"]
    assert "Earlier turns" in english
    assert "summarised" in english
    assert "still here" in english, (
        "the notice states a count without stating that the conversation "
        "survives, which is the half a person can act on")
    assert step["detail_i18n"]["en"] == detail
    assert detail.startswith(str(reports[0]["earlier"]))


def test_the_chinese_notice_is_a_catalogue_entry_and_the_count_is_a_pattern(project):
    """The sentence is fixed and carries no number, so it can never fall back.
    The number lives in the detail and is translated by PATTERN — a fixed entry
    there would fall back to English the moment the count changed, and this
    affordance is nothing but a count."""
    _, reports = _drive(project, 12)
    step = progress._project_context_step({
        "kind": "context_condensed", "text": _notice(),
        "detail": f"{int(reports[0]['earlier'])} turns"})
    chinese = step["text_i18n"]["zh"]
    assert chinese != _notice(), "the sentence fell back to English"
    assert "已将本对话中较早的轮次概括" in chinese
    assert "完整对话仍保留在这里" in chinese
    # And the count, for several counts, so a single lucky number proves nothing.
    for count in (1, 2, 7, 42, 1000):
        translated = progress._detail_i18n(f"{count} turns")["zh"]
        assert translated == f"{count} 轮", (
            f"the count fell back to English at {count}")


def test_the_notice_reaches_the_projection_a_person_reads():
    """The consumer already existed. That is a reason to CHECK it, not to
    assume it: F7 was a correct transport with nothing consuming it."""
    row = {"chat_id": "history", "steps": [{
        "kind": "context_condensed", "text": _notice(), "detail": "6 turns",
        "t": 10, "round_no": 1, "event_id": 3}]}
    events = progress.context_events(row)
    assert len(events) == 1
    assert events[0]["text_i18n"]["zh"].startswith("已将本对话中较早的轮次")
    assert events[0]["detail_i18n"]["zh"] == "6 轮"


def test_the_caller_is_wired_to_the_observer():
    """A WIRING claim and nothing more, said plainly. The observer existing and
    the loop passing it are different facts, and the tests above call
    `_conversation_context` directly, so they cannot see the second one. Driving
    `run_loop` needs a provider; this asserts the seam instead and says so."""
    assert "on_condense=context_report)" in _build_source(), (
        "the loop no longer passes the observer, so condensation reports to "
        "nobody and the person is not told")


# ----------------------------------------------------------------- mutations
# D64: condensation WITHOUT the affordance is the mutation, and it must redden
# by name. Both ways to reintroduce the defect are covered — the producer can
# stop reporting, or the caller can stop listening — because closing one door
# and leaving the other is how this class survives a fix.
MUTATIONS = (
    ("the producer stops reporting, so a chat condenses and says nothing — "
     "the defect exactly as it shipped",
     "        if on_condense is not None:\n"
     "            on_condense({\"reduction\": \"earlier_turns\", \"earlier\": earlier})",
     "        pass"),
    ("the caller stops listening, so the observer exists and nothing is "
     "wired to it",
     "    conversation = _conversation_context(cfg, chat_id, run_id,\n"
     "                                        on_condense=context_report)",
     "    conversation = _conversation_context(cfg, chat_id, run_id)"),
    ("the notice loses the half that says the conversation survives, leaving "
     "a bare count a person reads as loss",
     'EARLIER_TURNS_NOTICE = ("Earlier turns in this chat were summarised for the "\n'
     '                        "generator; the full conversation is still here")',
     'EARLIER_TURNS_NOTICE = "Earlier turns in this chat were summarised"'),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:36] for m in MUTATIONS])
def test_the_guard_is_shown_to_fail(why, before, after, project, monkeypatch):
    """Break the product on purpose and read WHICH assertion fires, not merely
    that one did."""
    import crossaudit.cli.build as build_module

    source = Path(build_module.__file__).read_text()
    assert source.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved and this "
        f"guard is no longer known to catch it")
    namespace: dict = {"__name__": "crossaudit.cli.build",
                       "__file__": build_module.__file__}
    exec(compile(source.replace(before, after), build_module.__file__, "exec"),
         namespace)
    mutated = source.replace(before, after)
    monkeypatch.setattr(build_module, "_conversation_context",
                        namespace["_conversation_context"])
    monkeypatch.setattr(build_module, "EARLIER_TURNS_NOTICE",
                        namespace["EARLIER_TURNS_NOTICE"])
    monkeypatch.setattr("tests.test_earlier_turns_affordance._conversation_context",
                        namespace["_conversation_context"])
    monkeypatch.setattr("tests.test_earlier_turns_affordance._SOURCE", mutated)

    caught = []
    for name, check in (
            ("condensed chat announces", test_a_condensed_chat_tells_the_person_it_happened),
            ("condensed is distinguishable", test_the_condensed_state_is_distinguishable_from_both),
            ("notice says nothing is gone", test_the_notice_says_what_was_folded_and_that_nothing_is_gone),
            ("caller is wired", lambda _cfg: test_the_caller_is_wired_to_the_observer())):
        try:
            check(project)
        except (AssertionError, IndexError) as exc:
            caught.append((name, str(exc).split("\n")[0][:110]))
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
