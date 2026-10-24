# Cross-vendor review — this release's changes (feat/tui-first), round 8

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 5400597 (the round-7 repairs: specific refusals for the state and ledger writes, the pre-commit writability probe, the last-resort OS-error handler), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-7 scenarios; ask whether the last-resort handler could hide a condition that should have been specific; check for overclaims. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-7 repairs verified; DO NOT MERGE on one P1 (a state write that fails after the ruling's commit leaves the ruling committed and the cycle ESCALATED, reported only as a write refusal, so a person could commit a second ruling; D176's "committed-but-unchanged sentence" claim was false) and two P2 (the credentials-file bootstrap runs before `main()`'s OS-error boundary; the ledger's `os.close` is outside its conversion). The repairs and round 9 are recorded in `…-r9.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Findings:

- **P1 — `src/crossaudit/controller/state.py:627-630`; `docs/DECISIONS.md:8636-8640`**  
  The pre-commit probe is not a transaction guarantee. If the actual state write fails after `rulings.record()` commits, the ruling is committed but state remains `ESCALATED`; `main()` reports only an ordinary writable-state denial, omitting that irreversible fact. This contradicts D176’s “committed-but-unchanged sentence” claim and permits a person to rule again, creating conflicting committed rulings.

  Reproduction: I created an escalated cycle, allowed `_require_writable()` to succeed, then made the actual state-file `fsync` fail with `ENOSPC`. In both languages: exit code `20`, no traceback, Git `HEAD` changed, and state remained `ESCALATED`. English output was:
  > DENIED (config): the controller state at …/state.json could not be written (ENOSPC: No space left on device); check the directory and file are writable

  Suggested fix: explicitly handle a post-commit state-write failure as an integrity/reconciliation state that names the committed ruling SHA and says state may be unchanged; refuse/reconcile any subsequent ruling for that cycle rather than silently allowing a second committed ruling. Add a regression that injects a write/fsync failure after the commit and asserts no duplicate resolution can be committed.

- **P2 — `src/crossaudit/cli/main.py:2491-2514`**  
  The “last resort” OSError handler does not cover bootstrap work before its `try`. An unreadable configured credentials file makes `wizard.load_keys_into_env()` raise raw `PermissionError` before line 2514, so the CLI traces back. This contradicts D176’s claim that any otherwise-untranslated OSError becomes one localized denial.

  Concrete input: set `CROSSAUDIT_KEYS_FILE` to an existing mode-`000` file, then call `main(["--lang", "zh", "status"])`; it raises `PermissionError: [Errno 13] Permission denied` instead of returning `20` with Chinese output.

  Suggested fix: place the post-parse bootstrap path inside the OSError boundary (or use an outer helper after `args` exists), and test English, Chinese, and `--json`.

- **P2 — `src/crossaudit/ledger/chain.py:188-196`**  
  `os.close(fd)` is outside the OSError-to-`ConfigDenial` conversion. A close error after a successful write propagates as raw `OSError` to direct ledger callers; through `main()` it is hidden by the generic `os_error` response rather than the specific ledger denial. D176’s assertion that every ledger-write-path OSError becomes `ConfigDenial` is therefore false.

  Concrete sequence: make `os.close` close the evidence-ledger descriptor and then raise `EIO`. `EvidenceLedger.append()` raises raw `OSError`, although one valid, verified entry is already on disk.

  Suggested fix: include close in the protected conversion and test it. Since the entry may already exist, use wording that does not claim it definitely was not recorded.

Requested round-7 reproductions succeeded. Each returned exit code `20`, had no traceback, and used the expected localized denial:

| Scenario | English | Chinese |
|---|---|---|
| `.crossaudit/` mode `0500`, existing lock | `DENIED (config): the controller state at …/state.json could not be written (EACCES: Permission denied); check the directory and file are writable` | `DENIED (config): 无法写入位于 …/state.json 的控制器状态（EACCES：Permission denied）；请确认该目录和文件可写` |
| `evidence.jsonl` mode `0400` | `DENIED (config): the evidence ledger at …/evidence.jsonl could not be written (EACCES: Permission denied); check the file and its directory are writable` | `DENIED (config): 无法写入位于 …/evidence.jsonl 的证据账本（EACCES：Permission denied）；请确认该文件及其目录可写` |
| Ledger directory replaced after `require_current()` | `DENIED (config): the evidence ledger at …/led/evidence.jsonl could not be written (ENOTDIR: Not a directory); check the file and its directory are writable` | `DENIED (config): 无法写入位于 …/led/evidence.jsonl 的证据账本（ENOTDIR：Not a directory）；请确认该文件及其目录可写` |

The torn-write test writes half an entry then raises `ENOSPC`; it confirmed the file bytes return exactly to their prior value, the next append chains normally, and verification passes.

I found no newly introduced PASS/verification bypass: the generic handler fails closed with configuration exit code. D175’s stale review claim is corrected. I found no additional relevant README or CHANGELOG overclaim; D176’s post-commit-write claim is the material overstatement.

Read in full: supplied `AGENTS.md`, the repair patch, `src/crossaudit/ledger/chain.py`, `tests/test_os_error_refusals.py`, and the round-7 review. I inspected the changed state, CLI, i18n, Chinese denial, fixture, D175/D176, README, CHANGELOG, and required regression tests. The tree remained unmodified.

Tests run:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_directory_refusals.py tests/test_kernel_held_locks.py
# 20 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_evidence_ledger.py
# 12 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_log_and_lock_round3.py
# 4 passed

env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_os_error_refusals.py
# 10 passed
```

I also ran the denial-string suite: 28 passed; its one loopback-server case failed because this sandbox denies binds (`PermissionError: Operation not permitted`). HTTP/loopback cases are therefore not counted as product failures.

VERDICT: DO NOT MERGE — committed ruling can be left without state change and reported misleadingly