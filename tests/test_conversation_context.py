"""Conversation context — a follow-up inherits the chat's real intent.

The reported failure, reproduced from the app: a chat asked for a review, was
corrected to "qled", then the person typed "continue". Because a continuation
was committed as the literal word "continue" (a goal that names no subject), the
generator filled it from a stale file in the working tree (a Transformer review)
and the auditor — judging that file against the vacuous task — passed it. The fix
is context management: a bare "continue" resolves to the chat's latest real
request, and the generator is given the conversation as read-only grounding.
"""
from __future__ import annotations

from dataclasses import dataclass

from crossaudit import generator as gen
from crossaudit import router
from crossaudit.auditor import prompt as apm
from crossaudit.runtime import RunJournal

CHAT = "f6f85568528fc263"


def _journal(tmp_path):
    return RunJournal(tmp_path / "runtime.sqlite3")


def _turn(journal, task, *, chat_id=CHAT, continuation_cycle="", outcome="escalated"):
    run_id = journal.start(task, chat_id=chat_id,
                           continuation_cycle=continuation_cycle)
    journal.finish(run_id, outcome)
    return run_id


# ---- the durable intent is stored and can be read back ----
def test_latest_intent_is_the_newest_substantive_request(tmp_path):
    j = _journal(tmp_path)
    _turn(j, "Write a detailed review.")
    _turn(j, "Replace the incorrect prior content with qled.")
    assert j.latest_intent(CHAT) == "Replace the incorrect prior content with qled."


def test_a_continuation_run_does_not_become_the_intent(tmp_path):
    # run #3 ("continue") must NOT overwrite the durable intent — it names no
    # subject, so latest_intent still returns the qled correction.
    j = _journal(tmp_path)
    _turn(j, "Write a detailed review.")
    _turn(j, "Replace the incorrect prior content with qled.")
    _turn(j, "continue", continuation_cycle="3336749bf5158e67", outcome="passed")
    assert j.latest_intent(CHAT) == "Replace the incorrect prior content with qled."


def test_latest_intent_is_isolated_per_chat(tmp_path):
    j = _journal(tmp_path)
    _turn(j, "Generate an essay on Cambridge.", chat_id="aaaaaaaaaaaaaaaa")
    _turn(j, "Write a detailed review of qled.", chat_id=CHAT)
    assert j.latest_intent(CHAT) == "Write a detailed review of qled."
    assert j.latest_intent("aaaaaaaaaaaaaaaa") == "Generate an essay on Cambridge."


def test_latest_intent_empty_when_no_prior_request(tmp_path):
    assert _journal(tmp_path).latest_intent(CHAT) == ""
    assert _journal(tmp_path).latest_intent("") == ""


# ---- chat_history: oldest-first grounding, excluding the current run ----
def test_chat_history_is_oldest_first_and_excludes_the_current_run(tmp_path):
    j = _journal(tmp_path)
    _turn(j, "Write a detailed review.")
    _turn(j, "Replace the incorrect prior content with qled.")
    current = j.start("continue", chat_id=CHAT, continuation_cycle="3336749bf5158e67")
    hist = j.chat_history(CHAT, exclude_run_id=current)
    tasks = [row["task"] for row in hist]
    assert tasks == ["Write a detailed review.",
                     "Replace the incorrect prior content with qled."]
    assert all(row["task"] != "continue" for row in hist)


# ---- resolve_continuation: the crux of the fix ----
def test_bare_continue_inherits_the_prior_intent():
    prior = "Replace the incorrect prior content with qled."
    for nudge in ("continue", "  continue.", "继续", "接着写", "ok, continue",
                  "好 继续", "", "go on"):
        assert router.resolve_continuation(nudge, prior) == prior, nudge


def test_a_substantive_continuation_message_is_honored_verbatim():
    prior = "Write a detailed review of qled."
    fresh = "actually make it about OLED instead, 500 words"
    assert router.resolve_continuation(fresh, prior) == fresh


def test_bare_continue_with_no_prior_intent_keeps_the_words():
    # Nothing to inherit → do not fabricate; keep today's behavior (the reopened
    # cycle's own committed task still applies downstream).
    assert router.resolve_continuation("continue", "") == "continue"


# ---- the generator is handed the conversation as subordinate grounding ----
def test_build_prompt_renders_the_conversation_block_below_the_task():
    convo = "- the person asked: Write a detailed review of qled."
    prompt = gen.build_prompt(task="continue", constitution="rules",
                              current={}, conversation=convo)
    assert "EARLIER IN THIS CONVERSATION" in prompt
    assert "qled" in prompt
    # THE TASK stays first and authoritative; the conversation is background.
    assert prompt.index("THE TASK") < prompt.index("EARLIER IN THIS CONVERSATION")
    assert "authoritative" in prompt


def test_build_prompt_has_no_conversation_block_without_context():
    prompt = gen.build_prompt(task="do it", constitution="rules", current={})
    assert "EARLIER IN THIS CONVERSATION" not in prompt


@dataclass
class _Reply:
    text: str


def test_generate_threads_conversation_into_the_prompt():
    seen = {}

    def complete(*, system, prompt):
        seen["prompt"] = prompt
        return _Reply('<<<CROSSAUDIT-OUTPUT-FILE path="experiments/demo/x.md">>>\n'
                      "ok\n<<<END-CROSSAUDIT-OUTPUT-FILE>>>\nNOTES:")

    gen.generate(task="continue", constitution="rules", current={},
                 complete=complete, allowed_dirs=["experiments"],
                 conversation="- the person asked: make it about qled")
    assert "EARLIER IN THIS CONVERSATION" in seen["prompt"]
    assert "qled" in seen["prompt"]


# ---- the payoff: a non-vacuous task re-arms the auditor's subject check ----
def test_resolving_the_continuation_gives_the_auditor_a_subject_to_enforce():
    files = {"work/review.md": b"# Attention Is All You Need\nA Transformer review."}
    vacuous, _, _ = apm.build("CONST", "abc123", {}, files, task="continue")
    resolved, _, _ = apm.build(
        "CONST", "abc123", {}, files,
        task=router.resolve_continuation(
            "continue", "Write a detailed review of qled."))
    # The literal "continue" gives CA-TASK-001 no subject — the exact hole that
    # let a Transformer review pass when the person had asked for qled.
    assert "qled" not in vacuous
    # Once the continuation inherits the real intent, the committed-task block the
    # auditor judges against names qled, so a review about something else is a
    # substituted requirement CA-TASK-001 can block.
    assert "qled" in resolved
    assert "COMMITTED TASK REQUIREMENTS" in resolved
