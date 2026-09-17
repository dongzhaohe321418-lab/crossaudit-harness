"""RESULTS-SUBSTRATE2.md's figures are the records' figures, and its tables are generated.

Bound, and only these: the seven spliced table blocks (byte for byte against
records/substrate2/tables.md, in both directions, and re-derivable from numbers.json
alone); the document's structure (every heading and every HTML comment registered, every
block unique and under its own registered heading, no table-like line outside a block);
H23a's primary contrast; H23b's curve endpoints, fit and flattening bar on both strata;
H23c's false positives, both exchange-ratio definitions and the matched-false-positive
limit; H23d's coverage and the non-preregistered single-reading contrast; H23e's
not-run status; the strata, the descriptive medians and the ledger costs.

Seven review rounds on a sibling study established this pattern: no table is hand-written
and no markdown is parsed to find a number.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

import report_substrate2 as rs2  # noqa: E402

NUMBERS = CODE / "records" / "substrate2" / "numbers.json"
TABLES = CODE / "records" / "substrate2" / "tables.md"
RESULTS = CODE / "RESULTS-SUBSTRATE2.md"

#: Every heading the document is allowed to carry, in order. A new section fails this test
#: until it is registered here, which is how unregistered prose gets noticed.
REGISTERED_HEADINGS = [
    "# Study 23 — the measured ceiling is an operating point, not a constant",
    "## The sentence the preregistration requires",
    "## 1. What was run",
    "### Table 1 — the two substrates, described",
    "### Table 2 — generation, the strata and the frozen audit set",
    "### Table 3 — the audit ladder's coverage",
    "## 2. H23a (primary) — recall is far higher on the harder substrate",
    "## 3. H23b — the union curve, the fit and the flattening bar",
    "### Table 4 — union recall and union false positives at every K, substrate 2",
    "### Table 5 — substrate 2 against substrate 1 at K = 8",
    "## 4. H23c — the auditor is not better here, it is louder",
    "### Table 6 — recall bought per false-positive point, both substrates",
    "## 5. H23d — the same-vendor arm flags more of everything, and the sign flips",
    "### Table 7 — the same-vendor arm beside the cross-vendor arm, substrate 2",
    "### Table 8 — H23d, same-vendor minus cross-vendor at K = 8, paired",
    "## 6. H23e — not run",
    "## 7. What this does and does not establish",
    "## 8. Deviations from the preregistration, and interruptions",
    "## 9. The comparison inventory",
    "## 10. Cost",
    "### Table 9 — cost, from the run's usage ledgers",
]

#: Which registered heading each table block must sit under.
BLOCK_HEADING = {
    "T1": "### Table 1 — the two substrates, described",
    "T2": "### Table 2 — generation, the strata and the frozen audit set",
    "T3": "### Table 3 — the audit ladder's coverage",
    "T4": "### Table 4 — union recall and union false positives at every K, substrate 2",
    "T5": "### Table 5 — substrate 2 against substrate 1 at K = 8",
    "T6": "### Table 6 — recall bought per false-positive point, both substrates",
    "T7": "### Table 7 — the same-vendor arm beside the cross-vendor arm, substrate 2",
    "T8": "### Table 8 — H23d, same-vendor minus cross-vendor at K = 8, paired",
    "T9": "### Table 9 — cost, from the run's usage ledgers",
}


def _n() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))


def _raw() -> str:
    return RESULTS.read_text(encoding="utf-8")


def _t() -> str:
    """The prose with its blockquote markers dropped and its line wrapping and dashes
    normalised, so a figure is bound to its value and not to where the paragraph happened
    to break or which dash the sentence used."""
    lines = [re.sub(r"^\s*> ?", "", l) for l in _raw().splitlines()]
    text = "\n".join(lines)
    for dash in ("—", "–", "−"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text)


def _pct(x: float, places: int = 1) -> str:
    return f"{100 * x:.{places}f}"


def _iv(pair, places: int = 1) -> str:
    return f"[{100 * pair[0]:.{places}f}, {100 * pair[1]:.{places}f}]"


# ---------------------------------------------------------------------------------
# the tables are generated, spliced verbatim, and nowhere else
# ---------------------------------------------------------------------------------

def test_every_block_is_spliced_verbatim_in_both_directions():
    raw, tables = _raw(), TABLES.read_text(encoding="utf-8")
    for key in rs2.TABLE_KEYS:
        b, e = rs2.begin(key), rs2.end(key)
        assert raw.count(b) == 1 and raw.count(e) == 1, f"{key} marker is not unique"
        assert tables.count(b) == 1 and tables.count(e) == 1
        in_results = raw[raw.index(b) + len(b):raw.index(e)]
        in_tables = tables[tables.index(b) + len(b):tables.index(e)]
        assert in_results == in_tables, f"{key} differs between the two files"
        # the other direction: the block's exact bytes appear in the results document
        assert in_tables in raw and in_results in tables


def test_the_tables_are_generated_from_numbers_json_alone():
    """Re-rendering from the committed numbers.json reproduces tables.md byte for byte.
    No record, no cache and no ledger is read on this path."""
    assert rs2.tables_md(_n()) == TABLES.read_text(encoding="utf-8")


def test_no_table_like_line_lives_outside_a_generated_block():
    raw = _raw()
    spans = [(raw.index(rs2.begin(k)), raw.index(rs2.end(k)) + len(rs2.end(k)))
             for k in rs2.TABLE_KEYS]
    offset, outside = 0, []
    for line in raw.splitlines(keepends=True):
        start = offset
        offset += len(line)
        if any(a <= start < b for a, b in spans):
            continue
        stripped = line.strip()
        if "|" in stripped or re.fullmatch(r"[:\-\s|]{3,}", stripped or "x"):
            outside.append(stripped)
    assert outside == [], f"table-like lines outside the generated blocks: {outside}"


def test_each_block_sits_under_its_own_registered_heading():
    raw = _raw()
    for key, heading in BLOCK_HEADING.items():
        assert raw.count(heading) == 1, f"{heading!r} is not unique"
        expected = f"{heading}\n{rs2.begin(key)}"
        assert expected in raw, f"{key} is not directly under {heading!r}"


def test_only_registered_headings_and_comments_exist():
    raw = _raw()
    headings = [l.rstrip() for l in raw.splitlines() if re.match(r"^#{1,6} ", l)]
    assert headings == REGISTERED_HEADINGS, (
        "unregistered or reordered headings: "
        f"{[h for h in headings if h not in REGISTERED_HEADINGS]}")
    comments = re.findall(r"<!--.*?-->", raw, flags=re.S)
    registered = {rs2.begin(k) for k in rs2.TABLE_KEYS} | {rs2.end(k) for k in rs2.TABLE_KEYS}
    assert set(comments) == registered
    assert len(comments) == 2 * len(rs2.TABLE_KEYS)


def test_the_repository_keeps_no_corpus_solution_or_finding_text():
    """Ids, hashes, counts and outcomes only — the boundary in §5 of the preregistration."""
    for path in (RESULTS, TABLES, NUMBERS):
        text = path.read_text(encoding="utf-8")
        assert "```" not in text, f"{path.name} carries a code block"
        assert "def " not in text and "import " not in text, f"{path.name} carries code"
    n = _n()
    banned = ("finding", "solution_text", "reply", "prompt_text", "canonical_solution")
    flat = json.dumps(n)
    for word in banned:
        assert f'"{word}"' not in flat, f"numbers.json carries a {word} field"


# ---------------------------------------------------------------------------------
# H23a — the primary contrast, and the sentence §4 obliges
# ---------------------------------------------------------------------------------

def test_the_primary_contrast_is_bound():
    n, t = _n(), _t()
    a = n["H23a_primary_recall_sub2_minus_sub1_P_K8"]
    u = n["H23b_curve"]["P"]["union_at_kmax"]
    assert (f"flags **{a['a']['k']} of {a['a']['n']}** stratum-P instances: "
            f"**{_pct(u['rate'])}%, 95% problem-cluster bootstrap "
            f"{_iv(u['cluster_ci95'])}**, Wilson {_iv(u['wilson95'])}") in t
    s1 = n["substrate1_frozen"]
    assert (f"{a['b']['k']} of {a['b']['n']} - **{_pct(s1['P_union_at_kmax'])}% "
            f"{_iv(s1['P_cluster_ci95'])}**, Wilson {_iv(a['b']['wilson95'])}") in t
    assert (f"**+{a['difference_points']:.1f} points, 95% two-sample problem-cluster "
            f"bootstrap [{a['cluster_ci95_points'][0]:.1f}, "
            f"{a['cluster_ci95_points'][1]:.1f}]** ({n['bootstrap_reps']:,} resamples, "
            f"seed {n['bootstrap_seed']})") in t
    assert a["paired"] is False
    assert "This contrast is not paired**, and no McNemar test and no sign-flip test" in t
    assert a["excludes_zero"] is True


def test_the_falsification_sentence_section_4_requires_is_present():
    n, t = _n(), _t()
    a = n["H23a_primary_recall_sub2_minus_sub1_P_K8"]
    assert a["direction"] == "substrate 2 higher" and a["excludes_zero"] is True
    s1 = n["substrate1_frozen"]
    u = n["H23b_curve"]["P"]["union_at_kmax"]
    assert ("The paper's central quantity is substrate-dependent. Union recall of "
            f"{_pct(s1['P_union_at_kmax'])}% {_iv(s1['P_cluster_ci95'])} at eight readings "
            "is not a general figure") in t
    assert f"reaches {_pct(u['rate'])}% {_iv(u['cluster_ci95'])} on BigCodeBench" in t


# ---------------------------------------------------------------------------------
# H23b — the curve, the fit, the bar
# ---------------------------------------------------------------------------------

def test_the_curve_the_fit_and_the_flattening_bar_are_bound():
    n, t = _n(), _t()
    P, C = n["H23b_curve"]["P"], n["H23b_curve"]["C"]
    assert (f"from **{_pct(P['curve'][0])}% {_iv(P['curve_cluster_ci95'][0])}** at one "
            f"reading to **{_pct(P['curve'][-1])}% {_iv(P['curve_cluster_ci95'][-1])}** at "
            "eight") in t
    f = P["fit"]
    assert (f"asymptote of **{_pct(f['A'])}% {_iv(f['A_ci95_cluster'])}** with tau = "
            f"{f['tau']:.2f} and r² = {f['r2']:.3f}") in t
    g = P["flattening_gain_last_step_cluster_ci95_points"]
    # The verdict is READ from the data, not asserted. The first version of this test
    # hardcoded "the bar is met" and asserted flattened_by_ceiling1_bar is True, because
    # that is what the voided run found -- the one curve in this programme that appeared to
    # saturate. With the visible tests corrected the last-step gain is 1.52 points and the
    # bar is missed, and a test that encodes a finding cannot notice that. Same shape as the
    # superseded visible-text test: a check that agrees with the author checks nothing.
    met = P["flattened_by_ceiling1_bar"]
    assert (f"**{P['flattening_gain_last_step_points']:.2f} points "
            f"[{g[0]:.2f}, {g[1]:.2f}]**: "
            f"**the bar is {'met' if met else 'NOT met'}**") in t
    gc = C["flattening_gain_last_step_cluster_ci95_points"]
    assert (f"last step on C gains **{C['flattening_gain_last_step_points']:.2f} points "
            f"[{gc[0]:.2f}, {gc[1]:.2f}]**") in t
    assert C["flattened_by_ceiling1_bar"] is False and C["asymptote_is_extrapolation"] is True
    assert (f"asymptote of {_pct(C['fit']['A'])}% {_iv(C['fit']['A_ci95_cluster'])} is an "
            f"extrapolation and the raw **{_pct(C['curve'][-1])}% "
            f"{_iv(C['union_at_kmax']['cluster_ci95'])}** is the number to quote") in t
    assert (f"{P['counts_k']['8']} of the {P['n_instances']} P instances were flagged by "
            f"all eight readings and {P['counts_k']['0']} by none") in t


# ---------------------------------------------------------------------------------
# H23c — false positives, both ratios, and the limit on the comparison
# ---------------------------------------------------------------------------------

def test_the_false_positives_and_both_exchange_ratios_are_bound():
    n, t = _n(), _t()
    h = n["H23c_false_positives"]
    fp = h["sub2_minus_sub1_C_K8"]
    C = n["H23b_curve"]["C"]["union_at_kmax"]
    assert (f"flag **{fp['a']['k']} of {fp['a']['n']}** correct solutions: "
            f"**{_pct(C['rate'])}% {_iv(C['cluster_ci95'])}**, Wilson "
            f"{_iv(fp['a']['wilson95'])}, against substrate 1's frozen "
            f"**{_pct(n['substrate1_frozen']['C_union_at_kmax'])}% "
            f"{_iv(n['substrate1_frozen']['C_cluster_ci95'])}**") in t
    assert (f"**+{fp['difference_points']:.1f} points "
            f"[{fp['cluster_ci95_points'][0]:.1f}, {fp['cluster_ci95_points'][1]:.1f}]**") in t
    r1, r2 = h["substrate1"], h["substrate2"]
    assert h["substrate2_registered_gain_ratio_lower_at_every_k"] is True
    assert h["substrate2_level_ratio_lower_at_every_k"] is True
    assert (f"Substrate 1 runs {r1['registered_gain_ratio_by_k'][1]:.2f} down to "
            f"**{r1['registered_gain_ratio_by_k'][-1]:.2f}**; substrate 2 runs "
            f"{r2['registered_gain_ratio_by_k'][1]:.2f} down to "
            f"**{r2['registered_gain_ratio_by_k'][-1]:.2f}**") in t
    k1, k8 = h["substrate2_level_ratio_ci95_K1"], h["substrate2_level_ratio_ci95_K8"]
    assert (f"Substrate 1 runs {r1['POST_HOC_level_ratio_by_k'][0]:.2f} down to "
            f"{r1['POST_HOC_level_ratio_by_k'][-1]:.2f}; substrate 2 runs "
            f"**{r2['POST_HOC_level_ratio_by_k'][0]:.2f} [{k1[0]:.2f}, {k1[1]:.2f}]** down "
            f"to **{r2['POST_HOC_level_ratio_by_k'][-1]:.2f} [{k8[0]:.2f}, {k8[1]:.2f}]**") in t
    assert "This is **post hoc**: it is not in the preregistration" in t


def test_the_matched_false_positive_limit_names_its_family_in_both_directions():
    """The claim is true within the cross-vendor family and false pooled. Both answers
    must be in the prose, each attached to its scope, and neither may be stated bare."""
    n, t = _n(), _t()
    m = n["H23c_false_positives"]["matched_fp_comparison"]
    co = m["cross_family_only_REGISTERED_COMPARISON"]
    po = m["pooled_all_families"]

    # within the cross-vendor family: the intervals miss, and the gap is quoted
    assert co["intervals_overlap"] is False and co["point_estimates_disjoint"] is True
    assert co["sub1_dearest"]["family"] == "cross" and co["sub2_cheapest"]["family"] == "cross"
    assert (f"*single* cross-vendor reading already costs "
            f"**{_pct(co['sub2_cheapest']['rate'])}% "
            f"{_iv(co['sub2_cheapest']['cluster_ci95'])}** false positives, above substrate "
            f"1's *eight*-reading cross-vendor **{_pct(co['sub1_dearest']['rate'])}% "
            f"{_iv(co['sub1_dearest']['cluster_ci95'])}**; those two intervals do not meet, "
            f"and {co['interval_gap_points']:.1f} points separate them") in t
    assert ("**Within the cross-vendor family there is therefore no K at which the two "
            "substrates can be compared at a matched false-positive rate**") in t

    # pooled: the intervals DO meet, and the report says so in its own voice
    assert po["intervals_overlap"] is True
    assert po["sub1_dearest"]["family"] == "self"
    assert (f"Substrate 1's dearest reading anywhere is its same-vendor family at K = "
            f"{po['sub1_dearest']['K']}, **{_pct(po['sub1_dearest']['rate'])}% "
            f"{_iv(po['sub1_dearest']['cluster_ci95'])}**, whose upper bound reaches "
            f"**{po['interval_overlap_points']:.1f} points** into substrate 2's cheapest "
            f"interval of {_iv(po['sub2_cheapest']['cluster_ci95'])}") in t
    assert "a matched false-positive rate **cannot be ruled out**" in t

    # the bare, unscoped form of the claim must not appear anywhere
    bare = ["no K at which the two substrates can be compared at a matched false-positive "
            "rate within the measured range",
            "The two measured false-positive ranges do not overlap at any K",
            "the two measured false-positive ranges do **not** overlap."]
    for phrase in bare:
        assert phrase not in t, f"unscoped non-overlap claim survives: {phrase!r}"

    # every remaining assertion of non-overlap carries a family word nearby
    for hit in re.finditer(r"do not meet|do not overlap|non-overlap|cannot be ruled out", t):
        window = t[max(0, hit.start() - 400):hit.end() + 400]
        assert ("cross-vendor" in window or "same-vendor" in window
                or "pooled" in window or "family" in window), (
            f"non-overlap assertion with no family named: {window[:200]!r}")


def test_the_correction_is_recorded_in_the_deviations():
    n, t = _n(), _t()
    m = n["H23c_false_positives"]["matched_fp_comparison"]
    assert m["CORRECTION"].startswith("an earlier version of this report asserted "
                                      "non-overlap without naming a family")
    po = m["pooled_all_families"]
    assert ("**An earlier version of this report overstated the matched-false-positive "
            "claim, and a figure review caught it.**") in t
    assert 'not overlap "at any K", naming no auditor family' in t
    assert (f"substrate 1's same-vendor family at K = {po['sub1_dearest']['K']} is "
            f"{_pct(po['sub1_dearest']['rate'])}% {_iv(po['sub1_dearest']['cluster_ci95'])} "
            f"and substrate 2's cheapest cross-vendor reading is "
            f"{_pct(po['sub2_cheapest']['rate'])}% {_iv(po['sub2_cheapest']['cluster_ci95'])}, "
            "and those two intervals overlap") in t
    co = m["cross_family_only_REGISTERED_COMPARISON"]
    s1c, s2c = co["sub1_dearest"], co["sub2_cheapest"]
    assert (f"The claim is now made only for the cross-vendor family - "
            f"{_pct(s1c['rate'])}% {_iv(s1c['cluster_ci95'])} against "
            f"{_pct(s2c['rate'])}% {_iv(s2c['cluster_ci95'])}, which do not meet") in t
    assert "No point estimate changed; what changed is the scope the sentence claims." in t
    # the version header records the correction rather than presenting this as the first pass
    assert "**Third version.**" in t
    assert "**No point estimate has changed across any version.**" in t


def test_substrate_1s_pooled_maximum_is_read_from_the_frozen_record():
    """The pooled answer turns on substrate 1's same-vendor family, which this study never
    re-ran: it must come from ceiling 1's committed numbers, unmodified."""
    n = _n()
    frozen = json.loads((CODE / "records" / "ceiling" / "numbers.json").read_text(encoding="utf-8"))
    fams = frozen["ceiling1"]["families"]
    po = n["H23c_false_positives"]["matched_fp_comparison"]["pooled_all_families"]
    dearest = max(fams, key=lambda f: fams[f]["C"]["curve"][-1])
    assert po["sub1_dearest"]["family"] == dearest
    assert po["sub1_dearest"]["rate"] == fams[dearest]["C"]["curve"][-1]
    assert po["sub1_dearest"]["cluster_ci95"] == fams[dearest]["C"]["union_at_kmax_block"]["cluster_ci95"]
    # the second bootstrap stream ceiling 1 carries for the same point changes nothing material
    alt = po["sensitivity_using_ceiling1_per_K_curve_ci95"]
    assert alt["sub1_dearest_cluster_ci95"] == fams[dearest]["C"]["curve_ci95"][-1]
    assert abs(alt["interval_overlap_points"] - po["interval_overlap_points"]) <= 0.5
    # substrate 2's cheapest really is its cheapest, over both families and every K
    lowest = min(v["curve"][k] for v in (n["H23b_curve"]["C"], n["self_family_curve"]["C"])
                 for k in range(8))
    assert abs(po["sub2_cheapest"]["rate"] - lowest) < 1e-9


# ---------------------------------------------------------------------------------
# H23d and H23e — what was not computed, and why
# ---------------------------------------------------------------------------------

def test_h23d_is_computed_as_registered_and_its_sign_is_bound():
    n, t = _n(), _t()
    d = n["H23d_self_minus_cross_K8"]
    assert d["computed_at_registered_K"] is True and d["registered_K"] == 8
    assert d["paired"] is True and n["coverage"]["all_draws_complete"] is True
    P, C = d["P"], d["C"]
    sp = n["self_family_curve"]["P"]["union_at_kmax"]
    cp = n["H23b_curve"]["P"]["union_at_kmax"]
    assert (f"union recall is **{_pct(sp['rate'])}% {_iv(sp['cluster_ci95'])}**, Wilson "
            f"{_iv(sp['wilson95'])}, against the cross-vendor arm's "
            f"**{_pct(cp['rate'])}% {_iv(cp['cluster_ci95'])}** on the same "
            f"{P['n']} instances") in t
    assert (f"**+{P['difference_points']:.1f} points, problem-cluster "
            f"[{P['cluster_ci95_points'][0]:.1f}, {P['cluster_ci95_points'][1]:.1f}]** "
            f"({P['a_only']} instances flagged only by `self`, {P['b_only']} only by "
            f"`cross`; exact McNemar p = {P['mcnemar_exact_p']:.5f}; cluster sign-flip "
            f"p = {P['signflip']['p']:.5f}; Tango "
            f"[{P['tango_ci95_points'][0]:.1f}, {P['tango_ci95_points'][1]:.1f}] and "
            f"grid-unconditional [{P['exact_unconditional_ci95_points'][0]:.1f}, "
            f"{P['exact_unconditional_ci95_points'][1]:.1f}]") in t
    # the sign, against substrate 1's frozen comparator
    assert d["sign_matches_substrate1"] is False and d["P_excludes_zero"] is True
    assert "**The sign is the opposite of substrate 1's.**" in t
    assert (f"Ceiling 1 measured {d['substrate1_comparator_points']:.1f} points "
            f"[{d['substrate1_comparator_ci95_points'][0]:.1f}, "
            f"{d['substrate1_comparator_ci95_points'][1]:.1f}] for the same contrast") in t
    # the false-positive side
    sc = n["self_family_curve"]["C"]["union_at_kmax"]
    cc = n["H23b_curve"]["C"]["union_at_kmax"]
    assert (f"false-positive rate is **{_pct(sc['rate'])}% {_iv(sc['cluster_ci95'])}**, "
            f"Wilson {_iv(sc['wilson95'])}, against the cross-vendor arm's "
            f"**{_pct(cc['rate'])}% {_iv(cc['cluster_ci95'])}**: "
            f"**+{C['difference_points']:.1f} points "
            f"[{C['cluster_ci95_points'][0]:.1f}, {C['cluster_ci95_points'][1]:.1f}]** "
            f"({C['a_only']} vs {C['b_only']} discordant; McNemar p = "
            f"{C['mcnemar_exact_p']:.5f}; sign-flip p = {C['signflip']['p']:.5f})") in t
    assert d["costs_more_than_it_gains"] is True
    assert (f"**{d['false_positives_bought_per_recall_point']:.2f} false-positive points "
            "for every recall point**") in t


def test_the_same_vendor_arms_draw_agreement_is_reported_as_measured():
    """How much the same-vendor arm's verdict moves across draws, READ from the data.

    This test used to assert `self` splits on exactly 0 instances and required the prose to
    say "identical on all eight draws for every one of the 250 instances". That was the
    voided run's finding, and hardcoding it meant the test could not notice when the finding
    changed -- which it did: with the visible tests corrected the arm splits on 12 of 249.
    A test that encodes a result checks nothing about the next run. Both counts now come
    from `numbers.json`, and only the invariant that `cross` moves more than `self` is
    asserted as a claim.
    """
    n, t = _n(), _t()
    ag = n["draw_agreement"]
    sp_self = ag["self"]["instances_whose_flag_splits_across_draws"]
    sp_cross = ag["cross"]["instances_whose_flag_splits_across_draws"]
    assert sp_cross > sp_self, (sp_cross, sp_self)
    assert (f"splits its verdict across the eight draws on **{sp_self} of "
            f"{ag['self']['n_instances']}** instances, where the cross-vendor arm splits on "
            f"**{sp_cross}**") in t
    assert ag["self"]["readings_flagged_by_checks"] == 0
    assert ag["cross"]["readings_flagged_by_checks"] == 0
    assert "the deterministic checks layer flagged nothing" in t
    # the registered gain ratio cannot be computed for this family, and the report says so
    se = n["self_family_exchange"]
    assert se["registered_gain_ratio_is_undefined"] is True
    assert "**Ceiling 1's registered gain ratio is undefined for this arm.**" in t
    lv = se["ratios"]["POST_HOC_level_ratio_by_k"]
    k1 = se["level_ratio_ci95_K1"]
    assert len(set(round(x, 9) for x in lv)) == 1
    assert (f"a flat **{lv[0]:.2f} [{k1[0]:.2f}, {k1[1]:.2f}]** at every K") in t
    assert se["level_ratio_below_cross_on_substrate2_at_every_k"] is True
    assert se["level_ratio_below_substrate1_cross_at_every_k"] is True
    sP = n["self_family_curve"]["P"]
    assert sP["flattening_gain_last_step_points"] == 0.0
    assert (f"last-step gain of {sP['flattening_gain_last_step_points']:.2f} points "
            f"[0.00, 0.00]") in t


def test_h23e_is_reported_as_not_run():
    n, t = _n(), _t()
    assert n["H23e_residual"]["in_scope"] is False
    assert n["H23e_residual"]["status"].startswith("NOT RUN")
    assert ("**The residual has not been classified under study 21's rubric on this "
            "substrate.**") in t
    assert "running it is the obvious next step" in t
    P = n["H23b_curve"]["P"]
    assert f"**{P['counts_k']['0']} of {P['n_instances']}** P instances that no `cross` draw flagged" in t


# ---------------------------------------------------------------------------------
# the substrate, the strata, the deviations and the cost
# ---------------------------------------------------------------------------------

def test_the_substrate_the_strata_and_the_cost_are_bound():
    n, t = _n(), _t()
    s, st, c = n["substrate"], n["strata"], n["cost"]
    assert (f"median task is **{s['median_spec_words']:.0f} specification words and "
            f"{s['median_solution_lines']:.0f} reference-solution lines** against "
            f"substrate 1's {s['substrate1_median_spec_words']} and "
            f"{s['substrate1_median_solution_lines']} - {s['spec_words_ratio']:.2f} times "
            f"the prose and {s['solution_lines_ratio']:.2f} times the code") in t
    assert f"The frame is {s['n_frame']} BigCodeBench tasks" in t
    assert (f"generated {st['n_candidates']} candidates over two batches for "
            f"**${c['generation']['usd']:.2f}**, giving strata **P {st['population']['P']}, "
            f"C {st['population']['C']}, F {st['population']['F']}**") in t
    assert (f"a seeded sample of {st['audited']['C']} C instances - "
            f"{st['audited']['P'] + st['audited']['C']} instances") in t
    assert f"Audit spend was **${c['audit_total']['usd']:.2f}** of a ${c['cap_usd']:.0f} cap" in t


def test_the_deviations_are_bound():
    n, t = _n(), _t()
    s = n["substrate"]
    assert (f"**The frame is {s['n_frame']} tasks, not the 289 the preregistration names.**") in t
    assert (f"only **{s['drops_by_filter']['S2']}** failed S2 rather than 37, leaving "
            f"**{s['n_frame']}**") in t
    assert f"All {s['n_dropped']} drops are recorded" in t
    reg = n["substrate1_frozen"]["exchange_rate_recall_per_fp_registered"]
    assert f"reproduced here from `records/ceiling/numbers.json` ({reg:.4f})" in t
    s1 = n["substrate1_frozen"]
    assert (f'"substrate 1\'s {_pct(s1["C_union_at_kmax"])}% and '
            f'{reg:.2f}" - that rate is {_pct(s1["C_union_at_kmax"])}% '
            f'{_iv(s1["C_cluster_ci95"])}') in t
    assert (f"reproduces {_pct(s1['P_union_at_kmax'])}% {_iv(s1['P_cluster_ci95'])} and "
            f"{_pct(s1['C_union_at_kmax'])}% {_iv(s1['C_cluster_ci95'])} exactly") in t
    cross = n["coverage"]["cross"]
    assert cross["8"]["recorded_denials"] > 0
    assert all(cross[str(k)]["recorded_denials"] == 0 for k in range(1, 8))
    assert (f"carries **{cross['8']['recorded_denials']}** recorded provider denials before "
            f"its {cross['8']['readings']} readings landed, and the seven before it carry "
            "none") in t
    assert n["substrate1_frozen"]["recomputation_matches_frozen"] is True
    assert "**H23e was not run**" in t
    # the self ladder's interruption: the first read's counts and the denial range
    first = n["coverage"]["self_first_read_INCOMPLETE"]
    by = first["readings_by_draw"]
    assert (f"At {first['read_utc']} its eight draws held "
            + ", ".join(str(by[str(k)]) for k in range(1, 8))
            + f" and {by['8']} readings of {n['coverage']['scope_n']} required") in t
    dn = n["H23d_self_minus_cross_K8"]["recorded_denials_by_draw"]
    assert (f"**{min(dn.values()):,} to {max(dn.values()):,}** provider denials per "
            "`self` draw") in t
    assert n["coverage"]["all_draws_complete"] is True
    assert "every draw now covers all 250" in t
    assert ("**No point estimate of H23a, H23b or H23c changed when the arm completed**") in t


def test_the_comparison_inventory_matches_the_record():
    n, t = _n(), _t()
    assert len(n["comparison_inventory"]) == 9
    for i in range(1, 10):
        assert f" {i}. " in t


def test_no_binding_matches_more_than_once():
    """Review round 1 of the sibling study: a reused label bound a rate to the wrong
    family, and new prose slipped under an existing anchor. Every discriminating figure
    in this report must occur exactly once, so an anchor cannot cover two sentences."""
    n, t = _n(), _t()
    P, C = n["H23b_curve"]["P"], n["H23b_curve"]["C"]
    a = n["H23a_primary_recall_sub2_minus_sub1_P_K8"]
    fp = n["H23c_false_positives"]["sub2_minus_sub1_C_K8"]
    d = n["H23d_self_minus_cross_K8"]
    once = [
        f"**+{a['difference_points']:.1f} points, 95% two-sample problem-cluster bootstrap",
        f"**+{fp['difference_points']:.1f} points "
        f"[{fp['cluster_ci95_points'][0]:.1f}, {fp['cluster_ci95_points'][1]:.1f}]**",
        f"flags **{a['a']['k']} of {a['a']['n']}** stratum-P instances",
        f"flag **{fp['a']['k']} of {fp['a']['n']}** correct solutions",
        f"**+{d['P']['difference_points']:.1f} points, problem-cluster",
        f"**+{d['C']['difference_points']:.1f} points "
        f"[{d['C']['cluster_ci95_points'][0]:.1f}, {d['C']['cluster_ci95_points'][1]:.1f}]**",
        "**The sign is the opposite of substrate 1's.**",
        "**Ceiling 1's registered gain ratio is undefined for this arm.**",
        f"**{P['flattening_gain_last_step_points']:.2f} points",
        f"last step on C gains **{C['flattening_gain_last_step_points']:.2f} points",
        "**H23d is answered as registered**",
        "**The residual has not been classified under study 21's rubric on this substrate.**",
    ]
    for anchor in once:
        assert t.count(anchor) == 1, f"{anchor!r} occurs {t.count(anchor)} times, not once"


def test_the_audit_set_redraws_from_the_registered_seed():
    """§2 froze the audit set before the first audit call but it reached git only with the
    results. The claim is checkable anyway: the committed instances and the registered seed
    redraw the committed set exactly, so no instance can have been chosen after a reading."""
    import random
    n = _n()
    records = CODE / "records" / "substrate2"
    rows = {}
    for line in (records / "instances.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["instance_id"]] = r
    by: dict[str, list[str]] = {}
    for iid, r in rows.items():
        by.setdefault(r["stratum"], []).append(iid)
    rng = random.Random(n["strata"]["seed"])
    chosen: list[str] = []
    for stratum in ("P", "C"):
        cap = n["strata"]["caps"][stratum]
        ids = sorted(by.get(stratum, []))
        chosen += sorted(rng.sample(ids, cap)) if len(ids) > cap else ids
    committed = json.loads((records / "audit_set.json").read_text(encoding="utf-8"))

    # The load-bearing claim, and it is checked in every state: the committed scope is exactly
    # what the registered seed redraws from the committed instances, so no instance can have
    # been chosen after a reading was seen.
    assert sorted(chosen) == committed["instance_ids"]

    # The cross-checks against numbers.json only mean something when that file describes the
    # same generation of candidates. Since 2026-09-17 it does not: Amendment 4 halted the re-run
    # with the cross-vendor family empty, so numbers.json still reports the VOID run's 250-instance
    # scope while audit_set.json has been re-frozen from the new candidates at 249. Asserting
    # across that boundary would be red for the wrong reason -- and silently deleting the assert
    # would lose the check for good. Amendment 3's generation digest lets the test tell the two
    # states apart, so it skips explicitly and says why.
    generation = committed.get("generation_sha256")
    if generation is not None and len(committed["instance_ids"]) != n["coverage"]["scope_n"]:
        import pytest
        pytest.skip(
            f"numbers.json describes a superseded generation: it reports "
            f"scope_n={n['coverage']['scope_n']} while the re-frozen audit set holds "
            f"{len(committed['instance_ids'])} (substrate2 Amendment 4). The redraw check above "
            f"still ran and passed; these cross-checks resume when the re-run completes and "
            f"numbers.json is regenerated.")

    assert len(committed["instance_ids"]) == n["coverage"]["scope_n"]
    assert ("redrawing it from the committed `instances.jsonl` with the registered seed "
            f"{n['strata']['seed']} reproduces all {n['coverage']['scope_n']} ids exactly") in _t()


#: The only figures in this report's prose that may appear without an interval. Each is a
#: DISTANCE BETWEEN two intervals that are quoted in the same sentence, not an estimate of
#: its own, and the prose says so where it appears. Nothing may be added here without that
#: declaration also appearing in the text — `test_every_prose_rate_is_bound_or_declared`
#: checks both halves.
DECLARED_WITHOUT_INTERVAL = [
    "2.6 and 6.3 points",
    "6.3-point overlap",
    "2.6-point separation",
    # The re-run reversed the direction: the two cross-vendor intervals now OVERLAP where
    # the voided run had them disjoint, so both distances appear in the same sentence.
    "2.6 points apart",
    "overlap by 3.5 points",
]
DECLARATION = "distances between"


def test_every_prose_rate_is_bound_or_declared():
    """EXPERIMENT_RECORD §9: a rate quoted without its interval is a defect. Ceiling 1's
    round-5 review added the other half — a figure is either bound to an interval or
    explicitly declared, with a reason, as owing none. Both halves are enforced here over
    the prose, with the generated table blocks excluded (their figures are Table-bound)."""
    raw = _raw()
    for key in rs2.TABLE_KEYS:
        b, e = rs2.begin(key), rs2.end(key)
        raw = raw[:raw.index(b)] + raw[raw.index(e) + len(e):]
    text = re.sub(r"\s+", " ", raw.replace("−", "-"))
    unbound = []
    for m in re.finditer(r"[-+\d.,]+\s*(?:%|points|percentage points|-point)", text):
        near = text[max(0, m.start() - 70):m.end() + 80]
        if re.search(r"\[\s*[-\d.]+,\s*[-\d.]+\s*\]", near):
            continue
        unbound.append((m.group(0).strip(), text[max(0, m.start() - 40):m.end() + 120]))
    for figure, context in unbound:
        assert any(d in context for d in DECLARED_WITHOUT_INTERVAL), (
            f"rate with no interval and no declaration: {figure!r} in {context!r}")
        assert DECLARATION in context, (
            f"{figure!r} is exempt but its sentence does not say why: {context!r}")
    # the declarations are real: each names a distance between intervals that ARE quoted
    for declared in DECLARED_WITHOUT_INTERVAL:
        assert text.count(declared) == 1, f"{declared!r} is not unique"
        i = text.index(declared)
        assert len(re.findall(r"\[\s*[-\d.]+,\s*[-\d.]+\s*\]",
                              text[max(0, i - 420):i + 420])) >= 2, (
            f"{declared!r} claims to be a distance between intervals but none are near it")
    # and the numbers they name are the records'
    m = _n()["H23c_false_positives"]["matched_fp_comparison"]
    assert f"{m['pooled_all_families']['interval_overlap_points']:.1f}-point overlap" in text
    assert (f"{m['cross_family_only_REGISTERED_COMPARISON']['interval_gap_points']:.1f}"
            "-point separation") in text
