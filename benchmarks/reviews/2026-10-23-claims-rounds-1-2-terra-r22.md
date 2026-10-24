# Cross-vendor review — this release's changes (feat/tui-first), round 22

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at dbeb258 (the round-21 repair: the ruling's post-commit confirmation under its own 5 s deadline, with the real post-commit hang test), in a detached worktree (the reviewer reports the tree stayed clean).
**Brief:** is the change at least as fail-closed and what does its refusal cost; are ruling 57 and the CHANGELOG exactly true on every Git step; anything unjudged. **Run by:** the Claude lead, 2026-10-24. **Verdict:** MERGE — no P1, P2 or P3; the repair judged more fail-closed, the real hang test and its mutation reproduced, every Git step's budget enumerated and found as the records say, parity present, nothing unjudged.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

No P1, P2, or P3 findings.

The repair is more fail-closed. [`_confirm_committed`](src/crossaudit/rulings.py:388) now gives its post-commit `git cat-file` a fresh `CLEANUP_TIMEOUT_S` deadline, rather than retaining a potentially much larger row deadline. A healthy but unusually slow blob read can therefore refuse a ruling after 5 seconds where it formerly proceeded; the commit remains append-only, controller state stays `ESCALATED`, the local intent remains, and the next ruling reconciles the committed row without another row or commit.

The real hang regression passes, including the post-commit-only hook/marker sequence and recovery assertions at [`tests/test_commit_lookup_fails_closed.py:213`](tests/test_commit_lookup_fails_closed.py:213). In a disposable `/tmp` copy, I restored the old `max(deadline, floor)` code: the test failed after 33.50s with “DID NOT RAISE IntegrityDenial,” proving it waits out the 30-second hang and the test detects the regression.

D176 ruling 57 and the CHANGELOG are accurate at the Git-step level:

- `commit_of`: each `git log` gets a fresh 5s cleanup deadline.
- `committed_rows`: `read_head`, `ls-tree`, and committed-blob `cat-file` reads each get 5s.
- `record_escalation` confirmation: `rev-parse` via `_cleanup_git` and `cat-file` each get 5s.
- `_confirm_committed`: its `cat-file` gets a fresh 5s deadline.
- Row-owned identity/add/commit operations retain the row budget; this distinction is accurately described in [`rulings.py:208`](src/crossaudit/rulings.py:208).

Chinese parity remains present for the dynamic read-back refusal and timeout fragments in [`denials_zh.py:636`](src/crossaudit/cli/denials_zh.py:636) and [`denials_zh.py:1606`](src/crossaudit/cli/denials_zh.py:1606); the runtime denial test passed. The scoped range contains exactly one commit, `dbeb258`; README and D175 content are unchanged. The D176 historical record update is truthful.

Read in full: `AGENTS.md`, `tests/test_commit_lookup_fails_closed.py`, and the round-21 review. I inspected the complete scoped diff; all deadline-wrapper call sites and the relevant ruling, escalation, recovery, Chinese-denial, fixture, CHANGELOG, and D176 sections.

Tests run:

- `env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_commit_lookup_fails_closed.py tests/test_ruling_restore_and_deadline.py tests/test_resolve_commits_the_ruling.py` — 23 passed.
- Same environment, `tests/test_stability_slice_a.py -k 'not trickled and not normal_fast and not get_json'` — 7 passed, 3 deselected.
- Same environment, `tests/test_denial_strings_are_legible.py -k 'not on_the_wire'` — 18 passed, 1 deselected.
- Targeted real-hang regression — 1 passed.
- Old-bound mutation in `/tmp` — 1 failed, as required.

The loopback HTTP case was intentionally excluded because sandbox loopback binds are denied.

VERDICT: MERGE