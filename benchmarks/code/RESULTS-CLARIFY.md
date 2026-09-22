# P3 — a clarified specification changes what the auditor diagnoses, and only when it is right

> **Second version, after the first cross-vendor review refused the first.** Its blocking finding
> was not about the arithmetic, which reproduced exactly. It was that **the intervention is not
> what the report said it was**: the generator sees the failing *inputs* and never their expected
> values, so the rule it adds is one it *inferred*, and on most instances that rule **contradicts
> the hidden oracle**. The review was right, the classification below is the consequence, and the
> result it produces is narrower, sharper, and differently framed.

Registered in `plan/P3-PREREGISTRATION.md` with thirteen amendments, each committed before the
step it governs. Records under `records/clarify/`. Auditor `gpt-5.6-terra`, clarifier
`gpt-5.6-luna`, adjudicators `L1` (the author) and `L2` (`gpt-6-astra`). **32 instances on 19
problems.** Readings for this run cost \$1.86; the discarded first audit cost \$2.13, and the
ledger's \$3.99 is the sum of both.

## The registered result

An instance counts as **correctly diagnosed** in a condition when at least one of that
condition's four readings carries a finding that **both** raters judged to state the behaviour
the hidden suite expects at an input it exercises, well enough to fix the code without seeing
the test. Disagreement counts as not diagnosed.

| condition | correctly diagnosed | Wilson (too narrow) |
|---|---:|---|
| original | **0 / 32** | [0.0, 10.7] |
| **clarified** | **9 / 32** = 28.1% | [15.6, 45.4] |
| placebo | **0 / 32** | [0.0, 10.7] |

| contrast | points | problem-cluster 95% | McNemar exact | cluster sign-flip |
|---|---:|---|---:|---:|
| **clarified − original** (H3's first half) | **+28.1** | **[+7.7, +51.4]** | 0.0039 | **0.0602** |
| placebo − original | +0.0 | [+0.0, +0.0] | 1.0000 | 1.0000 |
| clarified − placebo (post hoc) | +28.1 | [+7.7, +51.4] | 0.0039 | 0.0602 |
| **Amendment 2's registered secondary** (23 instances, 15 problems) | **+34.8** | [+10.0, +60.9] | — | 0.0632 |

H3 holds on the criterion §4 registered: the difference excludes zero on the problem-cluster
bootstrap and the placebo difference is smaller. **The secondary agrees in direction**, which
§5 required be reported beside the primary always and which the first version omitted.

**The test the registration itself prefers does not clear 0.05.** §5 asks for exact McNemar and
a cluster sign-flip permutation and says the sign-flip respects clustering; it is **0.0602**
against McNemar's 0.0039. The nine diagnosed instances sit on **five problems**, so McNemar
counts nine pieces of evidence where five exist. The registered kill criterion was written over
the interval and not over a p-value, so the reading stands as registered — and a reader wanting
a significance test should be handed the one the design prefers.

## What the intervention actually was

`generate.py` shows the clarifier the failing **inputs** and never their expected values. So the
added rule is **inferred**, and it is often wrong. Every clarification was compared by hand
against its own oracle and the table is published row by row in
`records/clarify/clarification_classification.json` so any row can be disputed:

| what the added rule does | instances | correctly diagnosed |
|---|---:|---:|
| **states the rule the oracle encodes** | 7 | **7 / 7** |
| relaxes a precondition the original prose asserted | 1 | 1 / 1 |
| right on some exercised inputs, wrong on others | 3 | 1 / 3 |
| **contradicts the oracle** | **21** | **0 / 21** |

Examples, each checkable against the record: `b2:Mbpp/137`'s clarification says an all-zero array
gives `0.0` where the oracle expects `inf`; `b1:Mbpp/278`'s says to count all elements, giving 6
for a six-element tuple where the oracle expects 5; `b2:Mbpp/559`'s says the largest sublist of
an all-negative list is its greatest element where the oracle expects 0; `b1:Mbpp/459`'s says
every non-uppercase character survives where the oracle keeps only lowercase letters.

**So the claim this study supports is not "clarifying a specification helps".** It is narrower:
**when the added rule is the rule the hidden suite encodes, the auditor diagnosed the defect in
7 of 7 instances; when the added rule contradicts it, in 0 of 21.** The registered contrast is
the average of those two populations, and it is reported above as registered rather than being
replaced by its favourable half.

**Two things that cross-tabulation is not.** It is **post hoc**, and the classification was
written after the outcome was known — published row by row precisely because a judgement that
cannot be mechanised should be disputable rather than trusted. And the consistent instances may
simply be the **easy** ones: a problem whose omission a generator can infer correctly from
inputs alone may also be a problem whose defect is easier to diagnose. Nothing here separates
those.

## Three readings that are not decoration

**Repeated reading bought nothing, on these draws.** Union at K = 1, 2, 3 and 4 is identical in
every arm: each of the nine was diagnosed on all four draws and none on only some. That is a
statement about the four draws taken, not about this auditor in general.

**The adjudication held.** `L1` and `L2` agreed on **84 of 91** items, Cohen's κ = **0.852**.
Two item judgements deserve their own note, both raised by the review: `P0001` accepts a
finding that complains about a docstring, where three near-equivalent findings were rejected by
`L2`; and one accepted finding contains a false example. Neither changes 9 of 32, because the
affected instances carry other jointly accepted findings.

**The clarification is largely not reproduced verbatim, and the first version measured that
wrongly.** Of 87 clarified-arm findings, **1 reproduces at least half of an added sentence
contiguously and in order**; 39 share at least half its content words in any order. The first
version reported 4 and 11 from a metric that **never checked order at all** — it asked whether
each word appeared *anywhere*, so a fully reversed sentence scored 1.00 — and from an extraction
that folded the specification's own assertions into the supposed addition on 21 of 31 instances.
Both are fixed, both counts moved, and **neither number establishes blinding**: lexical overlap
cannot exclude paraphrase.

## What this does not establish

* **The manipulation check cannot separate information from bulk.** Its registered bar was met,
  +28.1 points [+2.6, +54.3] of `determined` judgements, but the contrast holding added length
  constant is +18.8 points with an interval from **−9.4 to +45.2**. The audit's placebo arm
  diagnosed zero instances, so the *observed diagnosis contrast* is not subject to that
  ambiguity — but zero placebo diagnoses do not validate the proposed mechanism, and the
  determinacy instrument's own reading remains indeterminate.
* **The first audit read the wrong program.** All 384 readings of the first run audited
  `canonical_solution`, which is per problem, for instances that are per (batch, problem). They
  are kept as `rows-void-canonical-candidate.jsonl`. The code-identity gate passed throughout
  because it checks the candidate is the same across the three conditions, and it was —
  identically wrong. The check that now exists compares each candidate against the frozen batch
  source **and** requires it to reproduce the witness's recorded outputs; the source comparison
  establishes identity and the witness agreement establishes consistency, and an earlier version
  of this report claimed the second alone was sufficient, which it is not.
* **One instance was excluded for a leak that was not one.** `b1:Mbpp/427` was dropped because
  its clarification "quoted hidden-test lines" that are printed in its own specification and
  visible tests; they reached the gate through the candidate's embedded assertions. The gate now
  excludes public text, the instance is back, and the population is 32 — the same 32 the
  manipulation check used.
* **The population is small and the clarifier is weak.** 32 instances on 19 problems; nine
  successes on five problems. `gpt-5.6-luna` was chosen as the least entangled model available
  after the Anthropic credit ran out.
* **`L1` is the author.** One model and one interested party, not two independent raters. κ
  measures their agreement, not either one's accuracy.
* **Nothing here says an auditor could have written the clarification.** The generator was shown
  the witness's inputs; the auditor was shown neither. And on 21 of 32 instances the generator,
  with those inputs, inferred a rule that is wrong.

## Generation yields, as Amendment 9 requires them reported together

| run | gate | kept |
|---|---|---:|
| 1 | before Amendment 8 | 25 / 44 |
| 2 | Amendment 8 | 29 / 44 |
| 3 | Amendment 9 — registered as final | 32 / 44 |
| — | after Amendment 13's candidate repair and the public-text gate fix | **32** |
