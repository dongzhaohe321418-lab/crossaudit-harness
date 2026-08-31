# auditor3 — `agentA/cli-i18n-wave1` at `51b979a`

Auditor: Codex (`auditor3`), cross-vendor from the Claude author. No feature code
written. Audit performed against detached commit
`51b979a375b17cab0143f479379b94d4d6836dd0` in
`/tmp/crossaudit-audit3-51b979a-20260831`.

Verdict: **MERGE AFTER FIXES** — S0 0, S1 3, S2 1, S3 0. The failures are
reachable and gating, but each has a bounded repair on this branch rather than
requiring a redesign of the audit core.

Chinese assessment: `zh_complete=no`; `zh_position=half-shipped`. The narrow
front-door “present, not satisfied” claim is honest in isolation, but the branch
does expose `--lang zh` on the half-English build path and carries default
Chinese init into an English console handoff.

## F1 — S1 — `init` says Ready where `doctor` immediately says Not ready

The keyed source-install path violates the property named by
`test_init_says_ready_only_when_doctor_would_agree`.

Executed with the shared interpreter and both role keys present:

- `init --lang zh --no-console ...` printed `就绪` and offered `build`.
- In the created project, `doctor --lang zh` immediately printed `尚未就绪` and
  exited 20 because the source install cannot admit receipts.

The producer at `wizard.py:594-629` computes only missing credentials. The
consumer at `wizard.py:838-865` casts an empty credential list to Ready and
offers the run commands. `doctor` additionally checks `admission-capable`.

The guard stops before its own claim: the keyed case at
`tests/test_first_three_minutes.py:198-211` executes only `cmd_init` and never
executes doctor. The no-key case does execute both, but cannot reach this state.
This is the S1 already recorded in D34, still present in the rebased branch.

Required guard and mutation: execute keyed `init` followed by real `doctor`
under a non-admissible install identity; it must not permit Ready followed by
exit 20. Demonstrate it red by restoring credential-only readiness.

## F2 — S1 — the shipped Chinese command paths are half-localised beyond the tested seams

Two real consumers remain English after a person explicitly chooses Chinese.

1. Default `init --lang zh` continues through `_open_console` because
   `--no-console` defaults false. After a Chinese wizard it printed:

   ```text
   Console: http://127.0.0.1:7777/?token=fixture
   Open that URL when you are ready.
   ```

   The failure path at `main.py:1334-1335` is English too. The claimed end-to-end
   test fixes `no_console=True` at `tests/test_cli_i18n.py:100`; replacing the
   real console line with `UNTRANSLATED SENTINEL` left
   `test_the_whole_wizard_speaks_chinese_end_to_end` green by its own name.

2. A real keyless `build "写一份说明" --lang zh` printed the banner, round,
   actors, provider failure, and stop narration in English, then only the final
   three lines in Chinese. Its remedy also joined two environment identifiers
   with the English prose word `and` (`build.py:1162-1163`). The runtime consumer
   is `build.py:1096-1139`. The named test at
   `tests/test_cli_i18n.py:378-391` only calls `i18n.t()`; removing the production
   language-selection line at `build.py:1082` left that test green: 1 passed.

D21's reason for withholding `--lang` was to avoid exactly one translated piece
inside an English surface. `build` currently offers `--lang zh` on that shape,
and the default init route crosses the same seam after the test returns.

Required guards and mutations:

- Run `cmd_init` with `no_console=False` through the real `_open_console`
  renderer (daemon and browser may be controlled); inject untranslated prose in
  that renderer and require the named Chinese assertion to fail.
- Execute the real missing-credential `cmd_build` path and assert the human
  transcript beyond runtime events, not catalogue return values; remove the
  production language selector and require that guard to fail by its own name.

## F3 — S1 — Chinese enters the promised English-only `doctor --all` and JSON contracts

On a real project initialised with profile `own`, which creates a deliberate
no-rules constitution:

```text
[INFO] constitution rules      暂无规则 — 在你添加之前不会拦截任何东西；自动检查仍会运行
```

That row appeared in `doctor --all --lang zh`. The same Chinese sentence was the
`detail` value in `--json doctor --lang zh`. The branch contract says `detail`,
`fix`, `--all`, and JSON remain machine English; acceptance says `doctor --all`
contains no Chinese.

The producer translates the detail before choosing a renderer at
`main.py:367-370`. `_render_doctor_full` then emits the already-translated value
unchanged at `main.py:643-650`, while JSON consumes the same object at
`main.py:516-518`.

`test_the_doctor_machine_surfaces_stay_english` uses an empty directory and
returns at the missing-config branch before this row can exist
(`tests/test_cli_i18n.py:306-318,337-351`). Its green result is true only at that
seam.

Required guard and mutation: initialise a real `own` project, run both `--all`
and JSON under `--lang zh`, and assert machine detail remains byte-identical to
English. Move translation to the human renderer; restoring producer-side
translation must redden both assertions by name.

## F4 — S2 — visible fallback is only half implemented outside `init`

The module and A4 contract require both an inline `[en]` mark and a final
`[i18n]` count naming missing keys. `cmd_init` calls `_report_untranslated`, and
the human `Denial` dispatcher does; normal doctor and build completion do not.

Production-data mutation executed: removed
`doctor.admission_capable.label` from the Chinese catalogue and ran the real
doctor. Result: exit 20, inline mark present, fallback key recorded, **no
`[i18n]` summary**. The current catalogue is complete, so this is hardening
rather than a present untranslated sentence, but the stated two-half fallback
mechanism is not held for two of the three commands that expose `--lang`.

Required guard and mutation: delete one reached doctor translation and one
reached build translation; each command must name the fallback key at command
completion as well as mark the inline English.

## F3/PATH status — cleared suspicion

The PATH collision remains honestly open:

- `docs/findings/w1-bundle-reachability-b5b3ea5.md:62` says **OPEN** and
  `:80` says the app-side detector still does not close it.
- The live decision ledger repeats that F3 stays open (D66, D77, D82).
- The A6 contract says the new CLI only identifies itself and does not search
  for rival installs.

No current-branch claim says editing the new binary changes stale 3.2.0 output.
`f3_open=yes`.

## Other cleared suspicions

- Branch identity: `agentA/cli-i18n-wave1` resolves exactly to the dispatched
  full SHA. Detached worktree HEAD and tree were recorded before inspection.
- The front-door **present, not satisfied** position is honest in isolation: a
  fresh bare CLI process has no front-door `--lang`, so the translated origin
  line is not exposed as the lone Chinese line of that English screen.
- Catalogue key sets and format-slot sets are symmetric for English and Chinese;
  no copied-English translation remains outside the two named identifier-only
  exceptions.
- The rebase's drifted-constitution state is exercised on a real committed then
  edited file in both languages; it is not inferred from a string table.
- The restored `machine:<name>` key and Path-to-string slot coercion reached the
  real doctor/JSON suite; no serialization failure reproduced.
- `git diff --check` is clean. No audit-core file or receipt format changed in
  this branch delta.
- Install-origin tests do establish source CLI reachability. They do not prove
  frozen Core/DMG or GUI parity.

## Full-suite result and evidence seam

Exact command, with explicit detached checkout and shared interpreter:

```sh
cd /tmp/crossaudit-audit3-51b979a-20260831 && PYTHONPATH=src /Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python -m pytest -q
```

Result: **1,857 collected; 1,855 passed; 2 skipped; 0 failed** in 241.49 s.

The suite establishes source-mode Python/terminal behavior at the paths each
fixture reaches. It does not establish the frozen PyInstaller Core, DMG wrapper,
browser DOM, or accessibility tree. In particular, the Chinese init fixture
stops before the real console-launch consumer and the build fixture stops at the
catalogue.

## Independence limit

My weakest independence is linguistic: I independently executed reachability,
language continuity, and machine-contract boundaries, but I am not treating my
judgment of Chinese idiom or tone as a substitute for the design/native-language
reviewer. The gating findings above do not depend on translation taste; they are
English leakage, contradictory verdicts, and machine payload bytes.
