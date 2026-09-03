"""Turn a run directory into the two numbers.

**The accuracy question.** Mean CLEAR F1 for arm A (single model) against arm B
(CrossAudit), per task, with the per-instance paired difference and a two-sided Wilcoxon
signed-rank test. The sample size travels with every number, and the summary refuses to
call a result significant on a sample that cannot support the word.

**The confirmation-rate question**, which is what decision D142 deferred
``authority.lone_model_blocker``'s default on. For every BLOCKER the auditor raised, was
the rubric item it cited in fact wrong in the output it was raised against? The rate comes
with a Wilson interval and with the number of findings it rests on, and the findings that
map to no rubric item are shown separately rather than folded into either rate.

Cost per instance is reported for both arms, so any accuracy gain arrives with its price.

This module is pure arithmetic over ``results.json``. It makes no model calls, so it can be
re-run freely and is unit-tested.

Usage::

    python benchmarks/expertlongbench/report.py benchmarks/expertlongbench/runs/<run-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from stats import (  # noqa: E402
    Proportion,
    WilcoxonResult,
    mean,
    stderr,
    wilcoxon_signed_rank,
    wilson_interval,
)

CONFIRMED = "confirmed"
FALSE_POSITIVE = "false_positive"
UNMAPPED = "unmapped"
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class ArmSummary:
    arm: str
    n_scored: int
    n_attempted: int
    mean_f1: float
    stderr_f1: float
    mean_precision: float
    mean_recall: float
    mean_accuracy: float
    mean_cost_usd: float
    mean_score_cost_usd: float
    mean_wall_s: float
    mean_rounds: float
    failures: int


@dataclass(frozen=True)
class PairedComparison:
    n_pairs: int
    mean_a: float
    mean_b: float
    mean_difference: float
    wins_b: int
    wins_a: int
    ties: int
    test: WilcoxonResult
    differences: tuple[float, ...]


@dataclass(frozen=True)
class BlockerSummary:
    total_blockers: int
    rubric_relevant: int
    confirmed: int
    false_positive: int
    unmapped: int
    unreadable: int
    confirmation_rate: Proportion
    false_positive_rate: Proportion
    by_rule: dict[str, dict[str, int]]


def _arm_entries(instances: list[dict], arm: str) -> list[dict]:
    return [i["arms"][arm] for i in instances if arm in i.get("arms", {})]


def summarise_arm(instances: list[dict], arm: str) -> ArmSummary | None:
    entries = _arm_entries(instances, arm)
    if not entries:
        return None
    scored = [e for e in entries if e.get("score")]
    f1s = [e["score"]["f1"] for e in scored]
    return ArmSummary(
        arm=arm,
        n_scored=len(scored),
        n_attempted=len(entries),
        mean_f1=mean(f1s),
        stderr_f1=stderr(f1s),
        mean_precision=mean([e["score"]["precision"] for e in scored]),
        mean_recall=mean([e["score"]["recall"] for e in scored]),
        mean_accuracy=mean([e["score"]["accuracy"] for e in scored]),
        mean_cost_usd=mean([e.get("cost_usd", 0.0) for e in entries]),
        mean_score_cost_usd=mean([e.get("score_cost_usd", 0.0) for e in entries]),
        mean_wall_s=mean([e.get("wall_s", 0.0) for e in entries]),
        mean_rounds=mean([e.get("rounds", 0) for e in entries]),
        failures=sum(1 for e in entries if not e.get("ok")),
    )


def compare(instances: list[dict]) -> PairedComparison | None:
    """Paired A-vs-B over instances where *both* arms produced a scored output.

    Pairing is the whole point: the instances differ enormously in difficulty, so an
    unpaired comparison of means would be dominated by which samples each arm happened to
    complete.
    """
    pairs = []
    for instance in instances:
        arms = instance.get("arms", {})
        a, b = arms.get("A"), arms.get("B")
        if a and b and a.get("score") and b.get("score"):
            pairs.append((a["score"]["f1"], b["score"]["f1"]))
    if not pairs:
        return None

    differences = [b - a for a, b in pairs]
    return PairedComparison(
        n_pairs=len(pairs),
        mean_a=mean([a for a, _ in pairs]),
        mean_b=mean([b for _, b in pairs]),
        mean_difference=mean(differences),
        wins_b=sum(1 for d in differences if d > 0),
        wins_a=sum(1 for d in differences if d < 0),
        ties=sum(1 for d in differences if d == 0),
        test=wilcoxon_signed_rank(differences),
        differences=tuple(differences),
    )


def summarise_blockers(instances: list[dict]) -> BlockerSummary:
    """Confirmation and false-positive rates over every adjudicated arm-B BLOCKER."""
    counts = {CONFIRMED: 0, FALSE_POSITIVE: 0, UNMAPPED: 0, UNREADABLE: 0}
    by_rule: dict[str, dict[str, int]] = {}
    for instance in instances:
        for adjudication in instance.get("arms", {}).get("B", {}).get("adjudications", []):
            verdict = adjudication.get("verdict", UNREADABLE)
            counts[verdict] = counts.get(verdict, 0) + 1
            rule = adjudication.get("rule", "?")
            by_rule.setdefault(rule, {}).setdefault(verdict, 0)
            by_rule[rule][verdict] += 1

    # Only findings the rubric can rule on enter the rates. A complaint about a missing
    # file is not a false positive just because the rubric is silent about files.
    relevant = counts[CONFIRMED] + counts[FALSE_POSITIVE]
    return BlockerSummary(
        total_blockers=sum(counts.values()),
        rubric_relevant=relevant,
        confirmed=counts[CONFIRMED],
        false_positive=counts[FALSE_POSITIVE],
        unmapped=counts[UNMAPPED],
        unreadable=counts[UNREADABLE],
        confirmation_rate=wilson_interval(counts[CONFIRMED], relevant),
        false_positive_rate=wilson_interval(counts[FALSE_POSITIVE], relevant),
        by_rule=by_rule,
    )


# --------------------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------------------


def significance_sentence(comparison: PairedComparison) -> str:
    """Say what the p-value does and does not license, given this n."""
    test = comparison.test
    p = test.p_value
    n = test.n_used
    if n == 0:
        return "Every pair was an exact tie, so there is nothing to test."
    if n < 6:
        return (
            f"n = {n} usable pairs. A two-sided signed-rank test cannot reach p < 0.05 "
            f"below n = 6 whatever the data say, so the p-value of {p:.3f} is reported for "
            "completeness and settles nothing. This is a pilot, not a result."
        )
    if p < 0.05:
        return (
            f"p = {p:.4f} ({test.method}) on n = {n} usable pairs. That clears the "
            "conventional threshold, on a sample small enough that a single instance could "
            "move it; it is evidence, not a settled effect."
        )
    return (
        f"p = {p:.4f} ({test.method}) on n = {n} usable pairs -- not significant at 0.05. "
        "On a sample this size that is as consistent with a real effect too small to detect "
        "as with no effect at all, and it must not be reported as either."
    )


def headline(comparison: PairedComparison | None, arm_a: ArmSummary | None,
             arm_b: ArmSummary | None) -> str:
    """The first sentence. If the loop lost, it says so here."""
    if comparison is None:
        return (
            "**No paired result.** No instance produced a scored output in both arms, so "
            "the accuracy question is unanswered by this run."
        )
    delta = comparison.mean_difference
    n = comparison.n_pairs
    a, b = comparison.mean_a * 100, comparison.mean_b * 100
    if delta > 0:
        verdict = f"the audit loop scored **{delta * 100:+.1f} F1 higher** than the single model"
    elif delta < 0:
        verdict = (
            f"the audit loop scored **{delta * 100:+.1f} F1 — that is, *worse*** than the "
            "single model"
        )
    else:
        verdict = "the audit loop and the single model scored identically"
    return (
        f"**On n = {n} paired instances, {verdict}** "
        f"(arm A {a:.1f}, arm B {b:.1f}, CLEAR F1 scaled 0–100). "
        f"Arm B won {comparison.wins_b}, arm A won {comparison.wins_a}, "
        f"{comparison.ties} tied."
    )


def render(payload: dict) -> str:
    plan = payload.get("plan", {})
    instances = payload.get("instances", [])
    arm_a = summarise_arm(instances, "A")
    arm_b = summarise_arm(instances, "B")
    comparison = compare(instances)
    blockers = summarise_blockers(instances)

    lines: list[str] = []
    add = lines.append

    task = plan.get("task", "?")
    add(f"# {task} — arm A vs arm B")
    add("")
    add(headline(comparison, arm_a, arm_b))
    add("")

    add("## Run")
    add("")
    add(f"- task: `{task}`, **n = {plan.get('n', len(instances))}**, seed `{plan.get('seed')}`")
    add(f"- corpus sha256: `{plan.get('corpus_sha256', '?')[:16]}...` (pinned in manifest.json)")
    models = plan.get("models", {})
    for role in ("generator", "auditor", "mapper", "judge", "adjudicator"):
        if role in models:
            add(f"- {role}: `{models[role]}`")
    settings = plan.get("settings", {})
    if settings:
        add(f"- settings: {', '.join(f'{k}={v}' for k, v in settings.items())}")
    add("")

    add("## The accuracy question")
    add("")
    if comparison is None:
        add("No paired instances.")
    else:
        add("| | arm A (single model) | arm B (CrossAudit) |")
        add("|---|---|---|")
        for label, key in (
            ("mean F1", "mean_f1"),
            ("mean precision", "mean_precision"),
            ("mean recall", "mean_recall"),
            ("mean accuracy", "mean_accuracy"),
        ):
            a_value = getattr(arm_a, key) * 100 if arm_a else float("nan")
            b_value = getattr(arm_b, key) * 100 if arm_b else float("nan")
            add(f"| {label} | {a_value:.1f} | {b_value:.1f} |")
        if arm_a and arm_b:
            add(f"| std error of F1 | {arm_a.stderr_f1 * 100:.1f} | {arm_b.stderr_f1 * 100:.1f} |")
            add(f"| instances scored | {arm_a.n_scored}/{arm_a.n_attempted} | "
                f"{arm_b.n_scored}/{arm_b.n_attempted} |")
            add(f"| failures | {arm_a.failures} | {arm_b.failures} |")
            add(f"| mean rounds | {arm_a.mean_rounds:.2f} | {arm_b.mean_rounds:.2f} |")
        add("")
        add(f"Mean paired difference (B − A): **{comparison.mean_difference * 100:+.2f} F1**.")
        add("")
        add(significance_sentence(comparison))
        add("")
        add(f"Signed-rank detail: W+ = {comparison.test.w_plus:g}, "
            f"W− = {comparison.test.w_minus:g}, statistic = {comparison.test.statistic:g}."
            + (f" {comparison.test.note}." if comparison.test.note else ""))
        add("")
        add("### Per-instance paired differences")
        add("")
        add("| instance | arm A F1 | arm B F1 | B − A |")
        add("|---|---:|---:|---:|")
        for instance in instances:
            arms = instance.get("arms", {})
            a, b = arms.get("A"), arms.get("B")
            if not (a and b and a.get("score") and b.get("score")):
                continue
            a_f1, b_f1 = a["score"]["f1"] * 100, b["score"]["f1"] * 100
            short = instance["sample_id"].split("-", 1)[-1]
            add(f"| `{short}` | {a_f1:.1f} | {b_f1:.1f} | {b_f1 - a_f1:+.1f} |")
        add("")

    add("## The confirmation-rate question (D142)")
    add("")
    if blockers.total_blockers == 0:
        add("**The auditor raised no BLOCKER in arm B.** With zero findings there is no "
            "confirmation rate, and this run cannot inform `authority.lone_model_blocker`'s "
            "default either way.")
    else:
        add(f"The auditor raised **{blockers.total_blockers} BLOCKER"
            f"{'' if blockers.total_blockers == 1 else 's'}** across arm B.")
        add("")
        add(f"- about a rubric item, so the reference can rule on them: "
            f"**{blockers.rubric_relevant}**")
        add(f"- about no rubric item (formatting, missing deliverable, process): "
            f"**{blockers.unmapped}** — counted in neither rate")
        if blockers.unreadable:
            add(f"- could not be adjudicated: **{blockers.unreadable}**")
        add("")
        if blockers.rubric_relevant == 0:
            add("**No BLOCKER was about anything the rubric covers**, so neither rate can be "
                "computed. That is itself a finding: on this task the auditor's objections "
                "were about the shape of the deliverable rather than the correctness of its "
                "claims.")
        else:
            add(f"- **confirmation rate: {blockers.confirmation_rate.describe()}** — the "
                "cited item really was scored wrong in the output the finding was raised on")
            add(f"- **false-positive rate: {blockers.false_positive_rate.describe()}**")
            add("")
            add(f"These rates rest on **{blockers.rubric_relevant} findings**. "
                + ("That is far too few to set a policy default on; the interval spans most "
                   "of the range." if blockers.rubric_relevant < 20 else
                   "Read the interval, not the point estimate."))
        if blockers.by_rule:
            add("")
            add("| rule | confirmed | false positive | unmapped |")
            add("|---|---:|---:|---:|")
            for rule in sorted(blockers.by_rule):
                counts = blockers.by_rule[rule]
                add(f"| `{rule}` | {counts.get(CONFIRMED, 0)} | "
                    f"{counts.get(FALSE_POSITIVE, 0)} | {counts.get(UNMAPPED, 0)} |")
    add("")

    add("## What it cost")
    add("")
    add("| | arm A | arm B |")
    add("|---|---:|---:|")
    if arm_a and arm_b:
        add(f"| generation cost per instance | ${arm_a.mean_cost_usd:.4f} | "
            f"${arm_b.mean_cost_usd:.4f} |")
        add(f"| wall time per instance | {arm_a.mean_wall_s:.1f}s | {arm_b.mean_wall_s:.1f}s |")
        add(f"| scoring cost per instance | ${arm_a.mean_score_cost_usd:.4f} | "
            f"${arm_b.mean_score_cost_usd:.4f} |")
        if arm_a.mean_cost_usd > 0:
            ratio = arm_b.mean_cost_usd / arm_a.mean_cost_usd
            add("")
            add(f"Arm B costs **{ratio:.1f}×** arm A per instance to generate.")
            if comparison and comparison.mean_difference != 0:
                add(f"That buys {comparison.mean_difference * 100:+.2f} F1.")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("run_dir", help="a run directory produced by run.py")
    parser.add_argument("--out", default="", help="write the markdown here as well as stdout")
    args = parser.parse_args(argv)

    results = Path(args.run_dir) / "results.json"
    if not results.exists():
        raise SystemExit(f"{results} not found")
    text = render(json.loads(results.read_text(encoding="utf-8")))
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
