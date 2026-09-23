# A4S-3 — auditing scientific data: results

Registration: `PREREGISTRATION-DATA.md` with Amendments 1–3. Analysis: `analyze_data.py`
(committed before any valid reading existed), output `records/ai4s/data_results.json`. Items:
`records/ai4s/data_items.json`. Readings: `~/Documents/Crossaudit/ai4s/runs/data_audit/`
(`cross.d1-4.jsonl`, `self.d1-4.jsonl`, 1,120 each, every one `ok`). Spend: $30.61 cumulative,
including the voided run of Amendment 2 ($6.6) and the pilot of Amendment 1 ($0.08), against the
$60 halt of Amendment 3.

## What was measured

280 items of 120 rows each, drawn from four CC BY 4.0 physical-science tables (UCI 165, 291, 294,
464): 140 clean and 140 faulty, five per dataset for each of seven fault types. Each item was read
four times by the shipped cross-vendor auditor (`cross`, `gpt-5.6-terra`) and four times by the
generator's own model (`self`, `claude-haiku-4-5` through the Claude Code CLI), both through the
product's `run_audit` with the shipped constitution, the data as `work/data/data.csv` and the card
as `work/data/CARD.md`. Flag = at least one model BLOCKER; union over the four readings. The
comparison is the deterministic validator frozen from the card before any item was built.

## Table 1 — flag rates at K = 4, by fault type

Each cell: rate (count/n) [exact Clopper–Pearson 95%]. The registered interval (bootstrap over
items within dataset) is listed below the table for the overall rows. For single fault types it
degenerates wherever every item of a dataset has the same outcome (e.g. `cross` F3 and F4 give
[0, 0]), so the exact interval is the one to read per cell.

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

K = 1 against K = 4 for `cross`: recall 35.0% → 46.4%, false positives 0.7% → 2.9% (K = 2: 40.5%
at 1.4%; K = 3: 43.9% at 2.1%). For `self`: 54.1% → 69.3% at 27.1% → 47.9%.

## What only the model catches

The validator misses 48 of the 140 faulty items: all 20 shuffled targets (F4), 14 of 20 mixed-unit
items (F1) and 14 of 20 swapped-column items (F5). The six F1 and six F5 items it does catch are
the ones where the fault pushed a value out of a declared range, below zero, or (one F5) made a
continuous column integer-valued.

| | F1 missed by validator | F4 missed | F5 missed | total |
|---|---|---|---|---|
| validator misses | 14 | 20 | 14 | 48 |
| `cross` flags among them | **11** | **0** | **9** | **20** |
| `self` flags among them | 9 | 9 | 10 | 28 |

So the union of the shipped auditor with the validator reaches 80.0% (112/140) at the auditor's own
2.9% false-positive rate, against 65.7% for the validator alone at 0.0%. Every one of the 20
additional catches is a mixed-unit or swapped-column item that stayed inside the declared ranges.

`self`'s 28 cannot be read the same way: `self` flags 47.9% of clean items, and its rate on F4
(45.0%, 9/20) is no higher than that. Its F4 flags are not evidence of detection.

## Localisation (a flagging BLOCKER names the faulted column; case-insensitive substring)

| | F1 | F2 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|
| `cross`: named / flagged | 9/17 | 10/14 | – (0 flagged) | 13/15 | 15/16 | 2/3 |
| `self`: named / flagged | 9/15 | 12/17 | 5/9 | 6/15 | 14/18 | 3/10 |

F3 (duplicated rows) has no column. The string match is conservative: a finding that names a
column by a paraphrase ("the strength column") does not count.

## Flags on clean items, read one by one

The registration forbids calling a clean-item flag wrong without reading it. All were read.

**`cross`, 4 items, all airfoil.** Each says the card gives column identifiers and units but not
what the columns measure (e.g. that `frequency_Hz` is the measured frequency). That is true: the
airfoil card's unit column carries units only, while the other three cards' descriptions are
fuller. It is a property of the card we wrote, not of the data, and it is a fair reading of the task
("which states what each column is"). None of the four asserts anything false about the data.

**`self`, 67 items (supercond 34, concrete 26, ccpp 7, airfoil 0), 304 BLOCKER texts.** Classified
by pattern and then read; every text the patterns did not settle was read in full.

* **62 items carry at least one false statement about the files.** The dominant ones: that
  `work/data/data.csv` is absent, or present only "inline" and "not as a file" (both files were
  committed in every reading); that rows have 8 fields under a 9-field header (every row parses to 9;
  the concrete header's last name contains a comma and is quoted); that the file is truncated or
  lacks a final newline (it does not); that values fall outside the card's stated range (the
  validator finds none on any clean item).
* **5 items carry only documentation points**: the card's empty "stated range" cells, missing
  column descriptions, missing provenance or collection notes, and that 120 rows are a sample of a
  larger public table. These are true of the card; the card does not say the file is a sample.
* **One text found a real oddity in clean data**: `concrete.clean.29` contains a Blast Furnace Slag
  value of 0.02 kg/m³, which is in the UCI source itself (the smallest nonzero value in that column;
  the next is 11.0). The same item also carries false claims in other readings.

## Reading

1. **The shipped auditor adds real value on data at a low false-positive cost, and only on some
   faults.** On the faults a card-derived validator cannot see, it caught 11 of 14 mixed-unit items
   and 9 of 14 swapped-column items, at 2.9% false positives, all four of them true remarks about
   the card. It caught no shuffled target (0/20) and no duplicated rows (0/20), and it is worse than
   the validator on every fault the validator was built for (F2 70%, F6 80%, F7 15% against 100%).
2. **The two tiers are complementary, not substitutes.** The validator alone: 65.7% at 0.0%. The
   auditor alone: 46.4% at 2.9%. Together: 80.0% at 2.9%. The design rule of the product's science
   profile (the model reads, code verifies) is supported here in the sense that each tier catches
   what the other does not; the union is not dominated by either part.
3. **The same-vendor route does not work as a data auditor in this configuration.** It flags almost
   half of clean items, and 62 of its 67 clean flags assert something false about the files. Its
   higher recall is not detection: on the shuffled target, its rate equals its clean rate. This is
   one model through one route (the CLI, with its own added context and default sampling); it is not
   a statement about the vendor.
4. **Cross-row faults are the blind spot.** Duplicated rows and a shuffled target need comparison
   across rows. The shipped auditor never flagged either, which matches Bendinelli et al.'s
   observation that agents cleaning corrupted tables find row-level errors and miss errors spanning
   rows.

## What this does not license

A claim about scientific data in general (four tables, seven synthetic faults, 120-row samples);
a claim that the model "understands" units (it flagged mixed units; what it wrote was read only for
the clean items and for localisation); a comparison with a validator written with knowledge of the
faults (ours was frozen from the card before any item existed, and a validator that checked row
uniqueness across rows is exactly what caught F3). The `cross` numbers are one model at its
default sampling; `self` differs from Act 2's same-vendor family in route and sampling.

## Deviations and instrument history

* Amendment 1 (before any valid reading): card and CSV named one column differently; task framing
  changed so the data is the deliverable. Three pilot readings discarded.
* Amendment 2: the files first sat outside the audited scope, so the product rendered
  `NOTHING_TO_AUDIT` into the auditor's prompt; 313 `cross` readings voided. Draw-1 flag tallies
  of the void run had been seen as progress counts; the fix follows from the product's scope rule
  alone.
* Amendment 3: halt raised from $45 to $60 on cost alone, before it was reached and before any
  outcome was computed.
* The OpenAI account ran out of credit mid-study; the `cross` run was stopped and resumed after the
  owner topped it up, with no reading lost (every reading `ok`).
