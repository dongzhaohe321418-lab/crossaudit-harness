# Build report — "setup & preflight" UX slice

Branch `fusion/ux-setup` from `ad1dc0b`, worktree
`/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-ux-setup`.
Not pushed. No DECISIONS.md entries.

## Commits (in order)

| sha | item | files |
| --- | --- | --- |
| b56bd16 | S1 Gatekeeper + uninstall | README.md, packaging/macos/build_dmg.sh, packaging/macos/verify_dmg.sh, console/page.py (Security & privacy pane + ZH) |
| 2b7cd71 | S2 credential preflight | cli/build.py, console/server.py, cli/denials_zh.py, console/page.py (setup card CSS/JS/ZH) |
| 0132d14 | S3 same-vendor sentence | config.py, cli/denials_zh.py, tests/test_first_launch.py (pin updated) |
| 6ea35dd | S4 first retry narrated | providers/resilience.py |
| 4241e51 | S5 wizard default | console/page.py (toggle, draft restore, ZH) |
| cce8bc5 | S6 tests | tests/test_setup_preflight.py (14 tests) |

## What each item does

**S1.** `build_dmg.sh` writes `如何打开 · How to open.txt` beside the app in the DMG
root (EN + ZH). `verify_dmg.sh` now has a small manifest loop that refuses a DMG
missing either note (`如何打开 · How to open.txt`, `About the crossaudit
command.txt`, exit 7). README: a "First open" callout is the first thing under
`### macOS application`, the ad-hoc-signing paragraph moved up into it, the
Troubleshooting entry now says right-click → Open → Open and points back to
Install, and a new `### Uninstall / remove all data` table names the three
locations (app support dir / `CROSSAUDIT_APP_SUPPORT`, project `.crossaudit/`
with the note that `cycles/` is part of the repo, Keychain items
`io.crossaudit.app.provider.<vendor>` + `.backup`). Settings → Security &
privacy gained a text-only "Where CrossAudit keeps data" list of the same three.

**S2.** `cli/build.py`: `missing_credentials(cfg) -> ["generator"|"auditor"...]`
(presence only: role key_env non-empty OR `app_keys.status()[vendor]["configured"]`;
`NEEDS_KEY=False` providers — ChatGPT sign-in, replay/demo — and a human
generator exempt) and `credential_preflight(cfg)` raising `ConfigDenial`;
`preflight()` calls it after the heterogeneity check, so `crossaudit build`
refuses before `resolve_task` commits TASK.md. `console/server.py`:
`setup_needed(cfg)` (app mode only, `CROSSAUDIT_APP_MODE=1`) returns
`{"setup":"credentials","missing":[...],"action":"providers","asked":false,"lane":"setup"}`;
the `/api/say` handler checks it before `chats.touch` (no thread created) and
`say()` checks it at its top for direct callers. `page.py`: `setupCardMarkup()`
renders the card into the route strip (`.route.setup`), the single primary
button calls `openSettings('providers')`, and the composer text is not cleared.
Mid-run auth failures still go through the existing escalation path.

**S3.** `config.heterogeneity()` returns the plain sentence with the overlap as a
short last clause; the undeclared-generator branch also lost "I1". All callers
(cli build/run/doctor, console projects.py, auditor/run.py) pass it through
unchanged, so every surface is fixed at the source. "I1" stays in the docstring,
`add("heterogeneity (I1)", …)` doctor row *name*, and test names/comments.

**S4.** `resilience.complete()` reads the route's recorded `failures` before the
attempt loop; the "provider recovery · vendor:model · attempt N" event now also
fires on attempt 1 of the primary when the route carries failures from an
earlier call (the person's first retry). A healthy first attempt stays silent
(no "recovery" noise on every turn). `waiting to retry` was already unguarded.

**S5.** `id="github-toggle"` no longer `checked`; `<small>` is the requested one
line; `restoreProjectDraft` uses `draft.github===true` so an old draft without
the field stays local.

## New EN/ZH strings

| EN | ZH | where |
| --- | --- | --- |
| How to open CrossAudit / macOS may say the app can't be verified. Right-click CrossAudit.app → Open → Open. This happens once. | 如何打开 CrossAudit / macOS 可能提示无法验证此应用。右键点击 CrossAudit.app → 打开 → 打开。只需这样做一次。 | DMG note |
| Where CrossAudit keeps data | CrossAudit 的数据存放位置 | Settings pane |
| Everything CrossAudit stores lives in three places; removing them removes every trace. | CrossAudit 保存的所有内容只在三个位置；删除它们即可清除全部痕迹。 | Settings pane |
| App and workspace / Project state / API keys | 应用与工作区 / 项目状态 / API 密钥 | Settings pane |
| inside each project folder (the audit ledger in … is part of the repository) | 位于每个项目文件夹内（… 中的审计账本属于仓库的一部分） | Settings pane |
| — macOS Keychain items named … ; remove them under Providers | —— macOS 钥匙串条目，名为 … ；可在“供应商”中移除 | Settings pane |
| Connect a provider first | 请先连接供应商 | setup card title |
| The generator has no credential yet. | 生成者尚未连接凭据。 | setup card |
| The auditor has no credential yet. | 审计者尚未连接凭据。 | setup card |
| Neither the generator nor the auditor has a credential yet. | 生成者与审计者都尚未连接凭据。 | setup card |
| Open Settings → Providers | 打开设置 → 供应商 | setup card action |
| connect a provider first: the generator has no credential (`crossaudit doctor` will ask for it) | 请先连接供应商：生成者没有凭据（`crossaudit doctor` 会提示输入） | ConfigDenial |
| connect a provider first: the auditor has no credential (`crossaudit doctor` will ask for it) | 请先连接供应商：审计者没有凭据（`crossaudit doctor` 会提示输入） | ConfigDenial |
| connect a provider first: neither the generator nor the auditor has a credential (`crossaudit doctor` will ask for them) | 请先连接供应商：生成者与审计者都没有凭据（`crossaudit doctor` 会提示输入） | ConfigDenial |
| The generator and the auditor must use different providers — independent review is the core of the protocol. Change one of them in Project controls. Their routes overlap at {}. | 生成者与审计者必须使用不同的供应商——独立审查是协议的核心。请在项目控制里更改其中一个。两者的路由在 {} 处重叠。 | heterogeneity() |
| the generator's provider is not declared, so independent review cannot be asserted; choose one in Project controls | 未声明生成者的供应商，因此无法断言独立审查；请在项目控制里选择一个 | heterogeneity() |
| Recommended for shared or reviewed work; a single local project is fine to start. | 适合共享或需要评审的工作；一开始只用一个本地项目也完全可以。 | wizard step 3 |

Removed: "I1 violated: …" / "违反 I1：…", "generator vendor not declared: I1 cannot be asserted from config", and the wizard's old `<small>` ("The work repository holds deliverables…") + its ZH entry (no longer rendered anywhere).

## Deviations / judgement calls

- **`crossaudit run` not gated.** `cmd_run` has a deliberate offline (DCL-only)
  mode when the auditor key is absent (`offline = key_needed and not key_present`,
  README "DCL_ONLY"); a denial there would remove a documented feature and `run`
  needs no generator credential. The credential check lives in `preflight()`,
  which `build` and the console's `start_build` call.
- **App check gates every send, not only generator-lane sends.** Routing itself
  calls the auditor (`route_addressed` → `complete`), so with no auditor key
  every message failed anyway; with the generator missing, chat/query lanes
  would technically work but the directive was "connect both first".
- **S4 interpretation.** Attempt 2 on the primary was already narrated
  ("waiting to retry" is unguarded and "provider recovery · attempt 2" passed
  the guard). The silent case was the *next call's* attempt 1 after a failed
  call. Rather than drop the guard (which would label every healthy turn
  "provider recovery"), it is narrowed with the route's carried failure count.
  No existing test pinned the guard; the new test names the mutation.
- **README stays English-only** (`test_the_readme_is_entirely_english`), so the
  ZH copy lives in the DMG note and the README refers to it as "the `How to
  open` note". The `verify_dmg.sh` check is a two-entry `for` loop rather than a
  separate manifest file, since the verifier had no manifest to extend.
- **S3 second clause keeps the word "overlap"** so `test_resilience.py:105`
  (`"overlap" in why and "google" in why`) stays green without editing it.
- `test_first_launch.py::test_role_selection_rejects_a_same_vendor_pair` pinned
  `"I1" in reason`; updated to assert the plain sentence and `"I1" not in reason`.
- One new test was renamed after the guard-name meta-test flagged it (a
  markup-only body must not claim "renders").

## Counts

- Full suite, foreground, at HEAD cce8bc5 (`crossaudit.__file__` confirmed
  inside the worktree): **2484 passed, 2 skipped, 1 warning, 315 s — green.**
  (An earlier full run before the test rename was 2483 passed / 1 failed on the
  guard-name meta-test only.)
- New tests: 14 in `tests/test_setup_preflight.py`; 1 pin updated in
  `tests/test_first_launch.py`.
- Source changed: 9 files, 6 commits; page.py hunks kept to the Security pane,
  the ZH map, the wizard step-3 toggle, `restoreProjectDraft`, and the
  `form.onsubmit` response branch (outside the run-card and chat-turn regions).

## Review fixes (review-ux-setup.md, 10 items) — on `fusion/ux-setup` after merging `fusion/evidence-authority` (dc524f3, clean merge)

| sha | what |
| --- | --- |
| fd88ad4 | source fixes for items 1, 2, 3, 4, 8, 9, 10 |
| 5fd2313 | tests for items 1, 5, 6, 7, 9 and the emitter-driven ZH check (2, 3); pins updated |
| e331e69 | merge fallout only: `test_chat_lane.py` fakes and `test_perceived_latency.py` factory accept the billing/latency slices' extra positional arguments (they failed on the merged tip before any of my edits) |

1. **Every in-app build entry point → setup card.** `/api/escalation retry_provider` checks `setup_needed(current)` before `resolve_escalation`/`start_build` and returns the card; nothing is written to the ledger (cycle stays ESCALATED, byte-identical). `/api/interrupted retry` likewise. `start_build` in `say()`/intake already sat behind the guard. Page: both retry handlers now read the response and call `showSetupCard()`. Structural test enumerates every `start_build(` in the handler and requires `setup_needed(current)` on its path.
2. **ZH through the emitters.** `provider_recovery` is now a phase kind, so the run card gets `text_i18n` from `progress.phase_i18n`; five patterns added to `PHASE_PATTERNS_ZH` and to the page's `ZH_PATTERNS`. Test drives `resilience.complete` through the states that reach each `on_event(` call site (count of sentence shapes == call sites + 1, for the two-way credential line) and checks each sentence at both seams; the two seams must agree.
3. **Words on the first paint.** New emitter sentences (EN / ZH): `Retrying the generator's provider · attempt 2` / `正在重试生成者的供应商 · 第 2 次`; `Waiting to retry the generator's provider · 2.0 s` / `等待重试生成者的供应商 · 2.0 秒`; `Connected to the generator's backup provider` / `已连接生成者的备用供应商`; `The generator's backup provider is unavailable` / `生成者的备用供应商不可用`; `The generator's provider has no credential` / `生成者的供应商没有凭据` (auditor forms likewise). `vendor:model` lives in the event detail only; `progress.concise_detail` drops a route-only detail for `provider_recovery`. Old pin in `test_setup_preflight.py` and `test_resilience.py:53` updated.
4. **Same-vendor, two sentences, per surface.** `heterogeneity(cfg, surface="cli"|"console")`; `preflight(cfg, surface)`; the console's `start_build` and `projects` runtime update pass `"console"`. CLI: `… Change one in crossaudit.yml; their routes overlap at openai.` / `…请在 crossaudit.yml 里更改其中一个；两者的路由在 openai 处重叠。` Console: `… Change one in Project controls; …` / `…请在项目控制里更改其中一个；…`. The undeclared-generator sentence got the same split. `test_first_launch` pin updated (no "Project controls" in the CLI form, ≤2 sentences).
5–7. Pinned: auditor-only denial + its ZH (via `preflight`), `human`/`Human` generator exemption, `say()`'s own guard with routing stubbed to fail.
8. `.route.setup{background:var(--accent-bg);border:1px solid var(--line)}` — no escalation token; asserted.
9. A configured keyless generator provider (`replay`) wins over `CROSSAUDIT_GENERATOR_PROVIDER`; a keyed configured provider still honours the override. Test covers demo + override + keyed project.
10. Copy: `生成者还没有配置凭据。` / `审计者还没有配置凭据。` / `生成者与审计者都还没有配置凭据。`; data-location rows are one text node each with the dash from CSS (`#data-locations .data-where:before`), ZH keys `每个项目文件夹内的 .crossaudit/（cycles/ 中的审计账本属于仓库的一部分）` and `macOS 钥匙串条目，名为 io.crossaudit.app.provider.<vendor>；可在“供应商”中移除`; DMG note and README: `macOS may say the app can't be verified — right-click CrossAudit.app → Open → Open. This happens once.`

Not changed, on purpose: the latency test's *sample* step with the old `provider recovery` / `anthropic:… · attempt 2` shape stays as its "older events" fixture (journals written before this change still render). `crossaudit run` remains ungated (deliberate DCL-only offline mode).

**Full suite, foreground, at e331e69: 2579 passed, 2 skipped, 1 warning, 351 s — green.** New tests in `tests/test_setup_preflight.py`: 21 (was 14).
