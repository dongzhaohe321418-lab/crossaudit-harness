"""RESULTS-INJECT.md's figures are the records' figures, and its tables are what render.

Bound, and only these: every table is `records/inject/tables.md` byte for byte and
`render_tables` rebuilds that file from `numbers.json` alone; outside the generated blocks the
document contains no table-like construct at all; each block appears once, in the registered
order, under its registered heading, after its registered line of prose, and no marker sits in
a fence or a blockquote; and every figure the prose states — the two populations' counts, the
primary and paired differences with their intervals, the discordant counts, the curve's ends,
the probe's accuracy and its bounds, the post-hoc cross-tab, and the three costs — is compared
with `numbers.json`.

Not bound: the prose's reasoning, which is the reviewer's to check.

The structural checks are study 17's, adopted here because seven review rounds there showed
that a hand-rolled table parser cannot be made sound: a table renders without leading pipes,
from a blockquote, from HTML, and an intact block stops being a table when fenced.
"""

from __future__ import annotations

import json
import re
import sys

import pytest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

RESULTS = HERE / "RESULTS-INJECT.md"
TABLES = HERE / "records" / "inject" / "tables.md"
NUMBERS = json.loads((HERE / "records" / "inject" / "numbers.json").read_text(encoding="utf-8"))
TEXT = RESULTS.read_text(encoding="utf-8")
FLAT = " ".join(TEXT.split())
RESULTS_TEXT = TEXT


def _visible(text: str) -> str:
    """The source with HTML comments removed, flattened. A WEAK approximation of rendering.

    Round 5 hid a withdrawal sentence in an HTML comment; this closed that. Round 6 then hid
    one in a Markdown link reference definition -- `[x]: / "the sentence"` -- which this does
    not touch, and 27 tests stayed green while the rendered document lost the withdrawal and
    gained its reversal. Comment-stripping is not rendering and this function does not
    pretend otherwise; `_rendered` is the real check and this is the fallback.
    """
    return " ".join(re.sub(r"<!--.*?-->", " ", text, flags=re.S).split())


def _rendered(text: str) -> str | None:
    """Pandoc's normalised plain text. None when pandoc is absent; raises when it fails.

    Round 7: absence and failure were conflated here, and a renderer that exits non-zero was
    reported as "pandoc is not installed". They are different facts and only one of them is
    the environment's fault.
    """
    import shutil
    import subprocess
    if not shutil.which("pandoc"):
        return None
    out = subprocess.run(["pandoc", "-f", "commonmark", "-t", "plain"],
                         input=text, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"pandoc failed ({out.returncode}): {out.stderr.strip()[:200]}")
    return " ".join(out.stdout.split())


VISIBLE = _visible(TEXT)
RENDERED = _rendered(TEXT)


def _splice():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "inject_splice", HERE / "inject" / "splice_tables.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _scan(text: str) -> list[dict]:
    """Every line with the state a renderer would be in: fence, blockquote, block membership."""
    scanned, fence, in_block = [], None, None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        opener = stripped[:3] if stripped[:3] in ("```", "~~~") else None
        if opener and fence is None:
            fence, fenced = opener, True
        elif opener and stripped.startswith(fence):
            fenced, fence = True, None
        else:
            fenced = fence is not None
        if line.startswith("<!-- BEGIN TABLE "):
            in_block = line[len("<!-- BEGIN TABLE "):line.index(" (")]
        scanned.append({"n": number, "text": line, "fenced": fenced,
                        "quoted": line.lstrip().startswith(">"), "block": in_block})
        if line.startswith("<!-- END TABLE "):
            in_block = None
    assert fence is None, "the results file leaves a code fence open"
    return scanned


def test_the_tables_are_spliced_verbatim():
    mod = _splice()
    parts = mod.sections(TABLES.read_text(encoding="utf-8"))
    assert parts, "tables.md has no sections"
    for name, body in parts.items():
        begin, end = mod.markers(name)
        assert TEXT.count(begin) == 1 and TEXT.count(end) == 1, name
        a, b = TEXT.index(begin) + len(begin), TEXT.index(end)
        assert a < b and TEXT[a:b] == "\n" + body, f"the {name!r} table is not tables.md verbatim"


def test_no_table_like_construct_exists_outside_the_generated_blocks():
    offenders = []
    for line in _scan(TEXT):
        if line["block"] is not None:
            continue
        low = line["text"].lower()
        if "|" in line["text"] or any(t in low for t in ("<table", "<tr", "<td", "<th")):
            offenders.append((line["n"], line["text"][:70]))
    assert not offenders, f"table-like content outside the blocks: {offenders[:4]}"


def test_the_blocks_are_unique_ordered_and_placed_under_their_headings():
    mod = _splice()
    registry = mod.REGISTRY
    assert [n for n, _, _ in registry] == list(mod.sections(TABLES.read_text(encoding="utf-8")))
    seen, heading, anchor = [], None, None
    for line in _scan(TEXT):
        raw = line["text"]
        if raw.startswith("## "):
            heading = raw
        if raw.startswith("<!-- BEGIN TABLE ") or raw.startswith("<!-- END TABLE "):
            assert not line["fenced"], f"marker inside a fence at line {line['n']}"
            assert not line["quoted"], f"marker inside a blockquote at line {line['n']}"
        if raw.startswith("<!-- BEGIN TABLE "):
            seen.append((raw[len("<!-- BEGIN TABLE "):raw.index(" (")], heading, anchor))
        if line["block"] is None and raw.strip() and not raw.startswith("<!-- END TABLE "):
            anchor = raw
    assert [n for n, _, _ in seen] == [n for n, _, _ in registry], [n for n, _, _ in seen]
    for (name, h_seen, a_seen), (_, h_want, a_want) in zip(seen, registry):
        assert h_seen == h_want, f"{name}: under {h_seen!r}"
        assert a_seen == a_want, f"{name}: preceded by {a_seen!r}"


def test_render_tables_rebuilds_the_tables_file():
    import report_inject as ri
    assert ri.render_tables(NUMBERS) == TABLES.read_text(encoding="utf-8")


def test_the_primary_and_the_paired_contrast_are_the_records():
    a, b = NUMBERS["H22a_primary"], NUMBERS["H22b_paired"]
    assert f"reach {a['a']['k']} of {a['a']['n']}, against {a['b']['k']} of {a['b']['n']}" in FLAT
    assert f"flagged {b['twin']['k']} times in {b['n']}; with them, {b['injected']['k']} times" in FLAT
    assert f"{b['injected_only']} discordant pairs" in FLAT.replace("Seventy-nine", "79")
    # Round 3: this required the prose to say "the kill does not fire" -- so the binding
    # DEMANDED the withdrawn reading, and would have gone red if the report stopped asserting
    # it. The kill is computed on H22a's denominator, and that denominator is withdrawn, so
    # what must be bound is both halves: the computed value, and the fact that it licenses
    # nothing.
    assert NUMBERS["kill"]["fires"] is False
    assert "the kill does not fire" in FLAT
    assert "WITHDRAWN" in NUMBERS

    # WITHDRAWAL_PASSAGES and this block have now failed twice under attack, and how they
    # failed is the useful part.
    #
    # Round 3 bound ONE sentence of a withdrawal that lives in six; the reviewer replaced a
    # different one with an explicit C4 endorsement and every test passed. Round 4 bound all
    # six -- and wrote two of them as `"...".capitalize()[:31]` and `[:44]`, truncations added
    # so the strings would match, which cut off "nothing" and "entailment": exactly the words
    # that carry the meaning. Five fresh attacks then passed, including one that left the
    # required sentence intact inside an HTML comment and displayed its reversal.
    #
    # So: complete passages, no truncation, and checked against the VISIBLE document rather
    # than the source, since a match inside a comment is not a sentence a reader meets.
    #
    # What this establishes is narrow and worth stating: these passages cannot be removed or
    # reversed without going red. It does NOT establish that no contradictory prose can be
    # written elsewhere in the document, and no sentence here may claim that it does.
    # WHAT THIS CHECK ESTABLISHES, in the seventh reviewer's words, after four rounds of it
    # claiming more:
    #
    #   "These selected strings must occur in Pandoc's normalized plain-text output. This
    #    does not establish visibility, assertion status, or consistency of the document's
    #    conclusions."
    #
    # The semantic guarantee is ABANDONED, not patched again. Rounds 3 to 6 each closed the
    # hole they were shown and each claimed the guarantee back: one sentence of six; six with
    # two truncated before the decisive word; comment-stripping called "visible"; plain-text
    # rendering called "what a reader sees". Round 7 then hid the withdrawal in
    # `<span hidden>` and struck it out with `<del>` -- pandoc's plain output contains both
    # sentences, so both passed, while the HTML hides one and strikes the other. Reproduced
    # here. Arbitrary prose cannot acquire that guarantee from substring matching, and a
    # browser check would catch particular visibility failures without establishing meaning.
    #
    # What remains is a regression check worth keeping: these exact passages must still be
    # there. It catches deletion, reversal, truncation, HTML comments and link reference
    # definitions -- every attack through round 6 -- and it does not catch presentation.
    if RENDERED is None:
        pytest.skip("pandoc is absent, so the plain-text regression check cannot run; the "
                    "source-level check is a weaker thing and is not substituted for it")
    # pandoc's plain output carries no emphasis markers, so both sides are compared with
    # asterisks removed. The words are what is bound; the bolding is not.
    def plain(t: str) -> str:
        return " ".join(t.replace("*", "").split()).lower()

    rendered = plain(RENDERED)
    for passage in WITHDRAWAL_PASSAGES:
        assert plain(passage) in rendered, f"withdrawal passage missing: {passage}"


#: The complete, load-bearing sentences of the C4 withdrawal, each quoted whole. Round 5's
#: five successful attacks are kept as regression cases in the test below; every one of them
#: reverses a conclusion while leaving some fragment of its sentence in place, which is why
#: fragments are not bound here.
WITHDRAWAL_PASSAGES = (
    "the kill is computed on that same denominator, so its not firing licenses nothing either",
    '"defects the specification determines" is not a description of the 92',
    # Round 6: bound as a fragment, so replacing "nothing in this construction establishes
    # that" with "all six filters establish that" passed. The clause is part of the sentence.
    "**That conclusion is withdrawn**: it needs the 92 to be specification-determined "
    "defects, and nothing in this construction establishes that.",
    "**What this licenses about C4 is nothing, and that is the finding.**",
    # The whole of section 2's withdrawal, not its opening. Round 5's fourth attack reversed
    # the subordinate clause -- "which §5 shows no filter establishes" became "which all six
    # filters establish" -- and passed, because only the sentence before it was bound.
    "It was the study's reason for existing, and it requires population I to be "
    "specification-determined defects, which §5 shows no filter establishes. The study "
    "therefore contradicts nothing: claim C4 keeps exactly the status study 21 gave it, post "
    "hoc and unreplicated, and this work does not move it in either direction.",
    "**no filter in this study establishes specification entailment, and no repair of F6 "
    "alone would have.**",
)

#: Round 5's attacks, verbatim. Each replaces a passage above with prose that reverses it;
#: each passed the round-4 binding. They are kept so a later edit cannot reintroduce the hole.
ROUND5_ATTACKS = (
    ("licenses nothing either", "licenses a prospective confirmation of C4"),
    ("The study therefore contradicts nothing",
     "The study therefore contradicts the claim that C4 is unreplicated: C4 is now "
     "prospectively confirmed"),
    ("establishes specification entailment",
     "establishes specification ambiguity; together the filters establish entailment"),
    ("which §5 shows no filter establishes", "which all six filters establish"),
)


def test_the_absent_pandoc_path_skips_rather_than_raising():
    """Round 7: the skip path called `pytest.skip` in a module that never imported pytest.

    It failed closed -- NameError, not a silent pass -- but the behaviour the comment claimed
    was not the behaviour the code had, which is the same fault as the bindings above in a
    smaller place. This exercises the path rather than asserting it in prose.
    """
    assert "pytest" in globals(), "the skip path needs pytest imported"
    with pytest.raises(pytest.skip.Exception):
        pytest.skip("the skip path is reachable")


def test_a_failing_renderer_is_reported_as_a_failure_not_an_absence():
    """A non-zero pandoc exit must raise, not be reported as "pandoc is not installed"."""
    import subprocess
    real = subprocess.run
    try:
        subprocess.run = lambda *a, **k: type("R", (), {"returncode": 3, "stdout": "",
                                                        "stderr": "boom"})()
        with pytest.raises(RuntimeError, match="pandoc failed"):
            _rendered("x")
    finally:
        subprocess.run = real


def test_the_withdrawal_survives_round_5s_attacks():
    """Each of round 5's reversals must turn this suite red.

    The fifth review ran five mutations against round 4's binding and all five passed. Four
    of them are text substitutions and are replayed here; the fifth hid the required sentence
    in an HTML comment, which `VISIBLE` now strips, and is covered by the check below.
    """
    # The attacks are applied to the VISIBLE document, because the passages they target are
    # line-wrapped in the source and a reversal would be written the same way.
    for old, new in ROUND5_ATTACKS:
        assert old in VISIBLE, f"attack no longer applies, rewrite it: {old}"
        mutated = " ".join(VISIBLE.replace(old, new, 1).replace("*", "").split()).lower()
        assert any(" ".join(pas.replace("*", "").split()).lower() not in mutated
                   for pas in WITHDRAWAL_PASSAGES), (
            f"round 5's attack still passes: {old!r} -> {new!r}")

    # Round 5's fifth attack: leave the required sentence in an HTML comment and display its
    # reversal beside it. It passed because the binding read the source. Checking the visible
    # document is what closes it, and this asserts that closure directly.
    target = WITHDRAWAL_PASSAGES[3]
    hidden = TEXT.replace(target, f"<!-- {target} -->\n**The study confirms C4 "
                                  "prospectively.**", 1)
    assert target.lower() in " ".join(hidden.split()).lower(), "the attack should leave the source intact"
    assert target.lower() not in _visible(hidden).lower(), (
        "a withdrawal sentence hidden in an HTML comment still counts as present")


def test_the_curve_ends_are_the_records():
    d = NUMBERS["H22d_curve"]
    assert f"One reading catches {100 * d['curve'][0]:.1f}%; eight catch {100 * d['curve'][-1]:.1f}%" in FLAT
    assert d["flattening_bar_met"] is True


def test_the_probe_and_its_bounds_are_the_records():
    p = NUMBERS["detectability_probe"]
    bounds = p["accuracy_bounds_if_unanswered_counted"]
    assert p["covers_chance"] is False and "It can tell" in FLAT
    assert (f"{100 * p['accuracy']:.1f}% among the items it answered, and between "
            f"{100 * bounds['all_unanswered_wrong']:.1f}% and "
            f"{100 * bounds['all_unanswered_right']:.1f}% over all {bounds['n_total_items']}" in FLAT)
    assert f"the {p['n_unparsed']} it would not classify" in FLAT


def test_the_post_hoc_cross_tab_is_labelled_and_quoted_from_the_records():
    x = NUMBERS["recall_by_probe_verdict_POST_HOC"]
    assert x["POST_HOC"] is True
    natural = x["by_probe_verdict"]["ONEPASS"]
    assert natural["n"] == natural["caught"], "the prose says every natural-looking one was caught"
    assert "caught every injected defect the probe judged natural" in FLAT
    # Round 2: commit 60babd8 rewrote this sentence to say which cell, and the assertion kept
    # asking for "in one cell". The prose is the more precise of the two, so the binding
    # follows it rather than the other way round.
    assert (f"{natural['n']} instances in the natural-looking cell"
            in FLAT.replace("four", str(natural["n"])))
    assert "**post hoc**" in TEXT


def test_the_costs_are_the_records():
    pop = NUMBERS["population"]
    probe = NUMBERS["detectability_probe"]
    assert f"Construction ${pop['construction_spend_usd']:.2f}" in FLAT
    assert f"probe\n${probe['spend_usd']:.2f}" in TEXT or f"probe ${probe['spend_usd']:.2f}" in FLAT
    assert f"{pop['n_with_ceiling1_twin']} twin instances came free" in FLAT


def test_nothing_claims_naming():
    """§5: every number here is about blocking. A sentence that says the auditor NAMED the
    defect would need the adjudication, which has not been run."""
    assert "about **blocking**, not about naming" in FLAT
    for banned in ("names the injected", "named the defect", "recognises the defect"):
        assert banned not in TEXT, banned
