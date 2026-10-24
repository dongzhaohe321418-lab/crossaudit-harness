# Cross-vendor review — this release's changes (feat/tui-first), round 11

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at c26e74e (the round-10 repairs: commit-landed marks, the unborn-HEAD test, full-row confirmation and bound recovery), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-10 injections; ask whether any way is left for two committed rulings on one escalation or for a committed row to apply what this controller did not intend. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-10 repairs verified in their tested paths; DO NOT MERGE on three P1, all in how uncertainty is read (two unreadable `HEAD` reads compare equal and "prove" a commit did not land; any non-zero `show-ref` reads as "branch absent"; a committed row for the current escalation that is not a complete bound match reads as "no row"), and one P2 (README, CHANGELOG and D176's ruling 1 still say a failed commit means "nothing is recorded" without the qualification ruling 33 made). The repairs and round 12 are recorded in `…-r12.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Found three P1s and one P2. Do not merge.

- **P1** — [rulings.py:466](src/crossaudit/rulings.py:466): failed `rev-parse` reads collapse to `""`, so two unreadable HEAD checks compare equal and falsely prove that a failed commit did not land.

  I injected a post-commit failure after a real successful `git commit`, plus unreadable pre/post HEAD checks. The first call said “could not be committed … nothing was recorded,” cleared the intent, yet the commit count increased; the next ruling made another commit. Result: 2 ruling commits, final state `BLOCKED`, only one line at `HEAD`—also breaking the append-only working-log claim.

  Fix: return/retain HEAD-read status, not just stdout. Clear an intent only when both pre- and post-commit HEADs were positively read and equal. Any unreadable check is `_Uncertain`, with no restore/reset and intent retained. Add this exact regression.

- **P1** — [rulings.py:540](src/crossaudit/rulings.py:540)-[546](src/crossaudit/rulings.py:546): strict recovery treats *any* nonzero `git show-ref` as “branch absent,” including a Git/read failure.

  Reproduction: inject `rev-parse` → `128, "", "fatal: corrupt HEAD"`; `symbolic-ref` → `refs/heads/main`; `show-ref` → `128, "", "fatal: cannot read packed-refs"`. `committed_rows(strict=True)` returned `[]`, not the required refusal. This permits an intent to be cleared and a new ruling written under an unreadable repository state.

  Fix: accept unborn HEAD only when `show-ref` returns Git’s specific “ref missing” result (exit 1); refuse every other nonzero result in strict mode. Add the injected `show-ref` failure case.

- **P1** — [state.py:641](src/crossaudit/controller/state.py:641)-[678](src/crossaudit/controller/state.py:678): a committed row whose clean filter changed the nonce is not a `match`, so recovery assumes no commit, clears the intent, and writes a second ruling.

  I ran the supplied nonce-rewriting clean filter, received the expected first refusal: “could not be confirmed to contain it (a filter or hook changed the file)”. After removing the filter and retrying, recovery was not reconciled and produced two committed rows (`intent` values `00000000` and the new nonce), then applied the second close.

  Fix: with a pending intent, any committed row for the current escalation that is not a complete bound match must refuse and retain the intent, rather than treating it as no row. This may deliberately require manual repository repair, as the action/reason mismatch path already does. Extend `test_a_filter_that_rewrites_the_nonce_stops_phase_3` through a retry and assert one commit/row.

- **P2** — [README.md:1014](README.md:1014)-[1018](README.md:1018), [CHANGELOG.md:43](CHANGELOG.md:43)-[45](CHANGELOG.md:45), [DECISIONS.md:8402](docs/DECISIONS.md:8402)-[8406](docs/DECISIONS.md:8406): these say a failed commit means “nothing is recorded” / the log is restored. D176 ruling 33 correctly recognizes uncertain failures that may already have committed; the first P1 demonstrates the claim is false.

  Fix: qualify this as “when Git is positively known not to have committed and HEAD is unchanged”; document uncertainty as intent-preserving and fail-closed. D175 itself appeared current.

Verified repairs that do work:

- One-shot post-commit `cat-file` failure keeps the intent, says “could not be read back to confirm it … the next ruling on this cycle recovers it,” and reconciles without a second row.
- The tested corrupt-`rev-parse` path refuses: “the committed rulings log could not be read (fatal: corrupt HEAD); no ruling is made until it can be.”
- A genuine unborn repository accepts no rows, clears a stale intent, makes its first commit, and ends `BLOCKED`.
- Forged local action/reason-hash intent is refused; direct `_confirm_committed` with a changed nonce is refused.
- The new denial strings have Chinese entries; static denial coverage passed.

Read in full: `AGENTS.md`, `src/crossaudit/rulings.py`, `tests/test_ruling_two_phase_intent.py`, and `tests/test_ruling_intent_binding.py`. I also read the relevant `StateStore.rule_escalation` implementation, changed Chinese catalogue entries and fixture, D175/D176, README, CHANGELOG, and related ruling/lock/ledger tests.

Tests run:

- `… pytest -q --timeout=30 tests/test_ruling_two_phase_intent.py` — 10 passed
- `… tests/test_ruling_intent_binding.py -k 'not genuinely_unborn_repository'` — 7 passed, 1 deselected
- `… tests/test_ruling_reconciled_from_ledger.py -k 'not console'` — 9 passed, 1 deselected
- `… tests/test_resolve_commits_the_ruling.py` — 13 passed
- `… tests/test_kernel_held_locks.py` — 15 passed
- `… tests/test_evidence_ledger.py` — 12 passed
- `… tests/test_denial_strings_are_legible.py -k 'not console_serves_the_refusal_in_both_languages_on_the_wire'` — 18 passed, 1 deselected

The omitted HTTP cases cannot bind `127.0.0.1` in this sandbox (`PermissionError: EPERM`). I made no tree changes.

VERDICT: DO NOT MERGE — three remaining fail-open paths can create a second committed ruling or clear an intent while repository state is unreadable