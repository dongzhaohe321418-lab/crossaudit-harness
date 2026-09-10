"""RESULTS-CEILING3.md's figures are the records' figures.

Bound, and only these: the spliced table block (byte for byte against
records/ceiling3/tables.md); the primary, H18a and H18c contrasts with their intervals and
paired counts; the two never counts with both intervals; the residual counts; the
prompt-digest count; the ledger cost total and call count; the malformed-reply counts.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
NUMBERS = CODE / "records" / "ceiling3" / "numbers.json"
TABLES = CODE / "records" / "ceiling3" / "tables.md"
RESULTS = CODE / "RESULTS-CEILING3.md"
BEGIN, END = "<!-- BEGIN TABLES (records/ceiling3/tables.md) -->", "<!-- END TABLES -->"


def _n() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))


def _t() -> str:
    return RESULTS.read_text(encoding="utf-8").replace("−", "-")


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def test_the_tables_are_spliced_verbatim():
    text = RESULTS.read_text(encoding="utf-8")
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    assert text[a:b] == "\n" + TABLES.read_text(encoding="utf-8")


def test_the_contrasts_are_bound():
    n = _n(); t = _t()
    pr = n["primary_H18b_self_strong_minus_cross_P"]
    assert f"P = **{pr['difference_points']:.1f} points, problem-cluster 95% [{pr['cluster_ci95_points'][0]:.1f}, {pr['cluster_ci95_points'][1]:.1f}]**" in t
    assert f"{pr['a_only']} instances flagged by `self-strong`\n  only, {pr['b_only']} by `cross` only" in t
    hb = n["H18b_C_false_positives"]
    assert f"On C: {hb['difference_points']:.1f} points, cluster [{hb['cluster_ci95_points'][0]:.1f}, {hb['cluster_ci95_points'][1]:.1f}] ({hb['a_only']} vs {hb['b_only']}" in t
    # ceiling 1's paired-binary checks beside the primary
    assert f"Tango [{pr['tango_ci95_points'][0]:.1f}, {pr['tango_ci95_points'][1]:.1f}], exact unconditional\n  [{pr['exact_unconditional_ci95_points'][0]:.1f}, {pr['exact_unconditional_ci95_points'][1]:.1f}]" in t
    ha = n["H18a_self_strong_minus_self_P"]
    assert f"P at K = 8 = **{ha['difference_points']:.1f} points, cluster [{ha['cluster_ci95_points'][0]:.1f}, {ha['cluster_ci95_points'][1]:.1f}]** ({ha['a_only']} vs {ha['b_only']}" in t
    assert f"sign-flip p = {ha['signflip']['p']:.3f}" in t.replace("\n  ", " ")
    hc = n["H18c_frontier_minus_astra_P_k1_mean_over_draws"]
    assert f"P = **{hc['difference_points']:.1f}\n  points, cluster [{hc['cluster_ci95_points'][0]:.1f}, {hc['cluster_ci95_points'][1]:.1f}]**" in t
    hk = n["H18c_frontier_minus_astra_P_kmax"]
    assert f"K = 4 unions: {hk['difference_points']:.1f}, cluster [{hk['cluster_ci95_points'][0]:.1f}, {hk['cluster_ci95_points'][1]:.1f}] ({hk['a_only']} vs {hk['b_only']}" in t
    hcc = n["H18c_frontier_minus_astra_C_kmax"]
    assert f"on C {hcc['difference_points']:.1f}, cluster [{hcc['cluster_ci95_points'][0]:.1f}, {hcc['cluster_ci95_points'][1]:.1f}]" in t
    assert hk["one_signed_discordance"] is True
    assert f"exact unconditional interval is the one to quote: [{hk['exact_unconditional_ci95_points'][0]:.1f}, {hk['exact_unconditional_ci95_points'][1]:.1f}]" in t
    # the never-gap paired difference and the saturation figures
    gp = n["EXPLORATORY_any_finding_rule"]["gap_blocked_by_none_minus_mentioned_by_none_P"]
    assert f"{gp['difference_points']:.1f} points of the defect population (paired per instance, cluster\n[{gp['cluster_ci95_points'][0]:.1f}, {gp['cluster_ci95_points'][1]:.1f}])" in t
    ss = n["families"]["self-strong"]["P"]
    assert f"the fitted A = {_pct(ss['fit']['A'])}% (cluster {_pct(ss['fit']['A_ci95_cluster'][0])}–{_pct(ss['fit']['A_ci95_cluster'][1])}" in t
    g = ss["flattening_gain_last_step_cluster_ci95"]
    assert f"gain {100 * ss['flattening_gain_last_step']:.2f} points, cluster [{100 * g[0]:.2f}, {100 * g[1]:.2f}]" in t


def test_the_never_counts_and_the_residual_are_bound():
    n = _n(); t = _t()
    nv = n["never_flagged_by_any_family"]
    assert (f"{nv['k']} of {nv['n']} defects = {_pct(nv['rate'])}% (Wilson {_pct(nv['wilson95'][0])}–{_pct(nv['wilson95'][1])}; cluster\n"
            f"  {_pct(nv['cluster_ci95'][0])}–{_pct(nv['cluster_ci95'][1])})") in t
    na = n["EXPLORATORY_any_finding_rule"]["never_any_finding_by_any_family_P"]
    assert (f"{na['k']} of {na['n']} = {_pct(na['rate'])}%** (Wilson {_pct(na['wilson95'][0])}–{_pct(na['wilson95'][1])}; cluster\n{_pct(na['cluster_ci95'][0])}–{_pct(na['cluster_ci95'][1])})") in t
    r = n["residual_classification"]
    by = r["by_category"]
    assert f"({by['unexercised-edge']} unexercised-edge, {by['spec-misreading']} spec-misreading, {by['timeout']} timeout)" in t
    assert f"residual shrank from {r['ceiling1_residual_n']} to {r['n']}" in t
    e = n["EXPLORATORY_any_finding_rule"]["families"]["self-strong"]
    ep, ec = e["P"]["union_at_kmax"], e["C"]["union_at_kmax"]
    assert (f"flag {_pct(ep['rate'])}% of P (cluster {_pct(ep['cluster_ci95'][0])}–{_pct(ep['cluster_ci95'][1])}) "
            f"and {_pct(ec['rate'])}% of C (cluster {_pct(ec['cluster_ci95'][0])}–{_pct(ec['cluster_ci95'][1])})") in t
    fam = n["families"]
    assert (f"the two OpenAI families reach {_pct(fam['cross']['P']['union_at_kmax']['rate'])}% (cluster "
            f"{_pct(fam['cross']['P']['union_at_kmax']['cluster_ci95'][0])}–{_pct(fam['cross']['P']['union_at_kmax']['cluster_ci95'][1])}) and "
            f"{_pct(fam['astra']['P']['union_at_kmax']['rate'])}%") in t
    assert f"{_pct(fam['self']['P']['union_at_kmax']['rate'])}% ({_pct(fam['self']['P']['union_at_kmax']['cluster_ci95'][0])}–{_pct(fam['self']['P']['union_at_kmax']['cluster_ci95'][1])}) for Haiku 4.5" in t


def test_prompt_digests_cost_and_format_counts_are_bound():
    n = _n(); t = _t()
    s2 = {}
    for line in (CODE / "records" / "study2" / "arm-holistic-cross.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line); s2[r["instance_id"]] = r.get("prompt_sha256")
    match = mism = 0
    for f in glob.glob(str(CODE / "records" / "ceiling3" / "cache" / "holistic__self-*__d?.jsonl")):
        for line in Path(f).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("prompt_sha256") == s2.get(r["instance_id"]): match += 1
                else: mism += 1
    assert f"{match:,} of the new families' {match + mism:,}\nreadings carry the same prompt digest" in t
    assert f"the other {mism} are the product's bounded repair prompt" in t
    rf = n["reply_format_secondary"]
    repaired = sum(v["repair_prompt_rows"] for v in rf.values()); still = sum(v["repair_prompt_rows_still_invalid"] for v in rf.values())
    assert repaired == mism
    assert f"the repair succeeded on {repaired - still} of them" in t and f"failed on {still} Opus" in t
    rf = n["reply_format_secondary"]
    total = sum(v["ledger_usd"] for v in rf.values()); calls = sum(v["ledger_calls"] for v in rf.values())
    assert f"**Cost**: ${total:.2f} from the twelve project ledgers" in t and f"{calls:,} calls" in t
    inv_s = sum(v["invalid_reason_nonempty"] for k, v in rf.items() if k.startswith("self-strong"))
    inv_f = sum(v["invalid_reason_nonempty"] for k, v in rf.items() if k.startswith("self-frontier"))
    rows_s = sum(v["rows"] for k, v in rf.items() if k.startswith("self-strong")); rows_f = sum(v["rows"] for k, v in rf.items() if k.startswith("self-frontier"))
    assert f"{inv_s} of {rows_s:,} Sonnet readings and {inv_f} of {rows_f:,} Opus readings" in t
    extra = calls - rows_s - rows_f
    assert f"at\nmost {extra} readings needed the product's repair re-ask" in t
