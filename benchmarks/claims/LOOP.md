# The claims loop — does the product do what the README says, and if not, fix it

Each round: run `run.py` on a ref, record every FAIL/PARTIAL with evidence, fix
on a branch, run again. A round is closed when the results file for the fixed
ref is committed beside the one for the ref it started from. The harness is
held to the same standard as the product: when a row's expectation turns out
to be the harness's wording rather than the README's sentence, the row and
`CLAIMS.md` are corrected in the open and the earlier refs are re-run with the
same harness version, so every score in a round comes from one harness.

## Round 0 — baseline (2026-10-21, harness cf11bef)

| ref | PASS / 31 | PARTIAL | FAIL |
|---|---|---|---|
| `main` 1f6120e (what `pip install …@main` gives a user) | 19 | C03 C04 C09 C10 C15 C19 C20 C21 C25 C28 | C13 C18 |
| `fix/truncated-output-and-ledger-splitlines` ba202d6 | 20 | same ten | C18 |

Twelve sentences the product did not keep, grouped by what they were about:
a cut-off reply committed as a complete file (C13); the README's own
export-then-verify command pair crashing, an invalid signature exiting 0, a
deleted signature file unnoticed (C18); `doctor` writing state (C04); the
README's `build` → `audit --offline` flow refused because HEAD is a ledger
commit (C10); a changed `report.md` on disk still "verified" (C15); a lock
file already in the tree not recorded by the receipt (C19); `build` never
returning the provider exit code (C20); `--json routing` printing prose (C21);
the `resolve` reason never reaching git (C25); `console` opening no browser
(C28); the default check pack not the one the README lists and non-interactive
`init` silent about where keys come from (C03); and the wording drifts in C01,
C09, C16, C26.

## Round 1 — fixes (2026-10-22), integration branch `fix/claims-round-1` 5855d22

Four branches, one engineer each, merged in order; conflicts were only the
additive CHANGELOG/DECISIONS hunks:

| branch | record | what it closed |
|---|---|---|
| `fix/claims-round-1a` | D169 | loopback HTTP immune to proxy variables (product + suite); an input the auditor is never shown ends ESCALATE/BLOCKED, never PASS (I8); `AuthorizationStore` serialises its writes; a decimal comma is not a thousands separator; the escalation-ruling path pinned end to end |
| `fix/claims-round-1b` | D170 | non-provider children (git, gh, ssh, Codex) no longer inherit provider keys; a Codex turn with a tool event fails closed; the console CSP pins its two scripts by hash (three inline handlers moved); SECURITY.md says what the token authorises |
| `fix/claims-round-1c` | D171 | `export-pubkey` writes only the PEM; invalid or (when pinned) missing signatures exit 21; the signed predicate carries the real verdict and report hash; `verify` reports working-tree drift of the cycle files it binds (`--record-only` for the record alone); locks already in the audited tree are bound as `reproduction.tree_locks` and printed by `reproduce` |
| `fix/claims-round-1d` | D172 | `doctor` read-only; `audit`/`run` default to the latest increment commit and never overwrite a recorded cycle (main overwrote a PASSED cycle on re-audit — a data-loss defect in its own right); `build` exit codes from one table (22 provider, 11 other parks, 0 PASS); `--json` always JSON; `resolve` appends `cycles/rulings.jsonl` and commits it, `status` shows the ruling; `console` opens the dashboard at a terminal, `--no-open`; README corrections (default pack, non-interactive keys, `amend --yes`, the real `--version` line, PASS vs PASSED, the custom-endpoint message and `base_url:` example) |

Harness corrections made in this round, in the open: C03 reads the README's
first "Deterministic checks" table at the ref under test instead of a fixed
list, and accepts an init message naming the key variables in place of a keys
file; C09/C20 read `build`'s exit as the loop's final state (11 when a
check-blocked round spends its budget, 22 for a provider failure), which is
what the corrected README says; C13 accepts 22 as that provider failure; C19
accepts `reproduction.tree_locks`; C28 judges "opens the dashboard" under a
pseudo-terminal and checks `--no-open`.

| ref (same harness) | PASS / 31 | PARTIAL | FAIL |
|---|---|---|---|
| `main` 1f6120e | 20 | C03 C04 C10 C15 C19 C20 C21 C25 C28 | C13 C18 |
| ba202d6 | 21 | same nine | C18 |
| **`fix/claims-round-1` 5855d22** | **31** | — | — |

Full suite on 5855d22: 4414 passed, 8 skipped, 0 failed (7 min 56 s); ruff
E9/F63/F7/F82 clean; D167–D172 contiguous.

## What round 1 could not close, and what it cost

- **C32–C36 stay UNTESTED here.** The macOS app (a built DMG and a person at
  the screen), the GitHub two-repository flow (an account), SSH/Slurm and MCP
  (a host, a server), the published benchmark sentences (the archived runs and
  their review), and the auditor's quality on real work (live models and money)
  all need something this harness does not have. Round 2 takes the parts that
  can be had: building the DMG and running its self-test, `pair` in plan mode,
  and a stdio MCP server faked with the standard library.
- **Trade-offs the fixes introduced, stated as the records do:** any increment
  that carries a file the auditor cannot read (a PNG, an `.xlsx`, an `.npz`)
  now escalates every round, because I8 says an unread input can never PASS —
  a figure-bearing deliverable needs a person, or a readable form, until the
  document layer learns to describe images (D169); a receipt that carries
  `tree_locks` is refused by a verifier older than D171 (the receipt schema is
  strict); a Codex turn that touches any tool is now refused outright rather
  than annotated (D170); `build` returning 22 for a provider park changes a
  script-visible exit code (D172).
- **Deferred by the engineers, in their decision records:** a code gate on what
  the console token may do (MCP registration, allowed commands) is the owner's
  call (D170); the console's own decision screen still records rulings without
  writing the ledger (D172); `verify()` as a library and the console admit path
  do not run the working-tree comparison, only the CLI does (D171); the
  `AuthorizationStore` lock covers one process (D169); provider calls to a
  loopback endpoint still honour the proxy (D169); a configured `key_env` of an
  unusual shape is not stripped from children (D170).
- **Still open from the 2026-10-21 review and not in this loop's scope:** the
  ledger's tamper evidence against an editor who recomputes digests; gitlink
  submodules silently skipped; signature TOFU without `--pubkey`; the unenforced
  `CapabilityToken` fields; canonical JSON being CPython-specific; the
  `numbers.py` quadratic path; HTTP server socket timeouts; the engineering
  items (CI breadth, release automation, repository hygiene).

## Round 2 — opened 2026-10-22

Items: (1) build the DMG from 5855d22 with `packaging/macos/build_dmg.sh`
and run `verify_dmg.sh` and the frozen core's self-test (C32's automatable
half); (2) extend the harness with `pair` plan mode (C33a) and a stdlib stdio
MCP server driven through the documented consent flow (C34a); (3) the
`science-ai4s` pack's gaps found by a dogfood audit of a real report
(`~/Claude/crossaudit-dogfood/REPORT.md` §3: `where` on several columns,
ratio / percent change / population sd / median, byte-exact unit comparison,
trailing-zero `repr` in quotations), measured again on the AI4S test set.

### Round 2, item 1 — the DMG (C32a), 2026-10-22

Built from `fix/claims-round-1` at 1caddd3 on this Apple Silicon machine with
`PYTHON_BIN=/opt/homebrew/opt/python@3.13/libexec/bin/python3 bash
packaging/macos/build_dmg.sh`: PyInstaller froze the core, the pinned Codex
runtime (97.8 MB) was fetched and its SHA-256 checked, the app was ad-hoc
signed, the frozen core's self-test ran before signing, and
`packaging/macos/verify_dmg.sh` reported "Verified CrossAudit 4.17.0 DMG,
signature, architecture, and frozen runtime" (exit 0). Output:
`dist/CrossAudit-4.17.0-arm64.dmg`, 152,216,936 bytes; its `.sha256` is in
`records/round-2/evidence/C32a/` beside the full build log. **C32a (build +
self-test) PASS.** C32b — a person installing it and walking
`docs/UX_TEST_PLAN.md` — stays untested here.

Two things the build found: (1) with `PYTHON_BIN` unset the script takes the
system `python3`, which on this macOS is 3.9.6 and below the package's floor,
so the build fails at `pip install` — the README's "./packaging/macos/
build_dmg.sh" needs a 3.10+ interpreter named; (2) a `build/macos/venv` left by
an earlier run with the wrong interpreter is reused silently, so the second
attempt with the right `PYTHON_BIN` failed the same way until `build/macos`
was removed. Both are fixed on the integration branch in the next commit
(the script now recreates the venv when its interpreter's major.minor differs
from `PYTHON_BIN`'s, and refuses an interpreter below 3.10 with a sentence).
The built app still reports 4.17.0 although the tree carries D167–D172; a
release from this tree needs the version bump the release checklist describes.
