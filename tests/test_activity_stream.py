"""The activity stream (docs/design/ACTIVITY_STREAM.md).

The design document's Rules section is not prose here: each rule is a test, and
each test drives the SHIPPED page under node rather than reading a string out
of the source, because a string assertion cannot see which branch a row takes.

This file grows one section per numbered part of the rebuild. Section 1 is the
row model and the guard that makes design rule 6 mechanical.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from crossaudit.console import overview

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))

WORKTREE = Path(overview.__file__).parents[3]
needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

#: Declared in the page but not (yet) readable from an emitter. Each is here
#: with the reason it is declared, so an entry that stops meaning anything is
#: visible rather than merely tolerated.
DECLARED_AHEAD = {
    # console/progress.py lists it in PHASE_KINDS: the intake may project it
    # for a lane that answers without a run.
    "answered": "console/progress.py PHASE_KINDS",
    # Section 4a: the bounded repair attempt before an unreadable auditor
    # reply becomes anyone's problem. Emitted from cli/build.py once that
    # section lands; declared first so the row is never undesigned.
    "audit_repair_retry": "section 4a, the auditor repair retry",
}


def _js(names: list[str]) -> dict:
    """The named page constants/functions, evaluated under node."""
    from render_decision import eval_page

    body = ("console.log(JSON.stringify({"
            + ",".join(f"{n}:{n}" for n in names) + "}));")
    sigs = [f"const {n}=" for n in names]
    return json.loads(eval_page(WORKTREE, sigs, body))


# ============================================== 1. one row model, one shape
@needs_node
def test_every_emitted_event_kind_declares_exactly_one_shape():
    """Design rule 6, made mechanical.

    The kinds are enumerated FROM THE SOURCE (tests/harness/event_kinds.py),
    so a new ``emit()`` lands in this assertion because it was written, not
    because someone remembered to list it.

    Mutation: add ``emit("weather_changed", ...)`` to cli/build.py and this
    fails naming it; delete a line from EVENT_SHAPES and it fails naming that.
    """
    import event_kinds

    tables = _js(["EVENT_SHAPES", "ROW_SHAPES"])
    declared, shapes = tables["EVENT_SHAPES"], tables["ROW_SHAPES"]
    emitted = event_kinds.emitted_kinds()

    undeclared = sorted(set(emitted) - set(declared))
    assert not undeclared, (
        "these event kinds are emitted with no shape declared in "
        f"EVENT_SHAPES, so the stream would drop them silently: {undeclared}")

    stale = sorted(set(declared) - set(emitted) - set(DECLARED_AHEAD))
    assert not stale, (
        f"EVENT_SHAPES declares kinds nothing emits: {stale}. Either the "
        "emitter was deleted or the entry was a guess.")

    wrong = {k: v for k, v in declared.items() if v not in shapes}
    assert not wrong, f"shapes outside the design's five: {wrong}"
    assert set(shapes) == {"say", "do", "wait", "outcome", "note"}


@needs_node
def test_every_declared_kind_has_words_in_both_languages():
    """Design rule 7: every string is EN and ZH at the same commit.

    Mutation: drop the ``zh`` half of any EVENT_VERBS row and this fails
    naming the kind.
    """
    tables = _js(["EVENT_SHAPES", "EVENT_VERBS"])
    missing = sorted(k for k in tables["EVENT_SHAPES"]
                     if not (tables["EVENT_VERBS"].get(k, {}).get("en")
                             and tables["EVENT_VERBS"].get(k, {}).get("zh")))
    assert not missing, f"kinds with no verb phrase in both languages: {missing}"

    same = sorted(k for k, v in tables["EVENT_VERBS"].items()
                  if v.get("en") == v.get("zh"))
    assert not same, f"kinds whose Chinese is its English: {same}"


@needs_node
def test_a_row_refuses_a_shape_the_design_does_not_have():
    """``streamRow`` returns null rather than a row nobody designed.

    Mutation: make streamRow pass an unknown shape through and this fails.
    """
    from render_decision import eval_page

    out = eval_page(WORKTREE, ["const ROW_SHAPES=", "function streamRow(o)"],
                    "console.log(JSON.stringify(["
                    "streamRow({shape:'card',line:'x'})===null,"
                    "streamRow({shape:'',line:'x'})===null,"
                    "streamRow({shape:'note',line:'x'})!==null]));")
    assert json.loads(out) == [True, True, True]


@needs_node
def test_one_number_per_row_and_never_a_zero():
    """Design rules 3 and 5: one number, and a zero is not a count.

    Mutation: let rowNumber render a 0 and the third case fails.
    """
    from render_decision import eval_page

    body = """
const CASES=[{value:4,unit:'checks'},{value:1,unit:'file'},{value:0,unit:'files'},
  {value:412,unit:'words'},{value:2,unit:'retries'},{value:1,unit:'findings'},
  null,{value:3,unit:'nonsense'}];
const out={};
for(const locale of ['en','zh']){currentLocale=locale;
  out[locale]=CASES.map(c=>rowNumber(c));}
console.log(JSON.stringify(out));
"""
    out = json.loads(eval_page(
        WORKTREE,
        ["const ROW_UNITS=", "function rowNumber(n)", "function elapsedWords(seconds)"],
        body, prelude="let currentLocale='en';"))
    assert out["en"] == ["4 checks", "", "", "412 words", "retried 2 times",
                         "1 finding", "", ""]
    assert out["zh"] == ["4 项", "", "", "412 字", "已重试 2 次",
                         "1 条发现", "", ""]


@needs_node
def test_the_stream_is_one_ordered_list_of_declared_rows():
    """One list, chronological, every row carrying a declared shape.

    Mutation: emit a step whose kind is not in EVENT_SHAPES and it does not
    reach the list; reorder the sort and the timestamps stop ascending.
    """
    from render_decision import eval_page

    state = {
        "messages": [
            {"kind": "you", "t": 10, "utterance": "write the report"},
            {"kind": "generator", "t": 40, "summary": "wrote it", "round": 1},
        ],
        "steps": [
            {"kind": "round_started", "t": 12, "actor": "loop", "round_no": 1},
            {"kind": "generation_started", "t": 15, "actor": "generator",
             "round_no": 1},
            {"kind": "generation_completed", "t": 30, "actor": "generator",
             "round_no": 1},
            {"kind": "weather_changed", "t": 35, "actor": "loop"},
            {"kind": "audit_passed", "t": 50, "actor": "auditor", "round_no": 1},
        ],
    }
    body = ("currentLocale='en';const rows=streamRows({},%s);"
            "console.log(JSON.stringify(rows.map(r=>[r.shape,r.kind,r.t,r.line])));"
            % json.dumps(state))
    rows = json.loads(eval_page(WORKTREE, _MODEL_SIGS, body, prelude=_MODEL_PRELUDE))
    assert [r[1] for r in rows] == ["you", "generation_started",
                                    "generation_completed", "generator",
                                    "audit_passed"]
    assert [r[0] for r in rows] == ["say", "wait", "do", "say", "outcome"]
    assert [r[2] for r in rows] == sorted(r[2] for r in rows)
    # round_started carries its number onto the round's outcome row; it is not
    # a row of its own. An undeclared kind is simply not rendered.
    assert "round_started" not in [r[1] for r in rows]
    assert "weather_changed" not in [r[1] for r in rows]


_MODEL_PRELUDE = """
let currentLocale='en';
const localeText=(bundle,base)=>bundle&&bundle[currentLocale]?bundle[currentLocale]:base;
function humaniseDetail(t){return t;}
function elapsedWords(s){return s+'s';}
"""

_MODEL_SIGS = [
    "const EVENT_SHAPES=", "const CARRIED_KINDS=", "const EVENT_VERBS=",
    "const ROW_SHAPES=", "const ROW_UNITS=", "const STEP_ACTORS=",
    "function rowNumber(n)", "function shapeOf(kind)", "function verbOf(kind)",
    "function wireLine(s)", "function streamRow(o)", "function actorOfStep(s)",
    "function conciseDetail(s)", "function rowFromStep(s,d)",
    "function rowFromMessage(m,d)", "function streamRows(d,ctx)",
]


# =============================================== 2. one renderer, five shapes
_RENDER_PRELUDE = _MODEL_PRELUDE + """
function at(t){return 't'+t;}
function orbMarkup(phase,label,cls){
  return '<canvas class="orb '+cls+'" data-orb="'+phase+'" data-orb-size="20" '
    +'role="img" aria-label="'+esc(label)+'"></canvas>';}
function turn(m,d){return '<article class="turn"><div class="turn-body">'
  +esc(m.utterance||m.summary||m.response||'')+'</div></article>';}
function withTurnCost(html,m,d){return html;}
"""

_RENDER_SIGS = _MODEL_SIGS + [
    "const ROW_MARKS=", "const ROW_KIND_MARKS=", "const ROW_PHASES=",
    "const MERGE_UNITS=", "const STATUS_PHASE_ROWS=",
    "function rowPhase(r)", "function dropSettledWaits(rows)",
    "function mergeRuns(rows)", "function groupRounds(rows,current)",
    "function streamList(d,ctx)", "function rowText(r)", "function rowMark(r)",
    "function rowDetailHtml(detail,d)", "function rowActionHtml(action)",
    "function row(r,d)",
]


def _render(state: dict, locale: str = "en", body: str = "") -> str:
    from render_decision import eval_page

    program = (f"currentLocale={json.dumps(locale)};"
               f"const rows=streamList({{}},{json.dumps(state)});"
               + (body or "console.log(rows.map(r=>row(r,{})).join(''));"))
    return eval_page(WORKTREE, _RENDER_SIGS, program, prelude=_RENDER_PRELUDE)


@needs_node
def test_a_live_line_and_its_finished_line_never_both_appear():
    """Design: a `wait` row is replaced by the `do` row that resolves it.

    Mutation: delete dropSettledWaits from streamList and the drafting line
    survives beside "Drafted", which is the same fact said twice.
    """
    state = {"round": 1, "steps": [
        {"kind": "generation_started", "t": 10, "actor": "generator", "round_no": 1},
        {"kind": "generation_completed", "t": 20, "actor": "generator", "round_no": 1},
        {"kind": "audit_started", "t": 25, "actor": "auditor", "round_no": 1},
    ]}
    out = _render(state, body="console.log(JSON.stringify(rows.map(r=>[r.shape,r.kind])));")
    assert json.loads(out) == [["do", "generation_completed"],
                              ["wait", "audit_started"]]


@needs_node
def test_repetition_collapses_to_one_row_with_a_count():
    """Design rule: three consecutive reads become one row with a count.

    The deterministic checks are the case the design names: one row,
    ``自动检查通过 · 4 项``, expanding to the per-check list.

    Mutation: remove mergeRuns and four rows survive.
    """
    steps = [{"kind": "check_finished", "t": 10 + i, "actor": "auditor",
              "round_no": 1, "text_i18n": {"en": f"check {i} passed",
                                           "zh": f"检查 {i} 通过"}}
             for i in range(4)]
    state = {"round": 1, "steps": steps}
    shapes = json.loads(_render(
        state, body="console.log(JSON.stringify(rows.map("
                    "r=>[r.kind,r.n,(r.merged||[]).length])));"))
    assert shapes == [["check_finished", {"value": 4, "unit": "checks"}, 4]]
    en, zh = _render(state).strip(), _render(state, "zh").strip()
    # The collapsed line speaks the KIND's words: "check 3 passed · 4 checks"
    # would read as a claim about check 3.
    assert "Automatic checks passed · 4 checks" in en, en
    assert "自动检查通过 · 4 项" in zh, zh
    # The per-check list is the DETAIL, opened in place — not a second region.
    assert en.count("<details") == 1 and en.count("check 0 passed") == 1


@needs_node
def test_a_finished_round_collapses_into_its_own_outcome_row():
    """Design: a round is a group, not a region; its number lives on the row.

    Mutation: drop groupRounds and round 1's working rows stay expanded above
    round 2, which is the "new region per round" the rebuild removes.
    """
    state = {"round": 2, "steps": [
        {"kind": "generation_completed", "t": 10, "actor": "generator", "round_no": 1},
        {"kind": "audit_blocked", "t": 20, "actor": "auditor", "round_no": 1},
        {"kind": "generation_completed", "t": 30, "actor": "generator", "round_no": 2},
    ]}
    rows = json.loads(_render(state, body="console.log(JSON.stringify(rows.map("
                                          "r=>[r.kind,r.round,(r.rolled||[]).length])));"))
    assert rows == [["audit_blocked", 1, 1], ["generation_completed", 2, 0]]
    zh = _render(state, "zh")
    assert "需要修改 · 第 1 轮" in zh, zh


@needs_node
def test_no_animation_appears_without_words_beside_it():
    """Design rule 2. The orb is the MARK of a line; it is labelled with the
    very sentence it sits beside, so what is heard and what is read agree.

    Mutation: pass '' as the orb label and this fails.
    """
    state = {"round": 1, "steps": [
        {"kind": "audit_started", "t": 10, "actor": "auditor", "round_no": 1}]}
    for locale, words in (("en", "The auditor is reading"),
                          ("zh", "审计者正在阅读")):
        html = _render(state, locale)
        assert "<canvas" in html
        assert f'aria-label="{words}"' in html, html
        assert f">{words}<" in html, html


@needs_node
def test_no_row_opens_a_modal_and_every_detail_opens_in_place():
    """Design rule 1 and the row anatomy: detail is a disclosure, never a
    dialog and never a navigation.

    Mutation: render a detail as a <dialog> or an href and this fails.
    """
    state = {"round": 1, "steps": [
        {"kind": "provider_unavailable", "t": 10, "actor": "loop", "round_no": 1,
         "detail": "the provider returned an empty completion"},
        {"kind": "generation_completed", "t": 20, "actor": "generator", "round_no": 1},
    ]}
    html = _render(state)
    assert "<details" in html
    for forbidden in ("<dialog", "role=\"dialog\"", "role=\"alertdialog\"",
                      "<a href", "location.href", "project-modal"):
        assert forbidden not in html, forbidden


@needs_node
def test_one_number_per_row_on_the_rendered_line():
    """Design rule 5, on the surface rather than in the model: the rendered
    line carries at most one count.

    Mutation: append a second number to rowText and this fails.
    """
    import re

    state = {"round": 1, "steps": [
        {"kind": "check_finished", "t": 10, "actor": "auditor", "round_no": 1},
        {"kind": "check_finished", "t": 11, "actor": "auditor", "round_no": 1},
    ]}
    html = _render(state)
    line = re.search(r'<span class="srow-verb">([^<]*)</span>', html).group(1)
    assert len(re.findall(r"\d+", line)) == 1, line


# ==================================================== 3. one status line
_STATUS_SIGS = ["function elapsedWords(seconds)", "const PHASE_WORDS=",
                "function phaseWords(phase)", "function phaseCount(phase,facts)",
                "const ORB_STATES=", "function orbStateFor(phase)",
                "function orbMarkup(phase,label,cls)",
                "function orbWaitingStep(step)", "function runOrbPhase(p)",
                "function formatUsd(value)", "function statusRoundText(p,d)",
                "function statusCostText(d,p)", "function statusLine(d)"]
_STATUS_PRELUDE = """
let currentLocale='en';const PHASE_ELAPSED_S=5;
const chatProgress=d=>d.progress;const liveDraftFor=()=>null;
const liveFileCount=()=>0;const draftCount=()=>0;
"""


def _status(state: dict, locale: str = "en") -> str:
    from render_decision import eval_page

    return eval_page(WORKTREE, _STATUS_SIGS,
                     f"currentLocale={json.dumps(locale)};"
                     f"console.log(statusLine({json.dumps(state)}));",
                     prelude=_STATUS_PRELUDE).strip()


_RUNNING = {"max_rounds": 3, "progress": {
    "run_id": "r1", "state": "AUDITING", "finished": False, "elapsed": 38,
    "steps": [{"kind": "round_started", "round_no": 1, "round_limit": 3}]},
    "usage": {"attribution": {"runs": {"r1": {"api_value_usd": 0.04,
                                              "unpriced_calls": 0}}}}}


@needs_node
def test_the_status_line_is_the_design_line_in_both_languages():
    """The design writes the line out in full:

        [orb] 正在撰写 · 第 1/3 轮 · 38 秒 · ≈$0.04            [停止]

    Mutation: drop the round, the elapsed or the cost and the expected string
    fails; swap elapsedWords for elapsedText and the Chinese reads wrong.
    """
    en, zh = _status(_RUNNING), _status(_RUNNING, "zh")
    assert "The auditor is reading · round 1 of 3 · 38s · ≈$0.04" in en, en
    assert "审计者正在阅读 · 第 1/3 轮 · 38 秒 · ≈$0.04" in zh, zh
    for html in (en, zh):
        assert html.count("<canvas") == 1 and html.count("stream-status") == 2
        assert "requestStop()" in html
    assert ">停止<" in zh and ">Stop<" in en


@needs_node
def test_there_is_no_status_line_when_nothing_runs():
    """Design: "When nothing runs it is not there." Not a line saying idle,
    not a still orb — nothing.

    Mutation: return the line for a finished run and this fails.
    """
    import copy

    finished = copy.deepcopy(_RUNNING)
    finished["progress"]["finished"] = True
    assert _status(finished) == ""
    parked = copy.deepcopy(_RUNNING)
    parked["progress"]["state"] = "WAITING_FOR_HUMAN"
    assert _status(parked) == ""
    assert _status({}) == ""


@needs_node
def test_the_status_line_never_shows_a_cost_it_could_not_price():
    """One number per row means the numbers that ARE shown are real. A run
    with unpriced calls and no value has no cost to state.

    Mutation: render `≈$0.00` and this fails.
    """
    import copy

    unpriced = copy.deepcopy(_RUNNING)
    unpriced["usage"]["attribution"]["runs"]["r1"] = {"api_value_usd": 0,
                                                      "unpriced_calls": 2}
    assert "≈$" not in _status(unpriced)


def test_the_composer_is_never_taken_away_by_the_stream():
    """Design rule 8. Nothing the stream renders disables the composer, and
    nothing it renders makes the shell inert.

    Mutation: disable `say` while a run is live and this fails.
    """
    from crossaudit.console.page import PAGE

    stream = PAGE[PAGE.index("// ============================================================== THE STREAM"):
                  PAGE.index("function turn(m,d){")]
    for forbidden in ("say.disabled", "send.disabled", "setDecidingInert",
                      "inert", "hub-mode", "deciding"):
        assert forbidden not in stream, forbidden
    # The one control the stream owns stops the WORK, never the typing.
    assert stream.count("requestStop()") == 1
