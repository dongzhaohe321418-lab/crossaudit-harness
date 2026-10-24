"""`crossaudit tui`: the frame, the pure renderer, the verb, and the loop.

docs/design/TUI_FIRST.md §2 and the acceptance rows C37-C39. The renderer is
tested without a terminal (byte-exact frames, widths measured the way a
terminal counts them); the verb through the real `main`; the loop under a real
pseudo-terminal, where the terminal's own `isatty()` and termios state are what
is measured.

D10: each test's name says what it proves; the mutation that turns it red is
named in the docstring where it is not obvious from the name.
"""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import FakeVendors, audit_reply, increment_reply, init_project, with_keys

from crossaudit.cli import i18n, main, tui, tuiapp
from crossaudit.cli.build import narration_line
from crossaudit.errors import EXIT_ESCALATED, EXIT_OK
from crossaudit.gitio import git
from crossaudit.runtime.events import RunEvent
from crossaudit.runtime.runs import RunState

from .test_resolve_commits_the_ruling import ruling_rows

SRC = Path(__file__).resolve().parents[1] / "src"
REASON = "The benchmark is out of scope for this study; stopping after review."


@pytest.fixture(autouse=True)
def _english_and_no_colour(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    i18n.set_language("en")
    i18n.reset_fallbacks()
    yield
    i18n.set_language("en")


# ---------------------------------------------------------- a fixed frame
FIXED_FRAME = {
    "title": "bench-study",
    "generator": "anthropic:claude-sonnet-4-6",
    "auditor": "openai:gpt-5.6-terra",
    "rules_commit": "1e32185d0994",
    "tier": "local",
    "usage": {"today": 0.0008, "month": 1.25, "by_surface": None},
    "run": {"state": "waiting", "lines": []},
    "cycles": [
        {"id": "73fb37d87e66aa00", "status": "ESCALATED", "round": 3,
         "max_rounds": 3, "verdict": "BLOCKED", "sha": "5a3298358524ffff",
         "subject": "benchmark increment (round 3)",
         "ruling": None, "report": True,
         "findings": [{"severity": "BLOCKER", "rule": "CA-TASK-001",
                       "artifact": "experiments/bench/SUMMARY.md",
                       "observation": "The summary states a runtime the "
                                      "results file does not contain.",
                       "tier": "auditor"}],
         "receipt": {"path": "cycles/5a3298358524-r3/receipt.json"},
         "verified": None},
        {"id": "a78b14c81d28bb11", "status": "PASSED", "round": 1,
         "max_rounds": 3, "verdict": "PASS", "sha": "18272370ee32eeee",
         "subject": "benchmark increment", "ruling": None, "report": True,
         "findings": [{"severity": "ADVISORY", "rule": "CA-DATA-001",
                       "artifact": "experiments/bench/results.json",
                       "observation": "A unit is spelled out rather than "
                                      "abbreviated.", "tier": "check"}],
         "receipt": {"path": "cycles/18272370ee32-r1/receipt.json"},
         "verified": ["BINDINGS VERIFIED  receipt f021fcb9120acf96 for 18272370ee32",
                      ("SIGNED  7fc4956c5c14fec5  verifiable offline with the "
                      "project public key"),
                      "ADMISSION READY  latest recorded PASS"]},
        {"id": "0c11aa2b3c4d5e6f", "status": "CLOSED", "round": 2,
         "max_rounds": 3, "verdict": "BLOCKED", "sha": "9f9f9f9f9f9f0000",
         "subject": "", "report": True, "findings": [], "receipt": None,
         "ruling": {"action": "close", "at": "2026-10-22T09:15:00Z"},
         "verified": None},
    ],
    "escalations": [
        {"cycle_id": "73fb37d87e66aa00", "short_sha": "5a3298358524",
         "why": "The summary states a runtime the results file does not contain.",
         "why_zh": None, "round": 3, "max_rounds": 3, "limit_reached": True,
         "attempts": [{"round": 1, "verdict": "BLOCKED", "findings": 1},
                      {"round": 2, "verdict": "BLOCKED", "findings": 1},
                      {"round": 3, "verdict": "BLOCKED", "findings": 1}],
         "issues": [{"severity": "BLOCKER", "rule": "CA-TASK-001",
                     "artifact": "experiments/bench/SUMMARY.md",
                     "observation": "The summary states a runtime the results "
                                    "file does not contain."}],
         "files": ["experiments/bench/SUMMARY.md"]},
    ],
    "panel": None,
    "message": "",
}

EXPECTED_60 = "\n".join([
    'CrossAudit · bench-study',
    'generator anthropic:claude-sonnet-4-6 · auditor openai:gpt-…',
    'rules 1e32185d0994 · admission tier local',
    'usage today ≈$0.0008 · this month ≈$1.25 API value',
    'state: waiting for you',
    '─' * 60,
    'Waiting for you: cycle 73fb37d87e66 at 5a3298358524',
    '  Why it stopped: The summary states a runtime the results',
    '  file does not contain.',
    '  Round 3 of 3; the round limit is reached.',
    '  Verdicts so far: r1 BLOCKED, r2 BLOCKED, r3 BLOCKED',
    '  Still open:',
    '    BLOCKER CA-TASK-001 experiments/bench/SUMMARY.md',
    '      The summary states a runtime the results file does not',
    '      contain.',
    '  Affected files: experiments/bench/SUMMARY.md',
    '  r revise and continue · c stop this task · l later',
    '─' * 60,
    'cycles, newest first',
    '  73fb37d87e66  ESCALATED  3/3  BLOCKED  5a3298358524',
    '❯ a78b14c81d28  PASSED     1/3  PASS     18272370ee32',
    '    commit: benchmark increment',
    '    ADVISORY CA-DATA-001 experiments/bench/results.json',
    '      A unit is spelled out rather than abbreviated.',
    '      (verified by a check)',
    '    receipt: cycles/18272370ee32-r1/receipt.json',
    '      BINDINGS VERIFIED  receipt f021fcb9120acf96 for 18272…',
    '      SIGNED  7fc4956c5c14fec5  verifiable offline with the…',
    '      ADMISSION READY  latest recorded PASS',
    '  0c11aa2b3c4d  CLOSED     2/3  BLOCKED  9f9f9f9f9f9f  ruli…',
    '─' * 60,
    '↑/↓ j/k select · Enter expand · PgUp/PgDn u/d scroll',
    'n new task · v verify · a admit · x stop · o console',
    '? help · q quit',
])

EXPECTED_80 = "\n".join([
    'CrossAudit · bench-study',
    'generator anthropic:claude-sonnet-4-6 · auditor openai:gpt-5.6-terra',
    'rules 1e32185d0994 · admission tier local',
    'usage today ≈$0.0008 · this month ≈$1.25 API value',
    'state: waiting for you',
    '─' * 80,
    'Waiting for you: cycle 73fb37d87e66 at 5a3298358524',
    '  Why it stopped: The summary states a runtime the results file does not',
    '  contain.',
    '  Round 3 of 3; the round limit is reached.',
    '  Verdicts so far: r1 BLOCKED, r2 BLOCKED, r3 BLOCKED',
    '  Still open:',
    '    BLOCKER CA-TASK-001 experiments/bench/SUMMARY.md',
    '      The summary states a runtime the results file does not contain.',
    '  Affected files: experiments/bench/SUMMARY.md',
    '  r revise and continue · c stop this task · l later',
    '─' * 80,
    'cycles, newest first',
    '  73fb37d87e66  ESCALATED  3/3  BLOCKED  5a3298358524',
    '❯ a78b14c81d28  PASSED     1/3  PASS     18272370ee32',
    '    commit: benchmark increment',
    '    ADVISORY CA-DATA-001 experiments/bench/results.json',
    '      A unit is spelled out rather than abbreviated.',
    '      (verified by a check)',
    '    receipt: cycles/18272370ee32-r1/receipt.json',
    '      BINDINGS VERIFIED  receipt f021fcb9120acf96 for 18272370ee32',
    '      SIGNED  7fc4956c5c14fec5  verifiable offline with the project public key',
    '      ADMISSION READY  latest recorded PASS',
    '  0c11aa2b3c4d  CLOSED     2/3  BLOCKED  9f9f9f9f9f9f  ruling: close 2026-10-22…',
    '─' * 80,
    '↑/↓ j/k select · Enter expand · PgUp/PgDn u/d scroll · n new task · v verify',
    'a admit · x stop · o console · ? help · q quit',
])

EXPECTED_120 = "\n".join([
    'CrossAudit · bench-study',
    'generator anthropic:claude-sonnet-4-6 · auditor openai:gpt-5.6-terra',
    'rules 1e32185d0994 · admission tier local',
    'usage today ≈$0.0008 · this month ≈$1.25 API value',
    'state: waiting for you',
    '─' * 120,
    'Waiting for you: cycle 73fb37d87e66 at 5a3298358524',
    '  Why it stopped: The summary states a runtime the results file does not contain.',
    '  Round 3 of 3; the round limit is reached.',
    '  Verdicts so far: r1 BLOCKED, r2 BLOCKED, r3 BLOCKED',
    '  Still open:',
    '    BLOCKER CA-TASK-001 experiments/bench/SUMMARY.md',
    '      The summary states a runtime the results file does not contain.',
    '  Affected files: experiments/bench/SUMMARY.md',
    '  r revise and continue · c stop this task · l later',
    '─' * 120,
    'cycles, newest first',
    '  73fb37d87e66  ESCALATED  3/3  BLOCKED  5a3298358524',
    '❯ a78b14c81d28  PASSED     1/3  PASS     18272370ee32',
    '    commit: benchmark increment',
    '    ADVISORY CA-DATA-001 experiments/bench/results.json',
    '      A unit is spelled out rather than abbreviated.',
    '      (verified by a check)',
    '    receipt: cycles/18272370ee32-r1/receipt.json',
    '      BINDINGS VERIFIED  receipt f021fcb9120acf96 for 18272370ee32',
    '      SIGNED  7fc4956c5c14fec5  verifiable offline with the project public key',
    '      ADMISSION READY  latest recorded PASS',
    '  0c11aa2b3c4d  CLOSED     2/3  BLOCKED  9f9f9f9f9f9f  ruling: close 2026-10-22T09:15:00Z',
    '─' * 120,
    '↑/↓ j/k select · Enter expand · PgUp/PgDn u/d scroll · n new task · v verify · a admit · x stop · o console · ? help',
    'q quit',
])


# ================================================================= render
@pytest.mark.parametrize("width,expected", [(60, EXPECTED_60), (80, EXPECTED_80),
                                            (120, EXPECTED_120)])
def test_render_is_byte_exact_for_a_fixed_frame(width, expected):
    """The decision card, the list newest first, the selected row open to its
    finding, tier word and `verify` lines, the help bar wrapped between keys.
    Any change to what the screen says, or where, turns this red.

    The expected frames changed once, deliberately, when the help bar gained
    "PgUp/PgDn u/d scroll" (the body scrolls on a short terminal); at height
    40 these frames fit, so no scroll indicator appears in them."""
    got = tuiapp.render(FIXED_FRAME, width, 40, selected=1, expanded=True,
                        mode="decision")
    assert got == expected


def test_render_draws_no_colour_when_colour_is_off():
    assert "\x1b" not in tuiapp.render(FIXED_FRAME, 80, 40, selected=0,
                                       expanded=True, mode="decision")


def _zh_frame() -> dict:
    fr = json.loads(json.dumps(FIXED_FRAME))
    fr["title"] = "苯环吸附能基准研究项目"
    fr["cycles"][0]["findings"][0]["observation"] = (
        "摘要中声明的运行时间在结果文件中并不存在，因此这一结论无法从数据追溯。")
    fr["escalations"][0]["why"] = "摘要中声明的运行时间在结果文件中并不存在。"
    fr["run"] = {"state": "running", "phase": "auditing", "round": 2, "limit": 3,
                 "elapsed": 75, "cost": 0.0123, "run_id": "r1",
                 "lines": ["  auditor    读取增量 experiments/苯环/SUMMARY.md 的全部内容"]}
    fr["panel"] = {"title": "verify cycles/x/receipt.json (dry run)",
                   "lines": ["BINDINGS VERIFIED  receipt f021fcb9120acf96 for 18272370ee32"]}
    fr["message"] = "已拒绝：周期处于 PASSED，不是 ESCALATED；只有升级的周期才需要人工裁决"
    return fr


@pytest.mark.parametrize("lang", ["en", "zh"])
@pytest.mark.parametrize("width", [40, 60])
@pytest.mark.parametrize("mode", ["cycles", "decision", "help"])
def test_no_rendered_line_is_wider_than_the_terminal(lang, width, mode):
    """Measured as the terminal counts columns (CJK is two). D10: drop the
    `_fit` in any line builder and a narrow width goes red here."""
    i18n.set_language(lang)
    for fr in (FIXED_FRAME, _zh_frame()):
        for selected in range(3):
            text = tuiapp.render(fr, width, 200, selected=selected,
                                 expanded=True, mode=mode)
            for line in text.split("\n"):
                assert tui._visible(line) <= width, (width, line)


def test_a_narrow_terminal_truncates_with_an_ellipsis():
    text = tuiapp.render(FIXED_FRAME, 40, 200, selected=0, expanded=True)
    assert any(line.endswith(tui.glyph("…", "...")) for line in text.split("\n"))


def test_a_short_terminal_keeps_the_selected_row_on_screen():
    for selected in range(3):
        text = tuiapp.render(FIXED_FRAME, 80, 16, selected=selected,
                             expanded=True, mode="decision")
        lines = text.split("\n")
        assert len(lines) <= 16
        assert any(line.startswith("❯ " + FIXED_FRAME["cycles"][selected]["id"][:12])
                   for line in lines), text


def test_the_activity_pane_shows_the_live_run_with_elapsed_time_and_cost():
    fr = _zh_frame()
    i18n.set_language("en")
    text = tuiapp.render(fr, 100, 60)
    assert "state: running · auditing · round 2 of 3" in text
    assert "activity · 1m 15s elapsed · ≈$0.01 so far" in text
    assert "读取增量" in text


def test_the_usage_line_shows_the_surface_breakdown_only_when_summary_has_it():
    fr = json.loads(json.dumps(FIXED_FRAME))
    assert "cli " not in tuiapp.render(fr, 120, 60).split("\n")[3]
    fr["usage"]["by_surface"] = {"cli": {"calls": 12, "api_value_usd": 0.1},
                                 "tui": {"calls": 3}, "console": {"calls": 0}}
    assert tuiapp.render(fr, 120, 60).split("\n")[3].endswith(
        "API value · cli 12 · tui 3 · console 0")


def test_the_chinese_screen_has_no_english_fallback_and_the_consoles_tier_words():
    i18n.set_language("zh")
    i18n.reset_fallbacks()
    text = tuiapp.render(_zh_frame(), 100, 200, selected=0, expanded=True,
                         mode="decision")
    assert i18n.fallbacks() == ()
    assert i18n.FALLBACK_MARK not in text and "[missing:" not in text
    assert "由审计者提出，尚未复现" in text and "等待你的决定" in text
    help_text = tuiapp.render(_zh_frame(), 100, 200, mode="help")
    assert i18n.fallbacks() == () and "按键" in help_text


def test_the_tier_words_are_the_consoles_own_strings():
    """One vocabulary on two surfaces: the TUI's English catalogue, the
    projection's constants and the console page's `tierWord` must agree. This
    reads the page's script text — it guards drift between three copies; the
    rendered words are asserted by the frame tests above."""
    from crossaudit.console import overview
    from crossaudit.console.page import PAGE

    for key, word in overview.TIER_WORDS.items():
        assert i18n.CATALOGUE["en"][f"tui.tier.{key}"] == word
        assert f"'{word}'" in PAGE
    assert overview.tier_key({"tier": "deterministic"}) == "check"
    assert overview.tier_key({"tier": "model", "verified": True}) == "auditor_verified"
    assert overview.tier_key({"tier": "model"}) == "auditor"
    assert overview.tier_key({}) == ""


# ======================================================= narration_line
def _event(kind, **kw):
    return RunEvent(actor=kw.pop("actor", "loop"), text=kw.pop("text", "x"),
                    state=kw.pop("state", RunState.GENERATING), kind=kind, **kw)


def test_narration_line_says_what_build_printed_before_the_extraction():
    """The literal text `cmd_build`'s inline narrator printed (432fea4)."""
    assert narration_line(_event("round_started", round_no=2, round_limit=3),
                          verbose=False) == "\n  ── round 2 of 3 " + "─" * 32
    assert narration_line(_event("provider_unavailable", text="waiting for provider",
                                 detail="every route failed"),
                          verbose=False) == "  loop       stopped: every route failed"
    assert narration_line(_event("provider_unavailable", text="waiting for provider"),
                          verbose=False) == "  loop       stopped: waiting for provider"
    goal = _event("goal", actor="generator", text="goal set", detail='{"goal": 1}')
    assert narration_line(goal, verbose=False) == "  generator  goal set"
    assert narration_line(goal, verbose=True) == (
        '  generator  goal set\n             {"goal": 1}')
    plain = _event("check_passed", actor="auditor", text="schema ok", detail="d" * 120)
    assert narration_line(plain, verbose=False) == (
        "  auditor    schema ok\n" + " " * 13 + "d" * 96)
    for kind in ("generation_chunk", "thinking_chunk"):
        chunk = RunEvent(actor="generator", text="tok", state=RunState.GENERATING,
                         kind=kind, stream={"id": "s", "seq": 1, "done": False})
        assert narration_line(chunk, verbose=True) is None


def test_narration_line_reads_the_journals_dict_projection_the_same_way():
    event = _event("check_passed", actor="auditor", text="units ok", detail="fine")
    step = {"actor": "auditor", "text": "units ok", "detail": "fine",
            "kind": "check_passed", "round_no": 0, "round_limit": 0}
    assert narration_line(step, verbose=False) == narration_line(event, verbose=False)


# ================================================== the project fixture
def _blocked_answers(role, n, prompt):
    if role == "auditor":
        return audit_reply(prompt, "BLOCKED")
    return increment_reply().replace("seed 7.", f"seed 7 (revision {n}).")


@pytest.fixture()
def project(tmp_path, monkeypatch, capsys):
    """A README-made project with one PASSED cycle and, newer, one ESCALATED
    cycle — both produced by the real `build` loop (transport-faked vendors)."""
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    FakeVendors().install(monkeypatch)
    assert main.main(["build", "Create a small reproducible benchmark"]) == EXIT_OK
    FakeVendors(_blocked_answers).install(monkeypatch)
    assert main.main(["build", "Create a second benchmark"]) == EXIT_ESCALATED
    capsys.readouterr()
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    passed = next(c for c, v in state["cycles"].items() if v["status"] == "PASSED")
    escalated = next(c for c, v in state["cycles"].items()
                     if v["status"] == "ESCALATED")
    return root, passed, escalated


def test_frame_names_both_cycles_newest_first_with_findings_and_receipts(project):
    from crossaudit.config import load

    root, passed, escalated = project
    fr = tuiapp.frame(load())
    assert [c["id"] for c in fr["cycles"]] == [escalated, passed]
    esc, ok = fr["cycles"]
    assert (esc["status"], esc["verdict"], esc["round"]) == ("ESCALATED", "BLOCKED", 3)
    assert (ok["status"], ok["verdict"], ok["round"]) == ("PASSED", "PASS", 1)
    assert esc["findings"] and esc["findings"][0]["severity"] == "BLOCKER"
    assert esc["findings"][0]["tier"] == "auditor"
    assert (root / ok["receipt"]["path"]).is_file()
    assert fr["escalations"][0]["cycle_id"] == escalated
    assert fr["escalations"][0]["files"] == [esc["findings"][0]["artifact"]]
    assert fr["run"]["state"] == "waiting"
    assert fr["generator"] == "anthropic:claude-sonnet-4-6"
    assert fr["auditor"] == "openai:gpt-5.6-terra"
    assert fr["rules_commit"] == git("log", "-1", "--format=%H", "--",
                                     "AUDIT_RULES.md", cwd=root)[:12]


def test_the_snapshot_carries_the_fields_the_terminal_needs(project):
    """Added to the projection, not derived in the TUI: roles, rules commit,
    `closed` on a ruled cycle, the escalation's affected files."""
    from crossaudit.config import load
    from crossaudit.console.server import snapshot

    _root, passed, escalated = project
    cfg = load()
    snap = snapshot(cfg)
    assert snap["roles"] == {"auditor": "openai:gpt-5.6-terra",
                             "generator": "anthropic:claude-sonnet-4-6"}
    assert len(snap["rules_commit"]) == 40
    assert snap["escalations"][0]["files"]
    assert not any(c.get("closed") for c in snap["cycles"])
    main.resolve_cycle(cfg, escalated, "close", REASON)
    closed = {c["id"]: c for c in snapshot(load())["cycles"]}
    assert closed[escalated]["closed"] is True and "closed" not in closed[passed]


def test_tui_once_prints_one_frame_naming_both_cycles_statuses_and_tier_words(
        project, capsys, monkeypatch):
    """C37. No provider is reached: the fake vendors record every call."""
    _root, passed, escalated = project
    vendors = FakeVendors().install(monkeypatch)
    assert main.main(["tui", "--once"]) == EXIT_OK
    out, err = capsys.readouterr()
    assert passed[:12] in out and escalated[:12] in out
    assert "PASSED" in out and "ESCALATED" in out
    assert "raised by the auditor, not yet reproduced" in out
    # The newest cycle is open: its receipt was verified by `verify` itself.
    assert "BINDINGS VERIFIED" in out
    assert err == "" and vendors.calls == []
    assert out.count("cycles, newest first") == 1


def test_tui_without_a_terminal_prints_the_frame_and_says_why_on_stderr(
        project, capsys):
    _root, passed, escalated = project
    assert main.main(["tui"]) == EXIT_OK
    out, err = capsys.readouterr()
    assert passed[:12] in out and escalated[:12] in out
    assert err.strip() == i18n.CATALOGUE["en"]["tui.once.no_terminal"]


def test_tui_once_speaks_chinese_without_falling_back(project, capsys):
    _root, _passed, _escalated = project
    assert main.main(["--lang", "zh", "tui", "--once"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "周期，最新在前" in out and "由审计者提出，尚未复现" in out
    assert "[en]" not in out and "[missing:" not in out


def test_resolve_cycle_records_the_ruling_and_commits_it(project):
    from crossaudit.config import load

    root, _passed, escalated = project
    head = git("rev-parse", "HEAD", cwd=root)
    result = main.resolve_cycle(load(), escalated, "close", REASON)
    assert result["cycle"]["status"] == "BLOCKED" and result["cycle"]["closed_by_human"]
    assert result["ruling"]["commit"] == git("rev-parse", "HEAD", cwd=root) != head
    rows = ruling_rows(root)          # escalation rows are not rulings (D176 r. 43)
    assert [(r["cycle_id"], r["action"], r["reason"]) for r in rows] == [
        (escalated, "close", REASON)]
    assert REASON in git("log", "-1", "--format=%B", cwd=root)


def test_cmd_resolve_prints_exactly_the_lines_it_printed_before(
        project, monkeypatch, capsys):
    root, _passed, escalated = project
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert main.main(["resolve", escalated, "--close", "--because", REASON]) == EXIT_OK
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    commit = git("rev-parse", "HEAD", cwd=root)[:12]
    assert lines[:3] == [
        f"ruling recorded: {escalated} close — {REASON}",
        f"  committed to the ledger: {commit} (cycles/rulings.jsonl)",
        "cycle is now closed (round 3); the increment stays out of the record."]


def test_rule_on_with_an_empty_reason_records_nothing(project):
    from crossaudit.config import load

    root, _passed, escalated = project
    head = git("rev-parse", "HEAD", cwd=root)
    assert tuiapp.rule_on(load(), escalated, "close", "   ") == [
        i18n.CATALOGUE["en"]["tui.reason.empty"]]
    assert git("rev-parse", "HEAD", cwd=root) == head
    assert ruling_rows(root) == []


def test_rule_on_with_a_rejected_commit_shows_the_refusal_and_rules_nothing(project):
    """Review 2026-10-23, finding 2, through the TUI's own call. Mutation
    caught: the state changed before the commit -- the cycle reads BLOCKED and
    the history holds a `human_resolution` the ledger never got."""
    from crossaudit.config import load

    from .test_resolve_commits_the_ruling import REFUSING_HOOK, install_hook

    root, _passed, escalated = project
    install_hook(root, REFUSING_HOOK)
    head = git("rev-parse", "HEAD", cwd=root)
    lines = tuiapp.rule_on(load(), escalated, "close", REASON)
    assert lines == [
        (f"Refused: the ruling on cycle {escalated} could not be committed to the "
        f"ledger (pre-commit: refused by policy); the cycle stays ESCALATED and "
        f"nothing was recorded")]
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][escalated]["status"] == "ESCALATED"
    assert not any(h.get("event") == "human_resolution" for h in state["history"])
    assert ruling_rows(root) == []
    assert git("status", "--porcelain", "--", "cycles", cwd=root) == ""
    assert git("rev-parse", "HEAD", cwd=root) == head


def test_rule_on_a_cycle_that_is_not_escalated_shows_the_refusal(project):
    from crossaudit.config import load

    _root, passed, _escalated = project
    lines = tuiapp.rule_on(load(), passed, "reopen", "try again")
    assert lines[0].startswith("Refused: cycle is PASSED, not ESCALATED")


def test_verify_lines_are_verifys_own_output_and_admit_refuses_in_its_words(project):
    from crossaudit.config import load

    _root, passed, _escalated = project
    cfg = load()
    fr = tuiapp.frame(cfg)
    receipt = next(c for c in fr["cycles"] if c["id"] == passed)["receipt"]["path"]
    lines = tuiapp.verify_lines(cfg, receipt)
    assert lines[0].startswith("BINDINGS VERIFIED")
    assert lines[-1] == "DRY RUN  nothing consumed"
    assert tuiapp.receipt_heads(lines)[0].startswith("BINDINGS VERIFIED")


def test_the_console_key_says_how_to_start_one_when_none_runs(cfg):
    assert tuiapp.console_lines(cfg, open_browser=False) == [
        i18n.CATALOGUE["en"]["tui.console.none"]]


def test_the_stop_key_with_nothing_running_says_so(cfg):
    assert tuiapp.stop_run(cfg) == i18n.CATALOGUE["en"]["tui.stop.none"]


def test_watch_help_points_at_tui():
    parser = main.build_parser()
    sub = next(a for a in parser._actions if getattr(a, "dest", "") == "verb")
    helps = {c.dest: c.help for c in sub._choices_actions}
    assert "read-only" in helps["watch"] and "crossaudit tui" in helps["watch"]
    assert "tui" in sub.choices


# ===================================================== pseudo-terminal
def _spawn_tui(root: Path, rows: int = 60, cols: int = 120, *,
               in_a_shell: bool = False):
    """``crossaudit tui`` on a pty. ``in_a_shell`` runs it the way a person
    (and the claims harness) does: under ``sh -m`` in a session whose
    controlling terminal is the pty, so Ctrl-C there is a real SIGINT, with
    ``stty -g`` printed before and after (the session leader is the shell,
    which outlives the TUI, so the terminal is still there to be read).

    ``-m`` matters on Linux, where ``sh`` is dash: a non-interactive dash
    that receives SIGINT while waiting for a child kills itself once the
    child returns, whatever the child did with the signal, so the
    ``TUI-EXIT=`` line was never printed (seen on ubuntu CI; reproduced on
    macOS with ``/bin/dash`` as ``sh``). With job control dash runs the TUI
    in its own foreground process group, as an interactive shell does, and
    the signal reaches the TUI alone. bash 3.2 (macOS's ``sh``) ignores
    ``-m`` under ``-c`` but, after a SIGINT, carries on when the child caught
    it and exited normally, which is the case here."""
    import fcntl
    import pty
    import struct
    import termios

    leader, follower = pty.openpty()
    fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    before = termios.tcgetattr(follower)
    env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
    env.update(PYTHONPATH=str(SRC), NO_COLOR="1", TERM="xterm-256color")
    env.pop("COLUMNS", None)
    env.pop("LINES", None)
    argv = [sys.executable, "-c",
            "import sys; from crossaudit.cli.main import main; sys.exit(main(['tui']))"]
    extra = {}
    if in_a_shell:
        import shlex

        argv = ["sh", "-m", "-c", "echo STTY=$(stty -g); " + shlex.join(argv)
                + "; echo TUI-EXIT=$?; echo STTY=$(stty -g)"]
        extra["preexec_fn"] = _own_the_terminal     # setsid + ioctl only
    proc = subprocess.Popen(
        argv, cwd=root, env=env, stdin=follower, stdout=follower,
        stderr=follower, close_fds=True, **extra)
    return proc, leader, follower, before


def _own_the_terminal():
    """In the child: a new session whose controlling terminal is the pty, as
    a shell in a terminal window has. Without it the pty has no foreground
    process group, so Ctrl-C there signals nobody. SIGINT is reset to its
    default too: a test run started in the background of a non-interactive
    shell inherits it ignored, and Python then never raises
    KeyboardInterrupt (found when this passed alone and failed in the suite).
    """
    import fcntl
    import signal
    import termios

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class _Screen:
    def __init__(self, leader: int):
        self.leader = leader
        self.seen = ""

    def read_until(self, needle: str, timeout: float = 40.0) -> str:
        """Drain the pty (it must be drained or the child blocks) until
        ``needle`` appears in what arrived since this call began."""
        start = len(self.seen)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if needle in self.seen[start:]:
                return self.seen[start:]
            if select.select([self.leader], [], [], 0.2)[0]:
                try:
                    chunk = os.read(self.leader, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.seen += chunk.decode("utf-8", "ignore")
        raise AssertionError(f"{needle!r} never appeared; last screen:\n"
                             f"{self.seen[-3000:]}")

    def drain(self, seconds: float) -> str:
        start = len(self.seen)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([self.leader], [], [], 0.1)[0]:
                try:
                    chunk = os.read(self.leader, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.seen += chunk.decode("utf-8", "ignore")
        return self.seen[start:]


def _finish(proc, screen, leader, follower):
    deadline = time.monotonic() + 30
    while proc.poll() is None and time.monotonic() < deadline:
        screen.drain(0.2)
    code = proc.wait(timeout=5)
    return code


@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
@pytest.mark.timeout(120)
def test_under_a_pty_j_and_enter_open_the_passed_cycle_and_q_restores_the_terminal(
        project):
    """C38. The real `isatty()` of a pty; the termios state of the terminal is
    compared before and after. D10: remove the `finally` that restores the
    saved attributes and the comparison goes red."""
    import termios

    root, passed, escalated = project
    proc, leader, follower, before = _spawn_tui(root)
    screen = _Screen(leader)
    try:
        first = screen.read_until("q quit")
        assert escalated[:12] in first and passed[:12] in first
        assert "ADMISSION READY" not in first
        os.write(leader, b"j")
        screen.read_until("❯ " + passed[:12])
        os.write(leader, b"\r")
        opened = screen.read_until("ADMISSION READY")
        assert "The latest report has no findings." in opened
        assert "BINDINGS VERIFIED" in opened
        os.write(leader, b"z")              # not on the help bar: does nothing
        os.write(leader, b"q")
        code = _finish(proc, screen, leader, follower)
        after = termios.tcgetattr(follower)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
        os.close(follower)
    assert code == 0, screen.seen[-2000:]
    assert after == before
    assert "\x1b[?25h" in screen.seen[-50:]      # the cursor is given back


@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
@pytest.mark.timeout(120)
def test_under_a_pty_c_with_a_typed_reason_commits_the_ruling(project, capsys):
    """C39 (the C25 criterion): the reason is in `<ledger>/rulings.jsonl`, in
    `git log`, and `status` shows the cycle CLOSED."""
    root, _passed, escalated = project
    proc, leader, follower, _before = _spawn_tui(root)
    screen = _Screen(leader)
    try:
        screen.read_until("c stop this task")
        os.write(leader, b"c")
        screen.read_until("Why stop this task?")
        screen.drain(0.3)
        os.write(leader, REASON.encode() + b"\r")
        screen.read_until("Ruling recorded")
        screen.drain(0.5)
        assert proc.poll() is None, "recording the ruling ended the loop"
        os.write(leader, b"q")
        code = _finish(proc, screen, leader, follower)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
        os.close(follower)
    assert code == 0, screen.seen[-2000:]
    rows = ruling_rows(root)          # escalation rows are not rulings (D176 r. 43)
    assert [(r["cycle_id"], r["action"], r["reason"]) for r in rows] == [
        (escalated, "close", REASON)]
    assert REASON in git("log", "-1", "--format=%B", cwd=root)
    capsys.readouterr()
    assert main.main(["status"]) == EXIT_OK
    line = next(ln for ln in capsys.readouterr().out.splitlines()
                if ln.startswith(escalated))
    assert "CLOSED" in line


@pytest.mark.timeout(120)
def test_the_new_task_key_runs_builds_own_loop_in_a_thread_and_says_its_outcome(
        tmp_path, monkeypatch, capsys):
    """`n` reaches `run_loop` through `RunCommandService` exactly as `build`
    does: the cycle passes, the run is journalled, the narration is build's,
    and the closing sentence is build's own."""
    from crossaudit.config import load
    from crossaudit.runtime import RunJournal, journal_path

    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    FakeVendors().install(monkeypatch)
    cfg = load()
    session = tuiapp.Session()
    tuiapp.start_task(cfg, "Create a small reproducible benchmark", session)
    session.thread.join(90)
    assert not session.busy
    assert session.lines[-2:] == [i18n.CATALOGUE["en"]["build.done"],
                                  i18n.CATALOGUE["en"]["build.done.read"]]
    assert any(line.lstrip().startswith("── round 1 of") for line in session.lines)
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert [c["status"] for c in state["cycles"].values()] == ["PASSED"]
    latest = RunJournal(journal_path(cfg)).latest()
    assert latest["run_id"] == session.run_id and latest["state"] == "PASSED"
    assert "task: Create a small reproducible benchmark" in git(
        "log", "--format=%s", cwd=root)


@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
@pytest.mark.timeout(120)
def test_under_a_pty_j_only_moves_and_enter_opens_the_row_without_quitting(project):
    """The C38 harness defect: `j` must move the cursor and nothing else, and
    Enter must open the selected row and leave the loop running. Typed at the
    harness's pace (Enter, then 0.5 s, then the check). D10: make Enter break
    the loop, or let moving the cursor expand the row, and this goes red."""
    root, passed, _escalated = project
    proc, leader, follower, _before = _spawn_tui(root)
    screen = _Screen(leader)
    try:
        screen.read_until("q quit")
        os.write(leader, b"j")
        moved = screen.read_until("❯ " + passed[:12])
        moved += screen.drain(0.5)
        assert "The latest report has no findings." not in moved
        assert "ADMISSION READY" not in moved
        os.write(leader, b"\r")
        opened = screen.drain(0.5)
        assert proc.poll() is None, "Enter ended the loop"
        assert "The latest report has no findings." in opened
        assert "ADMISSION READY" in opened
        os.write(leader, b"\r")             # Enter again closes the row ...
        closed = screen.drain(0.5)
        assert proc.poll() is None, "a second Enter ended the loop"
        assert "q quit" in closed and "ADMISSION READY" not in closed
        os.write(leader, b"q")              # ... and only q quits
        code = _finish(proc, screen, leader, follower)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
        os.close(follower)
    assert code == 0, screen.seen[-2000:]


# ============================================ a terminal shorter than the frame
def _tall_frame() -> dict:
    """FIXED_FRAME with two more findings on the newest cycle: 38 lines at
    width 60 with that cycle selected and open, against a 24-line terminal."""
    fr = json.loads(json.dumps(FIXED_FRAME))
    fr["cycles"][0]["findings"] += [
        {"severity": "ADVISORY", "rule": "CA-META-002",
         "artifact": "experiments/bench/metadata.yml",
         "observation": "The seed is not recorded.", "tier": ""},
        {"severity": "BLOCKER", "rule": "CA-DATA-004",
         "artifact": "experiments/bench/results.json",
         "observation": "A quantity has no unit.", "tier": "check"}]
    return fr


def _render_tall(height, scroll=None):
    return tuiapp.render(_tall_frame(), 60, height, selected=0, expanded=True,
                         mode="decision", scroll=scroll)


def test_a_short_terminal_gets_exactly_its_height_and_says_what_is_hidden():
    """24 lines for a 38-line frame: header first, help bar last, the body cut
    with a line saying how many lines are below and which key shows them.
    D10: drop the indicator (silent clipping, the walk's finding) or let the
    frame run past the terminal and this goes red."""
    whole = _render_tall(tuiapp.ONCE_HEIGHT).split("\n")
    assert len(whole) == 38                      # --once still prints it all
    lines = _render_tall(24).split("\n")
    assert len(lines) == 24
    assert lines[0] == whole[0] == "CrossAudit · bench-study"
    assert lines[-3:] == whole[-3:]               # the help bar, whole, last
    assert lines[-1] == "? help · q quit"
    below = [ln for ln in lines if "more lines (PageDown)" in ln]
    assert len(below) == 1
    head, body, _focus, foot = tuiapp._sections(
        _tall_frame(), 60, selected=0, expanded=True, mode="decision")
    above = [ln for ln in lines if "above (PageUp)" in ln]
    hidden_above = int(re.search(r"(\d+)", above[0]).group(1)) if above else 0
    shown = 24 - len(head) - len(foot) - len(above) - 1
    assert below[0] == (f"… {len(body) - hidden_above - shown} "
                        f"more lines (PageDown)")


def test_scrolling_moves_the_window_and_both_indicators_account_for_every_line():
    """Swept over every scroll position, not sampled: each frame is exactly 24
    lines, shows a contiguous run of the body, and above + shown + below is
    the whole body. D10: an off-by-one in the window (a line lost between the
    indicator and the run) fails at the position where it happens."""
    fr = _tall_frame()
    head, body, _focus, foot = tuiapp._sections(fr, 60, selected=0, expanded=True,
                                                mode="decision")
    seen_first = []
    for scroll in range(len(body) + 3):
        lines = _render_tall(24, scroll).split("\n")
        assert len(lines) == 24, scroll
        middle = lines[len(head):24 - len(foot)]
        above = (int(re.search(r"(\d+) more lines? above", middle[0]).group(1))
                 if "above (PageUp)" in middle[0] else 0)
        below = (int(re.search(r"(\d+) more lines? \(PageDown\)", middle[-1]).group(1))
                 if "(PageDown)" in middle[-1] else 0)
        shown = middle[(1 if above else 0):len(middle) - (1 if below else 0)]
        assert shown == body[above:above + len(shown)], scroll
        assert above + len(shown) + below == len(body), scroll
        seen_first.append(above)
    assert seen_first[0] == 0 and max(seen_first) == len(body) - (24 - len(head)
                                                                   - len(foot) - 1)
    assert seen_first == sorted(seen_first)


def test_the_indicator_speaks_chinese():
    i18n.set_language("zh")
    text = _render_tall(24)
    assert re.search(r"… \d+ 行未显示（PageDown）", text)
    text = _render_tall(24, scroll=5)
    assert "… 上方还有 5 行（PageUp）" in text


def test_one_hidden_line_is_said_in_the_singular():
    fr = _tall_frame()
    whole = len(tuiapp.render(fr, 60, tuiapp.ONCE_HEIGHT, selected=0,
                              expanded=True, mode="decision").split("\n"))
    text = tuiapp.render(fr, 60, whole - 1, selected=0, expanded=True,
                         mode="decision", scroll=0)
    assert "… 2 more lines (PageDown)" in text  # the indicator takes a line too
    text = tuiapp.render(fr, 60, whole - 1, selected=0, expanded=True,
                         mode="decision", scroll=99)
    assert "… 2 more lines above (PageUp)" in text
    text = tuiapp.render(fr, 60, whole - 1, selected=0, expanded=True,
                         mode="decision", scroll=1)
    assert "… 1 more line above (PageUp)" in text


@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
@pytest.mark.timeout(120)
def test_under_a_24_line_pty_page_down_brings_the_receipt_lines_into_view(project):
    """The walk's finding, at a real 24-line terminal: the open cycle's receipt
    lines are below the fold and say so; PageDown (ESC [ 6 ~) shows them, `u`
    pages back. D10: read only three bytes of an escape sequence (the old
    `_read_key`) and PageDown arrives as ESC [ 6 plus a stray `~`: nothing
    scrolls and this goes red."""
    root, _passed, _escalated = project
    proc, leader, follower, _before = _spawn_tui(root, rows=24, cols=100)
    screen = _Screen(leader)
    try:
        first = screen.read_until("q quit")
        first += screen.drain(1.0)
        assert "more lines (PageDown)" in first
        assert "BINDINGS VERIFIED" not in first
        os.write(leader, b"\x1b[6~")
        paged = screen.read_until("BINDINGS VERIFIED")
        assert "above (PageUp)" in paged
        os.write(leader, b"u")
        screen.read_until("Waiting for you")
        assert proc.poll() is None
        os.write(leader, b"q")
        code = _finish(proc, screen, leader, follower)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
        os.close(follower)
    assert code == 0, screen.seen[-2000:]


# ================================================ a stream that is not UTF-8
def _once_under(root, encoding, *args):
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith("_proxy") and k != "PYTHONUTF8"}
    env.update(PYTHONPATH=str(SRC), NO_COLOR="1", PYTHONIOENCODING=encoding,
               COLUMNS="100")
    return subprocess.run(
        [sys.executable, "-c",
         "import sys; from crossaudit.cli.main import main; sys.exit(main())",
         *args, "tui", "--once"],
        cwd=root, env=env, capture_output=True, timeout=120, check=False)


@pytest.mark.timeout(120)
def test_an_ascii_stream_gets_ascii_glyphs_and_never_a_traceback(project):
    """`PYTHONIOENCODING=ascii crossaudit tui --once` tracebacked on the `·`
    in the header. D10: remove `_degrade` and `_write` and this exits 1 with
    UnicodeEncodeError."""
    root, passed, escalated = project
    for lang in ([], ["--lang", "zh"]):
        proc = _once_under(root, "ascii", *lang)
        assert proc.returncode == 0, proc.stderr.decode("ascii", "replace")
        assert b"Traceback" not in proc.stderr
        out = proc.stdout.decode("ascii")            # nothing but ASCII
        assert passed[:12] in out and escalated[:12] in out
        assert "~$" in out                           # ≈ -> ~
        assert "> " + escalated[:12] in out           # ❯ -> >
        assert "^/v j/k" in out                       # ↑/↓ -> ^/v
        assert "-" * 100 in out                       # ─ -> -
    english = _once_under(root, "ascii").stdout.decode("ascii")
    assert "CrossAudit - proj" in english            # · -> -


@pytest.mark.timeout(120)
def test_a_gbk_stream_keeps_the_chinese_and_the_glyphs_gbk_has(project):
    root, passed, escalated = project
    for lang in ([], ["--lang", "zh"]):
        proc = _once_under(root, "gbk", *lang)
        assert proc.returncode == 0, proc.stderr.decode("gbk", "replace")
        assert b"Traceback" not in proc.stderr
        out = proc.stdout.decode("gbk")
        assert passed[:12] in out and escalated[:12] in out
        assert "> " + escalated[:12] in out           # GBK has no ❯
    out = _once_under(root, "gbk", "--lang", "zh").stdout.decode("gbk")
    assert "周期，最新在前" in out and "由审计者提出，尚未复现" in out
    assert "≈" in out and "·" in out                   # GBK has these


# ====================================================== Ctrl-C at a prompt
@pytest.mark.skipif(sys.platform == "win32", reason="pty does not exist on Windows")
@pytest.mark.timeout(120)
def test_ctrl_c_at_a_prompt_cancels_the_prompt_not_the_window(project):
    """Ctrl-C at the `n` prompt and at the reason prompt returns to the frame
    with "cancelled"; nothing is started or ruled; then Ctrl-C in the loop
    still quits with the terminal restored. D10: drop the KeyboardInterrupt
    arm in `prompt` and the first Ctrl-C ends the TUI (exit 20)."""
    root, _passed, escalated = project
    head = git("rev-parse", "HEAD", cwd=root)
    proc, leader, follower, _before = _spawn_tui(root, in_a_shell=True)
    screen = _Screen(leader)
    try:
        screen.read_until("q quit")
        os.write(leader, b"n")
        screen.read_until("What should be built?")
        screen.drain(0.3)
        os.write(leader, b"\x03")
        back = screen.read_until("cancelled")
        assert "q quit" in back + screen.drain(0.5)
        assert proc.poll() is None, "Ctrl-C at the task prompt ended the TUI"
        os.write(leader, b"c")
        screen.read_until("Why stop this task?")
        screen.drain(0.3)
        os.write(leader, b"half a reason\x03")
        screen.read_until("cancelled")
        screen.drain(0.5)
        assert proc.poll() is None, "Ctrl-C at the reason prompt ended the TUI"
        os.write(leader, b"\x03")                 # in the loop: quits
        screen.read_until("TUI-EXIT=")
        screen.read_until("STTY=")
        screen.drain(0.5)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
        os.close(follower)
    stty = re.findall(r"STTY=(\S+)", screen.seen)
    assert len(stty) == 2 and stty[0] == stty[1], stty  # terminal restored
    exit_code = int(re.search(r"TUI-EXIT=(\d+)", screen.seen).group(1))
    assert exit_code != 0                     # interrupted, as before
    assert git("rev-parse", "HEAD", cwd=root) == head    # no task, no ruling
    state = json.loads((root / ".crossaudit" / "state.json").read_text())
    assert state["cycles"][escalated]["status"] == "ESCALATED"
