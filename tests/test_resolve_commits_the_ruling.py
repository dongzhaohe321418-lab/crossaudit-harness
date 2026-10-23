"""`resolve` commits the ruling and its reason to the ledger; `status` shows it.

README "Human escalation": "The reason is committed to the ledger." The
acceptance run (claim C25) found the reason only in the gitignored
`.crossaudit/state.json`: no commit, `status` silent about the ruling, the
closed cycle listed as BLOCKED and the run still WAITING_FOR_HUMAN. The
escalation here is produced by the real loop -- a real `build` whose
(transport-faked) auditor blocks every round until the budget is spent.

D10 mutations (checked by hand): drop the `record(...)` call in
`rulings.rule` and four go red (ledger, status, append, real pty); drop the
`settle_human_wait(...)` call there and the run case goes red. (Both lived in
`cli/main.py` until the one ruling transaction, review 2026-10-23.)

Failure atomicity (review 2026-10-23, finding 2): a ruling whose commit fails
leaves the cycle ESCALATED, the log as it was, nothing staged and no
`human_resolution` entry. Each test below names the mutation it catches.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import (FakeVendors, audit_reply, increment_reply,  # noqa: E402
                            init_project, with_keys)

from crossaudit.cli import main  # noqa: E402
from crossaudit.errors import (EXIT_CONFIG, EXIT_ESCALATED, EXIT_INTEGRITY,  # noqa: E402
                               EXIT_OK)
from crossaudit.gitio import git  # noqa: E402

REASON = "The benchmark is out of scope for this study; closing after review."


@pytest.fixture()
def escalated(tmp_path, monkeypatch, capsys):
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)

    def answer(role, n, prompt):
        if role == "auditor":
            return audit_reply(prompt, "BLOCKED")
        return increment_reply().replace("seed 7.", f"seed 7 (revision {n}).")
    FakeVendors(answer).install(monkeypatch)
    assert main.main(["build", "Create a small reproducible benchmark"]) == EXIT_ESCALATED
    capsys.readouterr()
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    cid = next(c for c, v in state["cycles"].items() if v["status"] == "ESCALATED")
    return root, cid


def _on_a_terminal(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)


def _status_row(capsys, cid):
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    doc = json.loads(capsys.readouterr().out)
    return next(r for r in doc["cycles"] if r["cycle_id"] == cid), doc


def test_a_close_ruling_is_committed_to_the_ledger_with_its_reason(
        escalated, monkeypatch, capsys):
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    head = git("rev-parse", "HEAD", cwd=root)
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_OK
    out = capsys.readouterr().out
    assert "committed to the ledger" in out and "closed" in out
    # One new commit, touching only the rulings log, the reason in its message.
    assert git("rev-list", "--count", f"{head}..HEAD", cwd=root) == "1"
    assert git("show", "--name-only", "--format=", "HEAD", cwd=root).split() == [
        "cycles/rulings.jsonl"]
    message = git("log", "-1", "--format=%B", cwd=root)
    assert cid in message and REASON in message
    rows = [json.loads(line) for line in
            (root / "cycles" / "rulings.jsonl").read_text().split("\n") if line]
    assert rows == [dict(rows[0], cycle_id=cid, action="close", reason=REASON)]
    assert rows[0]["by"] and rows[0]["at"]
    assert not git("status", "--porcelain", "--", "cycles", cwd=root)


def test_status_shows_the_ruling_and_reads_as_closed(escalated, monkeypatch, capsys):
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    main.main(["resolve", cid, "--close", "--because", REASON])
    row, doc = _status_row(capsys, cid)
    assert row["closed"] is True
    assert row["rulings"] == [{"action": "close", "by": row["rulings"][0]["by"],
                               "at": row["rulings"][0]["at"], "reason": REASON}]
    main.main(["status"])
    human = capsys.readouterr().out
    line = next(ln for ln in human.splitlines() if ln.startswith(cid))
    assert "CLOSED" in line and "BLOCKED" not in line
    assert f"ruling: close by " in human and REASON[:60] in human


def test_a_close_settles_the_run_that_was_waiting(escalated, monkeypatch, capsys):
    root, cid = escalated
    _, before = _status_row(capsys, cid)
    assert before["run"]["state"] == "WAITING_FOR_HUMAN"
    _on_a_terminal(monkeypatch)
    main.main(["resolve", cid, "--close", "--because", REASON])
    _, after = _status_row(capsys, cid)
    assert after["run"]["state"] == "CANCELLED"
    assert "closed by a human ruling" in after["run"]["note"]


def test_a_second_ruling_appends_and_never_rewrites(escalated, monkeypatch, capsys):
    """reopen, the cycle escalates again, then close: two lines, in order."""
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    assert main.main(["resolve", cid, "--reopen", "--because", "try once more"]) == EXIT_OK
    log = root / "cycles" / "rulings.jsonl"
    first = log.read_bytes()
    # The reopened cycle stops again. Recorded through the same store method
    # the build loop calls for a spent budget (cli/build.py record_decision_object).
    from crossaudit.config import load
    from crossaudit.controller import StateStore
    cfg = load()
    StateStore(cfg.root / cfg.state_dir / "state.json").escalate(
        cid, "build round budget spent (3)", kind="audit")
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_OK
    assert log.read_bytes().startswith(first)          # appended, not rewritten
    row, _ = _status_row(capsys, cid)
    assert [r["action"] for r in row["rulings"]] == ["reopen", "close"]
    subjects = git("log", "--format=%s", "-2", cwd=root).splitlines()
    assert subjects[0].startswith(f"ruling {cid} close")
    assert any(s.startswith(f"ruling {cid} reopen")
               for s in git("log", "--format=%s", cwd=root).splitlines())


def test_without_a_terminal_resolve_still_refuses(escalated, capsys):
    root, cid = escalated
    head = git("rev-parse", "HEAD", cwd=root)
    code = main.main(["resolve", cid, "--close", "--because", REASON])
    assert code == EXIT_CONFIG
    assert "refuses to run without a terminal" in capsys.readouterr().err
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert not (root / "cycles" / "rulings.jsonl").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
def test_on_a_real_pseudo_terminal_the_ruling_is_committed(escalated):
    """The gate is the real `isatty()` of a pty, not a patched one."""
    import pty

    root, cid = escalated
    src = Path(__file__).resolve().parents[1] / "src"
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith("_proxy")}
    env["PYTHONPATH"] = str(src)
    leader, follower = pty.openpty()
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; from crossaudit.cli.main import main; sys.exit(main())",
         "resolve", cid, "--close", "--because", REASON],
        cwd=root, env=env, stdin=follower, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=60)
    os.close(follower)
    os.close(leader)
    assert proc.returncode == 0, proc.stderr
    assert REASON in git("log", "-1", "--format=%B", cwd=root)


def test_the_talk_lane_ruling_is_committed_too(escalated, capsys):
    """`talk`'s resolve lane said "Your reason is in the ledger" as well."""
    from crossaudit.cli import talk
    from crossaudit.config import load
    from crossaudit.router import Routing

    root, cid = escalated
    words = "the source file is now available, try again"
    routing = Routing(utterance=words, lane="resolve", confidence=1.0,
                      reasoning="test", restated=words)
    assert talk.lane_resolve(load(), routing, assume_yes=True).startswith("reopened")
    assert git("log", "-1", "--format=%s", cwd=root).startswith(f"ruling {cid} reopen")
    assert words in git("log", "-1", "--format=%B", cwd=root)


# ------------------------------------------------- failure atomicity (finding 2)
REFUSING_HOOK = "#!/bin/sh\necho 'pre-commit: refused by policy' >&2\nexit 1\n"
#: Refuses only its second invocation: the hook "breaks" once and is repaired.
SECOND_ONLY_HOOK = (
    "#!/bin/sh\n"
    'n=$(cat "$0.count" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$0.count"\n'
    'if [ "$n" -eq 2 ]; then echo "pre-commit: refused once" >&2; exit 1; fi\n'
    "exit 0\n")


def install_hook(root: Path, script: str) -> Path:
    """A `pre-commit` hook for the project repository, kept outside the tree
    (so it never shows in `git status`) and named through the repository's
    own `core.hooksPath`, so a global hooks path cannot shadow it."""
    hooks = root.parent / f"{root.name}-hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(script)
    hook.chmod(0o755)
    git("config", "core.hooksPath", str(hooks), cwd=root)
    return hook


def assert_nothing_was_ruled(root: Path, cid: str, log_before: bytes | None,
                             head: str) -> None:
    """The four things a failed ruling must leave as they were."""
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution" and h.get("cycle") == cid
                   for h in state["history"])
    log = root / "cycles" / "rulings.jsonl"
    assert (log.read_bytes() if log.exists() else None) == log_before
    assert git("status", "--porcelain", "--", "cycles/rulings.jsonl", cwd=root) == ""
    assert git("diff", "--cached", "--name-only", cwd=root) == ""
    assert git("rev-parse", "HEAD", cwd=root) == head


def test_a_rejected_commit_leaves_the_cycle_escalated_and_nothing_recorded(
        escalated, monkeypatch, capsys):
    """Mutation caught: mutating the controller state before the commit (the
    old order in `resolve_cycle`) -- the cycle reads BLOCKED here; and
    dropping the restore/unstage in `rulings.record` -- the log keeps the
    line and `git status` shows it staged."""
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    install_hook(root, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=root)
    capsys.readouterr()
    code = main.main(["resolve", cid, "--close", "--because", REASON])
    err = capsys.readouterr().err
    assert code == EXIT_INTEGRITY
    assert (f"the ruling on cycle {cid} could not be committed to the ledger "
            f"(pre-commit: refused by policy); the cycle stays ESCALATED and "
            f"nothing was recorded") in err
    assert_nothing_was_ruled(root, cid, None, head)


def test_a_rejected_commit_restores_an_existing_log_byte_for_byte(
        escalated, monkeypatch, capsys):
    """Mutation caught: removing the log instead of truncating it back (or
    not restoring it at all) when it already held a committed ruling."""
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    assert main.main(["resolve", cid, "--reopen", "--because", "try once more"]) == EXIT_OK
    from crossaudit.config import load
    from crossaudit.controller import StateStore
    cfg = load()
    StateStore(cfg.root / cfg.state_dir / "state.json").escalate(
        cid, "build round budget spent (3)", kind="audit")
    before = (root / "cycles" / "rulings.jsonl").read_bytes()
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    resolutions = sum(1 for h in state["history"] if h.get("event") == "human_resolution")
    install_hook(root, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=root)
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_INTEGRITY
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "ESCALATED"
    assert sum(1 for h in state["history"]
               if h.get("event") == "human_resolution") == resolutions
    assert (root / "cycles" / "rulings.jsonl").read_bytes() == before
    assert git("status", "--porcelain", "--", "cycles", cwd=root) == ""
    assert git("rev-parse", "HEAD", cwd=root) == head


def test_after_a_failed_commit_a_repaired_hook_records_exactly_one_row(
        escalated, monkeypatch, capsys):
    """reopen (commit 1, accepted), the cycle stops again, close (commit 2,
    refused), close again (commit 3, accepted): two rows, one per landed
    commit. Mutation caught: a failed append left in the file -- the log
    would hold three rows, two of them closes."""
    root, cid = escalated
    _on_a_terminal(monkeypatch)
    install_hook(root, SECOND_ONLY_HOOK)
    assert main.main(["resolve", cid, "--reopen", "--because", "try once more"]) == EXIT_OK
    from crossaudit.config import load
    from crossaudit.controller import StateStore
    cfg = load()
    StateStore(cfg.root / cfg.state_dir / "state.json").escalate(
        cid, "build round budget spent (3)", kind="audit")
    log = root / "cycles" / "rulings.jsonl"
    after_first = log.read_bytes()
    head = git("rev-parse", "HEAD", cwd=root)
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_INTEGRITY
    assert log.read_bytes() == after_first
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert main.main(["resolve", cid, "--close", "--because", REASON]) == EXIT_OK
    rows = [json.loads(line) for line in log.read_text().split("\n") if line]
    assert [(r["action"], r["status_after"]) for r in rows] == [
        ("reopen", "OPEN"), ("close", "BLOCKED")]
    assert git("rev-list", "--count", f"{head}..HEAD", cwd=root) == "1"
    assert git("status", "--porcelain", "--", "cycles", cwd=root) == ""
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][cid]["status"] == "BLOCKED"
    assert [h["action"] for h in state["history"]
            if h.get("event") == "human_resolution"] == ["reopen", "close"]


def test_a_rejected_commit_through_resolve_cycle_raises_and_changes_nothing(
        escalated):
    """The TUI's path (`resolve_cycle`, which `tuiapp.rule_on` calls).
    Mutation caught: `resolve_cycle` calling `StateStore.resolve_escalation`
    and `rulings.record` in sequence instead of the one transaction."""
    from crossaudit.config import load
    from crossaudit.errors import IntegrityDenial

    root, cid = escalated
    install_hook(root, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=root)
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "reopen", "try once more")
    assert "could not be committed to the ledger" in denied.value.reason
    assert "the cycle stays ESCALATED and nothing was recorded" in denied.value.reason
    assert_nothing_was_ruled(root, cid, None, head)


def test_a_silent_hook_still_yields_a_legible_reason(escalated):
    """A hook that exits 1 and says nothing: git's stderr is empty, and the
    sentence must still say why. Mutation caught: an empty `why` slot (`()`)."""
    from crossaudit.config import load
    from crossaudit.errors import IntegrityDenial

    root, cid = escalated
    install_hook(root, "#!/bin/sh\nexit 1\n")
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "close", REASON)
    assert "(git commit failed and said nothing)" in denied.value.reason


def test_a_hook_slower_than_the_commit_timeout_fails_the_ruling_inside_the_lock(
        escalated, monkeypatch):
    """The ruling's commit runs under the controller lock, so it has its own
    bound (`rulings.COMMIT_TIMEOUT_S`, 90 s; 2 s here) instead of git's
    240 s. A hook that sleeps past it: the ruling is refused saying it timed
    out, the hook is killed rather than waited for, nothing is recorded, and
    the cycle stays ESCALATED. Since round 4 the killed git's `index.lock`
    is never deleted (it names no owner): the refusal says so, the recovery
    it describes is done here by hand, and the next ruling commits.

    Mutations caught: the commit bounded by git's general timeout (the hook
    finishes after 5 s, exits 0 and the ruling lands -- no denial); killing
    only git and not its process group (the ruling waits out the hook)."""
    import time

    from crossaudit import rulings
    from crossaudit.config import load
    from crossaudit.errors import IntegrityDenial

    root, cid = escalated
    monkeypatch.setattr(rulings, "COMMIT_TIMEOUT_S", 2.0)
    install_hook(root, "#!/bin/sh\nsleep 5\nexit 0\n")
    head = git("rev-parse", "HEAD", cwd=root)
    began = time.monotonic()
    with pytest.raises(IntegrityDenial) as denied:
        main.resolve_cycle(load(), cid, "close", REASON)
    assert time.monotonic() - began < 4.5
    assert denied.value.reason == (
        f"the ruling on cycle {cid} could not be committed to the ledger "
        f"(git commit timed out after 2s); the cycle stays ESCALATED and "
        f"nothing was recorded; .git/index.lock may have been left by the killed "
        f"git — if no git process is running, remove it by hand and run "
        f"`git reset -q -- cycles/rulings.jsonl`")
    gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=root))
    (gitdir / "index.lock").unlink()
    git("reset", "-q", "--", "cycles/rulings.jsonl", cwd=root)
    assert_nothing_was_ruled(root, cid, None, head)
    assert not list(gitdir.glob("next-index-*.lock"))
    install_hook(root, "#!/bin/sh\nexit 0\n")
    result = main.resolve_cycle(load(), cid, "close", REASON)
    assert result["cycle"]["status"] == "BLOCKED"
    assert git("rev-list", "--count", f"{head}..HEAD", cwd=root) == "1"
