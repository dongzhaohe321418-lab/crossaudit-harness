# P4 — What a flag on test-passing code points at

Registered 2026-09-23, **before any model call of this study**. Amendments are numbered and
committed before the step they govern.

## Why

The paper prices every recall figure by its false-positive rate: the shipped cross-vendor route
flags **24 of 150** (16.0%) correct increments at eight readings. "Correct" means *passes the
hidden suite*. The paper's own third result is that hidden suites often ask what the prose never
settled — so a suite can also fail to ask what the prose *did* settle, and a flag on
test-passing code may point at real behaviour the suite never exercised. A pre-submission
referee (R1-M9) observed that nothing in the paper adjudicates a single one of those flags. This
study does, as far as it can be done without a model judging correctness.

Ceiling 1 kept only a hash of each finding's text, so its 24 flags cannot be re-read. The
correct stratum is therefore **re-audited, with the texts kept**.

## Population and readings

* **Instances:** ceiling 1's 150 correct-stratum instances (b1 77, b2 73; 143 problems), each
  candidate byte-identical to the one ceiling 1 audited — checked against the `solution_sha256`
  of ceiling 1's cached rows before any call; any mismatch halts the study.
* **Auditor:** the shipped cross-vendor route, `openai:gpt-5.6-terra`, through **exactly the code
  path ceiling 1 used** (`explore.run_detector`, key `("holistic", "cross", d)`), the shipped
  constitution, ≥ 1 BLOCKER to flag. **K = 8** fresh readings. The only change is that each
  BLOCKER finding's observation text, which that path computes and then discards, is written to
  the study-data archive before it is discarded. Caches go to `records/fpadj/`, never to ceiling
  1's directory.
* **Not a replication test.** The route sends no sampling parameter and varies run to run, so
  this is a fresh sample of the same route, not a re-measurement of the 24. The new union
  false-positive rate at K = 8 is reported beside ceiling 1's 16.0% [10.1, 22.3] and neither is
  corrected by the other.

## Adjudication — execution, not judgement

For every instance flagged in at least one of its eight readings, every BLOCKER text:

1. **Input extraction.** `gpt-5.6-luna` — which holds no audit role anywhere in this programme —
   is shown the specification, the candidate, and one BLOCKER text, and asked for up to three
   concrete argument tuples on which the finding asserts the candidate behaves wrongly, as JSON,
   or an empty list if the finding names no concrete input. **It is never shown the reference
   solution, the hidden tests, or any expected output.** The prompt is hashed and a check asserts
   no line of the reference solution appears in it.
2. **Execution.** The candidate and the benchmark's reference solution (`canonical_solution`)
   are each run on every extracted input in a subprocess with a 10 s timeout. An input on which
   the **reference** raises or times out is *invalid* and dropped. Outputs are compared with
   Python equality, except that floats are compared with `math.isclose(rel_tol=1e-6,
   abs_tol=1e-6)`, recursively through lists, tuples and dicts. This is at least as lenient as
   EvalPlus's own comparison, so it errs toward finding *fewer* disagreements. A candidate that
   raises or times out where the reference returns **disagrees**.

**Classification of each flagged instance:**

| class | meaning |
|---|---|
| **D** | some valid extracted input on which candidate and reference disagree |
| **A** | at least one valid input extracted, and they agree on all of them |
| **N** | no valid input extracted from any of its BLOCKER texts |

## Outcome and registered reading

**Primary:** the share of flagged instances in **D**, with a problem-cluster percentile bootstrap
(10,000 resamples, seed **20260924**) and Wilson beside it, marked too narrow. **Secondary:** the
shares in A and N; the per-finding rates; the union false-positive rate at K = 8 with its
interval.

**Registered reading, fixed now:**

* If D's cluster interval excludes zero, the paper says that at least that share of this route's
  flags on test-passing code point at behaviour **the benchmark's own reference** contradicts on
  an input the hidden suite does not exercise, so the false-positive rate overstates false alarms
  by at least that share of flags.
* Otherwise the paper says that at this resolution there is no evidence that flags on
  test-passing code identify reference disagreements, and states the N share, since a flag with
  no executable input can be neither confirmed nor refuted here.

**What neither reading licenses.** D does not show the candidate violates the *specification*:
the reference may itself be wrong, or the prose may not settle the input. A does not show the
finding is wrong: it may concern something other than the extracted input. N is not a false
alarm. The words "true positive" and "false alarm" are not used of any class.

## Checks and limits fixed in advance

* **Extraction audit.** Twenty extractions drawn by seed 20260924 are read by the author, who
  records whether each extracted input is one the finding's text names. Reported as a count; it
  does not alter any classification. The author is not independent.
* **Leak check** as in step 1; a failure halts the study before execution.
* **Completeness.** The run asserts all 150 × 8 readings are present before analysis; an
  incomplete run reports the n reached and is not analysed as complete.
* **Budget.** Audit halt **$12**, extraction halt **$3**, read from the kernel's usage ledger,
  failing closed if the ledger shows no cost after any call. Expected audit cost ≈ $5.3 at
  ceiling 1's per-reading price.
* **Review.** The report goes to an independent cross-vendor review and enters the paper only
  if it ends quotable.

## Amendment 1 — the extractor's history was misstated (2026-09-23, after the first audit readings, before any extraction)

This registration said `gpt-5.6-luna` "holds no audit role anywhere in this programme". That is
false: `rate3/third_rater.py` records that it served as `cheap-cross`, an audit route, in the
explore study, and as a probe alternative in study 22. The same false sentence was written into
the paper the same day and is corrected there. What is true, and what this study needs, is
narrower: luna is **not the route whose flags are being adjudicated** (`gpt-5.6-terra`) and is
not shown the reference, the hidden tests or any expected output. Its role here is extraction,
not judgement, and the outcome is decided by execution. The choice of extractor is unchanged.
Known when written: 6 of 1,200 readings had landed, none flagged; no extraction had run.
