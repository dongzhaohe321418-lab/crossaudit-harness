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

## Amendment 1 (after development-split audits and scoring; before any test-split reading-only audit)

**What was seen.** All development-split audits (agentic and reading-only, both auditors) and the registered
scores on the development split (H1 +7.1 [+1.0, +16.1]; H2 +4.8 [0.0, +11.3]; H3 not estimable on
development tables; H4 +3.8 [0.0, +9.2]). Test-split agentic audits were in progress; no test score had been
computed.

**Why.** In reading-only mode the Codex route still exposed its shell tools: 80 of 224 development readings by
gpt-5.6-terra invoked a tool and were discarded as registered, so whether a reading survived could depend on
the item. Separately, `score_e3.py` dropped an item for an auditor unless every one of its readings was valid,
and dropped the whole item if one auditor was missing; the registration did not state a missing-data rule.

**Changes.** (1) Codex reading-only audits run with `--disable shell_tool --disable unified_exec`, which
removes every tool from the session (checked: no tool events), matching the Claude reading route, which
already ran with every tool disabled. All earlier Codex reading-only rows (development only) are kept in the
records but excluded by a route tag; every Codex reading-only reading, on both splits, is made under the new
route. (2) Missing data: each auditor's value is the union over its valid readings; an item's value is the
mean over the auditors with at least one valid reading; an item is dropped only if no auditor has one.
Missing readings are reported by mode and auditor. Hypotheses, thresholds, items, validators and the agentic
arm are unchanged.

## Amendment 2 (after Amendment 1's development rerun; before any test score)

**What was seen.** The development scores after Amendment 1 (H1 +7.1 [+1.0, +16.1], H4 +3.6 [-2.7, +9.8])
and, in the rerun, that the Codex reading route still invoked tools in 58 of 224 readings: on inspection,
`web_search` calls looking for the original UCI files. No test score has been computed.

**Why.** Web search let an auditor look up the clean source data, which no data team auditing a delivered
table would be able to do for its own data, and it was available in the Codex agentic route too. The Claude
agentic route allowed Bash without a network sandbox. Neither route kept a transcript of commands, so access
to the network, or to files outside the item (including other items and the injection manifest), cannot be
ruled out for any earlier reading.

**Changes.** (1) Every Codex call runs with web search disabled (`-c web_search="disabled"`, checked); the
reading route also disables the shell tools; the agentic route keeps the read-only sandbox, which has no
network. (2) Claude's agentic route runs inside Claude Code's sandbox with no allowed network domains
(checked: curl and Python HTTP both refused), with Bash and Read only, and emits a stream-json transcript.
(3) Each agentic reading runs in a fresh temporary copy of the item holding only `data.csv` and `CARD.md`.
(4) Every command and file read is stored; a reading whose commands name the network, a path outside its own
copy (other temporary or user directories, the item store, the repository) or any non-shell tool is
discarded as a failed attempt; raw transcripts are kept. (5) Every earlier E3 reading, on both splits and in
both modes, is excluded by a route tag and kept in the records; all audits are rerun under the new routes.
Hypotheses, thresholds, items, validators and Amendment 1's missing-data rule are unchanged.

## Amendment 3 (after the Amendment 2 rerun; test scores under Amendment 2 have been computed)

**What was seen, in order.** The Amendment 2 rerun finished on both splits. The registered analysis was then
run on both splits (test, Amendment 2 routes: H1 +1.5 [0.0, +3.4], not supported; H2 +19.2 [+4.8, +35.4],
not supported; H3 0.0; H4 -2.2 [-7.1, +2.2]). Only afterwards were the discarded readings inspected: 174 of
829 Codex agentic readings (21%; dev 85, test 89) had been discarded as out of scope, and none of Claude's.
The commands show the auditor looking for the clean source: `curl` to the UCI archive and GitHub mirrors,
and `find`/`rg` over the user's home directory, the temporary directory holding other items' copies, and
system directories. Several located and read the clean source files kept on the machine for item building.
Seven kept readings also searched system directories in ways the filter did not match.

**Why.** Discarding on attempt makes missingness depend on the item and the auditor (attempts concentrate where
the auditor cannot settle a question from the file), which biases every contrast involving the Codex agentic
arm; a post hoc command filter is also incomplete. The defect is in the isolation, not in the hypotheses.

**Changes.** (1) Every agentic reading runs its CLI inside a macOS seatbelt profile (`code/icml/isolate.py`):
reads are denied under the user's home directory, the temporary directories and mounted volumes, except the
reading's own fresh copy (now under a dedicated root, itself unreadable to other readings) and the files the
CLI needs (its installation and isolated login home); writes are denied outside the copy and the CLI's own
state; all network is denied except one loopback port, where an egress proxy admits HTTPS CONNECT only to the
vendor API hosts and logs every request. Checked before any reading: `ls ~`, the temporary directory, other
copies, `curl` and Python HTTP to the UCI archive and to an arbitrary host are all refused; a search of the
system directories found no copy of any E3 source dataset. Because seatbelt cannot nest, Codex runs with its
own sandbox off and Claude without its sandbox settings, inside this profile. (2) Out-of-scope attempts are
recorded per reading and reported (a secondary, descriptive outcome: rate of attempts to obtain the source,
by auditor), but no longer discard the reading, since under (1) an attempt cannot return information.
(3) All agentic readings, on both splits, are rerun under route `isolated-v3`; Amendment 2 agentic rows are
kept and excluded by the route tag. Reading-only rows from Amendment 2 are kept: that route has no tools.
(4) The Amendment 2 test results above are reported in the appendix beside the Amendment 3 results.
Hypotheses, thresholds, items, validators, the scoring code and the missing-data rule are unchanged.
