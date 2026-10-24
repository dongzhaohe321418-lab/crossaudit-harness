# Cross-vendor review — claims-loop rounds 1–2 (D167–D174), round 1

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`,
sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `fix/claims-round-1` at 05e78f7, in a detached worktree the
reviewer could not change (it reports the tree stayed clean).
**Brief:** AGENTS.md §0 and §1; the diff `main..05e78f7` for `src/` and
`tests/` (80 files, +6362/−417); the decision records D167–D174; the suite
command. **Run by:** the Claude lead, 2026-10-23. **Verdict:** DO NOT MERGE
(three P1, one P3). The repairs and the second round are recorded in D176 and
in `2026-10-23-claims-rounds-1-2-terra-r2.md`.

The reviewer's text follows verbatim.

---

Findings:

- P1 — `src/crossaudit/console/server.py:2088` and `:2102`: Console escalation actions bypass `rulings.record()` entirely. A bearer-token holder can POST `/api/escalation` with `{"action":"close","reason":"..."}`; `StateStore.resolve_escalation()` persists the resolution, but no `cycles/rulings.jsonl` line or Git commit is created. This bypasses D172’s durable-human-ruling requirement and leaves an audit-critical state transition only in mutable state. Route both console branches through one shared resolve-and-commit transaction; add an HTTP-boundary test asserting the committed log and failure-atomic behavior. The existing `tests/test_escalation_ruling_through_console.py:50` makes this invisible by asserting only controller state.

- P1 — `src/crossaudit/cli/main.py:1567`: CLI resolution changes controller state before committing the ruling. A rejecting Git hook, disk error, or `git commit` failure in `src/crossaudit/rulings.py:61` leaves the cycle reopened/closed despite `resolve` returning a denial and no committed ruling. Sequence: install a failing `pre-commit` hook, run `resolve <cycle> --close --because x`; state becomes `BLOCKED`/closed before the commit fails. Make state mutation plus ruling commit failure-atomic: a failure must leave the cycle `ESCALATED` and clean up the uncommitted append/stage state. Add regression coverage.

- P1 — `src/crossaudit/app_keys.py:55`: `child_env()` leaks configured provider secrets whose names are neither `CROSSAUDIT_*_KEY` nor `*_API_KEY`. `config.py:161` accepts any non-empty `key_env`. For example, configure `key_env: PROJECT_PROVIDER_SECRET`, export that variable, then run a non-provider child path such as Git; `child_env()` preserves it, allowing hooks/credential helpers to read it. I verified this directly: `child_env({"PROJECT_PROVIDER_SECRET": "test-only-value"})` retains the name. Track every configured role/fallback key name in the scrub set (or restrict valid key-env names compatibly), and test a nonconventional configured name.

- P3 — `src/crossaudit/ledger/chain.py:276`: The docstring says correctness “never depends on the cache,” but same-size external ledger rewrites hit the cache at `:258` and append without re-verification. D168 documents this as open, so the statement is overclaiming. Either correct the prose or re-derive/cache-bind stronger file identity metadata.

Verified:

- Read in full: `app_keys.py`, `netutil.py`, `ledger/chain.py`, `broker/tools_mcp.py`, `providers/anthropic.py`, `receipt/sign.py`, `crypto/keys.py`, `rulings.py`, and `receipt/schema.py`. I also traced the relevant paths in `console/server.py`, `cli/main.py`, `controller/state.py`, `mcp.py`, `receipt/build.py`, `receipt/verify.py`, `receipt/reproduction.py`, and their added tests.
- No tree modifications; worktree remained clean.
- Passed:
  - `... pytest -q --timeout=30 tests/test_child_env_strips_provider_keys.py tests/test_provider_truncation.py tests/test_ledger_line_framing.py` — 113 passed.
  - `... tests/test_mcp_evidence_ledger.py` — 4 passed.
  - `... tests/test_verify_signature_cli.py tests/test_verify_working_tree.py` — 21 passed.
  - `... tests/test_resolve_commits_the_ruling.py -k 'not second'` — 6 passed, 1 deselected.
  - `... tests/test_denial_strings_are_legible.py -k 'not on_the_wire'` — 18 passed, 1 deselected.
- The prescribed full-suite command was attempted but the runner stopped it after 30 seconds before completion. Socket-dependent subsets cannot bind loopback in this sandbox: `test_escalation_ruling_through_console.py` had 1 passed, 3 errors; the loopback/denial subset had 66 passed, 4 failed, 2 errors, all due to `PermissionError: [Errno 1] Operation not permitted` during `127.0.0.1` bind.

VERDICT: DO NOT MERGE — console and failed-commit ruling paths bypass durable audit evidence