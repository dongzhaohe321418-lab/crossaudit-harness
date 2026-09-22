# P1's third rating — and a rater that disagrees with itself on more than half the repeats

> **Third version, 2026-09-22.** Two cross-vendor reviews refused the two before it. Round 1
> found the arms overlapping, the accompanying registration's chronology false, and the rater
> named wrongly. Round 2 found that my repair had mislabelled an overlapping row as disjoint,
> that the withdrawal had **overcorrected** — much of the method *was* registered in advance —
> and that a claim about how nearly a wrong figure was published had no basis. All were right.
> The arithmetic has reproduced independently at every round; what keeps failing is the prose
> around it.

Record: `records/rate3/analysis.json`. Rater `L3` = **`gpt-5.6-luna`**, per `rate3/third_rater.py`.
All intervals: problem-cluster percentile bootstrap, 10,000 resamples, **seed 20260921**.

## The reading that constrains every other one

The sheet carries 11 instances **twice** — once in each arm — with the **same specification text
and the same witness display** both times. They are the same question asked twice in one pass.

> **The rater agreed with itself on 5 of those 11 pairs.** Six pairs got different labels, among
> them `determined` against `cannot-tell` on the same prose, twice.

Neither earlier version of this report mentioned it. It is the strongest constraint on
everything below: a contrast of about twenty points is being read off an instrument that
disagrees with itself on more than half of its own repeats. **No figure in this report should be
quoted without this sentence beside it.**

## Provenance, stated exactly

**Registered in advance**, in P3's Amendment 1 (`d5919b9`, 2026-09-21 20:24:05 — a day before
the ratings): the three-option rubric; the share taken over **all** entries in each group, so
`cannot-tell` sits in the denominator; the problem-cluster percentile bootstrap over the union
of their problems; 10,000 resamples; seed `20260921`; Wilson beside it; and an
**inconclusiveness gate at one-third `cannot-tell` in either group.**

**Not registered anywhere**: the disjoint-population reading and the comparison against the
broken sheet. Both are post hoc and are labelled so below.

**Withdrawn**: `plan/P1-ANALYSIS-REGISTRATION.md`, written the next day, which claimed no
contrast had been computed when one had been committed an hour earlier. The withdrawal notice
first said "nothing here was registered in advance", and **that was an overcorrection** — the
paragraph above is what the record supports. One draft of the analysis also ran at seed
`20260922` rather than the registered `20260921`; every figure here is at the registered seed.

## Table 1 — undetermined labels

| reading | first group | caught group | difference | cluster 95% |
|---|---:|---:|---:|---|
| the sheet's two groups (**overlapping — not two populations**) | 43/68 = 63.2% | 23/53 = 43.4% | +19.8 | [+1.2, +38.1] |
| **disjoint instances** (post hoc), 11 missed-arm copies removed | 38/57 = 66.7% | 23/53 = 43.4% | **+23.3** | [+2.0, +43.6] |
| overlapping, `cannot-tell` excluded | 43/61 = 70.5% | 23/48 = 47.9% | +22.6 | [+2.4, +42.7] |
| disjoint, `cannot-tell` excluded | 38/51 = 74.5% | 23/48 = 47.9% | +26.6 | [+4.8, +48.4] |
| six-category comparator (**a different instrument**) | 46/68 = 67.6% | 24/53 = 45.3% | +22.4 | — |

Wilson, registered and **too narrow**: 63.2% [51.4, 73.7] and 43.4% [31.0, 56.7].

Round 2 caught the third row being printed under a disjoint label in the previous version. On
the disjoint population, excluding abstentions moves the contrast by **+3.3 points**, not the
+2.7 that was reported.

The overlap **understated** the contrast — +19.8 to +23.3. The previous version's error was
therefore not modest, it was wrong in the direction that looks modest.

**Every interval's lower end is within five points of zero.** Nothing licenses quoting a point
estimate from this table as though its interval were tight, and the consistency reading above
applies to all of them.

The six-category row is orientation only: two raters, a six-category hierarchy, and witness
expected *and* actual values, against one rater, three options, and failing inputs with no
expected values — so this rating never checks whether the particular hidden expected value
follows from the prose. The instruments differ in more than option count. The closeness of +22.4
to +22.6 is a coincidence between two instruments and is not evidence.

## Table 2 — what the unanswerable sheet said, and why it could not have been published

The same model rated the sheet before it was rebuilt on mechanically recovered witnesses. That
version showed 42 of its 53 caught entries no failing input class at all.

| sheet | grouping | difference | cluster 95% |
|---|---|---:|---|
| rebuilt | sheet groups | +19.8 | [+1.2, +38.1] |
| broken | sheet groups | **+54.2** | [+38.5, +69.5] |
| rebuilt | disjoint | +23.3 | [+2.0, +43.6] |
| broken | disjoint | **+57.4** | [+38.5, +74.6] |

The previous version said the overlap "affects them equally". **It does not**: removing the
duplicates moves the rebuilt contrast +3.43 points and the broken one +3.15, so the ratio is
**2.47× on disjoint populations against 2.73× on the sheet groups.** The direction survives both
groupings; the exact multiple does not.

**And the previous version's "one analysis away from being quoted" was false.** Amendment 1's
registered gate makes a rating inconclusive when either group exceeds one-third `cannot-tell`.
The broken sheet's caught arm was **79.2%**. The gate fires, the committed outcome for that
sheet applied it, and no reading of it could have been quoted without first setting aside a rule
registered the day before. That is a worse story for me and a better one for the procedure, and
it is the true one.

What remains is still worth recording, and only this: **a control arm the rater could not answer
produced a large, confident number pointing where the hypothesis points.** It is a descriptive
association between one repair and one model's re-rating, **not** evidence that specifications
changed, and **not** a general law about unanswerable controls. A repair plus a fresh model run
does not isolate the effect of presentation — and 6 of the 11 identically presented duplicate
pairs disagree, which is how much of this movement plain instability can account for.

## Limits

* `L3` is a model. P1 exists to obtain a rating from **a human outside the project**; this does
  not deliver that, and no sentence here should be read as delivering it.
* **5 of 11 within-pass repeats agree.** See the top of this report.
* The disjoint reading and the broken-sheet comparison are post hoc.
* Every interval's lower end is within five points of zero.
* **L1 — the author — rated all 121 entries**, covering all 110 unique instances, so the
  programme holds a re-test rather than an independent review for each. That does not prevent an
  independent rater from re-rating; it is the reason P1 asks for one.
* `cannot-tell` stays in the denominator as registered, estimating the share *labelled*
  `undetermined` and claiming nothing about abstentions. Excluding them answers a different,
  conditional question. Both are reported.
* Seven of the 68 missed entries carry no concrete failing input: **five timeouts and two whose
  inputs could not be recovered**.
* **Two caught-arm entries, H003 and H117, render an escaped `\n` as an actual newline** in the
  displayed input. They are left as they are: the sheet is the artefact that was rated, and
  editing it afterwards would misdescribe what the rater saw.
* `rebuild_sheet.py` said the rebuilt blocks carry "the same information content" as the prose
  classes they replaced. They do not: some of the old descriptions stated oracle behaviour,
  while the replacement supplies concrete inputs and no expected values. That docstring is
  corrected.
