# Ceiling 4 — the referent rule raises the shipped auditor's union flag coverage at K = 8, and charges for it on the clean stratum

Study 20. Preregistered at `benchmarks/code/ceiling4/PREREGISTRATION.md` (8174337), committed
before any model call, with the driver `ceiling4.py` (a32d5b0) committed before the first
call too; Amendment 1 (e0b5b24) was committed during `cross-R` draw 1, before any result of
that draw was read, and adds one `cross-T` reading to the end of the ladder. Substrate,
instances, solutions, audit path, strata and the union-of-K protocol are ceiling 1's, frozen
(`RESULTS-CEILING.md`, D162); `cross` is ceiling 1's family, reused unchanged as the
comparator, and no file of ceiling 1's or study 18's is modified by this study.

Two routes were run through the product's provider broker on ceiling 1's scope of 110 P and
150 C instances: `cross-R`, the shipped cross auditor (`openai:gpt-5.6-terra`) with
`loop.REFERENT_RULE` appended to the shipped constitution, at K = 8; and, under Amendment 1,
`cross-T`, the shipped constitution unchanged, one reading, with every finding's text
archived. Records: `records/ceiling4/cache/` (one row per reading: ids, digests, counts and
outcomes, no text), `records/ceiling4/numbers.json` and `records/ceiling4/tables.md` (both
written by `report_ceiling4.py --run`; the tables below are that file, spliced verbatim by
`ceiling4/splice_tables.py`), the two adjudication label files
`records/ceiling4/L1-amendment1.csv` and `L2-amendment1.csv`, and the archive
`~/Documents/Crossaudit/study-data/wt-ceiling4-runs/` (the per-arm ledgers, `run.log`, and
`findings-cross-R-d*.jsonl` and `findings-cross-T-d1.jsonl`, which carry the finding texts
and are never committed).

Every estimator is study 18's or ceiling 1's, imported rather than reimplemented. Intervals:
a k/n rate carries the 95% Wilson interval and the 95% problem-cluster percentile bootstrap
at the preregistered seed 20260913 with 10,000 resamples; a subset-averaged curve point, a
single-draw mean, a mixed rate and a difference of fitted asymptotes are means, not k/n, and
carry the cluster interval only. The cluster interval is the primary one throughout, with
ceiling 1's caveat inherited: the percentile bootstrap's coverage under this clustered design
has not been validated by simulation. Counts of five or fewer are quoted as counts.

<!-- BEGIN PREAMBLE (records/ceiling4/tables.md) -->
Intervals: a k/n rate carries the 95% Wilson interval and the problem-cluster percentile bootstrap (10,000 resamples, seed 20260913); a subset-averaged curve point, a single-draw mean, a mixed rate and a difference of fitted asymptotes are means, not k/n, and carry the cluster interval only (2,000 resamples for mixed). The cluster interval is the primary one throughout. Beside each paired contrast the tables quote Tango's score interval and a grid-unconditional interval (an exact test maximised over a 41-point nuisance grid with no bound on the missed supremum — ceiling 1 Amendment 5's own qualification); both ignore clustering. The cluster sign-flip sampler keeps ceiling 1's frozen seed: report_ceiling.BOOT_SEED + 7 (ceiling 1's frozen 20260908 + 7 = 20260915), left unchanged.
<!-- END PREAMBLE -->

## 1. The preregistered outcomes

Flag = at least one BLOCKER finding, ceiling 1's rule. Union of K readings.

<!-- BEGIN TABLE1 (records/ceiling4/tables.md) -->
### Table 1 — union of K readings, BLOCKER rule (Wilson; problem-cluster bootstrap)

| family | K | P union recall | Wilson | cluster | C union FP | Wilson | cluster |
|---|---|---|---|---|---|---|---|
| `cross` (shipped constitution, ceiling 1) | 8 | 33/110 = 30.0% | 22.2–39.1 | 20.0–40.9 | 24/150 = 16.0% | 11.0–22.7 | 10.1–22.3 |
| **`cross-R` (shipped + referent rule)** | 8 | 67/110 = 60.9% | 51.6–69.5 | 48.6–72.5 | 55/150 = 36.7% | 29.4–44.6 | 28.5–44.8 |
| `cross-T` (shipped, texts archived — Amendment 1) | 1 | 9/110 = 8.2% | 4.4–14.8 | 3.6–14.2 | 4/150 = 2.7% | 1.0–6.7 | 0.7–5.4 |
<!-- END TABLE1 -->

<!-- BEGIN TABLE2 (records/ceiling4/tables.md) -->
### Table 2 — the preregistered contrasts (§2): union at K on the same instances, paired per instance

| hypothesis | stratum | K | A − B (points) | cluster 95% | Tango 95% | grid-unconditional 95% | A only | B only | McNemar exact p | cluster sign-flip p |
|---|---|---|---|---|---|---|---|---|---|---|
| **H20a (primary)** `cross-R` − `cross` | P | 8 | +30.9 | 19.1, 43.1 | 20.8, 41.0 | 16.8, 42.7 | 38 | 4 | 5.65e-08 | 1.00e-05 (sampled, 200000 draws, seed 20260915) |
| H20c `cross-R` − `cross` | C | 8 | +20.7 | 12.8, 28.8 | 13.1, 28.7 | 10.0, 30.1 | 36 | 5 | 7.84e-07 | 5.00e-06 (sampled, 200000 draws, seed 20260915) |
<!-- END TABLE2 -->

<!-- BEGIN KILL (records/ceiling4/tables.md) -->
**The preregistered kill** (§2): *H20a's interval includes zero, OR cross-R's eight-reading union falls inside cross's K=8 cluster interval [19.8, 40.7]*. H20a's cluster interval includes zero: **no**. `cross-R`'s eight-reading union 60.9% lies inside [19.8, 40.7]: **no**. The kill **did not fire**. (The same `cross` interval recomputed at this study's seed is [20.0, 40.9]; the kill is evaluated against the registered one.)
<!-- END KILL -->

* **H20a (primary): positive.** Union BLOCKER recall, `cross-R` minus `cross`, paired per
  instance on
  P at K = 8 = **+30.9 points, problem-cluster 95% [19.1, 43.1]**;
  38 instances blocked by `cross-R` only, 4 by `cross` only;
  exact McNemar p = 5.7e-08; cluster sign-flip p = 1.0e-05 (sampled, 200,000 draws,
  at `report_ceiling`'s frozen seed, which this study did not change). Ceiling 1's
  paired-binary checks beside it, both ignoring clustering, and "grid-unconditional" naming
  an exact test maximised over a 41-point nuisance grid with no bound on the missed
  supremum, which is ceiling 1 Amendment 5's own qualification:
  Tango [20.8, 41.0]; grid-unconditional [16.8, 42.7].
  The discordance is not one-signed, so the percentile bootstrap's bound is not the artefact
  ceiling 1 warns about and the cluster interval stands as the primary one. Eight readings
  under the rule block
  67 of 110 = 60.9% (Wilson 51.6–69.5; cluster 48.6–72.5)
  against
  33 of 110 = 30.0% (cluster 20.0–40.9)
  for the same auditor under the shipped constitution.
* **The preregistered kill did not fire.** Both of its clauses are false: H20a's cluster
  interval excludes zero, and `cross-R`'s eight-reading
  union 60.9% is above [19.8, 40.7],
  the `cross` K = 8 cluster interval the preregistration names. On the registered rule, this
  study does not license "the rule moves one reading, not the ceiling".

<!-- BEGIN TABLE3 (records/ceiling4/tables.md) -->
### Table 3 — the curves: union rate at each K with its problem-cluster interval (P; then C)

| family | stratum | K=1 | K=2 | K=3 | K=4 | K=5 | K=6 | K=7 | K=8 |
|---|---|---|---|---|---|---|---|---|---|
| `cross` (shipped constitution, ceiling 1) | P | 10.7 [5.1–17.3] | 15.0 [8.3–22.6] | 18.3 [10.8–26.6] | 21.2 [13.1–30.1] | 23.8 [15.1–33.2] | 26.0 [16.9–36.0] | 28.1 [18.4–38.4] | 30.0 [20.0–40.9] |
| `cross` (shipped constitution, ceiling 1) | C | 4.5 [2.4–7.0] | 7.1 [4.2–10.3] | 9.2 [5.7–13.1] | 10.9 [6.8–15.5] | 12.4 [7.9–17.5] | 13.7 [8.7–19.2] | 14.9 [9.5–20.9] | 16.0 [10.1–22.3] |
| **`cross-R` (shipped + referent rule)** | P | 43.3 [32.4–54.6] | 50.3 [38.9–61.7] | 54.2 [42.5–65.7] | 56.6 [44.7–68.3] | 58.3 [46.3–70.0] | 59.5 [47.4–71.2] | 60.3 [48.2–72.0] | 60.9 [48.6–72.5] |
| **`cross-R` (shipped + referent rule)** | C | 23.6 [17.1–30.3] | 28.2 [21.1–35.4] | 30.6 [23.2–38.1] | 32.3 [24.8–39.9] | 33.6 [25.9–41.4] | 34.8 [26.8–42.6] | 35.8 [27.7–43.8] | 36.7 [28.5–44.8] |
<!-- END TABLE3 -->

<!-- BEGIN TABLE4 (records/ceiling4/tables.md) -->
### Table 4 — H20b: the fitted asymptote (ceiling 1 §1.2, constrained), the registered flattening bar, and the exchange rate

| family | A (P) | A cluster 95% | τ | R² | max abs residual (points) | ZIBB π, ceiling 1 §1.2's secondary [cluster, 1,000 resamples] | K=7→K=8 gain (points) [cluster] | flattened by ceiling 1's bar (gain ≤ 1.0) | asymptote is an extrapolation | raw union at K_max (the sturdier number) | Δrecall/ΔFP K=1→K_max [cluster] (EXPLORATORY) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `cross` (shipped constitution, ceiling 1) | 31.5% | 21.5–46.0 | 3.27 | 0.9678 | 2.37 | 100.0% [100.0–100.0; 0 all-zero] | 1.93 [1.13, 2.82] | no | yes | 33/110 = 30.0% [20.0–40.9] | 1.68 [0.94–3.08] |
| **`cross-R` (shipped + referent rule)** | 58.6% | 46.8–70.2 | 0.85 | 0.8681 | 2.82 | 100.0% [65.8–100.0; 0 all-zero] | 0.57 [0.11, 1.04] | yes | no | 67/110 = 60.9% [48.6–72.5] | 1.35 [0.82–2.24] |
<!-- END TABLE4 -->

<!-- BEGIN ASYMPTOTE-DIFF (records/ceiling4/tables.md) -->
A(`cross-R`) − A(`cross`) on P, the constrained fit refitted inside every one of the 10,000 problem-cluster resamples: **+27.1 points, cluster [10.9, 39.0]** (10,000 resamples fitted). Method: the constrained fit of ceiling 1 §1.2, refitted inside each resample; A is bounded to [0, 1] inside the objective, so an interval that reaches 100.0 has reached the constraint, not a measurement.
<!-- END ASYMPTOTE-DIFF -->

* **H20b (the fitted asymptotes, not the slope): the two families fall on opposite sides of
  ceiling 1's flattening bar, so their asymptotes are not comparable in kind.**

  **What H20b does and does not establish.** It establishes a positive difference between the
  two *registered fitted asymptotes*, conditional on the single-exponential form. It does
  **not** establish a difference in the true ceiling, and this report may not say it does.
  Three reasons, the first two of which are in this section's own numbers. `cross` has not
  flattened, so one of the two terms is an extrapolation. Heterogeneous low-probability
  detection can look like a ceiling over eight readings: an instance found with probability
  0.02 per reading is missed by all eight about 85% of the time, so a curve can flatten
  because the remaining instances are *rare*, not because they are *unreachable*. And this
  study's own secondary estimator says there is no ceiling at all — the ZIBB fit puts the
  non-inflated share at essentially 1.0 for **both** families (`cross` π = 0.9999999999989448,
  `cross-R` π = 0.9999999999896982 on P, cluster [0.658, 1.0]), that is, it finds no evidence of a
  never-detectable class in either arm. Whatever the referent rule moves, it is not shown to
  be a limit. `cross-R` passes the
  registered bar — its K = 7 to K = 8
  gain 0.57 points, cluster [0.11, 1.04],
  is at most 1.0 point — so
  A(`cross-R`) = 58.6% (cluster 46.8–70.2, τ = 0.85)
  is a fit to a curve that has flattened, not an extrapolation. `cross` fails the bar exactly
  as ceiling 1 reported, with
  gain 1.93 points, cluster [1.13, 2.82],
  so
  A(`cross`) = 31.5% (cluster 21.5–46.0, τ = 3.27)
  **is an extrapolation past the readings taken** and is labelled one here as it was there.
  Their difference
  **+27.1 points, cluster [10.9, 39.0]**,
  refitted inside every resample, therefore inherits that caveat on one of its two terms and
  is the weaker of the two numbers on offer. The sturdier number is the one H20a already
  gives: the raw union at K = 8,
  67 of 110 = 60.9% (cluster 48.6–72.5)
  against
  33 of 110 = 30.0% (cluster 20.0–40.9),
  which assumes no functional form at all. The saturating form fits `cross-R` less well than
  it fits `cross`
  (R² 0.8681 against 0.9678, largest absolute residual 2.82 points against 2.37),
  and the fitted asymptote for `cross-R` falls slightly below its own observed K = 8 union,
  which is a property of the fit and not a measurement of anything. Ceiling 1 §1.2's
  secondary estimator disagrees with both families' saturation fits: the ZIBB mixing weight
  runs to its constrained bound,
  π = 100.0% (cluster 100.0–100.0) for `cross`
  and
  π = 100.0% (cluster 65.8–100.0) for `cross-R`,
  which is the upward instability §1.2 predicted in advance and which ceiling 1 and study 18
  also recorded. Where the two estimators disagree §1.2 says to prefer the conservative one.
  **Round 1 of review found the sentence that used to stand here numerically false**: it said
  the raw union at K = 8 is more conservative still, which holds for `cross` (30.00% against a
  fitted 31.50%) but **not** for `cross-R`, whose raw union of **60.91% exceeds its own fit of
  58.62%**. For `cross-R` the fit is the conservative estimator and the raw union is not.
* **H20c (the cost): the rule is expensive on the clean stratum.** Union false positives on
  C at K = 8: **+20.7 points, cluster [12.8, 28.8]**
  (36 vs 5; McNemar p = 7.8e-07; sign-flip p = 5.0e-06; Tango [13.1, 28.7]; grid-unconditional [10.0, 30.1]),
  that is
  55 of 150 = 36.7% against 24 of 150 = 16.0%
  of clean instances blocked by at least one of eight readings. The quantity the product
  actually constrains is worse: `cross-R`'s
  single-draw false-positive rate on C is 23.6% (cluster 17.1–30.3),
  against the product bar of 6.7% (`explore/PREREGISTRATION.md` §5), and
  0 of 8 individual draws sit at or below that bar. On this substrate the referent rule as
  written is not shippable at the product's own false-positive constraint, whatever it does
  for recall.
* **H20d (the residual): adding `cross-R` removes nearly half of it, and it is the
  unexercised-edge half.** P instances blocked by no reading of any measured family fall
  from 56 after study 18 to 32, over 40 draws of 6 families:
  **32 of 110 = 29.1%** (Wilson 21.4–38.2; cluster 18.5–40.2).
  24 instances leave it, and by ceiling 1 §1.5's categories they are
  1 spec-misreading, 23 unexercised-edge —
  which is the category the rule was written to address. No instance is new to the residual.
  `cross-T` is excluded from this count by Amendment 1, which keeps it out of every H20
  contrast; it is also the same constitution as `cross` and so would not be an independent
  family.

<!-- BEGIN TABLE5 (records/ceiling4/tables.md) -->
### Table 5 — H20c: the single-draw false-positive rate on C against the product bar (6.7%)

| family | mean over the K draws [cluster] | per-draw flagged instances (of 150) | draws at or below the bar |
|---|---|---|---|
| `cross` (shipped constitution, ceiling 1) | 4.5% [2.4–7.0] | 5, 7, 5, 10, 4, 7, 8, 8 | 8 of 8 |
| **`cross-R` (shipped + referent rule)** | 23.6% [17.1–30.3] | 38, 31, 38, 34, 32, 37, 36, 37 | 0 of 8 |
<!-- END TABLE5 -->

## 2. Secondaries

<!-- BEGIN TABLE6 (records/ceiling4/tables.md) -->
### Table 6 — the any-finding rule (§3, preregistered secondary): a flag rate, not a defect-naming rate

| family | K | P union | Wilson | cluster | single-draw P [cluster] | C union | Wilson | cluster | single-draw C [cluster] |
|---|---|---|---|---|---|---|---|---|---|
| `cross` (shipped constitution, ceiling 1) | 8 | 38/110 = 34.5% | 26.3–43.8 | 24.1–45.5 | 11.5 [5.9–18.1] | 29/150 = 19.3% | 13.8–26.4 | 12.8–26.2 | 5.2 [3.0–7.8] |
| **`cross-R` (shipped + referent rule)** | 8 | 67/110 = 60.9% | 51.6–69.5 | 48.6–72.5 | 43.4 [32.5–54.7] | 59/150 = 39.3% | 31.9–47.3 | 31.1–47.6 | 24.1 [17.6–30.8] |
| `cross-T` (shipped, texts archived — Amendment 1) | 1 | 9/110 = 8.2% | 4.4–14.8 | 3.6–14.2 | 8.2 [3.6–14.2] | 4/150 = 2.7% | 1.0–6.7 | 0.7–5.4 | 2.7 [0.7–5.4] |
<!-- END TABLE6 -->

<!-- BEGIN TABLE7 (records/ceiling4/tables.md) -->
### Table 7 — `mixed` (K/2 `cross` + K/2 `cross-R`) against each family alone at the same total

| stratum | total K | mixed | cluster 95% | `cross` alone [cluster] | `cross-R` alone [cluster] |
|---|---|---|---|---|---|
| P | 2 | 44.1% | 33.0–55.1 | 15.0% [8.3–22.6] | 50.3% [38.9–61.7] |
| P | 4 | 51.6% | 40.4–62.4 | 21.2% [13.1–30.1] | 56.6% [44.7–68.3] |
| P | 6 | 55.9% | 44.6–66.9 | 26.0% [16.9–36.0] | 59.5% [47.4–71.2] |
| P | 8 | 58.8% | 47.4–69.8 | 30.0% [20.0–40.9] | 60.9% [48.6–72.5] |
| C | 2 | 24.6% | 18.1–31.3 | 7.1% [4.2–10.3] | 28.2% [21.1–35.4] |
| C | 4 | 29.4% | 22.2–36.6 | 10.9% [6.8–15.5] | 32.3% [24.8–39.9] |
| C | 6 | 32.1% | 24.8–39.6 | 13.7% [8.7–19.2] | 34.8% [26.8–42.6] |
| C | 8 | 34.2% | 26.6–41.8 | 16.0% [10.1–22.3] | 36.7% [28.5–44.8] |
<!-- END TABLE7 -->

<!-- BEGIN TABLE8 (records/ceiling4/tables.md) -->
### Table 8 — H20d: the residual across 6 families (40 draws), by ceiling 1 §1.5's category

| category | after study 18 (5 families) | with `cross-R` added | left the residual |
|---|---|---|---|
| spec-misreading | 8 | 7 | 1 |
| timeout | 2 | 2 | 0 |
| unexercised-edge | 46 | 23 | 23 |
| **total** | **56** | **32** | **24** |

Residual rate with `cross-R` added: 32/110 = 29.1% (Wilson 21.4–38.2; cluster 18.5–40.2). New to the residual: 0.
<!-- END TABLE8 -->

* **The any-finding rule** (§3, preregistered here as a secondary, and a flag rate rather
  than a defect-naming rate):
  `cross-R` 67 of 110 = 60.9% (cluster 48.6–72.5)
  and
  `cross` 38 of 110 = 34.5% (cluster 24.1–45.5).
  For `cross-R` the two unions on P are the same set of instances, not merely the same count:
  the any-finding set contains the BLOCKER set by construction and the counts are equal. The
  reason is the severity grading, which under the referent rule almost never stops short of
  BLOCKER:
  671 of the 2,080 `cross-R` readings returned at least one finding and 664 returned at
  least one BLOCKER.
  So on this arm the looser rule adds almost nothing, unlike study 18's Anthropic families
  where the gap between the two rules was the whole story. **Neither complete eight-reading
  union was adjudicated; `cross-R` draw 1 and the separate `cross-T` reading were**, so neither
  rate is shown to name a defect. Round 2 corrected this again: the previous wording, "no text
  from these eight-reading unions was adjudicated", is literally false for `cross-R`, whose
  adjudicated draw 1 contributes to that union. The generator carried the same claim and so
  regenerated it unchanged; it is fixed there too.

  **The adjudicated results in §3 rest on labels whose production can no longer be audited.**
  L2's raw reply, prompt, launcher and execution log lived only under a session scratchpad and
  were destroyed before the first review's finding could be repaired. The sheet, key and
  label-file hashes verify and every number reproduces from the labels; how L2 produced them
  does not. That caveat is repeated here, beside the results it qualifies, rather than left in
  Amendment 2 where a reader of §3 would not meet it.
* **`mixed`** (Table 7): at every matched total, a mixture of `cross` and `cross-R` readings
  sits above `cross` alone and below `cross-R` alone, on both strata. Spending half the
  readings on the shipped constitution buys nothing here that spending all of them on the
  rule does not buy more of, and it does not recover the false-positive rate either.
* **Reply format**: not a factor. Every reading is one accepted reply.

## 3. Amendment 1 — the shipped auditor's own findings, adjudicated

`cross-T` is one reading of the shipped constitution with texts archived, added so the
paper's first-ranked gap — has anyone checked that `cross`'s flag rate names the defects? —
could be adjudicated at all. Ceiling 1's harness dropped the finding texts before caching, so
no such reading existed.

Its flag rate on P is
9 of 110 = 8.2% (Wilson 4.4–14.8; cluster 3.6–14.2),
a single reading, consistent with ceiling 1's `cross`
single-draw mean of 10.7% (cluster 5.1–17.3).
It returned a finding of
any severity on 9 of 110 = 8.2% (cluster 3.6–14.2)
of P instances, the same set.

The adjudication Amendment 1 registers **has been run**. The 80 blind sheet items — every
finding of any severity on a P instance in `cross-T` draw 1 and in `cross-R` draw 1 — were
answered by both raters: L1 the author, L2 `gpt-6-astra` through the Codex CLI, billed to a
subscription and not to this project's API key, so L2 enters no ledger of this study and
nothing of the $30 cap. `ceiling4/adjudication_sheet.py` built the sheet; the sheet stays
outside the repository because it quotes specifications, solutions and finding texts, and
`ceiling4/adjudication-manifest.json` carries the sheet's sha256, the key's, both label
files' sha256s, both raters' identities, L2's model, harness and endpoint, and the note that
L2 was subscription-billed. The returned labels are committed at
`records/ceiling4/L1-amendment1.csv` and `records/ceiling4/L2-amendment1.csv`.

**Read Table 9 before Table 10.** Every rate in Table 10 is built on the two raters' answers,
and those answers agree less well than study 19's did.

<!-- BEGIN TABLE9 (records/ceiling4/tables.md) -->
### Table 9 — Amendment 1's adjudication: the two raters against each other, over 80 blind sheet items

| question | scope | both yes | L1 only | L2 only | both no | agreement | Cohen κ |
|---|---|---|---|---|---|---|---|
| naming (study 19's registered question) | all 80 items | 39 | 7 | 16 | 18 | 57/80 = 71.2% | **0.391** |
| recognition, "defect" (registered HERE by Amendment 1) | the 39 consensus naming-yes items | 39 | 0 | 0 | 0 | 39/39 = 100.0% | undefined |

L1 answered yes on 46 items, L2 on 55; of the 23 disagreements 16 are L1-no/L2-yes and 7 are L1-yes/L2-no, so L2 is the more inclusive rater. kappa is undefined where both raters gave every item the same label: expected agreement is 1 and there is no marginal variation to correct for. That is perfect concordance, not kappa = 1.
<!-- END TABLE9 -->

The two raters agree on
57 of the 80 items, Cohen κ = 0.391
on the naming question. That is weak agreement, and it is far below the κ = 0.897 study 19
reported for the same question with the same two rater roles — that figure is quoted from
study 19 and is not recomputed here, since study 19's records are not on this branch. A rate
built on a κ of 0.391 is a rate two careful readers would not have produced the same way, and
the numbers below should be read with that in front of them, not behind them.

The disagreement is **asymmetric**, not noise in both directions.
L1 answered yes on 46 items and L2 on 55, and of the 23 disagreements 16 are L1-no/L2-yes,
so L2 is the more inclusive rater. A property of these findings is part of the reason, though
**not demonstrably the whole of it**: the first review re-read the items and found judgments
that are inconsistent within each rater as well, so the sentence that used to attribute the
disagreement to the findings "rather than" the raters claimed more than the labels support.
What the items do show is that many of them name an input class *adjacent* to the hidden
failing class — "the
visible tests never construct X", where X is near to, but not the same as, the class on which
the hidden suite actually fails. Where a finding names a neighbouring class, "does this name
the class on which the hidden test fails" stops having an obvious answer, and two careful
readers can answer it differently in good faith. Study 19's sheet presented fewer such cases,
which is the most likely reason its κ was higher; that comparison is the author's reading of
the two sheets and not a measurement.

The recognition question is not where the trouble is. On the
39 items both raters called named, both labelled all 39 "defect" — perfect concordance,
and κ is **undefined** there rather than 1, because with no marginal variation there is no
expected agreement to correct for. So the naming question carries the whole disagreement, and
the defect-asserting rate differs from the naming rate only through L2's four non-defect
labels, all of which fall on `cross-R` items.

<!-- BEGIN TABLE10 (records/ceiling4/tables.md) -->
### Table 10 — P instances named, and P instances with a defect-asserting finding, under each reader rule (rate over all 110 P instances; Wilson; problem-cluster bootstrap)

| route | question | rule | instances | rate | Wilson | cluster |
|---|---|---|---|---|---|---|
| `cross-T` | names the failing class | consensus | 5 of 110 | 4.5% | 2.0–10.2 | 0.9–8.9 |
| `cross-T` | names the failing class | L1 | 5 of 110 | 4.5% | 2.0–10.2 | 0.9–8.9 |
| `cross-T` | names the failing class | L2 | 7 of 110 | 6.4% | 3.1–12.6 | 1.8–11.8 |
| `cross-T` | names the failing class | either | 7 of 110 | 6.4% | 3.1–12.6 | 1.8–11.8 |
| `cross-T` | **asserts it is a defect** | consensus **(registered primary)** | 5 of 110 | 4.5% | 2.0–10.2 | 0.9–8.9 |
| `cross-T` | **asserts it is a defect** | L1 | 5 of 110 | 4.5% | 2.0–10.2 | 0.9–8.9 |
| `cross-T` | **asserts it is a defect** | L2 | 7 of 110 | 6.4% | 3.1–12.6 | 1.8–11.8 |
| `cross-T` | **asserts it is a defect** | either | 7 of 110 | 6.4% | 3.1–12.6 | 1.8–11.8 |
| `cross-R` | names the failing class | consensus | 26 of 110 | 23.6% | 16.7–32.4 | 14.3–33.9 |
| `cross-R` | names the failing class | L1 | 29 of 110 | 26.4% | 19.0–35.3 | 16.4–36.9 |
| `cross-R` | names the failing class | L2 | 36 of 110 | 32.7% | 24.7–41.9 | 21.8–44.4 |
| `cross-R` | names the failing class | either | 39 of 110 | 35.5% | 27.1–44.7 | 24.3–47.2 |
| `cross-R` | **asserts it is a defect** | consensus | 26 of 110 | 23.6% | 16.7–32.4 | 14.3–33.9 |
| `cross-R` | **asserts it is a defect** | L1 | 29 of 110 | 26.4% | 19.0–35.3 | 16.4–36.9 |
| `cross-R` | **asserts it is a defect** | L2 | 32 of 110 | 29.1% | 21.4–38.2 | 18.8–40.4 |
| `cross-R` | **asserts it is a defect** | either | 35 of 110 | 31.8% | 23.9–41.0 | 21.1–43.1 |

Denominators: `cross-T`'s one reading returned a finding on 9 of the 110 P instances (10 findings) and `cross-R`'s draw 1 on 49 (70 findings); the rates above are over all 110 either way. The consensus rule counts a disputed item as NOT named, which is the preregistered direction.
<!-- END TABLE10 -->

<!-- BEGIN KILL-A (records/ceiling4/tables.md) -->
**Amendment 1's kill.** Amendment 1 adopts the memo's kill: below 20 of 110 on cross-T's registered primary, the headline becomes 'flag rate 30.0%, defect-naming recall X%'. `cross-T`'s registered primary is 5 of 110, below 20, so the kill **FIRED** — and it fires under every one of the eight ways of reading that rate (two questions by four reader rules): the count runs from 5 to 7 of 110, every one below 20. The verdict therefore does not rest on the raters' disagreement, even though the point estimate does. **It does not rest on the adjudication at all**: only 9 of 110 instances drew any finding on this arm, so the largest defect-asserting count available under perfect adjudication was 9, already below 20. **The headline the kill prescribes juxtaposes two different quantities and must carry that warning wherever it is quoted**: the flag rate is a union over eight readings and the defect-naming rate is one reading whose texts were adjudicated; the eight readings' texts were never archived, so no naming rate exists for them and none may be inferred by scaling this one. The matched comparison inside this single reading is 9 instances flagged against 5 adjudicated as asserting the defect.
<!-- END KILL-A -->

**What this establishes, exactly.** On **one** reading, the shipped auditor returned a finding
on 9 of 110 defect instances and asserted the actual defect on 5 to 7 of them:
5 of 110 = 4.5% (Wilson 2.0–10.2; cluster 0.9–8.9)
under the preregistered consensus rule, and
7 of 110 = 6.4% (Wilson 3.1–12.6; cluster 1.8–11.8)
if either rater's yes is allowed. It does **not** establish a naming rate for the 30.0%
union at eight readings, and the two must not be set beside each other as if they were the
same kind of number: that union is eight draws and this is one, its readings' texts were
never kept by ceiling 1's harness, and nothing here licenses carrying 4.5% onto it or scaling
it up by the number of draws. What would make them comparable is adjudicating the texts of
eight `cross-T` readings, which has not been run.

`cross-R` draw 1 is adjudicated beside it, as Amendment 1 directs. Under consensus it names
the failing class on
26 of 110 = 23.6% (Wilson 16.7–32.4; cluster 14.3–33.9)
and asserts a defect on the same 26; by either rater's yes it is 39 of 110 for naming and
35 of 110 for defect-asserting. This too is one draw, and it is not the K = 8 union of §1.

## 4. Cost, run history, deviations, limits

<!-- BEGIN TABLE11 (records/ceiling4/tables.md) -->
### Table 11 — reply format, provider denials and ledger cost, per draw

| draw | readings | prompt digest = study 2's base | malformed after repair | repair re-asks (ledger calls − readings) | replies > 300 output tokens | denied attempts retried (rows / distinct instances) | ledger $ |
|---|---|---|---|---|---|---|---|
| `cross-R-d1` | 260 | 0 | 0 | 0 | 187 | 0 / 0 | 2.8872 |
| `cross-R-d2` | 260 | 0 | 0 | 0 | 199 | 0 / 0 | 2.0777 |
| `cross-R-d3` | 260 | 0 | 0 | 0 | 204 | 0 / 0 | 2.1656 |
| `cross-R-d4` | 260 | 0 | 0 | 0 | 192 | 0 / 0 | 2.0965 |
| `cross-R-d5` | 260 | 0 | 0 | 0 | 197 | 760 / 95 | 2.3926 |
| `cross-R-d6` | 260 | 0 | 0 | 0 | 191 | 2080 / 260 | 2.5667 |
| `cross-R-d7` | 260 | 0 | 0 | 0 | 193 | 2080 / 260 | 1.9684 |
| `cross-R-d8` | 260 | 0 | 0 | 0 | 193 | 2080 / 260 | 2.0904 |
| `cross-T-d1` | 260 | 260 | 0 | 0 | 35 | 0 / 0 | 1.5926 |
<!-- END TABLE11 -->

<!-- BEGIN COST (records/ceiling4/tables.md) -->
Total from the 9 project ledgers: **$19.84** over 2,340 calls for 2,340 readings, against the $30 cap. Note: the per-row cost_usd stamped into the cache is unreliable where a draw needed several passes (study 18's finding, inherited); the ledgers are the cost of record.
<!-- END COST -->

* **Cost**:
  **$19.84** from the nine project ledgers (2,340 calls for 2,340 readings),
  against the preregistered $30 cap, which was not reached. The per-row `cost_usd` stamped
  into the cache is unreliable where a draw needed several passes (study 18's finding,
  inherited), so the ledgers are the cost of record.
* **Reply format and the prompt digests**:
  2,340 readings, none malformed and none re-asked
  — `invalid_reason` is empty on every row, and the ledgers hold exactly one auditor call per
  reading, so the product's bounded repair prompt was never used. The positive control on
  which constitution each route ran:
  all 2,080 `cross-R` readings carry a prompt digest
  different from study 2's committed holistic-cross reading of the same instance, and
  all 260 `cross-T` readings carry the same digest,
  which is what appending the referent rule to one route and not to the other should produce.
* **Run history**: the ladder was run in two invocations of the same resumable loop. In the
  first, the provider rate-limited the run: draw 5 lost 95 instances and draws 6, 7 and 8 were
  denied outright, exhausting the eight passes with the breaker cooling between them, for
  7,000 provider denials recorded in the `.failed.jsonl` files. Those 7,000 rows are **96 HTTP
  429 responses, 6,903 circuit-breaker refusals and one TLS failure** — round 2 corrected this,
  which had said 7,000 rate-limit responses. Only 96 calls were refused by the provider; the
  breaker then declined 6,903 more on its own, so the denial count measures this client's
  reaction to rate limiting far more than it measures the rate limiting. A second invocation completed
  draws 5 to 8 and ran `cross-T`. A denial spends nothing and lands no reading, so the record
  contains no partial draw; every one of the nine draws is complete at 260 of 260. The retried
  readings were taken in the later invocation, after an interval this design does not control
  for. **How long an interval: the gap within draw 5 is 12:40:09.384**, from the last completion
  before the interruption at 2026-09-10T15:31:49.682Z to the first after resumption at
  2026-09-11T04:11:59.066Z (archive `projects/project-holistic__cross-R__d5/.crossaudit/
  usage.jsonl`, rows 165 and 166, field `t`, epoch milliseconds). The two run manifests are
  12:47:51 apart (2026-09-10T16:08:25Z and 2026-09-11T04:56:16Z), which is the separation of two
  end-of-invocation records and not the interruption itself.

  **Amendment 2 recorded this as a second permanent provenance gap. That was wrong and is
  withdrawn.** The claim rested on the committed cache rows, which carry `wall_s` and `run_id`
  but no clock time; the archived usage ledger carries `t` and was not consulted. Round 2 found
  it there and this study reproduced it before withdrawing the claim. Worth stating in its own
  right: this is the one error in this programme so far that made the work look **worse** than
  it is, by recording a loss that had not occurred. What the records do support is that
  draw 5's readings were split across the two invocations and that the manifests bound the split
  at about thirteen hours.

  **Two different interruptions are described in this study and must not be conflated.** The
  denials counted above are HTTP 429 rate-limiting recorded in the `.failed.jsonl` files, which
  is what the numbers in this bullet come from. Separately, the operator reported that the
  account's balance was exhausted during this period; **no record in this study attributes any
  particular denial to billing rather than to rate limiting**, so the balance report is context
  for why the run was resumed later and is not evidence about any individual denial.
* **Amendment 1's obligation is discharged.** An earlier version of this file reported the
  adjudication as prepared but not run, because the analysis was first carried out under an
  instruction to make no model call. Both raters have since answered the sheet, the registered
  primary rate is reported in §3 and Amendment 1's kill is evaluated and fires. L2's spend is
  not in this study's ledgers: it ran through the Codex CLI against a subscription, so the
  cost figures in this section are unchanged by it. Nothing else in the preregistration is
  unmet.
* **The registered status of the two adjudication questions differs, and is not relabelled
  here.** Naming is study 19's registered question. Recognition — "does the finding assert
  the code is wrong on that class, or only that it is untested?" — is **post-hoc in study
  19** and is **registered in this study** by Amendment 1, whose primary rate is "P instances
  with a defect-asserting finding over 110". Both are reported, and the kill is evaluated on
  the registered primary, which is the defect-asserting one.
* **The low κ is a limit on §3 and is reported as one**, not as a caveat at the end: the
  naming question's κ = 0.391 is stated above Table 10 rather than below it, and every rate
  is given under all four reader rules so a reader can see which conclusions survive the
  disagreement. `cross-T`'s kill verdict survives all of them; the point estimates do not
  survive unchanged, and the spread between rules is the honest width on them.
* **Reading choices where the preregistration is silent**, all resolved before the numbers
  were read and all visible in `numbers.json`. "Single-draw false-positive rate" (§2 H20c)
  is reported as the mean over the eight draws with its cluster interval, which is what
  ceiling 1's K = 1 curve point is, with the eight individual draws listed beside it so a
  reader can apply the bar either way; for `cross-R` both readings breach the bar by a wide
  margin, so the choice does not decide anything here. "All measured families" (§2 H20d) is read as study 18's five
  plus `cross-R`, with `cross-T` excluded by Amendment 1's own sentence. The kill's interval
  is evaluated as the preregistration writes it, [19.8, 40.7], with the same interval
  recomputed at this study's seed printed beside it. The cluster sign-flip test's sampler
  seed is not named by any preregistration, and `report_ceiling`'s frozen one is used
  unchanged rather than moved to this study's seed.
* **Labels**: everything preregistered in §2 and §3 is reported under its registered name and
  nothing is relabelled. The exchange rate in Table 4 is ceiling 1's diagnostic carried over
  and is marked EXPLORATORY because study 20 did not register it: it belongs to ceiling 1
  §1.4, which this study's §0 does not bind, and study 20's own §3 does not name it. The ZIBB
  fit is ceiling 1 §1.2's registered secondary, which §0 does bind, and it is reported in
  Table 4 and in §1 as that section requires. The `tau > K_max` diagnostic is study 18's
  post-hoc one and is not reached by either family here.
* **Limits**: one substrate, one auditor model, one reasoning setting (the product default for
  the auditor role), one constitution difference. `cross-R` measures the referent rule as
  `loop.REFERENT_RULE` writes it, appended to the shipped constitution, and nothing about
  instructions in general. The hidden suite reached no prompt, check or model. The large
  false-positive cost of H20c means the recall gain of H20a is not by itself a case for
  shipping the rule; the two hypotheses are reported together for that reason. `cross-T` is a
  single reading and carries a single reading's uncertainty.
  `tests/test_ceiling4_report.py` binds every generated block byte for byte, asserts the
  renderer reproduces them from `numbers.json` alone, asserts no table-like content exists
  outside those blocks, and binds every figure quoted above to the records; the prose is the
  reviewer's to check.
