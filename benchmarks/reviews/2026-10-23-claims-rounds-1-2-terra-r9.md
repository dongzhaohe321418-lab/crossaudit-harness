# Cross-vendor review — this release's changes (feat/tui-first), round 9

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at d973abd (the round-8 repairs: reconciliation of a committed ruling from the ledger, the bootstrap inside the OS-error boundary, the ledger's close inside its conversion), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-8 sequence; ask whether a forged or back-dated committed row could make the state apply a ruling nobody made, and whether the matching can misfire across re-escalations. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-8 repairs verified in the serial case; DO NOT MERGE on one P1 in three parts (the committed-log lookup ran before the controller lock, so two resolvers could commit opposite rulings; an unreadable log read as "no pending ruling"; any valid committed row was applied as authority, forgeable by a repository writer) and two P2 (the legacy same-second gap; D176, README and CHANGELOG overstating "failure-atomic" and "never ruled twice"). The repair — a local intent written under the lock before the commit, the row carrying its nonce, reconciliation only of a committed row that matches a local intent, everything under the lock, an unreadable log a refusal, foreign rows surfaced and never applied — and round 10 are recorded in `…-r10.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Findings:

- **P1 — reconciliation is neither atomic nor fail-closed.**  
  [rulings.py](src/crossaudit/rulings.py:466), [rulings.py](src/crossaudit/rulings.py:538)

  `pending_ruling()` reads the committed log before the controller lock is acquired. A second resolver can commit a ruling, fail its state write, then a resolver holding a stale “no pending ruling” result enters `rule_escalation()` and commits an opposite ruling.

  I reproduced this with a barrier after resolver A read no pending row; resolver B committed `close` and failed the post-commit state write; A then committed `reopen`. Result: **2 commits**, rows `[close, reopen]`, final state `OPEN`.

  Separately, `committed_rows()` converts any `cat-file` failure/non-zero result to `[]`. After the post-commit state failure, I made only that first `cat-file` fail; the next `reopen` committed successfully: **2 commits**, conflicting `close`/`reopen` rows.

  A syntactically valid committed row is also treated as authority without proving it came from `record()`. I committed a manually authored row with the cycle’s current `escalated_at`, `action: close`, and a 1970 timestamp; the next `rulings.rule()` reconciled it to `BLOCKED`. Any party able to write and get a commit into the audit repository—local filesystem writer, hook, or remote collaborator with merge/write authority—can do this. That is not a remote-model-only path, but it defeats the stated “human act” boundary for a repo writer who lacks access to the ignored local state.

  Suggested fix: perform strict committed-log lookup and reconciliation under the same controller lock as commit/state application; inability to read or parse `HEAD:cycles/rulings.jsonl` must deny rather than mean “no pending ruling.” Do not auto-apply an unauthenticated JSON row: establish and verify an authorized human provenance mechanism before reconciliation, or refuse ambiguous external rows. Add barrier-based race, one-shot `cat-file` failure, and forged-committed-row regressions.

- **P2 — legacy cycles retain a documented duplicate-ruling gap.**  
  [rulings.py](src/crossaudit/rulings.py:449), [DECISIONS.md](docs/DECISIONS.md:8670)

  For a pre-R9 cycle with no `escalated_at`, a newly committed ruling also has no escalation identifier. If the post-commit state write fails and the retry occurs in the same integer second, `row.t == cycle.updated_at`; the strict `>` comparison returns false and permits another ruling. The decision record acknowledges this as “a second ruling is then allowed,” but it is still a conflicting-ledger path for backward-compatible state.

  Suggested fix: for equality/otherwise ambiguous legacy timestamps, refuse and require repair rather than record another ruling. Add a contiguous same-second legacy-state regression.

- **P2 — D176, README, and CHANGELOG overstate the repaired behavior.**  
  [DECISIONS.md](docs/DECISIONS.md:8376), [DECISIONS.md](docs/DECISIONS.md:8654), [README.md](README.md:1004), [CHANGELOG.md](CHANGELOG.md:41)

  D176 says rulings are “failure-atomic” and “never ruled twice”; the race and unavailable-read paths above violate both. README says a second ruling “on the same cycle adds a line,” which is false for successful reconciliation and incomplete for the duplicate cases. CHANGELOG’s “one transaction” also conceals the committed-ledger/state-pending split. D175 itself appears accurate on this point.

  Suggested fix: qualify these claims after repairing the core behavior; distinguish a later re-escalation from retrying the same pending escalation.

Verified repairs:

- Serial post-commit failure: exit `21`, one new commit, state remained `ESCALATED`, `status --json` reported `ruling_pending: true`. The denial was:

  > the ruling on cycle … was committed to the ledger as …, but the cycle's state could not be written (ENOSPC: No space left on device); the state is unchanged, and ruling on this cycle again applies the committed ruling instead of writing a new one

- Same action reconciled with no new commit:

  > the ruling of … (close, …) was already in the ledger; the cycle's state now reflects it; no new ruling was written

  The direct opposite-action test produced the intended “a committed ruling … already stands” refusal; after the same-action reconciliation, a later opposite action correctly says the cycle is no longer `ESCALATED`.

- Mode-000 credentials file through `main()` returned exit `20` without traceback in English, Chinese, and JSON. The JSON result had `kind: "os_error"`.
- A post-write `os.close(...)=EIO` returned the new specific `ConfigDenial`; the entry remained verifiable.
- New denial strings have Chinese counterparts; the non-HTTP denial suite passed.

Read in full: supplied `AGENTS.md`; `benchmarks/reviews/2026-10-23-claims-rounds-1-2-terra-r8.md`; `src/crossaudit/rulings.py`; `tests/test_ruling_reconciled_from_ledger.py`. I inspected all changed hunks plus the relevant state, ledger, CLI, i18n, Chinese-denial, status, TUI, console, README, CHANGELOG, D175/D176, and fixture paths. The tree remains unmodified.

Completed tests:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_reconciled_from_ledger.py -k 'not console'
# 9 passed, 1 deselected

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_log_and_lock_round3.py tests/test_ruling_restore_and_deadline.py
# 9 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_evidence_ledger.py
# 12 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_kernel_held_locks.py
# 15 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_os_error_refusals.py tests/test_directory_refusals.py tests/test_ledger_line_framing.py tests/test_reproduction_tree_locks.py
# 44 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_denial_strings_are_legible.py -k 'not console_serves'
# 18 passed, 1 deselected
```

The omitted loopback cases cannot bind `127.0.0.1` in this sandbox (`PermissionError: [Errno 1] Operation not permitted`); I did not count that as a product failure. I did not run the full suite.

VERDICT: DO NOT MERGE — reconciliation can still create conflicting committed rulings and can apply an unauthenticated committed row