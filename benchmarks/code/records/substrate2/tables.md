<!-- BEGIN T1 (records/substrate2/tables.md) -->
Both columns are medians over the frozen frame; the ratio is the median ratio, not a ratio of medians drawn from matched tasks. No corpus text is reproduced here.

| | substrate 1 (HumanEval+ / MBPP+) | substrate 2 (BigCodeBench, stdlib half) | ratio |
|---|---:|---:|---:|
| median specification words | 41 | **118** (IQR 91–143) | 2.88× |
| median reference-solution lines | 6 | **41** (IQR 36–48) | 6.83× |
| median test methods per task | — | 5 (minimum kept 3) | — |
| tasks in the frame | — | 300 of 1,140 | — |
<!-- END T1 -->
<!-- BEGIN T2 (records/substrate2/tables.md) -->
Two batches over 300 tasks. The audit set was drawn by `random.Random(20260917)` and committed before the first audit call.

| | count |
|---|---:|
| candidates generated | 600 |
| stratum P (passes visible, fails hidden) | **99** |
| stratum C (passes both) | 461 |
| stratum F (fails visible) | 40 |
| P instances audited | 99 (cap 200; the whole population, no draw needed) |
| C instances audited | 150 (cap 150) |
| generation cost | $1.91 (600 calls) |
<!-- END T2 -->
<!-- BEGIN T3 (records/substrate2/tables.md) -->
The frozen audit set is 249 instances (99 P, 150 C). Both ladders are complete: every draw of both families covers all 249. A denial is a call that never produced a reading; it is not in the usage ledger and cost nothing. The last column is what the `self` ladder had reached at 2026-09-11T10:18:26Z, when the first version of this report was written and H23d was not yet evaluable.

| draw | `cross` readings | `cross` denials | `self` readings | `self` denials | `self` readings at the first read |
|---:|---:|---:|---:|---:|---:|
| 1 | 249 / 249 ✓ | 7,344 | 250 / 249 | 2,087 | 250 |
| 2 | 249 / 249 ✓ | 7,242 | 250 / 249 | 1,340 | 228 |
| 3 | 249 / 249 ✓ | 6,732 | 250 / 249 | 1,438 | 24 |
| 4 | 249 / 249 ✓ | 6,732 | 250 / 249 | 1,425 | 31 |
| 5 | 249 / 249 ✓ | 6,732 | 250 / 249 | 1,428 | 23 |
| 6 | 249 / 249 ✓ | 6,732 | 250 / 249 | 1,353 | 38 |
| 7 | 249 / 249 ✓ | 13,837 | 250 / 249 | 1,291 | 60 |
| 8 | 249 / 249 ✓ | 17,934 | 250 / 249 | 1,290 | 82 |

**Draw-to-draw agreement.** Over the 249 audited instances, the cross-vendor arm's flag splits across its eight draws on **96** of them; the same-vendor arm's splits on **12**. Every flag in both families came from the model (0 readings were flagged by the deterministic checks layer). The same-vendor arm returned one identical set of finding digests across all eight draws on 144 instances, the cross-vendor arm on 105; no finding text was archived or read.
<!-- END T3 -->
<!-- BEGIN T4 (records/substrate2/tables.md) -->
Unit of analysis: the instance. n = 99 stratum-P instances from 51 problems (recall) and 150 stratum-C instances from 117 problems (false positives), the same instances at every K. The union rate at K is averaged over all C(8, K) subsets of the eight draws, exactly. Intervals are 10,000-resample problem-cluster percentile bootstraps, seed 20260917. The **registered** gain ratio is ceiling 1's own column — recall gained over K = 1 divided by false positives gained over K = 1. The **level** ratio is recall at K divided by the false-positive rate paid at K; it is post hoc and is not in the preregistration.

| K | union recall on P [95% cluster CI] | union FP on C [95% cluster CI] | recall per FP point, registered gain ratio | recall per FP point, POST-HOC level ratio |
|---:|---|---|---:|---:|
| 1 | 52.1% [41.0, 63.5] | 25.2% [18.8, 32.2] | — | 2.07 |
| 2 | 60.8% [49.5, 72.0] | 31.6% [24.3, 39.4] | 1.35 | 1.92 |
| 3 | 65.5% [54.3, 76.3] | 35.5% [27.8, 43.7] | 1.30 | 1.84 |
| 4 | 68.9% [57.9, 79.5] | 38.4% [30.3, 46.8] | 1.27 | 1.79 |
| 5 | 71.4% [60.6, 81.9] | 40.6% [32.3, 49.1] | 1.26 | 1.76 |
| 6 | 73.5% [62.7, 83.8] | 42.4% [33.8, 51.1] | 1.25 | 1.73 |
| 7 | 75.3% [64.4, 85.5] | 43.9% [35.2, 52.8] | 1.24 | 1.71 |
| 8 | 76.8% [65.7, 87.0] | 45.3% [36.4, 54.4] | 1.23 | 1.69 |

Fit on P: A = 72.6% [62.2, 82.8], tau = 0.93, r² = 0.830. Last-step gain 1.52 points [0.62, 2.60] — ceiling 1's flattening bar (≤ 1.0 point) is **not met**.
Fit on C: A = 43.0% [34.5, 51.8], tau = 1.42, r² = 0.903. Last-step gain 1.42 points [0.78, 2.11] — the bar is **not met**.
<!-- END T4 -->
<!-- BEGIN T5 (records/substrate2/tables.md) -->
The two populations share no instance and no problem, so this is a **two-sample** bootstrap: each population's problems are resampled independently and the difference of the two resampled rates is taken. Nothing here is paired, so no McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and assumes instances are independent, which within a substrate they are not.

| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |
|---|---|---|---|
| **H23a (primary)** union recall, P, K = 8 | **76.8%** (76/99, 51 problems) Wilson [67.5, 84.0] | 30.0% (33/110, 56 problems) Wilson [22.2, 39.1] | **+46.8 points** [31.6, 61.3] |
| **H23c** union false positives, C, K = 8 | **45.3%** (68/150, 117 problems) Wilson [37.6, 53.3] | 16.0% (24/150, 143 problems) Wilson [11.0, 22.7] | **+29.3 points** [18.3, 40.2] |
<!-- END T5 -->
<!-- BEGIN T6 (records/substrate2/tables.md) -->
The level ratio is POST HOC — the preregistration's H23c names ceiling 1's registered gain ratio, whose values are in Table 4. Both definitions point the same way; the level ratio is shown here because it is the one that can be read against a fixed operating cost.

| K | substrate 1 recall | substrate 1 FP | substrate 1 level ratio | substrate 2 recall | substrate 2 FP | substrate 2 level ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.7% | 4.5% | 2.37 | 52.1% | 25.2% | 2.07 |
| 2 | 15.0% | 7.1% | 2.12 | 60.8% | 31.6% | 1.92 |
| 3 | 18.3% | 9.2% | 2.00 | 65.5% | 35.5% | 1.84 |
| 4 | 21.2% | 10.9% | 1.94 | 68.9% | 38.4% | 1.79 |
| 5 | 23.8% | 12.4% | 1.91 | 71.4% | 40.6% | 1.76 |
| 6 | 26.0% | 13.7% | 1.89 | 73.5% | 42.4% | 1.73 |
| 7 | 28.1% | 14.9% | 1.88 | 75.3% | 43.9% | 1.71 |
| 8 | 30.0% | 16.0% | 1.88 | 76.8% | 45.3% | 1.69 |

Substrate 2's level ratio is lower than substrate 1's at **every** K, and so is the registered gain ratio (**every** K).

**Can any reading count put the two substrates at the same false-positive rate?** The answer depends on which auditor families are admitted, so it is given twice.

**Within the cross-vendor family** — the comparison this study draws, since substrate 1's frozen comparator and substrate 2's primary are both the shipped cross-vendor auditor — **a matched rate CANNOT be ruled out**. Substrate 2's cheapest reading costs 25.2% [18.8, 32.2] at K = 1, and substrate 1's dearest costs 16.0% [10.1, 22.3] at K = 8. The point estimates are disjoint, but **the intervals overlap by 3.5 points**, so non-overlap is not available as a conservative proxy here. The voided run reported these intervals as disjoint; that finding does not survive the correction of the visible tests.

**Pooling every family measured on either substrate** — **yes, narrowly**. Substrate 1's dearest reading anywhere is its `self` family at K = 8, 24.0% [17.2, 31.2], and its upper bound reaches 12.5 points into substrate 2's cheapest interval of [18.8, 32.2]. The point estimates are still disjoint (24.0% against 25.2%), but the intervals overlap, so a matched false-positive rate cannot be ruled out pooled. Substrate 1's interval here is the one ceiling 1's own Table 1 quotes; its second bootstrap stream for the same point gives an overlap of 12.5 points instead.
<!-- END T6 -->
<!-- BEGIN T7 (records/substrate2/tables.md) -->
The same-vendor arm is `claude-haiku-4-5`, the generator's own model, over the same 99 P and 150 C instances at the same K = 8. Its flag splits across draws on 12 of 249 instances (Table 3), so ceiling 1's registered gain ratio is computable here: it runs 0.32 at K = 2 down to 0.25 at K = 8. The post-hoc level ratio is 1.22 [1.00, 1.48] at K = 1 and 1.18 [0.97, 1.42] at K = 8.

| K | `self` recall on P [95% cluster CI] | `self` FP on C [95% cluster CI] | `self` level ratio | `cross` recall on P | `cross` FP on C | `cross` level ratio |
|---:|---|---|---:|---:|---:|---:|
| 1 | 80.1% [69.2, 90.0] | 65.6% [56.6, 74.1] | 1.22 | 52.1% | 25.2% | 2.07 |
| 2 | 80.4% [69.6, 90.5] | 66.8% [57.8, 75.4] | 1.20 | 60.8% | 31.6% | 1.92 |
| 3 | 80.6% [69.7, 90.6] | 67.3% [58.4, 75.9] | 1.20 | 65.5% | 35.5% | 1.84 |
| 4 | 80.7% [69.9, 90.8] | 67.7% [58.8, 76.2] | 1.19 | 68.9% | 38.4% | 1.79 |
| 5 | 80.8% [70.0, 90.9] | 68.0% [59.1, 76.5] | 1.19 | 71.4% | 40.6% | 1.76 |
| 6 | 80.8% [70.0, 90.9] | 68.3% [59.4, 76.8] | 1.18 | 73.5% | 42.4% | 1.73 |
| 7 | 80.8% [70.0, 90.9] | 68.5% [59.6, 77.0] | 1.18 | 75.3% | 43.9% | 1.71 |
| 8 | 80.8% [70.0, 90.9] | 68.7% [59.9, 77.1] | 1.18 | 76.8% | 45.3% | 1.69 |

Last-step gain on P 0.00 points, on C 0.17 points. Both meet ceiling 1's bar, but from a curve that barely rises, which is a weaker event than saturating and is not read as one; the exponential fit is not quoted for this family.
<!-- END T7 -->
<!-- BEGIN T8 (records/substrate2/tables.md) -->
Paired: the same instances are read by both arms, so this is ceiling 1's paired contrast, computed by `report_ceiling3.paired_union_difference` unchanged under seed 20260917. The cluster bootstrap is the primary interval; Tango and the grid-unconditional interval ignore clustering and are labelled so; the sign-flip test is ceiling 1's frozen implementation and carries its own seed. `a vs b` counts instances only one arm flagged.

| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |
|---|---:|---:|---|---:|---:|---:|---|---|
| P (recall) | 80.8% | 76.8% | **+4.0** [-10.1, 18.2] | 16 vs 12 | 0.57159 | 0.67572 | [-6.7, 14.8] | [-9.6, 17.7] |
| C (false positives) | 68.7% | 45.3% | **+23.3** [12.6, 34.0] | 48 vs 13 | 0.00001 | 0.00015 | [13.7, 32.8] | [11.3, 34.3] |

Substrate 1's frozen comparator is -12.7 points [-25.0, -0.9] on P. The sign here is **the opposite**. The same-vendor arm buys 4.0 points of recall and pays 23.3 points of false positives for it — 5.77 false-positive points per recall point, so it costs **more than it gains**.
<!-- END T8 -->
<!-- BEGIN T9 (records/substrate2/tables.md) -->
Summed from the per-project `usage.jsonl` ledgers in the run archive as of 2026-09-17T12:42:53Z. Refused calls that never reached a model are not in the ledgers and cost nothing.

| | calls | USD |
|---|---:|---:|
| generation (`claude-haiku-4-5`) | 600 | $1.91 |
| audit, `cross` (`openai:gpt-5.6-terra`), 8 draws | 2,610 | $23.11 |
| audit, `self` (`claude-haiku-4-5`), 8 draws | 2,861 | $12.14 |
| **audit total** | **5,471** | **$35.25** |
| **study total** | **6,071** | **$37.16** (cap $60) |
<!-- END T9 -->
