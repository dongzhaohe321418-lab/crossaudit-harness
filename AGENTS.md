# AGENTS.md — working agreement for AI coding agents on CrossAudit

This file is the contract every AI agent working on this repo reads first —
whether it is Claude Code, Codex, or anything an orchestrator ("herdr") drives.
It exists so two agents can collaborate without stepping on each other **and**
without either one grading its own homework.

CrossAudit's entire thesis is *independent, cross-vendor audit — no agent blesses
its own output.* We build the product by living that rule ourselves.

---

## 0. The one law

**No agent merges a change it wrote without an independent review by the other
agent.** The reviewer reads the diff cold, runs the suite, and (for a UX change)
runs the UX walkthrough. Self-review is not review. This is the generator /
auditor separation the product is built on, applied to us.

---

## 1. Hard invariants (never violate; a change that needs to is a conversation, not a commit)

1. **The audit core is non-bypassable.** The independent cross-vendor Auditor
   sees *evidence only* and is blind to the generator's chain-of-thought (P2);
   deny-by-default; the append-only hash-chained Evidence Ledger; signed
   receipts; allowlist-only loading (no arbitrary code); secrets never enter a
   prompt/log/ledger/receipt; single-auditor independence. Do not weaken any of
   it. Bounding on the auditor side may only ever become *more* fail-closed
   (overflow ⇒ ESCALATE, never PASS).
2. **Additive / backward-compatible.** Old receipts and ledgers still verify;
   every existing test stays green. A deliberate contract change needs a stated
   reason in the commit and updated tests — never a silent break.
3. **Frozen, offline app.** It ships as a PyInstaller macOS app, ad-hoc signed,
   working with no network at rest. **Standard library only** — no new native
   dependency (no faiss/chroma/torch/numpy/tree-sitter/…) unless it is raised as
   an explicit decision. Reuse the already-configured provider; never add a model
   or vector DB.
4. **Scope.** Touch `src/` and `tests/` only. Do not push, publish, or deploy
   beyond a local rebuild + reinstall. No new remote calls.
5. **Never overclaim.** Report what is actually true — failing tests, skipped
   steps, known limits. A docstring or a UI string that promises more than the
   code delivers is a bug (we have already been bitten by this).

---

## 2. Collaboration model — **Hybrid** (the chosen model)

- **UX surface work runs in parallel on disjoint files.** The two agents each
  own a surface and do not edit the same file at the same time. Cross-review
  happens at merge.
- **Audit-core work is always cross-reviewed before merge**, no matter who wrote
  it. This is the sensitive half; two sets of eyes is mandatory.
- **Every change is UX-tested by the agent that did NOT write it**, following
  `docs/UX_TEST_PLAN.md`.

### Ownership map (adjust per task in the change contract)

| Surface | Notes |
|---|---|
| Console UI — `console/page.py` (markup/CSS/JS, i18n), decision center, settings, audit-loop display, MCP/skills dialogs, usage view | The largest UX surface. One agent owns a given slice end-to-end. |
| CLI + `console/` server/daemon/streams/chats/projects | Separable surface; good for the *other* agent to own in parallel. |
| **Audit core** — `auditor/`, `broker/`, `ledger/`, `policy/`, `dcl/`, `receipt/`, `controller/` | Either may write; the other MUST independently review before merge. |
| Context shaping — `context/`, `generator.py`, `cli/build.py` (prompt assembly) | Generator-side; review for determinism + recall-safety + the invariants above. |

---

## 3. Workflow mechanics (how to not collide)

1. **One branch or git worktree per task.** Never two agents editing the same
   file on the same branch concurrently. Shared files (e.g. `page.py`) are
   handled by **sequential handoff**: implement → hand off → independent review →
   fix, not simultaneous edits.
2. **Coordinate through git + a task ledger**, not out-of-band chatter. The task
   ledger is the source of truth for who owns what and what state it is in.
3. **Every task carries a change contract** (template below) so the reviewer can
   score it without reconstructing intent.
4. **Commits** end with the co-author trailer the orchestrator requires, name the
   invariant they were careful about, and state test results honestly.
5. **Tests:** `PYTHONPATH=src .venv/bin/python -m pytest -q` (full suite ~3 min).
   A change is not done until the full suite is green.
6. **See it work:** rebuild + reinstall the frozen app with
   `PYTHON_BIN=python3 bash packaging/macos/build_dmg.sh`, then install to
   `/Applications` and relaunch. For UI iteration, drive the source-mode console
   (`crossaudit console` prints a token'd URL) — see the UX test plan.

### Change contract (paste into the task, fill before writing code)

```
TASK:        <one concrete instruction — one deliverable>
SURFACE:     <files/area; is the audit core touched? y/n>
INVARIANTS:  <which of §1 this change is closest to; how it stays safe>
ACCEPTANCE:  <objective, checkable pass conditions>
UX EVIDENCE: <before/after screenshots or the console-error/network proof>
REVIEWER:    <the OTHER agent; must be independent of the author>
```

---

## 4. Definition of done

- Full suite green; new behavior has a test; a bug fix has a regression test.
- If the audit core was touched: an independent adversarial review confirms it is
  *strictly more* fail-closed and byte-identical for in-bound inputs.
- If a UX surface changed: the non-author ran the relevant scenarios in
  `docs/UX_TEST_PLAN.md`, in light **and** dark, and attached screenshots.
- The commit states, honestly, what was done, what was deferred, and why.

---

## 5. Off-limits without an explicit human decision

Weakening the audit core; adding a native/non-stdlib dependency; a model-based
summarizer or any nondeterminism in the deterministic paths; pushing/publishing;
changing the receipt/ledger format non-additively; capping or truncating the
generator's view of the rules (RULES) — the user's governing document.

When in doubt, escalate to the human. That is not a failure; it is the product.
