"""`crossaudit tui` — the loop, live, in the terminal, and the place to act on it.

docs/design/TUI_FIRST.md §2. Three layers, each testable on its own:

* ``frame(cfg)`` gathers one screen's worth of plain data from the projections
  the console and `status` already use (``console.server.snapshot``,
  ``console.overview``, ``rulings.by_cycle``, ``watch.gather``). Nothing is
  derived here that a projection could carry; where one lacked a field, the
  field was added to the projection.
* ``render(frame, width, height, ...)`` turns that data into the text of one
  screen. Pure: no terminal, no clock, no files. Every line is measured as the
  terminal counts it (CJK is two columns) and cut to the width with an
  ellipsis, so a narrow terminal truncates instead of wrapping into garbage.
* ``run_tui(cfg)`` draws frames with two ANSI escapes (home, clear to the end
  of the screen), reads keys in cbreak mode through ``termios``/``tty``, and
  restores the terminal on every way out. Without a terminal it prints one
  frame and returns, which is what makes the surface testable by a harness.

Every action is an engine verb the CLI already has: a new task runs through
the same ``RunCommandService`` + ``run_loop`` path as `build`; a decision goes
through `resolve`'s ruling path (``main.resolve_cycle``); verify and admit run
`verify` itself with its output captured; stop is the console's
``request_cancel``; the console URL comes from the running console's own record.
This screen never writes ``state.json``, never mints a cycle, never reads a
key, and a key the help bar does not list does nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import select
import shutil
import sys
import threading
import time

from ..config import Config
from ..errors import Denial
from . import i18n, tui
from .i18n import t

REFRESH_S = 2.0
#: While a task this window started is running, redraw this often so its
#: narration appears as it happens rather than on the next 2 s tick.
LIVE_REFRESH_S = 0.5
#: Lines of narration kept in the activity pane.
ACTIVITY_LINES = 8
#: A height large enough that `--once` prints the whole frame to a pipe.
ONCE_HEIGHT = 10_000

#: The words `verify` prints at the head of the lines worth repeating under a
#: cycle (the protocol's own words, never translated: a person compares them
#: with what `crossaudit verify` prints).
VERIFY_HEADS = ("BINDINGS VERIFIED", "SIGNED", "SIGNATURE INVALID", "UNSIGNED",
                "RECORDED", "UNRECORDED", "WORKING TREE", "ADMISSION READY",
                "ADMITTED", "DRY RUN", "REFUSED")


# ===================================================================== data
def _usd(value) -> str:
    """Money the way the console's ``formatUsd`` writes it."""
    if value is None:
        return "-"
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if n == 0:
        return "$0.00"
    if n < 0.01:
        return f"${n:.4f}"
    return f"${n:.2f}"


def _surfaces(by_surface) -> str:
    """``usage.summary``'s ``by_surface`` as "cli 12 · tui 3", or ""."""
    if not isinstance(by_surface, dict) or not by_surface:
        return ""
    parts = []
    for name, value in by_surface.items():
        calls = value.get("calls", 0) if isinstance(value, dict) else value
        try:
            parts.append(f"{name} {int(calls or 0)}")
        except (TypeError, ValueError):
            continue
    return " · ".join(parts)


def frame(cfg: Config) -> dict:
    """Everything one screen shows, as plain data, from existing projections."""
    from .. import rulings
    from ..console import overview, server
    from ..controller import StateStore
    from ..runtime.pacing import RUN_PHASES
    from .build import narration_line
    from .watch import gather

    snap = server.snapshot(cfg)
    audits = overview.read_cycles(cfg)
    state = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()
    records, history = state.get("cycles", {}), state.get("history", [])
    ruled = rulings.by_cycle(cfg)
    subjects = {c["sha"]: c["subject"] for c in gather(cfg)["commits"]}
    ledger = cfg.root / cfg.ledger_dir

    cycles = []
    for row in reversed(snap.get("cycles", [])):          # newest first
        cid = row["id"]
        related = overview.related_cycles(cid, records.get(cid, {}), history,
                                          audits)
        latest = related[-1] if related else None
        receipt = None
        if latest is not None:
            path = ledger / latest.directory / "receipt.json"
            if path.is_file():
                receipt = {"path": path.relative_to(cfg.root).as_posix()}
        last_ruling = (ruled.get(cid) or [None])[-1]
        cycles.append({
            "id": cid,
            # Exactly the word `crossaudit status` prints.
            "status": "CLOSED" if row.get("closed") else row["status"],
            "round": row["round"],
            "max_rounds": snap.get("max_rounds", cfg.max_rounds),
            "verdict": latest.verdict if latest is not None else "",
            "sha": row["sha"],
            "subject": subjects.get(row["sha"], ""),
            "ruling": ({"action": str(last_ruling.get("action", "")),
                        "at": str(last_ruling.get("at", ""))}
                       if last_ruling else None),
            "report": latest is not None,
            "findings": [{"severity": f.get("severity", ""),
                          "rule": f.get("rule", ""),
                          "artifact": f.get("artifact", ""),
                          "observation": f.get("observation", ""),
                          "tier": overview.tier_key(f)}
                         for f in (latest.findings if latest is not None else [])],
            "receipt": receipt,
            "verified": None,
        })

    escalations = [{
        "cycle_id": e["cycle_id"], "short_sha": e.get("short_sha", ""),
        "why": e.get("why", ""), "why_zh": e.get("why_zh"),
        "round": e.get("round", 0), "max_rounds": e.get("max_rounds", 0),
        "limit_reached": bool(e.get("limit_reached")),
        "attempts": list(e.get("attempts", [])),
        "issues": [{"severity": f.get("severity", ""), "rule": f.get("rule", ""),
                    "artifact": f.get("artifact", ""),
                    "observation": f.get("observation", "")}
                   for f in e.get("issues", [])],
        "files": list(e.get("files", [])),
    } for e in snap.get("escalations", [])]

    run: dict = {"state": "idle", "lines": []}
    progress = snap.get("progress")
    if progress and not progress.get("finished"):
        steps = progress.get("steps", [])
        marker = next((s for s in reversed(steps) if s.get("round_limit")), None)
        runs = ((snap.get("usage") or {}).get("attribution") or {}).get("runs") or {}
        spent = runs.get(str(progress.get("run_id", "")))
        cost = None
        if (isinstance(spent, dict) and spent.get("api_value_usd") is not None
                and not (spent.get("unpriced_calls") and not spent.get("api_value_usd"))):
            cost = spent["api_value_usd"]
        lines: list[str] = []
        for step in steps:
            said = narration_line(step, verbose=False)
            if said is not None:
                lines += [ln for ln in said.split("\n") if ln.strip()]
        run = {"state": "running",
               "phase": RUN_PHASES.get(str(progress.get("state", "")), "working"),
               "round": int(marker["round_no"]) if marker else 0,
               "limit": int(marker["round_limit"]) if marker else 0,
               "elapsed": int(progress.get("elapsed", 0) or 0),
               "cost": cost, "run_id": str(progress.get("run_id", "")),
               "lines": lines}
    elif escalations:
        run = {"state": "waiting", "lines": []}

    usage = snap.get("usage") or {}
    return {
        "title": snap.get("title", "") or cfg.science_repo,
        "generator": (snap.get("roles") or {}).get("generator", ""),
        "auditor": (snap.get("roles") or {}).get("auditor", ""),
        "rules_commit": str(snap.get("rules_commit", ""))[:12],
        "tier": str((snap.get("tier") or {}).get("tier", "")),
        "usage": {"today": (usage.get("today") or {}).get("api_value_usd"),
                  "month": (usage.get("month") or {}).get("api_value_usd"),
                  "by_surface": usage.get("by_surface")},
        "run": run,
        "cycles": cycles,
        "escalations": escalations,
        "panel": None,
        "message": "",
    }


# =================================================================== render
def _fit(text: str, width: int) -> str:
    """``text`` cut to ``width`` terminal columns, with an ellipsis if cut."""
    if width <= 0:
        return ""
    if tui._visible(text) <= width:
        return text
    ellipsis = tui.glyph("…", "...")
    room = width - tui._visible(ellipsis)
    if room < 0:
        return ellipsis[:width]
    out = ""
    for ch in text:
        if tui._visible(out + ch) > room:
            break
        out += ch
    return out + ellipsis


def _wrapped(text: str, width: int, indent: int = 0) -> list[str]:
    pad = " " * indent
    return [_fit(pad + line, width)
            for line in tui.wrap(text, max(1, width - indent))]


def _segments(text: str, width: int) -> list[str]:
    """A " · "-separated bar wrapped between its items, never inside one
    (an item wider than the screen is cut like any other line)."""
    lines: list[str] = []
    current = ""
    for item in text.split(" · "):
        candidate = f"{current} · {item}" if current else item
        if current and tui._visible(candidate) > width:
            lines.append(_fit(current, width))
            current = item
        else:
            current = candidate
    if current:
        lines.append(_fit(current, width))
    return lines


def _elapsed(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return t("tui.elapsed", m=m, s=f"{s:02d}")


def _header(fr: dict, width: int) -> list[str]:
    usage = fr.get("usage") or {}
    usage_line = t("tui.usage", today=_usd(usage.get("today")),
                   month=_usd(usage.get("month")))
    surfaces = _surfaces(usage.get("by_surface"))
    if surfaces:
        usage_line += " · " + surfaces
    run = fr.get("run") or {}
    if run.get("state") == "running":
        phase = t(f"tui.phase.{run.get('phase', 'working')}")
        state = (t("tui.state.running", phase=phase, round=run["round"],
                   limit=run["limit"]) if run.get("limit")
                 else t("tui.state.running.early", phase=phase))
    elif run.get("state") == "waiting":
        state = t("tui.state.waiting")
    else:
        state = t("tui.state.idle")
    lines = [
        tui.bold(_fit(t("tui.title", title=fr.get("title", "")), width)),
        _fit(t("tui.roles", generator=fr.get("generator", ""),
               auditor=fr.get("auditor", "")), width),
        _fit(t("tui.rules", rules=fr.get("rules_commit") or t("tui.rules.none"),
               tier=fr.get("tier", "")), width),
        _fit(usage_line, width),
        _fit(state, width),
    ]
    return lines


def _rule(width: int) -> str:
    return tui.dim(tui.glyph("─", "-") * max(0, width))


def _activity(fr: dict, width: int) -> list[str]:
    run = fr.get("run") or {}
    lines = run.get("lines") or []
    if not lines:
        return []
    if run.get("state") == "running":
        head = (t("tui.activity.cost", elapsed=_elapsed(run.get("elapsed", 0)),
                  cost=_usd(run["cost"])) if run.get("cost") is not None
                else t("tui.activity", elapsed=_elapsed(run.get("elapsed", 0))))
    else:
        head = t("tui.activity.last")
    return ([tui.bold(_fit(head, width))]
            + [_fit(line, width) for line in lines[-ACTIVITY_LINES:]]
            + [_rule(width)])


def _decision(fr: dict, width: int) -> list[str]:
    esc = fr["escalations"][0]
    why = esc.get("why_zh") if (i18n.language() == "zh" and esc.get("why_zh")) \
        else esc.get("why", "")
    out = [tui.amber(_fit(t("tui.decision.title", cycle=esc["cycle_id"][:12],
                              sha=esc.get("short_sha", "")), width))]
    out += _wrapped(t("tui.decision.why", why=why), width, 2)
    rounds = ("tui.decision.rounds.limit" if esc.get("limit_reached")
              else "tui.decision.rounds")
    out.append(_fit("  " + t(rounds, round=esc.get("round", 0),
                             limit=esc.get("max_rounds", 0)), width))
    history = ", ".join(f"r{a.get('round')} {a.get('verdict')}"
                        for a in esc.get("attempts", []))
    if history:
        out += _wrapped(t("tui.decision.history", history=history), width, 2)
    if esc.get("issues"):
        out.append(_fit("  " + t("tui.decision.open"), width))
        for issue in esc["issues"]:
            out.append(_fit(f"    {issue['severity']} {issue['rule']} "
                            f"{issue['artifact']}", width))
            out += _wrapped(issue["observation"], width, 6)
    if esc.get("files"):
        out += _wrapped(t("tui.decision.files", files=", ".join(esc["files"])),
                        width, 2)
    out.append(tui.bold(_fit("  " + t("tui.decision.keys"), width)))
    return out + [_rule(width)]


def _cycle_row(cycle: dict, current: bool, width: int) -> str:
    marker = tui.glyph("❯", ">") if current else " "
    verdict = cycle.get("verdict") or "-"
    text = (f"{marker} {cycle['id'][:12]}  {cycle['status']:<10s} "
            f"{cycle['round']}/{cycle['max_rounds']}  {verdict:<8s} "
            f"{str(cycle.get('sha', ''))[:12]}")
    if cycle.get("ruling"):
        text += "  " + t("tui.cycle.ruling", action=cycle["ruling"]["action"],
                         at=cycle["ruling"]["at"])
    text = _fit(text, width)
    return tui.bold(text) if current else text


def _cycle_detail(cycle: dict, width: int) -> list[str]:
    out = []
    if cycle.get("subject"):
        out.append(_fit("    " + t("tui.cycle.commit", subject=cycle["subject"]),
                        width))
    if not cycle.get("report"):
        out.append(_fit("    " + t("tui.cycle.noreport"), width))
    elif not cycle.get("findings"):
        out.append(_fit("    " + t("tui.cycle.nofindings"), width))
    for f in cycle.get("findings", []):
        out.append(_fit(f"    {f['severity']} {f['rule']} {f['artifact']}", width))
        out += _wrapped(f["observation"], width, 6)
        if f.get("tier"):
            out.append(tui.dim(_fit(f"      ({t('tui.tier.' + f['tier'])})", width)))
    receipt = cycle.get("receipt")
    if receipt:
        out.append(_fit("    " + t("tui.cycle.receipt", path=receipt["path"]), width))
        verified = cycle.get("verified")
        if verified:
            out += [_fit(f"      {line}", width) for line in verified]
        else:
            out.append(tui.dim(_fit("      " + t("tui.cycle.unverified"), width)))
    return out


def _help(width: int) -> list[str]:
    keys = ("select", "expand", "new", "verify", "admit", "stop", "console",
            "decision", "help", "quit")
    out = [tui.bold(_fit(t("tui.help.title"), width))]
    for key in keys:
        out += _wrapped(t(f"tui.help.{key}"), width, 2)
    return out


def render(frame: dict, width: int, height: int, *, selected: int = 0,
           expanded: bool = False, mode: str = "cycles") -> str:
    """The text of one screen. Pure: the same arguments give the same bytes.

    ``mode`` is "cycles" (the list), "decision" (the decision card above the
    list, while a cycle waits for a person), or "help" (the key overlay).
    ``expanded`` opens the ``selected`` row to its findings and receipt.
    No line is wider than ``width`` columns and there are at most ``height``
    lines; when the list does not fit, it scrolls to keep the selection seen.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    head = _header(frame, width) + [_rule(width)] + _activity(frame, width)

    body: list[str] = []
    focus = 0
    if mode == "help":
        body = _help(width)
    else:
        if mode == "decision" and frame.get("escalations"):
            body += _decision(frame, width)
        body.append(tui.bold(_fit(t("tui.cycles"), width)))
        cycles = frame.get("cycles") or []
        if not cycles:
            body.append(_fit("  " + t("tui.cycles.none"), width))
        for i, cycle in enumerate(cycles):
            if i == selected:
                focus = len(body)
            body.append(_cycle_row(cycle, i == selected, width))
            if expanded and i == selected:
                body += _cycle_detail(cycle, width)

    foot: list[str] = []
    panel = frame.get("panel")
    if panel:
        foot.append(_rule(width))
        foot.append(tui.bold(_fit(panel.get("title", ""), width)))
        for line in panel.get("lines", []):
            foot += _wrapped(line, width, 2) if line else [""]
        foot.append(tui.dim(_fit(t("tui.panel.close"), width)))
    if frame.get("message"):
        foot += _wrapped(frame["message"], width)
    foot.append(_rule(width))
    foot += [tui.dim(line) for line in _segments(t("tui.help.bar"), width)]

    room = height - len(head) - len(foot)
    if room < len(body):
        if room <= 0:
            body = []
        else:
            start = max(0, min(focus - room // 3, len(body) - room))
            body = body[start:start + room]
    lines = head + body + foot
    return "\n".join(lines[:height])


# ================================================================== actions
def verify_lines(cfg: Config, receipt_rel: str, *, admit: bool = False) -> list[str]:
    """Run `crossaudit verify` (dry run, or ``--admit``) on one receipt and
    return what it printed, line by line; a refusal becomes its sentence."""
    from .main import cmd_verify

    args = argparse.Namespace(
        receipt=str(cfg.root / receipt_rel), admit=admit, science_root=None,
        audit_root=None, expect_repo=None, expect_sha=None, pubkey=None,
        record_only=False, json=False)
    buffer = io.StringIO()
    refusal = ""
    try:
        with contextlib.redirect_stdout(buffer):
            cmd_verify(args)
    except Denial as exc:
        refusal = t("tui.refused", reason=i18n.denial_text(exc.reason))
    lines = [ln for ln in buffer.getvalue().split("\n") if ln.strip()]
    return lines + ([refusal] if refusal else [])


def receipt_heads(lines: list[str]) -> list[str]:
    """The lines of `verify`'s output that name a binding, signature,
    recording, working-tree or admission state, in the order it printed them."""
    return [ln for ln in lines if ln.startswith(VERIFY_HEADS)]


def console_lines(cfg: Config, *, open_browser: bool) -> list[str]:
    """The running console's tokenized URL, handed to the browser through
    `console`'s own rule when ``open_browser``; or how to start one."""
    from ..console import daemon
    from .main import _open_dashboard

    running = daemon.live(cfg)
    if not running:
        return [t("tui.console.none")]
    url = daemon.url_for(running)
    lines = [t("console.url", url=url)]
    if open_browser:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _open_dashboard(argparse.Namespace(no_open=False, json=False,
                                               foreground=False), url)
        lines += [ln.strip() for ln in buffer.getvalue().split("\n") if ln.strip()]
    return lines


def stop_run(cfg: Config, run_id: str = "") -> str:
    """Cancel the running task the way the console's Stop does."""
    from ..console import daemon
    from ..runtime import RunCommandService

    try:
        selected = RunCommandService(cfg, alive=daemon._pid_alive).request_cancel(
            run_id or None)
    except Denial as exc:
        if getattr(exc, "detail", {}).get("issue") == "run_not_active":
            return t("tui.stop.none")
        return t("tui.refused", reason=i18n.denial_text(exc.reason))
    said = t("tui.stop.requested", run=str(selected.get("run_id", ""))[:12])
    # Stop always stops; an escalation whose close could not be committed
    # stays ESCALATED, and the person is told it still needs a ruling.
    for reason in selected.get("ruling_refused", ()):
        said += " " + t("tui.stop.ruling_refused", reason=i18n.denial_text(reason))
    return said


def rule_on(cfg: Config, cycle_id: str, action: str, reason: str) -> list[str]:
    """Record a ruling through `resolve`'s path; what to tell the person."""
    from .main import resolve_cycle

    if not reason.strip():
        return [t("tui.reason.empty")]
    try:
        result = resolve_cycle(cfg, cycle_id, action, reason)
    except Denial as exc:
        return [t("tui.refused", reason=i18n.denial_text(exc.reason))]
    cycle = result["cycle"]
    lines = [t("tui.ruling.recorded", cycle=cycle_id[:12], action=action,
               commit=result["ruling"]["commit"][:12])]
    lines.append(t("tui.ruling.closed") if action == "close" else
                 t("tui.ruling.reopened", status=cycle["status"],
                   round=cycle["round"]))
    return lines


class Session:
    """What this window holds that no projection does: its own task's
    narration, the last panel and message, and decisions put off for later."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.lines: list[str] = []
        self.thread: threading.Thread | None = None
        self.run_id = ""
        self.panel: dict | None = None
        self.message = ""
        self.later: set[str] = set()
        self.verified: dict[tuple, list[str]] = {}

    def add(self, text: str) -> None:
        with self.lock:
            self.lines += [ln for ln in text.split("\n") if ln.strip()]

    @property
    def busy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())


def start_task(cfg: Config, task: str, session: Session) -> None:
    """Run ``task`` through `build`'s own path, in a thread, narrating into
    the session. Preflight and the TASK.md commit happen here, before the
    thread, so a refusal is said at once; Denials propagate to the caller."""
    from ..runtime import PreparedRun, RunCommandService
    from .build import (
        build_exit_code,
        narration_line,
        outcome_lines,
        preflight,
        resolve_task,
        run_loop,
    )

    preflight(cfg)
    prepared_task = resolve_task(cfg, [task])
    service = RunCommandService(cfg)
    produced: set[str] = set()
    final_park = [""]
    with session.lock:
        session.lines = []
    session.add(t("tui.new.started", task=prepared_task.splitlines()[0][:60]))

    def prepare() -> PreparedRun:
        return PreparedRun(task=prepared_task)

    def worker(prepared: PreparedRun, emit) -> int:
        def on_event(event) -> None:
            emit(event)
            final_park[0] = str((event.waiting_reason or {}).get("kind", "") or "")
            if event.kind == "audit_started":
                produced.add("yes")
            line = narration_line(event, verbose=False)
            if line is not None:
                session.add(line)

        # The same handles `cmd_build` carries across its narrator.
        on_event.heartbeat = getattr(emit, "heartbeat", None)
        on_event.run_id = getattr(emit, "run_id", "")
        session.run_id = str(on_event.run_id or "")
        return run_loop(cfg, prepared.task, on_event=on_event)

    def body() -> None:
        try:
            code = service.start(prepare, worker, background=False)
            code = build_exit_code(int(code), final_park[0])
            for line in outcome_lines(cfg, code, produced=bool(produced),
                                      task=prepared_task):
                session.add(line.strip())
        except Denial as exc:
            session.add(t("tui.refused", reason=i18n.denial_text(exc.reason)))
        except KeyboardInterrupt:
            session.add(t("build.interrupted"))
        except Exception as exc:                             # noqa: BLE001
            session.add(t("tui.refused", reason=f"{type(exc).__name__}: {exc}"))

    session.thread = threading.Thread(target=body, name="crossaudit-tui-task",
                                      daemon=True)
    session.thread.start()


# ===================================================================== loop
def _expanded_index(fr: dict, selected: int, expanded_id: str | None) -> bool:
    cycles = fr.get("cycles") or []
    return bool(cycles and 0 <= selected < len(cycles)
                and cycles[selected]["id"] == expanded_id)


def _attach_verification(cfg: Config, fr: dict, cycle_id: str | None,
                         session: Session) -> None:
    """Under the expanded cycle, the head lines `verify` printed for its
    receipt — run by `verify` itself, dry, cached until the state moves."""
    if not cycle_id:
        return
    cycle = next((c for c in fr.get("cycles", []) if c["id"] == cycle_id), None)
    if not cycle or not cycle.get("receipt"):
        return
    rel = cycle["receipt"]["path"]

    def sig(path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0
    key = (rel, sig(cfg.root / rel), sig(cfg.root / cfg.state_dir / "state.json"))
    if key not in session.verified:
        session.verified[key] = receipt_heads(verify_lines(cfg, rel))
    cycle["verified"] = session.verified[key]


def _mode(fr: dict, session: Session, helping: bool) -> str:
    if helping:
        return "help"
    pending = [e for e in fr.get("escalations", [])
               if e["cycle_id"] not in session.later]
    if pending:
        fr["escalations"] = pending
        return "decision"
    return "cycles"


def _compose(cfg: Config, session: Session, selected: int,
             expanded_id: str | None) -> dict:
    fr = frame(cfg)
    if session.lines and (session.busy or session.thread is not None):
        with session.lock:
            fr["run"] = dict(fr["run"], lines=list(session.lines))
    fr["panel"] = session.panel
    fr["message"] = session.message
    _attach_verification(cfg, fr, expanded_id, session)
    return fr


def _size() -> tuple[int, int]:
    size = shutil.get_terminal_size((80, 24))
    return (size.columns or 80, size.lines or 24)


def run_tui(cfg: Config, *, once: bool = False) -> int:
    """The interactive loop at a terminal; one printed frame anywhere else."""
    session = Session()
    interactive = (tui.HAVE_TERMIOS and sys.stdin.isatty()
                   and sys.stdout.isatty())
    if once or not interactive:
        fr = frame(cfg)
        newest = fr["cycles"][0]["id"] if fr.get("cycles") else None
        fr["panel"], fr["message"] = None, ""
        _attach_verification(cfg, fr, newest, session)
        width, _rows = _size()
        print(render(fr, width, ONCE_HEIGHT, selected=0,
                     expanded=newest is not None, mode=_mode(fr, session, False)))
        if not once:
            print(t("tui.once.no_terminal"), file=sys.stderr)
        return 0
    return _loop(cfg, session)


def _read_key(fd: int) -> bytes:
    raw = os.read(fd, 1)
    if raw == b"\x1b" and select.select([fd], [], [], 0.02)[0]:
        raw += os.read(fd, 2)
    return raw


def _loop(cfg: Config, session: Session) -> int:
    import termios
    import tty

    fd = sys.stdin.fileno()
    out = sys.stdout              # captured: a worker may redirect sys.stdout
    saved = termios.tcgetattr(fd)
    selected = 0
    expanded_id: str | None = None
    first = True
    helping = False
    fr: dict = {}

    def draw() -> None:
        nonlocal fr, expanded_id, first, selected
        fr = _compose(cfg, session, selected, expanded_id)
        cycles = fr.get("cycles") or []
        if first:
            # The first frame shows the newest cycle open, as `--once` does.
            expanded_id = cycles[0]["id"] if cycles else None
            first = False
            fr = _compose(cfg, session, selected, expanded_id)
        selected = max(0, min(selected, len(cycles) - 1)) if cycles else 0
        width, rows = _size()
        text = render(fr, width, rows, selected=selected,
                      expanded=_expanded_index(fr, selected, expanded_id),
                      mode=_mode(fr, session, helping))
        out.write("\x1b[H" + text.replace("\n", "\x1b[K\n") + "\x1b[K\x1b[J")
        out.flush()

    def prompt(ask):
        """Leave cbreak for one line of input with `tui.text`/`tui.confirm`."""
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        out.write("\x1b[?25h\x1b[H\x1b[J")
        out.flush()
        try:
            return ask()
        finally:
            tty.setcbreak(fd)
            out.write("\x1b[?25l\x1b[2J")
            out.flush()

    def current_cycle() -> dict | None:
        cycles = fr.get("cycles") or []
        return cycles[selected] if 0 <= selected < len(cycles) else None

    try:
        tty.setcbreak(fd)
        out.write("\x1b[?25l\x1b[2J")
        out.flush()
        draw()
        last = time.monotonic()
        while True:
            interval = LIVE_REFRESH_S if session.busy else REFRESH_S
            wait = max(0.0, interval - (time.monotonic() - last))
            if not select.select([fd], [], [], wait)[0]:
                draw()
                last = time.monotonic()
                continue
            raw = _read_key(fd)
            key = tui.decode(raw)
            ch = raw.decode("utf-8", "ignore") if len(raw) == 1 else ""
            mode = _mode(fr, session, helping)
            handled = True
            if ch == "q":
                break
            if helping:
                if ch == "?" or key == tui.ENTER:
                    helping = False
                else:
                    handled = False
            elif key == tui.ENTER and session.panel:
                session.panel = None
            elif key == tui.UP:
                selected = max(0, selected - 1)
            elif key == tui.DOWN:
                selected = min(max(0, len(fr.get("cycles") or []) - 1), selected + 1)
            elif key == tui.ENTER:
                cycle = current_cycle()
                if cycle is not None:
                    expanded_id = None if expanded_id == cycle["id"] else cycle["id"]
            elif ch == "?":
                helping = True
            elif ch == "n":
                session.panel, session.message = None, ""
                if session.busy:
                    session.message = t("tui.busy")
                else:
                    task = prompt(lambda: tui.text(t("tui.new.prompt")))
                    if not task.strip():
                        session.message = t("tui.new.empty")
                    else:
                        try:
                            start_task(cfg, task, session)
                        except Denial as exc:
                            session.message = t("tui.refused",
                                                reason=i18n.denial_text(exc.reason))
            elif ch in ("v", "a"):
                session.panel, session.message = None, ""
                cycle = current_cycle()
                if session.busy:
                    session.message = t("tui.busy")
                elif not cycle or not cycle.get("receipt"):
                    session.message = t("tui.verify.none")
                elif ch == "v":
                    rel = cycle["receipt"]["path"]
                    session.panel = {"title": t("tui.verify.title", path=rel),
                                     "lines": verify_lines(cfg, rel)}
                else:
                    rel = cycle["receipt"]["path"]
                    if prompt(lambda: tui.confirm(t("tui.admit.confirm"),
                                                  default=False)):
                        session.panel = {"title": t("tui.admit.title", path=rel),
                                         "lines": verify_lines(cfg, rel, admit=True)}
                    else:
                        session.message = t("tui.admit.declined")
            elif ch == "x":
                session.panel = None
                run_id = session.run_id if session.busy else str(
                    (fr.get("run") or {}).get("run_id", ""))
                session.message = (stop_run(cfg, run_id)
                                   if (fr.get("run") or {}).get("state") == "running"
                                   or session.busy else t("tui.stop.none"))
            elif ch == "o":
                session.message = ""
                session.panel = {"title": t("tui.help.console"),
                                 "lines": console_lines(
                                     cfg, open_browser=not session.busy)}
            elif mode == "decision" and ch in ("r", "c", "l"):
                session.panel, session.message = None, ""
                esc = fr["escalations"][0]
                if ch == "l":
                    session.later.add(esc["cycle_id"])
                    session.message = t("tui.later")
                elif session.busy:
                    session.message = t("tui.busy")
                else:
                    action = "reopen" if ch == "r" else "close"
                    question = t("tui.reason.reopen" if ch == "r"
                                 else "tui.reason.close")
                    reason = prompt(lambda q=question: tui.text(q))
                    session.message = " ".join(rule_on(cfg, esc["cycle_id"],
                                                       action, reason))
            else:
                handled = False          # a key the help bar does not list
            if handled:
                draw()
                last = time.monotonic()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        # BSD kernels (macOS) mark a switch back to canonical input with
        # PENDIN, a flag `stty -g` reports, so the terminal would read as
        # changed until something next polls it. Polling it here (ttnread
        # reprocesses pending input and clears the flag; nothing is consumed)
        # leaves the attributes exactly as they were found.
        select.select([fd], [], [], 0)
        out.write("\x1b[?25h\n")
        out.flush()
    return 0
