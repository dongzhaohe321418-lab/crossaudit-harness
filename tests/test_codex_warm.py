"""Codex subscription warm-up (new-conversation start latency).

A ChatGPT-subscription project otherwise cold-starts the Codex runtime — the
``codex app-server`` spawn plus the ``initialize`` handshake — on the user's
first message. ``codex_subscription.warm`` moves that cost to project-console
boot, in the background, and ``server._console_uses_codex`` decides when to.
These tests pin the two contracts the latency fix depends on: warming never
blocks, never raises, and collapses concurrent calls; and detection fires for
either role or a generator fallback but not for a non-subscription project.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from crossaudit.console.server import _console_uses_codex
from crossaudit.providers import codex_subscription


def _fake_cfg(auditor_provider, generator_provider=None, gen_fallbacks=()):
    return SimpleNamespace(
        auditor=SimpleNamespace(provider=auditor_provider),
        generator_provider=generator_provider,
        generator_fallbacks=tuple(
            SimpleNamespace(provider=p) for p in gen_fallbacks),
    )


# ------------------------------------------------------- detection

def test_detects_codex_auditor():
    assert _console_uses_codex(_fake_cfg("openai_codex")) is True


def test_detects_codex_generator():
    assert _console_uses_codex(
        _fake_cfg("replay", generator_provider="openai_codex")) is True


def test_detects_codex_generator_fallback():
    assert _console_uses_codex(
        _fake_cfg("replay", generator_provider="anthropic",
                  gen_fallbacks=["openai_codex"])) is True


def test_false_for_non_subscription_project():
    assert _console_uses_codex(
        _fake_cfg("replay", generator_provider="openai_compat")) is False
    # A None generator provider must not blow up the membership test.
    assert _console_uses_codex(_fake_cfg("anthropic")) is False


# ------------------------------------------------------- warm()

def _reset_guard():
    codex_subscription._warm_in_flight = False


def test_warm_is_nonblocking_and_runs_in_background(monkeypatch):
    _reset_guard()
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def fake_ensure():
        calls.append(1)
        entered.set()
        release.wait(2)          # hold the "handshake" open

    monkeypatch.setattr(codex_subscription.SERVER, "ensure_started", fake_ensure)

    t0 = time.monotonic()
    codex_subscription.warm()    # must return immediately, not wait on ensure
    assert time.monotonic() - t0 < 0.5
    assert entered.wait(2)       # the background thread really ran ensure_started
    release.set()
    for _ in range(200):         # let the worker clear the in-flight guard
        if not codex_subscription._warm_in_flight:
            break
        time.sleep(0.01)
    assert calls == [1]
    assert codex_subscription._warm_in_flight is False


def test_warm_swallows_errors(monkeypatch):
    _reset_guard()

    def boom():
        raise RuntimeError("codex runtime unavailable")

    monkeypatch.setattr(codex_subscription.SERVER, "ensure_started", boom)
    codex_subscription.warm()    # a failing warm must never propagate
    for _ in range(200):
        if not codex_subscription._warm_in_flight:
            break
        time.sleep(0.01)
    # The guard is released even on failure, so a later warm can retry.
    assert codex_subscription._warm_in_flight is False


def test_warm_collapses_concurrent_calls(monkeypatch):
    _reset_guard()
    entered = threading.Event()
    hold = threading.Event()
    count = []

    def fake_ensure():
        count.append(1)
        entered.set()
        hold.wait(2)

    monkeypatch.setattr(codex_subscription.SERVER, "ensure_started", fake_ensure)

    codex_subscription.warm()    # worker 1 enters and blocks on hold
    assert entered.wait(2)
    codex_subscription.warm()    # in-flight → no second spawn
    codex_subscription.warm()
    hold.set()
    for _ in range(200):
        if not codex_subscription._warm_in_flight:
            break
        time.sleep(0.01)
    assert count == [1]
