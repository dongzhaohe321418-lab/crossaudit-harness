# A4S-4 — Correct diagnosis at a fixed false-positive budget, on held-out scientific data

Registered 2026-09-24, **before any item of this study was built and before any model call of this
study**. Amendments are numbered and committed before the step they govern.

## Why

An independent referee of the paper (`reviews/cross-vendor/codex-review-paper3/report-r1.md` and
`-r2.md` in the paper repository) asked for one experiment: a held-out scientific audit measuring
**correctly diagnosed** faults, not flags, at a **prespecified false-positive budget**, with
**independent human or executable adjudication**. No human is available to this programme, so this
study uses executable adjudication: every fault is injected, its column and parameters are in the
manifest, and a fixed rule decides from the finding text whether the fault was named.

## Development and held-out sets

* **Development:** A4S-3's 280 items and its archived readings (`records/ai4s/data_items.json`,
  `~/Documents/Crossaudit/ai4s/runs/data_audit/`). Used only to fix the operating points below and to
  calibrate the diagnosis rule. Nothing from it is a result of this study.
* **Held-out:** 280 new items built by A4S-3's construction, unchanged (`build_data_items_ho.py`,
  which differs from `build_data_items.py` only in paths and the seed), seed **20261001**: the same
  four CC BY 4.0 tables, 35 clean and 35 faulty items per table (five per fault type, F1–F7), 120
  rows each. Manifest: `records/ai4s/data_items_ho.json`. These items have never been audited.

## Readings

`data_audit_run_ho.py`: A4S-3's runner, unchanged except paths, run id prefix and halt. Two families,
**K = 4** readings of every held-out item each: `cross` (`openai:gpt-5.6-terra`, the shipped route)
and `self` (`anthropic:claude-haiku-4-5-20251001` through the Claude Code CLI, A4S-1 Amendment 1).
Same task sentence and card, same shipped general rulebook, same audited scope as A4S-3 after its
Amendment 2. A reading that errors is retried by the runner (up to 7 attempts); after all passes, any
item still missing a reading is reported, and the analysis uses the readings that exist.

**Budget and halt:** $45 on this study's ledgers (A4S-3 cost $30.61 for the same design). The runner
halts at $45.

## The diagnosis rule (executable; frozen here)

`diag_match.py`, committed with this file. A faulty item is **diagnosed by a reading** when the
reading flags (at least one BLOCKER) and at least one of its BLOCKER texts:

* F1 mixed units, F2 negated values, F4 shuffled target, F6 sentinel, F7 rounding: names the
  injected column (an alias from the frozen table; word-bounded; case-insensitive except the
  all-capitals power-plant headers, which match case-sensitively);
* F5 swapped columns: names both swapped columns;
* F3 duplicated rows: contains a duplication term.

The validator is scored by the same function on its fired check names joined into one text.

**This rule is necessary, not sufficient, for a correct diagnosis.** It checks that the finding
points at the injected column (or, for F3, at duplication); it does not check that the finding says
what is wrong with it. It can count a finding that names the right column for a wrong reason, and
miss one that describes the right column without naming it. That is the price of adjudication no
model performs; the report states it wherever a diagnosis count appears.

**Calibration on development (no model call; `calibrate_diag.py`):** the rule diagnoses 60 of A4S-3's
faulty items for `cross` against A4S-3's post hoc fault-relevant count of 61 (by fault: F1 16 vs 15,
F2 13 vs 13, F5 13 vs 15, F6 16 vs 16, F7 2 vs 2), 65 for `self`, and 91 for the validator.

## Operating points (fixed on development, applied unchanged to held-out)

A family flags an item at threshold **m** when at least m of its K = 4 readings flag. The budget is a
**clean-item flag rate of at most 10%**. Each family's operating point is the smallest m whose
development clean-flag rate is within budget (`analyze_diag.py --dev`):

| family | development clean-flag rate at m = 1, 2, 3, 4 | operating point |
|---|---|---|
| cross | 2.9%, 0.0%, 0.0%, 0.0% | **m = 1** (any reading) |
| self | 47.9%, 35.0%, 18.6%, 7.1% | **m = 4** (all four readings) |
| validator | 0.0% (deterministic) | fires |

The budget is 10% rather than 5% because no `self` threshold reaches 5% on development; it is fixed
here, before held-out readings exist. The held-out clean-flag rate at each operating point is
reported with its interval; it may exceed the budget, and H1 says what then happens.

## Hypotheses

**H1 (primary).** On held-out faulty items, the union of the validator and `cross` at its operating
point correctly diagnoses more items than the validator alone. Estimand: paired difference in the
share of the 140 faulty items diagnosed. **Holds iff** the 95% interval's lower end exceeds 0
**and** the union's held-out clean-flag rate is at most 10%. Otherwise H1 is killed and reported as
killed. (On development the difference is +12.9 points; that number is the reason for the
hypothesis, not evidence for it.)

**H2 (secondary; a route comparison, model and sampling change together).** Paired difference in
diagnosed share between `cross` at m = 1 and `self` at m = 4 on held-out faulty items, with its
interval, two-sided. No direction is predicted, and neither sign is read as auditing ability.

**Also reported, no test:** each tier's diagnosed count and share with interval, by fault type; each
tier's held-out clean-flag count and rate with interval; for each model family, faulty items it flags
at its operating point without diagnosing (S1); exact McNemar p for H1 and H2 beside the intervals.

## Statistics

Intervals: 95% percentile bootstrap, 10,000 resamples, items resampled within dataset (A4S-3's
unit; four datasets are too few to resample, so no interval carries between-dataset variation), seed
20261001. No multiplicity correction: H1 is the single primary; H2 and the descriptives are labelled
secondary.

## What this study cannot show

It uses A4S-3's four tables and fault types, so "held-out" means new items from the same
distribution, not a new domain. The diagnosis rule is lexical. The operating points are integer vote
thresholds on K = 4, so the two families sit at different realised false-positive rates inside the
same budget; the budget is matched, the rates are not. One generator is not involved (the items are
constructed), but each family is one model through one route.

## Review

The report goes to independent cross-vendor review before anything from it enters the paper.
