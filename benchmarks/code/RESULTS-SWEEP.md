# P2 — the severity-threshold sweep: the auditor contrast does not survive a matched operating point

**No model calls.** This re-grades findings already archived by ceiling 1 and study 18 under
four decision rules. Every reading carries `model_blockers` and `model_findings`, so the
sweep is arithmetic over committed records; it cost nothing and nothing new was generated.

Both independent reviews of the manuscript named this as the single most important missing
experiment. It is missing no longer, and it changes what C2 may say.

## Why it was needed

The paper's second headline was that replacing the auditor with a stronger same-vendor model
moves union recall by **-26.4 points**. That contrast compares two auditors **at their own
operating points**, which is exactly the comparison the paper's own first caution warns
against. The sweep asks the question the caution implies: **at the same false-positive rate,
which auditor finds more?**

## The operating points, per family

Each family re-graded under four rules; the shipped rule is one BLOCKER or more. Union at
that family's own K, problem-cluster percentile bootstrap (10,000 resamples, seed 20260915).

| family | rule | K | recall on P | false positives on C |
|---|---|---:|---|---|
| `cross` | blocker ≥ 1 (shipped) | 5 | 22.7% [13.6, 32.4] | 12.7% [7.8, 18.2] |
| `cross` | any finding ≥ 1 | 5 | 27.3% [17.9, 37.6] | 14.0% [8.7, 19.7] |
| `cross` | blocker ≥ 2 | 5 | 3.6% [0.0, 8.3] | 1.3% [0.0, 3.4] |
| `self` | blocker ≥ 1 (shipped) | 7 | 14.8% [5.6, 24.1] | 18.6% [11.9, 26.1] |
| `self` | any finding ≥ 1 | 7 | 18.5% [9.3, 29.6] | 22.9% [15.5, 30.8] |
| `self` | blocker ≥ 2 | 7 | 5.6% [0.0, 13.0] | 13.6% [7.6, 20.0] |
| `astra` | blocker ≥ 1 (shipped) | 4 | 32.7% [21.1, 45.5] | 10.7% [5.9, 16.0] |
| `self-strong` | blocker ≥ 1 (shipped) | 8 | **3.6% [0.9, 7.3]** | **3.3% [0.7, 6.6]** |
| `self-strong` | any finding ≥ 1 | 8 | **59.1% [47.3, 70.6]** | **34.0% [26.3, 41.8]** |
| `self-frontier` | blocker ≥ 1 (shipped) | 4 | 0.9% [0.0, 2.8] | 2.7% [0.6, 5.4] |
| `self-frontier` | any finding ≥ 1 | 4 | 20.9% [11.6, 31.5] | 18.0% [11.7, 24.7] |

## The finding

**`self-strong` moves from 3.6% recall to 59.1% on the same readings, with no new model call,
by counting a finding it wrote instead of the severity it assigned.** Its false positives move
3.3% → 34.0% with it. The model was never blind to these defects. It wrote them down and
graded almost none of them BLOCKER.

**So C2's -26.4 points is a fact about severity calibration, not about auditing ability**,
and the sweep is the direct evidence rather than an argument from the reversal under one
alternative rule. The same holds for `self-frontier`, which goes 0.9% → 20.9%.

**At a matched operating point the same-vendor families still do not beat the cross-vendor
one.** Taking each family's point nearest `cross`'s shipped 12.7% false positives:

| family | nearest FP | recall there | against `cross`'s 22.7% |
|---|---|---|---|
| `self` | 13.6% (blocker ≥ 2) | 5.6% [0.0, 13.0] | lower |
| `self-strong` | 3.3% (shipped) | 3.6% [0.9, 7.3] | lower, and not matched — its rules jump 3.3% → 34.0% |
| `self-frontier` | 18.0% (any finding) | 20.9% [11.6, 31.5] | lower, at a *higher* cost |
| `astra` | 10.7% (shipped) | **32.7% [21.1, 45.5]** | **higher, at a lower cost** |

**What survives and what does not.** The direction of C2 survives — no same-vendor family
overtakes `cross` once cost is held near-constant — but **its stated magnitude does not**. A
-26.4-point gap read as a difference in what the auditors can see is wrong; most of that gap
is where each family sets BLOCKER. And `astra` remains the counterexample to any reading of
C2 as "stronger models audit worse": it dominates `cross` on both axes at fewer readings.

## Limits, stated

* **Four rules, not a curve.** The archive records counts, not per-finding severities, so the
  reachable thresholds are coarse. `self-strong` has no point between 3.3% and 34.0% false
  positives, which is precisely where a matched comparison with `cross` would sit. **The
  matched comparison for that family is therefore bracketed, not measured.**
* **Each family at its own K** (4 to 8), because that is what the archive holds. Families run
  to fewer draws are read at fewer draws.
* **Post hoc.** No preregistration names these rules. The sweep is exploratory and every
  figure here carries that label.
* Re-grading cannot recover what a different severity *prompt* would have produced. It shows
  where the existing findings fall under a different cut, not how the auditor would behave if
  asked differently.
