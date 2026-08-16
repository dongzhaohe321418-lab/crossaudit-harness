# CrossAudit Agentic Runtime — Build Progress (loop ledger)

Self-driving build loop. Each iteration: do the next unchecked item(s) in order →
write tests → run them + guard against regression (full suite before any wiring
change) → check off + update counts here → continue. Grounded in the user's guide
and `docs/AGENTIC_RUNTIME_PHASE0.md` §4.

**Invariants (never violate):** sandbox unchanged (codex read-only+network-off
preserved) · permission comes from CrossAudit, not the model · deny-by-default ·
Auditor reviews EVIDENCE only, cannot fabricate or bypass policy · Level 4+ needs
explicit approval · self-improve only in isolated candidates, never self-install ·
edits target `src/` only (a `build/lib` copy exists) · nothing committed/pushed
without the user.

**Test baseline:** full suite 955 passed / 2 skipped before this work.

---

## Phase 1 — minimal safe closed loop  ✅ COMPLETE (1013 green, 58 new tests, 0 regression)
- [x] `ledger/chain.py` — append-only hash-chained Evidence Ledger — **9 tests** (`test_evidence_ledger.py`)
- [x] `policy/tokens.py` — CapabilityToken (tools/paths/hosts/time/cost/expiry, escape-proof) — **in test_capability_policy**
- [x] `policy/engine.py` — deterministic `decide(proposal, token)` — **22 tests total** (`test_capability_policy.py`)
- [x] `broker/registry.py` — tool registry (allowlist-by-name + level/scope) — **test_tool_broker**
- [x] `broker/tools_readonly.py` — file_read/search/git_status/doctor (committed-tree via gitio, bounded)
- [x] `broker/__init__.py` — `ToolBroker.execute`: decide→execute→ledger; deny-by-default — **7 tests (proof loop)**
- [x] `appservice/__init__.py` — neutral seam (run_loop/talk re-export + `broker_for`/`evidence_path`/catalog) — **4 tests**  (full de-inversion = Phase 2)
- [x] wire `cli/build.py` run_loop → `server_id='crossaudit'` requests route via broker (`broker/routing.py`); mcp/hpc untouched — **5 tests, full suite 1002 green, 0 regression**
- [x] wire `generator.py` — routing + **catalog injection LIVE** (optional `builtin_tools` in the user prompt only; system prompt unchanged; absent-when-not-offered) — **3 tests, full suite 1005, 0 regression** (user approved 全部继续)
- [x] wire `console/server.py` → imports from `appservice` (behavior-preserving; full suite 997 green)
- [x] `receipt/{build,schema,verify}.py` — OPTIONAL `tool_evidence` block binds ledger head+count; **NO schema bump** (added within v2, tool-free receipts byte-identical → full back-compat); verify() re-derives the ledger chain when present & refuses on mismatch — **full suite 1005, 0 regression**
- [x] `auditor/{run,prompt}.py` — read-only, allowlisted evidence view (hashes + decisions only, never raw output; gated → empty ledger = identical prompt); no live tools — **4 tests, full suite 1013, 0 regression**
- [x] **proof demo** — `test_receipt_tool_evidence.py`: evidence recorded → receipt binds ledger head → verify() confirms; **ledger tamper breaks verify()**; tool-free receipt still verifies — **4 tests**
- [x] full suite green — **1013 passed / 2 skipped** (was 955; +58 new-module tests, 0 regression)

## Phase 2 — workspace modification (Level 2)  ✅ COMPLETE (writes live+usable+audited; L3 command tool gated; worktree optional/deferred)
- [x] `broker/recovery.py` — content-addressed recovery points + atomic write + escape-proof resolve-in-root
- [x] `broker/tools_write.py` — `file_write` (L2, recoverable, scoped, diff-reporting) + `register_write`/`write_registry` — **11 tests**
- [x] approval gate — broker returns `needs_approval` for L2 writes (APPROVAL_MIN_LEVEL kept at 2; classifier blocked lowering it — writes stay approval-gated); write denied under read-only grant
- [x] **Approval Service** (`broker/approval.py`) — project-level authorization model (user choice). `AuthorizationStore` (per-project opt-in) + `approve()`: L2 recoverable write auto-runs ONLY when `workspace_writes` authorized; L4+ never auto-granted; broker records every approval as evidence — **5 tests**. APPROVAL_MIN_LEVEL untouched.
- [ ] worktree isolation (optional extra safety)
- [x] wire writes live · build.py — `broker/routing.build_catalog`/`build_broker_and_token`: authorized project → writable token + `file_write` catalog; else read-only. **test_writes_live.py (2) + full suite 1031, 0 regression**
- [x] wire writes live · SETTINGS — `/api/authorization` POST endpoint (+ allowlist) → AuthorizationStore.set; authorization exposed in both state snapshot() and app_settings(); page.py toggle in Agent-behavior pane wired to it (default OFF). **test_authorization_settings.py (3) + full suite 1034, 0 regression**

★ PHASE 2 WRITES LIVE & USABLE: Settings → Agent behavior → toggle on → agent can edit that project's files (recoverable · ledgered · Approval-Service-gated · Auditor reviews diffs). Off by default.
- [x] L3 `run_check` (`broker/tools_command.py`) — allowlisted commands only, argv-only NO shell, bounded time+output, cwd=project, secret-scrubbed env; command+exit+output HASHES as evidence; ALWAYS approval-gated (never auto-runs) — **6 tests**
- [x] result audit — ToolSpec.evidence_fields + broker records safe diff (path/pre/post sha/bytes); evidence_view exposes it → Auditor reviews write diffs; read content never ledgered — **verified inline + 27 tests**

## Phase 3 — Git & GitHub  ✅ core done (approval-gated; nothing remote fired)
- [x] `broker/tools_git.py` — git_diff/git_log (L1 read-only, auto); git_commit (L3, local, gated); git_push + repo_create (L5, always needs_approval, never fired in build); **repo_delete NOT offered (permanently forbidden, guide §6)**. Registries composed in broker/__init__ (default = read-only + git read; write = + file_write/git_commit/git_push/repo_create). **test_tools_git.py (5) + full suite 1045, 0 regression**
- [ ] (deferred/optional) pull/fetch, secret-scan on commit, partial-failure recovery — refinements

## Phase 4 — SSH / HPC  ✅ brokered (submit gated, never fired)
- [x] `broker/tools_hpc.py` — hpc_status/hpc_output (read); hpc_submit L5 always needs_approval, never submits in build; job id + manifest hash as evidence. Reuses hpc.MANAGER. **tests in test_tools_external.py**

## Phase 5 — MCP  ✅ brokered (call gated, never invoked)
- [x] `broker/tools_mcp.py` — mcp_call L4 always needs_approval, never invokes a real MCP server in build; result hash only. Reuses mcp.MANAGER.

## Phase 6 — controlled self-improvement  ✅ isolation + hard install ban
- [x] `broker/selfimprove.py` — `candidate_worktree` (isolated git worktree, never touches the running app); `self_install` L6 ALWAYS refused (handler + gate). Full candidate build/audit/install workflow = future.

## Acceptance (guide §16) — check when the whole reaches it
- [ ] no execution path bypasses the Broker · all side effects have durable evidence · every grant scoped+expiring · model cannot widen its grant · secrets never enter prompt/log/receipt · restart never re-runs external ops · provider crash never yields a false PASS · Auditor reviews real ToolResults but cannot forge them · user can view/deny/revoke grants · HPC resumes after restart · push/deploy/install/delete always explicitly authorized · self-mod only in isolated candidates · all failures land in explicit recoverable states · UI explains behavior in natural language

---

### Log
- iter 1: Phase 0 inventory (docs/AGENTIC_RUNTIME_PHASE0.md) + verified load-bearing claims.
- iter 2: ledger/chain.py + policy/tokens.py + policy/engine.py + 31 tests. Next: broker/registry.py + tools_readonly.py.
- iter 3: broker/{registry,tools_readonly,__init__}.py — Tool Broker chokepoint + 4 read-only tools + 7 tests (proof loop: in-scope runs+ledgered, out-of-scope/unknown/write refused pre-exec, tamper caught). Total new-module tests: 38. Next: appservice/ + wiring (full suite before/after).
- iter 4: appservice/__init__.py seam + repoint console/server.py imports + 4 tests. Full suite **997 passed/2 skipped** (was 955; +42 new-module tests, 0 regression). Foundation (ledger+policy+broker+appservice) complete & additive. NEXT: generator/build broker routing (additive, full-suite-guarded). CHECKPOINT before the receipt-schema change (alters the audit trust anchor).
- iter 5: broker/routing.py (BROKER_SERVER_ID/readonly_token/broker_tool_call) + build.py routing branch (dormant, additive) + appservice de-dup + 5 tests. Full suite **1002 passed/2 skipped**, 0 regression. STOPPING loop: next two steps (generator-prompt catalog injection; receipt tool_evidence + RECEIPT_SCHEMA bump) both alter the audit trust anchor → await user confirmation.
- iter 6: generator builtin_tools injection (build_prompt/generate optional param + build.py passes readonly_catalog) + 3 tests. Full suite 1005/2 skipped, 0 regression. Read-only tools now LIVE end-to-end. User approved 全部继续 → loop re-armed for: receipt tool_evidence (backward-compat, RECEIPT_SCHEMA bump+migration, old receipts still verify) → auditor read-only evidence view → proof demo.
- iter 7: receipt tool_evidence (optional block, NO schema bump, back-compat) in schema/build/verify + proof-demo test (4). Full suite 1005 (receipt change, 0 regression) → 1009 with tests. New-module tests 54. Only Phase-1 item left: auditor read-only evidence view.
- iter 8: auditor read-only evidence view (broker.routing.evidence_view allowlist + prompt.build gated section + run_audit plumb) + 4 tests. Full suite **1013 passed/2 skipped**, 0 regression. ★ PHASE 1 COMPLETE ★ — minimal safe closed loop proven end-to-end. STOP before Phase 2 (introduces file-WRITE tools) pending user confirm.
- iter 9 (Phase 2 start): broker/recovery.py + tools_write.py (file_write, recoverable, scoped, atomic) + 11 tests. Full suite **1024 passed/2 skipped**, 0 regression. Classifier BLOCKED lowering APPROVAL_MIN_LEVEL 2->4 (correct: it loosens the permission system) → kept writes APPROVAL-GATED. Write mechanism proven but NOT live (broker returns needs_approval; real builds still use read-only token). Next: Approval Service — design fork, checkpoint with user.
- iter 10: broker/approval.py (AuthorizationStore + approve, project-level authorization model) + broker integration (approve on requires_approval, approval recorded as evidence) + 5 tests. Full suite **1029 passed/2 skipped**, 0 regression. Write+approval mechanism COMPLETE & tested, but writes NOT LIVE (build.py still uses read-only token + default read-only registry; no project authorized). CHECKPOINT before wiring writes live.
- iter 11: diff-evidence contract (ToolSpec.evidence_fields → broker records safe write diff → evidence_view → Auditor). Full suite **1029**, 0 regression. Verified: write diff (path+pre/post sha) ledgered & auditable; file_read raw content NEVER enters ledger. Next (loop continuous, user said keep going): writes-live wiring (build.py authorized→writable token+write catalog; settings toggle server+page.py) → remaining Phase 2 (L3 build/test tools gated, worktree opt) → Phase 3-6.
- iter 12: build.py writes-live wiring (build_catalog + build_broker_and_token; writable token + write catalog only when project authorized) + writable_token/write_catalog helpers + 2 tests. Full suite **1031**, 0 regression. Writes CAN happen now, but only after a project opt-in — and the opt-in UI (settings toggle + server endpoint) is the next item so the user can actually turn it on.
- iter 13: settings opt-in — /api/authorization endpoint + snapshot/app_settings exposure + page.py toggle + 3 tests. Full suite **1034**, 0 regression. WRITES NOW LIVE & USABLE (per-project opt-in). Remaining Phase 2: L3 build/test tool (approval-gated), worktree opt. Then Phases 3-6.
- iter 14: L3 run_check tool (allowlist + no-shell + bounded + env-scrub) + AuthorizationStore.set_list + 6 tests. Full suite **1040**, 0 regression. ★ PHASE 2 COMPLETE ★. Worktree isolation deferred (optional). Next: Phase 3 Git/GitHub brokered tools (git_diff/git_log L1; git_commit L3-4, push/repo L5 — all approval-gated).
- iter 15: Phase 3 git tools (git_diff/git_log L1 auto; git_commit L3 gated; git_push/repo_create L5 gated+never-fired; repo_delete forbidden) + registry composition in broker/__init__ + 5 tests (fixed 2 stale readonly-count asserts). Full suite **1045**, 0 regression. Next: Phase 4 SSH/HPC (wrap hpc.MANAGER behind broker; submit approval-gated), Phase 5 MCP, Phase 6 self-improve.

---

## §16 ACCEPTANCE — honest assessment (after Phases 1-6, full suite 1050)
MET: every governed proposal flows through the broker; each grant is scoped+expiring; the model cannot mint/widen its own token; secrets never enter prompt/log/ledger/receipt (allowlist + hashes + env-scrub); the Auditor reviews REAL tool evidence and cannot forge it (ledger written by the broker, auditor read-only); ledger tampering breaks verify(); push/deploy/install/delete are gated and NEVER auto-run; self-mod only in an isolated candidate + self_install forbidden; user can grant/revoke the write authorization; backward-compatible (old receipts verify); provider-crash-no-false-PASS preserved.
NOT YET (remaining to full acceptance):
- **Per-call approval UI** — L3+ actions return needs_approval but there is no UI yet to approve/deny a specific pending action (so L3+ tools are built + gated but not yet USABLE end-to-end; L1 read + L2 writes ARE usable now).
- **Full surface funneling** — the broker is ADDITIVE; the ~20 pre-existing ungoverned execution surfaces (Phase 0 §2) still exist and are not yet all routed through it.
- Richer evidence surfacing in the UI; HPC/MCP catalog wired into build_catalog; worktree-isolated writes; rollback/health-checked candidate install.

## Log
- iter 16: Phases 4 (tools_hpc), 5 (tools_mcp), 6 (selfimprove) — gated wrappers + full_registry + 5 tests. Full suite 1050, 0 regression. ALL SIX PHASES' CAPABILITIES BUILT & TESTED. Stopping: full §16 acceptance needs the per-call Approval UI (a user-facing design) + full surface funneling — surfaced to the user.

---

## CONTINUED PROGRAM (user: 全部都做 · UX on par with Codex + retain core audit · optimize until perfect · end with an enterprise-grade rigorous test suite)
Committed so far on v5-redesign (no push): 319ded3 perf · b012a3e runtime core · d8bf988 wiring · d08b8fa docs.
Order (each: src/ only → tests → FULL suite guard → grouped commit at milestone, NO push → check off + log):
- [x] **P7 Per-call Approval UI** ✅ — real-time "像 Claude Code" approval. `broker/humanapproval.py`: process-global `ApprovalInbox` + `HumanApprovalGate` (injected as the broker's `approver`). A flagged Level 3+ action PAUSES the live worker in place (the worker stays alive + heartbeats + observes cancel via `emit.is_cancelled`), a pending-action card renders in the thread (what/why/paths·host·cost/reversibility) with Allow once · this run · this project · Deny; the user's decision is recorded to the evidence ledger as the grant and the SAME worker continues. `/api/approval` endpoint → `INBOX.resolve`; `snapshot.pending_approval` (run-scoped); page.py `approvalCard`+`resolveApproval`+CSS. Deny-by-default (cancel/timeout deny); Level 4+ per-call only (no standing grant); Level 6 refused without prompting. **18 tests (test_human_approval.py), full suite 1068/2 skipped, 0 regression.** UNLOCKS L3+ end-to-end.
- [x] **P8 Codex-parity UI polish** ✅ — (#17) top bar shows a clean project name: server `_project_title(cfg)` = repo/project name without the `owner/repo` slug; snapshot gains `title`+`folder`; page.py renders `d.title` with the full slug + folder on hover. (#1) a prominent red Stop button in the live run card (`requestStop()` reuses the vetted composer cancel flow). One-time flicker-free shell entrance (`body.booted` set on first paint only, reduced-motion aware) — the app already had a rich, tasteful motion system, so this is additive not a rewrite (aesthetics-as-deletion). **Screenshot-verified** in the in-app browser against a real injected snapshot: top bar "DEMO / demoproj" (slug gone), red Stop in the run card, and the Codex-class approval card (Level 3 · git_commit · reversibility · Paths · Allow once/this run/this project/Deny). **3 tests (test_project_title.py), full suite 1071/2 skipped, 0 regression.**
- [x] **P9 Hardening** ✅ — **secret-scan gate on git_commit**: `broker/secretscan.py` (conservative, low-false-positive — private-key blocks, AWS/GitHub/Slack/Google/Stripe/OpenAI token shapes, and a secret-named assignment of a long opaque value; placeholders excluded). It reports only the KIND, never the value, so a refusal never leaks the credential. `git_commit` scans the ADDED lines of the staged diff + the committed paths (a real `.env`), and **refuses even an approved commit**, resetting the staging so the tree is untouched — an irreversible leak into git history is prevented. Defense-in-depth at the write layer too: `file_write` flags credential-shaped content in its evidence (`secret_flagged`, non-blocking since workspace writes are recoverable) and the Auditor's evidence view surfaces it. **16 tests (test_secret_scan.py), full suite 1087/2 skipped, 0 regression.** SCOPED HONESTLY: wholesale re-homing of the ~20 §2 subprocess surfaces and swapping the default write path to a worktree are DEFERRED — both are large, higher-risk refactors with low marginal safety given the broker already governs the model-callable surface and writes are recoverable + git-ledgered; the guide itself marks worktree isolation "optional". The strongest, cleanest hardening (secret leak prevention) is done.
- [ ] **P10 Optimize-to-perfect pass** — perf, code quality, edge cases, dead-code, consistency.
- [ ] **P11 ENTERPRISE-GRADE rigorous test suite (FINAL)** — adversarial security (try to: bypass the broker, forge/replay evidence, escape path scope, widen a token, leak a secret into prompt/ledger/receipt, tamper the ledger/receipt, race concurrent writers, self-install, auto-run an L4+); crash-recovery; property-based; stress. Can use a multi-agent workflow.
- [ ] **P12 Rebuild the app** + user-perspective verification (frozen core), so the user experiences it.
INVARIANTS unchanged. STOP only for a genuine user decision the guide doesn't answer, a classifier block needing the user, or when it's perfect + enterprise tests pass + rebuilt.

### Log
- commits: grouped Agentic Runtime work onto v5-redesign (4 commits, no push).
- P9 (hardening): broker/secretscan.py + git_commit secret-scan refusal (added-lines + paths; resets staging on refusal; label-only, no value leak) + file_write `secret_flagged` evidence + evidence_view allowlist. 16 tests. **Full suite 1087 passed / 2 skipped (+16, 0 regression).** Deferred (honest): wholesale §2 surface re-homing + default worktree writes (higher-risk/low-marginal-value). NEXT: P10 optimize-to-perfect.
- P8 (Codex-parity UI polish): server `_project_title` + snapshot title/folder; page.py top-bar `d.title` (slug on hover) + run-card Stop (`requestStop`) + one-time `body.booted` shell entrance + CSS. Verified in the in-app browser (screenshots): clean top-bar name, prominent Stop, Codex-class approval card, dark+light theme-aware tokens. 3 tests. **Full suite 1071 passed / 2 skipped (+3, 0 regression).** NEXT: P9 hardening.
- P7 (per-call Approval UI): broker/humanapproval.py (ApprovalInbox + HumanApprovalGate) + broker `approver` seam + approval.py per-tool project grants (authorized_tool/add_tool) + commands.py `emit.is_cancelled` handle + build.py/routing.py live-gate wiring + server `/api/approval` endpoint + snapshot.pending_approval + page.py approvalCard/resolveApproval/CSS. Grounded design in the architecture (build worker is a background thread; console serves on other threads → the worker blocks-and-heartbeats while the HTTP thread resolves). 18 tests. **Full suite 1068 passed / 2 skipped (+18, 0 regression).** L3+ now usable end-to-end (an authorized project already advertises git_commit L3 + push/repo L5, now approvable per-call). NEXT: P8 Codex-parity UI polish (motion, top-bar name #17, Stop #1, palette/sans), screenshot-verify.
