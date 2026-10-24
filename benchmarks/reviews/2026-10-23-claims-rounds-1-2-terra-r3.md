# Cross-vendor review — this release's changes (feat/tui-first), round 3

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at fa5127d (the round-2 repairs: exact-bytes ruling restore, one transaction deadline, owned controller lock, the direct `generator.key_env` check, `surface` declared by the entry point only), in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** reproduce each round-2 scenario against the repairs; say whether anything new is less fail-closed. **Run by:** the Claude lead, 2026-10-23. **Verdict:** the four round-2 repairs verified; DO NOT MERGE on two new P1 (a symlinked ruling log closes a cycle while the committed ledger holds no row; stale-lock breaking can delete a fresh owner's lock), one P2 (a detached hook child holding Git's pipes outlives the deadline) and one P3 (the module docstring's "a line in the file is a line in git" overclaims). The repairs and round 4 are recorded in `…-r4.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Do not merge. The four requested repairs work, but I found two P1 integrity defects.

- **P1 — a symlinked ruling log closes a cycle without committing the ruling row.** [rulings.py:219](src/crossaudit/rulings.py:219), [rulings.py:249](src/crossaudit/rulings.py:249), [rulings.py:254](src/crossaudit/rulings.py:254)  
  `open(path, "a")` follows `cycles/rulings.jsonl` symlinks, while `git add` commits the symlink itself. I reproduced this with an escalated project and `cycles/rulings.jsonl -> /tmp/outside-rulings.jsonl`: `resolve_cycle(..., "close", ...)` returned a commit and changed state to `BLOCKED`; the external target contained the ruling, but `git show HEAD:cycles/rulings.jsonl` contained only the target pathname. The committed ledger therefore has no ruling row.  
  Refuse symlinked ledger directories/files before reading or appending; use no-follow file operations where available, then assert the committed blob parses to the row. Add a real symlink regression test and Chinese denial/fixture parity.

- **P1 — stale-lock breaking can delete a fresh owner’s lock, recreating split-brain writers.** [state.py:146](src/crossaudit/controller/state.py:146), [state.py:151](src/crossaudit/controller/state.py:151)  
  A sees stale lock B, B releases, C acquires a fresh lock, then A’s unconditional `unlink()` deletes C’s lock and A acquires another. I forced that interleaving: `rival_deleted=True new_owner=True`. If C passes `_owns()` immediately before A’s unlink, both C and A can write snapshots; the ownership token cannot repair that check/write race.  
  The fail-closed fix is to stop auto-unlinking stale locks and refuse for human recovery, or replace the protocol with a kernel-managed lock/lifetime primitive. Add a barrier-based regression that forces a fresh owner between stale observation and deletion.

- **P2 — the claimed transaction deadline is bypassable by a detached hook retaining stdout/stderr.** [rulings.py:98](src/crossaudit/rulings.py:98), [rulings.py:108](src/crossaudit/rulings.py:108)  
  A pre-commit hook can start `setsid` child retaining Git’s pipes. After the process-group kill, `proc.communicate()` waits for that detached child. With `COMMIT_TIMEOUT_S=0.5` and stale threshold 1s, my ruling returned only after **4.32s**, despite refusing with `git commit timed out after 0.5s`.  
  After killing Git’s group, close the pipe readers and use a separately bounded `wait()` rather than unbounded `communicate()`. Add this detached-child case.

- **P3 — the ruling module overclaims ledger visibility.** [rulings.py:10](src/crossaudit/rulings.py:10)  
  “A line that is in the file is a line that is in git” is false between append and commit; concurrent `history()` can read the provisional line, and the symlink reproduction makes the discrepancy permanent. Say this only holds after `record()` returns successfully, or make readers expose only committed content.

Round-2 verification:

- Same-length binary overwrite and deletion by rejecting hooks both restored the exact prior bytes, clean index, unchanged HEAD, and `ESCALATED` state. The overwrite refusal was: `the ruling on cycle <id> could not be committed to the ledger (pre-commit: refused); the cycle stays ESCALATED and nothing was recorded`. The silent deletion hook reports `git commit failed and said nothing` in the same refusal form.
- Slow clean-filter + slow commit-hook shared one deadline and refused: `... (git commit timed out after 2s); the cycle stays ESCALATED and nothing was recorded`.
- The deliberate mid-ruling lock takeover left the newer lock intact and refused state write-back: `the ruling on cycle <id> was committed to the ledger (<sha>), but the controller lock was taken over before the cycle's state could change, so the cycle stays ESCALATED; rule on it again`.
- `generator.key_env: PATH` now refuses with `generator.key_env must name a variable that holds only a key; 'PATH' is not one`; `generator.key_env: 7` refuses with `...; 7 is not one`.
- `CROSSAUDIT_USAGE_SURFACE=app` with a CLI build records only `cli`. The old environment constant is absent.

I read in full: `AGENTS.md`, the round-2 review, `src/crossaudit/rulings.py`, `tests/test_ruling_restore_and_deadline.py`, `tests/test_config_key_env_names.py`, and `tests/test_usage_surface.py`. I inspected all changed regions of `state.py`, `config.py`, `usage.py`, `cli/main.py`, `denials_zh.py`, the runtime-denial fixture, and D176.

Tests run with the prescribed environment:

- `tests/test_ruling_restore_and_deadline.py`: **8 passed**
- `tests/test_resolve_commits_the_ruling.py`: **13 passed**
- `tests/test_config_key_env_names.py`: **7 passed**
- `tests/test_usage_surface.py -k 'not console and not app_mode_records'`: **10 passed, 3 deselected**
- denial-legibility target: **1 passed, 18 deselected**
- console ruling target: **1 passed; 7 fixture errors**
- parked-stop target: **4 passed; 1 fixture error**

The eight console-related errors were all sandbox-denied `127.0.0.1` binds (`PermissionError: [Errno 1] Operation not permitted`), before test assertions; I excluded them from the code assessment as requested. The tree remained unmodified.

VERDICT: DO NOT MERGE — ruling ledger symlinks bypass committed evidence, and stale-lock takeover is still split-brain-racy