"""Exploratory (not registered; added 2026-11-15 after an unanchored review): is E6's flag preference / convention
advantage concentrated where program A's code looks different from B's? Units are split by whether A has more
conditionals (ast If/IfExp nodes) than B; the registered estimands are recomputed on each stratum with E6's frozen
analysis code. Writes records/icml/e6_code_shape_test.json. Reads frozen records only.

    PYTHONPATH=src CROSSAUDIT_BENCH_EXECUTOR=... python benchmarks/code/icml/e6_code_shape.py
"""
import ast
import json

import analyse_e6 as A
import e1
import e6


def conditionals(src: str) -> int:
    return sum(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(ast.parse(src)))


def main(split: str = "test") -> dict:
    cells, units, _, _ = A.merged_open(split, allow_incomplete=False)
    prog = {}
    for kind in ("open", "open2"):
        e6.set_kind(kind)
        us = e6.units(split)
        for pid in units:
            if pid in us and pid not in prog:
                prog[pid] = us[pid]["program"]
    e6.set_kind("open")
    more = [u for u in units if conditionals(prog[u]["a"]) > conditionals(prog[u]["b"])]
    strata = {"all": list(units), "a_more_conditionals": more, "a_not_more": [u for u in units if u not in more]}
    out = {"split": split, "strata_sizes": {k: len(v) for k, v in strata.items()}, "strata": {}}
    for name, us in strata.items():
        _, nv = A.level(cells, us, "none", e6.CONFIGS, 1)
        out["strata"][name] = {
            "flag_pref_none": A.boot({k: v["flag_a"] - v["flag_b"] for k, v in nv.items()}),
            "convention_advantage_none": A.convention(cells, us, e6.CONFIGS, 1),
            "E6_5": A.contrast(cells, us, "sentence", "none", e6.SENTENCE_CONFIGS, e6.SENTENCE_CONFIGS, "cov", 1)}
    (e1.REC / f"e6_code_shape_{split}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    r = main()
    for k, v in r["strata"].items():
        print(k, r["strata_sizes"][k], {m: (round(d["est"], 1), round(d["lo"], 1), round(d["hi"], 1)) for m, d in v.items()})
