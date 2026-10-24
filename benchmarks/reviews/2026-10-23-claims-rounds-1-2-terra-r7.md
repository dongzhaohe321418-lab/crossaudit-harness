# Cross-vendor review — this release's changes (feat/tui-first), round 7

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 0d88003 (the round-6 repairs: `locks.ensure_directory` refusals, the two `O_EXCL` descriptions, D176 citing only existing rounds), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-6 scenario; judge whether any claim in D175/D176, the README or the CHANGELOG overstates the code. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-6 repairs verified; "no P1 fail-open path found"; DO NOT MERGE on two P2 (an existing but unwritable `.crossaudit/` or ledger file still surfaces as a raw `PermissionError`/`NotADirectoryError` through `main()`) and one P3 (D175's open item still said the TUI had not been reviewed). The repairs and round 8 are recorded in `…-r8.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Findings:

- P2 — [state.py:118](src/crossaudit/controller/state.py:118): `ensure_directory()` only catches failure to `mkdir`; an existing but unwritable `.crossaudit/` passes it. With a pre-existing writable `state.json.lock`, make `.crossaudit/` mode `0500`, then call `StateStore(...).open_or_advance()`: `_write()` raises raw `PermissionError` opening `state.json.tmp<PID>` at line 121. `main()` catches only `Denial`, so CLI callers traceback. Catch write/rename/fsync `OSError` and convert it to a translated `ConfigDenial`; add English/Chinese `main()` regressions for an existing unwritable state directory.

- P2 — [chain.py:152](src/crossaudit/ledger/chain.py:152): the same gap remains for the ledger file itself. I created an empty valid `evidence.jsonl`, chmodded it `0400`, and called `EvidenceLedger.append(...)`; it raised raw `PermissionError` from `os.open(...)`. The existing directory check and lock can both succeed first. A directory replacement immediately after `require_current()` likewise raises raw `NotADirectoryError`. Wrap the ledger open/write/fsync path in a translated denial (and re-check integrity where appropriate), with tests through `main()` in both languages.

- P3 — [DECISIONS.md:8372](docs/DECISIONS.md:8372): D175 still says the TUI “has not yet had a cross-vendor review,” contradicting D176’s recorded round-2 review at line 8624; `r2.md` exists. Update D175’s stale open item.

Verified:

- The requested regular-file reproduction now works through `main()` in English and Chinese: `tests/test_directory_refusals.py` replaces `.crossaudit/` with a file, gets `EXIT_CONFIG`, the expected translated denial, and no traceback.
- Chinese templates and runtime fixture entries exist for controller state, evidence ledger, and lock-file directory failures.
- Both retained descriptions now correctly say “kernel-held file lock”; no remaining `O_EXCL` in the two requested descriptions.
- D176 now cites only review texts that exist: `r1.md` through `r6.md` are present.
- No P1 fail-open path found: the new static regular-file case fails closed. The P2s are legible-denial/traceback defects, not an acceptance or ledger-verification bypass.
- Full reads: `AGENTS.md`, the supplied repair patch, `src/crossaudit/locks.py`, and `tests/test_directory_refusals.py`. I also inspected the changed functions/hunks in state, ledger, i18n, decisions, README, changelog, and enterprise-race test.
- Tests run:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_directory_refusals.py tests/test_kernel_held_locks.py
# 20 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_log_and_lock_round3.py tests/test_evidence_ledger.py tests/test_doctor*.py tests/test_enterprise_race.py
# 43 passed
```

I did not run loopback HTTP cases because sandbox loopback binds are denied.

VERDICT: DO NOT MERGE — raw PermissionError/NotADirectoryError still escapes instead of a legible denial