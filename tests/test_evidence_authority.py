"""Evidence authority (D148 slices B and C): derived, digest-bound, opt-in.

The layer writes down what each finding is and who produced it, binds that
into the receipt, and derives the round's route from the ladder's verdict. It
re-decides nothing under the default dial. Every test names the mutation it
was shown to fail against (D10/D64).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

import pytest

from crossaudit.auditor import run_audit
from crossaudit.auditor.authority import (CLAIM_CHARS, KNOWN_POLICY_VERSIONS,
                                          POLICY_VERSION, ROUTE_FROM_LABEL,
                                          ROUTE_LABELS, EvidenceRecord,
                                          decide_authority, records_from_audit,
                                          validate_block)
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.dcl.framework import ALLEGED, CONFIRMED
from crossaudit.errors import ConfigDenial, IntegrityDenial
from crossaudit.gitio import materialise, parent, resolve
from crossaudit.receipt import build, canonical, validate, verify
from crossaudit.receipt.verify import admit

from .conftest import BAD_RESULTS, GOOD_RESULTS, PASS_REPLY, git, record_reply, write_increment

DCL_BLOCKER = {"findings": [{"severity": "BLOCKER", "rule": "DCL:parseable",
                             "check": "parseable", "artifact": "result.json",
                             "observation": "invalid JSON", "state": CONFIRMED}],
               "total_hard_failures": 1, "scope_started": True}
MODEL_BLOCKED = {"verdict": "BLOCKED", "sections_applied": ["CA-DATA-001"],
                 "findings": [{"severity": "BLOCKER", "rule": "CA-DATA-001",
                               "artifact": "experiments/demo/SUMMARY.md",
                               "observation": "the claim may overstate the table"}]}
DIGESTS = dict(dcl_digest="d" * 64, prompt_sha256="p" * 64)


def _records(dcl, reply):
    return records_from_audit(dcl, reply, provider="replay", model="m",
                              vendor="anthropic", **DIGESTS)


def _decide(records, verdict, **kw):
    base = dict(integrity="OK", escalation_lock=False, scope_started=True,
                model_decided=False)
    base.update(kw)
    return decide_authority(records, verdict=verdict, **base)


# ------------------------------------------------------------- records
def test_records_carry_tier_state_and_producer_from_finding_states():
    """Mutation: swap the model producer digest for the DCL digest — the model
    row's producer_digest assertion fails."""
    records = _records(DCL_BLOCKER, MODEL_BLOCKED)
    det, mod = records
    assert (det.tier, det.state, det.verified) == ("deterministic", CONFIRMED, True)
    assert det.producer == "check:parseable" and det.producer_digest == "d" * 64
    assert (mod.tier, mod.state, mod.verified) == ("model", ALLEGED, False)
    assert mod.producer == "auditor:anthropic/replay:m"
    assert mod.producer_digest == "p" * 64
    assert mod.claim == "the claim may overstate the table"
    assert all(r.evidence_id.startswith("ev-") for r in records)


# -------------------------------------------- v1 derives; it does not decide
def test_deterministic_blocker_keeps_blocking_authority_offline():
    """Mutation: drop the confirmed-blocker filter — blocking ids come back
    empty and the route no longer names the reproduced evidence."""
    decision = _decide(_records(DCL_BLOCKER, None), "BLOCKED")
    assert decision.workflow_verdict == "BLOCKED"
    assert decision.route == "bounded-revision"
    assert decision.blocking_evidence_ids == (decision.evidence[0].evidence_id,)
    assert not decision.requires_human


def test_default_dial_keeps_blocked_for_a_lone_model_blocker():
    """Mutation: default the dial to 'escalate' — the verdict flips to
    ESCALATE and the three-round bounded revision contract breaks. Mutation:
    drop `model_decided` from the flip's conjunction — this still holds (dial
    is block) but test_escalate_dial_does_not_touch_a_deterministic_block
    goes red."""
    decision = _decide(_records({"findings": [], "total_hard_failures": 0},
                                MODEL_BLOCKED), "BLOCKED", model_decided=True)
    assert decision.workflow_verdict == "BLOCKED"
    assert decision.route == "bounded-revision"
    assert decision.blocking_evidence_ids == () and decision.contested_evidence_ids == ()
    assert decision.advisory_evidence_ids == (decision.evidence[0].evidence_id,)
    assert "unverified" in " ".join(decision.rationale)


def test_escalate_dial_routes_a_lone_model_blocker_to_a_person():
    """Mutation: drop `verdict == "BLOCKED"` from the flip's conjunction — a
    model PASS under the escalate dial would read ESCALATE and
    test_escalate_dial_leaves_a_model_pass_alone goes red; drop `model_decided`
    and test_escalate_dial_does_not_touch_a_deterministic_block goes red."""
    decision = _decide(_records({"findings": [], "total_hard_failures": 0},
                                MODEL_BLOCKED), "BLOCKED", model_decided=True,
                       lone_model_blocker="escalate")
    assert decision.workflow_verdict == "ESCALATE"
    assert decision.route == "human-decision" and decision.requires_human
    assert decision.contested_evidence_ids == (decision.evidence[0].evidence_id,)
    assert decision.blocking_evidence_ids == ()
    assert "a model reading without reproduced evidence" in decision.rationale[0]
    assert decision.lone_model_blocker == "escalate"


def test_escalate_dial_does_not_touch_a_deterministic_block():
    """A DCL hard failure decides BLOCKED before the ladder reaches the model
    (model_decided is False), so the dial has nothing to flip. Mutation: drop
    `model_decided` from the flip's conjunction — this reads ESCALATE."""
    decision = _decide(_records(DCL_BLOCKER, MODEL_BLOCKED), "BLOCKED",
                       model_decided=False, lone_model_blocker="escalate")
    assert decision.workflow_verdict == "BLOCKED"
    assert decision.contested_evidence_ids == ()
    assert len(decision.blocking_evidence_ids) == 1


def test_escalate_dial_leaves_a_model_pass_alone():
    """Mutation: drop `verdict == "BLOCKED"` from the flip — this reads ESCALATE."""
    decision = _decide((), "PASS", model_decided=True, lone_model_blocker="escalate")
    assert decision.workflow_verdict == "PASS" and decision.route == "receipt"


@pytest.mark.parametrize("verdict", ["ESCALATE", "DCL_ONLY"])
def test_an_unstarted_scope_never_yields_the_receipt_route(verdict):
    """Mutation: make the rationale ignore scope_started — "nothing was
    audited" disappears from the sentence."""
    decision = _decide((), verdict, integrity="NOTHING_AUDITED", scope_started=False)
    assert decision.route != "receipt"
    assert "nothing was audited" in decision.rationale[0].lower()


def test_an_unstarted_scope_under_a_provider_failure_says_both_plainly():
    """The ladder keeps the earlier integrity (PROVIDER_FAILURE) for an
    unstarted scope; the sentence must not then claim NOTHING_AUDITED was
    recorded. Mutation: hard-code the scope sentence's second half — the
    'could not run' clause disappears."""
    decision = _decide((), "ESCALATE", integrity="PROVIDER_FAILURE", scope_started=False)
    text = " ".join(decision.rationale)
    assert "nothing was audited" in text.lower()
    assert "the model audit could not run" in text.lower()


_ALL_CAPS = re.compile(r"\b[A-Z][A-Z_]{2,}\b")


@pytest.mark.parametrize("integrity", ["OK", "NOTHING_AUDITED", "BOUNDS_EXCEEDED",
                                       "INVALID_REPLY", "PROVIDER_FAILURE",
                                       "NON_EVIDENTIAL_PROVIDER", "SOMETHING_NEW"])
@pytest.mark.parametrize("verdict", ["PASS", "BLOCKED", "ESCALATE", "DCL_ONLY"])
@pytest.mark.parametrize("flags", [dict(), dict(escalation_lock=True),
                                   dict(scope_started=False),
                                   dict(model_decided=True, lone_model_blocker="escalate")])
def test_no_rationale_carries_an_integrity_code(integrity, verdict, flags):
    """Review B defect 5: the terminal prints rationale[0]. Mutation: put the
    integrity code back into any sentence — red for that cell. An unknown
    code falls back to plain words rather than being echoed."""
    for records in ((), _records(DCL_BLOCKER, MODEL_BLOCKED)):
        decision = _decide(records, verdict, integrity=integrity, **flags)
        assert decision.rationale
        for sentence in decision.rationale:
            assert _ALL_CAPS.search(sentence) is None, sentence
            assert "SOMETHING_NEW" not in sentence
        if integrity != "OK":
            assert len(decision.rationale) >= 1


def test_the_lock_is_named_and_outranks_everything():
    decision = _decide(_records(DCL_BLOCKER, None), "ESCALATE", escalation_lock=True)
    assert decision.route == "human-decision"
    assert "lock" in decision.rationale[0]


def test_unknown_dial_and_verdict_are_refused():
    with pytest.raises(ValueError):
        _decide((), "BLOCKED", lone_model_blocker="maybe")
    with pytest.raises(ValueError):
        _decide((), "PASSED")


# ------------------------------------------------------------ validate_block
def test_decision_id_binds_every_field_outside_the_evidence():
    """Review B defect 2: moving an id between partitions, rewriting the
    rationale, flipping the dial and smuggling a key all left a receipt that
    verified. Mutation: skip the decision_id re-derivation — every cell but
    the unknown-key one goes green."""
    good = _decide(_records({"findings": [], "total_hard_failures": 0},
                            MODEL_BLOCKED), "BLOCKED", model_decided=True).as_dict()
    assert validate_block(good) == []
    tampers = {
        "advisory id moved to blocking": lambda b: (
            b["blocking_evidence_ids"].append(b["advisory_evidence_ids"].pop())),
        "advisory id moved to contested": lambda b: (
            b["contested_evidence_ids"].append(b["advisory_evidence_ids"].pop())),
        "rationale rewritten": lambda b: b.__setitem__(
            "rationale", ["Everything is fine, trust me."]),
        "dial flipped": lambda b: b.__setitem__("lone_model_blocker", "escalate"),
        "decision id replaced": lambda b: b.__setitem__(
            "decision_id", "authority-0000000000000000"),
    }
    for name, tamper in tampers.items():
        block = json.loads(json.dumps(good))
        tamper(block)
        errors = validate_block(block)
        assert any("decision_id does not re-derive" in e for e in errors), (name, errors)
    block = json.loads(json.dumps(good))
    block["note"] = "smuggled"
    assert any("unknown keys ['note']" in e for e in validate_block(block))
    block = json.loads(json.dumps(good))
    block["advisory_evidence_ids"] *= 2
    assert any("repeats an id" in e for e in validate_block(block))


def test_two_identical_findings_are_two_records():
    """Review B defect 7. Mutation: drop the ordinal from the id payload — the
    two ids collide and validate_block reports them as not unique."""
    twice = {"verdict": "BLOCKED", "sections_applied": ["CA-DATA-001"],
             "findings": [MODEL_BLOCKED["findings"][0], MODEL_BLOCKED["findings"][0]]}
    records = _records({"findings": [], "total_hard_failures": 0}, twice)
    assert len({r.evidence_id for r in records}) == 2
    block = _decide(records, "BLOCKED", model_decided=True).as_dict()
    assert validate_block(block) == []
    block["evidence"][1] = dict(block["evidence"][0])
    assert any("not unique" in e for e in validate_block(block))


def test_a_claim_is_bounded_and_the_full_text_is_hashed():
    """Review B defect 6: a 3 MB observation was copied into the receipt.
    Mutation: store the observation unbounded — the length assertion fails."""
    long_text = "x" * (CLAIM_CHARS * 8)
    reply = {"verdict": "BLOCKED", "sections_applied": ["CA-DATA-001"],
             "findings": [dict(MODEL_BLOCKED["findings"][0], observation=long_text)]}
    (record,) = _records({"findings": [], "total_hard_failures": 0}, reply)
    assert len(record.claim) == CLAIM_CHARS
    assert record.claim_sha256 == hashlib.sha256(long_text.encode()).hexdigest()


def test_authority_evidence_digest_detects_mutation():
    """Mutation: skip the digest comparison — the edited claim validates."""
    block = _decide(_records(DCL_BLOCKER, MODEL_BLOCKED), "BLOCKED").as_dict()
    assert validate_block(block) == []
    block["evidence"][1]["claim"] = "changed after the decision"
    assert any("digest does not match" in e for e in validate_block(block))


def test_unknown_policy_version_is_rejected_by_name():
    """Mutation: compare against POLICY_VERSION with `!=` and drop the set —
    a future v2 verifier would refuse every v1 receipt instead of knowing it."""
    block = _decide((), "PASS").as_dict()
    block["policy_version"] = "crossaudit-evidence-authority-v9"
    errors = validate_block(block)
    assert any("v9" in e and "not one this verifier knows" in e for e in errors)
    assert POLICY_VERSION in KNOWN_POLICY_VERSIONS


def test_ids_must_be_within_the_evidence():
    """Mutation: drop the subset check — a block can name an id it never
    carried and the digest cannot see it."""
    block = _decide(_records(DCL_BLOCKER, None), "BLOCKED").as_dict()
    block["blocking_evidence_ids"] = ["ev-0000000000000000"]
    assert any("names evidence not in the block" in e for e in validate_block(block))


def test_route_must_follow_from_the_verdict():
    block = _decide((), "PASS").as_dict()
    block["route"] = "human-decision"
    errors = validate_block(block)
    assert any("does not follow from verdict" in e for e in errors)
    assert any("requires_human" in e for e in errors)


def test_missing_keys_are_named():
    block = _decide((), "PASS").as_dict()
    del block["contested_evidence_ids"]
    assert validate_block(block) == ["authority block is missing ['contested_evidence_ids']"]


# ------------------------------------------------------------- real runs
def _audit(cfg, sha, transcripts, reply=None, **kw):
    if reply is not None:
        record_reply(transcripts, cfg, sha, reply)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    kw.setdefault("escalation_lock", bool(cycle.get("blocked_by_escalation")))
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                        notes=notes, constitution=const, constitution_commit=cc, **kw)
    return outcome, cycle, store


def _escalate_dial(science):
    yml = science / "crossaudit.yml"
    yml.write_text(yml.read_text() + "authority:\n  lone_model_blocker: escalate\n")
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "escalate dial", cwd=science)
    return load(yml)


def test_escalation_lock_with_a_dcl_hard_failure_still_escalates(science, cfg, transcripts):
    """The lock is first (D148). Mutation: reorder the ladder so the DCL branch
    precedes `if escalation_lock:` — this reads BLOCKED."""
    sha = write_increment(science, BAD_RESULTS, "Bad.", "defective")
    outcome, _c, _s = _audit(cfg, sha, transcripts, escalation_lock=True, offline=True)
    assert outcome.dcl["total_hard_failures"] >= 1
    assert outcome.verdict == "ESCALATE"
    assert outcome.authority["route"] == "human-decision"
    assert "lock" in outcome.authority["rationale"][0]


def test_an_empty_scope_with_a_model_pass_is_nothing_audited(science, cfg, transcripts):
    """The real run, not the source text. Mutation: delete the scope_started
    branch from the ladder — this reaches PASS."""
    from crossaudit.auditor import prompt as pm
    from crossaudit.dcl import run_checks
    from crossaudit.providers import replay

    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    dcl = run_checks({}, cfg.checks, []).as_dict()
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    prompt, _b, _s = pm.build(const, cc, dcl, {})
    replay.record(transcripts, system=pm.SYSTEM, prompt=prompt, text=json.dumps(PASS_REPLY))
    outcome = run_audit(cfg=cfg, sha=sha, round_=1, files={}, notes=[],
                        constitution=const, constitution_commit=cc)
    assert outcome.model_reply is not None and outcome.model_reply["verdict"] == "PASS"
    assert outcome.verdict != "PASS"
    assert outcome.integrity == "NOTHING_AUDITED"
    assert outcome.authority["route"] != "receipt"


def test_default_run_keeps_a_model_blocker_in_bounded_revision(science, cfg, transcripts):
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, _c, _s = _audit(cfg, sha, transcripts, MODEL_BLOCKED)
    assert outcome.verdict == "BLOCKED"
    assert outcome.authority["route"] == "bounded-revision"
    assert outcome.authority["lone_model_blocker"] == "block"
    assert outcome.authority["contested_evidence_ids"] == []


def test_escalate_dial_run_routes_a_model_blocker_to_a_person(science, cfg, transcripts):
    """Mutation: ignore cfg.authority in run_audit — this reads BLOCKED."""
    cfg = _escalate_dial(science)
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, _c, _s = _audit(cfg, sha, transcripts, MODEL_BLOCKED)
    assert outcome.dcl["total_hard_failures"] == 0
    assert outcome.verdict == "ESCALATE"
    assert outcome.authority["route"] == "human-decision"
    assert len(outcome.authority["contested_evidence_ids"]) == 1
    assert "| verdict | **ESCALATE** |" in outcome.report
    assert "| evidence route | **your decision** |" in outcome.report


def test_the_escalate_dial_stop_reason_is_one_plain_sentence(science, cfg, transcripts):
    from crossaudit.cli.main import _provider_stop_kind, _provider_stop_reason
    from crossaudit.errors import classify_escalation_kind

    cfg = _escalate_dial(science)
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, _c, _s = _audit(cfg, sha, transcripts, MODEL_BLOCKED)
    reason = _provider_stop_reason(outcome)
    assert reason == ("the auditor raised a concern that no deterministic check "
                      "reproduces; it needs your judgment")
    assert classify_escalation_kind(reason) == "audit"
    assert _provider_stop_kind(outcome) == ""
    for word in ("alleged", "confirmed", "human-decision", "ev-"):
        assert word not in reason


def test_the_cli_escalated_line_is_plain_words(science, cfg, transcripts, monkeypatch, capsys):
    """cmd_run prints rationale[0] after `Escalated:`. Mutation: put the
    integrity code back into the bounded/invalid sentence — the all-caps
    check reddens."""
    from types import SimpleNamespace

    from crossaudit.cli.main import cmd_run

    cfg = _escalate_dial(science)
    monkeypatch.chdir(science)
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    record_reply(transcripts, cfg, sha, MODEL_BLOCKED)
    cmd_run(SimpleNamespace(sha=sha, json=False, allow_custom_endpoint=False,
                            continue_cycle=None))
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if "Escalated:" in l)
    assert "model reading" in line
    assert _ALL_CAPS.search(line.split("Escalated:", 1)[1]) is None, line


def test_config_rejects_an_unknown_dial(science):
    yml = science / "crossaudit.yml"
    yml.write_text(yml.read_text() + "authority:\n  lone_model_blocker: maybe\n")
    with pytest.raises(ConfigDenial, match="lone_model_blocker"):
        load(yml)


# -------------------------------------------------------- report rendering
def test_report_carries_the_route_in_plain_words_and_an_evidence_section(
        science, cfg, transcripts):
    """Review B item 9: the policy version stays in the receipt; the route row
    says what happens next in words verify() can map back. Mutation: print the
    route name — the label assertion and ROUTE_FROM_LABEL both fail."""
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, _c, _s = _audit(cfg, sha, transcripts, MODEL_BLOCKED)
    report = outcome.report
    assert "evidence policy" not in report and POLICY_VERSION not in report
    assert "| evidence route | **another revision round** |" in report
    assert "bounded-revision" not in report
    assert "## Evidence" in report
    assert "| finding | artifact | tier | verified by a check |" in report
    assert outcome.authority["rationale"][0] in report
    assert "| CA-DATA-001 | experiments/demo/SUMMARY.md | model | no |" in report
    for word in (ALLEGED, CONFIRMED):
        assert f'"{word}"' not in report and f" {word} " not in report
    assert set(ROUTE_FROM_LABEL.values()) == set(ROUTE_LABELS)


def test_a_dcl_only_report_says_the_model_audit_is_missing_once(science, cfg, transcripts):
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, _c, _s = _audit(cfg, sha, transcripts, offline=True)
    assert outcome.verdict == "DCL_ONLY"
    assert outcome.report.count("No model audit ran") == 1
    assert "| evidence route | **a model audit is still needed** |" in outcome.report


# ------------------------------------------------------- receipt round trip
def _receipt_for(cfg, sha, cycle, outcome, **extra):
    files, _ = materialise(cfg.root, sha, "experiments")
    manifest = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    ledger = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "report.md").write_text(outcome.report)
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    _sha, tree = resolve(cfg.root, sha)
    from crossaudit.auditor import dcl_source_digest
    return build(cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "experiments"},
                 cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
                 constitution_bytes=(cfg.root / cfg.constitution).read_bytes(),
                 constitution_commit=cc, dcl_source_sha256=dcl_source_digest(),
                 prompt_sha256=outcome.prompt_sha256, checks=cfg.checks,
                 verdict=outcome.verdict, exchange=outcome.exchange, retention="sealed",
                 report_bytes=(ledger / "report.md").read_bytes(), report_commit="",
                 cycle_path=str(ledger.relative_to(cfg.root)),
                 audit_repo=cfg.audit_repo or "local", mode="local",
                 integrity=outcome.integrity, **extra), ledger


def _verify(receipt, science, cfg, sha):
    return verify(receipt, science_root=science, audit_root=science,
                  expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_a_receipt_with_authority_verifies_and_a_tampered_claim_is_refused(
        science, cfg, transcripts, monkeypatch):
    """Mutation: drop validate_block from verify() — the tampered receipt
    verifies because the route row still matches."""
    monkeypatch.setattr("crossaudit.auditor.run.NON_EVIDENTIAL", frozenset())
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, store = _audit(cfg, sha, transcripts, PASS_REPLY)
    receipt, _l = _receipt_for(cfg, sha, cycle, outcome, authority=outcome.authority)
    assert receipt["authority"]["route"] == "receipt"
    validate(json.loads(json.dumps(receipt)))
    evidence = _verify(receipt, science, cfg, sha)
    assert evidence["verified"] and evidence["admission_ready"]

    tampered = json.loads(json.dumps(receipt))
    tampered["authority"]["evidence"] = [dict(finding_key="CA-X@y", severity="ADVISORY",
                                              tier="model", state=ALLEGED, claim="x",
                                              artifact="y", producer="p",
                                              producer_digest="q",
                                              evidence_id="ev-0000000000000001")]
    tampered["authority"]["advisory_evidence_ids"] = ["ev-0000000000000001"]
    with pytest.raises(IntegrityDenial, match="digest does not match"):
        validate(tampered)
    with pytest.raises(IntegrityDenial, match="digest does not match"):
        _verify(tampered, science, cfg, sha)
    # admit() consumes verify()'s evidence, so a tampered receipt never reaches
    # it with evidence in hand; the route refusal in admit() is covered below.


def test_a_non_receipt_route_is_a_shortfall_and_admit_refuses(science, cfg, transcripts):
    """Mutation: drop the route shortfall in verify() — the shortfall line is
    missing. admit() refuses on the verdict; see the next test for why it has
    no route branch of its own."""
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, store = _audit(cfg, sha, transcripts, MODEL_BLOCKED)
    receipt, _l = _receipt_for(cfg, sha, cycle, outcome, authority=outcome.authority)
    evidence = _verify(receipt, science, cfg, sha)
    assert "evidence route is bounded-revision, not receipt" in evidence["admission_shortfalls"]
    with pytest.raises(IntegrityDenial, match="not PASS"):
        admit(receipt, store, evidence, cfg=cfg)


def test_the_block_verdict_is_bound_to_the_audit_verdict(science, cfg, transcripts, monkeypatch):
    """Review B defect 3 (and 4). An internally consistent BLOCKED block on a
    PASS receipt is refused by validate — which is also why admit() has no
    route branch: a validated receipt with a non-receipt route cannot carry a
    PASS verdict. Mutation M7: `if False:` around the schema binding — the
    doctored receipt validates and this goes red."""
    from crossaudit.auditor.authority import decide_authority, records_from_audit
    monkeypatch.setattr("crossaudit.auditor.run.NON_EVIDENTIAL", frozenset())
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, _s = _audit(cfg, sha, transcripts, PASS_REPLY)
    receipt, _l = _receipt_for(cfg, sha, cycle, outcome, authority=outcome.authority)
    assert receipt["audit"]["verdict"] == "PASS"
    doctored = decide_authority((), verdict="BLOCKED", integrity="OK",
                                escalation_lock=False, scope_started=True,
                                model_decided=True).as_dict()
    assert validate_block(doctored) == []
    receipt["authority"] = doctored
    with pytest.raises(IntegrityDenial, match="differs from audit verdict"):
        validate(json.loads(json.dumps(receipt)))
    # And the other way to reach a non-receipt route on a PASS verdict — a
    # PASS block whose route is edited — is refused by validate_block itself.
    receipt["authority"] = dict(outcome.authority, route="bounded-revision")
    with pytest.raises(IntegrityDenial, match="does not follow from verdict"):
        validate(json.loads(json.dumps(receipt)))


def test_verify_binds_the_route_row_of_the_report(science, cfg, transcripts, monkeypatch):
    """Mutation: remove the route-row regex from verify() — the edited report
    verifies."""
    monkeypatch.setattr("crossaudit.auditor.run.NON_EVIDENTIAL", frozenset())
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, _s = _audit(cfg, sha, transcripts, PASS_REPLY)
    receipt, ledger = _receipt_for(cfg, sha, cycle, outcome, authority=outcome.authority)
    report = (ledger / "report.md").read_text()
    edited = report.replace("| evidence route | **admission** |",
                            "| evidence route | **your decision** |")
    assert edited != report
    receipt["ledger"]["report_sha256"] = hashlib.sha256(edited.encode()).hexdigest()
    (ledger / "report.md").write_text(edited)
    with pytest.raises(IntegrityDenial, match="evidence route"):
        _verify(receipt, science, cfg, sha)


@pytest.mark.parametrize("absent", [None, {}])
def test_a_receipt_without_the_block_is_byte_identical_and_verifies(
        science, cfg, transcripts, monkeypatch, absent):
    """Absent ⇒ identical, for None AND for the dataclass default {} that a
    hand-built AuditOutcome carries. Mutation M11: `if authority is not None:`
    in build.py — the {} cell writes an empty block, the key set grows and
    validate refuses it."""
    monkeypatch.setattr("crossaudit.auditor.run.NON_EVIDENTIAL", frozenset())
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, _s = _audit(cfg, sha, transcripts, PASS_REPLY)
    without, _l = _receipt_for(cfg, sha, cycle, outcome, authority=absent)
    legacy, _l = _receipt_for(cfg, sha, cycle, outcome)
    assert canonical(without) == canonical(legacy)
    assert "authority" not in without
    assert set(without) == {"receipt_schema", "subject", "cycle", "inputs", "audit",
                            "ledger", "verifier", "isolation"}
    evidence = _verify(without, science, cfg, sha)
    assert evidence["verified"] and evidence["admission_ready"]


def test_a_hand_built_outcome_carries_no_block():
    from crossaudit.auditor import AuditOutcome
    outcome = AuditOutcome(verdict="BLOCKED", dcl={"total_hard_failures": 1, "findings": []},
                           model_reply=None, invalid_reason=None, integrity="OK",
                           exchange={"mode": "none"}, prompt_sha256="a" * 64,
                           report="# r\n")
    assert outcome.authority == {}


def test_the_evidence_record_is_frozen():
    record = _records(DCL_BLOCKER, None)[0]
    with pytest.raises(Exception):
        record.claim = "edited"  # type: ignore[misc]
    assert isinstance(record, EvidenceRecord)
