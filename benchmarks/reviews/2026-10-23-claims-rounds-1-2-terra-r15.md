# Cross-vendor review — this release's changes (feat/tui-first), round 15

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 73e26b0 (the round-14 repairs: the escalation confirmation inside the conversion, the uncapped lineage walk, the ledger-row commit budget), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-14 sequences; ask whether any way is left for a lost escalation, two committed rulings on one committed escalation, or a run routing around a pending decision. **Run by:** the Claude lead, 2026-10-24. **Verdict:** all three sequences verified and "no inspected CrossAudit-controlled route" left for any of the three; DO NOT MERGE on one P2 (the row-budget regression inspects source for a call instead of exercising a ruling under a hung hook) and one P3 (a test docstring still says the ruling's bound is 90 s instead of git's). The repairs and round 16 are recorded in `…-r16.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P2 — [tests/test_escalation_paths_round14.py:124](tests/test_escalation_paths_round14.py:124)**  
  The new row-budget regression does not execute the claimed behavior. It verifies `row_budget()` itself, then searches function source for `"row_budget()"`. A mutant that changes `rule()` to use `COMMIT_TIMEOUT_S` but leaves a `# row_budget()` comment passes this test, while a ruling under `CROSSAUDIT_GIT_TIMEOUT=2` again holds the lock for 90 seconds.  
  Reproduction shape: install a `sleep 30` pre-commit hook, set `CROSSAUDIT_GIT_TIMEOUT=2`, call `rulings.rule(...)`; this must time out at 2 seconds.  
  Fix: replace the source inspection with a real ruling-hook test asserting the elapsed bound and `"git commit timed out after 2s"`. Keep the existing real escalation-hook test.

- **P3 — [tests/test_resolve_commits_the_ruling.py:361](tests/test_resolve_commits_the_ruling.py:361)**  
  The test docstring still says a ruling has its own `COMMIT_TIMEOUT_S` bound “instead of git’s 240 s.” That is no longer generally true: its budget is `min(COMMIT_TIMEOUT_S, CROSSAUDIT_GIT_TIMEOUT)`.  
  Fix: update the explanation and mutation description to state the minimum-of-two bound.

## Verified

The three requested round-14 sequences passed:

- Real escalation commit followed by a forced confirmation timeout: no traceback; state was `ESCALATED`, `escalation_commit == ""`, and the recorded sentence was: “the committed escalation row could not be confirmed: git cat-file timed out after 5s”. The ruling refusal was: “the committed rulings log could not be read …; no ruling is made until it can be”. After repair, exactly one escalation row was retained and the close ruling proceeded.
- A 70-commit ledger-only chain resolved lineage to the original work commit; `open_or_advance()` returned `blocked_by_escalation`.
- With `CROSSAUDIT_GIT_TIMEOUT=2` and a hung pre-commit hook, the loop finished in about five seconds, left the cycle `ESCALATED`, and recorded: “git commit timed out after 2s”.

I found no inspected CrossAudit-controlled route that loses an escalation, permits two committed rulings for one committed escalation, or routes a child work commit around a pending decision. The repaired README and CHANGELOG qualify the uncommitted-row exception correctly. D176 ruling 49 explicitly supersedes its earlier 90-second-only statement; D175 is unaffected.

Read in full: `src/crossaudit/rulings.py`, `tests/test_escalation_paths_round14.py`, `tests/test_ruling_signed_rows.py`, and `tests/test_slot_phrases_translated.py`. I also inspected the affected state, Git-lineage, i18n, README, CHANGELOG, D175/D176, and targeted legacy tests. No files were modified.

Tests run with the requested environment/runner prefix:

- `tests/test_escalation_paths_round14.py` — **5 passed**
- `tests/test_ruling_escalation_rows.py` — **7 passed**
- `tests/test_ruling_signed_rows.py` — **9 passed**
- `tests/test_loop_integrity.py` — **36 passed**
- `tests/test_resolve_commits_the_ruling.py` — **13 passed** (split into three runs)
- `tests/test_kernel_held_locks.py` — **15 passed**
- `tests/test_stability_slice_a.py -k 'not trickled_body and not normal_fast_response and not get_json_also'` — **7 passed, 3 deselected** (loopback binds are denied in this sandbox)
- i18n/denial coverage — **78 passed, 1 deselected** (wire-level loopback case)

VERDICT: DO NOT MERGE — the new row-budget test is source inspection, not an executable regression test for the claimed fail-closed timeout behavior