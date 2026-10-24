# Cross-vendor review — this release's changes (feat/tui-first), round 20

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 17ff4c7 (the round-19 repairs; ruling 57: a `git log` that cannot answer during a ruling is a refusal, after the pull request's CI wrote an escalation row twice), in a detached worktree (the reviewer reports the tree stayed clean).
**Brief:** judge ruling 57 as the audit core's reviewer (fail-closed, no new refusal in a healthy repository, the shim test and its mutations, the sentence's bound); say whether the causal account fits the CI evidence; judge the round-19 repairs; parity. **Run by:** the Claude lead, 2026-10-24. **Verdict:** DO NOT MERGE — one P2: a step reached with its deadline already passed still said "timed out after 90s"; corrected in the commit that records this review (the step is refused without starting git and says its budget was already spent, naming no number). The repair itself was found sound and more fail-closed, the causal account fitting, the round-19 repairs correct.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

P1: none.

- **P2 — `src/crossaudit/rulings.py:187-189`**: the repaired timeout wording is still false when a step receives an already-expired deadline. That branch reports `row_budget()` (normally 90s), though the step was given no time and never started. This contradicts D176 ruling 57 at `docs/DECISIONS.md:9033-9035` and the new CHANGELOG claim at `CHANGELOG.md:69-70`.

  Concrete reproduction: calling `_bounded_bytes(..., deadline=time.monotonic() - .01)` produced `git log timed out after 90s`. The actual bound was zero/expired, not 90 seconds.

  Suggested fix: calculate the displayed bound before the early return and report `0s` (or a distinct “deadline already exhausted” denial); add a regression test for an expired deadline. Keep the D176/CHANGELOG claim aligned with that behavior.

The core repair itself is otherwise sound and more fail-closed:

- `commit_of(strict=True)` refuses a timed-out, failed-to-start, or non-zero `git log`; strict callers cover escalation recovery, identity, assessment, and committed-ruling lookup. Display paths remain lenient.
- A successful `git log` with no matching line still returns `""`, not a refusal. I directly invoked strict lookup in a healthy repository with an absent legacy-shaped row and got `''`.
- In `/tmp` copies, I ran the first two claimed mutations:
  - Making `_escalation_already_committed()` use lenient lookup made the regression test fail after `HEAD` advanced, demonstrating the duplicate write.
  - Making `assess()` use lenient lookup made the test fail because it emitted the incorrect “ledger holds no verified escalation row” denial instead of the unreadable-log refusal.
- The CI causal account fits. The old `_cleanup_git()` collapsed the failed lookup to `""`; recovery then treated the committed-but-unconfirmed escalation as absent and wrote another row. With the fixture’s initial escalation and the later unconfirmed escalation, that produces the observed third escalation row. I found no alternate mechanism for that sequence in the old code, nor one in the new strict path.
- The positive timeout behavior is correct: the hanging shim under a 1-second lookup reports `after 1s`; the missing case is only the expired-before-start branch.

Round-19 repair (a) is correct:

- `render()` and the module docstring now name language, stdout encoding, and `tui.coloured()` state without claiming it has no terminal dependency.
- `main()` catches `KeyboardInterrupt` and returns `EXIT_CONFIG`, which is 20; the PTY regression test now asserts exactly 20.

Chinese parity is present: the new refusal reuses the existing composite template in `src/crossaudit/cli/denials_zh.py:614`; the runtime fixture includes it. No further source/test changes beyond the two stated commits were unjudged. I found no additional overclaim in the relevant D175/README text. D176 and CHANGELOG need the P2 wording correction above.

Read in full: `AGENTS.md`, `tests/test_commit_lookup_fails_closed.py`, and the round-18/round-19 review records. I inspected the relevant changed paths in `rulings.py`, `tuiapp.py`, `main.py`, `tui.py`, `denials_zh.py`, D176, CHANGELOG, and the specified existing tests. The repository tree was not modified.

Tests run successfully:

```text
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_commit_lookup_fails_closed.py
3 passed in 14.84s

… tests/test_escalation_paths_round14.py
6 passed in 15.73s

… tests/test_ruling_escalation_rows.py
7 passed in 18.13s

… tests/test_stability_slice_a.py -k 'not trickled and not normal_fast and not get_json'
7 passed, 3 deselected in 5.52s

… tests/test_denial_strings_are_legible.py -k 'not on_the_wire'
18 passed, 1 deselected in 3.79s

… tests/test_tui_app.py -k 'ctrl_c_at_a_prompt'
1 passed, 49 deselected in 6.88s
```

I did not run the full suite or loopback HTTP cases because loopback binds are denied in this sandbox.

VERDICT: DO NOT MERGE — P2: expired git-step deadlines still falsely report the row budget rather than the bound actually given.