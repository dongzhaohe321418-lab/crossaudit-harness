"""SPEC-9 — the locale-timing rule, as a class over every live region.

**The rule, and where it came from.** Driving slice 1 in Chinese, the Decision
Center announced its flag and title by reading two DOM nodes. Announcing
SYNCHRONOUSLY spoke the English source, while the dialog's own accessible name —
built from *the same two nodes* — was already translated, because the locale
observer (`localizeTree` via a MutationObserver on `document.body`) runs a
**microtask later** than the write. Same source, different timing, different
language. A live region announces what **is** there, not what is about to be.

That was fixed inside `announce()`. This file exists because the rule is not
about the announcer — it is about **anything that announces text it also
renders**, and the sweep found nine such nodes.

**Measured, not reasoned about.** In a Chinese page, calling the product's own
`frUpdateIndependence()` and sampling `#fr-role-msg` (a `role="alert"` node on
the first-run provider step) at three moments gave:

    at the write        Generator and auditor must run on different providers…
    next microtask      生成者和审计者必须运行在不同的供应商上。…
    after a task        生成者和审计者必须运行在不同的供应商上。…

The alert fired on the first of those. A Chinese person picking the same vendor
for both roles saw Chinese and was read English. Evidence:
`_ui_findings/locale-timing/evidence/real-path-fr-role-msg.json`.

**What this file guards.** A live region may not be given a string the product
knows how to translate, except through `liveText` / `liveHTML`, which write and
translate in the same task. That is decidable: the collection surface is every
live region in the page, and the property is "this literal is in ZH".

The debt list is EMPTY and may never grow. It is empty because the exposure is
narrow — a write only bites when the string has a dictionary entry, and today
only two writes did. Both are converted. The rest of these nodes are written
with runtime strings (`e.message`) that translate to themselves; they are one
translated literal away from the same defect, which is what this guard is for.

Ledger D10: every guard here is demonstrated to fail against a deliberate
mutation of the thing it guards, and the mutations are recorded.
"""
import re

import pytest

from crossaudit.console.page import PAGE

# Live regions that are known to be written unsafely and are not converted yet.
# This list may SHRINK and may never grow: a new unsafe write fails the guard
# instead of being added here. It is empty, and that is the point.
KNOWN_UNSAFE_WRITES: dict = {}

LIVE_MARKUP = (
    re.compile(r'id="([^"]+)"[^>]*(?:role="(?:alert|status|log)"|aria-live=)'),
    re.compile(r'(?:role="(?:alert|status|log)"|aria-live="[a-z]+")[^>]*id="([^"]+)"'),
)


def _script():
    return PAGE.split("<script>")[1].split("</script>")[0]


def _zh_keys():
    """The English sources the product knows how to translate."""
    start = PAGE.index("const ZH={")
    block = PAGE[start:PAGE.index("\n};\n", start)]
    return set(re.findall(r'"((?:[^"\\]|\\.)*)":"', block))


def _live_ids():
    """Every node a screen reader will speak on change — the collection surface."""
    return sorted({match for pattern in LIVE_MARKUP
                   for match in pattern.findall(PAGE)})


def _unsafe_writes(page=None):
    """Writes of a translatable literal into a live region, bypassing the rule.

    Resolves one level of aliasing (`const msg = document.getElementById(...)`)
    and scans the scope the alias is live in — the enclosing function, or the
    whole script when it is bound at module level. That aliasing is not an edge
    case: there is not a single direct `getElementById('…').textContent =` on a
    live region in the page, so a checker that only understood the direct form
    would report zero findings and look clean.
    """
    source = page if page is not None else PAGE
    script = source.split("<script>")[1].split("</script>")[0]
    start = source.index("const ZH={")
    known = set(re.findall(r'"((?:[^"\\]|\\.)*)":"',
                           source[start:source.index("\n};\n", start)]))
    ids = sorted({m for pattern in LIVE_MARKUP for m in pattern.findall(source)})
    lines = script.split("\n")
    heads = [i for i, line in enumerate(lines)
             if re.match(r"(async )?function [A-Za-z_$]", line)]
    found = []
    for live_id in ids:
        binding = re.compile(
            r"\b([A-Za-z_$][\w$]*)\s*=\s*document\.getElementById\('%s'\)"
            % re.escape(live_id))
        for index, line in enumerate(lines):
            for match in binding.finditer(line):
                alias = match.group(1)
                if line[:1].strip():
                    # Bound at module scope: the alias is live for the whole
                    # script, so the whole script is the window. Scoping it to
                    # a "nearest function" would silently stop looking exactly
                    # where these nodes are most reachable.
                    head, end = index, len(lines)
                else:
                    head = max([h for h in heads if h <= index], default=0)
                    after = [h for h in heads if h > head]
                    end = after[0] if after else len(lines)
                write = re.compile(
                    r"\b%s\.(?:textContent|innerHTML)\s*=\s*'((?:[^'\\]|\\.)*)'"
                    % re.escape(alias))
                for row in range(head, end):
                    for hit in write.finditer(lines[row]):
                        if hit.group(1) and hit.group(1) in known:
                            found.append((live_id, hit.group(1)))
    return found


def test_the_sweep_still_sees_every_live_region_it_claims_to():
    """D10's amendment: a guard that quietly stops collecting an input narrows
    what it checks without failing. Losing a row here is losing coverage, so it
    has to be a visible edit."""
    assert _live_ids() == [
        "announcer", "compute-message", "file-preview-find-count", "fr-role-msg",
        "mcp-approve-count", "mcp-connected", "mcp-error", "mcp-message",
        "project-review", "settings-error", "wizard-error"]
    # And the dictionary it is checked against is a real one, not an empty set
    # that would make every literal look untranslatable and the guard vacuous.
    assert len(_zh_keys()) > 500


def test_no_live_region_is_handed_a_translatable_string_outside_the_rule():
    unsafe = _unsafe_writes()
    unexpected = [row for row in unsafe if row[1] != KNOWN_UNSAFE_WRITES.get(row[0])]
    assert not unexpected, (
        "these live regions are written with a string the product knows how to "
        "translate, without translating it in the same task — so the region "
        "announces the English source and the screen then shows Chinese: %s"
        % unexpected)
    assert {row[0] for row in unsafe} <= set(KNOWN_UNSAFE_WRITES)


def test_the_rule_is_one_function_and_the_announcer_uses_it():
    """S1-1's lesson from the send path, applied here before it can bite: a rule
    re-implemented at each consumer holds at the consumers someone remembered."""
    assert "function liveText(node,value){" in PAGE
    assert "function liveHTML(node,markup){" in PAGE
    assert "liveText(document.getElementById('announcer'),text);" in PAGE
    # The old inline form is gone, so there is one implementation, not two that
    # can drift.
    announce = PAGE[PAGE.index("function announce(sentence){"):]
    announce = announce[:announce.index("\nfunction ")]
    assert "node.textContent=text;" not in announce


@pytest.mark.parametrize("helper,write", (
    ("function liveText(node,value){", "node.textContent="),
    ("function liveHTML(node,markup){", "node.innerHTML="),
))
def test_the_write_and_the_translation_are_in_the_same_task(helper, write):
    """Not merely "in this order". The defect is a task boundary between them,
    so the guard is about the boundary: nothing in this function may defer."""
    body = PAGE[PAGE.index(helper):]
    body = body[:body.index("\nfunction ")]
    assert write in body
    assert "localizeTree(node)" in body
    assert body.index(write) < body.index("localizeTree(node)")
    for defer in ("setTimeout", "queueMicrotask", "requestAnimationFrame",
                  "await", "Promise", "then("):
        assert defer not in body, (
            f"{helper} defers with {defer!r} between the write and the "
            f"translation, which is the exact window this rule closes")


MUTATIONS = (
    ("the translation stops happening in the same task, so a live region "
     "announces the English source to a Chinese reader",
     "function liveText(node,value){\n"
     "  if(!node)return;\n"
     "  node.textContent=String(value==null?'':value);\n"
     "  if(typeof localizeTree==='function')localizeTree(node);}",
     "function liveText(node,value){\n"
     "  if(!node)return;\n"
     "  node.textContent=String(value==null?'':value);\n"
     "  setTimeout(()=>{if(typeof localizeTree==='function')localizeTree(node);},0);}"),
    ("the announcer stops going through the shared rule and grows its own copy",
     "    liveText(document.getElementById('announcer'),text);},120);",
     "    const node=document.getElementById('announcer');\n"
     "    if(node)node.textContent=text;},120);"),
    ("the first-run independence alert goes back to a raw write — the site the "
     "browser drive caught, restored exactly",
     "liveText(msg,'Generator and auditor must run on different providers. "
     "Independent review is the core of the protocol and cannot be turned off.');",
     "msg.textContent='Generator and auditor must run on different providers. "
     "Independent review is the core of the protocol and cannot be turned off.';"),
    ("a translated literal is written raw into a DIFFERENT live region, which "
     "is how slices 3-6 would introduce this without noticing",
     "const previewFindCount=document.getElementById('file-preview-find-count');",
     "const previewFindCount=document.getElementById('file-preview-find-count');\n"
     "previewFindCount.textContent='Connection verified.';"),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:34] for m in MUTATIONS])
def test_the_class_guard_is_shown_to_fail(why, before, after, monkeypatch):
    """Write the guard, break the product on purpose, watch it catch — against
    the real source, run live, never against a recorded snapshot of what the
    guard once said (D10 as amended)."""
    assert PAGE.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved and this "
        f"guard is no longer known to catch it")
    mutated = PAGE.replace(before, after)
    import crossaudit.console.page as page_module
    import tests.test_live_region_locale_timing as self_module
    monkeypatch.setattr(page_module, "PAGE", mutated)
    monkeypatch.setattr(self_module, "PAGE", mutated)
    caught = []
    for name, check in (
            ("one rule, and the announcer uses it",
             test_the_rule_is_one_function_and_the_announcer_uses_it),
            ("same task", lambda: test_the_write_and_the_translation_are_in_the_same_task(
                "function liveText(node,value){", "node.textContent=")),
            ("no raw translatable write",
             test_no_live_region_is_handed_a_translatable_string_outside_the_rule)):
        try:
            check()
        except AssertionError:
            caught.append(name)
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
