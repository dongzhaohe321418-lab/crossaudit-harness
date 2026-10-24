# Cross-vendor review — this release's changes (feat/tui-first), round 6

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at fd5495e (the round-5 repairs: the still-current check before every protected write, the stated lock property, lock-service refusals), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce the round-5 sequence and the forced lock-service errors; judge whether the stated property is honest. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-5 repairs verified and the property judged honestly scoped; no P1; DO NOT MERGE on two P2 (a parent-directory `mkdir` for the state, ledger or lock file can still surface as a traceback; D176 cited this round as verifying before it existed) and one P3 (two retained descriptions still say `O_EXCL`). The repairs and round 7 are recorded in `…-r7.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P2 — `src/crossaudit/controller/state.py:159`; `src/crossaudit/locks.py:167`; `src/crossaudit/ledger/chain.py:144`**  
  Required-directory creation can still escape as a raw `OSError`/traceback. Create a regular file at the expected parent path, then acquire `state.json.lock` below it: I got `FileExistsError: [Errno 17] File exists`, not a `Denial`. `main()` only catches `Denial`, so a command reaching this path will traceback.  
  Fix: translate failures from all state/ledger/lock parent-directory creation sites into a legible `ConfigDenial`, with Chinese parity and a regression through `main()`.

- **P2 — `docs/DECISIONS.md:8601-8602`**  
  D176 claims “rounds 3 to 6 verified the repairs” and cites `…-r6.md`, but this tree contains no corresponding CrossAudit r6 review; this review also has blocking findings. This violates the repository’s “never overclaim” rule.  
  Fix: say rounds 3–5 only, and add an r6 reference only after the independent review is complete and clean.

- **P3 — `tests/test_enterprise_race.py:7,37,85`; `docs/AGENTIC_RUNTIME_PHASE0.md:43,148`**  
  These retained descriptions still say the evidence ledger/controller use an `O_EXCL` lock. The current implementation uses kernel-held `flock`/`msvcrt.locking`. The tests exercise real behavior, but their documentation is inaccurate.  
  Fix: change these descriptions to “kernel-held file lock” (and update obsolete line references in the phase document).

## Verification

I reproduced the round-5 post-acquisition replacement sequence with the hook after the inode comparison:

> `the lock file …/state.json.lock was replaced while this process held the lock; this process's change was discarded`

The first writer refused; the second writer’s cycle survived. The ledger counterpart passed too: only the initial and second entries remained, and `verify()` succeeded.

Forced lock-service failures are correctly handled:

- `ENOLCK` and `ENOTSUP` both reach `main()` as `DENIED (config)` with exit code **20**.
- English and Chinese translations are present and legible, e.g. Chinese begins: `此文件系统无法在 … 提供 CrossAudit 所需的独占锁`.
- Direct `EACCES` and `EPERM` opening the lock file also translate to the same config-denial family.

The repaired lock-replacement property is now honestly scoped: it applies to CrossAudit participants and expressly acknowledges the remaining check-to-write interval. The two round-5 descriptions specifically called out are corrected: `locks.py`/ledger describe `flock`, and `test_ruling_restore_and_deadline.py` no longer claims outside replacement is impossible. I found no new fail-open receipt, ledger, or controller path.

Read in full: supplied `AGENTS.md`; `src/crossaudit/locks.py`; `tests/test_kernel_held_locks.py`; D176; and the round-5 review. I also reviewed all changed hunks plus the relevant controller, ledger, CLI denial, Chinese-parity, fixture, and doctor code.

Tests run:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_kernel_held_locks.py
```

15 passed.

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_log_and_lock_round3.py tests/test_ruling_restore_and_deadline.py tests/test_evidence_ledger.py tests/test_doctor_read_only.py tests/test_doctor_parity.py tests/test_app_doctor.py
```

46 passed.

```sh
… pytest -q --timeout=30 tests/test_doctor.py
```

5 passed.

```sh
… pytest -q --timeout=30 tests/test_denial_strings_are_legible.py -k 'not console_serves_the_refusal_in_both_languages_on_the_wire'
```

18 passed, 1 deselected. The deselected HTTP case, when attempted, fails only because this sandbox denies loopback binds (`PermissionError`).

VERDICT: DO NOT MERGE — P2 traceback path and premature round-6 verification claim