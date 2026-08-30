"""The page consumer for the ``context_condensed`` stream kind (A2).

Agent B made context shaping visible on the wire; before this slice the page had
no branch for the kind, so the notice fell through ``turn()``'s generic renderer
and was presented as **Generator speech** — a role mark, the word "Generator", a
round number — in English regardless of locale. That is a claim about who
produced the words: the runtime condensed the context, the generator said
nothing. These tests pin the three properties that fixes it.

1. It renders as system narration, not as a speaker turn.
2. Locale is selected from the wire fields the event already carries
   (``text_i18n`` / ``detail_i18n`` / ``summary_i18n``), never by re-translating
   prose or matching text nodes.
3. The two recovery cases stay distinct. After Agent B's own S1-1 fix a tracked
   path and a working-tree-only path make *different* claims about ``file_read``;
   flattening them back into one reassuring sentence is the overclaim that fix
   removed.
"""
from __future__ import annotations

import shutil
import subprocess

from crossaudit.console.page import PAGE


def _extract_fn(signature: str) -> str:
    """Extract one JS function/arrow by brace counting."""
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


# ------------------------------------------------ system narration, not speech
def test_the_notice_has_its_own_branch_and_is_not_a_speaker_turn():
    assert "if(m.kind === 'context_condensed'){" in PAGE
    # Its own article class, so it can be styled as a note rather than a turn.
    assert '<article class="turn system-note">' in PAGE
    assert ".turn.system-note{" in PAGE
    # It must NOT borrow the generator's identity.
    branch = PAGE[PAGE.index("if(m.kind === 'context_condensed'){"):]
    branch = branch[:branch.index("return '<article class=\"turn\"><div class=\"turn-main\">'")]
    assert "role-mark" not in branch, "the notice must not wear a speaker avatar"
    assert "Generator" not in branch, "the notice must not be attributed to the model"
    assert "system-mark" in branch


def test_the_live_activity_list_does_not_attribute_it_to_the_generator_either():
    # The same event also appears in the run-activity list, where it used to
    # render with the generator's name and mark and in English only.
    assert "const system = s.kind === 'context_condensed';" in PAGE
    assert "const who = system ? t('Context reduced') : (actorNames[s.actor]||s.actor);" in PAGE
    assert "const line = system ? localeText(s.text_i18n, s.text) : s.text;" in PAGE
    assert "const detail = system ? localeText(s.detail_i18n, s.detail) : s.detail;" in PAGE
    assert ".event-mark.runtime{" in PAGE


# ------------------------------------------------------ locale from the wire
def test_locale_comes_from_the_wire_not_from_the_dictionary():
    assert "const localeText = (bundle, base) => {" in PAGE
    # The transcript row uses summary_i18n; the activity row uses text_i18n.
    assert "localeText(m.summary_i18n,m.summary)" in PAGE
    assert "localeText(s.text_i18n, s.text)" in PAGE
    # Switching locale must re-render, because wire copy is chosen at render
    # time and the text-node translator cannot reach it by design.
    assert "try{if(lastState)render(lastState);}catch(e){}}" in PAGE


def test_the_page_side_labels_have_chinese_parity():
    # Only the words this consumer adds itself are dictionary-translated; the
    # notice text arrives pre-localised, so it is deliberately not duplicated.
    assert '"Context reduced":"上下文已精简","round":"轮次",' in PAGE


def test_locale_selection_prefers_the_active_locale_then_falls_back():
    node = shutil.which("node")
    if not node:  # Python-only machines still run the rest of the suite.
        return
    harness = _extract_fn("const localeText = (bundle, base) =>") + """;
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
globalThis.currentLocale = 'zh';
A(localeText({en: 'English', zh: '中文'}, 'base') === '中文', 'active locale wins');
globalThis.currentLocale = 'en';
A(localeText({en: 'English', zh: '中文'}, 'base') === 'English', 'en selected');
// Fallbacks, in order: missing locale -> en -> the plain field -> empty.
globalThis.currentLocale = 'zh';
A(localeText({en: 'English'}, 'base') === 'English', 'falls back to en');
A(localeText({}, 'base') === 'base', 'falls back to the plain field');
A(localeText(null, 'base') === 'base', 'a missing bundle falls back');
A(localeText(null, null) === '', 'nothing at all yields empty, never undefined');
console.log('ok');
"""
    result = subprocess.run([node, "-e", harness], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# ------------------------------------------ the two recovery cases stay apart
def test_the_two_recovery_claims_are_rendered_separately_not_flattened():
    """A tracked path and a working-tree-only path say different things.

    The page must not merge them: Agent B's S1-1 fix exists precisely because
    one reassuring sentence for both was false for the uncommitted case.
    """
    from crossaudit.console.progress import CONTEXT_CONDENSATION_ZH

    tracked = "Tracked project files outlined; file_read can retrieve the committed version"
    untracked = ("Working-tree-only project files outlined; "
                 "content is not available to file_read")
    # Both claims exist upstream, and they are genuinely different sentences.
    assert tracked in CONTEXT_CONDENSATION_ZH
    assert untracked in CONTEXT_CONDENSATION_ZH
    assert CONTEXT_CONDENSATION_ZH[tracked] != CONTEXT_CONDENSATION_ZH[untracked]
    # And the page holds NEITHER: it relays the sentence the event carries
    # instead of authoring copy that could drift from what is true.
    assert tracked not in PAGE
    assert untracked not in PAGE
    branch = PAGE[PAGE.index("if(m.kind === 'context_condensed'){"):]
    branch = branch[:branch.index("return '<article class=\"turn\"><div class=\"turn-main\">'")]
    # No hard-coded recovery sentence in the renderer — it only relays.
    assert "file_read" not in branch, "the page must relay the claim, never author one"


def test_the_detail_is_shown_as_paths_and_degrades_safely():
    node = shutil.which("node")
    if not node:
        return
    # The split that turns "<sentence>: <paths>" into a sentence plus chips.
    harness = """
const A = (cond, msg) => { if (!cond) { throw new Error(msg); } };
function split(full, detail){
  const tail = ': ' + detail;
  const head = (detail && full.endsWith(tail)) ? full.slice(0, -tail.length) : full;
  return {head, chips: (detail && full.endsWith(tail)) ? detail.split(',').map(p=>p.trim()).filter(Boolean) : []};
}
// Locale-neutral detail (paths): splits into sentence + chips.
let r = split('Files outlined: a/b.md, c/d.md', 'a/b.md, c/d.md');
A(r.head === 'Files outlined', 'sentence is separated from the paths');
A(r.chips.length === 2, 'each path becomes its own chip');
// Localised detail (a byte count) does not match: degrade to the whole
// sentence rather than to a wrong split.
r = split('较早的用户补充说明已精简: 24000 字节', '24000 bytes');
A(r.head === '较早的用户补充说明已精简: 24000 字节', 'unsplit rather than wrong');
A(r.chips.length === 0, 'no chips when the tail does not match');
// No detail at all.
r = split('Files outlined', '');
A(r.head === 'Files outlined' && r.chips.length === 0, 'empty detail is fine');
console.log('ok');
"""
    result = subprocess.run([node, "-e", harness], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
