# Build report — slice D (repair guard), branch `fusion/repair-guard`

Worktree: `/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-repair-guard`
Base: `50349f9`. Not pushed. `auditor/ broker/ ledger/ policy/ dcl/ receipt/ console/ cli/main.py controller/` untouched.

## Commits (in order)

| sha | what |
|---|---|
| `bfb0f9e` | `src/crossaudit/repair_guard.py` — pure diff screen (D1) |
| `0c66d3f` | `config.py` `repair:` section + `RepairPolicy`; scaffold block; `generator.py` findings heading/instruction (D2, D3) |
| `5807ef6` | `cli/build.py` wiring: `revision_scope`, `locally_rendered`, guard call, one free retry, cause `repair_refused` (D4) |
| `280b566` | `tests/test_repair_guard.py` (unit) + `tests/test_build_repair_guard.py` (loop, config, init→load) (D5) |

## What was built

**D1 `repair_guard.py`.** `RepairGuard(max_changed_lines).assess(diff, allowed_files, locally_rendered_files=)` → `RepairAssessment`. `parse_unified_diff` handles the exact `git diff --cached --binary --no-ext-diff` shape (quoted paths, deletions, `GIT binary patch`). Scope and binary screens on every file; `DEFENSIVE_PATTERNS` (codex's five, same names) on ADDED lines of `is_code_file()` paths only; budget = added+removed over code files only. Each reason is one sentence naming the file ("src/x.py adds a catch-all `except` that swallows every error"; "other.md is outside what the last audit asked to change (allowed: report.md)"). No git calls.

**D2.** `config.py`: one entry in `_ALLOWED_TOP`, one `RepairPolicy` dataclass (placed directly above `Config`), one `Config.repair` field with default, one validation block before `return Config(`, one kwarg — all `ConfigDenial(..., file=str(p))` like the neighbours. Scaffold `CONFIG_TEMPLATE` gets the block after `checks:` with a two-line comment.

**D3.** `GENERATOR_SYSTEM`: the D144 dispute sentence is kept verbatim; a new bullet beside it: "Do not make a check disappear by adding broad exception handling, silent fallbacks, retries, suppressions, skipped tests, or relaxed assertions. Repair the cause with the smallest change; a revision that hides a finding is refused." `build_prompt`: heading `WHAT STOPPED THE LAST ROUND`, instruction as specified (smallest causal repair + the misreading→`notes`→dispute clause). No `verified_only` (D144).

**D4 `build.py`.** Top-level imports of `parse_findings` (from `..dispute`, no cycle) and `RepairGuard`. `revision_scope` starts `None`, is reset to `None` immediately before every audit, and is derived after a BLOCKED audit by `_blocker_scope(report)` (every `[BLOCKER]`, DCL and model alike; `set()` if any artifact is `increment` / `?` / `invalid Auditor reply`). `model_written = set(written)` after apply; `locally_rendered = set(written) - model_written` after render. Guard call sits after `_staged_secret` and before the commit `try:`; refusal emits `repair_refused` (state REVISING, detail = reasons joined), sets `findings` to the specified `[BLOCKER]` text (bulleted reasons + "The previous attempt was rolled back; make a smaller change that fixes the cause."), and `continue`s through the `with written:` exit (files + index restored — no hand-rolled `git restore`). `repair_refusal_used` gives one free retry (with a `revision_retry` event); the second refusal, or a refusal on the last round, sets `repair_refusal_stop`, a one-sentence `termination_reason` ("the automatic repair was refused in round N because <first reason>") and breaks; `record_decision_object()` maps it to `kind="audit"`, `cause="repair_refused"` (comment in the cause chain documents the string as stable).

## Deviations from the spec, and why

1. **Scope resolution by path suffix (`_resolve_scope`).** DCL findings name materialised relative paths; a model finding may name only `SUMMARY.md`. Exact matching would refuse an honest edit of the named file for its spelling — a D121 defect — so a scope entry matches a staged path exactly or as a `/`-suffix; unresolved entries are passed through as allowed names (harmless). Test + M2 mutation cover it.
2. **`revision_scope` lifetime.** Spec: "None on any round not following a BLOCKED audit". Implemented as "reset at every audit, set after BLOCKED": a generation-refused or guard-refused `continue` (no audit ran) keeps the scope of the still-BLOCKED audit, which is what the retry is repairing. Round 1 is provably never a repair round (test).
3. **`repair_refused` on the CLI side.** Only `build.py` enumerates causes; `errors.py` maps escalation *kinds* (`repair_refused` stays under kind `audit`, remedies REVISE/STOP fit) and `main.py` has no cause helper (grep `no_progress`: only `console/page.py`, not mine). So no other file needed the string; it is documented in the cause chain comment.
4. **`silent_pass` kept as codex wrote it** (any added bare `pass` in a code file). It can redden an honest `pass` (empty class body). Kept because the spec said port; it is code-only, so prose is safe. Flagging it here as the pattern most likely to need loosening after real use.
5. **`revision_retry` event reused** for the free re-ask rather than a new event kind, so the console needs no new copy for the retry itself; `repair_refused` is the one new event kind (console copy is the other slice's).

## Tests

- New: `tests/test_repair_guard.py` (unit) and `tests/test_build_repair_guard.py` (loop/config/init) — 67 passed together.
- D10 counterfactuals run against the real product (`codex-compare/mutate-D.py`, tree restored after each): 7/7 caught, each against the real code (script restores the file after each run):
  - M1 guard call removed → 3 loop tests fail (refused/rolled-back, second-refusal stop, scope-by-name)
  - M2 `_resolve_scope` exact-match only → basename-artifact test fails (D121)
  - M3 `.md` added to `CODE_SUFFIXES` → prose `.md` case, budget-exemption test, docs-only loop test fail (the .txt/.csv/.tex/.rst/README prose cases still pass, as they should)
  - M4 `repair` dropped from `_ALLOWED_TOP` → init→load test fails
  - M5 free retry never consumed → second-refusal test fails (loop would burn all rounds)
  - M6 removed lines screened too → all 5 per-pattern "only added lines" tests fail
  - M7 `cfg.repair.enabled` ignored → dial test fails
- Related suites after each step: `test_generator test_format_repair test_first_three_minutes test_cli_i18n test_install_origin test_constitution_moment test_build_commit_secretscan test_loop_integrity test_science_proposal` — 177 passed; loop trio after D4 — 56 passed.
- Full suite: `pytest -q tests/` → **2137 passed, 1 failed, 2 skipped** (304 s).
  The one failure is `tests/test_guard_names_match_what_they_check.py::test_no_test_name_claims_an_outcome_its_body_does_not_check`, whose offender list is exactly `tests/test_finding_states.py::test_no_user_facing_surface_renders_a_state_word` — a slice-A (finding-states merge) file, byte-identical to base `50349f9` on this branch, and none of my test names appear in the list. Pre-existing at the base; not touched here because it belongs to another slice's file.

## Undone / for the merger

- Console copy for event `repair_refused` and Decision Center branch for `cause === 'repair_refused'` (other slice; strings stable).
- `config.py` edit is five small hunks around `budgets`; an `authority:` section from the other builder should merge beside it without conflict unless it also edits the `budgets`→`return Config(` gap.

---

# Rework (after review-D: NEEDS CHANGES)

Branch `fusion/repair-guard`, worktree unchanged, still not pushed, tree clean. Four commits on top of `280b566`:

| sha | what |
|---|---|
| `06be993` | cherry-pick of `d6f1b5a` (docs slice E) so the two doc sections could be edited in place |
| `a0d7270` | the rework: `repair_guard.py` rewritten; `config.py` `repair.mode`; scaffold comment; `generator.py` bullet made honest; `cli/build.py` rewired; **one additive line in `cli/main.py::cmd_run`**; `docs/EVIDENCE_AUTHORITY.md` "The repair guard" and README "Where a finding's authority comes from" rewritten |
| `c82d5f0` | both test files rewritten to the new contract |
| `3851f0b` | two test names fixed for the D106 naming guard |

## The new contract

**Refusals** (every mode; round rolled back via the `with written:` exit, `repair_refused` event, `findings = original findings + refusal block`, one free retry, then `cause="repair_refused"`):
- a file outside `scope.dirs` (the audited increment — the artifact-string scope, `_blocker_scope`/`_resolve_scope`, is deleted);
- a binary the local document renderer did not produce;
- (the screen also refuses an empty diff).

**Cautions** (`repair.mode: caution`, default): the round commits and is audited; a `repair_caution` event (state REVISING) carries the sentences; each rides to the next audit as `revision caution: <sentence>` in `run_audit(notes=…)` → `dcl.notes`, which the auditor prompt renders (the `dcl` JSON block) and the ledger stores in `checks.json`. The prefix does not trip CA-META-004. `repair.mode: refuse` turns every caution into a refusal (validated: `caution|refuse`).
- code files only (`classify()`: code / data / document — JSON, YAML, TOML, INI, CSV, ipynb are data; never budgeted, never pattern-screened);
- added lines with comments, docstrings and string literals stripped: `broad_exception` (bare/`Exception`/`BaseException`/tuple/`except(Exception)`/`catch (Throwable`), `suppress_context`, `empty_handler` (`except …: pass`, two-line `except`/`pass` with the header as context, JS `catch {}`), `relaxed_assertion` (`assert True`, `… or True`), `disabled_test` (`mark.skip`, `skipif(True`, `mark.xfail`, `unittest.skip`), `shell_ignore_errors` (`set +e`, `|| true`);
- markers on the raw line: `lint_suppression` (`noqa`, `type: ignore`, `pragma: no cover`, `pylint: disable`, `pyright: ignore`, `eslint-disable`, `@ts-ignore`), `warning_suppression` (`filterwarnings('ignore')`);
- removed lines not re-added in the file: `removed_check` (`assert`/`raise`), `removed_test`;
- code lines over `max_changed_lines`; staged files beyond the 512 KB cap (`staged_files` + `truncated=True`; the scope screen uses git's staged list, so the cap can no longer hide a file).
- Gone: word-level `retry`/`fallback`/`skip`/`xfail`/`best effort`, bare `pass`, `suppress` as a word.

Honest claim (D10/D146): module docstring, `GENERATOR_SYSTEM`, EVIDENCE_AUTHORITY.md and README now say "a heuristic that surfaces likely defensive edits to the auditor, not a guarantee", and name what it cannot see (early return, narrow-except-and-continue, data thresholds, `sys.exit(0)`).

## Deviations from the rework instructions, and why

1. **`cli/main.py` touched (one additive line).** The instruction said the `notes` mapping is in build.py; it is not — `notes` are assembled in `main.py::_materialise_tree_scope` and handed to `run_audit` inside `cmd_run` (line ~1637). build.py calls `cmd_run(run_args)` in-process, so the only existing channel is an attribute on `run_args`: `notes = [*notes, *getattr(args, "extra_notes", ())]` — additive, default-empty for every other caller, no change to `auditor/`. Flagged for the main.py owner; it is one line beside the `run_audit(` call in `cmd_run` and should merge cleanly.
2. **Review #9 (prompt weight) taken:** the system-prompt bullet no longer repeats "smallest change"; that instruction lives once, in the findings block. The D144 dispute sentence is unchanged.
3. **Loop-level scope refusal is reached only by simulation**: `gen_mod.apply` already confines the generator to `scope.dirs`, so the test stages a stray path by wrapping `_stage_generated`. The screen is defense-in-depth there; the unit tests cover it directly.
4. **Round-1 repair after a human resumes a BLOCKED cycle** (review #10) is still unscreened — `repair_round` starts False; documented, not changed (the resumed round has no findings text in the prompt either).

## Counts

- `tests/test_repair_guard.py` + `tests/test_build_repair_guard.py`: **111 passed** (24 honest positive controls, 12 evasion cautions, non-claims, red/green per pattern, cap/scope/binary, loop caution/refusal/refuse-mode/M9/M12/config).
- D10 counterfactuals (`codex-compare/mutate-D2.py`, real code mutated, tree restored, clean at the end): **15/15 caught** — guard call removed; `.md` as code; `.json` as code; `extra_notes` hook dropped; `locally_rendered` emptied (review M9); diff-cap slice dropped (review M12); findings replaced instead of kept; removed-line screen dropped; `repair.mode` ignored; word-level retry/fallback/skip restored; free retry never consumed; comment/string stripping disabled; scope screen dropped; binary screen dropped; round 1 screened.
- Related suites after the rework (`test_loop_integrity test_build_commit_secretscan test_format_repair test_generator test_document_export test_first_three_minutes test_cli_i18n`): 159 passed.
- Full suite, foreground (`pytest -q tests/`, 365 s): **2181 passed, 2 skipped, 1 failed**. The failure was the D106 naming guard listing two names: my `test_only_a_locally_rendered_binary_may_be_committed` (renamed in `3851f0b`; guard + my files re-run: my name gone) and slice A's `tests/test_finding_states.py::test_no_user_facing_surface_renders_a_state_word`, byte-identical to base `50349f9` on this branch — the reviewer reports it absent on the fusion line, so it disappears at merge. Nothing else failed.

## Still open (other slices)

- Console copy for events `repair_caution` / `repair_refused`, the Decision Center branch for `cause === 'repair_refused'`, and ZH for the sentences listed in review #8 (now: the ten caution sentences, the two refusal sentences, the budget/unscreened sentences, the `[BLOCKER]`/rolled-back prompt text, the two event texts, the scaffold comment, the four config denials incl. `repair.mode must be caution or refuse`).

---

# Rework 2 (after review-D2: NEEDS CHANGES, 10 items)

Branch `fusion/repair-guard`, same worktree, tree clean, not pushed. `git merge fusion/evidence-authority` fast-forwarded to `3049958` (the lead's merge `e840b18` + `1fba14b` i18n + `3049958`). One commit on top:

| sha | what |
|---|---|
| `8b15fee` | "repair guard: exact path spellings, truthful caution sentences, wider reach (review D2)" — `repair_guard.py`, `cli/build.py`, `docs/EVIDENCE_AUTHORITY.md`, `README.md`, both test files |

## Items, as fixed

1. **Paths (D2 #1, #3).** `build.py::_staged_paths` reads `git diff --cached --name-only -z` (NUL, unquoted; `_stage_generated` and `_staged_secret` both use it); the screened diff is `git -c core.quotepath=false diff --cached --binary --no-ext-diff`. `parse_unified_diff` accepts quoted headers (`"a/say \"hi\".py"`), unquoted paths with spaces via an equal-halves split of `a/P b/P`, and `rename to` / `+++` fallbacks; `unquote_path` decodes `\346\212\245` to `报告`. Tests: a real-git unit test with `报告.md`, `fig 1.png`, `say "hi".py` (under both quotepath settings), loop tests T2 (CJK name in scope → no refusal) and T8 (`fig 1.png` model-written binary → refused).
2. **Scope normalisation (D2 #2).** `normalise_path` (`posixpath.normpath`; strips `./`, trailing `/`, `//`) on both scope dirs and paths. `apply`'s own helper `_request_parts` raises denials rather than normalising, so it was not reused; the spellings it accepts are the ones tested (`./experiments`, `experiments/`, `experiments/./demo`, `experiments//demo`). Loop test T3/N11.
3. **Truthful sentences (D2 #4).** `broad_exception` says "adds a catch-all `except` (its handler re-raises)" when the handler — same line or the following lines until dedent — contains `raise`/`throw`; `removed_check` says "changes an `assert` or `raise`" when a line with the same keyword was added in the same hunk; `removed_test` says "renames a test" when a test def was added in the same file. The strong sentences stay for E6/E7/E16/X13. Ten truthful cases plus the dedent case are tested.
4. **Doctests / docstrings (D2 #5).** `>>>` and `...` lines are comments; a per-hunk docstring state (odd count of `"""`/`'''` on a post-image line) blanks interiors. An opening outside the hunk remains the documented blind spot.
5. **Every alternative bites (D2 #6).** A table-driven test over 41 alternatives (every regex branch, incl. the two-line JS `catch (e) {` / `}`) plus the unquote path. Review survivors R1, R5–R10 now fail under mutation.
6. **New cautions (D2 #7).** `|| exit 0`, `importorskip(`, `if TYPE_CHECKING:` / `if False:` / `if 0:` (new pattern `dead_branch`), Makefile `\t-` recipe prefix; `.pyx` / `.pxd` are code. X2 / X4 stay listed as non-claims in the docstring.
7. **Apply-side denial keeps the findings (D2 #9).** New `audit_findings` (set when an audit BLOCKS) is what every pre-audit refusal appends to: the `apply` scope denial, both document-export refusals, and the screen's refusal — a repeated denial yields one refusal block per prompt, not a pile. Docs now say `apply` is the first line of the scope boundary. Loop tests T4 and pile-up.
8. Wording: "were larger than the review can read"; the scope refusal is two sentences.

## Counts

- `tests/test_repair_guard.py` + `tests/test_build_repair_guard.py`: 176 passed; together with ten related suites (loop integrity, secret scan, format repair, generator, document export, first-three-minutes, cli i18n, evidence authority, no-undefined-names, guards-state-their-reach): **498 passed**.
- D10 counterfactuals (`codex-compare/mutate-D3.py`; real code mutated, tree restored, clean at the end): **20/20 caught** — `-z` dropped; unquote returns raw; normalise dropped; equal-halves dropped; re-raise check dropped, and ignoring indentation; same-hunk check; added-test check; doctest prompts; docstring state; `}` in `_PASS_ONLY`; `pragma`, `unittest.skip`, `@ts-ignore`/`eslint-disable` branches; `|| exit 0`; `importorskip`; `dead_branch`; `.pyx`; apply-side replace; pile-up. The earlier `mutate-D2.py` (15) still applies.
- Full suite, foreground, 321 s: **2447 passed, 2 skipped, 0 failed**.

## Strings needing ZH (D2 #8 — console builder's) — exact, from `repair_guard.py` and `cli/build.py`

Cautions (each prefixed `{path} adds ` unless noted):
- `a catch-all `except` that swallows every error`
- `a catch-all `except` (its handler re-raises)`
- `a `suppress(...)` block that hides errors`
- `an error handler that does nothing`
- `an assertion that can no longer fail`
- `a skipped or expected-to-fail test`
- `code under a branch that never runs (`if TYPE_CHECKING:` / `if False:`)`
- `a shell or make step that ignores its own failure`
- `a marker that silences a checker (`noqa`, `type: ignore`, `pragma: no cover`, ...)`
- `a warnings filter set to ignore`
- `{path} removes an `assert` or `raise` without replacing it` / `{path} changes an `assert` or `raise``
- `{path} removes a test` / `{path} renames a test`
- `the code change touches {N} lines, more than the {M}-line limit for an automatic repair`
- `{N} staged file(s) were larger than the review can read and were not screened: {paths}`

Refusals:
- `{path} is outside the audited directories ({dirs}). Only files inside them may change; if the fix needs another file, say so in `notes`.`
- `{path} is a binary file written directly by the generator, which cannot be reviewed line by line`
- `the revision changed nothing that could be reviewed`

Events (`build.py`): `the revision was refused before the audit`; `asking for a repair that stays within the audited files`; `the revision has edits the auditor should weigh`; note prefix `revision caution: `.
Prompt (`build.py`): `[BLOCKER] The repair guard refused the last revision:`; `The previous attempt was rolled back. Repair the findings above without that change; if the fix genuinely needs it, say so in `notes`.`; termination `the automatic repair was refused in round {N} because {reason}`.
Config: already translated in `cli/denials_zh.py` (`repair must be a mapping`, `repair: unknown keys {}`, `repair.enabled must be true or false`, `repair.mode must be caution or refuse`, `repair.max_changed_lines must be an integer from 1 to 10000`). Scaffold comment: the `repair:` block in `scaffold/__init__.py`.
Console: `page.py`'s `repair_refused` Decision Center summary is stale (by default only out-of-scope files and unrendered binaries refuse); `repair_caution` has no copy.

## Not done (by ruling or out of reach)

- D2 #8 console/i18n copy: console builder's.
- D2 #10 (provider-failure paragraph carried into the retry prompt): pre-existing `render_findings` behaviour, untouched.
- X2 (assert moved into an unused fixture), X4 (`getattr` suppression): documented non-claims.

---

# Rework 3 (closure audit, row D #6: binary past the read cap was committed)

Branch `fusion/repair-guard`; `git merge fusion/evidence-authority` fast-forwarded to `ad1dc0b`; one commit on top: **`2696186`** "the binary screen reads git's numstat, not the capped diff text". Tree clean, not pushed.

**Defect.** `untrusted_binary` was derived from the parsed patch text; with the diff cut at `_MAX_SCAN_BYTES`, a model-written `fig 1.png` staged after a long document was never parsed and reached history with only an "unscreened" caution.

**Fix.** `repair_guard.parse_numstat(raw)` reads `git diff --cached --numstat -z` (binary = `-\t-`; the rename form `added\tremoved\t\0old\0new\0` keeps the post-image path; paths normalised). `build.py::_staged_binaries(cfg)` hands those paths to `assess(binary_files=...)`; any not in `locally_rendered_files` is refused whether or not the diff text still shows it, and they are excluded from the "unscreened" caution. The cap now limits only the pattern screen.

**Tests.** Unit: `parse_numstat` on a real repo with `图 2.png`, `fig 1.png` (binary) and `报告.md` (text), plus the rename form; a truncated diff with a reported binary → refused, and allowed when locally rendered. Loop: the auditor's scenario (cap 4 KB, long `SUMMARY.md` + `fig 1.png`) → `repair_refused` with the binary sentence, index and tree rolled back, PNG absent from `git log`, honest round 3 commits.

**Counts.** My two files + loop integrity, secret scan, document export: 236 passed. D10 counterfactuals (`mutate-D4.py`): 4/4 caught — `binary_files` no longer passed; `-\t-` read as text; reported binaries not unioned; rendered binaries no longer exempt (the `|`/`-` precedence bug I introduced and the existing tests caught). Full suite, foreground, 328 s: **2473 passed, 2 skipped, 0 failed**.
