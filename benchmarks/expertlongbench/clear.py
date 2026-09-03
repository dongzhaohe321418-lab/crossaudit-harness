"""CLEAR -- a reimplementation of ExpertLongBench's checklist-based scorer.

Grounded in arXiv:2506.01241v1 section 4 and appendix C. Read ``NOTES.md`` before changing
anything here; every design decision below cites the section it comes from, and the
authors released no reference implementation to diff against.

The pipeline, per model output:

1. **map** -- one model call extracts, for each rubric item, what the output says about it,
   returning ``"N/A"`` where the output says nothing (S-3.2, S-4.1);
2. **judge** -- two binary containment calls per item, in both directions (S-C.2);
3. **score** -- precision, recall, accuracy and F1 over the *full* checklist (S-4.1).

The arithmetic in :func:`score_sample` is deliberately free of model calls so it can be
unit-tested against hand-built cases.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

from tasks import RubricItem, Task

NA = "N/A"


# --------------------------------------------------------------------------------------
# The model seam
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Completion:
    """One model response, with whatever metering the provider gave us."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0


class ModelClient(Protocol):
    """Minimal seam over a chat model.

    ``benchmarks/expertlongbench/provider.py`` implements this against CrossAudit's own
    provider layer, so mapper and judge calls are configured and metered the same way the
    product's calls are. Tests implement it with a scripted stub.
    """

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> Completion: ...


# --------------------------------------------------------------------------------------
# Prompts (S-3.2 Table 10 style for the mapper; S-C.2 Table 44 verbatim for the judge)
# --------------------------------------------------------------------------------------

#: The paper's mapper is a role-playing extraction prompt, per-task, emitting JSON keyed by
#: checklist item, with "N/A" where the source says nothing (S-3.2 "Checklist-mapped
#: Reference Creation"; reused for model outputs at S-4.1). The paper prints only the
#: per-task variants (e.g. Table 10 for T03); this is the generalised form, which is a
#: documented deviation.
MAPPER_SYSTEM = (
    "You are a {domain} expert working as research staff. Your task is to examine the given "
    "text using the provided checklist and extract, for each checklist item, all of the "
    "relevant information that the text contains.\n\n"
    "Guidelines:\n"
    "- Extract the relevant information for each item as comprehensively as possible.\n"
    "- The information must be explicitly and directly present in the text. Do NOT infer, "
    "assume, or add anything that is not there.\n"
    "- If the text contains no information relevant to an item, return exactly \"N/A\" for "
    "that item.\n"
    "- Each extracted value must be as detailed and complete as possible, and may span more "
    "than one sentence.\n"
    "- Do not copy content from one item into another; assign each piece of information to "
    "the item whose definition it matches.\n\n"
    "Output format: a single JSON object whose keys are exactly the item numbers "
    "(\"item_1\", \"item_2\", ...) given below and whose values are strings. Output the JSON "
    "object and nothing else."
)

MAPPER_USER = (
    "Checklist item definitions:\n{item_definitions}\n\n"
    "Text to extract from:\n<text>\n{text}\n</text>\n\n"
    "Return the JSON object with keys item_1 .. item_{n}."
)

#: Verbatim from paper Table 44 (S-C.2), including both printed exemplars. The paper's
#: "{Few-shot examples placeholder}" is not recoverable -- see "Deviations from CLEAR".
JUDGE_SYSTEM = (
    "You are judging whether a model has generated an answer consistent with the ground "
    "truth. An model's answer will be longer and can be considered correct if it contains "
    "the semantic content of short reference answer somewhere within it. Don't worry about "
    "factuality with respect to the real world, just judge the example based on what you "
    "see. No need to overthink this task, it really comes down to just soft matching. "
    "Answer with only the word 'Yes' or 'No'.\n\n"
    "Model Answer: Dates of All Decrees: May 8, 2015; June 8, 2015; June 30, 2015; "
    "October 7, 2015; October 15, 2015; October 20, 2015; April 12, 2017; May 10, 2017; "
    "June 26, 2017; June 27, 2017; July 26, 2017; September 21, 2017; October 3, 2017; "
    "April 1, 2018; 2018; April 1, 2019\n\n"
    "Reference Answer: Dates of All Decrees: October 15, 2014; May 8, 2015; June 8, 2015; "
    "June 30, 2015; October 7, 2015; October 15, 2015; October 20, 2015; July 11, 2016; "
    "April 12, 2017; May 10, 2017; June 26, 2017; June 27, 2017; July 26, 2017; "
    "September 21, 2017; October 3, 2017; April 1, 2018; April 1, 2019\n\n"
    "Correct: No\n\n"
    "Model Answer: Remedy Sought: Injunction to stop smoking and prohibit the sale of "
    "tobacco products in prisons\n\n"
    "Reference Answer: Remedy Sought: injunction to stop the smoking at Crossroads and other "
    "correctional centers, as well as prohibiting the sale of tobacco products in prisons\n\n"
    "Correct: Yes"
)

JUDGE_USER = "Model Answer: {model_answer}\n\nReference Answer: {reference_answer}\n\nCorrect:"


class NAPolicy(str, Enum):
    """How to treat reference or response cells that are the literal string ``"N/A"``.

    ``LITERAL`` (default) is the faithful reading of S-4.1: the paper gives no ``"N/A"``
    carve-out for the performance-assessment judge, its denominator is the whole checklist,
    and only this reading reproduces the magnitude of the paper's reported T3 scores. Every
    item, including ``"N/A"`` ones, goes to the judge as text.

    ``EXACT_MATCH`` short-circuits the both-sides-``"N/A"`` case to correct without a model
    call. Cheaper and arguably more sensible, but it is *not* what the paper describes, and
    it inflates scores. Available for sensitivity analysis only; if you report a number
    under this policy you must say so.
    """

    LITERAL = "literal"
    EXACT_MATCH = "exact-match"


def is_na(value: str | None) -> bool:
    return value is None or value.strip().upper() in {"N/A", "NA", "N.A.", ""}


# --------------------------------------------------------------------------------------
# The arithmetic (no model calls -- this is what the unit tests pin)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemJudgement:
    """The two directional containment verdicts for one checklist item.

    ``precision_hit``: the *reference* contains the model's content for this item, i.e.
    the model said nothing the reference does not support (S-4.1: "the fraction of
    checklist items whose model response is semantically contained within the reference").

    ``recall_hit``: the *model response* contains the reference's content for this item.
    """

    key: str
    precision_hit: bool
    recall_hit: bool
    response_content: str = ""
    reference_content: str = ""

    @property
    def accuracy_hit(self) -> bool:
        """Mutual containment (S-4.1 "accuracy")."""
        return self.precision_hit and self.recall_hit


@dataclass(frozen=True)
class SampleScore:
    """Sample-level CLEAR metrics. All fractions of the *full* checklist length."""

    sample_id: str
    n_items: int
    precision: float
    recall: float
    accuracy: float
    f1: float
    judgements: tuple[ItemJudgement, ...] = ()

    def to_json(self) -> dict:
        """Digest-safe: counts and scores only, never dataset text."""
        return {
            "sample_id": self.sample_id,
            "n_items": self.n_items,
            "precision": self.precision,
            "recall": self.recall,
            "accuracy": self.accuracy,
            "f1": self.f1,
            "per_item": {
                j.key: {"precision_hit": j.precision_hit, "recall_hit": j.recall_hit}
                for j in self.judgements
            },
        }


def score_sample(sample_id: str, judgements: Sequence[ItemJudgement], n_items: int | None = None) -> SampleScore:
    """Compute sample-level precision / recall / accuracy / F1 (S-4.1).

    The denominator is ``n_items`` -- the length of the task's checklist -- not the number
    of items the model addressed and not the number of non-``N/A`` reference cells. If
    ``n_items`` is omitted it defaults to ``len(judgements)``; passing it explicitly lets a
    caller assert that every rubric item was judged.

    F1 is the harmonic mean of this sample's precision and recall, and is ``0.0`` when both
    are zero. Task-level scores are the *mean of these sample F1s* (see
    :func:`aggregate`), never the F1 of pooled counts.
    """
    total = len(judgements) if n_items is None else n_items
    if total <= 0:
        raise ValueError("a checklist must have at least one item")
    if n_items is not None and len(judgements) != n_items:
        raise ValueError(
            f"{sample_id}: got {len(judgements)} judgements for a {n_items}-item checklist; "
            "every rubric item must be judged, because the metric's denominator is the whole "
            "checklist"
        )

    precision = sum(j.precision_hit for j in judgements) / total
    recall = sum(j.recall_hit for j in judgements) / total
    accuracy = sum(j.accuracy_hit for j in judgements) / total
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    return SampleScore(
        sample_id=sample_id,
        n_items=total,
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        f1=f1,
        judgements=tuple(judgements),
    )


@dataclass(frozen=True)
class TaskScore:
    task_id: str
    n_samples: int
    mean_f1: float
    mean_precision: float
    mean_recall: float
    mean_accuracy: float


def aggregate(task_id: str, scores: Sequence[SampleScore]) -> TaskScore:
    """Task-level performance: the mean of the sample-level metrics (S-4.1)."""
    if not scores:
        raise ValueError("no samples to aggregate")
    n = len(scores)
    return TaskScore(
        task_id=task_id,
        n_samples=n,
        mean_f1=sum(s.f1 for s in scores) / n,
        mean_precision=sum(s.precision for s in scores) / n,
        mean_recall=sum(s.recall for s in scores) / n,
        mean_accuracy=sum(s.accuracy for s in scores) / n,
    )


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------


def parse_yes_no(text: str) -> bool:
    """Parse the judge's verdict. 'Yes' -> 1, 'No' -> 0 (Table 44 caption).

    The prompt asks for a bare word, but models garnish. We take the first standalone
    yes/no token and raise if there is none, rather than defaulting -- a silently
    defaulted judgement would bias the study in whichever direction the default points.
    """
    match = re.search(r"\b(yes|no)\b", text.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"judge did not answer Yes or No: {text[:200]!r}")
    return match.group(1).lower() == "yes"


def parse_mapper_json(text: str, items: Sequence[RubricItem]) -> dict[str, str]:
    """Parse the mapper's JSON into ``{rubric key: extracted content}``.

    Accepts a fenced code block. Missing keys become ``"N/A"`` -- an item the mapper
    declined to emit is an item the output said nothing about, which is what ``"N/A"``
    means.
    """
    blob = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", blob, flags=re.DOTALL)
    if fence:
        blob = fence.group(1).strip()
    start, end = blob.find("{"), blob.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"mapper returned no JSON object: {text[:200]!r}")
    payload = json.loads(blob[start : end + 1])

    out: dict[str, str] = {}
    for index, item in enumerate(items, start=1):
        value = payload.get(f"item_{index}")
        if value is None:
            value = payload.get(item.key, payload.get(item.name))
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        out[item.key] = NA if value is None else str(value).strip() or NA
    return out


# --------------------------------------------------------------------------------------
# The scorer
# --------------------------------------------------------------------------------------


@dataclass
class ScoreCost:
    """Metering for one scoring pass."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0

    def add(self, completion: Completion) -> None:
        self.calls += 1
        self.input_tokens += completion.input_tokens
        self.output_tokens += completion.output_tokens
        self.cost_usd += completion.cost_usd
        self.latency_s += completion.latency_s


@dataclass
class ScoredOutput:
    score: SampleScore
    mapped: dict[str, str] = field(default_factory=dict)
    cost: ScoreCost = field(default_factory=ScoreCost)


class ClearScorer:
    """CLEAR as described in S-4.

    ``mapper_model`` and ``judge_model`` are separate parameters on purpose. The paper uses
    an open-weight mapper (Qwen2.5-72B) and GPT-4o as judge (S-4.1). The runner defaults
    the judge to a *different vendor* from the one that produced the output under test, so
    a model is never the sole judge of its own work.
    """

    def __init__(
        self,
        client: ModelClient,
        *,
        mapper_model: str,
        judge_model: str,
        na_policy: NAPolicy = NAPolicy.LITERAL,
        max_mapper_tokens: int = 4096,
    ) -> None:
        self.client = client
        self.mapper_model = mapper_model
        self.judge_model = judge_model
        self.na_policy = na_policy
        self.max_mapper_tokens = max_mapper_tokens

    # -- stage 1 -----------------------------------------------------------------------

    def map_checklist(self, task: Task, text: str, cost: ScoreCost) -> dict[str, str]:
        """Extract a checklist from ``text`` against ``task``'s rubric (S-4.1)."""
        if not text.strip():
            return {item.key: NA for item in task.items}
        completion = self.client.complete(
            model=self.mapper_model,
            system=MAPPER_SYSTEM.format(domain=task.domain),
            user=MAPPER_USER.format(
                item_definitions=task.item_definitions(), text=text, n=len(task.items)
            ),
            max_tokens=self.max_mapper_tokens,
            temperature=0.0,
        )
        cost.add(completion)
        return parse_mapper_json(completion.text, task.items)

    # -- stage 2 -----------------------------------------------------------------------

    def _contains(self, container: str, contained: str, item: RubricItem, cost: ScoreCost) -> bool:
        """Ask the judge whether ``container`` semantically contains ``contained``.

        Both sides are prefixed with the item name, matching the two exemplars printed in
        Table 44 ("Remedy Sought: ...").
        """
        completion = self.client.complete(
            model=self.judge_model,
            system=JUDGE_SYSTEM,
            user=JUDGE_USER.format(
                model_answer=f"{item.name}: {container}",
                reference_answer=f"{item.name}: {contained}",
            ),
            max_tokens=8,
            temperature=0.0,
        )
        cost.add(completion)
        return parse_yes_no(completion.text)

    def judge_item(
        self, item: RubricItem, response: str, reference: str, cost: ScoreCost
    ) -> ItemJudgement:
        """Both containment directions for one item (S-C.2)."""
        if self.na_policy is NAPolicy.EXACT_MATCH and is_na(response) and is_na(reference):
            return ItemJudgement(item.key, True, True, response, reference)

        # recall: does the model response contain the reference's content?
        recall_hit = self._contains(response, reference, item, cost)
        # precision: reversed roles -- does the reference contain the model's content?
        precision_hit = self._contains(reference, response, item, cost)
        return ItemJudgement(item.key, precision_hit, recall_hit, response, reference)

    # -- end to end --------------------------------------------------------------------

    def score(
        self,
        task: Task,
        sample_id: str,
        output_text: str,
        reference_checklist: dict[str, str],
    ) -> ScoredOutput:
        """Map ``output_text`` and score it against ``reference_checklist``."""
        cost = ScoreCost()
        mapped = self.map_checklist(task, output_text, cost)

        judgements = []
        for item in task.items:
            if item.key not in reference_checklist:
                raise KeyError(
                    f"{sample_id}: reference checklist has no key {item.key!r}; the rubric in "
                    "tasks.py has drifted from the dataset"
                )
            judgements.append(
                self.judge_item(
                    item,
                    mapped.get(item.key, NA),
                    str(reference_checklist[item.key]),
                    cost,
                )
            )

        return ScoredOutput(
            score=score_sample(sample_id, judgements, n_items=len(task.items)),
            mapped=mapped,
            cost=cost,
        )
