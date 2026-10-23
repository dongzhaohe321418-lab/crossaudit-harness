# Cross-vendor review — this release's changes (feat/tui-first), round 2

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 2a7291f (the round-1 repairs, D176, and the new D175 work: `crossaudit tui`, the usage ledger's `surface`, the front door), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** the round-1 text and D176; three diffs (`05e78f7..2a7291f` split into the repairs, the new work, and the records); reproduce each round-1 scenario, review the new work cold against AGENTS.md §1, say what ran. **Run by:** the Claude lead, 2026-10-23. **Verdict:** DO NOT MERGE (two P1, one P2, one P3): the ruling log's restore after a failed commit only truncates; the commit bound is per git step, not per transaction, and the controller lock's release is not ownership-aware; the top-level `generator.key_env` bypasses the name refusal; `surface` can be set from the caller's environment. The repairs and round 3 are recorded in `…-r3.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Do not merge. I found two audit-integrity P1s and one configuration P2.

- **P1 — failed ruling commits can corrupt an existing ruling log while claiming “nothing was recorded.”**  
  [rulings.py:125](src/crossaudit/rulings.py:125), [rulings.py:175](src/crossaudit/rulings.py:175), [rulings.py:190](src/crossaudit/rulings.py:190)  
  `_restore()` remembers only the prior byte count and truncates. A rejecting `pre-commit` hook can overwrite an already-existing `cycles/rulings.jsonl` with same-length arbitrary bytes. Truncation preserves those replacement bytes. I reproduced this in an isolated temporary repository: the operation returned `the ruling … could not be committed …; the cycle stays ESCALATED and nothing was recorded`, but `byte_identical_after_failed_commit=False` and `git status` reported `M cycles/rulings.jsonl`. Binary replacement can additionally cause `rulings.history()` to throw `UnicodeDecodeError`.  
  Fix: preserve the original bytes in an fsynced temporary backup and restore with an atomic replacement; if restoration fails, report that the ledger may have been changed rather than claiming failure atomicity. Add a real hook regression that overwrites an existing log before rejecting.

- **P1 — the ruling transaction can outlive its 120-second controller lock and permit concurrent state mutation.**  
  [rulings.py:46](src/crossaudit/rulings.py:46), [rulings.py:64](src/crossaudit/rulings.py:64), [rulings.py:183](src/crossaudit/rulings.py:183), [state.py:126](src/crossaudit/controller/state.py:126)  
  `COMMIT_TIMEOUT_S=90` applies separately to `git add` and `git commit`, not to the complete transaction. A Git clean filter delaying `git add` for 60 seconds plus a pre-commit hook delaying `git commit` for 70 seconds holds the state lock for ~130 seconds. Another process then deletes the “stale” lock and writes state; the original holder can subsequently overwrite that state from its stale snapshot and unconditionally unlink the newer lock. This can lose a concurrent escalation while a ruling commit lands.  
  Fix: enforce one deadline across every external Git step while holding the lock, safely below `LOCK_STALE_S`; also make lock release ownership-aware so an old holder cannot unlink a replacement lock. Add a scaled-time concurrent regression covering delayed add plus delayed commit.

- **P2 — D176’s `key_env` refusal does not cover the direct generator configuration.**  
  [config.py:387](src/crossaudit/config.py:387), [config.py:414](src/crossaudit/config.py:414)  
  `_role()` rejects `PATH`, malformed names, and non-strings, but top-level `generator.key_env` bypasses `_role()` and is registered immediately. I reproduced `generator.key_env: PATH`: `load()` succeeds, `PATH` is registered, and `child_env({"PATH": "/bin"})` removes it. With `generator.key_env: 7`, `load()` succeeds and `missing_credentials()` later raises an uncaught `TypeError: str expected, not int`.  
  Fix: use the same key-env validator for the direct generator row before registration, with Chinese denial coverage and tests for `PATH`, a non-string, and an ordinary unconventional generator key name.

- **P3 — `surface` is caller-forgeable, so the README overstates attribution.**  
  [main.py:2470](src/crossaudit/cli/main.py:2470), [usage.py:229](src/crossaudit/usage.py:229), [README.md:602](README.md:602)  
  `CROSSAUDIT_USAGE_SURFACE=app crossaudit build …` records `app`, despite being a CLI invocation. `test_main_honours_crossaudit_usage_surface_from_a_parent` intentionally verifies this. Since the usage ledger is non-evidence, this is not a core-security issue, but it invalidates the claim that rows identify the surface that made the call and can distort D175’s measurement. Either remove external environment inheritance where it is not genuinely needed, or describe the field as caller-declared, untrusted attribution.

Round-1 repair checks:

- Rejecting pre-commit hook: repaired for the ordinary failure case. The tested refusal is: “the ruling on cycle … could not be committed to the ledger (pre-commit: refused by policy); the cycle stays ESCALATED and nothing was recorded.” The new hook-mutation case above breaks the stronger atomicity claim.
- `/api/escalation`: source tracing confirms both normal and retry branches now call `rulings.rule()` at [server.py:2115](src/crossaudit/console/server.py:2115) and [server.py:2134](src/crossaudit/console/server.py:2134). I could not run the HTTP POST locally because this sandbox denies all loopback binds.
- Odd configured name: repaired. The real-Git-child test confirms `PROJECT_PROVIDER_SECRET` is stripped.
- Same-size ledger rewrite: repaired for changed mtime or inode; the documented same-size/same-mtime/same-inode blind spot remains and its test passes.
- Stop on parked run with rejecting hook: repaired; the run is cancelled while the cycle remains ESCALATED, with the refusal surfaced.
- Commit timeout: the single slow-hook case is repaired; the targeted timeout test passed. The separate cumulative-step timeout defect above remains.

Verified read-only. I read in full: `AGENTS.md`, D175/D176, `src/crossaudit/cli/tuiapp.py`, `src/crossaudit/rulings.py`, `tests/test_config_key_env_names.py`, and `tests/test_ledger_head_cache_identity.py`; I additionally traced the changed paths in `controller/state.py`, `config.py`, `app_keys.py`, `ledger/chain.py`, `runtime/commands.py`, `console/server.py`, `usage.py`, `cli/main.py`, `cli/build.py`, and the touched TUI/ruling/usage tests.

Tests run:

- Exact prescribed environment with `tests/test_ledger_head_cache_identity.py tests/test_config_key_env_names.py tests/test_child_env_strips_provider_keys.py`: **79 passed**.
- Targeted rejecting-hook, timeout, and parked-stop tests: **3 passed**. The two console HTTP parametrizations could not start because sandbox loopback binding raises `PermissionError: [Errno 1] Operation not permitted`.
- Targeted TUI PTY/ruling/new-task tests: **4 passed**.
- TUI renderer, Chinese, non-terminal, and verify tests: **20 passed**.
- `tests/test_usage_surface.py`: **11 passed, 3 failed**, all three due the same prohibited loopback bind.
- `tests/test_denial_strings_are_legible.py -k 'ruling or key_env or runtime'`: **1 passed, 18 deselected**.
- `git diff --check 05e78f7..HEAD`: clean. Working tree remained unmodified.

VERDICT: DO NOT MERGE — ruling transactions are not failure-atomic and can outlive their controller lock