"""A completion the provider reports as cut off is refused, never returned.

The generator's file envelope deliberately tolerates a missing END marker
(``generator._extract_file_blocks``), so a reply stopped by the output-token
limit used to be parsed and its half-written file committed as if it were
complete. Both HTTP adapters now read the provider's own stop signal —
Anthropic ``stop_reason`` (non-stream body; ``message_delta`` in a stream) and
OpenAI-compatible ``finish_reason`` (``choices[0]`` in the body and in stream
chunks) — and raise a non-retryable ``truncated`` ProviderDenial instead.

Every case drives the real adapter: only the transport function the adapter
calls (``request_json`` / ``request_stream``) is stubbed, so the parser, the
stop-signal read and the refusal are what is executed. Each truncation case
has a happy-path twin with a normal stop reason, so the fix is shown not to
refuse finished replies.

D10 mutations (each checked by hand when this was written):
* delete the ``TRUNCATED_STOP_REASONS`` check in ``anthropic.complete`` — the
  non-stream Anthropic truncation cases go red (the half text is returned);
* delete it in ``anthropic._stream`` — the streamed Anthropic cases go red;
* delete the ``finish_reason`` capture in ``openai_compat._ChatStream._event``
  — the streamed OpenAI-compatible case goes red;
* delete the ``TRUNCATED_FINISH_REASONS`` check in the non-stream tail of
  ``openai_compat.complete`` — the non-stream OpenAI-compatible case goes red.
"""
from __future__ import annotations

import json

import pytest

from crossaudit import generator as gen_mod
from crossaudit.errors import ProviderDenial
from crossaudit.providers import anthropic, openai_compat

#: A reply that stops inside a file block: exactly the shape the tolerant
#: envelope parser would have accepted as a complete file.
HALF = ('SUMMARY: x\n<<<CROSSAUDIT-OUTPUT-FILE path="experiments/a.py">>>\n'
        'def f():\n    return [1, 2,')
WHOLE = ('SUMMARY: x\n<<<CROSSAUDIT-OUTPUT-FILE path="experiments/a.py">>>\n'
         'def f():\n    return [1, 2]\n<<<END-CROSSAUDIT-OUTPUT-FILE>>>')

ANTHROPIC_TRUNCATED = sorted(anthropic.TRUNCATED_STOP_REASONS)
#: Every other documented Anthropic stop reason, plus an absent one (an older
#: or compatible origin that omits the field is not second-guessed).
ANTHROPIC_FINISHED = ["end_turn", "stop_sequence", "tool_use", "pause_turn",
                      "refusal", None]
OPENAI_TRUNCATED = sorted(openai_compat.TRUNCATED_FINISH_REASONS)
OPENAI_FINISHED = ["stop", "content_filter", "tool_calls", None]


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_TEST_KEY", "local-fixture-key")


def _assert_truncated(caught, stop_reason, vendor):
    exc = caught.value
    assert exc.detail["category"] == "truncated"
    assert exc.detail["retryable"] is False
    assert exc.detail["stop_reason"] == stop_reason
    assert exc.detail["max_tokens"] == 4096
    # Retrying the identical request truncates again: never offered.
    assert "retry" not in exc.remediations
    assert exc.remediations[0] == "select_model"
    assert exc.reason.startswith(
        f"the reply from {vendor} was cut off at a token limit")
    assert "def f()" not in exc.reason         # the partial text is not echoed


# ---------------------------------------------------------------- anthropic
def _anthropic(monkeypatch, *, stop_reason, text=HALF, stream=False, chunks=None):
    if stream:
        def fake_stream(_url, _payload, _headers, *, timeout, on_bytes, on_idle):
            def sse(name, data):
                return (f"event: {name}\ndata: {json.dumps(data)}\n\n").encode()
            on_bytes(sse("message_start", {"type": "message_start", "message": {
                "id": "msg_1", "usage": {"input_tokens": 3}}}))
            on_bytes(sse("content_block_start", {
                "type": "content_block_start", "index": 0,
                "content_block": {"type": "text", "text": ""}}))
            on_bytes(sse("content_block_delta", {
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": text}}))
            on_bytes(sse("content_block_stop", {"type": "content_block_stop",
                                                "index": 0}))
            delta = {} if stop_reason is None else {"stop_reason": stop_reason}
            on_bytes(sse("message_delta", {"type": "message_delta", "delta": delta,
                                           "usage": {"output_tokens": 4096}}))
            on_bytes(sse("message_stop", {"type": "message_stop"}))
            return "rid"
        monkeypatch.setattr(anthropic, "request_stream", fake_stream)
    else:
        def fake_json(_url, _payload, _headers, *, timeout):
            body = {"id": "msg_1", "content": [{"type": "text", "text": text}],
                    "usage": {"output_tokens": 4096}}
            if stop_reason is not None:
                body["stop_reason"] = stop_reason
            return body, "rid"
        monkeypatch.setattr(anthropic, "request_json", fake_json)
    sink = chunks if chunks is not None else []
    on_chunk = ((lambda part, meta: sink.append((part, dict(meta))))
                if stream else None)
    return anthropic.complete(model="claude-fixture", system="s", prompt="p",
                              key_env="CROSSAUDIT_TEST_KEY", on_chunk=on_chunk)


@pytest.mark.parametrize("stop_reason", ANTHROPIC_TRUNCATED)
def test_anthropic_non_stream_truncation_is_refused(monkeypatch, stop_reason):
    with pytest.raises(ProviderDenial) as caught:
        _anthropic(monkeypatch, stop_reason=stop_reason)
    _assert_truncated(caught, stop_reason, "anthropic")


@pytest.mark.parametrize("stop_reason", ANTHROPIC_FINISHED)
def test_anthropic_non_stream_finished_reply_is_returned(monkeypatch, stop_reason):
    reply = _anthropic(monkeypatch, stop_reason=stop_reason, text=WHOLE)
    assert reply.text == WHOLE


@pytest.mark.parametrize("stop_reason", ANTHROPIC_TRUNCATED)
def test_anthropic_stream_truncation_is_refused_and_the_draft_aborted(
        monkeypatch, stop_reason):
    chunks: list = []
    with pytest.raises(ProviderDenial) as caught:
        _anthropic(monkeypatch, stop_reason=stop_reason, stream=True, chunks=chunks)
    _assert_truncated(caught, stop_reason, "anthropic")
    # The live draft is closed as aborted, never as a complete reply.
    assert chunks and chunks[-1][1]["done"] is True
    assert chunks[-1][1]["outcome"] == "aborted"


@pytest.mark.parametrize("stop_reason", ANTHROPIC_FINISHED)
def test_anthropic_stream_finished_reply_is_returned(monkeypatch, stop_reason):
    chunks: list = []
    reply = _anthropic(monkeypatch, stop_reason=stop_reason, text=WHOLE,
                       stream=True, chunks=chunks)
    assert reply.text == WHOLE
    assert chunks[-1][1]["outcome"] == "complete"


# ----------------------------------------------------------- openai_compat
def _openai(monkeypatch, *, finish_reason, text=HALF, stream=False, chunks=None):
    if stream:
        def fake_stream(_url, _payload, _headers, *, timeout, on_bytes, on_idle):
            def data(row):
                return ("data: " + json.dumps(row) + "\n\n").encode()
            on_bytes(data({"id": "c1", "choices": [{"index": 0, "delta": {
                "role": "assistant", "content": text}, "finish_reason": None}]}))
            # The terminal chunk: empty delta, finish reason set.
            on_bytes(data({"id": "c1", "choices": [{"index": 0, "delta": {},
                                                    "finish_reason": finish_reason}]}))
            on_bytes(b"data: [DONE]\n\n")
            return "rid"
        monkeypatch.setattr(openai_compat, "request_stream", fake_stream)
    else:
        def fake_json(_url, _payload, _headers, *, timeout):
            choice = {"index": 0, "message": {"role": "assistant", "content": text}}
            if finish_reason is not None:
                choice["finish_reason"] = finish_reason
            return {"id": "c1", "choices": [choice]}, "rid"
        monkeypatch.setattr(openai_compat, "request_json", fake_json)
    sink = chunks if chunks is not None else []
    on_chunk = ((lambda part, meta: sink.append((part, dict(meta))))
                if stream else None)
    return openai_compat.complete(model="fixture-model", system="s", prompt="p",
                                  key_env="CROSSAUDIT_TEST_KEY", on_chunk=on_chunk)


@pytest.mark.parametrize("finish_reason", OPENAI_TRUNCATED)
def test_openai_compat_non_stream_truncation_is_refused(monkeypatch, finish_reason):
    with pytest.raises(ProviderDenial) as caught:
        _openai(monkeypatch, finish_reason=finish_reason)
    _assert_truncated(caught, finish_reason, "openai")


@pytest.mark.parametrize("finish_reason", OPENAI_FINISHED)
def test_openai_compat_non_stream_finished_reply_is_returned(monkeypatch,
                                                             finish_reason):
    reply = _openai(monkeypatch, finish_reason=finish_reason, text=WHOLE)
    assert reply.text == WHOLE


@pytest.mark.parametrize("finish_reason", OPENAI_TRUNCATED)
def test_openai_compat_stream_truncation_is_refused_and_the_draft_aborted(
        monkeypatch, finish_reason):
    chunks: list = []
    with pytest.raises(ProviderDenial) as caught:
        _openai(monkeypatch, finish_reason=finish_reason, stream=True, chunks=chunks)
    _assert_truncated(caught, finish_reason, "openai")
    assert chunks and chunks[-1][1]["outcome"] == "aborted"


@pytest.mark.parametrize("finish_reason", OPENAI_FINISHED)
def test_openai_compat_stream_finished_reply_is_returned(monkeypatch,
                                                         finish_reason):
    chunks: list = []
    reply = _openai(monkeypatch, finish_reason=finish_reason, text=WHOLE,
                    stream=True, chunks=chunks)
    assert reply.text == WHOLE
    assert chunks[-1][1]["outcome"] == "complete"


def test_a_compatible_vendor_names_itself_in_the_refusal(monkeypatch):
    """The partials registered for other vendors pass ``_vendor``; the
    refusal names that vendor id rather than a generic word."""
    def fake_json(_url, _payload, _headers, *, timeout):
        return {"choices": [{"message": {"content": HALF},
                             "finish_reason": "length"}]}, "rid"
    monkeypatch.setattr(openai_compat, "request_json", fake_json)
    with pytest.raises(ProviderDenial) as caught:
        openai_compat.complete(model="m", system="s", prompt="p",
                               key_env="CROSSAUDIT_TEST_KEY",
                               base_url="http://127.0.0.1:9/v1", allow_custom=True,
                               _vendor="deepseek")
    assert caught.value.reason.startswith("the reply from deepseek was cut off")


# ---------------------------------------------------- the original defect
@pytest.mark.parametrize("stream", [False, True])
def test_a_truncated_reply_never_reaches_the_tolerant_file_parser(
        monkeypatch, stream):
    """The defect end to end at the generator seam: without the stop-signal
    check, ``parse_work_reply(HALF)`` returns the half file as complete work
    (asserted first, so this test fails loudly if that tolerance is ever
    removed and the premise changes). Through the adapter, ``generate`` sees a
    non-format denial and propagates it: no Work, no re-ask, no file."""
    assert gen_mod.parse_work_reply(HALF).files == {
        "experiments/a.py": "def f():\n    return [1, 2,"}
    calls = []

    def complete(*, system, prompt):
        calls.append(prompt)
        return _anthropic(monkeypatch, stop_reason="max_tokens", stream=stream)

    with pytest.raises(ProviderDenial) as caught:
        gen_mod.generate(task="write a.py", constitution="rules", current={},
                         complete=complete, allowed_dirs=["experiments"])
    assert caught.value.detail["category"] == "truncated"
    assert len(calls) == 1          # a truncation is not a format slip: no re-ask


# ------------------------------------------------- the loop records the stop
def test_a_truncated_generator_reply_parks_the_real_build_loop(
        science, cfg, monkeypatch):
    """The full stack below the transport: ``run_loop`` → ``generate`` →
    ``_generator_complete`` → ``resilience.complete`` → the openai_compat
    adapter, with only ``request_json`` / ``request_stream`` stubbed to report
    ``finish_reason: length``.

    What this pins: the non-retryable truncation is tried once per configured
    route (no retry loop), rolls up into the resilience layer's
    ``routes_exhausted`` refusal, and the build loop records it as a parked run
    with a cycle-side escalation whose reason carries the truncation sentence.
    It is never an unhandled exception, never a PASS, and the half file is
    never written or committed.

    D10 mutation: disable the ``TRUNCATED_FINISH_REASONS`` check in
    ``openai_compat`` (both paths) — the loop parses the half file, applies
    and commits it, and proceeds to the audit; in this fixture the replay
    auditor has no transcript, so the run fails with a ConfigDenial and this
    goes red (checked by hand).
    """
    from dataclasses import replace

    from crossaudit.cli import build as build_mod
    from crossaudit.controller import StateStore
    from crossaudit.errors import EXIT_ESCALATED
    from crossaudit.gitio import git
    from crossaudit.runtime import PreparedRun, RunCommandService

    calls = []

    def fake_json(_url, _payload, _headers, *, timeout):
        calls.append("json")
        return {"id": "c1", "choices": [{"message": {"content": HALF},
                                         "finish_reason": "length"}]}, "rid"

    def fake_stream(_url, _payload, _headers, *, timeout, on_bytes, on_idle):
        calls.append("stream")
        on_bytes(("data: " + json.dumps({"id": "c1", "choices": [{
            "delta": {"content": HALF}, "finish_reason": "length"}]})
            + "\n\ndata: [DONE]\n\n").encode())
        return "rid"

    monkeypatch.setattr(openai_compat, "request_json", fake_json)
    monkeypatch.setattr(openai_compat, "request_stream", fake_stream)
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "local-fixture-key")
    monkeypatch.chdir(science)
    # A real adapter on the generator side, reached through the registry; no
    # fallback route, so one route is tried exactly once.
    scoped = replace(cfg, scope_dirs=["experiments"],
                     generator_provider="openai_compat",
                     generator_model="gpt-fixture", generator_fallbacks=())
    head_before = git("rev-parse", "HEAD", cwd=science)

    service = RunCommandService(scoped)
    code = service.start(
        lambda: PreparedRun(task="write experiments/a.py"),
        lambda prepared, emit: build_mod.run_loop(
            scoped, prepared.task, on_event=emit),
        background=False)

    assert code == EXIT_ESCALATED
    assert len(calls) == 1                       # not retried with the same budget
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["waiting_reason"]["category"] == "routes_exhausted"
    assert "was cut off at a token limit" in row["waiting_reason"]["detail"]

    store = StateStore(scoped.root / scoped.state_dir / "state.json")
    escalated = [c for c in store.snapshot()["cycles"].values()
                 if c["status"] == "ESCALATED"]
    assert escalated, "the stop must be a recorded decision, not a silent end"
    assert "was cut off at a token limit" in escalated[-1]["escalation_reason"]
    assert not any(c["status"] == "PASSED"
                   for c in store.snapshot()["cycles"].values())

    # The half file never reached the tree or a commit.
    assert not (science / "experiments" / "a.py").exists()
    log = git("log", "--format=%H", f"{head_before}..HEAD", cwd=science)
    for sha in log.split():
        assert "experiments/a.py" not in git(
            "show", "--name-only", "--format=", sha, cwd=science)
