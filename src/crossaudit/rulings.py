"""Human rulings on escalations, recorded in the audit ledger (D172 ruling 5).

`crossaudit resolve <cycle> --reopen/--close --because "..."` is the human
answer to an escalation. The README promises "The reason is committed to the
ledger"; it used to live only in the gitignored controller state. A ruling is
now one line appended to ``<ledger>/rulings.jsonl`` -- the same append-only
JSONL shape as ``routing.jsonl`` and ``disputes.jsonl`` beside the receipts --
and committed on its own, with the reason in the commit message.

Append-only: a line is never rewritten or removed, so a second ruling on the
same cycle adds a line and both stay readable, in order. The one exception is
a line whose commit failed: :func:`record` puts the log's prior bytes back
before it raises. So once :func:`record` has returned, every line in the file
is in git; DURING a ruling the file holds the new line before it is committed
(the append precedes ``git add``), and a concurrent :func:`history` may read
that provisional line. Readers split on
"\\n" only (see D168: ``str.splitlines`` also splits on U+2028/U+2029/U+0085,
which a reason may carry).

One ruling path, every surface (review 2026-10-23, findings 1 and 2; D176
rulings 30 to 32): :func:`rule` is how `resolve`, the TUI, `talk`, the
console's ``/api/escalation`` (close, reopen, and the provider retry's
reopen) and Stop on a parked run rule on an escalation. A ruling's commit and
its state change are two phases joined by a local intent in the controller
state, all under the controller lock: the intent is written, the row is
committed, then the state changes and the intent is cleared. A failing commit
records nothing and leaves the cycle ESCALATED; a state write that fails
after the commit is recovered from the intent at the next ruling on that
cycle; the person is told at each step what was and was not recorded. A
close settles the waiting run the same way whichever surface it came from.

The commit runs while the controller lock is held, so it is bounded by
:data:`COMMIT_TIMEOUT_S`: a hook slower than that is a broken hook, and the
ruling fails rather than keeping every other process waiting on the lock
(whose acquirers give up after ``controller.state.LOCK_TIMEOUT_S``).

The log must be a regular file inside the repository (review round 3,
finding 1): ``open()`` follows a symlink while ``git add`` commits the link
itself, so a symlinked log or directory committed only a pathname. Both are
refused, the log is opened with ``O_NOFOLLOW`` where the platform has it, and
after the commit lands the committed blob is read back and must end with this
ruling's row before the state changes.
"""
from __future__ import annotations

import errno
import json
import os
import signal
import stat
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
#: gets :data:`CLEANUP_TIMEOUT_S` per step on top, so a ruling holds the
#: controller lock for a bounded time (review 2026-10-23 round 2, finding 2:
#: the bound used to apply to each step separately, so a slow clean filter
#: plus a slow hook held the lock far longer). Since round 4 the lock is
#: kernel-held and cannot be taken from a live holder at all; the bound is
#: what keeps other processes from waiting on a broken hook indefinitely
#: (they give up after ``controller.state.LOCK_TIMEOUT_S``). Not
#: ``CROSSAUDIT_GIT_TIMEOUT``, which may legitimately be raised for large trees.
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
    """:func:`_bounded_bytes` with stdout and stderr decoded as UTF-8."""
    code, out, err = _bounded_bytes(cfg, args, deadline)
    return code, out.decode("utf-8", "replace"), err


def _bounded_bytes(cfg, args: tuple[str, ...], deadline: float) -> tuple[int, bytes, str]:
    """Run one git step with whatever is left until ``deadline``.

    Returns ``(returncode, stdout bytes, stderr text)``. Raises
    ``_StepFailed`` when the step cannot run or runs out of time; a step with
    no time left fails without starting. A timed-out step is killed with its
    whole process group (git and the hook or filter it is running), and the
    index locks that git held are removed: a killed ``git commit`` otherwise
    leaves ``index.lock`` behind and every later git write in the repository
    fails.

    Output goes to temporary files, not pipes, and the bound is on the
    process's exit, not on end-of-file: a hook may leave a detached (setsid)
    child holding git's stdout/stderr, and reading a pipe to its end waited
    for that child long after git was gone (review round 3, finding 3).
    """
    import tempfile

    timeout = _remaining(deadline)
    if timeout <= 0:
        raise _StepFailed(f"git {args[0]} timed out after {COMMIT_TIMEOUT_S:g}s")
    posix = os.name != "nt"
    with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
        try:
            proc = subprocess.Popen(
                ["git", *args], cwd=str(cfg.root), stdin=subprocess.DEVNULL,
                stdout=out_f, stderr=err_f, env=child_env(), start_new_session=posix)
        except OSError as exc:
            raise _StepFailed(f"git {args[0]} could not run: {exc.strerror or exc}") from exc
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                if posix:
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=CLEANUP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                pass
            left = _drop_index_locks(cfg, proc.pid)
            raise _StepFailed(f"git {args[0]} timed out after {COMMIT_TIMEOUT_S:g}s",
                              index_lock_left=left) from exc
        out_f.seek(0)
        err_f.seek(0)
        return (proc.returncode, out_f.read(),
                err_f.read().decode("utf-8", "replace"))


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


def _drop_index_locks(cfg, pid: int) -> bool:
    """After killing our git: remove only the lock named by its pid.

    ``next-index-<pid>.lock`` (held by ``git commit -- <path>``) carries the
    killed process's pid in its name, so it is demonstrably ours. ``index.lock``
    carries no owner identity: another git writer may have taken it between
    the kill and this cleanup, and deleting it would defeat git's own
    serialization (review 2026-10-23 round 4, finding 2). It is never
    removed; returns True when it exists afterwards, so the refusal can say
    it may have been left by the killed git.
    """
    try:
        found = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"], cwd=str(cfg.root),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=child_env(), timeout=CLEANUP_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if found.returncode != 0 or not found.stdout.strip():
        return False
    gitdir = Path(found.stdout.strip())
    try:
        (gitdir / f"next-index-{pid}.lock").unlink(missing_ok=True)
    except OSError:
        pass
    return (gitdir / "index.lock").exists()


class _StepFailed(Exception):
    def __init__(self, why: str, *, index_lock_left: bool = False) -> None:
        super().__init__(why)
        self.why = why
        #: A timed-out git was killed and ``.git/index.lock`` exists after it.
        self.index_lock_left = index_lock_left


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


#: ``O_NOFOLLOW`` where the platform has it (POSIX); 0 elsewhere, where the
#: lstat check in :func:`_refuse_symlinks` is the only guard.
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _is_loop(exc: OSError) -> bool:
    import errno

    return exc.errno in (errno.ELOOP, getattr(errno, "EMLINK", -1)) and bool(_NOFOLLOW)


def _symlink_denial(rel: str, cid: str) -> IntegrityDenial:
    return IntegrityDenial(
        f"{rel} (or its directory) is a symbolic link; the rulings log must be a "
        f"regular file inside the repository, so the ruling was not recorded",
        cycle_id=cid, issue="symlinked_log")


def _refuse_symlinks(cfg, rel: str, cid: str) -> None:
    """``os.lstat`` every component below ``cfg.root`` down to the log; a
    symlink anywhere there is refused before anything is read or written.
    (``cfg.root`` itself may be reached through a link, e.g. macOS's
    ``/tmp``; that is the repository, not a component of the log's path.)"""
    current = Path(cfg.root)
    for part in Path(rel).parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise _symlink_denial(rel, cid)


def _read_nofollow(path: Path) -> bytes | None:
    """The log's bytes, or None when it does not exist; never via a link."""
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(fd)


def _confirm_committed(cfg, path: Path, rel: str, row: dict, deadline: float) -> None:
    """The committed blob must end with this ruling's row.

    A clean filter, or a hook that rewrote and re-staged the file, can make
    the commit carry something other than the line that was appended. The
    blob is read raw (``git cat-file blob HEAD:<rel>``: no filters, no
    textconv), bounded by what remains of the deadline but never less than
    :data:`CLEANUP_TIMEOUT_S`. If its last line is not this row (same
    ``cycle_id``, ``action``, ``reason``, ``t``), ``IntegrityDenial`` is raised
    and the controller state is not changed. The commit is NOT undone (the
    ledger is append-only); the working file is set to the committed bytes so
    it carries no line git does not have.
    """
    floor = time.monotonic() + CLEANUP_TIMEOUT_S
    changed = "a filter or hook changed the file"
    why = changed
    blob = b""
    try:
        code, blob, err = _bounded_bytes(
            cfg, ("cat-file", "blob", f"HEAD:{rel}"), max(deadline, floor))
        if code != 0:
            said = err.strip().split("\n")[0][:120] if err.strip() else "git said nothing"
            why = f"it could not be read back: {said}"
        else:
            lines = [ln for ln in blob.decode("utf-8").split("\n") if ln.strip()]
            got = json.loads(lines[-1]) if lines else None
            if isinstance(got, dict) and all(
                    got.get(k) == row[k] for k in ("cycle_id", "action", "reason", "t")):
                return
    except _StepFailed as exc:
        why = f"it could not be read back: {exc.why}"
    except (ValueError, UnicodeDecodeError):
        pass
    cid, sha = row["cycle_id"], str(row.get("commit", ""))[:12]
    if why == changed:
        try:
            _restore(path, blob)
        except OSError:
            pass
        raise IntegrityDenial(
            f"the ruling on cycle {cid} was committed as {sha}, but the committed "
            f"{rel} could not be confirmed to contain it (a filter or hook changed "
            f"the file); the cycle stays ESCALATED — check the repository's filters "
            f"and hooks before ruling again", cycle_id=cid, issue="ruling_not_in_commit")
    raise IntegrityDenial(
        f"the ruling on cycle {cid} was committed as {sha}, but the committed "
        f"{rel} could not be confirmed to contain it (it could not be read back: "
        f"{why.removeprefix('it could not be read back: ')}); the cycle stays "
        f"ESCALATED — check the repository's filters and hooks before ruling again",
        cycle_id=cid, issue="ruling_not_in_commit")


def record(cfg, cycle: dict, action: str, reason: str, *,
           intent: str, store, deadline: float | None = None) -> dict:
    """Append one ruling and commit exactly that file. Returns the row,
    with the ledger commit that carries it under ``commit``.

    ``status_after`` is the status the ruling SETS (``RESOLUTION_STATUS``),
    derived from ``action``: the row is written before the controller state
    changes (``StateStore.rule_escalation`` applies the change only after this
    returns), so ``cycle`` is the record as it was before the ruling.

    ``deadline`` (``time.monotonic()``) bounds every git step of the
    transaction together; by default it is :data:`COMMIT_TIMEOUT_S` from now.

    ``intent`` is the nonce of the local ruling intent ``store`` records for
    this cycle (phase 1 of ``StateStore.rule_escalation``; D176 ruling 30).
    The row carries it, and a nonce that is not the cycle's current intent is
    refused before anything is written: only this controller's own intent
    can become a row it will later act on.

    The log's exact bytes are kept before the append; if the
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
    current = store.current_intent(cid) if store is not None else None
    if not intent or not current or current.get("nonce") != intent:
        raise IntegrityDenial(
            f"the ruling on cycle {cid} does not match the intent this controller "
            f"recorded for it; nothing was recorded", cycle_id=cid,
            issue="intent_mismatch")
    _refuse_symlinks(cfg, rel, cid)
    try:
        prior = _read_nofollow(path)
    except OSError as exc:
        if _is_loop(exc):
            raise _symlink_denial(rel, cid) from exc
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
        # The local intent's nonce (D176 ruling 30): recovery applies a
        # committed row only when it carries the nonce of an intent this
        # controller wrote; any other row is never acted on (ruling 31).
        row["intent"] = intent
        if cycle.get("escalated_at") is not None:
            row["escalated_at"] = cycle["escalated_at"]   # informational
        line = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _NOFOLLOW, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        except OSError as exc:
            if _is_loop(exc):
                raise _symlink_denial(rel, cid) from exc
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
        if exc.index_lock_left:
            raise IntegrityDenial(
                f"the ruling on cycle {cid} could not be committed to the "
                f"ledger ({exc.why}); the cycle stays ESCALATED and nothing was "
                f"recorded; .git/index.lock may have been left by the killed git — if "
                f"no git process is running, remove it by hand and run "
                f"`git reset -q -- {rel}`",
                cycle_id=cid) from exc
        raise IntegrityDenial(
            f"the ruling on cycle {cid} could not be committed to the "
            f"ledger ({exc.why}); the cycle stays ESCALATED and nothing was recorded",
            cycle_id=cid) from exc
    # The commit has landed; reading its hash is cleanup-bounded, not
    # deadline-bounded, so a transaction that used its budget still reports it.
    row["commit"] = _cleanup_git(cfg, "rev-parse", "HEAD")
    _confirm_committed(cfg, path, rel, row, deadline)
    return row


def committed_rows(cfg, *, strict: bool = False) -> list[dict]:
    """The ruling rows in the COMMITTED log (the blob at HEAD), not the
    working file, so a provisional line during another ruling is not read.

    ``strict`` (recovery, D176 ruling 30): a log that is in HEAD but cannot
    be read or parsed raises ``IntegrityDenial``; it is never "no rows". A
    repository with no commit yet, or whose HEAD has no rulings log, has no
    committed rows. Not strict (``status``, read-only): any failure reads as
    no rows.
    """
    rel = log_path(cfg).relative_to(cfg.root).as_posix()

    def refuse(why: str) -> IntegrityDenial:
        return IntegrityDenial(
            f"the committed rulings log could not be read ({why}); no ruling is made "
            f"until it can be", issue="rulings_unreadable")

    try:
        code, _out, _err = _bounded(cfg, ("rev-parse", "--verify", "-q", "HEAD"),
                                    time.monotonic() + CLEANUP_TIMEOUT_S)
        if code != 0:
            return []                                   # no commit yet
        code, listed, err = _bounded(cfg, ("ls-tree", "HEAD", "--", rel),
                                     time.monotonic() + CLEANUP_TIMEOUT_S)
        if code != 0:
            if strict:
                raise refuse(err.strip().split("\n")[0][:120] or "git ls-tree failed")
            return []
        if not listed.strip():
            return []                                   # no rulings log at HEAD
        code, blob, err = _bounded_bytes(cfg, ("cat-file", "blob", f"HEAD:{rel}"),
                                         time.monotonic() + CLEANUP_TIMEOUT_S)
    except _StepFailed as exc:
        if strict:
            raise refuse(exc.why) from exc
        return []
    if code != 0:
        if strict:
            raise refuse(err.strip().split("\n")[0][:120] or "git cat-file failed")
        return []
    rows = []
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        if strict:
            raise refuse("it is not UTF-8") from exc
        return []
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            if strict:
                raise refuse("a line is not JSON") from exc
            continue
        if isinstance(row, dict) and row.get("cycle_id"):
            rows.append(row)
        elif strict:
            raise refuse("a line is not a ruling")
    return rows


def foreign_rows(cycle_id: str, cycle: dict, rows: list[dict]) -> list[dict]:
    """Committed rows on an ESCALATED cycle that this controller did not
    make and the state does not reflect (D176 ruling 31), for ``status``
    only; they are never applied. A row is this controller's when its
    ``intent`` is one the cycle records in ``ruling_intents`` or is the
    cycle's pending intent. A row that names an earlier escalation of the
    cycle (its informational ``escalated_at`` differs from the cycle's) is
    history, not a claim on the current stop, and is not listed."""
    if cycle.get("status") != "ESCALATED":
        return []
    known = set(cycle.get("ruling_intents") or [])
    out = []
    for row in rows:
        if str(row.get("cycle_id")) != cycle_id or row.get("intent") in known:
            continue
        if (row.get("escalated_at") is not None and cycle.get("escalated_at") is not None
                and row.get("escalated_at") != cycle.get("escalated_at")):
            continue
        out.append(row)
    return out


def commit_of(cfg, row: dict) -> str:
    """The sha of the commit that carries ``row`` (its subject names the
    cycle and the action; the latest such commit touching the log)."""
    rel = log_path(cfg).relative_to(cfg.root).as_posix()
    line = json.dumps({k: v for k, v in row.items() if k != "commit"},
                      ensure_ascii=False, sort_keys=True)
    # The commit that added this exact line (as record() serialises it);
    # else the latest commit whose subject names the cycle and the action.
    return (_cleanup_git(cfg, "log", "-n", "1", "--format=%H", "-S", line, "--", rel)
            or _cleanup_git(cfg, "log", "-n", "1", "--format=%H", "--fixed-strings",
                            f"--grep=ruling {row.get('cycle_id')} {row.get('action')}:",
                            "--", rel))


def rule(cfg, store, cycle_id: str, action: str, reason: str) -> dict:
    """A human ruling on an escalated cycle, from any surface.

    Two phases joined by a local intent, under the controller lock
    (``StateStore.rule_escalation``; D176 ruling 30): the intent is written
    to the local state store, the row (carrying the intent's nonce) is
    appended and committed (:func:`record`), and the state change is applied
    with the intent cleared. A commit that fails records nothing and the
    cycle stays ESCALATED. A state write that fails after the commit is
    refused with a sentence naming the committed sha; the intent stays, and
    the next ruling on that cycle applies the committed row (returned with
    ``reconciled: True``, no new row) or, if the person asked for the other
    action, applies it and refuses the request. An intent that never reached
    a commit is cleared and the new ruling proceeds (``intent_cleared``).
    A close settles the run that was waiting for this decision. Returns
    ``{"ruling": row, "cycle": cycle}`` plus those flags.
    """
    landed: dict = {}

    def commit(snapshot: dict, nonce: str) -> dict:
        # The budget starts here, with the controller lock held.
        row = record(cfg, snapshot, action, reason, intent=nonce, store=store,
                     deadline=time.monotonic() + COMMIT_TIMEOUT_S)
        landed.update(row)
        return row

    try:
        outcome = store.rule_escalation(
            cycle_id, action, reason, commit,
            read_committed=lambda: committed_rows(cfg, strict=True),
            by=_who(cfg, time.monotonic() + CLEANUP_TIMEOUT_S))
    except Denial as exc:
        if not landed or exc.detail.get("issue") != "state_unwritable":
            raise
        cause = exc.__cause__
        if isinstance(cause, OSError):
            name = errno.errorcode.get(cause.errno or 0, str(cause.errno))
            why = cause.strerror or str(cause)
        else:
            name, why = "?", exc.reason
        raise IntegrityDenial(
            f"the ruling on cycle {cycle_id} was committed to the ledger as "
            f"{str(landed.get('commit', ''))[:12]}, but the cycle's state could not "
            f"be written ({name}: {why}); the state is unchanged, and the next ruling "
            f"on this cycle applies the committed ruling",
            cycle_id=cycle_id, issue="ruling_committed_state_pending") from exc
    row, cycle = outcome["row"], outcome["cycle"]
    if outcome["reconciled"]:
        row = dict(row)
        row["commit"] = commit_of(cfg, row)
        _settle(cfg, str(row["action"]), outcome["before"], cycle,
                str(row.get("reason", "")))
        if row["action"] != action:
            raise IntegrityDenial(
                f"a committed ruling ({row['action']}, {row['commit'][:12]}) already "
                f"stands for cycle {cycle_id}; the state now reflects it",
                cycle_id=cycle_id, issue="committed_ruling_stands")
        return {"ruling": row, "cycle": cycle, "reconciled": True}
    _settle(cfg, action, outcome["before"], cycle, reason)
    result = {"ruling": row, "cycle": cycle}
    if outcome["intent_cleared"]:
        result["intent_cleared"] = True
    return result


def _settle(cfg, action: str, before: dict, cycle: dict, reason: str) -> None:
    if action == "close":
        # The close ruling settles the parked run this escalation references:
        # a stopped task must not keep signalling "needs your decision".
        from .console import daemon

        daemon.settle_closed_escalation(cfg, cycle)
        settle_human_wait(cfg, before, reason)


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
