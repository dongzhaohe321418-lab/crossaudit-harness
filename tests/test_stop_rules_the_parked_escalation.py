"""Stop on a parked run is a human ruling, committed like every other close.

D172 ruling 5: every human ruling is committed to the ledger. Pressing Stop on
a run parked for a provider closes the escalation that names the run
(`RunCommandService._close_park_escalations`); that close used to change only
the gitignored controller state. It now goes through `rulings.rule`, and Stop
always stops: a close that cannot be committed leaves the cycle ESCALATED and
says so in the stop result's `note` (and in the TUI's line), never closing it
silently or in the state alone.
"""
from __future__ import annotations

import json

from crossaudit.cli import i18n, tuiapp
from crossaudit.controller import StateStore
from crossaudit.gitio import git
from crossaudit.runtime import RunCommandService
from crossaudit.runtime.commands import STOP_RULING_REASON

from .test_admission_and_console import console, fetch, post_json_to  # noqa: F401
from .test_resolve_commits_the_ruling import REFUSING_HOOK, install_hook
from .test_run_liveness_adversarial import park_via_service


def _parked(cfg):
    journal = park_via_service(cfg, "parked task")
    run_id = journal.latest()["run_id"]
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cid = next(cid for cid, c in store.snapshot()["cycles"].items()
               if c["status"] == "ESCALATED")
    assert store.cycle(cid)["escalation_run_id"] == run_id
    return journal, run_id, store, cid


def _rows(root):
    log = root / "cycles" / "rulings.jsonl"
    if not log.exists():
        return None
    rows = [json.loads(line) for line in log.read_text().split("\n") if line]
    rows = [r for r in rows if r.get("kind") != "escalation"]   # escalation rows are not rulings (D176 ruling 43)
    return rows or None


def _assert_still_escalated(cfg, store, cid, head):
    root = cfg.root
    assert store.cycle(cid)["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution"
                   for h in store.snapshot()["history"])
    assert _rows(root) is None
    assert git("status", "--porcelain", "--", "cycles", cwd=root) == ""
    assert git("diff", "--cached", "--name-only", cwd=root) == ""
    assert git("rev-parse", "HEAD", cwd=root) == head


def test_stop_on_a_parked_run_commits_the_close_ruling(science, cfg):
    """Mutation caught: `_close_park_escalations` closing through
    `StateStore.resolve_escalation` (state only) -- the cycle closes but
    `cycles/rulings.jsonl` has no row and `git log` no commit."""
    journal, run_id, store, cid = _parked(cfg)
    result = RunCommandService(cfg).request_cancel(run_id)
    assert result["state"] == "CANCELLED" and "note" not in result
    assert journal.state(run_id).value == "CANCELLED"
    cycle = store.cycle(cid)
    assert cycle["status"] == "BLOCKED" and cycle["closed_by_human"] is True
    rows = _rows(science)
    assert [(r["cycle_id"], r["action"], r["reason"], r["status_after"])
            for r in rows] == [(cid, "close", STOP_RULING_REASON, "BLOCKED")]
    assert git("log", "-1", "--format=%s", cwd=science).startswith(f"ruling {cid} close")
    assert STOP_RULING_REASON in git("log", "-1", "--format=%B", cwd=science)
    assert git("status", "--porcelain", "--", "cycles", cwd=science) == ""


def test_stop_with_a_rejected_commit_still_stops_and_leaves_the_cycle_escalated(
        science, cfg):
    """Mutations caught: letting the ruling's IntegrityDenial escape
    `request_cancel` (Stop would raise); falling back to a state-only close
    (the cycle would read BLOCKED with no row); swallowing the refusal (no
    `note` -- the person would not learn the cycle still needs a ruling)."""
    journal, run_id, store, cid = _parked(cfg)
    install_hook(science, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=science)
    result = RunCommandService(cfg).request_cancel(run_id)
    assert result["state"] == "CANCELLED"
    assert journal.state(run_id).value == "CANCELLED"
    sentence = (f"the ruling on cycle {cid} could not be committed to the ledger "
                f"(pre-commit: refused by policy); the cycle stays ESCALATED and "
                f"nothing was recorded")
    assert result["note"] == sentence and result["ruling_refused"] == [sentence]
    _assert_still_escalated(cfg, store, cid, head)


def test_the_tui_stop_says_the_cycle_still_needs_a_ruling(science, cfg):
    """The TUI's Stop (`tuiapp.stop_run`). Mutation caught: `stop_run`
    ignoring `ruling_refused` -- it would say only "Stop requested"."""
    i18n.set_language("en")
    _journal, run_id, store, cid = _parked(cfg)
    install_hook(science, REFUSING_HOOK)
    said = tuiapp.stop_run(cfg, run_id)
    assert said.startswith(f"Stop requested for run {run_id[:12]}")
    assert ("The run is stopped, but its escalation still needs a ruling: "
            f"the ruling on cycle {cid} could not be committed") in said
    assert store.cycle(cid)["status"] == "ESCALATED"


def test_the_tui_stop_says_it_in_chinese(science, cfg):
    """The new line and the refusal inside it, both Chinese (parity)."""
    _journal, run_id, _store, cid = _parked(cfg)
    install_hook(science, REFUSING_HOOK)
    i18n.set_language("zh")
    try:
        said = tuiapp.stop_run(cfg, run_id)
    finally:
        i18n.set_language("en")
    assert f"运行已停止，但它的升级仍需要裁决：周期 {cid} 的裁决未能提交到账本" in said


def test_the_console_stop_returns_the_refusal_in_both_languages(console):  # noqa: F811
    """`/api/run` cancel through the tokened HTTP boundary. Mutation caught:
    the handler dropping the stop result's `note`, or a refusal served only
    in English (no `note_zh`)."""
    from pathlib import Path

    from crossaudit.config import load

    _status, body, _h = fetch(console.replace("/?t=", "/api/state?t="))
    root = Path(json.loads(body)["root"])
    cfg = load(root / "crossaudit.yml")
    # A park records its decision object against HEAD, so the project needs one.
    (root / ".gitignore").write_text(".crossaudit/\n")
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "bootstrap", cwd=root)
    _journal, run_id, store, cid = _parked(cfg)
    install_hook(root, REFUSING_HOOK)
    code, result, _h = post_json_to(console, "/api/run",
                                    {"action": "cancel", "run_id": run_id})
    assert code == 200 and result["state"] == "CANCELLED"
    assert result["note"].startswith(f"the ruling on cycle {cid} could not be committed")
    assert result["note_zh"].startswith(f"周期 {cid} 的裁决未能提交到账本")
    assert store.cycle(cid)["status"] == "ESCALATED"
    assert _rows(root) is None
