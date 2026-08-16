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
    #: A size-guarded head cache so a build's many appends stay O(1) instead of
    #: re-scanning the whole file each time. It is trusted ONLY when the file
    #: size still matches what we last saw; any change on disk (another writer,
    #: truncation) misses the cache and forces a full, authoritative re-derive.
    _cached_head: tuple[int, str] | None = field(default=None, init=False)
    _cached_size: int = field(default=-1, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._cached_head = None
        self._cached_size = -1

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
            prev_seq, prev_digest = self._head_locked()
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
                              ensure_ascii=False) + "\n"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
                new_size = os.fstat(fd).st_size
            finally:
                os.close(fd)
            # We just wrote the new head; remember it (guarded by the resulting
            # file size) so the next append does not have to re-scan the file.
            self._cached_head = (body["seq"], entry_digest)
            self._cached_size = new_size
            return entry_digest

    # -- read -----------------------------------------------------------------
    def head(self) -> str:
        """Digest of the last complete entry, or ``""`` for an empty ledger."""
        return self._head_locked()[1] if self.path.exists() else ""

    def entries(self) -> list[dict]:
        """All complete entries as parsed dicts (including their ``digest``)."""
        rows: list[dict] = []
        for _seq, obj, _complete in self._iter_lines():
            if obj is not None:
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
    def _head_locked(self) -> tuple[int, str]:
        """(seq, digest) of the last complete entry; (-1, "") when empty.

        Fast path: if the file is exactly the size we last recorded, the cached
        head is authoritative (we hold the append lock, and no size change means
        no writer appended). Otherwise fall back to an authoritative full scan
        and refresh the cache — so correctness never depends on the cache.
        """
        try:
            size = self.path.stat().st_size if self.path.exists() else 0
        except OSError:
            size = 0
        if size == 0:
            self._cached_head, self._cached_size = (-1, ""), 0
            return (-1, "")
        if self._cached_head is not None and size == self._cached_size:
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
        self._cached_head, self._cached_size = head, size
        return head

    def _iter_lines(self):
        """Yield (lineno, parsed_obj_or_None, complete_bool) for each line.

        ``complete`` is False only for a final line with no terminating newline
        (a crash mid-append). A parse failure yields obj=None, complete=True.
        """
        if not self.path.exists():
            return
        with open(self.path, "rb") as fh:
            raw = fh.read()
        if not raw:
            return
        text = raw.decode("utf-8", errors="replace")
        trailing_newline = text.endswith("\n")
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if not ln.strip():
                continue
            complete = trailing_newline or i < len(lines) - 1
            try:
                obj = json.loads(ln)
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
    """Exclusive O_EXCL advisory lock with stale-break, mirroring state.py."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path

    def __enter__(self) -> "_FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _LOCK_TIMEOUT_S
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                except OSError:
                    age = 0
                if age > _LOCK_STALE_S:
                    self.lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() > deadline:
                    raise ConfigDenial(
                        "the evidence ledger is locked by another writer")
                time.sleep(0.02)

    def __exit__(self, *exc: Any) -> None:
        self.lock_path.unlink(missing_ok=True)
