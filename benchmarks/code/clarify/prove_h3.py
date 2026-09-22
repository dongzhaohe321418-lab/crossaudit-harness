#!/usr/bin/env python3
"""Check P3's outcome code against planted datasets whose answers are known by hand.

An analysis is checked before the data arrives or it is checked by the data, and an analysis
checked by its own data is not checked. Each case below fixes what the three arms did and what
H3 must therefore say; a case that passes for the wrong reason is caught by asserting the
intermediate counts, not only the verdict.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import report_h3 as h3  # noqa: E402

ARMS = ("original", "clarified", "placebo")


def build(tmp: Path, diagnosed: dict[tuple[str, str], list[int]],
          l2_disagrees: set[str] | None = None) -> None:
    """`diagnosed[(instance, arm)]` = the four draws' truth. Writes rows, key and both raters."""
    rows, key, n = [], [], 0
    for (iid, arm), draws in diagnosed.items():
        for d, yes in enumerate(draws, 1):
            rows.append({"ok": True, "instance_id": iid, "condition": arm, "draw": d,
                         "flagged": bool(yes),
                         "findings": ([{"observation": "x"}] if yes else [])})
            if yes:
                n += 1
                key.append({"id": f"P{n:04d}", "instance_id": iid, "arm": arm, "draw": d,
                            "k": 0, "severity": "BLOCKER", "rule": "R"})
    (tmp / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    sheet = tmp / "sheet"
    sheet.mkdir(exist_ok=True)
    (sheet / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in key), encoding="utf-8")
    dis = l2_disagrees or set()
    for who in ("L1", "L2"):
        lines = ["id,label"]
        for k in key:
            lab = "no" if (who == "L2" and k["id"] in dis) else "yes"
            lines.append(f"{k['id']},{lab}")
        (sheet / f"{who}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    h3.ROWS = tmp / "rows.jsonl"
    h3.SHEET = sheet
    h3.OUT = tmp / "h3.json"


def run(tmp: Path) -> dict:
    h3.main()
    return json.loads((tmp / "h3.json").read_text(encoding="utf-8"))


def main() -> int:
    failures = []

    # union_at is exact subset averaging, not sampling: 1 flag in 4 draws, union at 2 is
    # C(3,2) subsets without it out of C(4,2) -> 1 - 3/6 = 0.5
    u = h3.union_at([1, 0, 0, 0], 2)
    if abs(u - 0.5) > 1e-12:
        failures.append(f"union_at([1,0,0,0], 2) = {u}, hand-computed 0.5")
    if abs(h3.union_at([0, 0, 0, 0], 4)) > 1e-12 or abs(h3.union_at([1, 1, 1, 1], 1) - 1) > 1e-12:
        failures.append("union_at is wrong at its endpoints")

    # exact McNemar against the binomial by hand: b=5, c=0 -> 2 * (1/2)^5 = 0.0625
    p = h3.mcnemar_exact(5, 0)
    if abs(p - 2 * 0.5 ** 5) > 1e-12:
        failures.append(f"mcnemar_exact(5,0) = {p}, hand-computed {2 * 0.5 ** 5}")
    if h3.mcnemar_exact(0, 0) != 1.0:
        failures.append("mcnemar_exact with no discordant pairs is not 1.0")

    cases = [
        # name, builder, what H3 must say
        ("clarified diagnosed everywhere, the other two never",
         lambda: {(f"b1:P{i}", a): ([1, 1, 1, 1] if a == "clarified" else [0, 0, 0, 0])
                  for i in range(12) for a in ARMS},
         True, True),
        ("both edited arms rise equally — H3's second half must fail",
         lambda: {(f"b1:P{i}", a): ([0, 0, 0, 0] if a == "original" else [1, 1, 1, 1])
                  for i in range(12) for a in ARMS},
         True, False),
        ("nothing differs — the first half must fail and kill H3",
         lambda: {(f"b1:P{i}", a): [1, 0, 0, 0] for i in range(12) for a in ARMS},
         False, False),
        ("clarified rises more than placebo, both above original",
         lambda: {(f"b1:P{i}", a): ([1, 1, 1, 1] if a == "clarified" else
                                    [1, 0, 0, 0] if a == "placebo" and i < 3 else
                                    [0, 0, 0, 0])
                  for i in range(12) for a in ARMS},
         True, True),
    ]

    for name, make, want_one, want_two in cases:
        tmp = Path(tempfile.mkdtemp())
        try:
            build(tmp, make())
            out = run(tmp)
            H = out["H3"]
            ok = (H["half_one_clarified_beats_original_excluding_zero"] == want_one
                  and H["half_two_placebo_difference_smaller"] == want_two)
            if not ok:
                failures.append(f"{name}: got {H['half_one_clarified_beats_original_excluding_zero']}"
                                f"/{H['half_two_placebo_difference_smaller']}, "
                                f"wanted {want_one}/{want_two}")
            print(f"  [{'ok ' if ok else 'FAIL'}] {name}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # disagreement counts as NOT diagnosed: L2 says no on every item, so nothing is diagnosed
    tmp = Path(tempfile.mkdtemp())
    try:
        d = {(f"b1:P{i}", a): ([1, 1, 1, 1] if a == "clarified" else [0, 0, 0, 0])
             for i in range(12) for a in ARMS}
        build(tmp, d)
        all_ids = {json.loads(l)["id"] for l in (tmp / "sheet/key.jsonl").read_text().splitlines()}
        build(tmp, d, l2_disagrees=all_ids)
        out = run(tmp)
        if out["rates_correct_diagnosis"]["clarified"]["k"] != 0:
            failures.append("rater disagreement did not count as not diagnosed")
        else:
            print("  [ok ] rater disagreement counts as not diagnosed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # one rater missing must refuse, not silently compute
    tmp = Path(tempfile.mkdtemp())
    try:
        build(tmp, {(f"b1:P{i}", a): [0, 0, 0, 0] for i in range(4) for a in ARMS})
        (tmp / "sheet/L2.csv").unlink()
        try:
            h3.main()
            failures.append("a missing second rater did not halt the analysis")
        except SystemExit as exc:
            if "TWO raters" not in str(exc):
                failures.append(f"halted for the wrong reason: {exc}")
            else:
                print("  [ok ] a missing second rater halts rather than computing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for f in failures:
        print(f"      {f}")
    if failures:
        print(f"\n{len(failures)} check(s) failed")
        return 1
    print("\nthe outcome code says what it should on datasets whose answers are known")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
