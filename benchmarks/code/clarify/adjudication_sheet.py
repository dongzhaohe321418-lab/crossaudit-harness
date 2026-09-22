#!/usr/bin/env python3
"""P3's blind adjudication sheet, built under Amendment 12.

Study 19's builder shows the specification. Here the specification is the manipulation, so it is
not shown: an item carries an opaque id, the candidate, the hidden failure's first failing
inputs with expected and actual values, and the finding text. No arm, no instance id, no
severity, no rule.

The question, unchanged from the core registration: **does this finding state the behaviour the
hidden suite expects at an input the hidden suite exercises, in a way that would let a reader
fix the code without seeing the test?**

Before the sheet is written, every finding is checked for overlap with the sentence its own
condition added. That check is the one Amendment 12 registered, and its counts go beside the
sheet whatever they say: a clarified-arm finding that quotes the clarification is a finding
whose adjudication the blinding cannot protect.

Sheet and key land in the durable archive; they quote model output and corpus specifications.
"""
from __future__ import annotations

import difflib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "expertlongbench"))

import residual_dump  # noqa: E402

ROWS = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/rows.jsonl"
COND = HERE.parent / "records/clarify/conditions.json"
DUMP = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/residual/index.json"
OUT = Path.home() / "Documents/Crossaudit/study-data/wt-clarify-runs/sheet"
SEED = 20260921
RECORD = HERE.parent / "records/clarify/sheet_leak_check.json"


def added_sentences(original: str, edited: str) -> list[str]:
    """The sentences `edited` has and `original` does not, whitespace-normalised."""
    def sents(t):
        return [x.strip() for x in re.split(r"(?<=[.!?])\s+", " ".join(t.split())) if x.strip()]
    o, e = sents(original), sents(edited)
    sm = difflib.SequenceMatcher(None, o, e, autojunk=False)
    out = []
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            out.extend(e[j1:j2])
    return out


def overlap(finding: str, added: list[str]) -> float:
    """Longest run of an added sentence's words the finding reproduces IN ORDER.

    This measures **quotation**, and it was written expecting it to measure reuse. A planted
    close paraphrase scored 0.41 against a 0.50 threshold, and the honest reading of that is
    not that the threshold is wrong: reordering breaks runs, so a run-based metric cannot see a
    paraphrase, and moving the threshold until the planted case passed would have been shaping
    the check around its own test. It keeps the name it earns, and `vocabulary_overlap` below
    measures the other thing.
    """
    fw = " ".join(finding.split()).lower()
    best = 0.0
    for sent in added:
        words = [w for w in re.findall(r"[a-z0-9_]+", sent.lower()) if len(w) > 2]
        if not words:
            continue
        run = hit = 0
        for w in words:
            if w in fw:
                run += 1; hit = max(hit, run)
            else:
                run = 0
        best = max(best, hit / len(words))
    return best


def vocabulary_overlap(finding: str, added: list[str]) -> float:
    """Share of an added sentence's distinct content words the finding uses, in any order.

    An upper bound on reuse rather than a measure of it: a finding that diagnoses the same
    defect independently will share the problem's vocabulary -- `underscore`, `separator`,
    `empty` -- without having read the clarification. Both numbers are reported and neither is
    called "the leak".
    """
    fw = set(re.findall(r"[a-z0-9_]+", " ".join(finding.split()).lower()))
    best = 0.0
    for sent in added:
        words = {w for w in re.findall(r"[a-z0-9_]+", sent.lower()) if len(w) > 2}
        if words:
            best = max(best, len(words & fw) / len(words))
    return best


def failing_block(row: dict) -> str:
    w = (row.get("witness") or {})
    cases = w.get("cases") or []
    if not cases:
        return "> the harness could not recover the failing inputs for this instance"
    lines = ["> the hidden suite's first failing cases:", ">"]
    for c in cases[:3]:
        lines.append(f"> - input `{str(c.get('input'))[:240]}` — "
                     f"expected `{str(c.get('expected'))[:120]}`, "
                     f"got `{str(c.get('actual'))[:120]}`")
    return "\n".join(lines)


def main() -> int:
    conds = json.loads(COND.read_text(encoding="utf-8"))["conditions"]
    witnesses = {r["instance_id"]: r for r in json.loads(DUMP.read_text(encoding="utf-8"))}
    rows = [json.loads(l) for l in ROWS.read_text(encoding="utf-8").splitlines() if l.strip()]

    items, leak = [], {"clarified": [], "placebo": [], "original": []}
    for r in rows:
        if not r.get("ok"):
            continue
        iid, arm = r["instance_id"], r["condition"]
        added = added_sentences(conds[iid]["original"]["spec"], conds[iid][arm]["spec"])
        for k, f in enumerate(r.get("findings") or []):
            text = (f.get("observation") or "").strip()
            if not text:
                continue
            leak[arm].append((overlap(text, added), vocabulary_overlap(text, added)))
            items.append({"instance_id": iid, "arm": arm, "draw": r["draw"], "k": k,
                          "severity": f.get("severity"), "rule": f.get("rule"),
                          "finding": text,
                          "candidate": conds[iid][arm]["candidate"],
                          "failing": failing_block(witnesses.get(iid, {}))})

    random.Random(SEED).shuffle(items)
    OUT.mkdir(parents=True, exist_ok=True)
    body, key = [], []
    for n, it in enumerate(items, 1):
        sid = f"P{n:04d}"
        key.append({"id": sid, **{k: it[k] for k in
                                  ("instance_id", "arm", "draw", "k", "severity", "rule")}})
        body.append(
            f"## {sid}\n\n**CANDIDATE**\n\n```python\n{it['candidate']}\n```\n\n"
            f"**WHERE THE HIDDEN SUITE FAILS**\n\n{it['failing']}\n\n"
            f"**FINDING**\n\n{it['finding']}\n\n"
            f"**{sid} your judgement** — does this finding state the behaviour the hidden suite "
            f"expects at an input it exercises, well enough that a reader could fix the code "
            f"without seeing the test? `yes` / `no` / `cannot tell`\n\n---\n\n")
    (OUT / "sheet.md").write_text("".join(body), encoding="utf-8")
    (OUT / "key.jsonl").write_text("".join(json.dumps(k) + "\n" for k in key), encoding="utf-8")

    def stat(vals, i):
        xs = [x[i] for x in vals]
        return {"max": max(xs) if xs else None,
                "n_over_half": sum(1 for x in xs if x >= 0.5),
                "n_over_threequarters": sum(1 for x in xs if x >= 0.75)}
    summary = {arm: {"n_findings": len(v),
                     "quotation_longest_run": stat(v, 0),
                     "vocabulary_any_order": stat(v, 1)}
               for arm, v in leak.items()}
    # The original arm adds nothing, so `added_sentences` is empty and both metrics are zero by
    # construction. That zero is structural and is NOT evidence that the original arm leaks
    # less; it is the arm the other two are measured against. Said here so the record cannot be
    # read as a three-way comparison when only two of its rows carry information.
    summary["original"]["zero_is_structural"] = True
    summary["original"]["note"] = ("the original condition adds no sentence, so there is "
                                   "nothing for a finding to overlap with; compare clarified "
                                   "against placebo, not against this row")
    RECORD.write_text(json.dumps({"seed": SEED, "n_items": len(items),
                                  "overlap_with_own_conditions_addition": summary},
                                 indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sheet: {len(items)} items -> {OUT/'sheet.md'}")
    for arm, d in sorted(summary.items()):
        q, v = d["quotation_longest_run"], d["vocabulary_any_order"]
        print(f"  {arm:10s} {d['n_findings']:4d} findings; quotation >=50%: {q['n_over_half']}, "
              f">=75%: {q['n_over_threequarters']}; shared vocabulary >=50%: "
              f"{v['n_over_half']}, >=75%: {v['n_over_threequarters']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
