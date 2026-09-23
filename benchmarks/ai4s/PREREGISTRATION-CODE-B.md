# A4S-1b — auditing scientific code with the step as the deliverable

Registered 2026-09-24, **after A4S-1's registered outcomes were computed and before any model call
of this arm**. A4S-1 (`PREREGISTRATION-CODE.md`) is not amended: its outcomes stand as registered and
are reported as such. This arm exists because of what reading A4S-1's flags showed.

## What is known when this is written

A4S-1's registered outcomes (`records/ai4s/code_results.json`): at K = 8 the `cross` family flags
87.7% of defective and 68.7% of correct instances; `self` 40.7% and 27.3%. A post hoc reading of a
seeded sample of 20 flagged correct instances, and a pattern count over all flagged ones, found that
the auditor's task included the whole problem's main description, which CrossAudit treats as what the
increment must deliver. Many BLOCKERs therefore say that the step's code does not implement the whole
multi-step problem ("implements only `f_V` … no RPA calculation"), or hold the step to requirements
stated for the whole problem. Such a BLOCKER is present on 69 of the 103 flagged correct instances
(the only kind on 16), by a pattern count that is itself post hoc. The framing is part of A4S-1's
registered design; it is a property of the instrument, not of scientific code.

## Question

With the same instances and the same program bytes, but a task that names the step's function as the
deliverable, how much of A4S-1's flag rate on correct code remains, and what happens to recall?

## Design

* **Instances**: A4S-1's 81 defective and 150 correct instances (`strata.json`), unchanged.
* **Program**: byte-identical to A4S-1 (the dependencies, then the sample's functions for steps 1..k,
  with the benchmark's code for its three skipped steps), as `work/solution/solution.py`.
* **Task** (the only change), exactly:

  > Deliver the function for step {n} of a multi-step scientific programming problem.
  >
  > Step {n}: {step description}
  >
  > Background: {step background}
  >
  > Function to implement: {function header and return line}
  >
  > Allowed dependencies: {dependencies}
  >
  > The file also contains the functions written for the earlier steps of this problem, which this
  > step may call; they are given, not part of this step's deliverable. The overall problem, for
  > context only (later steps will complete it): {main problem description}

* **Families and K**: `cross` (`openai:gpt-5.6-terra`) and `self` (`claude-haiku-4-5` through the CLI
  route of A4S-1 Amendment 1), K = 8 each, through the product's `run_audit` with the shipped
  constitution and checks as in A4S-1. Flag = at least one model BLOCKER.
* **Budget**: halt at **$40** cumulative for this arm, read from its own ledgers.

## Outcomes

Primary: `cross` union recall at K = 8 on the defective stratum and union flag rate on the correct
stratum, with problem-cluster percentile bootstraps (10,000, seed 20260930). Secondary: the same for
`self`; the K ladder; the paired self − cross contrast at K = 8 (exact McNemar, cluster sign-flip);
and the paired change from A4S-1 to A4S-1b per family and stratum (instance-level, flagged at K = 8
in one arm and not the other; exact McNemar, cluster sign-flip, cluster-bootstrap interval on the
difference).

**Residual**: defective instances flagged by no reading of either family in this arm are rated as in
A4S-1 (same rubric, a fresh blind sheet, seed 20260931, L1 then `gpt-5.6-luna`), and the H2 rule of
A4S-1 is applied to this residual as a secondary reading, not a replacement of A4S-1's.

## Expectations stated now

* **B1 (directional).** The `cross` flag rate on correct instances at K = 8 falls from A4S-1 to
  A4S-1b. Supported if the paired difference's cluster interval lies below zero; killed if it lies
  above zero; otherwise inconclusive.
* No directional expectation for recall. If recall also falls, the two arms together say that the
  flag rate on scientific code is set largely by what the task names as the deliverable.

What no reading licenses: that A4S-1b is "the" measurement and A4S-1 an error (both are registered
designs; the difference between them is the finding); calling a flag on a correct instance a mistake
without reading it (C16 applies).

## Review

The report covers both arms and goes to cross-vendor review; neither enters the paper before it is
quotable.
