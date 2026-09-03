"""SPEC-20 §6 — what the live region CONTAINS after condensation.

**Why this file exists separately.** The wiring pin in
`test_earlier_turns_affordance.py` asserts that `announceCondensation` is
defined and called. That is a presence check, and the audit was right to name
it: the law it is meant to enforce is *containers present, contents absent*, and
a guard for that law which only checks presence reproduces the defect one level
up. It passes on a live region that exists, is written, and stays empty.

So this file EXECUTES. It runs the page's own `announceCondensation`,
`announce`, `liveText` and locale machinery against a DOM stub whose only job is
to record what the announcer node ends up holding, and asserts the sentence is
in it — in the locale under test.

**The mutation is an EMPTY region, not a missing one.** A missing region is easy
and every version of this guard caught it. An empty one is the case the law
names, and if it passes the guard is still presence.
"""
from __future__ import annotations

import json
import shutil

import pytest

from crossaudit.console.page import PAGE

from .node_eval import run_node

SENTENCE_EN = ("Earlier turns in this chat were summarised for the generator; "
               "the full conversation is still here")
SENTENCE_ZH = "已将本对话中较早的轮次概括后提供给生成者；完整对话仍保留在这里"


def _script(page=None) -> str:
    return (page or PAGE).split("<script>")[1].split("</script>")[0]


def _extract(signature: str, page=None) -> str:
    script = _script(page)
    start = script.index(signature)
    depth, i = 0, script.index("{", start)
    while i < len(script):
        if script[i] == "{":
            depth += 1
        elif script[i] == "}":
            depth -= 1
            if depth == 0:
                return script[start:i + 1]
        i += 1
    raise AssertionError(signature)


def _sources(page=None) -> str:
    script = _script(page)
    tables = script[script.index("const ZH={"):script.index("function applyLocale(")]
    # Brace-matched, not sliced to the first `};` — that lands inside
    # `bundle || {}` and truncates the function mid-body, which node reports as
    # "Unexpected end of input" and which would look like a product defect.
    return "\n".join((
        tables, _extract("const localeText = (bundle, base) => {", page),
        _extract("function liveFragment(fill)", page),
        _extract("function liveText(node,value)", page),
        "let announcedText='';let announceTimer=null;",
        _extract("function announce(sentence,kind)", page),
        "let announcedCondensations=null;let announcedCondenseChat=null;",
        _extract("function announceCondensation(d)", page)))


HARNESS = r"""
const A=(c,m)=>{if(!c)throw new Error(m);};
globalThis.Node={ELEMENT_NODE:1,TEXT_NODE:3};
globalThis.NodeFilter={SHOW_ELEMENT:1,SHOW_TEXT:4};
class T{constructor(d){this._d=String(d);this.nodeType=3;this.parentElement=null;}
  get data(){return this._d;} set data(v){this._d=String(v);}
  get textContent(){return this._d;}}
class E{constructor(t){this.tagName=String(t).toUpperCase();this.nodeType=1;
    this.childNodes=[];this._a={};this.parentElement=null;}
  get textContent(){return this.childNodes.map(n=>n.textContent).join('');}
  set textContent(v){for(const c of this.childNodes)c.parentElement=null;
    this.childNodes=[];const s=String(v);
    if(s!==''){const t=new T(s);t.parentElement=this;this.childNodes.push(t);}}
  set innerHTML(v){this.textContent=String(v).replace(/<[^>]*>/g,'');}
  hasAttribute(n){return Object.prototype.hasOwnProperty.call(this._a,n);}
  getAttribute(n){return this.hasAttribute(n)?this._a[n]:null;}
  setAttribute(n,v){this._a[n]=String(v);}
  replaceChildren(...ns){for(const c of this.childNodes)c.parentElement=null;
    this.childNodes=ns.slice();for(const n of this.childNodes)n.parentElement=this;}}
function descendants(r){const o=[];(function rec(n){for(const c of n.childNodes||[]){
  o.push(c);rec(c);}})(r);return o;}
const announcer=new E('p');
globalThis.document={createElement:t=>new E(t),
  getElementById:id=>id==='announcer'?announcer:null,
  createTreeWalker(root,what){const list=descendants(root).filter(n=>
      (n.nodeType===1&&(what&1))||(n.nodeType===3&&(what&4)));
    let i=-1;return {currentNode:root,nextNode(){i++;if(i>=list.length)return null;
      this.currentNode=list[i];return list[i];}};}};
let timers=[];globalThis.setTimeout=fn=>{timers.push(fn);return timers.length;};
globalThis.clearTimeout=id=>{if(id)timers[id-1]=null;};
const flush=()=>{const t=timers;timers=[];for(const fn of t)if(fn)fn();};

// Named apart from the product's own `ZH` dictionary, which is in scope here.
const S_EN='Earlier turns in this chat were summarised for the generator; the full conversation is still here';
const S_ZH='已将本对话中较早的轮次概括后提供给生成者；完整对话仍保留在这里';
function state(rows){return {generator_stream:rows};}
function row(id,detail){return {kind:'context_condensed',chat_id:'history',
  event_id:id,t:id,summary:S_EN+': '+detail,
  summary_i18n:{en:S_EN+': '+detail,zh:S_ZH+': '+detail}};}

globalThis.activeChatId='history';
currentLocale=LOCALE;
// Baseline in silence: a thread that already had condensations must not
// announce its history on open.
announceCondensation(state([row(1,'6 turns')]));flush();
A(announcer.textContent==='','opening a thread announced its history: '
  +JSON.stringify(announcer.textContent));

// Now one arrives while the person is here.
announceCondensation(state([row(1,'6 turns'),row(2,'2 turns')]));flush();
const held=announcer.textContent;
// CONTENT, not presence. An empty region is the case the law names.
A(held!=='','the live region exists and is empty: a person is told nothing');
A(held.indexOf(WANTED)>=0,
  'the live region does not contain the condensation sentence in '+LOCALE
  +'; it holds '+JSON.stringify(held));
A(held.indexOf(FORBIDDEN)<0,
  'the region holds the wrong locale: '+JSON.stringify(held));
console.log('ok');
"""


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


def _run(js: str):
    return run_node(js)


def _program(locale: str, page=None) -> str:
    wanted, forbidden = ((SENTENCE_ZH, SENTENCE_EN) if locale == "zh"
                         else (SENTENCE_EN, SENTENCE_ZH))
    header = (f"const LOCALE={json.dumps(locale)};"
              f"const WANTED={json.dumps(wanted)};"
              f"const FORBIDDEN={json.dumps(forbidden)};\n")
    return _sources(page) + header + HARNESS


@pytest.mark.parametrize("locale", ("en", "zh"))
def test_the_live_region_contains_the_condensation_sentence(locale):
    _needs_node()
    result = _run(_program(locale))
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


MUTATIONS = (
    ("the region is written EMPTY — it exists, it is mutated, and it holds "
     "nothing. This is the mutation that separates a content guard from a "
     "presence one, and a presence check passes it",
     "  return announce(localeText(last.summary_i18n,last.summary),'event');}",
     "  liveText(document.getElementById('announcer'),'');return true;}"),
    ("nothing is announced at all",
     "  return announce(localeText(last.summary_i18n,last.summary),'event');}",
     "  return false;}"),
    ("the English source is announced instead of the localised string, so a "
     "Chinese reader is spoken English while the page shows Chinese",
     "  return announce(localeText(last.summary_i18n,last.summary),'event');}",
     "  return announce(last.summary,'event');}"),
    ("the baseline is dropped, so opening a thread announces every "
     "condensation it ever had",
     "    announcedCondenseChat=chat;announcedCondensations=ids;return false;}",
     "    announcedCondenseChat=chat;announcedCondensations=new Set();}"),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:34] for m in MUTATIONS])
def test_the_content_guard_is_shown_to_fail(why, before, after):
    """Read WHICH assertion fires, not merely that one did."""
    _needs_node()
    assert PAGE.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    mutated = PAGE.replace(before, after)
    caught = []
    for locale in ("en", "zh"):
        result = _run(_program(locale, mutated))
        if result.returncode != 0:
            first = next((line for line in result.stderr.splitlines()
                          if line.startswith("Error: ")), "")
            caught.append((locale, first[:120]))
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
