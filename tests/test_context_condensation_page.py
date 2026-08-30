"""The page consumer for the ``context_condensed`` stream kind (A2).

Agent B made context shaping visible on the wire; before this slice the page had
no branch for the kind, so the notice fell through ``turn()``'s generic renderer
and was presented as **Generator speech** — a role mark, the word "Generator", a
round number — in English regardless of locale. That is a claim about who
produced the words: the runtime condensed the context, the generator said
nothing.

**How these tests work, and why they were rewritten.** The first version of this
file asserted that certain strings appeared in ``PAGE``. An independent audit
rejected that, correctly: a source-string assertion proves what the file
*contains*, not what the page *renders* — the same defect class this project
filed against Agent B's own tests earlier the same day. So every behavioural
claim below is now **executed**: the real ``turn()`` and the real ``runCard()``
are pulled out of ``PAGE``, run under node against real wire-shaped payloads,
and their rendered HTML is parsed into a DOM and asserted structurally. Only
genuinely static data — a dictionary entry — is still checked as text, because a
dictionary *is* data rather than behaviour.

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
    zh_map = {TRACKED_EN: _zh_for(TRACKED_EN), UNTRACKED_EN: _zh_for(UNTRACKED_EN),
              "Context reduced": "上下文已精简", "round": "轮次"}
    program = "\n".join([
        _STUBS,
        f"const ZH = {json.dumps(zh_map, ensure_ascii=False)};",
        "const zhValue = v => ZH[v] || v;",
        "let currentLocale = 'en';",
        _extract_fn("const localeText = (bundle, base) =>") + ";",
        _extract_fn("const t = value =>") + ";",
        _extract_fn("function turn(m,d)"),
        _extract_fn("function runCard(d)"),
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
def test_the_notice_follows_a_locale_switch_in_both_directions():
    row = _stream_row(TRACKED_EN, TRACKED_PATHS, _zh_for(TRACKED_EN))
    rendered = _render([
        {"name": "en", "fn": "turn", "row": row, "locale": "en"},
        {"name": "zh", "fn": "turn", "row": row, "locale": "zh"},
        {"name": "back", "fn": "turn", "row": row, "locale": "en"},
    ])
    assert _Dom(rendered["en"]).text_of("turn-body") == TRACKED_EN
    assert _Dom(rendered["zh"]).text_of("turn-body") == _zh_for(TRACKED_EN)
    # Switching back restores English — no stale Chinese left behind.
    assert _Dom(rendered["back"]).text_of("turn-body") == TRACKED_EN
    assert "上下文已精简" in _Dom(rendered["zh"]).text_of("turn-meta")


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


# ------------------------------------------------------- static data only
def test_the_page_side_labels_have_chinese_parity():
    """A dictionary entry is data, so it is checked as data.

    The notice text itself is NOT duplicated here — it arrives pre-localised on
    the wire, which the render tests above exercise.
    """
    assert '"Context reduced":"上下文已精简","round":"轮次",' in PAGE
    assert re.search(r"try\{if\(lastState\)render\(lastState\);\}catch\(e\)\{\}\}",
                     PAGE), "a locale switch must re-render wire-localised rows"
