#!/usr/bin/env python3
"""P3 Amendment 4's manipulation check: did the clarification settle anything?

Registered before it ran. The clarifier is `gpt-5.6-luna`, the least entangled model available
and the weakest, because the Anthropic credit is out and the two strong OpenAI models are the
auditor and a family whose misses define this residual. A weak writer is a real risk to the
design, and the answer is to measure the manipulation rather than to assume it.

Each instance's ORIGINAL and CLARIFIED specification is rated for determinacy on the booklet's
three-option rubric, shuffled together, unlabelled, by a rater that is neither the clarifier nor
the auditor. **The clarification is doing its job only if the clarified specifications are judged
`determined` more often, with the difference excluding zero.** If it is not, no audit reading is
bought and the study reports that.

One rating pass. No audit readings.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "benchmarks/code")
sys.path.insert(0, "benchmarks/expertlongbench")

import report_ceiling as rc  # noqa: E402
from crossaudit.providers import openai_compat as provider  # noqa: E402

RATER = "gpt-5.6-sol"        # Amendment 10: astra had already rated all 44 originals as study 21's L2
KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"
COND = Path("benchmarks/code/records/clarify/conditions.json")
OUT = Path("benchmarks/code/records/clarify/manipulation_check.json")
SEED = 20260922
BATCH = 6

RUBRIC = """For each item you are asked one thing only:

> Does the specification's prose determine what should be returned on the inputs it describes?

  determined    — the specification says. A careful reader can derive what should be returned.
  undetermined  — the specification does not say. Several answers fit this text.
  cannot-tell   — you cannot tell.

`cannot-tell` is a legitimate answer. Do not force a choice to make the sheet look tidy.

Answer with one line per item, exactly `<id>,<label>`, and nothing else."""


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_keys()
    data = json.loads(COND.read_text(encoding="utf-8"))
    conds = data["conditions"]

    # One shuffled sheet carrying both conditions of every instance, with opaque ids. The rater
    # cannot see which condition an item is, and the two arms of a pair are not adjacent.
    sheet = []
    for iid, c in conds.items():
        for arm in ("original", "clarified", "placebo"):
            sheet.append({"iid": iid, "arm": arm, "spec": c[arm]["spec"]})
    random.Random(SEED).shuffle(sheet)
    for n, item in enumerate(sheet, 1):
        item["rid"] = f"M{n:03d}"

    labels: dict[str, str] = {}
    for start in range(0, len(sheet), BATCH):
        chunk = sheet[start:start + BATCH]
        prompt = "\n\n".join(f"## {i['rid']}\n**SPECIFICATION**\n\n```\n{i['spec']}\n```"
                             for i in chunk)
        text = ""
        for attempt in range(3):
            try:
                reply = provider.complete(model=RATER, key_env=KEY_ENV, system=RUBRIC,
                                          prompt=prompt, max_tokens=3000, timeout=240.0)
                text = (getattr(reply, "text", "") or "")
                if text.strip():
                    break
            except Exception as exc:                                   # noqa: BLE001
                print(f"    {chunk[0]['rid']}: {type(exc).__name__} {attempt + 1}/3", flush=True)
            time.sleep(4 * (attempt + 1))
        for m in re.finditer(r"(M\d+)\s*,\s*(determined|undetermined|cannot-tell)", text):
            labels[m.group(1)] = m.group(2)
        print(f"  {chunk[0]['rid']}-{chunk[-1]['rid']}: {len(labels)}/{len(sheet)}", flush=True)

    by_arm = {"original": [], "clarified": [], "placebo": []}
    probs = {}
    for item in sheet:
        lab = labels.get(item["rid"])
        if lab is None:
            continue
        by_arm[item["arm"]].append((item["iid"], 1 if lab == "determined" else 0))
        probs[item["iid"]] = item["iid"].split(":", 1)[1]

    rates = {}
    for arm, rows in by_arm.items():
        k = sum(v for _, v in rows)
        rates[arm] = {"k": k, "n": len(rows), "rate": 100 * k / len(rows) if rows else None}

    # Paired on the instance, clustered by problem: 44 instances sit on 26 problems, 18 of
    # which carry two instances, so the instance is not the independent unit.
    paired: dict[str, dict] = {}
    for arm in ("original", "clarified", "placebo"):
        for iid, v in by_arm[arm]:
            paired.setdefault(iid, {})[arm] = v

    def contrast(treat: str, ref: str) -> dict:
        both = {i: d for i, d in paired.items() if treat in d and ref in d}
        if not both:
            return {"n": 0, "points": None, "ci95": [None, None]}
        by_problem: dict[str, list] = {}
        for iid, d in both.items():
            by_problem.setdefault(probs[iid], []).append((d[treat], d[ref]))
        keys = sorted(by_problem)
        rng = random.Random(SEED)
        diffs = []
        for _ in range(10000):
            a = b = n = 0
            for _ in range(len(keys)):
                for t, r in by_problem[keys[rng.randrange(len(keys))]]:
                    a += t; b += r; n += 1
            if n:
                diffs.append(100 * (a - b) / n)
        diffs.sort()
        pt = 100 * sum(d[treat] - d[ref] for d in both.values()) / len(both)
        return {"n": len(both), "n_problems": len(keys), "points": pt,
                "ci95": [rc.percentile(diffs, 0.025), rc.percentile(diffs, 0.975)]}

    primary = contrast("clarified", "original")      # the bar Amendment 4 registered
    validity = contrast("placebo", "original")       # Amendment 7, reported beside it
    both = {i: d for i, d in paired.items() if "clarified" in d and "original" in d}
    point = primary["points"]
    lo, hi = primary["ci95"]
    passed = bool(lo is not None and lo > 0)

    OUT.write_text(json.dumps({
        "rater": RATER, "clarifier": data.get("model"), "seed": SEED,
        "n_pairs": len(both), "rates": rates,
        "primary_clarified_minus_original": primary,
        "validity_placebo_minus_original": validity,
        "clarified_minus_original_points": point, "cluster_ci95_points": [lo, hi],
        "manipulation_worked": passed,
        "bar": "registered in Amendment 4: clarified judged `determined` more often, "
               "difference excluding zero on the problem-cluster bootstrap",
        "labels": labels,
        "key": {i["rid"]: {"instance_id": i["iid"], "arm": i["arm"]} for i in sheet},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"\noriginal  {rates['original']['k']}/{rates['original']['n']} determined")
    print(f"clarified {rates['clarified']['k']}/{rates['clarified']['n']} determined")
    print(f"placebo   {rates['placebo']['k']}/{rates['placebo']['n']} determined")
    print(f"\nclarified - original {point:+.1f} points, cluster [{lo:+.1f}, {hi:+.1f}], "
          f"n={primary['n']} on {primary['n_problems']} problems   [the registered bar]")
    v = validity
    if v["points"] is not None:
        print(f"placebo   - original {v['points']:+.1f} points, cluster "
              f"[{v['ci95'][0]:+.1f}, {v['ci95'][1]:+.1f}], n={v['n']}   [validity: a placebo "
              f"that reads as MORE determined means the rating tracks length, not information]")
    print(f"\nMANIPULATION {'WORKED — the audit may be bought' if passed else 'FAILED — no audit reading is bought'}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
