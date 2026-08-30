"""Committed audit inputs are object bytes, never Git's display text.

The receipt cites a constitution commit.  These tests execute both CLI audit
entry paths and require the text given to the Auditor and the bytes given to
the receipt to be the exact blob at that commit, including framing whitespace.
"""
from __future__ import annotations

import argparse
import subprocess

import pytest

from crossaudit.auditor.run import AuditOutcome
from crossaudit.cli import main as cli
from crossaudit.controller import StateStore
from crossaudit.gitio import git
from tests.conftest import GOOD_RESULTS, write_increment


class _ReceiptReached(Exception):
    """Stop after both consumers have received the committed artifact."""


def _commit_constitution(cfg, data: bytes, message: str) -> str:
    path = cfg.root / cfg.constitution
    path.write_bytes(data)
    git("add", "--", cfg.constitution, cwd=cfg.root)
    git("commit", "-q", "-m", message, cwd=cfg.root)
    return git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)


def _object_bytes(cfg, commit: str) -> bytes:
    """Independent oracle: raw stdout from Git's blob plumbing."""
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{cfg.constitution}"],
        cwd=cfg.root, capture_output=True, check=True).stdout


def _outcome() -> AuditOutcome:
    return AuditOutcome(
        verdict="BLOCKED",
        dcl={"total_hard_failures": 1, "findings": []},
        model_reply=None,
        invalid_reason=None,
        integrity="OK",
        exchange={"mode": "none"},
        prompt_sha256="a" * 64,
        report="# test audit\n",
    )


def _drive_to_receipt(cfg, monkeypatch, surface: str, committed: bytes,
                      *, pinned: bool) -> tuple[dict, dict, str]:
    commit = _commit_constitution(cfg, committed, "constitution byte fixture")
    first_sha = write_increment(cfg.root, GOOD_RESULTS, "first", "first increment")
    continuation = None
    if pinned:
        store = StateStore(cfg.root / cfg.state_dir / "state.json")
        cycle = store.open_or_advance(cfg.science_repo, first_sha, None,
                                      constitution_commit=commit)
        store.record_verdict(cycle["cycle_id"], first_sha, "BLOCK", "receipt-1", 5)
        continuation = cycle["cycle_id"]
        _commit_constitution(
            cfg, b"# A different standard now in the working tree\n",
            "replace constitution after cycle opened")
        sha = write_increment(cfg.root, GOOD_RESULTS, "second", "revised increment")
    else:
        sha = first_sha

    # A dirty file must not affect either consumer even when its last committed
    # version happens to be the cycle pin currently in force.
    (cfg.root / cfg.constitution).write_bytes(b"DIRTY WORKING TREE WITHOUT NEWLINE")
    audit_seen: dict = {}
    receipt_seen: dict = {}

    def capture_audit(**kwargs):
        audit_seen.update(kwargs)
        return _outcome()

    def capture_receipt(**kwargs):
        receipt_seen.update(kwargs)
        raise _ReceiptReached

    monkeypatch.setattr(cli, "run_audit", capture_audit)
    monkeypatch.setattr(cli, "build_receipt", capture_receipt)
    monkeypatch.chdir(cfg.root)
    if surface == "audit":
        args = argparse.Namespace(
            sha=sha, scope=None, json=False, retention="sealed",
            allow_custom_endpoint=False, on_step=None,
            continue_cycle=continuation, offline=True, write_ledger=False,
            mode="local")
        operation = lambda: cli.cmd_audit(args)
    else:
        assert surface == "run" and not pinned
        args = argparse.Namespace(
            sha=sha, continue_cycle=None, allow_custom_endpoint=False)
        operation = lambda: cli.cmd_run(args)

    with pytest.raises(_ReceiptReached):
        operation()
    return audit_seen, receipt_seen, commit


_FRAMINGS = (
    b"",       # no final newline
    b"\n",     # the reported one-byte defect
    b"\r\n",   # two-byte line ending
    b" \n",    # whitespace git().strip() also destroys
    b"\t\n",   # another strip family member
)


@pytest.mark.parametrize("framing", _FRAMINGS)
@pytest.mark.parametrize("surface,pinned", (
    ("audit", False),
    ("audit", True),
    ("run", False),
))
def test_every_audit_consumer_gets_the_cited_constitution_blob(
        cfg, monkeypatch, surface, pinned, framing):
    committed = b"# Exact constitution bytes\n\n### CA-BYTE-001\n**BLOCKER.** keep" + framing
    audit_seen, receipt_seen, commit = _drive_to_receipt(
        cfg, monkeypatch, surface, committed, pinned=pinned)
    oracle = _object_bytes(cfg, commit)

    assert oracle == committed, "the fixture did not commit the intended bytes"
    assert audit_seen["constitution_commit"] == commit
    assert audit_seen["constitution"].encode("utf-8") == oracle
    assert receipt_seen["constitution_commit"] == commit
    assert receipt_seen["constitution_bytes"] == oracle


def test_the_commit_byte_guard_goes_red_when_the_real_reader_is_trimmed(
        cfg, monkeypatch):
    """D10: mutate the production boundary back to display-text semantics."""
    committed = b"# Strict standard\n\n### CA-BYTE-001\n**BLOCKER.** keep\n"
    audit_seen, receipt_seen, commit = _drive_to_receipt(
        cfg, monkeypatch, "audit", committed, pinned=True)
    oracle = _object_bytes(cfg, commit)

    def assert_commit_identity(audit: dict, receipt: dict) -> None:
        assert audit["constitution"].encode("utf-8") == oracle, (
            "AUDITOR_COMMIT_BYTES_DIVERGED")
        assert receipt["constitution_bytes"] == oracle, (
            "RECEIPT_COMMIT_BYTES_DIVERGED")

    assert_commit_identity(audit_seen, receipt_seen)

    # This is the historical implementation, invoked through the real audit
    # path: git() turns the object into convenience text and strips its newline.
    monkeypatch.setattr(
        cli, "read_committed_bytes",
        lambda repo, pinned_commit, path: git(
            "show", f"{pinned_commit}:{path}", cwd=repo).encode("utf-8"))
    mutated_audit, mutated_receipt, mutated_commit = _drive_to_receipt(
        cfg, monkeypatch, "audit", committed, pinned=True)
    assert _object_bytes(cfg, mutated_commit) == committed
    assert mutated_audit["constitution"].encode("utf-8") != committed, (
        "the mutation did not restore the trimming defect")
    with pytest.raises(AssertionError, match="AUDITOR_COMMIT_BYTES_DIVERGED"):
        assert_commit_identity(mutated_audit, mutated_receipt)
