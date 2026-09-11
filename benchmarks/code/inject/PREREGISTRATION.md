# Study 22 — the ceiling on defects the specification determines

Preregistered on `study/injection` **before any model call of this study**, at the commit that
adds this file. Binding: ceiling 1's preregistration §0–§1.5 and `RESULTS-CEILING.md` (the frozen
audit set, the strata, the union-of-K estimand, the interval conventions), study 21's
preregistration and `RESULTS-RERATE.md` (the rubric and the post-hoc split this study tests),
`EXPERIMENT_RECORD.md` §9–§10, D153.

## 0. The question, and why it needs a new population

Ceiling 1 measured the shipped cross auditor at 33 of 110 = **30.0%** [20.0, 40.7] union recall
at K = 8 on stratum P, and the union of all twenty draws of all three families at 53 of 110 =
**48.2%** [36.7, 60.0]. Study 21 then re-rated that population and found, **post hoc**, that the
twenty draws caught 23 of the 25 defects both raters called specification-determined but
unexercised, and 24 of the 68 they called oracle-defined. If that split is real, the ceiling
ceiling 1 measured is mostly a property of the benchmark's oracle, not of the auditor.

That claim rests on two raters, one of them the author, on one population, asked after the
counts were seen. This study tests it prospectively on a population where "the defect is
determined by the specification" is fixed **by construction and by mechanical filters**, with
no rater deciding membership, and where every other variable — the corpus, the generator, the
auditor, the constitution, the flag rule, K — is held at ceiling 1's frozen values.

## 1. The population

**Base.** The 150 stratum-C instances of ceiling 1's frozen audit set
(`records/study2/audit_set.json`): solutions written by `claude-haiku-4-5` under study 2's
prompt that pass the visible suite **and** the hidden suite. Same generator, same prompt, same
problems as stratum P; the only difference is that no defect is present.

**Injection.** For each base instance an injector model is shown the specification exactly as
the generator saw it, the visible suite, and that instance's solution, and must return JSON:
`code` (the solution with exactly one semantic defect introduced), `quote` (a span copied
verbatim from the specification that the modified code now violates), `input_class` (one
sentence naming the inputs on which it now fails), and `witness_input` (one concrete argument
tuple on which the modified code differs from the base). The injector is instructed to make the
defect look like an ordinary mistake, not a marker. Injector: `claude-haiku-4-5-20251001`, the
generator's own model, so the code's style is the generator's throughout. Temperature and
sampling: the harness defaults for that model. One injection attempt per instance; **no
resampling of a rejected instance** (an instance the filters reject is dropped, and the drop is
reported).

**Mechanical acceptance filters.** All must hold; none involves a judgment:

| | filter |
|---|---|
| F1 | `quote`, after collapsing runs of whitespace, is a literal substring of the specification and is at least six words long |
| F2 | the modified code passes **every** visible test (so the instance sits where stratum P sits: visible-clean, hidden-failing) |
| F3 | the modified code **fails** the hidden suite, and the failure is an assertion or exception, not a timeout |
| F4 | the unified diff against the base solution changes at most four lines and adds no import |
| F5 | the modified code compiles and runs at least one visible test to completion |
| F6 | `witness_input` is recorded and the first failing hidden input is recovered by the same witness path study 21 used |

**Construction gate (model-based, disclosed).** Each accepted instance is then shown — the
specification, the base solution, the modified solution, the quote and the input class — to two
gate models, `claude-sonnet-4-6` and `openai:gpt-5.6-luna`, which each answer yes/no to: *does
the specification as written entail that the modified code is wrong on the named input class?*
An instance enters population **I** only if both say yes. Neither gate model is the auditor
under test (`openai:gpt-5.6-terra`); `gpt-5.6-luna` is a same-vendor sibling of it, and that is
a disclosed limitation, not a hidden one. The gate's agreement rate and the per-gate counts are
reported.

**Why an imperfect filter is conservative.** The filters and the gate can only fail by admitting
an instance whose defect is *not* specification-determined. Such an instance behaves like a
stratum-P instance and can only pull recall on I **down**, toward the 30.0% this study predicts
it will exceed. No failure mode of the construction manufactures the predicted effect. The
opposite threat — that injected defects are easier to see because they are injected — is real
and is measured in §4.

## 2. What is run

The shipped cross auditor (`openai:gpt-5.6-terra`, ceiling 1's `cross` family, the shipped
constitution unmodified) reads each instance of I holistically, K = 8 independent draws, exactly
ceiling 1's protocol and cache discipline. Reply texts are archived (as study 20's `cross-T`
arm archives them) so §5's adjudication is possible; no finding text is committed.

The false-positive control is **free and paired**: the same 150 solutions without the injected
defect are ceiling 1's stratum C, already audited by the same auditor at K = 8 (24 of 150 =
16.0% union). Every instance of I therefore has its own unmodified twin already measured.

## 3. Hypotheses and the primary

* **H22a (primary).** Union recall at K = 8 on I exceeds the shipped cross auditor's union
  recall at K = 8 on ceiling 1's stratum P (33/110 = 30.0%). Estimand: the difference in union
  recall, I minus P. Interval: two-sample problem-cluster percentile bootstrap (seed 20260916,
  10,000 resamples), resampling problems within each population independently; Wilson reported
  beside each rate. The populations are different instances, so the difference is **not** paired.
* **H22b.** Union recall at K = 8 on I exceeds the union *false-positive* rate on the paired
  unmodified twins (24/150 = 16.0%). This one **is** paired: exact McNemar and the cluster
  sign-flip test over the 150 problems, both preregistered.
* **H22c.** Single-draw (K = 1) recall on I against cross's single-draw recall on P (11.8%
  is ceiling 1's `draw1_rate` 0.106818 → 10.7%); same two-sample interval.
* **H22d.** The saturation curve on I: union recall at every K from 1 to 8, the constrained
  exponential fit and ceiling 1's flattening bar (last-step gain ≤ 1.0 point). Reported whether
  or not it flattens; where it does not, the raw union at K = 8 is the number quoted.

**Kill.** If H22a's interval includes zero, study 21's post-hoc split does not replicate
prospectively; the paper will say so in those words and will not claim that the ceiling is set
by oracle-definedness. If H22a's interval is entirely below zero, the claim is refuted and that
is reported as the study's result.

**Multiplicity.** One primary (H22a). H22b–H22d and everything in §4–§5 are secondary; no
correction is applied to them and none is claimed to clear a corrected threshold. The full
inventory of comparisons is listed in the results.

## 4. The artificiality threat, measured

An injected defect might be easier to see than a natural one for reasons that have nothing to do
with the specification. Three preregistered measurements, all secondary:

1. **Detectability probe.** A model that is not the auditor and not a gate (`claude-opus-4-8`)
   is shown, one at a time and in random order (seed 20260916), the 150 modified solutions and
   150 natural stratum-P solutions, with the specification, and must answer: *was this solution
   written in one pass, or written and then edited to introduce a defect?* If its accuracy on
   this two-class question is at chance — its 95% Wilson interval covers 50% — artificiality is
   bounded below what a frontier model can detect from the code alone. The accuracy and its
   interval are reported whatever they are; this probe does not gate anything.
2. **Diff size.** Union recall on I split at the median number of changed lines, with intervals.
3. **Where the defect sits.** Union recall on I split by whether the injected line is inside the
   function's main path or a branch, decided mechanically by whether the changed line is nested
   under a conditional in the AST.

## 5. Secondaries with a real key

Because the defect is constructed, its identity is known without a rater. Two secondaries:

* **Naming.** For each blocked instance of I, does some finding name the injected input class?
  Adjudicated blind (instance ids and arm removed) by the author and by `gpt-6-astra`, as study
  19's H19d was, but here the key is the injector's own `input_class` and the diff, not a
  reading of the hidden failure. κ reported; disputed items count as not-named.
* **Wrong-reason blocks.** Of the blocked instances whose findings name nothing resembling the
  injected class, how many name something else. Reported as a count.

## 6. Budget, stopping and boundary

Injection ≈ 150 calls, gate ≈ 300 calls, audit 8 × |I| readings, probe 300 calls. Expected
**$17**; cap **$35** on the cumulative spend of this study, enforced from the project ledgers
across restarts (study 19's per-invocation counter is not sufficient and is not relied on). The
ladder is fixed in advance: draws 1–8 of `cross` on I in order; the run stops at the cap and the
draws completed are reported. No outcome may change the ladder, the filters, the gate, the
hypotheses or the kill.

Boundary: `src/` and the kernel directories are untouched; nothing in `ceiling.py`,
`report_ceiling.py` or study 21's files is modified. The corpus licence rule stands: no
specification text, no solution text and no finding text is committed; records carry ids,
hashes, counts and outcomes only. The injected solutions live in the run archive under
`~/Documents/Crossaudit/study-data/wt-inject-runs/`, never in the repository.

## Amendment 1 — 2026-09-11, after a ten-instance construction pilot, before any instance of I exists and before any audit call

**What was run.** With §1 as written, a pilot of the first ten base instances was run to check
that the pipeline works: 10 injector calls, $0.029, no gate calls, **no audit calls of any kind**.
Eight replies parsed; the filters accepted **none**. The drops: F2 (the modified code broke a
visible test) 6, F3 (the modified code did not fail the hidden suite) 2, F4 (diff too large) 1,
F1 (the quote is not in the specification) **0**. Two replies did not parse.

**Why this is not an outcome-dependent change.** Nothing about any auditor's behaviour has been
observed. What the pilot measured is the yield of the construction, and the dominant failure —
six of eight parsed replies broke a test that was printed in the prompt — is the injector not
doing what it was asked, not a property of the population. Population I is still empty; the
pilot's ten injections are discarded and those instances are rebuilt under this amendment.

**What changes, and only this.**

1. **Reply format.** The injector now returns a one-line JSON object with `quote`,
   `input_class` and `witness_input` (short fields, no code inside the JSON) followed by the
   modified solution in a single fenced Python block. The pilot's two parse failures were
   unescaped newlines inside a JSON string; this removes that failure mode.
2. **The prompt states the binding constraint plainly** — the modified solution must still pass
   every test shown — and asks the injector to check each shown test against its edit before
   answering.
3. **Up to three attempts per base instance**, fixed here in advance. Attempt 1 is as above.
   If the filters reject it, attempts 2 and 3 are told which *shown* tests failed and that the
   edit must survive them; they are shown nothing about the hidden suite, and nothing about any
   auditor. The first attempt whose filters accept is the instance's injection; a base instance
   whose three attempts all fail is dropped and counted. The per-instance attempt count is
   recorded and reported.

Attempts 2 and 3 push the injector toward defects that survive the visible suite — which is the
defining property of stratum P, the population I is compared against — and toward subtler edits,
which can only lower recall on I. Both directions are conservative for H22a.

**Unchanged:** the base population, the six filters and their thresholds, the two-model gate,
the auditor, the constitution, the ladder, K, every hypothesis, the primary, the kill, the
budget and the boundary. No outcome has been seen and none may change any of these.

## Amendment 2 — 2026-09-11, after a twelve-instance yield pilot, before any instance of I exists and before any audit call

**What was run.** The pilot of Amendment 1, on twelve base instances: 30 injector calls and 6
gate calls, $0.149, cumulative construction spend $0.178, **no audit call of any kind**. The
filters accepted 3 of 12 (Amendment 1's fix worked: F1 and F2 dropped nothing). The gate
accepted none of the three: `claude-sonnet-4-6` said yes to one and no to two — on quotes like
"sum of the elements with at most two digits" against negative numbers of more than two digits,
where the prose genuinely does not settle it, which is the gate doing its job — and
`gpt-5.6-luna` answered nothing at all: every call to it was refused by the harness project's
own model allowlist (`ProviderDenial`), not by the model.

Population I is still empty and no auditor has read anything. Three changes, all to
construction:

1. **The second gate model is actually called.** The build client is constructed with the
   harness's `allow_custom` flag so `gpt-5.6-luna` resolves, as `claude-sonnet-4-6` already did.
   Without this the gate was one model, not two. The pilot's six gate verdicts are discarded and
   re-taken.
2. **The base frame is every stratum-C instance of the frozen corpus (910), not only the 150 in
   ceiling 1's audit set.** The pilot's joint yield — roughly a quarter through the filters and
   a minority of those through the gate — cannot produce a population of useful size from 150.
   The frame is walked in one fixed order: the 910 ids sorted, then shuffled with seed 20260916.
   The walk stops at **|I| = 110** (ceiling 1's stratum-P size, chosen for comparability, not by
   any outcome) or when the **construction spend reaches $12** of the study's $35 cap, whichever
   comes first; both numbers are reported, and so is how much of the frame was consumed.
   The 150 instances that are in ceiling 1's audit set are flagged in the records: H22b's paired
   comparison (McNemar and the sign-flip test against the unmodified twin's already-measured
   audit) is computed **on that subset only**, and its n is reported. For the rest of I the
   false-positive comparator is ceiling 1's population-level 24/150 = 16.0%, not a paired twin.
3. **The drop accounting is per attempt.** The pilot's `filter_drop_reasons` counted only
   instances that ended accepted, so it reported zeros. It now counts, over every attempt of
   every base instance, which filter rejected it, and reports the per-instance attempt count.

**A confound this creates, and how it is measured.** Stratum P consists of instances where the
generator failed; stratum C of instances where it succeeded. Widening the frame to all C
instances means I sits on problems the generator found easier. Whether that makes an injected
defect easier to see is measurable and is added to §4 as a fourth secondary: **union recall on I
split by whether the instance's problem also contributes an instance to stratum P**, with
intervals, reported whatever it shows.

**Unchanged:** the injector, the six filters and their thresholds, both gate models and the
requirement that both say yes, the auditor, the constitution, the ladder, K, every hypothesis,
the primary, the kill, the $35 cap and the boundary. No outcome has been seen.

## Amendment 3 — 2026-09-11, the OpenAI credit balance is exhausted; still before any instance of I exists and before any audit call

**What happened.** Every OpenAI call now returns HTTP 429 `insufficient_quota`
(`credit_balance_exhausted`); the last OpenAI call that landed anywhere in the programme was at
23:31 local. That is why Amendment 2's second gate model, `openai:gpt-5.6-luna`, answered
nothing: not the harness's allowlist after all, and not the model — the account. It also stops
the audit, whose auditor is `openai:gpt-5.6-terra`.

**What changes.**

1. **The second gate model becomes `anthropic:claude-opus-4-8`.** Both gates are then from one
   vendor, which makes their judgements more correlated and the gate weaker. A weaker gate
   admits instances whose defect is *not* specification-determined, and those can only pull
   recall on I **down**, toward the 30.0% H22a predicts it will exceed: the change is
   conservative for the primary, as §1's argument already covers. Neither gate model is the
   auditor.
2. **The OpenAI gate is not abandoned, it is deferred.** When credits return,
   `openai:gpt-5.6-luna` is asked the same question about every instance of I, and the results
   report, as a preregistered sensitivity: how many instances of I it would also have admitted,
   and union recall on the subset it admits beside union recall on all of I. If that subset's
   recall differs materially from the whole, the gate's vendor mattered and the results will say
   so.
3. **The audit waits.** Nothing about the auditor, the ladder, K, the hypotheses, the primary or
   the kill changes; the construction proceeds now and the eight cross draws run when the
   account can pay for them. If OpenAI credit never returns, the study is reported as
   constructed-but-unaudited and nothing is claimed from it.

**Unchanged:** the injector, the six filters, the requirement that **both** gates say yes, the
frame and its seeded order, the target |I| = 110, the $12 construction cap and the $35 study
cap, the auditor, the ladder, every hypothesis, the primary, the kill and the boundary. No
outcome has been seen.

## Amendment 4 — 2026-09-11, a fully paired control; before any audit call

Amendment 2 widened the frame beyond ceiling 1's audited 150, which left most of population I
without the free paired twin §2 relied on: for those instances the false-positive comparator
was ceiling 1's population-level 16.0%, measured on a different set of problems. A reviewer is
right to ask whether a difference between I and that comparator is the injected defect or the
problem mix.

**Change.** The ladder gains a second arm: the **unmodified base solution** of every instance of
I, audited by the same auditor, the same constitution, the same K = 8. For the instances that
are in ceiling 1's audit set those readings already exist in the frozen cache and cost nothing;
only the others are bought. Every instance of I then has its own twin — same problem, same
specification, same generator, same code except the injected lines — measured under the same
auditor.

**What this changes in the analysis.** H22b becomes paired over all of I rather than over the
audited subset: union recall on I against the union flag rate on the twins, by exact McNemar and
the cluster sign-flip test, both preregistered. H22a is untouched: its comparator is still
ceiling 1's frozen 30.0% on stratum P. The twin arm is also the honest denominator for a
sentence the results will otherwise be tempted into — "the auditor flags the defect" — since a
twin flagged just as often would mean the auditor flags the *problem*, not the defect.

**Ladder order**, fixed here: `I` draws 1–8, then `twin` draws 1–8. If the cap stops the run
part-way, the completed draws are reported and the paired comparison is made at the largest K
both arms reached.

**Budget.** The twin arm roughly doubles the audit: expected total now **$25**, still under the
**$35** cap, which does not change. Nothing else changes: not the population, the filters, the
gate, the auditor, K, the hypotheses, the primary or the kill. No outcome has been seen.

## Amendment 5 — 2026-09-11, which contrast carries which confound, fixed before any audit call

No hypothesis, number, threshold or procedure changes here. This records, before any outcome is
visible, how the two contrasts must be read, so that the reading cannot be chosen later.

**H22a compares two populations that differ in two ways at once.** Population I sits on problems
the generator solved (stratum C); ceiling 1's stratum P sits on problems it failed. So a
difference in union recall between them is the *joint* effect of how the defect arose (injected
and specification-determined, against naturally occurring) and of which problems the instances
come from. H22a cannot separate those, and the results will say so in the sentence that reports
it. It is still the primary, because the paper's headline number is ceiling 1's 30.0% and a
reader is entitled to see the new population measured against it.

**H22b has no problem-mix confound at all.** Each instance of I is compared with its own twin —
the same problem, the same specification, the same generator, the same code but for the injected
lines, read by the same auditor at the same K (Amendment 4). Any difference there is the
injected defect and nothing else. H22b is therefore the internally controlled contrast, and
where the two point in different directions, the results must report H22b as the one that
isolates the defect.

**Neither licenses the sentence "the auditor catches specification-determined defects."** Both
measure whether the instance was blocked. Whether a block names the injected class is §5's
adjudication, and that is a separate, secondary number with its own key.

## Amendment 6 — 2026-09-12, after an internal hostile review, before the added arm is run

An internal review (Claude, same vendor as the author, run before the cross-vendor gate) found
that §1's conservativeness argument is **false**, and gave counterexamples from the archive. The
argument claimed the construction "can only fail by admitting an instance whose defect is not
specification-determined". It fails in the other direction too, and that direction inflates the
primary:

* The gate rejects instances whose defect the specification settles plainly. `b1:Mbpp/223` changes
  `count > n/2` to `count >= n/2` against a specification that says *"occurs more than n/2
  times"*, and **both** gates said no; `b1:Mbpp/409`, `b1:Mbpp/224` and `b1:HumanEval/5` are the
  same shape. The mechanism is visible: the gate is asked whether the specification settles the
  question *on the injector's own `input_class` string*, and F6 checks only that a witness exists,
  never that `input_class` names the class the edit actually breaks.
* The rejections are concentrated on boundary-shift edits, which are the subtlest in the pool and
  the ones an auditor is least likely to flag. What survives is enriched for edits that announce
  themselves.
* Amendment 1's retry loop amplifies it: attempts 2 and 3 are told to make the defect fire only on
  other inputs, and 37% of accepted injections came from a retry.

**The added arm.** A random sample of **40** of the 189 instances that passed the six filters and
were then rejected by the gate, drawn by `random.Random(20260916)` from the sorted ids, audited by
the same auditor, the same constitution and the same K = 8. Outcome: union recall on that sample,
with both intervals, reported beside 90 of 92.

**What it decides.** If recall on the rejected sample is close to recall on I, the gate is not
selecting for detectability and §1's headline survives with the conservativeness argument replaced
by this measurement. If it is materially lower, the gate is part of the effect, and the results
must say that the 90 of 92 is a property of the gate-accepted population rather than of
specification-determined defects in general. **No threshold is set here, because the quantity is a
magnitude to report, not a hypothesis to accept or reject**; the difference and its interval are
reported whatever they are, and §1's claim is written to match.

**Also corrected by this amendment, without new data.** Amendment 5 said of the paired twin
contrast: "Any difference there is the injected defect and nothing else." That is false. The twin
differs from its instance by the **edit**, which carries both the specification-violating semantics
and whatever surface salience the edit has; §4.1's probe shows that salience is detectable. The
paired contrast isolates the **edit**, not the defect, and controls the problem, not the salience.
Every sentence resting on A5's claim is rewritten.

**Budget.** 40 instances × 8 draws ≈ $3.5, taking the study to about $20 of its $35 cap. Nothing
else changes: not the population, the filters, the gate, the auditor, K, the hypotheses, the
primary or the kill.
