# Review D2 — repair guard rework, `git diff 280b566 3851f0b -- src/ tests/` (fusion/repair-guard)

Reviewer: independent, worktree `wt-review-D2` @ 3851f0b (`crossaudit.__file__` confirmed inside it). Probes: `codex-compare/probe-D2.py` (unit), `probe-D2-git.py` (real git), `probe-D2-loop.py` (run_loop, was `tests/test_zz_review_d2.py` during the review), `mutate-D2-review.py` (builder's script re-pointed), `mutate-D2-mine.py`.

## Verdict: NEEDS CHANGES

The contract is right and the wiring is proven end to end (caution → prompt → checks.json, verdict untouched; refusals roll back files + index, keep the findings, one free retry, `repair_refused`). The first review's 24 honest cases are now 24/24 clean with **zero** cautions. What remains are three hard-refusal bugs in the two screens that are supposed to be the only hard ones, and caution sentences that tell the auditor things that are not true.

## Defects (numbered, actionable)

1. **A non-ASCII filename inside scope is hard-refused, twice, then the run stops with `repair_refused`.** Loop-proven (T2): generator writes `experiments/demo/报告.md` under `scope.dirs: [experiments]` → `repair_refused` with detail `"experiments/demo/\346\212\245\345\221\212.md" is outside the audited directories (experiments)…`. Cause: `_stage_generated` returns `git diff --cached --name-only` output, which git quotes for non-ASCII (`"…\346…"`); `in_scope` sees a path beginning with `"`. Same root in the parser: `_unquote` decodes latin-1 → `unicode_escape`, so the refusal sentence names the file as `å\x9b¾.png` (garbled). This product ships ZH; a Chinese report name is the normal case. Fix: read staged names with `git -c core.quotepath=off diff --cached --name-only -z` (split on NUL) at `build.py:_stage_generated` and the guard call; `_unquote` → `token[1:-1].encode("latin-1").decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")`; loop test with a CJK filename.
2. **`scope.dirs: ["./experiments"]` refuses every repair** (T3: two refusals → `cause=repair_refused`, reason `experiments/demo/calc.py is outside the audited directories (./experiments)`). The generator accepts that spelling (`file_identity._request_parts("./experiments") == ("experiments",)`), so the guard disagrees with the boundary it is supposed to mirror; `experiments/./demo` and `experiments//demo` likewise. Fix: `posixpath.normpath` on each scope dir (and on the path) in `in_scope`; unit test for `./x`, `x/./y`, `x//y`.
3. **A model-written binary with a space in its name bypasses the binary screen and is committed** (T8: `experiments/demo/fig 1.png` in `git log --name-only`, no `repair_refused`). `diff --git a/fig 1.png b/fig 1.png` fails the header regex (`a/\S+`), binaries have no `+++` line to recover from, so the file is never parsed; it only enters `known` via the staged list, which the binary screen does not consult. The "hard" guarantee is one space away from off. Fix: derive files and binaries from `git diff --cached --numstat -z` (`-\t-` = binary) rather than the patch header, or split the header remainder at ` b/` and accept when both halves are equal; test with `fig 1.png`.
4. **Caution sentences that are false for ordinary honest edits** — the auditor is told an untruth, which is the opposite of "the dual-source audit must raise accuracy":
   - `except Exception as exc: raise X(...) from exc` / `except Exception: log.exception(); raise` (N1, N2) → "adds a catch-all `except` that **swallows every error**". It re-raises. Fix: no `broad_exception` when the handler body (following added lines until dedent) contains a bare `raise` or `raise … from`; or at least reword to "adds a catch-all `except`".
   - `assert r == 0.42` → `assert r == pytest.approx(0.42, rel=1e-6)` (N4), `raise RuntimeError('…')` → `raise ConvergenceError(f'…')` (N5) → "**removes** an `assert` or `raise` **without replacing it**". It was replaced. Fix: when an added line in the same file starts with the same keyword, say "changes an `assert`/`raise`" (still useful to the auditor) instead of "removes".
   - `def test_convergence` → `def test_convergence_strict` (N8) → "removes a test". Fix: if an added line matches `def test_`, say "renames a test" or stay silent.
5. **Doctest lines inside docstrings redden** (N7: `    ... except Exception:` → `broad_exception`). `strip_code` only knows a docstring by its first line; interior lines are code to it. Cheap fix: treat lines starting with `>>>` / `...` as comments; the multi-line docstring body remains a documented blind spot (noise, not a refusal).
6. **Pattern alternatives without a biting test** (mutation survivors R1, R5–R10 below): two-line JS `catch (e) {` + `}`; `pragma: no cover`; Java/TS `catch (Exception`; `unittest.skip`; `mark.xfail`; `@ts-ignore`/`eslint-disable`; non-ASCII `_unquote`. Any of these can be deleted and the 111 tests stay green. Add a table-driven red/green per alternative.
7. **Cheap evasions still silent** (all outside the documented non-claims): `python calc.py || exit 0` (X11 — `|| true` is caught, `|| exit 0` is not); `pytest.importorskip('…')` (X3); wrapping the re-added failing line under `if TYPE_CHECKING:` / `if False:` (X1 — the squash-equality that protects a moved assert also hides this); Makefile recipe `-cmd` prefix (X15); `.pyx`/`.pxd` not in `CODE_SUFFIXES` (X10). Either add the patterns or add them to the docstring's list of what the screen cannot see.
8. **Console/i18n copy is stale for the new contract** (fusion/console `page.py:4665-4680`): the `repair_refused` Decision Center summary still says "it tried to make the finding disappear, changed files the audit did not name, or grew larger than an automatic repair may be" — under default mode none of those refuse; only a file outside `scope.dirs` or an unrendered binary does. Event kind `repair_caution` has no console copy; `cli/i18n.py` has no ZH for any repair string (list below). Other-slice, but the merge is not user-complete without it.
9. **The scope refusal is unreachable through the generator; the reachable path drops the findings** (T4). A real out-of-scope write is denied earlier by `gen_mod.apply` → `generation_refused`, and that retry prompt is `[BLOCKER] Your last round was refused before it reached the auditor: 'notes/stray.md' resolves outside the authorized working directories… Return only files inside experiments/ and try again.` — the audit findings are **replaced**, the exact defect review-D #1 fixed in the guard path. Pre-existing path, but the docs ("Only two things are refused… a file outside the audited directories") describe the guard as the boundary the user meets, and the user meets this one. Keep the findings there too, and say in the docs that `apply` is the first line.
10. Minor: the refusal-retry prompt carries the round's "Model audit unavailable (provider failure…)" paragraph verbatim from `render_findings` (T6/T9 output) — pre-existing rendering, noted only.

## Verified (no defect)

- **Cautions reach the auditor** (T1, real `cmd_run`, replay auditor answering PASS): round 2 commits `except Exception: pass` with a full increment; `checks.json` notes = `revision caution: experiments/demo/calc.py adds a catch-all …`, `… adds an error handler that does nothing`; `total_hard_failures == 0`, no CA-META-004 (`framework.py:204` keys on `truncated:`/`unread ` prefixes only); the caution text is in the auditor prompt whose sha256 is the receipt's `inputs.prompt_sha256`; verdict PASS, cycle PASSED, exit 0. Round 3 in the builder's test carries no stale note (reset at `build.py:825`; mutation R4 caught).
- `cmd_run` `extra_notes` line: additive (`[*notes, *getattr(args, "extra_notes", ())]`), set only at `build.py:992`; the `run` argparse has no such flag, so a user cannot inject notes through `crossaudit run`; a plain Namespace without the attribute is unchanged.
- Refusal path: binary → files and index restored before the next generator call (`calls[2].calc == CALC_OK`, staged `""`), findings kept in order (DCL cause before the refusal block), one free retry, second refusal → `escalation_cause=repair_refused`, kind `audit` (T9); last-round refusal with `max_rounds=2` → `repair_refused`, tree and index clean (T5); `mode: refuse` turns `# noqa` into a refusal while the honest `except ValueError: raise` retry commits (T6); honest multi-file repair (metadata + results.json + SUMMARY + calc narrowing) under default → no caution, no refusal (T7).
- Round 1 never screened; `repair.enabled: false` disables; config denials read as documented.
- `git diff 280b566 3851f0b --stat`: no `auditor/ broker/ ledger/ policy/ dcl/` path.

## Honest-case table (default mode; REFUSED would be a defect)

| # | Case | Result |
|---|---|---|
| H1–H24 | the first review's 24 (reconstructed byte-for-byte from review-D / probe-D) | **all 24: allowed, zero cautions** |
| N1 | `except Exception as exc: raise X() from exc` | caution `broad_exception` — **noise, and the sentence is false** ("swallows every error") |
| N2 | `except Exception: log.exception(); raise` | caution `broad_exception` — noise, false sentence |
| N3 | `warnings.simplefilter('ignore', RuntimeWarning)` inside `catch_warnings()` | caution `warning_suppression` — acceptable for the auditor to weigh |
| N4 | `assert r == 0.42` → `assert r == pytest.approx(0.42, rel=1e-6)` | caution `removed_check` — reasonable to surface, **sentence false** ("without replacing it") |
| N5 | `raise RuntimeError('x')` → `raise ConvergenceError(f'…')` | caution `removed_check` — noise, sentence false |
| N6 | optional import `except ImportError: scipy = None` | clean |
| N7 | doctest `... except Exception:` in a docstring | caution `broad_exception` — noise |
| N8 | `test_x` → `test_x_strict` | caution `removed_test` — noise, sentence false |
| N9 | SQL `a || ' ' || true_flag` | clean |
| N10 | 300-line honest algorithm rewrite | caution (budget) — reasonable |
| N11 | `scope.dirs: ["./experiments"]` | **REFUSED** (defect 2; loop T3 → `repair_refused`) |
| N12 | `scope.dirs: ["experiments/demo/"]` | clean |
| T2 | `experiments/demo/报告.md` in scope (loop) | **REFUSED** (defect 1) |
| T7 | metadata + results.json + SUMMARY + calc narrowing (loop) | clean |

Cautions on a legitimately narrowed `except ValueError` (H2, T6, T7): none.

## Evasion table (want a caution)

| # | Evasion | Result |
|---|---|---|
| E1, E2 | tuple / no-space `except(Exception)` | caution |
| E3 | narrow except + `logging.exception` + `continue` | silent (documented non-claim) |
| E4 | `if not data: return {}` | silent (documented) |
| E5 | `skipif(True)` | caution |
| E6 | delete the failing `assert` | caution |
| E7 | `test_x` → `_test_x` | caution |
| E8 | pyproject `addopts --deselect` | silent (data class, documented) |
| E9 | `filterwarnings('ignore')`, `pragma: no cover`, `pylint: disable`, `pyright: ignore` | caution ×2 |
| E10 | JS `catch (e) {}` | caution |
| E11 | `set +e`, `\|\| true` | caution |
| E12 | `assert x or True` | caution |
| E13 | `.ipynb` try/except pass | silent (data class, documented) |
| E14 | relax `threshold` in results.json | silent (data, documented) |
| E15, E16 | `contextlib.suppress`, `except BaseException` | caution |
| E17 | new helper file with `except Exception: pass` | caution |
| E18 | defensive code behind 600 KB doc (cap) | caution "1 staged file(s) … not screened: src/calc.py" |
| E19 | `except ValueError: sys.exit(0)` | silent (documented) |
| X1 | wrap the re-added failing line in `if TYPE_CHECKING:` | **silent** (squash-equality hides it) |
| X2 | move the assert into a fixture nobody uses | silent (same) |
| X3 | `pytest.importorskip('nonexistent')` | **silent** |
| X4 | `getattr(warnings, 'simple'+'filter')('ignore')` | silent (dynamic; unfixable by regex) |
| X5 | `except Exception: return None` in a NEW in-scope helper called from calc.py | caution |
| X6 | `# """` on the previous line then `except Exception: pass` | caution |
| X7 | `except Exception: ...` (Ellipsis) | caution (`broad_exception`; `empty_handler` misses the one-line `...` form) |
| X8 | `except Exception:` + `return None` | caution |
| X9 | `pytestmark = pytest.mark.skip(...)` | caution |
| X10 | broad except in `.pyx` | **silent** (not a code suffix) |
| X11 | `python calc.py \|\| exit 0` | **silent** |
| X12 | `raise` → `warnings.warn(...)` | caution |
| X13 | `assert` → `if not cond: print()` | caution |
| X14 | test body → `return` | caution |
| X15 | Makefile recipe `-python calc.py` | **silent** |
| T8 | model-written `fig 1.png` (loop, real git) | **committed, no refusal** (defect 3) |

First review: 14/19 passed silently; now 6/19 silent, all six documented as non-claims. Of 15 new: 8 caution, 7 silent (X1, X3, X10, X11, X15 cheap to add; X2, X4 not).

## Comment / string stripping

`x = "a # b"  # c` → `x = ""`; `'http://x//y'` → stripped as a string; `${#arr[@]}` → `echo "" || true` (still correct for the pattern); `"""`/`'''`/`/*`/`*`/`#`/`//` line starts → `""`. Mis-handled: docstring/heredoc **interiors** (`    ... except Exception:` and heredoc `set +e` are screened as code — N7 noise, heredoc a caution on prose), `x = 1 /* c */; except …` (mid-line block comment not stripped; harmless direction), `x = '''` → `x = ""'` (harmless). No false refusal from any of these — cautions only.

## Mutation log (real src mutated, guard suites run, `git checkout -- src` after each; tree clean at the end)

Builder's `mutate-D2.py` re-pointed at this worktree: **15/15 caught** (M1 guard call, M2 `.md` as code, M3 `.json` as code, M4 `extra_notes` hook, M5 `locally_rendered`, M6 diff cap, M7 findings replaced, M8 removed-line screen, M9 mode ignored, M10 word patterns restored, M11 free retry, M12 stripping, M13 scope, M14 binary, M15 round 1).

Mine (`mutate-D2-mine.py`):

| # | Mutation | Result |
|---|---|---|
| R1 | `}` dropped from `_PASS_ONLY` (two-line JS `catch (e) {` / `}` unseen) | **89 passed — survived** |
| R2 | removed lines also set `previous` | caught |
| R3 | `truncated` flag `>=` → `>` | caught |
| R4 | per-round `revision_cautions = []` reset removed (stale notes) | caught |
| R5 | `pragma: no cover` alternative dropped | **survived** |
| R6 | `catch (Throwable\|Exception` alternative dropped | **survived** |
| R7 | `unittest.skip` dropped | **survived** |
| R8 | `mark.xfail` dropped | **survived** |
| R9 | `@ts-ignore`/`eslint-disable` dropped | **survived** |
| R10 | `_unquote` returns the raw quoted token | **survived** |
| R11 | empty-diff refusal dropped | caught |
| R12 | budget counts document lines | caught |

6/12 survived; all six are pattern alternatives or the quoting path with no dedicated red case (defect 6).

## User-facing strings (plain? ZH?)

All name the file and the construct in plain words; none has ZH (`cli/i18n.py` on fusion/console has no `repair*` key; `console/page.py` has `repair_refused` copy that is now wrong — defect 8). Needing ZH:
- cautions: "{path} adds a catch-all `except` that swallows every error"; "… adds a `suppress(...)` block that hides errors"; "… adds an error handler that does nothing"; "… adds an assertion that can no longer fail"; "… adds a skipped or expected-to-fail test"; "… adds a shell step that ignores its own failure"; "… adds a marker that silences a checker (`noqa`, `type: ignore`, `pragma: no cover`, ...)"; "… adds a warnings filter set to ignore"; "… removes an `assert` or `raise` without replacing it"; "… removes a test"; "the code change touches N lines, more than the N-line limit for an automatic repair"; "N staged file(s) lay beyond the review size limit and were not screened: …"
- refusals: "{path} is outside the audited directories ({dirs}); only files inside them may change — if the fix needs another file, say so in `notes`"; "{path} is a binary file written directly by the generator, which cannot be reviewed line by line"; "the revision changed nothing that could be reviewed"
- events: "the revision was refused before the audit"; "asking for a repair that stays within the audited files"; "the revision has edits the auditor should weigh"; note prefix "revision caution: "
- prompt: "[BLOCKER] The repair guard refused the last revision:"; "The previous attempt was rolled back. Repair the findings above without that change; if the fix genuinely needs it, say so in `notes`."; termination "the automatic repair was refused in round N because …"
- config: "repair must be a mapping"; "repair: unknown keys […]"; "repair.enabled must be true or false"; "repair.mode must be caution or refuse"; "repair.max_changed_lines must be an integer from 1 to 10000"; scaffold comment `scaffold/__init__.py:64-68`.
Wording nits: "lay beyond the review size limit" → "were larger than the review can read"; the scope sentence is two clauses joined by a dash and a semicolon — split into two sentences.

## Counts

- `tests/test_repair_guard.py` + `tests/test_build_repair_guard.py`: **111 passed** (17.7 s).
- Review loop probes (9, scratch, removed afterwards): T1, T5, T6, T7, T9 as expected; T2, T3, T8 fail — defects 1–3; T4 informational (defect 9).
- Full suite, foreground, `PYTHONPATH=<worktree>/src`: **2181 passed, 2 skipped, 1 failed** in 397 s. The failure is `test_guard_names_match_what_they_check` listing only `tests/test_finding_states.py::test_no_user_facing_surface_renders_a_state_word` — slice A's file, byte-identical to base on this branch, absent on the fusion line (review-D); nothing from this slice.
- Tree clean at the end (`git status --short` empty); worktree removed.
