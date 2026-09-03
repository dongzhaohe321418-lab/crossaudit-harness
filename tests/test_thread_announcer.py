"""SPEC-9 slice 2 — the thread announces that something arrived, not what it says.

`#conversation` is assigned innerHTML on every render, driven by a stream with a
two-second poll fallback. A live region on it re-announces the entire transcript
every two seconds — the naive fix is worse than the silence it replaces. So the
DELTA is announced, through slice 0's shared announcer.

And only that it arrived. Reading a generated answer aloud through a live region
is hostile: a person cannot pause it, skim it, or re-read it. They are told there
is something there; they read it themselves.

**The locale-timing rule, and a correction this file owes the reader.** An
earlier version of this docstring said the file "proves the node never holds an
English value in a Chinese page". It did not. It asserted the ORDER of two
statements in the source, which is a claim about the code, and the cross-vendor
auditor then drove the product and recorded the live region holding
`CrossAudit replied.` and only then `CrossAudit 已回复。` — the property violated,
the guard green. AGENTS.md §3.5 in its purest form, committed by the person who
wrote the rule.

The runtime property is now guarded where it can only be settled by execution:
`tests/test_live_region_locale_values.py` runs the product's own `liveText` and
records EVERY value the live-region node holds, in order. This file keeps the
delta behaviour — what is announced, when, and how many times.
"""
import shutil

import pytest

from crossaudit.console.page import PAGE

from .node_eval import run_node


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
                      _extract("function threadArrivalSentence(d)"),
                      _extract("function announceThread(messages,d)")))


def _run(js):
    return run_node(js)


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


HARNESS = r"""
const A=(c,m)=>{if(!c)throw new Error(m);};
let spoken=[];
globalThis.announce=(s,kind)=>{spoken.push({s,kind});return true;};
globalThis.activeChatId='chat-A';
// The real titleOf() needs the whole state shape; what this file is about is the
// sentence, so the title is supplied and threadArrivalSentence runs for real.
let title='Alpha analysis';
globalThis.titleOf=()=>title;
const d={};
const you=t=>({kind:'you',t,utterance:'from me '+t});
const reply=t=>({kind:'generator_chat',t,response:'from CrossAudit '+t});

// A transcript that already exists is not news.
const opening=[you(1),reply(2),reply(3)];
announceThread(opening,d);
A(spoken.length===0,'opening a thread must not announce its history, got '+JSON.stringify(spoken));

// A render that restates the same state says nothing. This is the property that
// a live region on the container could not have: it would speak every 2s.
announceThread(opening);announceThread(opening,d);
A(spoken.length===0,'a re-render of unchanged state is silent');

// Their own words are not read back to them.
announceThread(opening.concat([you(4)]),d);
A(spoken.length===0,'the person\'s own turn is not announced');

// A reply is one sentence, and it is about arrival, not content.
const answered=opening.concat([you(4),reply(5)]);
announceThread(answered,d);
A(spoken.length===1,'a new reply announces exactly once, got '+JSON.stringify(spoken));
A(spoken[0].s==='CrossAudit replied in Alpha analysis.',
  'and says that it arrived AND which thread it arrived in: '+JSON.stringify(spoken[0]));
// An arrival is an EVENT. Announced as a state, the second reply in a thread
// is suppressed by the shared announcer and a screen-reader user loses it.
A(spoken[0].kind==='event','and it is announced as an arrival, not a state');
A(JSON.stringify(spoken).indexOf('from CrossAudit')<0,'never the content of the reply');

// ...and not again on the next render.
announceThread(answered);announceThread(answered,d);
A(spoken.length===1,'the same reply is not announced again');

// Several arriving at once is still one sentence, not one per turn.
spoken=[];
announceThread(answered.concat([reply(6),reply(7),reply(8)]),d);
A(spoken.length===1,'three arriving together is one sentence, got '+spoken.length);

// Switching threads is not an event in either thread.
spoken=[];
globalThis.activeChatId='chat-B';
announceThread([reply(20),reply(21)],d);
A(spoken.length===0,'switching threads announces nothing');
announceThread([reply(20),reply(21),reply(22)],d);
A(spoken.length===1,'but a reply in the new thread does');

// Coming back to the first thread re-baselines rather than re-announcing it.
spoken=[];
globalThis.activeChatId='chat-A';
announceThread(answered,d);
A(spoken.length===0,'returning to a thread does not replay it');

// R2 S1 — a distinct reply must not be silenced by a lossy key.
// Two DIFFERENT replies, same kind, same second, and the same first 40
// characters. They render as two articles; the auditor observed ONE
// announcement, so a screen-reader user lost a message a sighted user could see.
spoken=[];
globalThis.activeChatId='chat-C';
const shared='The report is ready and here is the summary';   // 43 chars
const near1={kind:'generator_chat',t:900,response:shared+' — part one'};
const near2={kind:'generator_chat',t:900,response:shared+' — part two'};
A(near1.response.slice(0,40)===near2.response.slice(0,40),
  'the fixture must actually collide on a 40-character prefix, or it proves nothing');
A(near1.t===near2.t,'and on the second, or it proves nothing');
announceThread([you(800)],d);
spoken=[];
announceThread([you(800),near1],d);
A(spoken.length===1,'the first of the pair announces, got '+JSON.stringify(spoken));
spoken=[];
announceThread([you(800),near1,near2],d);
A(spoken.length===1,
  'a second, DIFFERENT reply sharing kind, second and its first 40 characters '+
  'must still be announced — it is on screen; got '+JSON.stringify(spoken));

// R2 S2 — an untitled thread falls back rather than announcing "New chat",
// which names nothing.
spoken=[];title='New chat';
globalThis.activeChatId='chat-D';
announceThread([you(1)],d);
announceThread([you(1),reply(2)],d);
A(spoken.length===1&&spoken[0].s==='CrossAudit replied.',
  'an untitled thread announces the bare sentence, got '+JSON.stringify(spoken));
title='Alpha analysis';
console.log('ok');
"""


def test_the_thread_announces_arrival_once_and_never_its_contents():
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_announcer_goes_through_the_shared_live_region_rule():
    """All this asserts is the WIRING — that the announcer does not write the
    node itself. Whether the rule is correct is settled by execution, in
    `test_live_region_locale_values.py`, because that is the only place it can
    be: the defect this replaces was a true statement about source order sitting
    over a violated runtime property."""
    announce = _extract("function announce(sentence,kind)")
    assert "const node=document.getElementById('announcer');" in announce
    assert "liveText(node,text);" in announce
    assert "node.textContent=text" not in announce


def test_the_conversation_itself_never_becomes_a_live_region():
    conversation = PAGE[PAGE.index("function renderConversation(d){"):
                        PAGE.index("const PANEL_TITLES=")]
    assert "aria-live" not in conversation
    assert "announceThread(messages,d);" in conversation


def test_the_sentence_reads_in_chinese():
    assert '"CrossAudit replied.":"CrossAudit 已回复。"' in PAGE
    # The named form is COMPOSED, so it needs a pattern. A fixed entry would
    # translate only the threads whose titles happen to be in the dictionary and
    # hand every other Chinese reader an English sentence — the i18n form of the
    # silent gap.
    assert "/^CrossAudit replied in (.+)\\.$/" in PAGE
    assert "'CrossAudit 在「'+m[1]+'」中已回复。'" in PAGE


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
    ("the identity goes back to a lossy 40-character prefix, so two distinct "
     "replies in the same second collapse and one of them is never announced — "
     "the exact defect the auditor drove",
     "  return [m.kind,m.t,String(m.utterance||m.summary||m.verdict||m.response||'')].join('|');}",
     "  return [m.kind,m.t,String(m.utterance||m.summary||m.verdict||m.response||'').slice(0,40)].join('|');}"),
    ("the announcement stops naming the thread, so a person with two threads "
     "hears that something replied without hearing what replied",
     "  return announce(threadArrivalSentence(d),'event');}",
     "  return announce('CrossAudit replied.','event');}"),
    ("an arrival is announced as a state, which is what suppresses the second "
     "reply in a thread inside the shared announcer",
     "  return announce(threadArrivalSentence(d),'event');}",
     "  return announce(threadArrivalSentence(d));}"),
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
    ("the announcer stops going through the shared rule at all",
     "    liveText(node,text);},120);",
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
            ("announcer wiring", test_the_announcer_goes_through_the_shared_live_region_rule),
            ("conversation is not a live region", test_the_conversation_itself_never_becomes_a_live_region),
            ("slice 0 render-target rule",
             live_module.test_no_live_region_is_emitted_into_a_container_that_is_replaced)):
        try:
            check()
        except AssertionError:
            caught.append(name)
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
