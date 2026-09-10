"""RESULTS-CEILING3B.md's figures are records/ceiling3b/numbers.json's figures.

Bound, and only these: the spliced table block (byte for byte against tables.md); H19a's
difference, interval, discordant counts and Tango/grid intervals; R − S on P and C with
their intervals and counts; the any-finding B − S and R − S differences; H19d's item count,
agreement, kappa and the per-arm named counts and rates with both intervals; the residual
counts; the ledger cost total and call count.
"""

from __future__ import annotations

import json
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
NUMBERS = CODE / "records" / "ceiling3b" / "numbers.json"
TABLES = CODE / "records" / "ceiling3b" / "tables.md"
RESULTS = CODE / "RESULTS-CEILING3B.md"
BEGIN, END = "<!-- BEGIN TABLES (records/ceiling3b/tables.md) -->", "<!-- END TABLES -->"


def _n() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))


def _t() -> str:
    return RESULTS.read_text(encoding="utf-8").replace("−", "-")


def _flat() -> str:
    """The prose with soft wraps joined, for sentences that may wrap anywhere."""
    return " ".join(_t().split())


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _ivp(p) -> str:
    return f"[{p[0]:+.1f}, {p[1]:+.1f}]"


def test_the_tables_are_spliced_verbatim():
    text = RESULTS.read_text(encoding="utf-8")
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    assert text[a:b] == "\n" + TABLES.read_text(encoding="utf-8")


def test_h19a_and_the_contrasts_are_bound():
    n = _n(); t = _t(); c = n["contrasts"]
    bs = c["B_minus_S"]["blocker"]["P"]
    assert f"**B - S = {bs['difference_points']:+.1f} points, cluster {_ivp(bs['cluster_ci95_points'])}** ({bs['a_only']} vs {bs['b_only']};" in t
    assert f"Tango {_ivp(bs['tango_ci95_points'])}; grid-unconditional {_ivp(bs['exact_unconditional_ci95_points'])}; McNemar p = {bs['mcnemar_exact_p']:.2f}" in t
    assert n["H19a"]["holds"] is False and n["H19a"]["kill_for_the_severity_inference"] is True
    rs = c["R_minus_S"]["blocker"]["P"]
    assert f"**R - S = {rs['difference_points']:+.1f} points, cluster\n  {_ivp(rs['cluster_ci95_points'])}** ({rs['a_only']} vs {rs['b_only']}; Tango {_ivp(rs['tango_ci95_points'])}; grid-unconditional {_ivp(rs['exact_unconditional_ci95_points'])}" in t
    rsc = c["R_minus_S"]["blocker"]["C"]
    assert f"R - S on C = {rsc['difference_points']:+.1f} points\n  {_ivp(rsc['cluster_ci95_points'])}" in t
    bsa = c["B_minus_S"]["any"]["P"]
    assert f"rule B - S on P is {bsa['difference_points']:+.1f} points {_ivp(bsa['cluster_ci95_points'])}" in t
    rsa = c["R_minus_S"]["any"]["P"]; rsac = c["R_minus_S"]["any"]["C"]
    assert f"R - S on P {rsa['difference_points']:+.1f} {_ivp(rsa['cluster_ci95_points'])}, on C {rsac['difference_points']:+.1f} {_ivp(rsac['cluster_ci95_points'])}" in t
    for arm in ("S", "R", "B"):
        u = n["arms"][arm]["blocker"]["P"]["union_at_kmax"]
        assert f"{u['k']}/110 = {_pct(u['rate'])}%" in t


def test_h19d_is_bound():
    n = _n(); t = _t(); h = n["H19d"]
    assert f"for the {h['n_items']} findings on P instances" in _flat()
    assert f"agreement {h['agreement'][0]}/{h['agreement'][1]}, **κ = {h['kappa']:.3f}**; the {len(h['disagreements'])} disputed items" in _flat()
    for arm in ("S", "R", "B"):
        v = h["by_arm"][arm]; r = v["names_rate_over_all_P"]
        assert f"{r['k']} of 110" in t and f"{_pct(r['rate'])}%" in t
    s = h["by_arm"]["S"]; rs = s["names_rate_over_all_P"]
    assert f"**{rs['k']} of 110 P instances = {_pct(rs['rate'])}%** (Wilson {_pct(rs['wilson95'][0])}–{_pct(rs['wilson95'][1])}; cluster {_pct(rs['cluster_ci95'][0])}–{_pct(rs['cluster_ci95'][1])})" in t
    assert f"some finding on {s['P_instances_with_a_finding']} of them — {s['findings_no']} of its {s['findings']} findings" in _flat()
    r = h["by_arm"]["R"]; rr = r["names_rate_over_all_P"]
    assert f"**{rr['k']} of 110 = {_pct(rr['rate'])}%** (Wilson {_pct(rr['wilson95'][0])}–{_pct(rr['wilson95'][1])}; cluster {_pct(rr['cluster_ci95'][0])}–{_pct(rr['cluster_ci95'][1])}; {r['findings_yes']} \"yes\" of {r['findings']} findings)" in _flat()
    st = h["strict_recognition_POST_HOC"]
    assert f"agreement {st['agreement'][0]}/{st['agreement'][1]}, κ = {st['kappa']:.3f}; {len(st['disagreements'])} disputed count as not \"defect\"" in _flat()
    for arm in ("S", "R", "B"):
        v = st["by_arm"][arm]["recognised_rate_over_all_P"]
        assert f"{v['k']} of 110 = {_pct(v['rate'])}%" in _flat()
    sr = st["by_arm"]["R"]["recognised_rate_over_all_P"]
    assert f"**{sr['k']} of 110 = {_pct(sr['rate'])}%** (Wilson {_pct(sr['wilson95'][0])}–{_pct(sr['wilson95'][1])}; cluster {_pct(sr['cluster_ci95'][0])}–{_pct(sr['cluster_ci95'][1])}) — {st['by_arm']['R']['correct']} of R's {st['by_arm']['R']['yes_findings']}" in _flat()
    assert all(n["contrasts"][k][rule][stt]["cluster_seed"] == 20260912 for k in n["contrasts"] for rule in ("blocker", "any") for stt in ("P", "C"))


def test_residual_and_cost_are_bound():
    n = _n(); t = _t(); s = n["secondaries"]; r = s["residual"]
    assert f"moves from {r['ceiling3_residual_n']} to {r['with_R']['n']} with R and not at all with B" in _flat()
    assert r["with_B"]["n"] == r["ceiling3_residual_n"]
    assert f"**${s['ledger_usd_total']:.2f}** from the nine project ledgers ({s['ledger_calls_total']} calls)" in t


def test_the_strict_kappa_and_the_inventory_are_rendered():
    """The recognition κ is a number in the prose (a template placeholder once survived here),
    and the comparison inventory's count equals Table 4's contrast count."""
    st = _n()["H19d"]["strict_recognition_POST_HOC"]
    assert f"its κ ({st['kappa']:.3f}) is lower" in _flat()
    assert "{" not in _t().split("<!-- tables:begin -->")[0].replace("{{", "")
    flat = _flat()
    assert "performs **twelve** paired contrasts" in flat
    assert "Preregistered among them, four" in flat
    for named in ("B − S, BLOCKER, P: the primary", "B − S, BLOCKER, C", "R − S **on P**, under both rules: two contrasts",
                  "B − S under the any-finding rule on P and on C", "R − S on C under either rule",
                  "B − R under both rules on both populations", "against the fixed 6.7% product bar"):
        assert named.replace("−", "-") in flat, named
    assert "the other **twenty** quantities" in flat
    h = _n()["H19d"]["by_arm"]
    for arm in ("S", "R", "B"):
        g = h[arm]["P_instances_named_by_some_finding"]
        assert f"| {g['k']}/{g['n']} = " in _t(), arm      # the registered denominator is rendered
    contrasts = _n()["contrasts"]
    leaves = [(pair, rule, pop) for pair, rules in contrasts.items() for rule, pops in rules.items()
              for pop in pops if isinstance(pops, dict)]
    assert len(leaves) == 12, leaves


def test_the_manifest_does_not_claim_a_blinding_the_study_did_not_have():
    """Round 4: the machine-readable record said the adjudication was allocation-blind while
    §4 said metadata-blind. A record that contradicts the prose is worse than no record.

    D10 mutation: put "allocation" back into either adjudicator's withheld list, or drop L2's
    base_url, and this goes red.
    """
    manifest = json.loads((CODE / "records" / "ceiling3b" / "manifest.json").read_text(encoding="utf-8"))
    adj = manifest["models"]["adjudicators"]
    assert "NOT ALLOCATION-BLIND" in adj["_blinding"]
    for who in ("L1", "L2"):
        assert "allocation" not in adj[who]["withheld_by_the_sheet"]
        assert adj[who]["not_blind_to"]
    assert adj["L2"]["base_url"]
    assert "author" in adj["L1"]["who"]
    assert "derived, not registered" in _flat()
