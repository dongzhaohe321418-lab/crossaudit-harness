"""Token warning & billing slice: attribution, alarms, resets, pricing, export.

Everything here runs against the local ledger only. No test reads another
application's session files or a vendor's usage endpoint — CrossAudit meters
what it spent itself, and nothing else.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crossaudit import usage
from crossaudit.config import Budgets
from crossaudit.providers.base import Reply


def _reply(raw: dict | None = None, text: str = "model output") -> Reply:
    raw = raw or {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
    return Reply(text=text, request_id="rid", request_sha256="a" * 64,
                 response_sha256="b" * 64, raw=raw)


def _record(cfg, **overrides):
    kwargs = dict(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                  phase="generation", vendor="openai", provider="openai_compat",
                  model="gpt-5.6-luna", reply=_reply(), system="s", prompt="p")
    kwargs.update(overrides)
    return usage.record_reply(**kwargs)


# ------------------------------------------------------------ B1 attribution
def test_attribution_ids_round_trip_and_old_lines_stay_readable(cfg):
    event = _record(cfg, context={"run_id": "run-1", "cycle_id": "cyc-1",
                                  "round": 2, "chat_id": "chat-1",
                                  "duration_ms": 4200})
    assert (event["run_id"], event["cycle_id"], event["round"], event["chat_id"],
            event["duration_ms"]) == ("run-1", "cyc-1", 2, "chat-1", 4200)
    assert event["v"] == 1
    bare = _record(cfg)                       # an old-style line: no context
    assert not {"run_id", "cycle_id", "round", "chat_id"} & set(bare)
    ledger = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    lines = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert lines[0]["run_id"] == "run-1" and "run_id" not in lines[1]
    # Readers tolerate both shapes side by side.
    result = usage.summary(cfg)
    assert result["all"]["calls"] == 2
    assert result["attribution"]["runs"]["run-1"]["calls"] == 1
    assert result["attribution"]["turns"][0]["run_id"] == "run-1"
    assert result["attribution"]["turns"][1]["run_id"] == ""


def test_router_is_a_recorded_role(cfg):
    event = _record(cfg, role="router", phase="control")
    assert event["role"] == "router"
    assert usage.summary(cfg)["roles"][0]["role"] == "router"


def test_aggregators_total_per_run_cycle_and_chat_on_a_fixture():
    events = [
        {"t": 1000, "role": "generator", "run_id": "r1", "cycle_id": "", "chat_id": "c1",
         "total": 100, "input": 80, "output": 20, "cache_read": 0, "cache_write": 0,
         "api_value_usd": 0.01, "method": "reported", "duration_ms": 1000},
        {"t": 2000, "role": "auditor", "run_id": "r1", "cycle_id": "cy1", "chat_id": "c1",
         "total": 50, "input": 40, "output": 10, "cache_read": 5, "cache_write": 0,
         "api_value_usd": None, "method": "estimated", "duration_ms": 500},
        {"t": 3000, "role": "generator", "run_id": "r2", "cycle_id": "cy1", "chat_id": "c2",
         "total": 10, "input": 8, "output": 2, "cache_read": 0, "cache_write": 0,
         "api_value_usd": 0.001, "method": "reported"},
        {"t": 4000, "role": "generator", "total": 7, "input": 7, "output": 0,
         "api_value_usd": 0.0, "method": "reported"},          # unattributed
    ]
    run = usage.per_run(events, "r1")
    assert (run["calls"], run["tokens"], run["cache_read"]) == (2, 150, 5)
    assert run["api_value_usd"] == pytest.approx(0.01)
    assert (run["reported_calls"], run["estimated_calls"], run["unpriced_calls"]) == (1, 1, 1)
    assert (run["first_t"], run["last_t"], run["duration_ms"]) == (1000, 2000, 1500)
    assert usage.per_cycle(events, "cy1")["tokens"] == 60
    assert usage.per_chat(events, "c2")["calls"] == 1
    assert usage.per_run(events, "missing")["calls"] == 0
    grouped = usage.attribution(events)
    assert set(grouped["runs"]) == {"r1", "r2"} and set(grouped["chats"]) == {"c1", "c2"}
    assert len(grouped["turns"]) == 4


# ------------------------------------------------------------ B6 pricing
def test_user_price_override_is_used_and_stamped(cfg):
    prices = {"private-model": {"input": 2.0, "output": 10.0,
                                "cache_write": 0.0, "cache_read": 0.0}}
    event = _record(cfg, vendor="other", provider="openai_compat", model="private-model",
                    base_url="https://models.example.test", context={"prices": prices})
    assert event["billing_kind"] == "user_priced"
    # 1000 in @ $2/M + 500 out @ $10/M
    assert event["api_value_usd"] == pytest.approx(0.002 + 0.005)
    assert usage._rates("other", "private-model", prices).output == 10.0
    assert usage._rates("other", "private-model") is None


def test_without_an_override_the_same_model_stays_unpriced_and_is_named(cfg):
    """Mutation: drop the override lookup in ``_rates`` and the first assertion
    of the test above goes red; here the negative side is pinned so a silent
    "everything priced" regression cannot hide either."""
    _record(cfg, vendor="other", provider="openai_compat", model="private-model",
            base_url="https://models.example.test")
    result = usage.summary(cfg)
    rows = result["budget"]["unpriced_models"]
    assert rows == [{"model": "private-model", "vendor": "other", "calls": 1,
                     "price_snapshot": usage.PRICE_SNAPSHOT}]


def test_prices_config_is_validated_with_legible_denials(tmp_path):
    from crossaudit.cli import i18n
    from crossaudit.config import load
    from crossaudit.errors import ConfigDenial

    (tmp_path / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    base = ("version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
            "auditor: {vendor: openai, provider: openai_compat, model: m, key_env: K}\n"
            "generator: {vendor: anthropic}\n")
    for tail in ("prices: 3\n", "prices: {m: 3}\n", "prices: {m: {input: -1}}\n",
                 "prices: {m: {bogus: 1}}\n"):
        (tmp_path / "crossaudit.yml").write_text(base + tail)
        with pytest.raises(ConfigDenial) as caught:
            load(tmp_path / "crossaudit.yml")
        assert i18n.denial_zh(caught.value.reason), caught.value.reason
    (tmp_path / "crossaudit.yml").write_text(
        base + "prices: {m: {input: 1, output: 2.5, cache_write: 0, cache_read: 0.1}}\n")
    assert load(tmp_path / "crossaudit.yml").prices["m"]["output"] == 2.5
