# Ceiling 4 — the referent rule raises the shipped auditor's ceiling, and charges for it on the clean stratum

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
`ceiling4/splice_tables.py`), and the archive
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

* **H20b (the ceiling, not the slope): the two families fall on opposite sides of ceiling 1's
  flattening bar, so their asymptotes are not comparable in kind.** `cross-R` passes the
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
  also recorded. Where the two estimators disagree §1.2 says to prefer the conservative one;
  that is the saturation fit here, and the raw union at K = 8 is more conservative still.
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
  where the gap between the two rules was the whole story. No text was adjudicated, so
  neither rate is shown to name a defect.
* **`mixed`** (Table 7): at every matched total, a mixture of `cross` and `cross-R` readings
  sits above `cross` alone and below `cross-R` alone, on both strata. Spending half the
  readings on the shipped constitution buys nothing here that spending all of them on the
  rule does not buy more of, and it does not recover the false-positive rate either.
* **Reply format**: not a factor. Every reading is one accepted reply.

## 3. Amendment 1 — the shipped auditor's own findings, and what is prepared but not run

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

**The adjudication is prepared and not run.** Amendment 1's primary rate is a *defect-naming*
rate, "P instances with a defect-asserting finding over 110", and the kill it adopts from the
memo is a threshold on that rate. Both are properties of an adjudication of the archived
texts, which this analysis does not perform: no model was called and no network was used, so
`amendment1_primary_rate` is null in `numbers.json` and the kill is recorded as not
evaluated. `ceiling4/adjudication_sheet.py` builds the blind sheet — study 19's questions,
every finding of any severity on a P instance in `cross-T` draw 1 and in `cross-R` draw 1,
each shown with the specification, the candidate solution and the hidden failure recovered
model-free by re-running the hidden suite in `execute.py`'s sandbox, and no arm, severity or
stratum. The sheet is written outside the repository because it quotes model output,
specifications and solutions; only the key and the manifest of counts and digests are
committed.

One bound does not need the adjudication. The naming rate cannot exceed the count of P
instances on which `cross-T` returned any finding at all, and that count is 9. Whatever L1
and L2 decide, Amendment 1's rate is
at most 9 of 110, which is below the memo's threshold of 20 of 110.
The adjudication remains necessary to say what the rate *is*, and to compare `cross-T` with
`cross-R`; it is not necessary to know which side of that threshold the shipped auditor falls
on, on this one reading.

## 4. Cost, run history, deviations, limits

<!-- BEGIN TABLE9 (records/ceiling4/tables.md) -->
### Table 9 — reply format, provider denials and ledger cost, per draw

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
<!-- END TABLE9 -->

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
  7,000 provider denials recorded in the `.failed.jsonl` files. A second invocation completed
  draws 5 to 8 and ran `cross-T`. A denial spends nothing and lands no reading, so the record
  contains no partial draw; every one of the nine draws is complete at 260 of 260. The retried
  readings were taken in the later invocation, after an interval this design does not control
  for.
* **Deviation, stated plainly**: Amendment 1 makes the adjudication **unconditional** — its
  `cross-T` draw is to be adjudicated with study 19's naming and recognition questions, and
  `cross-R` draw 1 beside it whether or not H20a is positive. H20a is positive and the
  adjudication has not been run. This analysis was carried out under an instruction to make
  no model call, and the adjudication needs a model for L2 and a reader for L1, so the inputs
  are built and the questions are left open. Amendment 1's registered primary rate is
  therefore not reported, and the study's §4 obligation is outstanding, not discharged.
  Nothing else in the preregistration is unmet.
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
