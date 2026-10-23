"""What the two O_EXCL lock files (controller state, evidence ledger) share.

Neither lock is ever broken automatically (review 2026-10-23 round 3,
finding 2): "observe stale, then unlink" can delete a fresh owner's lock when
the old holder releases and a new one acquires in between, and no token
check can close that window. A lock older than its stale limit is refused by
its owner module with a sentence naming the pid this module reads from it;
``crossaudit doctor`` reports such a lock and ``doctor --fix`` removes it
through :func:`remove_stale`, only when that pid is not alive.

A lock file holds ``"<pid> <unix time> <nonce>"``, written at acquisition
(:func:`new_token`); files written before the nonce existed hold
``"<pid> <time>"`` and read the same way.
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path


def new_token() -> str:
    """The owner token written into a lock file at acquisition."""
    return f"{os.getpid()} {time.time():.0f} {secrets.token_hex(8)}"


def holder(lock_path: Path) -> dict | None:
    """Who holds the lock at ``lock_path`` and for how long, or None when
    there is no lock: ``{"pid", "age", "token"}``; ``pid`` is None when the
    file names none."""
    try:
        age = time.time() - lock_path.stat().st_mtime
        text = lock_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return {"pid": None, "age": 0.0, "token": ""}
    head = text.split(" ", 1)[0].strip()
    return {"pid": int(head) if head.isdigit() else None, "age": age, "token": text}


def owns(lock_path: Path, token: str) -> bool:
    """Whether the lock file at ``lock_path`` still carries ``token``."""
    try:
        return lock_path.read_text(encoding="utf-8", errors="replace") == token
    except OSError:
        return False


def pid_alive(pid: int | None) -> bool:
    """``os.kill(pid, 0)``: only ESRCH counts as dead. A pid we may not
    signal (EPERM) is alive; an unreadable pid is treated as alive, so
    nothing is removed on a guess."""
    if pid is None or pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def status(lock_path: Path, stale_after: float) -> dict | None:
    """The lock as `doctor` reports it, or None when free:
    ``{"path", "pid", "age", "stale", "alive"}``."""
    found = holder(lock_path)
    if found is None:
        return None
    return {"path": str(lock_path), "pid": found["pid"], "age": found["age"],
            "stale": found["age"] > stale_after, "alive": pid_alive(found["pid"])}


def remove_stale(lock_path: Path, stale_after: float) -> str:
    """Remove the lock only if it is stale AND its pid is not alive
    (``doctor --fix``). Returns ``"absent"``, ``"fresh"``, ``"alive"`` or
    ``"removed"``. The file is re-read just before the unlink and left alone
    if it changed, so a lock taken meanwhile by a live process is not deleted
    on the strength of the old reading."""
    found = holder(lock_path)
    if found is None:
        return "absent"
    if found["age"] <= stale_after:
        return "fresh"
    if pid_alive(found["pid"]):
        return "alive"
    if not owns(lock_path, found["token"]):
        return "fresh"
    lock_path.unlink(missing_ok=True)
    return "removed"
