# Cross-vendor review — this release's changes (feat/tui-first), round 17

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at ca8a421 (after round 16's MERGE: the two CI repairs — an explicit identity on ledger-row commits, same-second cycle order by recorded position — and the TUI usability fixes), in a detached worktree (the reviewer reports no files modified).
**Brief:** verify the CI repairs in a repository with no git identity and with a configured one; verify the TUI changes and that `tuiapp.py` still writes no state, mints no cycle, reads no key and runs no model call; say whether the round-16 verdict carries. **Run by:** the Claude lead, 2026-10-24. **Verdict:** the repairs verified in their tested cases and the TUI judged within its invariants; DO NOT MERGE on one P2 (`-c user.name/email` does not override `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, so a row's `by` can disagree with the commit's author) and one P3 (`render()`'s docstring claims byte-equality regardless of the stdout encoding). The repairs and round 18 are recorded in `…-r18.md` and in D176.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

Found one merge-blocking P2 and one P3 documentation overclaim.

- **P2** — [rulings.py](src/crossaudit/rulings.py:105), [rulings.py](src/crossaudit/rulings.py:522), [rulings.py](src/crossaudit/rulings.py:833), [DECISIONS.md](docs/DECISIONS.md:8960): `-c user.name/user.email` does not override Git’s `GIT_AUTHOR_*` and `GIT_COMMITTER_*` environment variables. The signed row says the configured/default identity, while the immutable Git commit can name another author and committer. D176 ruling 52’s “exactly the identity the commit carries” is therefore false.

  Reproduced with repository `user.name=Configured Name`, `user.email=configured@example.invalid`, plus `GIT_AUTHOR_NAME=Environment Author`, `GIT_AUTHOR_EMAIL=author@env.invalid`, `GIT_COMMITTER_NAME=Environment Committer`, and `GIT_COMMITTER_EMAIL=committer@env.invalid`. After an escalation and close ruling, the row was `Configured Name <configured@example.invalid>` while Git reported `Environment Author <author@env.invalid>|Environment Committer <committer@env.invalid>`.

  The new test explicitly deletes these four variables at [test_ledger_identity_and_order.py](tests/test_ledger_identity_and_order.py:59), so it cannot catch this precedence path.

  Suggested fix: run each row `git commit` with a scrubbed child environment that explicitly sets all four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` name/email variables to the resolved tuple, and add default-identity and configured-identity regression cases with conflicting ambient variables. This preserves the intended signed `by`↔commit attribution.

- **P3** — [tuiapp.py](src/crossaudit/cli/tuiapp.py:479): `render()` claims “the same arguments give the same bytes,” but `_degrade()` consults `sys.stdout.encoding` via `tui.glyph`. The same frame and dimensions render Unicode on UTF-8 stdout and ASCII fallbacks on ASCII stdout. Amend the docstring, or make encoding an explicit rendering argument.

Verified:

- With no Git identity anywhere, the new identity tests show escalation and ruling commits both land as `CrossAudit <crossaudit@local.invalid>`, and both rows’ `by` fields match.
- With repository config and no overriding author environment, configured identity wins and rows match.
- Same-second ordering is correctly by recorded history position; the later cycle is first in the TUI.
- The 24-line render tests pass with the scroll indicator; ASCII and GBK `tui --once` tests pass without traceback; the two PTY tests for PageDown and Ctrl-C pass.
- The new TUI code does not add state writes, cycle minting, provider-key access, or model calls. It does intentionally read terminal keystrokes; existing `n` still delegates work through the pre-existing engine path.
- The `-c` identity is visible to hooks: a no-identity pre-commit hook reading `git config user.name` observed `CrossAudit`. This is an intentional behavioral consequence of fixing Git identity, but it is not covered as such.
- D175, README, and CHANGELOG do not overstate this repair. D176 ruling 52 does. Rounds 1–16’s earlier findings remain unaffected, but Round 16’s MERGE conclusion cannot carry to this head.

Read in full: `src/crossaudit/cli/tui.py`, `src/crossaudit/app_keys.py`, and `tests/test_ledger_identity_and_order.py`. Read the changed and surrounding paths in `rulings.py`, `console/server.py`, `cli/tuiapp.py`, `cli/i18n.py`, D175/D176, and the affected test files. No files were modified.

Successful tests:

```text
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ledger_identity_and_order.py
4 passed

… tests/test_ruling_escalation_rows.py
7 passed

… tests/test_tui_app.py -k 'short_terminal or scrolling_moves or indicator or hidden_line or ascii_stream or gbk_stream'
7 passed, 43 deselected

… tests/test_tui_app.py -k 'under_a_24_line_pty or ctrl_c_at_a_prompt'
2 passed, 48 deselected
```

I attempted the requested complete `tests/test_tui_app.py -k 'not pty'` run twice; the execution wrapper ended it after 30 seconds without a final count, so I do not claim it passed. I did not run the full suite. Loopback HTTP cases were skipped because this sandbox denies loopback binds.

VERDICT: DO NOT MERGE — row identity mismatch under GIT_AUTHOR_*/GIT_COMMITTER_*