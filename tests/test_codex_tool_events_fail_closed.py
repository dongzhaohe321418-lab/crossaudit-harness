"""A Codex subscription turn with any tool event is refused, its text discarded (D170, S2).

SECURITY.md: "any command, file-change, web, or tool event makes the provider
round fail closed." Before D170 the adapter only recorded such events on the
collector and returned the turn's text with ``blocked_tool_requests``
attached. These tests run the real ``_complete_in_workspace`` over a scripted
App Server event stream and sweep every forbidden item type, plus the
server-initiated request path through the real ``_read`` loop.

D10 mutation run by hand: deleting the ``if collector.forbidden:`` block in
``_complete_in_workspace`` turns every refusal case here red (the text comes
back) while the clean-turn cases stay green.
"""
from __future__ import annotations

import io
import json

import pytest

from crossaudit.errors import ProviderDenial
from crossaudit.providers import codex_subscription

TEXT = "a perfectly ordinary text answer"


def _server_with_stream(monkeypatch, events):
    server = codex_subscription.CodexAppServer("/fake/codex")

    def call(method, _params, **_kwargs):
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            collector = server._collectors["thread-1"]
            for event in events:
                collector.accept(event)
            collector.accept({"method": "turn/completed", "params": {
                "threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed"}}})
            return {"turn": {"id": "turn-1"}}
        raise AssertionError(method)

    monkeypatch.setattr(server, "call", call)
    return server


def _item(kind):
    return {"method": "item/completed", "params": {
        "threadId": "thread-1", "item": {"type": kind}}}


def _delta(text):
    return {"method": "item/agentMessage/delta", "params": {
        "threadId": "thread-1", "delta": text}}


def _complete(server, tmp_path):
    return server._complete_in_workspace(
        cwd=str(tmp_path), model="gpt-5.6-sol", system="s", prompt="p",
        reasoning_effort=None, timeout=1)


@pytest.mark.parametrize("kind", sorted(codex_subscription.FORBIDDEN_ITEM_TYPES))
@pytest.mark.parametrize("order", ["tool_then_text", "text_then_tool", "tool_only"])
def test_every_tool_item_refuses_the_turn_and_discards_its_text(
        kind, order, tmp_path, monkeypatch):
    events = {"tool_then_text": [_item(kind), _delta(TEXT)],
              "text_then_tool": [_delta(TEXT), _item(kind)],
              "tool_only": [_item(kind)]}[order]
    server = _server_with_stream(monkeypatch, events)
    with pytest.raises(ProviderDenial) as caught:
        _complete(server, tmp_path)
    denial = caught.value
    assert denial.detail["category"] == "response"
    assert denial.detail["blocked_tool_requests"] == [kind]
    assert f"requested {kind} in a text-only role" in denial.reason
    assert TEXT not in json.dumps(denial.as_dict())


def test_the_four_kinds_security_md_names_are_all_forbidden():
    """command, file-change, web and tool events, by their protocol names."""
    assert {"commandExecution", "fileChange", "webSearch", "mcpToolCall",
            "dynamicToolCall"} <= codex_subscription.FORBIDDEN_ITEM_TYPES


def test_several_tool_kinds_are_named_once_each(tmp_path, monkeypatch):
    server = _server_with_stream(monkeypatch, [
        _item("webSearch"), _item("commandExecution"), _item("webSearch"),
        _delta(TEXT)])
    with pytest.raises(ProviderDenial) as caught:
        _complete(server, tmp_path)
    assert caught.value.detail["blocked_tool_requests"] == [
        "commandExecution", "webSearch"]


@pytest.mark.parametrize("method", [
    "item/commandExecution/requestApproval", "item/fileChange/requestApproval",
    "item/tool/call", "execCommandApproval"])
def test_a_server_initiated_tool_request_refuses_the_turn(method, tmp_path, monkeypatch):
    """Through the real `_read` loop: the request is answered with an error,
    recorded on the collector, and the completion is then refused."""
    server = codex_subscription.CodexAppServer("/fake/codex")
    sent = []
    monkeypatch.setattr(server, "_send", sent.append)

    def call(m, _params, **_kwargs):
        if m == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if m == "turn/start":
            lines = [json.dumps(x) + "\n" for x in (
                {"id": 99, "method": method, "params": {"threadId": "thread-1"}},
                _delta(TEXT),
                {"method": "turn/completed", "params": {"threadId": "thread-1",
                 "turn": {"id": "turn-1", "status": "completed"}}})]
            proc = type("P", (), {"stdout": io.StringIO("".join(lines))})()
            # server._proc stays None, so the end of this scripted stdout is not
            # mistaken for the runtime dying (which would fail the turn anyway).
            server._read(proc)
            return {"turn": {"id": "turn-1"}}
        raise AssertionError(m)

    monkeypatch.setattr(server, "call", call)
    with pytest.raises(ProviderDenial) as caught:
        _complete(server, tmp_path)
    assert caught.value.detail["blocked_tool_requests"] == [method]
    assert TEXT not in json.dumps(caught.value.as_dict())
    assert sent and sent[0]["id"] == 99 and sent[0]["error"]["code"] == -32601


@pytest.mark.parametrize("harmless", [
    [], [_item("agentMessage")], [_item("reasoning")], [_item("userMessage")]])
def test_a_clean_turn_still_returns_its_text(harmless, tmp_path, monkeypatch):
    server = _server_with_stream(monkeypatch, [*harmless, _delta(TEXT)])
    reply = _complete(server, tmp_path)
    assert reply.text == TEXT
    assert reply.raw["blocked_tool_requests"] == []


def test_another_threads_tool_event_does_not_refuse_this_turn(tmp_path, monkeypatch):
    other = {"method": "item/completed", "params": {
        "threadId": "thread-2", "item": {"type": "commandExecution"}}}
    server = _server_with_stream(monkeypatch, [other, _delta(TEXT)])
    assert _complete(server, tmp_path).text == TEXT
