# P1's third rating — and a rater that repeats itself 7 times in 11

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

> **On the binary outcome the primary contrasts are built from — `undetermined` against
> everything else — `L3` agreed with itself on 7 of those 11 pairs.** On the full three-option
> label it agreed on 5, because two disagreements are `determined` against `cannot-tell`, which
> the primary counts identically.
>
> **The abstention-excluded rows are a third case, not either of those.** They drop
> `cannot-tell` from the denominator, so those two pairs leave the analysis rather than
> collapsing into agreement: **7 pairs survive with no abstention, and 5 of them agree.**

Neither earlier version of this report mentioned any of it. Each figure describes the analysis
named beside it; none of the three describes the others, and an earlier version's claim that the
two labels "count identically in every table below" was false of the abstention-excluded rows.

**The scope, exactly.** The 11 pairs sit on **6 problems**, so they are not 11 independent
observations — and the abstention-free subset sits on **4**: dropping the pairs that contain a
`cannot-tell` removes `HumanEval/154` and `Mbpp/300` entirely, leaving `Mbpp/119`, `Mbpp/244`,
`Mbpp/589` and `Mbpp/739`. **So the three readings are 7 of 11 on six problems, 5 of 11 on six,
and 5 of 7 on four**, and an earlier version assigned six problems to all three. They are also not the sheet's only repeated text: the 121 entries carry 56
distinct specifications, and across all 81 identical-text pairs 55 agree — a figure that is
heavily dependent and is **not** an alternative reliability estimate, only a second look at the
same weakness.

**The comparator's raters did not do this.** On the same 11 repeated instances, `L1` and `L2`
each agreed with themselves **11 times out of 11**. They were answering a different instrument
on a different sheet, with expected values shown, so this is not a controlled comparison — but
it does place `L3`'s 5, or 7, against a background of 11.

**No figure from the rebuilt-sheet rows should be quoted without the matching one of
those three numbers beside it.** The six-category comparator row is not covered: its raters
were checked above and were stable.

## Provenance, stated exactly

**Registered in advance**, in P3's Amendment 1 (`d5919b9`, 2026-09-21 20:24:05 — before the
**rebuilt** ratings; the broken sheet's outcome was already committed that evening): the three-option rubric; the share taken over **all** entries in each group, so
`cannot-tell` sits in the denominator; the problem-cluster percentile bootstrap over the union
of their problems; 10,000 resamples; seed `20260921`; Wilson beside it; and an
**inconclusiveness gate at one-third `cannot-tell` in either group.**

**Not registered anywhere**: the disjoint-population reading, the comparison against the broken
sheet, **and the abstention-excluded secondary** — Amendment 1 contains no such secondary; it
first appears in the withdrawn P1 registration, after the primary contrast was committed. All
three are post hoc and are labelled so below.

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
| overlapping, `cannot-tell` excluded (post hoc) | 43/61 = 70.5% | 23/48 = 47.9% | +22.6 | [+2.4, +42.7] |
| disjoint, `cannot-tell` excluded (post hoc) | 38/51 = 74.5% | 23/48 = 47.9% | +26.6 | [+4.8, +48.4] |
| six-category comparator (**a different instrument**) | 46/68 = 67.6% | 24/53 = 45.3% | +22.4 | — |

Wilson, registered and **too narrow**: 63.2% [51.4, 73.7] and 43.4% [31.0, 56.7].

Round 2 caught the third row being printed under a disjoint label in the previous version. On
the disjoint population, excluding abstentions moves the contrast by **+3.3 points**, not the
+2.7 that was reported.

The overlap **understated** the contrast — +19.8 to +23.3. The previous version's error was
therefore not modest, it was wrong in the direction that looks modest.

**Every one of the four rebuilt-sheet contrasts has its lower end within five points of zero**
(+1.2, +2.0, +2.4, +4.8). That is not true of the broken-sheet intervals in Table 2, which start
at +38.5, nor of the Wilson intervals. Nothing licenses quoting a point estimate from those four
rows as though its interval were tight, and the consistency reading above applies to them — but
**not** to the six-category comparator row, whose raters were checked above and were stable.

The six-category row is orientation only: two raters, a six-category hierarchy, and witness
expected *and* actual values, against one rater, three options, and failing inputs with no
expected values — so this rating never checks whether the particular hidden expected value
follows from the prose. The instruments differ in more than option count. The closeness of +22.4
to +22.6 is a coincidence between two instruments and is not evidence.

## Table 2 — what the unanswerable sheet said, and what the registered gate did with it

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
registered gate makes a rating **inconclusive rather than negative, with the decision waiting
for P1**, when either group exceeds one-third `cannot-tell`. The broken sheet's caught arm was
**79.2%**; the gate fires, and the committed outcome for that sheet applied it.

What that establishes is precise and smaller than the sentence it replaces: **the broken result
could not have authorised proceeding under the registered positive branch.** It does not forbid
describing an inconclusive result, and saying it "could not have been published" was the third
overcorrection toward modesty in this report's history. The gate did its work; it is not a
publication ban, and dressing it as one flatters the procedure in the opposite direction.

What remains is still worth recording, and only this: **a control arm the rater could not answer
produced a large, confident number pointing where the hypothesis points.** It is a descriptive
association between one repair and one model's re-rating, **not** evidence that specifications
changed, and **not** a general law about unanswerable controls. A repair plus a fresh model run
does not isolate the effect of presentation: the sheet changed and the model was asked again, and
nothing here separates the two. **The duplicate disagreements do not quantify that either** — six
discordant pairs cannot apportion a 34-point change between presentation, sampling and batch
context, and an earlier draft of this paragraph claimed they could.

## Limits

* `L3` is a model. P1 exists to obtain a rating from **a human outside the project**; this does
  not deliver that, and no sentence here should be read as delivering it.
* **Within-pass repeats: 7 of 11 agree on the primary binary outcome (6 problems), 5 of 11 on
  the full label (6 problems), and 5 of 7 among the abstention-free pairs (4 problems).** See
  the top of this report.
* The disjoint reading, the abstention-excluded secondary and the broken-sheet comparison
  are all post hoc.
* Each of the **four rebuilt-sheet contrasts** has its lower end within five points of zero
  (+1.2, +2.0, +2.4, +4.8). The broken-sheet contrast intervals start at +38.5, so
  this limit is about those four rows and not about the table. It is not about the Wilson
  intervals either — they are intervals for single rates rather than for a difference, and they
  are **narrower** than the broken-sheet contrasts (22.3 and 25.8 points against 31.0 and 36.1),
  not wider as an earlier version said.
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
* **The booklet's header overstates its own rationale.** It tells the rater that the expected
  value "is the answer, and giving it makes the question unaskable". Supplying an oracle value
  does not answer whether the prose entails it — that is precisely what the six-category
  comparator asked. `L3` never saw this text (`third_rater.py` takes the items and the rubric,
  not the header), so these labels are unaffected; a human rater reading the booklet would have
  seen it. The generator is corrected so a future rebuild does not reproduce it, and **the
  booklet on disk is left as it was rated**, for the same reason H003 and H117 are.
* `rebuild_sheet.py` said the rebuilt blocks carry "the same information content" as the prose
  classes they replaced. They do not: some of the old descriptions stated oracle behaviour,
  while the replacement supplies concrete inputs and no expected values. That docstring is
  corrected.
