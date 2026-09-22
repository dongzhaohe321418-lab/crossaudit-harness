# P1's third rating — what the sheet's two groups show, and what they are not

> **Rewritten 2026-09-22 after the first cross-vendor review refused the previous version.** It
> found three blocking errors, and all three were real. The sheet's two groups are not the
> missed and caught populations; the registration accompanying it claimed a chronology that the
> repository's own log contradicts, and is withdrawn; and the rater was named wrongly. The
> arithmetic reproduced exactly — the reviewer recomputed every rate, interval and cluster count
> independently. **Everything around the arithmetic was wrong.** The previous version's headline
> is withdrawn, not adjusted.

Record: `records/rate3/analysis.json`. Rater `L3` = **`gpt-5.6-luna`**, per `rate3/third_rater.py`.

## Three things this is not

**It is not a registered analysis.** `plan/P1-ANALYSIS-REGISTRATION.md` is withdrawn: it claimed
no contrast had been computed when one had been committed an hour earlier, by me, in the same
session (`b0719cd`, 16:32:20; the registration, 17:31:09). The `cannot-tell` rule and the
interval method below were written **with the result in view**. They are argued on their merits
here and must not be read as prior commitments.

**It is not a missed-against-caught contrast.** The sheet's 121 entries cover **110 unique
instances**: 11 appear in *both* arms, because the 68-item missed sheet is 57 residual instances
plus 11 that were caught. `b2:Mbpp/300` is entry H001 in the missed arm and H096 in the caught
arm. A difference between the sheet's two groups counts those 11 on both sides.

**It is not `gpt-6-astra`.** The previous version named that model. P3's own preregistration
chose `gpt-5.6-luna` *precisely to avoid* `gpt-6-astra`, which served as L2 in study 21 and may
have produced labels this rating is meant to be independent of. Naming the excluded model
reversed the reason the rater was chosen.

## Table 1 — undetermined labels, by sheet group and by instance

| reading | missed side | caught side | difference | problem-cluster 95% |
|---|---:|---:|---:|---|
| the sheet's two groups (**overlapping — not two populations**) | 43/68 = 63.2% | 23/53 = 43.4% | +19.8 | [+1.5, +38.2] |
| **disjoint instances**, the 11 missed-arm copies removed | 38/57 = 66.7% | 23/53 = 43.4% | **+23.3** | [+2.4, +44.0] |
| disjoint, `cannot-tell` excluded | — | — | +22.6 | [+2.1, +42.6] |
| six-category comparator (**a different instrument**) | 46/68 = 67.6% | 24/53 = 45.3% | +22.4 | — |

Wilson intervals, printed because the withdrawn registration promised them and the previous
version omitted them, and **too narrow** as everywhere in this programme: missed 63.2%
[51.4, 73.7], caught 43.4% [31.0, 56.7].

The overlap **understated** the contrast: removing the duplicated instances moves it from +19.8
to +23.3. That direction is worth stating plainly, because it removes the most comfortable
reading of the error — the previous version was not modest, it was wrong, and it happened to be
wrong in the direction that looks modest.

**Both intervals reach close to zero** — +1.5 and +2.4 points at the lower end. Nothing here
licenses quoting either point estimate as though its interval were tight.

The six-category row is for orientation only. It used **two raters, a six-category hierarchy,
and witness expected *and* actual values**; this used one rater, three options, and failing
inputs with no expected values — so it does not check whether the particular hidden expected
value follows from the prose. The instruments differ in more than option count, the rates are
not interchangeable, and neither replicates the other. The closeness of +22.4 to +22.6 is a
coincidence between two instruments and is not evidence.

## Table 2 — what the unanswerable sheet said

The same model rated the sheet before it was rebuilt on mechanically recovered witnesses. That
version showed 42 of its 53 caught entries no failing input class at all.

| sheet | missed side | caught side | difference | problem-cluster 95% |
|---|---:|---:|---:|---|
| rebuilt | 43/68 = 63.2% | 23/53 = 43.4% | +19.8 | [+1.5, +38.2] |
| broken | 42/68 = 61.8% | 4/53 = **7.5%** | **+54.2** | [+38.8, +69.8] |

Both rows use the same grouping, so the overlap above affects them equally; this comparison is
between two *sheets*, and the overlap does not confound it.

**The broken sheet reported 2.7 times the contrast, in the direction that flatters C4, with an
interval nowhere near zero.** The previous version said the mechanism was "entirely in the
caught arm", and that is false: **21 missed-side labels changed as well as 46 caught-side ones**,
67 of 121 in total. What is true is narrower and is the claim made here — **the movement in the
`undetermined` rate is almost entirely on the caught side, +35.85 points against +1.47.** Both
presentations changed and the model was re-run over the whole sheet.

This is **evidence about sheets, not about specifications**, and it is a descriptive association
between one repair and one model's re-rating. It does not establish that unanswerable controls
*necessarily* produce hypothesis-favouring numbers. What it establishes is that this one did:
a control arm the rater could not answer produced a large, confident number pointing where the
hypothesis points, and it was one analysis away from being quoted.

## Limits

* `L3` is a model. P1 exists to obtain a rating by **a human from outside the project**, and
  this does not deliver that. No sentence here should be read as delivering it.
* Nothing here was registered in advance. See the withdrawal notice above.
* The disjoint reading is a **post-hoc diagnostic**, computed after the overlap was found. It is
  not a registered primary and there is no registered primary.
* Both intervals nearly touch zero at the lower end.
* **L1 — the author — rated all 121 sheet entries**, covering all 110 unique instances, so the
  programme holds a re-test rather than an independent review for every one of them. (The
  previous version said 57, which was wrong.) That prior rating does not by itself prevent an
  independent rater from re-rating; it is the reason P1 asks for one.
* `cannot-tell` remains on 12 of 121 entries. The primary keeps them in the denominator, which
  estimates the proportion *labelled* `undetermined` and claims nothing about abstentions;
  excluding them answers a different, conditional question and moves the difference by +2.7
  points. Both are reported; neither was chosen in advance.
* Seven of the 68 missed entries carry no concrete failing input: **five timeouts and two whose
  inputs could not be recovered**. `rebuild_sheet.py` described all seven as timeouts; that
  docstring is corrected.
