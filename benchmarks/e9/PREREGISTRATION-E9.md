# E9 preregistration: do judges outside the construction accept both rules? (2026-11-14)

## Why
E6's primary population is defined by two judges (Claude Opus 5.5, GPT-6.1-sol) that also implemented the rules. A
first-read review of the paper (audit-ceiling-paper/plan/icml2027/reviews/review_gpt_M1.md, weakness 2) names semantic
admissibility as the central validity uncertainty, and the author has ruled out human raters. E9 asks whether judges
that took no part in the construction accept both rules of each open unit, whether the same judges exclude a rule
when the task's words do rule it out, and how E6's estimates change on the units they accept. E9 makes new model
calls only; it reads E6's frozen units and changes no E6 record, estimate or verdict.

What E9 can and cannot show. The judges are models from the same two vendors as the construction and are the same
model identities as two of E6's auditor configurations; they are outside the construction, not independent of it.
The positive controls were selected by E6's original judges, so agreement on them measures agreement with that
classification; the resolved items below give an anchor that does not depend on it. Hiding the rule labels cannot
hide the benchmark's behaviour from a judge that recognises a familiar task. E9 does not replace human validation.

## Items and readings
- Open items: every registered held-out open unit (41: 34 first attempt, 7 second attempt).
- Control items: every registered held-out positive control (78), where rule A is a misreading.
- Resolved items: each open unit's task with one of its two rules appended as an ordinary requirement (E6's sentence
  arm text), the rule fixed by a hash of the problem id (23 append A, 18 B); the other rule should be excluded.
Each item is read by both judges in both rule orders: 160 items, 640 readings.

## Judges and procedure (fixed in `e9.py`, frozen by hash, with this file, before the first held-out call)
Judges: Claude Sonnet 5.5 (`aud-claude-sonnet-high`) and GPT-5.6-terra (`aud-gpt-terra-high`), high reasoning budget.
Neither proposed, implemented, probed, red-teamed or judged any unit. Each reading shows the task (with the appended
requirement for resolved items), the visible tests and the two rules as RULE 1 and RULE 2, and asks whether the inputs
the rules concern are valid, and for each rule compatible / incompatible / unresolved; an "incompatible" verdict must
quote the words that rule the rule out, or say "ordinary meaning". All item kinds use the same prompt; judges are not
told which rule is the benchmark's or what kind of item they read. A reply is accepted only from a call that
succeeded without tool use and contains every field (domain, both verdicts, both quotes, reason); the full reply is
stored. Each reading may make at most two calls that reached the model (`e1.reached_model`) and six in all; a
reading that exhausts them is a terminal failure. Quotes are matched by program against the text shown (whitespace,
quotation marks and case folded; at least two words and eight characters): "found", "meaning" or "not_found". This is
a textual check only; whether the quoted words establish incompatibility is not judged.

A reading accepts an item when it calls the domain valid and both rules compatible.

## Estimands (unit values: means over the item's four readings; 10,000-draw problem bootstrap, seed 20261114)
- Adm_open: share of open-item readings that accept.
- Excl_A_open, Excl_A_control: share of readings calling rule A incompatible, on open and on control items.
- Disc = Excl_A_control - Excl_A_open (problems shared by both populations are resampled together).
- Disc_resolved: on resolved items, the share of readings excluding the rule that was not appended, minus, within
  the same problem, the share of open-item readings excluding that rule (paired).
Primary estimates use units whose four readings are complete. Identification bounds: Adm_open with terminal failures
as non-acceptance; Disc with failures as non-exclusion on controls and exclusion on open items.

## Hypotheses (one claim, a conjunction; no multiplicity adjustment because no hypothesis is claimed alone)
The claim "judges outside the construction accept the open population and are discriminating" requires all of:
- E9-1: Adm_open: the 95% lower confidence limit and the worst-case bound both exceed 50%. Fifty per cent is the point
  above which a judge accepts a randomly drawn open reading more often than not; the development pilot gives a
  sense of the likely value, but the threshold is chosen to be a low bar for a population E6 already admitted.
- E9-2: Disc: the lower confidence limit and the worst-case bound both exceed 30 points. A judge that accepted
  everything would give Disc near 0; 30 points requires that a known misreading be excluded at least 30 percentage
  points more often than an open rule, a margin that rules out indiscriminate acceptance while leaving room for
  disagreement with the original judges on some controls.
- E9-2b: Disc_resolved: lower confidence limit above 30 points, by the same reasoning, on items whose resolution
  does not depend on the original judges.
If any condition fails because the interval is wide or bounds are loose, the paper says the claim is not established
at this sample size, not that admissibility is refuted.

## E9-3: conditional sensitivity of E6 (descriptive; reported either way)
The frozen E6 analysis code recomputes E6-1 (resolved diagnosis and resolve minus menu, with its registered criterion:
lower limit of resolved diagnosis at least 50 and of the contrast above 0), E6-2 and E6-5 (lower limit above 0) and
the flag preference on: (i) the majority subset, open units that at least three of their four readings accept; (ii)
the strict subset, units all four accept; (iii) the units each judge accepts in both orders, reported with each
vendor's auditor outcomes so that selection by one vendor can be read against the other vendor's audits. Each is
reported with its number of units, estimate and interval and whether the registered criterion holds. Because the
selecting models are also E6 auditors, these are conditional sensitivity analyses, not independent replications.

## Descriptive
Per-judge acceptance, exclusion and domain-validity rates; order stability per item kind; agreement between judges on
open items; grounding of exclusions (found / meaning / not_found); Disc recomputed counting only grounded exclusions.

## Integrity
Analysis verifies the E6 freeze and the E9 freeze for the held-out split, rejects duplicate or unexpected readings and
any reading whose stored prompt hash differs from the frozen prompt, and refuses to rewrite the held-out freeze once
held-out records exist.

## Development pilot and revisions
First pilot (184 development readings, earlier prompt without the domain question or resolved items; archived as
`records/e9_dev_v1prompt.jsonl`): Adm_open 92.2 [83.9, 98.4], Disc 86.3 [76.5, 94.4], no terminal failures.
Revision before the freeze, after GPT review P11 (`review_gpt_P11.md`): replies accepted only from successful calls
without tool use; every field required and the full reply stored; domain judgement added and required for acceptance;
quote check renamed and tightened, with a grounded-only sensitivity; worst-case bounds required for E9-1 and E9-2;
non-estimable cases reported instead of failing; E9-3 keeps E6-1's registered criterion and reports per-vendor
outcomes for single-judge selections; resolved items added; analysis bound to the freeze; interpretation narrowed.
The second pilot uses the revised code on 248 development readings; its result is recorded below before the freeze.

Second pilot (2026-11-14, revised code, 248 development readings, no terminal failures): Adm_open 85.9 [76.7, 94.2];
Excl_A_open 9.4, Excl_A_control 95.0, Disc 85.6 [76.7, 93.4]; Disc_resolved 65.6 [53.1, 78.1]; all 166 exclusions
grounded (110 quotes found, 56 ordinary meaning). The judges differ: Claude accepted every open reading but excluded
the non-appended rule on only 37.5% of resolved readings; GPT accepted 71.9% of open readings and excluded it on all
resolved readings. The prompt is not changed in response; the held-out per-judge rates will be reported.
