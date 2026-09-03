"""Task definitions for ExpertLongBench.

Two things live here that are *not* in the dataset and had to be transcribed from the
paper's Appendix B:

1. the **description** of each rubric item -- the mapper prompt is built from these, and
   the dataset only carries item *names*;
2. the **task prompt** given to the model under test (Appendix B, "Model prompt" table).

Everything else (item names, ordering, the reference content) comes from the data.

Only T03MaterialSEG is transcribed in full so far, because that is the task the first
study runs. Adding a task means transcribing its Appendix B rubric verbatim -- do not
paraphrase, and do not let a model write these.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RubricItem:
    """One checklist item.

    ``key`` must match the corresponding key in ``human_reference_checklist`` exactly.
    """

    key: str
    name: str
    description: str
    group: str | None = None


@dataclass(frozen=True)
class Task:
    task_id: str
    domain: str
    #: Verbatim from the paper's per-task "Model prompt" table. Given to the model under test.
    model_prompt: str
    items: tuple[RubricItem, ...] = field(default_factory=tuple)
    #: Paper's reported F1 range on this task for frontier models, for orientation only.
    paper_reference_f1: str = ""

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.items)

    def item_definitions(self) -> str:
        """The item definition block used in the mapper prompt."""
        lines = []
        for index, item in enumerate(self.items, start=1):
            label = f"{item.group} / {item.name}" if item.group else item.name
            lines.append(f"{index}. {label}: {item.description}")
        return "\n".join(lines)


T03_MATERIAL_SEG = Task(
    task_id="T03MaterialSEG",
    domain="materials science",
    # Verbatim, paper Table 12 (S-B.3.4).
    model_prompt=(
        "You are a materials science researcher. Given a synthesis recipe that includes the "
        "target material, selected precursors, and synthesis steps, your task is to justify the "
        "key decisions made in the recipe. This includes explaining the rationale behind the "
        "choice of precursors, reaction conditions, and processing steps, using relevant "
        "principles such as structural compatibility, chemical reactivity, and desired phase "
        "formation. Output the explanation rationales as a list of bullet points, where each "
        "bullet point contains complete sentences."
    ),
    paper_reference_f1="15.2 (GPT-4o) to 19.5 (Gemini-2.0-Flash), Table 2 column T3",
    # Verbatim, paper S-B.3.5.
    items=(
        RubricItem(
            key="Selection of Precursors [level] Structural Considerations",
            name="Structural Considerations",
            group="Selection of Precursors",
            description=(
                "Justify precursor selection by explaining how the precursor's structural motifs "
                "(e.g., coordination environments, lattice arrangement) influence the target phase "
                "formation."
            ),
        ),
        RubricItem(
            key="Selection of Precursors [level] Handling Precursor Reactivity",
            name="Handling Precursor Reactivity",
            group="Selection of Precursors",
            description=(
                "Justify precursor selection by explaining the impact of precursor reactivity on "
                "phase evolution."
            ),
        ),
        RubricItem(
            key="Selection of Precursors [level] Physical and Chemical Properties of Precursors",
            name="Physical and Chemical Properties of Precursors",
            group="Selection of Precursors",
            description=(
                "Justify precursor selection by addressing how precursor properties (e.g., particle "
                "size, morphology) influences reaction kinetics and product morphology."
            ),
        ),
        RubricItem(
            key="Synthesis Conditions [level] Temperature and Heating Method",
            name="Temperature and Heating Method",
            group="Synthesis Conditions",
            description=(
                "Justify the choice of synthesis temperature and heating method (e.g., based on "
                "thermodynamic considerations, reaction kinetics, heat transfer efficiency, or side "
                "reactions)."
            ),
        ),
        RubricItem(
            key="Synthesis Conditions [level] Atmosphere",
            name="Atmosphere",
            group="Synthesis Conditions",
            description=(
                "Justify the choice of synthesis atmosphere environment (e.g., based on "
                "thermodynamic considerations, reaction kinetics, or side reactions)."
            ),
        ),
        RubricItem(
            key="Synthesis Conditions [level] Duration",
            name="Duration",
            group="Synthesis Conditions",
            description=(
                "Justify the choice of synthesis duration (e.g., based on reaction kinetics, phase "
                "transformation rates, or side reactions)."
            ),
        ),
    ),
)


TASKS: dict[str, Task] = {T03_MATERIAL_SEG.task_id: T03_MATERIAL_SEG}


def get_task(task_id: str) -> Task:
    if task_id not in TASKS:
        raise KeyError(
            f"{task_id} has no transcribed rubric yet. Available: {sorted(TASKS)}. "
            "Add it by transcribing its Appendix B 'Evaluation Rubric' and 'Model prompt' "
            "tables verbatim into tasks.py."
        )
    return TASKS[task_id]
