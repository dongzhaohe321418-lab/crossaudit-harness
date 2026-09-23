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
