# E6 preregistration: contract-randomised information release (protocol e6-v4.3)

Draft v4.3, 2026-11-07 (after GPT reviews P4, P5 and P6). Frozen when committed with the verified pre-test bundle (section 10), before any E6 test
audit. Code: `icml/e6.py` (construction, audits, witnesses, completeness), `icml/analyse_e6.py` (analysis),
`icml/e1.py` (judge-v3.2, routes). Rationale: `audit-ceiling-paper/plan/icml2027/CEILING_PROGRAM.md` v3; GPT reviews
P1, P2, P3 (`review_gpt_P3.md`: test release refused; every blocker is addressed below).

## 1. Prior exposure

Development only. (a) Pilot e6-v3 (55 execution-admitted units; 50 in its judge population): reported in P3.
(b) After P3, construction was revised (sections 3-4) and the development audits were rerun under e6-v4 (3,440 open
readings, 864 positive-control readings). (c) After P4 (`review_gpt_P4.md`), stress inputs were added to admission
(39 open and 48 control development units remain; readings of excluded units are kept and reported as superseded),
witness credit was tightened, and the budget and E6-3 rules were changed (sections 7, 8). Development results under
e6-v4.1 (24 open units in the registered population; 3,120 readings): unrevealed flags equal on defective and correct
programs; resolved verified coverage 91.7%, resolved FPR 2.1% (betting bound 7.5%); E6-1 +91.7 [84.4, 97.4]; E6-2
+13.5 [6.8, 21.4]; E6-5 +77.1 [67.7, 86.5]; sentence minus resolve -1.0 [-5.2, 3.1]; E6-3 0.0, bootstrap [-4.2, 4.2],
betting [-28.9, 28.9]. Test units were constructed
before registration (proposal, implementation, admission, probes, predicates, judging, behaviour); no test audit
exists.

## 2. Corpus and split

HumanEval+ and MBPP+ (542 problems), frozen problem-level split `records/icml/split.json` (136 dev, 406 test).
One open unit and at most one positive-control unit per problem.

## 3. Construction (attempt limits frozen)

1. *Proposal* (con-gpt-astra; one attempt per problem and kind; skips and parse failures are exclusions). Open: an
   input class the task text and visible tests leave open, RULE_B (the reference's behaviour), RULE_A (an equally
   compatible alternative), 4-8 class inputs, 3-5 other inputs. Positive control: RULE_A a plausible misreading the
   words rule out, RULE_B the required behaviour.
2. *Implementations*: each rule implemented from task plus rule by adj-gpt-sol and adj-claude-opus with the same
   prompt (one attempt each; a failed implementation excludes the unit).
3. *Pre-admission* (`stage_validate`, execution): used only to decide which units receive probes.
4. *Independent probes and domain predicate* (adj-claude-opus, which did not propose): `valid(*args)` and 16-24
   probe inputs (target, boundary, non-target, invalid). *Class predicate* `in_class(*args)` from the proposer, which
   defined the class (must classify its own class and other inputs correctly).
5. *Admission v4.2* (`stage_validate4`): on every input the reference evaluates without error (not only on inputs
   `valid` accepts, so that "correct program" labels hold for the whole program an auditor reads), among the hidden
   suite, the proposer's inputs, the probes and the stress inputs: both B implementations agree with the reference;
   outside the class all four implementations agree with the reference; inside it the two A implementations agree;
   A and B differ on at least two class inputs that `valid` accepts; predicates never raise; all implementations pass
   the visible tests. Stress inputs (v4.1, extended in v4.2 with complex numbers and flat and nested floating-point
   cancellation after P5) are listed below. v4.1 adds deterministic, type-guided stress inputs (unicode and special whitespace, extreme and
   overflowing floats, large integers, int/float widening, empty, singleton, duplicated and mixed containers;
   `stress_inputs`, up to 120 per unit) to the validation set, after GPT review P4 found outside-class and
   reference-oracle failures that the sampled inputs missed. Infrastructure failures are reported separately from
   substantive rejections. Development effect of v4.2: 25 of 55 open and 21 of 70 control units admitted (39 and 48
   under v4.1). Predicate history: the first v4 admission used an independent class predicate and admitted
   10 of 55 development units; it was replaced by the proposer's predicate (43 of 55; 39 after stress inputs). Both
   versions and their rejection reasons are kept. The construction is execution-checked, not independently validated.
   *v4.3 (after P6, before any test audit).* GPT review P6 found three retained development units broken by inputs
   outside the stress set: a complex number equal to an integer (open Mbpp/405), a string of combining marks
   (open2 HumanEval/74) and negative indices (control Mbpp/170). Two changes, applied to every kind and split and
   rerun from the stored implementations: (i) the stress generator adds complex values equal to the int or float,
   combining and spacing marks, zero-width and byte-order characters, non-ASCII digits and negative indices, and keeps
   up to 300 inputs per unit; (ii) *red-team admission* (`stage_redteam`): a third model (adj-gpt-sol), shown the task,
   the reference, both rules, both predicates and all four implementations, proposes up to 40 inputs intended to break
   the admission conditions; they are executed with the same checks, and any violation (or a predicate that raises)
   rejects the unit. One attempt per unit; a reply that contains no parseable input contributes none. The red-team
   model sees the reference and the rules but no audit; its use is outcome-blind. Finite testing still cannot prove
   the labels; the stated guarantee is agreement on the registered input set (hidden suite, proposer inputs, probes,
   stress inputs and red-team inputs). The v4.2 admissions are archived (`*_units4_v42.jsonl`).
6. *Judge panel v2* (adj-claude-opus, adj-gpt-sol; blind; rule order randomised by problem hash; complete visible
   tests; no class description): domain valid / invalid / unresolved, and each rule compatible / incompatible /
   unresolved, with the instruction that a missing example is not permission.
7. *Behaviour*: the twelve E1 task-only generations per problem (two vendors) that pass the visible tests,
   classified as following A, B or neither on the class inputs where A and B differ.

## 4. Populations

- *Open population* (primary): admission-v4 units for which both registered judges (by route identity) return
  domain valid and both rules compatible. Operational definition: **execution-validated, two-model-compatible
  contract pairs**. This is not human-validated ambiguity and not an estimate of ambiguity prevalence.
- *Positive-control population*: admission-v4 positive-control units with both judges returning domain valid, RULE_A
  incompatible and RULE_B compatible. A separate confirmatory family (section 8), not a prerequisite.
- *Enlargement (outcome-blind, before any test audit; added in v4.2 because only 32 first-attempt test units reached
  the primary population):* every problem whose first-attempt open unit is not in the primary population receives
  one second, independent construction attempt (kind `open2`, same prompts and stages, one attempt per stage). The
  registered open population is the first-attempt primary units plus the second-attempt primary units of the
  remaining problems (`analyse_e6.merged_open`); one unit per problem.
- Frozen in the bundle by problem id, with every exclusion and its reason. No unit enters or leaves after the first
  test audit.

## 5. Arms, programs, configurations, readings

Open units: arms `none`; `menu` (both rules, numbered in a per-unit order fixed by problem hash and independent of
the contract, preceded by "the function must follow exactly one of these two rules, and the task author has fixed
which" and followed by "The task does not say which of the two rules applies"); `resolve-a`, `resolve-b` (the same
menu followed by "The function must follow rule (k)"); `sentence-a`, `sentence-b` ("Additional requirement: <rule>",
no menu). Programs a and b: one vendor's implementations, vendor alternating by problem hash. Configurations:
aud-gpt-terra-low/-high, aud-claude-sonnet-low/-high for none, menu and resolve; aud-gpt-terra-low and
aud-claude-sonnet-low for sentence. Exactly two scheduled readings per cell (80 per open unit: 64 for none, menu
and resolve, 16 for sentence); positive controls:
arm none, four configurations (16 per unit). Unrevealed arms receive balanced counterfactual scoring under both
contracts from the same readings; these are not additional observations.

A reading is retried until valid, up to three attempts; failures that never reached the model (login refresh,
"not logged in", connection refused; `e6.PRE_MODEL_INFRA`) do not count as attempts, and a Codex login-refresh failure
is retried once after resynchronising the login. Every valid reading's prompt hash must equal the prompt rebuilt
from the frozen unit; conflicting scores under one witness key abort the analysis. Duplicate valid readings abort the analysis. The required
reading universe is rebuilt from the frozen population (`e6.completeness`); analysis refuses to run with unfinished
readings or unscored witness sets.

## 6. Scoring

A reading *blocks* if it reports at least one BLOCKER; it *escalates* if its verdict is ESCALATE without a BLOCKER;
otherwise it *passes*. Policy per (unit, program, arm, configuration): flag if at least one valid reading blocks
(t = 1 of 2; if one reading is exhausted, the remaining one decides). Verified diagnosis: a witness among the
blocking readings that (i) parses as a literal call, (ii) satisfies `valid`, (iii) lies in the class (`in_class`),
(iv) is an input on which the two contract oracles differ, and (v) is a verified disagreement under judge-v3.2 against
the contract's oracle: contract B's oracle is the benchmark reference, contract A's the non-shown vendor's A
implementation. *Experimental domain:* `valid` is frozen per unit and released; where it is narrower than the task's
words (for example integer-only), verified credit is restricted to that narrower domain, and two registered
sensitivity analyses rescore with the reference's own domain (it evaluates without error) and report off-class
witnesses. Witness keys bind scorer version and source, comparator and tolerance, program, both oracles, predicates,
contract and witness text.

Under contract X, program X is correct and the other program defective. Unit value: equally weighted mean over the
configurations of the arm; a unit missing any required cell (only possible after exhausted attempts) is excluded from
that contrast, counted, and bounded in the report (every excluded unit at the worst and at the best value) for every
registered endpoint: contrasts, E6-2, E6-4 and levels.

## 7. Clean-flag budget

alpha_FPR = 10% (a budget, distinct from the 5% significance level). Compliance of the pooled resolved arm (claim
E6-1b, reported separately and not gating Family 1): the one-sided 95% upper confidence bound for the mean
problem-level resolved clean-flag rate, by the hedged capital-betting method for bounded means (Waudby-Smith and
Ramdas, JRSS-B 2024, Theorem 3; bets capped at 0.75 / (1 - m) so that every capital factor stays positive;
`betting_upper`, values in a seeded random order), is below 10%. History: v4 used a bootstrap rule that P4 showed to
be miscalibrated; v4.1's betting implementation capped bets by the wrong denominator (P5), which made it anti-
conservative (dev bound 7.5%); corrected, the dev bound is about 17% on 24 units. The budget and method were chosen
after seeing development data, which is disclosed. The exact bound on the problem-level any-clean-flag indicator and
per-configuration and per-vendor bounds are reported; pooled compliance is not claimed for any configuration.

## 8. Hypotheses (problem-level bootstrap, 10,000 draws, seed 20261113; two-sided 95% percentile intervals,
indices [floor(0.025B), ceil(0.975B) - 1])

Family 1 (open units), tested in order; each is claimed only if all earlier ones hold:
- **E6-1 (information release).** Verified coverage, resolve minus menu, lower bound > 0; and resolved coverage
  lower bound >= 50%. (The budget of section 7 is claim E6-1b, reported beside it.)
- **E6-2 (benchmark-convention advantage).** None arm, (r_B - r_A)/2 (r_B: verified diagnosis of program a under
  contract B; r_A: of program b under contract A); lower bound > 0.
- **E6-5 (ordinary-language reveal).** Sentence minus none verified coverage (sentence configurations), lower
  bound > 0.
- **E6-3 (computation after release; equivalence).** Verified coverage after resolution, high minus low reasoning
  budget, both vendors pooled: the two-sided 95% betting interval for the bounded mean difference
  (`betting_interval`) lies within [-10, +10] points. (Changed from a bootstrap interval within [-5, +5] after P4:
  the bootstrap interval collapses to [0, 0] when every difference is zero, and a valid interval for a bounded mean
  cannot reach +/-5 points at the expected sample size; placed last so that it cannot block E6-5.)

Family 2 (positive controls): **E6-4.** None arm, flag TPR (program a) minus FPR (program b), lower bound > 0.

Check, not a finding: unrevealed flag J on open units is 0 by construction (Lemma).

## 9. Secondary (no correction)

Per configuration and per vendor: E6-1, E6-2, levels (TPR, FPR, coverage, betting FPR bound) by arm; bootstrap
interval for E6-3; sentence minus resolve; flag
preference (program a minus program b) in none; decision routing (block / escalate / pass) in menu and none by
configuration; witnesses outside the class and reference-domain credit (`--credit`); t = 2 policy; convention advantage by benchmark; behavioural subset (units
whose two rules are each followed by at least one task-only solution); units on which the two judges' reasons cite
the same requirement are not used as a subset (no frozen rubric). Behavioural convention strength per unit.

## 10. Precision and bundle

Development problem-level SDs under e6-v4 (points): E6-1 16.3, E6-2 18.0, E6-3 9.8, E6-5 23.7. The registered open
test population after the enlargement (section 4) has 40 units (32 first-attempt, 8 second-attempt; 40 problems), and
the positive-control population 54. With n units the bootstrap 95% half-width is about 1.96 SD / sqrt(n): at n = 40,
about 5, 5.5, 3 and 7.5 points. The betting interval for E6-3 is wider: simulated at the development SD it is about
+/-12 points at n = 40, so the E6-3 equivalence claim (margin 10) is expected to be inconclusive and is reported as
such; the margin is not changed. If fewer than 30 open test units had been admitted, all claims would be reported
as underpowered. No further enlargement.

Bundle (checksummed, verified before the first test call): corpus and split; proposals, implementations, probes,
predicates, admission records with exclusions, red-team inputs and verdicts; judge prompts, votes and reasons; behaviour records; frozen populations
(problem ids); shown-vendor and menu-order mappings; the rendered audit prompts and the required schedule;
constitution, parser and policy; judge, comparator, tolerance and analysis code; model routes and CLI versions;
interpreter and package versions; git commit.

## 11. Limitations stated in advance

No human validation (the author declined to rate; no second rater). Judges are the same model routes that implement
the contracts (separate calls, no program text). HumanEval+/MBPP+ are likely memorised; the Lemma stays exact under
randomisation, but E6-2 may reflect memorisation as well as convention. Programs are model-written and simpler than
natural defects; positive controls are conspicuous misreadings, not difficulty-matched. The menu wording is a strong
uncertainty cue; the sentence arm is the realistic clarification format. No execution-access route.
