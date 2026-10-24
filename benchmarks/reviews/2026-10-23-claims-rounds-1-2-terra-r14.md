# Cross-vendor review — this release's changes (feat/tui-first), round 14

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 91c8158 (the round-13 repairs: escalations as committed signed rows, the escalation gate, no implicit key recreation, the lineage walk past ledger-only commits; the slot-phrase translations), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-13 sequences; ask whether the escalation row, the lineage change or the fail-open receipt signing opens anything. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-13 identity repair held in every targeted case, and no tested path remains for two committed rulings on one committed escalation; DO NOT MERGE on two P1 in the new code (an escalation's post-commit confirmation that times out escapes as a raw exception, abandoning the state write, so the cycle stays OPEN; the lineage walker stops after 64 ledger-only commits and returns a ledger commit, so a child could open a fresh cycle past an escalation lock) and one P2 (README and CHANGELOG say every escalation is a signed line without the cannot-commit exception). The repairs and round 15 are recorded in `…-r15.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P1 — `src/crossaudit/rulings.py:775-784`, `src/crossaudit/controller/state.py:720-725`**  
  An escalation can commit successfully, then escape as a raw `_StepFailed` if its post-commit `git cat-file` confirmation times out or cannot start. That exception is neither wrapped as `EscalationNotCommitted` nor caught by CLI/build callers (which catch `Denial`); the state write is abandoned, so it remains OPEN and a traceback can escape. This violates the promised fail-closed outcome for an escalation whose ledger confirmation fails.  
  Concrete sequence: let `git commit` succeed, then make the confirmation `git cat-file blob HEAD:cycles/rulings.jsonl` hit its 5-second bound. `_bounded_bytes()` raises at line 776 outside the handler.  
  Fix: wrap the post-commit confirmation path and convert `_StepFailed` to `EscalationNotCommitted`; persist ESCALATED with empty `escalation_commit`, then refuse rulings until repair. Add a fault-injection regression test asserting no traceback and no OPEN/PASS path.

- **P1 — `src/crossaudit/gitio.py:188-194`, consumed by `src/crossaudit/cli/main.py:286-293`**  
  `past_ledger_commits()` silently stops after 64 ledger-only commits and returns a ledger commit rather than the nearest work commit. A child of the current escalation row then opens a fresh cycle instead of returning `blocked_by_escalation`, bypassing the pending-decision lock.  
  Concrete sequence: active work commit `A`, followed by 65 CrossAudit ledger-only commits (`cycles/` reports, receipts, or repeated pre-revision/provider-stop rows), then work commit `W` whose parent is the latest ledger commit. `_lineage_parent(W)` returns the first ledger commit rather than `A`; `open_or_advance()` finds no cycle whose active SHA equals that parent and creates a new OPEN cycle. I exercised the actual walker with a 65-node ledger chain; it returned `L1`, not the work ancestor.  
  Fix: walk to the first non-ledger ancestor without an arbitrary cap, or refuse fail-closed when the bound is reached. Add a 65+ ledger-commit regression test through `_lineage_parent()` and `open_or_advance()`.

- **P2 — `README.md:1021-1024`, `CHANGELOG.md:49-53`**  
  Both overclaim: “every escalation and every ruling is a line signed…” The explicitly supported failure path leaves an escalation in state with no committed row/signature (`escalation_commit == ""`) and blocks rulings. D176 describes that exception, but README and CHANGELOG do not.  
  Fix: say “every committed escalation or ruling row written by this version is signed,” and state that an escalation whose row cannot commit remains ESCALATED and cannot be ruled on until repaired.

## Requested verification

The round-13 identity repair itself held in the targeted tests:

- Post-commit `reopen` state-write failure, then tampering both by dropping the intent and by adding the nonce to `ruling_intents`: exactly one ruling row remained; the second `reopen` reconciled it without another commit.
- Reopen → new provider stop without a receipt created a second escalation row/identity; closing it was fresh and did not recover the earlier reopen.
- A refusing hook left the cycle ESCALATED with status text `"escalation not committed (pre-commit: refused by policy)"`; ruling refused: `"the escalation of cycle <cid> is not committed to the ledger (pre-commit: refused by policy); rule on it after the repository is repaired"`.
- A legacy escalation acquired its row on the next successful ruling.
- Missing seed with signed artefacts refused and did not recreate it: `"the project signing key at <path> is missing but signed rulings or receipts exist; restore it from your backup, since a new key would not verify them"`. Receipt signing remained unsigned. With no signed artefacts, a seed was created.

I found no remaining tested CrossAudit path for two committed rulings on one committed escalation, or for a ruling to recover an old reopen after a genuine new stop. Invalid/forged current ruling rows refuse; unverified escalation rows do not establish identity; a ruling requested while state is not ESCALATED still refuses. The receipt-signing fail-open path does not weaken ruling signing. The new 64-commit lineage limit is the remaining lock bypass.

Read in full: `src/crossaudit/rulings.py`, `src/crossaudit/crypto/keys.py`, `tests/test_ruling_escalation_rows.py`, and `tests/test_slot_phrases_translated.py`. I also inspected the affected controller, Git lineage, CLI/build, daemon, i18n, README, CHANGELOG, D176, and the requested test files.

Tests run:

- Requested six-file command: **54 passed, 1 error**. The error was the known loopback-binding sandbox restriction in `test_a_genuinely_unborn_repository_reads_as_no_rows` (`PermissionError: [Errno 1] Operation not permitted`).
- Same command excluding that HTTP-dependent test: **54 passed, 1 deselected**.
- `tests/test_slot_phrases_translated.py tests/test_denial_strings_are_legible.py tests/test_cli_i18n.py -k 'not console_serves_the_refusal_in_both_languages_on_the_wire'`: **77 passed, 1 deselected**.

VERDICT: DO NOT MERGE — raw escalation-confirmation failure can escape and the 64-commit lineage cap bypasses an escalation lock