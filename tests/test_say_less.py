"""Say less, and say it in words (D149).

Five defects from one real 4.16.0 run, each pinned here through the SHIPPED
surface rather than through a string in the source:

* S1 the thinking animation carried no information — it is now a 20 px mark on
  a line that names the phase, its number and its elapsed;
* S2 the live generator draft dumped its whole text — it is one summarising
  line, collapsible, collapsed by default;
* S3 the stop reason rendered in English inside a Chinese card and led with a
  raw 12-hex commit sha;
* S4 a "what is still blocking" heading with a zero badge and copy that only
  pointed back up the card;
* S5 a setup mistake wearing the escalation card.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit.cli import i18n
from crossaudit.console import overview
from crossaudit.console.page import PAGE
from crossaudit.controller import StateStore
from crossaudit.errors import ConfigDenial

from .conftest import git

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))
WORKTREE = Path(overview.__file__).parents[3]
needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

#: The vocabulary that must never reach a first paint (D149): a full, short or
#: abbreviated hash, a rule id, a provider:model route, a raw verdict word.
HEX = re.compile(r"\b[0-9a-f]{7,}\b")
RULE_ID = re.compile(r"CA-[A-Z]+-\d")
PROVIDER_MODEL = re.compile(r"[A-Za-z0-9_.-]+:(?:claude|gpt|gemini|deepseek|grok|o[0-9])")
RAW_VERDICT = re.compile(r"\b(PASS|BLOCKED|ESCALATE|ESCALATED|DCL_ONLY)\b")


def _node(program: str) -> str:
    handle, path = tempfile.mkstemp(suffix=".js")
    try:
        Path(path).write_text(program, encoding="utf-8")
        out = subprocess.run(["node", path], capture_output=True, text=True,
                             encoding="utf-8")
        assert out.returncode == 0, out.stderr
        return out.stdout
    finally:
        Path(path).unlink()


# ===================================================== S1 the live phase line
def _page_snippet(signature: str) -> str:
    from render_decision import _extract

    script = PAGE.split("<script>")[1].split("</script>")[0]
    return _extract(script, signature)


PHASE_LINES = [
    # phase, facts, english, chinese
    ("routing", {}, "Working out who should handle this", "正在判断由谁处理"),
    ("preparing", {"files": 12}, "Reading the workspace · 12 files", "正在读取工作区 · 12 个文件"),
    ("generating", {"words": 412}, "Drafting · 412 words so far", "正在撰写 · 已写 412 字"),
    ("auditing", {"files": 3}, "The auditor is reading · 3 files", "审计者正在阅读 · 3 个文件"),
    ("waiting", {"seconds": 38}, "Waiting for the provider · 38s", "等待供应商 · 已等 38 秒"),
    # Elapsed appears only once the phase has been going long enough for the
    # number to mean something, and then in words.
    ("generating", {"words": 4, "seconds": 4}, "Drafting · 4 words so far",
     "正在撰写 · 已写 4 字"),
    ("generating", {"words": 4, "seconds": 5}, "Drafting · 4 words so far · 5s",
     "正在撰写 · 已写 4 字 · 5 秒"),
    ("generating", {"words": 4, "seconds": 72}, "Drafting · 4 words so far · 1m 12s",
     "正在撰写 · 已写 4 字 · 1 分 12 秒"),
    # A phase with no number to show is the phase and its elapsed. Never an
    # animation on its own.
    ("routing", {"seconds": 9}, "Working out who should handle this · 9s",
     "正在判断由谁处理 · 9 秒"),
    ("auditing", {"files": 0, "seconds": 6}, "The auditor is reading · 6s",
     "审计者正在阅读 · 6 秒"),
]


@needs_node
def test_every_live_phase_line_says_the_phase_its_number_and_its_elapsed():
    """S1, through the shipped builder. Mutation: drop the count clause from
    `phaseCount` and every row carrying a number fails; move the elapsed
    threshold to 0 and the 4-second row grows a tail.
    """
    cases = [{"phase": p, "facts": f} for p, f, _en, _zh in PHASE_LINES]
    program = "\n".join([
        "let currentLocale='en';",
        _page_snippet("const PHASE_ELAPSED_S") + ";",
        _page_snippet("const PHASE_WORDS") + ";",
        _page_snippet("function elapsedWords(seconds)"),
        _page_snippet("function phaseWords(phase)"),
        _page_snippet("function phaseCount(phase,facts)"),
        _page_snippet("function phaseLineText(phase,facts)"),
        f"const CASES={json.dumps(cases, ensure_ascii=False)};const out=[];",
        "for(const c of CASES){const row={};"
        "for(const locale of ['en','zh']){currentLocale=locale;"
        "row[locale]=phaseLineText(c.phase,c.facts);}out.push(row);}",
        "console.log(JSON.stringify(out));"])
    got = json.loads(_node(program))
    for (phase, facts, en, zh), row in zip(PHASE_LINES, got):
        assert row["en"] == en, (phase, facts, row)
        assert row["zh"] == zh, (phase, facts, row)


# ========================================================= S2 the folded draft
_DRAFT_PRELUDE = """
let currentLocale='en';let STORE={};let lastState={project:'lab/perovskite'};
globalThis.localStorage={getItem:k=>k in STORE?STORE[k]:null,
  setItem:(k,v)=>{STORE[k]=String(v);}};
let DRAFT=null;const liveDraftFor=()=>DRAFT;
"""


@needs_node
def test_the_live_draft_is_one_line_until_the_reader_opens_it():
    """S2. Collapsed by default, the whole text behind a disclosure, and the
    choice remembered per project.

    Mutation: default the disclosure to open and the collapsed case renders
    the body; drop the project from `draftOpenKey` and the second project
    inherits the first one's choice.
    """
    esc = PAGE[PAGE.index("const esc = s =>"):]
    esc = esc[:esc.index(";\n") + 1]
    text = "第一段草稿 with three words"
    program = "\n".join([
        _DRAFT_PRELUDE, esc,
        _page_snippet("function draftCount(text)"),
        _page_snippet("const DRAFT_OPEN_KEY") + ";",
        _page_snippet("function draftOpenKey(d)"),
        _page_snippet("function draftOpen(d)"),
        _page_snippet("function rememberDraftOpen(el)"),
        _page_snippet("function draftSummaryLine(draft)"),
        _page_snippet("function liveDraftTurn(d)"),
        f"DRAFT={{text:{json.dumps(text)}}};const out={{}};",
        "for(const locale of ['en','zh']){currentLocale=locale;"
        "  out['collapsed_'+locale]=liveDraftTurn(lastState);}",
        # The reader opens it; the page remembers, for THIS project only.
        "rememberDraftOpen({open:true});",
        "for(const locale of ['en','zh']){currentLocale=locale;"
        "  out['open_'+locale]=liveDraftTurn(lastState);}",
        "out.other_project=liveDraftTurn({project:'lab/other'});",
        "console.log(JSON.stringify(out));"])
    out = json.loads(_node(program))

    # Collapsed: one line, the count, the unaudited label — and the text is
    # inside a closed <details>, so it is not on the first paint.
    for locale, line in (("en", "Generator is drafting · 8 words so far · not yet audited"),
                         ("zh", "生成者正在撰写 · 已写 8 字 · 尚未审计")):
        html = out["collapsed_" + locale]
        assert line in html, (locale, html)
        assert 'class="draft-fold" ontoggle=' in html, locale
        assert 'class="draft-fold" open' not in html, locale
        first_paint = re.sub(r"<details\b.*?</details>", "", html, flags=re.S)
        assert text not in first_paint, "the whole draft is not on the first paint"
    # Opened: the same line, and now the streaming text beside it, still
    # labelled unaudited and still wearing none of the audited furniture.
    for locale in ("en", "zh"):
        html = out["open_" + locale]
        assert 'class="draft-fold" open ontoggle=' in html
        assert text in html
        for borrowed in ("file-card", "data-download", "delivery", "status PASS"):
            assert borrowed not in html
    # Another project keeps its own default.
    assert 'class="draft-fold" open' not in out["other_project"]
# ============================================================ S3 the sentence
def test_the_reproduced_stop_reason_now_reaches_a_chinese_reader():
    """The exact sentence from the owner's screenshot. It has a Chinese
    template and was refused by the leading-slot guard because the slot held
    an eleven-word commit subject.

    Mutation: apply the guard to every leading-slot template again (drop the
    `_is_generic` term from `_swallows_a_sentence`) and both reproductions
    below go back to None — English inside a Chinese card.
    """
    subject = ("Complete the perovskite review article by filling in all "
               "truncated sections (round 1)")
    old = (f"68cb653b4148 ('{subject}') changed no science files — only rules, "
           f"configuration or ledger. Commit your experiment, then run again.")
    assert i18n.denial_zh(old) is not None
    assert subject in i18n.denial_zh(old), "the person's own words are carried through"
    new = (f"Your last commit ('{subject}') changed no science files — only "
           f"rules, configuration or ledger. Commit your experiment, then "
           f"run again.")
    zh = i18n.denial_zh(new)
    assert zh is not None and zh.startswith("你的上一次提交")
    assert HEX.search(zh) is None, "and it names no sha"


def test_a_genuinely_generic_template_still_refuses_a_sentence_shaped_slot():
    """The guard the fix narrows must keep doing its job: a one-slot frame
    whose own fixed text could introduce anything may not swallow a whole
    composed refusal and answer with a half-translation.

    Mutation: drop the guard entirely and this returns a Chinese frame wrapped
    around an English paragraph.
    """
    swallowed = ("The generator produced nothing under the audited folder and "
                 "the round was abandoned before any file was written is required")
    assert i18n.denial_zh(swallowed) is None
    # ...while a short, ordinary value in the same template still translates.
    assert i18n.denial_zh("scope.dirs is required") == "必须设置 scope.dirs"


def test_no_user_facing_stop_leads_with_a_commit_sha():
    """S3 sweep. The four refusals that opened with `sha[:12]` now name the
    commit by its subject. Mutation: restore any one of them and its literal
    reappears in the source.
    """
    source = (WORKTREE / "src/crossaudit/cli/main.py").read_text(encoding="utf-8")
    for gone in ('f"{sha[:12]} changed no science files',
                 'f"{sha[:12]} was already admitted',
                 'f"{sha[:12]} already has a recorded decision',
                 'f"{sha[:12]} only touches the ledger'):
        assert gone not in source, gone
    for kept in ("Your last commit ({subject!r}) changed no science files",
                 "That commit ({subject!r}) was already admitted",
                 "That commit ({subject!r}) already has a recorded decision",
                 "That commit ({subject!r}) only touches the ledger"):
        assert kept in source, kept
        # Each has its Chinese, or a Chinese reader gets the marked English.
        assert kept.split(" ({subject!r})")[0] in (
            WORKTREE / "src/crossaudit/cli/denials_zh.py").read_text(encoding="utf-8")


# ======================================================= the decision card
def _generic_row(science: Path) -> dict:
    """An escalation with no structured cause and no findings — the shape any
    record written before a cause existed still takes."""
    from crossaudit.config import load

    cfg = load(science / "crossaudit.yml")
    StateStore(cfg.root / cfg.state_dir / "state.json").record_build_escalation(
        cfg.science_repo, "c" * 40, "the automatic audit loop stopped", 1,
        task="Write it", kind="audit")
    return {"generic": [r for r in overview.escalations(cfg) if r["sha"] == "c" * 40][0]}


@needs_node
def test_a_card_with_no_findings_renders_no_section_and_no_zero_badge(science):
    """S4. A heading, a zero badge and a line that only points back at the
    text above it are three pieces of furniture, not information.

    Mutation: restore the generic `No structured findings were recorded.
    Review the stop reason above before continuing.` empty copy and the
    section comes back.
    """
    from render_decision import render

    out = render(WORKTREE, _generic_row(science))["generic"]
    for locale in ("en", "zh"):
        extra = out["extra"][locale]
        assert extra["issues_hidden"] is True, locale
        assert extra["count_hidden"] is True and extra["count_text"] == ""
        assert out[locale]["resolution-issues"] == ""
    assert "No structured findings were recorded. Review the stop reason" not in PAGE


@needs_node
def test_the_commit_sha_is_only_in_the_closed_details_block(science):
    """S3/D149: the identifier stays reachable and leaves the first paint.

    Mutation: put `row.short_sha` back into any visible slot and the sweep
    below finds it.
    """
    from render_decision import render

    out = render(WORKTREE, _generic_row(science))["generic"]
    for locale in ("en", "zh"):
        assert HEX.search(out["extra"][locale]["details_text"]), "one click away"
    assert "Technical details" in PAGE and '"Technical details":"技术细节"' in PAGE


@needs_node
def test_no_identifier_reaches_the_first_paint_of_a_decision_card(science):
    """D149, swept over every visible slot of the card, EN and ZH."""
    from render_decision import render

    card = render(WORKTREE, _generic_row(science))["generic"]
    for locale in ("en", "zh"):
        for slot, text in card[locale].items():
            assert HEX.search(text) is None, (locale, slot, text)
            assert RULE_ID.search(text) is None, (locale, slot)
            assert PROVIDER_MODEL.search(text) is None, (locale, slot)
            assert RAW_VERDICT.search(text) is None, (locale, slot)
