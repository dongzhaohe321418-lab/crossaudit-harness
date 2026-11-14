"""Exploratory sensitivity (not registered; added 2026-11-14 after a reviewer found it): the frozen E6 witness scorer
credits no diagnosis when the contract's oracle raises (e1.judge_witness returns outside_domain), so on held-out units
whose rule A requires an exception (Mbpp/93, Mbpp/623) verified diagnosis under contract A is zero by construction.
This script leaves the frozen results untouched and recomputes the registered estimands three ways:

- frozen:     the registered analysis, as a check that it reproduces e6_results_v4_test.json;
- exclude:    the affected units removed;
- exception:  a reading on the program that is defective under contract A also counts as a verified diagnosis under
              contract A when one of its in-class, in-interface, valid witness calls makes the A oracle raise and the
              auditor's stated expectation names an exception (an exception-aware scorer);
- upper:      every flagging reading on that program counts (the largest possible effect of the asymmetry).

    python benchmarks/code/icml/e6_exception_sensitivity.py
"""
from __future__ import annotations

import json
import re

import analyse_e6
import e1
import e6

AFFECTED = ("Mbpp/93", "Mbpp/623")
EXC = re.compile(r"(?i)raise|error|exception")
KEYS = ("E6_1_cov_resolve_minus_menu", "E6_1_abs_resolve_cov", "E6_2_convention_advantage_none",
        "E6_3_cov_high_minus_low_resolve", "E6_5_cov_sentence_minus_none", "flag_pref_a_minus_b_none")


def exception_credit(split: str) -> dict:
    """(pid, program, arm, cfg, reading) -> True when an exception-aware scorer would credit contract A."""
    credit = {}
    previous = e6.KIND
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        us = e6.units(split)
        probs = {p.problem_id: p for p in e6.problems(split)}
        wit = {r["input_sha256"]: r for r in e1.load(e6.WIT) if not r.get("infra")}
        for r in e1.load(e6.AUD):
            pid, prog, arm, cfg, k = r["key"]
            if (pid not in AFFECTED or pid not in us or prog != "b" or r["split"] != split or not r.get("ok")
                    or not r["flagged"] or not r.get("witnesses")):
                continue
            w = wit.get(e6.witness_key(r, us[pid], "a", probs[pid]))
            ok = bool(w) and any(res.get("status") == "outside_domain" and res.get("reference") == "exc"
                                 and res.get("in_class") and res.get("in_interface") and res.get("valid")
                                 and EXC.search(stated.get("expected", ""))
                                 for res, stated in zip(w["results"], r["witnesses"]))
            credit[(pid, prog, arm, cfg, k)] = ok
    e6.set_kind(previous)
    return credit


def run(split: str, mode: str, credit: dict) -> dict:
    original = analyse_e6.merged_open

    def patched(split_, allow_incomplete):
        cells, units, status, beh = original(split_, allow_incomplete)
        if mode == "exclude":
            units = [u for u in units if u not in AFFECTED]
            cells = {k: v for k, v in cells.items() if k[0] in units}
        elif mode in ("exception", "upper"):
            for (pid, prog, arm, cfg), rs in cells.items():
                if pid in AFFECTED and prog == "b":
                    # the policy credits a cell when any flagging reading is verified, so cell-level credit suffices
                    cell_credit = any(v for k, v in credit.items() if k[:4] == (pid, prog, arm, cfg))
                    for x in rs:
                        if x["flag"] and (mode == "upper" or cell_credit):
                            x["vd"]["a"] = True
        return cells, units, status, beh

    analyse_e6.merged_open = patched
    try:
        res = analyse_e6.analyse(split, allow_incomplete=False)
    finally:
        analyse_e6.merged_open = original
    out = {"n_units": res["n_units"], "verdicts": res["verdicts"]}
    for k in KEYS:
        v = res[k]
        out[k] = {f: v.get(f) for f in ("est", "lo", "hi") if f in v}
    return out


if __name__ == "__main__":
    split = "test"
    credit = exception_credit(split)
    out = {"note": __doc__.split("\n\n")[0], "affected_units": AFFECTED,
           "exception_credited_readings": sum(credit.values()), "affected_flagging_readings": len(credit)}
    for mode in ("frozen", "exclude", "exception", "upper"):
        out[mode] = run(split, mode, credit)
    frozen = json.loads((e1.REC / f"e6_results_v4_{split}.json").read_text())
    out["frozen_reproduces"] = all(out["frozen"][k].get("est") == frozen[k].get("est") for k in KEYS)
    (e1.REC / f"e6_exception_sensitivity_{split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
