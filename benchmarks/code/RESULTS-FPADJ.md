# P4 — What a flag on test-passing code points at

Registered in `fpadj/PREREGISTRATION.md` (`37ae487`) before any call; Amendment 1 (`75131f6`)
corrected the extractor's history before any extraction. Records under `records/fpadj/`; finding
texts, extractions and executions in the study-data archive. Spend: audit **$4.16**, extraction
**$0.077**.

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

`gpt-5.6-luna`, shown specification, candidate and one finding and never the reference or any
expected output, extracted up to three concrete inputs per finding: 58 of 70 findings yielded
inputs, 87 in all; one reply failed to parse. Candidate and reference were then executed on each.

| class | meaning | instances |
|---|---|---:|
| **D** | candidate and reference disagree on some valid extracted input | **2** |
| **A** | at least one valid input, and they agree on all | 9 |
| **N** | no valid input | 9 |

**D = 2 of 20 = 10.0%, problem-cluster 95% [0.0, 26.3]** (19 problems; Wilson [2.8, 30.1], too
narrow). The interval includes zero, so the **registered reading** applies: *at this resolution
there is no evidence that this route's flags on test-passing code identify behaviour the
benchmark's reference contradicts.* N is 9 of 20 — flags that name no executable input and can be
neither confirmed nor refuted here.

The two D instances are real disagreements on inputs the hidden suites do not exercise: in
`b1:Mbpp/245` the candidate initialises its running maximum at zero and returns 0 on an
all-negative array where the reference returns the negative sum; in `b1:Mbpp/123` the candidate
skips an amicable number whose partner exceeds the bound. Two of 20 is a count, and it is
quoted as one.

**What it does not license** (fixed in the registration): D does not show the candidate violates
the specification — the reference may be wrong or the prose silent on the input; A does not show
a finding wrong, since it may concern something besides the extracted input; N is not a false
alarm. None of the three is called a true positive or a false alarm.

## Checks

* **Extraction audit** (registered): 20 extractions drawn at seed 20260924, read by the author,
  who is not independent — **19 faithful, 1 omission** (a finding describing the empty-list case,
  for which the extractor returned no input). Record `records/fpadj/extraction_audit.json`.
* **Leak check:** passed on all 70 prompts.
* **Spend guard:** failed closed on the first extraction reply, which carries no cost field; the
  extractor now prices each reply from its token counts and the model's capability card, as the
  kernel's ledger does. One call was made before the halt and nothing was written.

## A post-hoc sensitivity, not the registered outcome

Eight extracted inputs were written as arithmetic or `float('inf')` rather than literals and were
dropped by the literal parser. Evaluated with a restricted evaluator
(`records/fpadj/sensitivity_nonliteral.json`): the three `float('inf')` inputs agree with the
reference, moving one instance (`b2:HumanEval/20`) from N to A; the five huge-integer inputs make
the **reference** raise and stay invalid. D is unchanged at 2 of 20.

## A description, not an outcome

Reading the 70 findings, a large share of the flags on this stratum do not concern the
candidate's behaviour at all: they assert that a visible test assertion or a docstring example
contradicts the specification's prose. Those land in A or N by construction, because the
candidate and the reference agree. This is a description of the texts, not a registered
quantity, and no count of it is offered.
