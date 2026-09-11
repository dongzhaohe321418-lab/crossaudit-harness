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
| stratum P (passes visible, fails hidden) | **100** |
| stratum C (passes both) | 462 |
| stratum F (fails visible) | 38 |
| P instances audited | 100 (cap 200; the whole population, no draw needed) |
| C instances audited | 150 (cap 150) |
| generation cost | $1.83 (600 calls) |
<!-- END T2 -->
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
<!-- BEGIN T5 (records/substrate2/tables.md) -->
The two populations share no instance and no problem, so this is a **two-sample** bootstrap: each population's problems are resampled independently and the difference of the two resampled rates is taken. Nothing here is paired, so no McNemar and no sign-flip test is reported. Wilson is quoted beside each rate and assumes instances are independent, which within a substrate they are not.

| contrast | substrate 2 | substrate 1 (frozen) | difference [95% two-sample cluster CI] |
|---|---|---|---|
| **H23a (primary)** union recall, P, K = 8 | **71.0%** (71/100, 51 problems) Wilson [61.5, 79.0] | 30.0% (33/110, 56 problems) Wilson [22.2, 39.1] | **+41.0 points** [24.8, 56.1] |
| **H23c** union false positives, C, K = 8 | **55.3%** (83/150, 121 problems) Wilson [47.3, 63.1] | 16.0% (24/150, 143 problems) Wilson [11.0, 22.7] | **+39.3 points** [28.2, 50.2] |
<!-- END T5 -->
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
<!-- BEGIN T8 (records/substrate2/tables.md) -->
Paired: the same instances are read by both arms, so this is ceiling 1's paired contrast, computed by `report_ceiling3.paired_union_difference` unchanged under seed 20260917. The cluster bootstrap is the primary interval; Tango and the grid-unconditional interval ignore clustering and are labelled so; the sign-flip test is ceiling 1's frozen implementation and carries its own seed. `a vs b` counts instances only one arm flagged.

| stratum | `self` at K = 8 | `cross` at K = 8 | self - cross [95% cluster CI] | discordant a vs b | McNemar p | sign-flip p | Tango | grid-unconditional |
|---|---:|---:|---|---:|---:|---:|---|---|
| P (recall) | 88.0% | 71.0% | **+17.0** [2.0, 32.0] | 26 vs 9 | 0.00599 | 0.04210 | [5.7, 28.2] | [2.0, 30.5] |
| C (false positives) | 77.3% | 55.3% | **+22.0** [11.2, 32.7] | 46 vs 13 | 0.00002 | 0.00015 | [12.4, 31.4] | [10.0, 33.0] |

Substrate 1's frozen comparator is -12.7 points [-25.0, -0.9] on P. The sign here is **the opposite**. The same-vendor arm buys 17.0 points of recall and pays 22.0 points of false positives for it — 1.29 false-positive points per recall point, so it costs **more than it gains**.
<!-- END T8 -->
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
