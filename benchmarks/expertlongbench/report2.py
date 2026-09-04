"""Turn study-2 run directories into the numbers study 1 could not produce.

Study 1 asked "does arm B beat arm A" and answered it on a sample where the audit fired
once. This module answers the two questions that decomposition raised, and it answers them
on the quantities that actually carry the signal:

**Q2 -- does revision help or harm?** Measured *within* an instance: the CLEAR score of the
pre-revision draft against the CLEAR score of the post-revision output, same sample, same
generator, same scorer. n is the number of revisions, not the number of instances, and the
measurement is immune to generation variance because both sides come from the same run.

**Q1 -- why is the auditor silent?** Measured as **recall against ground truth**: for every
rubric item CLEAR marked wrong in a given output, did any finding raised against that same
output name it? Three candidate causes get three separate arms, joined here by label:
``B`` (shipped constitution), ``B-rubric`` (constitution generated from the task's rubric),
and whatever label carried a different auditor model.

The arm-A-vs-arm-B headline is still computed, and is now explicitly secondary.

Pure arithmetic over ``results.json``. No model calls.

Usage::

    python benchmarks/expertlongbench/report2.py runs/<main-run> runs/<b-prime> ...
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from report import compare, significance_sentence, summarise_arm  # noqa: E402
from stats import mean, stderr, wilcoxon_signed_rank, wilson_interval  # noqa: E402

CONFIRMED = "confirmed"
FALSE_POSITIVE = "false_positive"
UNMAPPED = "unmapped"
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class Run:
    path: Path
    label: str
    plan: dict
    instances: list[dict]

    @property
    def arm_b(self) -> list[tuple[str, dict]]:
        return [
            (i["sample_id"], i["arms"]["B"])
            for i in self.instances
            if "B" in i.get("arms", {})
        ]


def load_run(path: Path) -> Run:
    payload = json.loads((path / "results.json").read_text(encoding="utf-8"))
    plan = payload["plan"]
    return Run(path, plan.get("label") or "B", plan, payload["instances"])


# --------------------------------------------------------------------------------------
# Q2 -- the paired pre/post revision measurement
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RevisionSummary:
    label: str
    n_instances: int
    n_revised: int
    deltas: tuple[float, ...]
    mean_delta: float
    stderr_delta: float
    better: int
    worse: int
    unchanged: int
    items_fixed: int
    items_broken: int
    test: object

    @property
    def revision_rate(self):
        return wilson_interval(self.n_revised, self.n_instances)


def revisions(run: Run) -> RevisionSummary:
    """Every instance whose loop actually produced a second draft."""
    pairs = [
        (sample_id, entry["revision"])
        for sample_id, entry in run.arm_b
        if entry.get("revision")
    ]
    deltas = [pair["delta_f1"] * 100 for _, pair in pairs]
    return RevisionSummary(
        label=run.label,
        n_instances=len(run.arm_b),
        n_revised=len(pairs),
        deltas=tuple(deltas),
        mean_delta=mean(deltas),
        stderr_delta=stderr(deltas),
        better=sum(1 for d in deltas if d > 0),
        worse=sum(1 for d in deltas if d < 0),
        unchanged=sum(1 for d in deltas if d == 0),
        items_fixed=sum(len(pair["items_fixed"]) for _, pair in pairs),
        items_broken=sum(len(pair["items_broken"]) for _, pair in pairs),
        test=wilcoxon_signed_rank(deltas) if deltas else None,
    )


def pooled_revisions(runs: list[Run]) -> RevisionSummary:
    """All revisions from every arm, pooled.

    Pooling across arms is legitimate here and only here: every one of these pairs is a
    within-instance before/after with the same generator and the same scorer, so what
    differs between arms (the constitution, the auditor model) changed *which* revisions
    happened, not what a revision's delta means.
    """
    merged = Run(Path("."), "pooled (every arm)", {}, [])
    entries: list[dict] = []
    for run in runs:
        for _sample_id, entry in run.arm_b:
            entries.append({"sample_id": _sample_id, "arms": {"B": entry}})
    merged = Run(Path("."), "pooled (every arm)", {}, entries)
    return revisions(merged)


# --------------------------------------------------------------------------------------
# Q1 -- did the auditor name what was wrong?
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditSummary:
    label: str
    n_instances: int
    n_rounds: int
    rounds_with_findings: int
    instances_with_findings: int
    n_findings: int
    n_blockers: int
    n_advisories: int
    by_rule: dict[str, int]
    #: recall against CLEAR, micro-averaged over rounds: wrong items named / wrong items
    items_wrong: int
    items_named: int
    items_wrong_and_named: int
    items_named_but_correct: int
    macro_recall: float
    #: round-one only, which is where a silent auditor decides the whole loop
    r1_rounds: int
    r1_with_findings: int
    r1_items_wrong: int
    r1_items_wrong_and_named: int
    verdicts: dict[str, int]

    @property
    def micro_recall(self) -> float:
        return self.items_wrong_and_named / self.items_wrong if self.items_wrong else 0.0

    @property
    def r1_recall(self) -> float:
        return self.r1_items_wrong_and_named / self.r1_items_wrong if self.r1_items_wrong else 0.0

    @property
    def firing_rate(self):
        return wilson_interval(self.instances_with_findings, self.n_instances)

    @property
    def item_precision(self):
        named = self.items_wrong_and_named + self.items_named_but_correct
        return wilson_interval(self.items_wrong_and_named, named)


def audit_summary(run: Run) -> AuditSummary:
    n_rounds = rounds_with = instances_with = 0
    n_findings = n_blockers = n_advisories = 0
    wrong = named = both = named_correct = 0
    r1_rounds = r1_with = r1_wrong = r1_both = 0
    per_round_recalls: list[float] = []
    by_rule: dict[str, int] = {}
    verdicts: dict[str, int] = {}

    for _sample_id, entry in run.arm_b:
        rounds = entry.get("audit_recall") or []
        if any(r["n_findings"] for r in rounds):
            instances_with += 1
        for record in rounds:
            n_rounds += 1
            n_findings += record["n_findings"]
            n_blockers += record["n_blockers"]
            n_advisories += record["n_advisories"]
            if record["n_findings"]:
                rounds_with += 1
            for rule in record["rules_cited"]:
                by_rule[rule] = by_rule.get(rule, 0) + 1
            wrong += record["n_items_wrong"]
            named += record["n_items_named"]
            both += record["n_wrong_and_named"]
            named_correct += record["n_named_but_correct"]
            if record["recall"] is not None:
                per_round_recalls.append(record["recall"])
            if record["round"] == 1:
                r1_rounds += 1
                r1_wrong += record["n_items_wrong"]
                r1_both += record["n_wrong_and_named"]
                if record["n_findings"]:
                    r1_with += 1
        for finding in entry.get("findings_mapped", []):
            verdict = finding.get("verdict", UNREADABLE)
            verdicts[verdict] = verdicts.get(verdict, 0) + 1

    return AuditSummary(
        label=run.label,
        n_instances=len(run.arm_b),
        n_rounds=n_rounds,
        rounds_with_findings=rounds_with,
        instances_with_findings=instances_with,
        n_findings=n_findings,
        n_blockers=n_blockers,
        n_advisories=n_advisories,
        by_rule=by_rule,
        items_wrong=wrong,
        items_named=named,
        items_wrong_and_named=both,
        items_named_but_correct=named_correct,
        macro_recall=mean(per_round_recalls),
        r1_rounds=r1_rounds,
        r1_with_findings=r1_with,
        r1_items_wrong=r1_wrong,
        r1_items_wrong_and_named=r1_both,
        verdicts=verdicts,
    )


# --------------------------------------------------------------------------------------
# the task: what could the auditor have checked at all?
# --------------------------------------------------------------------------------------


def checkability(runs: list[Run]) -> dict | None:
    per_item: dict[str, dict[str, int]] = {}
    yes = total = samples = errors = 0
    for run in runs:
        for instance in run.instances:
            probe = instance.get("checkability")
            if not probe:
                continue
            if probe.get("error"):
                errors += 1
                continue
            samples += 1
            for key, verdict in probe["per_item"].items():
                bucket = per_item.setdefault(key, {"yes": 0, "no": 0, "unclear": 0})
                bucket[verdict] = bucket.get(verdict, 0) + 1
                total += 1
                if verdict == "yes":
                    yes += 1
    if not samples:
        return None
    return {
        "samples": samples,
        "errors": errors,
        "fraction_derivable": yes / total if total else 0.0,
        "per_item": per_item,
    }


# --------------------------------------------------------------------------------------
# cost
# --------------------------------------------------------------------------------------


def cost(runs: list[Run]) -> dict:
    out: dict[str, float] = {}
    for run in runs:
        generation = scoring = 0.0
        for instance in run.instances:
            for entry in instance.get("arms", {}).values():
                generation += float(entry.get("cost_usd") or 0.0)
                scoring += float(entry.get("score_cost_usd") or 0.0)
            probe = instance.get("checkability") or {}
            scoring += float(probe.get("cost_usd") or 0.0)
        out[run.label] = generation + scoring
        out[f"{run.label}::generation"] = generation
        out[f"{run.label}::scoring"] = scoring
    out["TOTAL"] = sum(v for k, v in out.items() if "::" not in k and k != "TOTAL")
    return out


# --------------------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------------------


def render(runs: list[Run]) -> str:
    lines: list[str] = []
    add = lines.append

    add("=" * 86)
    add("Q2 -- DOES REVISION HELP OR HARM?  (paired, within-instance, n = revisions)")
    add("=" * 86)
    pooled = pooled_revisions(runs)
    if pooled.n_revised == 0:
        add("No instance in any arm produced a second draft. There is no revision to score.")
    else:
        add(f"revisions measured: {pooled.n_revised} "
            f"(of {pooled.n_instances} arm-B instances across every arm)")
        add(f"mean paired delta (post - pre): {pooled.mean_delta:+.2f} CLEAR F1 "
            f"(SE {pooled.stderr_delta:.2f})")
        add(f"better / worse / unchanged: {pooled.better} / {pooled.worse} / {pooled.unchanged}")
        add(f"rubric items fixed by revision: {pooled.items_fixed}; "
            f"broken by revision: {pooled.items_broken}")
        add(f"deltas: {', '.join(f'{d:+.1f}' for d in sorted(pooled.deltas))}")
        if pooled.test:
            add(f"two-sided Wilcoxon signed-rank: {pooled.test}")
    add("")
    for run in runs:
        summary = revisions(run)
        rate = summary.revision_rate
        add(f"  [{summary.label}] revised {summary.n_revised}/{summary.n_instances} "
            f"({100 * rate.point:.0f}%, 95% CI {100 * rate.low:.0f}-{100 * rate.high:.0f}%); "
            f"mean delta {summary.mean_delta:+.2f} F1; "
            f"items fixed {summary.items_fixed} / broken {summary.items_broken}")

    add("")
    add("=" * 86)
    add("Q1 -- IS THE AUDITOR SILENT, AND WHEN IT SPEAKS DOES IT NAME WHAT IS WRONG?")
    add("=" * 86)
    add(f"{'arm':<20} {'inst':>5} {'fired':>7} {'find':>6} {'blk':>5} "
        f"{'wrong':>6} {'named':>6} {'hit':>5} {'recall':>7} {'r1 rec':>7}")
    for run in runs:
        summary = audit_summary(run)
        add(f"{summary.label:<20} {summary.n_instances:>5} "
            f"{summary.instances_with_findings:>7} {summary.n_findings:>6} "
            f"{summary.n_blockers:>5} {summary.items_wrong:>6} {summary.items_named:>6} "
            f"{summary.items_wrong_and_named:>5} {100 * summary.micro_recall:>6.1f}% "
            f"{100 * summary.r1_recall:>6.1f}%")
    add("")
    add("  fired  = instances where the auditor raised at least one finding of any severity")
    add("  wrong  = rubric items CLEAR scored wrong, summed over every scored round")
    add("  named  = distinct rubric items some finding in that round was about")
    add("  recall = wrong items named / wrong items  (the auditor against ground truth)")
    add("  r1 rec = the same, restricted to round one, where a silent auditor ends the loop")
    add("")
    for run in runs:
        summary = audit_summary(run)
        precision = summary.item_precision
        add(f"  [{summary.label}] rules cited: "
            f"{', '.join(f'{k}x{v}' for k, v in sorted(summary.by_rule.items())) or 'none'}")
        add(f"  [{summary.label}] finding verdicts: "
            f"{', '.join(f'{k}={v}' for k, v in sorted(summary.verdicts.items())) or 'none'}")
        if summary.items_wrong_and_named + summary.items_named_but_correct:
            add(f"  [{summary.label}] of the items it did name, "
                f"{100 * precision.point:.0f}% were in fact wrong "
                f"(95% CI {100 * precision.low:.0f}-{100 * precision.high:.0f}%)")

    add("")
    add("=" * 86)
    add("THE TASK -- what could an auditor reading only the committed bytes check?")
    add("=" * 86)
    probe = checkability(runs)
    if not probe:
        add("not probed in these runs.")
    else:
        add(f"samples probed: {probe['samples']} (errors: {probe['errors']})")
        add(f"reference content derivable from the committed recipe alone: "
            f"{100 * probe['fraction_derivable']:.1f}% of rubric cells")
        for key, counts in sorted(probe["per_item"].items()):
            total = sum(counts.values())
            add(f"  {key[:62]:<62} {100 * counts['yes'] / total:5.1f}% derivable")

    add("")
    add("=" * 86)
    add("SECONDARY -- arm A (single model) vs arm B (CrossAudit)")
    add("=" * 86)
    for run in runs:
        comparison = compare(run.instances)
        if not comparison:
            continue
        for arm in ("A", "B"):
            summary = summarise_arm(run.instances, arm)
            if summary:
                add(f"  [{run.label}] arm {arm}: mean F1 {100 * summary.mean_f1:.1f} "
                    f"(SE {100 * summary.stderr_f1:.1f}) over {summary.n_scored} scored, "
                    f"mean rounds {summary.mean_rounds:.2f}")
        add(f"  [{run.label}] paired B-A = {100 * comparison.mean_difference:+.2f} F1 on "
            f"{comparison.n_pairs} pairs; B won {comparison.wins_b}, A won "
            f"{comparison.wins_a}, {comparison.ties} ties")
        add(f"  [{run.label}] {significance_sentence(comparison)}")

    add("")
    add("=" * 86)
    add("COST")
    add("=" * 86)
    spend = cost(runs)
    for key in sorted(spend):
        add(f"  {key:<34} ${spend[key]:.4f}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="dump the numbers as JSON")
    args = parser.parse_args(argv)

    runs = [load_run(path) for path in args.runs]
    if args.json:
        pooled = pooled_revisions(runs)
        payload = {
            "q2_pooled": {
                "n_revised": pooled.n_revised,
                "n_instances": pooled.n_instances,
                "mean_delta_f1": pooled.mean_delta,
                "stderr": pooled.stderr_delta,
                "better": pooled.better,
                "worse": pooled.worse,
                "unchanged": pooled.unchanged,
                "items_fixed": pooled.items_fixed,
                "items_broken": pooled.items_broken,
                "deltas": list(pooled.deltas),
                "test": str(pooled.test),
            },
            "q2_by_arm": {
                r.label: {
                    "n_revised": revisions(r).n_revised,
                    "n_instances": revisions(r).n_instances,
                    "mean_delta_f1": revisions(r).mean_delta,
                    "deltas": list(revisions(r).deltas),
                    "items_fixed": revisions(r).items_fixed,
                    "items_broken": revisions(r).items_broken,
                }
                for r in runs
            },
            "q1_by_arm": {
                audit_summary(r).label: {
                    "n_instances": audit_summary(r).n_instances,
                    "instances_with_findings": audit_summary(r).instances_with_findings,
                    "n_findings": audit_summary(r).n_findings,
                    "n_blockers": audit_summary(r).n_blockers,
                    "n_advisories": audit_summary(r).n_advisories,
                    "items_wrong": audit_summary(r).items_wrong,
                    "items_named": audit_summary(r).items_named,
                    "items_wrong_and_named": audit_summary(r).items_wrong_and_named,
                    "items_named_but_correct": audit_summary(r).items_named_but_correct,
                    "micro_recall": audit_summary(r).micro_recall,
                    "r1_recall": audit_summary(r).r1_recall,
                    "r1_items_wrong": audit_summary(r).r1_items_wrong,
                    "by_rule": audit_summary(r).by_rule,
                    "verdicts": audit_summary(r).verdicts,
                }
                for r in runs
            },
            "checkability": checkability(runs),
            "cost": cost(runs),
            "arms": {
                r.label: {
                    arm: (
                        None
                        if summarise_arm(r.instances, arm) is None
                        else {
                            "mean_f1": summarise_arm(r.instances, arm).mean_f1,
                            "stderr_f1": summarise_arm(r.instances, arm).stderr_f1,
                            "mean_precision": summarise_arm(r.instances, arm).mean_precision,
                            "mean_recall": summarise_arm(r.instances, arm).mean_recall,
                            "mean_accuracy": summarise_arm(r.instances, arm).mean_accuracy,
                            "n_scored": summarise_arm(r.instances, arm).n_scored,
                            "mean_rounds": summarise_arm(r.instances, arm).mean_rounds,
                            "mean_cost_usd": summarise_arm(r.instances, arm).mean_cost_usd,
                            "mean_wall_s": summarise_arm(r.instances, arm).mean_wall_s,
                        }
                    )
                    for arm in ("A", "B")
                }
                for r in runs
            },
            "paired": {
                r.label: (
                    None
                    if compare(r.instances) is None
                    else {
                        "n_pairs": compare(r.instances).n_pairs,
                        "mean_a": compare(r.instances).mean_a,
                        "mean_b": compare(r.instances).mean_b,
                        "mean_difference": compare(r.instances).mean_difference,
                        "wins_b": compare(r.instances).wins_b,
                        "wins_a": compare(r.instances).wins_a,
                        "ties": compare(r.instances).ties,
                        "test": str(compare(r.instances).test),
                    }
                )
                for r in runs
            },
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(render(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
