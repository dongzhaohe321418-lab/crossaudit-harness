"""D171 R3: a dependency lock already committed in the audited tree is named
by the receipt, and `reproduce` prints each lock's path and digest.

Before D171 `reproduction.detect_locks` read only the manifest, which for
`crossaudit build` is the increment's changed paths (and for `audit` the scope
directories), so a `requirements.txt` committed BEFORE the increment, or at the
repository root, was never recorded and `reproduce` said NO DEPENDENCY LOCK
RECORDED. The mutation each guard catches is named in its docstring (D10).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.cli import main as cli
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import changed_paths, materialise, parent, resolve
from crossaudit.receipt import build, reproduction
from crossaudit.receipt.schema import canonical, validate
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, git, write_increment

LOCK = "numpy==1.26.4\nscipy==1.13.0\n"


def _commit(repo: Path, rel: str, text: str, message: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git("add", "--", rel, cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)


def _mint_increment(cfg, science: Path) -> tuple[str, dict]:
    """A receipt the way `crossaudit build` mints one: the manifest is the
    increment's changed paths only (cli/main.py, scope "changed-paths")."""
    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                        notes=notes, constitution=const, constitution_commit=cc,
                        offline=True)
    changed = set(changed_paths(cfg.root, sha))
    manifest = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()
                if p in changed}
    ldir = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "report.md").write_text(outcome.report)
    _sha, tree = resolve(cfg.root, sha)
    receipt = build(
        cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "changed-paths"},
        cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
        constitution_bytes=(cfg.root / cfg.constitution).read_bytes(),
        constitution_commit=cc, dcl_source_sha256=dcl_source_digest(),
        prompt_sha256=outcome.prompt_sha256, checks=cfg.checks,
        verdict=outcome.verdict, exchange=outcome.exchange, retention="sealed",
        report_bytes=(ldir / "report.md").read_bytes(), report_commit="",
        cycle_path=str(ldir.relative_to(cfg.root)),
        audit_repo=cfg.audit_repo or "local", mode="local",
        integrity=outcome.integrity)
    return sha, receipt


def _verify(cfg, science, sha, receipt):
    return verify(receipt, science_root=science, audit_root=science,
                  expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def _reproduce(cfg, receipt, monkeypatch, capsys, tmp_path, *, as_json=True):
    cyc = tmp_path / "rc"
    cyc.mkdir(exist_ok=True)
    (cyc / "receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(cli, "load", lambda: cfg)
    capsys.readouterr()
    args = SimpleNamespace(receipt=str(cyc / "receipt.json"), json=as_json)
    assert cli.cmd_reproduce(args) == cli.EXIT_OK
    out = capsys.readouterr().out
    return json.loads(out) if as_json else out


def test_a_lock_committed_before_the_increment_is_recorded_and_verifies(cfg, science):
    """The C19 scenario: the lock is in scope but not in the increment.

    Mutation: make `build._tree_locks` return {} (the pre-D171 receipt) ->
    no reproduction block, red."""
    _commit(science, "experiments/demo/requirements.txt", LOCK, "pin the env")
    sha, receipt = _mint_increment(cfg, science)
    assert "experiments/demo/requirements.txt" not in receipt["inputs"]["manifest"]
    rep = receipt["reproduction"]
    want = hashlib.sha256(LOCK.encode()).hexdigest()
    assert rep["tree_locks"] == {"experiments/demo/requirements.txt": want}
    assert rep["locks"] == 1 and rep["lock_kinds"] == ["python"]
    validate(receipt)
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_a_lock_at_the_repository_root_is_recorded(cfg, science):
    _commit(science, "requirements.txt", LOCK, "pin the env at the root")
    sha, receipt = _mint_increment(cfg, science)
    assert "requirements.txt" in receipt["reproduction"]["tree_locks"]
    assert _verify(cfg, science, sha, receipt)["verified"]


def test_the_lock_is_read_from_the_commit_not_the_working_tree(science):
    """Mutation: hash `repo / path` instead of the blob -> the edited working
    copy's digest is recorded, red."""
    _commit(science, "requirements.txt", LOCK, "pin the env")
    sha = git("rev-parse", "HEAD", cwd=science)
    (science / "requirements.txt").write_text("edited==0\n")       # uncommitted
    found = reproduction.detect_tree_locks(science, sha, None, {})
    assert found == {"requirements.txt": hashlib.sha256(LOCK.encode()).hexdigest()}


def test_a_lock_outside_the_configured_scope_is_not_recorded(science):
    """Root plus `scope.dirs`, nothing else. Mutation: drop the
    `_in_lock_scope` filter -> `other/` is recorded, red."""
    config = science / "crossaudit.yml"
    config.write_text(config.read_text() + "scope:\n  dirs: [experiments]\n")
    _commit(science, "other/requirements.txt", LOCK, "a lock elsewhere")
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "configure scope", cwd=science)
    cfg = load(science / "crossaudit.yml")
    _sha, receipt = _mint_increment(cfg, science)
    assert "reproduction" not in receipt


def test_a_generator_written_lock_is_unchanged(cfg, science):
    """A lock the increment itself writes is in the manifest and bound there,
    exactly as before D171: no tree_locks key, and the block is the one the
    manifest-only code produced.

    Mutation: stop skipping manifest paths in `detect_tree_locks` -> the
    lock appears in tree_locks too, red."""
    (science / "experiments" / "demo" / "requirements.txt").write_text(LOCK)
    _sha, receipt = _mint_increment(cfg, science)
    assert "experiments/demo/requirements.txt" in receipt["inputs"]["manifest"]
    rep = receipt["reproduction"]
    assert "tree_locks" not in rep
    plain = {k: v for k, v in receipt.items() if k != "reproduction"}
    assert rep == reproduction.receipt_block(plain)       # the manifest-only block


def test_a_lock_free_receipt_is_byte_identical(cfg, science):
    """No lock anywhere -> no block, so the receipt's bytes are exactly a
    receipt minted before A2/D171. Mutation: drop `receipt_block`'s
    `if not locks: return None` -> a zero-lock block is attached, red."""
    _sha, receipt = _mint_increment(cfg, science)
    assert "reproduction" not in receipt
    assert reproduction.receipt_block(receipt, {}) is None
    assert b"reproduction" not in canonical(receipt)


def test_a_forged_tree_lock_digest_is_refused(cfg, science):
    """Mutation: drop the re-read loop in verify() -> the bundle digest
    alone cannot catch it once the block is re-minted, red."""
    _commit(science, "requirements.txt", LOCK, "pin")
    sha, receipt = _mint_increment(cfg, science)
    forged = json.loads(json.dumps(receipt))
    forged["reproduction"]["tree_locks"]["requirements.txt"] = "0" * 64
    # Re-mint the block consistently so only the re-read can catch it.
    plain = {k: v for k, v in forged.items() if k != "reproduction"}
    forged["reproduction"] = reproduction.receipt_block(
        plain, forged["reproduction"]["tree_locks"])
    with pytest.raises(IntegrityDenial, match="reproduction lock mismatch"):
        _verify(cfg, science, sha, forged)
    absent = json.loads(json.dumps(receipt))
    absent["reproduction"] = reproduction.receipt_block(
        plain, {"nope/requirements.txt": "1" * 64})
    with pytest.raises(IntegrityDenial, match="absent from the tree"):
        _verify(cfg, science, sha, absent)


@pytest.mark.parametrize("bad", [{}, {"requirements.txt": "short"}, []])
def test_schema_refuses_a_malformed_tree_locks(cfg, science, bad):
    _commit(science, "requirements.txt", LOCK, "pin")
    _sha, receipt = _mint_increment(cfg, science)
    receipt["reproduction"]["tree_locks"] = bad
    with pytest.raises(IntegrityDenial):
        validate(receipt)


def test_reproduce_prints_each_lock_path_and_digest(
        cfg, science, monkeypatch, capsys, tmp_path):
    """Mutation: drop the per-lock lines -> red."""
    _commit(science, "experiments/demo/requirements.txt", LOCK, "pin the env")
    _sha, receipt = _mint_increment(cfg, science)
    want = hashlib.sha256(LOCK.encode()).hexdigest()
    text = _reproduce(cfg, receipt, monkeypatch, capsys, tmp_path, as_json=False)
    assert text.startswith("ENVIRONMENT MATCHES  1 lock file(s) [python]")
    assert f"experiments/demo/requirements.txt  sha256 {want}  MATCHES" in text
    doc = _reproduce(cfg, receipt, monkeypatch, capsys, tmp_path)
    assert doc["locks"] == [{"path": "experiments/demo/requirements.txt",
                             "sha256": want, "state": "match"}]


def test_reproduce_says_drifted_after_the_lock_is_edited(
        cfg, science, monkeypatch, capsys, tmp_path):
    _commit(science, "requirements.txt", LOCK, "pin the env")
    _sha, receipt = _mint_increment(cfg, science)
    (science / "requirements.txt").write_text("numpy==2.0.0\n")
    text = _reproduce(cfg, receipt, monkeypatch, capsys, tmp_path, as_json=False)
    assert text.startswith("ENVIRONMENT DRIFTED  requirements.txt (changed)")
    assert "requirements.txt  sha256 " in text and "  DRIFTED" in text


def test_the_cli_audit_then_reproduce_names_a_precommitted_lock(
        science, monkeypatch, capsys):
    """End to end through the shipped verbs: a root `requirements.txt` is
    committed before the increment, `crossaudit audit --scope experiments`
    mints the receipt (the lock is outside its manifest), and `crossaudit
    reproduce` / `crossaudit verify` read it back."""
    from .test_verify_signature_cli import _mint

    _commit(science, "requirements.txt", LOCK, "pin the env")
    receipt_path = _mint(science, monkeypatch)
    receipt = json.loads(receipt_path.read_text())
    want = hashlib.sha256(LOCK.encode()).hexdigest()
    assert receipt["reproduction"]["tree_locks"] == {"requirements.txt": want}
    bundle = json.loads((receipt_path.parent / "reproduction.json").read_text())
    assert bundle["environment"]["locks"] == {"requirements.txt": want}
    capsys.readouterr()
    assert cli.main(["reproduce", str(receipt_path)]) == 0
    assert f"requirements.txt  sha256 {want}  MATCHES" in capsys.readouterr().out
    assert cli.main(["verify", str(receipt_path)]) == 0
