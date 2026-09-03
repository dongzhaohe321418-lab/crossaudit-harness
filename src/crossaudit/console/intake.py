"""What happens to a sentence between Send and the run (or the reply).

``/api/say`` used to hold the HTTP response open through the router's model
call, the context read, the preflight, the attachment staging and the routing
commit — several seconds during which the page showed a static "Starting…" and
nothing else. The intake is the process-local record of that stretch: the POST
creates it and returns at once; a worker thread runs the same ``say()`` the
console always ran, narrating each phase into it; the page reads it from the
state snapshot the way it reads run progress.

It is deliberately *not* the run journal. A run does not exist until routing
has decided a build should exist, and the journal must not carry a row for a
sentence that turned out to be a question. When a build does start, the journal
takes over (``run_started`` follows ``routed``) and the intake finishes with the
same result dictionary ``say()`` always returned. Nothing here is evidence: a
process restart loses at most the narration of a message that had not yet been
recorded anywhere, which is the state the page already shows honestly by
releasing the composer.

Lane replies (chat, direct auditor) stream through here as ``intake_chunk``
frames on the same named-SSE path as generation chunks: in memory, bounded,
never written to the ledger, and labelled unaudited wherever they show.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable

from ..runtime.pacing import PhaseClock, still_working_text
from .progress import TRACKER, phase_i18n

#: Steps kept per intake; a message is handled in a handful of phases and the
#: ``still_working`` clock adds one line per silent window, so this bounds a
#: pathological wait without ever hiding the latest line.
MAX_STEPS = 60
#: In-memory reply chunks per intake (8 KiB each at most, coalesced upstream).
MAX_CHUNKS = 512

ROUTED_TEXT = {
    "generator": "The generator will do this",
    "auditor": "The auditor will answer",
    "chat": "The generator will reply directly",
    "query": "Looking up the audit record",
    "amendment": "Drafting a change to the rules",
    "dispute": "Sending the finding back to the auditor",
    "resolve": "Recording your ruling",
    "project": "Nothing to set up",
}
ANSWERING_TEXT = {
    "auditor": "The auditor is replying",
    "chat": "The generator is replying",
    "amendment": "The auditor is drafting the rule change",
    "dispute": "The auditor is replying",
}
#: The ``still_working`` phase word for each intake phase.
PHASE_WORD = {"routing": "routing", "answering": "replying", "preparing": "preparing"}


class IntakeRecord:
    """One message in flight. Mutated only under the tracker's lock."""

    def __init__(self, chat_id: str, text: str, *, clock: Callable[[], float]):
        self.id = secrets.token_hex(8)
        self.chat_id = chat_id
        self.text = text
        self.started = time.time()
        self.lane = ""
        self.phase = "routing"
        self.steps: list[dict] = []
        self.chunks: list[dict] = []
        self.next_seq = 0
        self.stream_id = secrets.token_hex(8)
        self.finished = False
        self.result: dict | None = None
        self.error: dict | None = None
        self._clock = clock

    def snapshot(self) -> dict:
        return {
            "id": self.id, "chat_id": self.chat_id, "text": self.text,
            "started": self.started, "lane": self.lane, "phase": self.phase,
            "steps": list(self.steps), "finished": self.finished,
            "result": self.result, "error": self.error,
            "elapsed": max(0, round(time.time() - self.started)),
            "stream_id": self.stream_id, "chunks": len(self.chunks),
        }


class Intake:
    """Process-wide intake tracker: at most one message in flight per console."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 silence_s: float = PhaseClock.SILENCE_S) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._silence = silence_s
        self._current: IntakeRecord | None = None
        self._pacer: PhaseClock | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ----------------------------------------------------------- lifecycle
    def begin(self, chat_id: str, text: str) -> IntakeRecord:
        with self._lock:
            if self._current is not None and not self._current.finished:
                raise RuntimeError("the previous message is still being handled")
            record = IntakeRecord(chat_id, text, clock=self._clock)
            self._current = record
            self._pacer = PhaseClock(self._still_working, clock=self._clock,
                                     silence=self._silence)
        self.narrate("received", "Got it — working out who should handle this")
        self._pacer.touch("routing")
        return record

    def watch(self, stop: threading.Event | None = None, interval: float = 1.0
              ) -> threading.Thread:
        """Run the silence clock for the current intake in a daemon thread."""
        self._stop = stop or threading.Event()
        pacer = self._pacer

        def run() -> None:
            while pacer is not None and not self._stop.wait(interval):
                with self._lock:
                    live = (self._current is not None
                            and not self._current.finished
                            and self._pacer is pacer)
                if not live:
                    return
                pacer.check()

        thread = threading.Thread(target=run, name="crossaudit-intake-clock",
                                  daemon=True)
        thread.start()
        self._thread = thread
        return thread

    def check_silence(self) -> bool:
        """One explicit tick of the silence clock (tests drive this directly)."""
        pacer = self._pacer
        return bool(pacer is not None and pacer.check())

    def _still_working(self, phase: str, seconds: int) -> None:
        self.narrate("still_working",
                     still_working_text(PHASE_WORD.get(phase, phase), seconds),
                     touch=False)

    # ---------------------------------------------------------- narration
    def narrate(self, kind: str, text: str, detail: str = "", *,
                touch: bool = True) -> None:
        with self._lock:
            record = self._current
            if record is None or record.finished:
                return
            if len(record.steps) >= MAX_STEPS:
                del record.steps[1:2]          # keep "received" and the newest
            record.steps.append({
                "t": time.time(), "kind": kind, "text": text, "detail": detail,
                "text_i18n": phase_i18n(text), "actor": "loop",
            })
            if kind == "routed":
                record.lane = detail
                record.phase = "preparing" if detail == "generator" else "answering"
            elif kind == "answering":
                record.phase = "answering"
            pacer = self._pacer
        if touch and pacer is not None:
            pacer.touch(record.phase)
        TRACKER.notify()

    def routed(self, lane: str) -> None:
        self.narrate("routed", ROUTED_TEXT.get(lane, "Handled"), lane)

    def answering(self, lane: str) -> None:
        text = ANSWERING_TEXT.get(lane)
        if text:
            self.narrate("answering", text)

    def provider_event(self, role: str, text: str, detail: str = "") -> None:
        """The resilience layer's recovery narration, as a phase line."""
        self.narrate("provider_recovery", text, detail)

    def chunk(self, text: str, stream: dict) -> None:
        """A coalesced reply chunk; contiguous seq is re-assigned here."""
        with self._lock:
            record = self._current
            if record is None or record.finished:
                return
            if len(record.chunks) >= MAX_CHUNKS and not stream.get("done"):
                return
            seq = record.next_seq
            record.next_seq += 1
            row = {"event_id": seq, "t": time.time(), "text": text,
                   "stream": {"id": record.stream_id, "seq": seq,
                              "done": bool(stream.get("done"))}}
            if stream.get("done"):
                row["stream"]["outcome"] = str(stream.get("outcome") or "complete")
            record.chunks.append(row)
            pacer = self._pacer
        if pacer is not None:
            pacer.touch(record.phase)
        TRACKER.notify()

    def finish(self, result: dict) -> None:
        with self._lock:
            record = self._current
            if record is None or record.finished:
                return
            record.result = result
            record.lane = str(result.get("lane") or record.lane)
            record.finished = True
            self._pacer = None
        TRACKER.notify()

    def fail(self, status: int, reason: str) -> None:
        with self._lock:
            record = self._current
            if record is None or record.finished:
                return
            record.error = {"status": int(status), "reason": str(reason)}
            record.finished = True
            self._pacer = None
        TRACKER.notify()

    # ------------------------------------------------------------ reading
    def snapshot(self) -> dict | None:
        with self._lock:
            return self._current.snapshot() if self._current else None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._current is not None and not self._current.finished

    def reply_events(self, intake_id: str, *, after_sequence: int = -1,
                     limit: int = 256) -> list[dict]:
        """Reply chunks after a cursor, for the named ``intake_chunk`` frames."""
        with self._lock:
            record = self._current
            if record is None or record.id != intake_id:
                return []
            rows = [dict(row, intake_id=record.id, chat_id=record.chat_id,
                         lane=record.lane)
                    for row in record.chunks if row["event_id"] > after_sequence]
        return rows[:max(1, limit)]

    def clear(self) -> None:
        """Process/test reset."""
        with self._lock:
            self._current = None
            self._pacer = None
        self._stop.set()


INTAKE = Intake()
