"""RESULTS-CEILING4.md's figures are the records' figures.

WHAT IS BOUND HERE, and only this:

* **Structure.** Every generated block in `RESULTS-CEILING4.md` equals the block of the
  same name in `records/ceiling4/tables.md` **byte for byte**; the results file carries
  exactly the marker pairs the renderer emits, in the renderer's order; and **no
  table-like content — no `|` character, no `<table>`/`<tr>`/`<td>` tag — appears outside
  the generated blocks** (study 17 round 5: a hand-written table outside the blocks still
  renders, and a markdown-table parser accepts mutations the eye does not).
* **Reproducibility.** `report_ceiling4.render_tables(json.load(numbers.json))` reproduces
  `tables.md` byte for byte, from `numbers.json` alone — the renderer reads no record file.
* **Every figure quoted in the prose of `RESULTS-CEILING4.md`** is asserted to come from
  `records/ceiling4/numbers.json`: H20a's point estimate, its cluster, Tango and
  grid-unconditional intervals, its discordant counts, its exact-McNemar and cluster
  sign-flip p values, and its one-signed flag; the kill's two clauses and its verdict;
  H20b's two asymptotes with their cluster intervals and taus, their difference, both
  flattening gains with their intervals, both flattening verdicts and both
  extrapolation labels, both raw K = 8 unions, both R-squared values, both largest
  residuals and both ZIBB mixing weights with their cluster intervals; H20c's union-FP
  difference with its intervals, p values and counts, the
  single-draw mean with its interval, the product bar and the count of draws inside it,
  and both C unions; H20d's residual count with both intervals, its per-category counts,
  the count that left it and the count new to it; `cross-T`'s flag rate with both
  intervals, its any-finding rate, the `cross` single-draw comparator, the null
  Amendment-1 rate and the un-evaluated kill, with the memo's threshold read from the
  preregistration; the any-finding unions of both K = 8 families; the ledger total, its
  call count, its reading count, the malformed-reply and repair-re-ask counts, the
  denial count and the prompt-digest positive control; the run-history figures (the
  instances draw 5 lost, that draws 6 to 8 were denied whole, and that every draw is
  complete at 260); the two reading-level finding and BLOCKER counts behind §2's
  any-finding claim; the seeds, the reps and the strata sizes.
* **Three record-level invariants**: the repository's `records/ceiling4/` carries no
  finding, specification or solution text (ids, digests, counts and outcomes only) and
  neither do `numbers.json` and `tables.md`; the committed adjudication key carries no
  text field; and every count the intervals are built on — the four union counts, the two
  discordant counts, `cross-T`'s flag count and the per-draw reading and malformed counts —
  is recomputed straight from the cache files through the driver's own loader and compared
  with what the report wrote.

WHAT IS NOT BOUND HERE:

* The prose itself — its claims, its labels and its reasoning are the reviewer's to check.
* The estimators. They are study 18's and ceiling 1's, imported unchanged;
  `tests/test_ceiling_stats.py` is their evidence and is not duplicated.
* The readings. Whether the cache is a faithful record of the run is the archive's
  business (`run.log`, the ledgers), not this file's.
* Amendment 1's defect-naming rate and its kill: no adjudication was run, so there is no
  number to bind.

    PYTHONPATH=src python -m pytest benchmarks/code/tests/test_ceiling4_report.py -q
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

NUMBERS = CODE / "records" / "ceiling4" / "numbers.json"
TABLES = CODE / "records" / "ceiling4" / "tables.md"
RESULTS = CODE / "RESULTS-CEILING4.md"


def _n() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))


def _t() -> str:
    """The results file with the typographic minus folded to ASCII, as study 18 does."""
    return RESULTS.read_text(encoding="utf-8").replace("−", "-")


def _pct(x: float, places: int = 1) -> str:
    return f"{100 * x:.{places}f}"


# ---------------------------------------------------------------------------------
# structure: the blocks are generated, spliced verbatim, and nothing tabular escapes
# ---------------------------------------------------------------------------------

def _splice():
    sys.path.insert(0, str(CODE / "ceiling4"))
    import splice_tables
    return splice_tables


def test_every_block_is_spliced_byte_for_byte():
    st = _splice()
    source = st.blocks(TABLES.read_text(encoding="utf-8"))
    target = st.blocks(RESULTS.read_text(encoding="utf-8"))
    assert set(source) == set(target), (sorted(set(source) ^ set(target)))
    for name, body in source.items():
        assert target[name] == body, f"block {name} is not the rendered bytes"


def test_the_results_file_carries_exactly_the_renderers_blocks_in_order():
    import report_ceiling4 as r4
    st = _splice()
    names = [m.group("name") for m in st._BLOCK.finditer(RESULTS.read_text(encoding="utf-8"))]
    assert names == list(r4.BLOCK_NAMES)


def test_the_renderer_reproduces_tables_md_from_numbers_json_alone():
    import report_ceiling4 as r4
    assert r4.render_tables(_n()) == TABLES.read_text(encoding="utf-8")


def test_no_table_like_content_outside_the_generated_blocks():
    """A hand-written table outside a block would still render; it may not exist."""
    st = _splice()
    text = RESULTS.read_text(encoding="utf-8")
    outside = st._BLOCK.sub("", text)
    assert "|" not in outside, "a pipe character outside the generated blocks"
    assert not re.search(r"<\s*/?\s*(table|thead|tbody|tr|td|th)\b", outside, re.I), \
        "an HTML table tag outside the generated blocks"


# ---------------------------------------------------------------------------------
# the record carries no text
# ---------------------------------------------------------------------------------

def test_the_committed_records_carry_no_finding_or_specification_text():
    """The cache rows are ids, digests, counts and outcomes. The driver builds a row that
    also holds ``blocker_texts``; the cache writer drops it, and this asserts that it did."""
    banned = ("blocker_texts", "observation", "specification", "solution\"", "finding\"")
    for path in glob.glob(str(CODE / "records" / "ceiling4" / "**" / "*.jsonl"), recursive=True):
        body = Path(path).read_text(encoding="utf-8")
        for key in banned:
            assert key not in body, f"{path} carries {key}"
    for path in (NUMBERS, TABLES):
        body = path.read_text(encoding="utf-8")
        for key in ("blocker_texts", "observation"):
            assert key not in body, f"{path} carries {key}"
    key_path = CODE / "ceiling4" / "key-amendment1.jsonl"
    if key_path.exists():
        for line in key_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                assert set(row) == {"id", "instance", "arm", "k", "severity", "rule"}


def test_the_headline_counts_are_recomputable_from_the_readings():
    """numbers.json is bound to the cache, not only to itself.

    The union counts, the discordant counts and the reply-format counts are recomputed here
    straight from the record files, through the same loader the driver and the report use,
    and compared with what the report wrote. This is the cheap end of "the renderer
    reproduces the tables from the records": the whole analysis is not re-run (its bootstraps
    are 10,000 resamples apiece), but every count the intervals are built on is.
    """
    import report_ceiling4 as r4
    import report_ceiling as rc
    n = _n()
    instances = rc.load_instances()
    scope = [i for i in rc.load_audit_set() if instances[i]["stratum"] in ("P", "C")]
    P = [i for i in scope if instances[i]["stratum"] == "P"]
    C = [i for i in scope if instances[i]["stratum"] == "C"]
    draws = r4.load_draws(set(scope), ("cross", "cross-R", "cross-T"))
    for fam in ("cross", "cross-R"):
        for ids, stratum in ((P, "P"), (C, "C")):
            union = sum(1 for i in ids if any(draws[fam][d].get(i) for d in range(1, 9)))
            assert union == n["families"][fam][stratum]["union_at_kmax"]["k"]
    a_only = sum(1 for i in P if any(draws["cross-R"][d].get(i) for d in range(1, 9))
                 and not any(draws["cross"][d].get(i) for d in range(1, 9)))
    b_only = sum(1 for i in P if not any(draws["cross-R"][d].get(i) for d in range(1, 9))
                 and any(draws["cross"][d].get(i) for d in range(1, 9)))
    h = n["primary_H20a_crossR_minus_cross_P"]
    assert (a_only, b_only) == (h["a_only"], h["b_only"])
    ct = sum(1 for i in P if draws["cross-T"][1].get(i))
    assert ct == n["amendment1_cross_T"]["P_flag_rate"]["k"]
    fmt = n["secondary_reply_format_and_cost"]
    for name, v in fmt.items():
        route, draw = name.rsplit("-d", 1)
        rows = r4.cache_rows(route, int(draw))
        assert len(rows) == v["rows"]
        assert sum(1 for r in rows if r.get("invalid_reason")) == v["invalid_reason_nonempty"]


# ---------------------------------------------------------------------------------
# every figure the prose quotes
# ---------------------------------------------------------------------------------

def test_H20a_and_its_kill_are_bound():
    n = _n(); t = _t()
    h = n["primary_H20a_crossR_minus_cross_P"]
    assert (f"P at K = {h['k']} = **{h['difference_points']:+.1f} points, problem-cluster 95% "
            f"[{h['cluster_ci95_points'][0]:.1f}, {h['cluster_ci95_points'][1]:.1f}]**") in t
    assert (f"Tango [{h['tango_ci95_points'][0]:.1f}, {h['tango_ci95_points'][1]:.1f}]; "
            f"grid-unconditional [{h['exact_unconditional_ci95_points'][0]:.1f}, "
            f"{h['exact_unconditional_ci95_points'][1]:.1f}]") in t
    assert (f"{h['a_only']} instances blocked by `cross-R` only, {h['b_only']} by `cross` only") in t
    assert f"McNemar p = {h['mcnemar_exact_p']:.1e}" in t
    assert f"sign-flip p = {h['signflip']['p']:.1e}" in t
    assert h["one_signed_discordance"] is False
    k = n["H20a_kill"]
    assert k["fired"] is False
    assert (f"union {k['crossR_union_at_kmax_points']:.1f}% is above "
            f"[{k['cross_k8_cluster_ci95_points_preregistered'][0]:.1f}, "
            f"{k['cross_k8_cluster_ci95_points_preregistered'][1]:.1f}]") in t
    ur = n["families"]["cross-R"]["P"]["union_at_kmax"]
    uc = n["families"]["cross"]["P"]["union_at_kmax"]
    assert (f"{ur['k']} of {ur['n']} = {_pct(ur['rate'])}% (Wilson {_pct(ur['wilson95'][0])}–"
            f"{_pct(ur['wilson95'][1])}; cluster {_pct(ur['cluster_ci95'][0])}–{_pct(ur['cluster_ci95'][1])})") in t
    assert (f"{uc['k']} of {uc['n']} = {_pct(uc['rate'])}% (cluster "
            f"{_pct(uc['cluster_ci95'][0])}–{_pct(uc['cluster_ci95'][1])})") in t


def test_H20b_is_bound():
    n = _n(); t = _t()
    hb = n["H20b_asymptote_difference_P"]
    assert (f"**{hb['difference_points']:+.1f} points, cluster [{hb['cluster_ci95_points'][0]:.1f}, "
            f"{hb['cluster_ci95_points'][1]:.1f}]**") in t
    for fam, name in (("cross-R", "`cross-R`"), ("cross", "`cross`")):
        fit = n["families"][fam]["P"]["fit"]
        fl = n["H20b_flattening"][fam]
        u = fl["raw_union_at_kmax"]
        assert (f"A({name}) = {_pct(fit['A'])}% (cluster {_pct(fit['A_ci95_cluster'][0])}–"
                f"{_pct(fit['A_ci95_cluster'][1])}, τ = {fit['tau']:.2f})") in t
        assert (f"gain {fl['gain_last_step_points']:.2f} points, cluster "
                f"[{fl['gain_cluster_ci95_points'][0]:.2f}, {fl['gain_cluster_ci95_points'][1]:.2f}]") in t
        assert (f"{u['k']} of {u['n']} = {_pct(u['rate'])}% (cluster "
                f"{_pct(u['cluster_ci95'][0])}–{_pct(u['cluster_ci95'][1])})") in t
    # the two families fall on OPPOSITE sides of ceiling 1's registered bar, and the prose
    # says so: cross-R flattened, cross did not and its asymptote is an extrapolation
    assert n["H20b_flattening"]["cross-R"]["flattened"] is True
    assert n["H20b_flattening"]["cross-R"]["asymptote_is_extrapolation"] is False
    assert n["H20b_flattening"]["cross"]["flattened"] is False
    assert n["H20b_flattening"]["cross"]["asymptote_is_extrapolation"] is True
    assert "**is an extrapolation past the" in t
    # the goodness-of-fit figures the prose quotes
    fr, fc = n["families"]["cross-R"]["P"], n["families"]["cross"]["P"]
    assert (f"(R² {fr['fit']['r2']:.4f} against {fc['fit']['r2']:.4f}, "
            f"largest absolute residual {100 * fr['fit_max_resid']:.2f} points against "
            f"{100 * fc['fit_max_resid']:.2f})") in t
    assert fr["fit"]["A"] < fr["union_at_kmax"]["rate"]        # the prose's "falls slightly below"
    # ceiling 1 §1.2's registered secondary, reported beside A as that section requires
    for fam, name in (("cross", "`cross`"), ("cross-R", "`cross-R`")):
        z = n["families"][fam]["P"]["zibb"]
        assert z["reps"] == 1000
        assert (f"π = {_pct(z['pi'])}% (cluster {_pct(z['pi_cluster_ci95'][0])}–"
                f"{_pct(z['pi_cluster_ci95'][1])}) for {name}") in t


def test_H20c_is_bound():
    n = _n(); t = _t()
    hc = n["H20c_C_false_positives"]
    assert (f"C at K = {hc['k']}: **{hc['difference_points']:+.1f} points, cluster "
            f"[{hc['cluster_ci95_points'][0]:.1f}, {hc['cluster_ci95_points'][1]:.1f}]**") in t
    assert (f"({hc['a_only']} vs {hc['b_only']}; McNemar p = {hc['mcnemar_exact_p']:.1e}; "
            f"sign-flip p = {hc['signflip']['p']:.1e}; Tango [{hc['tango_ci95_points'][0]:.1f}, "
            f"{hc['tango_ci95_points'][1]:.1f}]; grid-unconditional "
            f"[{hc['exact_unconditional_ci95_points'][0]:.1f}, "
            f"{hc['exact_unconditional_ci95_points'][1]:.1f}])") in t
    s = n["H20c_single_draw_fp"]
    m = s["cross-R"]["mean_over_draws"]
    assert (f"single-draw false-positive rate on C is {_pct(m['rate'])}% (cluster "
            f"{_pct(m['cluster_ci95'][0])}–{_pct(m['cluster_ci95'][1])})") in t
    assert f"the product bar of {_pct(s['bar'])}%" in t
    assert s["crossR_mean_within_bar"] is False
    assert f"{s['cross-R']['draws_at_or_below_bar']} of {s['cross-R']['k_max']} individual draws" in t
    uc, ur = n["families"]["cross"]["C"]["union_at_kmax"], n["families"]["cross-R"]["C"]["union_at_kmax"]
    assert (f"{ur['k']} of {ur['n']} = {_pct(ur['rate'])}% against {uc['k']} of {uc['n']} = "
            f"{_pct(uc['rate'])}%") in t


def test_H20d_is_bound():
    n = _n(); t = _t()
    r = n["H20d_residual"]
    res = r["residual"]
    assert (f"**{r['n']} of {res['n']} = {_pct(res['rate'])}%** (Wilson {_pct(res['wilson95'][0])}–"
            f"{_pct(res['wilson95'][1])}; cluster {_pct(res['cluster_ci95'][0])}–"
            f"{_pct(res['cluster_ci95'][1])})") in t
    assert f"from {r['study18_residual_n']} after study 18 to {r['n']}" in t
    left = r["left_the_residual_when_cross_R_was_added"]
    assert f"{len(left)} instances leave it" in t
    by = r["left_the_residual_by_category"]
    assert (", ".join(f"{v} {k}" for k, v in by.items())) in t
    assert len(r["new_to_the_residual"]) == 0
    assert f"over {r['total_draws']} draws of {len(r['families'])} families" in t
    assert f"from {r['study18_residual_n']} after study 18" in t


def test_cross_T_and_the_any_finding_secondary_are_bound():
    n = _n(); t = _t()
    ct = n["amendment1_cross_T"]
    p = ct["P_flag_rate"]
    assert (f"{p['k']} of {p['n']} = {_pct(p['rate'])}% (Wilson {_pct(p['wilson95'][0])}–"
            f"{_pct(p['wilson95'][1])}; cluster {_pct(p['cluster_ci95'][0])}–"
            f"{_pct(p['cluster_ci95'][1])})") in t
    ap = ct["P_any_finding_rate"]
    assert (f"any severity on {ap['k']} of {ap['n']} = {_pct(ap['rate'])}% (cluster "
            f"{_pct(ap['cluster_ci95'][0])}–{_pct(ap['cluster_ci95'][1])})") in t
    assert ct["amendment1_primary_rate"] is None and ct["amendment1_kill_evaluated"] is False
    c1 = n["families"]["cross"]["P"]
    assert (f"single-draw mean of {_pct(c1['curve'][0])}% (cluster "
            f"{_pct(c1['curve_cluster_ci95'][0][0])}–{_pct(c1['curve_cluster_ci95'][0][1])})") in t
    # the bound that needs no adjudication: the naming rate cannot exceed the any-finding count
    assert ap['k'] == 9 and f"at most {ap['k']} of {ap['n']}" in t
    prereg = (CODE / "ceiling4" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "below 20 of 110" in prereg and "threshold of 20 of 110" in t
    fams = n["secondary_any_finding_rule"]["families"]
    for fam, name in (("cross-R", "`cross-R`"), ("cross", "`cross`")):
        u = fams[fam]["P"]["union_at_kmax"]
        assert (f"{name} {u['k']} of {u['n']} = {_pct(u['rate'])}% (cluster "
                f"{_pct(u['cluster_ci95'][0])}–{_pct(u['cluster_ci95'][1])})") in t
    # the prose's "the same set, not merely the same count": any-finding contains BLOCKER
    # by construction, so equal counts on P make the two unions the same instances
    assert fams["cross-R"]["P"]["union_at_kmax"]["k"] == n["families"]["cross-R"]["P"]["union_at_kmax"]["k"]
    fmt = n["secondary_reply_format_and_cost"]
    rr = [v for k, v in fmt.items() if k.startswith("cross-R")]
    reads = sum(v["rows"] for v in rr)
    finds = sum(v["model_findings_any"] for v in rr)
    blocks = sum(v["model_blockers_any"] for v in rr)
    assert (f"{finds} of the {reads:,} `cross-R` readings returned at least one finding and "
            f"{blocks} returned at\n  least one BLOCKER") in t


def test_cost_format_and_the_prompt_digest_control_are_bound():
    n = _n(); t = _t()
    cost = n["cost"]
    assert (f"**${cost['ledger_usd_total']:.2f}** from the nine project ledgers "
            f"({cost['ledger_calls_total']:,} calls for {cost['readings_total']:,} readings)") in t
    fmt = n["secondary_reply_format_and_cost"]
    assert sum(v["invalid_reason_nonempty"] for v in fmt.values()) == 0
    assert sum(v["ledger_calls_minus_readings"] for v in fmt.values()) == 0
    assert f"{sum(v['rows'] for v in fmt.values()):,} readings, none malformed and none re-asked" in t
    r_rows = sum(v["rows"] for k, v in fmt.items() if k.startswith("cross-R"))
    r_same = sum(v["prompt_digest_equals_study2_base"] for k, v in fmt.items() if k.startswith("cross-R"))
    t_rows = fmt["cross-T-d1"]["rows"]
    t_same = fmt["cross-T-d1"]["prompt_digest_equals_study2_base"]
    assert r_same == 0 and t_same == t_rows
    assert f"all {r_rows:,} `cross-R` readings carry a prompt digest" in t
    assert f"all {t_rows} `cross-T` readings carry the same digest" in t
    denials = sum(v["provider_denial_rows_before_completion"] for v in fmt.values())
    assert f"{denials:,} provider denials" in t
    d5 = fmt["cross-R-d5"]["provider_denial_instances_before_completion"]
    assert f"draw 5 lost {d5} instances" in t
    assert all(fmt[f"cross-R-d{d}"]["provider_denial_instances_before_completion"] == 260
               for d in (6, 7, 8))
    assert all(v["rows"] == 260 for v in fmt.values())
    assert f"complete at {fmt['cross-T-d1']['rows']} of {fmt['cross-T-d1']['rows']}" in t


def test_the_seeds_and_the_reps_are_the_preregistered_ones():
    n = _n()
    assert n["bootstrap"]["seed"] == 20260913 and n["bootstrap"]["reps"] == 10_000
    assert n["bootstrap"]["unit"] == "problem"
    assert n["k_max"] == 8 and n["n_P"] == 110 and n["n_C"] == 150
    assert n["H20b_asymptote_difference_P"]["seed"] == 20260913
