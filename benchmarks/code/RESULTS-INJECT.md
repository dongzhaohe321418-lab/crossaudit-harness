> # The headline is WITHDRAWN (Amendment 7, 2026-09-16)
>
> Two independent cross-vendor reviews refused quotation. Neither figure this study reported
> survives: 97.8% conditions on a gate that selects for detectability, and 84.2% removes that gate
> but keeps filters that **do not establish specification entailment at all**. F6 was implemented
> as `bool(obj.get("witness_input"))` while this study registered it as recovering the first
> failing hidden input; nothing here connects the quote, the named class, the witness and the
> actual failure.
>
> What the study may still report is descriptive: the auditor blocks small injected edits far more
> often than the natural residual, **and those edits are separable from natural code at 96.7%**, so
> the two populations differ in more than specification-determinedness. **This is not a
> prospective test of study 21's split, and C4 does not gain one from this work.**
>
> The numbers below are left unedited. Read them with the banner.

# Study 22 — the ceiling on defects the specification determines

Preregistered at `inject/PREREGISTRATION.md` before the first model call, with five
amendments, each committed before the step it governs: two construction pilots, the OpenAI
credit failure that changed a gate model, the paired twin arm, and a note fixing in advance
which contrast carries which confound. Tables in this file are generated from
`records/inject/numbers.json` by `report_inject.py` and spliced verbatim by
`inject/splice_tables.py`; no figure here is typed by hand.

## 1. What was measured

Ceiling 1 measured the shipped cross-vendor auditor at 33 of 110 = 30.0% [20.0, 40.7] union
recall at eight independent readings, on the defects an ordinary generation run left behind.
Study 21 then found, **post hoc**, that most of that residual is failure the specification's
prose does not determine. This study tests that prospectively on a population where
"specification-determined" is fixed by construction: a defect is injected into a solution that
passes every test, and the instance is admitted only if the injector quoted the specification
verbatim, six mechanical filters accept, and two models that are not the auditor both agree the
prose settles the question. Population I is 92 instances over 54 problems, built by walking all
910 stratum-C instances in one seeded order; 281 passed the filters and 92 passed both gates.

<!-- BEGIN TABLE primary (records/inject/tables.md) -->
| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| I — defects the specification determines, injected | 92 (54) | **90 of 92** | — |
| ceiling 1's stratum P — the natural residual | 110 (56) | **33 of 110** = 30.0% (Wilson [22.2, 39.1]) | [20.0, 40.7] |
| **difference (two-sample, not paired)** | | **+67.8 points** | **[+56.3, +78.9]** |
<!-- END TABLE primary -->

**H22a, the preregistered primary, is positive and the kill does not fire.** On defects the
specification determines, the same auditor, the same constitution and the same eight readings
reach 90 of 92, against 33 of 110 on the natural residual.

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

| population | n (problems) | union recall at K = 8 | 95% cluster CI |
|---|---:|---|---|
| I — filters accepted **and** both gates agreed | 92 (54) | **90 of 92** = 97.8% | — |
| gate-**rejected** sample — filters accepted, a gate refused | 40 (35) | **31 of 40** = 77.5% (Wilson [62.5, 87.7]) | [62.2, 90.5] |
| **all filter-accepted, stratified over both strata** | 281 | **84.2%** | **[73.8, 93.1]** |
| ceiling 1's stratum P — the natural residual | 110 (56) | 33 of 110 = 30.0% | [20.0, 40.7] |

Recall on the gate-rejected sample is **materially lower** than on I, 77.5% against 97.8%, so
under Amendment 6's stated reading rule **the gate is part of the effect** and the 90 of 92 may
not be quoted as a figure for specification-determined defects at large. It is quoted here only as
what the auditor achieves on the population both gates accepted.

What survives, and what this study should lead with, is the stratified figure over every instance
the six mechanical filters accepted regardless of the gate's vote: **84.2% [73.8, 93.1] against
the natural residual's 30.0% [20.0, 40.7]**. The gate inflates the headline by about 14 points; it
does not create the contrast. Even the instances the gate refused are audited at more than twice
the rate of the natural residual.

Two limits on the stratified figure. It still conditions on the six filters, which is a weaker
condition than the gate but not no condition. And the two strata are pooled by population weight
with the rejected stratum estimated from 40 of 189, so its contribution carries sampling error the
interval above includes and the point estimate hides.

**Duplication in population I, and why the cluster interval absorbs it.** |I| is 92 instances but
only **59 distinct programmes**: 33 groups of byte-identical `modified_sha256` cover 66 of the 92.
An interval that treats the 92 as independent is therefore too narrow by more than the usual
problem-recurrence margin, and **every Wilson figure in this study is to be read with that in
mind**. The primary intervals are not affected: **no duplicate group spans more than one
`problem_id`** (checked directly: 0 of 33), and the primary is a percentile bootstrap over whole
problem clusters, 54 of them, so byte-identical instances always resample together. Problem
clustering is here at least as conservative as programme clustering. The gate-rejected sample
carries no duplication at all: 40 instances, 40 distinct programmes, 35 problems.

The internally controlled contrast is stronger still, and it is the one with no problem-mix
confound: every instance of I was audited again without the injected lines.

<!-- BEGIN TABLE paired (records/inject/tables.md) -->
Each injected instance against its own unmodified twin: same problem, same specification, same generator, same code but for the injected lines, same auditor, same K = 8 (Amendment 4).

| arm | flagged | 95% Wilson |
|---|---:|---|
| injected | 90 of 92 | [92.4, 99.4] |
| unmodified twin | 11 of 92 | [6.8, 20.2] |
| **difference (paired)** | **+85.9 points** | **cluster [+77.3, +93.3]** |

Discordant pairs: 79 where only the injected instance was flagged, 0 where only the twin was. Exact McNemar p = 3.31e-24; cluster sign-flip p = 5.00e-06. Every discordant pair points one way, so the percentile bootstrap's bound is an artefact and the Tango interval [+77.3, +91.6] is the one to read (ceiling 1 Amendment 5).
<!-- END TABLE paired -->

**The auditor is responding to the defect, not to the problem.** The same code without the
injected lines is flagged 11 times in 92; with them, 90 times. Seventy-nine discordant pairs
point one way and none the other.

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

Last-step gain 0.00 points; the preregistered flattening bar (at most 1.0) is met, so the fitted asymptote 97.4% is quotable.
Single reading, I against the natural residual: +78.9 points [+69.0, +87.8].
<!-- END TABLE curve -->

One reading catches 94.4%; eight catch 97.8%. On the natural residual the same auditor climbs
from 10.7% to 30.0% over the same eight readings. **Whatever the 30.0% ceiling is, it is not
the auditor's ability to see a defect that the specification settles.**

## 2. The finding this study was built to be able to contradict, and did not

Study 21's split was post hoc, on one substrate, from two raters one of whom is the author.
This population was constructed before any auditor read it, admitted by mechanical filters and
two models that are not the auditor, and compared against a frozen number that was fixed in
2026-09-06. The direction survives, and the size of the gap is larger than study 21's post-hoc
split suggested.

What this licenses is narrow and worth stating exactly: **the measured audit ceiling is not a
limit on detecting specification-determined defects.** It does not license "the auditor catches
specification-determined defects" as a general claim — see §3 — and it says nothing about
whether the natural residual is beyond reach for some other reason.

## 3. The limitation that matters most: the defects are detectably artificial

The preregistration anticipated that an injected defect might be easier to see for reasons
having nothing to do with the specification, and fixed a measurement for it in advance: show a
frontier model that is neither the auditor nor a gate each solution with its specification, and
ask whether it was written in one pass or written and then edited.

<!-- BEGIN TABLE probe (records/inject/tables.md) -->
| quantity | value |
|---|---|
| prober | `anthropic:claude-opus-4-8` — not the auditor, not a gate |
| items | 92 injected, 92 natural |
| answered | 152; unparsed 32 |
| accuracy on the answered | **96.7%** (Wilson [92.5, 98.6]) |
| accuracy over all 184 items | between 79.9% and 97.3% |
| covers chance | **no** |
| injected called edited | 65 of 69 |
| natural called edited | 1 of 83 |
<!-- END TABLE probe -->

**It can tell.** The interval does not cover chance under any reading: 96.7% among the items it
answered, and between 79.9% and 97.3% over all 184 if the 32 it would not classify are counted
as all wrong or all right. Those 32 skew toward injected items, so the answered-only figure
flatters the separation. Artificiality is therefore **not** bounded, and a reader is entitled to
ask how much of §1's gap is salience rather than specification-determinedness.

One post-hoc cross-tabulation was computed on that question. It turns out to carry no
information, and it is kept here with that verdict rather than deleted:

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
explanation. **It does not, and the arithmetic says so.** With 2 misses over 92 instances and only
4 instances in the natural-looking cell, the chance that either miss lands in that cell even if
the auditor were riding exactly the signal the probe uses is about 11%; the expected number of
misses there is 0.12. Fisher's exact test on the table gives **p = 1.0**. Observing an empty cell
is what both hypotheses predict, so the table separates them not at all. It is **post hoc** and it
is **not evidence in either direction**, and no sentence in this study may lean on it.

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

## 5. What was not run

The naming adjudication of §5 of the preregistration — does a blocking finding name the injected
class? — is not in this report. The finding texts are archived and the injector's own
`input_class` and diff give it a real key, so it needs no new model call for its material, but it
needs the two-rater protocol and that has not been run. Until it is, every number here is about
**blocking**, not about naming, and no sentence may say otherwise.

The OpenAI gate deferred by Amendment 3 has not been re-run either; both gates are Anthropic
models, which makes them more correlated and the gate weaker, which §1 of the preregistration
argues is conservative for the primary.

## 6. Cost

Construction $9.58 (injection and both gates, 2,135 injector attempts over 910 base instances),
audit $6.26 (sixteen draws; 10 twin instances came free from ceiling 1's frozen cache), probe
$0.63. **Total $16.47** against a preregistered cap of $35.
