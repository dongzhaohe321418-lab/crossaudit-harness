"""`crossaudit tui` — the loop, live, in the terminal, and the place to act on it.

docs/design/TUI_FIRST.md §2. Three layers, each testable on its own:

* ``frame(cfg)`` gathers one screen's worth of plain data from the projections
  the console and `status` already use (``console.server.snapshot``,
  ``console.overview``, ``rulings.by_cycle``, ``watch.gather``). Nothing is
  derived here that a projection could carry; where one lacked a field, the
  field was added to the projection.
* ``render(frame, width, height, ...)`` turns that data into the text of one
  screen. Pure relative to its arguments and three settings it reads and never
  changes: the current language (``i18n``), the stdout encoding (a glyph the
  stream cannot encode falls back to ASCII) and whether colour is on
  (``tui.coloured()``: stdout is a TTY and ``NO_COLOR`` is unset). It reads no
  clock, no file and no key, and writes nothing. Every line is measured as the
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
    text = _degrade(text)        # measured as it will be drawn
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
    keys = ("select", "expand", "scroll", "new", "verify", "admit", "stop", "console",
            "decision", "help", "quit")
    out = [tui.bold(_fit(t("tui.help.title"), width))]
    for key in keys:
        out += _wrapped(t(f"tui.help.{key}"), width, 2)
    return out


#: Every non-ASCII glyph the screen draws on its own account, and the ASCII
#: it falls back to on a stream that cannot encode it (a Windows console at
#: cp1252 or cp936, ``PYTHONIOENCODING=ascii``), the way the wizard degrades.
GLYPH_FALLBACKS = {"·": "-", "≈": "~", "❯": ">", "…": "...", "─": "-",
                   "↑": "^", "↓": "v"}


def _degrade(text: str) -> str:
    """``text`` with each glyph the stream cannot encode replaced by its ASCII
    fallback, decided per glyph through `tui.glyph` (so a GBK console keeps
    the ones GBK has)."""
    table = {ch: tui.glyph(ch, fallback) for ch, fallback in GLYPH_FALLBACKS.items()}
    if all(ch == got for ch, got in table.items()):
        return text
    return "".join(table.get(ch, ch) for ch in text)


def _sections(frame: dict, width: int, *, selected: int, expanded: bool,
              mode: str) -> tuple[list[str], list[str], int, list[str]]:
    """(header, body, the body line of the selected row, footer)."""
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
    return head, body, focus, foot


def _more(key: str, n: int, width: int) -> str:
    said = t(key + (".plural" if n != 1 else ""), n=n)
    return tui.dim(_fit(tui.glyph("…", "...") + " " + said, width))


def _window(body_len: int, focus: int, room: int,
            scroll: int | None) -> tuple[int, int, bool, bool]:
    """Which body lines fit in ``room`` lines: (start, count, hidden above,
    hidden below). An indicator line takes the place of a body line at each
    end that hides something. ``scroll`` None follows the selection."""
    if body_len <= room:
        return 0, body_len, False, False
    if room < 3:
        # No space for indicators and content both: show what fits.
        start = max(0, min(focus, body_len - room)) if scroll is None else \
            max(0, min(scroll, body_len - room))
        return start, room, False, False
    if scroll is None:
        # Follow the selection with as little movement as possible: from the
        # top while the selected row is on the first screen (so the decision
        # card stays whole above it), else with the row a third of the way
        # down so what it opens to is in view.
        start = (0 if focus < room - 1 else
                 max(0, min(focus - (room - 2) // 3, body_len - (room - 1))))
    else:
        start = max(0, min(scroll, body_len - (room - 1)))
    above = start > 0
    count = room - (1 if above else 0)
    below = start + count < body_len
    if below:
        count -= 1
    return start, count, above, below


def view(frame: dict, width: int, height: int, *, selected: int = 0,
         expanded: bool = False, mode: str = "cycles",
         scroll: int | None = None) -> dict:
    """Where the body window falls for these arguments: ``start`` (first body
    line shown), ``count`` (body lines shown), ``total`` body lines and
    ``room`` (lines the body may use). The loop pages with it."""
    width = max(1, int(width))
    height = max(1, int(height))
    head, body, focus, foot = _sections(frame, width, selected=selected,
                                        expanded=expanded, mode=mode)
    room = max(0, height - len(head) - len(foot))
    start, count, _above, _below = _window(len(body), focus, room, scroll)
    return {"start": start, "count": count, "total": len(body), "room": room}


def render(frame: dict, width: int, height: int, *, selected: int = 0,
           expanded: bool = False, mode: str = "cycles",
           scroll: int | None = None) -> str:
    """The text of one screen. Pure relative to its arguments and three settings it
    reads and never changes: the same arguments give the same text for the same
    language (``i18n.language()``), the same stdout encoding (glyphs the stream
    cannot encode fall back to ASCII) and the same colour setting
    (``tui.coloured()``: stdout is a TTY and ``NO_COLOR`` is unset). It reads
    no clock, no file and no key, and writes nothing.

    ``mode`` is "cycles" (the list), "decision" (the decision card above the
    list, while a cycle waits for a person), or "help" (the key overlay).
    ``expanded`` opens the ``selected`` row to its findings and receipt.
    No line is wider than ``width`` columns. When the body (decision card and
    cycles) is taller than the space between header and help bar, the frame
    is exactly ``height`` lines: the body scrolls (``scroll`` is the first body
    line shown; None follows the selection) and a line at each end that hides
    something says how many lines are hidden there and which key shows them.
    Glyphs the output stream cannot encode are drawn in ASCII.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    head, body, focus, foot = _sections(frame, width, selected=selected,
                                        expanded=expanded, mode=mode)
    room = height - len(head) - len(foot)
    if room <= 0:
        # Not even the header and help bar fit: keep the help bar whole at
        # the bottom and as much header as there is room for above it.
        foot = foot[-height:]
        lines = head[:height - len(foot)] + foot
        return _degrade("\n".join(lines))
    start, count, above, below = _window(len(body), focus, room, scroll)
    shown = body[start:start + count]
    if above:
        shown = [_more("tui.more.above", start, width)] + shown
    if below:
        shown = shown + [_more("tui.more.below", len(body) - start - count, width)]
    return _degrade("\n".join(head + shown + foot))


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
    if result.get("reconciled"):
        row = result["ruling"]
        lines = [t("ruling.reconciled", at=row.get("at", ""),
                   action=row.get("action", ""), sha=str(row.get("commit", ""))[:12])]
    else:
        lines = [t("tui.ruling.recorded", cycle=cycle_id[:12], action=action,
                   commit=result["ruling"]["commit"][:12])]
        if result.get("intent_cleared"):
            lines.append(t("ruling.intent_cleared"))
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
                         session: Session, *, compute: bool = True) -> bool:
    """Under the expanded cycle, the head lines `verify` printed for its
    receipt — run by `verify` itself, dry, cached until the state moves.

    With ``compute`` False only a cached answer is attached, so a keypress can
    be drawn at once. Returns whether an answer is still owed (a receipt whose
    lines are not cached yet)."""
    if not cycle_id:
        return False
    cycle = next((c for c in fr.get("cycles", []) if c["id"] == cycle_id), None)
    if not cycle or not cycle.get("receipt"):
        return False
    rel = cycle["receipt"]["path"]

    def sig(path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0
    key = (rel, sig(cfg.root / rel), sig(cfg.root / cfg.state_dir / "state.json"))
    if key not in session.verified:
        if not compute:
            return True
        session.verified[key] = receipt_heads(verify_lines(cfg, rel))
    cycle["verified"] = session.verified[key]
    return False


def _mode(fr: dict, session: Session, helping: bool) -> str:
    if helping:
        return "help"
    pending = [e for e in fr.get("escalations", [])
               if e["cycle_id"] not in session.later]
    if pending:
        fr["escalations"] = pending
        return "decision"
    return "cycles"


def _overlay(data: dict, session: Session) -> dict:
    """The last gathered frame with this window's own state laid over it.

    A copy deep enough that attaching `verify` lines or narrowing the
    escalations never edits the gathered frame, which is reused between
    data refreshes so a keypress is drawn without gathering again."""
    fr = dict(data)
    fr["cycles"] = [dict(c) for c in data.get("cycles", [])]
    fr["escalations"] = list(data.get("escalations", []))
    if session.lines and (session.busy or session.thread is not None):
        with session.lock:
            fr["run"] = dict(fr.get("run") or {}, lines=list(session.lines))
    fr["panel"] = session.panel
    fr["message"] = session.message
    return fr


def _size() -> tuple[int, int]:
    size = shutil.get_terminal_size((80, 24))
    return (size.columns or 80, size.lines or 24)


def _printable(text: str, stream=None) -> str:
    """``text`` as ``stream`` can encode it: unencodable characters become
    the codec's replacement, never an exception (the last resort behind the
    ASCII glyph fallbacks)."""
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        try:
            return text.encode(encoding, "replace").decode(encoding)
        except LookupError:
            return text.encode("ascii", "replace").decode("ascii")


def _write(stream, text: str) -> None:
    stream.write(_printable(text, stream))
    stream.flush()


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
        _write(sys.stdout, render(fr, width, ONCE_HEIGHT, selected=0,
                                  expanded=newest is not None,
                                  mode=_mode(fr, session, False)) + "\n")
        if not once:
            _write(sys.stderr, t("tui.once.no_terminal") + "\n")
        return 0
    return _loop(cfg, session)


#: The escape sequences the loop reads as paging keys.
PAGE_UP, PAGE_DOWN = b"\x1b[5~", b"\x1b[6~"


def _read_key(fd: int) -> bytes:
    """One keypress: a byte, or a whole escape sequence (arrows are three
    bytes, PageUp/PageDown four), read while its bytes keep arriving."""
    raw = os.read(fd, 1)
    if raw == b"\x1b":
        while len(raw) < 8 and select.select([fd], [], [], 0.02)[0]:
            got = os.read(fd, 1)
            if not got:
                break
            raw += got
            if raw[-1:].isalpha() or raw[-1:] == b"~":
                break
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
    #: The first body line shown, once the person has paged; None follows
    #: the selection. Moving the selection or opening a row follows it again.
    scroll: int | None = None
    fr: dict = {}

    data: dict = {}
    #: The timer's gathering runs off the key loop, so a key pressed while
    #: the projections are being read is answered at once. ``generation``
    #: moves when an action gathers synchronously, and a background result
    #: started before it is dropped rather than drawn over the newer one.
    background: dict = {"thread": None, "result": None, "generation": 0}

    def gather_in_background() -> None:
        if background["thread"] is not None and background["thread"].is_alive():
            return
        started = background["generation"]

        def work() -> None:
            try:
                result = frame(cfg)
            except Exception:                                # noqa: BLE001
                return            # keep showing the last frame; retry next tick
            if background["generation"] == started:
                background["result"] = result

        background["thread"] = threading.Thread(
            target=work, name="crossaudit-tui-gather", daemon=True)
        background["thread"].start()

    def draw(*, fresh: bool = False, compute: bool = True) -> bool:
        """Draw one frame. ``fresh`` gathers the projections again (the timer,
        and after an action that changed something); otherwise the last
        gathered frame is re-rendered, which is what makes a keypress instant.
        Returns whether `verify` lines for the open cycle are still owed."""
        nonlocal fr, expanded_id, first, selected, data
        if fresh or not data:
            background["generation"] += 1
            background["result"] = None
            data = frame(cfg)
        fr = _overlay(data, session)
        cycles = fr.get("cycles") or []
        if first:
            # The first frame shows the newest cycle open, as `--once` does.
            expanded_id = cycles[0]["id"] if cycles else None
            first = False
        selected = max(0, min(selected, len(cycles) - 1)) if cycles else 0
        owed = _attach_verification(cfg, fr, expanded_id, session,
                                    compute=False)
        if owed and compute and not session.busy:
            # `verify` swaps sys.stdout to capture itself, so it never runs
            # beside the warmer or a task's own audit (which does the same).
            settle()
            owed = _attach_verification(cfg, fr, expanded_id, session)
        width, rows = _size()
        text = render(fr, width, rows, **layout())
        _write(out, "\x1b[H" + text.replace("\n", "\x1b[K\n") + "\x1b[K\x1b[J")
        return owed

    def layout() -> dict:
        return {"selected": selected,
                "expanded": _expanded_index(fr, selected, expanded_id),
                "mode": _mode(fr, session, helping), "scroll": scroll}

    def page(direction: int) -> None:
        nonlocal scroll
        width, rows = _size()
        where = view(fr, width, rows, **layout())
        step = max(1, where["room"] - 2)
        scroll = max(0, min(where["start"] + direction * step,
                            max(0, where["total"] - 1)))

    warmer: dict = {"thread": None}

    def warm() -> None:
        """Off the key loop, run `verify` for every listed receipt not yet
        cached, so Enter opens a row with its lines already known."""
        if session.busy or (warmer["thread"] is not None
                            and warmer["thread"].is_alive()):
            return
        cycles = [dict(c) for c in data.get("cycles", []) if c.get("receipt")]

        def work() -> None:
            for cycle in cycles:
                try:
                    _attach_verification(cfg, {"cycles": [cycle]}, cycle["id"],
                                         session)
                except Exception:                            # noqa: BLE001
                    return

        warmer["thread"] = threading.Thread(target=work, daemon=True,
                                            name="crossaudit-tui-verify")
        warmer["thread"].start()

    def settle() -> None:
        """Wait for the verify warmer: `verify` captures stdout by swapping
        ``sys.stdout``, so nothing that prints to it (a prompt, a verify of
        our own) may run beside it."""
        if warmer["thread"] is not None:
            warmer["thread"].join()

    def prompt(ask):
        """Leave cbreak for one line of input with `tui.text`/`tui.confirm`.

        Ctrl-C at the prompt cancels the prompt, not the window: it returns
        None and the caller says "cancelled" on the frame it goes back to."""
        settle()
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        _write(out, "\x1b[?25h\x1b[H\x1b[J")
        try:
            return ask()
        except (KeyboardInterrupt, EOFError):
            _write(out, "\n")
            return None
        finally:
            tty.setcbreak(fd)
            _write(out, "\x1b[?25l\x1b[2J")

    def current_cycle() -> dict | None:
        cycles = fr.get("cycles") or []
        return cycles[selected] if 0 <= selected < len(cycles) else None

    try:
        tty.setcbreak(fd)
        _write(out, "\x1b[?25l\x1b[2J")
        draw()
        warm()
        last = time.monotonic()
        while True:
            interval = LIVE_REFRESH_S if session.busy else REFRESH_S
            if time.monotonic() - last >= interval:
                gather_in_background()
                last = time.monotonic()
            if background["result"] is not None:
                data, background["result"] = background["result"], None
                draw()
                warm()
                continue
            if not select.select([fd], [], [], 0.1)[0]:
                continue
            raw = _read_key(fd)
            if not raw:
                # A read of nothing after select() said "readable" is the
                # terminal hanging up (cbreak reads block for one byte), not
                # a key: there is no one left to draw for.
                break
            key = tui.decode(raw)
            ch = raw.decode("utf-8", "ignore") if len(raw) == 1 else ""
            mode = _mode(fr, session, helping)
            handled = True
            changed = False          # did the action change the record?
            if ch == "q":
                break
            if helping:
                if ch == "?" or key == tui.ENTER:
                    helping = False
                else:
                    handled = False
            elif key == tui.ENTER and session.panel:
                session.panel = None
            elif raw == PAGE_UP or ch == "u":
                page(-1)
            elif raw == PAGE_DOWN or ch == "d":
                page(+1)
            elif key == tui.UP:
                selected, scroll = max(0, selected - 1), None
            elif key == tui.DOWN:
                selected = min(max(0, len(fr.get("cycles") or []) - 1), selected + 1)
                scroll = None
            elif key == tui.ENTER:
                scroll = None
                cycle = current_cycle()
                if cycle is not None:
                    expanded_id = None if expanded_id == cycle["id"] else cycle["id"]
            elif ch == "?":
                helping = True
            elif ch == "n":
                session.panel, session.message = None, ""
                changed = True
                if session.busy:
                    session.message = t("tui.busy")
                else:
                    task = prompt(lambda: tui.text(_printable(t("tui.new.prompt"))))
                    if task is None:
                        session.message = t("tui.cancelled")
                    elif not task.strip():
                        session.message = t("tui.new.empty")
                    else:
                        try:
                            start_task(cfg, task, session)
                        except Denial as exc:
                            session.message = t("tui.refused",
                                                reason=i18n.denial_text(exc.reason))
            elif ch in ("v", "a"):
                session.panel, session.message = None, ""
                changed = True
                cycle = current_cycle()
                if session.busy:
                    session.message = t("tui.busy")
                elif not cycle or not cycle.get("receipt"):
                    session.message = t("tui.verify.none")
                elif ch == "v":
                    settle()
                    rel = cycle["receipt"]["path"]
                    session.panel = {"title": t("tui.verify.title", path=rel),
                                     "lines": verify_lines(cfg, rel)}
                else:
                    rel = cycle["receipt"]["path"]
                    answer = prompt(lambda: tui.confirm(
                        _printable(t("tui.admit.confirm")), default=False))
                    if answer is None:
                        session.message = t("tui.cancelled")
                    elif answer:
                        session.panel = {"title": t("tui.admit.title", path=rel),
                                         "lines": verify_lines(cfg, rel, admit=True)}
                    else:
                        session.message = t("tui.admit.declined")
            elif ch == "x":
                session.panel = None
                changed = True
                run_id = session.run_id if session.busy else str(
                    (fr.get("run") or {}).get("run_id", ""))
                session.message = (stop_run(cfg, run_id)
                                   if (fr.get("run") or {}).get("state") == "running"
                                   or session.busy else t("tui.stop.none"))
            elif ch == "o":
                settle()
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
                    changed = True
                    action = "reopen" if ch == "r" else "close"
                    question = t("tui.reason.reopen" if ch == "r"
                                 else "tui.reason.close")
                    reason = prompt(lambda q=question: tui.text(_printable(q)))
                    session.message = (t("tui.cancelled") if reason is None else
                                       " ".join(rule_on(cfg, esc["cycle_id"],
                                                        action, reason)))
            else:
                handled = False          # a key the help bar does not list
            if handled:
                # Drawn at once from the last gathered frame; an action that
                # changed the record gathers again. `verify` lines for a row
                # Enter just opened follow in a second draw, so the row opens
                # without waiting for them.
                if draw(fresh=changed, compute=False):
                    draw()               # settles the warmer, then verifies
                warm()
                if changed:
                    last = time.monotonic()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        # BSD kernels (macOS) mark a switch back to canonical input with
        # PENDIN, a flag `stty -g` reports, so the terminal would read as
        # changed until something next polls it. Polling it here (ttnread
        # reprocesses pending input and clears the flag; nothing is consumed)
        # leaves the attributes exactly as they were found.
        select.select([fd], [], [], 0)
        _write(out, "\x1b[?25h\n")
    return 0
