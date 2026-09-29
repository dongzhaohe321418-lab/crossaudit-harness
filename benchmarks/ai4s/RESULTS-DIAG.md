# A4S-4 results — naming the injected fault at a fixed false-positive budget, on held-out scientific data

Registered at `a6c04af` (`PREREGISTRATION-DIAG.md`), before any held-out item was built and before
any model call. Items built and committed at `5affaed` (manifest `records/ai4s/data_items_ho.json`,
item files mirrored in `records/ai4s/data_items_ho/`, seed 20261001; 280 items, no CSV shared with
A4S-3). Readings: `records/ai4s/diag_readings/` (copied from `~/Documents/Crossaudit/ai4s/runs/
data_audit_ho/`; 8 files, 1,120 readings per family, **no reading missing**). Ledger API value
**$24.41** (`cross` $13.58, `self` $10.83; 2,244 completion events for 2,240 retained readings; the
`self` route runs through Claude Code, so this is the ledger's valuation, not an invoice). The runner
checks the $45 halt every 25 results, so it is not a hard cap; no overrun occurred. Registered
analysis: `analyze_diag.py` → `records/ai4s/diag_results.json`. Supplement after review round 1:
`diag_supplement.py` → `diag_supplement.json` (registered by-fault intervals; post hoc items below)
and `posthoc_diag.py` → `diag_posthoc.json` (post hoc). No amendment was made.

**Revised after review round 1** (`codex-review-a4s4`, `codex-review-paper4`): the first version
called the endpoint "correctly diagnosed". It is not. The registered rule is lexical, and the
reviews found findings it counts that are about something else. This version names the endpoint
for what it measures and reports the counterexamples and a post hoc stricter reading.

## What was measured

280 held-out data items (140 clean, 140 with one of seven injected faults, 20 each), four readings
each by `cross` (the shipped cross-vendor auditor) and `self` (the generator's own model through the
Claude Code CLI), plus A4S-3's frozen documentation-derived validator. The registered endpoint: a
faulty item **names the injected fault** when a flagging reading's BLOCKER text meets the rule in
`diag_match.py` — it names the injected column (both columns for a swap; a duplication term for
duplicated rows). No model judged any outcome. Each family's operating point was fixed on A4S-3
before these items existed: the smallest vote threshold with a development clean-flag rate of at most
10% — `cross` flags at any one of four readings; `self` only when all four flag, and then counts when
**at least one** of those flagging readings meets the rule (not all four).

## Results (registered)

| tier, at its registered operating point | faulty items meeting the rule (of 140) | clean items flagged (of 140) |
|---|---|---|
| validator | **90** (64.3%) [56.4, 72.1] | **0** (0.0%; the bootstrap interval is the degenerate [0, 0], not a bound) |
| `cross`, m = 1 | **57** (40.7%) [32.6, 48.9] | **9** (6.4%) [2.8, 10.5] |
| `self`, m = 4 | **40** (28.6%) [21.7, 35.9] | **14** (10.0%) [5.6, 14.8] |
| validator or `cross` | **105** (75.0%) [67.6, 81.9] | **9** (6.4%) [2.8, 10.5] |

Intervals: 95% percentile bootstrap, items resampled within dataset, 10,000 resamples; four datasets
are too few to resample, so no interval carries between-dataset variation.

**H1 (primary) holds as registered.** Adding `cross` to the validator raises the share of held-out
faulty items meeting the rule by **+10.7 points [6.0, 15.9]**: 15 items added, none lost (exact
McNemar p = 6.1 × 10⁻⁵), at a union clean-flag rate of 6.4%. The registered criterion is the
realised rate at most 10%; the union's interval reaches 10.5%, so this is not assurance that the
population rate is inside the budget. On development the same difference was +12.9 points.

**H2 (secondary; route comparison).** `cross` meets the rule on 12.1 points more of the faulty items
than `self` [4.1, 20.3] (27 against 10 discordant; exact McNemar p = 0.0076), at 9 against 14 clean
flags. Model and sampling change together, and the two sit at different realised rates inside one
budget, so this is not a measure of auditing ability.

**By fault type** (of 20 each; registered intervals, `diag_supplement.json`):

| tier | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|---|
| validator | 5 [7.1, 45.5] | 20 | 20 | 0 | 5 [7.1, 44.4] | 20 | 20 |
| `cross` | 13 [43.5, 85.7] | 14 [47.8, 89.5] | 0 | 0 | 12 [37.5, 81.2] | 18 [75.0, 100] | 0 |
| `self` | 11 [33.3, 76.5] | 12 [38.1, 81.2] | 0 | 3 [0.0, 32.0] | 5 [6.7, 45.0] | 7 [15.0, 56.2] | 2 [0.0, 25.0] |
| union | 13 [43.5, 85.7] | 20 | 20 | 0 | 12 [37.5, 81.2] | 20 | 20 |

(Cells of 0 or 20 have degenerate intervals.) The union's gain is mixed units (F1: 5 → 13) and
swapped columns (F5: 5 → 12). **`self`'s three F4 and two F7 counts are not diagnoses** (below).

**S1.** `cross` flags 63 faulty items at its operating point and 57 meet the rule; `self` flags 46
and 40 meet it.

## What the rule counts that it should not, and misses that it should (post hoc)

The rule is liberal about meaning and strict about wording. It is not a lower bound on correct
diagnosis. Read against the manifest and the item files after the outcome:

* **Counted, but about something else.** `cross` `airfoil.F2.3`: a request for column definitions
  that mentions the column. `self` `supercond.F4.0`, `F4.1`, `F4.2` and `concrete.F7.4`: complaints
  about the row count or the card that mention the column while listing the schema;
  `supercond.F7.3`: a column listing that says the structure is satisfied; `concrete.F5.2`: a
  complaint about missing ranges that lists both swapped columns without saying they are swapped.
  The rule would also accept a text such as "no duplicate rows".
* **Counted, partly wrong.** `cross` `concrete.F5.0`, one of the fifteen items the union adds,
  reports a three-column reassignment including coarse aggregate; the injected fault swaps
  superplasticizer and fine aggregate only.
* **Not counted, but relevant.** `cross` `supercond.F5.0` and `F5.3`, and `self` `ccpp.F5.2`, describe
  impossible values in one of the two swapped columns and name only that one.

**Stricter reading (post hoc; `posthoc_diag.py`).** Requiring each counted finding also to state the
fault itself — a negative value, a −999 or sentinel, a scale or unit, a swap, rounding, shuffling, or
a quoted value equal to an injected cell — leaves `cross` 53 and `self` 32. The four `cross` items it
drops are `airfoil.F2.3` and three power-plant swaps whose findings name both columns as out of range
without saying they are swapped, which is exactly what the validator's range checks say and are
credited for; all four are validator items, so the union is unchanged at 105. **All fifteen items
the union adds state the fault**; the agent's reading of each is recorded in `diag_supplement.json`.
Counting only the fourteen that also give the right columns (dropping `concrete.F5.0`), the contrast
is **+10.0 points [5.4, 15.1]**, 14 against 0 (exact McNemar p = 0.00012). This reading is the
agent's, after the outcome; it is not an independent adjudication.

**The earlier inspection sample** (seed 7; population: each `cross` reading's first BLOCKER text the
rule counts, in file order; `diag_supplement.json` lists the ten): each names the injected column and
describes the injected corruption. It was a sample of counted findings and did not look for
counterexamples; the round-1 report's "the rule is conservative" was wrong and is withdrawn.

**All nine `cross` clean-item flags** are on airfoil items and make one objection: the card gives
each column's name and unit but no definition. A4S-3's four clean flags made the same objection on
the same card. Whether that is a false positive or a fair reading of the task sentence ("states what
each column is") is the delivery dispute A4S-3 already reported; it is counted as a flag here, as
registered, and should not be read as an error.

## What this does and does not show

On these data, adding the model auditor to a documentation-derived validator raises, at a clean-flag
budget fixed in advance, the share of faulty items with a finding that names the injected column;
the fifteen items it adds all state the injected fault on the agent's post hoc reading, fourteen with
the right columns. It does not establish correct diagnosis in general: the registered rule is lexical,
counts findings about other things, and the stricter reading is post hoc and not independently
adjudicated. The items are new draws from A4S-3's four tables and seven synthetic faults, so the
result does not extend to other data, faults or cards. `cross`'s held-out clean-flag rate (6.4%) is
above its development rate (2.9%), all from one card. Provenance: the registration, build and call
times are consistent in the local records; that is not independent timestamp attestation.

## Review

Round 1 (`codex-review-a4s4`) found the arithmetic and chronology correct and the endpoint's name
wrong; this version is its repair. It goes back to review before anything from it enters the paper.
