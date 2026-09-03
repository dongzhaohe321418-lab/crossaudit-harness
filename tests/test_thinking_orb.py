"""The thinking orb: one canvas where a state is in progress, nowhere else.

Two halves. The wrapper (``crossauditOrb``) is executed under node over a
canvas stub — theme, DPR, the frame loop, off-screen and hidden-tab pauses,
reduced motion, state switches, destroy. The surfaces (the optimistic turn,
the stream's status line) are the SHIPPED renderers executed over
progress payloads in EN and ZH, so the state map is asserted on what is
rendered and the aria-label on what a reader is told: the phase sentence,
never the drawing's name.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from crossaudit.console.page import PAGE
from crossaudit.console.progress import phase_i18n

from .node_eval import run_node

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "harness"
sys.path.insert(0, str(HARNESS))
VENDORED = ROOT / "src/crossaudit/console/vendor/thinking_orbs_engine.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

ENGINE_STATES = ("working", "searching", "solving", "listening", "connecting",
                 "weaving", "composing", "breathing", "shaping")
ENGINE_MODES = ("orbits", "globe", "rubik", "wave", "web", "braid", "ribbon", "ring", "morph")
#: A label that is, or begins as, the drawing's own name — what the engine's
#: React wrapper would announce by default and what a reader must never hear.
STATE_LABEL = re.compile(r"^(" + "|".join(ENGINE_STATES + ENGINE_MODES) + r")\b[\s.…]*$", re.I)
IDENTIFIER = re.compile(r"\b[0-9a-f]{12,}\b|\b(run|intake|cycle)[_ -]?id\b", re.I)

#: The state map the surfaces ship (page.py ORB_STATES), phase → engine state.
#: D149 collapsed the two size tiers into one: the standalone 64 px orb is
#: gone, so every phase now draws at the single 20 px mark that leads a live
#: line of words.
STATE_MAP = {"sending": "searching", "routing": "searching",
             "preparing": "connecting", "answering": "composing",
             "generating": "composing", "thinking": "weaving",
             "auditing": "solving", "waiting": "breathing",
             "stopping": "breathing"}


def _script() -> str:
    return PAGE.split("<script>")[1].split("</script>")[0]


def _orb_block() -> str:
    script = _script()
    start = script.index("// ---- The thinking orb.")
    return script[start:script.index("function intakeLines(intake){", start)]


def _snippet(sig: str) -> str:
    from render_decision import _extract
    return _extract(_script(), sig)


def _esc() -> str:
    script = _script()
    esc = script[script.index("const esc = s =>"):]
    return esc[:esc.index(";\n") + 1]


_DOM = r"""
let rafQueue=[],rafId=0,cancelled=[];
globalThis.requestAnimationFrame=cb=>{rafQueue.push({id:++rafId,cb});return rafId;};
globalThis.cancelAnimationFrame=id=>{cancelled.push(id);rafQueue=rafQueue.filter(f=>f.id!==id);};
function flush(n){for(let i=0;i<n;i++){const q=rafQueue;rafQueue=[];q.forEach(f=>f.cb(performance.now()));}}
let reduce=false,darkScheme=true;const mediaListeners={};
globalThis.matchMedia=q=>({matches:q.includes('reduced-motion')?reduce:darkScheme,
  addEventListener(t,f){(mediaListeners[q]=mediaListeners[q]||[]).push(f);},removeEventListener(){}});
class IO{constructor(cb){this.cb=cb;this.observed=[];IO.last=this;}observe(el){this.observed.push(el);}disconnect(){this.disconnected=true;}}
globalThis.IntersectionObserver=IO;
class MO{constructor(cb){this.cb=cb;MO.last=this;}observe(el,opts){this.target=el;this.opts=opts;}disconnect(){}}
globalThis.MutationObserver=MO;
const docListeners={};
const html={attrs:{'data-theme':'dark'},getAttribute(k){return k in this.attrs?this.attrs[k]:null;},
  classList:{contains:()=>false},parentElement:null};
let canvases=[];
globalThis.document={visibilityState:'visible',documentElement:html,
  addEventListener(t,f){(docListeners[t]=docListeners[t]||[]).push(f);},
  removeEventListener(t,f){docListeners[t]=(docListeners[t]||[]).filter(g=>g!==f);},
  querySelectorAll:()=>canvases};
function fire(t){(docListeners[t]||[]).forEach(f=>f());}
globalThis.window=globalThis;globalThis.devicePixelRatio=3;
function makeCanvas(attrs){const calls=[];
  const ctx=new Proxy({},{get(_,k){if(typeof k!=='string')return undefined;return(...a)=>calls.push(k);},set(){return true;}});
  return {attrs:Object.assign({},attrs||{}),style:{},isConnected:true,parentElement:html,calls,
    getContext:()=>ctx,setAttribute(k,v){this.attrs[k]=String(v);},getAttribute(k){return k in this.attrs?this.attrs[k]:null;},
    classList:{contains:()=>false},
    get paints(){return this.calls.filter(c=>c==='setTransform').length;}};}
let currentLocale='en';
"""


def _run(program: str) -> dict:
    out = run_node(program)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().split("\n")[-1])


def _wrapper_program(body: str) -> str:
    from extract_zh import shipped_js
    return "\n".join([_DOM, f"require({str(VENDORED)!r});", shipped_js(ROOT), _esc(),
                      _snippet("const localeText = (bundle, base) =>") + ";",
                      _orb_block(), body])


# =============================================================== the wrapper
@node
def test_mount_paints_once_synchronously_then_runs_one_frame_loop():
    out = _run(_wrapper_program(r"""
const c=makeCanvas();const orb=crossauditOrb(c,{state:'composing',size:64,label:'The generator is replying'});
const afterMount={paints:c.paints,width:c.width,height:c.height,cssW:c.style.width,role:c.attrs.role,
  label:c.attrs['aria-label'],running:orb.running,queued:rafQueue.length,live:ORB_LIVE.size};
flush(3);
// Every paint clears then draws: the first call after setTransform is clearRect and
// something is drawn before the next setTransform.
const seq=c.calls;let blank=0;
for(let i=0;i<seq.length;i++){if(seq[i]!=='setTransform')continue;if(seq[i+1]!=='clearRect'){blank++;continue;}
  let j=i+2,drew=false;while(j<seq.length&&seq[j]!=='setTransform'){if(seq[j]!=='clearRect')drew=true;j++;}if(!drew)blank++;}
console.log(JSON.stringify({afterMount,paintsAfter3:c.paints,blank,observed:IO.last.observed.length}));
"""))
    m = out["afterMount"]
    assert m["paints"] == 1, "the first frame is painted synchronously, before any rAF"
    assert m["width"] == 128 and m["height"] == 128, "DPR 3 is capped at 2"
    assert m["cssW"] == "64px" and m["role"] == "img"
    assert m["label"] == "The generator is replying"
    assert m["running"] and m["queued"] == 1 and m["live"] == 1
    assert out["paintsAfter3"] == 4 and out["blank"] == 0
    assert out["observed"] == 1, "the canvas is observed for visibility"


@node
def test_set_state_switches_the_drawing_on_the_next_paint_without_a_blank_frame():
    out = _run(_wrapper_program(r"""
const c=makeCanvas();const orb=crossauditOrb(c,{state:'working',size:20,label:'Still generating · 8 s'});
const before=c.paints;orb.setState('solving');const afterSwitch=c.paints;
const same=orb.state;orb.setState('solving');orb.setState('not-a-state');
flush(1);
console.log(JSON.stringify({before,afterSwitch,state:same,unchanged:orb.state,running:orb.running,label:c.attrs['aria-label'],paints:c.paints}));
"""))
    assert out["afterSwitch"] == out["before"] + 1, "a switch paints immediately"
    assert out["state"] == "solving" and out["unchanged"] == "solving"
    assert out["running"] and out["paints"] == out["afterSwitch"] + 1
    assert out["label"] == "Still generating · 8 s", "the label is not the engine's state word"


@node
def test_pause_resume_hidden_tab_and_off_screen_stop_and_restart_the_loop():
    out = _run(_wrapper_program(r"""
const c=makeCanvas();const orb=crossauditOrb(c,{state:'weaving',size:64,label:'Thinking · not audited'});
const r={};
orb.pause();r.pausedRunning=orb.running;const p=c.paints;flush(2);r.pausedPaints=c.paints-p;
orb.resume();r.resumedRunning=orb.running;flush(1);r.resumedPaints=c.paints-p;
document.visibilityState='hidden';fire('visibilitychange');r.hiddenRunning=orb.running;
document.visibilityState='visible';fire('visibilitychange');r.visibleRunning=orb.running;
IO.last.cb([{isIntersecting:false}]);r.offscreenRunning=orb.running;
IO.last.cb([{isIntersecting:true}]);r.onscreenRunning=orb.running;
console.log(JSON.stringify(r));
"""))
    assert out["pausedRunning"] is False and out["pausedPaints"] == 0
    assert out["resumedRunning"] is True and out["resumedPaints"] == 1
    assert out["hiddenRunning"] is False and out["visibleRunning"] is True
    assert out["offscreenRunning"] is False and out["onscreenRunning"] is True


@node
def test_reduced_motion_paints_exactly_one_still_frame():
    out = _run(_wrapper_program(r"""
reduce=true;
const c=makeCanvas();const orb=crossauditOrb(c,{state:'composing',size:64,label:'The generator is replying'});
const r={mounted:c.paints,running:orb.running,still:orb.still,queued:rafQueue.length};
flush(5);r.after=c.paints;orb.resume();flush(2);r.afterResume=c.paints;
// The preference lifting starts the loop; setting it again stops it on one frame.
reduce=false;orb.motionChanged();r.liftedRunning=orb.running;
reduce=true;orb.motionChanged();r.reRunning=orb.running;
console.log(JSON.stringify(r));
"""))
    assert out["mounted"] == 1 and out["running"] is False and out["still"] is True
    assert out["queued"] == 0 and out["after"] == 1 and out["afterResume"] == 1
    assert out["liftedRunning"] is True and out["reRunning"] is False


@node
def test_theme_follows_the_html_attribute_and_the_system_scheme_live():
    out = _run(_wrapper_program(r"""
const r={};
const c=makeCanvas();const orb=crossauditOrb(c,{state:'working',size:64,label:'x'});
r.dark=orb.dark;
html.attrs['data-theme']='light';MO.last.cb([]);r.light=orb.dark;
delete html.attrs['data-theme'];darkScheme=false;(mediaListeners['(prefers-color-scheme: dark)']||[]).forEach(f=>f());r.system=orb.dark;
const pinned=crossauditOrb(makeCanvas(),{state:'working',size:64,label:'x',theme:'dark'});r.pinned=pinned.dark;
r.watch=MO.last.target===html&&MO.last.opts.attributeFilter.includes('data-theme');
console.log(JSON.stringify(r));
"""))
    assert out["dark"] is True and out["light"] is False and out["system"] is False
    assert out["pinned"] is True and out["watch"] is True


@node
def test_destroy_releases_the_frame_loop_the_observer_and_the_listener():
    out = _run(_wrapper_program(r"""
const c=makeCanvas();const orb=crossauditOrb(c,{state:'solving',size:20,label:'Still auditing · 16 s'});
const id=rafQueue[0].id;const listeners=docListeners.visibilitychange.length;
orb.destroy();
const r={running:orb.running,cancelled:cancelled.includes(id),queued:rafQueue.length,
  disconnected:IO.last.disconnected===true,listeners:docListeners.visibilitychange.length,live:ORB_LIVE.size,paints:c.paints};
flush(3);r.paintsAfter=c.paints;orb.setState('working');orb.resume();r.stateAfter=orb.state;r.runningAfter=orb.running;
console.log(JSON.stringify(Object.assign(r,{listenersBefore:listeners})));
"""))
    assert out["running"] is False and out["cancelled"] and out["queued"] == 0
    assert out["disconnected"] and out["listeners"] == out["listenersBefore"] - 1
    assert out["live"] == 0 and out["paintsAfter"] == out["paints"]
    assert out["stateAfter"] == "solving" and out["runningAfter"] is False, "a destroyed orb stays dead"


@node
def test_mount_orbs_starts_new_canvases_and_releases_detached_ones():
    out = _run(_wrapper_program(r"""
const a=makeCanvas({'data-orb':'composing','data-orb-size':'20','aria-label':'Still generating · 8 s'});
canvases=[a];mountOrbs(document);
const r={mounted:Boolean(a.__orb),state:a.__orb&&a.__orb.state,live:ORB_LIVE.size,width:a.width};
mountOrbs(document);r.liveAgain=ORB_LIVE.size;
a.isConnected=false;const b=makeCanvas({'data-orb':'solving','data-orb-size':'64','aria-label':'Still auditing · 8 s'});
canvases=[b];mountOrbs(document);
r.after={live:ORB_LIVE.size,aRunning:a.__orb.running,bState:b.__orb.state,bWidth:b.width};
console.log(JSON.stringify(r));
"""))
    assert out["mounted"] and out["state"] == "composing" and out["live"] == 1 and out["width"] == 40
    assert out["liveAgain"] == 1, "a second pass does not double-mount"
    assert out["after"] == {"live": 1, "aRunning": False, "bState": "solving", "bWidth": 128}


# ============================================================== the state map
@node
def test_every_phase_maps_to_a_shipped_engine_state():
    """D149: one size, and the per-phase map survives the deletion of the
    64 px tier. Mutation: drop a phase from ORB_STATES and its drawing falls
    back to `working`, which the comparison below catches."""
    out = _run(_wrapper_program(r"""
const E=globalThis.ThinkingOrbsEngine;const r={phases:{}};
for(const phase of Object.keys(ORB_STATES)){
  const s=orbStateFor(phase);r.phases[phase]={state:s,mode:E.STATE_TO_MODE[s],draw:typeof E.MODE_DRAWS[E.STATE_TO_MODE[s]]};}
r.unknown=orbStateFor('no-such-phase');
console.log(JSON.stringify(r));
"""))
    got = out["phases"]
    assert {k: v["state"] for k, v in got.items()} == STATE_MAP
    for row in got.values():
        assert row["mode"] and row["draw"] == "function"
    assert out["unknown"] == "working"


# ============================================================== the surfaces
def _step(kind: str, text: str, actor: str = "loop", detail: str = "") -> dict:
    return {"kind": kind, "actor": actor, "text": text, "detail": detail,
            "text_i18n": phase_i18n(text), "t": 1788000000}


def _intake(phase: str, steps: list[dict], lane: str = "chat") -> dict:
    return {"id": "i1", "chat_id": "", "phase": phase, "steps": steps, "lane": lane,
            "finished": False}


RECEIVED = "Got it — working out who should handle this"
ROUTED = "The generator will do this"
REPLYING = "The generator is replying"
WAITING = "Waiting to retry the generator's provider · 2.5 s"

#: D149. The label is no longer the newest narration step: it is the LINE the
#: orb marks — the phase in words, the number that phase produces, and the
#: elapsed once it passes 5 s. `_intake` records carry no elapsed, so these
#: are the bare phase words.
OPTIMISTIC_CASES = {
    "no_intake": {"intake": None, "state": "searching",
                  "line": {"en": "Working out who should handle this", "zh": "正在判断由谁处理"}},
    "routing": {"intake": _intake("routing", [_step("received", RECEIVED)]),
                "state": "searching",
                "line": {"en": "Working out who should handle this", "zh": "正在判断由谁处理"}},
    "preparing": {"intake": _intake("preparing", [_step("received", RECEIVED), _step("routed", ROUTED, detail="generator")], "generator"),
                  "state": "connecting",
                  "line": {"en": "Reading the workspace", "zh": "正在读取工作区"}},
    "answering_chat": {"intake": _intake("answering", [_step("received", RECEIVED), _step("answering", REPLYING)]),
                       "state": "composing",
                       "line": {"en": "Writing a reply", "zh": "正在撰写回复"}},
    "answering_query": {"intake": _intake("answering", [_step("answering", "Looking up the audit record")], "query"),
                        "state": "composing",
                        "line": {"en": "Writing a reply", "zh": "正在撰写回复"}},
    "waiting": {"intake": _intake("answering", [_step("answering", REPLYING), _step("provider_recovery", WAITING)]),
                "state": "breathing",
                "line": {"en": "Waiting for the provider", "zh": "等待供应商"}},
    # The one case with a number: past the 5 s threshold the wait itself is
    # what the phase has to report, so it is the line's second half.
    "waiting_38s": {"intake": dict(_intake("answering", [_step("answering", REPLYING), _step("provider_recovery", WAITING)]), elapsed=38),
                    "state": "breathing",
                    "line": {"en": "Waiting for the provider · 38s", "zh": "等待供应商 · 已等 38 秒"}},
    "routing_72s": {"intake": dict(_intake("routing", [_step("received", RECEIVED)]), elapsed=72),
                    "state": "searching",
                    "line": {"en": "Working out who should handle this · 1m 12s",
                             "zh": "正在判断由谁处理 · 1 分 12 秒"}},
}


def _optimistic_program(cases: dict) -> str:
    from extract_zh import shipped_js
    program = "\n".join([
        _DOM, f"require({str(VENDORED)!r});", shipped_js(ROOT), _esc(),
        _snippet("const localeText = (bundle, base) =>") + ";",
        "const t = value => currentLocale==='zh' ? zhValue(value) : value;",
        "const forecastText = () => 'First run here';let lastState=null;",
        "const AUDITOR_LANES=new Set(['auditor','amendment','dispute','resolve','query']);",
        _orb_block(),
        _snippet("function intakeLines(intake)"),
        _snippet("function optimisticTurn(text, queued, intake, replying)"),
        f"const CASES={json.dumps(cases, ensure_ascii=False)};const out={{}};",
        r"""for(const locale of ['en','zh']){currentLocale=locale;out[locale]={};
for(const [name,c] of Object.entries(CASES))out[locale][name]=optimisticTurn('hello',Boolean(c.queued),c.intake,Boolean(c.replying));}
console.log(JSON.stringify(out));"""])
    return program


def _canvases(html: str) -> list[dict]:
    found = []
    for m in re.finditer(r"<canvas ([^>]*)></canvas>", html):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        found.append(attrs)
    return found


def _unescape(text: str) -> str:
    return (text.replace("&#39;", "'").replace("&quot;", '"').replace("&lt;", "<")
            .replace("&gt;", ">").replace("&amp;", "&"))


@node
def test_the_optimistic_turn_renders_one_20px_orb_marking_a_line_of_words_en_and_zh():
    """D149: nothing animates on its own. The turn carries ONE 20 px orb, and
    the words beside it are the orb's own label — the phase, its number, its
    elapsed. Mutation: drop the words from `livePhaseLine` and the
    label-is-on-screen assertion fails; restore the 64 px size and the size
    assertion fails."""
    out = _run(_optimistic_program(OPTIMISTIC_CASES))
    for locale in ("en", "zh"):
        for name, case in OPTIMISTIC_CASES.items():
            html = out[locale][name]
            assert "thinking-dots" not in html
            orbs = _canvases(html)
            assert len(orbs) == 1, (locale, name, html)
            orb = orbs[0]
            assert orb["data-orb"] == case["state"], (locale, name)
            assert orb["data-orb-size"] == "20" and orb["role"] == "img"
            assert "event-orb" in orb["class"] and "turn-orb" not in orb["class"]
            label = _unescape(orb["aria-label"])
            expected = case["line"][locale]
            assert label == expected, (locale, name, label)
            assert label in _unescape(html.split("</canvas>")[1]), "the label is the sentence on screen"
            if locale == "zh":
                assert re.search(r"[一-鿿]", label), (name, label)
            assert not STATE_LABEL.match(label), (name, label)
            assert not IDENTIFIER.search(label), (name, label)
            assert "aria-label=\"working\"" not in html.lower()


@node
def test_no_orb_once_a_reply_is_arriving_or_the_message_is_queued():
    out = _run(_optimistic_program({
        "replying": {"intake": _intake("answering", [_step("answering", REPLYING)]), "replying": True},
        "queued": {"intake": None, "queued": True}}))
    for locale in ("en", "zh"):
        for name in ("replying", "queued"):
            assert "<canvas" not in out[locale][name], (locale, name)


def _progress(state: str, steps: list[dict], finished: bool = False, outcome: str = "") -> dict:
    return {"progress": {"steps": steps, "finished": finished, "outcome": outcome,
                         "state": state, "task": "produce the experiment", "run_id": "r1"},
            "pipeline": [{"state": "done", "label": "Generate", "title": "Generate", "detail": "d"}],
            "cycles": [], "max_rounds": 3}


AUDIT_STEP = _step("auditor_reading", "The auditor is reading the commit", "auditor")
GEN_STEP = _step("prompt_ready", "Asking the generator to write", "generator")
CLOCK = _step("still_working", "Still generating · 16 s")
RETRY = _step("provider_recovery", "Retrying the generator's provider · attempt 2", "generator")

#: D149. The run card's single orb sits on the live PHASE line, not on the
#: newest thing that already happened. `_progress` records carry no elapsed,
#: so these lines are the phase words plus the number that phase produced.
DRAFTING = {"en": "Drafting", "zh": "正在撰写"}


def _line(en: str, zh: str) -> dict:
    return {"en": en, "zh": zh}


RUN_CASES = {
    "generating": {"state": _progress("GENERATING", [GEN_STEP]), "orb": "composing",
                   "line": DRAFTING},
    "revising": {"state": _progress("REVISING", [GEN_STEP]), "orb": "composing",
                 "line": DRAFTING},
    "auditing": {"state": _progress("AUDITING", [GEN_STEP, AUDIT_STEP]), "orb": "solving",
                 "line": _line("The auditor is reading", "审计者正在阅读")},
    "queued": {"state": _progress("QUEUED", [GEN_STEP]), "orb": "connecting",
               "line": _line("Reading the workspace", "正在读取工作区")},
    "clock_keeps_state": {"state": _progress("GENERATING", [GEN_STEP, CLOCK]), "orb": "composing",
                          "line": DRAFTING},
    "provider_wait_state": {"state": _progress("WAITING_FOR_PROVIDER", [GEN_STEP]), "orb": "breathing",
                            "line": _line("Waiting for the provider", "等待供应商")},
    "provider_retry_step": {"state": _progress("GENERATING", [GEN_STEP, RETRY]), "orb": "breathing",
                            "line": _line("Waiting for the provider", "等待供应商")},
    "thinking": {"state": _progress("GENERATING", [GEN_STEP]), "thinking": {"text": "weighing the units"},
                 "orb": "composing", "line": DRAFTING},
    # The draft's word count IS the generating phase's number, so the line
    # says it and no second draft row repeats it.
    "draft": {"state": _progress("GENERATING", [GEN_STEP]), "draft": {"text": "one two three"},
              "orb": "composing", "line": _line("Drafting · 3 words so far", "正在撰写 · 已写 3 字")},
    "thinking_and_draft": {"state": _progress("GENERATING", [GEN_STEP]), "thinking": {"text": "w"},
                           "draft": {"text": "one two"}, "orb": "composing",
                           "line": _line("Drafting · 2 words so far", "正在撰写 · 已写 2 字")},
    "stopping": {"state": _progress("CANCELLING", [GEN_STEP]), "orb": "breathing",
                 "line": _line("Stopping", "正在停止")},
}
NO_ORB_CASES = {
    "finished_passed": {"state": _progress("PASSED", [GEN_STEP, AUDIT_STEP], finished=True, outcome="passed")},
    "finished_blocked": {"state": _progress("WAITING_FOR_HUMAN", [GEN_STEP], finished=True, outcome="blocked")},
    "needs_person": {"state": _progress("WAITING_FOR_HUMAN", [GEN_STEP])},
    "needs_approval": {"state": _progress("WAITING_FOR_CAPABILITY", [GEN_STEP])},
    "provider_unavailable": {"state": _progress("PROVIDER_UNAVAILABLE", [GEN_STEP])},
}


def _status_line_program(cases: dict) -> str:
    """The SHIPPED status line, driven under node.

    The run card is gone: the one orb of a live run now leads the ONE line at
    the foot of the stream (docs/design/ACTIVITY_STREAM.md §The status line),
    and everything the card used to draw around it — the outcome pill, the step
    meter, the pipeline, the focus panel — went with it. The invariant this
    file exists for did not change: one canvas where a state is in progress,
    labelled with the sentence a person reads beside it.
    """
    from extract_zh import shipped_js
    program = "\n".join([
        _DOM, f"require({str(VENDORED)!r});", shipped_js(ROOT), _esc(),
        "const chatProgress=d=>d.progress;let activeChatId='';",
        "let THINKING=null,DRAFT=null;const liveDraftFor=()=>DRAFT;const liveThinkingFor=()=>THINKING;",
        _snippet("const localeText = (bundle, base) =>") + ";",
        "const t = value => currentLocale==='zh' ? zhValue(value) : value;",
        _snippet("function draftCount(text)"),
        _snippet("function formatUsd(value)"),
        _orb_block(),
        _snippet("function statusRoundText(p,d)"),
        _snippet("function statusCostText(d,p)"),
        _snippet("function statusLine(d)"),
        f"const CASES={json.dumps(cases, ensure_ascii=False)};const out={{}};",
        r"""for(const locale of ['en','zh']){currentLocale=locale;out[locale]={};
for(const [name,c] of Object.entries(CASES)){THINKING=c.thinking||null;DRAFT=c.draft||null;out[locale][name]=statusLine(c.state);}}
console.log(JSON.stringify(out));"""])
    return program


@node
def test_the_status_line_renders_one_orb_on_the_live_phase_line_en_and_zh():
    """D149, on the surface that replaced the run card: exactly one orb while
    a run is live, on the line that says what is happening now — never on an
    event row, which is a thing that already happened.

    Mutation: put the orb back on a finished row and the line carries two
    canvases; drop the count from the generating line and the `draft` case's
    expected words fail.
    """
    out = _run(_status_line_program(RUN_CASES))
    for locale in ("en", "zh"):
        for name, case in RUN_CASES.items():
            html = out[locale][name]
            orbs = _canvases(html)
            assert len(orbs) == 1, (locale, name, html)
            orb = orbs[0]
            assert orb["data-orb"] == case["orb"], (locale, name, orb)
            assert orb["data-orb-size"] == "20" and orb["role"] == "img" and "srow-orb" in orb["class"]
            label = _unescape(orb["aria-label"])
            expected = case["line"][locale]
            assert label == expected, (locale, name, label)
            assert not STATE_LABEL.match(label) and not IDENTIFIER.search(label), (name, label)
            if locale == "zh":
                assert re.search(r"[一-鿿]", label), (name, label)
            # The orb is the mark of the line whose words label it.
            text = html[html.index('<span class="stream-status-text">'):]
            text = text[:text.index("</span>")]
            assert expected in _unescape(text), (locale, name)
            assert html.count("<canvas") == 1
            # Interruptible always: the one control on the line stops the work.
            assert "stream-stop" in html and "requestStop()" in html


@node
def test_no_status_line_where_nothing_is_in_progress():
    """A finished, parked or person-waiting run is not "running", so there is
    no line at all — not a line with a still orb on it."""
    out = _run(_status_line_program(NO_ORB_CASES))
    for locale in ("en", "zh"):
        for name in NO_ORB_CASES:
            assert out[locale][name] == "", (locale, name)


# ================================================================ the markup
def test_the_dots_and_their_keyframes_are_gone_and_the_orb_is_mounted_after_each_render():
    assert "thinking-dots" not in PAGE
    assert "@keyframes think{" not in PAGE
    # D149: the 64 px standalone orb is deleted, size and all.
    assert "turn-orb" not in PAGE and "width:64px" not in PAGE
    assert ".event-orb{width:20px;height:20px;margin:1px}" in PAGE
    assert ".live-phase{" in PAGE and ".srow-orb{" in PAGE
    conv = PAGE[PAGE.index("document.getElementById('conversation').innerHTML = html;"):]
    assert conv.split("\n")[1].strip() == "mountOrbs(document.getElementById('conversation'));"
    # The orb's label is always the caller's sentence; the engine's default
    # state labels never reach the page.
    assert "Working…" not in _orb_block() and "Thinking…" not in _orb_block()


def test_the_orb_is_the_mark_of_a_line_of_words_never_an_event_of_its_own():
    """D149. Both surfaces reach the orb only through `livePhaseLine`, which
    cannot render a canvas without the sentence beside it. Mutation: call
    `orbMarkup` directly from either renderer and these counts fail."""
    line = _snippet("function livePhaseLine(phase,facts,cls)")
    assert "orbMarkup(" in line and "live-phase-text" in line
    turn = _snippet("function optimisticTurn(text, queued, intake, replying)")
    assert turn.count("orbMarkup(") == 0 and turn.count("livePhaseLine(") == 1
    # The stream: a row reaches the orb only for a `wait` shape, and only
    # through `rowMark`, which labels it with `rowText(r)` — the very line the
    # canvas sits beside. Every other shape gets a letter or a dot.
    mark = _snippet("function rowMark(r)")
    assert mark.count("orbMarkup(") == 1 and "rowText(r)" in mark
    assert "'<span class=\"srow-mark '" in mark
    row = _snippet("function row(r,d)")
    assert row.count("orbMarkup(") == 0 and row.count("rowMark(r)") == 1
    # The status line: one orb, labelled with the sentence it leads.
    status = _snippet("function statusLine(d)")
    assert status.count("orbMarkup(") == 1 and "orbMarkup(phase,text," in status
