# Cross-vendor review — this release's changes (feat/tui-first), round 5

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 9f06ae1 (the round-4 repair: kernel-held controller and ledger locks through `locks.py`, no deletion of lock files, `index.lock` left to Git), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce each round-4 interleaving against the repair; probe the inert lock file, symlinked directories, filesystems without flock, the Windows branch. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-4 behaviours verified in their covered intervals; DO NOT MERGE on one P1 (the inode comparison is made at acquisition only, so a lock file replaced afterwards by something outside CrossAudit admits a second writer), one P2 (a filesystem without usable advisory locks, ENOLCK, surfaces as a traceback rather than a denial) and one P3 (two retained descriptions overclaim). The repair — a "still current" check before every protected write, legible lock-service denials, honest wording — and round 6 are recorded in `…-r6.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

## Findings

- **P1 — `src/crossaudit/locks.py:137-140`, `src/crossaudit/controller/state.py:156-163`**  
  The inode comparison is not atomic with returning the lock. A lock file replaced after `_same_file()` succeeds but before `acquire()` returns creates two valid kernel locks on different inodes. Both writers then proceed; the controller’s later write can discard the new owner’s state.

  Reproduction: I replaced `state.json.lock` from a hook on `_write_token`—which runs after the inode comparison—then started a second `StateStore` writer. The second writer acquired the replacement lock and wrote its cycle; the first writer then wrote its stale snapshot. Result: `child_cycle_survives: False`, `old_writer_overwrote_child: True`.

  This affects both the controller and the evidence ledger. For the latter, concurrent writers can derive the same head and fork the chain; for the controller it can lose state or undermine single-use admission.

  The new test at `tests/test_kernel_held_locks.py:137-168` only replaces the file before `flock`; it does not cover this later interval. Restore a fail-closed “still current” check before any protected mutation, add a regression test for this exact post-comparison replacement/state-loss sequence, and do not claim the primitive prevents arbitrary replacement unless the lock’s rendezvous inode is made non-replaceable for participating writers.

- **P2 — `src/crossaudit/locks.py:70-75, 135-146`; CLI catch at `src/crossaudit/cli/main.py:2523`**  
  An unsupported or exhausted kernel lock service produces an uncaught `OSError`, not a legible denial. I forced the real filesystem-shaped error `ENOLCK`; `StateStore.open_or_advance()` raised `OSError: [Errno 77] No locks available`. `main()` catches only `Denial`, so the CLI would traceback. This is relevant to NFS/network filesystems and other filesystems without usable advisory locks. Python’s Windows lock API likewise documents lock failures as `OSError`. [Python documentation](https://docs.python.org/3/library/msvcrt.html)

  Convert non-contention lock errors (`ENOLCK`, `ENOTSUP`, permission/open failures, no locking backend) into a translated `ConfigDenial` that explains the filesystem cannot provide CrossAudit’s required exclusive lock and advises using a local supported filesystem. Add Chinese parity and a regression test through `main()`.

- **P3 — `src/crossaudit/ledger/chain.py:12-14`; `tests/test_ruling_restore_and_deadline.py:15-18`**  
  Two retained descriptions are false after this repair: the ledger docstring says appends use an `O_EXCL` lock, and the test module says a live kernel-held lock “can no longer be removed or taken.” The implementation uses `flock`/`msvcrt`, and the P1 sequence shows removal/replacement remains possible after acquisition. Update both descriptions to state the narrower, true property: CrossAudit itself no longer unlinks lock paths.

## Verification

The requested round-4 behaviors work in their covered intervals:

- Releasing an old `HeldLock` after a fresh owner acquires it leaves the fresh inode in place: `fresh_lock_still_names_its_fd: True`.
- Replacement between `open()` and `flock()` is detected and retried by the supplied test.
- SIGKILL releases both controller and ledger locks; live holders wait and then refuse with the PID-bearing denial.
- `doctor` reports active holders only and does not remove locks.
- The timed-out Git case leaves a foreign `index.lock` intact; only the killed process’s `next-index-<pid>.lock` is removed.
- A symlinked `.crossaudit` path and its direct target resolved to the same lock inode for both controller and ledger in my probe; no second holder was admitted.
- I did not verify NFS or Windows behavior. The Windows branch is explicitly skipped by `tests/test_kernel_held_locks.py:39`.

Read in full: `src/crossaudit/locks.py`, `src/crossaudit/ledger/chain.py`, `tests/test_kernel_held_locks.py`, and D176’s round-4 section in `docs/DECISIONS.md`. I also reviewed the complete touched-file diff and the relevant controller, rulings, CLI/doctor, denial-parity, and regression-test sections.

Tests run:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ruling_log_and_lock_round3.py tests/test_ruling_restore_and_deadline.py tests/test_resolve_commits_the_ruling.py tests/test_evidence_ledger.py tests/test_doctor_read_only.py tests/test_doctor_parity.py tests/test_stop_rules_the_parked_escalation.py tests/test_kernel_held_locks.py
```

Result: 62 passed, 1 error—the sole error was the console HTTP test, blocked by sandbox loopback-bind policy.

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_doctor.py tests/test_denial_strings_are_legible.py
```

Result: 23 passed, 1 failed—the sole failure was likewise a loopback HTTP test blocked by the sandbox.

I reran those non-HTTP cases explicitly: 4 passed/1 deselected and 18 passed/1 deselected. `tests/test_kernel_held_locks.py` alone: 9 passed. `git diff --check a121ab7 -- src tests` passed.

VERDICT: DO NOT MERGE — P1 post-inode-check replacement still permits concurrent writers and lost controller state