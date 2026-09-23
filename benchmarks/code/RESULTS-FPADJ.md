# P4 — What a flag on test-passing code points at

Registered in `fpadj/PREREGISTRATION.md` (`37ae487`) before any call; Amendment 1 (`75131f6`)
corrected the extractor's history before any extraction. Records under `records/fpadj/`; finding
texts, extractions and executions in the study-data archive. Spend, from the kernel's usage
ledger: audit **$4.199** over 1,200 ledger events, including the six-reading first invocation
(summing cached row costs gives $5.72, because retry passes reuse run IDs; the ledger is the
figure); extraction **$0.077**, priced from token counts and the model's capability card.

## The readings

The shipped cross-vendor route (`gpt-5.6-terra`) re-read ceiling 1's 150 correct-stratum
instances through ceiling 1's own code path, K = 8, with every candidate checked byte-identical
to ceiling 1's before any call. 49 readings lost to provider cooldowns on the first invocation
were refused by the completeness guard and filled by a rerun: **1,200 of 1,200** present.

**20 of 150** instances were flagged in at least one reading — union false positives **13.3%**,
problem-cluster [7.9, 19.2] — against ceiling 1's 24/150 = 16.0% [10.1, 22.3] for the same route
on the same code. This is a fresh sample of a route that varies run to run, not a replication,
and neither figure corrects the other. The 20 carry **70 distinct BLOCKER findings**.

## The registered outcome

`gpt-5.6-luna` was shown the specification, the candidate and one finding. It was not given the
reference solution, the hidden tests or any separately supplied reference output; the
specifications, docstrings and findings it saw do themselves contain expected-output statements.
It extracted up to three concrete inputs per finding: 58 of 70 findings yielded inputs, 87 in
all. One reply was empty, with no cost recorded; another finding covers its input. Of the 87,
**79 were executed** on both candidate and reference; 8 written as arithmetic or `float('inf')`
were rejected by the literal parser before execution.

| class | meaning | instances |
|---|---|---:|
| **D** | candidate and reference disagree on some valid extracted input | **2** |
| **A** | at least one valid input, and they agree on all | 9 |
| **N** | no valid input survived extraction, parsing and the reference-validity rule | 9 |

**D = 2 of 20 = 10.0%, problem-cluster 95% [0.0, 26.3]** (19 problems; Wilson [2.8, 30.1], too
narrow). The interval includes zero, so the **registered reading** applies: *at this resolution
there is no evidence that this route's flags on test-passing code identify behaviour the
benchmark's reference contradicts.* That procedural reading does not erase the two observed
disagreements. N is 9 of 20: instances for which no input survived the procedure — three of them
had concrete expressions rejected as non-literals (see the sensitivity below) — so N can be
neither confirmed nor refuted here.

**Registered secondary, per finding** (same rule applied to each of the 70 findings): D **3/70
(4.3%)**, A **47/70 (67.1%)**, N **20/70 (28.6%)**. Twenty-eight of the 70 findings come from two
instances, so per-finding rates weight those instances heavily.

The two D instances are real disagreements on inputs the hidden suites do not exercise: in
`b1:Mbpp/245` the candidate initialises its running maximum at zero and returns 0 on an
all-negative array where the reference returns the negative sum; in `b1:Mbpp/123` the candidate
skips an amicable number whose partner exceeds the bound. Neither input occurs in its hidden
suite, and both candidates pass their complete hidden suites. Two of 20 is a count, and it is
quoted as one.

**What it does not license** (fixed in the registration): D does not show the candidate violates
the specification — the reference may be wrong or the prose silent on the input; A does not show
a finding wrong, since it may concern something besides the extracted input; N is not a false
alarm. None of the three is called a true positive or a false alarm.

## Checks

* **Extraction audit** (registered): 20 extractions drawn at seed 20260924, read by the author,
  who is not independent — **19 faithful, 1 omission** (a finding describing the empty-list case,
  for which the extractor returned no input). Record `records/fpadj/extraction_audit.json`. The
  first review read all 70 and found two further limitations: the empty-list omission recurs
  outside the sample, and one extraction encoded tab and newline as two-character escape strings
  rather than the characters the finding names. Neither changes a class: the implementations
  behave identically on those inputs and other findings supply the actual whitespace inputs.
* **Leak check,** as implemented: no line of the reference at least 20 characters long and absent
  from the specification and candidate appears in any prompt. That is narrower than the
  registration's "no line" wording; it passed on all 70 prompts.
* **Spend guards — not as registered.** The audit halt of $12 was checked per invocation, not
  cumulatively (total spend stayed at $4.20). The extraction guard priced replies from token
  counts rather than reading the usage ledger, and let an empty reply with no cost pass; it did
  halt on the first priced-reply attempt when no cost could be computed, but that halt is not
  independently documented in the archive. Registered per-call fail-closed accounting was not
  fully implemented.
* **Comparison rule:** correct on every output observed here, but not universal —
  `same("nan", "nan")` and `same("1.0", "'1'")` return true. Neither case occurs in this data.
* **Amendment 1's timing.** It says six readings, none flagged, had landed "when written"; at its
  commit time (17:39 +08:00) the ledger shows 57 readings. Both precede any extraction, which is
  what the amendment governs.

## A post-hoc sensitivity, not the registered outcome

Eight extracted inputs, belonging to three N instances, were written as arithmetic or
`float('inf')` rather than literals and were rejected by the literal parser before execution. Evaluated with a restricted evaluator
(`records/fpadj/sensitivity_nonliteral.json`): the three `float('inf')` inputs agree with the
reference, moving one instance (`b2:HumanEval/20`) from N to A; the five huge-integer inputs make
the **reference** raise and stay invalid. D is unchanged at 2 of 20.

## A description, not an outcome

Reading the 70 findings, many do not concern the candidate's behaviour on a new input: they assert
that a visible test assertion or a docstring example contradicts the specification's prose. Some
of those assertions are themselves mistaken — one says the candidate returns 4 on a documented
example on which both implementations return 2. Whether a finding of this kind lands in A or N is
an empirical outcome of the extraction and execution, not a consequence of its topic, and this
description offers no count and no explanation of the instance-level flag rate.
