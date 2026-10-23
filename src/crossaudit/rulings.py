"""Human rulings on escalations, recorded in the audit ledger (D172 ruling 5).

`crossaudit resolve <cycle> --reopen/--close --because "..."` is the human
answer to an escalation. The README promises "The reason is committed to the
ledger"; it used to live only in the gitignored controller state. A ruling is
now one line appended to ``<ledger>/rulings.jsonl`` -- the same append-only
JSONL shape as ``routing.jsonl`` and ``disputes.jsonl`` beside the receipts --
and committed on its own, with the reason in the commit message.

Append-only: a line is never rewritten or removed, so a second ruling on the
same cycle adds a line and both stay readable, in order. The one exception is
a line whose commit failed: :func:`record` takes it back out before it raises,
so a line that is in the file is a line that is in git. Readers split on
"\\n" only (see D168: ``str.splitlines`` also splits on U+2028/U+2029/U+0085,
which a reason may carry).

One transaction, every surface (review 2026-10-23, findings 1 and 2):
:func:`rule` is how `resolve`, the TUI, `talk`, the console's
``/api/escalation`` (close, reopen, and the provider retry's reopen) and Stop
on a parked run rule on an escalation. It commits the ruling first and changes
the controller state only once the commit has landed
(``StateStore.rule_escalation``), so a failing commit leaves the cycle
ESCALATED with nothing recorded, and a close settles the waiting run the same
way whichever surface it came from.

The commit runs while the controller lock is held, so it is bounded by
:data:`COMMIT_TIMEOUT_S`, well inside the lock's stale threshold
(``controller.state.LOCK_STALE_S``): a hook slower than that is a broken hook,
and the ruling fails rather than letting another process break the lock.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from .app_keys import child_env
from .errors import Denial, IntegrityDenial
from .gitio import git

RULINGS_LOG = "rulings.jsonl"

#: The bound on each git step of a ruling's commit (seconds). It must stay
#: below ``controller.state.LOCK_STALE_S`` (120 s): the commit runs under the
#: controller lock, and a step that outlived the stale threshold would let
#: another process break the lock mid-ruling. Not ``CROSSAUDIT_GIT_TIMEOUT``,
#: which may legitimately be raised for large trees.
COMMIT_TIMEOUT_S = 90.0


def log_path(cfg) -> Path:
    return Path(cfg.root) / cfg.ledger_dir / RULINGS_LOG


def _who(cfg) -> str:
    name = git("config", "user.name", cwd=cfg.root, check=False).strip()
    email = git("config", "user.email", cwd=cfg.root, check=False).strip()
    return f"{name} <{email}>" if email else name


def _git_step(cfg, *args: str) -> None:
    """Run one git step of the commit, bounded by :data:`COMMIT_TIMEOUT_S`.

    On failure raise ``_StepFailed`` with the first line of git's own stderr
    (trimmed), a plain stand-in when git said nothing (a hook that exits 1
    silently), or that it timed out. A timed-out step is killed with its whole
    process group (git and the hook it is running), and the index locks that
    git held are removed: a killed ``git commit`` otherwise leaves
    ``index.lock`` behind and every later git write in the repository fails.
    """
    timeout = COMMIT_TIMEOUT_S
    posix = os.name != "nt"
    try:
        proc = subprocess.Popen(
            ["git", *args], cwd=str(cfg.root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            env=child_env(), start_new_session=posix)
    except OSError as exc:
        raise _StepFailed(f"git {args[0]} could not run: {exc.strerror or exc}") from exc
    try:
        _out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            if posix:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except OSError:
            pass
        proc.communicate()
        _drop_index_locks(cfg, proc.pid)
        raise _StepFailed(f"git {args[0]} timed out after {timeout:g}s") from exc
    if proc.returncode != 0:
        first = (err or "").strip().split("\n")[0].strip()[:160]
        raise _StepFailed(first or f"git {args[0]} failed and said nothing")


def _drop_index_locks(cfg, pid: int) -> None:
    """Remove the locks a git process we just killed was holding.

    ``index.lock`` is held by ``git add``/``git commit`` for their whole run
    (hooks included), so right after killing ours it is ours; a ``git commit
    -- <path>`` also holds ``next-index-<pid>.lock``, named by its pid.
    """
    try:
        gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=cfg.root))
    except (Denial, OSError):
        return
    for name in ("index.lock", f"next-index-{pid}.lock"):
        try:
            (gitdir / name).unlink(missing_ok=True)
        except OSError:
            pass


class _StepFailed(Exception):
    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


def _restore(path: Path, existed: bool, size: int) -> None:
    """Put the log back to the bytes it had before the append."""
    try:
        if not existed:
            path.unlink(missing_ok=True)
        elif path.exists():
            with open(path, "r+b") as fh:
                fh.truncate(size)
    except OSError:
        pass


def record(cfg, cycle: dict, action: str, reason: str) -> dict:
    """Append one ruling and commit exactly that file. Returns the row,
    with the ledger commit that carries it under ``commit``.

    ``status_after`` is the status the ruling SETS (``RESOLUTION_STATUS``),
    derived from ``action``: the row is written before the controller state
    changes (``StateStore.rule_escalation`` applies the change only after this
    returns), so ``cycle`` is the record as it was before the ruling.

    Failure-atomic: if the append, ``git add`` or ``git commit`` fails, the
    log is restored to its previous bytes (or removed if it did not exist),
    the path is unstaged, and ``IntegrityDenial`` says the ruling was not
    committed. Once the commit has landed the ruling is recorded; a
    ``rev-parse`` that then fails leaves ``commit`` empty rather than undoing
    a commit that exists.
    """
    from .controller.state import RESOLUTION_STATUS

    now = time.time()
    row = {
        "cycle_id": cycle["cycle_id"],
        "action": action,
        "reason": reason,
        "by": _who(cfg),
        "t": int(now),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "round": cycle.get("round"),
        "active_sha": cycle.get("active_sha", ""),
        "status_after": RESOLUTION_STATUS.get(action, ""),
        "escalation_reason": str(cycle.get("escalation_reason", ""))[:400],
    }
    path = log_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = path.relative_to(cfg.root).as_posix()
    first = reason.strip().splitlines()[0] if reason.strip() else ""
    subject = f"ruling {cycle['cycle_id']} {action}: {first}"
    if len(subject) > 120:
        subject = subject[:117] + "..."
    existed = path.is_file()
    size = path.stat().st_size if existed else 0
    try:
        try:
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            raise _StepFailed(f"the log could not be written: {exc.strerror or exc}") from exc
        _git_step(cfg, "add", "--", rel)
        # Only this file: anything else the person has staged stays staged.
        _git_step(cfg, "commit", "-q", "-m", subject, "-m",
                  f"Human ruling on escalated cycle {cycle['cycle_id']} "
                  f"(round {cycle.get('round')}, {str(cycle.get('active_sha', ''))[:12]}): "
                  f"{action}.\n\nReason:\n{reason}\n\nBy: {row['by']}\nAt: {row['at']}",
                  "--", rel)
    except _StepFailed as exc:
        _restore(path, existed, size)
        try:
            git("reset", "-q", "--", rel, cwd=cfg.root, check=False)
        except (Denial, OSError):
            pass
        raise IntegrityDenial(
            f"the ruling on cycle {cycle['cycle_id']} could not be committed to the "
            f"ledger ({exc.why}); the cycle stays ESCALATED and nothing was recorded",
            cycle_id=cycle["cycle_id"]) from exc
    try:
        row["commit"] = git("rev-parse", "HEAD", cwd=cfg.root, check=False)
    except (Denial, OSError):
        row["commit"] = ""
    return row


def rule(cfg, store, cycle_id: str, action: str, reason: str) -> dict:
    """A human ruling on an escalated cycle, from any surface.

    ``store`` is the project's ``StateStore``. The ruling is validated and
    committed to ``<ledger>/rulings.jsonl`` first, and the controller state
    changes only once that commit has landed (``StateStore.rule_escalation``);
    a failing commit raises ``IntegrityDenial`` with the cycle still
    ESCALATED and nothing recorded. A close then settles the run that was
    waiting for this decision: the parked (provider) run it references
    (``daemon.settle_closed_escalation``) and a content escalation's
    WAITING_FOR_HUMAN run (:func:`settle_human_wait`). Returns
    ``{"ruling": row, "cycle": cycle}``: the committed row (with ``commit``)
    and the cycle record after the ruling.
    """
    before: dict = {}

    def commit(snapshot: dict) -> dict:
        before.update(snapshot)
        return record(cfg, snapshot, action, reason)

    row, cycle = store.rule_escalation(cycle_id, action, reason, commit)
    if action == "close":
        # The close ruling settles the parked run this escalation references:
        # a stopped task must not keep signalling "needs your decision".
        from .console import daemon

        daemon.settle_closed_escalation(cfg, cycle)
        settle_human_wait(cfg, before, reason)
    return {"ruling": row, "cycle": cycle}


def settle_human_wait(cfg, cycle: dict, reason: str) -> bool:
    """End the run that was WAITING_FOR_HUMAN on the cycle a person closed.

    ``daemon.settle_closed_escalation`` settles a PARKED (provider) run; a
    content escalation leaves its run in WAITING_FOR_HUMAN, which then kept
    reading as waiting after the person had ruled. WAITING_FOR_HUMAN ->
    CANCELLED is the declared edge for exactly this. ``cycle`` is the record
    as it was BEFORE the ruling.

    Which run: the one the escalation references (``escalation_run_id``).
    An escalation the audit ladder recorded (the round budget spent inside
    ``cmd_run``) carries no reference, so the association must be
    corroborated the way the daemon's reconciler does for legacy records:
    the NEWEST run, still waiting, whose start the cycle's last recorded
    activity does not precede, and the same chat when the cycle names one.
    Anything less could cancel an unrelated run.
    """
    from .runtime import RunJournal, journal_path

    runtime = journal_path(cfg)
    if not runtime.is_file():
        return False
    journal = RunJournal(runtime)
    run_id = str(cycle.get("escalation_run_id") or "")
    if not run_id:
        latest = journal.latest()
        if latest is None:
            return False
        touched = float(cycle.get("updated_at") or 0)
        same_chat = (not cycle.get("chat_id")
                     or str(cycle.get("chat_id")) == str(latest.get("chat_id", "")))
        if touched < float(latest.get("started") or 0) - 1 or not same_chat:
            return False
        run_id = str(latest["run_id"])
    return journal.settle_human_wait(
        run_id, f"closed by a human ruling: {reason.strip()[:300]}")


def history(cfg) -> list[dict]:
    path = log_path(cfg)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("cycle_id"):
            rows.append(row)
    return rows


def by_cycle(cfg) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in history(cfg):
        out.setdefault(str(row["cycle_id"]), []).append(row)
    return out
