# E8 preregistration: can an auditor find the behaviour a task leaves open? (draft, 2026-11-08)

Written after an exploratory development pilot (`pilot_discover.py`, records `records/discover_dev.jsonl`: open
units 31 of 32 readings, positive controls 53 of 60) and before any held-out E8 call. E8 uses only construction
records of E6 (protocol e6-v4.3: units, programs, rules) and new Claude calls; it reads no E6 audit and does not
affect E6.

## Units and readings
The registered held-out E6 units: 41 open units (34 first attempt, 7 second attempt) and the registered positive
controls (78, or as finally registered by E6's freeze). Each unit is read twice, once with each program shown.

## Procedure (fixed; prompts as in `pilot_discover.py`, frozen by hash at the first held-out call)
Elicitor: Claude Sonnet 5.5, low budget (`aud-claude-sonnet-low`), shown the task, the visible tests and one program,
asked for at most six unspecified behaviours as questions to the task author. Judge: Claude Opus 5.5
(`adj-claude-opus`), shown the task, both rules in a hash-fixed random order (not told which is the benchmark's) and
the questions; it answers whether any question targets the behaviour on which the rules differ. One attempt per
reading; a call that never reached the model (no usage recorded) is retried.

## Estimands (problem-level means over the two readings; 10,000-draw problem bootstrap, seed 20261113)
- D_open: share of readings on open units whose questions target the open behaviour.
- D_control: the same on positive controls, where the task's words decide the behaviour.
- S = D_open - D_control (selectivity), on the two populations as independent samples.
## Hypotheses
E8-1: D_open lower bound > 50 (an auditor asked to look usually names the open behaviour).
E8-2 (two-sided, reported either way): S, with its interval; the development pilot suggests S is small, and the paper
will state whether the held-out interval excludes 20 points (substantial selectivity) or 0 (any selectivity).

## Limitations stated in advance
One vendor for both elicitor and judge; a model judge decides what counts as targeting the behaviour; six questions
per reading make broad lists cheap, so D_open partly measures breadth. Review by a model from another vendor precedes
the held-out run.
