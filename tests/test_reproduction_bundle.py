"""A2: the reproducibility bundle — pin the dependency environment and the
re-run recipe, additively.

Two layers of proof: the module logic (which manifest entries are locks, the
deterministic bundle, the present-only-when-meaningful block), and the end-to-end
binding (a receipt built over a tree with a lock carries the block, verify()
re-derives it from the tree, a forged block is refused, and a lock-free tree
mints a byte-identical pre-A2 receipt).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit.auditor import dcl_source_digest, run_audit
from crossaudit.cli import main as cli
from crossaudit.controller import StateStore
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import materialise, parent, resolve
from crossaudit.receipt import build, reproduction
from crossaudit.receipt.schema import validate
from crossaudit.receipt.verify import verify

from .conftest import GOOD_RESULTS, write_increment


# ---------------------------------------------------------------- module logic

def _receipt_with(manifest: dict) -> dict:
    return {
        "subject": {"science_repo": "lab", "sha": "a" * 40, "tree": "t" * 40,
                    "scope": "experiments"},
        "audit": {"verdict": "PASS", "provider": "openai", "model": "gpt-x"},
        "verifier": {"project": "crossaudit", "version": "5",
                     "code_digest_sha256": "c" * 64},
        "ledger": {"cycle_path": "cycles/aaaaaaaaaaaa-r1"},
        "inputs": {"manifest": manifest},
    }


def test_detect_locks_picks_only_lockfiles_and_skips_absent():
    manifest = {"src/app.py": "1" * 64, "experiments/poetry.lock": "2" * 64,
                "package-lock.json": "3" * 64, "README.md": "4" * 64,
                "gone/uv.lock": "ABSENT"}
    locks = reproduction.detect_locks(manifest)
    assert set(locks) == {"experiments/poetry.lock", "package-lock.json"}
    assert locks["experiments/poetry.lock"] == "2" * 64
    assert reproduction.lock_kinds(locks) == ["node", "python"]


def test_block_present_only_when_a_lock_exists():
    assert reproduction.receipt_block(_receipt_with({"src/a.py": "1" * 64})) is None
    block = reproduction.receipt_block(_receipt_with({"go.sum": "9" * 64}))
    assert block["locks"] == 1 and block["lock_kinds"] == ["go"]


def test_bundle_is_deterministic():
    r = _receipt_with({"Cargo.lock": "5" * 64, "src/a.py": "1" * 64})
    b1, b2 = reproduction.build_bundle(r), reproduction.build_bundle(r)
    assert reproduction.bundle_digest(b1) == reproduction.bundle_digest(b2)
    assert reproduction.receipt_block(r)["bundle_sha256"] == reproduction.bundle_digest(b1)


def test_bundle_carries_rerun_recipe_and_locks():
    r = _receipt_with({"experiments/requirements.txt": "7" * 64})
    b = reproduction.build_bundle(r)
    assert b["environment"]["locks"] == {"experiments/requirements.txt": "7" * 64}
    assert b["rerun"]["checkout"].endswith("a" * 40)
    assert b["rerun"]["verify"] == "crossaudit verify cycles/aaaaaaaaaaaa-r1/receipt.json"
    assert "determinism" in b["rerun"]["note"]           # honest, not overclaiming


# ------------------------------------------------------------------- schema

def test_schema_accepts_a_valid_block():
    r = _receipt_with({"poetry.lock": "2" * 64})
    r["reproduction"] = reproduction.receipt_block(r)
    # validate() needs a full receipt; just exercise the reproduction sub-rules:
    from crossaudit.receipt import schema
    schema._require(r["reproduction"], ("bundle_sha256", "locks", "lock_kinds"),
                    "reproduction")


@pytest.mark.parametrize("mutate", [
    lambda b: b.update(locks=0),
    lambda b: b.update(bundle_sha256=""),
    lambda b: b.update(lock_kinds="python"),
    lambda b: b.pop("bundle_sha256"),
])
def test_schema_rejects_a_malformed_block(cfg, science, mutate):
    sha, receipt = _mint(cfg, science, with_lock=True)
    mutate(receipt["reproduction"])
    with pytest.raises(IntegrityDenial):
        validate(receipt)


# ---------------------------------------------------------------- end-to-end

def _mint(cfg, science: Path, *, with_lock: bool):
    if with_lock:
        (science / "experiments" / "demo" / "requirements.txt").write_text(
            "numpy==1.26.4\nscipy==1.13.0\n")
    sha = write_increment(science, GOOD_RESULTS, "Work done.", "increment")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = subprocess.run(["git", "log", "-1", "--format=%H", "--", cfg.constitution],
                        cwd=str(cfg.root), capture_output=True, text=True,
                        check=False).stdout.strip()
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
        verdict=outcome.verdict, exchange=outcome.exchange, retention="sealed",
        report_bytes=(ldir / "report.md").read_bytes(), report_commit="",
        cycle_path=str(ldir.relative_to(cfg.root)),
        audit_repo=cfg.audit_repo or "local", mode="local",
        integrity=outcome.integrity)
    return sha, receipt


def test_lock_free_receipt_has_no_block_and_verifies(cfg, science):
    sha, receipt = _mint(cfg, science, with_lock=False)
    assert "reproduction" not in receipt          # byte-identical to a pre-A2 receipt
    validate(receipt)
    ev = verify(receipt, science_root=science, audit_root=science,
                expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert ev["verified"]


def test_receipt_binds_the_lock_and_verify_rederives(cfg, science):
    sha, receipt = _mint(cfg, science, with_lock=True)
    rep = receipt.get("reproduction")
    assert rep and rep["locks"] == 1 and rep["lock_kinds"] == ["python"]
    ev = verify(receipt, science_root=science, audit_root=science,
                expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert ev["verified"]


def test_a_forged_reproduction_digest_is_refused(cfg, science):
    sha, receipt = _mint(cfg, science, with_lock=True)
    receipt["reproduction"]["bundle_sha256"] = "0" * 64      # forged
    with pytest.raises(IntegrityDenial):
        verify(receipt, science_root=science, audit_root=science,
               expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_a_forged_lock_hash_breaks_verification(cfg, science):
    """The lock's content is bound: altering its recorded hash (to smuggle in a
    different pinned environment) fails re-derivation. Git trees are immutable by
    sha, so this — not a new commit — is the real tamper vector, and the manifest
    guard refuses it before admission."""
    sha, receipt = _mint(cfg, science, with_lock=True)
    lock_path = next(p for p in receipt["inputs"]["manifest"]
                     if p.endswith("requirements.txt"))
    receipt["inputs"]["manifest"][lock_path] = "0" * 64      # forged lock hash
    with pytest.raises(IntegrityDenial):
        verify(receipt, science_root=science, audit_root=science,
               expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)


def test_sidecar_written_only_when_a_lock_exists(cfg, science, tmp_path):
    # Lock-free first (the shared tree gains a lock and keeps it), so this is the
    # genuinely lock-free case rather than a residue of an earlier mint.
    _sha0, plain = _mint(cfg, science, with_lock=False)
    d2 = tmp_path / "cyc2"
    d2.mkdir()
    assert cli._write_reproduction(plain, d2) is False
    assert not (d2 / "reproduction.json").exists()

    _sha, receipt = _mint(cfg, science, with_lock=True)
    d = tmp_path / "cyc"
    d.mkdir()
    assert cli._write_reproduction(receipt, d) is True
    bundle = json.loads((d / "reproduction.json").read_text())
    assert bundle["environment"]["kinds"] == ["python"]
    assert reproduction.bundle_digest(bundle) == receipt["reproduction"]["bundle_sha256"]


# ------------------------------------------------------------- reproduce cmd

def _run_reproduce(cfg, receipt, monkeypatch, capsys, tmp_path) -> dict:
    cyc = tmp_path / "rc"
    cyc.mkdir(exist_ok=True)
    (cyc / "receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(cli, "load", lambda: cfg)
    args = SimpleNamespace(receipt=str(cyc / "receipt.json"), json=True)
    assert cli.cmd_reproduce(args) == cli.EXIT_OK
    return json.loads(capsys.readouterr().out)


def test_reproduce_reports_matching_environment(cfg, science, monkeypatch, capsys, tmp_path):
    _sha, receipt = _mint(cfg, science, with_lock=True)
    out = _run_reproduce(cfg, receipt, monkeypatch, capsys, tmp_path)
    assert out["environment_matches"] is True
    assert out["lock_kinds"] == ["python"]
    assert all(d["state"] == "match" for d in out["locks"])


def test_reproduce_reports_drift_when_a_lock_changes(cfg, science, monkeypatch, capsys, tmp_path):
    _sha, receipt = _mint(cfg, science, with_lock=True)
    (science / "experiments" / "demo" / "requirements.txt").write_text("drifted==9\n")
    out = _run_reproduce(cfg, receipt, monkeypatch, capsys, tmp_path)
    assert out["environment_matches"] is False
    assert any(d["state"] == "changed" for d in out["locks"])


def test_reproduce_is_honest_when_nothing_is_pinned(cfg, science, monkeypatch, capsys, tmp_path):
    _sha, receipt = _mint(cfg, science, with_lock=False)
    out = _run_reproduce(cfg, receipt, monkeypatch, capsys, tmp_path)
    assert out["environment_matches"] is False and out["locks"] == []
