"""Every fixed phrase of ours that lands in a refusal's slot is translated with
the sentence (review 2026-10-23 round 13 follow-up). The ruling, escalation
and ledger refusals carry, in their parentheses, phrases written in our code
-- why an escalation is not committed, how a git step failed, why the
committed log could not be read. Each is a clause entry and its sentence a
composite, so a Chinese reader never meets them in English; the runtime
fixture carries every variant for the half-translation guard.

Mutation caught: dropping any clause below from `denials_zh.CLAUSES` (or a
composite from `COMPOSITES`) -- that phrase comes back in English inside a
Chinese sentence.
"""
from __future__ import annotations

import re

import pytest

from crossaudit.cli import i18n

CID = "60aa693f05b053a7"
ESC = ("the escalation of cycle {cid} is not committed to the ledger ({why}); rule on "
       "it after the repository is repaired")
RULING = ("the ruling on cycle {cid} could not be committed to the ledger ({why}); the "
          "cycle stays ESCALATED and nothing was recorded")
READ = "the committed rulings log could not be read ({why}); no ruling is made until it can be"

PHRASES = [
    (ESC, "the ledger holds no verified escalation row for it"),
    (ESC, "escalated by an older version of CrossAudit"),
    (ESC, "escalated by an older version of CrossAudit, and committing its escalation "
          "now failed: git commit failed and said nothing"),
    (ESC, "the ledger's latest escalation of this cycle is 0123456789ab, not ba9876543210"),
    (ESC, "its escalation row was not committed"),
    (ESC, "no project configuration was found for this state"),
    (ESC, "the committed escalation row could not be confirmed"),
    (ESC, "git commit timed out after 90s"),
    (ESC, "the committed escalation row could not be confirmed: git cat-file timed out "
          "after 5s"),
    (RULING, "git commit failed and said nothing"),
    (RULING, "the log could not be written: No space left on device"),
    (RULING, "git add could not run: No such file or directory"),
    (RULING, "the log could not be read: Permission denied"),
    (READ, "git rev-parse HEAD failed"),
    (READ, "git ls-tree failed"),
    (READ, "git cat-file failed"),
    (READ, "it is not UTF-8"),
    (READ, "a line is not JSON"),
    (READ, "a line is not a ruling"),
]
#: Words of the phrases above that must not survive into the Chinese.
OURS = re.compile(r"\b(ledger|escalation|older version|committing|said nothing|timed out|"
                  r"could not|is not|a line)\b")


@pytest.mark.parametrize("template,why", PHRASES)
def test_the_phrase_in_the_slot_is_translated(template, why):
    reason = template.format(cid=CID, why=why)
    rendered = i18n.denial_zh(reason)
    assert rendered is not None, reason
    assert not OURS.search(rendered), rendered


def test_the_status_line_translates_its_reason():
    i18n.set_language("zh")
    try:
        assert i18n.clause_text("escalated by an older version of CrossAudit") == \
            "由旧版 CrossAudit 升级"
        assert i18n.t("status.escalation_not_committed", why=i18n.clause_text(
            "the ledger holds no verified escalation row for it")) == \
            "升级未提交（账本中没有它的经过验证的升级行）"
    finally:
        i18n.set_language("en")
    assert i18n.clause_text("its escalation row was not committed") == \
        "its escalation row was not committed"
