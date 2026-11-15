# E14 preregistration: rule x code form (2026-11-15)

## Why
E6's task-alone arm flags the program that departs from the benchmark's behaviour (A) more than the one that follows
it (B). E13 (held out) found that adding a behaviour-preserving branch to B barely changes its flag rate (+0.6
[-1.2, 2.5]) while A is still flagged 20.6 [6.9, 33.8] points more often than the branched B, the residual preference
concentrated in units whose A has more conditionals than B. Review M4 (`review_gpt_M4.md`) asked whether A's own
implementation draws the flags and proposed rewriting both rules into matched forms. Registered after E6-E13 were
known; E6's and E13's held-out readings are known; E14's readings are new and held out.

## Programs (per registered E6 open unit; 16 development, 41 held out)
a = A and b = B (E6's audited programs); c = B' (E13's checked edit: B plus an explicit class branch; units without
one are missing); d = A_min; e = A_br. The vendor that wrote the unit's audited programs (`shown_route`) receives
the task, program A and the class description:
- A_min (`PROMPTS["amin"]` in `e14.py`): compute exactly A's result with as few `if` statements and conditional
  expressions as possible, with no branch, condition or early return dedicated to the class; check: fewer
  conditionals than A when A has any.
- A_br (`PROMPTS["abr"]`, E13's prompt applied to A): an explicit class branch computing A's behaviour, every other
  line kept; checks as E13's (at least one conditional added, no line of A removed).
Both: same status as A and equal value under E6's comparator on every registered admission input (E13's input set),
visible tests pass, units without hidden inputs fail; one second edit after a failure; calls that never reach the
model and executor infrastructure failures consume no attempt. A unit enters the analysis only with c, d and e.

## Audits
a, b, c, d and e are read afresh, interleaved in one seeded random order, in E6's task-alone arm with E6's four
configurations, two readings per cell (40 per unit), E6's frozen prompt, rulebook, parser, witness execution, scoring
and cell policy. E6's completeness check must pass before analysis.

## Hypotheses (held out; problem-level bootstrap, 10,000 draws; every registered unit in the denominator, missing
units at the registered worst and best values; a verdict needs the interval and the bound)
- E14-1 (primary): flag(A_min) - flag(B), both minimal: positive if the 95% lower limit and lower bound are above 0.
  A positive result means the preference does not need A's extra code.
- E14-2: flag(A_br) - flag(B'), both with an explicit branch: same criterion.
- Reported without a claim: flag(A_br) - flag(A_min) (form within rule A); the interaction (A_br - B') - (A_min - B);
  A - B and A - A_min in the same readings; B' - B (replicating E13); E14-1 in the prespecified stratum where A_min
  has no more control constructs (if, conditional expressions, try, and/or, match) than B, and in the rest.

## Interpretation
A_min and A_br are rewrites by the vendor that wrote A; A_min may hide special cases in other constructs (hence the
stratum by control constructs). E14 varies the form of each rule's code, not the rule; it cannot separate a
convention the models share from a plain reading of the task.

## Development pilot (2026-11-15)
Construction: A_min passed on 16 of 16 units, A_br on 15 (one unit added no branch, one changed a line of A in a
failed attempt); 15 units have c, d and e; 12 of the 15 A_min have no more control constructs than B (with `if`s alone,
all 16 would, because some rewrites move the case into try/except or and/or, hence the stratum's definition).
Audits: 600 of 600 readings valid, completeness passes. E14-1 A_min - B +30.0 [10.0, 51.7] (unit SD 42.5; 12-unit
stratum +31.2); E14-2 A_br - B' +41.7 [21.7, 61.7]; A - B +31.7; A - A_min +1.7 [-5.0, 8.3]; A_br - A_min +11.7
[5.0, 20.0]; B' - B 0.0 [-5.0, 5.0].

## Integrity
Freeze (`e14.py freeze`, after held-out construction, before any held-out audit) binds E13's freeze contents (E6's
code, product source, environments, tool versions, E13's construction and every B'), this file, `e14.py`, E14's
construction records, every program d and e, and every required reading with its prompt hash. Audits and analysis
verify it; it cannot be rewritten once a held-out E14 audit record exists.
