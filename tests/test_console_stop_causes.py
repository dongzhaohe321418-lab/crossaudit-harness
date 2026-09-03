"""D148 on the console: the two new stop causes, and evidence tiers in the
inspector.

A refused automatic repair (slice D) and the escalate dial handing a
model-only blocker to a person (slice B) are content stops that are not "the
rounds ran out". Each must say, in plain words and in both languages, what
happened, why, and what to do next — through the Decision Center's existing
slots, never a new element. And what a finding rests on (a deterministic
check, or the auditor's reading) is shown only where findings are already
listed, as a sentence, never as a route name or a finding state.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.console import overview, streams
from crossaudit.console.page import PAGE
from crossaudit.controller import StateStore
from crossaudit.dcl.framework import FINDING_STATES
from crossaudit.errors import CONTESTED_MODEL_BLOCKER_REASON

from .test_finding_states import _strings
from .test_overview import BLOCKER, DCL_BLOCKER, add_audit, cfg  # noqa: F401

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))
WORKTREE = Path(overview.__file__).parents[3]
STATE_WORD = re.compile(r"\b(" + "|".join(FINDING_STATES) + r")\b", re.I)
ROUTE_NAME = re.compile(r"automatic-repair|human-decision|obtain-audit")
GUARD_REASON = "src/x.py adds a catch-all `except` that swallows every error"
SHA = "d" * 40


def _authority(route: str = "automatic-repair") -> dict:
    """A receipt block the way `AuthorityDecision.as_dict()` writes it, for
    the two findings `DCL_BLOCKER` and `BLOCKER` raise."""
    return {"policy_version": "v1", "route": route,
            "blocking_evidence_ids": ["ev-1"],
            "contested_evidence_ids": ["ev-2"] if route == "human-decision" else [],
            "advisory_evidence_ids": [],
            "evidence": [
                {"evidence_id": "ev-1", "finding_key": "DCL:units@work/results.json",
                 "severity": "BLOCKER", "tier": "deterministic", "state": "confirmed"},
                {"evidence_id": "ev-2", "finding_key": "CA-TXT-001@work/a.md",
                 "severity": "BLOCKER", "tier": "model", "state": "alleged"}]}


def _receipt(cycle_dir: Path, authority: dict | None) -> None:
    body = {"ledger": {}}
    if authority is not None:
        body["authority"] = authority
    (cycle_dir / "receipt.json").write_text(json.dumps(body))


# ------------------------------------------------------------ repair refused
def test_a_refused_repair_leads_with_the_guards_own_sentence(cfg):
    """`why` is the file-and-pattern sentence, not the round wrapper, and the
    recommendation asks for the smallest causal repair."""
    add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    store.record_build_escalation(
        cfg.science_repo, SHA,
        f"the automatic repair was refused in round 2 because {GUARD_REASON}",
        2, "history", "Fix the summary", kind="audit", cause="repair_refused")
    row = overview.escalations(cfg)[0]
    assert row["cause"] == "repair_refused" and row["kind"] == "audit"
    assert row["why"] == GUARD_REASON
    assert row["requested"].startswith("Tell the generator to keep the fix inside")
    assert row["issues"][0]["rule"] == "CA-TXT-001"
    assert row["remediations"] == ["revise", "stop"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_decision_center_renders_each_cause_from_the_rows_the_dashboard_builds(cfg):
    """Review item 12: the shipped `openResolution()` driven under node over
    rows `escalations()` actually produced — a refused repair, the dial, a
    plain ESCALATE with an empty contested list — so a wrong branch shows up
    as the wrong sentence, in both languages, not as a missing string."""
    from render_decision import render

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    # a refused repair (build-level stop)
    add_audit(cfg, "a" * 12, "BLOCKED", BLOCKER)
    store.record_build_escalation(
        cfg.science_repo, "a" * 40,
        f"the automatic repair was refused in round 2 because {GUARD_REASON}",
        2, "history", "Fix the summary", kind="audit", cause="repair_refused")
    # the escalate dial (contested ids, no reason)
    dial = add_audit(cfg, "b" * 12, "ESCALATE", BLOCKER)
    _receipt(dial, _authority("human-decision"))
    c = store.open_or_advance(cfg.science_repo, "b" * 40, None)
    store.record_verdict(c["cycle_id"], "b" * 40, "ESCALATE", "r" * 64, 1)
    # a plain ESCALATE (empty contested list)
    plain = add_audit(cfg, "c" * 12, "ESCALATE", "")
    block = _authority("human-decision")
    block["contested_evidence_ids"] = []
    _receipt(plain, block)
    c = store.open_or_advance(cfg.science_repo, "c" * 40, None)
    store.record_verdict(c["cycle_id"], "c" * 40, "ESCALATE", "r" * 64, 1)

    # a provider failure on a keyless first run: the row carries `why_zh`
    # (overview, looked up by the recorded sentence) and the ZH pass of the
    # page prefers it over translating the English by text
    keyless = ("provider failure left this task waiting for a person: generator "
               "provider failure in round 1: all configured generator provider "
               "routes failed. anthropic:claude-opus-4-8 — anthropic credential "
               "$CROSSAUDIT_GENERATOR_KEY is not configured")
    store.record_build_escalation(cfg.science_repo, "e" * 40, keyless, 1,
                                  "history", "写一份报告", kind="provider")

    rows = {r["sha"][0]: r for r in overview.escalations(cfg)}
    out = render(WORKTREE, {"repair": rows["a"], "dial": rows["b"], "plain": rows["c"],
                            "keyless": rows["e"]})
    en, zh = out["keyless"]["en"], out["keyless"]["zh"]
    assert en["resolution-limit-copy"] == keyless, "the English sentence must not change"
    assert rows["e"]["why_zh"].startswith("供应商失败，该任务正在等待人工处理：生成者在第 1 轮失败：")
    assert zh["resolution-limit-copy"] == rows["e"]["why_zh"], zh["resolution-limit-copy"]
    assert "anthropic:claude-opus-4-8 — 未配置 anthropic 凭据 $CROSSAUDIT_GENERATOR_KEY" in zh["resolution-limit-copy"]
    assert not re.search(r"(?:\b[A-Za-z]+\b[ ,]+){6,}\b[A-Za-z]+\b", zh["resolution-limit-copy"]), (
        "a run of English inside the Chinese card: a slot swallowed a sentence")
    en, zh = out["repair"]["en"], out["repair"]["zh"]
    assert en["resolution-flag"] == "Automatic repair refused"
    assert "twice" not in en["resolution-summary"]
    assert en["resolution-limit-copy"] == GUARD_REASON
    assert zh["resolution-limit-copy"].startswith("src/x.py ") and "except" in zh["resolution-limit-copy"]
    assert "两次" not in zh["resolution-summary"] and "解锁额外一轮受审计执行" in zh["resolution-reopen-copy"]
    en, zh = out["dial"]["en"], out["dial"]["zh"]
    assert en["resolution-flag"] == "The auditor raised a concern"
    assert "Dispute" not in en["resolution-request"] and "提出争议" not in zh["resolution-request"]
    assert zh["resolution-flag"] == "审计者提出了一项疑虑"
    en, zh = out["plain"]["en"], out["plain"]["zh"]
    assert en["resolution-flag"] == "Automatic loop paused", en
    assert "auditor" not in en["resolution-summary"].lower()
    assert zh["resolution-flag"] == "自动循环已暂停"
    for name in out:
        for slot, text in out[name]["zh"].items():
            if slot != "resolution-issues" and text:
                assert re.search(r"[一-鿿]", text), (name, slot, text)


def test_the_page_keys_both_causes_on_the_structured_field():
    assert "row.cause==='repair_refused'" in PAGE
    assert "row.cause==='auditor_concern'" in PAGE
    assert "'Automatic repair refused'" in PAGE
    assert "'The auditor raised a concern'" in PAGE
    # A refused repair shows the guard's sentence, not the round wrapper.
    assert "(repairRefused&&row.why)" in PAGE


# ----------------------------------------------------------- auditor concern
def test_the_escalate_dial_stop_is_named_from_the_receipts_contested_ids(cfg):
    """The receipt ALONE names it: the verdict is recorded with no reason, so
    only `contested_evidence_ids` can. Mutation M13 (review): delete the
    id-based branch and keep the sentence fallback — red here."""
    cycle_dir = add_audit(cfg, SHA[:12], "ESCALATE", BLOCKER)
    _receipt(cycle_dir, _authority("human-decision"))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, SHA, None)
    assert store.record_verdict(cycle["cycle_id"], SHA, "ESCALATE", "r" * 64, 1,
                                escalation_reason="") == "ESCALATED"
    row = overview.escalations(cfg)[0]
    assert row["cause"] == "auditor_concern" and row["kind"] == "audit"
    assert row["requested"].startswith("Review the auditor's concern")
    latest = overview.read_cycles(cfg)[0]
    assert latest.authority_contested is True
    assert latest.authority_route == "human-decision"


def test_a_plain_escalate_keeps_the_generic_copy(cfg):
    """Review defect 1: every ESCALATE routes to human-decision — the
    auditor's own escalation, the lock, an integrity stop. Only a contested
    blocker is the dial. Mutation: derive from the route — red here."""
    cycle_dir = add_audit(cfg, SHA[:12], "ESCALATE", "")
    block = _authority("human-decision")
    block["contested_evidence_ids"] = []
    _receipt(cycle_dir, block)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, SHA, None)
    store.record_verdict(cycle["cycle_id"], SHA, "ESCALATE", "r" * 64, 1)
    row = overview.escalations(cfg)[0]
    assert row["cause"] == ""
    assert overview.read_cycles(cfg)[0].authority_route == "human-decision"
    assert row["requested"].startswith("Review why the loop stopped")


def test_the_sentence_alone_names_the_cause_when_no_receipt_is_beside_the_report(cfg):
    add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, SHA, None)
    store.record_verdict(cycle["cycle_id"], SHA, "BLOCKED", "r" * 64, 1,
                         escalation_reason=CONTESTED_MODEL_BLOCKER_REASON)
    assert overview.escalations(cfg)[0]["cause"] == "auditor_concern"


def test_an_ordinary_blocked_round_keeps_the_correction_copy(cfg):
    """The new branch must not swallow the existing one: a BLOCKED round with
    findings and no dial still asks for correction guidance."""
    cycle_dir = add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER)
    _receipt(cycle_dir, _authority("automatic-repair"))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, SHA, None)
    store.record_verdict(cycle["cycle_id"], SHA, "BLOCKED", "r" * 64, 1)
    row = overview.escalations(cfg)[0]
    assert row["cause"] == ""
    assert row["requested"].startswith("Tell the generator how to correct")


# ------------------------------------------------------------ evidence tiers
def test_findings_carry_their_tier_from_the_receipt(cfg):
    cycle_dir = add_audit(cfg, SHA[:12], "BLOCKED", DCL_BLOCKER + "\n" + BLOCKER)
    _receipt(cycle_dir, _authority())
    cycle = overview.read_cycles(cfg)[0]
    by_rule = {f["rule"]: f for f in cycle.findings}
    assert by_rule["DCL:units"]["tier"] == "deterministic"
    assert by_rule["DCL:units"]["verified"] is True
    assert by_rule["CA-TXT-001"]["tier"] == "model"
    assert by_rule["CA-TXT-001"]["verified"] is False
    assert cycle.authority_route == "automatic-repair"
    # The Audits stream lists the same findings and says the same thing.
    rows = [m for m in streams.auditor_stream(cfg, []) if m.get("findings")]
    assert {f["rule"]: f["tier"] for f in rows[0]["findings"]} == {
        "DCL:units": "deterministic", "CA-TXT-001": "model"}


def test_a_receipt_without_the_block_renders_no_tier(cfg):
    cycle_dir = add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER)
    _receipt(cycle_dir, None)
    cycle = overview.read_cycles(cfg)[0]
    assert "tier" not in cycle.findings[0] and cycle.authority_route == ""


def test_no_dashboard_surface_carries_a_route_name_or_a_state_word(cfg):
    """The route and the state stay in the receipt. The pipeline's Verdict
    detail is unchanged, and `annotate_findings` copies tier and verified but
    never `state`. Mutation: copy `state` into the finding — red here."""
    cycle_dir = add_audit(cfg, SHA[:12], "BLOCKED", DCL_BLOCKER + "\n" + BLOCKER)
    _receipt(cycle_dir, _authority())
    cycles = overview.read_cycles(cfg)
    surfaces = [overview.metrics(cfg, cycles), overview.pipeline(cfg, cycles),
                overview.escalations(cfg), [c.findings for c in cycles]]
    for text in _strings(surfaces):
        assert STATE_WORD.search(text) is None, text
        assert ROUTE_NAME.search(text) is None, text
    verdict = overview.pipeline(cfg, cycles)[3]
    assert verdict["detail"] == "BLOCKED · 2 finding(s)"


def test_the_page_names_the_tier_in_a_sentence_and_never_a_route():
    """Mutation (results & decisions slice R2): the tier sentence moved from
    its own row (`findingTier`) onto the finding's details line (`tierWord`,
    rendered by `findingCard`, the one renderer both lists share). Still a
    sentence, still only where findings are listed, still never a route."""
    assert "function tierWord(f)" in PAGE
    assert "findingTier" not in PAGE, "the separate tier row is gone; one details line"
    assert PAGE.count("findingCard") == 3  # the definition and the two lists
    assert "'verified by a check'" in PAGE
    assert "'raised by the auditor, not yet reproduced'" in PAGE, (
        "a model-only claim must say it is not yet reproduced, not merely lack a word")
    assert ROUTE_NAME.search(PAGE) is None
    # The stream's rows are untouched: no tier or route on the main surface.
    # (The run card is gone; the loop's events are rows now.)
    stream = PAGE[PAGE.index("// ============================================================== THE STREAM"):
                  PAGE.index("function turn(m,d){")]
    assert "tierWord" not in stream and "authority" not in stream


# ----------------------------------------------------------------- Chinese
NEW_COPY = [
    "Automatic repair refused", "The revision reached outside the audited files",
    "Why the last revision was refused",
    "Tell the generator to keep the fix inside the audited files, or stop the task without admitting its output.",
    "Name the file inside the audited directories that should change, then unlock one additional audited round.",
    "The auditor raised a concern",
    "The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.",
    CONTESTED_MODEL_BLOCKER_REASON,
    "Review the auditor's concern and its evidence. If it is a misreading, say so in your reason and continue; if it is right, tell the generator how to address it; or stop without admitting the work.",
    "If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.",
    "Verified by a deterministic check", "Raised by the auditor, not yet reproduced",
    "Raised by the auditor and verified",
    "the revision was refused before the audit",
    "asking for a repair that stays within the audited files",
    "the revision has edits the auditor should weigh",
    "Your task or message", "Search projects",
    # The repair guard's own sentences are gated by tests/test_repair_guard_console_zh.py,
    # which drives what the guard REALLY emits rather than a hand list.
    GUARD_REASON,
    f"the automatic repair was refused in round 2 because {GUARD_REASON}",
]



def _translate(values: list[str], tmp_path: Path) -> dict:
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"),
         str(Path(overview.__file__).parents[3])],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_new_sentence_reaches_a_chinese_reader(tmp_path):
    rendered = _translate(NEW_COPY, tmp_path)
    english = [v for v in NEW_COPY if not re.search(r"[一-鿿]", rendered[v])]
    assert english == [], f"still English: {english}"
    # Paths are never translated; the sentence around them is.
    assert rendered[GUARD_REASON].startswith("src/x.py ")
    assert "except" in rendered[GUARD_REASON]
    assert rendered[NEW_COPY[-1]].startswith("第 2 轮")
