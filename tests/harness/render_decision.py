"""Render the Decision Center's text slots through the SHIPPED openResolution()
under node with a fake DOM, EN and ZH (ZH = zhValue over each slot, the way
the locale observer translates text nodes). A string assertion on page.py
cannot see which branch a row takes; this can."""
from __future__ import annotations

import json
import pathlib
import subprocess

from extract_zh import shipped_js

SLOTS = ["resolution-flag", "resolution-title", "resolution-summary",
         "resolution-limit-title", "resolution-limit-copy", "resolution-request",
         "resolution-reopen-title", "resolution-reopen-copy", "resolution-issues"]


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
const mk=id=>({_id:id,hidden:false,className:'',value:'',classList:{add(){},remove(){}},
  setAttribute(){},removeAttribute(){},querySelector:()=>null,querySelectorAll:()=>[],focus(){},
  set textContent(v){slots[id]=String(v);},get textContent(){return slots[id]||'';},
  set innerHTML(v){slots[id]=String(v);},get innerHTML(){return slots[id]||'';}});
const els={};
globalThis.document={getElementById:id=>els[id]||(els[id]=mk(id)),
  querySelector:()=>({setAttribute(){},removeAttribute(){}}),body:{classList:{add(){},remove(){}}}};
globalThis.lastState=null;globalThis.activeResolution=null;globalThis.promptedEscalations=new Set();
globalThis.resolutionModal=mk('resolution-modal');globalThis.resolutionForm=mk('resolution-form');
globalThis.resolutionChoice=()=>{};globalThis.renderDecisionBanner=()=>{};globalThis.announce=()=>{};
globalThis.titleOf=()=>'';globalThis.setTimeout=()=>{};
const ROWS=%s;const SLOTS=%s;const out={};
const strip=h=>String(h).replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
for(const [name,row] of Object.entries(ROWS)){
  for(const k in slots)delete slots[k];
  openResolution(row);out[name]={en:{},zh:{}};
  for(const k of SLOTS){let v=slots[k]||'';if(k==='resolution-issues')v=strip(v);
    out[name].en[k]=v;out[name].zh[k]=zhValue(v);}}
console.log(JSON.stringify(out));
"""


def render(worktree: pathlib.Path, rows: dict) -> dict:
    """{row name: {"en": {slot: text}, "zh": {slot: text}}} for each row."""
    src = (worktree / "src/crossaudit/console/page.py").read_text()
    script = src.split("<script>")[1].split("</script>")[0]
    esc = script[script.index("const esc = s =>"):]
    esc = esc[:esc.index(";\n") + 1]
    parts = [shipped_js(worktree), esc,
             _extract(script, "function hasRemediation(row,action)"),
             _extract(script, "function openResolution(value,action='',sha='')"),
             _extract(script, "function decisionSentence()"),
             _extract(script, "function setDecidingInert(on)")]
    js = "\n".join(parts) + _SHIM % (json.dumps(rows), json.dumps(SLOTS))
    out = subprocess.run(["node", "-e", js], text=True, capture_output=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)
