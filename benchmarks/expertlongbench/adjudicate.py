"""Decide whether an auditor BLOCKER was pointing at something that was actually wrong.

This settles the second question of the study, the one decision **D142** deferred: the
auditor's blocking findings are only worth acting on automatically if most of them are
right. "Right" here is defined against the benchmark's own ground truth rather than
against anyone's opinion:

1. ask a model which rubric item(s) the finding is about (it may be about none -- a
   complaint about formatting or a missing file is a legitimate finding that the rubric
   simply does not cover);
2. look up what CLEAR already decided about those items **in the very output the finding
   was raised against**;
3. the finding is CONFIRMED if any item it cites was in fact scored wrong there, and a
   FALSE POSITIVE if every item it cites was scored correct.

The mapping step is a model call and is therefore fallible; the lookup step is not. The
findings that map to no rubric item are reported as their own bucket and are counted in
neither rate, because the reference checklist has nothing to say about them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from clear import Completion, ItemJudgement, ModelClient
from tasks import Task

CONFIRMED = "confirmed"
FALSE_POSITIVE = "false_positive"
UNMAPPED = "unmapped"
UNREADABLE = "unreadable"

ADJUDICATOR_SYSTEM = (
    "You are mapping a reviewer's objection onto a fixed evaluation rubric. You will be "
    "given the rubric's numbered items and one objection a reviewer raised about a "
    "document. Decide which rubric item or items the objection is about.\n\n"
    "Rules:\n"
    "- Choose an item only if the objection is about the CONTENT that item covers.\n"
    "- Many legitimate objections are about formatting, file structure, missing "
    "deliverables, placeholders, or process. Those are about no rubric item.\n"
    "- Do not stretch. If the objection is not clearly about one of the listed items, "
    "answer NONE.\n\n"
    "Answer with a comma-separated list of item numbers (for example '2' or '1,4'), or "
    "the single word NONE. Answer with nothing else."
)

ADJUDICATOR_USER = (
    "Rubric items:\n{item_definitions}\n\n"
    "The reviewer's objection:\n"
    "  rule cited: {rule}\n"
    "  artifact: {artifact}\n"
    "  observation: {observation}\n\n"
    "Which rubric items is this objection about?"
)


@dataclass(frozen=True)
class Finding:
    """One auditor finding, as recorded in a round's ``findings.json`` / ``report.md``."""

    severity: str
    rule: str
    artifact: str
    observation: str
    tier: str = "model"
    round_no: int = 0


@dataclass(frozen=True)
class Adjudication:
    finding: Finding
    verdict: str
    cited_items: tuple[str, ...] = ()
    #: The per-item CLEAR verdicts that decided it, for audit trail.
    item_was_wrong: dict[str, bool] | None = None
    note: str = ""


def parse_item_numbers(text: str, n_items: int) -> list[int]:
    """Parse the adjudicator's answer into 0-based item indices.

    ``NONE`` -> empty. Out-of-range numbers are dropped rather than raising: a model that
    invents item 9 of a 6-item rubric has told us it could not map the finding.
    """
    cleaned = text.strip()
    if re.search(r"\bnone\b", cleaned, flags=re.IGNORECASE):
        return []
    numbers = [int(match) for match in re.findall(r"\d+", cleaned)]
    return sorted({n - 1 for n in numbers if 1 <= n <= n_items})


class Adjudicator:
    """Maps findings onto rubric items and reads off CLEAR's verdict for them."""

    def __init__(self, client: ModelClient, *, model: str) -> None:
        self.client = client
        self.model = model
        self.calls: list[Completion] = []

    def map_finding(self, task: Task, finding: Finding) -> list[int]:
        completion = self.client.complete(
            model=self.model,
            system=ADJUDICATOR_SYSTEM,
            user=ADJUDICATOR_USER.format(
                item_definitions=task.item_definitions(),
                rule=finding.rule,
                artifact=finding.artifact,
                observation=finding.observation,
            ),
            max_tokens=32,
            temperature=0.0,
        )
        self.calls.append(completion)
        return parse_item_numbers(completion.text, len(task.items))

    def adjudicate(
        self, task: Task, finding: Finding, judgements: Sequence[ItemJudgement]
    ) -> Adjudication:
        """Judge one finding against the CLEAR verdicts for the output it was raised on."""
        by_key = {j.key: j for j in judgements}
        try:
            indices = self.map_finding(task, finding)
        except Exception as exc:  # a provider failure must not be silently scored
            return Adjudication(finding, UNREADABLE, note=f"adjudicator call failed: {exc}")

        if not indices:
            return Adjudication(finding, UNMAPPED, note="the objection is about no rubric item")

        cited = tuple(task.items[i].key for i in indices)
        missing = [key for key in cited if key not in by_key]
        if missing:
            return Adjudication(
                finding, UNREADABLE, cited, note=f"no CLEAR verdict for {missing}"
            )

        # "Wrong" is CLEAR's own accuracy criterion: the item failed mutual containment,
        # i.e. the output and the reference did not say the same thing about it.
        was_wrong = {key: not by_key[key].accuracy_hit for key in cited}
        verdict = CONFIRMED if any(was_wrong.values()) else FALSE_POSITIVE
        return Adjudication(finding, verdict, cited, was_wrong)


def parse_report_findings(report_text: str, round_no: int = 0) -> list[Finding]:
    """Pull findings out of an audit ``report.md``.

    Mirrors ``crossaudit.dispute.parse_findings``' heading grammar
    (``### [SEVERITY] RULE - artifact``) and takes the following prose as the observation.
    ``findings.json`` is preferred where present; it carries the tier and state but not the
    observation text, which the adjudicator needs.
    """
    heading = re.compile(
        r"^### \[(BLOCKER|ADVISORY)\] (CA-[A-Z]+-\d+|DCL:[a-z0-9_-]+) — (.+)$", re.MULTILINE
    )
    findings: list[Finding] = []
    matches = list(heading.finditer(report_text))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        body = report_text[start:end].strip()
        # stop at the next section of the report, whatever it is
        body = re.split(r"^##\s", body, maxsplit=1, flags=re.MULTILINE)[0].strip()
        findings.append(
            Finding(
                severity=match.group(1),
                rule=match.group(2),
                artifact=match.group(3).strip(),
                observation=body,
                tier="deterministic" if match.group(2).startswith("DCL:") else "model",
                round_no=round_no,
            )
        )
    return findings
