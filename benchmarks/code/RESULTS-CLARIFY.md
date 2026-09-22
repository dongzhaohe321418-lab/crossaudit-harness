# P3 — clarifying a specification changes what the auditor diagnoses, on 31 instances and 18 problems

Registered in `plan/P3-PREREGISTRATION.md` with thirteen amendments, every one committed before
the step it governs. Records: `records/clarify/{conditions,h3,manipulation_check,sheet_leak_check}.json`.
Auditor `gpt-5.6-terra`, clarifier `gpt-5.6-luna`, adjudicators `L1` (the author) and `L2`
(`gpt-6-astra`). Readings cost \$3.94.

## The outcome, which is correct diagnosis and not flagging

An instance counts as **correctly diagnosed** in a condition when at least one of that
condition's four readings carries a finding that **both** raters judged to state the behaviour
the hidden suite expects at an input it exercises, well enough to fix the code without seeing
the test. Disagreement counts as not diagnosed, as registered.

| condition | correctly diagnosed | Wilson (too narrow) |
|---|---:|---|
| original | **0 / 31** = 0.0% | [0.0, 11.0] |
| **clarified** | **9 / 31** = 29.0% | [16.1, 46.6] |
| placebo | **0 / 31** = 0.0% | [0.0, 11.0] |

| contrast | points | problem-cluster 95% | McNemar exact | cluster sign-flip |
|---|---:|---|---:|---:|
| **clarified − original** (H3's first half) | **+29.0** | **[+9.1, +51.7]** | 0.0039 | **0.0615** |
| placebo − original | +0.0 | [+0.0, +0.0] | 1.0000 | 1.0000 |
| clarified − placebo (post hoc) | +29.0 | [+9.1, +51.7] | 0.0039 | 0.0615 |

**H3 holds on the registered rule.** The clarified-minus-original difference excludes zero on
the problem-cluster bootstrap, which is the criterion the registration fixed before any call,
and the placebo difference is smaller than the clarified difference — both halves, as required.

## The thing that must be read next to it

**The registration asks for two paired tests and says which one respects clustering. That one
does not clear 0.05.** Exact McNemar gives 0.0039 and the cluster sign-flip permutation gives
**0.0615**, and §5 of the registration names the sign-flip as "the one that respects
clustering". The registered kill criterion was written over the bootstrap interval, not over
either p-value, so the outcome stands as registered — but a reader who wants a significance
test should be given the one the design itself prefers, and it is 0.0615.

**The reason is visible in the data.** The nine diagnosed instances sit on **five distinct
problems** out of the population's eighteen. McNemar treats nine discordant instances as nine
pieces of evidence; the sign-flip treats them as five. The gap between 0.0039 and 0.0615 is
exactly that difference, and the smaller number is the one that counts correctly.

## Three more readings, none of them decorative

**Repeated reading bought nothing.** Union at K = 1, 2, 3 and 4 is 29.0% in every case for the
clarified arm and 0.0% in every case for the other two. Each of the nine was diagnosed on **all
four** draws and none was diagnosed on only some. Whatever this auditor does with a clarified
specification, it does on the first reading.

**The adjudication held.** `L1` and `L2` agreed on **80 of 87** items, Cohen's κ = **0.844**.
`L2` used `cannot tell` on 4 items; `L1` on none.

**The clarification is not being read back.** Of the 83 findings the clarified arm produced,
**4 reproduce at least half of an added sentence as a contiguous run and none reaches three
quarters**; the placebo arm's findings quote nothing. This is the check Amendment 12 registered
for the case where the auditor simply echoes the clarification, and it is low.

## What this does not establish

**The manipulation check cannot separate information from bulk.** Its registered bar was met —
clarified specifications were judged `determined` more often than originals, +28.1 points
[+2.6, +54.3] — but the contrast that holds added length constant, clarified minus placebo, is
+18.8 points with an interval from **−9.4 to +45.2**. A third of the movement it measured is
reproduced by an edit that resolves nothing. **The audit result above is not subject to that
ambiguity** — its placebo arm diagnosed zero instances, exactly as the original did — but the
determinacy instrument's own reading remains indeterminate and is not repaired by the outcome.

**The first audit read the wrong program.** All 384 readings of the first run audited
`canonical_solution`, which is per problem, for instances that are per (batch, problem). They
were discarded and are kept as `rows-void-canonical-candidate.jsonl`. **No gate caught it**: the
code-identity gate checks that the candidate is the same across the three conditions, and it
was — identically wrong. The check that now exists requires each candidate to reproduce the
witness's own recorded outputs on the witness's own failing inputs.

**The population is small and the clarifier is weak.** 31 instances on 18 problems; the
clarifier is `gpt-5.6-luna`, chosen because it is the least entangled model available after the
Anthropic credit ran out, and Amendment 10 records that a rating pass by the same model family
agreed with itself on 7 of 11 repeats elsewhere in this programme.

**`L1` is the author.** The adjudication is one model and one interested party, not two
independent raters, and κ = 0.844 measures their agreement rather than either one's accuracy.

**Nothing here says an auditor could have written the clarification.** The generator was shown
the witness; the auditor was not. What this measures is whether a specification that settles the
rule changes what the auditor can diagnose — not whether anything in the pipeline could produce
that specification unaided.
