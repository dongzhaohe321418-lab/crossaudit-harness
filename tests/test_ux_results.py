"""Results & decisions on the main surface: plain words, no identifiers, a
forecast, and a cause with a next step for every ESCALATE branch.

The owner's directives for this slice: a concise surface (no hashes, cycle
ids, commit shas, provider:model strings or rule ids on the main surface —
details on demand only), plain-language results, and every stop telling the
person what happened, why, and what to do next, in English and Chinese.

Rendered through the SHIPPED page functions under node wherever the claim is
about what a person reads; the estimator and the cause ladder are pure and
are tested as such.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import usage
from crossaudit.console import overview
from crossaudit.console.page import PAGE
from crossaudit.controller import StateStore
from crossaudit.errors import (ESCALATION_CAUSES, escalation_cause,
                               escalation_remediations)

from .conftest import GOOD_RESULTS, PASS_REPLY, git, record_reply, write_increment
from .test_overview import BLOCKER, ADVISORY, add_audit, cfg  # noqa: F401

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))
WORKTREE = Path(overview.__file__).parents[3]
needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

HEX12 = re.compile(r"\b[0-9a-f]{12,40}\b")
PROVIDER_MODEL = re.compile(r"(anthropic:|openai_compat:|openai_codex:|:claude|:gpt)")
RULE_ID = re.compile(r"CA-[A-Z]+-\d")
RAW_VERDICT = re.compile(r"\b(PASS|BLOCKED|ESCALATE|ESCALATED|DCL_ONLY)\b")
CJK = re.compile(r"[一-鿿]")


def _visible(html: str) -> str:
    """What a person reads: tags gone, whitespace folded."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _without_details(html: str) -> str:
    """The first paint: everything a closed <details> hides is removed."""
    return re.sub(r"<details\b.*?</details>", "", html, flags=re.S)


def _sha(char: str) -> str:
    return char * 40


# =============================================================== R1 verdict words
_TURN_PRELUDE = r"""
globalThis.currentLocale='en';
globalThis.at=()=>'';globalThis.artifactList=()=>'';globalThis.auditStatus=()=>'';
globalThis.localeText=(b,base)=>base;globalThis.t=v=>v;
"""
_TURN_SIGS = ["const VERDICT_WORDS={", "function verdictWord(v)",
              "function severityWord(sev)", "function tierWord(f)",
              "function ruleTitle(rule)", "function findingCard(f)", "function turn(m,d)"]


def _auditor_turn(verdict: str, findings: list[dict] | None = None) -> str:
    from render_decision import eval_page
    m = real_state.row("auditor", for_sha=real_state.produced()["shas"]["a"],
                       verdict=verdict, t=0, findings=findings or [],
                       report_note="")
    return eval_page(WORKTREE, _TURN_SIGS,
                     f"console.log(turn({json.dumps(m)},{{}}));", _TURN_PRELUDE)


@needs_node
@pytest.mark.parametrize("verdict,word,zh", [
    ("PASS", "Passed", "已通过"), ("BLOCKED", "Needs changes", "需要修改"),
    ("ESCALATE", "Needs you", "需要你"), ("DCL_ONLY", "Checks only", "仅自动检查")])
def test_the_chat_badge_says_what_the_verdict_means(verdict, word, zh, tmp_path):
    """R1. The raw vocabulary stays as the CSS class (colour) and in --json,
    receipts, reports and the inspector; the words a person reads say what
    the verdict means, in both languages."""
    html = _auditor_turn(verdict)
    text = _visible(html)
    assert word in text
    assert RAW_VERDICT.search(text) is None, text
    assert f'class="status {verdict}"' in html, "the colour class keeps the raw word"
    from .test_console_translation_boundary import _translate
    assert _translate([word], tmp_path)[word] == zh


def test_the_raw_words_survive_where_scripts_and_records_read_them():
    """The main surface translates; the record does not. `--json` and the
    human line print the outcome's own verdict, and the receipt commit message
    names it — none of these pass through the page's word table."""
    source = (WORKTREE / "src/crossaudit/cli/main.py").read_text()
    assert 'result = {"verdict": outcome.verdict' in source
    assert 'f"audit receipt {sha[:12]} r{cycle[\'round\']} ({outcome.verdict})"' in source
    assert "VERDICT_WORDS" not in source


# =========================================================== R2 findings lead
@needs_node
def test_a_finding_leads_with_the_observation_and_demotes_the_rule_id():
    """R2. First line: what was observed. Details line: "must fix" or
    "suggestion", the place, the evidence tier sentence, and the rule id —
    small, muted, never opening the first line."""
    html = _auditor_turn("BLOCKED", [
        {"severity": "BLOCKER", "rule": "CA-TXT-001", "artifact": "work/a.md",
         "observation": "The summary states 0.052 while the data records 0.044.",
         "tier": "model", "verified": False},
        {"severity": "ADVISORY", "rule": "CA-REP-001", "artifact": "work/meta.yml",
         "observation": "No extraction procedure recorded.",
         "tier": "deterministic", "verified": True}])
    cards = re.findall(r'<div class="finding">(.*?)</div></div>', html, flags=re.S)
    assert len(cards) == 2
    for card in cards:
        first, details = card.split('<div class="finding-details"')
        assert first.startswith('<p class="finding-observation">')
        assert RULE_ID.search(_visible(card)) is None, "the rule id is not on the first paint"
        assert re.match(r' title="Rule id: CA-[A-Z]+-\d+">', details), "on demand: the tooltip"
    blocker, advisory = (_visible(c) for c in cards)
    assert blocker.startswith("The summary states 0.052")
    assert "must fix" in blocker and "raised by the auditor, not yet reproduced" in blocker
    assert "BLOCKER" not in blocker and "ADVISORY" not in advisory
    assert "suggestion" in advisory and "verified by a check" in advisory
    # The tier sentence sits on the details line, not in a row of its own.
    assert "<small" not in html


@needs_node
def test_finding_words_reach_a_chinese_reader(tmp_path):
    from .test_console_translation_boundary import _translate
    words = ["must fix", "suggestion", "verified by a check", "Rule id: CA-TXT-001",
             "raised by the auditor, not yet reproduced", "raised by the auditor, verified",
             "Details", "Rules"]
    rendered = _translate(words, tmp_path)
    assert rendered["must fix"] == "必须修改" and rendered["suggestion"] == "建议"
    assert all(CJK.search(rendered[w]) for w in words), rendered


# ================================================ R3 details on demand
# A settled cycle is no longer a card, so these are driven through the WHOLE
# shipped page (tests/harness/render_page.py) and the real `renderConversation`
# rather than through a sliced-out `reviewCard` with its callers stubbed. The
# claim is the same one and it is now made about what a person actually sees.
import real_state  # noqa: E402  (rows built by the product, not by a fixture)
import render_page  # noqa: E402  (the whole-page harness)


def _cycle_state(status: str, verdict: str, findings: list[dict],
                 progress: dict | None = None) -> dict:
    sha = real_state.produced()["shas"]["a"]
    return {
        "version": "4", "project": "lab/p", "title": "t", "folder": "f",
        "tier": {"tier": "local"}, "max_rounds": 3, "rules": 4, "metrics": [],
        "check_contracts": {}, "pipeline": [], "usage": {},
        "generator": "anthropic:claude-opus-4-8",
        "auditor": "openai_compat:gpt-5.6-terra",
        "generator_stream": [], "escalations": [],
        "chats": {"items": [{"id": "c1"}]}, "progress": progress,
        # Built by the product, never typed: see tests/harness/real_state.py.
        "cycles": [real_state.row("cycle", for_sha=sha, status=status,
                                  round=1)],
        "auditor_stream": [real_state.row("auditor", for_sha=sha,
                                          verdict=verdict, round=1, t=90,
                                          findings=findings, report_note="")],
    }


BLOCKER_FINDING = {"severity": "BLOCKER", "rule": "CA-TXT-001",
                   "artifact": "work/a.md", "observation": "Wrong figure."}


@needs_node
def test_an_escalated_cycle_is_a_row_in_the_stream_not_a_review_card():
    """A5. A stopped cycle is a decision, and a decision happens in the stream:
    a machine failure is a note row with one inline action, a judgment call is
    an outcome row that expands into the decision itself. A second surface
    announcing the same stop underneath would be the interface asking twice.

    The old version of this test asserted only that `reviewCard` returned "" —
    which is why it did not see the delivery band that had taken the card's
    place. It renders the whole conversation now.

    Mutation: give ESCALATED an entry in CYCLE_VERDICTS and the escalated cycle
    grows a second row saying the same thing.
    """
    state = _cycle_state("ESCALATED", "ESCALATE", [])
    out = render_page.render(WORKTREE, {"escalated": state})
    for locale in ("en", "zh"):
        html = out["escalated"][locale]["html"]
        assert "review-card" not in html, html
        assert "srow-outcome" not in html, (
            "an escalated cycle with no recorded decision must not paint a "
            "verdict of its own: the decision row is built from the stop")
        assert "Needs your input" not in html and "需要你处理" not in html


@needs_node
@pytest.mark.parametrize("status,verdict,findings", [
    ("PASSED", "PASS", []),
    ("BLOCKED", "BLOCKED", [BLOCKER_FINDING])])
def test_a_settled_cycles_row_carries_no_identifier_until_it_is_opened(
        status, verdict, findings):
    """R3, on the row that replaced the card: outside the folds there is no
    12/40-hex, no provider:model string, no raw verdict word and no rule id.
    Behind them, the models by their friendly names, then the commit and the
    cycle.

    Mutation: move the record out of its own `<details>` and the first paint
    grows the commit; paint `cycle.status` instead of the verdict words and
    RAW_VERDICT fires.
    """
    out = render_page.render(WORKTREE, {"settled": _cycle_state(status, verdict, findings)})
    paint = out["settled"]["en"]["first_paint"]
    html = out["settled"]["en"]["html"]
    assert paint, "the cycle rendered nothing"
    for pattern in (HEX12, PROVIDER_MODEL, RAW_VERDICT, RULE_ID):
        assert pattern.search(paint) is None, (pattern.pattern, paint)
    # ...and the record is there, one keystroke away, naming the models by the
    # names a person recognises.
    assert "Claude Opus" in html or "claude-opus" in html.lower(), html
    sha = real_state.produced()["shas"]["a"]
    assert sha[:12] in html, "the commit is in the record"
    assert real_state.row("cycle", for_sha=sha)["id"] in html, (
        "the cycle id is in the record")
    if findings:
        assert "Wrong figure." in html and "Wrong figure." not in paint
        assert "CA-TXT-001" in html



@needs_node
def test_friendly_model_names_are_derived_from_the_id():
    from render_decision import eval_page
    """Known catalogue shapes get their name; every other id renders bare
    (provider prefix dropped, nothing invented) so an operator who typed it
    can still find it. Mutation M12 from the review is now the spec."""
    cases = {
        "anthropic · anthropic:claude-opus-4-8 · high": "Claude Opus 4.8",
        "openai · openai_compat:gpt-5.6-terra": "GPT-5.6 Terra",
        "anthropic:claude-haiku-4-5-20251001": "Claude Haiku 4.5",
        "anthropic:claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "google:gemini-3.5-pro": "Gemini 3.5 Pro",
        "deepseek:deepseek-v4-pro": "DeepSeek V4 Pro",
        "anthropic:claude-sonnet-4-6": "Claude Sonnet 4.6",
        "human": "Human", "": "",
        "custom · openai_compat:my-local-model": "my-local-model",
        "openai_compat:gpt-oss-120b": "gpt-oss-120b",
        "openai_compat:Qwen/Qwen3-235B-A22B": "Qwen/Qwen3-235B-A22B",
        "zhipu:glm-4.6": "glm-4.6",
        "openai:gpt-4o": "gpt-4o",
        "openai_compat:abc_xyz-99": "abc_xyz-99",
    }
    out = eval_page(WORKTREE, ["function friendlyModel(value)"],
                    "console.log(JSON.stringify(Object.fromEntries("
                    + json.dumps(list(cases)) + ".map(v=>[v,friendlyModel(v)]))));")
    assert json.loads(out) == cases


# ================================================================ R4 forecast
def _rows(*seconds_usd):
    return [{"seconds": s, "usd": u} for s, u in seconds_usd]


def test_an_empty_record_forecasts_nothing():
    assert usage.run_forecast([]) == {"runs": 0, "priced_runs": 0,
                                      "seconds": None, "usd": None}


def test_one_run_is_its_own_median():
    got = usage.run_forecast(_rows((150, 0.31)))
    assert got["runs"] == 1
    assert got["seconds"] == {"p25": 150.0, "p50": 150.0, "p75": 150.0}
    assert got["usd"] == {"p25": 0.31, "p50": 0.31, "p75": 0.31}


def test_three_runs_give_a_middle_half():
    got = usage.run_forecast(_rows((120, 0.2), (180, 0.3), (240, 0.4)))
    assert got["seconds"] == {"p25": 150.0, "p50": 180.0, "p75": 210.0}
    assert got["usd"] == {"p25": 0.25, "p50": 0.3, "p75": 0.35}


def test_ten_runs_interpolate_quartiles():
    got = usage.run_forecast(_rows(*[(60 * i, 0.1 * i) for i in range(1, 11)]))
    assert got["runs"] == 10
    assert got["seconds"]["p50"] == 330.0
    assert got["seconds"]["p25"] == 195.0 and got["seconds"]["p75"] == 465.0


def test_a_single_outlier_barely_moves_the_forecast():
    """A run that hung for an hour must not turn "usually 3 min" into
    "usually 20 min": the estimate reads the middle of the record."""
    steady = _rows(*[(180, 0.3)] * 6)
    with_outlier = steady + _rows((3600, 9.0))
    a, b = usage.run_forecast(steady), usage.run_forecast(with_outlier)
    assert a["seconds"]["p50"] == b["seconds"]["p50"] == 180.0
    assert b["seconds"]["p75"] == 180.0 and b["usd"]["p50"] == 0.3


def test_unpriced_and_malformed_rows_are_left_out_not_zeroed():
    got = usage.run_forecast(_rows((100, None), (200, 0.5), ("x", 1.0), (-5, 1.0)))
    assert got["runs"] == 2 and got["priced_runs"] == 1
    assert got["usd"]["p50"] == 0.5


def test_forecast_rows_join_ledger_events_to_run_windows():
    """The ledger carries no run id, so a run's cost is the API value of the
    calls that fell inside its wall-clock window; an unpriced window is None."""
    runs = [{"started": 1000.0, "finished": 1120.0},
            {"started": 2000.0, "finished": 2060.0},
            {"started": 3000.0, "finished": 2990.0}]  # torn: dropped
    events = [{"t": 1_010_000, "api_value_usd": 0.1},
              {"t": 1_100_000, "api_value_usd": 0.2},
              {"t": 1_500_000, "api_value_usd": 5.0},  # between runs
              {"t": 2_030_000, "api_value_usd": None},
              {"t": "bad", "api_value_usd": 1.0}]
    rows = usage.forecast_rows(events, runs)
    assert rows == [{"seconds": 120.0, "usd": pytest.approx(0.3)},
                    {"seconds": 60.0, "usd": None}]


def test_the_snapshot_exposes_the_forecast_and_a_fresh_project_has_none(cfg):
    got = usage.summary(cfg)["forecast"]
    assert got == {"runs": 0, "priced_runs": 0, "seconds": None, "usd": None}


def test_the_forecast_reads_the_run_journal_read_only(cfg):
    """Runs that reached a verdict count; a cancelled one does not."""
    from crossaudit.runtime.runs import RunJournal, RunState, journal_path
    journal = RunJournal(journal_path(cfg))
    import sqlite3
    db = sqlite3.connect(journal_path(cfg))
    for i, state in enumerate(("PASSED", "WAITING_FOR_HUMAN", "CANCELLED")):
        db.execute(
            "INSERT INTO runs(run_id,task,chat_id,continuation_cycle,state,outcome,"
            "error,owner_pid,started,updated,finished) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (f"r{i}", "t", "history", "", state, "", "", 1, 1000.0 + i, 1000.0 + i,
             1000.0 + i + 120 * (i + 1)))
    db.commit(); db.close()
    del journal, RunState
    usage._SUMMARY_CACHE.clear()
    got = usage.summary(cfg)["forecast"]
    assert got["runs"] == 2 and got["seconds"]["p50"] == 180.0
    assert got["usd"] is None, "no ledger event fell in a window: no invented cost"


@needs_node
def test_the_forecast_line_reads_in_both_languages():
    """R4. "Usually 2–4 min · about $0.30" from three or more runs; the median
    alone below that; "First run here — no estimate yet" with nothing."""
    from render_decision import eval_page
    sigs = ["function formatUsd(value)", "function forecastText(d)"]
    body = r"""
const three={usage:{forecast:{runs:3,seconds:{p25:110,p50:180,p75:250},usd:{p50:0.3}}}};
const one={usage:{forecast:{runs:1,seconds:{p25:180,p50:180,p75:180},usd:{p50:0.3}}}};
const unpriced={usage:{forecast:{runs:4,seconds:{p25:60,p50:100,p75:140},usd:null}}};
const brief={usage:{forecast:{runs:3,seconds:{p25:10,p50:12,p75:14},usd:{p50:0.01}}}};
const twenty={usage:{forecast:{runs:1,seconds:{p25:20,p50:20,p75:20},usd:null}}};
const out={};
for(const locale of ['en','zh']){globalThis.currentLocale=locale;
  out[locale]=[forecastText(three),forecastText(one),forecastText(unpriced),forecastText({}),forecastText(null),
    forecastText(brief),forecastText(twenty)];}
console.log(JSON.stringify(out));"""
    out = json.loads(eval_page(WORKTREE, sigs, body, "globalThis.currentLocale='en';"))
    assert out["en"] == ["Usually 2–4 min · about $0.30", "Usually about 3 min · about $0.30",
                         "Usually 1–2 min", "First run here — no estimate yet",
                         "First run here — no estimate yet",
                         # Sub-minute runs floor to words, never "0 min" or a
                         # rounded "1 min" (review mutation M11).
                         "Usually under a minute · about $0.01", "Usually under a minute"]
    assert out["zh"] == ["通常 2–4 分钟 · 约 $0.30", "通常约 3 分钟 · 约 $0.30",
                         "通常 1–2 分钟", "首次运行，暂无预估", "首次运行，暂无预估",
                         "通常不到 1 分钟 · 约 $0.01", "通常不到 1 分钟"]


def test_the_forecast_line_is_one_line_at_task_start_and_nowhere_else():
    """R4 kept, narrowed by the activity stream.

    The run card's header carried the forecast beside a step meter; the header
    is now the status line, which says the RUNNING COST from the billing
    slice's per-run aggregate. An estimate beside a measurement of the same
    thing is the weaker of the two, so the forecast stays where it is the only
    number available — the moment the task is sent.

    Mutation: add forecastLine() back to statusLine and this fails.
    """
    start = PAGE[PAGE.index("function optimisticTurn("):PAGE.index("function userState(d)")]
    assert start.count("forecastText(") == 1
    status = PAGE[PAGE.index("function statusLine(d){"):PAGE.index("function liveThinkingRow(d){")]
    assert "forecast" not in status
    assert "statusCostText(d,p)" in status


# ============================================================ R5 every branch
def test_the_cause_follows_the_ladder_in_order():
    """errors.escalation_cause mirrors auditor/run.py: lock, then scope, then
    reply, then bounds, then the dial, then the auditor's own word."""
    assert escalation_cause(integrity="OK", verdict="PASS") == ""
    assert escalation_cause(integrity="NOTHING_AUDITED", verdict="ESCALATE",
                            escalation_lock=True) == "escalation_locked"
    assert escalation_cause(integrity="NOTHING_AUDITED", verdict="ESCALATE") == "nothing_audited"
    assert escalation_cause(integrity="INVALID_REPLY", verdict="ESCALATE") == "invalid_reply"
    assert escalation_cause(integrity="BOUNDS_EXCEEDED", verdict="ESCALATE") == "bounds_exceeded"
    assert escalation_cause(integrity="OK", verdict="ESCALATE",
                            model_verdict="BLOCKED", contested=True) == "auditor_concern"
    assert escalation_cause(integrity="OK", verdict="ESCALATE",
                            model_verdict="ESCALATE") == "auditor_escalated"
    assert escalation_cause(integrity="OK", verdict="ESCALATE") == ""
    assert set(ESCALATION_CAUSES) >= {"nothing_audited", "invalid_reply",
                                      "bounds_exceeded", "auditor_escalated",
                                      "escalation_locked"}


def test_remediations_stay_additive():
    assert escalation_remediations("audit") == ["revise", "stop"]
    assert escalation_remediations("provider")[0] == "retry"


def _escalate(cfg, char: str, cause: str = "", integrity: str = "",
              findings: str = "", chat: str = "history") -> str:
    """Record one ESCALATE round the way cmd_run does; `integrity` writes a
    receipt for the legacy path, `cause` the stored field for the new one."""
    sha = _sha(char)
    cycle_dir = add_audit(cfg, sha[:12], "ESCALATE", findings)
    if integrity:
        (cycle_dir / "receipt.json").write_text(
            json.dumps({"ledger": {}, "audit_integrity": integrity}))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    c = store.open_or_advance(cfg.science_repo, sha, None)
    store.record_verdict(c["cycle_id"], sha, "ESCALATE", "r" * 64, 3,
                         escalation_cause=cause)
    return c["cycle_id"]


def _lock(cfg, char: str, holder: str) -> str:
    """The refused commit's own decision object, the way _record_lock writes it."""
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    return store.record_build_escalation(
        cfg.science_repo, _sha(char), "", 1, task="Fix it", kind="audit",
        cause="escalation_locked", locked_by=holder)["cycle_id"]


@pytest.mark.parametrize("cause", ["nothing_audited", "invalid_reply", "bounds_exceeded",
                                   "auditor_escalated", "escalation_locked"])
def test_the_stored_cause_reaches_the_dashboard_with_a_why_and_a_next_step(cfg, cause):
    if cause == "escalation_locked":
        holder = _escalate(cfg, "h", cause="auditor_escalated")
        _lock(cfg, "a", holder)
        row = next(r for r in overview.escalations(cfg) if r["sha"] == _sha("a"))
    else:
        _escalate(cfg, "a", cause=cause)
        row = overview.escalations(cfg)[0]
    assert row["cause"] == cause and row["kind"] == "audit"
    assert row["why"] == overview.CAUSE_WHY[cause]
    assert row["requested"] == overview.CAUSE_REQUESTED[cause]
    assert row["remediations"] == ["revise", "stop"]


@pytest.mark.parametrize("integrity,cause", [
    ("NOTHING_AUDITED", "nothing_audited"), ("INVALID_REPLY", "invalid_reply"),
    ("BOUNDS_EXCEEDED", "bounds_exceeded")])
def test_a_record_without_a_stored_cause_is_named_from_its_receipt(cfg, integrity, cause):
    """Legacy rows: the receipt's `audit_integrity` alone names the branch."""
    _escalate(cfg, "b", integrity=integrity)
    row = overview.escalations(cfg)[0]
    assert row["cause"] == cause
    assert overview.read_cycles(cfg)[0].integrity == integrity


def test_the_auditors_own_escalation_keeps_its_stated_reason(cfg):
    _escalate(cfg, "d", cause="auditor_escalated", findings=BLOCKER)
    row = overview.escalations(cfg)[0]
    assert row["why"].startswith("The summary states 0.052")
    assert row["issues"][0]["rule"] == "CA-TXT-001"


def test_a_locked_cycle_points_at_its_holder_not_the_oldest_decision(cfg):
    """Review defects 1/2: three cycles — A (unrelated, oldest), B (unrelated),
    C refused because B is pending. C's earlier decision is B, never A, and
    never C itself. A lock whose holder is no longer waiting is not told as
    a lock at all."""
    a = _escalate(cfg, "a", cause="auditor_escalated")
    b = _escalate(cfg, "b", cause="auditor_escalated")
    c = _lock(cfg, "c", b)
    rows = {r["cycle_id"]: r for r in overview.escalations(cfg)}
    assert rows[c]["cause"] == "escalation_locked"
    assert rows[c]["earlier_cycle_id"] == b and rows[c]["earlier_cycle_id"] != a
    assert "earlier_cycle_id" not in rows[a] and "earlier_cycle_id" not in rows[b]
    # settle B: C no longer claims a lock it cannot name
    StateStore(cfg.root / cfg.state_dir / "state.json").resolve_escalation(b, "close", "done")
    rows = {r["cycle_id"]: r for r in overview.escalations(cfg)}
    assert rows[c]["cause"] == "" and "earlier_cycle_id" not in rows[c]
    assert rows[c]["requested"].startswith("Review why the loop stopped")


def _run(sha: str, science: Path) -> int:
    from crossaudit.cli.main import cmd_run
    return cmd_run(SimpleNamespace(sha=sha, json=False, allow_custom_endpoint=False,
                                   continue_cycle=None, offline=False, science=None))


def _audit(sha: str) -> int:
    from crossaudit.cli.main import cmd_audit
    return cmd_audit(argparse.Namespace(
        sha=sha, scope=None, json=False, retention=None, allow_custom_endpoint=False,
        on_step=None, continue_cycle=None, offline=False, write_ledger=True, mode=None))


ESCALATE_REPLY = {"verdict": "ESCALATE", "sections_applied": ["CA-DATA-001"],
                  "findings": []}


def test_the_real_commands_record_the_lock_on_the_refused_commit(
        science, transcripts, monkeypatch, capsys):
    """Review defect 3, driven through cmd_run and cmd_audit — no cause is
    injected. The reviewer's scenario: A and B escalate on unrelated
    lineages; C (child of B) is refused by cmd_run, D (child of C) by
    cmd_audit. Both refused commits get their own decision object whose
    holder is B; A and B are untouched; nothing points at itself."""
    from crossaudit.config import load
    from crossaudit.errors import EXIT_ESCALATED

    cfg = load(science / "crossaudit.yml")   # the science repo, not test_overview's
    monkeypatch.chdir(science)
    base = git("rev-parse", "HEAD", cwd=science)
    sha_a = write_increment(science, GOOD_RESULTS, "A.", "a")
    record_reply(transcripts, cfg, sha_a, ESCALATE_REPLY)
    assert _run(sha_a, science) == EXIT_ESCALATED
    git("checkout", "-q", "-b", "other", base, cwd=science)
    sha_b = write_increment(science, GOOD_RESULTS, "B.", "b")
    record_reply(transcripts, cfg, sha_b, ESCALATE_REPLY)
    assert _run(sha_b, science) == EXIT_ESCALATED
    from crossaudit.controller.state import cycle_id_for
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    a, b = cycle_id_for(cfg.science_repo, sha_a), cycle_id_for(cfg.science_repo, sha_b)
    assert {store.cycle(a)["escalation_cause"], store.cycle(b)["escalation_cause"]} == {
        "auditor_escalated"}

    # C is committed directly on B's commit (the ledger commits cmd_run made
    # sit on the branch tip, and the lock reads the direct parent).
    git("checkout", "-q", "-b", "on-b", sha_b, cwd=science)
    sha_c = write_increment(science, GOOD_RESULTS, "C.", "c")
    assert _run(sha_c, science) == EXIT_ESCALATED
    out = capsys.readouterr().out
    assert f"crossaudit resolve {b}" in out
    sha_d = write_increment(science, GOOD_RESULTS, "D.", "d")
    record_reply(transcripts, cfg, sha_d, PASS_REPLY)
    assert _audit(sha_d) == EXIT_ESCALATED

    rows = {r["sha"]: r for r in overview.escalations(cfg)}
    assert rows[sha_c]["cause"] == "escalation_locked"
    assert rows[sha_c]["earlier_cycle_id"] == b
    assert rows[sha_d]["cause"] == "escalation_locked"
    assert rows[sha_d]["earlier_cycle_id"] == b, "a chain of refused commits names the real holder"
    for row in rows.values():
        assert row.get("earlier_cycle_id") != row["cycle_id"]
    # the holders' own records are untouched
    assert store.cycle(b)["escalation_cause"] == "auditor_escalated"
    assert store.cycle(a)["escalation_cause"] == "auditor_escalated"
    assert "locked_by" not in store.cycle(b)
    # re-running the holder's own commit writes nothing new and names itself
    assert _run(sha_b, science) == EXIT_ESCALATED
    assert f"crossaudit resolve {b}" in capsys.readouterr().out
    assert len(overview.escalations(cfg)) == 4


@needs_node
def test_the_decision_center_names_every_cause_in_both_languages(cfg):
    """R5/R6. The shipped openResolution() over rows escalations() built:
    each cause has its own flag, title, what-happened line and next step;
    every Chinese slot is Chinese; the guidance box is prefilled where the
    next step is obvious; the locked cycle's button opens the earlier
    decision; the invalid reply's primary action is to run the audit again."""
    from render_decision import render

    ids = {}
    ids["nothing"] = _escalate(cfg, "a", cause="nothing_audited")
    ids["invalid"] = _escalate(cfg, "b", cause="invalid_reply")
    ids["bounds"] = _escalate(cfg, "c", cause="bounds_exceeded")
    ids["auditor"] = _escalate(cfg, "d", cause="auditor_escalated", findings=BLOCKER)
    ids["silent"] = _escalate(cfg, "f", cause="auditor_escalated")
    ids["locked"] = _lock(cfg, "e", ids["nothing"])
    rows = {r["cycle_id"]: r for r in overview.escalations(cfg)}
    out = render(WORKTREE, {name: rows[cid] for name, cid in ids.items()})

    flags = {name: out[name]["en"]["resolution-flag"] for name in out}
    assert flags == {"nothing": "Nothing to review yet", "invalid": "Auditor reply unreadable",
                     "bounds": "Task too large for one audit", "auditor": "The auditor asked for you",
                     "silent": "The auditor asked for you",
                     "locked": "Waiting on an earlier decision"}
    en = {name: out[name]["en"] for name in out}
    assert en["nothing"]["resolution-title"] == "The task produced no work in the audited folder"
    assert en["nothing"]["resolution-limit-copy"] == overview.CAUSE_WHY["nothing_audited"]
    assert en["invalid"]["resolution-title"] == "The auditor’s reply could not be read"
    assert en["invalid"]["resolution-reopen-title"] == "Run the audit again"
    assert en["bounds"]["resolution-request"].startswith("Narrow the scope or split the task")
    assert en["auditor"]["resolution-limit-title"] == "What the auditor said"
    assert en["auditor"]["resolution-limit-copy"].startswith("The summary states 0.052")
    # Review defect 11: no words from the auditor -> our sentence under OUR title.
    assert en["silent"]["resolution-limit-title"] == "What happened"
    assert en["silent"]["resolution-limit-copy"] == overview.CAUSE_WHY["auditor_escalated"]
    # Review defect 5: "What happened" never restates the title.
    for name in out:
        title, what = en[name]["resolution-title"], en[name]["resolution-limit-copy"]
        fold = lambda t: re.sub(r"[^a-z]", "", t.lower())
        assert fold(what) != fold(title) and not fold(what).startswith(fold(title)), (name, title, what)
        assert fold(what) not in fold(en[name]["resolution-summary"]), name
    assert en["locked"]["resolution-title"] == "This task is already waiting for your earlier decision"
    for name in out:
        assert "Automatic loop paused" not in en[name]["resolution-flag"]
        assert en[name]["resolution-request"], name
        for slot, text in out[name]["zh"].items():
            # The auditor's stated reason is its own words (D130: never marked
            # as a missing catalogue entry); every other slot is ours.
            own_words = name == "auditor" and slot == "resolution-limit-copy"
            if slot != "resolution-issues" and text and not own_words:
                assert CJK.search(text), (name, slot, text)
        # The issues slot is stripped HTML in the harness (one string, so the
        # per-node translator cannot be driven over it here); the English
        # form is checked for plain words and the words themselves in
        # test_finding_words_reach_a_chinese_reader.
        issues = out[name]["en"]["resolution-issues"]
        assert RAW_VERDICT.search(issues) is None
        assert "BLOCKER" not in issues and "ADVISORY" not in issues
    assert "must fix" in out["auditor"]["en"]["resolution-issues"]
    # The guidance box, prefilled where the next step is obvious.
    assert out["nothing"]["extra"]["en"]["reason_value"].startswith("Create the deliverable")
    assert CJK.search(out["nothing"]["extra"]["zh"]["reason_value"])
    assert out["invalid"]["extra"]["en"]["reason_value"].startswith("Run the audit again")
    assert out["bounds"]["extra"]["en"]["reason_value"] == ""
    # The locked cycle's secondary button opens the earlier decision.
    locked = out["locked"]["extra"]
    assert locked["en"]["settings_text"] == "Open the earlier decision"
    assert locked["zh"]["settings_text"] == "打开更早的决定"
    assert locked["en"]["settings_hidden"] is False
    assert locked["en"]["settings_earlier"] == ids["nothing"]
    # ...and stays the provider-connection button, hidden, for everyone else.
    assert out["bounds"]["extra"]["en"]["settings_text"] == "Review provider connection"
    assert out["bounds"]["extra"]["en"]["settings_hidden"] is True
    assert out["bounds"]["extra"]["en"]["settings_earlier"] == ""
    assert RULE_ID.search(out["auditor"]["en"]["resolution-issues"]) is None, (
        "the rule id is not on the Decision Center's first paint either")


@needs_node
def test_attempt_rows_and_issues_use_plain_words(cfg):
    """R1/R2 in the Decision Center: attempts say "Needs changes", never
    BLOCKED; an issue leads with the observation and says "must fix"."""
    from render_decision import render
    sha = _sha("a")
    add_audit(cfg, sha[:12], "BLOCKED", BLOCKER + "\n" + ADVISORY)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    c = store.open_or_advance(cfg.science_repo, sha, None)
    store.record_verdict(c["cycle_id"], sha, "BLOCKED", "r" * 64, 1)
    row = overview.escalations(cfg)[0]
    assert row["cause"] == "" and row["kind"] == "audit"
    out = render(WORKTREE, {"limit": row})
    issues = out["limit"]["en"]["resolution-issues"]
    assert issues.startswith("The summary states 0.052")
    assert "must fix" in issues and "suggestion" in issues
    assert "BLOCKER" not in issues and "ADVISORY" not in issues
    assert RULE_ID.search(issues) is None
    # The attempts row is HTML the harness does not strip; read it from the page.
    assert "esc(verdictWord(item.verdict))" in PAGE
    assert "esc(item.verdict)" not in PAGE


@needs_node
def test_every_new_string_reaches_a_chinese_reader(tmp_path):
    """Translation boundary for this slice: the page's cause table, the
    dashboard's why/next-step sentences, and the short words, all through the
    shipped translator."""
    from render_decision import eval_page
    from .test_console_translation_boundary import _translate
    table = json.loads(eval_page(WORKTREE, ["const CAUSE_COPY={"],
                                 "console.log(JSON.stringify(CAUSE_COPY));"))
    values = {v for copy in table.values() for v in copy.values() if v}
    values |= set(overview.CAUSE_WHY.values()) | set(overview.CAUSE_REQUESTED.values())
    values |= {"Passed", "Needs changes", "Needs you", "Checks only", "must fix",
               "suggestion", "Details", "Rules", "Open the earlier decision",
               "First run here — no estimate yet", "3 issues", "1 issue",
               "Usually 2–4 min · about $0.30", "Usually about 3 min",
               "Usually under a minute · about $0.01", "Rule id: CA-REP-001"}
    rendered = _translate(sorted(values), tmp_path)
    untranslated = sorted(v for v in values if not CJK.search(rendered[v]))
    assert untranslated == [], untranslated


def _big_project(cfg, runs: int, lines: int) -> None:
    """A ledger of `lines` events and a journal of `runs` completed runs."""
    from crossaudit.runtime.runs import RunJournal, journal_path
    RunJournal(journal_path(cfg))
    db = sqlite3.connect(journal_path(cfg))
    db.executemany(
        "INSERT INTO runs(run_id,task,chat_id,continuation_cycle,state,outcome,"
        "error,owner_pid,started,updated,finished) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [(f"r{i}", "t", "history", "", "PASSED", "", "", 1,
          1000.0 + 300 * i, 1000.0 + 300 * i, 1000.0 + 300 * i + 120) for i in range(runs)])
    db.commit(); db.close()
    ledger = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("w") as out:
        for i in range(lines):
            run = i % runs
            out.write(json.dumps({"t": int((1000 + 300 * run + 10) * 1000), "role": "generator",
                                  "phase": "completion", "input": 10, "output": 5,
                                  "cache_write": 0, "cache_read": 0, "total": 15,
                                  "method": "reported", "api_value_usd": 0.001,
                                  "billing_kind": "api_value"}) + "\n")


def test_the_forecast_is_cached_and_the_join_is_not_quadratic(cfg):
    """Review defect 7. 1000 runs x 50000 ledger lines: after the first
    computation the snapshot's cached path is a lookup (< 50 ms), and even the
    uncached join is bisected, not runs x events."""
    usage._SUMMARY_CACHE.clear(); usage._FORECAST_CACHE.clear()
    _big_project(cfg, 1000, 50000)
    first = usage.summary(cfg)["forecast"]
    assert first["runs"] == 1000 and first["seconds"]["p50"] == 120.0
    assert first["usd"]["p50"] == pytest.approx(0.05)
    usage.summary(cfg)   # the journal's first read-only open may settle its WAL
    started = time.perf_counter()
    again = usage.summary(cfg)["forecast"]
    cached_ms = (time.perf_counter() - started) * 1000
    assert again == first
    assert cached_ms < 50, f"cached snapshot path took {cached_ms:.1f} ms"
    # the forecast's own cache, keyed on the ledger stat and the run rows
    path = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    stat = path.stat()
    events, _ = usage.read_events(path)
    started = time.perf_counter()
    usage.project_forecast(cfg, path, (stat.st_mtime_ns, stat.st_size), events)
    hit_ms = (time.perf_counter() - started) * 1000
    assert hit_ms < 50, f"forecast cache hit took {hit_ms:.1f} ms"
    runs = usage._journal_runs(cfg)
    for run in runs:
        run["run_id"] = ""            # legacy rows: the window join, not the run id
    started = time.perf_counter()
    rows = usage.forecast_rows(events, runs)
    join_ms = (time.perf_counter() - started) * 1000
    assert len(rows) == 1000 and rows[0]["usd"] == pytest.approx(0.05)
    assert join_ms < 1000, f"the window join took {join_ms:.0f} ms (was quadratic)"


def test_a_non_utf8_byte_in_the_ledger_does_not_take_the_snapshot_down(cfg):
    """Review defect 10."""
    ledger = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    ledger.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps({"t": 1, "api_value_usd": 0.1, "total": 3, "method": "reported"})
    ledger.write_bytes((good + "\n").encode() + b'{"t": 2, "x": "\xff\xfe"}\n' + b"\xff{\n")
    usage._SUMMARY_CACHE.clear()
    got = usage.summary(cfg)
    assert got["all"]["calls"] >= 1 and got["malformed_lines"] == 1
    assert got["forecast"]["runs"] == 0
