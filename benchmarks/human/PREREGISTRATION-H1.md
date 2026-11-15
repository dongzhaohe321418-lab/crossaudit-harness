# H1 preregistration: a human admissibility check on E6's held-out units (2026-11-15, before any label)

## Why
Three unanchored reviews (audit-ceiling-paper/plan/icml2027/reviews/review_claude_fresh_F1-F3.md) name the same main
objection: that both rules of each randomised-contract unit are admissible readings of the task has been judged only
by models of the two vendors that also build and audit the units (E6's judges; E9's outside judges are the auditor
models). H1 adds one human judgement per unit.

## Rater and blinding
One rater: the paper's author, a scientist who did not construct, judge or inspect any unit (construction, judging and
analysis were run by an AI assistant). The rater sees, per unit, the task text exactly as auditors see it and the two
rules in an order fixed by a hash of the problem id (`admissibility_items_test.json`), with no indication of which
rule the benchmark's reference follows, of the auditors' readings or of any result. The key
(`admissibility_key_test.json`) is withheld from the repository until the labels are recorded. The rater is asked not
to run code or look up the benchmark.

## Question (per unit, 41 held-out units)
"Would a careful programmer, reading only this task, accept each rule as a correct way to complete it?" Answers per
rule: yes / no / unsure; optionally a one-line reason. A unit is human-admissible if both rules receive "yes".

## Analysis (fixed now)
- H1-1 (descriptive): the share of human-admissible units, with a Wilson 95% interval; and per rule, the share of
  "no" for the benchmark's rule and for the alternative (does the human side with the benchmark?).
- H1-2: E6's registered estimands on the human-admissible subset with E6's frozen analysis code (as E9's subset
  analysis): E6-5 (sentence minus task), E6-2 (convention advantage), and the exploratory flag preference; reported
  with intervals; "holds on the human-admissible subset" if each confirmatory lower limit stays above 0.
- Agreement with E9's outside judges (unit-level acceptance), Cohen's kappa.
Labels are recorded before the key is opened; the labels file is committed first, then the key, then the analysis.

## Limits
A single rater, who is also the author, is not a panel; H1 tests whether the units survive one careful human reading,
not population agreement. Reported either way.

## Amendment 1 (2026-11-15, before any label)
The rater is a co-author of the paper, not the first author: a person who did not construct, judge or inspect any
unit and has not seen the results by unit. Labelling is done in a standalone file
(audit-ceiling-paper/plan/icml2027/human_review/human_review_pack.html) that shows the 41 items first and unlocks the
paper-level questions (subtitle, contribution type, sign-off on the AI disclosure) only after every item has both
answers, so the rater labels before reading the paper's abstract. The file exports the answers as JSON
([{item, r1, r2, reason}] plus the paper-level answers), which is committed as received, before the key; the analysis
(h1.py) is unchanged except that it now also reads the pack's export format (labels under a "labels" key). The limitation in this file still applies: one rater, now a co-author.

## Amendment 2 (2026-11-16, before any second-rater label): a second rater
After the first rater's results (85.4% admissible; all four rejections on the alternative rule), a second rater is
added to measure agreement. The second rater is someone who did not construct, judge or inspect any unit, has not
seen the first rater's answers or any result by unit, and is not the first author. They receive the same 41 items in
the same order and the same instructions, in a pack with no paper questions (`human_review_pack_rater2.html`, pack
id hc2-v1); their labels are committed as received before analysis. Analysis (`hc2.py`, committed before the labels):
- inter-rater agreement on unit-level admissibility (both rules accepted): percent agreement and Cohen's kappa, and
  rule-level agreement on "no" answers;
- the second rater's admissible share (Wilson 95%) and where their rejections fall (benchmark or alternative rule);
- E6-5, E6-2 and the flag preference on the units both raters accept, with E6's frozen code.
Reported either way. In the paper the human check becomes "two raters"; the first rater's results stay as reported.


## Note (2026-11-16): amendment 2 not run
No second rater was available, so no second-rater labels were collected and `hc2.py` was not run on any. The paper
reports one human rater, as before amendment 2; the pack and the analysis script stay in the repository unused.
