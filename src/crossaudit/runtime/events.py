"""Typed operational facts emitted by the agent loop.

Display text is narration. It must never be parsed to discover lifecycle,
round number or event meaning. ``RunEvent`` carries those facts separately so
the CLI can print prose, the journal can persist state and the UI can localize
without changing control flow.

Liveness kinds the watchdog and shell add beside the loop's own narration:
``provider_unavailable`` (the run parked because no configured provider route
can take the next request) and ``run_stalled`` (display-only: the lease
expired while the owner still lives; the state does not change).
"""
from __future__ import annotations

from dataclasses import dataclass

from .runs import RunState


MAX_GENERATION_CHUNK_BYTES = 8 * 1024


@dataclass(frozen=True, slots=True)
class RunEvent:
    actor: str
    text: str
    state: RunState
    kind: str = "activity"
    detail: str = ""
    round_no: int = 0
    round_limit: int = 0
    #: Machine-readable {kind, category, detail} for waiting states, persisted
    #: on the run row so the UI can say *why* nothing is moving without
    #: parsing prose. Cleared by the next event that does not restate one.
    waiting_reason: dict | None = None
    #: Machine-readable identity and ordering for one streamed completion.
    #: This is event-local operational data, unlike run-level waiting_reason.
    stream: dict | None = None

    def __post_init__(self) -> None:
        if not self.actor or not self.kind:
            raise ValueError("run events require an actor and kind")
        if self.round_no < 0 or self.round_limit < 0:
            raise ValueError("run event round values cannot be negative")
        if self.round_limit and self.round_no > self.round_limit:
            raise ValueError("run event round cannot exceed its limit")
        if self.waiting_reason is not None and not isinstance(
                self.waiting_reason, dict):
            raise ValueError("a run event waiting_reason must be a mapping")
        if self.kind != "generation_chunk":
            if self.stream is not None:
                raise ValueError("stream metadata is only valid on generation chunks")
            return
        if self.actor != "generator" or self.state != RunState.GENERATING:
            raise ValueError(
                "generation chunks require the generator actor and GENERATING state")
        if not isinstance(self.text, str):
            raise ValueError("generation chunk text must be decoded text")
        if self.detail:
            raise ValueError("generation chunks cannot carry narration detail")
        if self.waiting_reason is not None:
            raise ValueError("generation chunks cannot carry a waiting reason")
        if not isinstance(self.stream, dict):
            raise ValueError("a generation chunk requires stream metadata")
        allowed = {"id", "seq", "done", "outcome"}
        if not set(self.stream) <= allowed:
            raise ValueError("generation chunk stream metadata has unknown fields")
        stream_id = self.stream.get("id")
        seq = self.stream.get("seq")
        done = self.stream.get("done")
        outcome = self.stream.get("outcome")
        if (not isinstance(stream_id, str) or not stream_id
                or len(stream_id.encode("utf-8")) > 128):
            raise ValueError("generation chunk stream id must be 1..128 bytes")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise ValueError("generation chunk sequence must be a non-negative integer")
        if not isinstance(done, bool):
            raise ValueError("generation chunk done must be boolean")
        if done and outcome not in {"complete", "aborted"}:
            raise ValueError("a terminal generation chunk needs a valid outcome")
        if not done and outcome is not None:
            raise ValueError("a non-terminal generation chunk cannot have an outcome")
        if not done and not self.text:
            raise ValueError("a non-terminal generation chunk cannot be empty")
        if len(self.text.encode("utf-8")) > MAX_GENERATION_CHUNK_BYTES:
            raise ValueError("a generation chunk cannot exceed 8 KiB")
