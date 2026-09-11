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
    "## 5. H23d — the same-vendor arm has no usable K",
    "## 6. H23e — not run",
    "## 7. What this does and does not establish",
    "## 8. Deviations from the preregistration, and interruptions",
    "## 9. The comparison inventory",
    "## 10. Cost",
    "### Table 7 — cost, from the run's usage ledgers",
]

#: Which registered heading each table block must sit under.
BLOCK_HEADING = {
    "T1": "### Table 1 — the two substrates, described",
    "T2": "### Table 2 — generation, the strata and the frozen audit set",
    "T3": "### Table 3 — the audit ladder's coverage",
    "T4": "### Table 4 — union recall and union false positives at every K, substrate 2",
    "T5": "### Table 5 — substrate 2 against substrate 1 at K = 8",
    "T6": "### Table 6 — recall bought per false-positive point, both substrates",
    "T7": "### Table 7 — cost, from the run's usage ledgers",
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
    assert (f"**{P['flattening_gain_last_step_points']:.2f} points "
            f"[{g[0]:.2f}, {g[1]:.2f}]**: **the bar is met**") in t
    assert P["flattened_by_ceiling1_bar"] is True
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


def test_the_matched_false_positive_limit_is_stated():
    n, t = _n(), _t()
    m = n["H23c_false_positives"]["matched_fp_comparison"]
    C = n["H23b_curve"]["C"]
    assert m["sub2_min_exceeds_sub1_max"] is True and m["overlap_exists"] is False
    assert (f"*single* reading already costs **{_pct(m['sub2_min_fp_rate'])}% "
            f"{_iv(C['curve_cluster_ci95'][0])}** false positives, which is above substrate "
            f"1's *eight*-reading **{_pct(m['sub1_max_fp_rate'])}% "
            f"{_iv(n['substrate1_frozen']['C_cluster_ci95'])}**") in t
    assert ("There is therefore no K at which the two substrates can be compared at a "
            "matched false-positive rate within the measured range**") in t


# ---------------------------------------------------------------------------------
# H23d and H23e — what was not computed, and why
# ---------------------------------------------------------------------------------

def test_the_self_arm_is_reported_as_not_evaluable():
    n, t = _n(), _t()
    d = n["H23d_self_arm"]
    assert d["computed_at_registered_K"] is False and d["registered_K"] == 8
    assert d["usable_K"] < d["registered_K"]
    assert "**H23d is not computed.**" in t
    r = d["readings_by_draw"]
    assert f"Draw 1 covers all {r['1']} frozen instances. Draw 2 covers {r['2']}." in t
    lo, hi = min(r[str(k)] for k in range(3, 9)), max(r[str(k)] for k in range(3, 9))
    assert f"**Draws 3 to 8 cover between {lo} and {hi}**" in t
    assert all(d["C_read_by_draw"][str(k)] == 0 for k in range(3, 9))
    assert "not one of them read a single stratum-C instance" in t
    assert f"**{d['instances_with_all_8_self_readings']}** instances carry all eight" in t
    dn = d["recorded_denials_by_draw"]
    assert (f"between **{min(dn.values()):,} and {max(dn.values()):,}** provider denials "
            "per `self` draw") in t


def test_the_single_reading_secondary_is_labelled_not_preregistered():
    n, t = _n(), _t()
    s = n["SECONDARY_self_minus_cross_single_reading_NOT_H23d"]
    assert s["label"].startswith("NOT PREREGISTERED AT THIS K")
    assert s["K"] == n["H23d_self_arm"]["usable_K"]
    P, C = s["strata"]["P"], s["strata"]["C"]
    cp = n["H23b_curve"]["P"]["curve_cluster_ci95"][0]
    cc = n["H23b_curve"]["C"]["curve_cluster_ci95"][0]
    assert (f"flags **{_pct(P['self_union_at_K'])}% of P {_iv(P['self_wilson95'])} Wilson** "
            f"against the cross-vendor auditor's mean single reading of "
            f"{_pct(P['cross_mean_single_draw'])}% {_iv(cp)}, a paired difference of "
            f"**+{P['difference_points']:.1f} points "
            f"[{P['cluster_ci95_points'][0]:.1f}, {P['cluster_ci95_points'][1]:.1f}]**") in t
    assert (f"**{_pct(C['self_union_at_K'])}% of C {_iv(C['self_wilson95'])} Wilson** "
            f"against {_pct(C['cross_mean_single_draw'])}% {_iv(cc)}, a paired difference "
            f"of **+{C['difference_points']:.1f} points "
            f"[{C['cluster_ci95_points'][0]:.1f}, {C['cluster_ci95_points'][1]:.1f}]**") in t
    assert "**not preregistered at this K**" in t
    assert "Secondary, **not preregistered at this K**" in t


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


def test_the_comparison_inventory_matches_the_record():
    n, t = _n(), _t()
    assert len(n["comparison_inventory"]) == 7
    for i in range(1, 8):
        assert f" {i}. " in t


def test_no_binding_matches_more_than_once():
    """Review round 1 of the sibling study: a reused label bound a rate to the wrong
    family, and new prose slipped under an existing anchor. Every discriminating figure
    in this report must occur exactly once, so an anchor cannot cover two sentences."""
    n, t = _n(), _t()
    P, C = n["H23b_curve"]["P"], n["H23b_curve"]["C"]
    a = n["H23a_primary_recall_sub2_minus_sub1_P_K8"]
    fp = n["H23c_false_positives"]["sub2_minus_sub1_C_K8"]
    s = n["SECONDARY_self_minus_cross_single_reading_NOT_H23d"]["strata"]
    once = [
        f"**+{a['difference_points']:.1f} points, 95% two-sample problem-cluster bootstrap",
        f"**+{fp['difference_points']:.1f} points "
        f"[{fp['cluster_ci95_points'][0]:.1f}, {fp['cluster_ci95_points'][1]:.1f}]**",
        f"flags **{a['a']['k']} of {a['a']['n']}** stratum-P instances",
        f"flag **{fp['a']['k']} of {fp['a']['n']}** correct solutions",
        f"**{_pct(s['P']['self_union_at_K'])}% of P {_iv(s['P']['self_wilson95'])} Wilson**",
        f"**{_pct(s['C']['self_union_at_K'])}% of C {_iv(s['C']['self_wilson95'])} Wilson**",
        f"**{P['flattening_gain_last_step_points']:.2f} points",
        f"last step on C gains **{C['flattening_gain_last_step_points']:.2f} points",
        "**H23d is not computed.**",
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
    assert sorted(chosen) == committed["instance_ids"]
    assert len(committed["instance_ids"]) == n["coverage"]["scope_n"]
    assert ("redrawing it from the committed `instances.jsonl` with the registered seed "
            f"{n['strata']['seed']} reproduces all {n['coverage']['scope_n']} ids exactly") in _t()
