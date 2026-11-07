# E6 preregistration: contract-randomised information release

Draft, 2026-11-07. Frozen when committed with the pre-test bundle, before any E6 test audit. Code:
`icml/e6.py` (construction, audits, witnesses), `icml/analyse_e6.py` (analysis). Design rationale:
`audit-ceiling-paper/plan/icml2027/CEILING_PROGRAM.md` (v3) and GPT reviews P1, P2.

## What was seen before registration

The full development pilot: construction on the 136 development problems (75 proposals, 55 execution-admitted
units, 50 rated compatible on both rules by both judges), behavioural evidence (94.5% of classified task-only
solutions follow RULE_B), and all development audits (3,520 readings) and results:
unrevealed flags 13.4% on defective and correct programs alike; menu 1.6%; resolved TPR 100%, FPR 0.9%, verified
coverage 95.0%; convention advantage +11.4 [6.4, 16.6]; reasoning-budget effect after resolution +0.9 [-0.9, 2.7];
the development positive controls. Test units are constructed (proposal, implementation, admission, judging,
behaviour) before registration; no test audit exists.

## Units and population

- *Open units* (primary): test problems (frozen problem-level split, 406 test problems) whose proposal yields two
  rules, whose four implementations pass execution admission (e6.py `stage_validate`), and whose two rules are both
  rated compatible by both judges (Claude Opus, GPT-6.1-sol; blind, order randomised). One unit per problem.
- *Positive controls*: test problems whose proposal (positive-control prompt) yields a misreading RULE_A and the
  required RULE_B, passing the same execution admission, with both judges rating RULE_A incompatible and RULE_B
  compatible. Evaluated under contract B only.
- No unit is added or removed after the first test audit. Units lost to infrastructure are reported.

## Arms, programs, configurations, readings

Open units: arms none, menu, resolve-a, resolve-b (texts by `arm_text`); programs a and b (the shown vendor's
implementations, vendor alternating by problem hash); configurations aud-gpt-terra-low, aud-gpt-terra-high,
aud-claude-sonnet-low, aud-claude-sonnet-high; two readings per cell (64 per unit). Positive controls: arm none
only (16 per unit). Same audit prompt as E1 (shipped constitution plus witness rule). A reading is retried up to
three attempts; invalid replies count as missing.

## Scoring and policy

A reading flags if it reports at least one BLOCKER. The deployable policy for a (unit, program, arm,
configuration) cell flags if at least one of its valid readings flags (k = 2, t = 1, chosen on development: resolved
FPR 0.9%). Its verified diagnosis is any verified witness among its flagging readings, scored by judge-v3.2 against
the contract's oracle implementation (the other vendor's implementation of that rule), with the input required to
be valid for the benchmark reference. Under contract X, program X is correct and the other program defective.
Unrevealed arms are scored under both contracts with the same readings. Unit value: mean over the configurations
with both cells present; a unit enters a contrast if at least one configuration does.

Clean-flag budget alpha = 5%: the resolved-arm FPR must have its 95% upper bound below 5%.

## Hypotheses (open units unless stated; problem-level bootstrap, 10,000 draws, seed 20261113; percentile
interval [floor(0.025B), ceil(0.975B) - 1]; tested in order, each claimed only if all earlier ones hold)

- **E6-1 (information release).** Verified coverage, resolve minus menu, lower bound > 0; and, as absolute criteria,
  resolved verified coverage lower bound >= 50% and resolved FPR upper bound < 5%.
- **E6-2 (benchmark-convention advantage).** In the none arm, (r_B - r_A)/2, where r_B is verified diagnosis of
  program a under contract B and r_A of program b under contract A; lower bound > 0.
- **E6-3 (computation after release).** Verified coverage after resolution, high minus low reasoning budget (both
  vendors). Claimed as "no difference larger than 5 points" if the interval lies within [-5, +5]; as a difference if
  it excludes 0; otherwise inconclusive.
- **E6-4 (positive control).** On positive-control units in the none arm, flag TPR (program a) minus FPR (program
  b), lower bound > 0.

By construction, unrevealed flag TPR equals FPR on open units (Lemma); it is reported as a check, not a finding.

## Secondary (no correction)

Every primary quantity per configuration and per vendor; levels (TPR, FPR, verified coverage) by arm; flag
preference (program a minus program b) in none; menu-arm abstention; t = 2 policy; sensitivity subsets: units whose
two rules are each followed by at least one task-only solution, and units with unanimous judge reasons; convention
advantage by benchmark (HumanEval+, MBPP+). Behavioural convention strength per unit is reported descriptively.

## Precision

Development problem-level SDs (points): E6-1 17.1, E6-2 19.1, E6-3 6.7. With about 150 or more test units the
95% interval half-widths are near 3, 3 and 1 points. No enlargement rule is needed; if fewer than 60 open test units
are admitted, all claims are reported as underpowered.

## Limitations stated in advance

No human validation (the author declined to rate; no second rater): admissibility rests on execution and a blind
two-vendor judge panel, and behaviour measures convention strength rather than admissibility. HumanEval+/MBPP+ are
likely memorised; contract randomisation keeps the Lemma exact regardless, but E6-2 may reflect memorisation as well
as convention. Proposals and implementations are model-written. The execution-access route is not part of E6.
