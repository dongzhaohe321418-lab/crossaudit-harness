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
