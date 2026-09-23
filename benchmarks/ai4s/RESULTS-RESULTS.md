# A4S-2 — validating scientific results: results

Registration: `PREREGISTRATION-RESULTS.md` with Amendments 1–3. Registered analysis:
`analyze_results.py` (committed before any item had its four readings) →
`records/ai4s/results_results.json`. Post hoc analyses, labelled so wherever used:
`posthoc_results.py` → `records/ai4s/results_posthoc.json`. Items: `records/ai4s/results_items.json`
and `~/Documents/Crossaudit/ai4s/runs/results_items/`. Re-execution: `reexec_results.py` →
`records/ai4s/results_reexec.json`. Readings: `~/Documents/Crossaudit/ai4s/runs/results_audit/`
(`cross.d1-4.jsonl`; all 592 planned readings exist and are `ok`). Spend: $7.70 cumulative including
the discarded two-reading pilot of Amendment 3, against the $30 halt. The halt shares the runner
code whose fail-closed limits are recorded in A4S-3's erratum; no cap was reached.

## What was measured

Each of the 74 correct SciCode instances (36 problems) whose output on one seeded test case is a real
scalar or a real array of at most ten elements became a results increment: the program, the test's
inputs, a script that runs one on the other and writes a run log, a `results.json` citing each value's
log line, metadata, and a one-paragraph report with `crossaudit-numbers` annotations. Each yields a
clean item and a faulty item carrying one fault, assigned in rotation by seed: five reporting faults
(R1–R5), where the artefacts disagree with each other or with the log the code wrote, and two
fabrications (F1, F4), where a ×10³ scale slip or a 5% error is written consistently into the log,
the results and the report. Three auditors read the same items:

* **LLM** (`cross`, `gpt-5.6-terra`) through `run_audit` with the project's checks set to the shipped
  `science` profile, four readings; flag = at least one model BLOCKER. **The model's prompt contains
  the deterministic tier's findings, as in the product**, so on the reporting faults it has seen the
  profile's BLOCKERs before it writes its own.
* **The `science` profile** (schema, units, convergence, provenance, number→source), from the same
  call; flag = a hard failure. Its verdict was identical in all four readings of every item and
  matched the builder's.
* **Re-execution**: run the program on the inputs; flag = the report's stated values are not
  `np.allclose` (defaults) to the output.

## Table 1 — flags by fault type (registered outcomes)

Each cell: flagged/n [Clopper–Pearson 95%, supplementary; it ignores clustering by problem]. The
registered problem-cluster bootstrap for the overall rows follows the table.

| fault | LLM, K=4 | science profile | re-execution | LLM ∪ re-execution |
|---|---|---|---|---|
| R1 scale slip ×10³ | 11/11 [71.5, 100.0] | 11/11 [71.5, 100.0] | 10/11 [58.7, 99.8] | 11/11 [71.5, 100.0] |
| R2 sign flip | 10/10 [69.2, 100.0] | 10/10 [69.2, 100.0] | 10/10 [69.2, 100.0] | 10/10 [69.2, 100.0] |
| R3 value from another case | 9/9 [66.4, 100.0] | 9/9 [66.4, 100.0] | 9/9 [66.4, 100.0] | 9/9 [66.4, 100.0] |
| R4 5% error | 11/11 [71.5, 100.0] | 11/11 [71.5, 100.0] | 10/11 [58.7, 99.8] | 11/11 [71.5, 100.0] |
| R5 transposed digits (report only) | 8/8 [63.1, 100.0] | 8/8 [63.1, 100.0] | 8/8 [63.1, 100.0] | 8/8 [63.1, 100.0] |
| F1 fabricated ×10³ | 14/14 [76.8, 100.0] | 0/14 [0.0, 23.2] | 14/14 [76.8, 100.0] | 14/14 [76.8, 100.0] |
| F4 fabricated 5% | 9/11 [48.2, 97.7] | 0/11 [0.0, 28.5] | 9/11 [48.2, 97.7] | 11/11 [71.5, 100.0] |
| **all faulty (74)** | 72/74 [90.6, 99.7] | 49/74 [54.3, 76.8] | 70/74 [86.7, 98.5] | 74/74 [95.1, 100.0] |
| **clean (74)** | 12/74 [8.7, 26.6] | 0/74 [0.0, 4.9] | 0/74 [0.0, 4.9] | 12/74 [8.7, 26.6] |

Registered problem-cluster bootstrap (36 problems, 10,000, seed 20260927), overall rows: LLM K = 4
recall 97.3% [93.0, 100.0], clean 16.2% [7.8, 26.1]; profile 66.2% [54.7, 76.8], clean 0.0%;
re-execution 94.6% [89.6, 98.7], clean 0.0%; LLM ∪ re-execution 100.0% [100.0, 100.0] (a
degenerate interval: every resample is 100%). LLM ∪ profile equals the LLM alone on every row. The
LLM's K ladder, recall and clean flags: K = 1 93.2% at 10.1%, K = 2 95.0% at 12.8%, K = 3 96.3% at
14.5%, K = 4 97.3% at 16.2%. At K = 1 its mean rate on F4 is 65.9% and on F1 94.6%.

**Paired comparisons (registered, both forms).** Between auditors on the 74 faulty items, exact
McNemar: LLM against the profile, 23 items flagged only by the LLM and 0 only by the profile
(p = 2.4 × 10⁻⁷, i.e. 2⁻²²); LLM against re-execution, 4 and 2 (p = 0.69). Within instance, faulty
flagged and clean not, against the reverse: LLM 61 against 1; profile 49 against 0; re-execution 70
against 0.

## What each auditor does

**The deterministic profile does exactly what it was built to do.** It blocks every reporting fault
(49/49: the log, the results and the report no longer agree, and number→source says where) and no
fabrication (0/25: everything agrees with everything else), with no flag on any clean item. That
matches the registration's stated expectation.

**The LLM catches fabrications by working out the result.** It flags 14 of 14 fabricated scale slips
and 9 of 11 fabricated 5% errors, where the profile flags none. Its findings recompute the output
from the program and the inputs, for example evaluating a KL divergence of two small distributions
to 1 where the report says 1000, or checking that a reported solver output fails the first row of the
linear system it solves. Its two misses are 5% errors on outputs of order 10⁻⁶. On the reporting
faults it flags 49 of 49, but it has the profile's findings in its prompt, so those flags are not an
independent measurement of the model.

**Re-execution catches what re-execution can.** It flags every fault except four whose output is so
close to zero that `np.allclose`'s default absolute tolerance (10⁻⁸) absorbs the change: an R1 and an
R4 on outputs of −3.2 × 10⁻¹⁶ and 2.2 × 10⁻¹⁶ (floating-point zeros, where the "fault" changes
numerical noise), and two F4 on outputs of 3.6 × 10⁻⁹ and −1.6 × 10⁻⁷. The registration's premise
that a 5% error lies beyond `np.allclose` defaults is false for such outputs. The LLM flagged all
four; the union of the LLM with re-execution flags all 74 faulty items.

## Flags on clean items, read one by one (post hoc)

The LLM flagged 12 of 74 clean items. All were read; labels are in `posthoc_results.py`.

* **8 are correct, and expose two defects in our construction.** In 9 instances the benchmark's test
  case passes its inputs as literals inside the call (e.g. `Fermi(2 * 10 ** 17, …)`), so
  `work/inputs.py` is empty, `work/run.py` hard-codes the arguments, and the report's sentence that the
  program ran "on the inputs in work/inputs.py" is false. Seven of the 9 clean items were flagged for
  exactly that. Separately, two solutions document their output's unit (nanometres, zeptojoules)
  while every report says `dimensionless`, the unit token Amendment 1 fixed for all quantities; both
  were flagged for the contradiction (one of them is also among the seven). The gate did not test
  either property.
* **4 are wrong**: three hand computations of the output that disagree with the executed output
  (one by a factor of 10¹²), and one claim of a syntax error in a line whose trailing text is a
  comment. On one of these instances (`25.1.s2`) the same model computed the output correctly when
  reading the faulty item and incorrectly when reading the clean one.

So, of the LLM's 16.2% clean flag rate, 5.4% (4/74) is error and the rest is a correct reading of
defects we built in.

## Sensitivity (post hoc)

| population | LLM recall | LLM clean flags | re-execution recall | re-execution clean |
|---|---|---|---|---|
| registered (74 instances) | 72/74 | 12/74 | 70/74 | 0/74 |
| without the 9 empty-input instances | 63/65 | 5/65 | 61/65 | 0/65 |
| without the 4 tolerance cases | 68/70 | 12/70 | 70/70 | 0/70 |

The 5 remaining clean flags without the empty-input instances are the 4 wrong ones and one correct
unit contradiction.

## Reading

1. **Deterministic provenance checks and an LLM auditor catch different things, and the difference is
   the one that matters for results.** A number→source chain verifies that artefacts agree; it cannot
   see a result that is consistently wrong. The LLM, reading the code and the inputs, caught 23 of 25
   such fabrications at K = 4. Neither is a substitute for the other: the profile has no false
   positives and needs no model; the LLM needs the code and inputs to be small enough to reason about,
   and it errs (4 wrong flags on 74 clean items, and inconsistent arithmetic across readings).
2. **Re-execution is the reference, and it has a blind spot the registration did not anticipate.**
   With default tolerances it cannot see faults in outputs near zero. Here the LLM covered those four.
3. **Much of what looked like false positives were true.** The LLM flagged a provenance sentence we
   wrote carelessly and a unit label we fixed by convention. A deterministic check could have caught
   neither without being written for it.

## What this does not license

A claim about validating scientific results in general: one benchmark, one test case per instance,
outputs of at most ten numbers, small programs, a single model at its default sampling. The LLM's
reporting-fault rate is not an independent measurement (it saw the profile's findings). The
fabrications are two synthetic types; a fabrication that also fits a plausible re-derivation (a wrong
but self-consistent method) was not tested.

## Deviations and instrument history

* Amendment 1 (before items): unit token, layout under `work/`, formats, population rule and fault
  construction, fixed after a mock item (no benchmark content) was run through the profile.
* Amendment 2 (before any model call): the task names Amendment 1's paths.
* Amendment 3: a two-reading pilot found that no file performed the run the report described; items
  gained `run.py`, a third gate condition (each clean item's `run.py` reproduces its log byte for
  byte), and the pilot readings were discarded. All 74 clean items passed all three gate conditions.
* Found after the readings, in the clean-flag reading above: the empty `inputs.py` in 9 instances and
  the unit label; and, in re-execution, the tolerance cases. None was repaired; all are reported as
  sensitivity above.
* The analysis script rounds exact p values to four places; the full values are in the post hoc
  record.
