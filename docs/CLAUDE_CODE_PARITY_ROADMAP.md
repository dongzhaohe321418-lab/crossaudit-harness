# CrossAudit → Claude Code parity roadmap

North star: make CrossAudit a harness at parity with Claude Code in **UI quality
AND functionality** — *especially functionality*. Produced by a multi-agent study
(2026-08) of Claude Code's app functionality mapped against CrossAudit's console.

## The core finding

CrossAudit's biggest gap is **functional, not visual**: it is an *audit engine +
console*, not a *tool-execution harness*. It lacks a first-class audited
file/shell/search toolset, graduated permission modes + a plan gate, a
user-authored hook layer, todo/subagent decomposition, context compaction, a
connectors/plugins ecosystem, a memory hierarchy, and a standing multi-scope
settings IA.

**The strategic unlock:** every one of these can be built *as audited provenance*
— each tool call, hook firing, mode transition, and approved-plan hash becomes a
ledger row — so reaching parity **strengthens** the non-bypassable audit core
rather than diluting it. The audit identity (generate → commit → independent
cross-vendor audit → signed ledger receipts, per-call approval, deterministic
non-overridable checks) stays fixed and outside every item below.

## Red lines (never cross)

1. **No bypass mode.** Do not port `bypassPermissions` / `dangerouslyDisableSandbox`.
   A low-friction mode may auto-approve prompts but must STILL emit receipts and
   STILL run the independent auditor. CI/headless = audited, never un-audited.
2. **Hooks never reach the audit gate.** User hooks fire only around tool calls
   and commits; they can never disable, skip, reorder, or mutate the auditor or
   the Git ledger.
3. **Single-auditor independence (I1).** Subagents are intra-*generator*
   delegation only — never a second auditor; never collapse the generator↔auditor
   vendor split. Output styles are cosmetic narration only.
4. **Auditor blindness.** Skills, MCP tool chatter, and memory never reach the
   auditor — it sees only the committed artifact. New memory/connectors/skills
   surfaces keep deny-by-default (only what `crossaudit.yml` names loads),
   per-tool human approval, and bounded results.

## Already shipped (this session, branch v5-redesign)

- Audit-loop **de-jargon** (plain status words, muted rule ids, friendly labels).
- **Add-MCP dialog** layout fix; **Manage Skills** routing fix.
- **Font discipline** (monospace reserved for hashes/code).
- **Project-card** redesign (hover-revealed row actions, breathing room).
- Reusable **`.dt` data table** + Skills rendered as a table.
- `run_check` orthogonal outcomes (`timed_out`/`signal`/`exit_code`) — DeepSeek R1.

## Quick UI wins (primitives exist — extend, don't rebuild)

- Finish the mono-font audit across the ~40 `--font-mono` selectors.
- **Settings shell → Claude Code style** (M): standing tabbed surface, grouped
  left-nav scope headers, table-first right panes (reuse `.dt`), top-right
  Search / Browse / Add / close cluster.
- **Extend `.dt`**: add Last-updated / Author columns + sort; apply to the
  MCP-tools view; retire dead `.skill-row` CSS.
- **Connectors**: All/Connected/Not-connected filter pills, inline Connect,
  real product-logo SVGs.
- Theme audit (light/dark) for every new surface.

## Functional roadmap (ordered; the real parity work)

1. **Audited first-class file-mutation toolset** (L ~3–4wk) — Read / Edit / Write
   as harness tools: Read-before-Edit, exact unique-match Edit (fail closed),
   Write guard against un-Read overwrite, in-session file-state tracking. Each
   mutation → a ledger evidence row + exact pre/post to the auditor. *The single
   largest true gap.*
2. **Audited Bash/exec tool** (L ~2–3wk) — persistent cwd, bounded per-call
   timeout, background/detached execution, sandbox toggle; every command+exit+
   output a signed replayable ledger row.
3. **Graduated permission modes + plan→approve gate** (L ~2–3wk) — Plan
   (read-only), acceptEdits, per-tool allow/deny in `crossaudit.yml`; an
   ExitPlanMode analog whose approved-plan hash is written into the receipt as
   audited intent; every mode transition recorded.
4. **User-authored hook layer** (M ~1–2wk) — deterministic Pre/Post Tool/Commit
   hooks in `crossaudit.yml`, harness-executed, veto by non-zero exit, hashed
   into the receipt. (Never around the audit gate — red line 2.)
5. **Todo list + scoped subagent delegation** (M ~1–2wk) — a rendered todo tool;
   user-defined generator subagent types (scoped dirs, allowed tools, model) for
   bounded isolated sub-tasks returning committed artifacts.
6. **Search/Glob primitives + NotebookEdit** (M ~1wk) — ripgrep/glob as dedicated
   audited tools (no unaudited shell escape); cell-level notebook edits.
7. **Context compaction with receipt continuity** (M ~2wk) — auto-compact long
   conversations preserving task/file-state/todos AND ledger-chain continuity
   (never orphan or rewrite prior receipts).
8. **Connectors catalog + plugin bundle format + marketplace** (L ~3–4wk) — a
   Connected/Not-connected gallery on the existing MCP host + OAuth lifecycle;
   generalize the check-pack plugin system into a bundle (skills + checks +
   MCP + slash-commands) with a versioned handshake + add-by-URL marketplace.
9. **Skills browse/add + authoring** (M ~1–2wk) — in-console discover/add/
   enable/version for skills + check packs; a skill-creator equivalent.
10. **CLAUDE.md-style memory hierarchy** (M ~1–2wk) — auto-loaded root/subdir/
    global instruction files with precedence + @-imports, committed & hashed;
    default generator-only (auditor-blind unless a dated hashed amendment).
11. **Standing multi-scope settings IA** (L ~3–5wk) — the sections that outlive a
    run: a **Usage/metering** view (audits, tokens/cost, tier usage, quotas —
    the strongest audit-runtime parity feature); promote the strictness dial into
    a persistent **Capabilities** catalog; Account/Billing/Privacy; Developer/MCP
    + connection logs. The setup wizard becomes an onboarding funnel into these.
12. **Richer tool-call & diff rendering** (M ~1wk) — compact tool-call blocks +
    full unified diffs for the new file toolset, so every mutation reads as
    plain evidence.

## Baseline checks before building each item

Re-read the current contracts (they were described from `crossaudit_v4`): `mcp.py`,
`skills.py`, `dcl/plugins.py` (the `crossaudit.checks` entry points),
`connections.py`, `providers/registry.py`; and find the real project-list
selectors in `projects.py`. The console is split (`page.py` + `chats.py` /
`overview.py` / `projects.py` / `daemon.py`), not a single string — locate each
surface before editing.
