# E15 preregistration: matched pairs with symmetric branch bodies (2026-11-15)

## Why
E14 (held out) matched all code outside one branch body and found M_A flagged 28.9 [14.5, 42.8] points more often than
M_B (n=38; worst case 19.5 [2.4, 35.4]). Review M5 (`audit-ceiling-paper/plan/icml2027/reviews/review_gpt_M5.md`)
named the remaining difference: the branch bodies may differ in form (a loop against a single `return`; M_A's body
longer in 9 of 38 pairs), and the preference is larger where A's rule needs more code (+40.0 against +16.7). E15 adds
one constraint to E14's construction so that the two bodies have the same form. Registered after E6-E14 were known;
E15's readings are new and held out. Its code is a copy of E14's (`e15.py`; `e14.py` stays frozen) with the added
check and prompt line below.

## Added constraint
Inside the differing `if` body, the two bodies' syntax trees are identical once every expression node is replaced by
one placeholder (so statements, nesting, match cases and patterns, operators, augmented-assignment operators and
import aliases must match; only expressions may differ); their token counts (Python tokenizer, no layout tokens)
differ by at most a factor of 1.5 or by at most 4 tokens. The prompt states both, numerically. Leading decorators of
the first body statement count as part of the body. (Review P17: a first version compared statement kinds only and
missed match cases and non-expression changes; the development pairs were rechecked under this rule and all 15 still
pass.) Everything else is E14's: construction, checks (same AST position and non-constant condition, masked
trees identical, identical source outside the body, status and value equality with A and B on every registered
admission input, separation on at least two valid class inputs, visible tests), up to three attempts, audits (A, B,
M_A and M_B afresh and interleaved, task-alone arm, E6's four configurations, two readings per cell), completeness,
freeze and closure marker, and the worst-case missing-unit rule.

## Hypotheses (held out)
- E15-1 (primary): flag(M_A) - flag(M_B) with symmetric bodies: positive if the 95% lower limit of the bootstrap with
  every missing unit at the worst value is above 0.
- Reported without a claim: complete-case estimate; A - B, M_A - A and M_B - B in the same readings; E15-1 in E13's
  code-shape strata with registered and analysed counts; body token counts.

## Interpretation
A positive E15-1 means the preference persists when the two programs share all code outside one branch body and the
bodies have matching statement skeletons with bounded token-count differences. It does not establish independence
from implementation: equal token counts allow different computations, padding and long literals, and the bodies
compute different values, which is the rule itself. Body token counts are reported per pair. E15 cannot separate a convention the models share from a plain reading of the task.

## Development pilot (2026-11-15)
Construction: 15 of 16 units with a checked pair after three rounds (two attempts failed the body-form check).
Audits: 480 of 480 readings valid, completeness passes. E15-1 +38.3 [21.7, 55.0] (unit SD 35.2); with the missing unit
at the worst value [6.2, 51.6]; body token counts equal in 11 of 15 pairs, M_A longer in 2 (medians 6 and 6); A - B in the same readings +25.0; M_A - A +13.3 [3.3, 23.3]; M_B - B 0.0; code-shape
strata +41.7 (6 of 7 units) and +36.1 (9 of 9).

## Integrity
As E14: the freeze (`e15.py freeze`, after held-out construction, before any held-out audit) binds E6's code, the
product source, environments and tool versions, E6's construction records, the corpus, data and split, this file,
`e15.py`, E15's construction records, the held-out problem list, every M_A and M_B, and every required reading with
its prompt hash; the first held-out audit writes a closure marker.
