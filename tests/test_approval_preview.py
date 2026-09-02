"""P13 — the approval card shows exactly what will happen before you say yes.

Each gated tool renders a bounded, human-readable preview (a diff, a command, a
commit summary). The broker threads it into the pending action; it is shown on
the card only, never logged or ledgered.
"""
from __future__ import annotations

import sys
import threading
import time

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.humanapproval import ONCE, ApprovalInbox, HumanApprovalGate
from crossaudit.broker.tools_command import run_check_preview
from crossaudit.broker.tools_git import git_commit_preview
from crossaudit.broker.tools_hpc import hpc_submit_preview
from crossaudit.broker.tools_write import file_write_preview
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _writable():
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_write"],
        "paths": ["**"], "writable": True, "expires_at": "2100-01-01T00:00:00Z"})


# -- the preview functions --
def test_file_write_preview_is_a_diff(cfg):
    (cfg.root / "work").mkdir(parents=True, exist_ok=True)
    (cfg.root / "work/a.md").write_text("one\ntwo\n")
    p = file_write_preview(cfg, {"path": "work/a.md", "content": "one\nTWO\n"})
    assert "write work/a.md" in p and "-two" in p and "+TWO" in p


def test_file_write_preview_marks_a_new_file(cfg):
    p = file_write_preview(cfg, {"path": "work/new.md", "content": "hi\nthere"})
    assert "(new file)" in p and "+hi" in p and "+there" in p


def test_run_check_preview_is_the_command_line(cfg):
    assert run_check_preview(cfg, {"command": [sys.executable, "-c", "print(1)"]}) \
        == f"run: {sys.executable} -c print(1)"


def test_git_commit_preview_shows_message_and_files(cfg):
    (cfg.root / "note.txt").write_text("hi")
    p = git_commit_preview(cfg, {"message": "add a note"})
    assert "commit: add a note" in p and "note.txt" in p


def test_hpc_submit_preview_summarizes_the_job(cfg):
    p = hpc_submit_preview(cfg, {"manifest": {"host": "cluster", "cmd": "run.sh"}})
    assert "submit HPC job" in p and "cluster" in p and "run.sh" in p


# -- end to end: the preview reaches the pending card --
def test_broker_puts_the_preview_on_the_pending_card(cfg, tmp_path):
    inbox = ApprovalInbox()
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"),
                        approver=HumanApprovalGate(inbox=inbox))
    captured = {}

    def resolver():
        deadline = time.time() + 4.0
        while time.time() < deadline:
            p = inbox.pending("r")
            if p is not None:
                captured["preview"] = p["preview"]
                inbox.resolve("r", ONCE)
                return
            time.sleep(0.005)

    t = threading.Thread(target=resolver, daemon=True)
    t.start()
    r = broker.execute(
        {"tool": "file_write", "args": {"path": "work/new.md", "content": "hi\nthere"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)
    t.join(timeout=5.0)
    assert r.status == "succeeded"
    assert "write work/new.md" in captured["preview"] and "+hi" in captured["preview"]
    # The preview is NOT ledgered — only hashes/metadata are.
    blob = (tmp_path / "ev.jsonl").read_text()
    assert "+hi" not in blob and "write work/new.md" not in blob


def test_page_markup_contains_the_approval_preview_block():
    """MARKUP ONLY. This asserts strings are present in ``page.py``; it does not
    render anything and cannot fail if the page never reaches a person. Renamed
    under D106: serving an empty document leaves it green, so a name claiming
    "renders"/"announces" was a property nobody tested.
    """
    from crossaudit.console.page import PAGE
    assert "approval-preview" in PAGE and "a.preview" in PAGE
