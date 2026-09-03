"""The page consumer for the ``context_condensed`` stream kind (A2).

Agent B made context shaping visible on the wire; before this slice the page had
no branch for the kind, so the notice fell through ``turn()``'s generic renderer
and was presented as **Generator speech** — a role mark, the word "Generator", a
round number — in English regardless of locale. That is a claim about who
produced the words: the runtime condensed the context, the generator said
nothing.

**How these tests work, and why they were rewritten twice.** The first version
asserted that strings appeared in ``PAGE``. An independent audit rejected that,
correctly: a source-string assertion proves what the file *contains*, not what
the page *renders*. The second version fixed most of it but repeated the defect
twice — it "verified" a locale switch with three independent renders that never
performed a switch, and kept one raw-source regex — and the audit rejected that
too. Both rejections were right, and the second is the more instructive: an
assertion that *looks* executed passes review unless someone tries to defeat it.

So, precisely, in this file:

* **No assertion reads ``PAGE`` as text.** ``PAGE`` is read as *data* — to
  extract the real renderers and the page's own ZH table — and every assertion
  is made against what executing those renderers produces.
* The locale test executes a real **transition**: one call to the real
  ``applyLocale``, with the DOM compared before and after. Three snapshots
  cannot prove a transition, which is exactly what the previous version got
  wrong.
* Rendered HTML is parsed into a DOM and asserted structurally, so a phrase
  split across child elements cannot hide from it.

Verified by attacking the tests rather than trusting them: deleting the
re-render line from ``applyLocale`` fails the transition test; deleting the ZH
label entries fails two tests; and all eleven fail against the pre-A2 page.

The three properties pinned:

1. It renders as system narration, not as a speaker turn.
2. Locale is selected from the wire fields the event carries
   (``text_i18n`` / ``detail_i18n`` / ``summary_i18n``), and follows a locale
   switch in both directions.
3. The two recovery cases stay distinct. After Agent B's S1-1 fix a tracked path
   and a working-tree-only path make *different* claims about ``file_read``;
   flattening them back into one reassuring sentence is the overclaim that fix
   removed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from crossaudit.console.page import PAGE

# ------------------------------------------------------------------ payloads
# Wire-shaped rows, exactly as console/streams.py and console/progress.py emit
# them (verified against a live /api/state during the slice's UX walkthrough).
TRACKED_EN = ("Tracked project files outlined; "
              "file_read can retrieve the committed version")
UNTRACKED_EN = ("Working-tree-only project files outlined; "
                "content is not available to file_read")
TRACKED_PATHS = "experiments/chapter_00.md, experiments/chapter_02.md"
UNTRACKED_PATHS = "experiments/draft_uncommitted.md"


def _zh_for(english: str) -> str:
    """The shipped Chinese for an upstream sentence, read from progress.py."""
    from crossaudit.console.progress import CONTEXT_CONDENSATION_ZH
    return CONTEXT_CONDENSATION_ZH[english]


def _page_zh_table() -> dict:
    """The page's own ZH dictionary, READ as data so it can be rendered with.

    Reading a table is not the same as asserting a string: nothing here claims
    an entry exists. The entries are fed to the real renderers, and the tests
    below assert what comes OUT. Delete an entry and zhValue falls through to
    English, so the rendered assertion fails — which is the behaviour we mean.
    """
    block = PAGE[PAGE.index("const ZH={"):PAGE.index("const ZH_PATTERNS=[")]
    pairs = re.findall(r'"((?:[^"\\]|\\.)*)":"((?:[^"\\]|\\.)*)"', block)
    unescape = lambda v: v.replace('\\"', '"').replace("\\'", "'")
    return {unescape(k): unescape(v) for k, v in pairs}


# ------------------------------------------------------------------ tiny DOM
class _Dom(HTMLParser):
    """Just enough DOM to ask structural questions about rendered HTML."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.nodes: list[dict] = []
        self._stack: list[dict] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        node = {"tag": tag,
                "classes": (attributes.get("class") or "").split(),
                "attrs": attributes, "text": ""}
        self.nodes.append(node)
        self._stack.append(node)

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        for node in self._stack:            # text belongs to every open ancestor
            node["text"] += data

    def by_class(self, name: str) -> list[dict]:
        return [n for n in self.nodes if name in n["classes"]]

    def one(self, name: str) -> dict:
        found = self.by_class(name)
        assert len(found) == 1, f"expected exactly one .{name}, got {len(found)}"
        return found[0]

    def text_of(self, name: str) -> str:
        return self.one(name)["text"].strip()


def _extract_fn(signature: str) -> str:
    """Extract one JS function/arrow from PAGE by brace counting."""
    start = PAGE.index(signature)
    depth, i = 0, PAGE.index("{", start)
    while i < len(PAGE):
        if PAGE[i] == "{":
            depth += 1
        elif PAGE[i] == "}":
            depth -= 1
            if depth == 0:
                return PAGE[start:i + 1]
        i += 1
    raise AssertionError(signature)


# ------------------------------------------------------------- the executor
_STUBS = """
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const at = () => '10:27';
const artifactList = () => '';
const auditStatus = () => 'passed';
const chatProgress = d => d.progress;
const chatCycles = () => [];
const statusOf = () => 'ready';
let handoffAt = 0, handoffDirection = '';
"""


def _render(cases: list[dict]) -> dict[str, str]:
    """Execute the REAL turn()/runCard() over real payloads; return rendered HTML."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute the page renderers")
    # The page's OWN table, plus the upstream sentences it does not carry.
    zh_map = dict(_page_zh_table())
    zh_map.setdefault(TRACKED_EN, _zh_for(TRACKED_EN))
    zh_map.setdefault(UNTRACKED_EN, _zh_for(UNTRACKED_EN))
    program = "\n".join([
        _STUBS,
        f"const ZH = {json.dumps(zh_map, ensure_ascii=False)};",
        "const zhValue = v => ZH[v] || v;",
        "let currentLocale = 'en';",
        _extract_fn("const localeText = (bundle, base) =>") + ";",
        _extract_fn("const t = value =>") + ";",
        _extract_fn("function turn(m,d)"),
        _extract_fn("function runCard(d)"),
        # Round 3: the run card reads elapsed time and event details in words.
        _extract_fn("function durationText(seconds)"),
        _extract_fn("function elapsedText(seconds)"),
        _extract_fn("function humaniseDetail(text)"),
        # Billing slice: runCard ends with its cost-line hook. Stubbed to
        # nothing here — this file is about the notice's attribution; the
        # hook's own rendering is pinned in test_billing.py.
        "const runCostLine = () => '';",
        # D150: the run card's activity rows moved into activityRow (with the
        # actor tables and the identifier scrub beside it), and the card reads
        # the live draft/thinking consumers, stubbed empty here. Mutation: put
        # the rows back inline in runCard and activityRow stops being shipped
        # code — this harness would then be extracting a dead function.
        _extract_fn("const ACTOR_NAMES") + ";",
        _extract_fn("const ACTOR_MARKS") + ";",
        _extract_fn("function conciseDetail(s)"),
        _extract_fn("function activityRow(s)"),
        # Review D7: the card now collapses a run of clock rows to its newest
        # before it takes the last twelve. Mutation: drop the call from runCard
        # and this extraction is of a function nothing ships.
        _extract_fn("const CLOCK_KINDS") + ";",
        _extract_fn("function collapseClockRows(steps)"),
        "const liveDraftFor = () => null; const liveThinkingFor = () => null;",
        "const draftCount = () => 0;",
        f"const CASES = {json.dumps(cases, ensure_ascii=False)};",
        """
const out = {};
for (const c of CASES) {
  currentLocale = c.locale || 'en';
  out[c.name] = c.fn === 'runCard' ? runCard(c.state) : turn(c.row, c.state || {});
}
console.log(JSON.stringify(out));
""",
    ])
    result = subprocess.run([node, "-e", program], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _stream_row(text: str, detail: str, locale_zh: str | None = None) -> dict:
    """A generator_stream row as console/streams.py builds it."""
    summary_en = f"{text}: {detail}"
    summary_zh = f"{locale_zh or text}: {detail}"
    return {"kind": "context_condensed", "t": 1788000000, "chat_id": "history",
            "round": 1, "summary": summary_en,
            "summary_i18n": {"en": summary_en, "zh": summary_zh},
            "notes": detail, "event_id": 7}


def _progress(steps: list[dict]) -> dict:
    return {"progress": {"steps": steps, "finished": True, "outcome": "passed",
                         "task": "write a review"},
            "pipeline": [{"state": "done", "label": "Generate"}],
            "cycles": [], "max_rounds": 3}


def _step(kind: str, actor: str, text: str, detail: str = "",
          zh_text: str = "", zh_detail: str = "") -> dict:
    step = {"kind": kind, "actor": actor, "text": text, "detail": detail,
            "t": 1788000000, "round_no": 1, "round_limit": 3, "event_id": 3}
    if zh_text:
        step["text_i18n"] = {"en": text, "zh": zh_text}
        step["detail_i18n"] = {"en": detail, "zh": zh_detail or detail}
    return step


# ---------------------------------------- 1. system narration, not speech
def test_turn_renders_the_notice_as_a_system_note_not_a_speaker_turn():
    html = _render([{"name": "tracked", "fn": "turn",
                     "row": _stream_row(TRACKED_EN, TRACKED_PATHS)}])["tracked"]
    dom = _Dom(html)

    article = dom.one("system-note")
    assert "turn" in article["classes"]
    # Attribution: no speaker avatar, and the model is not named.
    assert dom.by_class("role-mark") == [], "the notice must not wear a speaker avatar"
    assert "Generator" not in html, "the notice must not be attributed to the model"
    assert dom.by_class("system-mark"), "it carries the runtime mark instead"
    assert dom.text_of("turn-body") == TRACKED_EN


def test_turn_still_renders_an_ordinary_generator_row_as_the_generator():
    """The new branch must not have swallowed the normal path."""
    row = {"kind": "generator", "t": 1788000000, "round": 2,
           "summary": "wrote the review", "chat_id": "history"}
    dom = _Dom(_render([{"name": "gen", "fn": "turn", "row": row}])["gen"])

    marks = dom.by_class("role-mark")
    assert len(marks) == 1 and "generator" in marks[0]["classes"]
    assert dom.by_class("system-note") == []
    assert "Generator" in dom.text_of("turn-meta")


def test_run_card_does_not_attribute_the_notice_to_the_generator_either():
    steps = [
        _step("activity", "generator", "writing"),
        _step("context_condensed", "generator", TRACKED_EN, TRACKED_PATHS,
              _zh_for(TRACKED_EN), TRACKED_PATHS),
    ]
    dom = _Dom(_render([{"name": "card", "fn": "runCard",
                         "state": _progress(steps)}])["card"])

    rows = dom.by_class("audit-event")
    assert len(rows) == 2
    marks = [n["text"].strip() for n in dom.by_class("event-mark")]
    assert marks == ["G", "↻"], f"the notice must not carry the G mark: {marks}"
    # The ordinary activity row keeps the generator's name; the notice does not.
    lines = [n["text"] for n in dom.by_class("event-line")]
    assert "Generator" in lines[0]
    assert "Generator" not in lines[1]
    assert "Context reduced" in lines[1]
    assert TRACKED_EN in lines[1]


# ------------------------------------------- 2. locale comes off the wire
def test_a_locale_switch_re_renders_the_notice_rather_than_leaving_it_stale():
    """Executes the TRANSITION, not three independent renders.

    The bug this guards is real and was found by driving: wire-localised copy is
    chosen when a row is rendered, so the text-node translator cannot reach it,
    and without a re-render the body stays English after the locale changes.
    Three separate renders that each happen to be correct cannot prove a
    transition works — an earlier version of this test made exactly that mistake
    and the independent auditor rejected it.

    So: render once, call the real applyLocale ONCE, and assert the DOM produced
    by the page's own render path changed as a result of that single call.
    Delete the re-render line from applyLocale and this fails, because the
    recorded DOM never updates.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute the page renderers")
    row = _stream_row(TRACKED_EN, TRACKED_PATHS, _zh_for(TRACKED_EN))
    zh_map = dict(_page_zh_table())
    zh_map.setdefault(TRACKED_EN, _zh_for(TRACKED_EN))
    program = "\n".join([
        _STUBS,
        f"const ZH = {json.dumps(zh_map, ensure_ascii=False)};",
        "const zhValue = v => ZH[v] || v;",
        "let currentLocale = 'en';",
        # Enough DOM for the real applyLocale to run unmodified.
        """
const BUTTONS = {};
globalThis.document = {
  documentElement: {},
  body: {},
  getElementById: id => (BUTTONS[id] = BUTTONS[id] || {
    textContent:'', setAttribute(){}, title:'' }),
  cookie: '',
};
globalThis.localStorage = { setItem(){}, getItem(){ return null; } };
const LOCALE_KEY = 'k', LOCALE_COOKIE = 'c';
let localizeCalls = 0;
const localizeTree = () => { localizeCalls++; };
// The page's render path, reduced to the one row under test: whatever the
// current locale is when render() runs is what lands in the DOM.
let DOM = null;
let lastState = {row: null};
const render = state => { DOM = turn(state.row, {}); };
""",
        _extract_fn("const localeText = (bundle, base) =>") + ";",
        _extract_fn("const t = value =>") + ";",
        _extract_fn("function turn(m,d)"),
        _extract_fn("function applyLocale(locale,remember=true)"),
        f"lastState.row = {json.dumps(row, ensure_ascii=False)};",
        """
const seen = {};
render(lastState);                 // first paint, in English
seen.before = DOM;
applyLocale('zh');                 // ONE call: the transition under test
seen.afterSwitch = DOM;
applyLocale('en');                 // and back again
seen.afterSwitchBack = DOM;
seen.localizeCalls = localizeCalls;
console.log(JSON.stringify(seen));
""",
    ])
    result = subprocess.run([node, "-e", program], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout)

    before = _Dom(seen["before"]).text_of("turn-body")
    after = _Dom(seen["afterSwitch"]).text_of("turn-body")
    back = _Dom(seen["afterSwitchBack"]).text_of("turn-body")

    assert before == TRACKED_EN
    # The switch itself changed the DOM. This is the assertion the previous
    # version could not make, because it never performed a switch.
    assert after != before, "applyLocale must re-render; the body stayed stale"
    assert after == _zh_for(TRACKED_EN)
    assert back == TRACKED_EN, "switching back must restore English"
    # And the label the page supplies itself followed too, rendered not asserted.
    assert "上下文已精简" in _Dom(seen["afterSwitch"]).text_of("turn-meta")
    assert "Context reduced" in _Dom(seen["afterSwitchBack"]).text_of("turn-meta")
    assert seen["localizeCalls"] == 2, "the text-node translator still runs"


def test_run_card_localises_from_the_wire_fields_too():
    steps = [_step("context_condensed", "generator", TRACKED_EN, TRACKED_PATHS,
                   _zh_for(TRACKED_EN), TRACKED_PATHS)]
    rendered = _render([
        {"name": "en", "fn": "runCard", "state": _progress(steps), "locale": "en"},
        {"name": "zh", "fn": "runCard", "state": _progress(steps), "locale": "zh"},
    ])
    assert TRACKED_EN in _Dom(rendered["en"]).one("event-line")["text"]
    zh_line = _Dom(rendered["zh"]).one("event-line")["text"]
    assert _zh_for(TRACKED_EN) in zh_line
    assert TRACKED_EN not in zh_line, "English must not leak under 中文"


def test_a_row_without_wire_translations_falls_back_instead_of_blanking():
    """An older event, or one whose projection lacks i18n, must still render."""
    row = {"kind": "context_condensed", "t": 1788000000, "round": 1,
           "summary": f"{TRACKED_EN}: {TRACKED_PATHS}", "notes": TRACKED_PATHS}
    for locale in ("en", "zh"):
        dom = _Dom(_render([{"name": "f", "fn": "turn", "row": row,
                             "locale": locale}])["f"])
        assert dom.text_of("turn-body") == TRACKED_EN


# --------------------------------- 3. the two recovery cases stay distinct
def test_both_recovery_payloads_render_their_own_claim():
    rendered = _render([
        {"name": "tracked", "fn": "turn",
         "row": _stream_row(TRACKED_EN, TRACKED_PATHS, _zh_for(TRACKED_EN)),
         "locale": "zh"},
        {"name": "untracked", "fn": "turn",
         "row": _stream_row(UNTRACKED_EN, UNTRACKED_PATHS, _zh_for(UNTRACKED_EN)),
         "locale": "zh"},
    ])
    tracked = _Dom(rendered["tracked"]).text_of("turn-body")
    untracked = _Dom(rendered["untracked"]).text_of("turn-body")
    assert tracked == _zh_for(TRACKED_EN)
    assert untracked == _zh_for(UNTRACKED_EN)
    # The whole point of Agent B's S1-1 fix: these are NOT the same sentence,
    # and the page must not be able to collapse them into one.
    assert tracked != untracked
    assert "可读取" in tracked and "无法读取" in untracked


def test_the_page_relays_the_recovery_claim_and_never_authors_one():
    """Rendered output contains only the sentence the event carried.

    Executed rather than asserted: a payload with a deliberately fabricated
    sentence must render that sentence verbatim, proving the renderer has no
    copy of its own to substitute.
    """
    invented = "SENTINEL claim the page must not be able to invent"
    dom = _Dom(_render([{"name": "s", "fn": "turn",
                         "row": _stream_row(invented, "a/b.md")}])["s"])
    assert dom.text_of("turn-body") == invented
    assert "file_read" not in dom.text_of("turn-body")


def test_the_affected_paths_render_as_separate_chips():
    dom = _Dom(_render([{"name": "c", "fn": "turn",
                         "row": _stream_row(TRACKED_EN, TRACKED_PATHS)}])["c"])
    chips = [n["text"].strip() for n in dom.by_class("condense-path")]
    assert chips == ["experiments/chapter_00.md", "experiments/chapter_02.md"]


def test_a_localised_detail_degrades_to_one_sentence_rather_than_a_wrong_split():
    """A byte count is translated, so the "<sentence>: <detail>" split cannot
    fire; the row must render whole rather than mis-split."""
    row = {"kind": "context_condensed", "t": 1788000000, "round": 1,
           "summary": "Earlier owner guidance condensed: 24000 bytes",
           "summary_i18n": {"en": "Earlier owner guidance condensed: 24000 bytes",
                            "zh": "已精简较早的用户补充说明: 24000 字节"},
           "notes": "24000 bytes"}
    dom = _Dom(_render([{"name": "b", "fn": "turn", "row": row,
                         "locale": "zh"}])["b"])
    assert dom.text_of("turn-body") == "已精简较早的用户补充说明: 24000 字节"
    assert dom.by_class("condense-path") == []


# --------------------------------------------------- the page-supplied label
def test_the_page_supplied_label_renders_in_chinese_from_the_shipped_table():
    """The label the page adds itself, asserted as RENDERED output.

    "Context reduced" and "round" are page copy rather than event copy, so they
    go through the page ZH table. That table is read as data and fed to the real
    renderer; the assertion is on what comes out. Remove either entry and the
    renderer falls through to English here, so this fails.
    """
    row = _stream_row(TRACKED_EN, TRACKED_PATHS, _zh_for(TRACKED_EN))
    rendered = _render([{"name": "zh", "fn": "turn", "row": row, "locale": "zh"}])
    meta = _Dom(rendered["zh"]).text_of("turn-meta")
    assert "上下文已精简" in meta, "the page label must render in Chinese"
    assert "轮次 1" in meta, "the round word must render in Chinese"
    assert "Context reduced" not in meta and "round 1" not in meta
