# Cross-vendor review — this release's changes (feat/tui-first), round 19

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `feat/tui-first` at d731396 (the round-18 record with the docstring amendment; the Ctrl-C pty test's wrapper shell run with job control after the pull request's ubuntu CI failed under dash), in a detached worktree (the reviewer reports the tree stayed clean).
**Brief:** judge the amended docstrings and ruling 56; judge the test repair against bash 3.2 and dash on this machine, with the mutation; say whether anything since round 18 is unjudged. **Run by:** the Claude lead, 2026-10-24. **Verdict:** DO NOT MERGE — two P2s, both on the author's own wording and assertions: the render claim still omitted the language (and "no terminal"), and the Ctrl-C test accepted any non-zero exit where its D10 says 20. Both corrected in the commit that records this review (ruling 56; the test asserts 20). The shell-wrapper repair itself was found sound.

The reviewer's text follows verbatim (links rewritten to tree-relative paths).

---

P1: none.

- **P2** — `src/crossaudit/cli/tuiapp.py:10-13`, `:479`, `docs/DECISIONS.md:9007-9010`, `benchmarks/reviews/2026-10-23-claims-rounds-1-2-terra-r18.md:7`: the revised claim still omits `i18n.language()` and the module docstring still says `render()` has “no terminal.” With identical arguments, encoding, and colour state, set language to `en`, render, then set it to `zh` and render: outputs differ (`CrossAudit · bench-study` vs `CrossAudit · 项目 bench-study`). It also consults `sys.stdout.isatty()`, encoding, and `NO_COLOR` through `tui.coloured()`/`tui.glyph()`. The added review record incorrectly says the prior P3 was corrected.  
  Suggested fix: describe `render()` as pure only relative to its arguments plus current language, stdout encoding, and colour/TTY context—or make these explicit inputs. Amend the module docstring, ruling 56, and round-18 record consistently.

- **P2** — `tests/test_tui_app.py:981-984,1016-1017`: D10 and the test description say loop Ctrl-C exits 20, but the assertion accepts every non-zero exit. A regression mapping loop Ctrl-C to exit 1 would pass.  
  Suggested fix: assert `exit_code == 20`.

The shell-wrapper repair itself is sound for the checked environments:

- Normal `/bin/sh` (macOS bash 3.2): passed, 1 test in 14.09s.
- PATH shim selecting `/bin/dash`: passed, 1 test in 7.28s.
- Under a PTY, bash 3.2 reports monitor off despite `-m`; dash reports monitor on. This matches the helper docstring’s two stated shell behaviours.
- In a `/tmp` copy, removing `KeyboardInterrupt` from `prompt()` failed under dash: first prompt Ctrl-C produced `TUI-EXIT=20` and no “cancelled.”
- `-m` removes dash’s wrapper-shell SIGINT artifact; it does not hide the TUI prompt defect, as the mutation proves. It only stops testing the wrapper shell’s own SIGINT handling, which is outside the test’s stated product contract. The docstring establishes only bash 3.2 and dash, not arbitrary `sh` implementations.

Other scope checks: `392b023..HEAD` changes only the round-18 record, D176, `tuiapp.py` docstring, and `test_tui_app.py`. D175, README, CHANGELOG, audit core, denial catalogues, and Chinese-parity fixtures are untouched. Worktree remained clean.

Read in full: `src/crossaudit/cli/tuiapp.py`, `src/crossaudit/cli/tui.py`, `tests/test_tui_app.py`, and the added round-18 review; inspected changed D176 and D175 context.

Tests run:

```text
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_tui_app.py
50 passed in 81.17s
```

I did not run the complete suite or HTTP tests because loopback binds are unavailable in this sandbox.

VERDICT: DO NOT MERGE — correct the remaining render overclaims and make the D10 exit-20 assertion executable