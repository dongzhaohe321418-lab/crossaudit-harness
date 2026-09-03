# Changelog

All notable changes to CrossAudit are recorded here. Versions follow the
`MAJOR.MINOR.PATCH` scheme; the source on `main` is authoritative.

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
