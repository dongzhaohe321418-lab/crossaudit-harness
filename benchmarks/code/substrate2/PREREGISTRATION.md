# Study 23 — does the ceiling move with the substrate?

Preregistered on `study/substrate2` **before any model call of this study**, at the commit that
adds this file. Binding: ceiling 1's preregistration §0–§1.5 and `RESULTS-CEILING.md` (the
estimand, the strata, the union-of-K curve, the flattening bar, the interval conventions),
study 2's generation protocol, study 21's rubric (§2 of `rerate/PREREGISTRATION.md`),
`EXPERIMENT_RECORD.md` §9–§10.

## 0. The question

Every number this programme has produced comes from one substrate: HumanEval+ and MBPP+, whose
median task is 41 words of prose and 6 lines of reference code. The ceiling measured there —
union recall 30.0% [20.0, 40.7] at eight readings of the shipped cross-vendor auditor, 48.2%
[36.7, 60.0] pooling twenty readings of three families — is the paper's central quantity, and a
reader is entitled to ask whether it is a property of auditing or of short functions.

This study repeats ceiling 1's measurement, unchanged, on a substrate whose median task is
**117 words of prose and 41 lines of reference code**.

## 1. The substrate, fixed before any generation

**BigCodeBench** (`bigcode/bigcodebench`, split `v0.1.4`, Apache-2.0; 1,140 tasks), reduced by
two mechanical filters applied in the frozen environment and recorded with the environment's
own module inventory:

| | filter |
|---|---|
| S1 | every module the task declares is importable in this project's interpreter |
| S2 | the task's canonical solution passes the task's own unittest suite here, within 60 s |

Measured before this file was written: **326 tasks pass S1 and 289 of those pass S2**. The 37
drops are recorded with their reason (15 need `faker`, 5 `pandas`, 4 `pytz`, 1 `numpy`, 1
`pyfakefs`, 2 time out, 5 fail their own suite). The frame is those **289 tasks**, frozen with
each task's sha256 before generation, and it is not revisited.

This excludes the tasks that need the scientific stack, so the frame is the stdlib half of
BigCodeBench and the results say so wherever they are quoted. What it is not is a selection on
any outcome: no auditor and no generator has seen this corpus.

**Visible and hidden suites.** BigCodeBench ships one unittest class per task; ceiling 1 needs
a suite the author is shown and a suite that decides. The split is mechanical and seeded: the
task's test methods sorted by name, **two** of them chosen by `random.Random(20260917)` as the
**visible** suite, and **all** of them as the **hidden** suite — hidden ⊇ visible, exactly the
relation EvalPlus's plus-suite has to its base suite. 287 of the 289 tasks have at least four
test methods (median five). A task with fewer than three is dropped and counted.

**Strata**, ceiling 1's definitions unchanged: a candidate that passes the visible suite and
fails the hidden one is **P**; passes both, **C**; fails the visible suite, **F**.

## 2. What is run

* **Generation.** `claude-haiku-4-5-20251001`, study 2's prompt shape (the specification and
  the visible tests, nothing else), two batches (`g1`, `g2`) over the 289 tasks, temperature and
  sampling at the harness defaults. Solutions are executed locally; the strata follow.
* **Audit.** The shipped cross-vendor auditor (`openai:gpt-5.6-terra`), holistic, the shipped
  constitution unmodified, **K = 8** independent draws — ceiling 1's `cross` family exactly. If
  budget remains after the eighth cross draw, the same-vendor family (`self`,
  `claude-haiku-4-5`) is run at K = 8 on the same instances, in that order.
* **Scope.** All P instances up to **200**; if more than 200 exist, 200 are drawn by
  `random.Random(20260917)` from the sorted ids, before any audit call. Plus a **C sample of
  150** drawn the same way. The audit set is frozen and committed before the first audit call.

## 3. Hypotheses

* **H23a (primary).** The shipped auditor's union recall at K = 8 on substrate 2's P differs
  from its union recall at K = 8 on substrate 1's P (33/110 = 30.0%). Two-sample problem-cluster
  percentile bootstrap of the difference (seed 20260917, 10,000 resamples), Wilson beside each
  rate. **Sign not fixed**: a harder substrate could go either way, and both directions are
  interesting.
* **H23b.** The saturation curve on substrate 2 at every K from 1 to 8, the constrained
  exponential fit, and ceiling 1's flattening bar (last-step gain ≤ 1.0 point). Where the bar is
  not met the fitted asymptote is an extrapolation and the raw union at K = 8 is quoted.
* **H23c.** Union false positives on the C sample at K = 8, and the recall bought per
  false-positive point, against substrate 1's 16.0% and 1.68.
* **H23d.** If the `self` family runs: the same-vendor minus cross-vendor difference at K = 8,
  against substrate 1's −12.7 points [−25.0, −0.9]. Paired: exact McNemar and the cluster
  sign-flip test.
* **H23e.** The residual — P instances no draw flagged — classified under **study 21's rubric
  verbatim** (§2 of that preregistration, the oracle question asked second), by the same two
  raters, blind to instance id, with κ. This is where substrate 2 can confirm or break study
  21's central finding: on a substrate whose specifications are three times longer, is the
  residual still dominated by failures the prose does not determine?

Primary: H23a. Everything else is secondary; no correction is applied to the secondaries, none
is claimed to clear a corrected threshold, and the full comparison inventory is listed in the
results.

## 4. What would falsify what

* If H23a's interval excludes zero and substrate 2's recall is **lower**, the ceiling is not a
  property of short functions; the paper's headline generalises in the direction that matters
  and says the measured ceiling is, if anything, optimistic.
* If it is **higher**, the paper must say that its central quantity is substrate-dependent and
  that 30.0% is not a general figure. That sentence is written into the results either way.
* If H23e finds the residual is **not** dominated by oracle-defined failures on substrate 2,
  study 21's finding is local to MBPP-style prose, and claim 4 of the paper's ledger is narrowed
  to that substrate in the same revision.

No outcome may change the frame, the split seed, the strata, the ladder, K, the hypotheses or
this section.

## 5. Budget, stopping, boundary

Generation ≈ 578 calls, ≈ $2. Audit ≤ 350 instances × 8 draws for `cross`, and the same for
`self` if it runs. Expected **$40**; cap **$60** on this study's cumulative spend, enforced from
the project ledgers across restarts. The ladder is fixed: `cross` draws 1–8 in order, then
`self` draws 1–8. The run stops at the cap and the completed draws are reported.

Boundary: `src/` and the kernel directories are untouched; ceiling 1's files are not modified.
BigCodeBench is Apache-2.0, so its text may be redistributed, but this study keeps the corpus
out of the repository anyway and commits ids, hashes, counts and outcomes only — the same rule
substrate 1 follows. Solutions and model replies live in the run archive.
