"""Shared streaming pieces: the D4 coalescer and a generic SSE line parser.

Every adapter that streams shares one coalescing rule — first decoded text at
once, then 200 ms or 8 KiB, whichever first, sequence numbers assigned after
coalescing so they stay contiguous — because the consumer's gap rule is
written against exactly that contract. Keeping the emitter here means a second
adapter cannot drift from the first on the one thing the page relies on.
"""
from __future__ import annotations

import codecs
import secrets
import time

from ..errors import ProviderDenial

STREAM_FLUSH_SECONDS = 0.200
STREAM_CHUNK_BYTES = 8 * 1024


def take_prefix(value: str, limit: int = STREAM_CHUNK_BYTES) -> tuple[str, str]:
    """Split at a character boundary without exceeding a UTF-8 byte limit."""
    used = 0
    for index, char in enumerate(value):
        size = len(char.encode("utf-8"))
        if used + size > limit:
            return value[:index], value[index:]
        used += size
    return value, ""


class ChunkEmitter:
    """Coalesce decoded text before assigning contiguous consumer sequence."""

    def __init__(self, callback, *, clock=time.monotonic) -> None:
        self.callback = callback
        self.clock = clock
        self.stream_id = secrets.token_hex(16)
        self.seq = 0
        self.pending = ""
        self.pending_since: float | None = None
        self.first = True
        self.finished = False

    def _emit(self, text: str, *, done: bool = False,
              outcome: str | None = None) -> None:
        stream = {"id": self.stream_id, "seq": self.seq, "done": done}
        if outcome is not None:
            stream["outcome"] = outcome
        self.callback(text, stream)
        self.seq += 1

    def _flush(self) -> None:
        if not self.pending:
            self.pending_since = None
            return
        text, self.pending = take_prefix(self.pending)
        self._emit(text)
        self.pending_since = self.clock() if self.pending else None

    def feed(self, text: str) -> None:
        if self.finished or not text:
            return
        now = self.clock()
        if not self.pending:
            self.pending_since = now
        self.pending += text
        if self.first:
            # The first decoded text is visible immediately, independently of
            # provider token size and before the 200 ms coalescing window.
            self._flush()
            self.first = False
        while len(self.pending.encode("utf-8")) >= STREAM_CHUNK_BYTES:
            self._flush()
        if (self.pending and self.pending_since is not None
                and now - self.pending_since >= STREAM_FLUSH_SECONDS):
            self._flush()

    def idle(self) -> None:
        if (self.pending and self.pending_since is not None
                and self.clock() - self.pending_since >= STREAM_FLUSH_SECONDS):
            self._flush()

    def finish(self, outcome: str) -> None:
        if self.finished:
            return
        while self.pending:
            self._flush()
        self._emit("", done=True, outcome=outcome)
        self.finished = True


class SSELines:
    """Incremental UTF-8 + SSE framing: yields (event, data) pairs to a sink.

    Handles the transport's arbitrary byte splits (a code point may straddle
    two reads), ``event:`` names, multi-line ``data:``, and comments. The sink
    receives the joined data payload and the event name (``""`` when absent).
    """

    def __init__(self, on_event) -> None:
        self.on_event = on_event
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.lines = ""
        self.event_name = ""
        self.data_lines: list[str] = []

    def feed(self, raw: bytes) -> None:
        try:
            decoded = self.decoder.decode(raw, final=False)
        except UnicodeDecodeError as exc:
            raise ProviderDenial(
                f"provider returned invalid UTF-8 in completion stream: {exc}",
                category="response") from exc
        self._decoded(decoded)

    def _decoded(self, value: str) -> None:
        self.lines += value
        while "\n" in self.lines:
            line, self.lines = self.lines.split("\n", 1)
            self._line(line.rstrip("\r"))

    def _line(self, line: str) -> None:
        if not line:
            self._dispatch()
            return
        if line.startswith(":"):
            return
        if line.startswith("event:"):
            self.event_name = line[6:].strip()
        elif line.startswith("data:"):
            self.data_lines.append(line[5:].lstrip(" "))

    def _dispatch(self) -> None:
        if self.data_lines:
            payload = "\n".join(self.data_lines)
            name = self.event_name
            self.data_lines = []
            self.event_name = ""
            self.on_event(name, payload)
        else:
            self.event_name = ""

    def finish(self) -> None:
        try:
            self._decoded(self.decoder.decode(b"", final=True))
        except UnicodeDecodeError as exc:
            raise ProviderDenial(
                f"provider returned invalid UTF-8 in completion stream: {exc}",
                category="response") from exc
        if self.lines:
            self._line(self.lines.rstrip("\r"))
            self.lines = ""
        self._dispatch()
