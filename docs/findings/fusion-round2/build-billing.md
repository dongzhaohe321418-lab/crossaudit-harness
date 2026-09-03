# Build report — token warning & billing slice

Branch `fusion/billing`, worktree `scratchpad/wt-billing`, base `ad1dc0b`.
Final suite: **2555 passed, 2 skipped** in 350 s (foreground, worktree `src` on
`PYTHONPATH`, `crossaudit.__file__` confirmed inside the worktree).

Nothing in this slice reads another application's session files or a vendor's
usage endpoint. Every number comes from the project's own `usage.jsonl` and the
429 responses CrossAudit itself received.

## Commits

| commit | item | what |
| --- | --- | --- |
| `7ee24d6` | B1 | usage attribution (run/cycle/round/chat, `router` role, duration) and per-project price overrides |
| `bc197fc` | B2+B3 backend | threshold alarms as events, rate-limit reset moments parsed from 429 |
| `0a2543f` | B4–B7 | header pill, threshold banner, cost lines, 429 countdown, unpriced visibility, price editor, export + roll-up |
| `88cbf4f` | merge | `fusion/ux-results` (forecast reuses `run_id` attribution) |
| `bef4350` | B8 | pinned tests updated deliberately for the new hooks |
| `f057bf3` | B8 | alarm banner driven under node; clock tests no longer age out |
| `967ab4a` | merge | `fusion/evidence-authority` (tip `bf32c8e`) before the final suite |

Counts against `ad1dc0b`: 22 files, +1945/−85 for the billing work itself;
`usage.py` +671 (all additions in new functions at the end of the module, per
the concurrency note); `tests/test_billing.py` is new, 27 tests, 631 lines.
No push, no `DECISIONS.md` entry.

## B1 — attribution

`record_reply` gained one optional `context` mapping. The audit kernel passes it
through and never learns about billing:

    context = {"run_id", "cycle_id", "round", "chat_id", "duration_ms", "prices"}

Absent or empty fields are **not written**, so a line recorded without context
is byte-for-byte what the ledger always held and `v` stays `1`. Readers tolerate
both shapes side by side. `role` may now be `router` (phase `control`).

Pure aggregators, all taking a plain event list: `per_run`, `per_cycle`,
`per_chat`, `aggregate_by`, `attribution`. Each bucket carries calls, tokens,
input/output/cache split, ≈value, `reported_calls`/`estimated_calls`/
`unpriced_calls`, `first_t`/`last_t`/`duration_ms`.

## B2 — warnings as events

Thresholds are **80 %** and **95 %** of each configured budget (daily tokens,
monthly cost). The budget denominator is the hard limit when one is set, else
the warning line; a period with neither never fires.

State lives beside the ledger in `usage-warnings.json`:

    {"daily": {"period": "2026-09-03", "fired": [80]},
     "monthly": {"period": "2026-09", "fired": []}}

`check_budget_warnings(cfg, now=…)` returns only the alarms raised by *that*
call and persists the rest, so a restart cannot re-fire one; the period key is
the re-arm mechanism — a new day or month simply doesn't match, and both lines
come back armed. `budget_warning_state` reports what is already raised without
firing anything. Nothing is modal: a soft banner in the header shows the
highest line crossed with a Dismiss button; the dismissal key is
`project|budget|period|threshold` in the viewer's `localStorage`, and dismissing
95 % silences the 80 % line beneath it in the same period. The hard-limit park
is unchanged and its card now ends with the reset moment in words.

## B3 — rate-limit resets from 429

`providers/base.rate_limit_reset(headers, body="", *, now=…)` returns an epoch
second or `None`. It understands, taking the **latest** window (the call can only
succeed once the slowest bucket reopens):

- OpenAI `x-ratelimit-reset-requests` / `-tokens` durations: `1s`, `6m0s`,
  `1h2m3s`, `250ms`
- Anthropic `anthropic-ratelimit-*-reset` RFC 3339 stamps
- `Retry-After` as seconds or as an HTTP date
- Codex runtime `usage_limit_reached` bodies (`resets_in_seconds`, `reset_at`)

Unparseable values yield `None` and the surface simply says nothing rather than
guessing. The moment rides the denial into the parked card and the run card and
counts down in the browser.

## B4–B7 — surface

- **Pill** (`#usage-pill`): `Today $0.42 · Month $12.10`, token mode
  `Today 38K · Month 1.2M`, mode remembered per viewer
  (`crossaudit-usage-mode`), class `usage-pill ok|warning|blocked`, click opens
  the Usage view, hidden when the project has no calls yet.
- **Cost on the main surface**: run card `This task: 12K tokens · ≈$0.08`
  (or `· 2 unpriced`); completed generator turn one muted line `≈$0.05 · 42 s`.
  A test asserts these lines contain no run id, cycle id, sha, or
  provider/model string.
- **Unpriced visible**: sentence per model in the Usage view and the Budgets
  pane, naming the model and the snapshot date.
- **Prices override**: `prices: {model: {input, output, cache_write, cache_read}}`
  in `crossaudit.yml` (USD per 1M), editable in Project controls, validated with
  ZH denials, stamped `billing_kind="user_priced"`.
- **Export**: `GET /api/usage/export?format=csv|json&period=day|month|all`,
  token-gated, columns = event fields + attribution + ≈value. The
  Settings→Usage stub sentence is gone; `tests/test_settings_ia.py` was updated
  deliberately.
- **Roll-up**: `GET /api/usage/rollup` and a table of every known project
  (today/month tokens & ≈value, unpriced count, budget state) with a
  cross-project monthly total, plus a monthly report card (top models,
  generator vs auditor share, passed audits).

## New EN/ZH strings

Catalogue pairs: `Open usage`／打开用量 · `Usage warning`／用量预警 ·
`Budget warning`／预算预警 · `Budget`／预算 · `No budget`／未设预算 ·
`Within budget`／预算内 · `Paused at limit`／已达上限暂停 ·
`Resets at midnight`／明天 0:00 重置 · `Display mode`／显示模式 ·
`≈ value`／≈ 价值 · `Calls`／调用次数 · `Input`／输入 · `Output`／输出 ·
`Cache read`／缓存读取 · `Cache write`／缓存写入 · `Unpriced calls`／未计价调用 ·
`Monthly report`／月度报告 · `Top models`／主要模型 ·
`Generator share`／生成者占比 · `Auditor share`／审计者占比 ·
`Passed audits`／通过的审计 · `Model prices`／模型价格 · `Model ID`／模型 ID ·
`＋ Add price`／＋ 添加价格 · `Export CSV`／导出 CSV · `Export JSON`／导出 JSON ·
`Export period`／导出范围 · `Everything`／全部 ·
`Usage across projects`／各项目用量 ·
`This month across projects`／本月全部项目合计 ·
`Open a project to see usage across projects.`／打开一个项目后即可查看各项目的用量。 ·
`No overrides. Models missing from the price snapshot stay unpriced.`／没有覆盖价格。价格快照中缺失的模型保持未计价。 ·
`USD per 1M tokens for models the price snapshot does not carry. Used for this project's estimates only.`／价格快照未收录的模型按每 100 万 token 的美元价格计费。仅用于本项目的估算。 ·
`Usage and budgets are tracked per project, from each project's own local ledger. Nothing is sent anywhere.`／用量与预算按项目跟踪，来自每个项目自己的本地账本。不会发送到任何地方。

Composed at runtime (pattern-translated, both sides tested):
`Today's token budget is N% used`／今日 token 预算已用 N% ·
`This month's cost budget is N% used`／本月费用预算已用 N% ·
`Resets on Oct 1`／10 月 1 日重置 ·
`Provider limit reached · resets in 2 h 10 min`／已达供应商额度上限 · 2 小时 10 分钟后重置 ·
countdown words `now`／现在, `under a minute`／不到 1 分钟, `10 min`／10 分钟 ·
`Today $… · Month $…`／今日 $… · 本月 $… ·
pill accessible name `Usage: today …, this month … · within budget. Open usage`／用量：今日 …，本月 … · 预算内。打开用量 ·
`This task: 12K tokens · ≈$0.08`／本次任务：12K tokens · ≈$0.08 ·
`· 2 unpriced`／· 2 次未计价 ·
`3 calls this month could not be priced (model X has no price in the snapshot of 2026-08-03)`／本月有 3 次调用无法计价（模型 X 在 2026-08-03 的价格快照中没有价格）

Config denials (ZH in `denials_zh.py`): `prices must be a mapping`,
`prices: model ids must be 1 to 160 characters`,
`prices.{} must be a mapping of input, output, cache_write, cache_read`,
`prices.{}.{} must be a non-negative number (USD per 1M tokens)`, plus the four
Project-controls editor denials (`price overrides must be a list of up to 40
rows`, `price override rows must be objects`, `price override model ids contain
unsupported characters`, `price override rates must be non-negative numbers
(USD per 1M tokens)`).

## Tests (B8)

27 in `tests/test_billing.py`: attribution round-trip with old lines beside new;
`router` as a role; aggregators on a fixture; price override used and stamped,
plus the negative twin pinning that without the override the model stays
unpriced and named; config validation with ZH parity; thresholds under a fake
clock (fires once, persists, re-arms at rollover, silent when unconfigured);
monthly alarm on cost naming the first of next month; hard-limit view; four 429
parsing tests per vendor plus the parked-run path; header pill EN/ZH incl.
hidden-when-empty, colours and accessible name; token-mode preference; cost
lines free of identifiers; banner dismissal and re-arm; countdown on the parked
and run cards; Usage view unpriced sentences and monthly report; ZH parity
sweep over the catalogue; price editor persistence; export columns + token
gate; roll-up across two temp projects; forecast reusing run attribution.

Mutation checks run: dropping the override lookup in `_rates` turns the pricing
test red; weakening the banner's `>=` threshold comparison to `==` turns the
dismissal test red.

Deliberately updated pinned tests: `test_settings_ia.py` (the Usage stub is
replaced by export + roll-up), `test_context_condensation_page.py`,
`test_generation_stream_runtime.py`, `test_live_region_locale_timing.py`,
`test_chat_lane.py`, `test_router_and_constitution.py` (new hooks at the end of
the run-card and chat-turn renderers).

## Deviations

1. **The fake clock takes its day from the machine.** The first pass pinned
   `2026-09-02` in the threshold test; because the ledger stamps lines with
   wall-clock time, every recorded call fell outside the period under test as
   soon as the date rolled over, and the test went red on 2026-09-03. Only the
   hour is the test's now; the reset wording is checked against the test's own
   month table, with the September and December wordings kept as pure
   `reset_moments` calls so the calendar arithmetic is still pinned.
2. **`dismissUsageBanner()` is a named function.** The dismiss behaviour was an
   anonymous `onclick`, which the node harness extracts by signature and so
   could not reach. Naming it lets the test drive the shipped code rather than a
   copy of it; the handler assignment is unchanged.
3. **No new ledger version.** B1 could have bumped `v`, but since absent
   attribution fields are simply not written, old and new lines are the same
   shape and `v` stays `1` — a reader that ignores unknown keys needs no
   migration.
4. **AgentIsland's quota-window polling is not adopted.** It reads vendor OAuth
   usage endpoints and other apps' session files; CrossAudit derives its reset
   moments only from 429 responses it received itself. That is the one place
   where this slice is deliberately less informative than the reference.

---

# Review fixes

Independent review (`review-billing.md`) returned **NEEDS CHANGES** on twelve
defects. All twelve are addressed. Merged `fusion/evidence-authority` (tip
`fe6660e`, carrying the latency merge) as `470b6b2` — clean, with the narration
hooks and the usage context both kept in `cli/build.py`, `cli/main.py` and
`cli/talk.py`. Fixes are one commit, `4d36fe6`.

Final suite: **2580 passed, 2 skipped** in 353 s (foreground, worktree `src` on
`PYTHONPATH`, `crossaudit.__file__` confirmed inside the worktree).
`tests/test_billing.py`: 27 → **35 tests**. 15 mutations run, **0 survived**.

## 1 + 2 — attribution, pinned end-to-end, and the bug behind it

The reviewer's central finding was right and its cause was structural:
`test_billing.py` tested `record_reply` and the aggregators in isolation and
never drove a round, so all six call sites that feed them were unpinned.

A new end-to-end section drives the real `build_mod.run_loop` with the
providers stubbed at the wire (`providers/resilience.complete`) — nothing
between the loop and `record_reply` is faked, so the attribution the ledger
ends up with is the attribution the shipped call sites pass. One round, PASS,
two lines, the reviewer's own numbers (150 + 220 = 370):

| test | pins |
| --- | --- |
| `test_a_real_round_attributes_every_line_it_writes` | `run_id`, `cycle_id`, `round`, `chat_id`, role and `duration_ms` on **every** line |
| `test_a_single_cycle_run_costs_the_same_by_run_by_cycle_and_by_chat` | `per_run == per_cycle == per_chat == 370` |
| `test_the_projects_price_overrides_reach_the_ledger_from_the_loop` | `prices:` travelling from config to the ledger |
| `test_the_console_bills_its_routing_call_to_the_router_and_the_chat` | `role="router"` + `chat_id` on the console's routing call |
| `test_the_cli_bills_its_routing_call_to_the_router` | `role="router"` on `cmd_talk`'s routing call |

**Defect 2, the live bug.** A cycle is minted by the audit, and the audit judges
a generation that has already happened — so the first generator call of every
cycle was written before the cycle it belongs to existed. `per_cycle`
under-counted every cycle by exactly that call while `per_run` was right; a
single-cycle run disagreed with itself (370 vs 220).

`usage.attribute_round(root, state_dir, run_id=, round_no=, cycle_id=)` stamps
the cycle onto the round's lines that lack one. It rewrites **in place** on one
descriptor under the ledger's own advisory lock (`seek(0)` / write /
`ftruncate`), never temp-and-rename: an appender opens the path fresh and
appends under the same lock with `O_APPEND`, so it can neither lose a line nor
read a half-written one. The loop calls it through `adopt_cycle()` at both
places the audit names a cycle (the verdict path and the provider-park path),
which also carries the id forward for the rounds still to come.

## 3–12 — the rest

| # | defect | fix |
| --- | --- | --- |
| 3 | ZH countdown gained a stray space on exact hours (`.trim()` bound to the minutes ternary) | the join is trimmed, not the ternary |
| 4 | "resets in now" / "现在后重置" when the moment had passed | `resetSentence` has three shapes: counting down, `resets now` / `现在重置`, and `resets soon` / `稍后重置` when no usable moment was given |
| 5 | the pill said `$0.00` for a wholly unpriced project | `usageFigure` returns `unpriced` / `未计价` when the window has unpriced calls and no provable value; a partly-priced window still shows the money it can prove, and a real zero still reads `$0.00` |
| 6 | `Retry-After: inf` reached the wire as `Infinity`, which is not JSON | `rate_limit_reset` refuses non-finite and negative values, anything past a 7-day horizon (`MAX_RESET_HORIZON`), and long-stale stamps (`MAX_RESET_SLACK`, 1 h) |
| 7 | a price override silently priced a proxy origin | see below |
| 8 | `project_rollup(now=…)` was inert | `summary(cfg, now=now)`, pinned under a fake clock |
| 9 | the export period filter was unpinned | the fixture spans two months; day 1 / month 2 / all 3, over both the API and `export_rows` |
| 10 | `usage.monthly_report` was dead code | deleted (28 lines); the JS `monthlyReport` is the one that renders |
| 11 | "Passed audits" was all-time under a "this month" header | cycles filtered by `updated_at` falling in the reported month |
| 12 | `assert A and B or C` could not fail | split into three asserts |

**Defect 7, decided deliberately.** An override now prices only calls that went
to the vendor's own endpoint, unless the project declares `trust_origin: true`
for that model. The reason is the fail-closed one: a monthly cost *limit* pauses
the loop the moment anything is unpriced, and a user-typed rate for a relay
whose real billing CrossAudit cannot see must not reopen that limit by accident.
The flag is per model, validated in `config.py`, refused in Chinese, editable as
a checkbox per row in the Budgets pane, and stamped `user_priced` when it
applies. `price_override(..., official=False)` is the seam, tested both ways.

## New EN/ZH strings

`Trust this endpoint`／信任此端点 ·
`A price applies to calls that went to the vendor itself. Tick "trust this
endpoint" to price a relay or gateway too — CrossAudit cannot see what such a
route really bills, so a monthly cost limit would then rest on your figure.`／价格仅适用于直接发往供应商的调用。勾选“信任此端点”后，中转或网关的调用也会计价——CrossAudit 无法看到这类线路的真实账单，届时每月费用上限将以你填写的数字为准。

Composed at runtime: `Provider limit reached · resets now`／已达供应商额度上限 · 现在重置 ·
`Provider limit reached · resets soon`／已达供应商额度上限 · 稍后重置 ·
`Today unpriced · Month unpriced`／今日 未计价 · 本月 未计价

Config denials (ZH in `denials_zh.py`):
`prices.{} must be a mapping of input, output, cache_write, cache_read, trust_origin`
(the existing denial, widened) ·
`prices.{}.trust_origin must be true or false (it declares that this project knows what a non-vendor endpoint charges)` ·
`price override trust_origin must be true or false`

## Mutation log (15 run, 0 survived)

The six that survived the review — M11 CLI router role, M12 console router role,
M13 auditor `chat_id`, M14 auditor `cycle_id`/`round`, M15 chat-lane `chat_id`,
M16 `prices:` to the ledger — are all **RED** now. Nine more were run over the
same 118-test scope and are all RED: the cycle backfill removed, the pill's
unpriced fallback removed, a non-finite reset allowed through, the ZH stray
space restored, `resets now` removed, the override's origin gate removed,
"Passed audits" returned to all-time, `_in_period → True`, and
`summary(cfg, now=now)` → `summary(cfg)`.

## Deviations from the reviewer's suggested fixes

1. **Defect 6 rejects rather than clamps.** The reviewer suggested clamping an
   absurd moment to `now + 7 days`; the lead's ruling was to reject. Rejecting
   is the honest one — a clamped number is a countdown to a moment no vendor
   named — so an unusable header now yields `None`, and the card says "resets
   soon" instead of a figure.
2. **`providerResetLine` now renders for a rate-limited pause with no moment.**
   Previously it returned an empty string; the "soon" wording needs somewhere to
   land. It stays silent for a non-rate-limited provider pause.
3. **Defect 4's wording.** The reviewer proposed "you can retry now"; the lead
   specified "resets now" / "现在重置", which is what shipped — it keeps the
   sentence parallel with the two other shapes.
4. **Observations 1–4 in the review are not addressed.** They were explicitly
   not defects (SSE snapshot size, the always-zero `percent` on
   `budget_warning_state`'s rows, the absolute `root` path in the roll-up JSON,
   and `rate_limit_reset_at` being set when *any* route was rate-limited while
   `rate_limited` requires all). The last is the one worth a follow-up: a mixed
   429 + 500 exhaustion can still say "Provider limit reached".

---

# Closure audit 2 fix

Closure audit 2 (`review-closure2.md`) left one user-visible row in this slice:
observation 4, which the first review pass and I had both judged a follow-up.
The auditor was right that it is user-visible, and it is fixed. Merged
`fusion/evidence-authority` (tip `da71b9d`) as `205e954` — clean; fix is
`e7887b5`.

Final suite: **2600 passed, 2 skipped** in 364 s (foreground, worktree `src` on
`PYTHONPATH`, `crossaudit.__file__` confirmed inside the worktree).
`tests/test_billing.py`: 35 → **36 tests**. 3 mutations run, 0 survived.

## The defect

`resilience.py` set `rate_limit_reset_at` from **any** failure carrying one but
`rate_limited` only when **all** routes were rate-limited, and
`providerResetLine` branched on the moment alone. So a mixed exhaustion — one
route 429, the next 500 — painted "Provider limit reached · resets in 1 h
59 min" on the always-visible run card for a run that a provider outage had
stopped. The person waits out a window that was never what blocked them: exactly
the "needless error" the owner's directive rules out.

## The fix, at both ends

**Source.** The roll-up now decides once whether the exhaustion *is* a rate
limit: every route hit one, **or** the last route — the one that actually ended
the loop — did. Only then are `rate_limited` and `rate_limit_reset_at`
published, and the moment is the latest window among the **rate-limited**
routes, not among all of them (nothing can succeed before that one reopens).
Flag and moment can no longer disagree.

**Surface.** `providerResetLine` and `appendResolutionReset` read
`w.rate_limited`, not `w.reset_at`. Belt and braces: even if some other path
ever stamps a moment onto a non-quota park, the sentence stays away. A mixed
park renders `''` for the run-card line and leaves the parked card's generic
provider-failure sentence untouched, in both languages.

## Tests

- `test_a_mixed_exhaustion_is_a_provider_outage_not_a_quota_wall` — drives the
  real `resilience.complete` over two routes in three orders: 429→500 publishes
  neither key; 500→429 (the limit is decisive) publishes both; 429→429 publishes
  both.
- The countdown render test gains a mixed park in **EN and ZH**: the line, the
  run-card line and the parked card are all free of "Provider limit reached" /
  "已达供应商额度上限".

Mutations, all **RED**: `providerResetLine` gating on the moment again;
`appendResolutionReset` branching on the moment again; `resilience` rolling up a
reset from any failure again.

## The `[i18n]` stdout row is not this slice's

Checked as asked. The audit attributes it to **i18n (1st closure #7)**, and
`git log -L` on `_report_untranslated` puts it in `ac9715e` ("Let a person set up
CrossAudit in Chinese, start to finish") — the i18n slice, not billing. It is
also pinned to stdout by that slice's own test
(`tests/test_denial_strings_are_legible.py:551` asserts the notice is in `out`),
so moving it to stderr means editing their test as well. Left for its owner
rather than taken as a drive-by; the one-line change is
`print(..., file=sys.stderr)` at `cli/main.py:1523` plus that pin.

The audit's other two open rows (the D141 DECISIONS paragraph, the
`EVIDENCE_AUTHORITY.md` continuation-round sentence) belong to other slices, and
its item 2 for READY — pinning the `collapseClockRows` call site in `runCard` —
is the latency slice's.
