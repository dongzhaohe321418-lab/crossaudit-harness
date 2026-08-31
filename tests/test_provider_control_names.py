"""SPEC-13 — the provider controls have names, and the names are per-provider.

**Where the real guards live, and why they are not here.** SPEC-13 §4 is
explicit: the guards must locate controls **by role and accessible name**, and
forbids "any CSS selector plus an attribute assertion" — that is the check that
passes while the person fails, and it is the shape the spec exists to stop. An
`aria-labelledby` pointing at a missing id yields an EMPTY accessible name: it
looks correct in a diff and finds nothing at runtime, for a test and for a
person alike.

An accessible name is computed by the browser, so G1–G7 are driven in Chromium
against its own accessibility tree and live in
`_ui_findings/spec13/browser_spec13.mjs`, with the mutation runner beside them
(`mutate.py`).

**G8 IS DELETED, and what subsumes it.** This module used to guard eight
properties and claim all eight were mutation-proven. G8 — no two CONSECUTIVE tab
stops share an accessible name — was **established by G2**, which fails on the
same mutation. G2 asserts that the number of distinct accessible names equals
the number of controls, so ANY two controls sharing a name reddens it, adjacent
or not. Every state G8 rejected, G2 already rejects, and no mutation can redden
G8 while leaving G2 green.

So the separate assertion added a NAME, not coverage — and a name is worse than
nothing here, because a reader auditing by this module's claims ticked G8 off
and moved on. Removing it makes the remaining seven claims true rather than
making an eighth defensible.

**The subsumption is executed, not argued.** G8's specified mutation — remove the
group labelling and the per-control names together — is KEPT in the mutation
runner and filed under G2, and G2 reddens on it. A subsumption that is asserted
rather than run is a hole with an argument in front of it.

**Which seam each guard stops at, stated rather than implied.** A suite's
verdict is a claim about the seam it stops at — thirty streaming tests passed
while a page registered no listener, because they stopped at the transport.
G1/G2/G3 query Chromium's accessibility tree (`Accessibility.queryAXTree`,
`getByRole({name})`). G7 does now too, and did NOT at first: it read the status
badge's `textContent` and called that the accessible name. The two coincide for
a plain span, so it passed — for the wrong reason, and it would have kept
passing if the badge were hidden from assistive technology, given an overriding
`aria-label`, or replaced by a CSS `::before`. A mutation now pins the
difference: `aria-hidden="true"` on the badge leaves the text in the DOM and
turns G7 red, which the textContent version could not have done.

G5 asserts what the live region CONTAINS after an action — one announcement,
naming the provider — not how many regions exist. Empty regions prove wiring,
not speech.

**What this file is.** The regression guard for the parts that are decidable
from the source without a browser, named for what they actually check:

1. the page emits a DISTINCT name per (control, provider) — the composition,
   not the computation;
2. every id an `aria-labelledby` points at is emitted by the same row — idref
   resolution over the rendered markup, which is the runtime trap G3 names;
3. the names TRANSLATE, because they are composed and therefore need pattern
   entries — a fixed entry would translate only the providers that happen to be
   in the dictionary;
4. the final button never carries the `disabled` attribute, because `disabled`
   takes the reason out of reach along with the control.

It does NOT claim to check accessible names. That claim belongs to the drive.
"""
import json
import re
import shutil
import subprocess

import pytest

from crossaudit.console.page import PAGE

# Deliberately includes a provider whose label is two words and one whose label
# differs from its slug, because those are the cases a fixed dictionary entry
# silently drops.
VENDORS = {
    "openai": "OpenAI", "qwen": "Alibaba Qwen", "anthropic": "Anthropic",
    "mistral": "Mistral AI", "zhipu": "Zhipu GLM", "xai": "xAI",
}
ACTIONS = ("paste", "clear", "validate", "reveal", "replace", "remove")


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


def _needs_node():
    if not shutil.which("node"):
        pytest.skip("node is not available")


def _run(js):
    return subprocess.run([shutil.which("node"), "-e", js], text=True,
                          capture_output=True)


def _locale_sources():
    script = _script()
    return script[script.index("const ZH={"):script.index("function applyLocale(")]


def _label_sources():
    script = _script()
    head = script.index("const FR_KEY_ACTIONS=")
    return script[head:script.index("function frProvRow(")]


def test_every_control_gets_a_distinct_name_per_provider():
    """The composition. Ten providers times six controls must produce sixty
    different strings — the arithmetic G2 enforces on the computed names, done
    here on the emitted ones so a regression is caught without a browser."""
    _needs_node()
    js = _label_sources() + """
const A=(c,m)=>{if(!c)throw new Error(m);};
const VENDORS=%s, ACTIONS=%s;
const names=[];
for(const label of Object.values(VENDORS))
  for(const action of ACTIONS)names.push(frKeyLabel(action,label));
A(new Set(names).size===names.length,
  'names collide: '+JSON.stringify(names.filter((n,i)=>names.indexOf(n)!==i)));
for(const label of Object.values(VENDORS))
  for(const action of ACTIONS)
    A(frKeyLabel(action,label).includes(label),
      action+' does not name its provider: '+frKeyLabel(action,label));
console.log('ok');
""" % (json.dumps(VENDORS), json.dumps(list(ACTIONS)))
    result = _run(js)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_every_composed_name_translates_rather_than_falling_back_to_english():
    """Composed strings need PATTERN entries. A fixed entry translates only the
    providers somebody remembered to list, which is the i18n form of the silent
    gap — and it fails for exactly the providers a Chinese reader is most likely
    to be using."""
    _needs_node()
    js = _locale_sources() + _label_sources() + """
const A=(c,m)=>{if(!c)throw new Error(m);};
const VENDORS=%s, ACTIONS=%s;
const VERBS=['Paste','Clear','Validate','Reveal','Replace','Remove'];
for(const label of Object.values(VENDORS))
  for(const action of ACTIONS){
    const en=frKeyLabel(action,label),zh=zhValue(en);
    A(zh!==en,'not translated at all: '+en);
    A(zh.includes(label),'the provider name must survive translation: '+zh);
    for(const verb of VERBS)
      A(!zh.includes(verb),'English verb survived into '+zh);
    A(!/\\bkey\\b/.test(zh),'the English word key survived into '+zh);}
// The four outcome sentences and the checking line, same rule.
for(const label of Object.values(VENDORS))
  for(const en of [label+' key verified.',
                   label+' key rejected. Check it and try again.',
                   label+' key works, but no models are available to it.',
                   'Could not reach '+label+'. Check your connection and try again.',
                   'Checking '+label+' key…']){
    const zh=zhValue(en);
    A(zh!==en,'not translated at all: '+en);
    A(zh.includes(label),'the provider name must survive: '+zh);
    A(!/[A-Za-z]{2,}/.test(zh.split(label).join(' ')),
      'English prose survived into '+zh);}
console.log('ok');
""" % (json.dumps(VENDORS), json.dumps(list(ACTIONS)))
    result = _run(js)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_every_idref_the_row_emits_is_emitted_by_the_same_row():
    """G3's trap, resolved over the rendered markup rather than asserted as an
    attribute: `aria-labelledby` pointing at an id nothing emits computes to an
    empty name. This renders a row and RESOLVES the references."""
    _needs_node()
    row = _extract("function frProvRow(vendor,p)")
    js = _label_sources() + row + """
const A=(c,m)=>{if(!c)throw new Error(m);};
globalThis.esc=s=>String(s??'').replace(/[&<>"']/g,c=>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const html=frProvRow('qwen',{label:'Alibaba Qwen',console_url:'https://x',docs_url:'https://y'});
const ids=new Set([...html.matchAll(/\\bid="([^"]+)"/g)].map(m=>m[1]));
const refs=[...html.matchAll(/aria-labelledby="([^"]+)"/g)].flatMap(m=>m[1].split(/\\s+/));
A(refs.length>=2,'the row must actually use aria-labelledby, found '+refs.length);
for(const ref of refs)
  A(ids.has(ref),'aria-labelledby points at an id this row never emits: '+ref
    +' (emitted: '+[...ids].join(', ')+')');
A(html.includes('role="group"'),'the row is a named group');
console.log('ok');
"""
    result = _run(js)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_the_final_button_is_never_removed_from_the_tab_order():
    """`disabled` removes the control from the tab order, so the on-screen
    reason is unreachable WITH it. The person meets a stage they cannot complete
    and nothing tells them why."""
    body = _extract("function frSetContinue(enabled,reasonId)")
    assert "cont.disabled=false;" in body
    assert "cont.disabled=!enabled" not in body
    assert "aria-disabled" in body and "aria-describedby" in body
    # ...and every caller goes through it, so there is one mechanism.
    first_run = PAGE[PAGE.index("function setFirstRunStep("):]
    assert "fr-continue').disabled=" not in first_run
    assert "cont.disabled=true" not in first_run
    # aria-disabled does not stop a click, so the handler must decline.
    handler = PAGE[PAGE.index("document.getElementById('fr-continue').onclick"):]
    assert "if(frContinueBlocked())return;" in handler[:400]


def test_the_onboarding_footer_does_not_break_chinese_mid_character():
    """SPEC-13 §6.5 and SPEC-12 §8.4. Measured at 390 in zh: 返回 and 继续 each
    occupied TWO line boxes, breaking between characters; English was one line
    at every width. `nowrap` closes it and this pins it.

    A min-width is NOT added. The spec calls it "the shared nowrap + min-width
    rule", but no number is specified anywhere and `nowrap` alone closes the
    defect that was actually observed. Inventing a width would be an implementer
    making a layout decision it does not own.
    """
    for selector in (".fr-back{", ".fr-primary{"):
        rule = PAGE[PAGE.index(selector):]
        rule = rule[:rule.index("}")]
        assert "white-space:nowrap" in rule, (
            f"{selector} may wrap, and in Chinese that breaks between characters")


def test_the_stage_has_no_control_left_sharing_one_name_across_providers():
    """The per-row links were NOT in SPEC-13 §3.1 and carried the same defect:
    ten identical `Get key ↗` and ten identical `API docs ↗`. They are in scope
    because G2 is arithmetic, and arithmetic does not care what the table
    listed. This pins them so they cannot quietly go back."""
    row = PAGE[PAGE.index("function frProvRow(vendor,p){"):]
    row = row[:row.index("\nfunction renderFirstRunProviders(")]
    for markup in ("Get key ↗</a>", "API docs ↗</a>"):
        assert markup in row
    assert "esc('Get key — '+label)" in row
    assert "esc('API docs — '+label)" in row
    # And the placeholder is still there: it is a useful sighted affordance, it
    # is simply not a name.
    assert 'placeholder="Paste your API key"' in row
