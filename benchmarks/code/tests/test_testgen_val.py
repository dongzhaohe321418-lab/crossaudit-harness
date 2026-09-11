"""Study 17's rules are pure and are tested here without the API or the executor.

What is checked: the three preregistered rules on synthetic per-candidate outcomes (§3),
the arm they imply (§5), the primary's arithmetic and the kill (§4), the selection order
for the best rule, the unique-test aggregation (§5), and the frozen seven instances of §0.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import testgen  # noqa: E402
import testgen_val as tv  # noqa: E402

RESULTS = HERE.parent / "RESULTS-TESTGEN-VAL.md"
TABLES = HERE.parent / "records" / "testgen-val" / "tables.md"


# --- the rules, per candidate (§3) ----------------------------------------------------

def test_rule_a_keeps_a_failing_test_only_when_both_other_draws_also_fail():
    assert tv.keep("A", {0, 2}, {1}, {0}) == {0, 2}
    assert tv.keep("A", {0, 2}, {1}, set()) == set()
    assert tv.keep("A", {0, 2}, set(), {0}) == set()
    assert tv.keep("A", {0, 2}, set(), set()) == set()


def test_rule_b_keeps_when_either_other_draw_fails():
    assert tv.keep("B", {3}, set(), {5}) == {3}
    assert tv.keep("B", {3}, {0}, set()) == {3}
    assert tv.keep("B", {3}, set(), set()) == set()


def test_rule_cprime_needs_a_second_failing_draw1_test_and_ignores_the_other_draws():
    assert tv.keep("Cprime", {0, 1}, set(), set()) == {0, 1}
    assert tv.keep("Cprime", {0}, {0, 1}, {0, 1}) == set()


def test_a_passing_test_is_never_decided_on_and_an_unknown_rule_is_refused():
    # nothing fails on the candidate: no rule keeps or drops anything
    for rule in tv.RULES:
        assert tv.keep(rule, set(), {0}, {0}) == set()
    try:
        tv.keep("D", {0}, {0}, {0})
    except ValueError:
        pass
    else:
        raise AssertionError("an unpreregistered rule must be refused")


def test_the_rules_never_see_the_canonical_solution():
    import inspect
    src = inspect.getsource(tv.keep)
    assert "canonical" not in src


def test_the_implied_arm_flags_on_a_kept_test_or_a_draw1_timeout():
    assert tv.flag({1}, False) and tv.flag(set(), True)
    assert not tv.flag(set(), False)


# --- the primary and the kill (§4) ------------------------------------------------------

def _row(iid, pid, f1, wrong, kept, stratum="P", half="confirm", artefact=False, classifiable=True):
    return {"instance_id": iid, "problem_id": pid, "stratum": stratum, "half": half,
            "hc_flagged": False, "artefact": artefact, "classifiable": classifiable,
            "d1": {"n_tests": 4, "failed_candidate": sorted(f1), "failed_canonical": sorted(wrong),
                   "candidate_timed_out": False},
            "kept": {"A": sorted(kept), "B": sorted(kept), "Cprime": sorted(kept)},
            "flagged": {"A": bool(kept), "B": bool(kept), "Cprime": bool(kept)}}


def test_primary_counts_wrong_among_kept_and_retention_on_the_seven(monkeypatch):
    monkeypatch.setattr(tv, "BOOTSTRAP_REPS", 200)
    rows = [
        _row("b1:p1", "p1", f1={0, 1}, wrong={1}, kept={0, 1}),      # keeps one right, one wrong
        _row("b1:p2", "p2", f1={2}, wrong=set(), kept=set()),         # drops a right test
        _row("b2:p2", "p2", f1={2}, wrong={2}, kept=set()),           # drops a wrong test
        _row("b1:p3", "p3", f1={0, 1, 2, 3}, wrong={3}, kept={0, 1, 2, 3},
             artefact=True),                                          # excluded: artefact
        _row("b1:p4", "p4", f1={0}, wrong=set(), kept={0}, classifiable=False),  # excluded
    ]
    p = tv.primary_for("A", rows, seven=["b1:p1", "b1:p2"])
    assert p["wrong_among_kept"]["k"] == 1 and p["wrong_among_kept"]["n"] == 2
    assert p["right_failing_retained"]["k"] == 1 and p["right_failing_retained"]["n"] == 2
    assert p["wrong_failing_removed"]["k"] == 1 and p["wrong_failing_removed"]["n"] == 2
    assert p["retained"] == 1 and p["retained_ids"] == ["b1:p1"]
    assert p["killed"] and p["killed_by_wrong_rate"] and p["killed_by_retention"]
    lo, hi = p["wrong_among_kept"]["wilson"]
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0


def test_the_kill_is_two_percent_or_fewer_than_five_of_seven():
    assert tv.verdict(0.02, 5) == {"killed": False, "killed_by_wrong_rate": False, "killed_by_retention": False}
    assert tv.verdict(0.021, 7)["killed_by_wrong_rate"]
    assert tv.verdict(0.0, 4)["killed_by_retention"]
    assert tv.verdict(None, 7)["killed"] is False       # nothing kept: no rate to exceed


def test_best_rule_is_the_lowest_wrong_rate_among_those_retaining_five_then_ties_by_order():
    per = {"A": {"rate": 0.01, "retained": 5, "killed": False},
           "B": {"rate": 0.03, "retained": 7, "killed": True},
           "Cprime": {"rate": 0.128, "retained": 5, "killed": True}}
    assert tv.select_best(per) == ("A", True)
    per["A"]["retained"] = 4
    per["A"]["killed"] = True
    assert tv.select_best(per) == ("B", False)           # B retains, but is killed on the rate
    per["B"]["rate"] = 0.128
    assert tv.select_best(per) == ("B", False)           # tie on rate: higher retention wins
    per["B"]["retained"] = 5
    assert tv.select_best(per) == ("B", False)           # still tied: B before Cprime
    for r in per.values():
        r["retained"] = 3
    assert tv.select_best(per) == ("A", False)           # none reaches 5: highest retention, ties by order


# --- the unique-test aggregation (§5) ---------------------------------------------------

def test_unique_level_keeps_a_test_that_passes_everywhere_and_a_test_kept_anywhere(monkeypatch):
    monkeypatch.setattr(tv, "BOOTSTRAP_REPS", 200)
    rows = [_row("b1:p1", "p1", f1={0}, wrong={0, 3}, kept=set()),
            _row("b2:p1", "p1", f1={0, 1}, wrong={0, 3}, kept={0, 1})]
    u = tv.unique_level("A", rows)
    # four tests: 0 (wrong, fails on both, kept on b2), 1 (right, fails on b2, kept),
    # 2 (right, passes everywhere), 3 (wrong, passes everywhere — no signal)
    assert u["all_classifiable_tests"] == 4 and u["kept"] == 4
    assert u["wrong_among_kept_all"]["k"] == 2
    assert u["exposed_tests"] == 2 and u["wrong_among_kept_exposed"]["k"] == 1
    assert u["wrong_among_kept_exposed"]["n"] == 2


# --- the frozen inputs (§0) -------------------------------------------------------------

def test_the_seven_validated_only_instances_are_the_preregistered_ones():
    seven = tv.validated_only(testgen.load_rows())
    assert seven == ["b1:HumanEval/154", "b1:Mbpp/261", "b1:Mbpp/297", "b1:Mbpp/589",
                     "b1:Mbpp/594", "b2:Mbpp/559", "b2:Mbpp/594"]


def test_the_comparator_on_the_frozen_record_is_the_preregistered_baseline():
    """§3: C′ keeps 86 failing applications, 11 wrong, and retains 5 of 7 — before any draw."""
    d1 = testgen.load_rows()
    kept = wrong = retained = 0
    seven = set(tv.validated_only(d1))
    for r in d1.values():
        if r["canonical_unusable"] or tv.is_artefact(r):
            continue
        f1, w = set(r["failed_candidate"]), set(r["failed_canonical"])
        k = tv.keep("Cprime", f1, set(), set())
        kept += len(k)
        wrong += len(k & w)
        if r["instance_id"] in seven and (k - w):
            retained += 1
    assert (kept, wrong, retained) == (86, 11, 5)


def test_normalised_source_ignores_whitespace_and_quotes():
    assert tv.normalised("assert f( 1 )=='a'") == tv.normalised('assert f(1) == "a"')
    assert tv.normalised("assert f(1) == 'a'") != tv.normalised("assert f(2) == 'a'")


# --- the results file says what the records say (§1's table, verdicts, draws, ledger) ------

def test_results_headline_figures_are_the_records():
    import json
    import re
    numbers = json.loads((HERE.parent / "records" / "testgen-val" / "numbers.json").read_text(encoding="utf-8"))
    text = (HERE.parent / "RESULTS-TESTGEN-VAL.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())          # the prose wraps; the figures do not
    # §1's and §3's tables are generated and bound byte for byte below; the prose is bound here.
    assert numbers["decision"]["H17"] == "KILL" and "H17 is KILLED" in flat
    assert numbers["decision"]["best_rule"] == "A"
    assert "best-performing rule by the preregistered order is A" in flat
    for k in (2, 3):
        d = numbers[f"draw{k}"]
        assert f"**{d['unique_wrong']} wrong = {100 * d['rate']:.1f}%**" in flat
        assert f"{d['tests_total']:,} tests" in flat
    ledger = numbers["ledger"]["by_run_id"]
    total = sum(v["usd"] for v in ledger.values())
    assert f"**${total:.4f} in total**" in flat
    for rid, v in ledger.items():
        assert f"`{rid}` {v['calls']} calls, ${v['usd']:.4f}" in flat
    assert numbers["prompt_mismatches"] == 0
    assert not re.search(r"assert \w+\(", text), "no generated test text in the results file"


def _splice():
    import importlib.util
    spec = importlib.util.spec_from_file_location("splice_tables", HERE.parent / "testgen" / "splice_tables.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _scan(text: str) -> list[dict]:
    """Every line with the state a renderer would be in: fence, blockquote, block membership.

    Round 6 retired the "does the line start with a pipe" check: a table renders from a
    pipeline without leading pipes, from a blockquote, from HTML, and an intact block
    stops being a table when fenced. What the scan below supports is a stronger claim —
    outside the generated blocks the document contains no table-like construct AT ALL, and
    no marker sits anywhere a renderer would treat as code or as a quotation.
    """
    scanned, fence, in_block = [], None, None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        opener = stripped[:3] if stripped[:3] in ("```", "~~~") else None
        if opener and fence is None:
            fence = opener
            fenced = True                      # the fence line itself belongs to the fence
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
    """Every table in the results file is `records/testgen-val/tables.md`, byte for byte."""
    mod = _splice()
    text = RESULTS.read_text(encoding="utf-8")
    parts = mod.sections(TABLES.read_text(encoding="utf-8"))
    assert parts, "tables.md has no <!-- TABLE name --> sections"
    for name, body in parts.items():
        begin, end = mod.markers(name)
        assert text.count(begin) == 1 and text.count(end) == 1, f"marker pair for {name!r} is not unique"
        a, b = text.index(begin) + len(begin), text.index(end)
        assert a < b, f"markers for {name!r} are out of order"
        assert text[a:b] == "\n" + body, f"the {name!r} table is not tables.md verbatim"


def test_no_table_like_construct_exists_outside_the_generated_blocks():
    """(1) Outside the blocks: no pipe, no HTML table, no quoted or fenced table."""
    text = RESULTS.read_text(encoding="utf-8")
    offenders = []
    for line in _scan(text):
        if line["block"] is not None:
            continue
        low = line["text"].lower()
        if "|" in line["text"] or any(tag in low for tag in ("<table", "<tr", "<td", "<th")):
            offenders.append((line["n"], line["text"][:70]))
    assert not offenders, f"table-like content outside the generated blocks: {offenders[:4]}"


def test_the_generated_blocks_are_unique_ordered_and_placed_under_their_headings():
    """(2) Each block appears once, in the registered order, under its registered heading,
    after its registered anchor line; (3) no marker sits in a fence or a blockquote."""
    mod = _splice()
    text = RESULTS.read_text(encoding="utf-8")
    registry = mod.REGISTRY
    parts = mod.sections(TABLES.read_text(encoding="utf-8"))
    assert [name for name, _, _ in registry] == list(parts), "registry and tables.md disagree"

    scanned = _scan(text)
    seen, heading, anchor = [], None, None
    for line in scanned:
        raw = line["text"]
        if raw.startswith("## "):
            heading = raw
        if raw.startswith("<!-- BEGIN TABLE ") or raw.startswith("<!-- END TABLE "):
            assert not line["fenced"], f"a marker sits inside a code fence at line {line['n']}"
            assert not line["quoted"], f"a marker sits inside a blockquote at line {line['n']}"
        if raw.startswith("<!-- BEGIN TABLE "):
            seen.append((raw[len("<!-- BEGIN TABLE "):raw.index(" (")], heading, anchor))
        if line["block"] is None and raw.strip() and not raw.startswith("<!-- END TABLE "):
            anchor = raw                      # the last non-blank prose line before a marker

    assert [name for name, _, _ in seen] == [name for name, _, _ in registry], (
        f"blocks appear as {[n for n, _, _ in seen]}, registered order is {[n for n, _, _ in registry]}")
    for (name, heading_seen, anchor_seen), (_, heading_want, anchor_want) in zip(seen, registry):
        assert heading_seen == heading_want, f"{name}: under {heading_seen!r}, registered {heading_want!r}"
        assert anchor_seen == anchor_want, f"{name}: preceded by {anchor_seen!r}, registered {anchor_want!r}"
    for name, _, _ in registry:
        begin, end = mod.markers(name)
        assert text.count(begin) == 1 and text.count(end) == 1, f"{name}: markers are not unique"


def test_render_tables_reproduces_the_tables_file():
    """`render_tables` rebuilds tables.md from numbers.json and exploratory.json exactly."""
    import json
    numbers = json.loads((HERE.parent / "records" / "testgen-val" / "numbers.json").read_text(encoding="utf-8"))
    exploratory = json.loads((HERE.parent / "records" / "testgen-val" / "exploratory.json").read_text(encoding="utf-8"))
    assert tv.render_tables(numbers, exploratory) == TABLES.read_text(encoding="utf-8")


def test_the_exploratory_prose_outside_the_tables_is_bound():
    """What §3 says in prose about the record — the parts no table carries."""
    import json
    record = json.loads((HERE.parent / "records" / "testgen-val" / "exploratory.json").read_text(encoding="utf-8"))
    flat = " ".join(RESULTS.read_text(encoding="utf-8").split())
    # C′ is A's block in every column, in the record and in the prose
    assert record["rules"]["Cprime"]["wrong_among_kept_P_and_C"] == record["rules"]["A"]["wrong_among_kept_P_and_C"]
    assert "C′'s row is A's row in every column" in flat
    # C′ consults no other draw, so the corroboration quantity is undefined for it
    assert "corroborated_only_by_wrong_tests" not in record["rules"]["Cprime"]
    assert "C′ consults no other draw, so the quantity is not defined for it" in flat
    # B's additions over A reconcile the two counts, and are stated
    additions = record["B_minus_A_by_half_stratum"]
    assert sum(additions.values()) == (record["rules"]["B"]["kept_wrong_applications"]
                                       - record["rules"]["A"]["kept_wrong_applications"])
    assert ", ".join(f"{k} {v}" for k, v in additions.items()) == "confirm-C 1, confirm-P 2, explore-C 1"
    assert "B's four additions over A are confirm-C 1, confirm-P 2 and explore-C 1" in flat
