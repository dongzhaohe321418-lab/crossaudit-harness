"""Study 17 — EXPLORATORY, post hoc, not preregistered: why corroboration keeps wrong tests.

Reads ``records/testgen-val/rows.jsonl`` (no test text) and prints, per rule, where the
kept wrong applications sit and whether the failure that corroborated them in the other
draws is itself a wrong test (one that fails on the canonical solution). Every line
printed here is labelled exploratory in RESULTS-TESTGEN-VAL.md.

    python benchmarks/code/testgen/exploratory_val.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import testgen_val as tv  # noqa: E402


def main() -> int:
    rows = [r for r in tv.load_rows().values() if not r["artefact"] and r["classifiable"]]
    for rule in tv.RULES:
        kept_wrong, kept_wrong_by = [], {}
        corroborated_only_by_wrong = 0
        for r in rows:
            wrong1 = set(r["d1"]["failed_canonical"])
            kw = set(r["kept"][rule]) & wrong1
            if not kw:
                continue
            kept_wrong.append((r["instance_id"], len(kw)))
            key = f"{r['half']}-{r['stratum']}"
            kept_wrong_by[key] = kept_wrong_by.get(key, 0) + len(kw)
            if rule in ("A", "B"):
                # the corroborating failures: draw-k tests failing on this candidate
                only_wrong = True
                for k in (2, 3):
                    fk = set(r[f"d{k}"]["failed_candidate"])
                    wk = set(r[f"d{k}"]["failed_canonical"])
                    if fk - wk:            # a correct draw-k test also fails here
                        only_wrong = False
                if only_wrong:
                    corroborated_only_by_wrong += len(kw)
        n_kw = sum(n for _, n in kept_wrong)
        print(f"{rule}: kept wrong applications {n_kw} on {len(kept_wrong)} instances; "
              f"by half-stratum {dict(sorted(kept_wrong_by.items()))}")
        if rule in ("A", "B"):
            print(f"{rule}: of the {n_kw}, corroborated ONLY by wrong tests in the other draws: "
                  f"{corroborated_only_by_wrong}")
        # the strata the product meets — candidates that pass the visible suite (P and C)
        pc = [r for r in rows if r["stratum"] != "F"]
        kept_pc = sum(len(r["kept"][rule]) for r in pc)
        wrong_pc = sum(len(set(r["kept"][rule]) & set(r["d1"]["failed_canonical"])) for r in pc)
        print(f"{rule}: P and C rows only — wrong among kept {wrong_pc}/{kept_pc}")
    # study 16's three confirm-C false positives: kept or dropped per rule
    fps = [r for r in rows if r["half"] == "confirm" and r["stratum"] == "C" and r["d1"]["failed_candidate"]]
    for r in fps:
        print(f"confirm-C false positive {r['instance_id']}: kept under "
              + ", ".join(f"{rule}={'yes' if r['kept'][rule] else 'no'}" for rule in tv.RULES))
    # the two validated-only instances rule A drops
    seven = tv.validated_only(__import__("testgen").load_rows())
    for r in rows:
        if r["instance_id"] in seven:
            f2, f3 = len(r["d2"]["failed_candidate"]), len(r["d3"]["failed_candidate"])
            print(f"validated-only {r['instance_id']}: draw-2 failing {f2}, draw-3 failing {f3}; "
                  + ", ".join(f"{rule}={'kept' if r['kept'][rule] else 'dropped'}" for rule in tv.RULES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
