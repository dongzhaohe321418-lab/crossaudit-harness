# Study 18 — ceiling 3: does the ceiling belong to the auditor model, or to auditing?

Preregistered on `study/ceiling3` **before any model call**, at the commit that adds this
file. Binding: `ceiling/PREREGISTRATION.md` §0 (the substrate, unchanged), §1.1–§1.2 (the
union-of-K curve and the saturation form, unchanged), §1.5 (the residual rule), Amendments
3–5 (intervals for paired binary contrasts), `RESULTS-CEILING.md` (frozen at b88ce74; D162),
`EXPERIMENT_RECORD.md` §9–§10, D153.

## 0. Why this study

Ceiling 1 measured three auditor families on the same frozen instances: the shipped
cross-vendor auditor (`openai:gpt-5.6-terra`, K = 8: union recall 30.0% [20.0, 40.7] at
16.0% FP), the generator's own small model (`anthropic:claude-haiku-4-5`, K = 8: 17.3%
[8.3, 27.3] at 24.0% FP, flattened) and a frontier model through a subscription route
(`gpt-6-astra`, K = 4). Two of the three are one vendor's models, and the third-vendor
family is the smallest model in the set, so ceiling 1 cannot say whether **the low
same-vendor ceiling is a vendor effect or a model-size effect**, nor whether **the ~30%
figure is a property of auditing by reading or of one vendor's models**. The owner's aim
is a general statement about the ceiling of AI audit; this study adds the missing axis
cheaply, on the same instances, with the same protocol, so the curves are commensurable.

## 1. What is run

Two new families through the product's provider broker, on ceiling 1's scope (stratum P,
n = 110; stratum C, n = 150; the frozen study-2 solutions; the shipped constitution; the
same prompt path `crossaudit.auditor.run.run_audit`):

| family | detector | draws |
|---|---|---|
| `self-strong` | `holistic` audit, `anthropic:claude-sonnet-4-6`, `generator:` unset (the same deliberate same-vendor bypass ceiling 1's `self` used, confined to the harness) | **K = 8** |
| `self-frontier` | `holistic` audit, `anthropic:claude-opus-4-8`, same bypass | **K = 4** (budget) |

The existing `cross`, `self` and `astra` draws are read, never re-run. Everything is
cached per `(kind, route, draw, instance)` in `records/ceiling3/cache/` by the same loop
(`explore.run_detector`); a cached reading is never bought twice.

## 2. Hypotheses, each falsifiable, with the sign fixed now

* **H18a (model size, not vendor).** Union recall at K = 8 on P for `self-strong` exceeds
  `self`'s 17.3% by more than its problem-cluster bootstrap interval allows: the
  difference `self-strong` − `self` at K = 8, 95% cluster bootstrap, excludes zero and is
  positive. If it does not, the low same-vendor ceiling is not explained by model size and
  the vendor-effect reading of ceiling 1 stands.
* **H18b (the ~30% is not one vendor's number).** The difference `self-strong` − `cross`
  at K = 8 on P, 95% cluster bootstrap, **includes zero**. This is a hypothesis of
  equivalence and is read as such: it comes out false if the interval excludes zero in
  either direction, and "includes zero" is reported with the interval's width, never as
  "no difference". A wide interval that includes zero is "not distinguishable at this n",
  and the report says so.
* **H18c (the frontier point).** `self-frontier` at K = 1 (mean over its draws) against
  `astra` at K = 1: the difference on P, with its interval; and `self-frontier`'s K = 4
  union against `astra`'s K = 4 union. No direction is predicted; both are reported.

**Primary outcome: the difference of union recalls at K = 8 on stratum P,
`self-strong` − `cross`**, with the 10,000-resample problem-cluster bootstrap (seed
20260910) — the raw union difference, which `RESULTS-CEILING.md` found sturdier than the
fitted-asymptote contrast when a curve has not flattened. The fitted asymptotes (§1.2's
form, constrained A ∈ [0, 1]) and the flattening test (the K = 7 → 8 gain against ceiling
1's bar) are secondary.

## 3. Secondary outcomes, named in advance

Union FP on C at every K for the new families, in the same table as recall; the
recall-to-FP exchange rate K = 1 → K_max; single-draw recall and FP; the `mixed` union
across families at matched total draws (`cross` + `self-strong`, K/2 each) against each
alone; the residual of the strongest family under §1.5's rule (the classification is
re-run by the same script on the same categories); per-family cost per reading from the
ledger; the fraction of P instances flagged by **no** family across all draws of all five
families — the one number that speaks to "the ceiling of AI audit" rather than of one
auditor.

## 4. What this study can and cannot license

It can say whether the ~30% ceiling moves with the auditor's vendor and size on this
substrate. It cannot say anything about the generator axis (all solutions are Haiku's),
the task axis (function-level code with short specifications) or the human baseline; those
are the next stages of the programme, each with its own preregistration:
stage B regenerates the instances with a stronger generator (`claude-sonnet-4-6`) and
re-executes the hidden suites; stage C is a benchmark with long specifications.

## 5. Budget, ladder, stopping

Ceiling 1's Haiku draws cost $0.87–1.51 each over 260 instances; Sonnet's list price is
about four times Haiku's, Opus's about twenty. Ladder, set by budget alone: `self-strong`
draws 1–4, then `self-frontier` draw 1, then `self-strong` 5–8, then `self-frontier` 2–4,
while cumulative spend is below **$120**; the run stops at the cap and reports the K
reached, with K_common = min over the families compared. One instance = one `run_id`,
priced from the ledger exactly.

## 6. Boundary

Unchanged from ceiling 1: the hidden suite reaches no prompt, check or model
(`tests/test_architectures.py`); the audit path is the product's; the same-vendor bypass is
the harness's and `src/` is not touched.

## Amendment 1 — 2026-09-09, after `self-strong` draw 1 and before draw 2 ran

**What was seen.** Draw 1 of `self-strong` completed (260 of 260, $2.26; one SSL
transport failure re-run) with **0 of 110 P flagged and 3 of 150 C flagged**; median
reply 49 output tokens in about 4 s. Because that is far below every family in ceiling 1,
the author stopped the run at the start of draw 2 (no draw-2 reading had landed) to rule
out a harness fault before spending further. A probe outside the caches (`ceiling3-probe`,
three P instances the shipped auditor flags, the identical prompt bytes via
`ceiling.astra_prompt`, both Anthropic models) showed the readings are genuine: Sonnet 4.6
mostly returns a terse, well-formed `{"verdict": "PASS", "findings": []}`; on one of the
three it wrote a long prose analysis before any JSON; Haiku 4.5 on the same bytes wrote
BLOCKER findings. Both vendors run at the product's default reasoning setting for the
auditor role (`reasoning_effort` unset in the benchmark's `crossaudit.yml` template).

**What changes: nothing in the design.** The ladder is set by budget alone (§5) and the
run resumes at draw 2 as planned; a near-zero single-draw family is exactly the kind of
result the union curve must be measured for, not assumed. **What is added:** (1) the
three probe replies are archived with the run (`probe/`), outside the caches, and are not
readings; (2) a secondary outcome — the share of `self-strong` and `self-frontier` replies
that were prose rather than the JSON the validator expects, from the harness's
`invalid_reason` and re-ask counts in the ledger — so that "the model sees nothing" and
"the model does not answer in the product's format" can be told apart in the report;
(3) the report states the reasoning setting per vendor beside every family.

## Amendment 2 — 2026-09-10, after the first review; corrections of record, no design change

1. **Amendment 1's chronology was wrong.** It said the run was stopped "before draw 2 ran"
   and that "no draw-2 reading had landed". The archive shows draw 2 had begun: 31 calls
   between 11:10:07 and 11:11:37 UTC produced 30 cached readings before the process was
   killed, and Amendment 1 was committed at 11:14:31 UTC, after them. Those 30 readings
   were kept (the loop is resumable and a cached reading is never discarded or re-bought);
   the resumed draw 2 ran the other 230. Nothing else in Amendment 1 changes.
2. **The fit guard was outcome-dependent and is withdrawn.** After Sonnet's draws 1–4 the
   author added a rule that suppressed the preregistered saturation fit when the K_max
   union was below 5%, and described it as an estimability rule; the fitter in fact
   returns a finite fit on that curve (Sonnet P: A = 8.5%, τ = 14.3). The fit is now
   reported for every family as §1.2 requires; a post-hoc diagnostic (τ > K_max: the
   asymptote extrapolates past the readings taken, ceiling 1's own flattening caveat) is
   printed beside it and labelled post hoc.
3. **H18c's K = 1 contrast is computed as preregistered** — each family's mean single-draw
   rate over its draws, paired per instance, cluster-bootstrapped — and the draw-1-only
   contrast the first results reported is kept beside it, labelled exploratory.
4. **The probe replies were not archived**; they were printed to the author's terminal.
   The probe was re-run on 2026-09-10 with the same instances, prompt bytes and models,
   and the six new replies are archived with their digests (`probe/replies-rerun.jsonl`,
   `probe/README.md`). They are new samples, not the originals: one Sonnet reply this time
   carries a BLOCKER on an instance it passed before, so the probe's own lesson is the
   draw-to-draw variability the union curve exists to measure.
5. **The any-finding rule stays exploratory** and is reported as a flag rate — an
   instance on which the model returned at least one finding of any severity — not as
   evidence that the finding names the instance's defect; advisory texts were not archived
   or adjudicated. The reading "a severity policy, not a limit of seeing" is the author's
   inference, and the study designed to test it (ceiling 3b: the same families under a
   constitution that states the blocking criterion) is preregistered separately.
6. **Re-ask counts** are the ledger's excess of calls over readings per draw, not the
   multiplicity of `run_id`s, which `explore.run_detector` restarts per pass.

## Amendment 3 — 2026-09-10, after the second review; corrections of record

1. **Amendment 2 item 2 misnamed the diagnostic.** The τ > K_max note is a post-hoc
   diagnostic and is not ceiling 1's registered flattening test. That test is: the
   K_max−1 → K_max gain is at most 1.0 point. Under it Sonnet's curve (gain 0.34 points)
   **is** flattened; the first results said the opposite. The report now prints the
   registered bar and the diagnostic as two separate columns.
2. **Amendment 2 item 4 misdescribed the probe re-run.** All three archived Sonnet replies
   are PASS with no BLOCKER finding; the one BLOCKED reply is Haiku's. The word "BLOCKER"
   the author saw was in a Sonnet reply's prose, not in a finding. The sentence "on an
   instance it passed before" is withdrawn: the originals were not archived, so no such
   comparison exists.
3. **The residual secondary (§3) is now performed as §1.5 requires**: the residual across
   all families, classified with ceiling 1's per-instance categories, in the report and
   Table 6. It shrank from 57 to 56 (one `timeout` instance newly blocked); no instance is
   new to it, so no new label was needed.
4. **Every rate in the tables carries its intervals**: the curve points at every K now
   carry problem-cluster intervals (Table 2), and the mixed rates theirs (Table 5); the
   tables are rendered from `numbers.json` by the report and embedded in RESULTS verbatim,
   and the binding test compares the embedded block to the rendered file byte for byte.
5. **Reasoning setting**: the two new families and `cross`/`self` ran with
   `reasoning_effort` unset; `astra` ran at high reasoning through the Codex CLI (ceiling 1
   Amendment 1). "As the existing families did" was wrong for `astra`.
6. **Ceiling 3b is drafted, not preregistered**; its preregistration is committed when its
   branch opens, after this study is quotable.

## Amendment 4 — 2026-09-10, after the third review; corrections of record

1. Amendment 3 item 6 said ceiling 3b would be preregistered "after this study is
   quotable". It was preregistered (ed75d27) and run before this study's third review,
   because both quotas had run out and the alternative was an idle line. Nothing in
   ceiling 3b changes this study; the order is disclosed here.
2. The repair-prompt disclosure said all 46 repaired readings succeeded; 41 did and 5
   Opus readings stayed malformed (verdict ESCALATE, not flagged). Corrected.
3. "Every rate carries Wilson and cluster intervals" was false for subset-averaged
   curve points, single-draw means and mixed rates, which are means and carry the cluster
   interval only; the tables now say which interval each kind of rate carries, and the
   single-draw and `cross`-alone cells carry theirs.

## Amendment 5 — 2026-09-10, after the fourth review; the inherited standard applied in full

Ceiling 1 §1.2 and Amendments 3–5 are binding here and were only partly applied. Now
delivered, all from the same records and seeds: the ZIBB sensitivity fit and the maximum
absolute fit residual per family (Table 3); the Tango score interval and the exact
unconditional interval beside every paired-binary contrast, with ceiling 1's rule for
one-signed discordance applied to H18c's K = 4 contrast (0 vs 35); a problem-cluster
interval on every derived rate the prose repeats — the last-step gains, the exchange
ratios (2,000 resamples; resamples with no FP gain discarded and counted), the fitted
asymptotes, and the paired difference between "blocked by none" and "mentioned by none";
`cross`'s asymptote labelled an extrapolation beside its estimate, since it fails the
flattening bar. The title no longer carries a rate. The long-reply counts are described as
what they are (ledger calls per draw, repair calls included). Nothing measured changed.
