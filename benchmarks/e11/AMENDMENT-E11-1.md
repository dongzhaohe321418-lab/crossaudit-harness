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

## Addendum (2026-11-15, after the held-out audits; review M3)
- The archived proposal rows keep the error (`exit 1:` with empty output) but not usage or `reached`: E6's proposal
  stage does not store them, and the isolated Codex home kept no transport log. The classification as calls that did
  not reach the model therefore rests on the exit status, as `e1.reached_model` defines it. The archive holds 81 calls
  on 69 distinct tasks; the repeats used identical prompts.
- Gate reports before construction was complete were 12 (before the first rerun) and 17 (before the second); the
  registered gate, 18, was evaluated after all eligible construction calls had completed.
- E11-3's subset contrasts: E9's `subset_e6` reads E6's results, so E9's analysis failed on E11's units; the adapter
  `e11_admissibility.py`, which computes E11-1 and E11-2 on E9's subsets with E6's frozen contrast code, was written
  after the held-out audits. E11-3 is descriptive.
- `e11_report.py` reported the upper median of edit sizes (4); the median is 3.5 (corrected).
