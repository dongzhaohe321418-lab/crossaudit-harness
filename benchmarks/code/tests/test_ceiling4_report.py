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
  any-finding claim; the seeds, the reps and the strata sizes. For Amendment 1's
  adjudication: the naming agreement, its 2x2 cells, Cohen κ, both raters' yes counts and
  the asymmetry of the 23 disagreements; the recognition concordance and that its κ is
  undefined rather than 1; all sixteen rates (two routes x two questions x four reader
  rules), each recomputed from the two label files and the key rather than read from
  numbers.json; the registered primary with both intervals; the kill's threshold, its
  verdict and that it fires under every rule and question; and the manifest's sheet, key
  and label-file digests, both raters' identities, L2's model, endpoint and
  subscription billing, with an assertion that the sheet itself is not in the repository.
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
* The raters' judgements. Whether L1 and L2 answered the sheet *well* is not testable here;
  what is tested is that every rate and every agreement statistic is exactly what their two
  committed label files imply. The low κ is bound as a number, not adjudicated as a fact.
* Study 19's κ = 0.897, quoted in §3 for contrast: study 19's records are not on this
  branch, so that figure is attributed, not recomputed.
* The claim that study 19's sheet contained fewer adjacent-class findings. The results file
  labels that as the author's reading of the two sheets, and it is not a measurement.

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
    for path in (glob.glob(str(CODE / "records" / "ceiling4" / "**" / "*.jsonl"), recursive=True)
                 + glob.glob(str(CODE / "records" / "ceiling4" / "*.csv"))):
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
    assert ct["amendment1_kill_evaluated"] is True
    assert ct["amendment1_primary_rate"]["k"] == n["amendment1_adjudication"]["arms"]["T"]["defect_asserting"]["consensus"]["k"]
    c1 = n["families"]["cross"]["P"]
    assert (f"single-draw mean of {_pct(c1['curve'][0])}% (cluster "
            f"{_pct(c1['curve_cluster_ci95'][0][0])}–{_pct(c1['curve_cluster_ci95'][0][1])})") in t
    assert ap["k"] == 9
    prereg = (CODE / "ceiling4" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "below 20 of 110" in prereg
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


def _ratings():
    """The two label files and the key, read here rather than taken from numbers.json."""
    import csv as _csv
    R = CODE / "records" / "ceiling4"
    out = {}
    for name in ("L1", "L2"):
        with (R / f"{name}-amendment1.csv").open(encoding="utf-8", newline="") as h:
            out[name] = {r["id"].strip(): (r["naming"].strip(), r["recognition"].strip())
                         for r in _csv.DictReader(h)}
    key = {}
    for line in (CODE / "ceiling4" / "key-amendment1.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            key[row["id"]] = row
    return out["L1"], out["L2"], key


def test_the_adjudication_agreement_is_recomputed_and_bound():
    """κ, the cells and the asymmetry are recomputed from the csvs, not taken on trust."""
    import report_ceiling4 as r4
    n = _n(); t = _t()
    L1, L2, key = _ratings()
    ids = sorted(key)
    assert set(ids) == set(L1) == set(L2)
    y = lambda r, i: r[i][0] == "yes"                                     # noqa: E731
    a = sum(1 for i in ids if y(L1, i) and y(L2, i))
    b = sum(1 for i in ids if y(L1, i) and not y(L2, i))
    c = sum(1 for i in ids if not y(L1, i) and y(L2, i))
    d = sum(1 for i in ids if not y(L1, i) and not y(L2, i))
    nm = n["amendment1_adjudication"]["naming"]
    assert (nm["both_yes"], nm["L1_only"], nm["L2_only"], nm["both_no"]) == (a, b, c, d)
    assert nm["agree"] == a + d and nm["items"] == len(ids)
    assert abs(nm["kappa"] - r4.cohen_kappa(a, b, c, d)) < 1e-12
    assert nm["L1_yes"] == a + b and nm["L2_yes"] == a + c
    assert nm["disagreements_L1_no_L2_yes"] == c and nm["more_inclusive_rater"] == "L2"
    assert (f"{nm['agree']} of the {nm['items']} items, Cohen κ = {nm['kappa']:.3f}") in t
    assert (f"L1 answered yes on {nm['L1_yes']} items and L2 on {nm['L2_yes']}, and of the "
            f"{nm['disagreements']} disagreements {nm['disagreements_L1_no_L2_yes']} are "
            f"L1-no/L2-yes") in t
    # the recognition question: perfect concordance, so kappa is undefined, not 1
    rg = n["amendment1_adjudication"]["recognition"]
    cons = [i for i in ids if y(L1, i) and y(L2, i)]
    assert rg["items"] == len(cons)
    assert rg["both_defect"] == sum(1 for i in cons if L1[i][1] == "defect" and L2[i][1] == "defect")
    assert rg["kappa"] is None
    assert f"{rg['items']} items both raters called named, both labelled all {rg['both_defect']} \"defect\"" in t
    assert "κ is **undefined** there rather than 1" in t
    # the four non-defect labels the prose attributes to L2 on cross-R items only
    non_defect = [i for i in ids if y(L2, i) and L2[i][1] != "defect"]
    assert len(non_defect) == 4 and {key[i]["arm"] for i in non_defect} == {"R"}
    assert "L2's four non-defect\nlabels, all of which fall on `cross-R` items" in t


def test_the_adjudication_rates_and_amendment1_kill_are_bound():
    n = _n(); t = _t()
    L1, L2, key = _ratings()
    adj = n["amendment1_adjudication"]

    def hit(arm, question, rule):
        def q(r, i):
            named = r[i][0] == "yes"
            return named if question == "naming" else (named and r[i][1] == "defect")
        pick = {"consensus": lambda i: q(L1, i) and q(L2, i), "L1": lambda i: q(L1, i),
                "L2": lambda i: q(L2, i), "either": lambda i: q(L1, i) or q(L2, i)}[rule]
        return len({key[i]["instance"] for i in key if key[i]["arm"] == arm and pick(i)})

    for arm in ("T", "R"):
        for question in ("naming", "defect_asserting"):
            for rule in ("consensus", "L1", "L2", "either"):
                assert adj["arms"][arm][question][rule]["k"] == hit(arm, question, rule), (arm, question, rule)
    prim = adj["arms"]["T"]["defect_asserting"]["consensus"]
    assert (f"{prim['k']} of {prim['n']} = {_pct(prim['rate'])}% (Wilson {_pct(prim['wilson95'][0])}–"
            f"{_pct(prim['wilson95'][1])}; cluster {_pct(prim['cluster_ci95'][0])}–"
            f"{_pct(prim['cluster_ci95'][1])})") in t
    eith = adj["arms"]["T"]["defect_asserting"]["either"]
    assert (f"{eith['k']} of {eith['n']} = {_pct(eith['rate'])}% (Wilson {_pct(eith['wilson95'][0])}–"
            f"{_pct(eith['wilson95'][1])}; cluster {_pct(eith['cluster_ci95'][0])}–"
            f"{_pct(eith['cluster_ci95'][1])})") in t
    rc26 = adj["arms"]["R"]["naming"]["consensus"]
    assert (f"{rc26['k']} of {rc26['n']} = {_pct(rc26['rate'])}% (Wilson {_pct(rc26['wilson95'][0])}–"
            f"{_pct(rc26['wilson95'][1])}; cluster {_pct(rc26['cluster_ci95'][0])}–"
            f"{_pct(rc26['cluster_ci95'][1])})") in t
    assert (f"it is {adj['arms']['R']['naming']['either']['k']} of 110 for naming and\n"
            f"{adj['arms']['R']['defect_asserting']['either']['k']} of 110 for defect-asserting") in t
    # the "5 to 7" span, and the denominator of one reading
    assert f"finding\non {adj['arms']['T']['P_instances_with_a_finding']} of 110 defect instances" in t
    assert f"asserted the actual defect on {prim['k']} to {eith['k']} of them" in t
    # the kill
    kill = adj["amendment1_kill"]
    assert kill["threshold_k"] == 20 and kill["fired"] is True
    assert kill["fired_under_every_rule_and_question"] is True
    assert all(adj["arms"]["T"][q][r]["k"] < kill["threshold_k"]
               for q in ("naming", "defect_asserting")
               for r in ("consensus", "L1", "L2", "either"))
    assert "the kill **FIRED**" in t.replace("\n", " ")
    # the two quantities are not the same and the file must not treat them as one
    assert adj["arms"]["R"]["naming"]["L2"]["k"] != adj["arms"]["R"]["defect_asserting"]["L2"]["k"]


def test_the_adjudication_manifest_records_its_provenance():
    n = _n()
    import hashlib
    m = n["amendment1_adjudication"]["manifest"]
    assert len(m["sheet_sha256"]) == 64 and len(m["key_sha256"]) == 64
    assert m["adjudication_run"] is True
    for name in ("L1", "L2"):
        path = CODE / "records" / "ceiling4" / f"{name}-amendment1.csv"
        assert m["ratings"][name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert m["ratings"][name]["rows"] == m["items"]
    key_path = CODE / "ceiling4" / "key-amendment1.jsonl"
    assert m["key_sha256"] == hashlib.sha256(key_path.read_bytes()).hexdigest()
    assert "author" in m["raters"]["L1"]["identity"]
    assert m["raters"]["L2"]["model"] == "gpt-6-astra"
    assert m["raters"]["L2"]["endpoint"].startswith("https://")
    assert "subscription" in m["raters"]["L2"]["billing"]
    assert "not in any ledger" in m["raters"]["L2"]["billing"]
    # the sheet is never in the repository
    assert not (CODE / "records" / "ceiling4" / "sheet-amendment1.jsonl").exists()
    assert str(CODE) not in m["sheet_path_outside_repo"]
