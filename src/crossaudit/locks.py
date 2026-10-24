"""The kernel-held file lock behind the controller and the evidence ledger.

Review 2026-10-23 rounds 3 and 4 (finding 1 of each): every scheme that
decides ownership by reading a lock file and then deletes it by pathname has
a window in which another process releases and a third creates a fresh lock
that is then deleted -- "observe stale, then unlink" (round 3) and "check my
token, then unlink" (round 4) alike. So ownership is no longer a file's
existence or contents:

* The lock file is opened ``O_CREAT | O_RDWR`` and **never unlinked**; it may
  persist as an inert file between holders.
* Holding the lock is holding ``fcntl.flock(fd, LOCK_EX)`` on that open file
  (``msvcrt.locking`` on Windows). Release is unlock + close. The kernel
  releases it when the holder exits or is killed, so a dead holder leaves no
  stale lock and nothing ever needs breaking or removing.
* After the lock is obtained, ``fstat(fd)`` and ``stat(path)`` must name the
  same inode; if the file was replaced between ``open`` and ``flock`` the
  acquirer releases and retries, so it never proceeds on an orphaned inode.
* The owner token (pid, time, nonce) written into the file after
  acquisition is for ``doctor``'s report only; the kernel decides ownership.

What this does and does not guarantee (review 2026-10-23 round 5): CrossAudit
itself never unlinks a lock file (test-enforced:
``tests/test_kernel_held_locks.py``). The lock serialises CrossAudit's own
processes. It does not defend against a writer with access to
``.crossaudit/``, who could as easily edit ``state.json`` or the evidence
ledger directly. A lock file replaced from outside is detected at
acquisition, and again immediately before each protected write
(:meth:`HeldLock.still_current`, called by the controller before writing
state and by the ledger before appending), except within the microseconds
between that check and the write itself.

File descriptors are opened non-inheritable (Python's default), so a child
process (git, a hook) never holds the lock after its parent is gone. A plain
``os.fork()`` without exec shares the lock with the child until the child
exits; nothing in CrossAudit forks while holding one.

A filesystem that cannot provide the lock at all (``ENOLCK`` and ``ENOTSUP``
on some network filesystems, a lock file that cannot be opened, no locking
backend) is refused with a ``ConfigDenial`` naming the path and the error,
never a bare ``OSError``.
"""
from __future__ import annotations

import errno
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from .errors import ConfigDenial, IntegrityDenial

try:  # POSIX
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None

try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - POSIX
    _msvcrt = None

#: On Windows the byte-range lock sits far past the token, so a reader (doctor)
#: can still read the pid at offset 0 while the lock is held. Unverified on
#: Windows in this repository's CI.
_WIN_LOCK_OFFSET = 1 << 20

#: How long an acquirer sleeps between non-blocking attempts.
_POLL_S = 0.02


def new_token() -> str:
    """The owner token written into a held lock file, for reporting only."""
    return f"{os.getpid()} {time.time():.0f} {secrets.token_hex(8)}"


def _try_lock(fd: int) -> bool:
    """One non-blocking exclusive attempt; True when obtained."""
    try:
        if _fcntl is not None:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        if _msvcrt is not None:  # pragma: no cover - Windows
            os.lseek(fd, _WIN_LOCK_OFFSET, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
            return True
    except OSError as exc:
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES,
                         getattr(errno, "EDEADLK", -1)):
            return False
        raise
    raise OSError(errno.ENOSYS, "no file locking on this platform")


def _unlock(fd: int) -> None:
    try:
        if _fcntl is not None:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        elif _msvcrt is not None:  # pragma: no cover - Windows
            os.lseek(fd, _WIN_LOCK_OFFSET, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def _same_file(fd: int, path: Path) -> bool:
    try:
        held, named = os.fstat(fd), os.stat(path)
    except OSError:
        return False
    return (held.st_dev, held.st_ino) == (named.st_dev, named.st_ino)


class HeldLock:
    """An exclusive lock on ``path`` held through an open file descriptor.

    Use :func:`acquire`; release with :meth:`release` or as a context
    manager. Releasing twice is harmless.
    """

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd: int | None = fd

    def still_current(self) -> bool:
        """Whether ``path`` still names the file this lock is held on
        (``fstat(fd)`` against ``stat(path)``, device and inode)."""
        return self.fd is not None and _same_file(self.fd, self.path)

    def require_current(self) -> None:
        """Refuse a protected write when the lock file was replaced after
        acquisition: another process may now hold a lock on the replacement
        and be writing. Called immediately before each write; the window
        between this check and the write is the few microseconds between two
        system calls."""
        if not self.still_current():
            raise IntegrityDenial(
                f"the lock file {self.path} was replaced while this process held "
                f"the lock; this process's change was discarded",
                issue="lock_replaced", lock=str(self.path))

    def release(self) -> None:
        fd, self.fd = self.fd, None
        if fd is None:
            return
        _unlock(fd)
        os.close(fd)

    def __enter__(self) -> "HeldLock":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def acquire(path: Path, timeout: float,
            busy: Callable[[int | None], Exception]) -> HeldLock:
    """Take the exclusive lock on ``path``, waiting up to ``timeout`` seconds.

    When it stays held by another open file for the whole wait, raise
    ``busy(pid)``, where ``pid`` is the holder's pid as its token records it
    (None when unreadable). The lock file is created if missing and never
    removed.
    """
    path = Path(path)
    ensure_directory(path.parent, "the lock file")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        except OSError as exc:
            raise _unsupported(path, exc) from exc
        try:
            try:
                obtained = _try_lock(fd)
            except OSError as exc:
                raise _unsupported(path, exc) from exc
            if obtained:
                if _same_file(fd, path):
                    _write_token(fd)
                    return HeldLock(path, fd)
                # Replaced between open and flock: this inode is no longer
                # the lock anyone else will take. Release it and retry.
                _unlock(fd)
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)
        if time.monotonic() > deadline:
            raise busy(holder_pid(path))
        time.sleep(_POLL_S)


def ensure_directory(path: Path, what: str) -> None:
    """``mkdir(parents=True, exist_ok=True)`` for the directory that holds
    ``what`` (the controller state, the evidence ledger, a lock file), with
    any ``OSError`` -- a regular file where the directory should be, no
    permission, a read-only filesystem -- turned into a ``ConfigDenial``
    rather than a traceback (review 2026-10-23 round 6, finding 1)."""
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        name = errno.errorcode.get(exc.errno or 0, str(exc.errno))
        why = exc.strerror or str(exc)
        # One literal sentence per kind of file, so each is translated whole.
        if what == "the controller state":
            raise ConfigDenial(
                f"the directory {path} for the controller state could not be "
                f"created ({name}: {why}); check the path is a directory you "
                f"can write", issue="directory_unavailable", path=str(path)) from exc
        if what == "the evidence ledger":
            raise ConfigDenial(
                f"the directory {path} for the evidence ledger could not be "
                f"created ({name}: {why}); check the path is a directory you "
                f"can write", issue="directory_unavailable", path=str(path)) from exc
        raise ConfigDenial(
            f"the directory {path} for the lock file could not be created "
            f"({name}: {why}); check the path is a directory you can write",
            issue="directory_unavailable", path=str(path)) from exc


def _unsupported(path: Path, exc: OSError) -> ConfigDenial:
    """A lock service that is missing or refuses (not contention)."""
    name = errno.errorcode.get(exc.errno or 0, str(exc.errno))
    return ConfigDenial(
        f"this filesystem cannot provide the exclusive lock CrossAudit needs at "
        f"{path} ({name}: {exc.strerror or exc}); use a project directory on a "
        f"local filesystem", issue="lock_unsupported", lock=str(path))


def _write_token(fd: int) -> None:
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, new_token().encode())
    except OSError:
        pass  # the token is a report, never the ownership


def holder_pid(path: Path) -> int | None:
    """The pid the lock file's token records, or None."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    head = text.split(" ", 1)[0].strip()
    return int(head) if head.isdigit() else None


def pid_alive(pid: int | None) -> bool | None:
    """``os.kill(pid, 0)``: False only on ESRCH, True when it exists (EPERM
    included), None when there is no pid to ask about."""
    if pid is None or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def status(path: Path) -> dict | None:
    """Whether ``path`` is held right now, for `doctor`: None when free (or
    the file does not exist), else ``{"path", "pid", "alive"}``. Read-only: it
    never creates the file; it probes with a non-blocking lock on a second
    open file and releases at once."""
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        if _try_lock(fd):
            _unlock(fd)
            return None
    finally:
        os.close(fd)
    pid = holder_pid(path)
    return {"path": str(path), "pid": pid, "alive": pid_alive(pid)}
