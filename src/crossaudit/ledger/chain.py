"""The append-only, hash-chained evidence ledger.

Storage is one JSON object per line (JSONL). Each line is a *body* plus the
``digest`` taken over that body; the body carries ``prev`` (the previous
entry's digest, ``""`` for the genesis entry) and a monotonic ``seq``. Three
independent checks make tampering detectable on re-read:

* content   — ``digest(body)`` must equal the stored ``digest``;
* chain     — each ``prev`` must equal the prior entry's digest;
* order     — ``seq`` must increment by exactly one from 0.

Appends are serialised by an ``O_EXCL`` lock and made durable with ``fsync``
(mirroring ``controller/state``), so a crash cannot interleave two chains; a
torn final line is reported as an incomplete tail rather than silently trusted.

Line framing: an entry ends at ``"\\n"`` and nowhere else. The writer only ever
emits ``"\\n"``, and ``json.dumps`` escapes every control character, so a raw
``"\\n"`` or ``"\\r"`` can never occur inside an entry. ``str.splitlines`` was
used here once and also splits on U+2028, U+2029 and U+0085, which
``ensure_ascii=False`` leaves raw: one such character in a payload made the
ledger unverifiable and let the next appends fork the chain. Readers now split
on ``"\\n"`` only (a line that still carries a ``"\\r"`` was not written by this
writer and is unparseable, never silently CRLF-tolerated), and the writer
escapes those three characters so a ledger it writes is also readable by an
older reader. An append refuses a ledger whose complete lines do not verify.

Design note — determinism: the caller supplies ``ts`` (and any other evidence),
because the ledger records facts, it does not mint them. Re-deriving a stored
entry therefore reproduces its digest byte-for-byte on any host, which is what
lets an independent verifier confirm the chain offline.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import locks
from ..errors import ConfigDenial, IntegrityDenial
from ..receipt.schema import canonical, digest

#: Bump when the entry shape changes; a verifier never guesses the layout.
LEDGER_SCHEMA = 1

#: Evidence kinds recorded by the runtime. Kept open (validated as a plain
#: string) so Phase 2+ can add kinds without a schema break, but the core set
#: is named so readers and the Auditor share a vocabulary.
KINDS = ("tool_call", "decision", "tool_result", "approval", "note")

_LOCK_TIMEOUT_S = 10.0
_LOCK_STALE_S = 30.0

#: Line separators ``str.splitlines`` honours that ``json.dumps(...,
#: ensure_ascii=False)`` leaves raw (every other one is below U+0020 and is
#: escaped already). The writer escapes these; JSON decodes the escape to the
#: same character, so the body -- and therefore ``digest(body)``, which is
#: taken over ``canonical(body)`` and not over the line -- is unchanged, and a
#: line without them is byte-identical to what the writer always produced.
_LINE_SEPARATOR_ESCAPES = {0x2028: "\\u2028", 0x2029: "\\u2029", 0x85: "\\u0085"}


def _stamp_of(st: os.stat_result) -> tuple[int, int, int]:
    """What the head cache is keyed on: size, mtime in ns, inode."""
    return (st.st_size, st.st_mtime_ns, st.st_ino)


class LedgerError(IntegrityDenial):
    """A ledger read found tampering, corruption, or a broken chain."""


@dataclass
class VerifyReport:
    ok: bool
    count: int = 0
    head: str = ""
    error: str = ""
    #: seq of the entry the failure was found at, when ok is False.
    at_seq: int | None = None
    #: True when the only problem is an unterminated/partial trailing line
    #: (a crash mid-append); every complete entry before it still verifies.
    incomplete_tail: bool = False


@dataclass
class EvidenceLedger:
    """A single project's evidence chain, persisted at ``path`` (JSONL)."""

    path: Path
    _lock_path: Path = field(init=False)
    #: A head cache so a build's many appends stay O(1) instead of re-scanning
    #: the whole file each time. It is trusted ONLY when the file's identity
    #: stamp -- ``(st_size, st_mtime_ns, st_ino)`` -- still matches what this
    #: instance recorded after its own write or scan; a change in any one of
    #: the three (another writer, truncation, an in-place rewrite, a file
    #: replaced by rename) misses the cache and forces a full, authoritative
    #: re-derive. What it cannot see is spelled out in ``_head_locked``.
    _cached_head: tuple[int, str] | None = field(default=None, init=False)
    _cached_stamp: tuple[int, int, int] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._cached_head = None
        self._cached_stamp = None

    # -- append ---------------------------------------------------------------
    def append(self, kind: str, *, run_id: str, payload: dict,
               ts: str | None = None) -> str:
        """Record one evidence entry and return its digest (the new head).

        ``ts`` defaults to an ISO-8601 UTC stamp; callers that need a fixed
        timestamp (tests, replay) pass it explicitly. The whole read-head →
        build → append → advance sequence runs under the exclusive lock so two
        writers can never fork the chain.
        """
        if not isinstance(payload, dict):
            raise ConfigDenial("evidence payload must be a mapping")
        if not kind or not isinstance(kind, str):
            raise ConfigDenial("evidence kind must be a non-empty string")
        stamp = ts if ts is not None else _utc_now()
        with self._locked():
            self._refuse_torn_tail()
            prev_seq, prev_digest = self._verified_head_locked()
            body = {
                "ledger_schema": LEDGER_SCHEMA,
                "seq": prev_seq + 1 if prev_digest else 0,
                "prev": prev_digest,
                "kind": kind,
                "run_id": str(run_id),
                "ts": str(stamp),
                "payload": payload,
            }
            entry_digest = digest(body)
            line = json.dumps({**body, "digest": entry_digest},
                              sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False
                              ).translate(_LINE_SEPARATOR_ESCAPES) + "\n"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
                new_stamp = _stamp_of(os.fstat(fd))
            finally:
                os.close(fd)
            # We just wrote the new head; remember it (guarded by the resulting
            # file's size, mtime and inode) so the next append does not have to
            # re-scan the file.
            self._cached_head = (body["seq"], entry_digest)
            self._cached_stamp = new_stamp
            return entry_digest

    # -- read -----------------------------------------------------------------
    def head(self) -> str:
        """Digest of the last complete entry, or ``""`` for an empty ledger."""
        return self._head_locked()[1] if self.path.exists() else ""

    def entries(self) -> list[dict]:
        """All complete entries as parsed dicts (including their ``digest``).

        An unterminated final line (a crash mid-append) is NOT returned: a
        reader must agree with ``head()``/``verify()`` and never surface a torn
        tail as if it were a durable entry — otherwise it could leak into the
        Auditor's evidence view.
        """
        rows: list[dict] = []
        for _seq, obj, complete in self._iter_lines():
            if obj is not None and complete:
                rows.append(obj)
        return rows

    def verify(self) -> VerifyReport:
        """Re-derive the whole chain; refuse on the first inconsistency.

        A verifier trusts nothing it did not recompute: for every entry it
        rebuilds ``digest(body)`` and checks it against the stored value, that
        ``prev`` links the prior digest, and that ``seq`` counts up from 0.
        """
        if not self.path.exists():
            return VerifyReport(ok=True, count=0, head="")
        expected_seq = 0
        prev_digest = ""
        count = 0
        for lineno, obj, complete in self._iter_lines():
            if not complete:
                # A crash mid-append leaves a partial trailing line. Everything
                # before it is intact; report the tail rather than fail hard.
                return VerifyReport(ok=False, count=count, head=prev_digest,
                                    error=f"incomplete trailing entry at line {lineno}",
                                    at_seq=expected_seq, incomplete_tail=True)
            if obj is None:
                return VerifyReport(ok=False, count=count, head=prev_digest,
                                    error=f"unparseable entry at line {lineno}",
                                    at_seq=expected_seq)
            stored = obj.get("digest")
            body = {k: v for k, v in obj.items() if k != "digest"}
            recomputed = digest(body)
            if stored != recomputed:
                return VerifyReport(ok=False, count=count, head=prev_digest,
                                    error=f"entry {expected_seq} digest mismatch "
                                          "(content tampered)", at_seq=expected_seq)
            if body.get("prev", "") != prev_digest:
                return VerifyReport(ok=False, count=count, head=prev_digest,
                                    error=f"entry {expected_seq} broke the chain "
                                          "(prev does not link the prior entry)",
                                    at_seq=expected_seq)
            if body.get("seq") != expected_seq:
                return VerifyReport(ok=False, count=count, head=prev_digest,
                                    error=f"entry out of order: expected seq "
                                          f"{expected_seq}, found {body.get('seq')}",
                                    at_seq=expected_seq)
            prev_digest = stored
            expected_seq += 1
            count += 1
        return VerifyReport(ok=True, count=count, head=prev_digest)

    # -- internals ------------------------------------------------------------
    def _refuse_torn_tail(self) -> None:
        """Fail closed if the ledger file has an unterminated final line.

        A file that does not end in a newline carries a torn final entry — an
        append interrupted by a crash. Extending it would glue new bytes onto
        the partial line (``O_APPEND`` writes at end-of-file and does not repair
        the missing newline), physically corrupting the chain. Refusing here
        surfaces the damage explicitly for recovery instead of writing onto it;
        the trailing-newline durability signal is never silently trusted or
        resurrected. (Called under the append lock, so no writer can race it.)
        """
        if not self.path.exists():
            return
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size == 0:
            return
        with open(self.path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                raise LedgerError(
                    "the evidence ledger has an incomplete final entry (a crash "
                    "left a torn tail); refusing to append onto a damaged chain "
                    "until it is recovered")

    def _verified_head_locked(self) -> tuple[int, str]:
        """(seq, digest) to chain onto, refusing a ledger that does not verify.

        Computing a head from "the last line that parses" let a complete but
        unparseable line be skipped: the next two appends both chained onto
        the entry before it, with the same ``seq`` and ``prev`` -- a forked
        chain no verifier can repair. So on any cache miss the whole chain is
        re-derived first and an append onto a damaged chain is refused. The
        cache is trusted exactly as ``_head_locked`` trusts it, with the same
        stated blind spot: the file still has the size, mtime and inode this
        instance recorded after its own verified write or scan, under the
        lock. (The torn-tail refusal runs before this and is unchanged.)
        """
        stamp = self._stamp()
        if stamp is None:
            self._cached_head, self._cached_stamp = (-1, ""), None
            return (-1, "")
        if self._cached_head is not None and stamp == self._cached_stamp:
            return self._cached_head
        report = self.verify()
        if not report.ok:
            raise LedgerError(
                f"the evidence ledger does not verify ({report.error}); refusing "
                f"to append onto a damaged chain until it is recovered",
                at_seq=report.at_seq)
        head = (report.count - 1, report.head) if report.count else (-1, "")
        self._cached_head, self._cached_stamp = head, stamp
        return head

    def _head_locked(self) -> tuple[int, str]:
        """(seq, digest) of the last complete entry; (-1, "") when empty.

        Fast path: if the file has exactly the ``(st_size, st_mtime_ns,
        st_ino)`` this instance last recorded, the cached head is used without
        re-reading the file. A change in any one of the three falls back to an
        authoritative full scan and refreshes the cache. What the fast path
        does NOT detect: a rewrite by another process that keeps the size,
        restores ``st_mtime_ns`` exactly (``os.utime`` can) and stays on the
        same inode. An append then chains onto the cached head without
        re-verifying the file; the next ``verify()``, which never consults the
        cache, reports the rewrite.
        """
        stamp = self._stamp()
        if stamp is None:
            self._cached_head, self._cached_stamp = (-1, ""), None
            return (-1, "")
        if self._cached_head is not None and stamp == self._cached_stamp:
            return self._cached_head
        last_obj = None
        for _lineno, obj, complete in self._iter_lines():
            if obj is not None and complete:
                last_obj = obj
        if last_obj is None:
            head = (-1, "")
        else:
            seq = last_obj.get("seq")
            head = (seq if isinstance(seq, int) else -1,
                    str(last_obj.get("digest", "")))
        self._cached_head, self._cached_stamp = head, stamp
        return head

    def _stamp(self) -> tuple[int, int, int] | None:
        """The file's identity stamp, or None when it is missing or empty."""
        try:
            st = self.path.stat()
        except OSError:
            return None
        return _stamp_of(st) if st.st_size else None

    def _iter_lines(self):
        """Yield (lineno, parsed_obj_or_None, complete_bool) for each line.

        ``complete`` is False only for a final line with no terminating newline
        (a crash mid-append). A parse failure yields obj=None, complete=True.

        Lines are split on ``"\\n"`` only -- see the module docstring. A line
        carrying a ``"\\r"`` is reported unparseable: the writer never emits
        one raw, so it is not an entry this ledger wrote.
        """
        if not self.path.exists():
            return
        with open(self.path, "rb") as fh:
            raw = fh.read()
        if not raw:
            return
        text = raw.decode("utf-8", errors="replace")
        trailing_newline = text.endswith("\n")
        lines = text.split("\n")
        if trailing_newline:
            lines.pop()           # the empty remainder after the final "\n"
        for i, ln in enumerate(lines):
            if not ln.strip():
                continue
            complete = trailing_newline or i < len(lines) - 1
            try:
                obj = None if "\r" in ln else json.loads(ln)
                if not isinstance(obj, dict):
                    obj = None
            except (ValueError, TypeError):
                obj = None
            yield i + 1, obj, complete

    def _locked(self):
        return _FileLock(self._lock_path)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _FileLock:
    """Exclusive O_EXCL advisory lock, the same policy as the controller's.

    The lock file carries an owner token (pid, time, nonce; ``locks``), and
    release removes it only while it is still this holder's. A lock older
    than ``_LOCK_STALE_S`` is never broken automatically (review 2026-10-23
    round 3, finding 2, applied to this lock too): "observe stale, then
    unlink" could delete a fresh writer's lock. It is refused with a
    ``LedgerError`` naming the pid, and ``crossaudit doctor --fix`` removes it
    only when that pid is not alive.
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.token = ""

    def __enter__(self) -> "_FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _LOCK_TIMEOUT_S
        token = locks.new_token()
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, token.encode())
                finally:
                    os.close(fd)
                self.token = token
                return self
            except FileExistsError:
                holder = locks.holder(self.lock_path)
                if holder is None:
                    continue                    # released meanwhile; retry
                if holder["age"] > _LOCK_STALE_S:
                    pid = holder["pid"] if holder["pid"] is not None else "?"
                    raise LedgerError(
                        f"the evidence ledger lock {self.lock_path} has been held by "
                        f"pid {pid} for {holder['age']:.0f}s, longer than the "
                        f"{_LOCK_STALE_S:g}s stale limit, and is not broken "
                        f"automatically; if no crossaudit process is running for "
                        f"this project, `crossaudit doctor --fix` removes it",
                        issue="stale_lock", lock=str(self.lock_path))
                if time.monotonic() > deadline:
                    raise ConfigDenial(
                        "the evidence ledger is locked by another writer")
                time.sleep(0.02)

    def __exit__(self, *exc: Any) -> None:
        if locks.owns(self.lock_path, self.token):
            self.lock_path.unlink(missing_ok=True)


def lock_status(ledger_path: Path) -> dict | None:
    """The ledger's lock as `doctor` reports it (``locks.status``)."""
    ledger_path = Path(ledger_path)
    return locks.status(ledger_path.with_suffix(ledger_path.suffix + ".lock"),
                        _LOCK_STALE_S)


def remove_stale_lock(ledger_path: Path) -> str:
    """``doctor --fix`` for the ledger's lock: removed only when stale and its
    pid is not alive (``locks.remove_stale``)."""
    ledger_path = Path(ledger_path)
    return locks.remove_stale(ledger_path.with_suffix(ledger_path.suffix + ".lock"),
                              _LOCK_STALE_S)
