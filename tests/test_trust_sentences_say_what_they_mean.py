"""The five sentences a person is misled by if they soften.

These sentences ARE the product. The audit machinery exists to earn the right to
say them, and each one converts into a false assurance when its QUALIFYING
CLAUSE is dropped — not when the sentence disappears. A report described as
"not committed yet" without "so it cannot be verified yet" reads as a note about
housekeeping; with the clause it is a refusal to vouch. Same words, opposite
meaning.

WHY CLAUSES AND NOT STRINGS. A presence check passes on the weakened sentence,
because the weakened sentence still contains the string. Every guard here
asserts the clause that carries the caveat, and every one was shown red by
DELETING THAT CLAUSE while leaving the rest of the sentence in place. Deleting
the whole sentence is the easy mutation and it proves nothing: it is the state
we are not worried about.

CEILING, stated because it bounds all five. These assert the sentence at the
producer of record and, where the surface is the terminal, at the renderer a
person reads. For the two console sentences the page renders `report_note`
verbatim through `esc()` with no transformation, so this pins the words and NOT
that a browser painted them; that last hop has no home in this suite and is the
standing seam (D106). A guard that stops at the wire is worth having and is not
worth mistaking for one that does not.
"""
from __future__ import annotations

import argparse
import json

import pytest

from crossaudit import admission as adm
from crossaudit.cli import main
from crossaudit.console.overview import ReportSource
from crossaudit.doctor_shared import constitution_state


def _note(state_kwargs) -> str:
    """The sentence the console is handed for one report state."""
    return ReportSource(path=None, text="", **state_kwargs).note


# ---------------------------------------------------------------- 1 of 5
def test_an_uncommitted_report_says_it_cannot_be_verified_not_merely_that_it_is_new():
    """Rank 1. Softened, unverified work appears safe."""
    note = _note({"commit": "", "on_disk_differs": False})
    assert "not committed" in note, note
    assert "cannot be verified" in note, (
        "the caveat is gone: without it this reads as a housekeeping note about "
        f"a new file, not a refusal to vouch for it. Got: {note!r}")


# ---------------------------------------------------------------- 2 of 5
def test_a_report_edited_after_its_audit_says_the_disk_copy_differs_and_how_to_check():
    """Rank 2. Softened, post-hoc bytes appear audited."""
    note = _note({"commit": "abc123", "on_disk_differs": True})
    assert "differs" in note, note
    assert "audited" in note, (
        f"it no longer says WHICH copy is the audited one. Got: {note!r}")
    assert "crossaudit verify" in note, (
        f"the sentence no longer names the command that settles it. Got: {note!r}")

    # Same class, narrower state: committed bytes no receipt vouches for.
    unverified = _note({"commit": "abc123", "on_disk_differs": False, "cited": False})
    assert "cannot confirm" in unverified, (
        "without this the fallback ASSERTS provenance it does not have — a "
        f"report rewritten after its audit and then committed. Got: {unverified!r}")


# ---------------------------------------------------------------- 3 of 5
def test_the_local_tier_says_the_history_is_rewritable_not_merely_that_it_is_self_review():
    """Rank 3. Softened, a self-reviewed history appears accountable."""
    means = adm.TIER_MEANING[adm.LOCAL]
    assert "self-review" in means, means
    assert "rewrite" in means, (
        "'self-review' alone reads as a process choice; the clause that makes it "
        f"a warning is that the history can be rewritten. Got: {means!r}")

    rendered = adm.Assessment(tier=adm.LOCAL).render()
    assert "rewrite" in rendered, f"the warning is lost in the rendered tier: {rendered!r}"
    assert "rewrite" in adm.Assessment(tier=adm.LOCAL).as_dict()["means"]


# ---------------------------------------------------------------- 4 of 5
def test_a_drifted_constitution_says_the_audit_would_cite_other_bytes(cfg):
    """Rank 4. Softened, a governing standard appears current when it is not."""
    (cfg.root / cfg.constitution).write_text("R1: changed but not committed\n",
                                             encoding="utf-8")
    status, detail = constitution_state(cfg)
    assert status == "drifted", (status, detail)
    assert "uncommitted changes" in detail, detail
    assert "would cite the committed version" in detail, (
        "without this the sentence reports an edit; with it, it warns that the "
        f"rules being audited against are NOT the ones on screen. Got: {detail!r}")
    assert "not what is on disk" in detail, detail


# ---------------------------------------------------------------- 5 of 5
def test_every_failing_doctor_row_tells_the_person_what_to_do_next(cfg, monkeypatch,
                                                                   capsys):
    """Rank 5. Softened, a user reaches an unrecoverable setup state."""
    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=True, all=True, fix=False, online=False))
    payload = capsys.readouterr().out
    checks = json.loads(payload[payload.index("{"):payload.rindex("}") + 1])["checks"]
    failing = [c for c in checks if not c["ok"]]
    assert failing, "no failing row in this fixture; the guard would be vacuous"

    without_next_action = [c["check"] for c in failing if not str(c.get("fix", "")).strip()]
    assert without_next_action == [], (
        f"these rows tell a person something is wrong and not what to do about "
        f"it: {without_next_action}")

    # And the renderer a person actually reads must carry it, not just the payload.
    main.cmd_doctor(argparse.Namespace(json=False, all=True, fix=False, online=False))
    rendered = capsys.readouterr().out
    for row in failing:
        assert row["fix"] in rendered, (
            f"the next action for {row['check']!r} never reaches the terminal: "
            f"{row['fix']!r}")
