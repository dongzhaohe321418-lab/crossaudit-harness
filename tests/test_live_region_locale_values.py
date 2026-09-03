"""SPEC-9 — what the live region HELD, not what order the source is written in.

This file exists because a guard of mine was green on a defect that was fully
present, and I am the person who wrote the rule it failed to apply.

The rule, from driving slice 1 in Chinese: the locale observer (`localizeTree`
via a MutationObserver on `document.body`) runs a **microtask later** than the
write, so writing an English source into a live region SPEAKS the English while
the screen goes on to show Chinese. A live region announces what IS there, not
what is about to be.

The proof method, which is the part that transfers: **record every intermediate
value the node takes, not just its final text.** That is what separates "the
node ends up correct" from "the person hears the correct thing".

My first repair moved the translation into the same task as the write. That
closed the microtask window and did not close the defect, because the write and
the translation are still TWO MUTATIONS OF THE SAME NODE and the live-region
notification fires on the first. The cross-vendor auditor drove the product and
recorded exactly that:

    thread arrival      CrossAudit replied.  ->  CrossAudit 已回复。
    escalation arrival  A task is waiting…   ->  有一个任务正在等待你的决定。

while my guard — which asserted that `node.textContent=` appears before
`localizeTree(node)` in the source — passed. Source order is a claim about the
code. **"Ends in Chinese" is not "never held English."**

So this guard executes. It runs the product's OWN `liveText`, `liveHTML`,
`announce` and `localizeTree` against a DOM stub whose only real job is to
record, in order, every distinct value the live-region node holds — including
values produced by mutations somewhere else, because "was this region ever
English" cannot be answered by watching only its own writes.

**What this is not.** The stub is not a browser and this file does not claim a
speech result: it settles the DOM contract (how many values the region took, and
which), which is what the auditor could execute and what a screen reader reads
from. An actual VoiceOver queue was out of reach for the auditor too, and is
recorded as such in `_audit_artifacts/spec9-2-39df6a0/39df6a0.md`.

Ledger D10: the guard is demonstrated to fail against the previous
implementation — the real one, taken from the previous commit, not a caricature.
"""
import shutil

import pytest

from crossaudit.console.page import PAGE

from .node_eval import run_node

# The two live-region doors as they ship today. Pinned so that a rewrite of them
# fails this file loudly rather than leaving it guarding a shape that is gone.
CURRENT_IMPLEMENTATION = """function liveFragment(fill){
  const holder=document.createElement('div');
  fill(holder);
  if(typeof localizeTree==='function')localizeTree(holder);
  return holder;}
function liveText(node,value){
  if(!node)return;
  const holder=liveFragment(h=>{h.textContent=String(value==null?'':value);});
  node.replaceChildren(...holder.childNodes);}
function liveHTML(node,markup){
  if(!node)return;
  const holder=liveFragment(h=>{h.innerHTML=String(markup==null?'':markup);});
  node.replaceChildren(...holder.childNodes);}"""

# The implementation this replaces, verbatim as it stood at b41d7e4. It is the
# honest mutation: the code a competent person wrote after reading the rule
# correctly, which nevertheless left the region holding English first.
SAME_TASK_IMPLEMENTATION = """function liveFragment(fill){return null;}
function liveText(node,value){
  if(!node)return;
  node.textContent=String(value==null?'':value);
  if(typeof localizeTree==='function')localizeTree(node);}
function liveHTML(node,markup){
  if(!node)return;
  node.innerHTML=String(markup==null?'':markup);
  if(typeof localizeTree==='function')localizeTree(node);}"""


def _script(page=None):
    return (page or PAGE).split("<script>")[1].split("</script>")[0]


def _extract(signature, page=None):
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


def _sources(page=None):
    """The product's real locale machinery, plus the two live-region doors.

    Sliced rather than re-stated: a guard that runs a copy of the code proves
    the copy correct. `applyLocale` and the observer are excluded because they
    reach for cookies, storage and `document.body` on load, not because the
    property stops there — the observer is the mechanism this rule exists to
    beat, and beating it means never handing it an English value to translate.
    """
    script = _script(page)
    tables = script[script.index("const ZH={"):script.index("function applyLocale(")]
    return "\n".join((tables,
                       _extract("function liveFragment(fill)", page),
                       _extract("function liveText(node,value)", page),
                       _extract("function liveHTML(node,markup)", page),
                       "let announcedText='';let announceTimer=null;",
                       _extract("function announce(sentence,kind)", page)))


HARNESS = r"""
// ---------------------------------------------------------------- mini DOM
// Enough of a DOM to run the product's OWN localizeTree/liveText, and no more.
// Its whole job is to record EVERY value the live-region node holds, in order.
const A=(c,m)=>{if(!c)throw new Error(m);};
globalThis.Node={ELEMENT_NODE:1,TEXT_NODE:3};
globalThis.NodeFilter={SHOW_ELEMENT:1,SHOW_TEXT:4};
// SEEN is the sequence of DISTINCT SUCCESSIVE VALUES the live region held after
// its baseline. Mutations anywhere (including in a detached holder) are sampled,
// because "was the region ever English" cannot be answered by looking only at
// the region's own writes — that is the assumption that made the source-order
// guard green on a defect.
let RECORD=null,LAST='',SEEN=[];
function note(){if(!RECORD)return;const v=RECORD.textContent;
  if(v===LAST)return;LAST=v;SEEN.push(v);}
class T{
  constructor(d){this._d=String(d);this.nodeType=3;this.parentElement=null;}
  get data(){return this._d;}
  set data(v){this._d=String(v);note();}
  get textContent(){return this._d;}
}
class E{
  constructor(tag){this.tagName=String(tag).toUpperCase();this.nodeType=1;
    this.childNodes=[];this._a={};this.parentElement=null;}
  get textContent(){return this.childNodes.map(n=>n.textContent).join('');}
  set textContent(v){for(const c of this.childNodes)c.parentElement=null;
    this.childNodes=[];const s=String(v);
    if(s!==''){const t=new T(s);t.parentElement=this;this.childNodes.push(t);}note();}
  set innerHTML(v){parseInto(this,String(v));note();}
  get innerHTML(){return this.textContent;}
  hasAttribute(n){return Object.prototype.hasOwnProperty.call(this._a,n);}
  getAttribute(n){return this.hasAttribute(n)?this._a[n]:null;}
  setAttribute(n,v){this._a[n]=String(v);}
  appendChild(n){n.parentElement=this;this.childNodes.push(n);note();return n;}
  replaceChildren(...nodes){for(const c of this.childNodes)c.parentElement=null;
    this.childNodes=nodes.slice();
    for(const n of this.childNodes)n.parentElement=this;note();}
}
// Single-level-aware tag/text tokenizer. Only shapes this page actually writes.
function parseInto(root,markup){
  for(const c of root.childNodes)c.parentElement=null;
  root.childNodes=[];
  const stack=[root];
  const re=/<(\/?)([a-zA-Z][\w-]*)([^>]*?)(\/?)>|([^<]+)/g;let m;
  while((m=re.exec(markup))!==null){
    const top=stack[stack.length-1];
    if(m[5]!==undefined){const t=new T(m[5]);t.parentElement=top;top.childNodes.push(t);continue;}
    if(m[1]==='/'){if(stack.length>1)stack.pop();continue;}
    const el=new E(m[2]);
    for(const a of m[3].matchAll(/([\w-]+)="([^"]*)"/g))el.setAttribute(a[1],a[2]);
    el.parentElement=top;top.childNodes.push(el);
    if(!m[4]&&!['br','img','input','hr'].includes(m[2].toLowerCase()))stack.push(el);
  }
}
function descendants(root){const out=[];(function rec(n){
  for(const c of n.childNodes||[]){out.push(c);rec(c);}})(root);return out;}
const BY_ID={};
globalThis.document={
  createElement:t=>new E(t),
  getElementById:id=>BY_ID[id]||null,
  createTreeWalker(root,what){
    const list=descendants(root).filter(n=>
      (n.nodeType===1&&(what&NodeFilter.SHOW_ELEMENT))||
      (n.nodeType===3&&(what&NodeFilter.SHOW_TEXT)));
    let i=-1;return {currentNode:root,nextNode(){i++;if(i>=list.length)return null;
      this.currentNode=list[i];return list[i];}};},
};
let timers=[];
globalThis.setTimeout=(fn)=>{timers.push(fn);return timers.length;};
globalThis.clearTimeout=(id)=>{if(id)timers[id-1]=null;};
const flush=()=>{const t=timers;timers=[];for(const fn of t)if(fn)fn();};

// ------------------------------------------------------------------ drives
const announcer=new E('p');BY_ID['announcer']=announcer;
function drive(locale,call){
  currentLocale=locale;announcedText='';announceTimer=null;timers=[];
  announcer.textContent='';
  RECORD=announcer;LAST=announcer.textContent;SEEN=[];
  call();flush();
  RECORD=null;return SEEN.slice();
}
// The two production callers the auditor drove, plus the plural escalation.
const CASES=[
  ['thread arrival','CrossAudit replied.','CrossAudit 已回复。'],
  ['escalation arrival','A task is waiting for your decision.','有一个任务正在等待你的决定。'],
  ['escalation, plural','3 tasks are waiting for your decision.','有 3 个任务正在等待你的决定。'],
];
for(const [name,en,zh] of CASES){
  const zhSeen=drive('zh',()=>announce(en));
  A(zhSeen.length===1,
    name+': the live region held '+JSON.stringify(zhSeen)+'. A Chinese reader '+
    'must never be handed an English value to speak — "ends in Chinese" is not '+
    '"never held English".');
  A(zhSeen[0]===zh,name+': expected '+JSON.stringify(zh)+', got '+JSON.stringify(zhSeen));
  const enSeen=drive('en',()=>announce(en));
  A(enSeen.length===1&&enSeen[0]===en,
    name+': in English the region must hold the source exactly once, got '+JSON.stringify(enSeen));
}
// liveText and liveHTML are the rule's two doors; both must be single-valued.
{
  const zhSeen=drive('zh',()=>liveText(announcer,'Connection verified.'));
  A(zhSeen.length===1&&zhSeen[0]==='连接已验证。',
    'liveText held '+JSON.stringify(zhSeen));
  const htmlSeen=drive('zh',()=>liveHTML(announcer,'<b>Connection verified.</b>'));
  A(htmlSeen.length===1&&htmlSeen[0]==='连接已验证。',
    'liveHTML held '+JSON.stringify(htmlSeen));
}
// An EVENT repeated verbatim reaches the region twice, and every value it holds
// on the way is still in the reader's language. This is the case where the two
// halves of the R2 fix meet: the repeat must happen (or a reply is lost) AND the
// clear-then-write it happens through must not reintroduce an English value.
{
  currentLocale='zh';announcedText='';announceTimer=null;timers=[];
  announcer.textContent='';RECORD=announcer;LAST='';SEEN=[];
  announce('CrossAudit replied.','event');flush();
  announce('CrossAudit replied.','event');flush();
  RECORD=null;
  const spoken=SEEN.filter(v=>v!=='');
  A(spoken.length===2,
    'a repeated arrival must reach the live region twice, got '+JSON.stringify(SEEN));
  A(spoken.every(v=>v==='CrossAudit 已回复。'),
    'and every value it held is Chinese, got '+JSON.stringify(SEEN));
  A(SEEN.indexOf('CrossAudit replied.')<0,
    'the English source must never be one of them: '+JSON.stringify(SEEN));
}
// A STATE repeated is still suppressed, so the fix above did not turn the
// 2-second render loop into speech.
{
  currentLocale='zh';announcedText='';announceTimer=null;timers=[];
  announcer.textContent='';RECORD=announcer;LAST='';SEEN=[];
  announce('CrossAudit replied.');flush();
  announce('CrossAudit replied.');flush();
  RECORD=null;
  A(SEEN.filter(v=>v!=='').length===1,
    'a repeated state stays one announcement, got '+JSON.stringify(SEEN));
}
// The English source survives the write, so a later locale switch re-translates
// it the ordinary way rather than freezing the region in one language.
{
  drive('zh',()=>liveText(announcer,'CrossAudit replied.'));
  currentLocale='en';localizeTree(announcer);
  A(announcer.textContent==='CrossAudit replied.',
    'switching back to English must restore the source, got '+JSON.stringify(announcer.textContent));
  currentLocale='zh';localizeTree(announcer);
  A(announcer.textContent==='CrossAudit 已回复。',
    'and switching to Chinese again must re-translate, got '+JSON.stringify(announcer.textContent));
}
console.log('ok');

"""


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


def _run(js):
    return run_node(js)


def test_the_stub_records_a_value_the_region_held_and_not_only_its_last():
    """The method has a trap in it and I fell into it once already: a probe that
    looks like it captures intermediates and does not. So the recorder is tested
    against a sequence whose intermediate value is known, before it is trusted to
    report that there is none."""
    _needs_node()
    probe = HARNESS.split("// ------------------------------------------------------------------ drives")[0] + """
const n=new E('p');RECORD=n;LAST='';SEEN=[];
n.textContent='first';n.childNodes[0].data='second';
if(JSON.stringify(SEEN)!=='["first","second"]')
  throw new Error('the recorder does not record intermediates: '+JSON.stringify(SEEN));
console.log('ok');
"""
    result = _run(probe)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_a_chinese_reader_is_never_handed_an_english_value_to_speak():
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


MUTATIONS = (
    ("the same-task implementation — the one that shipped at b41d7e4, was read "
     "as correct, and left the live region holding English first",
     SAME_TASK_IMPLEMENTATION),
    ("the region is written directly with the source and never translated at "
     "all, so a Chinese reader gets English and keeps it",
     """function liveFragment(fill){return null;}
function liveText(node,value){if(node)node.textContent=String(value==null?'':value);}
function liveHTML(node,markup){if(node)node.innerHTML=String(markup==null?'':markup);}"""),
    ("the translation is deferred a task, which is where this whole class "
     "started",
     """function liveFragment(fill){return null;}
function liveText(node,value){if(!node)return;
  node.textContent=String(value==null?'':value);
  setTimeout(()=>localizeTree(node),0);}
function liveHTML(node,markup){if(!node)return;
  node.innerHTML=String(markup==null?'':markup);
  setTimeout(()=>localizeTree(node),0);}"""),
)


@pytest.mark.parametrize("why,replacement", MUTATIONS,
                         ids=[m[0][:38] for m in MUTATIONS])
def test_the_value_guard_is_shown_to_fail(why, replacement):
    """Run the mutant and read WHICH error fired, not merely that the exit code
    is non-zero — three times a guard of mine went red for an unrelated reason
    (a SyntaxError, a TypeError from a stub) and I recorded it as a catch."""
    _needs_node()
    sources = _sources()
    doors = "\n".join((_extract("function liveFragment(fill)"),
                        _extract("function liveText(node,value)"),
                        _extract("function liveHTML(node,markup)")))
    assert sources.count(doors) == 1, (
        "the mutation no longer applies; the live-region doors moved")
    result = _run(sources.replace(doors, replacement) + HARNESS)
    assert result.returncode != 0, f"MUTATION SURVIVED — {why}."
    first = next((line for line in result.stderr.splitlines()
                  if line.startswith("Error: ")), "")
    assert "the live region held" in first or "must never" in first \
        or "expected" in first or "restore the source" in first, (
        f"the mutant for {why!r} failed for the wrong reason, so this guard is "
        f"not known to catch it: {result.stderr[:400]}")


def test_the_doors_this_file_guards_are_the_ones_that_ship():
    assert CURRENT_IMPLEMENTATION.strip() in PAGE
