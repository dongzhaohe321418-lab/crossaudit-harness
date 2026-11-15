# E11 amendment 1 (2026-11-15): calls that never reached the model during held-out construction

Recorded after held-out construction and before the population freeze and any held-out audit. Kept outside
PREREGISTRATION-E11.md so that the protocol freeze (`records/FREEZE11_protocol.json`) still verifies; no registered
code, prompt, criterion or analysis changes.

Held-out construction (2026-11-14/15, before the population freeze and any held-out audit). The first attempt ran to
completion: 88 proposals, 71 pre-admitted, 37 admitted, 17 past the red team, 12 past both judges. In the second
attempt, 69 of 81 proposal calls exited without any recorded model usage (a provider outage); under E6's amendment 5
(`e1.reached_model`) such calls do not consume the one attempt, so, as in E7, they were moved to
`records/e6b_proposals_infra_archive.jsonl` and rerun; 12 of the rerun calls failed the same way at the end of the
run and were archived and rerun once more (harness commits 9c28fe4 and e482d6b). After that no record in E11's
construction holds a call that did not reach the model. Second attempt: 81 proposals (78 usable), 67 pre-admitted,
27 admitted, 10 past the red team, 6 past both judges. Gate: 18 units (12 + 6), met; no rendered pointer was refused.
The first gate evaluation, run before the reruns, gave 12 (12 + 0); the registered gate is the one after construction
is complete. Edit sizes are reported by `e11_report.py` (committed before any held-out audit).
