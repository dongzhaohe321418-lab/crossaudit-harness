# Changelog

All notable changes to CrossAudit are recorded here. Versions follow the
`MAJOR.MINOR.PATCH` scheme; the source on `main` is authoritative.

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
