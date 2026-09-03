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
