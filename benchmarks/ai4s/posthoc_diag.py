#!/usr/bin/env python3
"""A4S-4 POST HOC fault-specific rescoring. Not registered; the registered result is analyze_diag.py.

Written after review round 1 of the paper branch found findings that the registered lexical rule
counts although they are about something else (a documentation request that mentions the column; a
schema listing that mentions the target). This rule keeps the registered operating points and adds,
per fault type, a requirement that the finding state the fault itself, and where the fault writes
numbers into cells, allows a quoted injected value as the witness:

  F1 mixed units   column named AND (a quoted number equal to an injected cell, or a unit word of
                   the converted unit, or a scale/unit term: "unit", "scale", "mixed", "converted",
                   "magnitude", "factor of");
  F2 negated       column named AND ("negative", or a quoted injected negative value);
  F3 duplicates    a duplication term (unchanged from the registered rule);
  F4 shuffled      target named AND a shuffle term ("shuffl", "permut", "scrambl", "randomi",
                   "misaligned", "does not correspond", "inconsistent with the features");
  F5 swapped       both columns named AND a swap term ("swap", "exchang", "transpos", "misassign",
                   "interchang", "reversed", "mislabel", "belong to", "values of ... under");
  F6 sentinel      column named AND ("-999" or "sentinel" or "placeholder" or "missing-value");
  F7 rounding      column named AND ("round", "integer", "whole number", "no decimal",
                   "truncat", "precision").

The validator is scored as registered (its checks are fault-specific by construction: a named check
on a named column). Writes records/ai4s/diag_posthoc.json.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diag_match import _names, diagnoses, validator_texts  # noqa: E402

REC = HERE.parents[1] / "benchmarks/code/records/ai4s"
OUTREC = REC
ITEMS = HERE.parents[1] / "benchmarks/code/records/ai4s/data_items_ho"   # mirrored item files
K = 4
M = {"cross": 1, "self": 4}                     # the registered operating points

UNIT_WORDS = {"g per m^3": ["g/m", "g per", "grams"], "psi": ["psi"], "kHz": ["khz"],
              "mm": ["mm", "millimet"], "kelvin": ["kelvin", " k)", " k,", " k "],
              "kPa": ["kpa"], "kW": ["kw", "kilowatt"], "degrees C": ["°c", "celsius", "degrees c"],
              "angstrom": ["angstrom", "ångström", "å"], "g/cm^3": ["g/cm", "g cm"]}
SCALE = re.compile(r"\bunits?\b|scale|mixed|converted|conversion|magnitude|factor of|order of", re.I)
TERMS = {
    "F2": re.compile(r"negative", re.I),
    "F4": re.compile(r"shuffl|permut|scrambl|randomi|misalign|does not correspond|"
                     r"inconsistent with the features", re.I),
    "F5": re.compile(r"swap|exchang|transpos|misassign|interchang|reversed|mislabel|belong to|"
                     r"under the wrong|placed under", re.I),
    "F6": re.compile(r"-999|sentinel|placeholder|missing[- ]value", re.I),
    "F7": re.compile(r"round|integer|whole number|no decimal|truncat|precision", re.I),
}
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def injected_values(item: dict) -> set[float]:
    p, f = item["params"], item["fault"]
    if f not in ("F1", "F2", "F6") or "rows" not in p:
        return set()
    rows = list(csv.DictReader(io.StringIO((ITEMS / item["item"] / "data.csv").read_text())))
    return {round(float(rows[r][p["column"]]), 6) for r in p["rows"]}


def fault_specific(item: dict, text: str, inj: set[float]) -> bool:
    d, f, p = item["dataset"], item["fault"], item["params"]
    if f == "F3":
        return diagnoses(d, f, p, text)
    if f == "F5":
        a, b = p["columns"]
        return _names(d, a, text) and _names(d, b, text) and bool(TERMS["F5"].search(text))
    if not _names(d, p["column"], text):
        return False
    quoted = {round(float(x), 6) for x in NUM.findall(text)}
    if f == "F1":
        words = UNIT_WORDS.get(p.get("to_unit", ""), [])
        return bool(quoted & inj) or any(w in text.lower() for w in words) or bool(SCALE.search(text))
    if f in ("F2", "F6"):
        return bool(TERMS[f].search(text)) or bool(quoted & inj)
    return bool(TERMS[f].search(text))


def main() -> int:
    items = {i["item"]: i for i in json.loads((REC / "data_items_ho.json").read_text())["items"]}
    faulty = [i for i, it in items.items() if it["fault"]]
    inj = {i: injected_values(items[i]) for i in faulty}
    nflag = {f: {} for f in M}
    lex = {f: {} for f in M}
    spec = {f: {} for f in M}
    texts = {f: {} for f in M}
    for f in M:
        for d in range(1, K + 1):
            for line in (REC / "diag_readings" / f"{f}.d{d}.jsonl").read_text().splitlines():
                r = json.loads(line)
                i = r["instance_id"]
                nflag[f][i] = nflag[f].get(i, 0) + bool(r["flagged"])
                it = items[i]
                if it["fault"] and r["flagged"]:
                    for t in r["blocker_texts"]:
                        if diagnoses(it["dataset"], it["fault"], it["params"], t):
                            lex[f][i] = True
                        if fault_specific(it, t, inj[i]):
                            spec[f][i] = True
                            texts[f].setdefault(i, t)
    v = {i: diagnoses(items[i]["dataset"], items[i]["fault"], items[i]["params"],
                      " ".join(validator_texts(items[i]["validator"]["checks"]))) for i in faulty}
    out = {"note": "POST HOC; not registered. Operating points as registered.", "families": {}}
    for f in M:
        at = {i for i in faulty if nflag[f].get(i, 0) >= M[f]}
        L = {i for i in at if lex[f].get(i)}
        S = {i for i in at if spec[f].get(i)}
        out["families"][f] = {"lexical": len(L), "fault_specific": len(S),
                              "lexical_not_specific": sorted(L - S),
                              "specific_not_lexical": sorted(S - L)}
    cross_at = {i for i in faulty if nflag["cross"].get(i, 0) >= M["cross"]}
    union_spec = {i for i in faulty if v[i] or (i in cross_at and spec["cross"].get(i))}
    only = sorted(i for i in union_spec if not v[i])
    out["validator"] = sum(v.values())
    out["union_fault_specific"] = len(union_spec)
    out["union_only_items"] = {i: texts["cross"][i] for i in only}
    out["self_minus_cross_note"] = "route comparison"
    (OUTREC / "diag_posthoc.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v_ for k, v_ in out.items() if k != "union_only_items"}, indent=1))
    print("union-only items:", only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
