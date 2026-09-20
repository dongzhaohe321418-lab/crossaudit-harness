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
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "expertlongbench"))

RESULTS = HERE / "RESULTS-INJECT.md"
TABLES = HERE / "records" / "inject" / "tables.md"
NUMBERS = json.loads((HERE / "records" / "inject" / "numbers.json").read_text(encoding="utf-8"))
TEXT = RESULTS.read_text(encoding="utf-8")
FLAT = " ".join(TEXT.split())


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
    assert NUMBERS["kill"]["fires"] is False and "the kill does not fire" in FLAT


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
