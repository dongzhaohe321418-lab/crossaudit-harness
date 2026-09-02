"""A project may choose to be advised rather than gated.

The product used to REFUSE an advisory-only constitution, on the premise that
"nothing can ever gate". The premise was false twice over, and refusing on it is
what taught every surface downstream that being valuable means being able to
stop someone.

The test this change rests on is not that the refusal is gone. It is that the
DETERMINISTIC FLOOR STILL BLOCKS when the constitution has no teeth — because if
widening this ever let a model waive a deterministic finding, that would be
worse than the defect being removed.
"""
from __future__ import annotations

import subprocess

from crossaudit.auditor import run_audit
from crossaudit.constitution import Draft
from crossaudit.controller import StateStore
from crossaudit.errors import ConfigDenial
from crossaudit.gitio import materialise, parent

from .conftest import BAD_RESULTS, GOOD_RESULTS, PASS_REPLY, record_reply, write_increment

ADVISORY_ONLY = {
    "project_summary": "A group that wants review, not a gate.",
    "domain": "research",
    "rules": [
        {"id": "CA-DATA-001", "severity": "ADVISORY", "title": "Results carry units",
         "criterion": "Every reported quantity states its unit.", "from_user": ""},
        {"id": "CA-METH-002", "severity": "ADVISORY", "title": "Method is described",
         "criterion": "Each result names the method that produced it.", "from_user": ""},
    ],
}


def _audit_with(cfg, science, transcripts, rules_text, results, reply):
    """One real audit round against a constitution this test supplies."""
    (science / cfg.constitution).write_text(rules_text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(science), check=True)
    subprocess.run(["git", "commit", "-qm", "constitution"], cwd=str(science), check=True)
    sha = write_increment(science, results, "All fine.", "increment")
    record_reply(transcripts, cfg, sha, reply)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    cc = subprocess.run(["git", "log", "-1", "--format=%H", "--", cfg.constitution],
                        cwd=str(science), capture_output=True, text=True,
                        check=False).stdout.strip()
    return run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files, notes=notes,
                     constitution=rules_text, constitution_commit=cc)


def test_an_advisory_only_constitution_is_accepted():
    """The symptom. Refusing this made 'advise, do not gate' unconfigurable."""
    try:
        draft = Draft.from_json(ADVISORY_ONLY)
    except ConfigDenial as exc:
        raise AssertionError(
            f"ADVISORY_ONLY_ACCEPTED_GUARD: a constitution of only ADVISORY rules "
            f"was refused: {exc}") from exc
    assert [r.severity for r in draft.rules] == ["ADVISORY", "ADVISORY"]


def test_the_deterministic_floor_still_blocks_without_any_blocker_rule(
        science, cfg, transcripts):
    """THE TEST THIS CHANGE RESTS ON.

    No rule in the constitution can gate, and the model says PASS. The
    deterministic layer must still block, because it computes its own verdict
    without consulting the constitution and `auditor/run.py` reads it before it
    reads the model at all.
    """
    rules = Draft.from_json(ADVISORY_ONLY).render("demo")
    outcome = _audit_with(cfg, science, transcripts, rules, BAD_RESULTS, PASS_REPLY)

    assert outcome.model_reply and outcome.model_reply["verdict"] == "PASS", (
        "DETERMINISTIC_FLOOR_GUARD: the model did not return PASS, so this run "
        "does not exercise a model opinion the floor has to override")
    assert outcome.dcl["total_hard_failures"] > 0, (
        "DETERMINISTIC_FLOOR_GUARD: no deterministic failure was produced, so "
        "there is nothing for the floor to hold against")
    assert outcome.verdict == "BLOCKED", (
        f"DETERMINISTIC_FLOOR_GUARD: with an advisory-only constitution and "
        f"{outcome.dcl['total_hard_failures']} deterministic hard failure(s), the "
        f"model's PASS produced {outcome.verdict!r}. A model waived the floor.")


def test_an_advisory_only_constitution_still_passes_clean_work(
        science, cfg, transcripts):
    """The other direction: advisory-only does not block everything either."""
    rules = Draft.from_json(ADVISORY_ONLY).render("demo")
    outcome = _audit_with(cfg, science, transcripts, rules, GOOD_RESULTS, PASS_REPLY)
    assert outcome.dcl["total_hard_failures"] == 0
    assert outcome.verdict == "PASS", (
        f"ADVISORY_ONLY_ACCEPTED_GUARD: clean work under an advisory-only "
        f"constitution produced {outcome.verdict!r}")


def test_a_constitution_with_blocker_rules_is_unchanged(science, cfg, transcripts):
    """This widens what is permitted and changes nothing for anyone who has
    already configured blocking rules."""
    with_blocker = dict(ADVISORY_ONLY)
    with_blocker["rules"] = [dict(ADVISORY_ONLY["rules"][0], severity="BLOCKER"),
                             ADVISORY_ONLY["rules"][1]]
    draft = Draft.from_json(with_blocker)
    assert [r.severity for r in draft.rules] == ["BLOCKER", "ADVISORY"]
    outcome = _audit_with(cfg, science, transcripts, draft.render("demo"),
                          BAD_RESULTS, PASS_REPLY)
    assert outcome.verdict == "BLOCKED"


def test_the_rendered_constitution_still_carries_the_universal_task_blocker():
    """Stated so 'advisory-only' is not overclaimed.

    `render()` unconditionally prepends CA-TASK-001, which is a BLOCKER, so the
    document a project actually commits always contains one. Removing the
    validate() refusal permits an advisory-only DRAFT; it does not make the
    shipped constitution free of BLOCKER rules, and the model can still return a
    BLOCKER for task noncompliance.
    """
    text = Draft.from_json(ADVISORY_ONLY).render("demo")
    assert "CA-TASK-001" in text
    assert "**BLOCKER.**" in text, (
        "UNIVERSAL_TASK_RULE_GUARD: CA-TASK-001 no longer renders as a BLOCKER; "
        "the note in constitution.validate() about why no warning was added is "
        "now stale and must be revisited")
