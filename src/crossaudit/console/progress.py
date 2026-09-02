"""A read-only console projection of the canonical operational run journal.

The old tracker also implemented an in-memory Run/Step lifecycle.  That made
tests convenient but left a second state machine beside SQLite.  Commands now
go through :class:`crossaudit.runtime.RunCommandService`; this object only
selects a journal, reads its projection and wakes live views after a durable
mutation.
"""
from __future__ import annotations

import re

from ..cli.build import EARLIER_TURNS_NOTICE
import threading
from collections.abc import Callable
from pathlib import Path

from ..runtime import ACTIVE_STATES, RunJournal, RunState


# Fixed event copy is translated here because run events are also consumed by
# non-page clients. Dynamic paths/tool labels are locale-neutral; byte counts
# translate their unit explicitly.
CONTEXT_CONDENSATION_ZH = {
    "Tracked project files outlined; file_read can retrieve the committed version":
        "已用结构化大纲精简已跟踪的项目文件；file_read 可读取其已提交版本",
    "Working-tree-only project files outlined; content is not available to file_read":
        "已用结构化大纲精简仅存在于工作区的项目文件；file_read 无法读取其内容",
    "Tracked project files briefly stubbed; file_read can retrieve the committed version":
        "已将已跟踪的项目文件暂时缩为简短占位；file_read 可读取其已提交版本",
    "Working-tree-only project files briefly stubbed; content is not available to file_read":
        "已将仅存在于工作区的项目文件暂时缩为简短占位；file_read 无法读取其内容",
    "Earlier tool results condensed to previews; rerun the tool for full output":
        "已将较早的工具结果精简为预览；如需完整输出可重新运行该工具",
    "Earlier compute results condensed to previews; rerun compute for full output":
        "已将较早的计算结果精简为预览；如需完整输出可重新运行计算",
    "Earlier owner guidance condensed; full messages remain in the run record":
        "已精简较早的用户补充说明；完整消息仍保存在运行记录中",
    EARLIER_TURNS_NOTICE:
        "已将本对话中较早的轮次概括后提供给生成者；完整对话仍保留在这里",
}


#: Counted units are translated by PATTERN, never as fixed strings: a fixed
#: entry falls back to English the moment the number changes, and these details
#: are nothing but numbers. Paths and tool labels are locale-neutral and are
#: deliberately left alone.
COUNTED_DETAIL_ZH = (
    (re.compile(r"(\d+) bytes"), "{0} 字节"),
    # `turns?` — both halves of the singular fix, or the singular detail stops
    # matching the pattern and lands in the other failure mode: an English
    # "1 turn" shown to a Chinese reader.
    (re.compile(r"(\d+) turns?"), "{0} 轮"),
)


def _detail_i18n(detail: str) -> dict[str, str]:
    """Translate generated units while leaving paths/tool labels untouched."""
    for pattern, template in COUNTED_DETAIL_ZH:
        match = pattern.fullmatch(detail)
        if match:
            return {"en": detail, "zh": template.format(match.group(1))}
    return {"en": detail, "zh": detail}


#: Phase narration (D150, perceived latency). Every kind here is a fixed
#: sentence or a counted pattern, at most 60 characters, carrying no id, hash,
#: sha, provider:model string or rule id: it is the main surface. The English
#: sentence is what the journal stores; the Chinese form is projected here so
#: page and non-page clients read the same catalogue.
PHASE_KINDS = frozenset({
    "received", "routed", "answering", "preparing", "prompt_ready",
    "still_working", "auditor_reading", "auditor_progress",
    "check_started", "check_finished", "answered",
})

PHASE_TEXT_ZH = {
    "Got it — working out who should handle this": "已收到，正在判断由谁处理",
    "The generator will do this": "交给生成者处理",
    "The auditor will answer": "由审计者回答",
    "The generator will reply directly": "生成者将直接回复",
    "Looking up the audit record": "正在查询审计记录",
    "Drafting a change to the rules": "正在起草规则修改",
    "Sending the finding back to the auditor": "正在将该结论退回审计者",
    "Recording your ruling": "正在记录你的裁定",
    "Nothing to set up": "无需设置",
    "The generator is replying": "生成者正在回复",
    "The auditor is replying": "审计者正在回复",
    "The auditor is drafting the rule change": "审计者正在起草规则修改",
    "Asking the generator to write": "正在请生成者撰写",
    "Reply received": "已收到回复",
    "The auditor is reading the commit": "审计者正在阅读提交内容",
}

#: The phase words of ``still_working``; the number is a count of seconds in
#: the phase, so the sentence is a pattern, never a fixed entry.
STILL_WORKING_ZH = {
    "routing": "仍在判断由谁处理",
    "preparing": "仍在准备",
    "generating": "仍在生成",
    "auditing": "仍在审计",
    "replying": "仍在回复",
    "reviewing": "仍在审阅",
}

#: Deterministic checks named in words. A plugin or future check falls back to
#: its configured name, which is a word, not an id.
CHECK_WORDS = {
    "schema": ("Schema", "结构"),
    "units": ("Units", "单位"),
    "convergence": ("Convergence", "收敛"),
    "provenance": ("Provenance", "来源"),
    "parseable": ("Parseable", "可解析"),
    "source_provenance": ("Source provenance", "来源出处"),
    "documents": ("Document integrity", "文档完整性"),
}


def check_words(name: str) -> tuple[str, str]:
    return CHECK_WORDS.get(name, (name.replace("_", " "), name.replace("_", " ")))


def _zh_check(word: str) -> str:
    for en, zh in CHECK_WORDS.values():
        if en == word:
            return zh
    return word


PHASE_PATTERNS_ZH = (
    (re.compile(r"Still (routing|preparing|generating|auditing|replying|reviewing) · (\d+) s"),
     lambda m: f"{STILL_WORKING_ZH[m.group(1)]} · {m.group(2)} 秒"),
    (re.compile(r"Reading the workspace · (\d+) files?"),
     lambda m: f"正在读取工作区 · {m.group(1)} 个文件"),
    (re.compile(r"The auditor is reading (\d+) files?"),
     lambda m: f"审计者正在阅读 {m.group(1)} 个文件"),
    (re.compile(r"Running the (.+) check"),
     lambda m: f"正在运行{_zh_check(m.group(1))}检查"),
    (re.compile(r"(.+) check passed"),
     lambda m: f"{_zh_check(m.group(1))}检查通过"),
    (re.compile(r"(.+) check found (\d+) issues?"),
     lambda m: f"{_zh_check(m.group(1))}检查发现 {m.group(2)} 个问题"),
)


def phase_i18n(text: str) -> dict[str, str]:
    """EN/ZH pair for one phase sentence; unknown text stays as it is."""
    zh = PHASE_TEXT_ZH.get(text)
    if zh is None:
        for pattern, render in PHASE_PATTERNS_ZH:
            match = pattern.fullmatch(text)
            if match:
                zh = render(match)
                break
    return {"en": text, "zh": zh if zh is not None else text}


def still_working_text(phase: str, seconds: int) -> str:
    return f"Still {phase} · {int(seconds)} s"


#: Recovery narration carries ``vendor:model · attempt N`` in its detail. The
#: attempt is the fact a person needs; the route identity is for the Models
#: panel, not the run card (D150: no provider:model strings on the surface).
_ROUTE_DETAIL = re.compile(r"^\S+:\S+ · (.+)$")


def _project_phase_step(step: dict) -> dict:
    kind = step.get("kind")
    if kind in PHASE_KINDS:
        projected = dict(step)
        projected["text_i18n"] = phase_i18n(str(step.get("text") or ""))
        return projected
    if kind == "provider_recovery":
        detail = str(step.get("detail") or "")
        match = _ROUTE_DETAIL.match(detail)
        if match:
            projected = dict(step)
            projected["detail"] = match.group(1)
            return projected
    return step


def _project_context_step(step: dict) -> dict:
    """Add locale-ready display copy without changing the durable event."""
    if step.get("kind") != "context_condensed":
        return _project_phase_step(step)
    text = str(step.get("text") or "")
    detail = str(step.get("detail") or "")
    projected = dict(step)
    projected["text_i18n"] = {
        "en": text,
        "zh": CONTEXT_CONDENSATION_ZH.get(text, text),
    }
    projected["detail_i18n"] = _detail_i18n(detail)
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
