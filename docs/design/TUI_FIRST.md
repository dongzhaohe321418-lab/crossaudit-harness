# TUI first — the terminal is the product; the app leaves the main line

Owner decision, 2026-10-23. This document is the specification the
`feat/tui-first` branch is built to. It supersedes the "60-second tour" that
begins with a DMG; it does not change the audit protocol (DESIGN.md), the
invariants (AGENTS.md §1), or any receipt or ledger format.

## 1. Why

What this product proves is in the audit core: deterministic checks, the git
ledger, receipts, `verify`. Every one of the 38 README sentences the claims
harness can test (`benchmarks/claims/`) is kept by the **command line**; the
native app is the one surface no harness can reach, the one with the largest
security boundary (a bearer token that authorises local code execution, a
WebKit shell, Keychain, an ad-hoc-signed DMG), the most maintenance (a 10,000
line page string, Swift, PyInstaller, notarisation that never happened), and
no measured users. The users the evidence points at — scientists whose
pipelines run on Linux machines and clusters, and people who already live in
Claude Code or Codex — are in a terminal. A terminal surface can be tested
under a pseudo-terminal by the same harness; an app cannot.

So: the CLI and a terminal UI are the product. The browser console stays as an
optional local viewer for rich content (reports, diffs, previews), started by
`crossaudit console`, with no native shell around it. The macOS app and DMG
leave the main line: the code stays, nothing is deleted, but it is not built,
not released, and not in the README's front door until a measured user needs
it. Which surface people actually use is recorded (§5) so that decision can
be revisited with data.

## 2. The surface: `crossaudit tui`

One new verb. It is the loop, live, in the terminal, **and** the place where
the person acts on it — through the same engine verbs the CLI already
exposes (`build`'s `run_loop`, `resolve`'s ruling path, `verify`, `talk`'s
lanes), never a second implementation of any of them. `crossaudit watch`
stays as it is (the read-only viewfinder) and its help text points at `tui`.

### 2.1 Rendering model (stdlib only, no curses)

- A **pure renderer**: `render(frame: dict, width: int, height: int) -> str`
  turns plain data into the text of one screen. It is tested without a
  terminal (byte-exact frames for fixed inputs, widths 60/80/120, a narrow
  terminal truncating gracefully, Chinese width-2 characters measured with
  `unicodedata.east_asian_width` as `tui.py` already does).
- A thin **loop** draws frames with ANSI (home, clear-to-end-of-screen), reads
  keys with the existing `tui.read_key()` in raw mode, and refreshes on a
  timer (2 s, like `watch`) or on an event. Colour follows `tui.coloured()`;
  glyphs fall back through `tui.glyph()`; the whole thing degrades to plain
  ASCII under a strict GBK stream like the wizard does.
- **Not a TTY** (a script, CI, the harness): `crossaudit tui --once` prints
  exactly one frame and exits 0; `crossaudit tui` without a TTY does the same
  and says so on stderr. This is what makes the surface testable. The one
  frame has the newest cycle selected and expanded, so a reader (or the
  harness) sees that cycle's findings and tier words without pressing a key;
  at a terminal the same first frame is drawn, and keys move on from it.
- `--json` is not added here; `status --json` and `/api/state` already carry
  the data.

### 2.2 What the screen shows (all from existing projections)

The data comes from `console.server.snapshot(cfg)` (cycles, findings,
escalations, usage, progress, chats) and `console.overview` (`read_cycles`,
`escalations`, `receipt_integrity`, `annotate_findings`), plus `rulings.by_cycle`
and `watch.gather` for the commit list. Nothing is computed twice; if the
projection lacks a field the TUI needs, the field is added to the projection,
not derived in the TUI.

1. **Header**: project title, generator and auditor (vendor:model), the
   rules commit (short), admission tier, usage today / this month as the
   `≈ API value` the console shows, run state (idle / running phase N of M /
   waiting for you).
2. **Activity** (the top pane while a run is live): the current run's phases
   and rounds as `build` narrates them — routing, preparing, generating
   (streamed draft summary line), checks (per check), audit, repair guard,
   verdict — with elapsed time and running cost; the 8 s silence heartbeat.
3. **Cycles**: one row per cycle, newest first: id (short), status as
   `status` prints it (PASSED, BLOCKED, ESCALATED, CLOSED, CONSUMED, DCL_ONLY),
   round/max, verdict, sha, any ruling (kind, when). The selected row expands
   to its **findings**: severity, rule id, artifact, observation, and the tier
   word the console shows ("verified by a check" / "raised by the auditor"),
   plus the receipt line (BINDINGS VERIFIED / SIGNED / ADMISSION READY) when
   a receipt exists.
4. **Decision card** (replaces the cycles pane while a cycle waits for a
   person): the cause in plain words, the round limit and verdict history,
   remaining blockers, affected files, and the two actions the README
   documents: **Revise and continue** (`r`) and **Stop this task** (`c`),
   each asking for the written reason with `tui.text` and recording it
   through the D172 ruling path (`cycles/rulings.jsonl`, committed). A third
   key, `l` (later), leaves it pending and says the project stays paused.
5. **Help bar**: the keys. `↑/↓` or `j/k` select, `Enter` expand, `n` new
   task, `v` verify selected receipt (dry run, prints the four lines in a
   panel), `a` admit (asks `tui.confirm`, then `verify --admit`), `x` stop
   the running task, `o` open the console (prints the tokenized URL; opens a
   browser only at a TTY, the D172 rule), `?` help, `q` quit.
6. **New task** (`n`): `tui.text` for the task, then `run_loop` in a thread
   with an `on_event` that feeds the activity pane exactly as `cmd_build`'s
   does (reuse its event handling by extracting it into a function both
   call, if it is inline today). Exit codes do not apply inside the TUI; the
   outcome line is the same sentence `build` prints.

Every string shown to a person exists in English and Chinese
(`cli/i18n.py`, the `t()` table), including the help bar, and the
`tests/test_denial_strings_are_legible.py` / `test_cli_i18n.py` guards keep
passing. The language follows the resolved CLI language as every other
command does.

### 2.3 What it never does

It never reads a provider key, never writes `state.json` directly, never
mints a cycle id, never changes the rules, never touches the ledger except
through the engine verbs above, and never runs a model call that the same
`build`/`talk` invocation would not run. A key the help bar does not list
does nothing.

## 3. Install, front door, README

- The README's install is `pip install` (and `pipx` for those who have it);
  the 60-second tour is `crossaudit init my-project --no-console …` →
  `crossaudit build "…"` → `crossaudit tui` → `crossaudit verify …`. The
  desktop tour, the DMG download, the macOS badge and the "Native app"
  bullets move to one short section near the end, "The native macOS app
  (not on the main line)", that says what it is, that it is not built or
  released from this branch, and where the code lives.
- `crossaudit` with no arguments keeps printing the front door; the front
  door's first suggestion becomes `crossaudit tui` when a project exists.
- The command reference gains `tui`; the "Watch the loop live" step names
  `tui` first and `console` as the optional viewer.
- `docs/RELEASE_CHECKLIST.md`: the DMG steps become an optional appendix;
  `scripts/release_gate.sh` runs the Swift type-check only when `swiftc` is
  present and says so. `packaging/` is untouched.
- SECURITY.md: the "Desktop trust boundary" paragraph is prefixed with one
  sentence saying the app is not on the main line and the paragraph
  describes it for whoever builds it; the console paragraph stays as D170
  wrote it.
- One decision record, **D175**, states the owner's decision and this
  document; CHANGELOG `## Unreleased` gets the user-visible lines.

## 4. Keys and credentials without the app

Nothing changes: the CLI and the console already read keys from the
environment or the mode-600 keys file (`crossaudit init` writes it at a
terminal; non-interactive `init` names the variables, D172). The Keychain
path belongs to the app and is not referenced by the main line.

## 5. Measuring which surface people use

The usage ledger (`.crossaudit/usage.jsonl`) already attributes every
completion to task, cycle, round, chat and role. Each row gains one
additive field, `surface`, with one of `cli` (`build`, `talk`, `audit`,
`run`), `tui`, `console` (the server's own calls: say, chat, routing), `app`
(the native core process; the value the frozen app would write). It is set
at the entry point, not guessed from the call stack; rows without it (older
ledgers) read as `unknown`. `usage.summary` gains a `by_surface` breakdown
(calls and API value), shown by `crossaudit --json status` and in the TUI
header's usage line as a tooltip-free "cli 12 · tui 3 · console 0".
That is the number the 90-day decision about the app is made on.

## 6. Acceptance (what the claims harness will check)

New rows in `benchmarks/claims/CLAIMS.md`:

- C37 `crossaudit tui --once` on a project with a PASSED and an ESCALATED
  cycle prints one frame naming both cycles, their statuses and the
  findings' tier words; exit 0; no provider request; no browser.
- C38 under a pseudo-terminal, `tui` draws, `↓`/`Enter` expands a cycle to
  its findings, `q` exits 0 and restores the terminal (no raw mode left
  behind: `stty` state identical before and after).
- C39 under a pseudo-terminal, the decision card's `c` with a typed reason
  records a ruling that `git log` and `status` show (the C25 criterion),
  and `r` reopens.
- C40 the README's 60-second tour, run literally from a fresh venv, ends
  with `verify` printing BINDINGS VERIFIED.
- C41 `usage.jsonl` rows written by `build` carry `surface: cli` and rows
  written by the TUI's `n` carry `surface: tui`; `--json status` shows
  `by_surface`.
- C32 (the DMG) moves to the "not on the main line" section of CLAIMS.md
  with the sentence the README now makes.
