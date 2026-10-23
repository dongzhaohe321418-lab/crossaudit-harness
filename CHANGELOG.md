# Changelog

All notable changes to CrossAudit are recorded here. Versions follow the
`MAJOR.MINOR.PATCH` scheme; the source on `main` is authoritative.

## Unreleased

### Added
- **`crossaudit tui`: the loop, live, in the terminal, and the place to act on it.**
  It shows the project's cycles with their status, findings and the tier of each
  finding, a decision card when a cycle waits for you (**Revise and continue** or
  **Stop this task**, each with a written reason recorded as the same committed
  ruling `crossaudit resolve` records), and keys to start a task, verify or admit a
  receipt, stop a run, or open the console. It acts only through the existing engine
  verbs (`build`'s loop, the ruling path, `verify`). Without a terminal,
  `crossaudit tui --once` prints one frame and exits 0. `crossaudit watch` stays the
  read-only view (D175).
- **The usage ledger records which surface each call came from.** Each
  `.crossaudit/usage.jsonl` row carries `surface` (`cli`, `tui`, `console` or `app`;
  older rows read as `unknown`), and `crossaudit --json status` shows a `by_surface`
  breakdown of calls and API value (D175).
- `science-ai4s` check profile (opt-in; `science` is unchanged): numeric validity,
  constitution-declared value ranges, derivations recomputed from committed
  data, split integrity and declared statistical claims as blockers, with
  reproducibility and precision as advisories. Measured on the synthetic AI4S
  test set in `benchmarks/ai4s/` (`RESULTS.md`). Its declaration contract was
  tightened after an independent cross-vendor review found six shapes that
  passed silently (an empty `where` match, `uncommitted: true` without a file,
  duplicate JSON keys, unknown range or split keys, a path outside the
  declaring file's directory); each is now a blocker naming the shape
  (`benchmarks/reviews/2026-10-23-ai4s-pack-v2-terra-r{1,2}.md`, DESIGN.md
  Amendment 5).

### Changed
- **The README's front door is the terminal.** The 60-second tour is `pip install`,
  `crossaudit init`, `crossaudit build`, `crossaudit tui`, `crossaudit verify`, and
  the install section installs the Python package from this repository. Bare
  `crossaudit` inside a project suggests `crossaudit tui` first, and no longer says
  that nothing is configured (D175).
- **The native macOS app and its DMG are off the main line.** The code is kept in
  `packaging/macos/`; it is not built or released from `main`. The README describes
  it in one section near the end, the last DMG stays on the v4.17.0 release, and the
  DMG steps are an optional appendix of `docs/RELEASE_CHECKLIST.md` (D175).
- **The release gate skips the Swift type-check when `swiftc` is absent.**
  `scripts/release_gate.sh` prints one line saying so and continues; it still checks
  the packaging scripts with `bash -n` (D175).

### Fixed
- **A ruling made from the console is committed to the ledger, like one made
  with `crossaudit resolve`.** The console's decision screen (close, revise and
  continue, and the provider-failure retry) used to change only the local
  controller state; every surface now rules through one transaction that
  appends to `cycles/rulings.jsonl` and commits it first, then changes the
  state. If the commit fails (a rejecting hook, a full disk), the cycle stays
  ESCALATED, the log is restored byte for byte, nothing stays staged, and the
  refusal says so, in English and Chinese. Found by the first independent
  cross-vendor review of this release's changes (D176).
- **A provider key held under a nonconventional configured name no longer
  reaches Git, `gh`, SSH or the Codex runtime.** `child_env()` stripped only
  `CROSSAUDIT_*_KEY` and `*_API_KEY` names; it now also strips every `key_env`
  a loaded configuration declares (roles, fallbacks, backup slots). A `key_env`
  that is not a key variable at all (`PATH`, `HOME`, a malformed name) is
  refused when the configuration loads (D176).
- **The evidence ledger's head cache is bound to the file's identity.** It was
  keyed on size alone, so a same-size rewrite by another process was appended
  onto without re-verification; it is now keyed on size, mtime and inode, and
  its docstring states the one case that remains undetected (D176).
- **MCP tool calls made during a build are now in the evidence ledger.** Each call
  the Generator makes to a registered MCP tool, from `crossaudit build` or a console
  chat, writes a `tool_call` entry before it runs and a `tool_result` entry after it
  (hashes, status, size, timing; never the arguments or the output). The audit receipt
  binds them and `crossaudit verify` re-checks them. Before this, those calls went
  only to `.crossaudit/mcp/calls.json`. If the ledger cannot record a call, the call
  does not run (D174).
- **A reply cut off by the output-token limit is refused, not committed.** When
  Anthropic reports `stop_reason: max_tokens` or an OpenAI-compatible provider
  reports `finish_reason: length`, the reply is discarded and the run stops with
  a legible reason instead of committing a half-written file as the round's work
  (D167).
- **One character no longer breaks the evidence ledger.** A payload holding
  U+2028, U+2029 or U+0085 (common in text extracted from PDFs) made the ledger
  unverifiable and let the next appends fork the chain. Ledgers already written
  that way verify again, and an append onto a ledger that does not verify is now
  refused instead of forking it (D168).
- **A local proxy no longer intercepts CrossAudit's own loopback traffic.** With
  `HTTP_PROXY` or `ALL_PROXY` pointing at a local proxy, the console's daemon
  health checks, the project relay and the app self-test were sent to the proxy
  (with the console's session token) and could report a running console as
  dead. Requests to 127.0.0.1 now always go direct; remote MCP servers and
  providers still use the proxy (D169).
- **A file the auditor could not read can no longer pass.** A file that is not
  UTF-8 text and not a PDF or DOCX (a UTF-16 CSV, a spreadsheet, an image) was
  shown to the auditor only as its size, and the round could still pass. Such a
  round now escalates to you and the report lists the files the auditor was not
  shown; a `.csv`, `.json`, `.md` or other text file that is not UTF-8 is
  blocked by the `parseable` check (D169).
- **Approving a tool "for this project" can no longer undo a revoke.** Two
  changes to a project's standing authorizations made at the same moment (a
  tool approved from a card while `workspace_writes` was switched off in
  settings) could each overwrite the other, losing the revoke. Changes are now
  applied one at a time (D169).
- **A decimal comma is no longer read as a thousands separator.** The
  `number_source` check treated a transcribed `1,5` as `15`, so a citation of
  "1,5 mg" passed against a source saying 15 mg. A comma is now accepted only
  as thousands grouping (`1,000`, `12,345.67`); any other comma is reported as
  not a number (D169).
- **Provider keys stay in the core process.** Git, the GitHub CLI, OpenSSH and
  the bundled Codex runtime used to inherit every provider key the app loaded
  from the Keychain (and any `*_API_KEY` exported in the launching shell). They
  are now started without them; only project workers, which call the providers
  themselves, still receive keys (D170).
- **A ChatGPT-subscription turn that tries a tool is refused.** If the Codex
  runtime reports a command, file change, web search, MCP or other tool event
  for a turn, the reply is discarded and the round fails closed with a reason
  naming what was requested, as SECURITY.md already said. Before, the tool was
  blocked but the turn's text was still used (D170).
- **The console page runs only its own scripts.** Its Content-Security-Policy
  now allows the two script blocks it ships, by hash, instead of any inline
  script, so an injected `<script>` or `onclick=` attribute does not execute.
  The server's description of what the policy guarantees was corrected (D170).
- **SECURITY.md says what the console token authorises.** Anyone holding the
  token in the console URL can register a local MCP server or change the
  allowed check commands, and so run programs as you; the policy now says so,
  says where the token is kept, and says to treat it like a password (D170).
- **The README's export-then-verify pair works.** `crossaudit export-pubkey >
  project.pem` now writes only the PEM block (the key id goes to standard
  error), and a `--pubkey` file that is not an Ed25519 PEM key is refused with
  exit 20 and its name instead of a traceback. A signature that does not verify
  is refused (exit 21) in a dry-run `verify` too, not only with `--admit`, and a
  pinned `--pubkey` verification refuses a receipt with no signature. The signed
  statement now carries the receipt's verdict and report digest, which it left
  empty; signatures made before still verify (D171).
- **`crossaudit verify` checks the report you would open, not only the
  committed one.** A `report.md` (or `reproduction.json`) on disk that differs
  from the bytes the receipt binds — edited, or edited and committed on top —
  now prints `WORKING TREE DRIFTED` and is refused with exit 21 naming the file;
  before, it still printed `BINDINGS VERIFIED`. `--record-only` verifies the
  committed record alone and still prints the drift line (D171).
- **A dependency lock already in the project is named by the receipt.** A
  `requirements.txt` (or any recognised lock) committed before the audited
  round, or at the repository root, is now found in the audited commit and
  bound in the receipt; before, only a lock the round itself changed was.
  `crossaudit reproduce` prints each lock's path and sha256 and whether your
  copy still matches it (D171).
- **`crossaudit doctor` is read-only again.** On a fresh project it created
  `.crossaudit/state.json` through its admission probe; it now writes nothing
  unless you run `doctor --fix` in a terminal (D172).
- **`build` then `audit --offline` (or `run`) works as the README shows.**
  Without `--sha`, both now judge the latest commit that changed your work
  instead of the ledger commit `build` leaves at `HEAD`, and say which commit
  they chose (D172).
- **Re-auditing a commit no longer overwrites its recorded cycle.** An explicit
  `audit --sha <commit>` on a commit whose cycle had already PASSED replaced
  that cycle with a new one, so the earlier receipt could no longer be admitted.
  The re-audit now opens a new cycle beside the old one, and `status` lists both
  (D172).
- **`build` exits 22 when the provider failed.** A build that stopped because
  every provider route failed (HTTP 5xx, network) exited 11 like any other
  escalation. It now exits 22, as the README's exit-code table says (D172).
- **`crossaudit --json routing` prints JSON on a fresh project.** It printed
  the sentence `no routing decisions recorded yet`. It now prints `[]`, the
  same list shape it prints once decisions exist (D172).
- **`crossaudit resolve` commits the ruling, as the README says.** The reason
  was kept only in the local state file. Each ruling now appends a line to
  `cycles/rulings.jsonl` in its own commit, with the reason in the commit
  message. `status` lists every ruling and shows a closed cycle as `CLOSED`, and
  closing ends the run that was waiting for the decision (D172).
- **`crossaudit console` opens the dashboard.** The README said it did, but it
  only printed the URL. Run from a terminal, it now opens the tokenized URL in
  your browser. `--no-open` prints the URL only, and nothing opens under
  `--json` or when output is not a terminal (D172).
- **A non-interactive `init` says where your keys come from.** Without a
  terminal it cannot prompt for keys and writes no keys file. Its summary now
  says the keys are read from `CROSSAUDIT_AUDITOR_KEY` and
  `CROSSAUDIT_GENERATOR_KEY` (D172).
- **The plain-HTTP refusal names a setting that exists.** It pointed at a
  `--allow-insecure-localhost` flag that never existed. It now names a loopback
  `base_url:` with `CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT=1` (D172).
- **README corrections.** The default check pack is `general`, `amend --yes`
  is documented for scripts, the `--version` line is shown as printed, and
  verdicts (`PASS`) are kept apart from cycle states (`PASSED`) (D172).
- **`crossaudit pair` prints what `--apply` does, all of it, in order.** The
  plan left out the push of the local history, the local commit recording the
  pair and the `origin` remote, and listed branch protection, which `--apply`
  never did. The plan and `--apply` now come from one list of steps, each shown
  with its commands; what `--apply` leaves to you (branch protection, the key
  upload when the key is not loaded) is printed under "You do afterwards"
  (D173).
- **`crossaudit pair --science … --audit …` shows its plan without a GitHub
  account.** It asked GitHub for the account name before printing anything, so
  the plan the README tells you to review was refused when `gh` was signed out.
  The account is now needed only for `--apply`, or when `--science` is left out;
  a signed-out or missing `gh` adds one line saying what `--apply` will need
  (D173).
- **`crossaudit init --github` no longer says `pair --apply` "does all of it",
  and its GitHub warning says one thing.** The closing panel now lists `pair`'s
  own steps and what is left to you; with `gh` installed but signed out the
  warning says to run `gh auth login` instead of also telling you to install it
  (D173).

## 4.17.0 — The activity stream

The conversation is now one chronological stream, in one visual language,
instead of the audit protocol's state machine drawn as cards.

### Changed
- **Five row shapes for every event.** Say, do, wait, outcome, note. A row is a
  verb, one number and an elapsed time; detail opens in place. Finished rounds
  fold to a single row. The run card, the review card and the delivery band are
  gone — a settled cycle and an escalated one render the same way.
- **Failure is not a decision.** An empty completion, an unreadable reply, a
  timeout, a rate limit or a commit with nothing in the audited folder is a note
  with one retry beside the words. Only the auditor's own concern, exhausted
  rounds or an unsettled earlier decision asks you to decide, and that happens
  in the stream. Nothing is modal; the composer is never taken away.
- **One status line while work runs**: the phase, the round, the elapsed time and
  the running cost, with a stop control.
- **Progress you can read.** The thinking animation marks a line of words rather
  than spinning alone; the generator's draft is one summarising line you can
  open; identifiers live in a closed details block.

### Added
- One bounded repair when an auditor reply cannot be read at all — never when it
  parses and fails a content rule, because a verdict may not get looser because
  of a retry. The attempt and the rejected reply's digest are in the receipt.
- `benchmarks/expertlongbench` — an ExpertLongBench harness and a faithful CLEAR
  reimplementation, with the first measured result recorded as it came out.

## 4.16.0 — Evidence Authority

The audit records where a finding's power to block comes from, and the loop
stops asking the generator to hide findings behind defensive code.

### Added
- **Evidence authority.** Every receipt binds each finding's tier
  (deterministic check or auditor model), whether a check verified it, the
  route the workflow took, and a digest over the set; the report gains an
  `Evidence` section. Verdict synthesis is unchanged under default settings.
- **`authority.lone_model_blocker` dial.** `block` (default) keeps bounded
  automatic revision; `escalate` hands a model-only blocker to a person at
  round one.
- **Repair guard.** A revision after a BLOCKED audit is screened before commit:
  a file outside the audited directories or a binary the renderer did not
  produce is refused (one free retry, then a decision card); catch-all excepts,
  deleted assertions, skipped tests and over-budget code changes are cautions
  the auditor sees in the next round. `repair.mode: refuse` makes them refusals.
  Prose and data files are never pattern-screened.
- **Finding states** (`findings.json` beside each round) so a confirmation
  rate for auditor findings can be measured.
- **Chinese for refusals.** 538 of 540 distinct denial messages have Chinese at
  the CLI and in the console; the language is resolved for every command.
- Decision Center copy for the two new stop causes; per-finding "verified by a
  check / raised by the auditor" in the review detail; composer, search and
  provider controls have accessible names.
- **Progress from the first millisecond.** Sending a message returns at once;
  routing, preparation, generation, checks and the audit each narrate a line,
  generator output streams into the turn for every provider that can stream
  (Anthropic included), and a server-side clock speaks whenever a phase is
  silent for 8 s. Chat and query replies stream too.
- **Setup before failure.** A missing provider credential shows a setup card
  with one button to Settings, on every path that can start a task; the
  same-vendor rule is stated in plain words; new projects default to a single
  local repository; the DMG carries a first-open note.
- **Plain results.** Passed / Needs changes / Needs you instead of verdict
  codes; findings lead with what was observed; identifiers live in a collapsed
  details block; the run card forecasts duration and cost from the project's
  history; every escalation names its cause and its next action.
- **Token warnings and billing.** Usage is attributed to task, cycle, round,
  chat and role; 80% and 95% of a budget warn once per period and re-arm at
  rollover; a provider's 429 shows a reset countdown; a header pill shows
  today and this month; per-task cost on the run card; unpriced models are
  visible and can be priced per project; CSV/JSON export and a workspace
  roll-up.

### Fixed
- `verify --admit` on an invalid signature raised NameError instead of
  returning an exit code (since 4.14).
- "approximately" in a task no longer makes a 5% length deviation a blocker;
  the rule text says what it means and reaches template projects too.
- The in-process network guard names exactly what it covers; the test suite no
  longer calls `gh`.
- Test-suite guard: no undefined names anywhere in `src/`.

## 4.15.0 — Agentic Runtime

CrossAudit becomes a Claude-Code / Codex-class capable agent **without giving up
the cross-vendor audit**. The sandboxed model proposes actions; every real
operation is routed through a controlled Tool Broker, decided by a deterministic
Capability Policy Engine against a scoped, expiring Capability Token, recorded to
an append-only hash-chained Evidence Ledger, and reviewed by the independent
Auditor — which sees evidence only and can neither fabricate it nor bypass policy.

### Added
- **Tool Broker + Capability Policy + Evidence Ledger.** A single chokepoint every
  model-proposed action passes through: deny-by-default policy decision → capability
  token (tools / paths / hosts / cost / bytes / expiry, escape-proof) → append-only,
  hash-chained evidence ledger the Auditor reviews and the receipt binds. Permission
  levels 0–6 (inference · read · recoverable write · command · network · high-impact
  · destructive).
- **Real-time per-call approval ("like Claude Code").** A flagged Level 3+ action
  pauses the run in place; a pending-action card shows what / why / scope /
  reversibility / cost with a **diff or command preview**, and your Allow once /
  this run / this project / Deny is recorded to the ledger as the grant. Level 4+ is
  always per-call; Level 6 (self-install) is refused outright.
- **Governed capabilities** behind explicit per-project opt-in and per-call approval:
  recoverable file writes, `run_check` (run tests / build / format as an argv list,
  never a shell), `git_commit`, and SSH/HPC read + submit.
- **Governed actions (evidence) panel** — the audit ledger is now visible in the
  console: every action the agent took, under which grant, approved how, and the
  content hashes recorded (never raw output).
- **Secret-scan gate** — a governed commit, and the build's own per-round commit,
  refuse to write a credential into git history (the secret's kind is reported,
  never its value).

### Changed
- Evidence-ledger append is O(1) (size-guarded head cache); the ledger fails closed
  on a crash-torn tail instead of extending a damaged chain.
- The console top bar shows a clean project name (not the `owner/repo` slug); a
  prominent Stop is always visible while a run is live; a one-time, reduced-motion-
  aware shell entrance.

### Security
- Adversarially hardened: 202 red-team tests attempt to bypass the broker, forge or
  replay evidence, escape path scope, widen a token, leak a secret, tamper the
  ledger / receipt, race concurrent writers, self-install, or auto-run a Level 4+ —
  every invariant held. Backward-compatible: receipts without governed-tool evidence
  still verify.

## 4.14.0

Prior release. See the git history and `docs/ENTERPRISE_TEST_REPORT.md` for the
4.14.0 assessment and its published DMG checksum.
