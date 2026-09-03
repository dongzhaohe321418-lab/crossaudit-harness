# Independent review — A. setup & preflight (at bf32c8e)

Reviewer: independent (did not write the change). Worktree
`/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-review-setup`
detached at `bf32c8e`, `PYTHONPATH=<worktree>/src`, python
`/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python`.
`crossaudit.__file__` confirmed at
`<worktree>/src/crossaudit/__init__.py`. No tracked file left modified
(`git status --porcelain` empty at the end).

Commits reviewed: b56bd16, 2b7cd71, 0132d14, 6ea35dd, 4241e51, cce8bc5
(branch `fusion/ux-setup`, merged 5ff640c). 11 files, +537 / −25.

## Verdict

**NEEDS CHANGES** — 10 defects (1 high, 3 medium, 6 low). The slice does what
the build report claims on the paths it covers; the failures are on the paths
it does not cover: a second in-app entry point still shows the CLI sentence and
records the setup step as an audit escalation, and the retry narration the
slice deliberately widened has no Chinese at all.

## Counts

| | |
| --- | --- |
| Full suite, foreground, at bf32c8e | **2527 passed, 2 skipped, 1 warning, 349.94 s — green** |
| New tests | 14 in `tests/test_setup_preflight.py`; 1 pin updated in `tests/test_first_launch.py` |
| Mutations run | 13 |
| Mutations killed | 10 |
| Mutations survived | 3 (M2, M6, M12 — defects 5, 6, 7) |

## What I verified as correct

- **Credential preflight, driven against the real console server**
  (`server.setup_needed`), five cases from the spec:

  | case | `missing_credentials` | `setup_needed` |
  | --- | --- | --- |
  | (a) no keys | `['generator','auditor']` | card |
  | (b) generator key only | `['auditor']` | card |
  | (c) gen key + auditor `openai_codex` | `[]` | none |
  | (c) gen key + auditor `replay` | `[]` | none |
  | (d) generator vendor `human` / `Human` | `[]` | none |
  | (e) demo project (both roles `replay`) | `[]` | none |
  | (a) with `CROSSAUDIT_APP_MODE` unset | `['generator','auditor']` | none |

  Card only in (a)(b); never in (c)(d)(e); never outside app mode. No false
  fire from "env var set but Keychain empty" (`app_keys.status()` is itself
  env-derived, and `load_into_environment` writes both the vendor variable and
  the `ROLE_FALLBACKS` role variable, so vendor aliases resolve).
- **Composer survives.** `page.py:7702-7709` — the `r.setup==='credentials'`
  branch contains no `say.value=''`; the clear lives only in the success
  branch. Killed by mutation M9.
- **Resend after connecting starts the run.** Through the shipped HTTP handler:
  1st send with no keys → `200 {"setup":"credentials","missing":["generator"],…}`
  and `chats._read(cfg)["chats"] == []` (no thread); after exporting the key,
  the 2nd send creates the thread and proceeds past the check.
- **CLI `build` denial under `LANG=zh_CN.UTF-8`** — one Chinese sentence naming
  the role, for each of the three shapes:
  `请先连接供应商：生成者与审计者都没有凭据（\`crossaudit doctor\` 会提示输入）` /
  `…审计者没有凭据…` / `…生成者没有凭据…`. No `TASK.md`, no new commit
  (`git rev-list --count HEAD` unchanged).
- **Same-vendor jargon is gone from every rendered surface.** `grep` over
  `src/**/*.py`, `page.py` and `denials_zh.ENTRIES` finds no `I1 violated`,
  `违反 I1`, `recovery pools`, `恢复池`. The invariant name survives only in
  docstrings, `config.py:19`, `receipt/build.py:66`, the doctor row *name*
  (`cli/main.py:464`) and test names. Killed by mutation M5 (3 tests).
- **First retry narration.** `resilience.complete` emits exactly one
  `provider recovery` on the first attempt after a route that carried failures,
  and nothing on a healthy route; `_record(success=True)` resets
  `failures` to 0 (`resilience.py:105-107`), so the guard cannot latch on.
  Killed by mutation M1.
- **Wizard default.** `github-toggle` has no `checked`; `openProjectModal`
  calls `configureProjectForm()` → `syncGithubFields()` *after*
  `projectForm.reset()`, so the repository fields are correctly hidden on first
  paint (I checked this specifically — the static markup has no `off` class).
  `restoreProjectDraft` uses `draft.github===true`. Killed by mutation M4.
- **DMG.** `bash -n` clean on both scripts. Note filename byte-identical
  (and NFC-identical) in `build_dmg.sh:211` and `verify_dmg.sh:37`; written to
  `$DMG_ROOT` before `hdiutil create`; `exit 7` is not used elsewhere in the
  verifier (2,3,4,5,6,7 all distinct). Killed by mutations M7 and M11.
- **README.** "First open" precedes `1. Download`; "Uninstall / remove all
  data" lists exactly three locations; Troubleshooting links back to
  `#install`; the Keychain pattern `io.crossaudit.app.provider.<vendor>` (+
  `.backup`) matches `app_keys.APP_SERVICE_PREFIX` / `_service()`.

## Defects

### 1. [High] `console/server.py:1845` and `:1879` — the in-app retry paths skip the setup card and record the setup step as an audit escalation

`/api/escalations` (`action=retry`) and `/api/interrupted` (`action=retry`)
call `start_build`, which calls `preflight()` (`server.py:866` →
`cli/build.py:1187`) → `credential_preflight()`. `setup_needed` is never
consulted. Reproduced with `CROSSAUDIT_APP_MODE=1` and no generator key:

```
setup_needed        : {'setup': 'credentials', 'missing': ['generator'], ...}
start_build (app)   : Denial -> connect a provider first: the generator has no
                      credential (`crossaudit doctor` will ask for it)
  and in Chinese    : 请先连接供应商：生成者没有凭据（`crossaudit doctor` 会提示输入）
```

Two problems. The desktop app has no terminal, so the one instruction the
person is given (`crossaudit doctor`) is unusable and there is no
Settings → Providers button. And `server.py:1848-1853` catches that `Denial`
and writes it into the ledger as

```python
store.escalate(cycle_id,
    f"generator provider failure retry could not start: {exc.reason}",
    task=task, kind="provider")
```

— a missing credential permanently recorded as a *provider failure*
escalation, which is exactly what `setup_needed`'s own docstring
(`server.py:899-906`) says must not happen ("a role without a credential is a
setup step still to do, not an audit event").

**Fix.** In both handlers, check `setup_needed(current)` before calling
`start_build` and send the same `{"setup":"credentials",…}` payload the page
already renders (`page.py:7702`); do not escalate. Equivalently, move the
check into `start_build` and have it return the payload in app mode.

### 2. [Medium] `providers/resilience.py:199-201` and `:241` — the retry narration this slice widens has no Chinese

The event kinds `"provider recovery"` and `"waiting to retry"` appear in
neither `ZH` nor `ZH_PATTERNS` in `console/page.py`. Through the shipped
translator (`tests/harness/extract_zh.py` + node):

```
provider recovery               ->  provider recovery
waiting to retry                ->  waiting to retry
anthropic:claude-x · attempt 2  ->  anthropic:claude-x · attempt 2
```

`grep -rn "供应商恢复|等待重试|正在重试"` over `src/` finds only the *Settings*
label "Advanced provider recovery" → "高级供应商恢复". The pre-existing gap is
not this slice's fault, but S4's entire purpose is to make this event fire on
the person's first retry — i.e. far more often, on healthy-looking turns — so
the change measurably increases the amount of untranslated English a Chinese
user reads in the run card. Shipping S4 without the ZH entries is shipping a
regression in the ZH surface.

**Fix.** Add `"provider recovery":"供应商恢复"` and
`"waiting to retry":"等待重试"` to `ZH`, plus a `ZH_PATTERNS` entry for the
detail (`/^(.+) · attempt (\d+)$/`).

### 3. [Medium] `providers/resilience.py:201` — `vendor:model` in the first paint

`f"{role.vendor}:{role.model} · attempt {attempt}"` renders as
`openai:model-a · attempt 1` in the run events and run card. The owner's
directive is a concise surface with no `provider:model` in the first paint.
S4 both widens when this fires and, at `tests/test_setup_preflight.py:317`,
now *pins* the format:

```python
assert events == [("generator", "provider recovery", "openai:model-a · attempt 1")]
```

**Fix.** Narrate the attempt without the route (`· attempt 1`, or the friendly
model name), and keep `vendor:model` for the collapsed route detail; update the
pin to match.

### 4. [Medium] `config.py:409-412` — three sentences, and a surface the CLI does not have

```
The generator and the auditor must use different providers — independent
review is the core of the protocol. Change one of them in Project controls.
Their routes overlap at anthropic.
```

ZH (`denials_zh.py:1183`) is the same three sentences. The spec caps every new
string at two sentences. Worse, "Project controls" is a console screen
(`page.py:2674`, `page.py:3014`) and this exact sentence is what
`crossaudit build`, `crossaudit run` and `crossaudit doctor` print on stderr,
where no such screen exists — I saw it on my own terminal.

**Fix.** Drop the middle sentence, or make it surface-neutral: "The generator
and the auditor must use different providers — independent review is the core
of the protocol. Their routes overlap at anthropic." Two sentences, true
everywhere it is printed.

### 5. [Low] `cli/build.py:1236-1238` — the auditor-only denial is untested (mutation M2 survived)

Replacing the auditor-only branch with a bare `return` leaves the targeted
suite at **126 passed**. The generator-only sentence is pinned
(`test_setup_preflight.py:181`) and the both-missing one is
(`:244`); the auditor-only one is not, so it could silently stop denying.

**Fix.** Extend `test_outside_the_app_the_check_is_the_preflight_refusal` with
an auditor-only fixture asserting the sentence and `i18n.denial_zh` of it.

### 6. [Low] `cli/build.py:1226` — the human-generator exemption is untested (mutation M6 survived)

`if generator_vendor and generator_vendor.lower() != "human":` →
`if generator_vendor:` leaves the suite at **126 passed**, even though a human
generator is spec case (d) and the build report names it as a deliberate
exemption. (I verified the behaviour by hand — `human` and `Human` both yield
`missing_credentials == []` — so the code is right and only the guard is
missing.)

**Fix.** Add a `generator="human"` case to
`test_the_card_names_whichever_role_is_unconnected`.

### 7. [Low] `console/server.py:932-934` — `say()`'s own guard is unpinned (mutation M12 survived)

Deleting

```python
    blocked = setup_needed(cfg)
    if blocked is not None:
        return blocked
```

leaves the suite at **126 passed**: every test enters through the HTTP handler,
which has its own check. The build report presents this as the guard "for
direct callers"; nothing holds it there.

**Fix.** One assertion: `server_mod.say(cfg, "x")["setup"] == "credentials"`.

### 8. [Low] `console/page.py:888` — the setup card is painted in the escalation colour

`.route.setup{background:var(--escalated-bg,var(--surface-2))}`.
`--escalated-bg` (`page.py:44`, `:100`) is the amber used by
`.status.ESCALATED` and the "needs your decision" surfaces, so a setup step
reads visually as an escalation — contradicting the card's own comment at
`page.py:7704` ("A setup step, not an audit event"). The `var(…, …)` fallback
is dead: the token is defined in both themes.

**Fix.** Use `--surface-2` (or an informational tint) and drop the fallback.

### 9. [Low] `cli/build.py:1227` — an exported `CROSSAUDIT_GENERATOR_PROVIDER` re-arms the card on the credential-free demo

The generator provider is resolved as
`os.environ.get("CROSSAUDIT_GENERATOR_PROVIDER") or cfg.generator_provider`
(mirroring `resilience.py:35`). With that variable exported, the demo project
— whose two roles are both `provider: replay` by construction
(`console/projects.py:1841-1853`, "No API key is read") — reports:

```
(e ) demo project                                 missing=[]              setup_needed=None
(e') demo + CROSSAUDIT_GENERATOR_PROVIDER set     missing=['generator']   card
```

So the one project guaranteed to need no key can be made to demand one. Low
because the variable is a developer override, but the demo is the "always
works" door.

**Fix.** Ignore the env override when `cfg.generator_provider` has
`NEEDS_KEY == False`, or exempt `projects.is_demo_project(cfg)` outright.

### 10. [Low] Copy — quoted and corrected

| where | shipped | correction |
| --- | --- | --- |
| `page.py:3596` | 生成者尚未连接凭据。 | 生成者还没有配置凭据。 — one connects a *provider*; a credential is 配置/填写, not 连接. The CLI ZH already pairs them correctly (`生成者没有凭据`), so the app and the CLI disagree on the collocation. |
| `page.py:3596` | 审计者尚未连接凭据。 | 审计者还没有配置凭据。 |
| `page.py:3597` | 生成者与审计者都尚未连接凭据。 | 生成者与审计者都还没有配置凭据。 |
| `page.py:3093` fragments | `位于每个项目文件夹内（` | `translatePreservingSpace` keeps the source's surrounding spaces, so the rendered ZH is `…内（ cycles/ 中的审计账本…` — a half-width space inside a full-width parenthesis. Wrap the whole `<li>` sentence as one ZH key instead of three fragments. |
| `page.py:3093` list | `<b>Project state</b> — <code>` | the ` — ` text node trims to `—`, which has no ZH entry, while the third row's ` — macOS Keychain items named ` becomes `——`. Two different dashes in one three-row list; make them consistent. |
| `build_dmg.sh:213-218`, `README.md:154` | "macOS may say the app can't be verified. Right-click CrossAudit.app → Open → Open. This happens once." | three sentences, over the spec's two-sentence cap. Acceptable for a standalone note file rather than UI chrome, but recorded: "macOS may say the app can't be verified — right-click CrossAudit.app → Open → Open. This happens once." |

Everything else new reads plain and ≤2 sentences: the three ConfigDenial
sentences, `Connect a provider first` / `Open Settings → Providers`,
`Where CrossAudit keeps data`, `Everything CrossAudit stores lives in three
places; removing them removes every trace.`, and
`Recommended for shared or reviewed work; a single local project is fine to
start.` (ZH `适合共享或需要评审的工作；一开始只用一个本地项目也完全可以。` — natural).

## Mutation log

Targeted suite for every mutation:
`tests/test_setup_preflight.py test_first_launch.py test_resilience.py
test_doctor_parity.py test_product_readiness.py test_projects_ui.py
test_source_independence.py` — **baseline 126 passed in 17.9 s**. Every mutant
reverted with `git checkout -- <file>`; final `git status --porcelain` empty.

| # | file:line | mutation | result |
| --- | --- | --- | --- |
| M1 | `providers/resilience.py:200` | `attempt > 1 or index > 0 or carried > 0` → `attempt > 1 or index > 0` | **killed** — `test_the_first_attempt_after_a_failed_turn_is_narrated` |
| M2 | `cli/build.py:1236` | auditor-only `raise ConfigDenial(...)` → `return` | **SURVIVED** (126 passed) → defect 5 |
| M3 | `console/server.py:907` | drop the `CROSSAUDIT_APP_MODE != "1"` early return | **killed** — `test_outside_the_app_the_check_is_the_preflight_refusal` |
| M4 | `console/page.py:2550` | re-add `checked` to `#github-toggle` | **killed** — `test_two_repositories_is_off_by_default_and_explained` |
| M5 | `config.py:409` | restore `"I1 violated: recovery pools overlap "` | **killed** — 3 tests (incl. `test_first_launch.py::test_role_selection_rejects_a_same_vendor_pair`) |
| M6 | `cli/build.py:1226` | drop `and generator_vendor.lower() != "human"` | **SURVIVED** (126 passed) → defect 6 |
| M7 | `packaging/macos/verify_dmg.sh:35-38` | delete the two-note manifest loop | **killed** — `test_the_dmg_window_says_how_to_open_the_app_in_both_languages` |
| M8 | `console/server.py:1930-1934` | remove the pre-`chats.touch` check in the handler | **killed** — `test_the_app_answers_a_task_without_credentials_with_a_setup_card` |
| M9 | `console/page.py:7706` | add `say.value='';` to the setup branch | **killed** — `test_page_markup_declares_the_setup_card_and_leaves_the_composer_alone` |
| M10 | `cli/build.py:1220-1221` | drop the `NEEDS_KEY` exemption | **killed** — 3 tests |
| M11 | `packaging/macos/build_dmg.sh:211` | rename the note to `How to open.txt` | **killed** — `test_the_dmg_window_says_how_to_open_the_app_in_both_languages` |
| M12 | `console/server.py:932-934` | delete `say()`'s own `setup_needed` guard | **SURVIVED** (126 passed) → defect 7 |
| M13 | `cli/build.py:1187` | remove `credential_preflight(cfg)` from `preflight()` | **killed** — 2 tests |

**10 killed / 13 run.** The three survivors are all in the same shape: a
branch the build report names as a deliberate decision (auditor-only sentence,
human-generator exemption, the direct-caller guard) with no test holding it.
