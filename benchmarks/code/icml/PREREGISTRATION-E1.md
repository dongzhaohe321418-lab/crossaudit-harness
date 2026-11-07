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
