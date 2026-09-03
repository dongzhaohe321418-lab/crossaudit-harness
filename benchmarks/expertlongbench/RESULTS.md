# T03MaterialSEG, n = 12 — the audit loop did not demonstrably improve accuracy

**On 12 paired instances of ExpertLongBench T03MaterialSEG (materials science), CrossAudit's
full loop scored 18.1 CLEAR F1 against the single model's 15.4 — a difference of +2.7 that
is not statistically distinguishable from zero (two-sided Wilcoxon signed-rank, p = 0.67 on
7 usable pairs), and that the run's own internals say is not the audit's doing.** On 11 of
the 12 instances the auditor passed at round one having raised **no finding of any
severity**, so the loop returned an unmodified first draft and the arms differ only by
generation variance. On the single instance where the audit did intervene, the revision it
forced scored **worse** — 40.0 → 22.2, −17.8 F1.

This does not show that the dual-source audit fails to improve accuracy. It shows that at
this sample size, on this task, with a default configuration, **the audit almost never
fires, and this study therefore has almost no audit to measure.** That is the finding.

Total cost of the run: **$1.76**.

---

## What was run

| | |
|---|---|
| task | `T03MaterialSEG` — justify the key decisions in a solid-state synthesis recipe |
| n | **12** of the task's 50 samples, seeded (`--seed 20260904`), sampled after sorting by id |
| corpus | sha256 `0b525eae93aab406…`, verified against `manifest.json` at run start |
| generator (both arms) | `anthropic:claude-sonnet-4-6` |
| auditor (arm B) | `openai:gpt-5.6-terra` |
| CLEAR mapper / judge / adjudicator | `openai:gpt-5.6-terra` |
| settings | `max_rounds: 3`, `checks: general`, `authority.lone_model_blocker: block`, N/A policy literal |
| code | frozen at commit `e037d96` before the study; nothing changed after scores were seen |

Arm A is one generator call with the paper's own T03 prompt (Table 12, transcribed verbatim)
and the sample's input. Arm B is `crossaudit.cli.build.run_loop` in a fresh git project with
a real `crossaudit.yml`, the general constitution, the recipe committed inside the audited
scope so a content audit has source material, and the same generator vendor, model and
effort as arm A.

## The accuracy question

| | arm A (single model) | arm B (CrossAudit) |
|---|---:|---:|
| **mean F1** | **15.4** | **18.1** |
| mean precision | 15.3 | 20.8 |
| mean recall | 26.4 | 20.8 |
| mean accuracy | 13.9 | 16.7 |
| std error of F1 | 5.3 | 5.5 |
| instances scored | 12/12 | 12/12 |
| mean rounds | 1.00 | 1.08 |
| generation cost / instance | $0.0199 | $0.0477 |
| wall time / instance | 28.5 s | 46.1 s |

Mean paired difference (B − A) = **+2.69 F1**. Arm B won 4, arm A won 3, 5 were exact ties.
Two-sided Wilcoxon signed-rank, exact by enumeration: W+ = 17, W− = 11, statistic = 11,
**p = 0.6719** on the 7 non-tied pairs. Not significant, and on a sample this size that is
as consistent with a real effect too small to detect as with no effect at all.

A useful sanity check on the scorer: the paper's Table 2 reports frontier models at
**15.2–19.5 F1 on T3**. Our arm A lands at 15.4 and arm B at 18.1 — inside that band. The
reimplementation is at least in the right regime, though see "Deviations" before treating
any absolute number as comparable.

### Per-instance, with what the audit actually did

| instance | rounds | arm A | arm B | B − A | findings raised |
|---|---:|---:|---:|---:|---|
| `10.1002/adfm.201000591` | 1 | 0.0 | 16.7 | +16.7 | none |
| `10.1002/adma.202208974` | 1 | 0.0 | 0.0 | 0.0 | none |
| `10.1002/adma.202416342` | 1 | 0.0 | 22.2 | +22.2 | none |
| `10.1002/aesr.202200017` | 1 | 16.7 | 16.7 | 0.0 | none |
| `10.1002/ange.202300209` | 1 | 22.2 | 16.7 | −5.6 | none |
| `10.1002/anie.201812472` | 1 | 50.0 | 66.7 | +16.7 | none |
| `10.1002/batt.202200056` | 1 | 22.2 | 0.0 | −22.2 | none |
| **`10.1002/celc.202200984`** | **2** | **40.0** | **22.2** | **−17.8** | **1 BLOCKER** |
| `10.1002/cnma.202200403` | 1 | 0.0 | 0.0 | 0.0 | none |
| `10.1002/cssc.201000245` | 1 | 0.0 | 22.2 | +22.2 | none |
| `10.1002/smtd.202400640` | 1 | 33.3 | 33.3 | 0.0 | none |
| `10.1002/zaac.201800357` | 1 | 0.0 | 0.0 | 0.0 | none |

### The decomposition that matters

Split the same 12 pairs by whether the loop actually revised anything:

| subset | n | mean B − A |
|---|---:|---:|
| audit passed at round 1, output unchanged | 11 | **+4.55** |
| audit raised a blocker and forced a revision | 1 | **−17.78** |

**The +2.7 headline is the +4.55 on the eleven instances the audit never touched**, diluted
by the one it did. On those eleven, arm B is a single generator call that happened to be
framed differently from arm A's — it saw CrossAudit's system prompt and file contract rather
than the bare task prompt — and was then waved through. Whatever produced the +4.55 is
generation variance and framing, not auditing. Reporting it as an audit effect would be
false, and the difference is not significant in any case (signed-rank on that subset alone:
p = 0.44, 6 usable pairs).

The audit's actual contribution to this study is a single data point, and it is negative.

## The confirmation-rate question (D142)

**The auditor raised exactly one BLOCKER across all 12 instances.** D142 deferred
`authority.lone_model_blocker`'s default until a confirmation rate existed. A rate computed
from one finding is not that number, and this run does not settle D142.

For completeness, the one finding, on `10.1002/celc.202200984`, round 1, rule
`CA-CONTENT-001`, tier `model`:

> The Annealing Step is internally inconsistent: it states that annealing at 700 °C is
> "above the decomposition points" of Li₂CO₃, but parenthetically identifies Li₂CO₃
> decomposition onset as approximately 720 °C. A 700 °C anneal cannot be above a 720 °C
> onset.

That is a real, sharp, checkable defect, caught by a model from a different vendor than the
one that wrote it. Adjudicated against the rubric, it maps to *Synthesis Conditions →
Temperature and Heating Method*, and CLEAR had independently scored that item wrong in that
same round-1 output. So:

- **confirmation rate: 100% (1/1), 95% CI [20.7%, 100.0%]**
- **false-positive rate: 0% (0/1), 95% CI [0.0%, 79.3%]**
- findings about no rubric item: 0

**These rates rest on one finding and are worthless as a policy input.** The interval spans
four fifths of the range. `authority.lone_model_blocker` should stay where it is until a run
with two orders of magnitude more findings exists.

The uncomfortable detail worth more than the rate: **the audit caught a genuine error and
the corrected version scored lower.** 40.0 → 22.2. Either the revision lost correct content
elsewhere while fixing the contradiction, or CLEAR's checklist-containment metric is
insensitive to the kind of correctness this finding was about. Both are plausible and this
run cannot distinguish them. It is a direct warning against assuming "the audit caught
something real" and "the score improves" are the same claim.

## What it cost

| | arm A | arm B |
|---|---:|---:|
| generation per instance | $0.0199 | $0.0477 |
| wall time per instance | 28.5 s | 46.1 s |
| CLEAR scoring per instance | $0.0395 | $0.0399 |

Arm B costs **2.4×** arm A per instance to generate, and roughly 1.6× the wall time. On this
run that bought +2.7 F1 that the data cannot distinguish from zero.

Whole-study spend, from CrossAudit's own usage ledger: **$1.76**, of which $0.99 (325 calls)
was CLEAR scoring, $0.24 arm A generation, $0.001 adjudication, and the remainder arm B
generation and auditing across the per-instance scratch projects. **Scoring costs more than
generating**: CLEAR needs 1 mapper call plus 2 judge calls per rubric item, so 13 calls per
scored output on a 6-item rubric, and arm B additionally re-scores every round that carried
a blocker.

### What a larger run would cost

Per instance, both arms plus scoring: **~$0.147**. So, at this task's rubric size:

| n | approx. cost | wall time (serial) |
|---:|---:|---:|
| 12 (this run) | $1.76 | ~40 min |
| 50 (all of T03) | ~$7.35 | ~2.8 h |
| 100 (e.g. T07ChemMDG) | ~$15 | ~5.5 h |

To reproduce exactly this run:

```sh
export PYTHONPATH="$(git rev-parse --show-toplevel)/src"
python benchmarks/expertlongbench/fetch.py
python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 12 --seed 20260904
python benchmarks/expertlongbench/report.py benchmarks/expertlongbench/runs/<run-id>
```

Note that it will not reproduce byte-identically: the provider layer exposes no seed, and
temperature is decided by the model's capability card, not by us (see Deviations 7).

## What this run does and does not license

**It does not license** the claim that the dual-source audit improves output accuracy. The
measured difference is not significant, and its sign on the only instance where the audit
acted was negative.

**It does not license** the opposite claim either. Eleven of twelve instances contain no
audit to evaluate, so the study has an effective sample size of one for the question it was
built to answer.

**It does license** one concrete observation about the product: on an expert prose task
under a default general configuration, **the auditor passed 11 of 12 first drafts with no
finding at all**. Whether that is correct behaviour (the drafts were fine) or under-firing
(the rubric-level errors CLEAR detected — arm A averaged 15.4 F1, so most rubric items were
wrong — went unremarked) is the question worth answering next, and it is answerable: CLEAR
already knows which items were wrong in each output, so a follow-up can ask how many of
those the auditor mentioned. That measurement is not in this slice.

**Do not re-run this study hoping for a different number.** If the configuration changes,
the study restarts and says so here.

---

## Deviations from CLEAR

Every place this reimplementation departs from arXiv:2506.01241v1, or approximates something
the paper does not fully specify. The authors released no evaluation code (checked
2026-09-04; the HF Space is a Streamlit leaderboard containing no scorer), so none of these
could be resolved by reading theirs.

1. **Mapper model.** The paper uses **Qwen2.5-72B**, chosen for open weights and validated at
   90.1% average mapping F1 across T1/T6/T7/T8 (§4.2). We use `gpt-5.6-terra`. The paper's
   own validation argues the mapper is interchangeable among strong models, but we did
   **not** re-validate mapping quality for ours. Untested transfer.
2. **Judge model.** The paper uses **GPT-4o**, justified by near-perfect Cohen's κ against
   Gemini-2.0-Flash (§4.2). We use `gpt-5.6-terra`. Same argument, same untested transfer.
3. **The judge shares a vendor with the auditor.** Only two vendors had credentials on this
   machine, so OpenAI supplied both the arm-B auditor and the CLEAR judge. The judge is *not*
   the generator's vendor, so no model graded its own output — but a judge from the auditor's
   family scoring the audited arm is a bias risk pointing **in arm B's favour**, and arm B
   still failed to show a significant gain. A third vendor for the judge is the first thing
   to fix in a repeat.
4. **Few-shot examples.** Table 44 ends with `{Few-shot examples placeholder}`; the paper
   prints two exemplars and states more exist without showing them. We use exactly the two
   printed. This is unrecoverable from the paper and is the single largest source of
   divergence in absolute scores.
5. **Mapper prompt.** The paper prints only per-task extraction prompts (Table 10 for T03),
   and that one is for extracting from *source papers* during dataset construction, not for
   mapping a *model response*. §3.2/§4.1 describe the response-mapping prompt without
   printing it. Ours is a generalised role-playing extraction prompt following that
   description: comprehensive per-item extraction, `"N/A"` when absent, JSON keyed by item.
   The paper's "we design instructions for each checklist item" is approximated by one prompt
   carrying all six item definitions.
6. **`"N/A"` handling.** §4.1 gives the performance-assessment judge no `"N/A"` carve-out
   (the one in §C.1 belongs to a different prompt, for validating the mapper). We take the
   literal reading — all *n* items judged, `"N/A"` passed through as text — argued at length
   in `NOTES.md` §4, including that only this reading reproduces the paper's reported T3
   magnitude. `--na-policy exact-match` implements the alternative for sensitivity analysis.
   **Both arms are scored by the identical scorer, so the paired difference is robust to this
   choice even though the absolute values are not.**
7. **No temperature or seed control.** CrossAudit's provider layer decides temperature from
   the model's capability card and exposes no seed parameter, so we can record determinism
   inputs (model ids, prompt sha256s, sample ids, corpus digest) but cannot enforce
   determinism. Re-running will not reproduce byte-identical outputs.
8. **`max_tokens` is not plumbed** through `resilience.complete`; adapters use their default
   of 4096. Judge calls that need 1 token are allowed 4096.
9. **Rubric item descriptions transcribed by hand** from §B.3.5 into `tasks.py`, because the
   dataset carries item *names* only. A transcription error would be invisible to the tests;
   only the item *keys* are checked against the pinned manifest.
10. **A fidelity gain, for once:** for T03 the dataset's `human_reference_checklist` *is* the
    annotation product (§3.2 names T3 as an exception), so no GPT-4o reference-mapping step
    sits between the human reference and our scoring, as it does for most other tasks.
11. **Sample size.** 12 of 50, seeded. The paper scores all samples.
12. **The arms differ in more than "audit on/off".** Arm B's generator sees CrossAudit's own
    system prompt and file-output contract and is told where to read the recipe and where to
    write the deliverable; arm A sees the bare task prompt. This is inherent to measuring the
    product rather than a simulation of it, but it is a confound, and it is the most likely
    explanation of the +4.55 on the eleven instances the audit never touched.
13. **Blocker adjudication is our own method**, not part of CLEAR. Its mapping step is a
    model call and is fallible; its lookup step is not. Findings that map to no rubric item
    are excluded from both rates.
14. **Absolute scores are not comparable to the paper's leaderboard.** Different mapper,
    different judge, reconstructed prompts, no reference implementation to diff against. The
    only claim made here is the paired, within-scorer comparison of two arms.
