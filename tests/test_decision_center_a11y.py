"""SPEC-9 slice 1 — the Decision Center announces what it is, not that it exists.

Design's sweep: the Decision Center is not a dialog to assistive technology at
all. `role` and `aria-modal` were both null and the background stayed reachable,
while focus moved in and the Tab trap held — so keyboard users were fine and a
screen-reader user was never told they had entered a modal.

The two halves ship together on purpose. Being told a modal opened and not being
told what it is about are the same failure: a person who hears "dialog" and
nothing else has been notified of a container, not of a decision they have to
make. So the dialog is NAMED by the flag and the title — the same words the
announcer speaks, so what is heard and what is read agree.

Also here, because it is the same surface and the same person: the close button
could not be clicked while Project controls was open. Both computed to z-index
60 and the inspector wins the tie by DOM order, so the button rendered, looked
live and did nothing — on the screen that says a decision "becomes part of the
durable audit ledger". A control that lies about being clickable is worse in a
modal that announces itself than in one that does not.

Every guard here is demonstrated to fail against a recorded mutation (D10).
"""
import re
import shutil
import subprocess

import pytest

from crossaudit.console.page import PAGE


def test_it_is_a_dialog_and_it_says_what_the_decision_is_about():
    assert ('<div class="decision" id="resolution-modal" role="dialog" aria-modal="true"\n'
            '  aria-labelledby="resolution-flag resolution-title"'
            ' aria-describedby="resolution-summary">') in PAGE
    # A static aria-label would override the name built from the flag and the
    # title, and announce a container instead of a decision.
    assert 'id="resolution-modal"' in PAGE
    modal = PAGE.split('id="resolution-modal"')[1].split(">")[0]
    assert "aria-label=" not in modal


def test_page_markup_defers_the_announcement_behind_a_zero_timeout():
    """The flag and the title are written, then translated on the next
    microtask. Announcing synchronously speaks the English source to a Chinese
    reader while the dialog's own name — built from the same nodes — is already
    translated, so the heard and the read versions disagree.
    MARKUP ONLY. Asserts strings in ``page.py``; renders nothing and cannot
    fail if the page never reaches a person — proved under D106 by serving an
    empty document, which left it green.
    """
    assert "setTimeout(()=>announce(decisionSentence()),0);" in PAGE
    assert "announce(decisionSentence());" not in PAGE.replace(
        "setTimeout(()=>announce(decisionSentence()),0);", "")


def test_page_markup_declares_the_inert_boundary_and_calls_it_once():
    """aria-modal tells a screen reader a boundary exists; inert makes it true.
    MARKUP ONLY. Asserts strings in ``page.py``; renders nothing and cannot
    fail if the page never reaches a person — proved under D106 by serving an
    empty document, which left it green.
    """
    assert "function setDecidingInert(on){" in PAGE
    assert "shell.setAttribute('inert','')" in PAGE
    assert PAGE.count("setDecidingInert(true)") == 1
    assert PAGE.count("setDecidingInert(false)") == 1


def test_the_decision_sits_above_the_panel_it_shared_a_layer_with():
    assert "z-index:calc(var(--z-sheet) + 1);" in PAGE
    decision = PAGE[PAGE.index(".decision{"):PAGE.index(".decision.on{")]
    assert "z-index:var(--z-sheet)" not in decision


def test_the_container_the_escalations_land_in_carries_no_live_region():
    """#escalations is assigned innerHTML on every render, so a live region on it
    would re-announce every waiting decision every two seconds (slice 0)."""
    assert "announceEscalations(escalations);" in PAGE
    block = PAGE[PAGE.index("function announceEscalations("):
                 PAGE.index("function renderInspector(d){")]
    assert "aria-live" not in block and 'role="alert"' not in block


HARNESS = r"""
const A=(c,m)=>{if(!c)throw new Error(m);};
let spoken=[];
globalThis.announce=s=>{spoken.push(s);return true;};
let FLAG='Generator connection stopped',TITLE='The task is waiting for a working Generator connection';
globalThis.document={getElementById:id=>id==='resolution-flag'?{textContent:FLAG}
  :id==='resolution-title'?{textContent:TITLE}:null,
  querySelector:()=>({setAttribute(){},removeAttribute(){}})};

// The dialog is named by what the decision is about, as one sentence.
A(decisionSentence()===FLAG+' — '+TITLE,'flag and title are announced together, got '+decisionSentence());
FLAG='';A(decisionSentence()===TITLE,'a missing flag does not leave a dangling dash');
FLAG='Only a flag';TITLE='';A(decisionSentence()==='Only a flag','nor a missing title');
FLAG='Generator connection stopped';TITLE='The task is waiting';

// An escalation APPEARING is news. A render that restates the same escalations
// is not, and neither is one resolving while another arrives.
spoken=[];
announceEscalations([{cycle_id:'a'}]);
A(spoken.length===1&&spoken[0]==='A task is waiting for your decision.','one new decision announces once');
announceEscalations([{cycle_id:'a'}]);
A(spoken.length===1,'the same decision on the next render must not announce again');
announceEscalations([{cycle_id:'a'},{cycle_id:'b'}]);
A(spoken.length===2,'a second, new decision announces');
A(spoken[1]==='A task is waiting for your decision.','one at a time is still singular');
spoken=[];announceEscalations([{cycle_id:'a'},{cycle_id:'b'}]);
A(spoken.length===0,'and neither of them announces again');
// One resolves as another arrives: the COUNT is unchanged, so a count-based
// check would say nothing. Identity is what makes this news.
spoken=[];announceEscalations([{cycle_id:'b'},{cycle_id:'c'}]);
A(spoken.length===1,'a swap at the same count is still a new decision');
// Two at once reads as two.
spoken=[];announceEscalations([{cycle_id:'x'},{cycle_id:'y'},{cycle_id:'b'}]);
A(spoken.length===1&&spoken[0]==='2 tasks are waiting for your decision.',
  'two new at once is one sentence naming two, got '+JSON.stringify(spoken));
// Nothing waiting says nothing.
spoken=[];announceEscalations([]);announceEscalations([]);
A(spoken.length===0,'an empty list is not an announcement');
console.log('ok');
"""


def _script():
    return PAGE.split("<script>")[1].split("</script>")[0]


def _extract(signature):
    script = _script()
    start = script.index(signature)
    depth, i = 0, script.index("{", start)
    while i < len(script):
        if script[i] == "{":
            depth += 1
        elif script[i] == "}":
            depth -= 1
            if depth == 0:
                return script[start:i + 1]
        i += 1
    raise AssertionError(signature)


def _sources():
    script = _script()
    state = script[script.index("let announcedEscalations=new Set();"):
                   script.index("function announceEscalations(rows){")]
    return "\n".join((state,
                      _extract("function announceEscalations(rows)"),
                      _extract("function decisionSentence()")))


def _run(js):
    return subprocess.run([shutil.which("node"), "-e", js], text=True,
                          capture_output=True)


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


def test_a_waiting_decision_announces_once_when_it_appears():
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


MUTATIONS = (
    ("the escalation announcement keys on the COUNT, so a decision resolving as "
     "another arrives says nothing, and a re-render says everything",
     "  const fresh=ids.filter(id=>id&&!announcedEscalations.has(id));\n"
     "  announcedEscalations=new Set(ids);\n"
     "  if(!fresh.length)return;",
     "  const fresh=ids;\n"
     "  announcedEscalations=new Set(ids);\n"
     "  if(!fresh.length)return;"),
    ("the dialog announces that a container opened, not what it is about",
     "  return flag&&title?flag+' \\u2014 '+title:(title||flag);}",
     "  return 'Human decision';}"),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:34] for m in MUTATIONS])
def test_the_announcement_guard_is_shown_to_fail(why, before, after):
    _needs_node()
    sources = _sources()
    assert sources.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    result = _run(sources.replace(before, after) + HARNESS)
    assert result.returncode != 0, f"MUTATION SURVIVED — {why}."


SOURCE_MUTATIONS = (
    ("aria-modal is dropped, so a screen reader is never told a boundary exists",
     'id="resolution-modal" role="dialog" aria-modal="true"',
     'id="resolution-modal" role="dialog"'),
    ("the dialog takes a static name again, so it announces a container",
     'aria-labelledby="resolution-flag resolution-title"',
     'aria-label="Human decision"'),
    ("the background stops being inert, so aria-modal claims a boundary the "
     "page does not enforce",
     "  if(on)shell.setAttribute('inert','');else shell.removeAttribute('inert');",
     "  if(on)return;shell.removeAttribute('inert');"),
    ("the decision goes back on the layer the inspector wins, so its close "
     "button renders, looks live and does nothing",
     "z-index:calc(var(--z-sheet) + 1);", "z-index:var(--z-sheet);"),
)


@pytest.mark.parametrize("why,before,after", SOURCE_MUTATIONS,
                         ids=[m[0][:34] for m in SOURCE_MUTATIONS])
def test_the_dialog_guards_are_shown_to_fail(why, before, after, monkeypatch):
    import crossaudit.console.page as page_module
    import tests.test_decision_center_a11y as self_module

    assert PAGE.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    mutated = PAGE.replace(before, after)
    monkeypatch.setattr(page_module, "PAGE", mutated)
    monkeypatch.setattr(self_module, "PAGE", mutated)
    caught = []
    for name, check in (
            ("dialog semantics", test_it_is_a_dialog_and_it_says_what_the_decision_is_about),
            ("inert boundary", test_page_markup_declares_the_inert_boundary_and_calls_it_once),
            ("stacking", test_the_decision_sits_above_the_panel_it_shared_a_layer_with)):
        try:
            check()
        except AssertionError:
            caught.append(name)
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
