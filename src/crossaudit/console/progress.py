"""A read-only console projection of the canonical operational run journal.

The old tracker also implemented an in-memory Run/Step lifecycle.  That made
tests convenient but left a second state machine beside SQLite.  Commands now
go through :class:`crossaudit.runtime.RunCommandService`; this object only
selects a journal, reads its projection and wakes live views after a durable
mutation.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from ..runtime import ACTIVE_STATES, RunJournal, RunState


# Fixed event copy is translated here because run events are also consumed by
# non-page clients. Dynamic details are paths, tool labels, or byte counts and
# therefore remain identical in both locales.
CONTEXT_CONDENSATION_ZH = {
    "Project files outlined; full content remains one file_read away":
        "已用结构化大纲精简项目文件；完整内容仍可通过一次 file_read 读取",
    "Project files briefly stubbed; full content remains one file_read away":
        "已将部分项目文件暂时缩为简短占位；完整内容仍可通过一次 file_read 读取",
    "Earlier tool results condensed to previews; rerun the tool for full output":
        "已将较早的工具结果精简为预览；如需完整输出可重新运行该工具",
    "Earlier compute results condensed to previews; rerun compute for full output":
        "已将较早的计算结果精简为预览；如需完整输出可重新运行计算",
    "Earlier owner guidance condensed; full messages remain in the run record":
        "已精简较早的用户补充说明；完整消息仍保存在运行记录中",
}


def _project_context_step(step: dict) -> dict:
    """Add locale-ready display copy without changing the durable event."""
    if step.get("kind") != "context_condensed":
        return step
    text = str(step.get("text") or "")
    detail = str(step.get("detail") or "")
    projected = dict(step)
    projected["text_i18n"] = {
        "en": text,
        "zh": CONTEXT_CONDENSATION_ZH.get(text, text),
    }
    projected["detail_i18n"] = {"en": detail, "zh": detail}
    return projected


def project_snapshot(row: dict | None) -> dict | None:
    """Enrich context notices in a journal projection for user-facing clients."""
    if row is None:
        return None
    projected = dict(row)
    projected["steps"] = [_project_context_step(step)
                          for step in row.get("steps", [])]
    return projected


def context_events(row: dict | None) -> list[dict]:
    """The durable condensation notices that belong in the generator stream."""
    projected = project_snapshot(row)
    return [step for step in (projected or {}).get("steps", [])
            if step.get("kind") == "context_condensed"]


class Tracker:
    """One run projection with optional durable journal backing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._journal: RunJournal | None = None
        self._journal_path: Path | None = None
        self._listeners: list[Callable[[], None]] = []

    def bind(self, path: Path) -> None:
        """Bind this project process to its durable operational journal.

        Rebinding the same path is cheap. A different project replaces only the
        process-local projection; the old project's database remains intact.
        This read model deliberately performs no crash recovery or mutation.
        """
        selected = Path(path).resolve()
        with self._lock:
            if self._journal_path == selected and self._journal is not None:
                return
            journal = RunJournal(selected)
            self._journal = journal
            self._journal_path = selected

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Wake a view when progress changes; the ledger remains the record."""
        with self._lock:
            self._listeners.append(listener)

    def notify(self) -> None:
        """Wake subscribers after a command has committed a journal change."""
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener()

    @property
    def running(self) -> bool:
        with self._lock:
            if self._journal is None:
                return False
            latest = self._journal.latest()
            return bool(latest and RunState(latest["state"]) in ACTIVE_STATES)

    def snapshot(self) -> dict | None:
        with self._lock:
            row = self._journal.latest() if self._journal is not None else None
        return project_snapshot(row)

    def interruption(self) -> dict | None:
        with self._lock:
            return self._journal.interruption() if self._journal is not None else None

    def clear(self) -> None:
        with self._lock:
            # `clear` is a process/test reset, not deletion of durable history.
            self._journal = None
            self._journal_path = None
        self.notify()

#: One tracker per process. The console is a single-project window, and a build
#: is a single-project act.
TRACKER = Tracker()
