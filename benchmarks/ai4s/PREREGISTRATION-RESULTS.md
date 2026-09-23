# A4S-2 — validating scientific results

Registered 2026-09-23 **before the items are built and before any model call of this study**.
Programme: `plan/AI4S-PROGRAM.md`. Depends on A4S-1's correct stratum (programs that pass the
scientists' tests); nothing from A4S-1's audit readings is used.

## Question

Given the code, its run log and a report of the results, can an auditor tell whether the reported
results follow? Three auditors answer on the same items: the LLM auditor reading the artefacts;
CrossAudit's deterministic `science` profile as shipped (schema, units, convergence, provenance,
number→source); and re-execution of the cited code on the cited inputs.

## Items

From A4S-1's correct instances whose step output on a chosen test case is a real scalar or a real
array of at most 10 elements (the case drawn by seed **20260927**), one **results increment** each:

* `work/solution.py` — the candidate program (steps 1..k);
* `work/inputs.py` — the test case's input assignments, verbatim from the benchmark;
* `outputs/run.log` — the program's output on those inputs, one value per line, written by
  executing it;
* `results/results.json` — `quantities` with `name`, `value`, `unit` and `source` citing the
  run-log line (`outputs/run.log#Ln`), and `metadata.yml` declaring `code_version` and `inputs`;
* `report.md` — one paragraph stating the result, with a `crossaudit-numbers` block whose rows
  quote `results/results.json`.

Units: SciCode does not state output units, so every quantity carries the unit token registered in
the gate below (dimensionless where the step does not state one); the same token appears in clean
and faulty items.

**Clean items** state the true output everywhere. **Faulty items**, one fault each, drawn by seed:

| code | fault | where |
|---|---|---|
| R1 | scale slip ×10³ | report and results.json; run.log true |
| R2 | sign flip | report and results.json; run.log true |
| R3 | value from a different test case of the same step | report and results.json; run.log true |
| R4 | relative error of 5% (beyond `np.allclose` defaults) | report and results.json; run.log true |
| R5 | transcription mismatch: report differs from results.json by a transposed pair of digits | report only |
| F1 | **fabricated run**: R1's scale slip in run.log, results.json and report alike | all three |
| F4 | **fabricated run**: R4's 5% error in all three | all three |

R-faults are reporting faults: the artefacts disagree with each other or with the log the code
wrote. F-faults are fabrications: the artefacts agree with one another and not with the code.
Design: each instance yields one clean item and one faulty item, fault type assigned in rotation
by seed, so clean and faulty are paired on the instance.

## Gate before any model call

Every clean item must pass the shipped `science` profile with no BLOCKER, and must re-execute to
its reported value. If any clean item fails either, the construction is repaired and the gate rerun
before any model call; the number of repairs is reported.

## Auditors and outcomes

* **LLM, `cross`** (`openai:gpt-5.6-terra`) through `run_audit` with the project's checks set to
  `science`; task: "Deliver the result of running work/solution.py on work/inputs.py, reported in
  report.md with its provenance." **K = 4.** Flag = at least one model BLOCKER.
* **Deterministic `science` profile**: the same `run_audit` call's DCL verdict (no model involved).
* **Re-execution**: run `work/solution.py` on `work/inputs.py` and compare to the reported value with
  `np.allclose` defaults.

Outcomes: recall by fault type and overall, false positives on clean items, for each auditor and for
the unions LLM+DCL and LLM+re-execution; the paired clean/faulty design gives McNemar-type
comparisons within instance. Intervals: problem-cluster percentile bootstrap, 10,000, seed 20260927.

## Expectations stated now

DCL: R1–R5 caught (the log or results disagree with what is cited), F1 and F4 missed (everything
agrees). Re-execution: all value faults caught. The LLM: unknown, and the study exists to measure it,
in particular on F1 and F4, where only reasoning about the code could catch the fabrication without
running it. No directional hypothesis about the LLM is registered.

## Budget and review

Model halt **$30**, cumulative, from the ledger, failing closed. Cross-vendor review before the paper.

## Amendment 1 — construction details the registration left open (2026-09-24)

Written before any item is built and before any model call of this study, after a mock item (two
made-up numbers, no benchmark content) was run through the shipped `science` profile to find a
layout its checks accept. Known when written: A4S-1's strata (81 defective, 150 correct); nothing
from any A4S-1 audit reading is used or has been analysed.

* **The unit token is `dimensionless`.** The registration says every quantity carries "the unit
  token registered in the gate" and the gate names none. SciCode states no output units, so every
  quantity, clean or faulty, carries `dimensionless`.
* **Every file sits under `work/`** (`work/solution.py`, `work/inputs.py`, `work/outputs/run.log`,
  `work/results/results.json`, `work/results/metadata.yml`, `work/report.md`), inside the audited
  scope; A4S-3 Amendment 2 is the reason.
* **Formats.** Values are written with 8 significant digits (`format(x, ".8g")`), a relative
  rounding well inside `np.allclose` defaults. `run.log` holds one element per line as
  `<value> dimensionless`. Each element of the output is one quantity named `output[i]`, whose
  `source` is `work/outputs/run.log@<rev>#L<i+1>` and which carries a `text` field
  `"<value> dimensionless"`. A JSON line never holds a number followed by its unit, so without
  that field no report row could quote `results.json` in a form the shipped check can verify.
  `metadata.yml` declares `code_version: <rev>` and the three inputs `path@<rev>`. The report is
  one paragraph stating the values, and its `crossaudit-numbers` rows each quote a `text` field.
* **Population.** A4S-1's correct stratum as sampled (the 150 instances in `strata.json`). For
  each, one test case is drawn at seed 20260927. The instance qualifies if the call can be read
  from that case's assertion (the argument compared with `target`) and the output on the case's
  inputs is a finite real scalar or a finite real array of at most 10 elements with at least one
  nonzero element. Booleans and complex values do not qualify. An all-zero output would make R1,
  R2 and R4 no-ops. Instances that do not qualify are dropped, and their count is reported.
* **Faults.** The seven fault types are shuffled once at seed 20260927 and assigned in that
  cycle over the qualifying instances in sorted order. R1, R2 and R4 apply to every element
  (×1000, sign, ×1.05). R3 takes the output of another test case of the same step that has the
  same shape and is not `np.allclose` to the true one, drawn by seed. R5 transposes the first
  pair of adjacent distinct digits in the first element that has one, in the report's prose and
  its row `v` only; the row's quote is copied from `results.json`, as a transcription slip would
  leave it. F1 and F4 apply R1's and R4's change to `run.log`, `results.json` and the report
  alike. If the assigned fault cannot be constructed (R3 with no eligible other case; R5 with no
  eligible digit pair), the instance takes the next fault in the cycle, and the substitutions
  are reported.
* **Re-execution** compares the report's stated values (the rows' `v`) with the program's output
  on `work/inputs.py`, under `np.allclose` defaults.

## Amendment 2 — the task names Amendment 1's paths (2026-09-24)

Before any model call. Amendment 1 moved every file under `work/`, and the registered task still
names `report.md`. The task now reads "Deliver the result of running work/solution.py on
work/inputs.py, reported in work/report.md with its provenance." Nothing else changes. The item
gate passed on the first build with no repair: 74 of the 150 correct instances qualify, every
clean item passes the shipped `science` profile with no BLOCKER, and every clean item
re-executes to its reported value. Known when written: the gate result and the deterministic
profile's verdict on every item, which the builder records by design. No model reading exists.

## Amendment 3 — the items did not say how the result was produced (2026-09-24)

A two-item pilot (one clean, one faulty item of the same instance; one `cross` reading each,
$0.04) found an instrument defect. `work/solution.py` only defines functions and `work/inputs.py`
only assigns inputs (using `np` without importing it), and no file runs the step's call. Both
readings blocked on exactly that, correctly: the report claims a run that nothing in the
increment performs. Every clean item would carry the same legitimate defect.

Fix: each item gains `work/run.py`, which imports the candidate program, executes
`work/inputs.py` verbatim in that namespace, evaluates the registered call, and writes
`work/outputs/run.log` in the registered format. `metadata.yml` declares it as a fourth input,
and the report names it and the call. The builder now runs `run.py` inside every clean item and
requires the log it writes to equal the item's `run.log` byte for byte, so the clean log is the
program's own output and not a transcription. Items, seeds, faults and everything else are
unchanged. The two pilot readings are discarded, archived as `runs/results_audit_pilot/`, and
counted toward the $30 halt. The gate is rerun before any further model call.

## Erratum to Amendment 2 (2026-09-24, after the first review)

Amendment 2 says it was written before any model call and that no model reading existed. The runner
already carried the corrected task text when the two pilot readings of Amendment 3 were made
(00:08:44 and 00:08:55, UTC+8), but Amendments 2 and 3 were committed together afterwards (`bc48540`,
00:09:20). Both pilot readings' task hashes match Amendment 2's text. The amendment's content governed
every reading; its commit did not precede the pilot. Separately, two clean runners of problem 80
import an unused plotting module that needs a writable Matplotlib cache; in a read-only environment
their logs reproduce only with that import removed.
