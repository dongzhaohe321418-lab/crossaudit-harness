"""Recovery acts only on committed, verified ruling rows (review 2026-10-23
round 12; D176 rulings 40-41). Every ruling row is signed with the project's
Ed25519 key and names the committed identity of the escalation it answers;
the local state (intent, cursor) is a hint that decides nothing. Each test
names the mutation it catches.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from crossaudit import rulings
from crossaudit.cli import i18n, main
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.crypto import ed25519
from crossaudit.errors import EXIT_OK, ConfigDenial, IntegrityDenial
from crossaudit.gitio import git

from .test_resolve_commits_the_ruling import REASON, escalated  # noqa: F401
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


def _rows(root: Path) -> list[dict]:
    path = root / LOG
    return ([json.loads(ln) for ln in path.read_text().split("\n") if ln]
            if path.exists() else [])


def _commit_row(root: Path, row: dict) -> str:
    with open(root / LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    git("add", "--", LOG, cwd=root)
    git("commit", "-q", "-m", "a commit to the audit repository", "--", LOG, cwd=root)
    return git("rev-parse", "HEAD", cwd=root)


def _row_for(root: Path, cid: str, **extra) -> dict:
    cycle = _state(root)["cycles"][cid]
    return {"cycle_id": cid, "action": "close", "reason": "forged", "by": "x",
            "t": 0, "at": "1970-01-01T00:00:00Z", "round": cycle["round"],
            "active_sha": cycle["active_sha"], "status_after": "BLOCKED",
            "escalation_reason": "", **extra}


def _post_commit_failure(root, cid, cfg, monkeypatch, action="close"):
    _fail_phase3_write(monkeypatch)
    with pytest.raises(IntegrityDenial):
        rulings.rule(cfg, _store(root), cid, action, REASON)
    monkeypatch.undo()
    return git("rev-parse", "HEAD", cwd=root)


# ---------------------------------------------------------- the reviewer's sequences
@pytest.mark.parametrize("tamper", ["drop_intent", "move_cursor", "shape_intent"])
def test_local_state_cannot_hide_a_committed_ruling(escalated, monkeypatch, tamper):
    """After a post-commit state failure, state.json is edited (the intent
    removed, a cursor moved past the row, the intent reshaped), then
    `reopen` is asked. The signed committed `close` is found by its
    `escalation_commit`, applied, and the request refused; no second commit.
    Mutation caught: letting the local intent decide whether a committed
    ruling exists (rounds 9-11) -- with the intent gone a second ruling is
    committed."""
    root, cid = escalated
    cfg = load()
    sha = _post_commit_failure(root, cid, cfg, monkeypatch)
    store = _store(root)
    with store._locked() as state:
        intents = state.setdefault("pending_rulings", {})
        if tamper == "drop_intent":
            intents.pop(cid, None)
        elif tamper == "move_cursor":
            intents[cid]["rows_before"] = 10 ** 6
        else:
            intents[cid].update(action="reopen", nonce="e" * 32,
                                reason_sha256="0" * 64)
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, store, cid, "reopen", "the other way")
    assert denied.value.reason == (f"a committed ruling (close, {sha[:12]}) already "
                                   f"stands for cycle {cid}; the state now reflects it")
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"


def test_an_intent_shaped_to_a_foreign_row_applies_nothing(escalated):
    """An unsigned row claiming the current escalation is committed, and the
    local intent is shaped to its values. Mutation caught: accepting a row
    without a valid signature -- the foreign `close` would be applied."""
    root, cid = escalated
    cfg = load()
    identity = rulings.escalation_identity(cfg, cid)
    sha = _commit_row(root, _row_for(root, cid, intent="d" * 32,
                                     escalation_commit=identity))
    with _store(root)._locked() as state:
        state.setdefault("pending_rulings", {})[cid] = {
            "action": "close", "nonce": "d" * 32, "by": "",
            "reason_sha256": rulings.hashlib.sha256(b"forged").hexdigest(),
            "started_at": 0}
    with pytest.raises(IntegrityDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert denied.value.reason == (
        f"a committed ruling for cycle {cid} ({sha[:12]}) carries no valid signature "
        f"from this project; nothing was applied, and no new ruling is made until the "
        f"repository is repaired")
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"


def test_a_row_signed_with_another_key_is_refused_and_listed(escalated, capsys):
    """A forged row claiming the current escalation, signed with a key that
    is not the project's. Mutation caught: trusting any present signature
    (or a key named by the row) -- the forged `close` would be applied."""
    root, cid = escalated
    cfg = load()
    identity = rulings.escalation_identity(cfg, cid)
    row = _row_for(root, cid, intent="c" * 32, escalation_commit=identity,
                   keyid="0" * 16)
    other = ed25519.generate_seed()
    row["sig"] = base64.b64encode(ed25519.sign(other, rulings._signed_bytes(row))).decode()
    sha = _commit_row(root, row)
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    status = next(r for r in json.loads(capsys.readouterr().out)["cycles"]
                  if r["cycle_id"] == cid)
    assert [f["commit"] for f in status["unverified_rulings"]] == [sha[:12]]
    assert main.main(["status"]) == EXIT_OK
    assert f"unverified ruling row ({sha[:12]})" in capsys.readouterr().out
    with pytest.raises(IntegrityDenial, match="carries no valid signature"):
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"


def test_a_genuine_row_whose_signature_was_stripped_is_refused(escalated, monkeypatch):
    """The project's own committed `close` (its state write failed), then a
    commit that removes its `sig`. Mutation caught: skipping a row without a
    signature as if it were absent -- a second ruling would be committed."""
    root, cid = escalated
    cfg = load()
    _post_commit_failure(root, cid, cfg, monkeypatch)
    rows = _rows(root)
    rows[-1].pop("sig")
    (root / LOG).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)
                                    + "\n" for r in rows))
    git("add", "--", LOG, cwd=root)
    git("commit", "-q", "-m", "strip a signature", "--", LOG, cwd=root)
    sha = git("rev-parse", "HEAD", cwd=root)
    with pytest.raises(IntegrityDenial, match="carries no valid signature"):
        rulings.rule(cfg, _store(root), cid, "close", "again")
    assert git("rev-parse", "HEAD", cwd=root) == sha
    assert _state(root)["cycles"][cid]["status"] == "ESCALATED"


def test_a_legacy_row_is_listed_as_unverified_and_does_not_block(escalated, capsys):
    """A row written before ruling 40 (no signature, no
    `escalation_commit`). Mutation caught: treating rows without an
    `escalation_commit` as candidates -- the legacy row would block the
    cycle (or be applied)."""
    root, cid = escalated
    cfg = load()
    sha = _commit_row(root, _row_for(root, cid, action="reopen", status_after="OPEN"))
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    status = next(r for r in json.loads(capsys.readouterr().out)["cycles"]
                  if r["cycle_id"] == cid)
    assert [f["commit"] for f in status["unverified_rulings"]] == [sha[:12]]
    result = rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert "reconciled" not in result
    assert _state(root)["cycles"][cid]["status"] == "BLOCKED"
    assert int(git("rev-list", "--count", f"{sha}..HEAD", cwd=root)) == 1


# ---------------------------------------------------------- the row's shape
def test_every_ruling_row_is_signed_and_names_its_escalation(escalated):
    """Mutation caught: a row written without `sig` or `escalation_commit`
    (recovery would refuse the project's own row)."""
    root, cid = escalated
    cfg = load()
    identity = rulings.escalation_identity(cfg, cid)
    rulings.rule(cfg, _store(root), cid, "close", REASON)
    row = _rows(root)[-1]
    assert row["escalation_commit"] == identity and identity
    assert row["keyid"] and rulings.row_verifies(row, rulings._project_pubkey(cfg))
    receipt_path = git("show", "--name-only", "--format=", identity, cwd=root).split()
    assert any(p.endswith("/receipt.json") for p in receipt_path)


def test_no_signing_key_no_ruling(escalated, monkeypatch, tmp_path):
    """The signing key cannot be loaded or created (its directory is a
    regular file). Mutation caught: signing a ruling fail-open, like a
    receipt -- an unsigned row would be committed."""
    root, cid = escalated
    cfg = load()
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setenv("CROSSAUDIT_SIGNING_KEYFILE", str(blocker))
    head = git("rev-parse", "HEAD", cwd=root)
    with pytest.raises(ConfigDenial) as denied:
        rulings.rule(cfg, _store(root), cid, "close", REASON)
    assert denied.value.reason.startswith(
        f"the project signing key at {blocker / 'ed25519.seed'} is not available (")
    assert denied.value.reason.endswith(
        "); a ruling must be signed, so none was made")
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert _rows(root) == []
    state = _state(root)
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert cid not in state.get("pending_rulings", {})
