> # The headline is WITHDRAWN (Amendment 7, 2026-09-16)
>
> Two independent cross-vendor reviews refused quotation. Neither figure this study reported
> survives: 97.8% conditions on a gate that selects for detectability, and 84.2% removes that gate
> but keeps filters that **do not establish specification entailment at all**. F6 was implemented
> as `bool(obj.get("witness_input"))` while this study registered it as recovering the first
> failing hidden input; nothing here connects the quote, the named class, the witness and the
> actual failure. §5 sets out what each of the six filters does check, which round 2 of the
> review established is less than four of them claim — and corrects two things this banner
> said in its first version: F6 is a **truthiness** check, not a non-empty *string* check (102
> of the 281 recorded witnesses are lists, not strings), and F6 as **registered** would not
> have been enough either, since recovering the failing input and executing a witness still
> does not show that the specification entails the hidden suite's expected value.
>
> What the study may still report is descriptive: the auditor blocks small injected edits far more
> often than the natural residual, **and a probe separates the two sets at 96.7%** by a feature
> it does not identify — the two arms differ in task composition, which is a confound on its own,
> so the classification result does not establish an additional distinguishing property. **This is not a
> prospective test of study 21's split, and C4 does not gain one from this work.**
>
> The counts below are the ones the run produced and have not been recomputed; several
> sentences around them HAVE been corrected across seven review rounds, and the cost
> section now carries two figures where it carried one. Read them with the banner.

# Study 22 — the ceiling on defects the specification determines

Preregistered at `inject/PREREGISTRATION.md` before the first model call, with five
amendments, each committed before the step it governs: two construction pilots, the OpenAI
credit failure that changed a gate model, the paired twin arm, and a note fixing in advance
which contrast carries which confound. Tables in this file are generated from
`records/inject/numbers.json` by `report_inject.py` and spliced verbatim by
`inject/splice_tables.py`. Figures inside those blocks are generated; figures in the prose
around them — §5's witness-type split, the cost breakdown, the self-announcing count — are
written by hand and checked only where a test names the exact string. Round 7 corrected
"no figure here is typed by hand".

## 1. What was measured

Ceiling 1 measured the shipped cross-vendor auditor at 33 of 110 = 30.0% [20.0, 40.7] union
recall at eight independent readings, on the defects an ordinary generation run left behind.
Study 21 then found, **post hoc**, that most of that residual is failure the specification's
prose does not determine. This study set out to test that prospectively on a population where
"specification-determined" would be fixed by construction: a defect is injected into a solution
that passes every test, and the instance is admitted only if the injector quoted the
specification verbatim, six mechanical filters accept, and two models that are not the auditor
both agree the prose settles the question. **That construction does not deliver the property**
(§5): the filters are textual and executional, none of them tests entailment, and the gate
is associated with detectability, and conditioning on it cannot be assumed to lower recall. The
paragraphs below describe what
was built and measured; the label "specification-determined" is withdrawn from it. Population I is 92 instances over 54 problems, built by walking all
910 stratum-C instances in one seeded order; 281 passed the filters and 92 passed both gates.

<!-- BEGIN TABLE primary (records/inject/tables.md) -->
| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| I — injected edits accepted by the filters and both gates (**NOT established as specification-determined**) | 92 (54) | **90 of 92** | — |
| ceiling 1's stratum P — the natural residual | 110 (56) | **33 of 110** = 30.0% (Wilson [22.2, 39.1]) | [20.0, 40.7] |
| **difference (two-sample, not paired)** | | **+67.8 points** | **[+56.3, +78.9]** |
<!-- END TABLE primary -->

**H22a, the preregistered primary, is positive on its own terms and the kill does not fire —
and both statements are WITHDRAWN as evidence, because the denominator is not what H22a says it
is.** On the gate-accepted injected population, the same auditor, the same constitution and the
same eight readings reach 90 of 92, against 33 of 110 on the natural residual. The counts are
reproducible; "defects the specification determines" is not a description of the 92 (§5), and
the kill is computed on that same denominator, so its not firing licenses nothing either.

**That 90 of 92 is a property of the gate-accepted population, not of specification-determined
defects in general, and Amendment 6 measured the difference rather than arguing about it.**
An earlier draft of this section argued that the filters and the gate could only err by admitting
instances they should have refused, so any failure mode would depress recall and none could
manufacture the effect. That argument is false. The gate asks whether the specification settles
the behaviour on an `input_class` the injector itself names, and no filter ever checked that the
named class is the one the edit actually breaks, so the gate refuses plainly determined boundary
edits: `b1:Mbpp/223` changes `count > n/2` to `count >= n/2` against a specification that says
"occurs more than n/2 times", and both gate models voted no. Edits of that kind are the subtlest
in the population and the hardest to see, so the gate plausibly selects for detectability in the
direction that *raises* recall.

Amendment 6 therefore preregistered, with no threshold and as a magnitude to report rather than a
hypothesis to accept, an audit of **40 of the 189 instances the six filters accepted and the gate
then refused**, drawn by `random.Random(20260916)`, under the same auditor and the same K = 8.

<!-- BEGIN TABLE rejected (records/inject/tables.md) -->
Amendment 6's gate-rejected arm: the six filters accepted these instances and a gate then refused them. Same auditor, same K. Round 2 of the review moved this table out of hand-written prose and into the records, where it can be regenerated. Every figure reproduces the hand-computed one exactly, at the registered seed 20260916. Round 2 of this report claimed the published cluster interval could not be reproduced because its seed was never recorded; that was wrong on both counts, and round 3 disproved it by reproducing the interval from the seed the registration names.

| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| gate-**rejected** sample | 40 (35 problems, 35 distinct programmes) | **31 of 40** = 77.5% (Wilson [62.5, 87.7]) | [62.2, 90.5] |

The instances the gate discarded are caught nearly as often as the ones it kept. **That is why Amendment 3's "the gate is conservative" is withdrawn**: the gate selects on detectability, so conditioning on it cannot be assumed to lower recall. This observation survives the withdrawal of both headline figures.
<!-- END TABLE rejected -->

The 84.2% that stood in this table — the filter-accepted population stratified over both
strata — **is withdrawn**, and the reason is its denominator, not its arithmetic. It is
"small injected edits that survived a sparse visible suite and failed a hidden one", not
"defects the specification determines", so it lacks the **semantic** denominator C4 needs. Its
population is well defined — the 281 filter-accepted edits — and round 4 corrected the earlier
"no population to be a recall of", which withdrew more than the evidence requires.
Round 2 of this report added a second reason, that the figure had been hand-computed and its
interval could not be reproduced. **That was wrong.** Round 3 reproduced both the estimate
(84.15%) and its interval [73.8, 93.1] from the registered seed 20260916; being absent from
`numbers.json` is a provenance weakness, not irreproducibility. Two further limits on it, from
round 3 and stated here rather than left implicit: the weighted estimator is appropriate only
for the 281 filter-accepted edits under the stated protocol, and its bootstrap is not a
validated finite-population interval — 40 of 189 were sampled without replacement, I was
measured in full, and one problem crosses the sampled strata — so its coverage is uncalibrated
under `EXPERIMENT_RECORD.md` §10. The 97.8% on population I is withdrawn for the same reason and
is quoted only where the record labels it withdrawn.

Recall on the gate-rejected sample is **materially lower** than on I, 77.5% against 97.8%, so
under Amendment 6's stated reading rule **the gate is part of the effect** and the 90 of 92 may
not be quoted as a figure for specification-determined defects at large. It is quoted here only as
what the auditor achieves on the population both gates accepted.

An earlier version of this section said that what survives, and what the study should lead
with, is the stratified figure over every instance the six filters accepted regardless of the
gate's vote — 84.2% against the natural residual's 30.0%. **That is withdrawn.** Dropping the
gate removes the selection on detectability but leaves a denominator of "small injected edits
that survived a sparse visible suite and failed a hidden one", which is not the population the
comparison needs; a recall figure needs a population to be a recall *of*. What remains true, and
is descriptive rather than a test of anything, is that the auditor blocks these injected edits
far more often than the natural residual, and that even the edits the gate refused are blocked
at more than twice the natural rate — which is the observation that killed the gate's
conservativeness argument, not a measurement of detecting specification-determined defects.

Two limits on the stratified figure. It still conditions on the six filters, which is a weaker
condition than the gate but not no condition. And the two strata are pooled by population weight
with the rejected stratum estimated from 40 of 189, so its contribution carries sampling error the
interval above includes and the point estimate hides.

**Duplication in population I, and why the cluster interval absorbs it.** Population I holds
92 instances but
only **59 distinct programmes**: 33 groups of byte-identical `modified_sha256` cover 66 of the 92.
An interval that treats the 92 as independent is therefore too narrow by more than the usual
problem-recurrence margin, and **every Wilson figure in this study is to be read with that in
mind**. The primary intervals are not affected: **no duplicate group spans more than one
`problem_id`** (checked directly: 0 of 33), and the primary is a percentile bootstrap over whole
problem clusters, 54 of them, so byte-identical instances always resample together. Problem
clustering is here at least as conservative as programme clustering. The gate-rejected sample
carries duplication of its own: 40 readings over **35 distinct programmes** across 35 problems,
five byte-identical pairs, each pair inside its own problem cluster so the cluster interval
already absorbs it. An earlier version of this line said 40 distinct programmes and "no
duplication at all", contradicting the generated table beside it.

The internally controlled contrast is stronger still, and it is the one with no problem-mix
confound: every instance of I was audited again without the injected lines.

<!-- BEGIN TABLE paired (records/inject/tables.md) -->
Each injected instance against its own unmodified twin: same problem, same specification, same generator, same code but for the injected lines, same auditor, same K = 8 (Amendment 4).

| arm | flagged | 95% Wilson |
|---|---:|---|
| injected | 90 of 92 | [92.4, 99.4] |
| unmodified twin | 11 of 92 | [6.8, 20.2] |
| **difference (paired)** | **+85.9 points** | **cluster [+77.3, +93.3]** |

Discordant pairs: 79 where only the injected instance was flagged, 0 where only the twin was. Exact McNemar p = 3.31e-24; cluster sign-flip p = 5.00e-06. Every discordant pair points one way, so the percentile bootstrap's bound is an artefact and the Tango interval [+77.3, +91.6] is reported beside it as an INDEPENDENCE-BASED sensitivity calculation: it is computed on the discordant counts alone and accounts for neither the problem clusters nor the duplicated programmes. The cluster interval remains the primary one, and its coverage under this design has not been calibrated (ceiling 1 Amendment 5).
<!-- END TABLE paired -->

**The auditor is responding to the edit, not to the problem.** The same code without the
injected lines is flagged 11 times in 92; with them, 90 times. Seventy-nine discordant pairs
point one way and none the other. Round 2 narrowed this heading: the twin contrast identifies a
response to **the edit, including whatever the edit carries with it**, and §3's probe shows the
two sets are separable by *something* it does not identify. It does not identify a response to a
defect as such, and it does not establish that the separating feature is a cue in the edit.

And the reading barely needs repeating:

<!-- BEGIN TABLE curve (records/inject/tables.md) -->
| K | union recall on I |
|---:|---|
| 1 | 94.4% |
| 2 | 96.5% |
| 3 | 97.0% |
| 4 | 97.4% |
| 5 | 97.6% |
| 6 | 97.7% |
| 7 | 97.8% |
| 8 | 97.8% |

Last-step gain 0.00 points; the preregistered flattening bar (at most 1.0) is met, so the fitted asymptote 97.4% would be quotable on the flattening bar alone, but is NOT quotable: the bar speaks to the shape of the curve, not to what the population is.
Single reading, I against the natural residual: +78.9 points [+69.0, +87.8].
<!-- END TABLE curve -->

One reading catches 94.4%; eight catch 97.8%. On the natural residual the same auditor climbs
from 10.7% to 30.0% over the same eight readings. An earlier version concluded from this that
whatever the 30.0% ceiling is, it is not the auditor's ability to see a defect the specification
settles. **That conclusion is withdrawn**: it needs the 92 to be specification-determined
defects, and nothing in this construction establishes that. What the contrast shows is that the
auditor blocks these injected edits far more often than the natural residual — and §3 shows the
edits are separable from natural code, so the difference is not isolated to the property this
study meant to test.

## 2. The finding this study was built to be able to contradict, and did not

Study 21's split was post hoc, on one substrate, from two raters one of whom is the author.
This population was constructed before any auditor read it, admitted by mechanical filters and
two models that are not the auditor, and compared against a frozen number that was fixed in
2026-09-06. The direction survives, and the size of the gap is larger than study 21's post-hoc
split suggested.

**What this licenses about C4 is nothing, and that is the finding.** The sentence that stood
here —
"the measured audit ceiling is not a limit on detecting specification-determined defects" — is
**withdrawn**. It was the study's reason for existing, and it requires population I to be
specification-determined defects, which §5 shows no filter establishes. The study therefore
contradicts nothing: claim C4 keeps exactly the status study 21 gave it, post hoc and
unreplicated, and this work does not move it in either direction.

## 3. The limitation that matters most: the two populations are separable, by something

The preregistration anticipated that an injected defect might be easier to see for reasons
having nothing to do with the specification, and fixed a measurement for it in advance: show a
frontier model — the preregistration asked for one that is neither the auditor nor a gate, and
the implemented probe **departed from that**: it runs `claude-opus-4-8`, one of the two gate
models — each solution with its specification, and
ask whether it was written in one pass or written and then edited.

<!-- BEGIN TABLE probe (records/inject/tables.md) -->
| quantity | value |
|---|---|
| prober | `anthropic:claude-opus-4-8` — not the auditor, but **one of the two gate models**, so this probe is not independent of the gate |
| items | 92 injected, 92 natural |
| answered | 152; unparsed 32 |
| accuracy on the answered | **96.7%** (Wilson [92.5, 98.6]) |
| accuracy over all 184 items | between 79.9% and 97.3% |
| covers chance | **no** |
| injected called edited | 65 of 69 |
| natural called edited | 1 of 83 |
<!-- END TABLE probe -->

**It can tell the two sets apart.** The interval does not cover chance under any reading: 96.7%
among the items it answered, and between 79.9% and 97.3% over all 184 if the 32 it would not
classify are counted as all wrong or all right. Those 32 skew toward injected items, so the
answered-only figure flatters the separation; the archived `?` values record unparsed
classifications, which are not necessarily refusals. Artificiality is therefore **not** bounded,
and a reader is entitled to ask how much of §1's gap is salience rather than
specification-determinedness.

**Three limits on this probe, from round 3, and they matter more than the accuracy does.** Its
model is `anthropic:claude-opus-4-8`, which is **one of the two gate models** — so the check on
the gate's population was run by a model that had already gated it, and it is not an independent
reading. Its injected and natural arms **share no problem at all**, so what it separates may be
two task sets rather than edited from unedited code. And it is shown the specification as well as
the code, so it is not restricted to surface salience. What survives is that the two populations
are separable by *something*; **which something is not identified**, and "edit salience" is one
candidate among several rather than the measured quantity.

One post-hoc cross-tabulation was computed on that question. It does not distinguish the
explanations, and it is kept here with that verdict rather than deleted — round 6 removed the
stronger "carries no information", which stood directly above the paragraph rejecting it:

<!-- BEGIN TABLE xtab (records/inject/tables.md) -->
POST HOC: asked after the probe and the audit were both in hand.

| the probe called it | n | the auditor caught |
|---|---:|---:|
| it would not say | 23 | 23 |
| edited (artificial) | 65 | 63 |
| written in one pass (natural) | 4 | 4 |

The auditor's only misses were `b1:Mbpp/404`, `b2:Mbpp/404`, which the probe called edited and edited.
<!-- END TABLE xtab -->

The auditor caught every injected defect the probe judged natural, and its only two misses were
items the probe judged artificial. An earlier draft read that as pointing against the salience
explanation. **It does not, and the table is too small to say anything either way.** Place 2 misses
uniformly at random among the 92 instances, with only 4 instances in the natural-looking cell:
the chance that either lands there is **8.55%** (1 − C(88,2)/C(92,2)), and the expected number
of misses there is **0.087** (2 × 4/92). Round 5 requires three qualifications on that calculation, and they matter
more than the figures do. It is a **uniform-placement** calculation, not a probability derived
from any model of the auditor following the probe's signal — no such model is specified here.
It is **not cluster-aware**, and that is not incidental: the two misses are `inj:b1:Mbpp/404`
and `inj:b2:Mbpp/404`, **the two instances of one problem**, so they are not two independent
draws. And round 4's earlier 11% and 0.12 used 69 as the denominator — the injected items the
probe answered — in a sentence that says 92.

Fisher's exact test on the table gives **p = 1.0**. What that supports is that **this table does
not distinguish the proposed explanations** — not the stronger readings that stood here: that
both hypotheses predict an empty cell, or that the table contains no information. It is
**post hoc**, it is far too small to separate anything, and no sentence in this study may lean
on it.

The honest summary of §1 and §3 together: the gap is real, large, and measured against a frozen
comparator and a paired control, and part of it may be salience that this study cannot separate
out and has no evidence against. Separating it needs a population of natural defects independently known to be
specification-determined, which is what study 23's second substrate and a human rater would
supply.

## 4. The other preregistered secondaries

<!-- BEGIN TABLE splits (records/inject/tables.md) -->
| split | group | caught |
|---|---|---:|
| more than 2 changed lines | yes | 13 of 13 |
| | no | 77 of 79 |
| the changed line sits under a conditional | yes | 30 of 30 |
| | no | 60 of 62 |
<!-- END TABLE splits -->

Recall does not fall with a larger edit or with the defect sitting inside a branch; both groups
are at or near ceiling, so these splits discriminate nothing and are reported as such rather
than read as null effects. The third preregistered split — whether the instance's problem also
contributes a stratum-P instance — has an empty side: population I is built from stratum C,
where the generator succeeded, and stratum P is where it failed, so the two populations share
almost no problems. That is the problem-mix confound Amendment 5 fixed in advance, visible in
the data, and it is exactly why H22b exists.

## 5. What the six filters check, and what they were registered to check

Round 2 of the cross-vendor review exercised each filter against the real implementation. The
gaps below are **implementation gaps demonstrated by counterexample**, not measurements of how
often they bite in the archived population; nobody has counted that, and this section does not
claim to.

* **F1** was registered as: the quote appears in the specification, whitespace-normalised, at
  least six words. It implements exactly that textual check and establishes nothing semantic.
* **F2** was registered as: every visible test passes. A binary suite can report success after
  a `SystemExit(0)` raised before any assertion completes.
* **F3** was registered as: the hidden failure is an assertion or an exception, not a timeout.
  It accepts any non-timeout non-pass — an `os._exit(2)` candidate passed all six filters with
  neither an assertion nor an exception.
* **F4** was registered as: the edit adds no import. It compares **sets of module names**, so
  `from math import cos` beside an existing `import math` passes.
* **F5** was registered as: compiles and completes at least one visible test. It checks only
  that no visible test timed out and that the text `"SyntaxError"` is absent; it stayed true
  after an immediate `ZeroDivisionError`, and the early-exit case above passed F2 and F5
  without completing a test.
* **F6** was registered as: records the witness **and** recovers the first failing hidden input
  by study 21's witness path. It is `bool(obj.get("witness_input"))`, a truthiness check.
  Study 21's `witness_for` exists and is never called here. Of the 281 recorded witnesses,
  **179 are strings and 102 are lists**; F6 validates neither type nor argument structure, and
  nothing is executed.

**Two corrections to this study's own account of its failure**, both from round 2 and both
against the direction that would have made the self-criticism cleaner:

* Amendment 7 called F6 "a non-empty string check". It is not: it is a truthiness check, and
  102 of the 281 witnesses are not strings at all.
* Amendment 7 implied that F6 *as registered* would have established specification entailment.
  It would not. Recovering the first failing hidden input and executing a witness shows that
  the edit changes behaviour on an input the hidden suite exercises. It does not show that the
  **specification** entails the value the hidden suite expects there, which is the property
  population I was supposed to have.

So the conclusion stands and its grounds are wider than Amendment 7 gave: **no filter in this
study establishes specification entailment, and no repair of F6 alone would have.** What would
is a population whose specification-determinedness is established by someone other than the
injector.

**That successor needs more than independence, and round 7 named what.** An independent party
must validate **the actual violation and the specification-entailing expected behaviour**,
under a fixed, blinded protocol. Independence alone does not do it, and neither does a second
substrate alone: **task composition and construction confounding survive both**, as §3's probe
shows here. This is a condition on a future C4 study. **It is not work required to finish this
one**, which is finished.

## 6. What was not run, and is not going to be

**This report is final in its descriptive form.** What it delivers is blocking observations on a
constructed population, after the withdrawal of the C4 interpretation. The two items below are
**final omissions, not outstanding work**: completing this study does not depend on buying
either, because neither would supply the semantic denominator whose absence is the reason C4
gains nothing here. Round 7 of the review asked for that to be said plainly, so it is said here
rather than left for a reader to infer from seven rounds of deferral.

The naming adjudication of §5 of the preregistration — does a blocking finding name the injected
class? — is not in this report. The finding texts are archived and the injector's own
`input_class` and diff give it a real key, so it needs no new model call for its material, but it
needs the two-rater protocol and that has not been run. Until it is, every number here is about
**blocking**, not about naming, and no sentence may say otherwise.

The OpenAI gate deferred by Amendment 3 has not been re-run either; both gates are Anthropic
models, which makes them more correlated and the gate weaker. §1 of the preregistration argues
that this is conservative for the primary; **that argument is withdrawn** (Amendment 6 and §5).
A weaker gate is not a conservative one here: the instances it refused are caught 31 times in
40, so gate acceptance is associated with detectability. That is an association, not a finding
that specification judgements played no part — round 4 narrowed this, and the same overstatement
stood in §1.

## 7. Cost

Construction $9.58 (injection and both gates, **2,292** paid injector attempts over 910 base
instances — 2,135 is the number that reached the filters, which round 6 found this line
conflating),
audit $6.26 (sixteen draws; 10 twin instances came free from ceiling 1's frozen cache), probe
$0.63 — **$16.47** — plus Amendment 6's gate-rejected arm at **$1.90** (320 readings, derived
here from the cached per-reading costs), for a **total of $18.37** against a preregistered cap
of $35. Round 4 found the rejected arm missing from this section, and round 6 corrected how
that was put: it was in both usage ledgers and its committed manifest all along, and missing
only from this paragraph.

**$18.37 is the retained-record subtotal, not the study's recorded API value.** Summing
`api_value_usd` over the archived project ledgers — 4,794 distinct event ids — gives
**$18.53**, $0.16 more. The difference is construction beyond the retained injection and gate
caches ($0.110073), an earlier audit invocation `inject-0911042818` ($0.049900), and a route
probe ($0.000195). Both figures are below the $35 cap; the larger one is what was spent.
