"""Slice A — the chat lane: a direct, unaudited conversational answer.

A simple question ("what is 1+1") gets an immediate generator reply in the
conversation, labeled as unaudited, with no build, no audit, and no admission.
A work request must never land here — the router biases toward generator when
in doubt — and nothing the generator says reaches the auditor (P2). Faults
refuse cleanly and are never ledgered as answers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from crossaudit import router as router_mod
from crossaudit.cli import talk as talk_mod
from crossaudit.console import server as server_mod
from crossaudit.console.page import PAGE
from crossaudit.console.streams import auditor_stream, generator_stream
from crossaudit.errors import ConfigDenial, ProviderDenial


@dataclass
class Reply:
    text: str


def _routing(text="hi", lane="chat", confidence=0.95):
    return router_mod.Routing(
        utterance=text, lane=lane, confidence=confidence,
        reasoning="conversational", restated=text, t=1, chat_id="a" * 16)


# ------------------------------------------------------------- lane_chat unit
def test_lane_chat_returns_the_generator_answer(monkeypatch):
    monkeypatch.setattr(talk_mod, "_generator_chat_complete",
                        lambda cfg: lambda *, system, prompt: Reply("Hello!"))
    executed = talk_mod.lane_chat(SimpleNamespace(), _routing("hi"))
    # The prefix is the wire contract streams reconstruction depends on.
    assert executed == "answered by generator: Hello!"


def test_lane_chat_refuses_an_empty_reply(monkeypatch):
    monkeypatch.setattr(talk_mod, "_generator_chat_complete",
                        lambda cfg: lambda *, system, prompt: Reply("   "))
    with pytest.raises(ConfigDenial, match="empty"):
        talk_mod.lane_chat(SimpleNamespace(), _routing("hi"))


def test_chat_prompt_contains_only_the_user_words(cfg, monkeypatch):
    """P2: the chat lane transmits the user's words alone — no project files,
    no Constitution text, no audit records; and the system prompt says so."""
    sent = {}

    def fake_complete(cfg_):
        def complete(*, system, prompt):
            sent.update(system=system, prompt=prompt)
            return Reply("2")
        return complete

    monkeypatch.setattr(talk_mod, "_generator_chat_complete", fake_complete)
    routing = _routing("what is 1+1")
    talk_mod.lane_chat(cfg, routing)
    assert sent["prompt"] == "what is 1+1"          # exactly the user's words
    rules = (cfg.root / cfg.constitution).read_text()
    marker = next(line for line in rules.splitlines() if "CA-" in line)
    assert marker not in sent["system"] and marker not in sent["prompt"]
    assert "No project files" in sent["system"]
    assert "no audit reviewed this reply" in sent["system"].lower() or \
           "no build ran" in sent["system"].lower()


def test_router_biases_work_requests_to_generator_not_chat():
    """The split that keeps audit intact: chat is described as only for
    sentences no other lane could execute, and work stays generator."""
    assert "chat" in router_mod.LANES
    assert "it is generator, not chat" in router_mod.ROUTER_SYSTEM


def test_safe_default_continues_ambiguous_chat_without_a_build():
    raw = router_mod.route("thanks!", complete=lambda *, system, prompt: Reply(
        json.dumps({"lane": "chat", "confidence": 0.4, "reasoning": "greeting",
                    "restated": "thanks!", "clarify": "chat or work?"})))
    routed = router_mod.apply_safe_default(raw)
    assert routed.certain and routed.lane == "chat"
    assert routed.confidence == 0.4                  # observable in the ledger
    assert routed.routing_mode == "automatic_safe_default"
    assert "nothing was generated or audited" in routed.reasoning


# ------------------------------------------------------------- server say()
def test_say_chat_answers_without_starting_a_build(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda *_a, **_k: _routing("thanks!"))
    monkeypatch.setattr(server_mod, "start_build",
                        lambda *_a, **_k: pytest.fail("chat must never build"))
    monkeypatch.setattr(talk_mod, "_record_routing",
                        lambda _c, decision, executed: seen.update(
                            decision=decision, executed=executed))
    monkeypatch.setattr(talk_mod, "_generator_chat_complete",
                        lambda cfg_: lambda *, system, prompt: Reply("You bet."))
    result = server_mod.say(cfg, "thanks!", chat_id="history")
    assert result["asked"] is False and result["lane"] == "chat"
    assert result["executed"] == "answered by generator: You bet."
    assert seen["executed"] == "answered by generator: You bet."


def test_say_refuses_attachments_on_the_chat_lane(cfg, monkeypatch):
    recorded = {}
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda *_a, **_k: _routing("hi"))
    monkeypatch.setattr(talk_mod, "_record_routing",
                        lambda _c, decision, executed: recorded.update(
                            executed=executed))
    result = server_mod.say(cfg, "hi", attachments=[object()],
                            attachment_consent=True, chat_id="history")
    assert result["executed"].startswith(
        "refused — attachments are accepted only for generator tasks")
    assert recorded["executed"].startswith("refused")


# ------------------------------------------------------------------ streams
def _stream_cfg(tmp_path):
    return SimpleNamespace(root=tmp_path, ledger_dir="cycles", scope_dirs=[])


def test_chat_turn_reconstructs_as_question_then_answer(tmp_path):
    rows = generator_stream(_stream_cfg(tmp_path), [
        {"lane": "chat", "utterance": "hi", "t": 1, "chat_id": "a" * 16,
         "executed": "answered by generator: Hello."}], commits=[])
    assert [r["kind"] for r in rows] == ["you", "generator_chat"]
    assert rows[1]["response"] == "Hello."
    assert rows[1]["chat_id"] == "a" * 16


def test_chat_turns_never_enter_the_auditor_stream(tmp_path):
    rows = auditor_stream(_stream_cfg(tmp_path), [
        {"lane": "chat", "utterance": "hi", "t": 1, "chat_id": "a" * 16,
         "executed": "answered by generator: Hello."}], commits=[])
    assert rows == []                                 # P2: nothing crosses over


def test_a_denied_chat_never_fabricates_an_answer_turn(tmp_path):
    rows = generator_stream(_stream_cfg(tmp_path), [
        {"lane": "chat", "utterance": "hi", "t": 1, "chat_id": "a" * 16,
         "executed": "denied: model unavailable"}], commits=[])
    assert [r["kind"] for r in rows] == ["you"]       # question shown, no reply


# ------------------------------------------------------------ fault injection
def test_provider_exception_during_chat_is_a_clean_refusal(cfg, monkeypatch):
    recorded = {}
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda *_a, **_k: _routing("hi"))
    monkeypatch.setattr(talk_mod, "_record_routing",
                        lambda _c, decision, executed: recorded.update(
                            executed=executed))

    def boom(cfg_):
        def complete(*, system, prompt):
            raise ProviderDenial("model unavailable")
        return complete

    monkeypatch.setattr(talk_mod, "_generator_chat_complete", boom)
    result = server_mod.say(cfg, "hi", chat_id="history")
    assert result["executed"].startswith("refused — model unavailable")
    assert recorded["executed"].startswith("denied:")
    assert "answered by generator" not in recorded["executed"]


def test_empty_chat_reply_is_ledgered_as_denied_not_answered(cfg, monkeypatch):
    recorded = {}
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda *_a, **_k: _routing("hi"))
    monkeypatch.setattr(talk_mod, "_record_routing",
                        lambda _c, decision, executed: recorded.update(
                            executed=executed))
    monkeypatch.setattr(talk_mod, "_generator_chat_complete",
                        lambda cfg_: lambda *, system, prompt: Reply(""))
    result = server_mod.say(cfg, "hi", chat_id="history")
    assert result["executed"].startswith("refused — ")
    assert recorded["executed"].startswith("denied:")


# ------------------------------------------------------------- PAGE contracts
def test_page_renders_the_generator_chat_turn_kind():
    assert "generator_chat" in PAGE
    assert "conversational reply · not audited" in PAGE


def test_page_explains_a_failed_admission_with_options():
    assert "admissionCard" in PAGE and "lastAdmission" in PAGE
    assert "What would make it admissible" in PAGE
    assert "No work was lost" in PAGE
    # The historical strip line survives for continuity.
    assert "Not admitted." in PAGE


def test_chat_and_admission_strings_have_chinese_parity():
    for en in ("conversational reply · not audited",
               "direct reply · no project files shared",
               "Answered.", "Not admitted.", "Admitted.", "Try again",
               "What would make it admissible"):
        assert f'"{en}"' in PAGE, en                  # each has a ZH map entry
