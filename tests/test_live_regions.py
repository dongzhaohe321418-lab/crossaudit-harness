"""SPEC-9 slice 0 — one announcer, and the rule that stops the obvious fix.

The console has no way to tell a screen-reader user that anything happened. The
obvious fix — `aria-live` on the containers that change — is not merely
insufficient here, it is worse than the silence it replaces:

    document.getElementById('conversation').innerHTML = html;   // every render

The conversation is replaced WHOLESALE, driven by a stream with a 2-second poll
fallback. A live region on it re-announces the entire transcript every two
seconds. So live regions may only ever be attached to small, stable nodes that
are written in place.

This slice ships nothing a person can see: the hidden announcer, `announce()`,
and the rule as a test. It is built first because the failure it prevents is
SILENT — a live region on a replaced node does not error, it just announces
nothing or announces everything, and nobody notices until a screen-reader user
does.

Ledger D10: every guard here is demonstrated to fail against a deliberate
mutation of the thing it guards, and the mutations are recorded.
"""
import re
import shutil

import pytest

from crossaudit.console.page import PAGE

from .node_eval import run_node

LIVE_ATTR = re.compile(r'role="(?:alert|status|log)"|aria-live="[a-z]+"')
# The same thing said in JS rather than in markup. A rule that only reads
# attributes is one setAttribute call away from being decorative.
LIVE_CALL = re.compile(
    r"""setAttribute\(\s*['"](?:aria-live|role)['"]\s*,\s*['"](?:polite|assertive|alert|status|log)['"]""")

# Known violations that predate this slice, each with the slice that closes it.
# This list may SHRINK and may never grow: a new live region on a render target
# fails the guard instead of being added here.
KNOWN_VIOLATIONS = {
    # Interrupt-class error lines rendered inside panel-dynamic. They only
    # repeat while an error is displayed, unlike the optimistic turn which
    # repeated unconditionally and is fixed in this slice. The correct shape is
    # SPEC-9 §2 — an alert node inserted at the moment it becomes true — and it
    # belongs with the surface that owns each pane.
    "computeView": 'role="alert"',
    "toolsView": 'role="alert"',
}


def _script():
    return PAGE.split("<script>")[1].split("</script>")[0]


def _render_targets():
    """Ids whose innerHTML is assigned, i.e. replaced wholesale on render."""
    script = _script()
    ids = set(re.findall(r"getElementById\('([^']+)'\)\.innerHTML\s*=", script))
    # `const dynamic = document.getElementById('panel-dynamic')` then
    # `dynamic.innerHTML = ...` — resolve one level of aliasing.
    for var in set(re.findall(r"\b([A-Za-z_$][\w$]*)\.innerHTML\s*=", script)):
        found = re.search(
            r"\b%s\s*=\s*document\.getElementById\('([^']+)'\)" % re.escape(var), script)
        if found:
            ids.add(found.group(1))
    return ids


def _functions_feeding(targets):
    """Functions whose HTML ends up inside a render target, one hop deep.

    Seeded from the identifiers in each `X.innerHTML = ...` statement, then
    expanded through the bodies of those functions — which is how
    `optimisticTurn` reaches `#conversation` via `renderConversation`.
    """
    script = _script()
    seeds = set()
    for match in re.finditer(r"\.innerHTML\s*=\s*([^;]+);", script):
        seeds.update(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", match.group(1)))
    bodies = dict(re.findall(
        r"function ([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", script) and [])
    # Walk each function body by brace matching and pull the calls out of it.
    reachable, frontier = set(seeds), list(seeds)
    while frontier:
        name = frontier.pop()
        start = script.find("function %s(" % name)
        if start < 0:
            continue
        depth, i = 0, script.index("{", start)
        while i < len(script):
            if script[i] == "{":
                depth += 1
            elif script[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        for called in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", script[start:i]):
            if called not in reachable and ("function %s(" % called) in script:
                reachable.add(called)
                frontier.append(called)
    return reachable, bodies


def _function_at(index):
    """The function a source offset sits inside, by scanning backwards."""
    script = _script()
    best, name = -1, None
    for match in re.finditer(r"function ([A-Za-z_$][\w$]*)\s*\(", script[:index]):
        if match.start() > best:
            best, name = match.start(), match.group(1)
    return name


def test_no_live_region_is_emitted_into_a_container_that_is_replaced():
    """SPEC-9 §6.6, and the reason this slice exists.

    A live region inside a wholesale-replaced container re-announces its whole
    contents on every render. The render loop polls every two seconds.
    """
    script = _script()
    reachable, _ = _functions_feeding(_render_targets())
    offenders = {}
    for match in LIVE_ATTR.finditer(script):
        owner = _function_at(match.start())
        if owner in reachable:
            offenders.setdefault(owner, set()).add(match.group(0))
    # ...and the same thing done imperatively, on a render target by name.
    targets = _render_targets()
    for match in LIVE_CALL.finditer(script):
        window = script[max(0, match.start() - 160):match.start()]
        named = re.findall(r"getElementById\('([^']+)'\)", window)
        if named and named[-1] in targets:
            offenders.setdefault(named[-1], set()).add(match.group(0))
    unexpected = {name: sorted(attrs) for name, attrs in offenders.items()
                  if KNOWN_VIOLATIONS.get(name) not in attrs}
    assert not unexpected, (
        "these live regions are emitted into a container that is replaced on "
        "every render, so they re-announce their whole contents every two "
        "seconds: %s" % unexpected)
    # The debt list may shrink, never grow.
    assert set(offenders) <= set(KNOWN_VIOLATIONS), sorted(
        set(offenders) - set(KNOWN_VIOLATIONS))


def test_page_markup_gives_the_optimistic_turn_no_live_region_attribute():
    """It carried aria-live on the article and role=status on the dots, inside
    #conversation — so the whole echoed message was re-announced every two
    seconds for as long as it was on screen. The announcement it was reaching
    for is Progress class and is made once, as a sentence, in slice 2.
    MARKUP ONLY. Asserts strings in ``page.py``; renders nothing and cannot
    fail if the page never reaches a person — proved under D106 by serving an
    empty document, which left it green.
    """
    assert '<article class="turn" aria-live="polite">' not in PAGE
    assert '<span class="thinking-dots" role="status"' not in PAGE
    assert '<article class="turn">' in PAGE


def test_the_announcer_is_a_stable_node_outside_every_render_target():
    assert ('<p id="announcer" role="status" aria-live="polite" class="sr-only">'
            '</p>') in PAGE
    # Directly under <body>, so no render can replace it.
    assert PAGE.split("<body>\n")[1].startswith('<p id="announcer"')
    assert "announcer" not in _render_targets()


# ------------------------------------------------------------------ executed
HARNESS = r"""
const A=(c,m)=>{if(!c)throw new Error(m);};
let writes=[];
// The announcer now reaches its node through liveText, which builds the value in
// a detached holder and moves it in with ONE replaceChildren — so the stub has
// to model that door rather than a bare textContent setter. What this file
// measures is unchanged: how many times, and with what, the region is written.
const node={childNodes:[],
  replaceChildren(...ns){this.childNodes=ns.slice();writes.push(this.textContent);},
  set textContent(v){this.childNodes=v===''?[]:[{text:v}];writes.push(v);},
  get textContent(){return this.childNodes.map(n=>n.text).join('');}};
globalThis.document={getElementById:id=>id==='announcer'?node:null,
  createElement:()=>({childNodes:[],
    set textContent(v){this.childNodes=v===''?[]:[{text:v}];},
    set innerHTML(v){this.childNodes=v===''?[]:[{text:v}];}})};
let timers=[];
globalThis.setTimeout=(fn)=>{timers.push(fn);return timers.length;};
globalThis.clearTimeout=(id)=>{if(id)timers[id-1]=null;};
const flush=()=>{const t=timers;timers=[];for(const fn of t)if(fn)fn();};

// Two identical consecutive renders write the announcer ONCE, not twice.
announce('Round 2 of 3 started');
announce('Round 2 of 3 started');
flush();
A(writes.length===1,'a repeated state must not be announced twice, got '+writes.length);
A(writes[0]==='Round 2 of 3 started','and it says the sentence it was given');

// The same sentence in two separate frames is still not news. This is the case
// the debounce alone cannot satisfy, so it is what discriminates the two.
writes=[];
announce('Round 2 of 3 started');flush();
A(writes.length===0,'a state already announced must stay silent across frames, got '+JSON.stringify(writes));

// A burst inside one frame is coalesced to the last sentence, not spoken in turn.
writes=[];
announce('Round 3 of 3 started');
announce('CrossAudit replied');
flush();
A(writes.length===1,'a burst must coalesce, got '+writes.length+': '+JSON.stringify(writes));
A(writes[0]==='CrossAudit replied','and the last state is the one spoken');

// A genuine change still speaks.
writes=[];announce('Tools & Skills');flush();
A(writes.length===1&&writes[0]==='Tools & Skills','a new sentence is announced');

// Returning to an earlier state is news again.
writes=[];announce('CrossAudit replied');flush();
A(writes.length===1,'A -> B -> A must announce, got '+writes.length);

// Nothing is announced for nothing.
writes=[];announce('');announce(null);announce('   ');flush();
A(writes.length===0,'empty sentences are not announcements');

// R2. The suppression above is a rule about a STATE. An EVENT repeated verbatim
// is a SECOND occurrence, and silencing it is how a screen-reader user loses a
// reply a sighted user can see. The auditor found this through a colliding
// identity key; the browser drive then showed it silences every repeat arrival,
// collision or not.
writes=[];
announce('CrossAudit replied in Alpha analysis.','event');flush();
announce('CrossAudit replied in Alpha analysis.','event');flush();
A(writes.filter(w=>w!=='').length===2,
  'a repeated EVENT must be announced again, got '+JSON.stringify(writes));
A(writes.filter(w=>w!=='').every(w=>w==='CrossAudit replied in Alpha analysis.'),
  'and it says the same thing both times: '+JSON.stringify(writes));
// ...and it is a real change to the region, not the same string re-assigned,
// which a screen reader comparing content would have nothing to notice.
A(writes[0]===''&&writes[2]==='',
  'each event clears the region before writing, got '+JSON.stringify(writes));

// A state is still a state: the default is unchanged, so the 2-second render
// loop cannot become speech.
writes=[];
announce('Round 4 of 4 started');flush();
announce('Round 4 of 4 started');flush();
A(writes.length===1,'a repeated STATE is still silent, got '+JSON.stringify(writes));

// A burst of events inside one frame is still one sentence.
writes=[];
announce('CrossAudit replied in Alpha analysis.','event');
announce('CrossAudit replied in Alpha analysis.','event');
announce('CrossAudit replied in Alpha analysis.','event');
flush();
A(writes.filter(w=>w!=='').length===1,
  'three arriving in one frame is one sentence, got '+JSON.stringify(writes));
console.log('ok');
"""


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
    head = _script()
    prefix = head[head.index("let announcedText="):head.index("function announce(")]
    return prefix + _extract("function announce(sentence,kind)")


def _run(js):
    return run_node(js)


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


def test_the_announcer_speaks_once_per_change_and_not_once_per_render():
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


MUTATIONS = (
    ("an arrival is treated as a state, so every reply after the first is "
     "silent — the R2 finding, in behaviour",
     "  if(!event&&text===announcedText)return false;",
     "  if(text===announcedText)return false;"),
    ("an event stops being a real change to the region, so a screen reader "
     "comparing content has nothing to notice",
     "    if(event)liveText(node,'');", "    "),
    ("the debounce is removed, so a burst of stream events becomes a burst of "
     "speech — SPEC-9 slice 0's own mutation",
     "  if(announceTimer)clearTimeout(announceTimer);", "  "),
    ("a repeated state is announced again, so a render that restates what it "
     "already stated speaks",
     "  if(!event&&text===announcedText)return false;", "  if(!text)return false;"),
)


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[0][:32] for m in MUTATIONS])
def test_the_announcer_guard_is_shown_to_fail(why, before, after):
    _needs_node()
    sources = _sources()
    assert sources.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    result = _run(sources.replace(before, after) + HARNESS)
    assert result.returncode != 0, f"MUTATION SURVIVED — {why}."


SOURCE_MUTATIONS = (
    ("aria-live is attached to #conversation itself — the naive fix the whole "
     "spec exists to rule out",
     "document.getElementById('conversation').innerHTML = html",
     "document.getElementById('conversation').setAttribute('aria-live','polite');"
     "document.getElementById('conversation').innerHTML = html"),
    ("a live region goes back into a view that panel-dynamic replaces",
     "function planView(d){", "function planView(d){/* role=\"status\" */"),
    ("the optimistic turn re-announces itself again",
     "+ '<article class=\"turn\"><div class=\"turn-main\">'",
     "+ '<article class=\"turn\" aria-live=\"polite\"><div class=\"turn-main\">'"),
)


@pytest.mark.parametrize("why,before,after", SOURCE_MUTATIONS,
                         ids=[m[0][:32] for m in SOURCE_MUTATIONS])
def test_the_render_target_rule_is_shown_to_fail(why, before, after, monkeypatch):
    """Break the page on purpose, run the real rule against it, watch it catch."""
    import crossaudit.console.page as page_module
    import tests.test_live_regions as self_module

    assert PAGE.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    mutated = PAGE.replace(before, after)
    monkeypatch.setattr(page_module, "PAGE", mutated)
    monkeypatch.setattr(self_module, "PAGE", mutated)
    caught = []
    for name, check in (
            ("render-target rule", test_no_live_region_is_emitted_into_a_container_that_is_replaced),
            ("optimistic turn", test_page_markup_gives_the_optimistic_turn_no_live_region_attribute),
            ("announcer placement", test_the_announcer_is_a_stable_node_outside_every_render_target)):
        try:
            check()
        except AssertionError:
            caught.append(name)
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."
