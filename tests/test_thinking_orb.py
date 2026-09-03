"""The thinking orb: one canvas where a state is in progress, nowhere else.

Two halves. The wrapper (``crossauditOrb``) is executed under node over a
canvas stub — theme, DPR, the frame loop, off-screen and hidden-tab pauses,
reduced motion, state switches, destroy. The surfaces (the optimistic turn,
the run card's newest live row) are the SHIPPED renderers executed over
progress payloads in EN and ZH, so the state map is asserted on what is
rendered and the aria-label on what a reader is told: the phase sentence,
never the drawing's name.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.console.page import PAGE
from crossaudit.console.progress import phase_i18n

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
STATE_MAP = {
    64: {"sending": "working", "routing": "working", "preparing": "working",
         "answering": "composing", "generating": "composing", "thinking": "weaving",
         "auditing": "solving", "waiting": "breathing"},
    20: {"routing": "searching", "preparing": "connecting", "answering": "composing",
         "generating": "composing", "thinking": "weaving", "auditing": "solving",
         "waiting": "breathing"},
}


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
    out = subprocess.run(["node", "-e", program], text=True, capture_output=True)
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
def test_every_phase_maps_to_a_shipped_engine_state_at_both_sizes():
    out = _run(_wrapper_program(r"""
const E=globalThis.ThinkingOrbsEngine;const r={};
for(const size of [64,20]){r[size]={};for(const phase of Object.keys(ORB_STATES[size])){
  const s=orbStateFor(phase,size);r[size][phase]={state:s,mode:E.STATE_TO_MODE[s],draw:typeof E.MODE_DRAWS[E.STATE_TO_MODE[s]]};}}
r.unknown=orbStateFor('no-such-phase',20);
console.log(JSON.stringify(r));
"""))
    for size, table in STATE_MAP.items():
        got = out[str(size)]
        assert {k: v["state"] for k, v in got.items()} == table
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

OPTIMISTIC_CASES = {
    "no_intake": {"intake": None, "state": "working", "label": None},
    "routing": {"intake": _intake("routing", [_step("received", RECEIVED)]),
                "state": "working", "label": RECEIVED},
    "preparing": {"intake": _intake("preparing", [_step("received", RECEIVED), _step("routed", ROUTED, detail="generator")], "generator"),
                  "state": "working", "label": ROUTED},
    "answering_chat": {"intake": _intake("answering", [_step("received", RECEIVED), _step("answering", REPLYING)]),
                       "state": "composing", "label": REPLYING},
    "answering_query": {"intake": _intake("answering", [_step("answering", "Looking up the audit record")], "query"),
                        "state": "composing", "label": "Looking up the audit record"},
    "waiting": {"intake": _intake("answering", [_step("answering", REPLYING), _step("provider_recovery", WAITING)]),
                "state": "breathing", "label": WAITING},
}


def _render_optimistic(cases: dict) -> dict:
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
    return _run(program)


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
def test_the_optimistic_turn_renders_one_orb_per_phase_labelled_with_the_phase_text_en_and_zh():
    out = _render_optimistic(OPTIMISTIC_CASES)
    for locale in ("en", "zh"):
        for name, case in OPTIMISTIC_CASES.items():
            html = out[locale][name]
            assert "thinking-dots" not in html
            orbs = _canvases(html)
            assert len(orbs) == 1, (locale, name, html)
            orb = orbs[0]
            assert orb["data-orb"] == case["state"], (locale, name)
            assert orb["data-orb-size"] == "64" and orb["role"] == "img"
            assert "turn-orb" in orb["class"]
            label = _unescape(orb["aria-label"])
            if case["label"] is None:
                assert label == ("正在处理你的消息" if locale == "zh" else "Handling your message")
            else:
                expected = phase_i18n(case["label"])[locale]
                assert label == expected, (locale, name, label)
                assert label in _unescape(html.split("</canvas>")[1]), "the label is the sentence on screen"
            if locale == "zh":
                assert re.search(r"[一-鿿]", label), (name, label)
            assert not STATE_LABEL.match(label), (name, label)
            assert not IDENTIFIER.search(label), (name, label)
            assert "aria-label=\"working\"" not in html.lower()


@node
def test_no_orb_once_a_reply_is_arriving_or_the_message_is_queued():
    out = _render_optimistic({
        "replying": {"intake": _intake("answering", [_step("answering", REPLYING)]), "replying": True},
        "queued": {"intake": None, "queued": True}})
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

RUN_CASES = {
    "generating": {"state": _progress("GENERATING", [GEN_STEP]), "orb": "composing", "label": GEN_STEP["text"]},
    "revising": {"state": _progress("REVISING", [GEN_STEP]), "orb": "composing", "label": GEN_STEP["text"]},
    "auditing": {"state": _progress("AUDITING", [GEN_STEP, AUDIT_STEP]), "orb": "solving", "label": AUDIT_STEP["text"]},
    "queued": {"state": _progress("QUEUED", [GEN_STEP]), "orb": "connecting", "label": GEN_STEP["text"]},
    "clock_keeps_state": {"state": _progress("GENERATING", [GEN_STEP, CLOCK]), "orb": "composing", "label": CLOCK["text"]},
    "provider_wait_state": {"state": _progress("WAITING_FOR_PROVIDER", [GEN_STEP]), "orb": "breathing", "label": GEN_STEP["text"]},
    "provider_retry_step": {"state": _progress("GENERATING", [GEN_STEP, RETRY]), "orb": "breathing", "label": RETRY["text"]},
    "thinking": {"state": _progress("GENERATING", [GEN_STEP]), "thinking": {"text": "weighing the units"},
                 "orb": "weaving", "label": "Thinking · not audited", "row": "live-thinking"},
    "draft": {"state": _progress("GENERATING", [GEN_STEP]), "draft": {"text": "one two three"},
              "orb": "composing", "label": "Draft: 3 words so far", "row": "live-draft"},
    "thinking_and_draft": {"state": _progress("GENERATING", [GEN_STEP]), "thinking": {"text": "w"},
                           "draft": {"text": "one two"}, "orb": "weaving", "label": "Thinking · not audited",
                           "row": "live-thinking"},
    "stopping": {"state": _progress("CANCELLING", [GEN_STEP]), "orb": "working", "label": GEN_STEP["text"]},
}
NO_ORB_CASES = {
    "finished_passed": {"state": _progress("PASSED", [GEN_STEP, AUDIT_STEP], finished=True, outcome="passed")},
    "finished_blocked": {"state": _progress("WAITING_FOR_HUMAN", [GEN_STEP], finished=True, outcome="blocked")},
    "needs_person": {"state": _progress("WAITING_FOR_HUMAN", [GEN_STEP])},
    "needs_approval": {"state": _progress("WAITING_FOR_CAPABILITY", [GEN_STEP])},
    "provider_unavailable": {"state": _progress("PROVIDER_UNAVAILABLE", [GEN_STEP])},
}


def _render_run_cards(cases: dict) -> dict:
    from extract_zh import shipped_js
    program = "\n".join([
        _DOM, f"require({str(VENDORED)!r});", shipped_js(ROOT), _esc(),
        "const at=()=>'10:27';const artifactList=()=>'';",
        "const auditStatus=()=>'passed';const chatProgress=d=>d.progress;",
        "const chatCycles=()=>[];const statusOf=()=>'ready';",
        "let handoffAt=0,handoffDirection='';const runCostLine=()=>'';",
        "const forecastLine=()=>'';const titleOf=()=>'';",
        _snippet("const MARK = ") + ";",
        "let THINKING=null,DRAFT=null;const liveDraftFor=()=>DRAFT;const liveThinkingFor=()=>THINKING;",
        _snippet("const localeText = (bundle, base) =>") + ";",
        "const t = value => currentLocale==='zh' ? zhValue(value) : value;",
        _snippet("function draftCount(text)"),
        _snippet("function durationText("),
        _snippet("function elapsedText("),
        _snippet("function humaniseDetail("),
        _snippet("const ACTOR_NAMES") + ";",
        _snippet("const ACTOR_MARKS") + ";",
        _snippet("function conciseDetail("),
        _orb_block(),
        _snippet("function activityRow(s, orbPhase)"),
        _snippet("const CLOCK_KINDS") + ";",
        _snippet("function collapseClockRows("),
        _snippet("function runCard(d)"),
        f"const CASES={json.dumps(cases, ensure_ascii=False)};const out={{}};",
        r"""for(const locale of ['en','zh']){currentLocale=locale;out[locale]={};
for(const [name,c] of Object.entries(CASES)){THINKING=c.thinking||null;DRAFT=c.draft||null;out[locale][name]=runCard(c.state);}}
console.log(JSON.stringify(out));"""])
    return _run(program)


@node
def test_the_run_card_renders_one_orb_on_the_newest_live_line_en_and_zh():
    out = _render_run_cards(RUN_CASES)
    for locale in ("en", "zh"):
        for name, case in RUN_CASES.items():
            html = out[locale][name]
            orbs = _canvases(html)
            assert len(orbs) == 1, (locale, name, html)
            orb = orbs[0]
            assert orb["data-orb"] == case["orb"], (locale, name, orb)
            assert orb["data-orb-size"] == "20" and orb["role"] == "img" and "event-orb" in orb["class"]
            label = _unescape(orb["aria-label"])
            if case["label"] == "Thinking · not audited":
                expected = "思考中 · 未经审计" if locale == "zh" else case["label"]
            elif case["label"].startswith("Draft: "):
                expected = "草稿：已写 3 字" if locale == "zh" else case["label"]
            else:
                expected = phase_i18n(case["label"])[locale]
            assert label == expected, (locale, name, label)
            assert not STATE_LABEL.match(label) and not IDENTIFIER.search(label), (name, label)
            if locale == "zh":
                assert re.search(r"[一-鿿]", label), (name, label)
            # The orb is the mark of the row whose sentence labels it.
            row = html[html.index("<canvas"):]
            row = row[:row.index("</div>", row.index("event-line"))]
            assert expected in _unescape(row), (locale, name)
            if case.get("row"):
                before = html[:html.index("<canvas")]
                assert before.rstrip().endswith(case["row"] + '">' if case["row"] == "live-draft"
                                                else "<summary>"), (name, before[-80:])
            # Only the newest line carries it: every other row keeps its actor mark.
            assert html.count("<canvas") == 1


@node
def test_no_orb_where_nothing_is_in_progress():
    out = _render_run_cards(NO_ORB_CASES)
    for locale in ("en", "zh"):
        for name in NO_ORB_CASES:
            html = out[locale][name]
            assert "<canvas" not in html, (locale, name)
            assert "event-mark" in html, "the rows keep their ordinary marks"


# ================================================================ the markup
def test_the_dots_and_their_keyframes_are_gone_and_the_orb_is_mounted_after_each_render():
    assert "thinking-dots" not in PAGE
    assert "@keyframes think{" not in PAGE
    assert ".turn-orb{width:64px;height:64px}" in PAGE
    assert ".event-orb{width:20px;height:20px;margin:1px}" in PAGE
    conv = PAGE[PAGE.index("document.getElementById('conversation').innerHTML = html;"):]
    assert conv.split("\n")[1].strip() == "mountOrbs(document.getElementById('conversation'));"
    # The orb's label is always the caller's sentence; the engine's default
    # state labels never reach the page.
    assert "Working…" not in _orb_block() and "Thinking…" not in _orb_block()


def test_the_orb_is_the_mark_never_an_addition():
    """The orb replaces the dots (optimistic turn) and the newest row's mark
    (run card); it is never rendered next to either."""
    turn = _snippet("function optimisticTurn(text, queued, intake, replying)")
    assert turn.count("orbMarkup(") == 1 and "event-mark" not in turn
    row = _snippet("function activityRow(s, orbPhase)")
    assert "orbPhase ? orbMarkup(orbPhase, 20, line, 'event-orb')" in row
    assert ": '<span class=\"event-mark '" in row
    card = _snippet("function runCard(d)")
    assert card.count("orbMarkup(") == 2, "the thinking row and the draft row"
    assert "orbPhase && !thinking && !draft && i === rows.length - 1" in card
