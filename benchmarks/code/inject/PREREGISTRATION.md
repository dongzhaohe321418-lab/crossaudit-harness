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
