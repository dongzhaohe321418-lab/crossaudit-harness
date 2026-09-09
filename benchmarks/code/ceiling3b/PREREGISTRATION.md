# Study 19 — ceiling 3b: is the Anthropic families' near-zero BLOCKER rate the constitution's?

Preregistered on `study/ceiling3b` (branched from `study/ceiling3` at f5e77dc) **before any
model call**, at the commit that adds this file. Binding: study 18's preregistration and
its Amendments 1–3, `RESULTS-CEILING3.md` at f5e77dc (under review; nothing here changes
it), ceiling 1 §0–§1.2 and §1.5, ceiling 2's referent arm (`loop.py`, `REFERENT_RULE`),
D155, `EXPERIMENT_RECORD.md` §9–§10.

## 0. Why

Study 18 found Sonnet 4.6 blocks 3.6% of the defect population at eight readings under the
shipped constitution while, under a post-hoc any-finding rule, its readings carry some
finding on 59% of them. RESULTS-CEILING3 §2 labels "a severity policy, not a limit of
seeing" the author's inference. This study tests it by changing only the constitution's
text, holding model, prompt path, instances and reading count fixed, and by archiving and
adjudicating the finding texts so that "sees the defect" becomes a measured quantity.

## 1. Arms — all `anthropic:claude-sonnet-4-6`, K = 4, ceiling 1's 110 P + 150 C

* **S** — the shipped constitution: study 18's `self-strong` draws 1–4, reused (no call).
* **R** — the shipped constitution plus ceiling 2's referent rule, verbatim:

```
### CA-COVER-001
**BLOCKER.** The increment's visible test suite is shown to you. It is not a
specification and it is not complete. Identify the behaviour the specification
requires that the visible tests **do not exercise** — the input classes they
never construct — and judge the solution on those. A defect the visible tests
would not catch is the defect this rule exists to find.
```

* **B** — the shipped constitution plus one grading rule, verbatim:

```
### CA-GRADE-001
**BLOCKER.** A finding that names a specific input on which the implementation
returns a value the specification does not allow is a BLOCKER, whatever else it
is; grade it BLOCKER. A finding that names no such input is ADVISORY.
```

Rule B asks the model to name an input, not to assert what any test would say (D155: a
model may name evidence; it may not state what the evidence will say). Nothing else in the
constitution, prompt or settings changes. The route runs with `reasoning_effort` unset, as
study 18's did.

## 2. Outcomes

Flags: **BLOCKER rule** (preregistered primary, as ceiling 1) and **any-finding rule**
(preregistered here as a secondary for every arm, so it is no longer post hoc).

* **H19a (primary).** Union BLOCKER recall at K = 4 on P, **B − S**, problem-cluster
  bootstrap (seed 20260912, 10,000 resamples), paired per instance: positive and its
  interval excluding zero. Sign fixed: positive means the grading rule raises blocking.
  **Kill for the inference "a severity policy"**: if B − S is not positive beyond its
  interval, the near-zero rate is not (only) the severity rule.
* **H19b.** Union BLOCKER FP at K = 4 on C, B − S, with its interval; and B's single-draw
  FP against the product bar (6.7% at K = 1, `RESULTS-EXPLORE.md`).
* **H19c.** R − S on P under both rules: does the referent rule move the Anthropic family
  as it moved the shipped auditor in ceiling 2 (+26.8 points on flags)? Sign not fixed.
* **H19d (the seeing question, adjudicated).** For every P instance on which arm S, R or B
  returned any finding in draw 1, the finding texts (archived) are adjudicated blind
  against the instance's hidden failure by two labellers (L1 the author; L2 a different
  vendor's model through the Codex CLI when quota allows, else a second blinded session),
  answering one question: *does the finding name the input class, or the behaviour, on
  which the hidden test fails?* (yes / no / cannot tell). The rate "names the defect"
  among any-finding P rows, per arm, with Wilson and cluster intervals and κ. This is the
  measurement that "sees" in study 18's inference stands or falls on.

## 3. Secondaries

Per-arm curves at K = 1…4 with per-K cluster intervals (both rules); exchange rates;
reply-format counts (malformed, extra calls, long replies); BLOCKER-graded share among
findings per arm; the residual under B across all families (does the 56 shrink, and which
categories leave it); cost per draw from the ledgers.

## 4. Budget, ladder, stopping

R draws 1–4, then B draws 1–4 (ladder set by budget alone); ≈ $2.3 per draw → ≈ $18;
cap **$30**; stop at the cap and report the K reached. Adjudication spends no model money
except L2's Codex quota. One reading = one `run_id`; the run-ID-per-pass limitation of
`explore.run_detector` is known (study 18 §4) and costs are taken from the ledgers.

## 5. Records and boundary

Cache rows as study 18's under `records/ceiling3b/cache/`; **the finding texts go to the
archive only** (`~/Documents/Crossaudit/study-data/wt-ceiling3b-runs/findings-*.jsonl`),
never the repository; the adjudication sheet is blind (id, finding text, the specification;
no stratum, no arm); the key is committed. The hidden suite reaches no prompt, check or
model; `src/` is not touched; the same-vendor bypass is the harness's as before.

## Amendment 1 — 2026-09-10, during arm R draw 1; before any arm-S text reading

§2 H19d adjudicates arm S's draw-1 finding texts, but study 18's harness popped finding
texts before caching (`explore.run_detector` keeps hashes and counts), so no S text exists.
**Added to the end of the ladder: one reading of arm S with texts archived** — route
`self-strong-S`, the shipped constitution unchanged, draw 1 over the 260 instances
(≈ $2.3, inside the $30 cap). It enters H19d only; the BLOCKER and any-finding contrasts
of H19a–c keep using study 18's `self-strong` draws 1–4 as S, so a fifth S reading does
not enter them. The adjudication sheet is built from the draw-1 findings of R, B and this
S-text reading, blind as §5 says.

## Amendment 2 — 2026-09-10, during arm R draw 1 (75 of 260 readings landed); the cap

§4 estimated $2.3 per draw from study 18's Sonnet draws. Under the referent rule the
replies are longer: the ledger shows $1.39 for the first 75 readings, ≈ $4.8 per draw, so
the nine-draw ladder (R 1–4, B 1–4, S-text 1) would cost ≈ $43 and the $30 cap would stop
it inside arm B, leaving H19a's B − S at unequal K. **The cap is raised to $55** so the
ladder completes; the ladder order is unchanged. This is a cost-driven change made after
the author had seen the interim cache of R draw 1 (P instances run first: 17 of the first
95 blocked, 92 with a finding); it is disclosed here so the reader can weigh it, and it
changes no arm, rule, outcome or kill. The running process, started with the old cap, is
stopped and resumed with the new one; the loop is resumable and re-buys nothing.
