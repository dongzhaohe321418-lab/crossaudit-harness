"""Render the Decision Center's text slots through the SHIPPED openResolution()
under node with a fake DOM, EN and ZH (ZH = zhValue over each slot, the way
the locale observer translates text nodes). A string assertion on page.py
cannot see which branch a row takes; this can."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

from extract_zh import shipped_js

SLOTS = ["resolution-flag", "resolution-title", "resolution-summary",
         "resolution-limit-title", "resolution-limit-copy", "resolution-request",
         "resolution-reopen-title", "resolution-reopen-copy", "resolution-issues"]


def _run_node(js: str) -> subprocess.CompletedProcess:
    """Run `js` under node from a FILE, never from `node -e <argv>`.

    The assembled program is ~200 KB. Linux caps a single argv entry at
    `MAX_ARG_STRLEN` (128 KiB), so `node -e js` raised
    `OSError: [Errno 7] Argument list too long` on every Linux runner while
    passing on macOS, whose limit is on the total block rather than one entry.
    A temporary file has no such cap and is byte-identical input.
    """
    handle, path = tempfile.mkstemp(suffix=".js", text=False)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(js)
        return subprocess.run(["node", path], text=True, capture_output=True,
                              encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)


def _extract(script: str, sig: str) -> str:
    start = script.index(sig)
    depth, i = 0, script.index("{", start)
    while i < len(script):
        if script[i] == "{":
            depth += 1
        elif script[i] == "}":
            depth -= 1
            if depth == 0:
                return script[start:i + 1]
        i += 1
    raise AssertionError(sig)


_SHIM = r"""
const slots={};
const mk=id=>({_id:id,hidden:false,className:'',value:'',classList:{add(){},remove(){}},attrs:{},
  setAttribute(k,v){this.attrs[k]=String(v);},getAttribute(k){return k in this.attrs?this.attrs[k]:null;},
  removeAttribute(k){delete this.attrs[k];},querySelector:()=>null,querySelectorAll:()=>[],focus(){},
  set textContent(v){slots[id]=String(v);},get textContent(){return slots[id]||'';},
  set innerHTML(v){slots[id]=String(v);},get innerHTML(){return slots[id]||'';}});
const els={};
globalThis.document={getElementById:id=>els[id]||(els[id]=mk(id)),
  querySelector:()=>({setAttribute(){},removeAttribute(){}}),body:{classList:{add(){},remove(){}}}};
globalThis.lastState=null;globalThis.activeResolution=null;globalThis.promptedEscalations=new Set();
globalThis.resolutionModal=mk('resolution-modal');globalThis.resolutionForm=mk('resolution-form');
globalThis.resolutionChoice=()=>{};globalThis.renderDecisionBanner=()=>{};globalThis.announce=()=>{};
// The page's short-word translator (`t`), the way page.py defines it.
globalThis.t=v=>globalThis.currentLocale==='zh'?zhValue(v):v;
globalThis.titleOf=()=>'';globalThis.setTimeout=()=>{};
const ROWS=%s;const SLOTS=%s;const out={};
const strip=h=>String(h).replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
// Two passes per row: the page's own locale accessor is `currentLocale`,
// and a row may carry a pre-localised field (`why_zh`) the ZH pass prefers.
for(const [name,row] of Object.entries(ROWS)){
  out[name]={en:{},zh:{}};
  for(const locale of ['en','zh']){
    globalThis.currentLocale=locale;
    for(const k in slots)delete slots[k];
    openResolution(row);
    for(const k of SLOTS){let v=slots[k]||'';if(k==='resolution-issues')v=strip(v);
      out[name][locale][k]=locale==='zh'?zhValue(v):v;}
    // Additive: the guidance box's prefilled value (already localised by the
    // page's own `t`) and the secondary button's label, visibility and target.
    // Kept OUTSIDE the slot maps (which older tests sweep as text).
    out[name].extra=out[name].extra||{};
    const sb=els['resolution-open-settings'];
    out[name].extra[locale]={reason_value:els['resolution-reason']?els['resolution-reason'].value:'',
      settings_text:sb?(locale==='zh'?zhValue(sb.textContent):sb.textContent):'',
      settings_hidden:sb?Boolean(sb.hidden):true,
      settings_earlier:sb?(sb.getAttribute('data-earlier-cycle')||''):''};}}
console.log(JSON.stringify(out));
"""


def render(worktree: pathlib.Path, rows: dict) -> dict:
    """{row name: {"en": {slot: text}, "zh": {slot: text}, "extra": {...}}}
    for each row; `extra[locale]` carries the guidance box's prefilled value
    and the secondary button's label / visibility / target cycle."""
    src = (worktree / "src/crossaudit/console/page.py").read_text()
    script = src.split("<script>")[1].split("</script>")[0]
    esc = script[script.index("const esc = s =>"):]
    esc = esc[:esc.index(";\n") + 1]
    parts = [shipped_js(worktree), esc,
             _extract(script, "function hasRemediation(row,action)"),
             # R1/R5: the cause copy table and the plain verdict words the
             # Decision Center renders through.
             _extract(script, "const CAUSE_COPY={"),
             _extract(script, "const VERDICT_WORDS={"),
             _extract(script, "function verdictWord(v)"),
             _extract(script, "function severityWord(sev)"),
             _extract(script, "function ruleTitle(rule)"),
             _extract(script, "function openResolution(value,action='',sha='')"),
             _extract(script, "function decisionSentence()"),
             _extract(script, "function setDecidingInert(on)"),
             # Billing slice: openResolution appends the reset moment (budget
             # pause) or the 429 countdown (provider pause) to the summary.
             # With the shim's lastState=null both read nothing and the slots
             # stay exactly what the branches wrote.
             _extract(script, "function resetWords(g)"),
             _extract(script, "function countdownText(resetAt)"),
             _extract(script, "function resetSentence(resetAt)"),
             _extract(script, "function appendResolutionReset(row,budget,provider)")]
    js = "\n".join(parts) + _SHIM % (json.dumps(rows), json.dumps(SLOTS))
    out = _run_node(js)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def eval_page(worktree: pathlib.Path, signatures: list[str], body: str,
              prelude: str = "") -> str:
    """Run `body` under node with the shipped catalogue, `esc`, and the page
    functions named by `signatures` (each a `function name(` prefix) in scope.
    `prelude` may define stubs the functions expect. Returns stdout."""
    src = (worktree / "src/crossaudit/console/page.py").read_text()
    script = src.split("<script>")[1].split("</script>")[0]
    esc = script[script.index("const esc = s =>"):]
    esc = esc[:esc.index(";\n") + 1]
    parts = [shipped_js(worktree), esc, prelude]
    parts += [_extract(script, sig) for sig in signatures]
    js = "\n".join(parts) + "\n" + body
    out = _run_node(js)
    assert out.returncode == 0, out.stderr
    return out.stdout
