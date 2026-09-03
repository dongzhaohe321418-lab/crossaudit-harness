"""The activity stream (docs/design/ACTIVITY_STREAM.md).

Every rendering test here loads the WHOLE shipped `page.py` script under node
and calls the real `renderConversation`. That is not a style choice. The first
version of this file drove sliced-out functions with the rest of the page
stubbed, and an independent review that loaded the script whole found the
owner's original complaints still painted on the screen while all twenty-seven
tests were green: a slice cannot see a second surface rendered further down
`renderConversation`, an action sealed inside a closed `<details>`, or where a
button leads three calls later. So the harness is
`tests/harness/render_page.py`, the stops come from the real
`record_build_escalation` -> `overview.escalations` projection
(`tests/harness/real_stops.py`), and the assertions are made on two
projections of the render:

* `html` — everything rendered.
* `first_paint` — what is on the SCREEN before anyone opens anything. An
  action that appears only in `html` is an action nobody is offered.

Design rules 1 and 8 are driven rather than grepped: every action the render
offers is clicked through the page's own delegated handler, and what became
modal is read off the shipped DOM.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from crossaudit.console import overview

HARNESS = Path(__file__).parent / "harness"
sys.path.insert(0, str(HARNESS))

import render_page  # noqa: E402  (the whole-page harness; see the docstring)

WORKTREE = Path(overview.__file__).parents[3]
needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

#: Declared in the page but not (yet) readable from an emitter. Each is here
#: with the reason it is declared, so an entry that stops meaning anything is
#: visible rather than merely tolerated.
DECLARED_AHEAD = {
    "answered": "console/progress.py PHASE_KINDS",
}


# ============================================================ the fixtures
def _state(*, escalations=(), steps=None, messages=None, cycles=(),
           auditor_stream=(), run_state="AUDITING", finished=False,
           outcome="", elapsed=38, usage=None, run_id="r1"):
    """A console snapshot shaped exactly as `/api/state` sends one."""
    progress = None
    if steps is not None:
        progress = {"run_id": run_id, "chat_id": "c1", "state": run_state,
                    "finished": finished, "outcome": outcome, "elapsed": elapsed,
                    "task": "Write the review.", "steps": steps, "queued": 0,
                    "started": 0, "updated": 0, "waiting_reason": None}
    return {
        "version": "4", "project": "lab/p", "title": "t", "folder": "f",
        "tier": {"tier": "local"}, "max_rounds": 3, "rules": 4, "metrics": [],
        "check_contracts": {}, "generator": "anthropic:claude-opus-4-8",
        "auditor": "openai_compat:gpt-5.6-terra",
        "generator_stream": list(messages if messages is not None else [_YOU]),
        "auditor_stream": list(auditor_stream), "cycles": list(cycles),
        "escalations": list(escalations), "chats": {"items": [{"id": "c1"}]},
        "usage": usage or {}, "pipeline": [], "progress": progress,
    }


_YOU = {"kind": "you", "t": 10, "chat_id": "c1",
        "utterance": "Write the cache-warming review."}
_USAGE = {"attribution": {"runs": {"r1": {"api_value_usd": 0.04,
                                          "unpriced_calls": 0}}, "turns": []}}


def _step(kind, actor, t, text="", detail="", round_no=1):
    return {"kind": kind, "actor": actor, "t": t, "text": text, "detail": detail,
            "round_no": round_no, "round_limit": 3, "event_id": t,
            "state": "GENERATING"}


def _project(steps):
    """Steps as the CONSOLE projects them — text_i18n, detail_i18n and all."""
    from crossaudit.console.progress import project_snapshot

    return project_snapshot({"steps": steps})["steps"]


CHECKS = [_step("check_finished", "auditor", 40 + i, f"{w} check passed")
          for i, w in enumerate(["Schema", "Units", "Convergence", "Provenance"])]
ROUND1 = [_step("round_started", "loop", 20, "round 1 of 3"),
          _step("generation_started", "generator", 22, "Asking the generator to write"),
          _step("generation_completed", "generator", 30, "wrote the review"),
          _step("audit_started", "auditor", 35, "The auditor is reading the commit")]


def _scenarios() -> dict:
    """The eight the spec's gate names, as console snapshots."""
    live = dict(usage=_USAGE)
    return {
        "1 clean pass": _state(steps=_project(
            ROUND1 + CHECKS + [_step("audit_passed", "auditor", 60, "PASS")]), **live),
        "2 needs changes then passes": _state(steps=_project(
            ROUND1 + CHECKS + [
                _step("audit_blocked", "auditor", 60, "BLOCKED"),
                _step("revision_requested", "generator", 62, "asked for a revision"),
                _step("round_started", "loop", 70, "round 2 of 3", round_no=2),
                _step("generation_completed", "generator", 80, "revised", round_no=2),
                _step("audit_passed", "auditor", 95, "PASS", round_no=2)]), **live),
        "3 provider empty completion recovered": _state(steps=_project([
            _step("round_started", "loop", 20, "round 1 of 3"),
            _step("generation_started", "generator", 22, "Asking the generator to write"),
            _step("provider_recovery", "generator", 24,
                  "Retrying the generator's provider · attempt 1"),
            _step("provider_recovery", "generator", 26,
                  "Retrying the generator's provider · attempt 2"),
            _step("generation_completed", "generator", 40, "wrote the review")]),
            run_state="GENERATING", elapsed=41, **live),
        "4 unreadable auditor reply repaired": _state(steps=_project(
            ROUND1 + [_step("audit_repair_retry", "auditor", 45,
                            "Asking the auditor to answer again", "1 attempt")]
            + CHECKS + [_step("audit_passed", "auditor", 70, "PASS")]), **live),
        "5 no science commit": _state(escalations=[_stop("no_science_commit")]),
        "6 an auditor concern": _state(escalations=[_stop("auditor_concern")]),
        "7 the rounds ran out": _state(escalations=[_stop("limit_reached")]),
        "8 a budget threshold": _state(steps=_project(
            ROUND1[:3] + [_step("budget_warning", "loop", 45,
                                "Today's token budget is 80% used")]),
            run_state="GENERATING", elapsed=62, **live),
    }


def _stop(name: str) -> dict:
    import real_stops

    return real_stops.cached_rows()[name]


#: The ten stops the design calls machine failures — the loop can retry them,
#: and rules 1 and 8 apply to every one.
RETRYABLE = ("provider", "budget", "invalid_reply", "no_science_commit",
             "nothing_audited", "generator_format", "no_progress",
             "bounds_exceeded", "repair_refused", "answered")
#: The four the design says are worth interrupting a person for.
JUDGEMENT = ("auditor_concern", "auditor_escalated", "escalation_locked",
             "limit_reached")


# ============================================================== the harness
_RENDERED: dict | None = None
_CLICKED: dict | None = None


def _all_states() -> dict:
    states = dict(_scenarios())
    for name in RETRYABLE + JUDGEMENT:
        states["stop:" + name] = _state(escalations=[_stop(name)])
    states["settled pass"] = _settled("PASSED", "PASS", [])
    states["settled needs changes"] = _settled("BLOCKED", "BLOCKED", [_FINDING])
    states["settled admitted"] = _settled("CONSUMED", "PASS", [])
    #: One chat carrying both a settled cycle and an unresolved decision — the
    #: shape the review called "actively confusing" while the settled half was
    #: a card contradicting the row above it.
    mixed = _settled("PASSED", "PASS", [])
    mixed["escalations"] = [_stop("auditor_concern")]
    states["settled and escalated"] = mixed
    return states


_FINDING = {"severity": "BLOCKER", "rule": "CA-TXT-001", "artifact": "work/review.md",
            "observation": "The cited speed-up is not in the paper."}


def _settled(status: str, verdict: str, findings: list) -> dict:
    """A finished cycle exactly as `/api/state` carries one: the generator's
    message, the auditor's report, the cycle row and the project's checks."""
    sha = "c" * 40
    state = _state(
        messages=[_YOU, {"kind": "generator", "t": 80, "chat_id": "c1", "round": 1,
                         "sha": sha, "summary": "Drafted the review.",
                         "files": ["work/review.md"]}],
        cycles=[{"id": "f" * 16, "sha": sha, "status": status, "round": 1,
                 "chat_id": "c1"}],
        auditor_stream=[{"kind": "auditor", "verdict": verdict, "sha": sha[:12],
                         "round": 1, "t": 90, "chat_id": "c1",
                         "findings": findings}])
    state["check_contracts"] = {
        "schema": {"description": "the results file parses", "state": "passed"},
        "units": {"description": "every quantity has a unit", "state": "passed"}}
    state["metrics"] = [{"label": "Audits", "value": 1}]
    return state


def rendered() -> dict:
    """Every state, rendered once through the whole shipped page, EN and ZH."""
    global _RENDERED
    if _RENDERED is None:
        _RENDERED = render_page.render(WORKTREE, _all_states())
    return _RENDERED


def clicked() -> dict:
    """Every state, plus what every action it offers does when clicked."""
    global _CLICKED
    if _CLICKED is None:
        _CLICKED = render_page.render_and_click(WORKTREE, _all_states())
    return _CLICKED


def _js(names: list[str]) -> dict:
    return render_page.globals_of(WORKTREE, names)


def _first(name: str, locale: str = "en") -> str:
    return rendered()[name][locale]["first_paint"]


def _html(name: str, locale: str = "en") -> str:
    return rendered()[name][locale]["html"]


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
        f"EVENT_SHAPES declares kinds nothing emits: {stale}.")
    wrong = {k: v for k, v in declared.items() if v not in shapes}
    assert not wrong, f"shapes outside the design's five: {wrong}"
    assert set(shapes) == {"say", "do", "wait", "outcome", "note"}


@needs_node
def test_every_declared_kind_has_words_in_both_languages():
    """Design rule 7 on the vocabulary. Mutation: drop the ``zh`` half of any
    EVENT_VERBS row and this fails naming the kind."""
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
    out = render_page.run(WORKTREE, "console.log(JSON.stringify(["
              "streamRow({shape:'card',line:'x'})===null,"
              "streamRow({shape:'',line:'x'})===null,"
              "streamRow({shape:'note',line:'x'})!==null]));")
    assert json.loads(out) == [True, True, True]


@needs_node
def test_one_number_per_row_and_never_a_zero():
    """Design rules 3 and 5 on the number itself: one unit, and a zero is not
    a count. Mutation: let rowNumber render a 0 and the third case fails."""
    body = """
const CASES=[{value:4,unit:'checks'},{value:1,unit:'file'},{value:0,unit:'files'},
  {value:412,unit:'words'},{value:2,unit:'retries'},{value:1,unit:'findings'},
  null,{value:3,unit:'nonsense'}];
const out={};
for(const locale of ['en','zh']){currentLocale=locale;out[locale]=CASES.map(rowNumber);}
console.log(JSON.stringify(out));
"""
    out = json.loads(render_page.run(WORKTREE, body))
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
    ctx = {"messages": [{"kind": "you", "t": 10, "utterance": "x"},
                        {"kind": "generator", "t": 40, "summary": "y", "round": 1}],
           "steps": [{"kind": "round_started", "t": 12, "actor": "loop", "round_no": 1},
                     {"kind": "generation_started", "t": 15, "actor": "generator",
                      "round_no": 1},
                     {"kind": "generation_completed", "t": 30, "actor": "generator",
                      "round_no": 1},
                     {"kind": "weather_changed", "t": 35, "actor": "loop"},
                     {"kind": "audit_passed", "t": 50, "actor": "auditor",
                      "round_no": 1}]}
    rows = json.loads(render_page.run(
        WORKTREE, f"currentLocale='en';const rows=streamRows({{}},{json.dumps(ctx)});"
        "console.log(JSON.stringify(rows.map(r=>[r.shape,r.kind,r.t])));"))
    assert [r[1] for r in rows] == ["you", "generation_started",
                                    "generation_completed", "generator",
                                    "audit_passed"]
    assert [r[0] for r in rows] == ["say", "wait", "do", "say", "outcome"]
    assert [r[2] for r in rows] == sorted(r[2] for r in rows)


# =============================================== 2. one renderer, five shapes
@needs_node
def test_a_live_line_and_its_finished_line_never_both_appear():
    """Design: a `wait` row is replaced by the `do` row that resolves it.

    Mutation: delete dropSettledWaits from streamList and "Drafting" survives
    beside "Drafted" — the same fact said twice.
    """
    paint = _first("1 clean pass")
    # `generation_started` narrates "writing"; `generation_completed` carries
    # the generator's own summary. Only the finished one is on the screen.
    assert "wrote the review" in paint, paint
    assert "Drafting" not in paint, paint


@needs_node
def test_a_provider_retry_stops_being_live_the_moment_anything_succeeds():
    """Waiting for a provider is the one phase nothing of its own finishes.

    Mutation: drop the provider clause from dropSettledWaits and "Retrying"
    stands underneath the draft it was waiting for.
    """
    paint = _first("3 provider empty completion recovered")
    assert "wrote the review" in paint, paint
    assert "Retrying" not in paint, paint


@needs_node
def test_repetition_collapses_to_one_row_with_a_count():
    """Design: three consecutive reads become one row with a count — four
    deterministic checks become ``自动检查通过 · 4 项``.

    Mutation: remove mergeRuns and four rows survive in the first paint.
    """
    en, zh = _first("1 clean pass"), _first("1 clean pass", "zh")
    assert "Automatic checks passed · 4 checks" in en, en
    assert "自动检查通过 · 4 项" in zh, zh
    assert en.count("check passed") <= 1, "the four members are the DETAIL"
    # And the members are there, one keystroke away.
    assert "Schema check passed" in _html("1 clean pass")


@needs_node
def test_a_finished_round_collapses_into_its_own_outcome_row():
    """Design: a round is a group, not a region; its number lives on the row.

    Mutation: drop groupRounds and round 1's rows stay expanded above round 2.
    """
    zh = _first("2 needs changes then passes", "zh")
    assert "需要修改 · 第 1 轮" in zh, zh
    assert zh.index("需要修改 · 第 1 轮") < zh.index("已通过审查"), zh
    # round 1's own rows are folded into it, not stacked above round 2.
    assert "自动检查通过" in _html("2 needs changes then passes", "zh")


@needs_node
def test_no_animation_appears_without_words_beside_it():
    """Design rule 2. Every canvas the conversation paints is labelled with
    the very sentence it sits beside.

    Mutation: pass '' as the orb label and UNLABELLED appears.
    """
    for name in _all_states():
        for locale in ("en", "zh"):
            paint = _first(name, locale)
            assert "[orb:UNLABELLED]" not in paint, (name, locale, paint)
            for label in re.findall(r"\[orb:([^\]]*)\]", paint):
                assert label.strip(), (name, locale)
                assert label in paint.replace(f"[orb:{label}]", ""), (
                    f"{name}/{locale}: the orb's words are not beside it")


@needs_node
def test_one_number_per_row_on_the_rendered_line():
    """Design rule 5, on the surface: no row's line carries two counts.

    Mutation: append a second number to rowText and this fails.
    """
    import html as html_mod

    for name in _all_states():
        for raw in re.findall(r'<span class="srow-verb">([^<]*)</span>',
                              _html(name)):
            line = html_mod.unescape(raw)
            assert len(re.findall(r"\d+", line)) <= 1, (name, line)


# ==================================================== 3. one status line
@needs_node
def test_the_status_line_is_the_design_line_in_both_languages():
    """The design writes the line out in full:

        [orb] 正在撰写 · 第 1/3 轮 · 38 秒 · ≈$0.04            [停止]

    Mutation: drop the round, the elapsed or the cost and this fails.
    """
    en = _first("1 clean pass")
    zh = _first("1 clean pass", "zh")
    assert "The auditor is reading · round 1 of 3 · 38s · ≈$0.04" in en, en
    assert "审计者正在阅读 · 第 1/3 轮 · 38 秒 · ≈$0.04" in zh, zh
    assert "Stop" in en and "停止" in zh


@needs_node
def test_there_is_no_status_line_when_nothing_runs():
    """Design: "When nothing runs it is not there." Not a line saying idle,
    not a still orb — nothing.

    Mutation: return the line for a finished run and this fails.
    """
    for name in ["stop:provider", "stop:auditor_concern", "settled pass"]:
        assert "[orb:" not in _first(name), name
        assert "stream-status" not in _html(name), name


# ============================================ 4. failure is not a decision
@needs_node
def test_a_machine_failure_is_a_note_and_a_judgment_call_is_an_outcome():
    """The distinction the design calls the point of the product.

    Mutation: move ``auditor_concern`` into FAILURE_NOTES and it renders as a
    quiet note with a retry button — a real dispute silently downgraded.
    """
    for name in RETRYABLE:
        html = _html("stop:" + name)
        assert "srow-note" in html, name
        assert "srow-outcome" not in html, name
    for name in JUDGEMENT:
        assert "srow-outcome" in _html("stop:" + name), name


@needs_node
def test_a_failures_one_action_is_on_the_screen_not_behind_a_disclosure():
    """The design says a note "offers the one action that would fix it". An
    offer a person must open the row to find is not an offer: the first paint
    of a provider outage was one grey line and a chevron.

    Mutation: put rowActionHtml back inside `srow-body` and every one of these
    disappears from the first paint.
    """
    expected = {
        "provider": ("Retry now", "重试"),
        "budget": ("Raise the limit & retry", "提高上限并重试"),
        "invalid_reply": ("Run the audit again", "重试审计"),
        "no_science_commit": ("I have committed it — try again", "我已提交，重试"),
    }
    for name, (en, zh) in expected.items():
        assert en in _first("stop:" + name), (name, _first("stop:" + name))
        assert zh in _first("stop:" + name, "zh"), (name, _first("stop:" + name, "zh"))
    # The three whose fix is a SENTENCE carry the box itself, open, on the row.
    for name in ("nothing_audited", "generator_format", "no_progress"):
        paint = _first("stop:" + name)
        assert "Revise and continue" in paint or "Run the audit again" in paint, paint
        assert "Stop this task" in paint, paint


@needs_node
def test_the_failure_notes_say_it_in_both_languages():
    """Design rule 7 on the copy this section adds."""
    tables = _js(["FAILURE_NOTES"])["FAILURE_NOTES"]
    for cause, note in tables.items():
        assert note["en"] and note["zh"] and note["en"] != note["zh"], cause
        if note.get("action"):
            assert note["action"]["en"] != note["action"]["zh"], cause
        if note.get("detail"):
            assert note["detail"]["en"] != note["detail"]["zh"], cause


@needs_node
def test_the_provider_note_counts_the_retries_it_actually_made():
    """"供应商无响应 · 已重试 2 次" — counted from the narration the page
    already holds, and absent when it is zero.

    Mutation: invent the count and the zero case shows a number.
    """
    steps = _project([
        _step("provider_recovery", "auditor", 1,
              "Retrying the auditor's provider · attempt 1"),
        _step("provider_recovery", "auditor", 2,
              "Retrying the auditor's provider · attempt 2")])
    busy = _state(escalations=[_stop("provider")], steps=steps,
                  run_state="WAITING_FOR_PROVIDER", finished=True)
    out = render_page.render(WORKTREE, {"busy": busy}, locales=("zh",))
    assert "供应商无响应 · 已重试 2 次" in out["busy"]["zh"]["first_paint"]
    assert "已重试" not in _first("stop:provider", "zh")


# ============================================== 5. decisions in the stream
@needs_node
def test_a_decision_expands_in_place_with_three_sentences_and_two_buttons():
    """Design: "its Outcome row expands in place: what happened, why, what the
    choices are, in three sentences and two buttons."

    Mutation: close the row by default and the sentences leave the screen.
    """
    paint = _first("stop:auditor_concern")
    assert "The auditor raised a concern" in paint
    assert "no deterministic check reproduces" in paint
    assert "Revise and continue" in paint and "Stop this task" in paint
    assert "Your guidance or reason" in paint, paint
    assert "data-decision-reason" in _html("stop:auditor_concern")


@needs_node
def test_the_decision_says_the_same_words_the_decision_centre_says():
    """The per-cause copy was reviewed and is good: it is MOVED, not
    rewritten. Both surfaces read `decisionSlots`, so they cannot drift.

    Mutation: retype any sentence in decisionDetail and it stops matching the
    slot the Decision Center renders.
    """
    from render_decision import render as render_slots

    row = _stop("auditor_concern")
    slots = render_slots(WORKTREE, {"concern": row})["concern"]
    for locale in ("en", "zh"):
        paint = _first("stop:auditor_concern", locale).replace("\n", " ")
        for slot in ("resolution-summary", "resolution-request",
                     "resolution-reopen-title"):
            words = slots[locale][slot]
            assert words, slot
            assert words in paint, (locale, slot, words)


# ========================= 6. the shell entrance takes itself away
# A browser defect no node harness can see, because none of them paint: the
# whole workspace loaded blank with a correct DOM and an empty console, and
# writing `thread.scrollTop` the value it already held made it appear. A
# `both` animation never stops applying once it finishes, so each of the four
# shell elements kept a compositing layer for the life of the page — and three
# of the four are filled by JavaScript AFTER boot.
SHELL_TARGETS = (".topbar", ".sidebar", ".thread", ".composer-wrap")


def test_the_shell_entrance_never_fills_forwards_onto_a_permanent_layer():
    """Mutation: put `both` back on any of the four rules and this fails."""
    from crossaudit.console.page import PAGE

    block = PAGE[PAGE.index("@media (prefers-reduced-motion:no-preference){"):]
    block = block[:block.index("@keyframes shell-in")]
    rules = re.findall(r"body\.booted (\S+)\{animation:([^}]+)\}", block)
    assert [r[0] for r in rules] == list(SHELL_TARGETS), rules
    for target, value in rules:
        assert "backwards" in value, (target, value)
        for forbidden in (" both", "forwards"):
            assert forbidden not in value, (target, value, forbidden)


@needs_node
def test_the_shell_entrance_runs_once_and_removes_its_own_class():
    """The SHIPPED `enterShell` driven under node over a fake clock.

    Mutation: drop the `setTimeout(... remove ...)` and the class is still on
    the body at the end; make the class the latch and the second call replays
    the animation.
    """
    body = """
const log=[];const cls=document.body.classList;
let frame=null,timer=null;
globalThis.requestAnimationFrame=fn=>{frame=fn;};
globalThis.setTimeout=(fn,ms)=>{timer=[fn,ms];};
cls.remove('booted');
shellEntered=false;
enterShell();
const beforeFrame=cls.contains('booted');
frame();
const afterFrame=cls.contains('booted');
const delay=timer[1];
enterShell();
const afterSecond=cls.contains('booted');
timer[0]();
console.log(JSON.stringify({beforeFrame,afterFrame,afterSecond,
  end:cls.contains('booted'),delay}));
"""
    got = json.loads(render_page.run(WORKTREE, body))
    assert got["beforeFrame"] is False, "nothing before the next frame"
    assert got["afterFrame"] is True
    assert got["afterSecond"] is True, "a snapshot must not replay it"
    assert got["end"] is False, "the class does not outlive the entrance"
    assert got["delay"] >= 700


# ======================== 7. two things a browser saw that node did not
@needs_node
def test_a_row_with_no_number_carries_no_separator_and_no_stray_mark():
    """Reported from the browser as `· 供应商无响应` — a leading middot with an
    empty number slot. It was the runtime's actor MARK.

    Mutation: give `system` a middot again and this fails.
    """
    assert _js(["ROW_MARKS"])["ROW_MARKS"]["system"] == ""
    assert _js(["ROW_KIND_MARKS"])["ROW_KIND_MARKS"] == {"context_condensed": "↻"}
    line = _first("stop:provider", "zh").split("\n")
    assert any(l.strip() == "供应商无响应" for l in line), line


def test_no_second_band_describes_a_stop_the_stream_already_described():
    """Reported from the browser: under the provider note, the
    `delivery-status` band read the sentence the owner complained about, with
    a button into the Decision Center.

    Mutation: render deliveryStatus again and the first assertion fails.
    """
    from crossaudit.console.page import PAGE

    assert "function deliveryStatus" not in PAGE
    assert "delivery-status" not in PAGE and "delivery-dot" not in PAGE
    assert "CrossAudit needs a decision before it can continue." not in PAGE


@needs_node
def test_a_run_that_simply_stopped_still_says_so_once():
    """The one thing only the deleted band said.

    Mutation: drop `stoppedRow` from `streamStops` and a failed run with no
    cycle and no decision says nothing at all.
    """
    states = {
        "failed": _state(steps=[], run_state="FAILED", finished=True,
                         outcome="failed"),
        "passed": _state(steps=[], run_state="PASSED", finished=True,
                         outcome="passed"),
    }
    out = render_page.render(WORKTREE, states)
    assert "The task stopped without completing" in out["failed"]["en"]["first_paint"]
    assert "任务已停止，没有完成" in out["failed"]["zh"]["first_paint"]
    assert "stopped" not in out["passed"]["en"]["first_paint"].lower()


@needs_node
def test_the_emitters_own_sentence_is_never_traded_for_a_generic_verb():
    """The verb table is a FALLBACK for a kind that carries no sentence, never
    an override. "Today's token budget is 80% used" became "Usage threshold
    reached" — the same row with the number, the threshold and the reason
    removed.

    Mutation: put `wireLine(s)||verbOf(kind)` back and both assertions fail.
    """
    assert "Today's token budget is 80% used" in _first("8 a budget threshold")
    assert "今日 token 预算已用 80%" in _first("8 a budget threshold", "zh")
    assert "Usage threshold reached" not in _first("8 a budget threshold")


# ================================ 8. the eight rules, driven not grepped
_ASCII_SENTENCE = re.compile(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}")
#: Fields whose value a PERSON or a MODEL authored. Those are never translated
#: — not because they look English, but because of where they came from: the
#: user typed it, the generator summarised with it, the auditor observed it.
#: Exemption by identity is the whole discipline; a predicate that exempted
#: "text that looks like prose" would exempt the leak too.
_AUTHORED_FIELDS = ("utterance", "summary", "observation", "task")


def _authored(node, out: set) -> set:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _AUTHORED_FIELDS and isinstance(value, str):
                out.add(value)
            elif key == "text" and node.get("kind") == "generation_completed":
                out.add(str(value))       # the generator's own summary
            else:
                _authored(value, out)
    elif isinstance(node, list):
        for item in node:
            _authored(item, out)
    return out


@needs_node
def test_no_english_sentence_is_painted_into_a_chinese_screen():
    """Design rule 7 where it actually bites: the PAINTED text, not two
    tables. `1 attempt` and `build round budget spent (3)` both reached a
    Chinese reader in English while three ZH tests were green.

    Walks every line of every first paint in ZH. A line that is a person's or
    a model's own words is exempt by identity, never by looking English.

    Mutation: drop the `t()` from rowFromStep's detail, or remove the
    `build round budget spent ({})` entry from denials_zh, and this fails
    naming the line.
    """
    states = _all_states()
    authored = _authored(states, set())
    assert authored, "the fixture carries no person- or model-authored text"
    leaks = []
    for name in states:
        for line in rendered()[name]["zh"]["first_paint"].split("\n"):
            body = line.strip()
            if not body:
                continue
            for words in authored:
                body = body.replace(words, "")
            body = re.sub(r"\[orb:[^\]]*\]|\[textarea\]|\[button\]", "", body)
            body = re.sub(r"\b[\w./-]+\.(md|py|json|yml)\b", "", body)
            if _ASCII_SENTENCE.search(body):
                leaks.append((name, line.strip()))
    assert not leaks, f"English painted into a Chinese screen: {leaks}"


@needs_node
def test_no_retryable_failure_can_reach_a_modal_or_make_the_shell_inert():
    """Design rule 1, driven. Every action the render offers is clicked
    through the page's OWN delegated handler, and what became modal is read
    off the shipped DOM.

    A substring blacklist over a source slice let two mutations through: a
    button whose attribute leads, three calls later, to `openResolution` ->
    `aria-modal` + `inert` on the shell that holds the composer is invisible
    to a grep and obvious to a click.

    Mutation: give any of the ten `act:'guidance'` or `act:'settings'` with a
    `data-open-decisions` / `data-open-runtime` attribute and this fails.
    """
    allowed = {"type", "class", "data-stream-retry", "data-stream-post",
               "data-stream-reason", "data-decide", "data-decide-cycle"}
    for name in RETRYABLE:
        got = clicked()["stop:" + name]
        html = got["html"]
        for forbidden in ("aria-modal", "role=\"dialog\"", "role=\"alertdialog\"",
                          "<dialog", " inert", "project-modal"):
            assert forbidden not in html, (name, forbidden)
        assert got["before"]["shell_inert"] is False, name
        assert got["before"]["modals_on"] == [], name
        for click in got["clicks"]:
            extra = set(click["attrs"]) - allowed
            assert not extra, (
                f"{name}: an action carries {sorted(extra)}, which is how a "
                "retryable failure used to reach the Decision Center")
            assert click["shell"]["modals_on"] == [], (name, click["attrs"])
            assert click["shell"]["shell_inert"] is False, (name, click["attrs"])
            assert click["shell"]["body_deciding"] is False, (name, click["attrs"])


@needs_node
def test_the_composer_is_never_taken_away_in_any_rendered_state():
    """Design rule 8, driven. The composer's own `disabled` and `inert` are
    read off the shipped DOM after every render AND after every click.

    Mutation: `document.getElementById('say').disabled=true` anywhere in the
    render path — a spelling no blacklist contains — reddens this.
    """
    for name, got in clicked().items():
        for where, shell in [("render", got["before"])] + [
                ("click " + json.dumps(c["attrs"]), c["shell"]) for c in got["clicks"]]:
            assert shell["say_disabled"] is False, (name, where)
            assert shell["send_disabled"] is False, (name, where)
            assert shell["composer_inert"] is False, (name, where)
            assert shell["shell_inert"] is False, (name, where)


@needs_node
def test_no_identifier_reaches_a_first_paint():
    """Design rule 4, over every painted line of every state, both languages.

    Mutation: drop a scrub from conciseDetail and a sha appears.
    """
    forbidden = re.compile(
        r"\b[a-f0-9]{12,}\b|CA-[A-Z]+-\d|[A-Za-z0-9_.-]+:(?:claude|gpt|gemini|deepseek)"
        r"|\b(PASS|BLOCKED|ESCALATE|ESCALATED|DCL_ONLY)\b")
    for name in _all_states():
        for locale in ("en", "zh"):
            paint = _first(name, locale)
            hit = forbidden.search(paint)
            assert hit is None, (name, locale, hit.group(0), paint)



# =============================== 9. a settled cycle is rows, not a card
@needs_node
def test_a_settled_cycle_is_its_rounds_outcome_row_and_not_a_card():
    """The last deviation from the design, closed.

    A settled cycle used to render `<section class="review-card">` under the
    stream: its own heading, its own verdict pill, its own round counter and
    twenty lines of sections. An ESCALATED cycle was already a row, so one
    surface read as two designs.

    It is the round's outcome row now — the verdict in plain words, the round
    number on the line, one action — and everything the card stacked is the
    detail that opens in place.

    Mutation: render a card again from `renderConversation` and the first two
    assertions fail; drop `cycleRows` from `streamContext` and the verdict
    leaves the conversation.
    """
    from crossaudit.console.page import PAGE

    assert "function reviewCard" not in PAGE
    assert "review-card" not in PAGE and "data-review-toggle" not in PAGE
    for name, en, zh in (("settled pass", "Passed review", "已通过审查"),
                         ("settled needs changes", "Needs changes", "需要修改"),
                         ("settled admitted", "Admitted", "已准入")):
        assert "review-card" not in _html(name), name
        assert f"{en} · round 1" in _first(name), (name, _first(name))
        assert f"{zh} · 第 1 轮" in _first(name, "zh"), (name, _first(name, "zh"))
        assert "srow-outcome" in _html(name), name


@needs_node
def test_a_finished_round_is_one_line_and_everything_else_opens_in_place():
    """"A finished round folds to one row and expands in place." What the card
    stacked — the deterministic checks, the auditor's findings, the report's
    provenance and the technical record — is behind that one row's fold, and
    the files it produced are already the chips on the generator's own row.

    Mutation: open the fold by default and the whole card is back, one shape
    later; drop a sub-row and the thing it carried is unreachable.
    """
    paint = _first("settled needs changes")
    html = _html("settled needs changes")
    # ONE line for the round, plus the rows that were already there.
    assert paint.count("Needs changes") == 1, paint
    for hidden in ("Automatic checks", "What the auditor raised", "Details",
                   "The cited speed-up is not in the paper.", "CA-TXT-001",
                   "c" * 12, "f" * 16):
        assert hidden in html, hidden
        assert hidden not in paint, (hidden, paint)
    # The files are rows already: the chips on the generator's say row, which
    # is where a passing cycle's deliverable has always been.
    assert "work/review.md" in _first("settled pass"), _first("settled pass")
    # Nothing the card said twice survives.
    for gone in ("Independent review", "Independent auditor approved the result",
                 "No blocking findings", "Recorded in the audit ledger",
                 "No checks configured", "View audit details"):
        assert gone not in html, gone


@needs_node
def test_one_verdict_has_one_vocabulary_and_one_round_counter():
    """D8. The stream row said `已通过审查` and the card said `通过复核` six lines
    apart, about the same verdict; the card carried `第 2/3 轮` while the status
    line carried `round 2 of 3`.

    Mutation: put `"Passed review":"通过复核"` back in the catalogue and a
    Chinese reader gets two phrases for one fact again.
    """
    zh = _html("settled pass", "zh")
    assert "已通过审查" in zh and "通过复核" not in zh, zh
    # Mechanically: every verdict word the page can paint has ONE Chinese, and
    # it is the one the row says. The catalogue is the second speaker — it is
    # what the locale observer reaches for when an English row is already on
    # the screen — so it must agree with the row rather than merely be unused.
    tables = _js(["EVENT_VERBS", "CYCLE_VERDICTS", "ZH"])
    catalogue = tables["ZH"]
    spoken = [tables["EVENT_VERBS"][k] for k in
              ("audit_passed", "audit_blocked", "audit_escalated")]
    spoken += list(tables["CYCLE_VERDICTS"].values())
    for words in spoken:
        assert catalogue.get(words["en"], words["zh"]) == words["zh"], (
            f"{words['en']!r} is {words['zh']!r} on the row and "
            f"{catalogue.get(words['en'])!r} in the catalogue: one verdict, "
            "two vocabularies")
    for name in _all_states():
        for locale in ("en", "zh"):
            html = _html(name, locale)
            assert "通过复核" not in html, (name, locale)
            # The card's own counter — `Round 1/3` beside the status line's
            # `round 1 of 3` — has no second speaker any more.
            assert "Round 1/3" not in html, (name, locale)
            # `第 1/3 轮` / `round 1 of 3` belongs to the status line and to
            # nothing else: the card's counter had no chronology to place it.
            rest = re.sub(r'<div class="stream-status".*?</div>\s*$', "", html,
                          flags=re.S)
            assert "第 1/3 轮" not in rest and "round 1 of 3" not in rest, (
                name, locale, rest)


@needs_node
def test_a_chat_holding_both_a_settled_cycle_and_a_decision_reads_in_order():
    """The review rendered one chat carrying both and called it "actively
    confusing": the card asserted `Passed review` and `Round 3/3` directly
    under a row saying the auditor had raised a concern about round 2, with no
    chronology to say which was current.

    Both are rows of one list now: the settled verdict sorts at the time of the
    report that decided it, and the unresolved decision — which is where the
    conversation IS — stands last.

    Mutation: append the settled cycle after the stops and the decision stops
    being the last thing on the screen.
    """
    paint = _first("settled and escalated")
    assert "Passed review · round 1" in paint, paint
    assert "The auditor raised a concern" in paint, paint
    assert paint.index("Passed review") < paint.index("The auditor raised a concern")
    assert "review-card" not in _html("settled and escalated")


@needs_node
def test_the_status_line_does_not_carry_a_fourth_figure():
    """D10. `审计者正在阅读 · 1 个文件 · 第 1/3 轮 · 38 秒 · ≈$0.04` — the file
    count is a number the design's status line does not have, it never moves
    while you watch it, and the files it counts are already chips on the
    generator's row. The number that belongs beside the verb is the one that is
    accumulating: the words of the draft.

    Mutation: pass `files:` to phaseCount again and the fourth figure is back.
    """
    from crossaudit.console.page import PAGE

    assert "liveFileCount" not in PAGE
    states = {"auditing": _state(
        messages=[_YOU, {"kind": "generator", "t": 80, "chat_id": "c1", "round": 1,
                         "sha": "c" * 40, "summary": "Drafted.",
                         "files": ["work/review.md", "work/notes.md"]}],
        steps=_project(ROUND1), usage=_USAGE)}
    out = render_page.render(WORKTREE, states)
    en = out["auditing"]["en"]["first_paint"]
    zh = out["auditing"]["zh"]["first_paint"]
    assert "The auditor is reading · round 1 of 3" in en, en
    assert "审计者正在阅读 · 第 1/3 轮" in zh, zh
    assert "2 files" not in en and "2 个文件" not in zh
    # ...and the accumulating number is still there where it accumulates.
    drafting = render_page.render(
        WORKTREE, {"drafting": _state(steps=_project(ROUND1[:2]),
                                      run_state="GENERATING", usage=_USAGE)},
        opts={"drafting": {"liveDraft": {"run": "r1", "text": "one two three four"}}})
    assert "4 words so far" in drafting["drafting"]["en"]["first_paint"], drafting
    assert "已写 4 字" in drafting["drafting"]["zh"]["first_paint"]


@needs_node
def test_rows_that_arrive_after_their_rounds_outcome_fold_into_it_in_order():
    """F3. A provider retry narrated late, a budget threshold crossed while the
    verdict was being written, a clock tick behind the outcome that ended the
    round: a single-pass fold dropped every one of them on the floor, because
    the round was already closed by the time they were read.

    They belong to that round, so they fold into its outcome row — and in the
    order they happened, not the order the fold noticed them.

    Mutation: collect `held` in the same pass that emits, and the three late
    rows vanish from the conversation entirely.
    """
    late = _state(steps=_project(ROUND1 + [
        _step("audit_blocked", "auditor", 60, "BLOCKED"),
        _step("budget_warning", "loop", 61, "Today's token budget is 80% used"),
        _step("revision_unchanged", "generator", 62, "The revision changed nothing"),
        _step("provider_recovery", "generator", 63,
              "Retrying the generator's provider · attempt 1"),
        _step("round_started", "loop", 70, "round 2 of 3", round_no=2),
        _step("generation_completed", "generator", 80, "revised", round_no=2)]),
        usage=_USAGE)
    out = render_page.render(WORKTREE, {"late": late})
    paint = out["late"]["en"]["first_paint"]
    text = out["late"]["en"]["text"]
    # Round 1 is one line, and round 2 is open above the status line.
    assert "Needs changes · round 1" in paint, paint
    assert "Today's token budget" not in paint, paint
    # Every late row is inside that round's fold...
    for late_line in ("Today's token budget is 80% used",
                      "The revision changed nothing",
                      "Retrying the generator's provider"):
        assert late_line in text, (late_line, text)
    # ...in the order they happened, behind the row that closed the round.
    order = [text.index("wrote the review"),
             text.index("Today's token budget is 80% used"),
             text.index("The revision changed nothing"),
             text.index("Retrying the generator's provider")]
    assert order == sorted(order), (order, text)
    assert text.index("Needs changes · round 1") < order[0], text

# ================================================= the engine, unchanged
GOOD_INCREMENT = {
    "experiments/demo/metadata.yml":
        "code_version: a1b2c3d\ninputs:\n  - scripts/run_demo.py@a1b2c3d\n",
    "experiments/demo/results.json": json.dumps({
        "quantities": [
            {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
             "source": "scripts/run_demo.py@a1b2c3d"},
            {"name": "distance", "value": 2.73, "unit": "angstrom",
             "source": "scripts/run_demo.py@a1b2c3d"},
        ],
        "convergence": {"converged": True, "achieved": 7.4e-07, "threshold": 1e-06},
    }, indent=1),
    "experiments/demo/SUMMARY.md": "attempt one\n",
}
PASS_REPLY = {"verdict": "PASS",
              "sections_applied": ["CA-DATA-001", "CA-METH-002"], "findings": []}


def _loop_with_auditor_replies(cfg, science, monkeypatch, replies: list[str]):
    """Run the real loop with the auditor answering `replies` in order."""
    from crossaudit import generator as generator_mod
    from crossaudit.auditor import run as audit_run
    from crossaudit.cli import build as build_mod
    from crossaudit.config import load
    from crossaudit.providers.base import Reply, sha256_text

    asked: list[str] = []
    events = []

    def complete_factory(_cfg, _allow_custom, on_event=None, _heartbeat=None, **_kw):
        def complete(*, system, prompt):
            return Reply("ok", "id", "a" * 64, "b" * 64)
        return complete

    def fake_generate(**kwargs):
        kwargs["complete"](system="s", prompt="p")
        return generator_mod.Work(summary="attempt", files=GOOD_INCREMENT)

    def auditor_complete(_cfg, _role, _primary, *, system, prompt, **_kw):
        asked.append(prompt)
        text = replies[min(len(asked) - 1, len(replies) - 1)]
        return Reply(text, "audit-id", sha256_text(system + "\n" + prompt),
                     sha256_text(text), raw={})

    monkeypatch.setattr(build_mod, "_generator_complete", complete_factory)
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.setattr(audit_run.provider_resilience, "complete", auditor_complete)
    monkeypatch.chdir(science)
    cfg.path.write_text(cfg.path.read_text(encoding="utf-8")
                        + "scope:\n  dirs: [experiments]\n", encoding="utf-8")
    code = build_mod.run_loop(load(cfg.path), "produce the experiment",
                              on_event=events.append)
    return code, asked, events


def test_an_empty_auditor_reply_is_repaired_once_before_it_becomes_a_stop(
        cfg, science, monkeypatch):
    """4a. ONE bounded repair attempt goes back to the same route with the
    validator's own reason appended. It is additive: it adds an attempt in
    FRONT of an existing failure path and moves no verdict mapping.

    Mutation: delete the repair branch and the round escalates on
    INVALID_REPLY instead of passing.
    """
    code, asked, events = _loop_with_auditor_replies(
        cfg, science, monkeypatch, ["", json.dumps(PASS_REPLY)])

    assert code == 0, [(e.kind, e.text) for e in events][-4:]
    assert len(asked) == 2, "the auditor is asked exactly twice"
    assert "Your previous reply was rejected" in asked[1]
    assert "in the required shape" in asked[1]
    for word in ("PASS", "BLOCKED", "ESCALATE"):
        assert word not in asked[1].split("Your previous reply was rejected")[1]
    retries = [e for e in events if e.kind == "audit_repair_retry"]
    assert len(retries) == 1 and retries[0].detail == "1 attempt"
    assert retries[0].text == "Asking the auditor to answer again"


def test_the_repair_is_capped_at_one_and_changes_no_verdict_mapping(
        cfg, science, monkeypatch):
    """The cap is one attempt per round, and a reply that is still unreadable
    is still unreadable: the ladder is untouched.

    Mutation: loop the repair and the ask count grows past two per round.
    """
    from crossaudit.errors import escalation_cause

    code, asked, events = _loop_with_auditor_replies(
        cfg, science, monkeypatch, ["", "still not json"])

    assert code != 0
    rounds = len([e for e in events if e.kind == "round_started"])
    assert len(asked) == 2 * rounds, "two auditor turns per round, never three"
    assert len([e for e in events if e.kind == "audit_repair_retry"]) == rounds
    assert escalation_cause(integrity="INVALID_REPLY",
                            verdict="ESCALATE") == "invalid_reply"


def test_a_setup_mistake_reaches_the_console_as_its_own_cause(cfg):
    """4b. The no-science-commit refusal arrives as its own cause rather than
    a generic escalation, so the console routes it to a note with a retry.

    Mutation: drop ``cause=NO_SCIENCE_COMMIT_CAUSE`` from cmd_run and the
    console sees a causeless stop, which `isDecisionStop` treats as a
    judgment call — the exact confusion this exists to end.
    """
    from crossaudit.controller import StateStore
    from crossaudit.errors import NO_SCIENCE_COMMIT_CAUSE

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    row = store.record_build_escalation(
        cfg.science_repo, "e" * 40, "that commit had no experiment in it", 1,
        kind="audit", cause=NO_SCIENCE_COMMIT_CAUSE)
    assert row["escalation_cause"] == NO_SCIENCE_COMMIT_CAUSE


def test_the_receipt_shows_the_repair_and_both_digests_name_the_same_turn(
        cfg, science, monkeypatch):
    """The repair was invisible in the receipt, and `inputs.prompt_sha256`
    named the REJECTED prompt while `exchange.request_sha256` named the one
    that answered — so every model-tier evidence record was stamped with the
    digest of a prompt the auditor never answered.

    Mutation: drop the `repair_attempts` block in auditor/run.py and the
    digests disagree again.
    """
    import hashlib

    from crossaudit.auditor import prompt as prompt_mod
    from crossaudit.auditor import run as audit_run

    from crossaudit.cli import main as main_mod

    seen = {}
    real_run = audit_run.run_audit

    def capture(*a, **kw):
        out = real_run(*a, **kw)
        seen["outcome"] = out
        return out

    monkeypatch.setattr(main_mod, "run_audit", capture)
    _code, asked, _events = _loop_with_auditor_replies(
        cfg, science, monkeypatch, ["", json.dumps(PASS_REPLY)])

    outcome = seen["outcome"]
    assert outcome.exchange["repair_attempts"] == 1
    assert outcome.exchange["rejected_prompt_sha256"] != outcome.prompt_sha256
    # `prompt_sha256` names the prompt that produced the reply that was read.
    assert outcome.prompt_sha256 == hashlib.sha256(
        asked[1].encode("utf-8")).hexdigest()
    assert outcome.exchange["rejected_prompt_sha256"] == hashlib.sha256(
        asked[0].encode("utf-8")).hexdigest()
    assert prompt_mod.REPAIR_HEADER.split("{")[0] in asked[1]


def test_a_repair_that_never_reached_a_provider_is_not_narrated(
        cfg, science, monkeypatch):
    """The attempt used to be announced before it was placed, so a denial left
    the run record claiming an attempt that never happened.

    Mutation: move the narrate() back above ask() and this fails.
    """
    from crossaudit.auditor import run as audit_run
    from crossaudit.errors import ProviderDenial

    calls = {"n": 0}
    real = audit_run.provider_resilience.complete

    def deny_second(*a, **kw):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise ProviderDenial("no recorded reply for this prompt",
                                 detail={"category": "transcript"})
        return real(*a, **kw)

    code, _asked, events = _loop_with_auditor_replies(
        cfg, science, monkeypatch, [""])
    # Re-run with the repair denied: the first turn answers, the second raises.
    monkeypatch.setattr(audit_run.provider_resilience, "complete", deny_second)
    code2, _a2, events2 = _loop_with_auditor_replies(
        cfg, science, monkeypatch, [""])
    assert code != 0 and code2 != 0
    assert [e for e in events if e.kind == "audit_repair_retry"], (
        "the placed attempt is still narrated")
    assert not [e for e in events2 if e.kind == "audit_repair_retry"], (
        "a repair that never reached a provider must not be narrated")
