# A4S-4 results — correct diagnosis at a fixed false-positive budget, on held-out scientific data

Registered at `a6c04af` (`PREREGISTRATION-DIAG.md`), before any held-out item was built and before
any model call. Items built and committed at `5affaed` (manifest `records/ai4s/data_items_ho.json`,
seed 20261001; 280 items, no CSV shared with A4S-3). Readings: `~/Documents/Crossaudit/ai4s/runs/
data_audit_ho/` (8 files, 1,120 readings per family, **no reading missing**). Spend **$24.41**
(halt $45). Analysis: `analyze_diag.py` → `records/ai4s/diag_results.json`. No amendment was made.

## What was measured

280 held-out data items (140 clean, 140 with one of seven injected faults, 20 each), four readings
each by `cross` (the shipped cross-vendor auditor) and `self` (the generator's own model through the
Claude Code CLI), plus A4S-3's frozen documentation-derived validator. A faulty item is **diagnosed**
when the executable rule in `diag_match.py` finds, in a flagging reading's BLOCKER text, the injected
column (both columns for a swap; a duplication term for duplicated rows). **No model judged any
outcome.** Each family's operating point was fixed on A4S-3 before these items existed: the smallest
vote threshold with a development clean-flag rate of at most 10% — `cross` flags at any one of four
readings, `self` only when all four flag.

## Results

| tier, at its registered operating point | faulty items diagnosed (of 140) | clean items flagged (of 140) |
|---|---|---|
| validator | **90** (64.3%) [56.4, 72.1] | **0** (0.0%) |
| `cross`, m = 1 | **57** (40.7%) [32.6, 48.9] | **9** (6.4%) [2.8, 10.5] |
| `self`, m = 4 | **40** (28.6%) [21.7, 35.9] | **14** (10.0%) [5.6, 14.8] |
| validator or `cross` | **105** (75.0%) [67.6, 81.9] | **9** (6.4%) [2.8, 10.5] |

Intervals: 95% percentile bootstrap, items resampled within dataset, 10,000 resamples; four datasets
are too few to resample, so no interval carries between-dataset variation.

**H1 (primary) holds.** Adding `cross` to the validator raises the share of held-out faulty items
correctly diagnosed by **+10.7 points [6.0, 15.9]**: 15 items diagnosed only by the union, none only
by the validator (exact McNemar p = 6.1 × 10⁻⁵), at a union clean-flag rate of 6.4%, inside the 10%
budget. On development the same difference was +12.9 points.

**H2 (secondary; route comparison).** At their operating points `cross` diagnoses **12.1 points
more** of the faulty items than `self` [4.1, 20.3] (27 against 10 discordant; exact McNemar
p = 0.0076), at 9 against 14 clean flags. The two families sit at different realised false-positive
rates within the same budget, and model and sampling change together, so this is not a measure of
auditing ability.

**By fault type** (diagnosed of 20): validator F1 5, F2 20, F3 20, F4 0, F5 5, F6 20, F7 20;
`cross` F1 13, F2 14, F5 12, F6 18, and none of F3, F4, F7; `self` F1 11, F2 12, F4 3, F5 5, F6 7,
F7 2. As in A4S-3, the union's gain comes from mixed units (F1: 5 → 13) and swapped columns
(F5: 5 → 12), which the validator sees only when they push a value out of a declared range. No tier
diagnosed a shuffled target except `self` on 3 of 20.

**S1.** `cross` flags 63 faulty items at its operating point and the rule diagnoses 57; `self` flags
46 and the rule diagnoses 40.

## What the rule counted (post hoc inspection, not a registered analysis)

* **The six `cross` flags the rule did not count** (S1): three are the card-documentation request
  described below, one objects that the file has fewer rows than the source dataset, and two are
  swapped-column items where the finding names one of the two swapped columns and describes its
  impossible values. The rule requires both, so on these two it is stricter than a reader would be.
* **A seeded sample of ten findings the rule counted** (seed 7) was read in full: each names the
  injected column and describes the injected corruption (a −999 sentinel, negated values, a column
  in millimetres among metres, a pressure column holding humidity-range values). None counted a
  finding about something else.
* **All nine `cross` clean-item flags** are on airfoil items and make one objection: the card gives
  each column's name and unit but no definition. A4S-3's four clean flags made the same objection on
  the same card. Whether that is a false positive or a fair reading of the task sentence ("states
  what each column is") is the delivery dispute A4S-3 already reported; it is counted as a flag here,
  as registered.

## What this does and does not show

It is the held-out, executably adjudicated version of A4S-3's post hoc finding: on these data, a model
auditor added to a documentation-derived validator correctly diagnoses faults the validator misses,
at a clean-flag rate inside a budget fixed in advance. It does not show this for other data, other
fault types or other cards: the items are new draws from A4S-3's four tables and seven synthetic
faults. The diagnosis rule is lexical and necessary rather than sufficient; the inspection above
found it conservative on the items read, not validated in general. `cross`'s held-out clean-flag
rate (6.4%) is above its development rate (2.9%), all from one card.

## Review

This report goes to independent cross-vendor review before anything from it enters the paper.
