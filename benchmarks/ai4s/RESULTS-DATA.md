# A4S-3 — auditing scientific data: results (revised after review round 1)

Registration: `PREREGISTRATION-DATA.md`, Amendments 1–3 and the erratum at its end. Registered
analysis: `analyze_data.py` → `records/ai4s/data_results.json`. Post hoc analyses, added after
review round 1 and labelled so wherever used: `posthoc_data.py` → `records/ai4s/data_posthoc.json`
and `clean_flag_exemplars.py` → `records/ai4s/data_clean_flag_exemplars.json`. Items:
`records/ai4s/data_items.json`. Readings: `~/Documents/Crossaudit/ai4s/runs/data_audit/`
(`cross.d1-4.jsonl`, `self.d1-4.jsonl`; all 2,240 planned readings exist and are `ok`; the ledgers
hold 1,126 and 1,125 call events, the difference being retried calls). Spend: $30.61 cumulative,
including the voided run of Amendment 2 ($6.60) and the pilot of Amendment 1 ($0.08), against the
$60 halt of Amendment 3.

## What was measured

280 items of 120 rows each, drawn from four CC BY 4.0 physical-science tables (UCI 165, 291, 294,
464): 140 clean and 140 faulty, five per dataset for each of seven fault types. Each item was read
four times by the shipped cross-vendor auditor (`cross`, `gpt-5.6-terra`) and four times by the
generator's own model (`self`, `claude-haiku-4-5` through the Claude Code CLI), both through the
product's `run_audit` with the shipped constitution. The CSV and the card were supplied to the
auditor as the increment's two named files, `work/data/data.csv` and `work/data/CARD.md` (passed in
memory with a placeholder commit id, not committed to git). Flag = at least one model BLOCKER;
union over the four readings. The comparison is a deterministic validator frozen before any item
was built. It uses the card's stated ranges and non-negativity, plus the spec's list of columns
that are continuous in the source, which the card itself does not state; and it omits one range
the concrete source's README gives (Age, 1 to 365 days). "Clean" means uninjected and filtered for
exact duplicates and, for the power plant, humidity above 100%; it does not mean independently
free of anomalies (a Blast Furnace Slag value of 0.02 kg/m³, genuine in the source, appears in 16
clean concrete items).

## Table 1 — flag rates at K = 4, by fault type (registered flag rule)

Each cell: rate (count/n) [Clopper–Pearson 95%]. The Clopper–Pearson intervals are supplementary:
they treat each cell as a binomial sample and do not carry dataset-level uncertainty. The
registered interval is a bootstrap over items within dataset (dataset-stratified, 10,000, seed
20260926); a bootstrap over the four datasets as clusters was registered as too few to compute, so
between-dataset variation is not captured by any interval here. The stratified bootstrap
degenerates for a single fault type wherever every item of a dataset has the same outcome, so its
per-cell values are not shown; its overall rows are listed below the table.

| fault | validator | cross K=4 | cross + validator | self K=4 |
|---|---|---|---|---|
| F1 mixed units | 30.0% (6/20) [11.9, 54.3] | 85.0% (17/20) [62.1, 96.8] | 85.0% (17/20) [62.1, 96.8] | 75.0% (15/20) [50.9, 91.3] |
| F2 negated values | 100.0% (20/20) [83.2, 100.0] | 70.0% (14/20) [45.7, 88.1] | 100.0% (20/20) [83.2, 100.0] | 85.0% (17/20) [62.1, 96.8] |
| F3 duplicated rows | 100.0% (20/20) [83.2, 100.0] | 0.0% (0/20) [0.0, 16.8] | 100.0% (20/20) [83.2, 100.0] | 65.0% (13/20) [40.8, 84.6] |
| F4 shuffled target | 0.0% (0/20) [0.0, 16.8] | 0.0% (0/20) [0.0, 16.8] | 0.0% (0/20) [0.0, 16.8] | 45.0% (9/20) [23.1, 68.5] |
| F5 swapped columns | 30.0% (6/20) [11.9, 54.3] | 75.0% (15/20) [50.9, 91.3] | 75.0% (15/20) [50.9, 91.3] | 75.0% (15/20) [50.9, 91.3] |
| F6 -999 sentinel | 100.0% (20/20) [83.2, 100.0] | 80.0% (16/20) [56.3, 94.3] | 100.0% (20/20) [83.2, 100.0] | 90.0% (18/20) [68.3, 98.8] |
| F7 rounded to integers | 100.0% (20/20) [83.2, 100.0] | 15.0% (3/20) [3.2, 37.9] | 100.0% (20/20) [83.2, 100.0] | 50.0% (10/20) [27.2, 72.8] |
| **all faulty** | 65.7% (92/140) [57.2, 73.5] | 46.4% (65/140) [38.0, 55.0] | 80.0% (112/140) [72.4, 86.3] | 69.3% (97/140) [60.9, 76.8] |
| **clean (false positives)** | 0.0% (0/140) [0.0, 2.6] | 2.9% (4/140) [0.8, 7.2] | 2.9% (4/140) [0.8, 7.2] | 47.9% (67/140) [39.3, 56.5] |

Bootstrap (items within dataset, 10,000, seed 20260926), overall rows:
- validator recall: 65.7% [57.9, 73.6]
- validator FP: 0.0% [0.0, 0.0]
- cross K=4 recall: 46.4% [38.6, 54.3]
- cross K=4 FP: 2.9% [0.7, 5.7]
- cross+validator recall: 80.0% [73.6, 86.4]
- cross+validator FP: 2.9% [0.7, 5.7]
- self K=4 recall: 69.3% [64.3, 75.0]
- self K=4 FP: 47.9% [42.9, 52.9]
- cross K=1 recall: 35.0% [28.4, 41.8]
- cross K=1 FP: 0.7% [0.2, 1.4]
- self K=1 recall: 54.1% [48.2, 60.0]
- self K=1 FP: 27.1% [23.4, 31.1]

K = 1 to 3 are additional summaries, not registered outcomes: for `cross`, recall 35.0%, 40.5%,
43.9% at false positives 0.7%, 1.4%, 2.1%; for `self`, 54.1% → 69.3% at 27.1% → 47.9% from K = 1 to
4. (One registered-analysis value outside this report, `cross` K = 1 F6's bootstrap lower bound, is
stored as 63.7 and is 63.75 exactly; a floating-point rounding artefact.)

## Flags that do not concern the injected fault (post hoc)

`cross` raised one kind of BLOCKER that is about the card rather than the data: that the airfoil
card gives column identifiers and units without describing what each column measures. It is the
only BLOCKER on 8 airfoil items, 4 clean and 4 faulty (`airfoil.F1.1`, `F1.2`, `F2.4`, `F7.0`). On
those four faulty items the flag is not a detection of the injected fault. Counting only items with
at least one other BLOCKER (a post hoc rule, not the registered one):

| | registered flag rule | fault-relevant flags (post hoc) |
|---|---|---|
| `cross`, all faulty | 65/140 (46.4%) | 61/140 (43.6%) |
| `cross`, F1 / F2 / F7 | 17 / 14 / 3 of 20 | 15 / 13 / 2 of 20 |
| `cross` ∪ validator | 112/140 (80.0%) | 110/140 (78.6%) |
| `cross`, clean | 4/140 (2.9%) | 0/140 |

## What only the model flags

The validator misses 48 of the 140 faulty items: all 20 shuffled targets (F4), 14 of 20 mixed-unit
items (F1) and 14 of 20 swapped-column items (F5). The six F1 and six F5 items it does catch are the
ones where the fault pushed a value out of a stated range, below zero, or (one F5) made a declared
continuous column integer-valued.

| among the validator's 48 misses | F1 (14) | F4 (20) | F5 (14) | total |
|---|---|---|---|---|
| `cross` flags (registered rule) | 11 | 0 | 9 | 20 |
| of which fault-relevant (post hoc) | 9 | 0 | 9 | 18 |
| `self` flags (registered rule) | 9 | 9 | 10 | 28 |

All 18 were read; each names the faulted quantity (by column name or in words) and describes the
corruption: thousand-fold values beside normal ones, a count column holding fractions, columns whose
values fit each other's documented quantity, and in one case (`supercond.F1.4`) an arithmetic
argument that three atoms spanning a 135 pm radius range cannot have a mean radius of 1.6 pm, the
cell converted to ångströms. Had the validator used the Age range
the concrete README states, it would also catch `concrete.F5.4` (Age values 594 to 945 days, swapped
into range violation), raising its recall to 93/140 (66.4%) at 0 clean flags and leaving 17
fault-relevant model-only catches (post hoc sensitivity).

`self`'s 28 were not adjudicated for fault relevance, so what they detect is unestablished. It flags
47.9% of clean items, and on shuffled targets its rate (45.0%, 9/20) is no higher than that, so its
flag rate alone does not show detection; individual `self` findings do identify real faults (for
example the humidity sentinel in `ccpp.F6.0`).

## Localisation (registered: a flagging BLOCKER contains the faulted column's name)

| | F1 | F2 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|
| `cross`: named / flagged | 9/17 | 10/14 | – (0 flagged) | 13/15 | 15/16 | 2/3 |
| `self`: named / flagged | 9/15 | 12/17 | 5/9 | 6/15 | 14/18 | 3/10 |

F3 has no column. The substring rule misses a column named by paraphrase and counts a mention made
for another reason: `airfoil.F1.2` counts as localised because its documentation complaint names
`frequency_Hz`, the faulted column, without identifying the corruption.

## Flags on clean items, read one by one

The registration forbids calling a clean-item flag wrong without reading it. Every BLOCKER text on a
clean item was read.

**`cross`: 4 items (all airfoil), one text each.** Each asks for fuller column definitions than the
airfoil card gives, a fair reading of the task ("which states what each column is"); the airfoil
card is the sparsest of the four. Two of them (`airfoil.clean.11`, `.33`) also say the card does not
identify the sound-pressure column as the target, which is false: the card states "Target column:
scaled_sound_pressure_dB". None of the four asserts anything about the data.

**`self`: 67 items (superconductivity 34, concrete 26, power plant 7), 304 texts.** Claims here are
item-level only, and each flagged clean item is placed in exactly one group (post hoc;
`clean_flag_exemplars.py`, which names the exemplars, checks each against the item's CSV, and runs a
negative control showing each check fails on a file that matches the claim):

| group | items | what the findings claim |
|---|---|---|
| refuted | **48** | at least one unwithdrawn statement that the CSV contradicts: a data row count other than 120 (e.g. 100, 101, 122, 150), 38 items; a named column, the target values or the header's closing quote missing, 7; a field count of 8, 2; a truncated final row, 1 |
| delivery dispute | 12 | the CSV was not delivered as a file (only shown as contents, not on disk, path not established); no refutable statement found |
| withdrawn | 2 | the one refutable allegation is withdrawn in the same text (`concrete.clean.8`); in `concrete.clean.24` only in part, and its surviving claim that the columns do not match the card is not counted |
| documentation | 5 | only documentation or requirement judgements (empty range cells, missing descriptions or provenance, a sample rather than the full table); `concrete.clean.18` also calls genuine early-age strengths of about 6.5 MPa implausible |

The 48 is a lower bound: items in the other groups may carry statements not examined here. The
delivery disputes are not counted as false: the harness passes the files' named contents in memory
and writes nothing to disk, so a finding that the file was not "physically" delivered disputes the
protocol rather than misreading the data. We give no text-level totals: an earlier text-level
labelling was found in review to misapply its own rubric and was withdrawn. One observation about
the data among the texts is true: `concrete.clean.29` notes the Blast Furnace Slag value of 0.02,
which is in the source.

## Construction cues found in review

Unit conversion by floating-point arithmetic leaves long binary tails (e.g. `290.84999999999997`).
In the airfoil and power-plant tables these appear only in faulty F1 items (2 of 5 and 3 of 5) and
in no clean item, so they could mark a converted cell; in the concrete and superconductivity tables
clean items carry such tails too. None of `cross`'s flagging F1 texts gives the representation as
its reason; they argue from scale, range or neighbouring rows. That does not show the cue had no
influence. No other difference between clean and faulty items besides the fault was found in
review: row order, formatting of whole numbers and cards are identical within dataset, and no
label or hash reaches the prompt.

## Reading

1. **On data, the shipped auditor flags faults a card-derived validator misses, at a low
   false-positive cost, for two of the three fault types the validator cannot see.** Of the
   validator's 14 missed mixed-unit items and 14 missed swapped-column items it flagged 9 and 9 for
   the fault itself (post hoc; 11 and 9 under the registered rule), at 2.9% flags on clean data, all
   four about the card. It flagged no shuffled target (0/20). It is weaker than the validator on
   every fault the validator was written for (duplicates 0/20, rounding 3/20, negatives 14/20,
   sentinels 16/20, against 20/20 each).
2. **The two tiers are complementary.** Registered rule: validator alone 65.7% at 0.0% flags on
   clean items; auditor alone 46.4% at 2.9%; union 80.0% at 2.9%. Post hoc fault-relevance rule,
   which also removes the four clean flags: auditor 43.6% at 0.0%; union 78.6% at 0.0%.
   Each catches items the other does not, which is the design premise of the product's science
   profile (the model reads, code verifies); the union is not dominated by either part.
3. **The same-vendor route did not work as a data auditor in this configuration.** It flags 47.9% of
   clean items; for at least 48 of those 67 items one of its findings states, without withdrawing it,
   a row count, field count, missing column or truncation that the file contradicts, and 12 more
   dispute that the file was delivered at all. This is
   one model through one route (the CLI, with its own added context and default sampling), not a
   statement about the vendor.
4. **Both cross-row fault types were missed by the shipped auditor.** Duplicated rows and a shuffled
   target were never flagged (0/20 each). This is consistent with Bendinelli et al.'s report that
   cleaning agents find row-level errors more readily than errors spanning rows, though their
   setting (Python-equipped agents, performance feedback) differs; it is not evidence of a general
   incapacity, since several of the auditor's mixed-unit findings compare rows.

## What this does not license

A claim about scientific data in general (four tables, seven synthetic faults, 120-row samples); a
claim about what the model "understands"; a comparison with a validator written with knowledge of
the faults, or one that uses every range the source documentation states (the post hoc Age
sensitivity above is the one such check made). The `cross` numbers are one model at its default
sampling; `self` differs from Act 2's same-vendor family in route and sampling.

## Deviations and instrument history

* Amendment 1: card and CSV named one column differently; the task was reframed so the data is the
  deliverable; three pilot readings discarded. The amendment was committed with the rebuilt
  manifest (erratum).
* Amendment 2: the files first sat outside the audited scope, so the product rendered
  `NOTHING_TO_AUDIT` into the auditor's prompt; 313 `cross` readings voided. Draw-1 flag tallies of
  the void run had been seen as progress counts; the fix follows from the product's scope rule.
* Amendment 3: halt raised from $45 to $60 before it was reached. Its progress note misstates
  `self`'s draw (erratum).
* The analysis script was committed after 278 valid `self` readings existed. The agent states it had
  not analysed them; no record can verify that (erratum; the first version of this report said
  "before any valid reading existed").
* The OpenAI account ran out of credit mid-study; the `cross` run was stopped and resumed after the
  owner topped it up.
* The halt is not strictly fail-closed (erratum); no cap was reached.
* Review round 1 (not quotable) led to: the post hoc fault-relevance analysis, the Age-range
  sensitivity, the construction-cue disclosure and the corrections above. Review round 2 (not
  quotable) found that a text-level labelling of the clean-item flags misapplied its own rubric; it
  was withdrawn and replaced by the item-level exemplars, and the chronology wording was narrowed.
  Review round 3 (not quotable) found that some exemplars only doubted on-disk delivery or withdrew
  their allegation; those were replaced by directly refutable texts where they exist, the other six
  items were removed from the count (62 → 56), and the record now checks each kind against the file.
  Review round 4 (not quotable) found that delivery disputes were still counted as refuted facts and
  that the column check did not verify the column named; delivery disputes now form their own group
  (56 → 48 refuted), the column check verifies the named column, and a negative control was added.
