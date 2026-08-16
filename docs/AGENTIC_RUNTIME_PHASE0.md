# CrossAudit Agentic Runtime — Phase 0 Inventory Report

Grounded only in the six per-subsystem inventories. No code is asserted that isn't referenced there.

---

## 1. Current-State Map (target module → what exists vs. what's missing)

### Agent Runtime
**Has (reuse foundations):**
- The de-facto runtime is the generator→commit→auditor→revise loop `cli/build.py:144 run_loop` (entry `cmd_build` at `cli/build.py:539`; foreground/background both via `runtime/commands.py:268 RunCommandService.start`).
- Propose-only contract already enforced at the model boundary: `generator.py:29 GENERATOR_SYSTEM` + `:86 MCP_SYSTEM` + `:139 ToolRequest` / `:172 parse_tool_request` / `:134 ComputeRequest` / `:148 parse_compute_request`. The model emits an envelope and has no execution path; tool output is marked untrusted (`generator.py:289`).
- The one true sandbox primitive: `providers/codex_subscription.py:126` (Popen app-server), `:338` read-only ephemeral-cwd, `:360` `networkAccess:false`, `:190` server-request denial.

**Missing:** The *host* Python process running `run_loop` is unsandboxed — it can spawn subprocess, write anywhere, open sockets. "Sandboxed model only proposes" is realized only for the codex provider; anthropic/openai_compat run server-side with no local sandbox. The generator's `ToolRequest`/`ComputeRequest` are dispatched straight to `mcp`/`hpc` MANAGER by the loop (`cli/build.py:237/264`) with no broker deciding/recording between model and tool.

### Tool Broker
**Has (two siloed prototypes to generalize):**
- `mcp.MANAGER` — the closest working prototype: `mcp.py:540 register` (per-tool allowlist, review-before-enable, timeout/call bounds), `:660 agent_context`, `:691 call_agent` (enable→allowlist→ordinal-cap→bound-args→execute→hashed-record→notify), `:685 _record_call`.
- `hpc.MANAGER` — parallel prototype for remote compute: `hpc.py:720 submit_agent`, `:804 run_agent`, ceilings + `_agent_inputs` scope checks.
- Read-only git tool surface already disciplined: `gitio.py` `resolve/parent/changed_paths/entries/read_blob/materialise/is_ancestor/commit_exists`.

**Missing:** No unified broker. ~20 modules call `subprocess/urllib/os` directly with inline guards. MCP and HPC duplicate gating (allowlist / ordinal cap / hashed ledger / notify) with different limits (per-task ordinal vs. per-build `MAX_MCP_CALLS_PER_BUILD=40` / `MAX_AGENT_JOBS_PER_BUILD=20` living in `cli/build.py`). Read-only tools (git status, doctor) have nowhere to register. No single chokepoint every execution funnels through.

### Capability Policy Engine + Capability Tokens
**Has (scattered scope primitives to consolidate):**
- Network/host: `base.py:148 egress_check`, `:80 tls_context`, `:142 _NoRedirect`; `mcp.py:172 _safe_url` (SSRF/private-IP), `:148 _safe_command` / `:158 _safe_args`.
- Path: `scope_dirs` gate at `generator.py:105 Work.validate`, `transfers.py:461 resolve_artifact`, `hpc.py:684 _agent_inputs`.
- Time/size: `gitio.py` `GIT_TIMEOUT_S`, `blob_limit`/`MAX_BLOB_BYTES`/`MAX_DOC_BYTES`; hpc regex validators `hpc.py:33-147`.
- Cost: `resilience.py:154 enforce_budget` (`usage.py`) — provider spend only.
- Schema skeleton: `config.py:38 Role` / `:71 Config` frozen dataclasses + strict allowlist `load()` (`:155`) — reusable shape for a token schema.
- Decision-object posture: `admission.py:55 Assessment` ("absent evidence never counts in favour").
- Registry/allowlist patterns: `dcl/plugins.py:30 load_allowed` (allowlist-by-name + API-version pin).
- Seed level heuristic: `router.py:159 apply_safe_default` (reversible → supervised; control-plane → ask), `:117 AUDITOR_MUTATIONS`.

**Missing:** No Capability Token object carrying tools/paths/hosts/time/cost/expiry. No permission levels 0-6; only 3 isolation booleans + 4 admission-tier strings exist. MCP `readOnlyHint`/`destructiveHint` are UI-only (`console/page.py:5108/5490`), not enforced. Policy is deployment-wide (`crossaudit.yml`), not per-action. Cost/expiry govern only model spend, not MCP/SSH/git/fs. Policy logic is inlined inside each Manager, not a separable deterministic `decide()`.

### Evidence Ledger (append-only, hash-chained)
**Has (strong hashing/verify primitives, git substrate):**
- `receipt/schema.py:37 canonical()` / `:43 digest()` / `:53 validate()` — canonical JSON + SHA-256 content-addressing.
- `receipt/build.py:104 build()` — provenance-complete, derived-not-narrated record; `:60 isolation_evidence`.
- `receipt/verify.py:39 verify()` — read-only re-derivation, refuse-on-first-mismatch; `:104-111` `report_commit` ancestor check (the only append-order tamper check); `:136 admit()`.
- `controller/state.py:87 _write` (atomic O_EXCL + fsync + rename) / `:102 _locked` / `:375 admit` consume-once — durable-append + single-use-claim substrate.
- `gitio.py` tree-materialization + `is_ancestor`/`commit_exists` — git-as-append-only read layer (symlink/submodule refusal `:259`).
- `_selfid.py:30 code_digest` / `:90 identity` — verifier provenance block per entry.
- `auditor/run.py:45 dcl_source_digest` — pins the exact code that produced evidence.
- Append-only cycle-dir discipline `cli/main.py:461-507` (`.2/.3` attempt suffixes).

**Missing:** **No global hash chain across entries** — receipts are content-addressed; the only link is per-cycle `parent_receipt` (round N→N-1), stored in the *mutable* `state.json`. No Merkle root, no ledger head, no receipt→receipt chain across cycles; tamper-evidence rests on git's DAG + branch protection. **No cryptographic signatures anywhere** (verifier identity is a self-asserted `code_digest`; anyone running the code can mint a byte-identical receipt). Append-only is a *convention* locally (dir naming + ancestry check); `git amend`/`rebase`/force-push rewrites the ledger, resisted only by optional, online-only remote branch protection. **No per-action evidence records** — MCP `calls.json` (rolling last-200, `mcp.py:685`, not chained), `router.py:186`/`dispute.py:161` plain JSONL, `runtime/runs.py` SQLite (operational, not evidence). Receipt schema `REQUIRED_*` tuples are hard-coded to the audit-cycle shape — no generic evidence-entry type for tool calls / compute / approvals.

### Approval Service
**Has:** `mcp` register-time approval + `allowed_tools`; `hpc` host policy + `agent_enabled` toggle; `admission` gate; `cli/pair.py:423 plan()` two-step plan/apply; UI typed confirmations (`projects.py` `DELETE GITHUB`); gh device-flow scope grant (`projects.py:647`).

**Missing:** No unified Approval Service. Approval is at *registration* time, not per-call. No per-call approval, no permission-level (0-6) gating, no cost/time admission. The HPC "I approve this remote execution" checkbox (`page.py:2569`) is client-side only, not verified server-side.

### Artifact Registry
**Has:** Two-repo privilege separation (science vs. audit repo). `console/transfers.py:461 resolve_artifact` + generator-recorded outputs. `hpc` outputs (`:977 outputs`, `:1003 open_output`). Candidate/version fingerprint material: `_selfid` `crossaudit-build.json` + SHA-256-pinned Codex/gh binaries (`build_dmg.sh`).

**Missing:** No governed registry. Outputs are discovered/streamed ad hoc, not content-addressed, no retention policy, no promotion state. HPC output bytes returned to the Generator (`_agent_result`, `hpc.py:768`) are **not hashed or ledgered**. DMG + `.sha256` + build.json are ad-hoc files, not a registry of candidate artifacts with provenance.

### Remote Compute Manager
**Has (this is the most complete prototype):** the entire control plane in `hpc.py` — `OpenSSH` transport (`:200-297`, argv-only, hardened `_SSH_OPTIONS`), `register`/`probe`, `submit`/`submit_agent`/`run_agent`, `_poll_job`/`refresh`/`watch`, `logs`/`outputs`/`cancel`, input sha256 (`:607`), detach-persistence (nohup/setsid + sbatch), atomic `_write` (`:76`). Contract pinned by 20 tests.

**Missing:** It's a global singleton called directly by console router + build loop — no broker seam, no Capability Token (ceilings are static per-host config, nothing expires), **zero cost accounting**, last-writer-wins JSON (not append-only/chained), outputs unhashed and fed to the Generator as trusted context with no Auditor/Admission step, no Recovery Supervisor (the 60s "submitting" timeout can mark a genuinely-running job FAILED and orphan compute).

### Admission Gate
**Has:** `admission.py:142 assess()` (tier from probed evidence: local/remote/paired/notification/enforced), `:104 probe_branch_protection` (real `gh api`), `receipt/verify.py:136 admit()` transaction, `controller/state.py:375 admit` single-use consume, `receipt/schema.py:94 isolation_shortfall` cross-tier replay guard.

**Missing:** The Gate today governs **receipt/merge admission, not per-action tool calls**. The real merge refusal is *external* GitHub branch protection; `admission.py` only assesses/reports. There is no in-process gate that admits/denies a proposed action against a policy decision + token. `enforced` (the only refusing tier) needs network + gh; offline the posture is unknown. Compute outputs flow straight back to the Generator with no admission decision.

### Recovery Supervisor
**Has (seeds only):** Swift `launchCore` 20s readiness watchdog + `terminationHandler` + `restartCore` (`CrossAuditApp.swift:219-286/386-401`); `app.self_test()` JSON health contract; `hpc.refresh` transient-loss tolerance; detach-persistence substrate. `console/daemon.py:256` self-exec primitive.

**Missing:** No Recovery Supervisor. Only crash-detection + manual "Retry startup". No automatic rollback, no known-good fallback slot, no health-gated promote/demote. `hpc.watch` daemon threads die on app exit; the console watchdog never calls `hpc.refresh`, so a job completing while the app is closed is reconciled only on the next snapshot. Torn submit → FAILED-with-possible-orphan. (Self-improve/packaging subsystem confirms: no candidate build, rollback, or parallel install exists.)

---

## 2. Ungoverned Execution Surfaces Today (consolidated, de-duplicated)

Every subprocess / network / fs-write / exec that Phase 1's Tool Broker must eventually funnel. Grouped by kind; `path:line`.

**Model invocation (already centralized — the natural first "level-0 tool"):**
- `providers/resilience.py:150 complete()` — single chokepoint for both roles (carries `enforce_budget:154` + circuit-breaker `write_text:82`).
- `providers/base.py:169 request_json` / `:200 get_json` — provider HTTPS (guarded by `egress_check`).
- `providers/anthropic.py:44`, `providers/openai_compat.py:75` — HTTPS POST.
- `providers/codex_subscription.py:126` — Popen app-server. **PRESERVE the read-only + network-disabled sandbox (`:338/:360/:190`) verbatim.**

**Model-callable tool executors (the de-facto Tool Broker to re-home):**
- `mcp.py:216 _StdioSession.Popen` — arbitrary approved local executable (argv, never shell).
- `mcp.py:390 _HTTPSession._post` — arbitrary approved HTTPS (guarded by `_safe_url`).
- `hpc.py:239 OpenSSH.run` / `:261 stream` / `:272 send_file` / `:209 expanded` — arbitrary remote shell + remote fs write over SSH.
- `hpc.py:549 submit` / `:720 submit_agent` / `:804 run_agent` / `:955 cancel` — remote job launch + process control (largest model-driven surface).

**Git (read):** `gitio.py:72 git()`, `:93 is_repo`, `:130 entries`, `:183 _stream_blob Popen`, `:285 is_ancestor`, `:290 commit_exists`; console reads `streams.py:59/92`, `chats.py:117`.

**Git (write):** `app.py:42 _git` / `:97 commit`; `cli/build.py:117 add` / `:364 commit`; `cli/wizard.py:167-231` init/add/config/commit; `cli/talk.py:62-64/119-120/239-240`; `console/projects.py:1013 commit` / `:1023 restore` / `:1941 _demo_git_commit` / `:2126 rev-list`; `admission.py:93 git remote`.

**gh CLI (network/VCS, incl. mutating & credential):** `cli/pair.py:71 auth status`, `:87 _gh`, `:129 api user`, `:147 repo view`, `:333 repo create` (L5), `:366 repo clone`, `:389/:358 push` (L4), **`:401 gh secret set` (credential egress, L5)**; `console/projects.py:647 gh auth login --web` (OAuth device-flow), `:2212 repo delete --yes` (L5); `admission.py:88 _gh`; `app_doctor.py:200/81`.

**Keychain (`security` CLI):** `app_keys.py:58/72/89`; `mcp.py:103/118/130`.

**Other subprocess:** `runtime/processes.py:125/146 ps`; `app.py:84 xcode-select -p`; `app_doctor.py:329 Popen xcode-select --install`; `console/daemon.py:256 Popen self-spawn`; `document_export.py:128 git log` + pandoc-style rendering.

**Non-provider network egress:** `app_doctor.py:124 _latest_release` (GitHub release GET); loopback self-probe/SSE `daemon.py:151/163`, `projects.py:568 _watch`, `app.py:142 self-test`.

**Inbound control plane (preserve, front with shared Application Service):** `console/server.py:1632/:284 ThreadingHTTPServer` bind 127.0.0.1; loopback + per-session-token + Host gate; `:1388-1426` dispatches to the same hpc/mcp MANAGER the CLI uses.

**Filesystem writes (model-authored + product):** `generator.py:343 apply()` (model bytes → work tree, then committed **before the auditor sees them** — preserve the write-then-commit-then-audit invariant); `document_export.py:517/362/814`; `console/transfers.py:252/263/384/429`; `mcp.py:70 _write`; ledger/state writes `router.py:186`, `dispute.py:161`, `controller/state.py:87`, `runtime/runs.py` (sqlite), `hpc.py:76`, `workspace.py:86/169`, `runtime/workspaces.py:93`.

**Dynamic code load (highest-risk, easy to miss):** `dcl/plugins.py:41 ep.load()` — arbitrary entry-point code, allowlisted by name only, runs unsandboxed in the key-holding, ledger-writing process.

**Boundaries to preserve when funneling:**
1. `codex_subscription` read-only + network-disabled sandbox (subtle: server tool-requests denied but turn continues).
2. `gitio` tree-as-source-of-truth + symlink/submodule refusal + byte-identical blob caps (audit/verify parity).
3. Hand-tuned bounds (total-deadline reads, git timeouts, decompression-bomb/memory caps) must carry forward, not regress.
4. HPC detach-persistence: token expiry must mean "no new submits", never "kill running compute".
5. `generator.apply` write-then-commit-then-audit ordering.

---

## 3. Top Gaps + Risks, Ranked

1. **No proposer/executor separation in-process (foundational).** The generator/build loop and every executor share one unsandboxed Python process with direct `subprocess`/`gitio.git()` reach. A model with code access bypasses every check. Retrofitting a broker is a *subtractive* change (remove direct reachability), not additive. — *Highest.*
2. **No unified Tool Broker / chokepoint.** ~20 modules exec directly; two prototype managers (mcp/hpc) with duplicated, subtly divergent gating. Any broker that misses one surface leaves a de-facto ungoverned tool.
3. **No Capability Token / permission levels 0-6.** Scope is piecemeal per-surface; nothing carries tools/paths/hosts/time/cost/expiry. High-value ungoverned L4-6 actions (`gh secret set`, `gh auth login` OAuth, Keychain writes, `xcode-select --install`, repo create/delete) sit *outside* the mcp/hpc managers and are easy to miss.
4. **Evidence is fragmented and not hash-chained; no signatures.** Tool-call evidence (mcp `calls.json` last-200, JSONL logs, sqlite) is lossy, mutable, and never enters the receipt. An Auditor cannot replay "which tool ran under which grant with what output." Integrity ultimately depends on optional, online-only remote branch protection.
5. **Ambient gh auth = unbounded blast radius.** One global token reaches every repo the account can access, not just the paired project's two repos. Must be host/repo-constrained before it can be governed.
6. **CLI/UI share MANAGERs but not one governed Application Service.** Console imports *up* into `cli.*` (`server.py:661/725`); no neutral app-service module. Inserting a broker risks two divergent execution paths.
7. **Admission/isolation are recorded, not enforced.** `permissive=false` is written when one process holds both keys but the process is never prevented; the merge refusal is external GitHub, not in-product.
8. **Migration risk on evidence hardening.** Adding a chain/signatures changes receipt bytes and the canonical digest, breaking the deliberately-preserved "byte-identical" guarantee — needs a `RECEIPT_SCHEMA` bump + migration. The consume-once admission ledger lives in a rewritable `state.json` (advisory 120s-stale-break lock) — the weakest link if receipts are chained without hardening it.
9. **HPC recovery/orphan risk.** 60s "submitting" timeout can mark a running job FAILED. No Recovery Supervisor; must reattach-by-scan (squeue/pgid) before declaring failure.
10. **`dcl/plugins.py:41 ep.load()`** — arbitrary code in the key-holding process, allowlisted by name only. Small surface, large privilege.

*Note: two package copies exist (`src/crossaudit` vs `build/lib/crossaudit` + `.venv`); edits must target `src/` only.*

---

## 4. Phase 1 Scope — Minimal Safe Closed Loop

**Goal:** a read-only agent whose proposals pass through one deterministic broker that checks a capability token, executes only read-only tools (file read / search / git-status / doctor), records each call to an append-only hash-chained Evidence Ledger, and lets the Auditor review the *real* recorded tool evidence. No mutation, no network egress beyond the existing provider chokepoint, no self-modification (explicitly out of scope — the highest-privilege self-replace path is wired last).

### New modules to create
- `src/crossaudit/broker/__init__.py` — the single `ToolBroker.execute(proposal, token) -> ToolResult` chokepoint. Generalizes the `mcp.call_agent` pattern (enable→scope-check→bound→execute→record→return). Both `run_loop` and the console call it; nothing else may exec.
- `src/crossaudit/broker/registry.py` — tool registry (allowlist-by-name + API-version pin, modeled on `dcl/plugins.load_allowed`). Registers the Phase-1 read-only tools; each declares a permission level (all 0-1 here).
- `src/crossaudit/broker/tools_readonly.py` — the four brokered tools, each wrapping an existing primitive: `file_read` (via `gitio.read_blob` + `scope_dirs` gate), `search` (scoped grep over the committed tree), `git_status` (via `gitio` read ops), `doctor` (wrap `app.self_test`/`app_doctor.collect`, no `repair`).
- `src/crossaudit/policy/tokens.py` — `CapabilityToken` frozen dataclass (tools, paths, hosts, time-window, cost ceiling, expiry) reusing `config.Role`'s strict-allowlist schema shape.
- `src/crossaudit/policy/engine.py` — deterministic `decide(proposal, token) -> Decision` (reuse the `admission.Assessment` "absent evidence never counts in favour" posture). Separable from execution so it can be replayed.
- `src/crossaudit/ledger/chain.py` — append-only, hash-chained evidence ledger: `append(entry) -> digest` where each entry carries `prev_digest` + a head pointer. Reuse `schema.canonical()/digest()` for hashing and `controller/state._locked/_write` for the atomic O_EXCL durable append. Generic evidence-entry type (tool-call / decision / result), distinct from the audit-cycle receipt schema.
- `src/crossaudit/appservice/__init__.py` — neutral Application Service both `cli.*` and `console.*` import (fixes the inverted layering), exposing `run_loop` + broker wiring.

### Existing files to modify
- `cli/build.py:144 run_loop` — replace direct `mcp.MANAGER.call_agent` (`:237`) and `hpc.MANAGER.run_agent` (`:264`) dispatch with `ToolBroker.execute(...)`. For Phase 1, only read-only tools are registered; the mcp/hpc dispatch is gated behind the broker (and can remain disabled).
- `generator.py:172 parse_tool_request` — keep the propose-only envelope; route the parsed `ToolRequest` to the broker instead of straight to a manager. Inject the read-only tool catalog via a broker `agent_context` (generalize `mcp.agent_context:660`).
- `console/server.py:661/725` — import from `appservice` instead of `cli.build`/`cli.talk`; route `/api/*` execution through the same `ToolBroker`.
- `receipt/build.py:104` — add a `tool_evidence` block referencing the ledger head digest, so a cycle's receipt binds the tool-call chain (schema bump + `verify.py` continuity check).
- `auditor/run.py` / `auditor/prompt.py` — give the auditor a **read-only view of the ledger entries** (the recorded tool evidence: tool name, args_sha256, result_sha256, decision, token ref) as reviewable evidence, without handing it live tools — reconciling "Auditor reviews EVIDENCE" with the existing contextual-isolation invariant (auditor still has no execution path).
- `receipt/schema.py` / `receipt/verify.py` — `RECEIPT_SCHEMA` bump + migration; `verify()` re-derives the ledger chain (prev_digest continuity) read-only, refuse-on-first-mismatch.

### Smallest end-to-end demo that proves the loop
On a sample user project:
1. Generator emits a `<<<CROSSAUDIT-MCP-TOOL>>>`-style envelope proposing `file_read` of an in-scope path and a `search` for a token.
2. `ToolBroker.execute` asks `policy.engine.decide` against a `CapabilityToken` scoped to that project's `scope_dirs`, read-only tools only, with an expiry. A proposal for an out-of-scope path or a write/network tool is **denied deterministically**.
3. Allowed calls run via `gitio.read_blob`; each call (proposal, decision, args_sha256, result_sha256, prev_digest) is appended to `ledger/chain.py`; the head digest advances.
4. The Auditor reads the ledger entries as evidence, and `receipt/verify.py` re-derives the chain offline and confirms continuity + that the receipt binds the head digest.
5. **Proof points:** (a) an out-of-scope/write proposal is refused before execution; (b) tampering with any ledger entry breaks `verify()`; (c) the same demo produces byte-identical ledger digests when replayed on a second host (audit/verify parity), inheriting `gitio`'s deterministic blob caps.

This stays entirely within existing primitives (`gitio` read layer, `mcp.call_agent` gating pattern, `schema.canonical/digest`, `state._locked/_write`, `admission.Assessment` posture, propose-only generator envelope) and touches no mutating, network-egress, or self-modification surface.
---

## Addendum A — Verification (load-bearing claims spot-checked against code)

Two inventory agents ran without the safety classifier (evidence-ledger, mcp-skills-appservice); their load-bearing claims were re-verified directly:

- **No cross-entry hash chain / no signatures.** CONFIRMED. `receipt/schema.py` provides `canonical()`/`digest()` (SHA-256 content addressing) and hard-coded `REQUIRED_*` tuples (audit-cycle shape only); grep finds no signature/hmac/ed25519 and no `prev_digest`/chain across entries. `parent_receipt` links only cycle N→N-1 and is stored in the **mutable** `controller/state.py` state.json (`:200/:311/:369/:394`). → the exact gap `ledger/chain.py` fills.
- **Console imports up into `cli.*` (no neutral Application Service).** CONFIRMED. `console/server.py:661` `from ..cli.build import preflight, resolve_task, run_loop`; `:725` `from ..cli import talk as talk_mod`.
- **Build loop dispatches straight to managers (no broker).** CONFIRMED. `cli/build.py` → `mcp.MANAGER.call_agent` (~:237) and `hpc.MANAGER.run_agent` (~:264), with only per-build counters (`MAX_MCP_CALLS_PER_BUILD` / `MAX_AGENT_JOBS_PER_BUILD`) between model and tool.

## Addendum B — Run-state-machine subsystem (the failed inventory agent, filled in)

`runtime/runs.py` is one of the **strongest reuse foundations** and was missing from the synthesis:

- **Full state machine:** `RunState` (QUEUED, GENERATING, WAITING_FOR_CAPABILITY, AUDITING, REVISING, PROVIDER_UNAVAILABLE, CANCELLING, CANCELLED, PASSED, FAILED, INTERRUPTED, WAITING_FOR_PROVIDER, WAITING_FOR_HUMAN), `ACTIVE_STATES`/`TERMINAL_STATES`/`PARKED_STATES` frozensets, and an explicit allowed-transition table validated on every write.
- **Durable + crash-safe:** SQLite-WAL journal; heartbeat/lease/`waiting_reason`; **clock-free worker identity** (pid + start-time); `recover_abandoned` watchdog; `_cancel_grace_elapsed` (CANCELLING force-complete); `prune_terminal_runs` retention; `latest()` event cap. `runtime/commands.py` observes `CANCELLING` at every boundary (`_cancelled`).
- **Maps to:** the tool-run state machine (per-tool-call lifecycle: proposed→policy_checking→approval_required→authorized→running→succeeded/failed/timed_out/cancelled/rolled_back) **and** the Recovery Supervisor. Phase 1's per-tool-call state should extend this machine, not reinvent it.
- **Gap:** it governs the audit *run*, not per-tool-call execution; no idempotency key surfaced to a broker; no rollback state. These are additive extensions to a proven core.
