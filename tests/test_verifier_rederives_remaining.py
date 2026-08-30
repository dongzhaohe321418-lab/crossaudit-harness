"""D41 gaps #9 / #10 / #11 — the three receipt inputs the verifier never derived.

Every guard here names the production reader it protects and is demonstrated red
under a mutation that reverts exactly that reader (D63/D64). The two properties
that matter are held apart on purpose, because `9f54b81` traded one for the
other:

* a claim is derived from **the object the receipt cites**, never from the
  verifying host's working tree or its own installed source (D63);
* a divergence is **reported**, never raised as a denial — a verifier that
  denies honest, signed, controller-recorded history is worse than one that is
  too permissive (D63/F1).
"""
from __future__ import annotations

import hashlib
import importlib
import shutil
from pathlib import Path

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.controller import StateStore
from crossaudit.errors import ConfigDenial, Denial, IntegrityDenial
from crossaudit.gitio import entries as entries_fn
from crossaudit.gitio import materialise, parent
from crossaudit.gitio import read_blob as read_blob_fn
from crossaudit.gitio import resolve
from crossaudit.receipt import build

verify_mod = importlib.import_module("crossaudit.receipt.verify")

from .conftest import GOOD_RESULTS, git, write_increment

CHECKS_LINE = "checks: [schema, units, convergence, provenance]"
SKILL_A = "---\napplies_to: experiments/\n---\n\nState the units in every table.\n"
SKILL_B = "---\napplies_to: experiments/\n---\n\nState the units, and the error.\n"
SKILL_C = "---\n---\n\nOne claim per paragraph.\n"


def _mint(cfg, science, *, before_build=None):
    """Mint a receipt through the shipped writers, including `_skills_manifest`.

    `_mint` in test_receipt_tool_evidence never passes `skills=`, so every
    receipt in that file carries `inputs.skills == {}` and the skills claim is
    never exercised by a passing test. This one runs the real writer.
    """
    from crossaudit.cli.main import _skills_manifest

    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
    if before_build is not None:
        before_build()
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                        notes=notes, constitution=const, constitution_commit=cc,
                        offline=True)
    manifest = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
    ldir = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "report.md").write_text(outcome.report)
    _sha, tree = resolve(cfg.root, sha)
    receipt = build(
        cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "experiments"},
        cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
        constitution_bytes=(cfg.root / cfg.constitution).read_bytes(),
        constitution_commit=cc, dcl_source_sha256=dcl_source_digest(),
        prompt_sha256=outcome.prompt_sha256, checks=cfg.checks,
        skills=_skills_manifest(cfg),
        verdict=outcome.verdict, exchange=outcome.exchange, retention="sealed",
        report_bytes=(ldir / "report.md").read_bytes(), report_commit="",
        cycle_path=str(ldir.relative_to(cfg.root)),
        audit_repo=cfg.audit_repo or "local", mode="local",
        integrity=outcome.integrity)
    return sha, receipt


def _verify(cfg, science, sha, receipt, audit_root=None):
    return verify_mod.verify(receipt, science_root=science,
                             audit_root=audit_root or science,
                             expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def _row(evidence, claim):
    rows = {row["claim"]: row for row in evidence["input_derivations"]}
    return rows[claim]


def _verify_or_fail(cfg, science, sha, receipt, marker, audit_root=None):
    """Verification of an honest receipt that refuses is the S0, so a refusal
    fails by the guard's name rather than escaping as a bare exception."""
    try:
        return _verify(cfg, science, sha, receipt, audit_root=audit_root)
    except Denial as exc:
        pytest.fail(f"{marker}: verification refused this receipt — {exc}")


def _assert_status(evidence, claim, expected, marker):
    """Every failure carries the guard's name, so a reader of a red run knows
    which property broke without reconstructing the test."""
    actual = _row(evidence, claim)["status"]
    assert actual == expected, \
        f"{marker}: {claim} derived as {actual!r}, expected {expected!r}"


def _write_working_checks(science, value):
    path = science / "crossaudit.yml"
    path.write_text(path.read_text().replace(CHECKS_LINE, f"checks: {value}"))


def _skill(science, rel, text):
    path = science / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _body_digest(text: str) -> str:
    from crossaudit import skills as skills_mod
    return skills_mod._parse(text, "x", "x").digest


# --------------------------------------------------------------------------
# #10 — the configured check list
# --------------------------------------------------------------------------

def test_checks_are_rederived_from_the_cited_commit_not_the_working_tree(
        cfg, science, monkeypatch):
    """F2's false-verification half, executed.

    A forged `inputs.checks` that an attacker has made true by editing the
    UNCOMMITTED `crossaudit.yml` must still be reported as diverged: the
    committed configuration is the cited object, and the attacker never touched
    a commit.
    """
    sha, receipt = _mint(cfg, science)
    receipt["inputs"]["checks"] = ["schema"]
    _write_working_checks(science, "[schema]")

    evidence = _verify_or_fail(cfg, science, sha, receipt, "CHECKS_CITED_OBJECT_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "checks", "diverged", "CHECKS_CITED_OBJECT_GUARD")

    # Counterfactual: revert the reader to the working-tree read F2 condemned.
    monkeypatch.setattr(
        verify_mod, "_committed_config_bytes",
        lambda _root, _commit: (science / "crossaudit.yml").read_bytes())
    with pytest.raises(AssertionError, match="CHECKS_CITED_OBJECT_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "checks")["status"] == "diverged", \
            "CHECKS_CITED_OBJECT_GUARD"


def test_editing_the_working_config_does_not_invalidate_an_honest_receipt(
        cfg, science, monkeypatch):
    """F2's false-denial half. Editing your config must not retroactively
    invalidate a receipt the controller already recorded."""
    sha, receipt = _mint(cfg, science)
    _write_working_checks(science, "[schema]")

    evidence = _verify_or_fail(cfg, science, sha, receipt, "CHECKS_HONEST_HISTORY_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "checks", "corroborated", "CHECKS_HONEST_HISTORY_GUARD")

    monkeypatch.setattr(
        verify_mod, "_committed_config_bytes",
        lambda _root, _commit: (science / "crossaudit.yml").read_bytes())
    with pytest.raises(AssertionError, match="CHECKS_HONEST_HISTORY_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "checks")["status"] == "corroborated", \
            "CHECKS_HONEST_HISTORY_GUARD"


def test_the_check_selection_is_rerun_not_string_compared(cfg, science, monkeypatch):
    """`checks: general` in the commit must re-derive to the four concrete names
    the receipt records — the "re-run the selection" half of gap #10."""
    path = science / "crossaudit.yml"
    path.write_text(path.read_text().replace(CHECKS_LINE, "checks: general"))
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "profile by name", cwd=science)
    cfg = __import__("crossaudit.config", fromlist=["load"]).load(path)
    assert cfg.checks == ["parseable", "declared", "internal", "complete"]

    sha, receipt = _mint(cfg, science)
    evidence = _verify_or_fail(cfg, science, sha, receipt, "CHECKS_PROFILE_RESOLVED_GUARD")
    _assert_status(evidence, "checks", "corroborated", "CHECKS_PROFILE_RESOLVED_GUARD")

    # Counterfactual: compare the raw `checks:` value instead of resolving it.
    import yaml as _yaml
    monkeypatch.setattr(
        verify_mod, "_resolve_committed_checks",
        lambda raw: raw if isinstance(raw, list) else [raw])
    with pytest.raises(AssertionError, match="CHECKS_PROFILE_RESOLVED_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "checks")["status"] == "corroborated", \
            "CHECKS_PROFILE_RESOLVED_GUARD"
    assert _yaml is not None


def test_a_diverging_check_list_is_reported_and_never_denied(cfg, science, monkeypatch):
    sha, receipt = _mint(cfg, science)
    honest = _verify(cfg, science, sha, receipt)["admission_shortfalls"]

    receipt["inputs"]["checks"] = ["schema"]
    evidence = _verify_or_fail(cfg, science, sha, receipt, "CHECKS_DIVERGENCE_IS_NOT_A_DENIAL_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "checks", "diverged", "CHECKS_DIVERGENCE_IS_NOT_A_DENIAL_GUARD")
    assert evidence["admission_shortfalls"] == honest, \
        "a derivation must not change what admission refuses"

    # Counterfactual: 9f54b81's policy — raise IntegrityDenial on divergence.
    real = verify_mod._input_derivations

    def deny_on_divergence(*args, **kwargs):
        rows = real(*args, **kwargs)
        for row in rows:
            if row["status"] == "diverged":
                raise IntegrityDenial(row["detail"])
        return rows

    monkeypatch.setattr(verify_mod, "_input_derivations", deny_on_divergence)
    with pytest.raises(AssertionError, match="CHECKS_DIVERGENCE_IS_NOT_A_DENIAL_GUARD"):
        denied = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            denied = True
        assert not denied, "CHECKS_DIVERGENCE_IS_NOT_A_DENIAL_GUARD"


# --------------------------------------------------------------------------
# #11 — the skills manifest
# --------------------------------------------------------------------------

def test_a_committed_skill_minted_by_the_real_writer_corroborates(cfg, science):
    """The positive control the branch under audit never had: without it the
    whole skills block can be vacuous and every negative test still passes."""
    _skill(science, "skills/house.md", SKILL_A)
    sha, receipt = _mint(cfg, science)

    assert receipt["inputs"]["skills"] == {"skills/house.md": _body_digest(SKILL_A)}, \
        "the shipped writer must actually have recorded a skill"
    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_POSITIVE_CONTROL")
    assert evidence["verified"] is True
    _assert_status(evidence, "skills", "corroborated", "SKILLS_POSITIVE_CONTROL")


def test_skills_are_rederived_from_the_cited_commit_not_the_working_directory(
        cfg, science, monkeypatch):
    """The mutation nothing in the 1,742-test suite detected (F5/M6): revert the
    skills reader to a working-directory read and the guard must go red."""
    from crossaudit.cli.main import _skills_manifest

    _skill(science, "skills/house.md", SKILL_A)
    sha, receipt = _mint(cfg, science)

    _skill(science, "skills/house.md", SKILL_B)          # edited, never committed
    receipt["inputs"]["skills"] = {"skills/house.md": _body_digest(SKILL_B)}

    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_CITED_OBJECT_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "skills", "diverged", "SKILLS_CITED_OBJECT_GUARD")

    monkeypatch.setattr(
        verify_mod, "_committed_skills",
        lambda _root, _commit: {rel: (d, d)
                                for rel, d in _skills_manifest(cfg).items()})
    with pytest.raises(AssertionError, match="SKILLS_CITED_OBJECT_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "skills")["status"] == "diverged", \
            "SKILLS_CITED_OBJECT_GUARD"


def test_an_underdeclared_skill_is_caught_by_rederiving_the_whole_manifest(
        cfg, science, monkeypatch):
    """F4/test_S2: two skills in force, one dropped from the receipt. A subset
    check over the declared entries can never see this."""
    _skill(science, "skills/house.md", SKILL_A)
    _skill(science, "skills/style.md", SKILL_C)
    sha, receipt = _mint(cfg, science)
    assert len(receipt["inputs"]["skills"]) == 2
    receipt["inputs"]["skills"].pop("skills/style.md")

    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_WHOLE_MANIFEST_GUARD")
    _assert_status(evidence, "skills", "diverged", "SKILLS_WHOLE_MANIFEST_GUARD")

    real = verify_mod._committed_skills
    monkeypatch.setattr(
        verify_mod, "_committed_skills",
        lambda root, commit: {k: v for k, v in (real(root, commit) or {}).items()
                              if k in receipt["inputs"]["skills"]})
    with pytest.raises(AssertionError, match="SKILLS_WHOLE_MANIFEST_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "skills")["status"] == "diverged", \
            "SKILLS_WHOLE_MANIFEST_GUARD"


def test_an_empty_skills_claim_is_not_free_when_a_skill_is_in_force(
        cfg, science, monkeypatch):
    """F4/test_S3: `if declared:` skipped the whole block, so claiming no
    guidance at all was the cheapest forgery available."""
    _skill(science, "skills/house.md", SKILL_A)
    sha, receipt = _mint(cfg, science)
    receipt["inputs"]["skills"] = {}

    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_EMPTY_CLAIM_GUARD")
    _assert_status(evidence, "skills", "diverged", "SKILLS_EMPTY_CLAIM_GUARD")

    real = verify_mod._committed_skills
    monkeypatch.setattr(
        verify_mod, "_committed_skills",
        lambda root, commit: {k: v for k, v in (real(root, commit) or {}).items()
                              if k in receipt["inputs"]["skills"]})
    with pytest.raises(AssertionError, match="SKILLS_EMPTY_CLAIM_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        assert _row(reverted, "skills")["status"] == "diverged", \
            "SKILLS_EMPTY_CLAIM_GUARD"


def test_a_skill_added_after_the_audited_commit_is_reported_not_denied(
        cfg, science, monkeypatch):
    """F3, driven through the real writer. The shipped `_skills_manifest` reads
    the working directory, so a skill created after the audited commit is
    genuinely recorded in an honest receipt. Denying it rejects what the product
    itself mints — the default path for anyone iterating on house guidance."""
    sha, receipt = _mint(
        cfg, science, before_build=lambda: _skill(science, "skills/late.md", SKILL_A))

    assert receipt["inputs"]["skills"] == {"skills/late.md": _body_digest(SKILL_A)}
    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_LATE_ADDITION_IS_NOT_A_DENIAL_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "skills", "diverged", "SKILLS_LATE_ADDITION_IS_NOT_A_DENIAL_GUARD")

    real = verify_mod._input_derivations

    def deny_on_divergence(*args, **kwargs):
        rows = real(*args, **kwargs)
        for row in rows:
            if row["status"] == "diverged":
                raise IntegrityDenial(row["detail"])
        return rows

    monkeypatch.setattr(verify_mod, "_input_derivations", deny_on_divergence)
    with pytest.raises(AssertionError, match="SKILLS_LATE_ADDITION_IS_NOT_A_DENIAL_GUARD"):
        denied = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            denied = True
        assert not denied, "SKILLS_LATE_ADDITION_IS_NOT_A_DENIAL_GUARD"


# --------------------------------------------------------------------------
# #9 — the deterministic-layer source digest
# --------------------------------------------------------------------------

def test_the_check_layer_digest_is_reported_against_this_installation_never_denied(
        cfg, science, monkeypatch):
    """F1, the S0. `dcl_source_sha256` hashes the check layer of the process
    that minted the receipt; no committed object pins it, so comparing it to the
    verifying host is an identity claim, not a re-derivation. It is labelled as
    such and it never denies."""
    sha, receipt = _mint(cfg, science)
    honest = _verify_or_fail(cfg, science, sha, receipt, "DCL_DIGEST_IS_NOT_A_DENIAL_GUARD")
    _assert_status(honest, "dcl_source_sha256", "local-match", "DCL_DIGEST_IS_NOT_A_DENIAL_GUARD")

    # F7: the three claims are derived from the receipt and the repository
    # only, so a library caller passing no Config gets the same rows rather
    # than two integrity bindings silently skipped. (Executed both ways; there
    # is no cfg-gated branch to revert, so this carries no mutation.)
    without_cfg = verify_mod.verify(receipt, science_root=science,
                                    audit_root=science,
                                    expect_repo=cfg.science_repo,
                                    expect_sha=sha, cfg=None)
    assert without_cfg["input_derivations"] == honest["input_derivations"]

    receipt["inputs"]["dcl_source_sha256"] = "f" * 64
    evidence = _verify_or_fail(cfg, science, sha, receipt, "DCL_DIGEST_IS_NOT_A_DENIAL_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "dcl_source_sha256", "local-differs", "DCL_DIGEST_IS_NOT_A_DENIAL_GUARD")
    assert evidence["admission_shortfalls"] == honest["admission_shortfalls"]

    real = verify_mod._input_derivations

    def deny_on_mismatch(*args, **kwargs):
        rows = real(*args, **kwargs)
        for row in rows:
            if row["status"] == "local-differs":
                raise IntegrityDenial("deterministic-layer source digest mismatch")
        return rows

    monkeypatch.setattr(verify_mod, "_input_derivations", deny_on_mismatch)
    with pytest.raises(AssertionError, match="DCL_DIGEST_IS_NOT_A_DENIAL_GUARD"):
        denied = False
        try:
            _verify(cfg, science, sha, receipt)
        except IntegrityDenial:
            denied = True
        assert not denied, "DCL_DIGEST_IS_NOT_A_DENIAL_GUARD"


def test_an_unavailable_check_layer_identity_is_reported_not_raised(
        cfg, science, monkeypatch):
    """A frozen build missing `crossaudit-build.json` makes `dcl_source_digest()`
    raise ConfigDenial. A config error must never reach a person from inside an
    integrity read."""
    sha, receipt = _mint(cfg, science)

    def unavailable():
        raise ConfigDenial("the frozen application is missing its identity")

    monkeypatch.setattr("crossaudit.auditor.run.dcl_source_digest", unavailable)
    evidence = _verify_or_fail(cfg, science, sha, receipt, "DCL_UNAVAILABLE_IS_NOT_AN_ERROR_GUARD")
    assert evidence["verified"] is True
    _assert_status(evidence, "dcl_source_sha256", "not-derivable", "DCL_UNAVAILABLE_IS_NOT_AN_ERROR_GUARD")

    monkeypatch.setattr(verify_mod, "_local_dcl_source_digest", unavailable)
    with pytest.raises(AssertionError, match="DCL_UNAVAILABLE_IS_NOT_AN_ERROR_GUARD"):
        raised = False
        try:
            _verify(cfg, science, sha, receipt)
        except Denial:
            raised = True
        assert not raised, "DCL_UNAVAILABLE_IS_NOT_AN_ERROR_GUARD"


# --------------------------------------------------------------------------
# F6 — the cited commit is resolved in the repository that holds it
# --------------------------------------------------------------------------

def test_a_separate_audit_repo_reports_not_derivable_rather_than_a_git_error(
        cfg, science, tmp_path, monkeypatch):
    """F6: the subject sha is verified to exist in the SCIENCE repo and was then
    looked up in the AUDIT repo, reaching the person as
    `ConfigDenial: git ls-tree failed: fatal: not a tree object`."""
    sha, receipt = _mint(cfg, science)

    audit = tmp_path / "audit"
    audit.mkdir()
    git("init", "-q", "-b", "main", cwd=audit)
    git("config", "user.email", "lab@example.invalid", cwd=audit)
    git("config", "user.name", "Lab", cwd=audit)
    shutil.copy(science / cfg.constitution, audit / cfg.constitution)
    shutil.copytree(science / receipt["ledger"]["cycle_path"],
                    audit / receipt["ledger"]["cycle_path"])
    git("add", "-A", cwd=audit)
    git("commit", "-q", "-m", "audit repo", cwd=audit)
    receipt["inputs"]["constitution_commit"] = git("rev-parse", "HEAD", cwd=audit)

    evidence = _verify_or_fail(cfg, science, sha, receipt, "SEPARATE_AUDIT_REPO_GUARD", audit_root=audit)
    assert evidence["verified"] is True
    for claim in ("checks", "skills"):
        assert _row(evidence, claim)["status"] == "not-derivable"
        # The reported source is a claim about which object was consulted; it
        # must not name one this repository does not have.
        assert _row(evidence, claim)["source"] == "none", \
            f"SEPARATE_AUDIT_REPO_GUARD: {claim} names an object this repo lacks"
    assert not [row for row in evidence["input_derivations"]
                if "fatal:" in row["detail"] or "ls-tree" in row["detail"]]

    # Counterfactual: reuse the science sha in the audit repo unconditionally —
    # `entries(audit_root, subject_sha)` with no existence test, which is how a
    # raw `git ls-tree failed: fatal: not a tree object` reached the person.
    monkeypatch.setattr(verify_mod, "_cited_audit_commit",
                        lambda receipt, _root: receipt["subject"]["sha"])
    with pytest.raises(AssertionError, match="SEPARATE_AUDIT_REPO_GUARD"):
        reverted = _verify(cfg, science, sha, receipt, audit_root=audit)
        assert _row(reverted, "checks")["source"] == "none", \
            "SEPARATE_AUDIT_REPO_GUARD"
        assert not [row for row in reverted["input_derivations"]
                    if "fatal:" in row["detail"]], "SEPARATE_AUDIT_REPO_GUARD"


# --------------------------------------------------------------------------
# The person is told (D66 — execute the change against the reported symptom)
# --------------------------------------------------------------------------

def test_crossaudit_verify_tells_a_person_what_was_and_was_not_derived(
        cfg, science, monkeypatch, capsys):
    """A derivation nobody is shown changes nothing about the reported symptom.
    Driven through the real `cmd_verify`, over the rendered output."""
    import json as _json
    from types import SimpleNamespace

    from crossaudit.cli import main as cli_main

    _skill(science, "skills/house.md", SKILL_A)
    sha, receipt = _mint(cfg, science)
    receipt_path = science / receipt["ledger"]["cycle_path"] / "receipt.json"
    receipt_path.write_text(_json.dumps(receipt))
    monkeypatch.chdir(science)

    args = SimpleNamespace(receipt=str(receipt_path), science_root=None,
                           audit_root=None, expect_repo=None, expect_sha=None,
                           admit=False, json=False)
    assert cli_main.cmd_verify(args) == 0
    text = capsys.readouterr().out

    for expected in ("DERIVED  checks:", "DERIVED  skills:",
                     "SAME CHECK LAYER  dcl_source_sha256:"):
        assert expected in text, f"RENDERED_DERIVATION_GUARD: {expected!r} absent"
    # The check-layer row must not be worded as a re-derivation of the receipt.
    assert "not a re-derivation" in text

    # Counterfactual: the renderer ignores the field the verifier returned.
    monkeypatch.setattr(cli_main, "_derivation_lines", lambda _evidence: "")
    with pytest.raises(AssertionError, match="RENDERED_DERIVATION_GUARD"):
        assert cli_main.cmd_verify(args) == 0
        shown = capsys.readouterr().out
        assert "DERIVED  checks:" in shown, "RENDERED_DERIVATION_GUARD"


def test_the_check_comparison_is_ordered_and_says_so(cfg, science, monkeypatch):
    """F9: an ordered comparison is stricter than `cfg.checks` semantics
    require, so the choice is pinned rather than left to whoever reads it next.
    A reordered committed list is a different configuration text and is
    reported as a divergence."""
    sha, receipt = _mint(cfg, science)
    receipt["inputs"]["checks"] = list(reversed(receipt["inputs"]["checks"]))

    evidence = _verify_or_fail(cfg, science, sha, receipt,
                               "CHECKS_ORDERED_COMPARISON_GUARD")
    _assert_status(evidence, "checks", "diverged", "CHECKS_ORDERED_COMPARISON_GUARD")

    # Counterfactual: compare the two selections as sets.
    monkeypatch.setattr(verify_mod, "_checks_match",
                        lambda declared, derived: sorted(declared) == sorted(derived))
    with pytest.raises(AssertionError, match="CHECKS_ORDERED_COMPARISON_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        _assert_status(reverted, "checks", "diverged",
                       "CHECKS_ORDERED_COMPARISON_GUARD")


def test_an_oversize_committed_skill_is_refused_by_both_halves(
        cfg, science, monkeypatch):
    """F9/M7: the verifier's read bound and the writer's limit are the same
    number, and neither side may quietly hash a truncated skill."""
    from crossaudit import skills as skills_mod

    # The accept side of the same boundary, so the pair is swept rather than
    # sampled: exactly MAX_SKILL_BYTES is accepted by the writer AND re-derives.
    _skill(science, "skills/exact.md", "x" * skills_mod.MAX_SKILL_BYTES)
    at_limit_sha, at_limit = _mint(cfg, science)
    assert list(at_limit["inputs"]["skills"]) == ["skills/exact.md"], \
        "SKILLS_OVERSIZE_GUARD: the writer refused a skill exactly at the limit"
    _assert_status(
        _verify_or_fail(cfg, science, at_limit_sha, at_limit, "SKILLS_OVERSIZE_GUARD"),
        "skills", "corroborated", "SKILLS_OVERSIZE_GUARD")
    (science / "skills" / "exact.md").unlink()

    body = "x" * (skills_mod.MAX_SKILL_BYTES + 1)
    _skill(science, "skills/huge.md", body)
    sha, receipt = _mint(cfg, science)

    # The shipped writer refuses it, so the receipt records no skills at all.
    assert receipt["inputs"]["skills"] == {}, \
        "SKILLS_OVERSIZE_GUARD: the writer accepted an oversize skill"

    evidence = _verify_or_fail(cfg, science, sha, receipt, "SKILLS_OVERSIZE_GUARD")
    _assert_status(evidence, "skills", "not-derivable", "SKILLS_OVERSIZE_GUARD")
    assert str(skills_mod.MAX_SKILL_BYTES) in _row(evidence, "skills")["detail"]

    # Counterfactual: drop the size refusal and the verifier derives a skill
    # the shipped disk writer refuses to mint. The tree read now goes through
    # `gitio.materialise`, whose bound is `blob_limit` (512 KiB) rather than
    # MAX_SKILL_BYTES, so this refusal is the only thing keeping the verifier
    # inside the writer's own limit.
    monkeypatch.setattr(verify_mod, "_refuse_oversize_skill",
                        lambda path, data, total, skills_mod: None)
    with pytest.raises(AssertionError, match="SKILLS_OVERSIZE_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        _assert_status(reverted, "skills", "not-derivable", "SKILLS_OVERSIZE_GUARD")


def test_both_shipped_skill_digest_conventions_corroborate_and_are_named(
        cfg, science, monkeypatch):
    """The product ships two `_skills_manifest` paths that hash the SAME
    committed skill differently — `skills.manifest`'s parsed body on the disk
    path, `sha256` of the raw blob on the subject-commit path — and the receipt
    records no marker saying which one minted it. Executed at the integration
    tip, on one file, they are `fb0a0761…` and `42a6d019…`.

    A verifier that knew only one convention would report half the product's own
    honest receipts as diverged. Both corroborate, and the row says which."""
    _skill(science, "skills/house.md", SKILL_A)
    sha, receipt = _mint(cfg, science)

    # Convention 1 — the parsed body, as the disk writer mints it.
    parsed = _verify_or_fail(cfg, science, sha, receipt,
                             "SKILLS_WRITER_CONVENTION_GUARD")
    _assert_status(parsed, "skills", "corroborated",
                   "SKILLS_WRITER_CONVENTION_GUARD")
    assert "parsed skill body" in _row(parsed, "skills")["detail"], \
        "SKILLS_WRITER_CONVENTION_GUARD: the row does not name the convention"

    # Convention 2 — sha256 of the committed blob, as the subject-commit writer
    # mints it. Derived from the committed object here, never transcribed.
    blob = {path: b for _mode, path, b in
            entries_fn(science, sha, prefix="skills/")}["skills/house.md"]
    data, _truncated = read_blob_fn(science, blob, limit=None)
    receipt["inputs"]["skills"] = {
        "skills/house.md": hashlib.sha256(data).hexdigest()}
    assert receipt["inputs"]["skills"] != {"skills/house.md": _body_digest(SKILL_A)}, \
        "SKILLS_WRITER_CONVENTION_GUARD: the two conventions must actually differ"

    bytes_conv = _verify_or_fail(cfg, science, sha, receipt,
                                 "SKILLS_WRITER_CONVENTION_GUARD")
    _assert_status(bytes_conv, "skills", "corroborated",
                   "SKILLS_WRITER_CONVENTION_GUARD")
    assert "committed file bytes" in _row(bytes_conv, "skills")["detail"], \
        "SKILLS_WRITER_CONVENTION_GUARD: the row does not name the convention"

    # Counterfactual: know only the parsed-body convention, as this branch did
    # before the subject-commit writer landed on integration.
    monkeypatch.setattr(
        verify_mod, "_skills_match",
        lambda declared, derived: (
            all(declared[p] == derived[p][0] for p in declared)
            and set(declared) == set(derived), "the parsed skill body"))
    with pytest.raises(AssertionError, match="SKILLS_WRITER_CONVENTION_GUARD"):
        reverted = _verify(cfg, science, sha, receipt)
        _assert_status(reverted, "skills", "corroborated",
                       "SKILLS_WRITER_CONVENTION_GUARD")


def test_these_guards_ran_against_the_tree_under_test():
    """A harness that resolves the product by PATH and never asserts its
    IDENTITY can measure an installed CrossAudit while naming a tree.

    This is not hypothetical here. The shared venv has CrossAudit installed, and
    the two resolutions disagree on a real receipt:

        PYTHONPATH=<this tree>/src  crossaudit verify …  -> BINDINGS VERIFIED
        (PYTHONPATH unset)          crossaudit verify …  -> DENIED (integrity)

    So every count and every verdict this file produces is meaningless until the
    tree that answered is asserted rather than assumed. Asserted here, once, by
    identity: the imported package must be the `src/crossaudit` that sits beside
    this `tests/` directory.
    """
    import crossaudit

    package = Path(crossaudit.__file__).resolve().parent
    tests_dir = Path(__file__).resolve().parent
    assert package.name == "crossaudit", \
        f"TREE_IDENTITY_GUARD: imported {package}"
    assert package.parent.parent == tests_dir.parent, (
        f"TREE_IDENTITY_GUARD: imported crossaudit from {package}, which is not "
        f"the src/crossaudit beside {tests_dir}")
