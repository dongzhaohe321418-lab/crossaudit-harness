"""A finding can now say what became of it. Nothing decides anything with it yet.

`BLOCKER` carried two meanings at once — *a model believes there is a problem*
and *there is a problem* — and the dashboard said "a defect was caught" because
the structure had nothing else to offer. It was not overclaiming by choice.

This slice adds the field and populates it. Blocking is unchanged, no surface
renders the words, and no receipt digest moves.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from crossaudit.auditor import prompt as prompt_mod
from crossaudit.auditor.run import finding_states, render_report, run_audit
from crossaudit.console import overview
from crossaudit.dcl import framework
from crossaudit.dcl.framework import (ALLEGED, CONFIRMED, FINDING_STATES,
                                      Finding, run_checks)
from crossaudit.gitio import materialise

from .conftest import BAD_RESULTS, GOOD_RESULTS, PASS_REPLY, git, record_reply, write_increment

SRC = Path(framework.__file__).parent.parent
#: Whole words, any case: "unconfirmed" is prose, "Confirmed" is the state.
STATE_WORD = re.compile(r"\b(" + "|".join(FINDING_STATES) + r")\b", re.I)
MODEL_BLOCKER = {"verdict": "BLOCKED", "sections_applied": ["CA-DATA-001"],
                 "findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                               "artifact": "experiments/demo/SUMMARY.md",
                               "observation": "the claim overstates the table"}]}


def _strings(value) -> list[str]:
    """Every string a structure carries, however nested."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    if hasattr(value, "__dataclass_fields__"):
        return [s for k in value.__dataclass_fields__ for s in _strings(getattr(value, k))]
    return []


def _real_round(science, cfg, transcripts, results=BAD_RESULTS, reply=None):
    """One audit round the way the CLI runs it, its report placed in the ledger."""
    sha = write_increment(science, results, "Attempt.", "increment")
    if reply is not None:
        record_reply(transcripts, cfg, sha, reply)
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    outcome = run_audit(cfg=cfg, sha=sha, round_=1, files=files, notes=notes,
                        constitution=const, constitution_commit=cc,
                        offline=reply is None)
    ledger = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r1"
    ledger.mkdir(parents=True)
    (ledger / "report.md").write_text(outcome.report)
    return sha, outcome
STARTED = {"experiments/demo/notes.txt": b"x"}
CLEAN = {"experiments/demo/results.json":
         b'{"quantities":[{"name":"x","value":1,"unit":"m","source":"s"}]}',
         "experiments/demo/metadata.yml": b"code_version: abc\ninputs: [d@v1]\n"}


def test_all_six_states_exist_and_are_distinct():
    assert FINDING_STATES == ("alleged", "confirmed", "fixed", "withdrawn",
                              "overridden", "unresolved")
    assert len(set(FINDING_STATES)) == 6


# ------------------------------------------------- the two honest defaults
def test_a_deterministic_finding_is_confirmed_not_alleged():
    """Verdict-in-code: `hard_failures` never consults a model, and the audit
    ladder reads it BEFORE the model's verdict. Demoting these into allegations
    would give up the distinction the states exist for."""
    result = run_checks(STARTED, ["schema"]).as_dict()
    assert result["findings"], "the fixture raised nothing to inspect"
    for finding in result["findings"]:
        assert finding["state"] == CONFIRMED, (
            f"a deterministic finding is {finding['state']!r}; that layer was "
            f"never an allegation")


def test_a_model_finding_is_alleged():
    reply = {"findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                           "artifact": "r.json", "observation": "x"}]}
    rows = finding_states(run_checks(CLEAN, ["schema"]).as_dict(), reply)
    model = [r for r in rows if r["tier"] == "model"]
    assert model and all(r["state"] == ALLEGED for r in model), (
        "a model finding claims to be established")


def test_both_tiers_appear_in_one_record_with_their_own_states():
    reply = {"findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                           "artifact": "r.json", "observation": "x"}]}
    rows = finding_states(run_checks(STARTED, ["schema"]).as_dict(), reply)
    by_tier = {r["tier"]: r["state"] for r in rows}
    assert by_tier == {"deterministic": CONFIRMED, "model": ALLEGED}


def test_a_dcl_row_without_a_state_is_confirmed_and_an_unknown_state_is_refused():
    """The default lives in finding_states itself, not only on the dataclass:
    checks.json read back or a hand-built dict is still a deterministic finding.
    Mutation: `f.get("state", "")` (the merged version) — the first assertion
    reads "" and the second raises nothing."""
    plain = {"findings": [{"severity": "BLOCKER", "rule": "DCL:schema",
                           "artifact": "a.json", "observation": "x"}]}
    assert finding_states(plain, None)[0]["state"] == CONFIRMED
    bogus = {"findings": [{"severity": "BLOCKER", "rule": "DCL:schema",
                           "artifact": "a.json", "state": "probable"}]}
    with pytest.raises(ValueError, match="probable"):
        finding_states(bogus, None)


# ------------------------------------------- constraint 1: nothing decides
def test_nothing_gates_on_the_new_field():
    """A slice that both introduces the states and changes what they gate is
    two changes, and the second cannot be reviewed while the first moves."""
    for module in ("dcl/framework.py", "auditor/run.py", "cli/main.py",
                   "receipt/build.py", "receipt/verify.py"):
        text = (SRC / module).read_text()
        for state in FINDING_STATES:
            assert f'== "{state}"' not in text and f'!= "{state}"' not in text, (
                f"{module} branches on the finding state; this slice adds the "
                f"field and populates it, it does not decide with it")


def test_blocking_is_unchanged_by_the_field():
    """The count that gates is still severity, untouched by state."""
    result = run_checks(STARTED, ["schema"]).as_dict()
    assert result["total_hard_failures"] == sum(
        1 for f in result["findings"] if f["severity"] == "BLOCKER")
    assert result["verdict"] == "BLOCKED"


# ------------------------------------ constraint 2: no user-facing surface
def test_no_user_facing_surface_renders_a_state_word(science, cfg, transcripts):
    """The product goal is a black box; a person must never meet "alleged".

    Asserted on what the dashboard actually returns for a blocked round with
    both tiers raising something — metrics, pipeline, findings, top rules,
    escalations — not on page source. Mutation M6 (review A): change the
    Blocked note in overview.py to "alleged" — this reads it in the metrics
    row and goes red. Mutation: make read_cycles copy `state` into each
    finding dict — red through `_strings(cycles)`.
    """
    _real_round(science, cfg, transcripts, BAD_RESULTS, None)
    cycles = overview.read_cycles(cfg)
    assert cycles and cycles[0].verdict == "BLOCKED" and cycles[0].findings
    surfaces = [overview.metrics(cfg, cycles), overview.pipeline(cfg, cycles),
                overview.findings_by_severity(cycles), overview.top_rules(cycles),
                overview.escalations(cfg), cycles]
    for text in _strings(surfaces):
        hit = STATE_WORD.search(text)
        assert hit is None, f"the dashboard says {hit.group(0)!r}: {text!r}"


def test_page_markup_declares_no_state_word():
    """The static half: the page's own markup and catalogue carry none of the
    words either. `"fixed"` is exempt here only because CSS `position: fixed`
    is a quoted token in this file and not a word a person reads."""
    page = (SRC / "console/page.py").read_text()
    zh_and_markup = re.sub(r"^\s*//.*$", "", page, flags=re.M)
    for state in FINDING_STATES:
        assert f'"{state}"' not in zh_and_markup or state == "fixed", (
            f"the console markup carries the finding state {state!r}")


def test_the_report_does_not_carry_the_state(cfg):
    """The report is what a user reads; it is deliberately not the states'
    home. Asserted on the rendered text with a deterministic failure, a model
    blocker and an authority block all present. Mutation M5 (review A):
    render_report appends `Status: {f.get("state")}` per finding — red.
    Mutation: render the evidence table's `verified` column as the state word
    instead of yes/no — red."""
    from crossaudit.auditor.authority import decide_authority, records_from_audit

    dcl = run_checks(STARTED, ["schema"]).as_dict()
    records = records_from_audit(dcl, MODEL_BLOCKER, provider="replay", model="m",
                                 vendor="anthropic", dcl_digest="d" * 64,
                                 prompt_sha256="p" * 64)
    decision = decide_authority(records, verdict="BLOCKED", integrity="OK",
                                escalation_lock=False, scope_started=True,
                                model_decided=False)
    report = render_report(cfg=cfg, sha="a" * 40, round_=1, verdict="BLOCKED",
                           dcl=dcl, reply=MODEL_BLOCKER, invalid=None,
                           constitution_commit="c" * 40, provider="replay",
                           model="m", authority=decision.as_dict())
    assert "DCL:schema" in report and "CA-DATA-001" in report and "## Evidence" in report
    hit = STATE_WORD.search(report)
    assert hit is None, f"the report says {hit.group(0)!r} near: {report[max(0, hit.start() - 40):hit.end() + 40]!r}"


def test_the_model_prompt_carries_no_state():
    """The auditor is shown the deterministic output, not how the record is
    kept: `state` is projected out before json.dumps, so the receipt-bound
    prompt_sha256 is a function of what was checked. Mutation: json.dumps(dcl)
    directly (the merged version) — '"state": "confirmed"' appears and this
    goes red."""
    dcl = run_checks(STARTED, ["schema"]).as_dict()
    assert dcl["findings"] and all(f["state"] == CONFIRMED for f in dcl["findings"])
    prompt, _bounded, _sha = prompt_mod.build("### CA-X\n", "c" * 40, dcl, STARTED)
    section = prompt[prompt.index("DETERMINISTIC CHECK OUTPUT"):prompt.index("INCREMENT DATA")]
    assert "DCL:schema" in section, "the projection dropped the finding itself"
    assert '"state"' not in section
    assert STATE_WORD.search(section) is None


# ------------------------------- constraint 3: old receipts still verify
def test_a_receipt_without_the_authority_block_carries_no_state_word(
        science, cfg, transcripts):
    """The receipt's only home for a finding state is the OPTIONAL authority
    block (D148 slice B), which binds it by digest. Without that block a
    receipt carries none of the words, which is what keeps every receipt
    written before the field byte-identical. Mutation: write the block when
    authority is None — the canonical bytes carry "confirmed" and go red."""
    from crossaudit.gitio import resolve
    from crossaudit.receipt import build, canonical

    sha, outcome = _real_round(science, cfg, transcripts, BAD_RESULTS, None)
    assert outcome.dcl["findings"], "nothing deterministic was raised to leak"
    _s, tree = resolve(cfg.root, sha)
    from crossaudit.auditor import dcl_source_digest
    receipt = build(cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "experiments"},
                    cycle={"cycle_id": "c", "root_sha": sha, "active_sha": sha, "round": 1},
                    manifest={}, constitution_path=cfg.constitution,
                    constitution_bytes=b"x", constitution_commit="c" * 40,
                    dcl_source_sha256=dcl_source_digest(), prompt_sha256="p" * 64,
                    checks=cfg.checks, verdict=outcome.verdict, exchange=outcome.exchange,
                    retention="sealed", report_bytes=b"r", report_commit="",
                    cycle_path="cycles/x", audit_repo="local", mode="local",
                    integrity=outcome.integrity, authority=None)
    assert "authority" not in receipt
    assert STATE_WORD.search(canonical(receipt).decode()) is None


def test_the_receipt_builder_never_copies_findings_in():
    """Findings are not in the receipt outside the digest-bound authority
    block, and the sidecar is not bound by it.

    If this ever changes, every receipt already written stops verifying — the
    field would have been added at the cost of all history.
    """
    build = (SRC / "receipt/build.py").read_text()
    assert "findings" not in build, (
        "the receipt now carries findings; adding a field to them changes the "
        "digest of every receipt written from here, and breaks none written "
        "before only by luck")
    for state in FINDING_STATES:
        assert state not in build


def test_the_sidecar_is_written_beside_the_receipt_not_inside_it():
    main = (SRC / "cli/main.py").read_text()
    assert 'ledger / "findings.json"' in main, "the states are not persisted"
    receipt_line = main[main.index('ledger / "receipt.json"'):][:200]
    assert "finding_states" not in receipt_line


def test_the_sidecar_is_committed_with_the_ledger_and_leaves_the_tree_clean(
        science, cfg, transcripts, monkeypatch):
    """Review A defect 1: the sidecar was written but never staged, so it sat
    untracked, was swept into the next science commit by `git add -A`, and
    tripped the console's workspace_dirty refusal. Mutation: drop
    `findings.json` from either `git add` in cmd_run — `git ls-files` lacks it
    and the porcelain status is non-empty."""
    from types import SimpleNamespace

    from crossaudit.cli.main import cmd_run

    monkeypatch.chdir(science)
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    record_reply(transcripts, cfg, sha, PASS_REPLY)
    cmd_run(SimpleNamespace(sha=sha, json=False, allow_custom_endpoint=False,
                            continue_cycle=None))
    tracked = git("ls-files", "cycles", cwd=science).splitlines()
    assert f"cycles/{sha[:12]}-r1/findings.json" in tracked, tracked
    assert git("status", "--porcelain", cwd=science) == "", "the run left the tree dirty"
    assert json.loads((science / "cycles" / f"{sha[:12]}-r1" / "findings.json").read_text())["findings"] == []


# ------------------------------------------- constraint 4: the dashboard
def test_the_dashboard_no_longer_claims_a_defect_was_caught():
    """Checkably false the moment a finding can be `alleged`."""
    text = (SRC / "console/overview.py").read_text()
    live = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    assert '"a defect was caught"' not in live, (
        "the dashboard still asserts a defect was established")
    assert '"a concern was raised"' in live, (
        "replaced with something other than what the system knows")


def test_the_replacement_reaches_a_chinese_reader():
    page = (SRC / "console/page.py").read_text()
    assert '"a concern was raised":' in page, "the new note has no Chinese form"
    assert '"a defect was caught":' not in page, (
        "a stale entry translates a string nothing renders")
