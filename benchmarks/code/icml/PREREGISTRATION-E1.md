# Preregistration — study E1/E2: specification information and operating characteristics

Committed before the first audit call of this study. Generation, execution, item selection and clause
construction may run before this commit; none of them calls an auditor or reads an audit outcome.
Departures after this commit are numbered amendments appended below, each committed before the data it
governs.

## Question

The paper's general-code results suggest that most defects no reading flags are ones the specification does
not determine (a post hoc association, C-residual). E1 tests it by intervention: holding the program fixed,
does stating the requirement the specification leaves open make auditors diagnose the defect, beyond what an
equally long irrelevant sentence does and beyond what more readings do? E2 uses the same readings to describe
operating characteristics across auditors and generators.

## Population

* Problems: all 542 HumanEval+ and MBPP+ problems (corpus pinned in `manifest_corpus.json`), minus those
  whose oracle fails validation: the reference must pass the visible and hidden suites, and two wrong
  implementations (returning `None`; raising) must fail the hidden suite. Five fail (HumanEval/32, MBPP/590,
  /737, /787, /794) and are excluded.
* Generators: `claude-haiku-4-5` (Claude Code CLI; the original study's generator) and `gpt-5.6-terra`
  (Codex CLI, reasoning effort low); three samples per problem each, with the original study's generation
  prompt.
* Item: a (problem, generator) pair with at least one *defective* sample (passes the visible suite, fails the
  hidden suite, and the reference runs on the first failing hidden input) and at least one *correct* sample
  (passes both). The first of each by sample index is used.
* Split: all 542 problems are assigned once to dev (25%) or test (75%) by a fixed seed (20261109), written to
  `split.json` before selection and never redrawn. Selection requires every generation to be complete and
  writes a frozen `items.json`. Dev items are used only to check the pipeline; every hypothesis is tested on
  test items alone. "Correct" samples are called *test-passing* controls: they pass both suites, which does
  not prove them correct.

## Construction (before any audit)

For each item, `gpt-6-astra` (high reasoning) is shown the task, visible tests, reference, defective
candidate and the first failing hidden input with both outputs, and writes a CLAUSE (a behavioural
requirement the task leaves unstated, at most 40 words, naming no specific value), 3-8 CASES (argument lists
that exercise the clause; the failing input may not be reused) and a PLACEBO (a sentence of similar length
that changes no required output). Expected outputs of the cases come from executing the reference, never from
the model. **Execution admission**: the reference runs on every case; the test-passing control agrees with the
reference on every case (benchmark float tolerance); the defective candidate disagrees on at least one; the
placebo is 0.6-1.5 times the clause's length; neither sentence contains a literal of the failing input or
outputs (two or more characters, whole tokens). **Adjudication** by a second vendor (`claude-opus-5-5`, Claude
Code CLI, tools disabled), shown the task, visible tests, clause, cases with reference outputs and placebo,
but neither candidate: admitted only if the clause matches the cases (q1 true) and is not already determined
by the task (q2), does not contradict it (q3), does not reveal a test value or prescribe a technique (q4), the
placebo changes no correct output (q5) and is unrelated to the clause's behaviour (q6). Up to three
construction attempts and two adjudication attempts. The admission funnel is reported by benchmark and
generator; E1's population is defects for which a missing behavioural requirement could be written and
validated in this way, not all defects.

## Arms and readings

Program bytes are identical across arms. Task text: **orig** = the specification; **clause** = specification +
"Additional requirement: <clause>"; **placebo** = specification + "Additional requirement: <placebo>".
Prompts are built by the product's prompt builder with the shipped rulebook plus one fixed paragraph asking
for a `WITNESS: <call> -> <expected>` line on behavioural BLOCKERs (identical in every arm).
Auditors (primary): `gpt-5.6-terra` (Codex CLI, reasoning effort medium) and `claude-sonnet-5-5` (Claude
Code CLI), the same prompt bytes on stdin. Isolation: Codex runs with a CODEX_HOME holding only the login,
user config, rules and session persistence disabled, an empty working directory and `--json` event capture;
a reading in which the model invoked any tool is discarded as a failed attempt. Claude runs with every tool
disabled and no session persistence. Neither CLI exposes a temperature, so auditor contrasts are
configuration contrasts. Readings per item and kind: orig 4, clause 2, placebo 2. All readings of a split
follow one persisted random schedule (seed 7) across arms, auditors and items.

## Endpoints

* **Flag**: at least one BLOCKER (the paper's existing rule).
* **Verified diagnosis** (defective items): at least one BLOCKER witness whose call parses as
  `entry(<literal args>)`, on which the reference runs without exception, the candidate's output differs from
  the reference's (benchmark float tolerance) or the candidate raises, and the auditor's stated expected value
  (a Python literal) equals the reference's output. Arguments are materialised once and the same pickled
  objects are passed to both programs.
* **Witnessed disagreement** (secondary): as above without the expected-value condition.
* A witness on which the reference raises is *outside the domain* and never counts.
* Readings: a reading is valid if the reply parses and passes the product's reply validator; each reading key
  gets at most two attempts; a key with no valid reading after two attempts is missing.
* Unit: for each item, auditor, kind and arm, the union over that arm's valid readings. For the original arm
  with two readings, the union is averaged exactly over the six two-reading subsets of its four readings
  (subsets containing a missing reading are dropped from the average).

## Hypotheses (test split)

Estimand weighting: each item's value is the mean over the two primary auditors; the pooled estimate is the
mean over items; intervals are problem-cluster percentile bootstraps (10,000 draws, seed 20261110) that
resample problems with all their items, generators and auditors. Let C2, P2 be the two-reading unions of the
clause and placebo arms, O2 the subset-averaged two-reading union and O4 the four-reading union of the
original arm.

* **H1 (primary).** Verified diagnosis on defective items: C2 - P2 > 0. Supported if the interval's lower
  bound exceeds 0; the paper calls the effect substantive only if the point estimate is at least 5 points.
* **H2.** Flags on test-passing controls: C2 - P2 < +10 points (the permitted false-alarm increase, fixed
  here); supported if the interval's upper bound is below +10.
* **H3.** Verified diagnosis: C2 - O4 > 0 (the clause with two readings beats the original task with four).
  Supported if the lower bound exceeds 0. Construction cost is not counted, so H3 is not an equal-cost claim.
* **H4 (manipulation control, equivalence).** Verified diagnosis: P2 - O2 lies within +-5 points: supported
  only if the whole interval lies inside [-5, +5].
* Secondary, reported without correction: each hypothesis per auditor and per generator; the same contrasts
  for flags and for witnessed disagreement.

## E2 — operating characteristics (descriptive, secondary)

On the orig arm (4 readings): union flag and verified-diagnosis rates on defective items against union flag
rates on correct items at K = 1–4, per auditor and generator, exact subset averaging; and the same under the
any-finding rule. The paper reports whether the auditor ordering changes across operating points; no test is
claimed.

## Stopping and exclusions

Every admitted test item is audited in every arm. A reading that fails twice (transport or unreadable reply)
is recorded as failed and excluded from that arm's union; items with a missing arm for an auditor are dropped
from that auditor's paired analyses, and the counts are reported. No item is dropped for its outcome.

## What would weaken the paper's account

H1 not supported, or supported only together with a correct-item flag increase beyond the H2 margin, would
mean that stating the requirement does not move what auditors can establish, and the specification account
would stay a post hoc description.

## Amendment 1 (before any audit call; after generation, execution and selection with three samples)

Selection with three samples per problem gave 38 items: only 136 (generator, problem) pairs had a defective
sample, and 98 of them had no test-passing sample. Two changes, made before construction or any audit:
(a) six samples per problem and generator (samples 3-5 added with the same prompt and routes);
(b) the test-passing control is the same generator's first passing sample, else the other generator's first
passing sample, else the reference solution; `control_source` records which. H1, H3 and H4 do not use controls.
H2 is reported on all items and, as a sensitivity analysis, on items whose control is generated
(control_source in {same, other}). Seen before this amendment: the selection funnel counts only; no
construction, adjudication or audit output existed.

## Amendment 2 (after the development split was audited under protocol e1-v2; before any test audit)

**What was seen.** All development-split audits and witness results under e1-v2 (36 items; 1,152 readings),
the registered analysis on that split, and a cross-vendor methods review of the pipeline (GPT,
`records/icml/v2/review_gpt_A3.md`). No test-split audit call has been made. Development outcomes: the clause
arm reached verified diagnosis on every development item for both auditors; the placebo-original contrast was
+4.2 points [+0.5, +10.3]. The e1-v2 records are archived unchanged with checksums in `records/icml/v2/` and
will be reported as a pilot; none of them enters a test analysis.

**Why.** The review found that (i) some admitted clauses contradicted the task's words or codified reference
quirks, with inconsistent adjudication across generators; (ii) the placebo controls length but not diagnostic
relevance, so a clause that names the failing input class confounds behavioural information with attention;
(iii) the hidden-suite instrumentation replaced task-specific tolerances and the witness comparator differed
from the benchmark's (tolerance, set comparison for some problems, string-to-float coercion, timeouts counted
as disagreement, unfixed hash seed); (iv) construction cases lost tuple types through JSON and could admit a
control that violates the clause; (v) the analysis dropped arms with any missing reading, contrary to the
registered missing-data rule; (vi) unfinished or stale witness scoring could silently become negatives;
(vii) several registered secondary outputs were absent.

**Changes (protocol e1-v3; all stages from oracle validation onwards are rerun on both splits).**

1. *Ground truth.* Hidden suites run with their own assertion call, including task-specific tolerance.
   Construction cases, first failing inputs and witnesses are compared with the suite's own `assertion`
   function and tolerance, in one executor process per call with PYTHONHASHSEED fixed and the arguments
   unpickled afresh for each program. A candidate timeout on a witness is recorded as `candidate_timeout` and
   does not count as disagreement; a reference timeout is an infrastructure failure and is retried.
2. *Construction.* The constructor no longer sees the defective candidate or its output; it sees the task,
   visible tests, reference, the first failing input and the reference's output on it, and must skip items
   where the task's words already determine the behaviour, or where the reference's behaviour contradicts
   them or looks like an arbitrary quirk. Cases are Python literal tuples (types preserved), must fall inside
   the per-position type signatures of the hidden suite's inputs, must show at least two distinct reference
   outputs, and the test-passing control must agree with the reference on every case. The constructor also
   writes a **pointer**: a length-matched sentence that names the same kind of input as the clause without
   stating or implying the correct output.
3. *Adjudication.* Two adjudicators from different vendors (claude-opus-5-5 and gpt-6.1-sol, high effort),
   each blind to the candidates and to every audit, answer nine questions (correspondence; determined by the
   task's words, where agreement with visible tests is explicitly insufficient; contradiction; leakage or
   technique; plausible author intent; placebo neutrality and unrelatedness; pointer relevance; pointer
   non-resolution). An item is admitted only if both admit.
4. *Arms.* orig (4 readings), clause (2), placebo (2), pointer (2).
5. *Missing data* as registered: an arm's union is over its valid readings; O2 averages the two-reading
   subsets whose readings are both valid; an item's pooled value is the mean over the auditors whose contrast
   exists, and the item is dropped only if none exists. Omissions are reported by arm, auditor and contrast.
6. *Completeness and provenance.* The analysis refuses to run while any scheduled reading is unfinished or any
   valid reading's witnesses lack a current score; witness scores are bound to a hash of the scorer version,
   the solution, the reference and the witnesses; infrastructure failures are retried, never scored negative.
   Raw Codex event streams are stored with each reading. A checksummed bundle of the frozen test inputs
   (items, constructions, adjudications, schedule, code commit) is committed before the first test audit.
7. *Secondary outputs* now include every hypothesis per auditor and per generator, and flag and
   witnessed-disagreement versions of every defective-item contrast. E2's verified-diagnosis curve uses
   BLOCKER witnesses under both counting rules; the any-finding rule changes only the flag curves.
8. *Bootstrap convention* (unchanged code, now named): with sorted draws indexed from 0, the interval is
   [draw floor(0.025 B), draw ceil(0.975 B) - 1].

**New hypothesis.** *H5.* Verified diagnosis on defective items: C2 - R2 > 0, where R2 is the two-reading
union of the pointer arm: stating the behaviour helps beyond directing attention to the input class.
Supported if the interval's lower bound exceeds 0. Descriptive, without a test: R2 - P2 for verified
diagnosis on defective items and for flags on test-passing controls.

**Unchanged.** H1-H4, their thresholds and margins, the estimand weighting, the bootstrap, the split, the
auditors and the sample. H2 remains a flag rate on test-passing controls, not a false-positive rate on
known-correct programs. The paper will describe the intervention as failure-informed specification
supplementation. The development split is rerun under e1-v3 as a pipeline check only.

## Amendment 3 (after e1-v3 construction and adjudication; before any test audit)

**What was seen.** The e1-v3 construction and adjudication funnel on both splits, with no audit output on
either split: of 150 selected items, the candidate-blind constructor skipped 79 (its stated reasons: the
task's words already determine the behaviour, or the reference's behaviour contradicts the task or is an
implementation artefact), 7 failed the execution gates, 64 passed them, and 38 were admitted by both
adjudicators (9 development, 29 test). Development-split e1-v3 audits were started as a pipeline check.

**Why.** The skip rate means the clause intervention can only address a minority of hidden-test failures, and
that the hidden-test definition of "defective" mixes three different situations. Measuring the auditors on
all three is a direct test of the paper's account of what limits recall, and it uses items that are already
frozen.

**Changes.** (1) *Taxonomy.* Both adjudicator routes, blind to every audit and shown only the task, the
visible tests, the first failing input and the two outputs (not the program text), classify every selected
item as DETERMINED (the task's words require the reference's output and the program's output violates them),
OPEN (both outputs are consistent with the task's words) or AT_ODDS (the reference's output contradicts the
task's words or is an implementation artefact). An item's class is the class both give; otherwise DISPUTED.
Agreement and Cohen's kappa are reported. (2) *Original-arm audits for every selected item.* Items not
admitted to the intervention receive the original arm only (4 readings per kind and auditor, same prompt,
auditors and validity rules) on a separate persisted schedule (seed 7); admitted items contribute their
original-arm readings from the main schedule.

**New hypothesis (test split, all selected items).** *H6.* Four-reading verified diagnosis on defective items
is higher for DETERMINED items than for OPEN items: the difference of class means, with a problem-cluster
bootstrap (10,000 draws, seed 20261110; draws in which either class is empty are discarded and counted).
Supported if the lower bound exceeds 0. Secondary, without correction: the same for flags, DETERMINED minus
AT_ODDS, per auditor, and every class's levels of flag, verified diagnosis and witnessed disagreement on
defective items and flags on test-passing controls. DISPUTED items are reported but enter no contrast.

**Unchanged.** H1-H5 and everything in Amendment 2. Sample size for H1-H5 is the 29 admitted test items; no
items will be added to the intervention after test audits begin.

## Amendment 4 (after GPT review A4 of the e1-v3 development pipeline; before any test audit)

**What was seen.** The development results (unchanged since Amendment 3) and the review `review_gpt_A4.md`, which
read every admitted construction and every taxonomy record and found: admitted items whose clause codifies a
reference quirk or restates what the task already decides (B1); placebos and pointers that change which outputs
are permitted (B2); taxonomy labels that confuse domain violations with open behaviour, are not exhaustive, differ
on identical evidence, and describe only the first failing input while diagnosis credits any witness (B3); judge
failure modes (B4); a completeness check that trusts whatever schedule files exist (B5); an incomplete H6 matrix
(B6); and percentile intervals that collapse to [0, 0] when every contrast is zero (B7). No test audit exists.

**Changes.**
1. *Judge (B4), judge-v3.2.* The executor returns its result through a file, not a stdout marker; the suite's
   comparator runs under the time limit; a comparator that rejects the reference compared with itself makes the
   call unscorable (infrastructure), not a disagreement; exception kinds are kept. Witness cache keys bind the
   scorer source, the suite comparator and tolerance, both programs and the witness text. Development witnesses
   were rescored; development results are unchanged.
2. *Completeness (B5).* The required reading universe is rebuilt from the frozen items and admissions (test:
   1,160 intervention + 1,248 original-only = 2,408 readings); schedule files holding keys outside it, and audit
   rows outside it, abort the analysis.
3. *Semantic reconciliation (B1), revised before any rating was collected.* The author decided not to rate, and no
   second human rater is available, so no human ratings enter the study. An admitted item stays in the intervention
   only if taxonomy v4 (change 5) classifies it OPEN, that is, both adjudicators, blind to item identity, to which
   result is the reference (order randomised) and to all audit outcomes, judge the input valid and both
   first-failure results acceptable under the task text and visible tests. As behavioural evidence, reported for
   every selected item and not used for retention: of the twelve E1 generations of the item's problem that pass the
   visible tests (two vendors, six samples each, written from the task alone), how many return the reference's
   result and how many the defective program's result on the first failing input. H1-H5 rest on the retained test
   items; thresholds are unchanged. The funnel and every exclusion are reported, and the absence of human
   validation is stated as a limitation.
4. *Control texts (B2).* Every admitted placebo and pointer is rechecked by both adjudicators against the two
   first-failure outputs with two questions (does the sentence rule out either output; does it reveal which output
   is required). A placebo or pointer failing either is regenerated by the constructor and rechecked, before any
   test audit. H5 is reported as "benefit beyond the specified pointer control", not as a general separation of
   information from attention.
5. *Taxonomy v4 (B3).* Both adjudicators reclassify every selected item with domain validity decided first,
   comparator semantics and exception status stated, the two results in an evidence-determined random order, and
   five exhaustive classes (OUT_OF_DOMAIN, DETERMINED, OPEN, AT_ODDS, NEITHER). Votes on byte-identical evidence are
   pooled, so identical evidence cannot receive different classes. H6 uses the v4 labels and is reported as a
   programme-level observational association with first-failure labels; a secondary analysis restricts credit to
   witnesses on the classified input class where that can be decided by execution.
6. *Analysis (B6, B7).* The full H6 secondary matrix ({verified diagnosis, flag} x {DETERMINED-OPEN,
   DETERMINED-AT_ODDS} x {pooled, each auditor}) with effective counts; every selected item must carry both
   classifications. Beside every percentile interval, a registered sensitivity: when every problem-level contrast is
   zero, the exact one-sided 95% upper bound over problems is reported. Verdict rules are unchanged.
7. *Pre-test bundle.* Items, constructions, adjudications, control rechecks, taxonomy v4, the behavioural counts, the
   required universe and the code commit are frozen with SHA-256 checksums before the first test
   audit.
