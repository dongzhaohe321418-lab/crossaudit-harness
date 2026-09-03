"""D150 — perceived latency: the POST returns at once and nothing is silent.

The owner's directive: after Send, thinking and progress start showing
immediately; never a long silent gap; the surface stays concise. These tests
drive the real console over HTTP with the provider stubbed to be slow, so the
property measured is the one a person feels — how long Send blocks, and what
the page can show while the message is being handled.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from crossaudit import router as router_mod
from crossaudit.cli import talk as talk_mod
from crossaudit.console import intake as intake_mod

from .node_eval import run_node
from .loopback import NumericLoopbackHTTPServer



def fetch(url: str, **headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode(), dict(r.headers)


def post_json_to(console: str, path: str, payload: dict):
    url = console.replace("/?t=", f"{path}?t=")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read()), dict(response.headers)


def settled_say(console: str, accepted: dict, timeout: float = 5.0) -> dict:
    """The result ``say()`` produced for an accepted message (D150)."""
    assert accepted.get("accepted") is True, accepted
    state_url = console.replace("/?t=", "/api/state?t=")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _status, raw, _headers = fetch(state_url)
        intake = json.loads(raw).get("intake") or {}
        if intake.get("id") == accepted["intake"] and intake.get("finished"):
            return intake
        time.sleep(0.02)
    raise AssertionError("the accepted message never settled")


@pytest.fixture()
def console(tmp_path: Path):
    from crossaudit.config import load
    from crossaudit.console import serve

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
        "checks: [parseable]\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def _routing(text: str, lane: str) -> router_mod.Routing:
    return router_mod.Routing(utterance=text, lane=lane, confidence=0.95,
                              reasoning="test", restated=text, t=1)


# ------------------------------------------------------------------ (a)
def test_send_returns_before_the_router_has_answered(console, monkeypatch):
    """(a) With the routing provider sleeping 2 s, POST /api/say answers in
    under 200 ms and the result arrives on the intake afterwards.

    Mutation: run ``say()`` inline in the handler again and the POST takes the
    provider's 2 s, which the latency bound refuses.
    """
    def slow_route(text, *, complete, context=""):
        time.sleep(2.0)
        return _routing(text, "chat")

    monkeypatch.setattr(router_mod, "route_addressed", slow_route)
    monkeypatch.setattr(talk_mod, "lane_chat",
                        lambda cfg, routing, on_event=None:
                        "answered by generator: Hello.")
    started = time.monotonic()
    status, body, _headers = post_json_to(console, "/api/say", {"text": "hi there"})
    latency = time.monotonic() - started
    assert status == 200 and body["accepted"] is True
    assert latency < 0.2, f"Send blocked for {latency:.3f}s"

    intake = settled_say(console, body, timeout=6)
    assert intake["result"]["lane"] == "chat"
    assert intake["result"]["executed"] == "answered by generator: Hello."


def test_the_page_can_show_progress_while_the_router_thinks(console, monkeypatch):
    """(b, intake half) received → routed → answering is on the state before
    the lane finishes, each line with EN and ZH copy and nothing internal."""
    gate = threading.Event()

    def route(text, *, complete, context=""):
        return _routing(text, "auditor")

    def lane(cfg, routing, on_event=None):
        gate.wait(5)
        return "answered by auditor: Fine."

    monkeypatch.setattr(router_mod, "route_addressed", route)
    monkeypatch.setattr(talk_mod, "lane_auditor", lane)
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "@auditor hi"})
    state_url = console.replace("/?t=", "/api/state?t=")
    deadline = time.monotonic() + 5
    kinds: list[str] = []
    while time.monotonic() < deadline:
        intake = json.loads(fetch(state_url)[1]).get("intake") or {}
        kinds = [step["kind"] for step in intake.get("steps", [])]
        if kinds[-1:] == ["answering"]:
            break
        time.sleep(0.02)
    assert kinds == ["received", "routed", "answering"], kinds
    assert intake["finished"] is False
    for step in intake["steps"]:
        assert step["text_i18n"]["en"] == step["text"]
        assert step["text_i18n"]["zh"] != step["text"], step
        assert len(step["text"]) <= 60
    gate.set()
    settled = settled_say(console, body)
    assert settled["result"]["executed"] == "answered by auditor: Fine."


def test_a_denial_in_the_worker_is_the_same_refusal_the_page_always_saw(
        console, monkeypatch):
    """A Denial raised while handling the message becomes the intake's error
    with its reason — the 400 the synchronous path used to send — never a
    traceback and never a silent composer."""
    from crossaudit.errors import ConfigDenial

    def route(text, *, complete, context=""):
        raise ConfigDenial("the router is not configured")

    monkeypatch.setattr(router_mod, "route_addressed", route)
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "hello"})
    settled = settled_say(console, body)
    assert settled["error"] == {"status": 400, "reason": "the router is not configured"}
    assert settled["result"] is None


def test_a_second_message_while_one_is_being_handled_is_refused_not_lost(
        console, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda text, **_k: _routing(text, "chat"))

    def lane(cfg, routing, on_event=None):
        gate.wait(5)
        return "answered by generator: ok"

    monkeypatch.setattr(talk_mod, "lane_chat", lane)
    _status, first, _headers = post_json_to(console, "/api/say", {"text": "one"})
    req = urllib.request.Request(
        console.replace("/?t=", "/api/say?t="), data=b'{"text":"two"}',
        method="POST", headers={"content-type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(req, timeout=5)
    assert caught.value.code == 409
    gate.set()
    assert settled_say(console, first)["result"]["executed"].startswith("answered")


def test_consent_is_still_checked_before_anything_is_accepted(console):
    """The consent boundary answers synchronously, as before: nothing is
    accepted, so nothing is narrated and no worker starts."""
    req = urllib.request.Request(
        console.replace("/?t=", "/api/say?t="),
        data=json.dumps({"text": "use it", "attachments": [{
            "name": "a.csv", "type": "text/csv",
            "data": "eCx5CjEsMgo="}], "attachment_consent": False}).encode(),
        method="POST", headers={"content-type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(req, timeout=5)
    assert caught.value.code == 400
    assert "explicit consent" in caught.value.read().decode()
    assert not intake_mod.INTAKE.active


# ------------------------------------------------------------------ (c)
THINKING = "Weighing the two readings of the task"
ANSWER = "First visible token · 中文 · final answer"


def _anthropic_sse(*events: tuple[str, dict]) -> bytes:
    out = b""
    for name, data in events:
        out += (f"event: {name}\ndata: "
                + json.dumps(data, ensure_ascii=False) + "\n\n").encode("utf-8")
    return out


class _AnthropicFixture:
    """A loopback Messages endpoint replaying one recorded stream with a
    thinking block before the text, split inside a multi-byte code point."""

    def __init__(self) -> None:
        fixture = self
        from http.server import BaseHTTPRequestHandler

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):  # noqa: N802
                size = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(size))
                fixture.payloads.append(payload)
                assert payload.get("stream") is True
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("request-id", "anthropic-header-rid")
                self.end_headers()
                head = _anthropic_sse(
                    ("message_start", {"type": "message_start", "message": {
                        "id": "msg_fixture", "usage": {"input_tokens": 4}}}),
                    ("content_block_start", {"type": "content_block_start", "index": 0,
                                             "content_block": {"type": "thinking"}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                             "delta": {"type": "thinking_delta",
                                                       "thinking": THINKING}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                             "delta": {"type": "signature_delta",
                                                       "signature": "sig"}}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                    ("content_block_start", {"type": "content_block_start", "index": 1,
                                             "content_block": {"type": "text"}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 1,
                                             "delta": {"type": "text_delta",
                                                       "text": "First visible token · "}}),
                )
                self.wfile.write(head)
                self.wfile.flush()
                time.sleep(0.24)
                tail = _anthropic_sse(
                    ("content_block_delta", {"type": "content_block_delta", "index": 1,
                                             "delta": {"type": "text_delta", "text": "中文"}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 1,
                                             "delta": {"type": "text_delta",
                                                       "text": " · final answer"}}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 1}),
                    ("message_delta", {"type": "message_delta",
                                       "delta": {"stop_reason": "end_turn"},
                                       "usage": {"output_tokens": 9}}),
                    ("message_stop", {"type": "message_stop"}),
                )
                marker = tail.index("中".encode("utf-8"))
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
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def test_anthropic_streams_text_and_thinking_on_separate_contiguous_streams(
        monkeypatch):
    """(c) The Messages SSE stream is parsed incrementally; text deltas become
    coalesced ``on_chunk`` calls with contiguous seq, thinking deltas become a
    separate ``on_thinking`` stream, and the reply commits to the text alone.

    Mutation: feed thinking into the text emitter and the reply text (and its
    digest) would carry THINKING, which the last assertions refuse.
    """
    import hashlib

    from crossaudit.providers import anthropic

    monkeypatch.setenv("CROSSAUDIT_TEST_KEY", "local-fixture-key")
    chunks: list[tuple[str, dict]] = []
    thoughts: list[tuple[str, dict]] = []
    with _AnthropicFixture() as fixture:
        reply = anthropic.complete(
            model="claude-fixture", system="system", prompt="prompt",
            key_env="CROSSAUDIT_TEST_KEY", base_url=fixture.base_url,
            allow_custom=True, timeout=2,
            on_chunk=lambda text, stream: chunks.append((text, dict(stream))),
            on_thinking=lambda text, stream: thoughts.append((text, dict(stream))))

    assert fixture.payloads[0]["stream"] is True
    assert reply.text == ANSWER
    assert reply.request_id == "anthropic-header-rid"
    assert reply.response_sha256 == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert reply.raw["usage"] == {"input_tokens": 4, "output_tokens": 9}

    assert "".join(text for text, _ in chunks) == ANSWER
    assert [meta["seq"] for _, meta in chunks] == list(range(len(chunks)))
    assert chunks[0][0] == "First visible token · "      # first text at once
    assert chunks[-1] == ("", {"id": chunks[0][1]["id"], "seq": len(chunks) - 1,
                               "done": True, "outcome": "complete"})
    assert len(chunks) < 6                                # coalesced, not per token

    assert "".join(text for text, _ in thoughts) == THINKING
    assert [meta["seq"] for _, meta in thoughts] == list(range(len(thoughts)))
    assert thoughts[0][1]["id"] != chunks[0][1]["id"]     # two streams, two ids
    assert thoughts[-1][1] == {"id": thoughts[0][1]["id"], "seq": len(thoughts) - 1,
                               "done": True, "outcome": "complete"}
    assert THINKING not in reply.text


def test_a_dropped_thinking_frame_is_refused_at_the_journal(tmp_path):
    """(c) Gap detection holds per stream kind: a thinking chunk whose seq
    skips is refused, and the text stream's own contiguity is judged apart
    from it (the two interleave in time by nature)."""
    from crossaudit.runtime import RunEvent, RunJournal, RunState

    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("stream it")

    def chunk(kind: str, stream_id: str, seq: int, text: str = "x") -> RunEvent:
        return RunEvent(kind=kind, actor="generator", text=text,
                        state=RunState.GENERATING,
                        stream={"id": stream_id, "seq": seq, "done": False})

    journal.append(run_id, chunk("thinking_chunk", "think", 0))
    journal.append(run_id, chunk("generation_chunk", "text", 0))
    journal.append(run_id, chunk("thinking_chunk", "think", 1))
    with pytest.raises(RuntimeError, match="not contiguous"):
        journal.append(run_id, chunk("thinking_chunk", "think", 3))
    journal.append(run_id, chunk("generation_chunk", "text", 1))
    kinds = [row["kind"] for row in journal.generation_events(run_id)]
    assert kinds == ["thinking_chunk", "generation_chunk", "thinking_chunk",
                     "generation_chunk"]
    assert all(step["kind"] not in ("thinking_chunk", "generation_chunk")
               for step in journal.latest()["steps"])


# ------------------------------------------------------------------ (e)
def test_thinking_text_never_reaches_the_auditor_prompt_commit_or_receipt(
        science, cfg):
    """(e) Same guard as the draft sentinel, for thinking. Mutation: append
    the thinking sentinel to the auditor prompt (or the receipt) and the
    assertions go red."""
    import subprocess as sp

    from crossaudit.auditor import prompt as auditor_prompt
    from crossaudit.broker.routing import evidence_view
    from crossaudit.receipt import build as build_receipt
    from crossaudit.runtime import RunEvent, RunJournal, RunState

    sentinel = "THINKING-ONLY-SENTINEL-7a2c"
    journal = RunJournal(science / cfg.state_dir / "runtime.sqlite3")
    run_id = journal.start("thinking separation")
    journal.append(run_id, RunEvent(
        kind="thinking_chunk", actor="generator", text=sentinel,
        state=RunState.GENERATING,
        stream={"id": "think", "seq": 0, "done": False}))
    journal.append(run_id, RunEvent(
        kind="thinking_chunk", actor="generator", text="",
        state=RunState.GENERATING,
        stream={"id": "think", "seq": 1, "done": True, "outcome": "complete"}))
    prompt, _bounded, _digest = auditor_prompt.build(
        "rules", "c" * 40, {"findings": []}, {"work/a.txt": b"clean"},
        tool_evidence=evidence_view(cfg))
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
    commit_messages = sp.run(["git", "log", "--format=%B"], cwd=science,
                             check=True, capture_output=True, text=True).stdout
    from crossaudit.console.progress import Tracker
    tracker = Tracker()
    tracker.bind(journal.path)

    assert sentinel in repr(journal.generation_events(run_id))
    assert sentinel not in prompt
    assert sentinel not in commit_messages
    assert sentinel not in repr(receipt)
    assert sentinel not in repr(tracker.snapshot())       # not a run-card step


def test_the_auditor_clock_narrates_time_and_never_the_reply_text():
    """The auditor's chunks drive one line per 10 s of arriving tokens and
    the chunk text is dropped on the floor. Mutation: pass the text through
    and the sentinel shows up in what was said."""
    from crossaudit.cli.build import _auditor_progress_clock

    now = [100.0]
    said: list[str] = []
    on_chunk = _auditor_progress_clock(said.append, clock=lambda: now[0])
    for step in range(0, 45, 3):
        now[0] = 100.0 + step
        on_chunk("VERDICT-DRAFT-SENTINEL", {"id": "a", "seq": step, "done": False})
    on_chunk("", {"id": "a", "seq": 99, "done": True, "outcome": "complete"})
    assert said == ["Still reviewing · 12 s", "Still reviewing · 24 s",
                    "Still reviewing · 36 s"]
    assert not any("SENTINEL" in line for line in said)


# ------------------------------------------------------------------ (b), L3
GOOD_INCREMENT = {
    "experiments/demo/metadata.yml":
        "code_version: a1b2c3d\ninputs:\n  - scripts/run_demo.py@a1b2c3d\n",
    "experiments/demo/results.json": json.dumps({
        "quantities": [
            {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
             "source": "scripts/run_demo.py@a1b2c3d"},
            {"name": "distance", "value": 2.73, "unit": "angstrom",
             "source": "scripts/run_demo.py@a1b2c3d"},
        ],
        "convergence": {"converged": True, "achieved": 7.4e-07, "threshold": 1e-06},
    }, indent=1),
    "experiments/demo/SUMMARY.md": "attempt one\n",
}
def test_run_checks_tells_an_observer_and_decides_nothing_by_it():
    """L3: ``run_checks(on_check=...)`` is additive — started/finished per
    check with the finding count — and the result is identical without it.
    Mutation: make the observer's presence skip a check and the two results
    differ."""
    from crossaudit.dcl import run_checks

    files = {"experiments/demo/results.json": b'{"quantities": [{"name": "x", "value": 1, "unit": "m", "source": "a@b"}], "convergence": {"converged": true, "achieved": 1e-7, "threshold": 1e-6}}'}
    seen: list[tuple[str, str, int]] = []
    observed = run_checks(files, ["schema", "units"],
                          on_check=lambda *row: seen.append(row))
    silent = run_checks(files, ["schema", "units"])
    assert [row[:2] for row in seen] == [("schema", "started"), ("schema", "finished"),
                                         ("units", "started"), ("units", "finished")]
    assert all(isinstance(row[2], int) for row in seen)
    assert observed.as_dict() == silent.as_dict()


def test_events_run_from_submit_to_verdict_in_the_owner_facing_order(
        science, cfg, monkeypatch):
    """(b) One build, providers stubbed: the journal-bound event order is
    goal → round_started → generation_started → preparing → prompt_ready →
    generation_chunk… → generation_completed → audit_started → check_* →
    auditor_reading → audit_passed, and every narrated line is concise.
    (received → routed precede these on the intake; see the HTTP tests.)

    Mutation: drop the ``preparing`` emit in run_loop and the order assertion
    fails; route a check event through ``provider_recovery`` and the kinds
    list loses ``check_finished``.
    """
    from crossaudit import generator as generator_mod
    from crossaudit.auditor import run as audit_run
    from crossaudit.cli import build as build_mod
    from crossaudit.providers.base import Reply, sha256_text
    PASS_REPLY = {"verdict": "PASS",
                  "sections_applied": ["CA-DATA-001", "CA-METH-002"],
                  "findings": []}

    events = []
    bridge = {}

    def complete_factory(_cfg, _allow_custom, on_event=None, _heartbeat=None, **_kw):
        bridge["provider"] = on_event

        def complete(*, system, prompt):
            on_event.on_chunk("draft text ", {"id": "s", "seq": 0, "done": False})
            on_event.on_thinking("weighing", {"id": "t", "seq": 0, "done": False})
            on_event.on_thinking("", {"id": "t", "seq": 1, "done": True, "outcome": "complete"})
            on_event.on_chunk("", {"id": "s", "seq": 1, "done": True, "outcome": "complete"})
            return Reply("ok", "id", "a" * 64, "b" * 64)
        return complete

    def fake_generate(**kwargs):
        kwargs["complete"](system="s", prompt="p")
        return generator_mod.Work(summary="attempt", files=GOOD_INCREMENT)

    def auditor_complete(_cfg, _role, _primary, *, system, prompt, **_kw):
        text = json.dumps(PASS_REPLY)
        return Reply(text, "audit-id", sha256_text(system + "\n" + prompt),
                     sha256_text(text), raw={})

    monkeypatch.setattr(build_mod, "_generator_complete", complete_factory)
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.setattr(audit_run.provider_resilience, "complete", auditor_complete)
    monkeypatch.chdir(science)
    from crossaudit.config import load
    cfg.path.write_text(cfg.path.read_text(encoding="utf-8")
                        + "scope:\n  dirs: [experiments]\n", encoding="utf-8")
    cfg = load(cfg.path)
    code = build_mod.run_loop(cfg, "produce the experiment", on_event=events.append)
    assert code == 0, [(e.kind, e.text) for e in events][-4:]

    kinds = [event.kind for event in events]
    # Review D6: the order is the order things happen in. "writing" used to be
    # announced before the workspace read it was waiting on, so the reader saw
    # the conclusion first and the reason for the pause underneath it.
    # Mutation: emit generation_started above preparing again and this goes red.
    expected = ["goal", "round_started", "preparing", "prompt_ready",
                "generation_started", "generation_chunk", "thinking_chunk",
                "generation_completed", "audit_started", "check_started",
                "check_finished", "auditor_reading", "audit_passed"]
    positions = [kinds.index(kind) for kind in expected]
    assert positions == sorted(positions), list(zip(expected, positions))
    assert kinds.count("check_started") == len(cfg.checks)
    assert kinds.count("check_finished") == len(cfg.checks)

    from crossaudit.console.progress import PHASE_KINDS, phase_i18n
    narrated = [event for event in events if event.kind in PHASE_KINDS]
    assert narrated, "no phase narration reached the journal"
    for event in narrated:
        assert len(event.text) <= 60, event.text
        assert phase_i18n(event.text)["zh"] != event.text, event.text
        assert not any(token in event.text for token in (":claude", ":gpt", "CA-")), event.text
    assert any(event.text.endswith("check passed") for event in narrated)
    assert any(event.text.startswith("The auditor is reading") for event in narrated)


# ------------------------------------------------------------------ (d)
def test_still_working_fires_after_eight_silent_seconds_and_not_otherwise():
    """(d) The phase clock, decided with a fake clock: silence in a narrated
    phase becomes one ``still_working`` line naming the phase and the seconds
    in it; activity resets the window; a phase the clock does not narrate
    stays silent. Mutation: drop the ``touch`` on emit and the second check
    fires early."""
    from crossaudit.runtime.pacing import PhaseClock

    now = [0.0]
    said: list[tuple[str, int]] = []
    clock = PhaseClock(lambda phase, secs: said.append((phase, secs)),
                       clock=lambda: now[0])
    clock.touch("generating")
    now[0] = 7.9
    assert clock.check() is False and said == []
    now[0] = 8.0
    assert clock.check() is True and said == [("generating", 8)]
    now[0] = 12.0
    assert clock.check() is False                     # the line itself was activity
    clock.touch("generating")                         # a chunk arrived
    now[0] = 19.9
    assert clock.check() is False
    now[0] = 20.0
    assert clock.check() is True and said[-1] == ("generating", 20)
    clock.touch("auditing")                           # phase change resets elapsed
    now[0] = 28.0
    assert clock.check() is True and said[-1] == ("auditing", 8)
    clock.touch(None)                                 # waiting for a person: quiet
    now[0] = 100.0
    assert clock.check() is False


def test_the_run_shell_appends_still_working_in_the_journal_with_the_phase(cfg):
    """(d) Under the command shell the line is a durable journal event in the
    run's current state, so the run card shows it like any other step and the
    page needs no timer. A cancelled run ends the clock instead of erroring."""
    from crossaudit.runtime import (PreparedRun, RunCommandService, RunEvent,
                                    RunJournal, RunState, journal_path)

    now = [1000.0]
    service = RunCommandService(cfg, clock=lambda: now[0], pace_interval=None)

    def worker(prepared, emit) -> int:
        emit(RunEvent(actor="generator", text="writing", kind="generation_started",
                      state=RunState.GENERATING, round_no=1, round_limit=3))
        now[0] += 9
        assert emit.phase_clock.check() is True
        emit(RunEvent(actor="auditor", text="reviewing the commit",
                      kind="audit_started", state=RunState.AUDITING,
                      round_no=1, round_limit=3))
        now[0] += 45
        assert emit.phase_clock.check() is True
        return 0

    service.start(lambda: PreparedRun(task="pace it"), worker, background=False)
    steps = RunJournal(journal_path(cfg)).latest()["steps"]
    lines = [(s["text"], s["state"], s["round_no"]) for s in steps
             if s["kind"] == "still_working"]
    assert lines == [("Still generating · 9 s", "GENERATING", 1),
                     ("Still auditing · 45 s", "AUDITING", 1)]

    from crossaudit.console.progress import project_snapshot
    projected = project_snapshot(RunJournal(journal_path(cfg)).latest())
    zh = [s["text_i18n"]["zh"] for s in projected["steps"] if s["kind"] == "still_working"]
    assert zh == ["仍在生成 · 9 秒", "仍在审计 · 45 秒"]


def test_the_intake_clock_speaks_while_the_router_is_silent():
    """(d) Same clock on the intake: eight silent seconds of routing produce
    one line; finishing the intake stops it."""
    from crossaudit.console.intake import Intake

    now = [0.0]
    intake = Intake(clock=lambda: now[0])
    intake.begin("a" * 16, "hello")
    now[0] = 7.0
    assert intake.check_silence() is False
    now[0] = 8.5
    assert intake.check_silence() is True
    steps = intake.snapshot()["steps"]
    assert [s["kind"] for s in steps] == ["received", "still_working"]
    assert steps[-1]["text"] == "Still routing · 8 s"
    assert steps[-1]["text_i18n"]["zh"] == "仍在判断由谁处理 · 8 秒"
    intake.routed("chat")
    intake.answering("chat")
    now[0] = 30.0
    assert intake.check_silence() is True
    assert intake.snapshot()["steps"][-1]["text"] == "Still replying · 21 s"
    intake.finish({"lane": "chat"})
    now[0] = 90.0
    assert intake.check_silence() is False
    intake.clear()


# ------------------------------------------------------------------ (f)
def _page_snippet(script: str, signature: str) -> str:
    start = script.index(signature)
    first_line = script[start:script.index("\n", start)]
    if signature.startswith("const ") and "{" not in first_line:
        # A one-expression arrow: runs to the first line that ends the statement.
        end = start
        while True:
            end = script.index("\n", end + 1)
            if script[start:end].rstrip().endswith(";"):
                return script[start:end]
    depth, i = 0, script.index("{", start)
    while i < len(script):
        depth += (script[i] == "{") - (script[i] == "}")
        if depth == 0:
            return script[start:i + 1]
        i += 1
    raise AssertionError(signature)


NEW_KINDS = ("received", "routed", "answering", "preparing", "prompt_ready",
             "still_working", "auditor_reading", "auditor_progress",
             "check_started", "check_finished")


def _sample_steps() -> list[dict]:
    texts = {
        "received": "Got it — working out who should handle this",
        "routed": "The generator will do this",
        "answering": "The generator is replying",
        "preparing": "Reading the workspace · 12 files",
        "prompt_ready": "Asking the generator to write",
        "still_working": "Still generating · 45 s",
        "auditor_reading": "The auditor is reading 3 files",
        "auditor_progress": "Still reviewing · 40 s",
        "check_started": "Running the Schema check",
        "check_finished": "Units check found 2 issues",
    }
    steps = [{"t": 1, "actor": "loop", "kind": kind, "text": text, "detail": "",
              "state": "GENERATING", "round_no": 1, "round_limit": 3}
             for kind, text in texts.items()]
    # Older events whose details carry identifiers the surface must not show.
    steps += [
        {"t": 2, "actor": "auditor", "kind": "audit_escalated", "text": "ESCALATED",
         "detail": "cycle " + "4a0cac15dc4e061b" + " is waiting for a human",
         "state": "AUDITING", "round_no": 1, "round_limit": 3},
        {"t": 3, "actor": "generator", "kind": "provider_recovery",
         "text": "provider recovery", "detail": "anthropic:claude-fable-5 · attempt 2",
         "state": "GENERATING", "round_no": 1, "round_limit": 3},
        {"t": 4, "actor": "auditor", "kind": "audit_blocked", "text": "BLOCKED",
         "detail": "[BLOCKER] CA-DATA-001 the value has no unit; [MAJOR] CA-METH-002 x",
         "state": "AUDITING", "round_no": 1, "round_limit": 3},
        {"t": 5, "actor": "loop", "kind": "goal", "text": "produce the experiment",
         "detail": json.dumps({"task": "x", "sha": "a" * 40}),
         "state": "QUEUED", "round_no": 0, "round_limit": 3},
        {"t": 6, "actor": "loop", "kind": "commit_refused",
         "text": "the round could not be committed",
         "detail": "commit " + "b" * 40 + " refused; see " + "c" * 12,
         "state": "GENERATING", "round_no": 1, "round_limit": 3},
    ]
    return steps


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_stream_renders_every_new_event_in_both_locales_without_identifiers(
        tmp_path):
    """(f) The shipped row model and renderer, driven under node over the server's own
    projection of every new event kind plus older events that carry
    identifiers. In zh every phase line is Chinese; in both locales the
    rendered HTML holds no 40-hex, no 16-hex, no 12-hex, no rule id, no
    provider:model route and no raw JSON.

    Mutations: drop ``text_i18n`` from ``wireLine`` and the zh assertion is
    red (the verb table's own Chinese would still be Chinese, so the test also
    checks the English sentence is not echoed); drop a scrub from
    conciseDetail and the identifier grep is red.
    """
    import re
    import subprocess as sp
    import sys

    from crossaudit.console import page as page_mod
    from crossaudit.console.progress import project_snapshot

    harness = Path(__file__).parent / "harness" / "extract_zh.py"
    zh_js = sp.run([sys.executable, str(harness), str(Path(page_mod.__file__).parents[3])],
                   capture_output=True, text=True, check=True).stdout
    script = page_mod.PAGE.split("<script>")[1].split("</script>")[0]
    pieces = [zh_js, "let currentLocale='en';",
              "const at=()=>'';",
              _page_snippet(script, "const esc = "),
              _page_snippet(script, "const localeText = "),
              _page_snippet(script, "const t = "),
              _page_snippet(script, "function durationText("),
              _page_snippet(script, "function humaniseDetail("),
              _page_snippet(script, "function conciseDetail("),
              _page_snippet(script, "function elapsedWords("),
              _page_snippet(script, "const ORB_STATES=") + ";",
              _page_snippet(script, "function orbStateFor("),
              _page_snippet(script, "function orbMarkup("),
              _page_snippet(script, "const EVENT_SHAPES=") + ";",
              _page_snippet(script, "const CARRIED_KINDS=") + ";",
              _page_snippet(script, "const EVENT_VERBS=") + ";",
              _page_snippet(script, "const ROW_SHAPES=") + ";",
              _page_snippet(script, "const ROW_UNITS=") + ";",
              _page_snippet(script, "const STEP_ACTORS=") + ";",
              _page_snippet(script, "const ROW_MARKS=") + ";",
              _page_snippet(script, "const ROW_KIND_MARKS=") + ";",
              _page_snippet(script, "function rowNumber("),
              _page_snippet(script, "function shapeOf("),
              _page_snippet(script, "function verbOf("),
              _page_snippet(script, "function wireLine("),
              _page_snippet(script, "function streamRow("),
              _page_snippet(script, "function actorOfStep("),
              _page_snippet(script, "function rowFromStep("),
              _page_snippet(script, "function rowText("),
              _page_snippet(script, "function rowMark("),
              _page_snippet(script, "function rowDetailHtml("),
              _page_snippet(script, "function rowActionHtml("),
              _page_snippet(script, "function row(")]
    projected = project_snapshot({"steps": _sample_steps()})["steps"]
    driver = "\n".join(pieces) + "\nconst STEPS=" + json.dumps(projected, ensure_ascii=False) + ";" + """
const out={};
for(const locale of ['en','zh']){currentLocale=locale;
  out[locale]=STEPS.map(s=>[s.kind,row(rowFromStep(s,{}),{})]);}
console.log(JSON.stringify(out));
"""
    (tmp_path / "rows.js").write_text(driver)
    run = sp.run(["node", str(tmp_path / "rows.js")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    rendered = json.loads(run.stdout)

    forbidden = re.compile(r"[a-f0-9]{40}|[a-f0-9]{16}|(?<![a-z0-9])[a-f0-9]{12}(?![a-z0-9])"
                           r"|CA-[A-Z]+-\d|:claude|:gpt|[{\[]\"")
    for locale in ("en", "zh"):
        html = "\n".join(row for _kind, row in rendered[locale])
        assert not forbidden.search(html), (locale, forbidden.search(html).group(0))
        assert "attempt 2" in html                     # the fact survives the scrub
        assert "this cycle is waiting for a human" in html
    kinds_seen = [kind for kind, _row in rendered["zh"]]
    assert set(NEW_KINDS) <= set(kinds_seen)
    for kind, row in rendered["zh"]:
        if kind in NEW_KINDS:
            assert re.search(r"[一-鿿]", row), (kind, row)
            en_text = next(s["text"] for s in projected if s["kind"] == kind)
            assert en_text not in row, (kind, row)         # translated, not echoed
    for kind, row in rendered["en"]:
        if kind in NEW_KINDS:
            en_text = next(s["text"] for s in projected if s["kind"] == kind)
            assert en_text in row and len(en_text) <= 60


def test_phase_copy_is_short_bilingual_and_free_of_identifiers():
    """(f, server half) Every fixed phase sentence and every counted pattern
    has a Chinese form, and none is longer than 60 characters."""
    import re

    from crossaudit.console.progress import (PHASE_TEXT_ZH, CHECK_WORDS_ZH,
                                             phase_i18n)
    from crossaudit.auditor.run import CHECK_NAMES

    for en, zh in PHASE_TEXT_ZH.items():
        assert len(en) <= 60 and re.search(r"[一-鿿]", zh), en
        assert phase_i18n(en)["zh"] == zh
    assert set(CHECK_NAMES.values()) <= set(CHECK_WORDS_ZH)
    for text in ("Still generating · 45 s", "Reading the workspace · 12 files",
                 "The auditor is reading 1 file", "Running the Units check",
                 "Schema check passed", "Provenance check found 3 issues",
                 "Still reviewing · 40 s"):
        pair = phase_i18n(text)
        assert pair["zh"] != text and re.search(r"[一-鿿]", pair["zh"]), text


def test_the_pipeline_commit_step_names_the_round_not_the_sha(science, cfg):
    from crossaudit.console import overview

    cycle = overview.Cycle(directory="dddddddddddd-r2", sha="d" * 40, round=2,
                           verdict="PASS", findings=[], at=0)
    steps = overview.pipeline(cfg, [cycle])
    assert steps[0]["title"] == "Commit" and steps[0]["detail"] == "round 2"


# ============================================================ review fixes
# Guards for the defects the independent review found (review-latency.md
# D3-D8). Each names the mutation that reproduces the original defect.

def _generator_role(monkeypatch):
    """A configured generator role, so the chat lane reaches its provider."""
    from crossaudit.config import Role

    monkeypatch.setattr(
        talk_mod.provider_resilience, "generator_role",
        lambda _cfg: Role(vendor="anthropic", provider="anthropic",
                          model="m", key_env="CROSSAUDIT_GENERATOR_KEY"))
    monkeypatch.setattr(talk_mod, "record_completion", lambda **_kw: None)
    monkeypatch.setattr(talk_mod, "check_budget_warnings", lambda _cfg: None)


def _streaming_chat(monkeypatch, chunks: tuple[str, ...]):
    """A chat lane whose generator streams ``chunks`` through the resilience
    layer's real gate, so the callback plumbing is exercised, not stubbed."""
    from crossaudit.providers.base import Reply

    def complete(_cfg, _role, _primary, *, system, prompt, on_event=None, **_kw):
        text = "".join(chunks)
        callback = getattr(on_event, "on_chunk", None)
        if callable(callback):
            for seq, part in enumerate(chunks):
                callback(part, {"id": "lane", "seq": seq, "done": False})
            callback("", {"id": "lane", "seq": len(chunks), "done": True,
                          "outcome": "complete"})
        return Reply(text, "id", "a" * 64, "b" * 64, raw={})

    _generator_role(monkeypatch)
    monkeypatch.setattr(talk_mod.provider_resilience, "complete", complete)
    return complete


def test_a_streaming_chat_reply_reaches_the_page_as_intake_chunks(
        console, monkeypatch):
    """D3. The lane's narration object really carries ``on_chunk``.

    Before the fix the lanes were handed ``INTAKE.provider_event`` — a bound
    method, which has no ``__dict__``, so ``resilience`` could never read
    ``on_chunk`` off it and ``Intake.chunk`` had no call site anywhere in the
    source. The whole live-reply path (frames, cursor, consumer) was
    unreachable and a chat question showed three dots until it finished.

    Mutation: hand the lanes ``watch.provider_event`` again and the chunk
    count is 0 while the reply still arrives — exactly the silent gap.
    """
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda text, *, complete, context="": _routing(text, "chat"))
    _streaming_chat(monkeypatch, ("Hel", "lo the", "re."))
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "hi"})
    intake = settled_say(console, body)
    assert intake["result"]["executed"] == "answered by generator: Hello there."
    assert intake["chunks"] > 0, "the lane streamed nothing to the page"


def test_a_lane_that_does_not_stream_still_ends_with_the_whole_reply(
        console, monkeypatch):
    """D3, the other half: an adapter with no streaming path is unchanged —
    no chunks, and the complete answer at the end."""
    from crossaudit.providers.base import Reply

    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda text, *, complete, context="": _routing(text, "chat"))

    def complete(_cfg, _role, _primary, *, system, prompt, on_event=None, **_kw):
        return Reply("Quiet but complete.", "id", "a" * 64, "b" * 64, raw={})

    _generator_role(monkeypatch)
    monkeypatch.setattr(talk_mod.provider_resilience, "complete", complete)
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "hi"})
    intake = settled_say(console, body)
    assert intake["chunks"] == 0
    assert intake["result"]["executed"] == "answered by generator: Quiet but complete."


def test_the_lane_narration_object_can_carry_the_streaming_callback():
    """D3, at the seam: the shape the resilience layer reads, asserted
    directly, because the bound method it replaced looked identical at the
    call site and failed only at ``getattr``."""
    from crossaudit.console.intake import INTAKE

    assert getattr(INTAKE.provider_event, "on_chunk", None) is None
    narration = INTAKE.lane_narration()
    assert callable(narration) and callable(getattr(narration, "on_chunk", None))


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_page_renders_a_streamed_lane_reply_as_an_unaudited_turn(tmp_path):
    """D3, page side: the shipped ``replyChunk``/``liveReplyTurn`` driven under
    node over the frames the server now writes. Contiguous seqs assemble the
    reply and label it unaudited; a dropped frame discards the whole text
    rather than showing a hole. Mutation: drop the gap rule in replyChunk and
    the second case renders 'Ac' as though nothing were missing."""
    import subprocess as sp

    from crossaudit.console import page as page_mod
    from crossaudit.console.server import _intake_sse_frame

    frames = [_intake_sse_frame(
        {"event_id": seq, "t": 1, "text": text, "intake_id": "i1",
         "chat_id": "", "lane": "chat",
         "stream": {"id": "s", "seq": seq, "done": False}}).decode()
        for seq, text in enumerate(("Hel", "lo."))]
    assert all("\nid: intake:i1:" in frame for frame in frames), frames
    rows = [json.loads(frame.split("data: ", 1)[1]) for frame in frames]
    gapped = [rows[0], dict(rows[1], stream={"id": "s", "seq": 5, "done": False},
                            text="c")]

    script = page_mod.PAGE.split("<script>")[1].split("</script>")[0]
    pieces = ["let currentLocale='en';let liveReply=null;let activeChatId='';",
              "let lastState=null;const render=()=>{};const ZH={};",
              "const AUDITOR_LANES=new Set(['auditor','amendment']);",
              "const t=v=>v;",
              _page_snippet(script, "const esc = "),
              _page_snippet(script, "function replyChunk("),
              _page_snippet(script, "function liveReplyTurn(")]
    driver = "\n".join(pieces) + """
const state={intake:{id:'i1',chat_id:'',finished:false,lane:'chat'}};
const out={};
for(const row of ROWS)replyChunk(row);
out.whole=liveReplyTurn(state);
liveReply=null;
for(const row of GAPPED)replyChunk(row);
out.gapped=liveReplyTurn(state);
console.log(JSON.stringify(out));
"""
    driver = ("const ROWS=" + json.dumps(rows) + ";const GAPPED="
              + json.dumps(gapped) + ";\n" + driver)
    (tmp_path / "reply.js").write_text(driver)
    run = sp.run(["node", str(tmp_path / "reply.js")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert "Hello." in out["whole"]
    assert "Generator live reply · not audited" in out["whole"]
    assert 'class="turn draft"' in out["whole"]
    assert out["gapped"] == "", "a dropped frame must discard the reply, not patch it"


def test_a_refused_second_message_leaves_no_thread_behind(console, monkeypatch):
    """D4. ``chats.touch`` ran before ``accept_say``, so the 409 path created
    an empty conversation for a message the console never sent — the rule the
    setup card already followed. Mutation: touch the chat before
    ``say_refusal`` again and the chat count goes to 2.
    """
    import urllib.error

    from crossaudit.config import load

    gate = threading.Event()
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda text, *, complete, context="": _routing(text, "chat"))
    monkeypatch.setattr(talk_mod, "lane_chat",
                        lambda cfg, routing, on_event=None: (gate.wait(5), "answered by generator: ok")[1])
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "first"})
    assert body["accepted"] is True
    try:
        post_json_to(console, "/api/say", {"text": "second"})
        raise AssertionError("the second message was not refused")
    except urllib.error.HTTPError as exc:
        assert exc.code == 409
        assert "still being handled" in exc.read().decode()
    gate.set()
    settled_say(console, body)

    from crossaudit.console import chats
    cfg = load(Path(json.loads(fetch(console.replace("/?t=", "/api/state?t="))[1])
                    ["root"]) / "crossaudit.yml")
    titles = [chat["title"] for chat in chats._read(cfg)["chats"]]
    assert titles == ["first"], titles


def test_the_refusal_sentences_the_page_paints_are_both_translated():
    """D4/D5, copy: the two sentences a refused message can show are in the
    page's Chinese catalogue, so the shipped text-node translator reaches
    them. Mutation: drop either entry and this goes red."""
    from crossaudit.console import page as page_mod
    from crossaudit.console.server import UNEXPECTED_FAILURE

    for sentence in ("the previous message is still being handled",
                     UNEXPECTED_FAILURE):
        assert f'"{sentence}":"' in page_mod.PAGE, sentence


def test_an_unexpected_error_shows_a_sentence_not_the_exception(
        console, monkeypatch):
    """D5. The worker painted ``f"{type(exc).__name__}: {exc}"`` on the main
    surface — a class name and whatever paths the message carried, English
    only, a class of text that could not reach the page before D150.

    Mutation: fail with the exception's own words again and the path and the
    class name are back on the surface.
    """
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda text, *, complete, context="": _routing(text, "chat"))

    def boom(cfg, routing, on_event=None):
        raise ValueError("internal boom with /Users/secret/path")

    monkeypatch.setattr(talk_mod, "lane_chat", boom)
    _status, body, _headers = post_json_to(console, "/api/say", {"text": "hi"})
    intake = settled_say(console, body)
    reason = intake["error"]["reason"]
    assert intake["error"]["status"] == 500
    assert reason == ("Something went wrong handling that message. "
                      "Nothing was started.")
    assert "ValueError" not in reason and "/Users/secret" not in reason


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_clock_never_crowds_the_narration_off_the_stream(tmp_path):
    """D7. The clock speaks every 8 s of silence and the auditor's every 10 s
    of streaming, so a two-minute audit emitted fifteen rows and every one of
    the twelve visible slots became "Still auditing · N s".

    Repetition collapses (docs/design/ACTIVITY_STREAM.md): a run of consecutive
    rows of one kind is ONE row. For a `wait` shape — a clock is one fact, how
    long this phase has been going — only its newest survives, in place.

    Mutation: drop the wait branch from ``mergeRuns`` and fifteen clock rows
    are back.
    """
    import subprocess as sp

    from crossaudit.console import page as page_mod

    substantive = [{"kind": "audit_started", "text": "reviewing the commit"},
                   {"kind": "check_started", "text": "Running the Schema check"},
                   {"kind": "check_finished", "text": "Schema check passed"}]
    # A 120 s audit on the 8 s clock: fifteen consecutive clock rows.
    clock = [{"kind": "still_working", "text": f"Still auditing · {n * 8} s"}
             for n in range(1, 16)]
    steps = [dict(s, t=1788000000 + i, actor="loop", round_no=1, detail="")
             for i, s in enumerate(substantive + clock)]
    script = page_mod.PAGE.split("<script>")[1].split("</script>")[0]
    driver = "\n".join([
        "let currentLocale='en';",
        "const localeText=(b,base)=>(b&&b[currentLocale])||base||'';",
        "function humaniseDetail(x){return x;}",
        _page_snippet(script, "const EVENT_SHAPES=") + ";",
        _page_snippet(script, "const CARRIED_KINDS=") + ";",
        _page_snippet(script, "const EVENT_VERBS=") + ";",
        _page_snippet(script, "const ROW_SHAPES=") + ";",
        _page_snippet(script, "const STEP_ACTORS=") + ";",
        _page_snippet(script, "const ROW_PHASES=") + ";",
        _page_snippet(script, "const MERGE_UNITS=") + ";",
        _page_snippet(script, "function shapeOf("),
        _page_snippet(script, "function verbOf("),
        _page_snippet(script, "function wireLine("),
        _page_snippet(script, "function streamRow("),
        _page_snippet(script, "function actorOfStep("),
        _page_snippet(script, "function conciseDetail("),
        _page_snippet(script, "function rowFromStep("),
        _page_snippet(script, "function rowPhase("),
        _page_snippet(script, "function mergeRuns("),
        "const STEPS=" + json.dumps(steps, ensure_ascii=False) + ";",
        "const kept=mergeRuns(STEPS.map(s=>rowFromStep(s,{})).filter(Boolean));",
        "console.log(JSON.stringify(kept.map(r=>[r.kind,r.line])));"])
    (tmp_path / "clock.js").write_text(driver)
    run = sp.run(["node", str(tmp_path / "clock.js")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    kept = json.loads(run.stdout)
    clocks = [line for kind, line in kept if kind == "still_working"]
    assert len(clocks) == 1, kept
    # No wire i18n on these fixtures, so the row speaks the verb table's words:
    # what matters is that ONE clock row survives, not fifteen.
    assert [kind for kind, _ in kept[:3]] == [s["kind"] for s in substantive]


def test_the_thinking_row_is_folded_shut_and_says_it_is_unaudited():
    """D8. Thinking is model text no auditor has read — further from evidence
    than the draft, which already wears its label. It rendered as a bare row
    with 160 characters of reasoning showing and nothing saying what it was.

    Mutation: render it as a `<div>` again, or open the `<details>` by
    default, and this goes red.
    """
    import re

    from crossaudit.console import page as page_mod

    script = page_mod.PAGE.split("<script>")[1].split("</script>")[0]
    block = _page_snippet(script, "function liveThinkingRow(d)")
    assert "<details class=\"audit-event live-thinking\">" in block
    assert "<details open" not in block and " open>" not in block
    assert "Thinking · not audited" in block and "思考中 · 未经审计" in block
    assert "<summary>" in block
    assert '"Thinking · not audited":"思考中 · 未经审计"' in page_mod.PAGE
    # Display only: the fold is drawn from the live consumer every render, so
    # there is nothing to persist and nothing that could be reopened later.
    assert "localStorage" not in block
    assert re.search(r"details\.live-thinking>summary\{", page_mod.PAGE)


def _render_stream(steps: list[dict]) -> str:
    """The SHIPPED stream renderer executed under node over run steps.

    Everything the stream reaches for that is not part of the row path is
    stubbed; the row path — the shape table, the verb table, the identifier
    scrub, the collapse under test and ``row()`` itself — is real shipped
    source.
    """

    from crossaudit.console import page as page_mod

    script = page_mod.PAGE.split("<script>")[1].split("</script>")[0]
    state = {"progress": {"steps": steps, "finished": False, "outcome": "",
                          "state": "AUDITING", "run_id": "r1",
                          "task": "produce the experiment"},
             "cycles": [], "max_rounds": 3}
    pieces = [
        "let currentLocale='en';const ZH={};const zhValue=v=>ZH[v]||v;",
        "const at=()=>'10:27';let activeChatId='';",
        "const chatProgress=d=>d.progress;const chatCycles=()=>[];",
        "const turn=()=>'';const withTurnCost=h=>h;",
        _page_snippet(script, "const esc = "),
        _page_snippet(script, "const localeText = ") + ";",
        _page_snippet(script, "const t = ") + ";",
        _page_snippet(script, "function durationText("),
        _page_snippet(script, "function humaniseDetail("),
        _page_snippet(script, "function elapsedWords("),
        _page_snippet(script, "function conciseDetail("),
        _page_snippet(script, "const ORB_STATES=") + ";",
        _page_snippet(script, "function orbStateFor("),
        _page_snippet(script, "function orbMarkup("),
        _page_snippet(script, "function orbWaitingStep("),
        _page_snippet(script, "function runOrbPhase("),
        _page_snippet(script, "const EVENT_SHAPES=") + ";",
        _page_snippet(script, "const CARRIED_KINDS=") + ";",
        _page_snippet(script, "const EVENT_VERBS=") + ";",
        _page_snippet(script, "const ROW_SHAPES=") + ";",
        _page_snippet(script, "const ROW_UNITS=") + ";",
        _page_snippet(script, "const STEP_ACTORS=") + ";",
        _page_snippet(script, "const ROW_MARKS=") + ";",
        _page_snippet(script, "const ROW_KIND_MARKS=") + ";",
        _page_snippet(script, "const ROW_PHASES=") + ";",
        _page_snippet(script, "const MERGE_UNITS=") + ";",
        _page_snippet(script, "const STATUS_PHASE_ROWS=") + ";",
        _page_snippet(script, "function rowNumber("),
        _page_snippet(script, "function shapeOf("),
        _page_snippet(script, "function verbOf("),
        _page_snippet(script, "function wireLine("),
        _page_snippet(script, "function streamRow("),
        _page_snippet(script, "function actorOfStep("),
        _page_snippet(script, "function rowFromStep("),
        _page_snippet(script, "function rowFromMessage("),
        _page_snippet(script, "function streamRows("),
        _page_snippet(script, "function rowPhase("),
        _page_snippet(script, "function dropSettledWaits("),
        _page_snippet(script, "function mergeRuns("),
        _page_snippet(script, "function groupRounds("),
        _page_snippet(script, "function streamList("),
        _page_snippet(script, "function rowText("),
        _page_snippet(script, "function rowMark("),
        _page_snippet(script, "function rowDetailHtml("),
        _page_snippet(script, "function rowActionHtml("),
        _page_snippet(script, "function row("),
        _page_snippet(script, "function streamContext("),
        "const D=" + json.dumps(state, ensure_ascii=False) + ";",
        "console.log(streamList(D,streamContext(D,[])).map(r=>row(r,D)).join(''));",
    ]
    run = run_node("\n".join(pieces))
    assert run.returncode == 0, run.stderr
    return run.stdout


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_shipped_stream_collapses_the_clock_rows_it_renders():
    """D7, the call site. Closure audit 2: the test above drives the collapse
    directly, so dropping the call from the renderer — the mutation its own
    docstring names — survived. This one renders the shipped stream over a
    progress payload holding two consecutive clock rows and counts what comes
    out.

    Mutation: drop ``mergeRuns`` from ``streamList`` and two "Still auditing"
    rows are rendered instead of one.
    """
    import re

    def step(kind: str, actor: str, text: str) -> dict:
        return {"kind": kind, "actor": actor, "text": text, "detail": "",
                "text_i18n": {"en": text, "zh": text},
                "t": 1788000000, "round_no": 1, "round_limit": 3, "event_id": 3}

    html = _render_stream([
        step("audit_started", "auditor", "reviewing the commit"),
        step("still_working", "loop", "Still auditing \u00b7 8 s"),
        step("still_working", "loop", "Still auditing \u00b7 16 s")])

    # Counted on the LINE, not on the markup: the orb beside a live line is
    # labelled with that same sentence, which is the point of the orb.
    lines = re.findall(r'<span class="srow-verb">([^<]*)</span>', html)
    assert [x for x in lines if "Still auditing" in x] == ["Still auditing · 16 s"], html
    assert "Still auditing · 8 s" not in html
    # The substantive row is never what gets dropped — and here it is the LIVE
    # phase, so the status line carries it; the stream keeps its own rows.
    assert "srow" in html
