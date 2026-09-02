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


# ------------------------------------------------------------ page surface
import shutil
import subprocess
import sys
from pathlib import Path

from crossaudit.console import page as page_mod

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))
WORKTREE = Path(page_mod.__file__).parents[3]
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_PRELUDE = """
globalThis.currentLocale='en';const t=v=>currentLocale==='zh'?zhValue(v):v;
const USAGE_MODE_KEY='crossaudit-usage-mode',USAGE_DISMISS_KEY='crossaudit-usage-dismissed';
globalThis.activeChatId='chat-1';globalThis.lastState=null;
const els={};const mk=id=>({id,hidden:false,className:'',textContent:'',title:'',attrs:{},
  setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];}});
globalThis.document={getElementById:id=>els[id]||(els[id]=mk(id)),body:{classList:{contains:()=>false}}};
"""

_PILL_FNS = ["function usageMode()", "function shortUsd(value)", "function usageFigure(bucket)",
             "function budgetState(g)", "function renderUsagePill(d)", "function formatTokens(value)",
             "function formatUsd(value)"]


def _eval(signatures, body, prelude=_PRELUDE):
    from render_decision import eval_page
    return eval_page(WORKTREE, signatures, body, prelude=prelude)


@node
def test_header_pill_hides_when_empty_and_colours_by_budget_state_en_and_zh():
    out = _eval(_PILL_FNS, """
    const base={usage:{all:{calls:3},today:{tokens:38000,api_value_usd:0.42},month:{tokens:1200000,api_value_usd:12.1}}};
    const results={};
    for(const locale of ['en','zh']){currentLocale=locale;
      for(const [name,budget] of [['ok',{state:'ok'}],['warn',{state:'ok',fired:[{threshold:80}]}],['blocked',{state:'blocked'}],['none',{state:'unconfigured'}]]){
        renderUsagePill({usage:{...base.usage,budget}});const pill=document.getElementById('usage-pill');
        results[locale+':'+name]={text:pill.textContent,cls:pill.className,hidden:pill.hidden,name:pill.attrs['aria-label']};}}
    renderUsagePill({usage:{all:{calls:0},today:{},month:{}}});results.empty=document.getElementById('usage-pill').hidden;
    renderUsagePill({});results.missing=document.getElementById('usage-pill').hidden;
    console.log(JSON.stringify(results));""")
    got = json.loads(out)
    assert got["en:ok"]["text"] == "Today $0.42 · Month $12.10"
    assert got["en:ok"]["cls"] == "usage-pill ok" and got["en:ok"]["hidden"] is False
    assert got["en:ok"]["name"] == "Usage: today $0.42, this month $12.10 · within budget. Open usage"
    assert got["en:warn"]["cls"] == "usage-pill warning"
    assert got["en:blocked"]["cls"] == "usage-pill blocked"
    assert got["en:none"]["name"] == "Usage: today $0.42, this month $12.10. Open usage"
    assert got["zh:ok"]["text"] == "今日 $0.42 · 本月 $12.10"
    assert got["zh:blocked"]["name"].endswith("已达上限暂停。打开用量")
    assert got["empty"] is True and got["missing"] is True


@node
def test_header_pill_token_mode_is_a_per_viewer_preference():
    out = _eval(_PILL_FNS, """
    Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{store:{'crossaudit-usage-mode':'tokens'},getItem(k){return this.store[k]||null;},setItem(k,v){this.store[k]=v;}}});
    renderUsagePill({usage:{all:{calls:1},today:{tokens:38000,api_value_usd:0.42},month:{tokens:1200000,api_value_usd:12.1},budget:{state:'ok'}}});
    console.log(document.getElementById('usage-pill').textContent);""")
    assert out.strip() == "Today 38K · Month 1.2M"


@node
def test_cost_lines_carry_no_run_ids_hashes_or_provider_model_strings():
    """The run card line and the chat-turn line: tokens, ≈value, seconds — and
    nothing that identifies a run, a commit or a route."""
    fns = ["function chatProgress(d)", "function formatTokens(value)", "function formatUsd(value)",
           "function countdownText(resetAt)", "function resetSentence(resetAt)",
           "function providerResetLine(p)", "function runCostLine(d)", "function turnCost(m,d)",
           "function withTurnCost(html,m,d)"]
    out = _eval(fns, """
    const d={progress:{run_id:'run-deadbeef01',chat_id:'chat-1',state:'GENERATING',finished:false},
      usage:{attribution:{runs:{'run-deadbeef01':{tokens:12300,api_value_usd:0.08,unpriced_calls:0}},
        turns:[{t:1000*1000,role:'generator',phase:'generation',chat_id:'chat-1',run_id:'run-deadbeef01',round:1,tokens:9000,api_value_usd:0.05,duration_ms:42000},
               {t:1002*1000,role:'auditor',phase:'audit',chat_id:'chat-1',cycle_id:'cyc-abc',round:1,tokens:3300,api_value_usd:null,duration_ms:9000}]}}};
    const results={};
    for(const locale of ['en','zh']){currentLocale=locale;
      results[locale]={run:runCostLine(d),
        gen:withTurnCost('<article class="turn"><div class="turn-main"><div class="turn-body">x</div></div></article>',{kind:'generator',t:1001,round:1,sha:'abc123def456'},d),
        aud:turnCost({kind:'auditor',t:1003,round:1},d),none:turnCost({kind:'you',t:1003},d)};}
    const unpriced={...d,usage:{attribution:{runs:{'run-deadbeef01':{tokens:500,api_value_usd:0,unpriced_calls:2}},turns:[]}}};
    currentLocale='en';results.unpriced=runCostLine(unpriced);
    console.log(JSON.stringify(results));""")
    got = json.loads(out)
    assert got["en"]["run"] == '<div class="run-cost"><span>This task: 12K tokens · ≈$0.08</span></div>'
    assert got["zh"]["run"] == '<div class="run-cost"><span>本次任务：12K tokens · ≈$0.08</span></div>'
    assert '<div class="turn-cost">≈$0.05 · 42 s</div></div></article>' in got["en"]["gen"]
    assert got["en"]["aud"] == '<div class="turn-cost">3.3K tokens · 9 s</div>'
    assert got["zh"]["aud"] == got["en"]["aud"] and got["en"]["none"] == ""
    assert got["unpriced"] == '<div class="run-cost"><span>This task: 500 tokens · 2 unpriced</span></div>'
    for text in (got["en"]["run"], got["en"]["gen"], got["en"]["aud"], got["unpriced"]):
        assert "run-deadbeef01" not in text and "cyc-abc" not in text and "abc123def456" not in text
        assert "gpt" not in text and "claude" not in text and "openai" not in text


@node
def test_the_parked_card_and_run_card_count_down_to_the_provider_reset():
    fns = ["function chatProgress(d)", "function formatTokens(value)", "function formatUsd(value)",
           "function countdownText(resetAt)", "function resetSentence(resetAt)",
           "function providerResetLine(p)", "function runCostLine(d)", "function resetWords(g)",
           "function appendResolutionReset(row,budget,provider)"]
    out = _eval(fns, """
    Date.now=()=>1_800_000_000_000;const at=1_800_000_000+2*3600+10*60+5;
    const p={run_id:'r',chat_id:'chat-1',state:'PROVIDER_UNAVAILABLE',finished:true,waiting_reason:{kind:'provider',reset_at:at,rate_limited:true}};
    const results={};
    for(const locale of ['en','zh']){currentLocale=locale;
      results[locale]={line:providerResetLine(p),run:runCostLine({progress:p,usage:{attribution:{runs:{}}}}),
        soon:countdownText(1_800_000_000+30),past:countdownText(1_800_000_000-5),minutes:countdownText(1_800_000_000+600)};
      lastState={progress:p,usage:{budget:{blocked:true,blocked_by:['daily'],resets:{daily:'Resets at midnight',daily_zh:'明天 0:00 重置'}}}};
      document.getElementById('resolution-summary').textContent='Paused.';appendResolutionReset({},true,false);
      results[locale].budgetCard=document.getElementById('resolution-summary').textContent;
      document.getElementById('resolution-summary').textContent='Waiting.';appendResolutionReset({},false,true);
      results[locale].providerCard=document.getElementById('resolution-summary').textContent;}
    console.log(JSON.stringify(results));""")
    got = json.loads(out)
    assert got["en"]["line"] == '<span class="run-reset" data-reset-at="' + str(1_800_000_000 + 7805) + '">Provider limit reached · resets in 2 h 10 min</span>'
    assert got["zh"]["line"].endswith(">已达供应商额度上限 · 2 小时 10 分钟后重置</span>")
    assert got["en"]["run"] == '<div class="run-cost">' + got["en"]["line"] + "</div>"
    assert (got["en"]["soon"], got["en"]["past"], got["en"]["minutes"]) == ("under a minute", "now", "10 min")
    assert (got["zh"]["soon"], got["zh"]["past"], got["zh"]["minutes"]) == ("不到 1 分钟", "现在", "10 分钟")
    assert got["en"]["budgetCard"] == "Paused. Resets at midnight"
    assert got["zh"]["budgetCard"] == "Paused. 明天 0:00 重置"
    assert got["en"]["providerCard"] == "Waiting. Provider limit reached · resets in 2 h 10 min"


@node
def test_the_usage_view_names_unpriced_models_and_carries_the_monthly_report():
    fns = ["function usageMode()", "function formatTokens(value)", "function formatUsd(value)",
           "function usageQuality(row)", "function resetWords(g)", "function unpricedSentences(g)",
           "function monthlyReport(d)", "function usageView(d)"]
    out = _eval(fns, """
    const d={cycles:[{status:'passed'},{status:'blocked'}],usage:{today:{tokens:10},month:{tokens:1000,calls:4,api_value_usd:0.5,unpriced_calls:3},
      days:[],roles:[{role:'generator',tokens:600,calls:2,api_value_usd:0.3},{role:'auditor',tokens:400,calls:2,api_value_usd:0.2}],
      models:[{model:'private-model',role:'generator',provider:'openai_compat',tokens:600,cache_read:0,cache_write:0,api_value_usd:0,unpriced_calls:3,calls:3},
              {model:'claude-sonnet-4-6',role:'auditor',provider:'anthropic',tokens:400,api_value_usd:0.2,calls:1}],recent:[],
      budget:{state:'blocked',blocked:true,reasons:['The monthly cost limit cannot be proven because one or more calls use an unpriced model. Remove the cost limit or select priced models.'],
        blocked_by:['unpriced'],price_snapshot:'2026-08-03',resets:{},fired:[{text:'Today\\'s token budget is 80% used',text_zh:'今日 token 预算已用 80%',resets:'Resets at midnight',resets_zh:'明天 0:00 重置'}],
        unpriced_models:[{model:'private-model',vendor:'other',calls:3,price_snapshot:'2026-08-03'}]}}};
    const results={};for(const locale of ['en','zh']){currentLocale=locale;results[locale]={view:usageView(d),sentences:unpricedSentences(d.usage.budget)};}
    console.log(JSON.stringify(results));""")
    got = json.loads(out)
    assert got["en"]["sentences"] == ["3 calls this month could not be priced (model private-model has no price in the snapshot of 2026-08-03)"]
    assert got["zh"]["sentences"] == ["本月有 3 次调用无法计价（模型 private-model 在 2026-08-03 的价格快照中没有价格）"]
    view = got["en"]["view"]
    assert got["en"]["sentences"][0] in view and "Today&#39;s token budget is 80% used" in view.replace("'", "&#39;") or "Today's token budget is 80% used" in view
    assert "今日 token 预算已用 80%" in got["zh"]["view"]
    assert "<h3>Monthly report</h3>" in view and "<th>Passed audits</th><td>1</td>" in view
    assert "<th>Generator share</th><td>60%</td>" in view and "<th>Auditor share</th><td>40%</td>" in view
    assert "<th>Top models</th>" in view and "<td>private-model</td><td>600</td><td>Unpriced</td>" in view
    assert 'data-usage-mode="value" aria-pressed="true"' in view and 'data-usage-mode="tokens" aria-pressed="false"' in view


def test_every_new_billing_string_has_chinese_parity():
    from crossaudit.console.page import PAGE
    for pair in ('"Open usage":"打开用量"', '"Monthly report":"月度报告"', '"Model prices":"模型价格"',
                 '"＋ Add price":"＋ 添加价格"', '"Export CSV":"导出 CSV"', '"Export JSON":"导出 JSON"',
                 '"This month across projects":"本月全部项目合计"', '"Resets at midnight":"明天 0:00 重置"',
                 '"Usage across projects":"各项目用量"', '"Display mode":"显示模式"'):
        assert pair in PAGE, pair
    assert 'id="usage-pill"' in PAGE and 'id="usage-banner"' in PAGE and 'id="runtime-prices"' in PAGE
    assert "Export isn't available here yet" not in PAGE
    assert 'data-usage-export="csv"' in PAGE and 'id="settings-usage-rollup"' in PAGE


# ------------------------------------------------------------ B6 UI + B7 server
def _project(root, name="p", extra=""):
    from crossaudit.config import load

    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n" + extra)
    return load(root / "crossaudit.yml")


def test_project_controls_persist_and_clear_price_overrides(tmp_path, monkeypatch):
    """Mutation: make ``_price_payload`` drop the model key — the reload below
    goes red on ``prices["my-relay-model"]``."""
    from crossaudit.config import load
    from crossaudit.console import projects
    from crossaudit.errors import ConfigDenial

    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    created = projects.create_project(tmp_path, {
        "name": "priced", "description": "Produce accurate user-facing work.",
        "max_rounds": 3, "auditor_vendor": "openai", "auditor_model": "gpt-5.6-sol",
        "generator_vendor": "anthropic", "generator_model": "claude-sonnet-4-6",
        "github": False}, lambda *_: None)
    cfg = load(Path(created["root"]) / "crossaudit.yml")
    base = {"generator_model": cfg.generator_model, "auditor_model": cfg.auditor.model,
            "generator_reasoning_effort": "", "auditor_reasoning_effort": "", "max_rounds": 3}
    projects.update_runtime(cfg, {**base, "prices": [
        {"model": "my-relay-model", "input": "1.5", "output": "6", "cache_write": "", "cache_read": "0.1"},
        {"model": "", "input": "9"}]})                        # a half-typed row is ignored
    updated = load(cfg.path)
    assert updated.prices == {"my-relay-model": {"input": 1.5, "output": 6.0,
                                                 "cache_write": 0.0, "cache_read": 0.1}}
    assert projects.runtime_options(updated)["prices"][0]["model"] == "my-relay-model"
    with pytest.raises(ConfigDenial, match="non-negative"):
        projects.update_runtime(updated, {**base, "prices": [{"model": "x", "input": "-1"}]})
    with pytest.raises(ConfigDenial, match="unsupported characters"):
        projects.update_runtime(updated, {**base, "prices": [{"model": "bad model!", "input": "1"}]})
    projects.update_runtime(updated, {**base, "prices": []})
    assert load(cfg.path).prices == {} and "prices:" not in cfg.path.read_text()


def _serve(cfg):
    import threading

    from crossaudit.console import serve

    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return url, httpd, thread


def test_export_carries_the_event_columns_and_is_token_gated(tmp_path):
    import urllib.error
    import urllib.request

    cfg = _project(tmp_path / "exported")
    usage.record_reply(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                       phase="generation", vendor="openai", provider="openai_compat",
                       model="gpt-5.6-luna", reply=_reply(), system="secret system",
                       prompt="secret prompt", context={"run_id": "run-1", "round": 2,
                                                        "chat_id": "chat-1"})
    url, httpd, thread = _serve(cfg)
    try:
        csv_url = url.replace("/?t=", "/api/usage/export?format=csv&period=all&t=")
        with urllib.request.urlopen(csv_url, timeout=5) as response:
            body = response.read().decode()
            disposition = response.headers["content-disposition"]
        header, row = body.splitlines()[:2]
        assert header.split(",") == list(usage.EXPORT_COLUMNS)
        cells = dict(zip(header.split(","), row.split(",")))
        assert cells["run_id"] == "run-1" and cells["round"] == "2" and cells["chat_id"] == "chat-1"
        assert cells["model"] == "gpt-5.6-luna" and cells["billing_kind"] == "api_value"
        assert cells["total"] == "1500" and float(cells["api_value_usd"]) > 0
        assert "secret" not in body and disposition.startswith('attachment; filename="crossaudit-usage-')
        json_url = url.replace("/?t=", "/api/usage/export?format=json&period=day&t=")
        with urllib.request.urlopen(json_url, timeout=5) as response:
            payload = json.loads(response.read())
        assert payload["columns"] == list(usage.EXPORT_COLUMNS) and payload["rows"][0]["run_id"] == "run-1"
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(csv_url.split("&t=")[0], timeout=5)
        assert denied.value.code == 403
        denied.value.close()
        with pytest.raises(urllib.error.HTTPError) as bad:
            urllib.request.urlopen(url.replace("/?t=", "/api/usage/export?format=xml&t="), timeout=5)
        assert bad.value.code == 400
        bad.value.close()
    finally:
        httpd.shutdown(); thread.join(timeout=5); httpd.server_close()


def test_rollup_totals_this_month_across_two_projects(tmp_path, monkeypatch):
    import urllib.request

    monkeypatch.delenv("CROSSAUDIT_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    one = _project(tmp_path / "alpha")
    two = _project(tmp_path / "beta", extra="budgets: {daily_token_limit: 100}\n")
    for cfg, count in ((one, 1), (two, 2)):
        for _ in range(count):
            usage.record_reply(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                               phase="generation", vendor="openai", provider="openai_compat",
                               model="gpt-5.6-luna", reply=_reply(), system="s", prompt="p")
    rollup = usage.workspace_rollup([one, two])
    assert [row["name"] for row in rollup["projects"]] == ["beta", "alpha"]
    assert rollup["total"]["projects"] == 2 and rollup["total"]["month_tokens"] == 4500
    assert rollup["total"]["month_api_value_usd"] == pytest.approx(3 * (0.001 + 0.003))
    assert rollup["projects"][0]["budget_state"] == "blocked"        # 3000 tokens > 100
    assert rollup["projects"][1]["budget_state"] == "unconfigured"
    url, httpd, thread = _serve(one)
    try:
        with urllib.request.urlopen(url.replace("/?t=", "/api/usage/rollup?t="), timeout=5) as response:
            served = json.loads(response.read())
    finally:
        httpd.shutdown(); thread.join(timeout=5); httpd.server_close()
    assert {row["name"] for row in served["projects"]} == {"alpha", "beta"}
    assert served["total"] == rollup["total"] and served["local_only"] is True
