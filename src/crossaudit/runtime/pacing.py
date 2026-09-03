"""A server-side phase clock: silence becomes a sentence, never a page timer.

D4 rules out a page-side stall timer — the page must not guess about a run it
cannot see. The clock therefore lives beside the worker: whoever narrates a
phase touches it, and when a phase has gone ``SILENCE_S`` seconds without a
new event the clock emits one ``still_working`` line naming the phase and the
seconds spent in it. The emit is the caller's, so the same clock serves the run
journal (through the command shell's cancellation-aware emit) and the intake.

Injectable clock; ``check()`` is the whole decision, so a test drives it with
a fake clock and never sleeps.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable


def still_working_text(phase: str, seconds: int) -> str:
    """The one sentence the clock speaks: phase word, seconds in the phase."""
    return f"Still {phase} · {int(seconds)} s"


#: The phase word for each run state the clock narrates. Waiting states are
#: not silence — a card already says what is being waited for — so they map
#: to nothing and the clock stays quiet in them.
RUN_PHASES = {
    "QUEUED": "preparing",
    "GENERATING": "generating",
    "REVISING": "generating",
    "AUDITING": "auditing",
}


class PhaseClock:
    SILENCE_S = 8.0

    def __init__(self, emit_still: Callable[[str, int], None], *,
                 clock: Callable[[], float] = time.monotonic,
                 silence: float = SILENCE_S) -> None:
        self._emit = emit_still
        self._clock = clock
        self._silence = float(silence)
        self._lock = threading.Lock()
        self._phase: str | None = None
        self._phase_since = 0.0
        self._last = 0.0

    def touch(self, phase: str | None) -> None:
        """A new event in ``phase`` (None: a phase the clock does not narrate)."""
        now = self._clock()
        with self._lock:
            if phase != self._phase:
                self._phase = phase
                self._phase_since = now
            self._last = now

    @property
    def phase(self) -> str | None:
        with self._lock:
            return self._phase

    def check(self) -> bool:
        """Emit ``still_working`` if the phase has been silent long enough."""
        now = self._clock()
        with self._lock:
            phase = self._phase
            if phase is None or now - self._last < self._silence:
                return False
            elapsed = int(now - self._phase_since)
            self._last = now
        self._emit(phase, elapsed)
        return True

    def run(self, stop: threading.Event, interval: float = 1.0) -> None:
        """Tick until ``stop`` is set or the emit refuses (run over, cancelled)."""
        while not stop.wait(interval):
            try:
                self.check()
            except Exception:       # noqa: BLE001 -- a refused emit ends the clock
                return
