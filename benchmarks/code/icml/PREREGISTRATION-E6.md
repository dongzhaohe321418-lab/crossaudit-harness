# E6 preregistration: contract-randomised information release (protocol e6-v4)

Draft v4, 2026-11-07. Frozen when committed with the verified pre-test bundle (section 10), before any E6 test
audit. Code: `icml/e6.py` (construction, audits, witnesses, completeness), `icml/analyse_e6.py` (analysis),
`icml/e1.py` (judge-v3.2, routes). Rationale: `audit-ceiling-paper/plan/icml2027/CEILING_PROGRAM.md` v3; GPT reviews
P1, P2, P3 (`review_gpt_P3.md`: test release refused; every blocker is addressed below).

## 1. Prior exposure

Development only. (a) Pilot e6-v3 (55 execution-admitted units; 50 in its judge population): reported in P3.
(b) After P3, construction was revised (sections 3-4) and the development audits were rerun under e6-v4 (3,440 open
readings, 864 positive-control readings). Development results under e6-v4 (27 open units in the registered
population): unrevealed flags 15.7% on defective and correct programs alike; menu 0.9%; resolved TPR 100%, FPR 1.9%
(bootstrap upper 4.2%), target-verified coverage 91.7%; sentence reveal coverage 91.7%; E6-1 +91.7 [85.2, 97.2];
E6-2 +12.5 [6.0, 19.4]; E6-3 0.0 [-3.7, 3.7]; positive controls (48 units) J 90.6 [83.9, 96.4]. The resolved-FPR
boundary rule (section 7) was fixed after seeing that the conservative any-clean-flag bound alone (3 of 27 units,
exact upper 26%) cannot certify a 5% budget at this sample size; this is disclosed. Test units were constructed
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
5. *Admission v4* (`stage_validate4`): on every input the `valid` predicate accepts and the reference evaluates,
   among the hidden suite, the proposer's inputs and the probes: both B implementations agree with the reference;
   outside the class all four implementations agree with the reference; inside it the two A implementations agree;
   A and B differ on at least two valid class inputs; predicates never raise; all implementations pass the visible
   tests. Infrastructure failures are reported separately from substantive rejections.
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
- Frozen in the bundle by problem id, with every exclusion and its reason. No unit enters or leaves after the first
  test audit.

## 5. Arms, programs, configurations, readings

Open units: arms `none`; `menu` (both rules, numbered in a per-unit order fixed by problem hash and independent of
the contract, preceded by "the function must follow exactly one of these two rules, and the task author has fixed
which" and followed by "The task does not say which of the two rules applies"); `resolve-a`, `resolve-b` (the same
menu followed by "The function must follow rule (k)"); `sentence-a`, `sentence-b` ("Additional requirement: <rule>",
no menu). Programs a and b: one vendor's implementations, vendor alternating by problem hash. Configurations:
aud-gpt-terra-low/-high, aud-claude-sonnet-low/-high for none, menu and resolve; aud-gpt-terra-low and
aud-claude-sonnet-low for sentence. Exactly two scheduled readings per cell (72 per open unit); positive controls:
arm none, four configurations (16 per unit). Unrevealed arms receive balanced counterfactual scoring under both
contracts from the same readings; these are not additional observations.

A reading is retried until valid, up to three attempts; infrastructure errors that never reached the model (for
example a blocked login refresh) do not count as attempts. Duplicate valid readings abort the analysis. The required
reading universe is rebuilt from the frozen population (`e6.completeness`); analysis refuses to run with unfinished
readings or unscored witness sets.

## 6. Scoring

A reading *blocks* if it reports at least one BLOCKER; it *escalates* if its verdict is ESCALATE without a BLOCKER;
otherwise it *passes*. Policy per (unit, program, arm, configuration): flag if at least one valid reading blocks
(t = 1 of 2; if one reading is exhausted, the remaining one decides). Verified diagnosis: a witness among the
blocking readings that (i) parses as a literal call, (ii) satisfies `valid`, (iii) lies in the class (`in_class`;
target-discrepancy credit; witnesses outside the class are reported separately), and (iv) is a verified disagreement
under judge-v3.2 against the contract's oracle: contract B's oracle is the benchmark reference, contract A's the
non-shown vendor's A implementation. Witness cache keys bind scorer version and source, comparator, program, oracle,
predicates, contract and witness text.

Under contract X, program X is correct and the other program defective. Unit value: equally weighted mean over the
configurations of the arm; a unit missing any required cell (only possible after exhausted attempts) is excluded from
that contrast, counted, and bounded (best and worst case) in the report.

## 7. Clean-flag budget

alpha_FPR = 5% (a budget, distinct from the 5% significance level). Compliance of the pooled resolved arm: the
bootstrap upper bound of the resolved FPR is below 5%; if that interval is [0, 0], the exact one-sided 95% bound on the
problem-level indicator of any clean-cell flag must also be below 5%. The exact bound is reported in every case.
Pooled compliance is not claimed for individual configurations, which are reported separately.

## 8. Hypotheses (problem-level bootstrap, 10,000 draws, seed 20261113; two-sided 95% percentile intervals,
indices [floor(0.025B), ceil(0.975B) - 1])

Family 1 (open units), tested in order; each is claimed only if all earlier ones hold:
- **E6-1 (information release).** Verified coverage, resolve minus menu, lower bound > 0; and resolved coverage
  lower bound >= 50%; and the budget rule of section 7.
- **E6-2 (benchmark-convention advantage).** None arm, (r_B - r_A)/2 (r_B: verified diagnosis of program a under
  contract B; r_A: of program b under contract A); lower bound > 0.
- **E6-3 (computation after release; equivalence).** Verified coverage after resolution, high minus low reasoning
  budget, both vendors pooled: the interval lies within [-5, +5] points.
- **E6-5 (ordinary-language reveal).** Sentence minus none verified coverage (sentence configurations), lower
  bound > 0.

Family 2 (positive controls): **E6-4.** None arm, flag TPR (program a) minus FPR (program b), lower bound > 0.

Check, not a finding: unrevealed flag J on open units is 0 by construction (Lemma).

## 9. Secondary (no correction)

Per configuration and per vendor: E6-1, E6-2, levels (TPR, FPR, coverage) by arm; sentence minus resolve; flag
preference (program a minus program b) in none; decision routing (block / escalate / pass) in menu and none by
configuration; witnesses outside the class; t = 2 policy; convention advantage by benchmark; behavioural subset (units
whose two rules are each followed by at least one task-only solution); units on which the two judges' reasons cite
the same requirement are not used as a subset (no frozen rubric). Behavioural convention strength per unit.

## 10. Precision and bundle

Development problem-level SDs under e6-v4 (points): E6-1 16.3, E6-2 18.0, E6-3 9.8, E6-5 23.7. With n open test units the 95%
half-width is about 1.96 SD / sqrt(n): at n = 60, about 4, 4 and 2 points. If fewer than 30 open test units are
admitted, all claims are reported as underpowered. No enlargement.

Bundle (checksummed, verified before the first test call): corpus and split; proposals, implementations, probes,
predicates, admission records with exclusions; judge prompts, votes and reasons; behaviour records; frozen populations
(problem ids); shown-vendor and menu-order mappings; the rendered audit prompts and the required schedule;
constitution, parser and policy; judge, comparator, tolerance and analysis code; model routes and CLI versions;
interpreter and package versions; git commit.

## 11. Limitations stated in advance

No human validation (the author declined to rate; no second rater). Judges are the same model routes that implement
the contracts (separate calls, no program text). HumanEval+/MBPP+ are likely memorised; the Lemma stays exact under
randomisation, but E6-2 may reflect memorisation as well as convention. Programs are model-written and simpler than
natural defects; positive controls are conspicuous misreadings, not difficulty-matched. The menu wording is a strong
uncertainty cue; the sentence arm is the realistic clarification format. No execution-access route.
