# Cross-vendor review — this release's changes (feat/tui-first), round 21

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at e927c9f (the round-20 repair: a step reached with no time left says so; the bound in force carried on the deadline), in a detached worktree (the reviewer reports the tree stayed clean).
**Brief:** verify the sentence on every branch of `_bounded_bytes`; whether the deadline subclass changes anything else; parity; anything unjudged. **Run by:** the Claude lead, 2026-10-24. **Verdict:** DO NOT MERGE — one P2: the records said "5 s for a lookup or confirmation" while the ruling's own confirmation ran under the greater of the row's remaining deadline and the 5 s floor, so a hung read-back could name the row budget. Corrected in the commit that records this review (the confirmation has its own 5 s deadline, like the escalation row's; a real hang after the commit is tested). Everything else verified.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Found one P2; no P1.

- **P2 — `CHANGELOG.md:70`, `docs/DECISIONS.md:9033` overstate confirmation’s bound.** They say a lookup *or confirmation* has a 5 s bound. But [`rulings.py:405`](src/crossaudit/rulings.py:405) builds a 5 s floor and [`rulings.py:411`](src/crossaudit/rulings.py:411) passes `max(deadline, floor)`. Immediately after a normal 90 s row commit, that selects the row `_Deadline`, preserving `budget=90`. A blocked `git cat-file` confirmation therefore says `git cat-file timed out after 90s`, not 5 s. I reproduced this with a forced subprocess timeout: `max(_until(90), _until(5))` was `_Deadline budget=90`, and `_bounded_bytes` produced exactly that 90 s message. This violates the repository’s no-overclaim invariant; the current test stubs a prewritten “after 5s” failure and does not exercise this deadline selection.  
  Suggested fix: either pass the dedicated 5 s deadline for confirmation and add a real timeout regression test, or correct the CHANGELOG, D176, and commit wording to say confirmation uses the greater of its remaining row deadline and the 5 s floor, naming whichever actually applies.

Verified:

- The new expired-before-start path works: `test_a_step_reached_with_no_time_left_says_so_and_never_starts_git` passed using the hanging-git shim.
- The slow-filter/slow-hook scenario passed and still reports `git commit timed out after 2s`.
- Lookup deadlines carry the 1 s cleanup bound; plain floats retain the documented `ceil(remaining)` fallback.
- `_Deadline` is otherwise numerically compatible: arithmetic yields plain `float`, comparisons work, JSON encodes it as a number, and `max()` preserves the selected decorated deadline. The test monkeypatch wrappers I inspected forward `deadline` unchanged.
- Chinese parity is present: the fixture contains the new full refusal and `i18n.denial_zh()` rendered it fully in Chinese.
- The only commit since round 20 is `e927c9f`; I reviewed all files in its diff. No separate unjudged code change exists.

Read in full: `src/crossaudit/rulings.py`, `tests/test_commit_lookup_fails_closed.py`. I also read the changed sections of the decision record, changelog, denial catalogue, runtime fixture, and related deadline/escalation tests.

Tests run:

- `env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_commit_lookup_fails_closed.py tests/test_ruling_restore_and_deadline.py` — **9 passed**.
- Same environment/runner, `tests/test_stability_slice_a.py -k 'not trickled and not normal_fast and not get_json'` — **7 passed, 3 deselected**.
- Same environment/runner, `tests/test_escalation_paths_round14.py tests/test_denial_strings_are_legible.py -k 'not on_the_wire'` — **24 passed, 1 deselected**.

The three loopback HTTP tests were excluded as requested; an initial bundled invocation selected them due to pytest’s single global `-k` handling, and they failed only with sandbox `PermissionError` on `127.0.0.1` bind.

VERDICT: DO NOT MERGE — confirmation-bound documentation overclaims actual behavior