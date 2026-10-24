# Cross-vendor review — this release's changes (feat/tui-first), round 4

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at a121ab7 (the round-3 repairs: symlink refusal and committed-blob check, no automatic breaking of the controller or ledger lock, bounded post-kill wait; `locks.py`), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce each round-3 scenario against the repairs; say whether anything new is less fail-closed. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the round-3 repairs verified; DO NOT MERGE on one P1 (lock release and `doctor --fix` still check a token then unlink by pathname, so a fresh owner's lock can be deleted in the window between) and one P2 (the post-kill cleanup can unlink another Git writer's `index.lock`). The repair — kernel-held locks that need no stale-file deletion — and round 5 are recorded in `…-r5.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

I found two defects.

- **P1 — lock “ownership” is still check-then-unlink, so `doctor --fix` or a releasing owner can delete a fresh owner’s lock.** [locks.py:89](src/crossaudit/locks.py:89), [locks.py:91](src/crossaudit/locks.py:91), [state.py:199](src/crossaudit/controller/state.py:199), [chain.py:405](src/crossaudit/ledger/chain.py:405).  
  `locks.remove_stale()` verifies the dead stale token, then unlinks by pathname. Between those operations, B can release and C can create a fresh O_EXCL lock; A then unlinks C’s lock. The same TOCTOU exists in controller and ledger release: `owns()` succeeds, C replaces the lock, then the old holder unlinks C’s lock. I forced each interleaving; all three printed `fresh-owner-lock-exists: False`. This recreates split-brain controller/ledger writers. The existing barrier tests cover automatic stale-lock acquisition, not `doctor --fix` nor release; the doctor tests are sequential liveness checks and pass despite this defect.  
  Suggested fix: do not use pathname-token comparison plus unlink as an ownership primitive. Move these locks to an OS-held lock whose release is closing the owner fd (e.g. `fcntl.flock` on the macOS-supported target), eliminating stale-file deletion/recovery entirely. Until then, `doctor --fix` must not claim safe automatic removal.

- **P2 — timeout cleanup can unlink an unrelated Git writer’s `index.lock`.** [rulings.py:165](src/crossaudit/rulings.py:165), [rulings.py:182](src/crossaudit/rulings.py:182).  
  After a timed-out CrossAudit Git process is killed, another user Git process can acquire `.git/index.lock` before `_drop_index_locks()` finishes its `git rev-parse`. CrossAudit then unconditionally removes that new lock. A third writer can subsequently acquire another `index.lock` while the second writer is still active, defeating Git’s serialization and risking index corruption. D176 describes this as a “narrow race,” but it remains a real unsafe cleanup path.  
  Suggested fix: leave generic `index.lock` for manual recovery and return a legible denial; only remove a lock with a demonstrable owner identity, if any.

Round-3 repair verification:

- Symlinked `cycles/rulings.jsonl` and symlinked `cycles/` both refused before state change: “`cycles/rulings.jsonl (or its directory) is a symbolic link; the rulings log must be a regular file inside the repository, so the ruling was not recorded`”.
- A clean filter stripping the row left the cycle `ESCALATED`, restored the working log to the committed blob, and refused: “`the ruling on cycle <id> was committed as <sha>, but the committed cycles/rulings.jsonl could not be confirmed to contain it (a filter or hook changed the file); the cycle stays ESCALATED — check the repository's filters and hooks before ruling again`”.
- The requested stale-observation barrier for automatic acquisition refused and preserved C’s fresh lock. A dead controller lock refused with: “`the controller lock <path> has been held by pid <pid> for 151s, longer than the 120s stale limit, and is not broken automatically; if no crossaudit process is running for this project, \`crossaudit doctor --fix\` removes it`”; `doctor --fix` then removed it. However, the P1 finding shows that removal is not race-safe.
- The detached-`setsid` hook case returned within its asserted bounded interval and refused with “`… (git commit timed out after 0.5s); the cycle stays ESCALATED and nothing was recorded`”.
- A stale ledger lock likewise refused: “`the evidence ledger lock <path> has been held by pid <pid> for 61s, longer than the 30s stale limit, and is not broken automatically; if no crossaudit process is running for this project, \`crossaudit doctor --fix\` removes it`”. Its automatic-acquisition barrier preserves C’s lock, but its release and doctor-recovery paths have the P1 race.

The documented loss of silent stale-lock recovery is deliberate and tested: a dead lock now needs `doctor --fix`; I found no missing Chinese counterpart. The new symlink, filter, controller-lock, and ledger-lock denials have entries in `denials_zh.py` and the runtime fixture; Chinese denial tests passed.

I read in full: `AGENTS.md`; the round-3 review; D176; `src/crossaudit/locks.py`, `rulings.py`, and `ledger/chain.py`; and `tests/test_ruling_log_and_lock_round3.py`, `test_ruling_restore_and_deadline.py`, and `test_resolve_commits_the_ruling.py`. I inspected all changed regions of `controller/state.py`, `cli/main.py`, `cli/i18n.py`, `cli/denials_zh.py`, and the runtime-denial fixture. The tree remained unmodified.

Tests run with the prescribed environment:

- `tests/test_ruling_restore_and_deadline.py`: **8 passed**
- `tests/test_ruling_log_and_lock_round3.py tests/test_resolve_commits_the_ruling.py`: **24 passed**
- Requested doctor, ledger, head-cache, and stop files: **40 passed, 1 error**. The error was the requested HTTP console case failing before assertions because this sandbox denies the `127.0.0.1` bind (`PermissionError: [Errno 1] Operation not permitted`).
- Non-HTTP stop and Chinese-denial parity targets: **20 passed, 4 deselected**

VERDICT: DO NOT MERGE — doctor/release lock handling can still delete a fresh controller or evidence-ledger owner’s lock