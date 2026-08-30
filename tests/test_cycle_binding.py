"""One decision, one standard, and a receipt that binds what was judged.

This carries four properties onto integration. Their history matters, because
three of the four exist only because a guard was found not to reach the code it
named:

  1. A verdict row names the standard the round was ACTUALLY judged against.
     The class sweep found a round whose controller record said C0 while its
     receipt said C1 and the Auditor received neither — one decision, two
     commits, a third byte source.
  2. `inputs.skills` derives from the subject commit. It read the working
     directory, so a receipt attributed `skills/late.md` to work committed
     before that file existed.
  3. `run` no longer advertises a command that always refuses.
  4. The suite reaches neither the developer's credentials nor the network.

The constitution read itself is NOT here. Integration's `_committed_constitution`
and `read_committed_bytes` already do that job, and better than the version this
branch's predecessor carried: `git show <commit>:<path>` returns a committed
symlink's TARGET STRING as if it were file content, so a symlinked constitution
would have been handed to the Auditor and hashed into the receipt, both agreeing
and neither holding the rules. `read_committed_bytes` refuses it on mode. That
primitive is theirs and it stays theirs.
"""
from __future__ import annotations

import argparse
import hashlib
from types import SimpleNamespace

import pytest

from crossaudit.controller import StateStore
from crossaudit.controller.state import BLOCKED, PASSED
from crossaudit.errors import IntegrityDenial
from crossaudit.gitio import git, read_committed_bytes


def _store(cfg) -> StateStore:
    return StateStore(cfg.root / cfg.state_dir / "state.json")


def _head_constitution(cfg) -> str:
    return git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)


def _loosen(cfg) -> str:
    const = cfg.root / cfg.constitution
    const.write_text(const.read_text().replace("**BLOCKER.**", "**ADVISORY.**"))
    git("add", "--", cfg.constitution, cwd=cfg.root)
    git("commit", "-q", "-m", "loosen the rules", cwd=cfg.root)
    return _head_constitution(cfg)


# ---------------------------------------------------------------- property 1
def test_a_verdict_row_names_the_standard_the_round_was_judged_against(cfg):
    """A judgment cannot name a standard its cycle does not."""
    store = _store(cfg)
    strict = _head_constitution(cfg)
    cycle = store.open_or_advance(cfg.science_repo, "a" * 40, None,
                                  constitution_commit=strict)
    cid = cycle["cycle_id"]
    store.record_verdict(cid, "a" * 40, "BLOCK", "r1", max_rounds=5,
                         constitution_commit=strict)
    assert store.cycle(cid)["verdicts"][-1]["constitution_commit"] == strict

    loosened = _loosen(cfg)
    # Advance onto the revision first: a verdict for a sha that is not the
    # cycle's active one is discarded as stale before any of this runs, so a
    # test that skips this step cannot reach the code it is guarding.
    store.continue_cycle(cid, cfg.science_repo, "b" * 40)
    with pytest.raises(IntegrityDenial) as caught:
        store.record_verdict(cid, "b" * 40, "PASS", "r2", max_rounds=5,
                             constitution_commit=loosened)
    assert "a decision cannot name a standard its cycle does not" in str(caught.value)
    assert store.cycle(cid)["status"] != PASSED
    rows = store.cycle(cid)["verdicts"]
    assert len(rows) == 1 and rows[0]["constitution_commit"] == strict


def test_the_first_judgment_establishes_a_pin_a_cycle_arrived_without(cfg):
    """A pre-revision or legacy cycle acquires its standard when it first needs one."""
    store = _store(cfg)
    strict = _head_constitution(cfg)
    cycle = store.open_or_advance(cfg.science_repo, "a" * 40, None)   # no pin
    cid = cycle["cycle_id"]
    assert not (store.cycle(cid).get("constitution_commit") or "")

    store.record_verdict(cid, "a" * 40, "BLOCK", "r1", max_rounds=5,
                         constitution_commit=strict)
    assert store.cycle(cid)["constitution_commit"] == strict
    assert store.cycle(cid)["verdicts"][-1]["constitution_commit"] == strict


def test_the_five_unpinned_by_design_paths_are_untouched(cfg):
    """A caller that judges nothing and mints no receipt passes nothing.

    The sweep separated design from omission deliberately. Normalising a
    defensible difference into consistency would not look like a defect in a
    diff and would destroy the distinction the sweep bought, so the parameter is
    optional and these callers stay silent.
    """
    store = _store(cfg)
    cycle = store.open_or_advance(cfg.science_repo, "s" * 40, None)   # sample style
    cid = cycle["cycle_id"]
    assert store.record_verdict(cid, "s" * 40, "PASS", "", max_rounds=5) == PASSED
    assert store.cycle(cid).get("constitution_commit", "") == ""
    assert store.cycle(cid)["verdicts"][-1]["constitution_commit"] == ""

    other = store.record_build_escalation(cfg.science_repo, "e" * 40,
                                          "provider failure: no key", 1,
                                          task="t", kind="provider")
    assert store.cycle(other["cycle_id"]).get("constitution_commit", "") == ""


# -------------------------------------- the guard that reaches build_receipt
def _drive_to_receipt(cfg, monkeypatch, sha, *, continuation=None):
    """Run the REAL `cmd_audit` far enough to build a receipt, and capture both.

    The predecessor of this guard defined a receipt capture and never installed
    it, then stopped `run_audit` with SystemExit — so receipt construction, the
    thing it claimed to guard, was never reached. `run_audit` here RETURNS, so
    the command proceeds through report writing into `build_receipt`, which is
    where the capture actually lives.
    """
    from crossaudit.cli import main as _main

    audited: dict = {}
    bound: dict = {}

    def fake_audit(**kw):
        audited.update(kw)
        return SimpleNamespace(
            report="| round | 1 |\n| verdict | **PASS** |\n",
            dcl={"crossaudit_dcl_version": 3, "verdict": "PASS",
                 "total_hard_failures": 0, "findings": [], "notes": [],
                 "contracts": {}},
            prompt_sha256="0" * 64, verdict="PASS", exchange=None, integrity=None)

    def capture_receipt(**kw):
        bound.update(kw)
        raise SystemExit(0)

    monkeypatch.setattr(_main, "run_audit", fake_audit)
    monkeypatch.setattr(_main, "build_receipt", capture_receipt)
    monkeypatch.chdir(cfg.root)
    args = argparse.Namespace(sha=sha, scope=None, json=False, retention=None,
                              allow_custom_endpoint=False, on_step=None,
                              continue_cycle=continuation, offline=True,
                              write_ledger=False, mode=None)
    with pytest.raises(SystemExit):
        _main.cmd_audit(args)
    assert audited and bound, "the command never reached receipt construction"
    return audited, bound


def _assert_binding_is_coherent(cfg, audited: dict, bound: dict) -> None:
    """Three things must agree, checked against an INDEPENDENT read of the blob.

    The failure this exists for had the first two agreeing while both disagreed
    with the third — worse than a contradiction, because a consistent wrong
    answer is not detectable.
    """
    cited = bound["constitution_commit"]
    at_that_commit = read_committed_bytes(cfg.root, cited, cfg.constitution)
    assert audited["constitution"].encode("utf-8") == bound["constitution_bytes"], (
        "the receipt hashes bytes the auditor never judged")
    assert bound["constitution_bytes"] == at_that_commit, (
        "the receipt cites a commit whose bytes are not the bytes it hashed")
    assert audited["constitution_commit"] == cited, (
        "the auditor and the receipt name different commits")


def test_a_new_cycle_audits_and_hashes_the_commit_it_cites(cfg, monkeypatch):
    """The route a dirty working file used to reach. All four columns agree."""
    from tests.conftest import write_increment

    committed = (cfg.root / cfg.constitution).read_bytes()
    sha = write_increment(cfg.root, {"quantities": []}, "s", "increment one")
    (cfg.root / cfg.constitution).write_bytes(
        committed + b"\n### CA-DIRTY-001\n**ADVISORY.** uncommitted\n\nx\n")

    audited, bound = _drive_to_receipt(cfg, monkeypatch, sha)
    _assert_binding_is_coherent(cfg, audited, bound)
    assert bound["constitution_bytes"] == committed, (
        "the uncommitted working file reached the audit")
    assert hashlib.sha256(bound["constitution_bytes"]).hexdigest() == \
        hashlib.sha256(committed).hexdigest()


def test_a_pinned_continuation_audits_and_hashes_the_commit_it_cites(cfg,
                                                                     monkeypatch):
    """The route that was already correct, kept so a later fix cannot break it."""
    from tests.conftest import write_increment

    strict_raw = (cfg.root / cfg.constitution).read_bytes()
    strict = _head_constitution(cfg)
    sha = write_increment(cfg.root, {"quantities": []}, "s", "increment one")
    store = _store(cfg)
    opened = store.open_or_advance(cfg.science_repo, sha, None,
                                   constitution_commit=strict)
    store.record_verdict(opened["cycle_id"], sha, "BLOCK", "r1", max_rounds=5,
                         constitution_commit=strict)
    _loosen(cfg)
    revised = write_increment(cfg.root, {"quantities": []}, "s2", "increment two")

    audited, bound = _drive_to_receipt(cfg, monkeypatch, revised,
                                       continuation=opened["cycle_id"])
    _assert_binding_is_coherent(cfg, audited, bound)
    assert bound["constitution_commit"] == strict
    assert bound["constitution_bytes"] == strict_raw


def test_the_binding_guard_goes_red_when_the_working_file_is_read_again(
        cfg, monkeypatch):
    """D10: the PROPERTY ASSERTION must fail under the mutation.

    Not "the defect was reproduced" — a guard can reproduce a defect and still
    be insensitive to it. This runs the same `_assert_binding_is_coherent` the
    real guard runs and requires it to raise.
    """
    from crossaudit.cli import main as _main
    from tests.conftest import write_increment

    committed = (cfg.root / cfg.constitution).read_bytes()
    sha = write_increment(cfg.root, {"quantities": []}, "s", "increment one")
    (cfg.root / cfg.constitution).write_bytes(committed + b"\ndirty\n")

    # The pre-fix behaviour: the receipt reads the working file for itself.
    monkeypatch.setattr(
        _main, "_committed_constitution",
        lambda cfg_, commit: (
            (cfg_.root / cfg_.constitution).read_text(encoding="utf-8"),
            (cfg_.root / cfg_.constitution).read_bytes()))
    audited, bound = _drive_to_receipt(cfg, monkeypatch, sha)
    with pytest.raises(AssertionError) as caught:
        _assert_binding_is_coherent(cfg, audited, bound)
    assert "not the bytes it hashed" in str(caught.value), (
        "the guard failed for some other reason; this proves nothing")


# ---------------------------------------------------------------- property 2
def test_the_receipt_attributes_only_skills_the_subject_commit_holds(cfg):
    """A receipt naming a skill created after the work is a provenance falsehood."""
    from crossaudit.cli import main as _main
    from tests.conftest import write_increment

    (cfg.root / "skills").mkdir(exist_ok=True)
    (cfg.root / "skills" / "early.md").write_text("# early\n\nguidance\n")
    git("add", "-A", cwd=cfg.root)
    git("commit", "-q", "-m", "an early skill", cwd=cfg.root)
    sha = write_increment(cfg.root, {"quantities": []}, "s", "the subject")
    (cfg.root / "skills" / "late.md").write_text("# late\n\nafter the fact\n")

    manifest = _main._skills_manifest(cfg, sha)
    assert any(k.endswith("early.md") for k in manifest), sorted(manifest)
    assert not any(k.endswith("late.md") for k in manifest), (
        f"a skill absent from the subject commit was attested: {sorted(manifest)}")
    assert any(k.endswith("late.md") for k in _main._skills_manifest(cfg)), (
        "the contrast is not real; the disk read should see it")


# ---------------------------------------------------------------- property 3
def test_run_stops_advertising_a_command_that_always_refuses(cfg, monkeypatch,
                                                             capsys):
    from crossaudit.cli import main as _main
    from tests.conftest import write_increment

    strict = _head_constitution(cfg)
    sha = write_increment(cfg.root, {"quantities": []}, "s", "increment one")
    store = _store(cfg)
    opened = store.open_or_advance(cfg.science_repo, sha, None,
                                   constitution_commit=strict)
    store.record_verdict(opened["cycle_id"], sha, "BLOCK", "r1", max_rounds=5,
                         constitution_commit=strict)

    monkeypatch.chdir(cfg.root)
    code = _main.cmd_run(argparse.Namespace(
        sha=sha, json=False, offline=True, science=None,
        allow_custom_endpoint=False, continue_cycle=None))
    out = capsys.readouterr().out
    assert code == 0 and "Already audited" in out
    assert "crossaudit audit --sha" not in out, (
        "the front door still advertises a command that always refuses")
    assert "Commit a revision" in out and "new increment" in out
    assert "dispute" not in out.lower(), "a dispute route was invented"


# ---------------------------------------------------------------- property 4
def test_the_suite_cannot_reach_the_developers_credentials_or_the_network():
    """The guard itself, asserted rather than assumed."""
    import os
    import socket
    import tempfile

    keys = os.environ.get("CROSSAUDIT_KEYS_FILE", "")
    assert keys, "the keys file was not sandboxed"
    assert keys.startswith(tempfile.gettempdir()) or "/pytest-" in keys, (
        f"the keys file is not inside a sandbox: {keys}")

    with socket.socket() as probe:
        with pytest.raises(AssertionError) as caught:
            probe.connect(("example.invalid", 80))
    assert "must not reach the network" in str(caught.value)
