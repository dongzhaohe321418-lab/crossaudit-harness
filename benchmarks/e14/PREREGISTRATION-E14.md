# E14 preregistration: matched pairs (2026-11-15)

## Why
E6's task-alone arm flags the program that departs from the benchmark's behaviour (A) more than the one that follows
it (B). E13 (held out) found that adding a behaviour-preserving branch to B barely changes its flag rate (+0.6
[-1.2, 2.5]) while A is still flagged 20.6 [6.9, 33.8] points more often, the residual preference concentrated in
units whose A has more conditionals. Review M4 (`review_gpt_M4.md`) asked whether A's own implementation draws the
flags and proposed matching the form of the two rules' code. Registered after E6-E13 were known; E6's and E13's
held-out readings are known; E14's readings are new and held out.

A first design (A rewritten with few conditionals, and A with an added branch) was piloted on development units and
rejected by review P15 (`review_gpt_P15.md`): fewer conditionals did not establish that the special case had gone
(it survived as arithmetic on a comparison), an unreachable added branch would pass the structural check, the nested
freeze did not bind the corpus or split, the closure guard depended on the current split, and the decision rule was
not a missing-data-robust test. Its records are in `records/pilot_v1/` and `records/pilot_v1b/` and are not used.

## Programs (per registered E6 open unit; 16 development, 41 held out)
The vendor that wrote the unit's audited programs (`shown_route`) receives the task, programs A and B and the class
description, and writes a matched pair (`PAIR_PROMPT` in `e14.py`): M_A computing exactly what A computes and M_B
exactly what B computes, identical character for character except inside the body of one `if` statement whose
condition selects the class. Checks, by execution and parsing, no model:
- M_A has A's status and value and M_B has B's on every registered admission input (E13's input set: hidden suite,
  proposer inputs, probes, stress and red-team inputs, interface inputs only); units without hidden inputs fail;
- both parse, and every line on which they differ lies inside the body of one `if` whose header line is identical in
  both; the programs are not identical. Since A and B differ on at least two valid class inputs (E6's admission),
  the differing body is reached on those inputs;
- both pass the visible tests.
Up to three pairs per unit (raised from two after the development pilot, before any held-out construction,
because each missing unit weighs heavily under the worst-case rule below); calls that never reach the model and executor infrastructure failures consume no
attempt.

## Audits
A, B, M_A and M_B are read afresh, interleaved in one seeded random order, in E6's task-alone arm with E6's four
configurations, two readings per cell (32 per unit), E6's frozen prompt, rulebook, parser, witness execution,
scoring and cell policy. E6's completeness check must pass before analysis.

## Hypotheses (held out; problem-level bootstrap, 10,000 draws)
Every registered unit is in the denominator. Units without a checked pair or with an incomplete schedule are missing;
the bootstrap is recomputed with every missing unit at the worst value (and, separately, the best), and a verdict
needs the 95% lower limit of the worst-case bootstrap above 0.
- E14-1 (primary): flag(M_A) - flag(M_B), the preference with the two rules' code matched except for one branch body.
- Reported without a claim: flag(A) - flag(B) in the same readings; flag(M_A) - flag(A) and flag(M_B) - flag(B)
  (effect of the common form within each rule); the difference (M_A - M_B) - (A - B) with bounds [-2, +2]; E14-1 in
  E13's code-shape strata, with registered and analysed counts.

## Interpretation
The matched programs differ only in what the branch computes, so a positive E14-1 means the preference does not need
differences in the surrounding code. Within the branch the two rules still differ, and M_B's branch often repeats
what the general path computes, which a reader can notice (if anything this should draw flags to M_B). E14 varies
the form of the code, not the rule; it cannot separate a convention the models share from a plain reading of the
task. The pairs are written by the vendor that wrote A and B.

## Development pilot (2026-11-15)
Construction: 15 of 16 units with a checked pair in two attempts (one failed: M_A differed from A, then M_B from B).
Audits: 480 of 480 readings valid, completeness passes. E14-1 +26.7 [6.7, 48.3] (unit SD 42.7); with the missing
unit at the worst value the bootstrap gives [-6.25, 43.75], so the development verdict would be negative; A - B in
the same readings +25.0 [6.7, 45.0]; (M_A - M_B) - (A - B) +1.7 [-15.0, 20.0]; M_A - A +3.3, M_B - B +1.7. Power: at
the development SD, 41 units give a complete-case interval of roughly +/-13 points; each missing unit at the worst
value lowers the estimate by about 3 points and widens the interval, so the verdict is sensitive to missingness.

## Integrity
Freeze (`e14.py freeze`, after held-out construction, before any held-out audit) binds E6's code, the product source,
both environments' package lists and tool versions (E13's state function), E6's construction records, the corpus
module, data files and frozen split, this file, `e14.py`, E14's construction records, the list of held-out problems,
every program M_A and M_B, and every required reading with its prompt hash. Audits and analysis verify it. The first
held-out audit writes a closure marker; construction and the freeze refuse once it exists or once any audit row
recorded with split "test" exists.
