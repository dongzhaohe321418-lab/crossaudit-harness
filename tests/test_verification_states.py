"""SPEC-2 — a claim may not be shown before it is true.

The console opened on `✓ convergence ✓ provenance ✓ schema ✓ units` above
`Ledger: 0 Audits 0 Passed 0 Blocked`, with zero artifacts, zero receipts and the
generator never run. The `✓` was a literal prefix on every CONFIGURED check; there
was no not-yet-run state in the data or in the rendering. For a product whose
whole thesis is independent verification, four ticks for verification that never
happened is the worst class of defect we have (AGENTS.md §1.5, ledger D5 goal 2).

**What this file guards, and how it is known to guard it (ledger D10).**
Every assertion below runs the page's OWN rendering functions under node and
asserts over the HTML they return — never over the text of `page.py`, because a
source grep would have passed against the defect. The "no tick" assertion is made
against the TAG-STRIPPED output, which is the attack that defeated an earlier
guard: a phrase split across an `<em>` survives a substring check on markup and
does not survive one on the stripped text.

And the guard is demonstrated, on every run, to fail: `MUTATIONS` below breaks the
renderer on purpose in five ways — most importantly "make a not-yet-run state
render as passed" — and the test asserts the harness goes RED for each. A guard
whose counterfactual is not written down cannot be re-checked by the next person.

What this does NOT prove: that the browser lays it out or announces it as
intended. That was verified by driving a live console (both themes, both locales,
1440 and 390) and reading the rendered nodes, the composited contrast and the
accessibility tree; the numbers are recorded in the commit.
"""
import shutil
import subprocess

import pytest

from crossaudit.console.page import PAGE

# The pieces of the page the harness executes. CHECK_STATES is the vocabulary,
# the rest is everything that turns payload into markup.
SOURCES = (
    "const esc = s =>",
    "const CHECK_STATES=",
    "function checkEntry(value)",
    "function checkRows(d)",
    "function auditCount(d)",
    "function checkSummary(rows,audits)",
    "function renderCheckRows(rows)",
)

# Each entry: (why it is a defect, exact text in the extracted source, replacement).
# Every one of these must make the harness below FAIL. If a mutation stops
# applying because the source moved, the test fails too — a silently unapplied
# mutation is a guard that has quietly stopped guarding.
MUTATIONS = (
    ("a not-yet-run check renders as passed — the original defect",
     "not_run:{glyph:'\\u00b7'", "not_run:{glyph:'\\u2713'"),
    ("a not-yet-run check is styled as passed",
     "not_run:{glyph:'\\u00b7',cls:'not-run'", "not_run:{glyph:'\\u00b7',cls:'passed'"),
    ("an absent or unknown state defaults to passed instead of not-run",
     "?row.state:'not_run'", "?row.state:'passed'"),
    ("the first-run summary line claims the checks passed",
     ":'Not run yet — these run automatically on your first task.';",
     ":'All checks passed.';"),
    ("not-applicable is collapsed into not-run, so \"we looked and there was "
     "nothing to judge\" reads as \"we have not looked\"",
     "n_a    :{glyph:'\\u2013'", "n_a    :{glyph:'\\u00b7'"),
)

HARNESS = r"""
const A=(cond,msg)=>{if(!cond)throw new Error(msg);};
// What a person actually sees, and what a screen reader reads out: the markup
// with its tags removed. Asserting on raw HTML is defeatable by splitting a
// phrase across an element; asserting on the stripped text is not.
const seen=html=>html.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const rows=states=>checkRows({check_contracts:Object.fromEntries(
  states.map((s,i)=>[('check'+i),s===null?('a bare contract string'):{description:'d',state:s}]))});
const label=(html,name)=>{const m=html.match(new RegExp('aria-label="'+name+': ([^"]*)"'));return m&&m[1];};

// === 1. the defect itself: the shape the server sends today, and no audits ===
// check_contracts is {name: contract} — no state anywhere in the payload.
const today={check_contracts:{convergence:'c',provenance:'p',schema:'s',units:'u'},
             metrics:[{label:'Audits',value:0},{label:'Passed',value:0}]};
const todayRows=checkRows(today);
A(todayRows.length===4,'four configured checks');
A(todayRows.every(r=>r.state==='not_run'),'a payload with no state is not-run, never passed');
A(auditCount(today)===0,'the ledger reports zero audits');
const todayHtml=renderCheckRows(todayRows);
A(!seen(todayHtml).includes('✓'),'NO tick may be rendered while nothing has run');
A(!seen(todayHtml).includes('✕'),'and nothing may be rendered as failed either');
A(checkSummary(todayRows,0)==='Not run yet — these run automatically on your first task.',
  'the first-run line says the checks have not run, in plain language');

// === 2. every state renders its own mark, class and spoken name ===
const four=rows(['passed','failed','not_run','n_a']);
const fourHtml=renderCheckRows(four);
A(seen(fourHtml).includes('✓ check0'),'passed renders a tick');
A(seen(fourHtml).includes('✕ check1'),'failed renders a cross');
A(seen(fourHtml).includes('· check2'),'not-run renders a middot');
A(seen(fourHtml).includes('– check3'),'not-applicable renders a dash');
A(fourHtml.includes('class="check-row passed"'),'passed carries its own class');
A(fourHtml.includes('class="check-row failed"'),'failed carries its own class');
A(fourHtml.includes('class="check-row not-run"'),'not-run carries its own class');
A(fourHtml.includes('class="check-row n-a"'),'not-applicable carries its own class');
A(label(fourHtml,'check0')==='passed','a screen reader is told the state, not handed a glyph');
A(label(fourHtml,'check1')==='did not pass','...for failed');
A(label(fourHtml,'check2')==='not run yet','...for not run');
A(label(fourHtml,'check3')==='nothing to check','...for not applicable');

// The four marks must be four DIFFERENT marks: the glyph is what survives
// greyscale, colour-blindness and a screenshot in a bug report.
const glyphs=['passed','failed','not_run','n_a'].map(s=>CHECK_STATES[s].glyph);
A(new Set(glyphs).size===4,'four states, four distinguishable glyphs');
A(CHECK_STATES.n_a.glyph!==CHECK_STATES.not_run.glyph,
  '"nothing to judge" is not "we have not looked"');
const words=['passed','failed','not_run','n_a'].map(s=>CHECK_STATES[s].word);
A(new Set(words).size===4,'four states, four distinct spoken names');

// === 3. only an executed check may be green ===
for(const state of ['failed','not_run','n_a']){
  const html=renderCheckRows(rows([state]));
  A(!seen(html).includes('✓'),'a '+state+' check must never render a tick');
  A(!html.includes('class="check-row passed"'),'a '+state+' check must never be styled passed');
}

// === 4. the fail-safe default, in every shape the payload can take ===
// A client that ships ahead of its server has to fail in the honest direction.
for(const value of ['a bare contract string','',null,undefined,0,
                    {description:'no state key'},{description:'x',state:'verified'},
                    {description:'x',state:''},{description:'x',state:null},
                    {description:'x',state:'constructor'},{description:'x',state:'toString'}]){
  const entry=checkEntry(value);
  A(entry.state==='not_run','an unrecognised state is not-run, got '+entry.state
    +' for '+JSON.stringify(value));
}

// === 5. the summary line never says more than the states it counts ===
const line=(states,audits)=>checkSummary(rows(states),audits);
A(line(['not_run','not_run','not_run','not_run'],0)===
  'Not run yet — these run automatically on your first task.','nothing run, no audits');
A(line(['not_run','not_run'],3)===
  'These run with every task; no result has been reported for the latest round.',
  'nothing reported, but rounds have happened: the line may not claim a first run');
A(line(['passed','passed','passed','passed'],3)==='All 4 checks passed on the latest round.','all passed');
A(line(['passed','failed','passed','passed'],3)==='1 of 4 checks did not pass on the latest round.','one failed');
A(line(['passed','passed','not_run','not_run'],3)==='2 of 4 checks have not run on the latest round.','two not run');
A(line(['passed','passed','passed','not_run'],3)==='1 of 4 checks has not run on the latest round.','one not run');
A(line(['passed','passed','passed','n_a'],3)==='3 checks passed, 1 had nothing to check.','one n/a');
A(line(['passed','n_a'],3)==='1 check passed, 1 had nothing to check.','singular reads as singular');
A(line([],3)==='','no checks configured says nothing at all');
// A failure outranks everything else in the ladder: it is the one a person must
// see, and it may never be hidden behind a cheerier line.
A(line(['failed','n_a','not_run','passed'],3).includes('did not pass'),
  'a failure is what the line reports when there is one');
// and the not-run count may never be reported as a pass count
A(!line(['passed','not_run'],3).includes('All '),'a partial result is never "all"');
console.log('ok');
"""


def _extract(signature: str) -> str:
    """One top-level JS definition, by brace matching from its signature."""
    start = PAGE.index(signature)
    depth, i = 0, PAGE.index("{", start)
    while i < len(PAGE):
        if PAGE[i] == "{":
            depth += 1
        elif PAGE[i] == "}":
            depth -= 1
            if depth == 0:
                # `const esc = s => ...` closes with `}));` — take the statement.
                tail = PAGE.index(";", i)
                return PAGE[start:tail + 1] if signature.startswith("const esc") \
                    else PAGE[start:i + 1]
        i += 1
    raise AssertionError(signature)


def _sources() -> str:
    return "\n".join(_extract(signature) for signature in SOURCES)


def _run(js: str) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    return subprocess.run([node, "-e", js], text=True, capture_output=True)


def _needs_node():
    if not shutil.which("node"):  # Python-only machines still run the rest.
        pytest.skip("node is not available")


def test_a_check_that_has_not_run_is_never_shown_as_passed():
    """Executes the page's own renderer; asserts over what it produces."""
    _needs_node()
    result = _run(_sources() + HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


@pytest.mark.parametrize("why,before,after", MUTATIONS,
                         ids=[m[1][:28] for m in MUTATIONS])
def test_the_guard_above_is_shown_to_fail_when_the_product_is_broken(why, before, after):
    """Ledger D10: write the guard, break the product on purpose, watch it catch.

    Each mutation is a real regression someone could ship. If the guard stays
    green against one of them it is not guarding that property, whatever its
    name says.
    """
    _needs_node()
    sources = _sources()
    assert sources.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved and this "
        f"guard is no longer known to catch it")
    result = _run(sources.replace(before, after) + HARNESS)
    assert result.returncode != 0, (
        f"MUTATION SURVIVED — {why}. The guard did not go red, so it does not "
        f"guard this. Replaced {before!r} with {after!r}.")


# --------------------------------------------------------------- ZH, executed
ZH_HARNESS = r"""
const A=(cond,msg)=>{if(!cond)throw new Error(msg);};
// SPEC-2 §5.8: no ASCII in the section line in zh. Checked by running the page's
// own translator over every line the summary can mint, not by eyeballing a dict.
const ascii=/[A-Za-z]/;
const LINES=[
  'Not run yet — these run automatically on your first task.',
  'These run with every task; no result has been reported for the latest round.',
  'All 4 checks passed on the latest round.',
  'All 1 check passed on the latest round.',
  '1 of 4 checks did not pass on the latest round.',
  '2 of 4 checks have not run on the latest round.',
  '1 of 4 checks has not run on the latest round.',
  '3 checks passed, 1 had nothing to check.',
  '1 check passed, 1 had nothing to check.',
  'No checks configured',
  'Automatic checks',
];
for(const line of LINES){
  const zh=zhValue(line);
  A(zh!==line,'untranslated in zh: '+line);
  A(!ascii.test(zh),'ASCII leaked into the zh string: '+zh+'  (from: '+line+')');
}
// The per-row accessible name keeps the check id — which is a rule id and is not
// translated — so it is asserted separately: the STATE half must be Chinese.
for(const [en,zh] of [['schema: not run yet','尚未运行'],['schema: passed','已通过'],
                      ['schema: did not pass','未通过'],['schema: nothing to check','没有可检查的内容']]){
  const got=zhValue(en);
  A(got.includes(zh),'aria-label state not translated: '+en+' -> '+got);
  A(got.startsWith('schema'),'the rule id must survive translation: '+got);
}
// SPEC-2 §4.1: the old pattern is REPLACED, not extended. If it survived, a
// caller still minting the wrong string would keep getting a confident zh
// translation of a claim we have corrected in English.
A(zhValue('8 blocker rules')==='8 blocker rules','the blocker-rules translation must be gone');
A(zhValue('8 rules')==='8 条规则','the replacement translates the string we now mint');
A(zhValue('1 rule')==='1 条规则','...in the singular too');
console.log('ok');
"""

ZH_MUTATIONS = (
    ("the section line loses its Chinese and ships English to a zh reader",
     '"Not run yet — these run automatically on your first task.":'
     '"尚未运行——它们会在你的第一个任务中自动运行。",', ""),
    ("the counted summary lines lose their Chinese",
     "[/^(\\d+) of (\\d+) checks? did not pass on the latest round\\.$/,"
     "m=>'最近一轮中有 '+m[1]+' 项检查未通过。']", "[/^__never__$/,m=>m[0]]"),
    ("the old blocker-rules pattern is left in place beside the new one",
     "[/^(\\d+) rules?$/i,m=>m[1]+' 条规则']",
     "[/^(\\d+) blocker rules?$/i,m=>m[1]+' 条阻断规则'],[/^(\\d+) rules?$/i,m=>m[1]+' 条规则']"),
)


def _block(opening: str, closing: str) -> str:
    start = PAGE.index(opening)
    end = PAGE.index(closing, start)
    return PAGE[start:end + len(closing)]


def _zh_sources() -> str:
    return "\n".join((
        _block("const ZH={", "\n};"),
        _block("const ZH_PATTERNS=[", "\n];"),
        _extract("function zhValue(value)"),
    ))


def test_every_new_verification_string_reads_in_chinese():
    """Runs zhValue over each line the summary can mint, in both directions."""
    _needs_node()
    result = _run(_zh_sources() + ZH_HARNESS)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


@pytest.mark.parametrize("why,before,after", ZH_MUTATIONS,
                         ids=[m[0][:34] for m in ZH_MUTATIONS])
def test_the_chinese_guard_is_shown_to_fail_when_a_translation_is_dropped(
        why, before, after):
    _needs_node()
    sources = _zh_sources()
    assert sources.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved")
    result = _run(sources.replace(before, after) + ZH_HARNESS)
    assert result.returncode != 0, f"MUTATION SURVIVED — {why}."


# ------------------------------------------------- structural pins (not guards)
# These assert over the page source. They cannot prove behaviour — the defect
# this slice fixes would have passed a source grep — so they exist only to pin
# wiring the executed harnesses above cannot reach. The behaviour they stand in
# for was verified by driving a live console; the numbers are in the commit.
def test_the_section_is_labelled_and_described_for_assistive_tech():
    assert 'id="runtime-checks-title">Automatic checks</div>' in PAGE
    assert '<p class="check-summary" id="runtime-checks-state"></p>' in PAGE
    assert ('<div id="runtime-checks" role="list" aria-labelledby="runtime-checks-title"'
            ' aria-describedby="runtime-checks-state"></div>') in PAGE


def test_both_constitution_mint_sites_stopped_calling_every_rule_a_blocker():
    """AUDIT_RULES.md ships 7 BLOCKER + 1 ADVISORY; the row said "8 blocker
    rules", reporting an advisory rule as gating. SPEC-2 4.1 wants
    "8 rules · 7 blocking"; the blocking half needs a server field this slice
    does not own, so the row states only what the payload knows."""
    assert "blocker rules" not in PAGE
    assert "d.rules + (d.rules===1?' rule':' rules')" in PAGE
    assert "esc(d.rules)+(d.rules===1?' rule':' rules')" in PAGE


def test_the_not_run_state_does_not_use_the_token_that_fails_contrast():
    """--text-3 measures 3.06:1 light / 3.77:1 dark on --surface. Using it for
    not-run would make the honest state the unreadable one."""
    css = PAGE[PAGE.index(".check-summary{"):PAGE.index(".mini-metrics{")]
    assert "--text-3" not in css
    assert ".check-row{" in css and "color:var(--text-2)" in css
