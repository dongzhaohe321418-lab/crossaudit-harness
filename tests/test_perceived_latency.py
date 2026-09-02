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
from crossaudit.console import server as server_mod



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
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
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

    def complete_factory(_cfg, _allow_custom, on_event=None, _heartbeat=None):
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
    expected = ["goal", "round_started", "generation_started", "preparing",
                "prompt_ready", "generation_chunk", "thinking_chunk",
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
