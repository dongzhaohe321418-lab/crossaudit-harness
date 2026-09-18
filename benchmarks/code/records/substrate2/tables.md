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
| stratum P (passes visible, fails hidden) | **102** |
| stratum C (passes both) | 460 |
| stratum F (fails visible) | 38 |
| P instances audited | 102 (cap 200; the whole population, no draw needed) |
| C instances audited | 150 (cap 150) |
| generation cost | $1.91 (600 calls) |
<!-- END T2 -->
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
<!-- BEGIN T5 (records/substrate2/tables.md) -->
The two populations share no instance and no problem, so this is a **two-sample** bootstrap: each population's problems are resampled independently and the difference of the two resampled rates is taken. Nothing here is paired, so no McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and assumes instances are independent, which within a substrate they are not.

| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |
|---|---|---|---|
| **H23a (primary)** union recall, P, K = 8 | **74.5%** (76/102, 53 problems) Wilson [65.3, 82.0] | 30.0% (33/110, 56 problems) Wilson [22.2, 39.1] | **+44.5 points** [29.5, 58.7] |
| **H23c** union false positives, C, K = 8 | **53.3%** (80/150, 117 problems) Wilson [45.4, 61.1] | 16.0% (24/150, 143 problems) Wilson [11.0, 22.7] | **+37.3 points** [26.5, 48.1] |
<!-- END T5 -->
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
<!-- BEGIN T8 (records/substrate2/tables.md) -->
Paired: the same instances are read by both arms, so this is ceiling 1's paired contrast, computed by `report_ceiling3.paired_union_difference` unchanged under seed 20260917. The cluster bootstrap is the primary interval; Tango and the grid-unconditional interval ignore clustering and are labelled so; the sign-flip test is ceiling 1's frozen implementation and carries its own seed. `a vs b` counts instances only one arm flagged.

| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |
|---|---:|---:|---|---:|---:|---:|---|---|
| P (recall) | 81.4% | 74.5% | **+6.9** [-4.9, 18.6] | 16 vs 9 | 0.22952 | 0.34174 | [-2.9, 16.8] | [-6.3, 19.3] |
| C (false positives) | 66.0% | 53.3% | **+12.7** [1.4, 23.7] | 39 vs 20 | 0.01834 | 0.03709 | [2.7, 22.5] | [0.7, 24.0] |

Substrate 1's frozen comparator is -12.7 points [-25.0, -0.9] on P. The sign here is **the opposite**. The same-vendor arm buys 6.9 points of recall and pays 12.7 points of false positives for it — 1.85 false-positive points per recall point, so it costs **more than it gains**.
<!-- END T8 -->
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
