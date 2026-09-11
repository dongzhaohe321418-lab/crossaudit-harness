# Study 23 — the measured ceiling is an operating point, not a constant

> **First version.** Preregistered at `benchmarks/code/substrate2/PREREGISTRATION.md`,
> committed before any model call of this study. Ceiling 1's protocol was repeated
> unchanged on a second substrate. H23a (primary), H23b and H23c are answered. **H23d is
> not evaluable** and **H23e was not run**; both are said so in §5 and §6. No cross-vendor
> review has read this, so nothing here is approved for quotation.

## The sentence the preregistration requires

Section 4 fixed, before the first reading, what had to be written if substrate 2's recall
came out higher. It did.

> **The paper's central quantity is substrate-dependent. Union recall of 30.0%
> [20.0, 40.7] at eight readings is not a general figure: it is what the shipped
> cross-vendor auditor reaches on HumanEval+/MBPP+-shaped tasks, and the same auditor under
> the same protocol reaches 71.0% [59.2, 82.2] on BigCodeBench's stdlib half.**

That sentence is true and it is not the finding. The auditor is not *better* on the harder
substrate. It is **louder**: it flags more of everything, its recall per false-positive
point is lower at every reading count, and on correct code it flags so much more that there
is no K at which the two substrates can be compared at the same false-positive rate. §7 says
what that leaves standing.

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
shipped constitution unmodified, then read every one of them **eight** times: all eight
`cross` draws are complete over the frozen set (Table 3). Audit spend was **$21.34** of a
$60 cap (Table 7).

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
The frozen audit set is 250 instances (100 P, 150 C). Read once at 2026-09-11T10:18:26Z; the `self` cache was still being filled.

| draw | `cross` readings | `self` readings | `self` P missing | `self` C missing |
|---:|---:|---:|---:|---:|
| 1 | 250 / 250 ✓ | 250 / 250 | 0 | 0 |
| 2 | 250 / 250 ✓ | 228 / 250 | 0 | 22 |
| 3 | 250 / 250 ✓ | 24 / 250 | 76 | 150 |
| 4 | 250 / 250 ✓ | 31 / 250 | 69 | 150 |
| 5 | 250 / 250 ✓ | 23 / 250 | 77 | 150 |
| 6 | 250 / 250 ✓ | 38 / 250 | 62 | 150 |
| 7 | 250 / 250 ✓ | 60 / 250 | 40 | 150 |
| 8 | 250 / 250 ✓ | 82 / 250 | 18 | 150 |
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

**The honest limit on this comparison.** Substrate 2's *single* reading already costs
**31.8% [24.9, 39.0]** false positives, which is above substrate 1's *eight*-reading
**16.0% [10.1, 22.3]**. The two measured false-positive ranges do not overlap at any K.
**There is therefore no K at which the two substrates can be compared at a matched
false-positive rate within the measured range**, and every recall comparison in this report
— H23a's +41.0 points [24.8, 56.1] included — compares two different operating points, not
two detection abilities. Matching the rate would take readings this study did not buy: a
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

Substrate 2's level ratio is lower than substrate 1's at **every** K, and so is the registered gain ratio (**every** K). Substrate 2's cheapest reading already costs 31.8% false positives at K = 1, above substrate 1's dearest 16.0% at K = 8: the two measured false-positive ranges do **not** overlap.
<!-- END T6 -->

## 5. H23d — the same-vendor arm has no usable K

**H23d is not computed.** Its registered form is a paired union at K = 8 over the frozen
audit set, against substrate 1's −12.7 points [−25.0, −0.9]. The `self` arm
(`claude-haiku-4-5`) has no K at which that is defined. Its coverage was read once, at the
timestamp in Table 3, and frozen to `records/substrate2/self_coverage.json`, because the
Anthropic route was still retrying while this was written:

* Draw 1 covers all 250 frozen instances. Draw 2 covers 228. **Draws 3 to 8 cover between 23
  and 82**, and **not one of them read a single stratum-C instance**, so at K ≥ 3 there is
  no false-positive side at all.
* **22** instances carry all eight `self` readings. They are not a random subset of P: they
  are the instances the route happened to answer on all eight attempts while refusing under
  load. A union computed on them would estimate a different population from the one H23d
  names, so it is not computed and not quoted.
* The refusals are recorded: between **1,290 and 2,087** provider denials per `self` draw.

**One contrast is available and it is not H23d.** At K = 1 — the only K whose `self` draws
cover the whole frozen set — a single same-vendor reading flags **88.0% of P [80.2, 93.0]
Wilson** against the cross-vendor auditor's mean single reading of 49.5% [38.5, 60.4], a
paired difference of **+38.5 points [24.2, 52.4]**; and **77.3% of C [70.0, 83.3] Wilson**
against 31.8% [24.9, 39.0], a paired difference of **+45.5 points [36.0, 54.8]**. That is
**not preregistered at this K** and it is not evidence that the same-vendor auditor is
better: it flags four solutions in five, correct ones included. It is reported because it is
the same story as §4 in a second auditor — on this substrate, higher recall arrives strapped
to a higher false-positive rate.

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

**Nothing here says which substrate is more representative of real code**, and nothing here
ranks the two. Substrate 2 is BigCodeBench's stdlib half — the tasks whose declared modules
are importable in this project's interpreter — which excludes the scientific stack entirely.
Substrate 1 is short functions. Neither was selected on any audit outcome; neither was chosen
to resemble any particular production codebase.

**What carries over from ceiling 1 is the shape, not the level.** Reading the same code more
times saturates on both substrates; on this one it saturates by the eighth reading, where on
substrate 1 it had not. What does not carry over is the level of either curve, or the
distance between them.

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
* **The `self` ladder never completed and was still filling as this was written.** Its
  coverage and its flags were read once and frozen (§5); its cost was frozen at the
  timestamp in Table 7. A later reading of the cache will show more readings than Table 3
  does, and may make a larger K usable. **Nothing in §2, §3 or §4 depends on the `self`
  arm.**
* **The `self` arm read P before C.** Draws 3 to 8 have stratum-P readings and no stratum-C
  readings at all, so for most of the ladder the arm had a recall side and no false-positive
  side. Nothing was reordered by hand; it is recorded because it means the arm could not
  have produced a usable K = 8 by running a little longer.
* **The audit set was frozen to disk before the first audit call but not committed to
  git until this commit.** §2 asks for both. Its provenance is checkable without the
  earlier commit: redrawing it from the committed `instances.jsonl` with the
  registered seed 20260917 reproduces all 250 ids exactly, and a test asserts that.
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
7. Secondary, **not preregistered at this K** — self minus cross at a single reading, on P
   and on C, at the only K whose `self` draws cover the frozen audit set.

Every interval in this report is a 10,000-resample percentile bootstrap over **problem
clusters** at seed 20260917, except the Wilson score intervals, which are named as such
wherever they appear and which assume instances are independent, and the cluster sign-flip
test in §5, which is ceiling 1's frozen implementation and carries its own seed. Substrate
1's figures are read unmodified from `records/ceiling/numbers.json`; recomputing its curve
from its own records reproduces 30.0% [20.0, 40.7] and 16.0% [10.1, 22.3] exactly.

## 10. Cost

### Table 7 — cost, from the run's usage ledgers
<!-- BEGIN T7 (records/substrate2/tables.md) -->
Summed from the per-project `usage.jsonl` ledgers in the run archive as of 2026-09-11T10:18:49Z. Refused calls that never reached a model are not in the ledgers and cost nothing, and the `self` row grows while that arm keeps retrying.

| | calls | USD |
|---|---:|---:|
| generation (`claude-haiku-4-5`) | 600 | $1.83 |
| audit, `cross` (`openai:gpt-5.6-terra`), 8 complete draws | 2,000 | $18.31 |
| audit, `self` (`claude-haiku-4-5`), incomplete | 746 | $3.03 |
| **audit total** | **2,746** | **$21.34** |
| **study total** | **3,346** | **$23.17** (cap $60) |
<!-- END T7 -->
