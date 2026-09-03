# ExpertLongBench / CLEAR — grounding notes

Source of every claim below: **Ruan et al., *ExpertLongBench: Benchmarking Language Models on
Expert-Level Long-Form Generation Tasks with Structured Checklists*, arXiv:2506.01241v1**, read as
HTML at <https://arxiv.org/html/2506.01241v1> on 2026-09-04, plus the dataset card and files at
<https://huggingface.co/datasets/launch/ExpertLongBench> (repo sha `bd9e6d4ab066a29f5b55c150b92b6296c14ea930`,
lastModified 2025-07-30).

Section numbers in **bold** are the paper's own. This file exists so that the scorer in `clear.py`
can be checked line-by-line against the method, rather than against a recollection of it.

---

## 1. What the benchmark is

**§3.1.** 11 expert-level tasks over 9 domains, 1,050 samples total, average input 36,204 tokens and
average human reference 851 tokens. Each sample has three elements:

- **Task Input** — the context of the task.
- **Human Reference** — human-authored, natural language. (**§B intro**: exceptions are
  T3MaterialSEG and T9MedicalDR, where the checklist-based reference *is* the annotation product and
  no unstructured reference exists.)
- **Checklist-mapped Reference** — the human reference decomposed against the task's expert-designed
  rubric, one entry per rubric item.

**§3.2 "Sample Selection"**: tasks with >100 candidates were cut to 100 samples chosen for diversity
and difficulty.

Seven of the eleven tasks are public (T01, T03, T04, T06, T07, T08, T11). Confirmed against the HF
file listing: exactly those seven `.jsonl` files exist. T02, T05, T09, T10 "remain private"
(**§I.6**).

### Record schema (verified by download, not assumed)

Every row of every public `.jsonl` is an object with exactly:

| field | type | notes |
|---|---|---|
| `id` | str | e.g. `T03MaterialSEG-10.1002/smtd.202400640` |
| `input` | str | the task input |
| `raw_human_reference` | str \| dict \| null | `null` for T03 (see above); a `dict` for T11 |
| `human_reference_checklist` | dict[str, str] | **the checklist-mapped reference**; keys are rubric item names, values are the extracted content or the literal string `"N/A"` |

Observed shapes (downloaded 2026-09-04):

| task | rows | checklist items | mean input chars | `"N/A"` reference cells |
|---|---:|---:|---:|---|
| T01LegalMDS | 100 | 26 | 427,558 | 703 / 2600 (27%) |
| T03MaterialSEG | 50 | 6 | 627 | 189 / 300 (63%) |
| T04EduPAE | 100 | 7 | 1,347 | 177 / 700 (25%) |
| T06HealthCNG | 100 | 29 | 5,692 | 1473 / 2900 (51%) |
| T07ChemMDG | 100 | 6 | 146 | 282 / 600 (47%) |
| T08BioPDG | 100 | 5 | 207 | 92 / 500 (18%) |
| T11CyberRDG | 100 | 6 | 5 | 0 / 600 (0%) |

The high `"N/A"` density is the single most consequential fact for reimplementing the metric; see §4
below.

---

## 2. The rubric format

**§3.2 "Expert-guided Rubric Design".** Per task, a checklist-based fine-grained rubric, built either
by *expert-guided design* (co-designed with domain experts) or *protocol-refinement design*
(refining an existing expert protocol). The paper stresses these are **human-written** and that
"existing LLMs cannot yet replicate" them (**§3.2**, pointing at **§I**) — i.e. the rubric is data,
not something to be generated at eval time.

The rubric is a flat, ordered list of named items, each with a one-or-two-sentence *description* of
what the item is meant to capture. Notation from **§3.2**: the checklist for a task is
`C = {c_1, ..., c_n}` where `n` is the number of items for that task.

The item **names** are recoverable from the dataset (they are the keys of
`human_reference_checklist`). The item **descriptions** are *not* in the dataset — they live only in
the per-task "Evaluation Rubric" subsections of **Appendix B**. Since the mapper prompt is built
from the item definitions, the descriptions must be transcribed from the paper. This repo does that
for T03 in `tasks/T03MaterialSEG.py` (verbatim from **§B.3.5**).

### T03MaterialSEG rubric, verbatim from §B.3.5 (n = 6)

Grouped under two headings, which is why the dataset keys carry a `[level]` separator:

*Selection of Precursors*
1. **Structural Considerations** — "Justify precursor selection by explaining how the precursor's
   structural motifs (e.g., coordination environments, lattice arrangement) influence the target
   phase formation."
2. **Handling Precursor Reactivity** — "Justify precursor selection by explaining the impact of
   precursor reactivity on phase evolution."
3. **Physical and Chemical Properties of Precursors** — "Justify precursor selection by addressing
   how precursor properties (e.g., particle size, morphology) influences reaction kinetics and
   product morphology."

*Synthesis Conditions*
4. **Temperature and Heating Method** — "Justify the choice of synthesis temperature and heating
   method (e.g., based on thermodynamic considerations, reaction kinetics, heat transfer efficiency,
   or side reactions)."
5. **Atmosphere** — "Justify the choice of synthesis atmosphere environment (e.g., based on
   thermodynamic considerations, reaction kinetics, or side reactions)."
6. **Duration** — "Justify the choice of synthesis duration (e.g., based on reaction kinetics, phase
   transformation rates, or side reactions)."

**§B.3.5** also records the provenance: five papers with well-written explanations were summarised by
GPT-4o / Claude-3.7-Sonnet / Gemini-2.0-Flash, and a materials-science PhD student reviewed, revised
and extended the result into the final six items.

### The task's own generation prompt, verbatim from Table 12 (§B.3.4)

> You are a materials science researcher. Given a synthesis recipe that includes the target material,
> selected precursors, and synthesis steps, your task is to justify the key decisions made in the
> recipe. This includes explaining the rationale behind the choice of precursors, reaction
> conditions, and processing steps, using relevant principles such as structural compatibility,
> chemical reactivity, and desired phase formation. Output the explanation rationales as a list of
> bullet points, where each bullet point contains complete sentences.

This is the prompt given to the *model under test*. Both of our arms use it unchanged, so that the
thing being measured is the audit loop and not prompt engineering.

---

## 3. The CLEAR pipeline (§4)

**§4** in one sentence: *given a model output, map its information onto the task's checklist, then
score that mapped output item-wise against the checklist-mapped human reference.*

Two model-driven stages, in this order.

### Stage 1 — checklist mapping / extraction (§4.1 "Generating Checklist-Mapped Model Responses")

"We follow the same procedure described in §3.2 to extract checklists from model responses."

The §3.2 procedure ("Checklist-mapped Reference Creation") is:

- a **role-playing** prompt ("As a material science research staff, your task is to examine the given
  paper using the provided checklist…", Table 10),
- instructing the model to extract, **for each checklist item, all relevant information as
  comprehensively as possible**,
- and **"if no such information is present, the model is instructed to return 'N/A'"**,
- with per-item instructions designed from the item definitions,
- emitting **JSON** keyed by checklist item.

Model used: for building the *reference* checklists, **GPT-4o** (§3.2). For mapping *model outputs*
at evaluation time, the paper deliberately switches to an open-weight model, **Qwen2.5-72B**,
"considering its availability of model weights and decent extraction performance" and cost (§4.1).

So the mapper is *not* required to be a frontier model, and the paper's own choice is an
open-weight one. That matters: it means the mapper is a commodity component, and swapping it is a
change the paper itself sanctions in principle (see §5 for the agreement evidence).

### Stage 2 — item-wise comparison (§4.1 "Assessing Response Quality using Checklists")

LLM-as-a-judge, **GPT-4o**, adapting reference-based scoring. For each checklist item `i`, with the
mapped model content `a_i` and the mapped reference content `r_i`, the judge assigns a **binary**
score answering a **semantic containment** question. The paper is explicit that containment is
directional and that both directions are run:

> **§C.2**: "It is used to evaluate whether each element from the checklist-mapped response
> semantically includes the corresponding element of the checklist-mapped reference. **By reversing
> the roles of the model response and reference**, we can also check if the reference contains the
> response. These bidirectional containment checks are jointly used to determine the correctness of
> each checklist item."

### The judge prompt, verbatim from Table 44 (§C.2)

> You are judging whether a model has generated an answer consistent with the ground truth. An
> model's answer will be longer and can be considered correct if it contains the semantic content of
> short reference answer somewhere within it. Don't worry about factuality with respect to the real
> world, just judge the example based on what you see. No need to overthink this task, it really
> comes down to just soft matching. Answer with only the word 'Yes' or 'No'.
>
> Model Answer: Dates of All Decrees: May 8, 2015; June 8, 2015; June 30, 2015; October 7, 2015;
> October 15, 2015; October 20, 2015; April 12, 2017; May 10, 2017; June 26, 2017; June 27, 2017;
> July 26, 2017; September 21, 2017; October 3, 2017; April 1, 2018; 2018; April 1, 2019
>
> Reference Answer: Dates of All Decrees: October 15, 2014; May 8, 2015; June 8, 2015; June 30, 2015;
> October 7, 2015; October 15, 2015; October 20, 2015; July 11, 2016; April 12, 2017; May 10, 2017;
> June 26, 2017; June 27, 2017; July 26, 2017; September 21, 2017; October 3, 2017; April 1, 2018;
> April 1, 2019
>
> Correct: No
>
> Model Answer: Remedy Sought: Injunction to stop smoking and prohibit the sale of tobacco products
> in prisons
>
> Reference Answer: Remedy Sought: injunction to stop the smoking at Crossroads and other
> correctional centers, as well as prohibiting the sale of tobacco products in prisons
>
> Correct: Yes
>
> {Few-shot examples placeholder}

Notes on this prompt that the implementation must respect:

- The slots are literally named **`Model Answer:`** and **`Reference Answer:`**, and the output is
  literally the word `Yes` or `No`. Table 44's caption: "The label 'Yes' corresponds to a binary
  score of [1] and 'No' corresponds to [0]."
- The prompt's *semantics* are "does the thing in the `Model Answer` slot contain the thing in the
  `Reference Answer` slot". The caption says this configuration is "for recall measurement".
  Therefore:
  - **recall direction**: `Model Answer := a_i` (mapped model), `Reference Answer := r_i` (mapped
    reference).
  - **precision direction**: swap them — `Model Answer := r_i`, `Reference Answer := a_i`.
- Both worked examples are prefixed with the item name ("Dates of All Decrees: …", "Remedy Sought:
  …"), i.e. the item name is prepended to each side's content.
- `{Few-shot examples placeholder}` — the paper shows two exemplars and states more exist but does
  not print them. **This is unrecoverable from the paper**; see "Deviations" in RESULTS.md.

---

## 4. How the numbers are computed (§4.1, final paragraph)

Verbatim:

> After performing item-level assessment for a checklist-mapped model response, we define its
> **checklist precision** (**checklist recall**) as the fraction of checklist items whose model
> response (reference) is semantically contained within the reference (model response) and
> **accuracy** as the fraction of checklist items whose model response and reference mutually contain
> each other. The **sample-level checklist F1 score is the harmonic mean of the checklist precision
> and checklist recall**, and we obtain the **task-level performance by averaging the sample-level
> metrics**.

Unpacked, for one sample with checklist `C = {c_1..c_n}`, letting

- `P_i = 1` iff the judge says the reference contains the model's content for item `i`,
- `R_i = 1` iff the judge says the model's content contains the reference for item `i`:

```
precision = (1/n) * sum_i P_i
recall    = (1/n) * sum_i R_i
accuracy  = (1/n) * sum_i (P_i AND R_i)
F1        = 2 * precision * recall / (precision + recall)      # 0 when both are 0
task score = mean over samples of the sample-level F1
```

Four things to be precise about, because they are where a reimplementation silently diverges:

1. **The denominator is `n`, the full checklist length** — not the number of non-empty items, and not
   the number of items the model happened to address. "the fraction of checklist items" is
   unqualified. This is what makes the scores low.
2. **F1 is computed per sample and then averaged.** It is *not* the F1 of the pooled item counts.
   Macro over samples, and the harmonic mean is taken *before* averaging. Getting this backwards
   changes the number.
3. **Precision and recall are separate judge calls.** They are not derivable from one another. Cost
   is therefore `2 * n` judge calls per output, plus 1 mapper call.
4. **`"N/A"` is not given a carve-out in §4.** The only place the paper special-cases `"N/A"` is
   **§C.1**, the prompt that audits *mapping quality* ("If the extracted information for a specific
   item shows 'N/A', the label for both faithfulness and coverage should be yes"). §C.1 is a
   different prompt for a different purpose (validating the mapper, §4.2), and its rule does not
   transfer to §C.2. The literal reading of §4.1 is that all `n` items go to the judge, with `"N/A"`
   passed through as its literal string.

   Sanity check that the literal reading is the right one: T03 has 63% `"N/A"` reference cells. If
   `"N/A"` items were excluded from the denominator, a competent model answering the ~2.2 real items
   would score far above the **15.2–19.5 F1 that Table 2 reports for frontier models on T3**. Under
   the literal reading, a model that dutifully writes all six explanations fails precision on the
   ~3.8 `"N/A"` items (its content is not contained in "N/A") and fails recall on them too, landing
   in exactly the observed range. The literal reading reproduces the paper's magnitude; the
   exclusion reading does not. We implement the literal reading as the default and expose the other
   as a flag — see `NAPolicy` in `clear.py` and "Deviations from CLEAR" in RESULTS.md.

### Reported headline numbers (Table 2, F1 scaled 0–100)

Top of the leaderboard by average across all 11 tasks: Gemini-2.0-Flash **26.8**, GPT-4o **26.5**,
GPT-4o-mini **26.1**, Llama-3.3-70B-Instruct **24.6**. On **T3 specifically**: Gemini-2.0-Flash
19.5, Mistral-Large-Instruct 17.9, Llama-3.3-70B 16.8, GPT-4o 15.2, GPT-4o-mini 15.2. Per-task
standard errors are in **§D.2**; alternative metrics (accuracy, precision, recall, coverage) in
**§D.1**, Tables 45–48.

The "best model around 33 F1" figure quoted in some summaries is a *per-task* number (e.g. T7/T11
column maxima), not the best average. The best **average** in Table 2 is 26.8. Our RESULTS.md
compares against the T3 column, not the average.

---

## 5. What the paper says about extractor / judge agreement with experts (§4.2)

This is the evidence that the automated pipeline is trustworthy, and it is worth stating exactly
because it bounds how much of our own result is measurement noise.

**Reference-checklist quality.** "We, first, validate the quality of these reference checklists
through human and automated evaluations on tasks T1 and T6, confirming **over 90% faithfulness and
coverage**." (§4.2, echoed in §3.2: "the mapped references achieve over 90% faithfulness and
coverage"). T1 and T6 were chosen "due to their challenging long contexts and extended output
requirements". For other tasks, "human inspection was employed to ensure the mapping quality"
(§3.2). The measuring instrument is the §C.1 prompt (Table 43), which scores each extracted item on
*faithfulness* (fully supported by the source, or directly inferable) and *coverage* (main elements
captured).

**Mapper selection.** Open-weight candidates Llama-3.3-70B-Instruct, Mistral-Large-Instruct and
Qwen2.5-72B were scored against GPT-4o-extracted reference checklists on T1, T6, T7 and T8 ("spans
diverse domains and configurations of input / output length"). **Qwen2.5-72B achieved the highest
average performance with an average F1-score of 90.1%**, and was adopted as the mapper. Detail in
**Appendix E**.

**Judge selection.** Agreement between **GPT-4o** and **Gemini-2.0-Flash** annotations on the same
data, reported as **Cohen's Kappa**, described as "**near-perfect level of inter-annotator
agreement**" for T1, T6, T7 and T8. (The v1 HTML renders the four kappa values as empty math nodes —
the numbers themselves did not survive the HTML conversion; only the "near-perfect" characterisation
and the four task labels are legible.) On this basis the paper uses GPT-4o alone as judge, noting it
"saves cost", against the general advice (their citation [27]) to use multiple judge families to
mitigate bias.

**Consequence for us.** The paper's own validation says the mapper is interchangeable among strong
models at ~90% F1, and that two different judge vendors agree near-perfectly. That is what licenses
us to run the mapper and judge on a vendor of our choosing rather than on Qwen2.5-72B + GPT-4o
exactly — but it is an argument by transfer, and it is listed as a deviation.

---

## 6. Is the authors' evaluation code public?

**No — checked 2026-09-04.** The paper links no code repository. The two artefacts that exist are:

- the dataset: <https://huggingface.co/datasets/launch/ExpertLongBench> — 7 `.jsonl` files, a README,
  `.gitattributes`. No code.
- the leaderboard: <https://huggingface.co/spaces/launch/ExpertLongBench> — file listing is
  `Dockerfile`, `README.md`, `requirements.txt`, `src/streamlit_app.py`, `src/models.json`,
  `src/model_acc.json`, and three images. That is a results-display app; it contains no scorer.

So `clear.py` is a **from-the-paper reimplementation with no reference implementation to diff
against**. Every judgement call it makes is recorded in §4 above and in "Deviations from CLEAR" in
RESULTS.md. This is the main threat to the validity of any absolute number we publish, and the
reason our headline claim is a *paired within-scorer* comparison (arm A vs arm B under an identical
scorer) rather than a claim about where CrossAudit sits on the ExpertLongBench leaderboard.

---

## 7. Licence obligations

Three statements exist and they do not perfectly agree; we comply with the union (i.e. the strictest).

1. **§I.6 "New Assets"**: "The data for tasks T1LegalMDS, T3MaterialSEG, T4EduPAE, T6HealthCNG,
   T7ChemMDG, T8BioPDG, and T11CyberRDG are shared under the **CC BY-NC-SA 4.0** license
   (<https://creativecommons.org/licenses/by-nc-sa/4.0/>)". These are exactly the seven public tasks.
2. **The HF dataset card** declares `license: cc-by-nc-4.0` — NonCommercial, but *without* the
   ShareAlike term.
3. **§I.5 licence table** records the *upstream* licences of the source corpora, which are various
   and in some cases more permissive than the benchmark's own terms: CC BY-NC 4.0 (T1LegalMDS);
   Apache-2.0 (T4EduPAE / Tutorbot-Spock); **CC BY 4.0** (T3MaterialSEG's Science and Wiley papers,
   T6HealthCNG / ACI-Bench, T7ChemMDG / Text2Mol); MIT (T8BioPDG / SciKnowEval, T11CyberRDG /
   AgentHarm); CC BY-NC-SA 4.0 (T11CyberRDG / R-Judge).

**We treat the corpus as CC BY-NC-SA 4.0.** Operationally that means:

- **Attribution** — the citation must accompany any use or reporting. Recorded in
  `THIRD_PARTY_NOTICES.md` and in the benchmark README.
- **NonCommercial** — this benchmark directory is a research/measurement artefact. It must not be
  wired into a paid product surface, shipped in a distribution, or used to advertise. It is
  deliberately a top-level `benchmarks/` directory outside `src/crossaudit/`, is not referenced by
  the package, and is excluded from the wheel.
- **ShareAlike** — applies to *adaptations of the data*. We therefore do not create or publish
  adaptations: the fetch script writes into a **gitignored** `data/` directory, and nothing derived
  from dataset text is committed. Concretely the following are all forbidden in git:
  dataset rows, `input` text, `human_reference_checklist` values, model outputs (which quote the
  input), mapped checklists, and judge transcripts. Only aggregate statistics — counts, means, F1
  values, sha256 digests — are committed. `.gitignore` and the manifest design enforce this.
- **No redistribution** — we ship a *fetcher*, not the corpus. A user must obtain the data from
  Hugging Face themselves and thereby accept the licence directly.

Citation to reproduce wherever the benchmark is mentioned:

> Jie Ruan, Inderjeet Jayakumar Nair, Shuyang Cao, Amy Liu, Sheza Munir, Micah Pollens-Dempsey, et
> al. *ExpertLongBench: Benchmarking Language Models on Expert-Level Long-Form Generation Tasks with
> Structured Checklists.* arXiv:2506.01241, 2025.
