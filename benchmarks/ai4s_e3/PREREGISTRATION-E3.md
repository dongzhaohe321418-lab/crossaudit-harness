# Preregistration — study E3: what a model adds to strong deterministic data validation

Committed before any E3 audit reading is analysed. Items, both validators and the item manifest were built
before this commit by `build_e3.py` (no model calls); the validators' outputs on all items were printed at build
time and are disclosed as seen. One pilot reading per primary auditor on one development item (ccpp, 1,200
rows, F4) was made to check the reply format; it is excluded from analysis. Departures are numbered amendments.

## Question

A4S-3 found that a card-derived validator and the model auditor flag different faults on four small tables.
E3 asks whether the model still adds detections when the deterministic tier is strong (profile checks against a
reference sample, as data teams deploy), on datasets the study has never used, and on tables too large to read.

## Items

Twelve CC BY 4.0 UCI tables (`spec_e3.py`): four development tables from A4S-3 (concrete, airfoil, combined
cycle power plant, superconductivity) and eight held-out test tables (gas turbine emissions, steel plant energy,
appliances energy, household power, wine quality, abalone, electrical grid stability, air quality). Each table's
clean pool is split once into a reference sample (30%, at most 3,000 rows) and an item pool. Items have 120,
1,200 or 12,000 rows where the pool allows (size at most 70% of the pool). Per table and size: 14 clean items and
two items for each of seven faults (mixed units on 20% of rows, negated values on 1% of rows, 10% duplicated rows,
30% of target values permuted, two columns swapped, -999 sentinels on 5% of rows, one continuous column rounded).
168 development and 532 test items. Item directories have opaque names and contain only `data.csv` and
`CARD.md`. Stated ranges that the source data itself violate were removed from the cards before building (six
gas-turbine ranges; listed in `items.json`).

## Deterministic tier (frozen)

`card validator`: card ranges, non-negativity from units, sentinels, exact duplicates, all-integer values in a
column that is non-integer in the reference (only when that is improbable by chance). `profile validator`: the
card validator plus fixed thresholds against the reference sample — more than 2% of values outside the
reference 0.1-99.9% range widened by 10%; a median shift above 0.5 reference IQR; a target-feature correlation
change with Fisher z above 4.5 and absolute change above 0.2. Thresholds were chosen before any test item was
built and checked only on development clean items (5 of 84 flagged).

## Model tier

Auditors: `gpt-5.6-terra` (Codex CLI, medium) and `claude-sonnet-5-5` (Claude Code CLI). **Agentic**: run in the
item directory with shell and Python access (Codex read-only sandbox; Claude Bash and Read only), one reading per
item and auditor, all sizes. **Reading**: the same instructions with both files inlined and tools disabled,
120-row items only, two readings per item and auditor. Replies are JSON with typed findings (fault type, columns,
rows, evidence); each reading gets at most two attempts.

## Endpoints (scored by code, `score_e3.py`)

* **Flag**: at least one BLOCKER.
* **Localised detection** (faulty items): a BLOCKER whose fault type equals the injected type and whose columns
  include the injected column (F5: either swapped column; F3: no column required).
* Validators: flag = any check fired; localised = a fired check whose type and column match (sentinel, negative,
  range or profile:oop for F1/F6, negative for F2, duplicates for F3, profile:corr on any feature or profile:med
  of the target for F4, any check naming either column for F5, integer for F7).
* Model value per item: the mean over the two auditors.

## Hypotheses (test items)

* **H1 (primary).** Localised detection of (profile validator OR agentic model) exceeds that of the profile
  validator alone, on faulty test items. Paired item difference averaged over auditors; 95% interval from a
  bootstrap that resamples datasets and items within dataset (10,000 draws, seed 20261112). Supported if the
  lower bound exceeds 0.
* **H2.** The union's clean-flag rate on clean test items is at most 10 points above the profile validator's:
  supported if the paired interval's upper bound is below 10.
* **H3.** The H1 gain holds at 12,000 rows (the four tables large enough): lower bound above 0 on that subset.
* **H4.** At 120 rows, agentic localised detection (its one reading) exceeds reading-only localised detection
  (the union of its two readings): paired difference averaged over auditors, lower bound above 0. The arms
  differ in tools and in the number of readings, so H4 compares configurations.
* Secondary, without correction: per fault type, per table, per auditor; the card validator in place of the
  profile validator.

## What would weaken the paper's account

H1 failing would mean that once the deterministic tier is strong, the model adds nothing localised on these
faults; the paper would say so, and the A4S-3 complementarity would be a property of a weak validator.
