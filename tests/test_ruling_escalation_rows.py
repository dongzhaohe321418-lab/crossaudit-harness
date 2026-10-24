"""Escalations are committed, signed rows; no implicit key recreation (review
2026-10-23 round 13; D176 rulings 43-44).

The cycle's current escalation identity is the commit of its latest signed
`escalation` row in `cycles/rulings.jsonl`. A verified ruling answering it is
recovered whenever the state does not reflect it -- close and reopen alike --
because a new stop always writes a new escalation row. No local state decides
that. Each test names the mutation it catches.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.crypto import keys
from crossaudit.errors import EXIT_OK, ConfigDenial, IntegrityDenial
from crossaudit.gitio import git
from crossaudit.receipt.sign import sign_receipt

from .test_resolve_commits_the_ruling import (REASON, REFUSING_HOOK, escalated,  # noqa: F401
                                              install_hook, ruling_rows)
from .test_ruling_two_phase_intent import _fail_phase3_write

LOG = "cycles/rulings.jsonl"


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _store(root: Path) -> StateStore:
    return StateStore(root / ".crossaudit" / "state.json")


def _state(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())


def _escalation_rows(root: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in (root / LOG).read_text().split("\n") if ln]
    return [r for r in rows if r.get("kind") == "escalation"]


def _status(capsys, cid):
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    return next(r for r in json.loads(capsys.readouterr().out)["cycles"]
                if r["cycle_id"] == cid)


# ------------------------------------------------ the reviewer's sequence
@pytest.mark.parametrize("tamper", ["drop_intent", "mark_applied"])
def test_a_committed_reopen_is_recovered_whatever_the_state_says(
        escalated, monkeypatch, tamper):
    """A `reopen` whose state write failed after its commit; then the state
    file is edited (the intent dropped, or the reopen's nonce written into
    `ruling_intents` as if applied); then `reopen` again. The signed
    committed reopen answers the current escalation and is recovered:
    exactly one ruling row, no second commit. Mutation caught: letting
    `ruling_intents` decide whether a verified reopen is pending (round 12)
    -- the edited state would make a second reopen row."""
    root, cid = escalated
    cfg = load()
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, "reopen", REASON)
    monkeypatch.undo()
    sha = git("rev-parse", "HEAD", cwd=root)
    nonce = ruling_rows(root)[-1]["intent"]
    with _store(root)._locked() as state:
        if tamper == "drop_intent":
            state.get("pending_rulings", {}).pop(cid, None)
        else:
            state["cycles"][cid]["ruling_intents"] = [nonce]
    result = rulings.rule(cfg, _store(root), cid, "reopen", "again")
    assert result["reconciled"] is True and result["ruling"]["commit"] == sha
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert len(ruling_rows(root)) == 1
    assert _state(root)["cycles"][cid]["status"] == "OPEN"


def test_a_stop_after_a_reopen_is_a_new_escalation(escalated, capsys):
    """A genuine reopen, then a stop that leaves no receipt (a provider
    failure): a new escalation row and a new identity, so ruling on it is a
    fresh ruling, not a recovery of the old reopen. Mutation caught: taking
    the cycle's FIRST escalation row as its identity -- the old reopen would
    be "recovered" onto the new stop."""
    root, cid = escalated
    cfg = load()
    first = rulings.escalation_identity(cfg, cid)
    rulings.rule(cfg, _store(root), cid, "reopen", "try once more")
    _store(root).escalate(cid, "generator provider failure in round 3: down",
                          kind="provider")
    second = rulings.escalation_identity(cfg, cid)
    assert second and second != first
    assert len(_escalation_rows(root)) == 2
    assert _status(capsys, cid)["escalation"] == {"committed": True,
                                                  "commit": second[:12]}
    head = git("rev-parse", "HEAD", cwd=root)
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "reconciled" not in result
    assert result["ruling"]["escalation_commit"] == second
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 1
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


# ------------------------------------------------ an escalation row that did not commit
def test_an_escalation_whose_row_cannot_commit_still_escalates_and_blocks_rulings(
        escalated, capsys):
    """A rejecting hook when the cycle stops again: the cycle is ESCALATED,
    status says the escalation is not committed, and a ruling refuses by
    name; once the hook is gone the next ruling commits the escalation and
    proceeds. Mutations caught: letting the escalation fail with the commit
    (the stop would not happen); ruling on an escalation the ledger does not
    hold."""
    root, cid = escalated
    cfg = load()
    rulings.rule(cfg, _store(root), cid, "reopen", "try once more")
    install_hook(root, REFUSING_HOOK)
    _store(root).escalate(cid, "build round budget spent (3)", kind="audit")
    state = _state(root)
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert state["cycles"][cid]["escalation_commit"] == ""
    assert _status(capsys, cid)["escalation"] == {
        "committed": False, "why": "pre-commit: refused by policy"}
    main.main(["status"])
    assert "escalation not committed (pre-commit: refused by policy)" in \
        capsys.readouterr().out
    head = git("rev-parse", "HEAD", cwd=root)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert denied.value.reason == (
        f"the escalation of cycle {cid} is not committed to the ledger (pre-commit: "
        f"refused by policy); rule on it after the repository is repaired")
    assert git("rev-parse", "HEAD", cwd=root) == head
    install_hook(root, "#!/bin/sh\nexit 0\n")
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "reconciled" not in result
    assert int(git("rev-list", "--count", f"{head}..HEAD", cwd=root)) == 2
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_a_cycle_escalated_by_an_older_version(escalated):
    """A cycle with no escalation row (written before ruling 43; its state
    has no `escalation_commit`). The ruling commits its escalation now and
    proceeds; if that cannot be committed, the refusal names the cause.
    Mutation caught: ruling on a legacy cycle with no committed escalation
    (its identity would be empty, and any ruling naming "" would answer it)."""
    root, cid = escalated
    cfg = load()
    with _store(root)._locked() as state:
        state["cycles"][cid].pop("escalation_commit", None)
    install_hook(root, REFUSING_HOOK)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert denied.value.reason == (
        f"the escalation of cycle {cid} is not committed to the ledger (escalated by "
        f"an older version of CrossAudit, and committing its escalation now failed: "
        f"pre-commit: refused by policy); rule on it after the repository is repaired")
    install_hook(root, "#!/bin/sh\nexit 0\n")
    before = len(_escalation_rows(root))
    rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert len(_escalation_rows(root)) == before + 1
    assert ruling_rows(root)[-1]["escalation_commit"] == \
        rulings.escalation_identity(cfg, cid)
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


# ------------------------------------------------ ruling 44: no implicit recreation
def test_a_missing_key_with_signed_artefacts_is_refused_not_recreated(escalated):
    """The seed file is deleted after rows were signed. Mutation caught:
    creating a new key implicitly -- it would verify nothing already signed."""
    root, cid = escalated
    cfg = load()
    seed = root / ".crossaudit" / "signing" / "ed25519.seed"
    seed.unlink()
    with pytest.raises(ConfigDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert denied.value.reason == (
        f"the project signing key at {seed} is missing but signed rulings or receipts "
        f"exist; restore it from your backup, since a new key would not verify them")
    assert not seed.exists()
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"
    # Receipt signing stays fail-open, and creates no second key either.
    assert sign_receipt(cfg, {"cycle": {"cycle_id": cid}}, root / "cycles") == ""
    assert not seed.exists()


def test_a_missing_key_with_nothing_signed_is_created(tmp_path):
    """A project with nothing signed. Mutation caught: refusing whenever the
    seed is absent (a new project could never sign its first row)."""
    cfg = SimpleNamespace(root=tmp_path, state_dir=".crossaudit", ledger_dir="cycles")
    (tmp_path / "cycles").mkdir()
    seed, pub, keyid = keys.load_or_create(cfg)
    assert (tmp_path / ".crossaudit" / "signing" / "ed25519.seed").is_file()
    assert keys.load_or_create(cfg)[2] == keyid
