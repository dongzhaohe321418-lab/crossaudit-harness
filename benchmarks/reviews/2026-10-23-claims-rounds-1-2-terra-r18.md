# Cross-vendor review — this release's changes (feat/tui-first), round 18

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at 392b023 (the round-17 repair: the row identity resolved once and forced onto author and committer; the docstring), in a detached worktree (the reviewer reports the tree stayed clean).
**Brief:** reproduce the round-17 scenario; judge the chosen precedence; say whether anything since round 16 is unjudged. **Run by:** the Claude lead, 2026-10-24. **Verdict:** MERGE — no P1/P2; the precedence lets the launching environment choose the `by` attribution but not forge or authorise a ruling (the signature and the committed escalation lineage still decide); one P3 (`render()` also depends on colour and TTY state, corrected in the commit that records this review).

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

No P1/P2 findings.

- **P3** — [tuiapp.py:10](src/crossaudit/cli/tuiapp.py:10), [tuiapp.py:479](src/crossaudit/cli/tuiapp.py:479), [DECISIONS.md:9007](docs/DECISIONS.md:9007): the repaired claim still omits colour context. With identical arguments and UTF-8 stdout encoding, changing `NO_COLOR` (or stdout’s `isatty()` result) changes `render()` from ANSI-coloured text to plain text. The function returns text, not bytes. I reproduced this with a UTF-8 TTY-like stream: equal output was `False`; ANSI was present only when `NO_COLOR` was absent. Amend the module docstring, `render()` docstring, and D176 ruling 56 to say rendering depends on stdout encoding and colour/TTY context, or make those inputs explicit.

The requested identity reproductions passed:

- Repository identity plus conflicting `GIT_AUTHOR_*` and `GIT_COMMITTER_*`: both escalation and close rows’ `by`, Git author, and Git committer were `Ambient Author <author@ambient.invalid>`. Ambient author wins.
- No configured identity with only `GIT_COMMITTER_*`: both rows and both Git identities were `CrossAudit <crossaudit@local.invalid>`. Committer-only ambient values do not leak.

The chosen `GIT_AUTHOR_*` precedence permits the launching environment to choose the signed `by` claim, but not to forge or authorize a ruling: `by` is included before `sign_row()` signs the row, and recovery authority still requires the project signature and committed escalation lineage. This is attribution metadata, not authenticated human identity; the documentation does not claim otherwise.

Since round 16, the pre-repair TUI/i18n/test changes were judged in round 17; `ca8a421..HEAD` contains only this repair, its tests/docs, and the preserved review record. No new denial string was added, no Chinese-parity surface changed, and the environment merge adds neither locks nor a new exception path. D175, README, and CHANGELOG do not overstate this repair; D176 ruling 56 does as noted.

Read in full: `AGENTS.md`, `src/crossaudit/rulings.py`, `tests/test_ledger_identity_and_order.py`, `README.md`, `CHANGELOG.md`, and the round-17 review. Read the relevant D175/D176 sections, changed TUI rendering paths, signing path, and child-environment handling. Worktree remained clean; `git diff --check ca8a421..HEAD` passed.

Ran successfully:

```text
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_ledger_identity_and_order.py
7 passed

… tests/test_ruling_escalation_rows.py
7 passed

… tests/test_ruling_signed_rows.py
9 passed
```

I did not run the full suite. HTTP cases were skipped because loopback binds are denied in this sandbox.

VERDICT: MERGE