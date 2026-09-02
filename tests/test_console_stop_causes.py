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

from crossaudit.cli.main import CONTESTED_MODEL_BLOCKER_REASON
from crossaudit.console import overview, streams
from crossaudit.console.page import PAGE
from crossaudit.controller import StateStore
from crossaudit.dcl.framework import FINDING_STATES

from .test_finding_states import _strings
from .test_overview import BLOCKER, DCL_BLOCKER, add_audit, cfg  # noqa: F401

HARNESS = Path(__file__).parent / "harness"
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
    assert row["requested"].startswith("Tell the generator the smallest change")
    assert row["issues"][0]["rule"] == "CA-TXT-001"
    assert row["remediations"] == ["revise", "stop"]


def test_the_page_keys_both_causes_on_the_structured_field():
    assert "row.cause==='repair_refused'" in PAGE
    assert "row.cause==='auditor_concern'" in PAGE
    assert "'Automatic repair refused'" in PAGE
    assert "'The auditor raised a concern'" in PAGE
    # A refused repair shows the guard's sentence, not the round wrapper.
    assert "(repairRefused&&row.why)" in PAGE


# ----------------------------------------------------------- auditor concern
def test_the_escalate_dial_stop_is_named_from_the_receipt_route(cfg):
    cycle_dir = add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER)
    _receipt(cycle_dir, _authority("human-decision"))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, SHA, None)
    assert store.record_verdict(cycle["cycle_id"], SHA, "BLOCKED", "r" * 64, 1,
                                escalation_reason=CONTESTED_MODEL_BLOCKER_REASON
                                ) == "ESCALATED"
    row = overview.escalations(cfg)[0]
    assert row["cause"] == "auditor_concern" and row["kind"] == "audit"
    assert "Dispute a misreading" in row["requested"]
    assert row["stop_reason"] == CONTESTED_MODEL_BLOCKER_REASON
    assert overview.read_cycles(cfg)[0].authority_route == "human-decision"


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
    assert "function findingTier(f)" in PAGE
    assert PAGE.count("findingTier(f)") == 3  # the definition and the two lists
    assert "'Verified by a deterministic check'" in PAGE
    assert "'Raised by the auditor, not yet reproduced'" in PAGE
    assert ROUTE_NAME.search(PAGE) is None
    # The run card's loop steps are untouched: no tier or route on the main surface.
    loop = PAGE[PAGE.index("function runCard(d){"):PAGE.index("function approvalCard(d){")]
    assert "findingTier" not in loop and "authority" not in loop


# ----------------------------------------------------------------- Chinese
NEW_COPY = [
    "Automatic repair refused", "The revision did not repair the cause",
    "Why the last revision was refused",
    "Tell the generator the smallest change that repairs the cause, or stop the task without admitting its output.",
    "Name the file and the smallest change that repairs the cause, then unlock one additional audited round.",
    "The auditor raised a concern",
    "The auditor blocked this round on its own reading; no deterministic check reproduces the concern. CrossAudit does not let a model-only claim drive automatic rewrites, so it stopped and left the files unchanged.",
    CONTESTED_MODEL_BLOCKER_REASON,
    "Review the auditor's concern and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission.",
    "If the concern is right, tell the generator how to address it. If it is a misreading, say so here; your reason is recorded.",
    "Verified by a deterministic check", "Raised by the auditor, not yet reproduced",
    "Raised by the auditor and verified",
    "the revision was refused before the audit",
    "asking for a smaller repair that fixes the cause",
    "Your task or message", "Search projects",
    # The guard's composed sentences: the path survives, the rest is Chinese.
    GUARD_REASON,
    "docs/other.md is outside what the last audit asked to change (allowed: report.md)",
    "the code change touches 90 lines, more than the 60-line limit for an automatic repair",
    "src/x.py adds a bare `pass` where a failure would otherwise surface; src/y.py adds a retry or fallback path instead of fixing the cause",
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
    joined = rendered[NEW_COPY[-2]]
    assert joined.startswith("src/x.py ") and "src/y.py " in joined and "；" in joined
    assert rendered[NEW_COPY[-1]].startswith("第 2 轮")
