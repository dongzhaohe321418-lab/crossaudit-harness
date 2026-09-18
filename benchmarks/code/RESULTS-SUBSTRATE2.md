> # Third run — complete, and holding no quotable number
>
> Two earlier runs were voided for the same fault in different costumes: the visible-test text
> shown to **both** the auditor and the generator was sliced out of its test class, first without
> the class header (300 of 300 tasks failed to parse), then — by the repair for that — with a
> hidden method's decorators re-attached to the first visible method (26 of 300 altered ASTs).
> Their readings are quarantined in `cache-void-2026-09-17/` and their numbers are kept in git so
> this run can be compared against them.
>
> This run passed all three of Amendment 8's gates before a call was made, each proved able to
> fail first: execution equivalence on all 300 frame tasks, every displayed method AST-identical
> to the scored one at digest `5c21539e…`, and the driver's own guards. Both ladders are complete,
> 8 draws x 252 instances per family, none short. Generation $1.907, audit $27.659, total
> **$29.566** against a $45 cap and a $40 halt.
>
> **Amendment 8 asked one question before the numbers existed: does a clean extraction reproduce
> the six reversals the voided run produced? Five of the six did. One did not** — the
> false-positive intervals, which across the three runs have been apart, overlapping, and apart
> again. Amendment 8 states its criterion over the set, and five of six is a case it did not
> anticipate. The looser reading, judging each reversal on its own, would license five findings
> and **is declined**: the five that reproduced are the ones favourable to this work, and
> adopting a reading after seeing which way the numbers fell is the failure this study has
> already made three times. **The registered consequence follows — the study has consumed three
> runs and about $82 without a quotable number, and that is reported as found.**
>
> This run is not void. Its gates passed, its ladders are complete, its numbers are internally
> consistent, and they are all below. What they lack is the licence Amendment 8 conditioned on
> reproducing the six, and the independent cross-vendor review that every number in this
> programme needs. Whether 5 of 6 should license the five is left to the owner and to review,
> not settled by the author of the run that would benefit.

# Study 23 — the measured ceiling is an operating point, not a constant

> **Fourth version, and the first on a clean extraction.** Preregistered at
> `benchmarks/code/substrate2/PREREGISTRATION.md`, committed before any model call of this
> study. Ceiling 1's protocol was repeated unchanged on a second substrate. The first three
> versions reported the two voided runs; every number below is the third run's and none is
> carried over. Both ladders were complete when this version was written, so H23d is answered
> as registered rather than deferred. **H23e was not run** (§6). No cross-vendor review has
> read this, so nothing here is approved for quotation.

## The sentence the preregistration requires

Section 4 fixed, before the first reading, what had to be written if substrate 2's recall
came out higher. It did.

> **The paper's central quantity is substrate-dependent. Union recall of 30.0%
> [20.0, 40.7] at eight readings is not a general figure: it is what the shipped
> cross-vendor auditor reaches on HumanEval+/MBPP+-shaped tasks, and the same auditor under
> the same protocol reaches 74.5% [63.8, 84.5] on BigCodeBench's stdlib half.**

That sentence is true and it is not the finding. The auditor is not *better* on the harder
substrate. It is **louder**: it flags more of everything, and its recall per false-positive
point is lower at every reading count.

**The matched-operating-point claim is the one finding that has not held still.** On the
registered cross-vendor comparison, substrate 2's cheapest reading costs 32.8% [25.5, 40.2]
at K = 1 against substrate 1's dearest 16.0% [10.1, 22.3] at K = 8: **those two intervals do
not meet**. Across three runs this quantity has been apart, overlapping, and apart again,
**so it is reported as unstable and is not leaned on**, whichever run one believes. Pooling
every family reverses it in this run too, which is why the comparison is stated with its
family named, in both directions. §4 gives both families' answers and all three runs'
distances; §7 says what that leaves standing.

## 1. What was run

Ceiling 1's measurement, unchanged, on a substrate whose median task is **118
specification words and 41 reference-solution lines** against substrate 1's 41 and 6 — 2.88
times the prose and 6.83 times the code (Table 1). The frame is 300 BigCodeBench tasks that
pass two mechanical filters in this project's interpreter; the visible/hidden suite split is
seeded and mechanical, with hidden ⊇ visible.

`claude-haiku-4-5` generated 600 candidates over two batches for **$1.91**, giving strata
**P 102, C 460, F 38** (Table 2). The whole P population and a seeded sample of 150 C
instances — 252 instances — were frozen into `records/substrate2/audit_set.json` before the
first audit call, from this generation and no other: the frozen file carries the generation
digest it was drawn from and a scope drawn from a different one is refused. The shipped
cross-vendor auditor (`openai:gpt-5.6-terra`), holistic, the shipped constitution unmodified,
then read every one of them **eight** times, and the same-vendor auditor (`claude-haiku-4-5`,
the generator's own model) read all 252 eight times after it. **Both ladders are complete**:
every draw of both families covers all 252 instances (Table 3). Audit spend was **$27.66** of
a $60 cap (Table 9).

The cross-vendor ladder was not bought in one sitting. An unstable local proxy — SSL
`UNEXPECTED_EOF` and `RemoteDisconnected`, no HTTP 429 and no `insufficient_quota` — left
draws 5 to 8 short on the first pass, and a supervised process finished them against the
cache, which never buys a reading twice. There are **6237** recorded provider denials across
the eight cross-vendor draws, and every draw still landed its 252 readings. A denial is a
call that produced no reading; it is not in the usage ledger and cost nothing.

### Table 1 — the two substrates, described
<!-- BEGIN T1 (records/substrate2/tables.md) -->
Both columns are medians over the frozen frame; the ratio is the median ratio, not a ratio of medians drawn from matched tasks. No corpus text is reproduced here.

| | substrate 1 (HumanEval+ / MBPP+) | substrate 2 (BigCodeBench, stdlib half) | ratio |
|---|---:|---:|---:|
| median specification words | 41 | **118** (IQR 91–143) | 2.88× |
| median reference-solution lines | 6 | **41** (IQR 36–48) | 6.83× |
| median test methods per task | — | 5 (minimum kept 3) | — |
| tasks in the frame | — | 300 of 1,140 | — |
<!-- END T1 -->
### Table 2 — generation, the strata and the frozen audit set
<!-- BEGIN T2 (records/substrate2/tables.md) -->
Two batches over 300 tasks. The audit set was drawn by `random.Random(20260917)` and committed before the first audit call.

| | count |
|---|---:|
| candidates generated | 600 |
| stratum P (passes visible, fails hidden) | **102** |
| stratum C (passes both) | 460 |
| stratum F (fails visible) | 38 |
| P instances audited | 102 (cap 200; the whole population, no draw needed) |
| C instances audited | 150 (cap 150) |
| generation cost | $1.91 (600 calls) |
<!-- END T2 -->
### Table 3 — the audit ladder's coverage
<!-- BEGIN T3 (records/substrate2/tables.md) -->
The frozen audit set is 252 instances (102 P, 150 C). Both ladders are complete: every draw of both families covers all 252. A denial is a call that never produced a reading; it is not in the usage ledger and cost nothing. Both ladders were complete when this report was first written, so there is no earlier, shorter read to record.

| draw | `cross` readings | `cross` denials | `self` readings | `self` denials |
|---:|---:|---:|---:|---:|
| 1 | 252 / 252 ✓ | 0 | 252 / 252 ✓ | 307 |
| 2 | 252 / 252 ✓ | 0 | 252 / 252 ✓ | 178 |
| 3 | 252 / 252 ✓ | 0 | 252 / 252 ✓ | 98 |
| 4 | 252 / 252 ✓ | 180 | 252 / 252 ✓ | 85 |
| 5 | 252 / 252 ✓ | 282 | 252 / 252 ✓ | 924 |
| 6 | 252 / 252 ✓ | 1,451 | 252 / 252 ✓ | 660 |
| 7 | 252 / 252 ✓ | 2,242 | 252 / 252 ✓ | 1,008 |
| 8 | 252 / 252 ✓ | 2,082 | 252 / 252 ✓ | 673 |

**Draw-to-draw agreement.** Over the 252 audited instances, the cross-vendor arm's flag splits across its eight draws on **102** of them; the same-vendor arm's splits on **22**. Every flag in both families came from the model (0 readings were flagged by the deterministic checks layer). The same-vendor arm returned one identical set of finding digests across all eight draws on 71 instances, the cross-vendor arm on 96; no finding text was archived or read.
<!-- END T3 -->

## 2. H23a (primary) — recall is far higher on the harder substrate

Unioning eight independent readings flags **76 of 102** stratum-P instances: **74.5%, 95%
problem-cluster bootstrap [63.8, 84.5]**, Wilson [65.3, 82.0] beside it. Substrate 1's
frozen comparator is 33 of 110 — **30.0% [20.0, 40.7]**, Wilson [22.2, 39.1].

The difference is **+44.5 points, 95% two-sample problem-cluster bootstrap [29.5, 58.7]**
(10,000 resamples, seed 20260917). The two populations share no instance and no problem, so
each population's problems were resampled independently within one seed stream and the
difference of the two resampled rates taken. **This contrast is not paired**, and no
McNemar test and no sign-flip test is reported for it. The interval excludes zero and the
sign is the one §4 said would oblige the sentence above.

The preregistration fixed no direction here and said both directions were interesting. This
is the direction that costs the paper a headline.

## 3. H23b — the union curve, the fit and the flattening bar

Recall on P runs from **50.5% [39.3, 61.5]** at one reading to **74.5% [63.8, 84.5]** at
eight, with every point's cluster interval in Table 4. The constrained exponential fit gives
an asymptote of **70.7% [60.4, 80.8]** with tau = 0.92 and r² = 0.860 — the fitted asymptote
sits *below* the raw union at K = 8, which is what a curve this flat at the end does to a
one-parameter exponential, and it is the raw union that is quoted.

Ceiling 1's registered flattening bar is a last-step gain of at most 1.0 point. On P the
gain from seven readings to eight is **1.47 points [0.73, 2.31]**: **the bar is NOT met**,
and no asymptote may be quoted for this curve. On substrate 1 the same auditor gained
1.93 points [1.14, 2.78] at the same step and also missed the bar.

This is one of the five reversals of the first voided run that the clean extraction
reproduces. That run recorded 0.62 points [0.13, 1.23] here and reported the bar as met — the
one curve in this programme that appeared to saturate; the second voided run recorded 1.52
and missed it, and this run records 1.47 and misses it. Neither substrate's cross-vendor
curve has flattened at the budget reached, and the word "saturates" is available for neither.

The population is still mostly decided early: 29 of the 102 P instances were flagged by all
eight readings and 26 by none. What changed is the tail — enough instances are still
flipping at the eighth reading to carry the last step past the bar.

The false-positive curve has **not** flattened either. Its last step on C gains **1.17 points
[0.63, 1.75]**, so C's fitted asymptote of 50.7% [42.0, 59.5] is an extrapolation and the
raw **53.3% [44.2, 62.3]** is the number to quote.

### Table 4 — union recall and union false positives at every K, substrate 2
<!-- BEGIN T4 (records/substrate2/tables.md) -->
Unit of analysis: the instance. n = 102 stratum-P instances from 53 problems (recall) and 150 stratum-C instances from 117 problems (false positives), the same instances at every K. The union rate at K is averaged over all C(8, K) subsets of the eight draws, exactly. Intervals are 10,000-resample problem-cluster percentile bootstraps, seed 20260917. The **registered** gain ratio is ceiling 1's own column — recall gained over K = 1 divided by false positives gained over K = 1. The **level** ratio is recall at K divided by the false-positive rate paid at K; it is post hoc and is not in the preregistration.

| K | union recall on P [95% cluster CI] | union FP on C [95% cluster CI] | recall per FP point, registered gain ratio | recall per FP point, POST-HOC level ratio |
|---:|---|---|---:|---:|
| 1 | 50.5% [39.3, 61.5] | 32.8% [25.5, 40.2] | — | 1.54 |
| 2 | 59.7% [48.4, 70.8] | 40.4% [32.4, 48.3] | 1.21 | 1.48 |
| 3 | 64.3% [53.1, 75.3] | 44.6% [36.1, 52.9] | 1.18 | 1.44 |
| 4 | 67.4% [56.4, 78.0] | 47.3% [38.7, 55.7] | 1.17 | 1.42 |
| 5 | 69.6% [58.7, 80.0] | 49.3% [40.5, 57.9] | 1.17 | 1.41 |
| 6 | 71.5% [60.7, 81.7] | 50.8% [41.9, 59.5] | 1.17 | 1.41 |
| 7 | 73.0% [62.4, 83.1] | 52.2% [43.1, 61.0] | 1.17 | 1.40 |
| 8 | 74.5% [63.8, 84.5] | 53.3% [44.2, 62.3] | 1.17 | 1.40 |

Fit on P: A = 70.7% [60.4, 80.8], tau = 0.92, r² = 0.860. Last-step gain 1.47 points [0.73, 2.31] — ceiling 1's flattening bar (≤ 1.0 point) is **not met**.
Fit on C: A = 50.7% [42.0, 59.5], tau = 1.14, r² = 0.901. Last-step gain 1.17 points [0.63, 1.75] — the bar is **not met**.
<!-- END T4 -->
### Table 5 — substrate 2 against substrate 1 at K = 8
<!-- BEGIN T5 (records/substrate2/tables.md) -->
The two populations share no instance and no problem, so this is a **two-sample** bootstrap: each population's problems are resampled independently and the difference of the two resampled rates is taken. Nothing here is paired, so no McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and assumes instances are independent, which within a substrate they are not.

| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |
|---|---|---|---|
| **H23a (primary)** union recall, P, K = 8 | **74.5%** (76/102, 53 problems) Wilson [65.3, 82.0] | 30.0% (33/110, 56 problems) Wilson [22.2, 39.1] | **+44.5 points** [29.5, 58.7] |
| **H23c** union false positives, C, K = 8 | **53.3%** (80/150, 117 problems) Wilson [45.4, 61.1] | 16.0% (24/150, 143 problems) Wilson [11.0, 22.7] | **+37.3 points** [26.5, 48.1] |
<!-- END T5 -->

## 4. H23c — the auditor is not better here, it is louder

Eight readings flag **80 of 150** correct solutions: **53.3% [44.2, 62.3]**, Wilson
[45.4, 61.1], against substrate 1's frozen **16.0% [10.1, 22.3]**. That is **+37.3 points
[26.5, 48.1]** on the same two-sample bootstrap — close to the recall difference, and in the
same direction.

So the recall bought per false-positive point is **lower on substrate 2 at every K**, under
both definitions of that quantity:

* **Ceiling 1's registered gain ratio**, which is the comparator H23c names: recall gained
  over one reading divided by false positives gained over one reading. Substrate 1 runs 1.67 down to **1.68**; substrate 2 runs 1.21 down to **1.17**. This is one of the five reversals the
  clean extraction reproduces. The first voided run reported 1.16 down to 0.91 and concluded
  that from K = 6 on, each extra reading of substrate 2 bought less recall than it bought
  false positives; on a clean extraction the ratio stays above 1 at every K, and that
  conclusion is withdrawn.
* **The level ratio** — recall at K divided by the false-positive rate actually paid at K.
  This is **post hoc**: it is not in the preregistration, and it is reported because it is
  the form a reader can weigh against a fixed operating cost. Substrate 1 runs 2.37 down to
  1.88; substrate 2 runs **1.54 [1.12, 2.11]** down to **1.40 [1.12, 1.76]**.

**The honest limit on this comparison, stated for a named family.** Substrate 2's *single*
cross-vendor reading already costs **32.8% [25.5, 40.2]** false positives, above substrate
1's *eight*-reading cross-vendor **16.0% [10.1, 22.3]**; **those two intervals do not meet,
and 3.2 points separate them** — a 3.2-point separation, one of the distances between
quoted intervals that owe no interval of their own. **The claim is now made only for the cross-vendor family - 16.0% [10.1, 22.3]
against 32.8% [25.5, 40.2], which do not meet**, and on this run's arithmetic
**Within the cross-vendor family there is therefore no K at which the two substrates can be
compared at a matched false-positive rate**.

**That conclusion is true of this run and has not held still across runs, and both halves are
stated.** The first voided run separated the same two intervals by 2.6 points and the
second overlapped them by 3.5 points — distances between quoted intervals, owing no interval
of their own — where this run separates them. It is the one quantity of
the six that the clean extraction did not settle in the same direction as the run before it,
and a reader weighing it should weigh that it has moved twice under the same protocol.

**Pooled across families the separation does not survive, and it is stated rather than left
to be found.** Substrate 1's dearest reading anywhere is its same-vendor family at K = 8:
substrate 1's same-vendor family at K = 8 is 24.0% [17.2, 31.2] and substrate 2's cheapest
cross-vendor reading is 32.8% [25.5, 40.2], and those two intervals overlap: a 5.7-point
overlap, likewise a distances between quoted intervals figure owing none of its own. The
point estimates are still disjoint, but a matched false-positive rate **cannot be ruled out**
once every family and its uncertainty are admitted. Table 6 carries both answers.

Either way, every recall comparison in this report — H23a's +44.5 points [29.5, 58.7]
included — compares two different operating points, not two detection abilities. Bringing
the cross-vendor rates onto common ground would take readings this study did not buy: a
stricter flag rule, or a different auditor, on substrate 2.

### Table 6 — recall bought per false-positive point, both substrates
<!-- BEGIN T6 (records/substrate2/tables.md) -->
The level ratio is POST HOC — the preregistration's H23c names ceiling 1's registered gain ratio, whose values are in Table 4. Both definitions point the same way; the level ratio is shown here because it is the one that can be read against a fixed operating cost.

| K | substrate 1 recall | substrate 1 FP | substrate 1 level ratio | substrate 2 recall | substrate 2 FP | substrate 2 level ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.7% | 4.5% | 2.37 | 50.5% | 32.8% | 1.54 |
| 2 | 15.0% | 7.1% | 2.12 | 59.7% | 40.4% | 1.48 |
| 3 | 18.3% | 9.2% | 2.00 | 64.3% | 44.6% | 1.44 |
| 4 | 21.2% | 10.9% | 1.94 | 67.4% | 47.3% | 1.42 |
| 5 | 23.8% | 12.4% | 1.91 | 69.6% | 49.3% | 1.41 |
| 6 | 26.0% | 13.7% | 1.89 | 71.5% | 50.8% | 1.41 |
| 7 | 28.1% | 14.9% | 1.88 | 73.0% | 52.2% | 1.40 |
| 8 | 30.0% | 16.0% | 1.88 | 74.5% | 53.3% | 1.40 |

Substrate 2's level ratio is lower than substrate 1's at **every** K, and so is the registered gain ratio (**every** K).

**Can any reading count put the two substrates at the same false-positive rate?** The answer depends on which auditor families are admitted, so it is given twice.

**Within the cross-vendor family** — the comparison this study draws, since substrate 1's frozen comparator and substrate 2's primary are both the shipped cross-vendor auditor — **no**. Substrate 2's cheapest reading costs 32.8% [25.5, 40.2] at K = 1, and substrate 1's dearest costs 16.0% [10.1, 22.3] at K = 8. Those intervals do not meet: 3.2 points separate them.

**Pooling every family measured on either substrate** — **yes, narrowly**. Substrate 1's dearest reading anywhere is its `self` family at K = 8, 24.0% [17.2, 31.2], and its upper bound reaches 5.7 points into substrate 2's cheapest interval of [25.5, 40.2]. The point estimates are still disjoint (24.0% against 32.8%), but the intervals overlap, so a matched false-positive rate cannot be ruled out pooled. Substrate 1's interval here is the one ceiling 1's own Table 1 quotes; its second bootstrap stream for the same point gives an overlap of 5.8 points instead.
<!-- END T6 -->

## 5. H23d — the same-vendor arm flags more of everything, and the sign flips

**H23d is answered as registered**, paired at K = 8 over the whole frozen audit set, by
`report_ceiling3.paired_union_difference` unchanged under seed 20260917.

On P the same-vendor arm's union recall is **81.4% [71.0, 90.4]**, Wilson [72.7, 87.7],
against the cross-vendor arm's **74.5% [63.8, 84.5]** on the same 102 instances:
**+6.9 points, problem-cluster [-4.9, 18.6]** (16 instances flagged only by `self`, 9 only
by `cross`; exact McNemar p = 0.22952; cluster sign-flip p = 0.34174; Tango [-2.9, 16.8] and
grid-unconditional [-6.3, 19.3] beside it, both ignoring clustering). **The interval spans
zero.** The first voided run reported +17.0 points [2.0, 32.0] here and read it as a sign
reversal against substrate 1; on a clean extraction the same-vendor arm is not shown to
differ from the cross-vendor one on recall at all, and that reading is withdrawn.

**No sign reversal is established.** Ceiling 1 measured −12.7 points [−25.0, −0.9] for the
same contrast — the generator's own model saw *less* of its own defects than a stranger did.
The first voided run measured +17.0 [2.0, 32.0] here and read the pair as a
substrate-dependent reversal. The second measured +4.0 [−10.1, 18.2] and the third measures
**+6.9 [−4.9, 18.6]**; both include zero. This is one of the five reversals the clean
extraction reproduces: the same-vendor arm is not shown to differ from the cross-vendor one
on recall at all, so there is no sign to be opposite, and the substrate-dependence claim is
withdrawn rather than restated.

**And it is bought, again, by flagging more of everything.** On C the same-vendor arm's
false-positive rate is **66.0% [57.1, 74.5]**, Wilson [58.1, 73.1], against the cross-vendor
arm's **53.3% [44.2, 62.3]**: **+12.7 points [1.4, 23.7]** (39 vs 20 discordant;
McNemar p = 0.01834; sign-flip p = 0.03709). The same-vendor arm pays **1.85 false-positive
points for every recall point** it gains over the cross-vendor arm — it costs more than it
gains.

**The same-vendor arm barely moves with more readings, and the first voided run overstated
that into "not at all".** It splits its verdict across the eight draws on **22 of 252**
instances, where the cross-vendor arm splits on **102**. Its recall runs 79.2% [68.8, 88.5]
at one reading to 81.4% [71.0, 90.4] at eight; its false-positive rate 59.9% [51.0, 68.6] to
66.0% [57.1, 74.5]. So the curve is nearly flat, not flat.

**This is the finding the correction changed most, and it must be said plainly.** The first
voided run reported that this arm's flag was identical on all eight draws for *every one* of
its 250 instances — zero splits — and that "identical verdict everywhere" became the
empirical illustration behind a caution this programme drew about union-of-K. **It does not
survive.** That run split on 0 of 250, the second on 12 of 249, and this one on 22 of 252.
The models in the first run were reading visible-test text that did not parse (Amendment 1);
with it corrected, the arm is merely near-deterministic rather than deterministic.

Those comparisons are descriptive and post hoc under Amendment 2 — one run against another —
so no interval and no p value attaches to them, they are not an estimate of what unparseable
tests do to an auditor, and **they do not retroactively validate either voided run**, whose
defect was that its input was not what the study said it was. Every flag in both families
came from the model; the deterministic checks layer flagged nothing.

Two consequences follow, and they are reported rather than smoothed:

* **Ceiling 1's registered gain ratio is computable for this arm, and it is poor.** It
  divides the recall gained over one reading by the false positives gained over one reading,
  and runs **0.66** at K = 2 down to **0.36** at K = 8 — every extra reading of this arm buys
  roughly three false-positive points per recall point. The post-hoc level ratio runs
  **1.32 [1.08, 1.61]** at K = 1 down to **1.23** [1.03, 1.48] at K = 8, below the
  cross-vendor arm's 1.54 → 1.40 on this substrate at every K, and below substrate 1's
  2.37 → 1.88. The same-vendor arm is still the worst exchange measured anywhere in this
  programme.

  **The first voided run could not compute this ratio at all**, because the arm never split
  and the denominator was exactly zero. That it is computable is one of the five reversals
  the clean extraction reproduces.
* **Unioning readings buys this arm very little.** Ceiling 1's flattening bar is met on
  substrate 2 for this family — its last step on P gains 0.00 points [0.00, 0.00] — but from
  a curve that barely rises: on P it runs
  79.2% [68.8, 88.5] at one reading to 81.4% [71.0, 90.4] at eight, and on C 59.9%
  [51.0, 68.6] to 66.0% [57.1, 74.5]. Meeting a flattening bar from a curve that barely rises
  is not the same event as saturating, and it is not read as one here.

### Table 7 — the same-vendor arm beside the cross-vendor arm, substrate 2
<!-- BEGIN T7 (records/substrate2/tables.md) -->
The same-vendor arm is `claude-haiku-4-5`, the generator's own model, over the same 102 P and 150 C instances at the same K = 8. Its flag splits across draws on 22 of 252 instances (Table 3), so ceiling 1's registered gain ratio is computable here: it runs 0.66 at K = 2 down to 0.36 at K = 8. The post-hoc level ratio is 1.32 [1.08, 1.61] at K = 1 and 1.23 [1.03, 1.48] at K = 8.

| K | `self` recall on P [95% cluster CI] | `self` FP on C [95% cluster CI] | `self` level ratio | `cross` recall on P | `cross` FP on C | `cross` level ratio |
|---:|---|---|---:|---:|---:|---:|
| 1 | 79.2% [68.8, 88.5] | 59.9% [51.0, 68.6] | 1.32 | 50.5% | 32.8% | 1.54 |
| 2 | 80.7% [70.5, 89.8] | 62.2% [53.4, 70.8] | 1.30 | 59.7% | 40.4% | 1.48 |
| 3 | 81.2% [70.9, 90.2] | 63.7% [54.9, 72.2] | 1.28 | 64.3% | 44.6% | 1.44 |
| 4 | 81.3% [71.0, 90.4] | 64.6% [55.7, 73.0] | 1.26 | 67.4% | 47.3% | 1.42 |
| 5 | 81.4% [71.0, 90.4] | 65.2% [56.4, 73.7] | 1.25 | 69.6% | 49.3% | 1.41 |
| 6 | 81.4% [71.0, 90.4] | 65.6% [56.7, 74.1] | 1.24 | 71.5% | 50.8% | 1.41 |
| 7 | 81.4% [71.0, 90.4] | 65.8% [57.0, 74.4] | 1.24 | 73.0% | 52.2% | 1.40 |
| 8 | 81.4% [71.0, 90.4] | 66.0% [57.1, 74.5] | 1.23 | 74.5% | 53.3% | 1.40 |

Last-step gain on P 0.00 points, on C 0.17 points. Both meet ceiling 1's bar, but from a curve that barely rises, which is a weaker event than saturating and is not read as one; the exponential fit is not quoted for this family.
<!-- END T7 -->
### Table 8 — H23d, same-vendor minus cross-vendor at K = 8, paired
<!-- BEGIN T8 (records/substrate2/tables.md) -->
Paired: the same instances are read by both arms, so this is ceiling 1's paired contrast, computed by `report_ceiling3.paired_union_difference` unchanged under seed 20260917. The cluster bootstrap is the primary interval; Tango and the grid-unconditional interval ignore clustering and are labelled so; the sign-flip test is ceiling 1's frozen implementation and carries its own seed. `a vs b` counts instances only one arm flagged.

| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |
|---|---:|---:|---|---:|---:|---:|---|---|
| P (recall) | 81.4% | 74.5% | **+6.9** [-4.9, 18.6] | 16 vs 9 | 0.22952 | 0.34174 | [-2.9, 16.8] | [-6.3, 19.3] |
| C (false positives) | 66.0% | 53.3% | **+12.7** [1.4, 23.7] | 39 vs 20 | 0.01834 | 0.03709 | [2.7, 22.5] | [0.7, 24.0] |

Substrate 1's frozen comparator is -12.7 points [-25.0, -0.9] on P. The sign here is **the opposite**. The same-vendor arm buys 6.9 points of recall and pays 12.7 points of false positives for it — 1.85 false-positive points per recall point, so it costs **more than it gains**.
<!-- END T8 -->

## 6. H23e — not run

**The residual has not been classified under study 21's rubric on this substrate.** H23e
asked whether the P instances no draw flagged are still dominated by failures the prose does
not determine, on a substrate whose specifications are nearly three times longer. That is
the question this study most obviously leaves open, and running it is the obvious next step.
The residual it would be run on is the **26 of 102** P instances that no `cross` draw
flagged. Until it is run, claim 4 of the paper's ledger is neither confirmed nor narrowed by
this study.

## 7. What this does and does not establish

**The measured ceiling is an operating point, not a constant.** A union-recall figure quoted
without the false-positive rate it was paid for is not a portable number. Ceiling 1's 30.0%
[20.0, 40.7] and this study's 74.5% [63.8, 84.5] are the same auditor under the same
protocol at 16.0% [10.1, 22.3] and 53.3% [44.2, 62.3] false positives respectively; recall
moved 44.5 points [29.5, 58.7] and the false-positive rate moved 37.3 points [26.5, 48.1]
with it.

**Both auditors tell the same story on this substrate.** The cross-vendor arm reaches
74.5% [63.8, 84.5] recall at 53.3% [44.2, 62.3] false positives; the same-vendor arm
reaches 81.4% [71.0, 90.4] at 66.0% [57.1, 74.5]. Higher recall, higher price, a worse
exchange each time — and for the same-vendor arm the exchange is the worst measured anywhere
in this programme, 0.66 down to 0.36 in ceiling 1's registered form, because reading the code
eight times tells it very little that reading it once did not. Whether the generator's own
model sees more or less of its own defects than a stranger does is **not** settled here: the
H23d interval on P spans zero, so no sign is established and none is claimed.

**Nothing here says which substrate is more representative of real code**, and nothing here
ranks the two. Substrate 2 is BigCodeBench's stdlib half — the tasks whose declared modules
are importable in this project's interpreter — which excludes the scientific stack entirely.
Substrate 1 is short functions. Neither was selected on any audit outcome; neither was chosen
to resemble any particular production codebase.

**What carries over from ceiling 1 is the shape, not the level.** Reading the same code more
times shows diminishing returns on both substrates, and **on neither does the curve flatten by
the registered bar**: substrate 1 gains 1.93 points [1.14, 2.78] at the last step and this one
gains 1.52 [0.62, 2.60], both above the 1.0-point bar. The voided run recorded 0.62 points here
and reported the bar as met; that was the one curve in this programme that appeared to saturate,
and it does not. What does not carry over is the level of either curve, or the distance between
them.

**The non-overlap claim holds for one family on this run and fails pooled, and it has not
held still across runs.** "No reading count puts the two substrates at the same
false-positive rate" is true here of the cross-vendor family, where 16.0% [10.1, 22.3] and
32.8% [25.5, 40.2] do not meet. Pooled it fails, as it has on every run: substrate 1's
same-vendor family at K = 8 is 24.0% [17.2, 31.2] against that same 32.8% [25.5, 40.2].
Quoted without its family the claim is an overstatement, and §8 records that an earlier
version of this report made it that way. Quoted with its family it is still the one finding
of the six that the three extractions did not agree on, so it is reported and not relied
upon.

**Limits.** One generator, one auditor route, one flag rule ("at least one BLOCKER"), K = 8.
The 100 P instances come from 51 problems and the 150 C instances from 121, which is why
every interval here is a problem-cluster bootstrap and why the Wilson intervals beside them
are too narrow. The two substrates differ in more than task length — corpus, authorship,
test style and suite size all move together — so "length" is a label for the contrast, not
an isolated variable.

## 8. Deviations from the preregistration, and interruptions

**An unstable route, and what it did not change.** This run met no rate limiting at all: not one denial row carries HTTP 429, `insufficient_quota`, 401 or 403. What it met was a local proxy that dropped connections — SSL `UNEXPECTED_EOF` and `RemoteDisconnected` — whose failures tripped the driver's circuit breaker and blocked far more calls than they caused: **6237** recorded provider denials across the eight cross-vendor draws, and every draw still landed its 252 readings. A denied call lands no reading and is not billed, so the denials cost wall clock and nothing else. They are not evenly spread — draws 1 to 3 met none and draws 6 to 8 met 5,775 between them — so any comparison of per-draw timing across runs is not like for like.

* **The frame is 300 tasks, not the 289 the preregistration names.** §1 recorded 326 tasks
  passing filter S1 and 289 of those passing S2, measured before that file was written. In
  the frozen environment at generation time 326 still passed S1, but only **26** failed S2
  rather than 37, leaving **300**. The filters, the seed and the split rule are exactly as
  registered; the count moved because the environment's own module inventory did. All 840
  drops are recorded with their filter and reason in `records/substrate2/frame.json`.
* **H23c's registered comparator is 1.68, not 1.88.** The preregistration writes "substrate
  1's 16.0% and 1.68" — that rate is 16.0% [10.1, 22.3]. 1.68 is ceiling 1's
  registered gain ratio, reproduced here from
  `records/ceiling/numbers.json` (1.6798). The value 1.88 is the **level** ratio, a
  different quantity; it appears in §4 and Table 6 and is labelled post hoc everywhere.
* **The run was interrupted by the route, not by a budget or a quota.** Draws were taken
  **hours apart** rather than back to back: the first invocation left the cross-vendor draws
  5 to 8 short when the proxy degraded, and a supervised process finished them afterwards
  against the cache. Every reading is cached by (kind, route, draw, instance) and none was
  bought twice, so the interruptions cost time and not data. The denials are concentrated at
  the end of each ladder: **85 to 1,008** provider denials per `self` draw, and 0, 0, 0, 180,
  282, 1,451, 2,242 and 2,082 across the eight `cross` draws in order.
* **Both ladders were complete before this report was first written.** Unlike the report on
  the voided re-run, no version of this document was written against a partly filled arm, so
  H23d is answered as registered here rather than deferred and later added, and **every draw
  now covers all 252**.
* **The same-vendor arm's eight draws are near-deterministic, not identical.** Its flag is
  the same across all eight draws on 230 of 252 instances and splits on **22**, so K has a
  small effect on it and ceiling 1's registered gain ratio is computable, at 0.66 down to
  0.36 (§5). The first voided run found no splits at all and reported the ratio as
  undefined; that is one of the five reversals this run reproduces. The preregistration
  assumed the union-of-K machinery would apply to both families; for this one it nearly
  degenerates. That is reported as a result, not worked around.
* **The audit set was frozen to disk before the first audit call, and carries the generation
  it was drawn from.** §2 asks that it be frozen and committed. Its provenance is checkable
  without trusting the commit order: redrawing it from the committed `instances.jsonl` with
  the registered seed 20260917 reproduces all 252 ids exactly, and a test asserts that. It
  also records the generation digest it was drawn from, and a scope drawn from a different
  generation is refused rather than reused — the guard Amendment 3 added after the first
  re-run audited a scope frozen from a superseded generation.
* **A short ladder can no longer be reported as a curve.** The union curve reads a draw's
  flag with `.get`, so an instance never read in a draw counts exactly like one the auditor
  read and passed: a short ladder understates recall at high K, shrinks the last step, and
  makes the flattening bar easier to meet. The report now halts unless every draw of every
  family covers the full scope. This run's cross-vendor arm was short by 45, 128, 205 and 189
  readings when the proxy degraded, and was finished rather than reported short.
* **An earlier version of this report overstated the matched-false-positive claim, and a
  figure review caught it.** It asserted that the two substrates' false-positive ranges do
  not overlap "at any K", naming no auditor family. That rests on the **point estimates**.
  Once the intervals are admitted and both families are pooled it is false: substrate 1's
  same-vendor family at K = 8 is 24.0% [17.2, 31.2] and substrate 2's cheapest cross-vendor
  reading is 32.8% [25.5, 40.2], and those two intervals overlap. The claim is made only for
  the cross-vendor family — 16.0% [10.1, 22.3] against 32.8% [25.5, 40.2], which do not
  meet — and the pooled overlap is stated beside it in §4, §7 and Table 6. Every separation
  and overlap quoted in this report is a distance between quoted intervals, not an estimate
  carrying an interval of its own. What that review changed is the scope the sentence
  claims, and it is kept: this run separates the cross-vendor intervals and overlaps the
  pooled ones, exactly the pattern the narrower claim was written for.
* **H23e was not run** (§6). It is in the preregistration and it is not in this report.

## 9. The comparison inventory

Primary: **H23a**. Everything else is secondary; no correction is applied to the
secondaries, and none is claimed to clear a corrected threshold. The inventory is also in
`records/substrate2/numbers.json` under `comparison_inventory`:

1. H23a (primary) — union recall at K = 8 on P, substrate 2 minus substrate 1.
2. H23c — union false positives at K = 8 on C, substrate 2 minus substrate 1.
3. H23c — recall bought per false-positive point, registered gain ratio, both substrates.
4. H23c — recall bought per false-positive point, post-hoc level ratio, both substrates.
5. H23b — the union curve at K = 1..8 on P and on C, with per-K cluster intervals.
6. H23b — the constrained fit and ceiling 1's flattening bar, on P and on C.
7. H23d — same-vendor minus cross-vendor union recall at K = 8 on P, paired.
8. H23d — same-vendor minus cross-vendor union false positives at K = 8 on C, paired.
9. H23d — the same-vendor arm's own curve, fit and exchange ratios on P and on C.

Every interval in this report is a 10,000-resample percentile bootstrap over **problem
clusters** at seed 20260917, except the Wilson score intervals, which are named as such
wherever they appear and which assume instances are independent, and the cluster sign-flip
test in §5, which is ceiling 1's frozen implementation and carries its own seed. Substrate
1's figures are read unmodified from `records/ceiling/numbers.json`; recomputing its curve
from its own records reproduces 30.0% [20.0, 40.7] and 16.0% [10.1, 22.3] exactly.

## 10. Cost

### Table 9 — cost, from the run's usage ledgers
<!-- BEGIN T9 (records/substrate2/tables.md) -->
Summed from the per-project `usage.jsonl` ledgers in the run archive as of 2026-09-18T16:57:09Z. Refused calls that never reached a model are not in the ledgers and cost nothing.

| | calls | USD |
|---|---:|---:|
| generation (`claude-haiku-4-5`) | 600 | $1.91 |
| audit, `cross` (`openai:gpt-5.6-terra`), 8 draws | 2,016 | $19.44 |
| audit, `self` (`claude-haiku-4-5`), 8 draws | 2,034 | $8.22 |
| **audit total** | **4,050** | **$27.66** |
| **study total** | **4,650** | **$29.57** (cap $60) |
<!-- END T9 -->
