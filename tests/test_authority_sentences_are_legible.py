"""The evidence-authority sentences a person reads have a Chinese form.

D148 review B made the route row, the integrity clauses and the rationale
plain words. Plain English is still English to the person D25 is about, so
every sentence the decision can compose — enumerated by driving the shipped
`decide_authority` over the same grid review B used — is translated at the
CLI seam (`i18n.sentence_zh`), with counts carried and clauses translated in
turn. The console renders none of these (the Decision Center says the same
thing in its own sentence, and route names are kept off every surface by
design), so the seam under test is the CLI's.
"""
from __future__ import annotations

import itertools
import re

import pytest

from crossaudit.auditor import authority as authority_mod
from crossaudit.auditor.authority import (INTEGRITY_IN_WORDS, ROUTE_LABELS,
                                          _INTEGRITY_FALLBACK)
from crossaudit.cli import i18n
from crossaudit.errors import CONTESTED_MODEL_BLOCKER_REASON

from .test_evidence_authority import DCL_BLOCKER, MODEL_BLOCKED, _decide, _records

CJK = re.compile(r"[一-鿿]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
INTEGRITIES = ["OK", "NOTHING_AUDITED", "BOUNDS_EXCEEDED", "INVALID_REPLY",
               "PROVIDER_FAILURE", "NON_EVIDENTIAL_PROVIDER", "SOMETHING_NEW"]
VERDICTS = ["PASS", "BLOCKED", "ESCALATE", "DCL_ONLY"]
FLAG_SETS = [dict(), dict(escalation_lock=True), dict(scope_started=False),
             dict(model_decided=True, lone_model_blocker="escalate")]


def _every_rationale_sentence() -> set[str]:
    out: set[str] = set()
    for integrity, verdict, flags in itertools.product(INTEGRITIES, VERDICTS, FLAG_SETS):
        for records in ((), _records(DCL_BLOCKER, MODEL_BLOCKED)):
            out.update(_decide(records, verdict, integrity=integrity, **flags).rationale)
    return out


def test_every_sentence_the_decision_can_write_is_chinese_at_the_seam():
    """Driven, not read: the grid is the one review B used, so a new branch
    in `_rationale` lands here the moment it is reachable. Mutation: remove
    any SENTENCES_ZH entry — red, naming the sentence."""
    sentences = _every_rationale_sentence()
    assert len(sentences) >= 12, f"the grid has drifted: {len(sentences)}"
    english = sorted(s for s in sentences if i18n.sentence_zh(s) is None)
    assert english == [], f"rationale a Chinese reader meets in English: {english}"
    half = sorted(s for s in sentences if LATIN_WORD.search(i18n.sentence_zh(s)))
    assert half == [], f"half-translated (a clause slot left in English): {half}"


def test_route_labels_integrity_clauses_and_the_escalate_sentence():
    for text in [*ROUTE_LABELS.values(), *INTEGRITY_IN_WORDS.values(),
                 _INTEGRITY_FALLBACK, CONTESTED_MODEL_BLOCKER_REASON]:
        rendered = i18n.sentence_zh(text)
        assert rendered and CJK.search(rendered) and not LATIN_WORD.search(rendered), text


def test_counts_are_carried_and_a_clause_slot_is_translated_in_turn():
    rendered = i18n.sentence_zh(
        "3 deterministic check failure(s) on committed bytes block this round; "
        "the block rests on reproduced evidence.")
    assert rendered and "3" in rendered and not LATIN_WORD.search(rendered)
    composed = i18n.sentence_zh("The model audit could not run, so a person owns this round.")
    assert composed == "模型审计无法运行，因此本轮由人来负责。"


def test_no_entry_is_for_a_sentence_nobody_writes():
    """An entry whose English no longer appears in the source is one that rots.
    Each literal chunk of an entry (around its slots) must be in
    `auditor/authority.py` or `cli/main.py`, allowing for the f-string and
    line-wrapped forms the source uses."""
    import inspect

    from crossaudit import errors as errors_mod
    from crossaudit.cli import main as main_mod

    source = (inspect.getsource(authority_mod) + inspect.getsource(main_mod)
              + inspect.getsource(errors_mod))
    flat = re.sub(r'"\s*\n\s*f?"', "", source)  # join wrapped string literals
    orphans = []
    for english, _zh in i18n.SENTENCES_ZH:
        chunks = [c.strip(" ,") for c in english.split("{}")]
        if not all(c in flat for c in chunks if len(c) >= 8):
            orphans.append(english)
    assert orphans == [], f"entries for sentences nobody writes: {orphans}"
    keys = [e for e, _ in i18n.SENTENCES_ZH]
    assert len(keys) == len(set(keys)), "duplicate English keys"


def test_sentence_text_marks_and_counts_a_gap_the_way_t_does():
    i18n.set_language("zh")
    i18n.reset_fallbacks()
    try:
        assert i18n.sentence_text("your decision") == "由你决定"
        assert i18n.sentence_text("a sentence with no entry") == "[en] a sentence with no entry"
        assert i18n.fallbacks() == ("sentence:a sentence with no entry",)
    finally:
        i18n.set_language("en")
        i18n.reset_fallbacks()
    assert i18n.sentence_text("your decision") == "your decision"


def test_the_escalated_line_translates_only_our_own_sentence():
    """Review defect 4: the auditor's invalid-reply prose must never pass
    through the sentence seam (it would be marked `[en]` and counted as OUR
    missing entry), and the literal fallback is a catalogue key."""
    import inspect

    from crossaudit.cli import main as main_mod

    source = inspect.getsource(main_mod.cmd_run)
    assert "i18n.sentence_text(rationale[0])" in source
    assert "sentence_text(why)" not in source and "sentence_text(outcome.invalid_reason" not in source
    assert 'i18n.t("run.human_decision_needed")' in source
    i18n.set_language("zh")
    try:
        assert i18n.t("run.human_decision_needed") == "需要人工决定"
    finally:
        i18n.set_language("en")
    assert i18n.t("run.human_decision_needed") == "a human decision is needed"


def test_the_denial_seam_is_unchanged_by_sharing_its_compiler():
    """`denial_zh` was refactored onto the shared compiler; its answers and
    its ordering rule (fewest slots, then most literal text) must not move."""
    assert i18n.denial_zh("/nope is not a git repository") == "/nope 不是 git 仓库"
    assert i18n.denial_zh("a sentence with no entry") is None
