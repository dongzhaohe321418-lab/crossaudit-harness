"""D4 provider streaming: latency, byte identity, and evidence separation."""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler

import pytest

from crossaudit.auditor import prompt as auditor_prompt
from crossaudit.broker.routing import evidence_view
from crossaudit.config import Role, load
from crossaudit.errors import ConfigDenial, ProviderDenial
from crossaudit.ledger import EvidenceLedger
from crossaudit.providers import base as provider_base
from crossaudit.providers import openai_compat, resilience
from crossaudit.providers.base import Reply, sha256_text
from crossaudit.receipt import build as build_receipt
from crossaudit.runtime import RunEvent, RunJournal, RunState

from .loopback import NumericLoopbackHTTPServer


TEXT = "First visible token · 中文 · final text"


def _event(content: str, *, usage: dict | None = None) -> bytes:
    row = {
        "id": "fixture-request",
        "choices": ([{"delta": {"content": content}}]
                    if content else []),
    }
    if usage is not None:
        row["usage"] = usage
    return ("data: " + json.dumps(row, ensure_ascii=False)
            + "\n\n").encode("utf-8")


class _Fixture:
    """One loopback adapter fixture serving equivalent JSON and SSE replies."""

    def __init__(self) -> None:
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802 -- BaseHTTPRequestHandler contract
                size = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(size))
                fixture.payloads.append(payload)
                if not payload.get("stream"):
                    time.sleep(0.32)
                    body = json.dumps({
                        "id": "fixture-request",
                        "choices": [{"message": {"content": TEXT}}],
                        "usage": {"prompt_tokens": 4, "completion_tokens": 7},
                    }, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.send_header("request-id", "header-request")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("request-id", "header-request")
                self.end_headers()
                time.sleep(0.04)
                first = _event("First visible token · ")
                self.wfile.write(first)
                self.wfile.flush()
                time.sleep(0.24)
                tail = (_event("中文") + _event(" · final text")
                        + _event("", usage={
                            "prompt_tokens": 4, "completion_tokens": 7,
                        }) + b"data: [DONE]\n\n")
                marker = tail.index("中".encode("utf-8"))
                # Force two transport boundaries inside this three-byte code
                # point; the adapter must decode incrementally, never replace.
                for part in (tail[:marker + 1], tail[marker + 1:marker + 2],
                             tail[marker + 2:]):
                    self.wfile.write(part)
                    self.wfile.flush()
                    time.sleep(0.003)

        self.payloads: list[dict] = []
        self.server = NumericLoopbackHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def _complete(base_url: str, *, on_chunk=None) -> Reply:
    return openai_compat.complete(
        model="fixture-model", system="system", prompt="prompt",
        key_env="CROSSAUDIT_TEST_KEY", base_url=base_url,
        allow_custom=True, timeout=2, on_chunk=on_chunk)


def test_streaming_reduces_silence_and_preserves_assembled_commitment(monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_TEST_KEY", "local-fixture-key")
    chunks: list[tuple[float, str, dict]] = []
    with _Fixture() as fixture:
        streamed_at = time.monotonic()
        streamed = _complete(
            fixture.base_url,
            on_chunk=lambda text, stream:
            chunks.append((time.monotonic(), text, dict(stream))))
        stream_elapsed = time.monotonic() - streamed_at
        baseline_at = time.monotonic()
        baseline = _complete(fixture.base_url)
        baseline_elapsed = time.monotonic() - baseline_at

    first_text = next(row for row in chunks if row[1])
    ttft = first_text[0] - streamed_at
    assert ttft < 1.0 and ttft < baseline_elapsed
    assert stream_elapsed < baseline_elapsed + 0.15
    assert streamed.text == baseline.text == TEXT
    assert streamed.response_sha256 == baseline.response_sha256 == sha256_text(TEXT)
    assert streamed.raw["usage"] == baseline.raw["usage"]
    assert "".join(text for _, text, meta in chunks if not meta["done"]) == TEXT
    assert [meta["seq"] for _, _, meta in chunks] == list(range(len(chunks)))
    assert chunks[-1][2]["outcome"] == "complete"
    assert fixture.payloads[0]["stream"] is True
    assert "stream" not in fixture.payloads[1]


def test_incremental_decoder_preserves_every_adversarial_utf8_split():
    wire = (_event("A中文B") + b"data: [DONE]\n\n")
    marker = wire.index("中".encode("utf-8"))
    split_sets = [
        (1,), (marker + 1,), (marker + 2,),
        (marker + 1, marker + 2), (len(wire) - 1,),
    ]
    for splits in split_sets:
        chunks = []
        emitter = openai_compat._ChunkEmitter(
            lambda text, stream: chunks.append((text, dict(stream))))
        parser = openai_compat._ChatStream(emitter)
        start = 0
        for stop in (*splits, len(wire)):
            parser.feed(wire[start:stop])
            start = stop
        text = parser.finish()
        emitter.finish("complete")
        assert text == "A中文B"
        assert sha256_text(text) == hashlib.sha256("A中文B".encode("utf-8")).hexdigest()
        assert "".join(value for value, meta in chunks if not meta["done"]) == text


def test_stream_reader_preserves_size_cap_and_total_deadline(monkeypatch):
    class Response:
        def __init__(self, sock):
            self.sock = sock

        def fileno(self):
            return self.sock.fileno()

        def read1(self, size):
            return self.sock.recv(size)

    left, right = socket.socketpair()
    try:
        with pytest.raises(ProviderDenial, match="time budget"):
            provider_base._stream_body_within_deadline(
                Response(left), time.monotonic() + 0.04, lambda _raw: None)
    finally:
        left.close()
        right.close()

    left, right = socket.socketpair()
    try:
        monkeypatch.setattr(provider_base, "MAX_RESPONSE_BYTES", 5)
        right.sendall(b"123456")
        with pytest.raises(ProviderDenial, match="size cap"):
            provider_base._stream_body_within_deadline(
                Response(left), time.monotonic() + 1, lambda _raw: None)
    finally:
        left.close()
        right.close()


def test_provider_failure_flushes_residual_before_explicit_abort(
        monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_TEST_KEY", "local-fixture-key")
    chunks = []

    def fail_stream(_url, _payload, _headers, *, on_bytes, on_idle, timeout):
        on_bytes(_event("draft then fail"))
        raise ConfigDenial("injected provider failure")

    monkeypatch.setattr(openai_compat, "request_stream", fail_stream)
    with pytest.raises(ConfigDenial, match="injected provider failure"):
        openai_compat.complete(
            model="fixture", system="s", prompt="p",
            key_env="CROSSAUDIT_TEST_KEY",
            on_chunk=lambda text, stream:
            chunks.append((text, dict(stream))))

    assert [text for text, _ in chunks] == ["draft then fail", ""]
    assert chunks[-1][1]["done"] is True
    assert chunks[-1][1]["outcome"] == "aborted"


def test_provider_coalesces_after_first_text_before_assigning_sequences():
    now = [10.0]
    chunks = []
    emitter = openai_compat._ChunkEmitter(
        lambda text, stream: chunks.append((text, dict(stream))),
        clock=lambda: now[0])
    emitter.feed("first")
    emitter.feed("second")
    now[0] += 0.199
    emitter.idle()
    assert [text for text, _ in chunks] == ["first"]
    now[0] += 0.002
    emitter.idle()
    emitter.feed("x" * (8 * 1024))
    emitter.finish("complete")

    assert chunks[1][0] == "second"
    assert len(chunks[2][0].encode("utf-8")) == 8 * 1024
    assert [meta["seq"] for _, meta in chunks] == list(range(len(chunks)))
    assert chunks[-1] == ("", {
        "id": chunks[0][1]["id"], "seq": len(chunks) - 1,
        "done": True, "outcome": "complete",
    })


def test_streaming_is_on_by_default_and_threads_to_every_capable_adapter(
        cfg, monkeypatch):
    """D150 (owner directive: thinking and progress start showing at once;
    never a long silent gap). This test used to pin streaming OFF by default and
    to the one adapter named ``openai_compat``. Both pins are reversed on
    purpose: the flag defaults to True, and the gate is the adapter's own
    ``supports_streaming`` capability, so Anthropic and every vendor preset
    built on the compatible adapter stream, while an adapter that declares
    nothing (replay) never receives a callback it cannot honour.

    Mutations: restore ``provider == "openai_compat"`` and the Anthropic call
    loses ``on_chunk``; restore the False default and the first call loses it.
    """
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return Reply("ok", "id", "a" * 64, "b" * 64)

    callback = lambda *_args: None
    on_event = lambda *_args: None
    on_event.on_chunk = callback
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "fixture")
    monkeypatch.setattr(resilience, "get_provider", lambda _name: provider)
    assert cfg.generator_streaming is True

    for provider_name in ("openai_compat", "anthropic", "deepseek", "google"):
        assert resilience.supports_streaming(provider_name), provider_name
        role = Role(provider_name, "fixture-model", "vendor",
                    "CROSSAUDIT_GENERATOR_KEY")
        resilience.complete(cfg, "generator", role, system="s", prompt="p",
                            on_event=on_event)
        assert calls[-1]["on_chunk"] is callback, provider_name

    assert not resilience.supports_streaming("replay")
    resilience.complete(cfg, "generator",
                        Role("replay", "fixture-model", "vendor",
                             "CROSSAUDIT_GENERATOR_KEY"),
                        system="s", prompt="p", on_event=on_event)
    assert "on_chunk" not in calls[-1]

    disabled = replace(cfg, generator_streaming=False)
    resilience.complete(disabled, "generator",
                        Role("anthropic", "fixture-model", "anthropic",
                             "CROSSAUDIT_GENERATOR_KEY"),
                        system="s", prompt="p", on_event=on_event)
    assert "on_chunk" not in calls[-1]


def test_generator_streaming_setting_is_boolean_and_on_by_default(
        science):
    """D150: the default flipped from False to True on the owner's directive;
    a project can still say ``streaming: false``, and a non-boolean is still
    refused. Mutation: default back to False and the first assertion is red."""
    path = science / "crossaudit.yml"
    assert load(path).generator_streaming is True
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace(
        "generator:\n  vendor: openai\n",
        "generator:\n  vendor: openai\n  streaming: false\n"),
        encoding="utf-8")
    assert load(path).generator_streaming is False
    path.write_text(path.read_text(encoding="utf-8").replace(
        "streaming: false", "streaming: yes-please"), encoding="utf-8")
    with pytest.raises(ConfigDenial, match="generator.streaming must be true or false"):
        load(path)


def test_streamed_sentinel_remains_operational_and_out_of_p2_surfaces(
        science, cfg):
    sentinel = "STREAM-DRAFT-ONLY-SENTINEL-5d91"
    journal = RunJournal(science / cfg.state_dir / "runtime.sqlite3")
    run_id = journal.start("stream separation")
    journal.append(run_id, RunEvent(
        kind="generation_chunk", actor="generator", text=sentinel,
        state=RunState.GENERATING,
        stream={"id": "sentinel-stream", "seq": 0, "done": False}))
    journal.append(run_id, RunEvent(
        kind="generation_chunk", actor="generator", text="",
        state=RunState.GENERATING,
        stream={"id": "sentinel-stream", "seq": 1, "done": True,
                "outcome": "aborted"}))

    ledger = EvidenceLedger(science / cfg.state_dir / "evidence.jsonl")
    ledger.append("note", run_id=run_id, payload={"status": "clean"}, ts="t0")
    evidence = evidence_view(cfg)
    prompt, _bounded, _digest = auditor_prompt.build(
        "rules", "c" * 40, {"findings": []}, {"work/a.txt": b"clean"},
        tool_evidence=evidence)
    receipt = build_receipt(
        cfg=cfg,
        subject={"sha": "a" * 40, "tree": "b" * 40, "scope": "experiments"},
        cycle={"cycle_id": "cycle", "root_sha": "a" * 40,
               "active_sha": "a" * 40, "round": 1},
        manifest={}, constitution_path=cfg.constitution,
        constitution_bytes=b"rules", constitution_commit="c" * 40,
        dcl_source_sha256="d" * 64, prompt_sha256="e" * 64,
        checks=[], verdict="PASS", exchange={}, retention="sealed",
        report_bytes=b"clean report", report_commit="f" * 40,
        cycle_path="cycles/clean", audit_repo="local", mode="local")
    commit_messages = subprocess.run(
        ["git", "log", "--format=%B"], cwd=science, check=True,
        capture_output=True, text=True).stdout

    assert sentinel in repr(journal.generation_events(run_id))
    assert sentinel not in (science / cfg.state_dir / "evidence.jsonl").read_text()
    assert sentinel not in repr(evidence)
    assert sentinel not in prompt
    assert sentinel not in commit_messages
    assert sentinel not in repr(receipt)


def test_response_digest_guard_goes_red_if_adapter_hashing_is_mutated(
        monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_TEST_KEY", "local-fixture-key")
    with _Fixture() as fixture:
        with monkeypatch.context() as mutant:
            mutant.setattr(openai_compat, "sha256_text",
                           lambda _text: "0" * 64)
            reply = _complete(fixture.base_url, on_chunk=lambda *_args: None)
            with pytest.raises(AssertionError):
                assert reply.response_sha256 == hashlib.sha256(
                    reply.text.encode("utf-8")).hexdigest()
