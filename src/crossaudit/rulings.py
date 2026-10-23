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

RULINGS_LOG = "rulings.jsonl"

#: The budget for a ruling's whole commit transaction (seconds): one
#: deadline, started when the transaction starts under the controller lock,
#: shared by every git step that can run a hook or a filter (``git config``
#: for the author, ``git add``, ``git commit``, ``rev-parse``); each step gets
#: what remains, and a step with nothing left fails at once as timed out. The
#: cleanup after a failure (unstaging, dropping a killed git's index locks)
#: gets :data:`CLEANUP_TIMEOUT_S` per step on top. Together they must stay
#: below ``controller.state.LOCK_STALE_S`` (120 s), or another process could
#: break the lock mid-ruling (review 2026-10-23 round 2, finding 2: the bound
#: used to apply to each step separately, so a slow clean filter plus a slow
#: hook held the lock past it). Not ``CROSSAUDIT_GIT_TIMEOUT``, which may
#: legitimately be raised for large trees.
COMMIT_TIMEOUT_S = 90.0

#: Per-step bound on the cleanup after a failed commit (two steps at most).
CLEANUP_TIMEOUT_S = 5.0


def log_path(cfg) -> Path:
    return Path(cfg.root) / cfg.ledger_dir / RULINGS_LOG


def _who(cfg, deadline: float) -> str:
    name = _bounded(cfg, ("config", "user.name"), deadline)[1].strip()
    email = _bounded(cfg, ("config", "user.email"), deadline)[1].strip()
    return f"{name} <{email}>" if email else name


def _remaining(deadline: float) -> float:
    return deadline - time.monotonic()


def _bounded(cfg, args: tuple[str, ...], deadline: float) -> tuple[int, str, str]:
    """Run one git step with whatever is left until ``deadline``.

    Returns ``(returncode, stdout, stderr)``. Raises ``_StepFailed`` when the
    step cannot run or runs out of time; a step with no time left fails
    without starting. A timed-out step is killed with its whole process group
    (git and the hook or filter it is running), and the index locks that git
    held are removed: a killed ``git commit`` otherwise leaves ``index.lock``
    behind and every later git write in the repository fails.
    """
    timeout = _remaining(deadline)
    if timeout <= 0:
        raise _StepFailed(f"git {args[0]} timed out after {COMMIT_TIMEOUT_S:g}s")
    posix = os.name != "nt"
    try:
        proc = subprocess.Popen(
            ["git", *args], cwd=str(cfg.root), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            env=child_env(), start_new_session=posix)
    except OSError as exc:
        raise _StepFailed(f"git {args[0]} could not run: {exc.strerror or exc}") from exc
    try:
        out, err = proc.communicate(timeout=timeout)
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
        raise _StepFailed(f"git {args[0]} timed out after {COMMIT_TIMEOUT_S:g}s") from exc
    return proc.returncode, out or "", err or ""


def _git_step(cfg, deadline: float, *args: str) -> None:
    """One git step of the commit; a non-zero exit raises ``_StepFailed``
    with the first line of git's own stderr (trimmed), or a plain stand-in
    when git said nothing (a hook that exits 1 silently)."""
    code, _out, err = _bounded(cfg, args, deadline)
    if code != 0:
        first = err.strip().split("\n")[0].strip()[:160]
        raise _StepFailed(first or f"git {args[0]} failed and said nothing")


def _cleanup_git(cfg, *args: str) -> str:
    """A cleanup step after a failure, bounded on its own (CLEANUP_TIMEOUT_S)."""
    try:
        return _bounded(cfg, args, time.monotonic() + CLEANUP_TIMEOUT_S)[1].strip()
    except _StepFailed:
        return ""


def _drop_index_locks(cfg, pid: int) -> None:
    """Remove the locks a git process we just killed was holding.

    ``index.lock`` is held by ``git add``/``git commit`` for their whole run
    (hooks included), so right after killing ours it is ours; a ``git commit
    -- <path>`` also holds ``next-index-<pid>.lock``, named by its pid.
    """
    try:
        found = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"], cwd=str(cfg.root),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=child_env(), timeout=CLEANUP_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return
    if found.returncode != 0 or not found.stdout.strip():
        return
    gitdir = Path(found.stdout.strip())
    for name in ("index.lock", f"next-index-{pid}.lock"):
        try:
            (gitdir / name).unlink(missing_ok=True)
        except OSError:
            pass


class _StepFailed(Exception):
    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


def _restore(path: Path, prior: bytes | None) -> None:
    """Put the log back to exactly ``prior`` (or remove it when ``prior`` is
    None: it did not exist). Raises OSError when that cannot be done.

    The bytes, not a length: a rejecting hook may rewrite, replace, append to
    or delete the log before it fails, and truncating to the old length kept
    whatever it wrote (review 2026-10-23 round 2, finding 1). The restore
    writes a sibling temporary file, fsyncs it and ``os.replace``s it over the
    log, so the log is never half-restored.
    """
    if prior is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.restore-{os.getpid()}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(prior)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    if os.name != "nt":
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def record(cfg, cycle: dict, action: str, reason: str, *,
           deadline: float | None = None) -> dict:
    """Append one ruling and commit exactly that file. Returns the row,
    with the ledger commit that carries it under ``commit``.

    ``status_after`` is the status the ruling SETS (``RESOLUTION_STATUS``),
    derived from ``action``: the row is written before the controller state
    changes (``StateStore.rule_escalation`` applies the change only after this
    returns), so ``cycle`` is the record as it was before the ruling.

    ``deadline`` (``time.monotonic()``) bounds every git step of the
    transaction together; by default it is :data:`COMMIT_TIMEOUT_S` from now.

    Failure-atomic: the log's exact bytes are kept before the append; if the
    append, ``git add`` or ``git commit`` fails (or runs out of time), the log
    is restored to those bytes (or removed if it did not exist), the path is
    unstaged, and ``IntegrityDenial`` says the ruling was not committed. If
    the restore itself fails, a different ``IntegrityDenial`` says so and does
    not claim nothing changed. Once the commit has landed the ruling is
    recorded; a ``rev-parse`` that then fails leaves ``commit`` empty rather
    than undoing a commit that exists.
    """
    from .controller.state import RESOLUTION_STATUS

    if deadline is None:
        deadline = time.monotonic() + COMMIT_TIMEOUT_S
    path = log_path(cfg)
    rel = path.relative_to(cfg.root).as_posix()
    cid = cycle["cycle_id"]
    try:
        prior = path.read_bytes() if path.is_file() else None
    except OSError as exc:
        # Nothing has been written yet, so nothing needs restoring.
        raise IntegrityDenial(
            f"the ruling on cycle {cid} could not be committed to the ledger "
            f"(the log could not be read: {exc.strerror or exc}); the cycle stays "
            f"ESCALATED and nothing was recorded", cycle_id=cid) from exc
    first = reason.strip().splitlines()[0] if reason.strip() else ""
    subject = f"ruling {cid} {action}: {first}"
    if len(subject) > 120:
        subject = subject[:117] + "..."
    try:
        now = time.time()
        row = {
            "cycle_id": cid,
            "action": action,
            "reason": reason,
            "by": _who(cfg, deadline),
            "t": int(now),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "round": cycle.get("round"),
            "active_sha": cycle.get("active_sha", ""),
            "status_after": RESOLUTION_STATUS.get(action, ""),
            "escalation_reason": str(cycle.get("escalation_reason", ""))[:400],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            raise _StepFailed(f"the log could not be written: {exc.strerror or exc}") from exc
        _git_step(cfg, deadline, "add", "--", rel)
        # Only this file: anything else the person has staged stays staged.
        _git_step(cfg, deadline, "commit", "-q", "-m", subject, "-m",
                  f"Human ruling on escalated cycle {cid} "
                  f"(round {cycle.get('round')}, {str(cycle.get('active_sha', ''))[:12]}): "
                  f"{action}.\n\nReason:\n{reason}\n\nBy: {row['by']}\nAt: {row['at']}",
                  "--", rel)
    except _StepFailed as exc:
        try:
            _restore(path, prior)
        except OSError as lost:
            _cleanup_git(cfg, "reset", "-q", "--", rel)
            raise IntegrityDenial(
                f"the ruling on cycle {cid} could not be committed to the ledger "
                f"({exc.why}), and {rel} could not be restored "
                f"({lost.strerror or lost}); the cycle stays ESCALATED, but check "
                f"{rel} against git before ruling again", cycle_id=cid) from exc
        _cleanup_git(cfg, "reset", "-q", "--", rel)
        raise IntegrityDenial(
            f"the ruling on cycle {cid} could not be committed to the "
            f"ledger ({exc.why}); the cycle stays ESCALATED and nothing was recorded",
            cycle_id=cid) from exc
    # The commit has landed; reading its hash is cleanup-bounded, not
    # deadline-bounded, so a transaction that used its budget still reports it.
    row["commit"] = _cleanup_git(cfg, "rev-parse", "HEAD")
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
    landed: dict = {}

    def commit(snapshot: dict) -> dict:
        # The budget starts here, with the controller lock held.
        before.update(snapshot)
        row = record(cfg, snapshot, action, reason,
                     deadline=time.monotonic() + COMMIT_TIMEOUT_S)
        landed.update(row)
        return row

    try:
        row, cycle = store.rule_escalation(cycle_id, action, reason, commit)
    except Denial as exc:
        if exc.detail.get("issue") != "lock_taken_over" or not landed:
            raise
        # The commit landed, but the lock was broken and taken while it ran,
        # so the state change was discarded (never written over newer state).
        raise IntegrityDenial(
            f"the ruling on cycle {cycle_id} was committed to the ledger "
            f"({str(landed.get('commit', ''))[:12]}), but the controller lock was "
            f"taken over before the cycle's state could change, so the cycle stays "
            f"ESCALATED; rule on it again", cycle_id=cycle_id,
            issue="lock_taken_over") from exc
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
