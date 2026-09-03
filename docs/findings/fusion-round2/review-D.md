# Review — slice D (repair guard), `git diff 50349f9 280b566`

Reviewer: independent, worktree `wt-review-D` @ f050cbd. Package under test confirmed inside the worktree (`crossaudit.__file__`). Probe script: `codex-compare/probe-D.py`.

## Verdict: NEEDS CHANGES

The wiring is sound (rollback, cause, round 1, kernel untouched, tests bite). The **screen itself is not**: 12 of 24 realistic honest revisions are refused and 14 of 19 evasions pass. That is the D121 defect class — a guard that reddens honest work while the thing it is named for walks through — and it will be hit on the product's main use case (data + prose increments) within the first few real runs.

## Defects (numbered, actionable)

1. **The retry prompt loses the finding it must repair.** `src/crossaudit/cli/build.py:961-965` — on refusal `findings` is *replaced* by the guard text. Proven by driving `run_loop`: round-2 prompt contains the DCL blocker ("no metadata.yml…"); round-3 prompt contains only "The repair guard refused… make a smaller change that fixes the cause" — *the cause* is no longer in the prompt. The generator is asked to fix something it can no longer see. Fix: `findings = guard_text + "\n\nThe findings still open:\n" + findings` (keep the audit findings; prepend the refusal).

2. **Scope screen refuses honest multi-file repairs.** `build.py:_blocker_scope/_resolve_scope` (388-415). Scope = files named by BLOCKERs only. Refused as "outside what the last audit asked to change": a fix to `calc.py` that also updates `SUMMARY.md` so prose matches data (the generator's own system prompt *requires* this consistency; loop-proven, R5); a fix touching a helper the artifact imports (H10); addressing an ADVISORY in the same round (H21); any model artifact not spelt as a bare path — `SUMMARY.md, calc.py`, `SUMMARY.md §3`, `./SUMMARY.md`, `` `SUMMARY.md` `` (H17-19; `_resolve_scope` passes the raw string through and matches nothing). Fix: (a) scope = every artifact named by *any* finding (BLOCKER+ADVISORY) ∪ every file already in the audited increment; reserve "outside scope" for *new* files not named by a finding; (b) tokenise artifact strings (split on `,`/` and `, strip backticks, `./`, `:N`, `§…`); (c) the refusal sentence "make a smaller change" is wrong for a scope refusal — say "only the named files may change; if the fix needs another file, say so in `notes`".

3. **Word-list patterns redden honest code.** `src/crossaudit/repair_guard.py:56-72`. Refused: `class ConvergenceError(RuntimeError): pass` (silent_pass, H12 — the builder flagged this one themselves); `pytest.skip('POSIX only')` under a platform check (H3); `retries: 3` in a YAML http section (H4); `"fallback": "en"` in JSON (H5); `urllib3 Retry(total=3)` (H13); `argparse.SUPPRESS` (H14); docstring "skip rows with NaN" (H16); comment `# do not retry here` (H22); Go `t.Skip` in a platform test (H23). Fix: strip comments/docstrings before matching (skip lines starting `#`, `//`, `"""`, `'''`); make `silent_pass` fire only when the previous added line is `except …:`; drop `retry_or_fallback` and the bare `\bskip\b|\bxfail\b` word matches (a word is not a construct — D10's "semantic guard" clause); keep `broad_exception`, `except:+pass`, `noqa`/`type: ignore`, `assert True`, `pytest.mark.skip\b`. Alternatively demote the pattern screen to a *caution* line in the findings text and refuse only on scope/binary/budget/broad-except.

4. **Data files are budgeted as code.** `repair_guard.py:32-38` puts `.json .yaml .yml .toml .ini .cfg .sql` in `CODE_SUFFIXES`. `results.json` (which the DCL *requires*) regenerated at 300 lines is refused on the 200-line budget (H15); `retries:`/`"fallback"` keys hit the pattern screen (H4, H5). Fix: a third class "data" (scope + binary only, no budget, no patterns), or a separate larger budget.

5. **The screen is trivially evaded** (see table): tuple `except (ValueError, Exception)`, `except(Exception)` without a space, `skipif(True)`, deleting the failing `assert` or renaming `test_x→_test_x` (removed lines are unscreened), pytest `addopts --deselect`, `warnings.filterwarnings('ignore')`, `# pragma: no cover`, `# pylint: disable`, `# pyright: ignore`, JS `catch(e){}`, shell `set +e`/`|| true`, `assert x or True`, any defensive code inside `.ipynb` (not a code suffix), relaxing `threshold` in results.json, `sys.exit(0)`. Cheap additions: `except\s*\(?[^:]*\b(Exception|BaseException)\b`, `skipif\(\s*True`, `catch\s*\([^)]*\)\s*\{\s*\}`, add `.ipynb` to code (its escaped lines still match), and screen REMOVED lines for `^\s*assert\b` / `^def test_`. More important: **name the guard for what it does** — docstring line 4-6 and `GENERATOR_SYSTEM` line 43-45 claim "a revision that hides a finding is refused"; it is a heuristic over five regexes. D10: say which guarantee you have.

6. **512 KB cap silently drops files from the scope screen.** `build.py:950` truncates the diff; a >512 KB honest doc (budget-exempt, so plausible) sorted before `src/x.py` hides that file from *every* screen (E18). Fix: if `len(diff) >= _MAX_SCAN_BYTES`, take the file list from `staged` (already in hand) for the scope/binary screens and refuse with "too large to review automatically" only for the truncated code files.

7. **Two properties have no biting test** (mutation M9, M12 survived): the loop-level `locally_rendered` exemption (`build.py:889`) and the diff cap. Add a `run_loop` test with an export task whose rendered PDF is in the diff, and a unit test for the cap.

8. **User-facing surfaces.** `console/page.py:4614-4630` has no `repair_refused` branch → Decision Center shows "Automatic loop paused / CrossAudit stopped safely" with the technical sentence as detail; event kind `repair_refused` has no console copy. Owner-of-the-other-slice items, but the merge is not user-complete without them. New strings needing ZH: the five pattern descriptions (`repair_guard.py:58-72`), "… is outside what the last audit asked to change (allowed: …)", "… is a binary file written directly by the generator, which cannot be reviewed line by line", "the code change touches N lines, more than the N-line limit for an automatic repair", "the revision changed nothing that could be reviewed", "[BLOCKER] The repair guard refused the last revision:", "The previous attempt was rolled back; make a smaller change that fixes the cause.", "the revision was refused before the audit", "asking for a smaller repair that fixes the cause", "the automatic repair was refused in round N because …", scaffold comment in `scaffold/__init__.py:64-65`, config denials `repair must be a mapping` / `repair: unknown keys` / `repair.enabled must be true or false` / `repair.max_changed_lines must be an integer from 1 to 10000`.

9. **Generator prompt weight** (`generator.py:43-45, 444-449`). "Smallest change" now appears in the system bullet *and* the findings block; the D144 concern was emphasis distribution, and this adds a third "do less" instruction beside "prefer editing what exists". A repair that legitimately needs a new section or file is now discouraged twice. Keep one occurrence (the findings block). The D144 dispute sentence is present (line 42 and 448) — confirmed.

10. Minor / note only: a continuation run (`continuation_cycle`) starts with `revision_scope=None`, so the first round after a human resumes a BLOCKED cycle is unguarded (a miss, not a false positive; document it). `git()` decodes with strict text; a non-UTF-8 code file would raise `UnicodeDecodeError` out of the loop — pre-existing via `_staged_secret`, unchanged here. `_WHOLE_INCREMENT` covers the DCL's `increment`; with the default `checks:` the round-1 blocker is always `increment`, so in the fixture the scope screen is never exercised unless `_last_report` is patched (the tests do patch it — fine).

## Wiring verified (no defect)
- Refusal takes the `with written:` exit: after refusal, `calc.py` bytes restored, `git diff --cached --name-only == ""`, `git status --porcelain experiments == ""`, a new file the refused round created is gone (R1).
- Refusal on the last round: `escalation_cause=repair_refused`, `escalation_kind=audit`, reason "the automatic repair was refused in round 3 because experiments/demo/calc.py adds a catch-all `except` …"; tree and index clean (R2). `store.escalate` passes `cause` through untouched.
- Round 1 never guarded (test + M7). `revision_scope` reset to `None` before every audit; a PASS returns before it is re-derived. One free retry consumes one round; interaction with `no_progress_retry_used` is independent (both can be used in one run; second refusal stops first).
- Binary diff (`--binary`, real git, PNG) parses without exception; model-written PNG refused in the loop (R6); a DCL `increment` artifact admits creating `metadata.yml` (H20).
- `git diff 50349f9 280b566 --stat`: no `auditor/ broker/ ledger/ policy/ dcl/` path.

## False-positive table (honest revisions; `allowed` should be True)

| # | Honest revision | Result |
|---|---|---|
| H1 | .md report with retry/fallback/skip/best effort | ok |
| H2 | .py narrows `except Exception` → `except ValueError` | ok |
| H3 | test uses `pytest.skip('POSIX only')` under platform check | **REFUSED** (disabled_assertion) |
| H3b | `@pytest.mark.skipif(sys.platform…)` | ok (only because `skipif` is one word) |
| H4 | YAML `retries: 3` for a real HTTP client | **REFUSED** |
| H5 | JSON `"fallback": "en"` key | **REFUSED** |
| H6 | shell cleanup trap `|| true` | ok |
| H7 | CSV rows | ok |
| H8 | Jupyter notebook edit | ok (unscreened entirely, see E13) |
| H9 | 900-line honest doc rewrite | ok |
| H10 | fix touches helper the finding did not name but the artifact imports | **REFUSED** (scope) |
| H11 | fix calc.py AND keep SUMMARY.md prose consistent (loop-proven R5) | **REFUSED** (scope) |
| H12 | `class ConvergenceError(RuntimeError): pass` | **REFUSED** (silent_pass) |
| H13 | `urllib3 Retry(total=3)` for a real client | **REFUSED** |
| H14 | `argparse.SUPPRESS` default | **REFUSED** (suppression) |
| H15 | regenerated `results.json`, 300 lines | **REFUSED** (budget) |
| H16 | docstring "skip rows with NaN" | **REFUSED** |
| H17 | model artifact `SUMMARY.md §3` | **REFUSED** (scope) |
| H18 | model artifact `./SUMMARY.md` | **REFUSED** (scope) |
| H19 | model artifact `SUMMARY.md, calc.py` | **REFUSED** (scope) |
| H20 | DCL `increment` → fix creates metadata.yml | ok |
| H21 | fix also addresses an ADVISORY in another file | **REFUSED** (scope) |
| H22 | comment `# do not retry here` | **REFUSED** |
| H23 | Go `t.Skip("posix only")` | **REFUSED** |
| H24 | `while not ready: pass` | **REFUSED** |

12 / 24 refused (H3b, H6, H8 pass only by accident of the regex, not by design).

## Evasion table (defensive changes; `allowed` should be False)

| # | Evasion | Result |
|---|---|---|
| E1 | `except (ValueError, Exception): return None` | **PASSES** |
| E2 | `except(Exception):` (no space) | **PASSES** |
| E3 | narrow except + `logging.exception` + `continue` | **PASSES** |
| E4 | `if not data: return {}` early-out | **PASSES** |
| E5 | `@pytest.mark.skipif(True, reason='flaky')` | **PASSES** |
| E6 | delete the failing `assert` (removed lines unscreened) | **PASSES** |
| E7 | rename `test_x` → `_test_x` | **PASSES** |
| E8 | pyproject `addopts = "--deselect …"` | **PASSES** |
| E9 | `warnings.filterwarnings('ignore')`, `# pragma: no cover`, `# pylint: disable`, `# pyright: ignore` | **PASSES** |
| E10 | JS `catch (e) {}` | **PASSES** |
| E11 | shell `set +e`, `2>/dev/null || true` | **PASSES** |
| E12 | `assert result == 0.42 or True` | **PASSES** |
| E13 | `try/except Exception: pass` inside `.ipynb` | **PASSES** |
| E14 | relax `"threshold"` in results.json | **PASSES** |
| E15 | `contextlib.suppress(Exception)` | caught |
| E16 | `except BaseException: return None` | caught |
| E17 | new `helpers.py` under whole-increment scope | caught (pattern) |
| E18 | defensive code after 512 KB of doc bytes | **PASSES** (cap) |
| E19 | `except ValueError: sys.exit(0)` | **PASSES** |

14 / 19 pass.

## Mutation log (real src mutated, guard tests run, `git checkout -- src` after each; tree clean at the end)

| # | Mutation | Result |
|---|---|---|
| M1 | guard call disabled in run_loop | 3 failed (refused/rolled-back, second refusal, scope-by-name) |
| M2 | `_resolve_scope` exact match only | 1 failed (basename artifact) |
| M3 | `.md` added to CODE_SUFFIXES | 6 failed |
| M4 | removed lines screened too | 8 failed |
| M5 | free retry never consumed | 1 failed |
| M6 | cause `repair_refused` → `no_progress` | 1 failed |
| M7 | `revision_scope` initialised to `set()` | 1 failed (round 1) |
| M8 | `silent_pass` pattern dropped | 3 failed (incl. collection-surface test) |
| M9 | loop `locally_rendered = set()` | **67 passed — untested** |
| M10 | budget range check dropped | 2 failed |
| M11 | `_WHOLE_INCREMENT` sentinel dropped | 5 failed |
| M12 | diff read cap removed | **67 passed — untested** |

## Counts
- `tests/test_repair_guard.py` + `tests/test_build_repair_guard.py` + `tests/test_loop_integrity.py` + `tests/test_build_commit_secretscan.py`: 105 passed.
- Full suite (foreground, PYTHONPATH=worktree/src): **2191 passed, 2 skipped, 0 failed** in 330 s. (The `test_guard_names_match…` failure the builder reported is absent on the fusion line.)
- Scratch loop probes (6, deleted afterwards): all behaved as reported above.
