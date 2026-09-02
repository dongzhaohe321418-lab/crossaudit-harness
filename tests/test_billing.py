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


# ------------------------------------------------------------ B2 warnings
class _Clock:
    """A fake clock: budget periods roll over only when we say so."""

    def __init__(self, when: datetime) -> None:
        self.now = when

    def tick(self, **delta) -> datetime:
        self.now = self.now + timedelta(**delta)
        return self.now


def _spend(cfg, tokens: int) -> None:
    _record(cfg, reply=_reply({"usage": {"prompt_tokens": tokens,
                                         "completion_tokens": 0}}))


def test_threshold_alarms_fire_once_persist_and_rearm_at_rollover(cfg):
    cfg = replace(cfg, budgets=Budgets(daily_token_limit=1000))
    clock = _Clock(datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc))
    assert usage.check_budget_warnings(cfg, now=clock.now) == []       # nothing spent
    _spend(cfg, 790)
    assert usage.check_budget_warnings(cfg, now=clock.now) == []       # 79 %: quiet
    _spend(cfg, 20)
    fired = usage.check_budget_warnings(cfg, now=clock.now)            # 81 %
    assert [w["threshold"] for w in fired] == [80]
    assert fired[0]["text"] == "Today's token budget is 80% used"
    assert fired[0]["text_zh"] == "今日 token 预算已用 80%"
    assert fired[0]["resets"] == "Resets at midnight"
    assert fired[0]["resets_zh"] == "明天 0:00 重置"
    # Same period, more spend under the next line: nothing re-fires.
    _spend(cfg, 10)
    assert usage.check_budget_warnings(cfg, now=clock.tick(hours=1)) == []
    # A restart reads the persisted file, not memory.
    stored = json.loads((cfg.root / cfg.state_dir / usage.WARNINGS_NAME).read_text())
    assert stored["daily"] == {"period": "2026-09-02", "fired": [80]}
    assert [w["threshold"] for w in
            usage.budget_warning_state(cfg, now=clock.now)["active"]] == [80]
    _spend(cfg, 140)                                                    # 96 %
    assert [w["threshold"] for w in
            usage.check_budget_warnings(cfg, now=clock.now)] == [95]
    # The 80 % alarm has been raised once this period and stays raised.
    assert [w["threshold"] for w in
            usage.budget_warning_state(cfg, now=clock.now)["active"]] == [80, 95]
    # A new day re-arms both; the state read at that moment shows none fired.
    tomorrow = clock.tick(days=1)
    assert usage.budget_warning_state(cfg, now=tomorrow)["active"] == []
    assert usage.check_budget_warnings(cfg, now=tomorrow) == []        # nothing spent today


def test_alarms_never_fire_when_no_budget_is_configured(cfg):
    _spend(cfg, 1_000_000)
    assert usage.check_budget_warnings(cfg) == []
    assert not (cfg.root / cfg.state_dir / usage.WARNINGS_NAME).exists()
    assert usage.summary(cfg)["budget"]["fired"] == []


def test_monthly_alarm_uses_cost_and_names_the_first_of_next_month(cfg):
    cfg = replace(cfg, budgets=Budgets(monthly_cost_warning_usd=0.01))
    clock = _Clock(datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc))
    # 1000 input + 500 output on gpt-5.6-luna = $0.001 + $0.003 = $0.004 (40 %)
    _record(cfg)
    assert usage.check_budget_warnings(cfg, now=clock.now) == []
    _record(cfg)                                                       # 80 %
    fired = usage.check_budget_warnings(cfg, now=clock.now)
    assert [(w["budget"], w["threshold"]) for w in fired] == [("monthly", 80)]
    assert fired[0]["text"] == "This month's cost budget is 80% used"
    assert fired[0]["text_zh"] == "本月费用预算已用 80%"
    assert fired[0]["resets"] == "Resets on Oct 1" and fired[0]["resets_zh"] == "10 月 1 日重置"
    # December rolls into January of the next year.
    assert usage.reset_moments(datetime(2026, 12, 3, tzinfo=timezone.utc))["monthly"] == "Resets on Jan 1"


def test_the_hard_limit_view_names_which_budget_closed_and_when_it_reopens(cfg):
    cfg = replace(cfg, budgets=Budgets(daily_token_limit=10))
    _spend(cfg, 20)
    view = usage.summary(cfg)["budget"]
    assert view["blocked"] and view["blocked_by"] == ["daily"]
    assert view["resets"]["daily"] == "Resets at midnight"
    assert view["resets"]["daily_zh"] == "明天 0:00 重置"


# ------------------------------------------------------------ B3 429 resets
NOW = 1_800_000_000.0


def test_openai_429_reset_headers_are_parsed_as_durations():
    from crossaudit.providers.base import rate_limit_reset

    headers = {"x-ratelimit-reset-requests": "1s",
               "x-ratelimit-reset-tokens": "6m0s",
               "Retry-After": "20"}
    # The later window wins: the call can only succeed once tokens reopen.
    assert rate_limit_reset(headers, now=NOW) == pytest.approx(NOW + 360)
    assert rate_limit_reset({"x-ratelimit-reset-tokens": "1h2m3s"}, now=NOW) == pytest.approx(NOW + 3723)
    assert rate_limit_reset({"x-ratelimit-reset-requests": "250ms"}, now=NOW) == pytest.approx(NOW + 0.25)


def test_anthropic_429_reset_headers_are_rfc3339_stamps():
    from crossaudit.providers.base import rate_limit_reset

    headers = {"retry-after": "30",
               "anthropic-ratelimit-requests-reset": "2027-01-15T10:00:00Z",
               "anthropic-ratelimit-tokens-reset": "2027-01-15T10:05:30Z"}
    expected = datetime(2027, 1, 15, 10, 5, 30, tzinfo=timezone.utc).timestamp()
    assert rate_limit_reset(headers, now=NOW) == expected


def test_retry_after_alone_and_http_dates_and_bodies_are_understood():
    from crossaudit.providers.base import rate_limit_reset

    assert rate_limit_reset({"Retry-After": "90"}, now=NOW) == pytest.approx(NOW + 90)
    http_date = "Wed, 21 Oct 2026 07:28:00 GMT"
    expected = datetime(2026, 10, 21, 7, 28, tzinfo=timezone.utc).timestamp()
    assert rate_limit_reset({"Retry-After": http_date}, now=NOW) == expected
    body = json.dumps({"error": {"type": "usage_limit_reached",
                                 "resets_in_seconds": 7800}})
    assert rate_limit_reset({}, body, now=NOW) == pytest.approx(NOW + 7800)
    body = json.dumps({"error": {"message": "limit", "reset_at": NOW + 100}})
    assert rate_limit_reset({}, body, now=NOW) == pytest.approx(NOW + 100)
    assert rate_limit_reset({}, "not json", now=NOW) is None
    assert rate_limit_reset({"x-ratelimit-reset-tokens": "soon"}, now=NOW) is None


def test_a_429_denial_carries_its_reset_moment_only_when_the_vendor_gave_one():
    from crossaudit.providers.base import _http_denial

    denial = _http_denial(429, '{"error":{"message":"slow down"}}', "https://x/y",
                          {"Retry-After": "120"})
    assert denial.detail["category"] == "rate_limit"
    assert denial.detail["rate_limit_reset_at"] == pytest.approx(__import__("time").time() + 120, abs=5)
    bare = _http_denial(429, "", "https://x/y", {})
    assert "rate_limit_reset_at" not in bare.detail
    other = _http_denial(500, "", "https://x/y", {"Retry-After": "5"})
    assert "rate_limit_reset_at" not in other.detail


def test_codex_runtime_usage_limit_events_become_rate_limits_with_a_reset():
    from crossaudit.providers.codex_subscription import _Collector, rate_limit_from_error

    collector = _Collector("thread-1")
    collector.accept({"method": "turn/completed", "params": {
        "threadId": "thread-1", "turn": {"id": "t1", "status": "failed", "error": {
            "code": "usage_limit_reached", "message": "You have hit your usage limit",
            "resets_at": NOW + 3600}}}})
    limited, reset_at = rate_limit_from_error(collector.error_data, collector.error, now=NOW)
    assert limited and reset_at == pytest.approx(NOW + 3600)
    assert rate_limit_from_error({"message": "network broke"}, "network broke") == (False, None)
    assert rate_limit_from_error({}, "rate limit exceeded")[0] is True


def test_exhausted_routes_and_the_parked_run_keep_the_reset_moment(cfg, monkeypatch):
    """Through the resilience layer and the run journal: the max reset over
    the failed attempts survives the roll-up into routes_exhausted, and the
    park writes it on waiting_reason where the console counts down from."""
    from crossaudit.config import Role
    from crossaudit.errors import ProviderDenial
    from crossaudit.providers import resilience

    def limited(**_kw):
        raise ProviderDenial("provider returned HTTP 429", status=429,
                             category="rate_limit", retryable=True,
                             rate_limit_reset_at=NOW + 600)

    monkeypatch.setattr(resilience, "get_provider", lambda _name: limited)
    monkeypatch.setitem(resilience.NEEDS_KEY, "limited", False)
    monkeypatch.setattr(resilience, "_sleep", lambda _s: None)
    cfg = replace(cfg, resilience=replace(cfg.resilience, max_attempts=1))
    role = Role("limited", "m", "openai", "K")
    with pytest.raises(ProviderDenial) as caught:
        resilience.complete(cfg, "generator", role, system="s", prompt="p")
    detail = caught.value.detail
    assert detail["category"] == "routes_exhausted"
    assert detail["rate_limit_reset_at"] == NOW + 600 and detail["rate_limited"] is True

    from crossaudit.runtime import RunJournal, RunState
    from crossaudit.runtime.commands import RunCommandService
    from crossaudit.runtime.runs import journal_path

    service = RunCommandService(cfg)
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("task", chat_id="history")
    journal.append(run_id, __import__("crossaudit.runtime.events", fromlist=["RunEvent"]).RunEvent(
        actor="generator", text="working", state=RunState.GENERATING))
    assert service._park_provider_unavailable(run_id, caught.value) is True
    waiting = journal.latest()["waiting_reason"]
    assert waiting["reset_at"] == NOW + 600 and waiting["rate_limited"] is True
