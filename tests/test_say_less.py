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
