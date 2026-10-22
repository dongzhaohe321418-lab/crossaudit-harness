# AI4S audit test set — results

<!-- numbers: 131236b578fd5decebc027867e8add44084b4501ec92fd4ecf1fb3e19056de42 -->

Rendered by `report.py` from `numbers.json` only; the design and the preregistered claims are in `DESIGN.md`. Every rate below is quoted as count/n with its 95% Wilson score interval.

## Claims

- **H1 holds on this corpus.** The shipped profile `science` has class-averaged deterministic recall 0.259 over 18 classes; H1 requires below 0.500.
- **H2 does not hold on this corpus.** Extended minus shipped class-averaged recall is 0.648 (required at least 0.300), and the extended profile's false-block Wilson upper bound is 6.0% (required at most 2.5%).
  Secondary condition, stated alongside and not part of the preregistered decision rule: the bootstrap interval's lower bound 0.648 is above 0.

## Primary outcome

Extended (`science-ai4s`) minus shipped (`science`) class-averaged recall: **0.648**, 95% cluster-bootstrap percentile interval [0.648, 0.648] for the class-averaged recall difference, resampling 60 templates (`pair_id`) with replacement, 2000 resamples, percentiles 2.5/97.5, seed 20261021.

Coverage status: **uncalibrated**. Simulated at the corpus design (60 templates, 18 classes, 300 simulations of 400 resamples each), the interval covered the true delta in 92.7% of corpora under a null delta and 90.0% under a delta of 0.312; the required band is 93.0%–97.0%.

## Recall per class

Caught = BLOCKED with a BLOCKER finding from an expected rule or check; for an instance whose expected severity is ADVISORY, any finding from an expected rule or check (DESIGN §5). The fired columns count instances per rule; `:ADVISORY` marks a non-blocking finding.

| class | name | tier | n | shipped `science` | extended `science-ai4s` | expected rule | fired (shipped) | fired (extended) |
|---|---|---|---|---|---|---|---|---|
| D01 | schema_missing_field | deterministic_existing | 180 | 180/180 (100.0% [97.9%, 100.0%]) | 180/180 (100.0% [97.9%, 100.0%]) | `CA-META-001` | `CA-DATA-003` ×60, `CA-META-001` ×180 | `CA-DATA-003` ×60, `CA-DERIV-001` ×60, `CA-META-001` ×180, `CA-STAT-004` ×30 |
| D02 | unit_missing | deterministic_existing | 120 | 120/120 (100.0% [96.9%, 100.0%]) | 120/120 (100.0% [96.9%, 100.0%]) | `CA-DATA-001` | `CA-DATA-001` ×120 | `CA-DATA-001` ×120, `CA-PHYS-001` ×60 |
| D03 | unit_wrong | deterministic_new | 60 | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) | `CA-PHYS-001` | nothing | `CA-PHYS-001` ×60 |
| D04 | provenance_broken | deterministic_existing | 180 | 180/180 (100.0% [97.9%, 100.0%]) | 180/180 (100.0% [97.9%, 100.0%]) | `CA-DATA-003` | `CA-DATA-003` ×120, `CA-DATA-003:ADVISORY` ×60 | `CA-DATA-003` ×120, `CA-DATA-003:ADVISORY` ×60, `CA-DERIV-001` ×50, `CA-ML-001` ×10 |
| D05 | unconverged_reported | deterministic_existing | 20 | 20/20 (100.0% [83.9%, 100.0%]) | 20/20 (100.0% [83.9%, 100.0%]) | `CA-METH-002` | `CA-METH-002` ×20 | `CA-METH-002` ×20 |
| D06 | prose_data_mismatch | mixed | 180 | 60/180 (33.3% [26.9%, 40.5%]) | 60/180 (33.3% [26.9%, 40.5%]) | `CA-NUM-002`, `CA-DATA-002` | `CA-NUM-002` ×60 | `CA-NUM-002` ×60 |
| D07 | sign_flip | deterministic_new | 30 | 0/30 (0.0% [0.0%, 11.4%]) | 30/30 (100.0% [88.6%, 100.0%]) | `CA-PHYS-001` | nothing | `CA-DERIV-001` ×30, `CA-PHYS-001` ×30 |
| D08 | physical_range_violation | deterministic_new | 120 | 0/120 (0.0% [0.0%, 3.1%]) | 120/120 (100.0% [96.9%, 100.0%]) | `CA-PHYS-001` | nothing | `CA-DERIV-001` ×110, `CA-PHYS-001` ×120, `CA-STAT-004` ×20 |
| D09 | numeric_invalid | deterministic_new | 240 | 0/240 (0.0% [0.0%, 1.6%]) | 240/240 (100.0% [98.4%, 100.0%]) | `CA-NUM-005` | nothing | `CA-DERIV-001` ×240, `CA-NUM-005` ×240, `CA-PHYS-001` ×240, `CA-STAT-004` ×80 |
| D10 | derivation_mismatch | deterministic_new | 140 | 0/140 (0.0% [0.0%, 2.7%]) | 140/140 (100.0% [97.3%, 100.0%]) | `CA-DERIV-001` | nothing | `CA-DERIV-001` ×140, `CA-STAT-004` ×4 |
| D11 | n_mismatch | deterministic_new | 120 | 0/120 (0.0% [0.0%, 3.1%]) | 120/120 (100.0% [96.9%, 100.0%]) | `CA-DERIV-001` | nothing | `CA-DERIV-001` ×120 |
| D12 | split_leakage | deterministic_new | 40 | 0/40 (0.0% [0.0%, 8.8%]) | 40/40 (100.0% [91.2%, 100.0%]) | `CA-ML-001` | nothing | `CA-ML-001` ×40 |
| D13 | claim_false | deterministic_new | 40 | 0/40 (0.0% [0.0%, 8.8%]) | 40/40 (100.0% [91.2%, 100.0%]) | `CA-STAT-004` | nothing | `CA-STAT-004` ×40 |
| D14 | method_claim_mismatch | judgement | 60 | 0/60 (0.0% [0.0%, 6.0%]) | 0/60 (0.0% [0.0%, 6.0%]) | `CA-DATA-002` | nothing | nothing |
| D15 | placeholder_or_truncated | mixed | 180 | 60/180 (33.3% [26.9%, 40.5%]) | 180/180 (100.0% [97.9%, 100.0%]) | `CA-NUM-001` | `CA-NUM-001` ×60 | `CA-FILE-004:ADVISORY` ×120, `CA-NUM-001` ×60 |
| D16 | reproducibility_missing | deterministic_new | 150 | 0/150 (0.0% [0.0%, 2.5%]) | 150/150 (100.0% [97.5%, 100.0%]) | `CA-REPRO-001` | nothing | `CA-REPRO-001:ADVISORY` ×150 |
| D17 | precision_overclaim | deterministic_new | 60 | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) | `CA-PREC-001` | nothing | `CA-PREC-001:ADVISORY` ×60 |
| D18 | aggregate_mismatch | deterministic_new | 80 | 0/80 (0.0% [0.0%, 4.6%]) | 80/80 (100.0% [95.4%, 100.0%]) | `CA-DERIV-001` | nothing | `CA-DERIV-001` ×80 |

Class-averaged recall (unweighted over the classes present): shipped 0.259, extended 0.907.

### Recall per variant

D06's variants carry different tiers, so its class rate mixes a deterministic variant with referent-only ones; the variant rows are the readable unit.

| class | variant | variant tier | shipped `science` | extended `science-ai4s` |
|---|---|---|---|---|
| D01 | inputs_not_path_at_rev | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D01 | no_code_version | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D01 | no_quantities | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D02 | empty_source | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D02 | empty_unit | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D03 | label_swapped | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D04 | input_file_missing | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D04 | revision_mismatch | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D04 | source_not_declared | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D05 | achieved_over_threshold | deterministic_existing | 10/10 (100.0% [72.2%, 100.0%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D05 | converged_false | deterministic_existing | 10/10 (100.0% [72.2%, 100.0%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D06 | annotated_digit_swap | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D06 | sign_word_flip | referent | 0/60 (0.0% [0.0%, 6.0%]) | 0/60 (0.0% [0.0%, 6.0%]) |
| D06 | unannotated_digit_swap | referent | 0/60 (0.0% [0.0%, 6.0%]) | 0/60 (0.0% [0.0%, 6.0%]) |
| D07 | value_negated | deterministic_new | 0/30 (0.0% [0.0%, 11.4%]) | 30/30 (100.0% [88.6%, 100.0%]) |
| D08 | above_max | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D08 | below_min | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D09 | inf | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D09 | nan | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D09 | null | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D09 | string_value | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D10 | value_perturbed_10pct | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D10 | value_perturbed_1pct | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D10 | wrong_rows_used | deterministic_new | 0/20 (0.0% [0.0%, 16.1%]) | 20/20 (100.0% [83.9%, 100.0%]) |
| D11 | n_deflated | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D11 | n_inflated | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D12 | duplicate_test_id | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D12 | group_overlap | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D12 | id_overlap | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D12 | test_id_not_in_data | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D13 | ci_claim_false | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D13 | improvement_claim_false | deterministic_new | 0/20 (0.0% [0.0%, 16.1%]) | 20/20 (100.0% [83.9%, 100.0%]) |
| D13 | significance_overclaim | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D14 | prose_method_differs | judgement | 0/60 (0.0% [0.0%, 6.0%]) | 0/60 (0.0% [0.0%, 6.0%]) |
| D15 | summary_truncated_mid_block | deterministic_existing | 60/60 (100.0% [94.0%, 100.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D15 | template_placeholder | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D15 | todo_left | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D16 | no_command | deterministic_new | 0/50 (0.0% [0.0%, 7.1%]) | 50/50 (100.0% [92.9%, 100.0%]) |
| D16 | no_environment | deterministic_new | 0/50 (0.0% [0.0%, 7.1%]) | 50/50 (100.0% [92.9%, 100.0%]) |
| D16 | no_seed | deterministic_new | 0/50 (0.0% [0.0%, 7.1%]) | 50/50 (100.0% [92.9%, 100.0%]) |
| D17 | digits_beyond_uncertainty | deterministic_new | 0/60 (0.0% [0.0%, 6.0%]) | 60/60 (100.0% [94.0%, 100.0%]) |
| D18 | median_perturbed_1pct | deterministic_new | 0/20 (0.0% [0.0%, 16.1%]) | 20/20 (100.0% [83.9%, 100.0%]) |
| D18 | percent_sign_flipped | deterministic_new | 0/20 (0.0% [0.0%, 16.1%]) | 20/20 (100.0% [83.9%, 100.0%]) |
| D18 | ratio_inverted | deterministic_new | 0/20 (0.0% [0.0%, 16.1%]) | 20/20 (100.0% [83.9%, 100.0%]) |
| D18 | sd_as_sd_population | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |
| D18 | sd_population_as_sd | deterministic_new | 0/10 (0.0% [0.0%, 27.8%]) | 10/10 (100.0% [72.2%, 100.0%]) |

## False blocks on clean controls

| profile | false-block rate | by check | by rule |
|---|---|---|---|
| `science` | 0/60 (0.0% [0.0%, 6.0%]) | nothing | nothing |
| `science-ai4s` | 0/60 (0.0% [0.0%, 6.0%]) | nothing | nothing |

## Secondary outcomes

| profile | recall (all planted) | any-blocker recall | attribution accuracy | advisory-only detections |
|---|---|---|---|---|
| `science` | 620/2000 (31.0% [29.0%, 33.1%]) | 560/2000 (28.0% [26.1%, 30.0%]) | 560/560 (100.0% [99.3%, 100.0%]) | 60/2000 (3.0% [2.3%, 3.8%]) |
| `science-ai4s` | 1820/2000 (91.0% [89.7%, 92.2%]) | 1430/2000 (71.5% [69.5%, 73.4%]) | 1430/1430 (100.0% [99.7%, 100.0%]) | 390/2000 (19.5% [17.8%, 21.3%]) |

Attribution accuracy is computed among planted instances that were blocked for any rule: the fraction where an expected rule or check fired.

## Wall time and noise floor

| profile | mean ms per instance | max ms | n |
|---|---|---|---|
| `science` | 1.26 | 15.32 | 2060 |
| `science-ai4s` | 2.51 | 5.46 | 2060 |

The layer was run twice on the same bytes and the two row files were byte-identical apart from wall time: run-to-run spread is zero by measurement, not quoted as an interval.

## Environment

```
python:                   3.13.14
platform:                 macOS-26.6.2-arm64-arm-64bit-Mach-O
git sha:                  966a218f0033b0cf8aacea000caff784f7c0e0ef
tree dirty:               True
crossaudit:               /Users/ericdong/Claude/crossaudit-harness-ai4s-v2/src/crossaudit/__init__.py
generation seed:          20261021 (from taxonomy.json)
corpus manifest sha256:   726da406a435ff32c838193786e73cb86072d1b8d45dc139f2ecd2425ac66aca
taxonomy sha256:          d70b5f1c1dd8fab314819dcb6c700008c02337e0f4ce890ad949a95abcd33916
checks contracts sha256:  4e7d565a57bdfd772a41b169d0e5ec7b72dd97d6a9646aa772ada9e6d3676e8d
rows sha256:              24d31e658da682e37a014f7c01784d1e350d2712adeccf3011f4a6d5e60b3f2f
utc start:                2026-10-22T00:05:21+00:00
utc end:                  2026-10-22T00:05:40+00:00
```

## Deviations

- None recorded by the runner.

## Limitations

Fixed text; the full statement is DESIGN.md §6, which binds this record.

- **Synthetic.** Data follow the governing relation plus Gaussian noise; a class caught here is caught on a well-formed increment, nothing more.
- **Single fault.** Each defective instance carries one planted edit; interactions between defects are unmeasured.
- **Planted means known.** Ground truth is exact because it was planted; it says nothing about how often any class occurs in real work.
- **Deterministic layer only.** The model rung is prepared (`run_auditor.py`) but not run in this record.
- **Declarations are honest by construction.** The corpus writes the declarations a compliant generator would; whether real generators do is a separate study.
- **One author, one vendor.** The pack and the corpus were written by the same agent line; cross-vendor review of the measurement code has not happened.
