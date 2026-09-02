"""Round 3 — what a live browser session found, each fixed and rendered.

(1) the language toggle was unreachable while a decision card was open;
(2) a raw seconds count ("heartbeat 205214s ago") and "等待 provider";
(3) 生成端 beside 生成者 on one card; (4) a days-old chat reading "just now";
(5) the review card's button doing nothing after "Review later", and
"Needs your input" beside "Round 1/3 · PASS" with no word about the later
round. Rendered under node through the shipped functions where the defect was
behaviour, and pinned in markup where it was structure.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest

from crossaudit.cli import denials_zh, i18n
from crossaudit.console import chats, overview, page as page_mod, progress
from crossaudit.console.page import PAGE

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))
WORKTREE = Path(overview.__file__).parents[3]
CJK = re.compile(r"[一-鿿]")
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


# ---------------------------------------------------------------- (1)
class _Where(HTMLParser):
    """Which ancestors an element with a given id sits under."""

    def __init__(self, target: str) -> None:
        super().__init__()
        self.target, self.stack, self.found = target, [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append(a.get("class", "") + "#" + a.get("id", ""))
        if a.get("id") == self.target:
            self.found = list(self.stack)
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            self.stack.pop()

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


def test_the_decision_card_carries_its_own_language_toggle_outside_the_inert_shell():
    markup = re.sub(r"<script>.*?</script>", "", PAGE, flags=re.S)
    where = _Where("decision-locale")
    where.feed(markup)
    assert where.found, "no #decision-locale in the card header"
    assert any(s.endswith("#resolution-modal") for s in where.found)
    assert not any(s.startswith("app#") for s in where.found), (
        "the toggle sits inside .app, which setDecidingInert makes inert")
    assert "document.getElementById('decision-locale').onclick=document.getElementById('locale-toggle').onclick;" in PAGE
    assert "for(const id of ['locale-toggle','hub-locale','decision-locale'])" in PAGE


@node
def test_switching_language_from_the_card_relabels_the_card_toggle(tmp_path):
    """Rendered: the shipped applyLocale() over a fake DOM holding the three
    toggles; the card's toggle reads EN / 切换到英文 after a switch to zh."""
    from render_decision import eval_page

    prelude = r"""
    const els={};const mk=id=>({id,textContent:'',attrs:{},setAttribute(n,v){this.attrs[n]=v;},title:''});
    for(const id of ['locale-toggle','hub-locale','decision-locale'])els[id]=mk(id);
    globalThis.document={getElementById:id=>els[id]||null,documentElement:{lang:''},body:{},cookie:''};
    globalThis.localStorage={setItem(){}};globalThis.lastState=null;globalThis.render=()=>{};
    globalThis.localizeTree=()=>{};let currentLocale='en';const LOCALE_KEY='k',LOCALE_COOKIE='c';
    """
    out = eval_page(WORKTREE, ["function applyLocale(locale,remember=true)"], """
    applyLocale('zh');
    console.log(JSON.stringify({text:els['decision-locale'].textContent,label:els['decision-locale'].attrs['aria-label'],lang:document.documentElement.lang}));
    applyLocale('en');
    console.log(JSON.stringify({text:els['decision-locale'].textContent,label:els['decision-locale'].attrs['aria-label']}));
    """, prelude=prelude)
    zh, en = [json.loads(line) for line in out.strip().splitlines()]
    assert zh == {"text": "EN", "label": "切换到英文", "lang": "zh-CN"}
    assert en == {"text": "中文", "label": "Switch to Chinese"}


# ---------------------------------------------------------------- (2)
@node
def test_relative_ages_and_durations_are_words_in_both_languages():
    from render_decision import eval_page

    out = eval_page(WORKTREE, ["function relAge(seconds)", "function durationText(seconds)",
                               "function elapsedText(seconds)", "function humaniseDetail(text)"], """
    const rows=[relAge(5),relAge(90),relAge(7200),relAge(86400),relAge(205214),
      'Waiting for the provider · heartbeat '+relAge(205214),'last heartbeat '+relAge(150),
      elapsedText(12),elapsedText(252),elapsedText(3900),humaniseDetail('no heartbeat for 7200s'),
      humaniseDetail('other detail')];
    console.log(JSON.stringify(rows.map(v=>[v,zhValue(v)])));
    """)
    rows = dict(json.loads(out))
    assert rows["just now"] == "刚刚"
    assert rows["1 min ago"] == "1 分钟前" and rows["2 h ago"] == "2 小时前"
    assert rows["1 day ago"] == "1 天前" and rows["2 days ago"] == "2 天前"
    assert rows["Waiting for the provider · heartbeat 2 days ago"] == "等待供应商 · 心跳 2 天前"
    assert rows["last heartbeat 2 min ago"] == "最后心跳 2 分钟前"
    assert rows["12s elapsed"] == "已运行 12 秒" and rows["4m 12s elapsed"] == "已运行 4 分 12 秒"
    assert rows["1h 5m elapsed"] == "已运行 1 小时 5 分"
    assert rows["no heartbeat for 2 h"] == "已 2 小时无心跳"
    assert rows["other detail"] == "other detail"


def test_no_surface_renders_a_raw_seconds_count():
    script = PAGE.split("<script>")[1].split("</script>")[0]
    assert "+'s ago'" not in script and "p.elapsed + 's elapsed'" not in script
    assert "heartbeatAge+'s" not in script and "elapsedText(p.elapsed)" in script
    assert "等待 provider" not in PAGE and "Waiting for provider'" not in PAGE


# ---------------------------------------------------------------- (3)
BANNED = re.compile(r"生成端|审计端|执行端")


def test_console_and_cli_chinese_use_one_word_for_each_role():
    """The product terms are 生成者 and 审计者. The only place the old words
    may appear is the @-mention parser, which ACCEPTS them from a person and
    never shows them."""
    sources = {
        "page.py": Path(page_mod.__file__).read_text(),
        "progress.py": Path(progress.__file__).read_text(),
        "i18n.py": Path(i18n.__file__).read_text(),
        "denials_zh.py": Path(denials_zh.__file__).read_text(),
    }
    offenders = []
    for name, text in sources.items():
        for n, line in enumerate(text.splitlines(), 1):
            if BANNED.search(line) and "mentionPrefix" not in line and "includes(m[1]" not in line:
                offenders.append(f"{name}:{n}: {line.strip()[:80]}")
    assert offenders == [], offenders


# ---------------------------------------------------------------- (4)
def test_a_recovered_chat_is_dated_by_its_evidence_not_by_the_snapshot(tmp_path):
    from crossaudit.config import load

    root = tmp_path / "p"
    root.mkdir()
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n")
    cfg = load(root / "crossaudit.yml")
    old = int(time.time()) - 3 * 86400
    chat = "a" * 16
    rows = chats.snapshot(cfg, [chat], last_seen={chat: old})["items"]
    assert [r["updated"] for r in rows if r["id"] == chat] == [old]
    rows = chats.snapshot(cfg, [chat])["items"]
    assert [r["updated"] for r in rows if r["id"] == chat] == [0], "unknown is no time, not now"
    assert "last_seen=last_seen" in Path(overview.__file__).with_name("server.py").read_text()


# ---------------------------------------------------------------- (5)
@node
def test_the_review_card_button_finds_its_own_decision_and_names_a_later_round():
    from render_decision import eval_page

    prelude = "globalThis.activeChatId='chat-1';globalThis.chatCycles=d=>d.cycles||[];"
    out = eval_page(WORKTREE, ["function currentEscalations(d)", "function decisionRowFor(d,cycleId,sha)",
                               "function pendingDecisionLine(row,lastRound)"], """
    const st={cycles:[{id:'c1',sha:'abc',chat_id:'chat-1'}],escalations:[
      {cycle_id:'c2',sha:'abc',chat_id:'other',kind:'provider',round:2},
      {cycle_id:'c3',sha:'zzz',chat_id:'other',kind:'audit',round:1}]};
    const byId=decisionRowFor(st,'c2','');const bySha=decisionRowFor(st,'nope','abc');
    const none=decisionRowFor({cycles:[],escalations:[]},'c9','');
    const lines=[pendingDecisionLine(byId,1),pendingDecisionLine({kind:'audit',round:1},1),
      pendingDecisionLine({kind:'audit',round:2},1),pendingDecisionLine({kind:'budget',round:1},1)];
    console.log(JSON.stringify({byId:byId&&byId.cycle_id,bySha:bySha&&bySha.cycle_id,none,lines,zh:lines.map(zhValue)}));
    """, prelude=prelude)
    got = json.loads(out)
    assert got["byId"] == "c2" and got["bySha"] == "c2" and got["none"] is None
    assert got["lines"] == ["Waiting for the provider · round 2", "", "Needs your decision · round 2", "Usage limit reached"]
    assert got["zh"][0] == "等待供应商 · 第 2 轮" and got["zh"][2] == "需要你决定 · 第 2 轮"
    assert got["zh"][3] == "已达用量上限"


def test_the_review_card_button_carries_its_cycle_and_falls_back_to_the_detail():
    assert 'data-open-decisions="\'+esc(cycle.id)+\'"' in PAGE
    handler = PAGE[PAGE.index("const openDecisions=ev.target.closest('[data-open-decisions]')"):]
    handler = handler[:handler.index("openInspector();")]
    assert "decisionRowFor(lastState,id,sha)" in handler
    assert "expandedReviews.add(id);render(lastState);openPanelTab('audits');" in handler
    assert "pendingLine" in PAGE[PAGE.index("function reviewCard(d){"):PAGE.index("function runCard(d){")]
