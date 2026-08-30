"""SPEC-9 slice 2 — the thread announces that something arrived, not what it says.

`#conversation` is assigned innerHTML on every render, driven by a stream with a
two-second poll fallback. A live region on it re-announces the entire transcript
every two seconds — the naive fix is worse than the silence it replaces. So the
DELTA is announced, through slice 0's shared announcer.

And only that it arrived. Reading a generated answer aloud through a live region
is hostile: a person cannot pause it, skim it, or re-read it. They are told there
is something there; they read it themselves.

**The locale-timing rule, which the boss asked be carried into this slice.**
Driving slice 1 in Chinese found that announcing synchronously spoke the English
source while the name of the dialog — built from the same nodes — was already
translated, because the locale observer runs a microtask later. Same source,
different timing, different language. So `announce()` now translates in the SAME
TASK as the write, and this file proves the node never holds an English value in
a Chinese page — the browser run reads every intermediate value the node takes,
not just the final one.
"""
import re
import shutil
import subprocess

import pytest

from crossaudit.console.page import PAGE


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
    state = script[script.index("let announcedTurns=null;"):
                   script.index("function turnKey(m){")]
    return "\n".join((state,
                      _extract("function turnKey(m)"),
                      _extract("function announceThread(messages)")))


def _run(js):
    return subprocess.run([shutil.which("node"), "-e", js], text=True,
                          capture_output=True)


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


HARNESS = r"""
const A=(c,m)=>{if(!c)throw new Error(m);};
let spoken=[];
globalThis.announce=s=>{spoken.push(s);return true;};
globalThis.activeChatId='chat-A';
const you=t=>({kind:'you',t,utterance:'from me '+t});
const reply=t=>({kind:'generator_chat',t,response:'from CrossAudit '+t});

// A transcript that already exists is not news.
const opening=[you(1),reply(2),reply(3)];
announceThread(opening);
A(spoken.length===0,'opening a thread must not announce its history, got '+JSON.stringify(spoken));

// A render that restates the same state says nothing. This is the property that
// a live region on the container could not have: it would speak every 2s.
announceThread(opening);announceThread(opening);
A(spoken.length===0,'a re-render of unchanged state is silent');

// Their own words are not read back to them.
announceThread(opening.concat([you(4)]));
A(spoken.length===0,'the person\'s own turn is not announced');

// A reply is one sentence, and it is about arrival, not content.
const answered=opening.concat([you(4),reply(5)]);
announceThread(answered);
A(spoken.length===1,'a new reply announces exactly once, got '+JSON.stringify(spoken));
A(spoken[0]==='CrossAudit replied.','and says that it arrived: '+spoken[0]);
A(spoken[0].indexOf('from CrossAudit')<0,'never the content of the reply');

// ...and not again on the next render.
announceThread(answered);announceThread(answered);
A(spoken.length===1,'the same reply is not announced again');

// Several arriving at once is still one sentence, not one per turn.
spoken=[];
announceThread(answered.concat([reply(6),reply(7),reply(8)]));
A(spoken.length===1,'three arriving together is one sentence, got '+spoken.length);

// Switching threads is not an event in either thread.
spoken=[];
globalThis.activeChatId='chat-B';
announceThread([reply(20),reply(21)]);
A(spoken.length===0,'switching threads announces nothing');
announceThread([reply(20),reply(21),reply(22)]);
A(spoken.length===1,'but a reply in the new thread does');

// Coming back to the first thread re-baselines rather than re-announcing it.
spoken=[];
globalThis.activeChatId='chat-A';
announceThread(answered);
A(spoken.length===0,'returning to a thread does not replay it');
console.log('ok');
"""


def test_the_thread_announces_arrival_once_and_never_its_contents():
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_announcement_is_translated_in_the_same_task_as_the_write():
    """The boss's rule from slice 1, generalised: anything announced must be in
    the locale the person is reading, not the locale the DOM held a microtask
    ago. A live region announces what is there, not what is about to be.

    The rule now lives in `liveText`, because the sweep found it is a property of
    every live region and not of the announcer — so this guard follows it there
    rather than being deleted. The class-level version, with the collection
    surface and the same-task check, is `test_live_region_locale_timing.py`.
    """
    announce = _extract("function announce(sentence)")
    assert "liveText(document.getElementById('announcer'),text);" in announce
    write = _extract("function liveText(node,value)")
    assert "node.textContent=String(value==null?'':value);" in write
    assert "if(typeof localizeTree==='function')localizeTree(node);" in write
    # ...and in that order: translating before the write would translate nothing.
    assert write.index("node.textContent=") < write.index("localizeTree(node)")


def test_the_conversation_itself_never_becomes_a_live_region():
    conversation = PAGE[PAGE.index("function renderConversation(d){"):
                        PAGE.index("const PANEL_TITLES=")]
    assert "aria-live" not in conversation
    assert "announceThread(messages);" in conversation


def test_the_sentence_reads_in_chinese():
    assert '"CrossAudit replied.":"CrossAudit 已回复。"' in PAGE


MUTATIONS = (
    ("every render announces, which is what a live region on #conversation "
     "would do — the mutation SPEC-9 asks for, in behaviour",
     "  const fresh=messages.filter(m=>m.kind!=='you'&&!announcedTurns.has(turnKey(m)));\n"
     "  announcedTurns=keys;\n"
     "  // Their own words are not read back to them.\n"
     "  if(!fresh.length)return false;",
     "  announcedTurns=keys;"),
    ("opening a thread announces its whole history, because the baseline is not "
     "taken in silence",
     "  if(announcedTurnChat!==chat||announcedTurns===null){\n"
     "    announcedTurnChat=chat;announcedTurns=keys;return false;}",
     "  if(announcedTurnChat!==chat||announcedTurns===null){\n"
     "    announcedTurnChat=chat;announcedTurns=new Set();}"),
    ("the person's own words are read back to them",
     "  const fresh=messages.filter(m=>m.kind!=='you'&&!announcedTurns.has(turnKey(m)));",
     "  const fresh=messages.filter(m=>!announcedTurns.has(turnKey(m)));"),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:34] for m in MUTATIONS])
def test_the_delta_guard_is_shown_to_fail(why, before, after):
    _needs_node()
    sources = _sources()
    assert sources.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    result = _run(sources.replace(before, after) + HARNESS)
    assert result.returncode != 0, f"MUTATION SURVIVED — {why}."


SOURCE_MUTATIONS = (
    ("the announcement stops being translated in the same task, so a Chinese "
     "reader hears the English source",
     "  node.textContent=String(value==null?'':value);\n"
     "  if(typeof localizeTree==='function')localizeTree(node);}",
     "  node.textContent=String(value==null?'':value);}"),
    ("the announcer stops going through the shared rule and writes the node "
     "itself, which is how the rule held here and drifted everywhere else",
     "    liveText(document.getElementById('announcer'),text);},120);",
     "    const node=document.getElementById('announcer');\n"
     "    if(node)node.textContent=text;},120);"),
    ("aria-live is attached to the conversation — the mutation SPEC-9 §6.6 and "
     "slice 0 exist to catch",
     "document.getElementById('conversation').innerHTML = html;",
     "document.getElementById('conversation').setAttribute('aria-live','polite');"
     "document.getElementById('conversation').innerHTML = html;"),
)


@pytest.mark.parametrize("why,before,after", SOURCE_MUTATIONS,
                         ids=[m[0][:34] for m in SOURCE_MUTATIONS])
def test_the_source_guards_are_shown_to_fail(why, before, after, monkeypatch):
    import crossaudit.console.page as page_module
    import tests.test_live_regions as live_module
    import tests.test_thread_announcer as self_module

    assert PAGE.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    mutated = PAGE.replace(before, after)
    for module in (page_module, live_module, self_module):
        monkeypatch.setattr(module, "PAGE", mutated)
    caught = []
    for name, check in (
            ("locale timing", test_the_announcement_is_translated_in_the_same_task_as_the_write),
            ("conversation is not a live region", test_the_conversation_itself_never_becomes_a_live_region),
            ("slice 0 render-target rule",
             live_module.test_no_live_region_is_emitted_into_a_container_that_is_replaced)):
        try:
            check()
        except AssertionError:
            caught.append(name)
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
