# Study 23 — the measured ceiling is an operating point, not a constant

> **Third version.** Preregistered at `benchmarks/code/substrate2/PREREGISTRATION.md`,
> committed before any model call of this study. Ceiling 1's protocol was repeated
> unchanged on a second substrate. The **second version** answered H23d as registered: the
> first was written while the same-vendor ladder was still filling and reported H23d as not
> evaluable, and the run completed afterwards. The **third** narrowed the
> matched-false-positive claim to the cross-vendor family after a figure review found that
> the unscoped form rested on point estimates and fails once every family and its interval
> is admitted (§8). **No point estimate has changed across any version.** **H23e was not
> run** (§6). No cross-vendor review has read this, so nothing here is approved for
> quotation.

## The sentence the preregistration requires

Section 4 fixed, before the first reading, what had to be written if substrate 2's recall
came out higher. It did.

> **The paper's central quantity is substrate-dependent. Union recall of 30.0%
> [20.0, 40.7] at eight readings is not a general figure: it is what the shipped
> cross-vendor auditor reaches on HumanEval+/MBPP+-shaped tasks, and the same auditor under
> the same protocol reaches 71.0% [59.2, 82.2] on BigCodeBench's stdlib half.**

That sentence is true and it is not the finding. The auditor is not *better* on the harder
substrate. It is **louder**: it flags more of everything, its recall per false-positive
point is lower at every reading count, and on correct code it flags so much more that
**within the cross-vendor family** — the comparison this study draws — no reading count on
either substrate puts the two at the same false-positive rate. Pooling in the same-vendor
family the intervals do meet, narrowly; §4 gives both answers. §7 says what that leaves
standing.

## 1. What was run

Ceiling 1's measurement, unchanged, on a substrate whose median task is **118
specification words and 41 reference-solution lines** against substrate 1's 41 and 6 — 2.88
times the prose and 6.83 times the code (Table 1). The frame is 300 BigCodeBench tasks that
pass two mechanical filters in this project's interpreter; the visible/hidden suite split is
seeded and mechanical, with hidden ⊇ visible.

`claude-haiku-4-5` generated 600 candidates over two batches for **$1.83**, giving strata
**P 100, C 462, F 38** (Table 2). The whole P population and a seeded sample of 150 C
instances — 250 instances — were frozen into `records/substrate2/audit_set.json` before the
first audit call. The shipped cross-vendor auditor (`openai:gpt-5.6-terra`), holistic, the
shipped constitution unmodified, then read every one of them **eight** times, and the
same-vendor auditor (`claude-haiku-4-5`, the generator's own model) read all 250 eight
times after it. **Both ladders are complete**: every draw of both families covers all 250
instances (Table 3). Audit spend was **$26.41** of a $60 cap (Table 9).

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
| stratum P (passes visible, fails hidden) | **100** |
| stratum C (passes both) | 462 |
| stratum F (fails visible) | 38 |
| P instances audited | 100 (cap 200; the whole population, no draw needed) |
| C instances audited | 150 (cap 150) |
| generation cost | $1.83 (600 calls) |
<!-- END T2 -->
### Table 3 — the audit ladder's coverage
<!-- BEGIN T3 (records/substrate2/tables.md) -->
The frozen audit set is 250 instances (100 P, 150 C). Both ladders are complete: every draw of both families covers all 250. A denial is a call that never produced a reading; it is not in the usage ledger and cost nothing. The last column is what the `self` ladder had reached at 2026-09-11T10:18:26Z, when the first version of this report was written and H23d was not yet evaluable.

| draw | `cross` readings | `cross` denials | `self` readings | `self` denials | `self` readings at the first read |
|---:|---:|---:|---:|---:|---:|
| 1 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 2,087 | 250 |
| 2 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,340 | 228 |
| 3 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,438 | 24 |
| 4 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,425 | 31 |
| 5 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,428 | 23 |
| 6 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,353 | 38 |
| 7 | 250 / 250 ✓ | 0 | 250 / 250 ✓ | 1,291 | 60 |
| 8 | 250 / 250 ✓ | 999 | 250 / 250 ✓ | 1,290 | 82 |

**Draw-to-draw agreement.** Over the 250 audited instances, the cross-vendor arm's flag splits across its eight draws on **103** of them; the same-vendor arm's splits on **0**. Every flag in both families came from the model (0 readings were flagged by the deterministic checks layer). The same-vendor arm returned one identical set of finding digests across all eight draws on 219 instances, the cross-vendor arm on 96; no finding text was archived or read.
<!-- END T3 -->

## 2. H23a (primary) — recall is far higher on the harder substrate

Unioning eight independent readings flags **71 of 100** stratum-P instances: **71.0%, 95%
problem-cluster bootstrap [59.2, 82.2]**, Wilson [61.5, 79.0] beside it. Substrate 1's
frozen comparator is 33 of 110 — **30.0% [20.0, 40.7]**, Wilson [22.2, 39.1].

The difference is **+41.0 points, 95% two-sample problem-cluster bootstrap [24.8, 56.1]**
(10,000 resamples, seed 20260917). The two populations share no instance and no problem, so
each population's problems were resampled independently within one seed stream and the
difference of the two resampled rates taken. **This contrast is not paired**, and no
McNemar test and no sign-flip test is reported for it. The interval excludes zero and the
sign is the one §4 said would oblige the sentence above.

The preregistration fixed no direction here and said both directions were interesting. This
is the direction that costs the paper a headline.

## 3. H23b — the union curve, the fit and the flattening bar

Recall on P runs from **49.5% [38.5, 60.4]** at one reading to **71.0% [59.2, 82.2]** at
eight, with every point's cluster interval in Table 4. The constrained exponential fit gives
an asymptote of **68.6% [57.1, 79.9]** with tau = 0.88 and r² = 0.905 — the fitted asymptote
sits *below* the raw union at K = 8, which is what a curve this flat at the end does to a
one-parameter exponential, and it is the raw union that is quoted.

Ceiling 1's registered flattening bar is a last-step gain of at most 1.0 point. On P the
gain from seven readings to eight is **0.62 points [0.13, 1.23]**: **the bar is met**. On
substrate 1 the same auditor gained 1.93 points [1.14, 2.78] at the same step and the bar
was not met. Saturation here is not an artefact of the fit: 26 of the 100 P instances were
flagged by all eight readings and 29 by none, so most of the population is decided long
before the eighth reading.

The false-positive curve has **not** flattened. Its last step on C gains **1.33 points
[0.69, 2.06]**, so C's fitted asymptote of 52.8% [44.2, 61.5] is an extrapolation and the
raw **55.3% [46.3, 64.2]** is the number to quote.

### Table 4 — union recall and union false positives at every K, substrate 2
<!-- BEGIN T4 (records/substrate2/tables.md) -->
Unit of analysis: the instance. n = 100 stratum-P instances from 51 problems (recall) and 150 stratum-C instances from 121 problems (false positives), the same instances at every K. The union rate at K is averaged over all C(8, K) subsets of the eight draws, exactly. Intervals are 10,000-resample problem-cluster percentile bootstraps, seed 20260917. The **registered** gain ratio is ceiling 1's own column — recall gained over K = 1 divided by false positives gained over K = 1. The **level** ratio is recall at K divided by the false-positive rate paid at K; it is post hoc and is not in the preregistration.

| K | union recall on P [95% cluster CI] | union FP on C [95% cluster CI] | recall per FP point, registered gain ratio | recall per FP point, POST-HOC level ratio |
|---:|---|---|---:|---:|
| 1 | 49.5% [38.5, 60.4] | 31.8% [24.9, 39.0] | — | 1.55 |
| 2 | 58.9% [47.4, 70.1] | 39.9% [32.2, 47.6] | 1.16 | 1.48 |
| 3 | 63.5% [51.6, 74.9] | 44.8% [36.6, 52.9] | 1.08 | 1.42 |
| 4 | 66.4% [54.4, 77.8] | 48.2% [39.7, 56.5] | 1.03 | 1.38 |
| 5 | 68.2% [56.3, 79.7] | 50.6% [42.0, 59.1] | 1.00 | 1.35 |
| 6 | 69.5% [57.6, 80.9] | 52.5% [43.7, 61.1] | 0.97 | 1.33 |
| 7 | 70.4% [58.5, 81.7] | 54.0% [45.1, 62.8] | 0.94 | 1.30 |
| 8 | 71.0% [59.2, 82.2] | 55.3% [46.3, 64.2] | 0.91 | 1.28 |

Fit on P: A = 68.6% [57.1, 79.9], tau = 0.88, r² = 0.905. Last-step gain 0.62 points [0.13, 1.23] — ceiling 1's flattening bar (≤ 1.0 point) is **met**.
Fit on C: A = 52.8% [44.2, 61.5], tau = 1.32, r² = 0.917. Last-step gain 1.33 points [0.69, 2.06] — the bar is **not met**.
<!-- END T4 -->
### Table 5 — substrate 2 against substrate 1 at K = 8
<!-- BEGIN T5 (records/substrate2/tables.md) -->
The two populations share no instance and no problem, so this is a **two-sample** bootstrap: each population's problems are resampled independently and the difference of the two resampled rates is taken. Nothing here is paired, so no McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and assumes instances are independent, which within a substrate they are not.

| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |
|---|---|---|---|
| **H23a (primary)** union recall, P, K = 8 | **71.0%** (71/100, 51 problems) Wilson [61.5, 79.0] | 30.0% (33/110, 56 problems) Wilson [22.2, 39.1] | **+41.0 points** [24.8, 56.1] |
| **H23c** union false positives, C, K = 8 | **55.3%** (83/150, 121 problems) Wilson [47.3, 63.1] | 16.0% (24/150, 143 problems) Wilson [11.0, 22.7] | **+39.3 points** [28.2, 50.2] |
<!-- END T5 -->

## 4. H23c — the auditor is not better here, it is louder

Eight readings flag **83 of 150** correct solutions: **55.3% [46.3, 64.2]**, Wilson
[47.3, 63.1], against substrate 1's frozen **16.0% [10.1, 22.3]**. That is **+39.3 points
[28.2, 50.2]** on the same two-sample bootstrap — almost exactly the recall difference.

So the recall bought per false-positive point is **lower on substrate 2 at every K**, under
both definitions of that quantity:

* **Ceiling 1's registered gain ratio**, which is the comparator H23c names: recall gained
  over one reading divided by false positives gained over one reading. Substrate 1 runs 1.67
  down to **1.68**; substrate 2 runs 1.16 down to **0.91**. From K = 6 on, each extra
  reading of substrate 2 buys less recall than it buys false positives.
* **The level ratio** — recall at K divided by the false-positive rate actually paid at K.
  This is **post hoc**: it is not in the preregistration, and it is reported because it is
  the form a reader can weigh against a fixed operating cost. Substrate 1 runs 2.37 down to
  1.88; substrate 2 runs **1.55 [1.12, 2.12]** down to **1.28 [1.01, 1.61]**.

**The honest limit on this comparison, stated for a named family.** Substrate 2's
*single* cross-vendor reading already costs **31.8% [24.9, 39.0]** false positives, above
substrate 1's *eight*-reading cross-vendor **16.0% [10.1, 22.3]**; those two intervals do
not meet, and 2.6 points separate them. **Within the cross-vendor family there is
therefore no K at which the two substrates can be compared at a matched false-positive
rate**, which is the comparison that matters here, because substrate 1's frozen comparator
and substrate 2's primary are both the shipped cross-vendor auditor.

**Pooled across families the claim does not survive, and it is stated rather than left to
be found.** Substrate 1's dearest reading anywhere is its same-vendor family at K = 8,
**24.0% [17.2, 31.2]**, whose upper bound reaches **6.3 points** into substrate 2's
cheapest interval of [24.9, 39.0]. The point estimates are still disjoint (24.0% [17.2,
31.2] against 31.8% [24.9, 39.0]), but a matched false-positive rate **cannot be ruled
out** once every family and its uncertainty are admitted. Table 6 carries both answers.

Either way, every recall comparison in this report — H23a's +41.0 points [24.8, 56.1]
included — compares two different operating points, not two detection abilities. Bringing
the cross-vendor rates onto common ground would take readings this study did not buy: a
stricter flag rule, or a different auditor, on substrate 2.

### Table 6 — recall bought per false-positive point, both substrates
<!-- BEGIN T6 (records/substrate2/tables.md) -->
The level ratio is POST HOC — the preregistration's H23c names ceiling 1's registered gain ratio, whose values are in Table 4. Both definitions point the same way; the level ratio is shown here because it is the one that can be read against a fixed operating cost.

| K | substrate 1 recall | substrate 1 FP | substrate 1 level ratio | substrate 2 recall | substrate 2 FP | substrate 2 level ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.7% | 4.5% | 2.37 | 49.5% | 31.8% | 1.55 |
| 2 | 15.0% | 7.1% | 2.12 | 58.9% | 39.9% | 1.48 |
| 3 | 18.3% | 9.2% | 2.00 | 63.5% | 44.8% | 1.42 |
| 4 | 21.2% | 10.9% | 1.94 | 66.4% | 48.2% | 1.38 |
| 5 | 23.8% | 12.4% | 1.91 | 68.2% | 50.6% | 1.35 |
| 6 | 26.0% | 13.7% | 1.89 | 69.5% | 52.5% | 1.33 |
| 7 | 28.1% | 14.9% | 1.88 | 70.4% | 54.0% | 1.30 |
| 8 | 30.0% | 16.0% | 1.88 | 71.0% | 55.3% | 1.28 |

Substrate 2's level ratio is lower than substrate 1's at **every** K, and so is the registered gain ratio (**every** K).

**Can any reading count put the two substrates at the same false-positive rate?** The answer depends on which auditor families are admitted, so it is given twice.

**Within the cross-vendor family** — the comparison this study draws, since substrate 1's frozen comparator and substrate 2's primary are both the shipped cross-vendor auditor — **no**. Substrate 2's cheapest reading costs 31.8% [24.9, 39.0] at K = 1, and substrate 1's dearest costs 16.0% [10.1, 22.3] at K = 8. Those intervals do not meet: 2.6 points separate them.

**Pooling every family measured on either substrate** — **yes, narrowly**. Substrate 1's dearest reading anywhere is its `self` family at K = 8, 24.0% [17.2, 31.2], and its upper bound reaches 6.3 points into substrate 2's cheapest interval of [24.9, 39.0]. The point estimates are still disjoint (24.0% against 31.8%), but the intervals overlap, so a matched false-positive rate cannot be ruled out pooled. Substrate 1's interval here is the one ceiling 1's own Table 1 quotes; its second bootstrap stream for the same point gives an overlap of 6.4 points instead.
<!-- END T6 -->

## 5. H23d — the same-vendor arm flags more of everything, and the sign flips

**H23d is answered as registered**, paired at K = 8 over the whole frozen audit set, by
`report_ceiling3.paired_union_difference` unchanged under seed 20260917.

On P the same-vendor arm's union recall is **88.0% [78.0, 96.0]**, Wilson [80.2, 93.0],
against the cross-vendor arm's **71.0% [59.2, 82.2]** on the same 100 instances:
**+17.0 points, problem-cluster [2.0, 32.0]** (26 instances flagged only by `self`, 9 only
by `cross`; exact McNemar p = 0.00599; cluster sign-flip p = 0.04210; Tango [5.7, 28.2] and
grid-unconditional [2.0, 30.5] beside it, both ignoring clustering).

**The sign is the opposite of substrate 1's.** Ceiling 1 measured −12.7 points
[−25.0, −0.9] for the same contrast — the generator's own model saw *less* of its own
defects than a stranger did. Here it sees more. Both intervals exclude zero and they point
opposite ways, so the direction of the same-vendor effect is substrate-dependent too.

**And it is bought, again, by flagging more of everything.** On C the same-vendor arm's
false-positive rate is **77.3% [69.3, 84.9]**, Wilson [70.0, 83.3], against the
cross-vendor arm's **55.3% [46.3, 64.2]**: **+22.0 points [11.2, 32.7]** (46 vs 13
discordant; McNemar p = 0.00002; sign-flip p = 0.00015). The same-vendor arm pays
**1.29 false-positive points for every recall point** it gains over the cross-vendor arm —
it costs more than it gains.

**The same-vendor arm has no saturation curve at all.** Its flag is identical on all eight
draws for **every one of the 250 instances**: not a single instance splits, where the
cross-vendor arm splits on **103** of 250 (Table 3). Its recall is 88.0% [78.0, 96.0] at
one reading and 88.0% [78.0, 96.0] at eight, and its false-positive rate 77.3%
[69.3, 84.9] at both. This is not a caching artefact: the eight draws are eight separate
calls with distinct run ids, wall times and costs, and the arm returned differing finding
digests across draws on 31 of the 250 instances. What does not move is the BLOCKER
*decision*. Every flag in both families came from the model; the deterministic checks layer
flagged nothing.

Two consequences follow, and they are reported rather than smoothed:

* **Ceiling 1's registered gain ratio is undefined for this arm.** It divides the recall
  gained over one reading by the false positives gained over one reading, and for the
  same-vendor arm that denominator is exactly zero. Only the post-hoc level ratio can be
  quoted: a flat **1.14 [0.98, 1.31]** at every K, below the cross-vendor arm's 1.55
  [1.12, 2.12] → 1.28 [1.01, 1.61] on this substrate at every K, and below substrate 1's
  2.37 → 1.88 at every K. The same-vendor arm is the worst exchange measured anywhere in
  this programme.
* **Unioning readings buys this arm nothing.** Ceiling 1's flattening bar is met on both
  strata with a last-step gain of 0.00 points [0.00, 0.00] — every resample gives exactly
  zero because no instance splits — but by arithmetic and not by saturation: a curve that
  never rises has nowhere to flatten from. The exponential fit is not quoted for
  this family.

### Table 7 — the same-vendor arm beside the cross-vendor arm, substrate 2
<!-- BEGIN T7 (records/substrate2/tables.md) -->
The same-vendor arm is `claude-haiku-4-5`, the generator's own model, over the same 100 P and 150 C instances at the same K = 8. Its curve does not move with K because its flag does not split across draws (Table 3), so **ceiling 1's registered gain ratio is undefined for it**: that ratio divides by the false-positive gain from K = 1, and that gain is exactly zero. Only the post-hoc level ratio can be quoted, and it is 1.14 [0.98, 1.31] at K = 1 and 1.14 [0.98, 1.31] at K = 8.

| K | `self` recall on P [95% cluster CI] | `self` FP on C [95% cluster CI] | `self` level ratio | `cross` recall on P | `cross` FP on C | `cross` level ratio |
|---:|---|---|---:|---:|---:|---:|
| 1 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 49.5% | 31.8% | 1.55 |
| 2 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 58.9% | 39.9% | 1.48 |
| 3 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 63.5% | 44.8% | 1.42 |
| 4 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 66.4% | 48.2% | 1.38 |
| 5 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 68.2% | 50.6% | 1.35 |
| 6 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 69.5% | 52.5% | 1.33 |
| 7 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 70.4% | 54.0% | 1.30 |
| 8 | 88.0% [78.0, 96.0] | 77.3% [69.3, 84.9] | 1.14 | 71.0% | 55.3% | 1.28 |

Last-step gain on P 0.00 points, on C 0.00 points. Both meet ceiling 1's bar trivially: a curve that never rises has flattened by arithmetic, not by saturation, and the exponential fit is not quoted for this family.
<!-- END T7 -->
### Table 8 — H23d, same-vendor minus cross-vendor at K = 8, paired
<!-- BEGIN T8 (records/substrate2/tables.md) -->
Paired: the same instances are read by both arms, so this is ceiling 1's paired contrast, computed by `report_ceiling3.paired_union_difference` unchanged under seed 20260917. The cluster bootstrap is the primary interval; Tango and the grid-unconditional interval ignore clustering and are labelled so; the sign-flip test is ceiling 1's frozen implementation and carries its own seed. `a vs b` counts instances only one arm flagged.

| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |
|---|---:|---:|---|---:|---:|---:|---|---|
| P (recall) | 88.0% | 71.0% | **+17.0** [2.0, 32.0] | 26 vs 9 | 0.00599 | 0.04210 | [5.7, 28.2] | [2.0, 30.5] |
| C (false positives) | 77.3% | 55.3% | **+22.0** [11.2, 32.7] | 46 vs 13 | 0.00002 | 0.00015 | [12.4, 31.4] | [10.0, 33.0] |

Substrate 1's frozen comparator is -12.7 points [-25.0, -0.9] on P. The sign here is **the opposite**. The same-vendor arm buys 17.0 points of recall and pays 22.0 points of false positives for it — 1.29 false-positive points per recall point, so it costs **more than it gains**.
<!-- END T8 -->

## 6. H23e — not run

**The residual has not been classified under study 21's rubric on this substrate.** H23e
asked whether the P instances no draw flagged are still dominated by failures the prose does
not determine, on a substrate whose specifications are nearly three times longer. That is
the question this study most obviously leaves open, and running it is the obvious next step.
The residual it would be run on is the **29 of 100** P instances that no `cross` draw
flagged. Until it is run, claim 4 of the paper's ledger is neither confirmed nor narrowed by
this study.

## 7. What this does and does not establish

**The measured ceiling is an operating point, not a constant.** A union-recall figure quoted
without the false-positive rate it was paid for is not a portable number. Ceiling 1's 30.0%
[20.0, 40.7] and this study's 71.0% [59.2, 82.2] are the same auditor under the same
protocol at 16.0% [10.1, 22.3] and 55.3% [46.3, 64.2] false positives respectively; recall
moved 41.0 points [24.8, 56.1] and the false-positive rate moved 39.3 points [28.2, 50.2]
with it.

**Both auditors tell the same story on this substrate.** The cross-vendor arm reaches
71.0% [59.2, 82.2] recall at 55.3% [46.3, 64.2] false positives; the same-vendor arm
reaches 88.0% [78.0, 96.0] at 77.3% [69.3, 84.9]. Higher recall, higher price, a worse
exchange each time — and for the same-vendor arm the exchange cannot even be computed in
ceiling 1's registered form, because reading the code eight times tells it nothing that
reading it once did not. Whether the generator's own model sees more or less of its own
defects than a stranger does is substrate-dependent too: the sign of H23d here is the
opposite of substrate 1's.

**Nothing here says which substrate is more representative of real code**, and nothing here
ranks the two. Substrate 2 is BigCodeBench's stdlib half — the tasks whose declared modules
are importable in this project's interpreter — which excludes the scientific stack entirely.
Substrate 1 is short functions. Neither was selected on any audit outcome; neither was chosen
to resemble any particular production codebase.

**What carries over from ceiling 1 is the shape, not the level.** Reading the same code more
times saturates on both substrates; on this one it saturates by the eighth reading, where on
substrate 1 it had not. What does not carry over is the level of either curve, or the
distance between them.

**The non-overlap claim is a within-family claim.** "No reading count puts the two
substrates at the same false-positive rate" holds for the cross-vendor family: 16.0%
[10.1, 22.3] against 31.8% [24.9, 39.0], two intervals that do not meet. It does not hold
pooled: substrate 1's same-vendor family at K = 8 is 24.0% [17.2, 31.2] against the same
31.8% [24.9, 39.0], two intervals that do meet. The separation in the first case and the
overlap in the second — 2.6 and 6.3 points — are distances between those quoted intervals,
not estimates with intervals of their own. Quoted without its family the claim is an
overstatement, and §8 records that an earlier version of this report made it that way.

**Limits.** One generator, one auditor route, one flag rule ("at least one BLOCKER"), K = 8.
The 100 P instances come from 51 problems and the 150 C instances from 121, which is why
every interval here is a problem-cluster bootstrap and why the Wilson intervals beside them
are too narrow. The two substrates differ in more than task length — corpus, authorship,
test style and suite size all move together — so "length" is a label for the contrast, not
an isolated variable.

## 8. Deviations from the preregistration, and interruptions

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
* **The run was interrupted twice**: once by an exhausted OpenAI balance during the `cross`
  ladder, and repeatedly by Anthropic rate-limit cooldowns during the `self` ladder. Draws
  were therefore taken **hours apart** rather than back to back. Every reading is cached by
  (kind, route, draw, instance) and none was bought twice, so for `cross` the interruptions
  cost time and not data; the eighth `cross` draw's cache carries **999** recorded provider
  denials before its 250 readings landed, and the seven before it carry none.
* **The `self` ladder was incomplete when the first version of this report was written,
  and completed afterwards.** At 2026-09-11T10:18:26Z its eight draws held 250, 228, 24, 31,
  23, 38, 60 and 82 readings of 250 required (Table 3's last column); H23d was
  reported then as not evaluable. The run filled the ladder over the following hours and
  every draw now covers all 250. The refusals that caused this are recorded: **1,290 to 2,087**
  provider denials per `self` draw, against **999** on the eighth `cross` draw and none on
  the seven before it. Draws were therefore taken **hours apart** rather than back
  to back, and readings within a draw were bought over a long window under repeated
  rate-limit cooldowns. Every reading is cached by (kind, route, draw, instance) and none
  was bought twice. **No point estimate of H23a, H23b or H23c changed when the arm
  completed**; §5 is the only section that changed.
* **The same-vendor arm's eight draws are not independent in their verdicts.** Its flag is
  identical across all eight draws on all 250 instances, so K has no effect on it and
  ceiling 1's registered gain ratio is undefined for it (§5). The preregistration assumed
  the union-of-K machinery would apply to both families; for this one it degenerates. That
  is reported as a result, not worked around.
* **The audit set was frozen to disk before the first audit call but not committed to
  git until this commit.** §2 asks for both. Its provenance is checkable without the
  earlier commit: redrawing it from the committed `instances.jsonl` with the
  registered seed 20260917 reproduces all 250 ids exactly, and a test asserts that.
* **An earlier version of this report overstated the matched-false-positive claim, and a
  figure review caught it.** It asserted that the two substrates' false-positive ranges do
  not overlap "at any K", naming no auditor family. That rests on the **point estimates**.
  Once the intervals are admitted and both families are pooled it is false: substrate 1's
  same-vendor family at K = 8 is 24.0% [17.2, 31.2] and substrate 2's cheapest cross-vendor
  reading is 31.8% [24.9, 39.0], and those two intervals overlap. The claim is now made
  only for the cross-vendor family — 16.0% [10.1, 22.3] against 31.8% [24.9, 39.0], which
  do not meet — and the pooled overlap is stated beside it in §4, §7 and Table 6. The
  6.3-point overlap and the 2.6-point separation are distances between quoted intervals,
  not estimates carrying intervals of their own. No point estimate changed; what changed is
  the scope the sentence claims.
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
Summed from the per-project `usage.jsonl` ledgers in the run archive as of 2026-09-11T11:16:55Z. Refused calls that never reached a model are not in the ledgers and cost nothing.

| | calls | USD |
|---|---:|---:|
| generation (`claude-haiku-4-5`) | 600 | $1.83 |
| audit, `cross` (`openai:gpt-5.6-terra`), 8 draws | 2,000 | $18.31 |
| audit, `self` (`claude-haiku-4-5`), 8 draws | 2,000 | $8.10 |
| **audit total** | **4,000** | **$26.41** |
| **study total** | **4,600** | **$28.23** (cap $60) |
<!-- END T9 -->
