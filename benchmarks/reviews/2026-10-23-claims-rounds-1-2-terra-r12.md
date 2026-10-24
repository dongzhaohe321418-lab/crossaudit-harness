# Cross-vendor review — this release's changes (feat/tui-first), round 12

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 0910eba (the round-11 repairs: status-carrying `HEAD` reads, Git's own "ref missing" only, committed-log order through `rows_before`), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-11 injections; ask whether any way is left for two committed rulings on one escalation or for a committed row to apply what this controller did not intend. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-11 repairs verified; no path left that clears an intent after an unreadable read; DO NOT MERGE on one P1 (the `rows_before` cursor and the intent's fields live in mutable local state yet decide which committed row applies and whether a prior commit existed, so a writer of `.crossaudit/state.json` can hide a committed ruling and cause a second one, or make a foreign row apply) and one P2 (a test's foreign row lacks the `escalated_at` a real earlier ruling carries). The repair — rows signed with the project key and bound to the escalation's committed identity, recovery decided from committed and verified data only — and round 13 are recorded in `…-r13.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P1 — `src/crossaudit/controller/state.py:651-701`**  
  The new `rows_before` cursor is trusted from mutable local state. A syntactically valid but altered cursor can hide a committed ruling, clear the pending intent, and create a second committed ruling for the same escalation.

  Reproduction sequence:
  1. Force phase-3 state write failure after a `close` ruling commit, leaving its pending intent and one committed row.
  2. Change only `pending_rulings[cid]["rows_before"]` to the current committed-row count (not an invalid value).
  3. Retry with `reopen`.

  `rows[start_at:]` is empty at line 657, so lines 700-701 clear the intent; lines 712-724 create and commit a new ruling. The ledger now contains conflicting `close` and `reopen` rows for the same escalation, with a readable repository throughout.

  The same trust issue lets a committed foreign/earlier row apply: set a pending intent’s `nonce`, `action`, and `reason_sha256` to that row’s values and set `rows_before=0`. Recovery accepts that row at lines 674-696; it does not bind it to the current escalation except through state-controlled data.

  Suggested fix: do not use an unauthenticated state-only cursor as the authority boundary between old and current committed rows. Persist an append-only, committed intent/start marker (or equivalent ledger-bound escalation identity) before a ruling can be recovered, and require recovery to bind to that marker. Add regressions for both cursor advancement and complete pending-intent replacement.

  This also makes these claims overstate the implementation:
  - `README.md:1017-1023`
  - `CHANGELOG.md:46-50`
  - `docs/DECISIONS.md:8752-8768` and ruling 38  
  In particular, D176 says the state file is not an authority boundary while relying on mutable intent fields and `rows_before` to decide both which ledger row applies and whether a prior commit existed.

- **P2 — `tests/test_ruling_uncertainty_reads.py:122-158`**  
  The test says it covers “a foreign row on an earlier, already-ruled escalation,” but `_forge()` omits `escalated_at`. It therefore tests an unscoped/malformed foreign row, not the shape produced by a prior real ruling, which carries `escalated_at`. The status assertion checks `foreign_rulings`, whereas `foreign_rows()` intentionally excludes a row whose `escalated_at` differs from the present escalation.

  Suggested fix: create the foreign row with the first escalation’s actual `escalated_at`, assert it remains in ordinary ruling history, and assert the new escalation proceeds without treating it as a recovery candidate. This is a D10 false-assurance gap, although the current cursor logic does not block the normal prior-escalation flow.

## Requested round-11 reproductions

All three new uncertainty tests passed:

- Unreadable pre/post `HEAD`: refusal was  
  “**may have been committed to the ledger … the cycle stays ESCALATED, and the next ruling on this cycle recovers it**”; intent remained, one committed row existed, and the next ruling reconciled without another commit.
- Packed-refs injection: refusal was  
  “**the committed rulings log could not be read (fatal: cannot read packed-refs); no ruling is made until it can be**”; intent and HEAD remained unchanged.
- Nonce-rewriting filter then retry: first refusal said  
  “**could not be confirmed to contain it (a filter or hook changed the file)**”; after removing the filter, retry refused  
  “**does not match this controller’s intent (intent); nothing was applied**”; intent remained and there was one row.
- Earlier foreign-row sequence: the test passed; its status result listed the forged row and the later ruling committed once. The P2 above explains why it does not prove the claimed `escalated_at` shape.

I found no remaining path that clears an intent after an unreadable committed-log read: both recovery and fresh-ruling setup use strict committed-log reads. I did find the P1 paths above for two committed rulings and applying a row not intended by this controller.

## Verification performed

Read in full:

- `src/crossaudit/rulings.py`
- `tests/test_ruling_uncertainty_reads.py`
- `tests/test_ruling_intent_binding.py`

Inspected the relevant recovery/state, Chinese-denial, fixture, README, CHANGELOG, and D175/D176 sections. `git diff --check c26e74e..HEAD` was clean. The new English denials have Chinese entries and passed translation/runtime-fixture checks.

Executed with the requested environment prefix:

- `tests/test_ruling_uncertainty_reads.py` — 3 passed
- `tests/test_ruling_intent_binding.py -k 'not genuinely_unborn'` — 7 passed, 1 deselected
- `tests/test_ruling_two_phase_intent.py` — 10 passed
- `tests/test_ruling_reconciled_from_ledger.py -k 'not console'` — 9 passed, 1 deselected
- `tests/test_resolve_commits_the_ruling.py -k 'not hook_slower'` — 12 passed, 1 deselected
- `tests/test_resolve_commits_the_ruling.py::test_a_hook_slower_than_the_commit_timeout_fails_the_ruling_inside_the_lock` — 1 passed
- `tests/test_kernel_held_locks.py` — 15 passed
- denial/i18n targeted checks — 10 passed, 49 deselected

I skipped the two loopback-console cases because loopback binds are denied in this sandbox. I did not run the full suite.

VERDICT: DO NOT MERGE — mutable `rows_before`/intent state can bypass committed-ruling recovery and produce conflicting committed rulings