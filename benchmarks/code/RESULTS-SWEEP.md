# P2 — the severity-threshold sweep: what a grading rule moves, and what it does not

> **First cross-vendor review, 2026-09-21: NOT QUOTABLE, and it was right.** The loader in the
> first version read one cache directory and renumbered what it found, so `cross` was reported at
> "K = 5" when those were draws 4 to 8, and `self`'s population came from a partial draw of 172
> rows — 54 P and 118 C where every other report in this programme uses 110 and 150. The
> sentence "each family at its own K, because that is what the archive holds" was false: the
> archive holds 8, 8, 4, 8, 4, and the missing draws are committed in `records/explore/cache`,
> where this project's own `report_ceiling3.load_draws` has always looked. **Every cross-family
> figure in the first version was computed on the wrong readings.** They are recomputed below
> from complete ladders, and they reproduce ceiling 1's own headline under the shipped rule —
> 30.0% [20.0, 40.7] recall at 16.0% [10.2, 22.3] false positives — which is the cross-check the
> first version could not have passed.

**No model calls.** This re-grades findings already archived by ceiling 1 and study 18 under four
decision rules. Every reading carries `model_blockers` and `model_findings`, so the sweep is
arithmetic over committed records. The inherited arms were checked to carry both counts; a row
that carries neither is dropped loudly rather than silently, and none was.

Both reviews of the manuscript named this as the single most important missing experiment, and
the paper's Discussion still names it as the cheapest of the experiments it needs.

## Why it was needed

The paper's second headline is that replacing the auditor with a stronger same-vendor model moves
union recall by **-26.4 points**. That contrast compares two auditors **at their own operating
points**, which is exactly the comparison the paper's own first caution warns against. The sweep
asks the question the caution implies: **at the same false-positive rate, and at the same reading
depth, which auditor finds more?**

## The operating points, per family, on complete ladders

Union at each family's full archived K, problem-cluster percentile bootstrap, 10,000 resamples,
seed 20260915. The fourth rule, `any finding>=2`, was computed and unnamed in the first version's
table; it is here.

| family | rule | K | recall on P | false positives on C |
|---|---|---:|---|---|
| `cross` | blocker>=1 (shipped) | 8 | 30.0% [20.0, 40.7] | 16.0% [10.2, 22.3] |
| `cross` | blocker>=2 | 8 | 5.5% [0.9, 10.9] | 1.3% [0.0, 3.4] |
| `cross` | any finding>=1 | 8 | 34.5% [24.1, 45.9] | 19.3% [13.1, 26.4] |
| `cross` | any finding>=2 | 8 | 6.4% [1.8, 12.7] | 1.3% [0.0, 3.4] |
| `self` | blocker>=1 (shipped) | 8 | 17.3% [8.1, 27.3] | 24.0% [17.2, 31.3] |
| `self` | blocker>=2 | 8 | 9.1% [2.7, 16.4] | 20.0% [13.6, 26.8] |
| `self` | any finding>=1 | 8 | 20.9% [10.9, 31.5] | 27.3% [20.3, 34.9] |
| `self` | any finding>=2 | 8 | 10.0% [3.6, 17.4] | 20.0% [13.6, 26.8] |
| `astra` | blocker>=1 (shipped) | 4 | 32.7% [21.1, 45.5] | 10.7% [5.9, 16.0] |
| `astra` | blocker>=2 | 4 | 2.7% [0.0, 7.3] | 0.7% [0.0, 2.1] |
| `astra` | any finding>=1 | 4 | 32.7% [21.1, 45.5] | 10.7% [5.9, 16.0] |
| `astra` | any finding>=2 | 4 | 2.7% [0.0, 7.3] | 0.7% [0.0, 2.1] |
| `self-strong` | blocker>=1 (shipped) | 8 | 3.6% [0.9, 7.3] | 3.3% [0.7, 6.6] |
| `self-strong` | blocker>=2 | 8 | 1.8% [0.0, 4.6] | 1.3% [0.0, 3.4] |
| `self-strong` | any finding>=1 | 8 | 59.1% [47.3, 70.6] | 34.0% [26.3, 41.8] |
| `self-strong` | any finding>=2 | 8 | 2.7% [0.0, 6.5] | 1.3% [0.0, 3.4] |
| `self-frontier` | blocker>=1 (shipped) | 4 | 0.9% [0.0, 2.8] | 2.7% [0.6, 5.4] |
| `self-frontier` | blocker>=2 | 4 | 0.0% [0.0, 0.0] | 2.0% [0.0, 4.6] |
| `self-frontier` | any finding>=1 | 4 | 20.9% [11.6, 31.5] | 18.0% [11.7, 24.7] |
| `self-frontier` | any finding>=2 | 4 | 0.0% [0.0, 0.0] | 2.0% [0.0, 4.6] |

## The same families at a common depth

Families read at their own K cannot isolate auditor identity: a family read four times is not
being asked the same question as one read eight times. K = 4 is the largest depth every family
reaches. Each rate is averaged **exactly** over all C(K_max, 4) four-draw subsets, so a family
with eight draws gains nothing from a lucky choice of which four to use. Round 1 of the review
required this table; the first version had none.

| family | rule | recall on P @ K=4 | false positives on C @ K=4 |
|---|---|---|---|
| `cross` | blocker>=1 (shipped) | 21.2% [13.1, 30.3] | 10.9% [6.9, 15.4] |
| `cross` | blocker>=2 | 3.6% [0.9, 7.3] | 1.2% [0.0, 3.1] |
| `cross` | any finding>=1 | 24.0% [15.7, 33.0] | 13.1% [8.7, 18.0] |
| `cross` | any finding>=2 | 4.0% [0.9, 8.4] | 1.2% [0.0, 3.1] |
| `self` | blocker>=1 (shipped) | 16.4% [7.7, 26.1] | 23.2% [16.6, 30.4] |
| `self` | blocker>=2 | 7.7% [2.3, 14.3] | 18.6% [12.7, 25.2] |
| `self` | any finding>=1 | 20.0% [10.4, 30.6] | 26.5% [19.6, 34.0] |
| `self` | any finding>=2 | 8.6% [3.1, 15.5] | 18.9% [12.8, 25.5] |
| `astra` | blocker>=1 (shipped) | 32.7% [21.1, 45.5] | 10.7% [5.9, 16.0] |
| `astra` | blocker>=2 | 2.7% [0.0, 7.3] | 0.7% [0.0, 2.1] |
| `astra` | any finding>=1 | 32.7% [21.1, 45.5] | 10.7% [5.9, 16.0] |
| `astra` | any finding>=2 | 2.7% [0.0, 7.3] | 0.7% [0.0, 2.1] |
| `self-strong` | blocker>=1 (shipped) | 2.1% [0.4, 4.3] | 2.5% [0.5, 5.0] |
| `self-strong` | blocker>=2 | 0.9% [0.0, 2.3] | 0.9% [0.0, 2.3] |
| `self-strong` | any finding>=1 | 52.3% [41.1, 63.4] | 29.4% [22.7, 36.4] |
| `self-strong` | any finding>=2 | 2.1% [0.0, 4.9] | 1.0% [0.0, 2.7] |
| `self-frontier` | blocker>=1 (shipped) | 0.9% [0.0, 2.8] | 2.7% [0.6, 5.4] |
| `self-frontier` | blocker>=2 | 0.0% [0.0, 0.0] | 2.0% [0.0, 4.6] |
| `self-frontier` | any finding>=1 | 20.9% [11.6, 31.5] | 18.0% [11.7, 24.7] |
| `self-frontier` | any finding>=2 | 0.0% [0.0, 0.0] | 2.0% [0.0, 4.6] |

## What the sweep shows

**On `self-strong`, a grading rule moves the measured rate by more than the choice of model
does.** Its re-grading gain is 55.5 points against C2's -26.4-point model contrast. The same is
**not** true of `self-frontier`, whose 20.0-point re-grading gain is smaller than its 29.1-point
shipped-rule gap from the full-ladder `cross`; round 2 asked for that comparator to be named
rather than left implied. `self-strong` goes from 3.6% [0.9, 7.3] recall to 59.1% [47.3, 70.6] on the same
readings, with no new model call, by counting a finding it wrote instead of the severity it
assigned; its false positives move 3.3% [0.7, 6.6] to 34.0% [26.3, 41.8] with it. `self-frontier`
goes 0.9% to 20.9% the same way. At the common depth the pattern holds: 2.1% to 52.3% and 0.9% to
20.9%.

**What that does and does not establish, stated because the first version got it wrong.** It
establishes a change in **flag coverage** under re-grading: 65 of 110 P instances drew some
finding where 4 drew a BLOCKER. It does **not** establish that those findings identified the
hidden failure. The sweep neither reads nor adjudicates their content, and
`RESULTS-CEILING3.md` expressly forbids reading a flag rate as a naming or recognition rate. The
first version said "the model was never blind to these defects; it wrote them down", and that
sentence is **withdrawn**. Changing the counting rule mechanically changes the result; it does
not identify the cause of the families' original differences.

**So C2's -26.4 points cannot be read as a difference in what the auditors can see.** What the
sweep establishes is narrower and worth stating exactly: **the measured flag coverage is
rule-dependent**. C2's magnitude is specific to its **preregistered** BLOCKER rule — ceiling 1's
registration fixes the flag as "≥ 1 BLOCKER finding" and study 18 inherits it — and exploratory
re-grading changes that magnitude and reverses its sign. Round 3 corrected "a grading rule that
no preregistration fixed", which was larger than the truth in the direction of disparaging the
original study's rigour. It does **not** establish why the families produced different findings or different
severities — round 2 was right that "a large part of the gap is attributable to where each family
sets BLOCKER" is a causal attribution the re-grading cannot support. C2's estimate remains valid
for its own rule and configuration; its sign reverses under any-finding grading; and neither fact
resolves the ranking at a matched false-positive rate.

**The matched comparison, stated as what it is.** Choosing each family's point nearest `cross`'s
false-positive rate is a **descriptive selection rule, not a measurement at a matched rate**. The
first version called those points matched and then concluded that C2's direction survives; round
1 was right that neither half of "direction survives, magnitude does not" works as written. On
the four reachable rules `self-strong` has no point between 3.3% and 34.0% false positives —
precisely where a matched comparison with `cross` would sit — so **that family's comparison is
bracketed, not measured, and nothing here resolves the ranking between its two endpoints.**

**The comparison at equal depth, and what it does and does not settle.** At the common depth
K = 4 the observed false-positive rates are similar — 10.7% [5.9, 16.0] against 10.9%
[6.9, 15.4] — which is an observation about two rates and not a matched operating point; the
contrast below leaves their difference unresolved. At that depth `astra` reaches **32.7%** [21.1, 45.5] recall against
`cross`'s **21.2%** [13.1, 30.3]. Paired over the same instances and clustered by problem, with
three comparators because they answer different questions:

| `astra` at K = 4, minus… | recall difference | false-positive difference |
|---|---|---|
| `cross` at K = 4, averaged over all 70 four-draw subsets | **+11.5 points** [+2.9, +21.3] | -0.3 points [-3.8, +3.4] |
| `cross` draws 1–4 only (sensitivity) | **+12.7 points** [+3.6, +22.7] | +0.0 points [-4.8, +4.7] |
| `cross` on its complete K = 8 ladder | **+2.7 points** [-6.5, +13.0] | -5.3 points [-10.3, -0.7] |

The first row is the one that matches the table above it: each side averaged over all its
available four-draw subsets, which is 70 for `cross` and, since it has exactly four draws, one
for `astra`. The second holds `cross` to its first four draws and is a sensitivity
analysis, not the headline — the first version of this report used it while presenting the
subset-averaged table beside it, which is a different estimand and is why 32.7 minus 21.2 could
not give +12.7. The third compares `astra` at four readings against `cross` at eight, which is a
comparison between budgets rather than between auditors.

**What this supports:** higher flag recall at equal depth, with similar observed false-positive
rates and a false-positive difference **unresolved around zero**. An interval containing zero is
not evidence of equality, and the first version's "equal cost" and "the same price" are
withdrawn. Against the deeper `cross`, the recall advantage is not established while the
false-positive advantage is. **Neither comparison isolates model identity from the differing
sampling configurations**, which is C2's confound and is not removed here.

## Limits, stated

* **Four rules, not a curve.** The archive records counts, not per-finding severities. Four rules
  are a chosen analysis set and not the archive's limit — the observed counts also permit a
  cutoff at three — but the reachable points remain coarse, and the gap that matters for
  `self-strong` falls inside one of them.
* **Post hoc.** This four-rule sweep was not preregistered, so every figure here carries the
  exploratory label. That is a limit on what it can become, not on what it can support: an
  exploratory analysis can carry exploratory inference, and it cannot be turned into a
  preregistered confirmatory test after the fact. Round 2 found "it may not be read as a test of
  anything" too strong, and it was — the fifth time in this programme that a stated limit has
  been larger than the truth.
* **Re-grading is not re-asking.** It shows where the existing findings fall under a different
  cut, not how an auditor would behave if its severity instructions were different.
* **Flag coverage is not naming.** No figure here says what a finding identified. Establishing
  that needs the two-rater adjudication that studies 18 and 19 ran, on texts this sweep does not
  read.
* **The sampling asymmetry travels with every cross-family row.** The cross-vendor route is sent
  no sampling parameter and the same-vendor routes are sent temperature 0, so the families are
  not equally free to vary between draws. That confound is C2's and it is not removed here.
