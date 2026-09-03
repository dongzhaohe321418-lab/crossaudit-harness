# Contributing to CrossAudit

Thank you for looking under the hood. CrossAudit is a dual-source audit
harness: the product's own rule, that no model blesses its own output, is also
how the project is built. Every change is reviewed by someone who did not write
it, and the audit core only ever becomes more fail-closed. This page tells you
how to run the suite, what is off limits, and how a change is expected to look.
`AGENTS.md` is the longer working agreement; `docs/DECISIONS.md` is the record
of why things are the way they are.

## Run the suite

```bash
git clone https://github.com/dongzhaohe321418-lab/crossaudit-harness.git
cd crossaudit-harness
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
python -m pytest -q --timeout=30
```

That installs the same wheel layout users receive, which is what CI tests on
Python 3.10 to 3.13 across Linux, macOS, and Windows. While iterating on
source, run against the tree instead of reinstalling after every edit:

```bash
PYTHONPATH=src python -m pytest -q --timeout=30            # full suite, about 3 minutes
PYTHONPATH=src python -m pytest -q tests/test_repair_guard.py   # one file
```

The suite needs Git on `PATH` and a Git identity (`git config user.name` and
`user.email`); it needs no network, no provider key, and no Keychain entry. A
test that reads the developer's Keychain is a bug (D150): tests set placeholder
credentials themselves.

Two more gates run in CI and are worth running before you open a pull request:

```bash
python -m ruff check --select E9,F63,F7,F82 src tests   # syntax, undefined names, control flow
python -m coverage run -m pytest -q --timeout=30 && python -m coverage report
```

The website under `website/` has its own toolchain; see `website/README.md`.

## The audit core is additive only

`AGENTS.md` section 1 is the contract. In short:

- **Non-bypassable.** The cross-vendor auditor sees committed evidence only and
  never the generator's reasoning; policy is deny by default; the evidence
  ledger is append-only and hash-chained; receipts are signed; secrets never
  enter a prompt, log, ledger, or receipt. Do not weaken any of it. A bound on
  the auditor side may only become more fail-closed: overflow escalates, it
  never passes.
- **Additive and backward compatible.** Old receipts and ledgers keep
  verifying byte for byte; every existing test stays green. A deliberate
  contract change states its reason in the commit and updates the tests. A
  silent break is not a change, it is a regression.
- **Standard library only in the core.** The app ships frozen and works with no
  network at rest. A new native dependency is a decision, not a commit.
- **Never overclaim.** A docstring, a UI string, or a README sentence that
  promises more than the code delivers is a bug.

The verdict ladder in `auditor/run.py` is the only place a verdict is
synthesised. New evidence layers derive from its result; they do not replace
it (D148).

## A guard is specified with its mutation (D10)

A test whose job is to guard a property must be shown to fail. Write the
guard, break the product on purpose, watch the guard catch it, and record in
the test which mutation you used, so the next person can re-check it. A test
that inspects source text may not claim to pin rendered behaviour: if the
property is "the page never says X", render the page and assert over the DOM.
If the claim is that a class of input is refused, construct the inputs and run
them. A guard that cannot be made to fail is not a guard, whatever it is named.

Some properties are semantic and cannot be guarded mechanically. When a guard
has been defeated three times, ask whether the property is decidable at all;
if it is not, replace the guarantee with one that is (an approval fixture a
human re-reads, for example) and name the test for what it now does.

## Decision records

`docs/DECISIONS.md` holds numbered entries, `## D<n> — <the ruling in one
line>`, each stating what was decided, what was considered and rejected, and
what was deliberately left open. Add an entry when a change settles a question
that a later reader could otherwise reopen by accident: a default, a boundary,
a rule about what a test may claim, a product-level trade-off. Routine work
does not get an entry. Decisions that belong to the owner (defaults that move
strictness, anything in `AGENTS.md` section 5) are listed for the owner in the
entry rather than taken.

## Adding a Chinese string

The complete interface is bilingual and the tests enforce it. Where a string
lives decides where its Chinese goes:

| Surface | English | Chinese | Guarded by |
| --- | --- | --- | --- |
| Console (markup, JavaScript, `aria-label`, `title`) | the literal in `src/crossaudit/console/page.py` | the `ZH` map in the same file, keyed by the exact English | `tests/test_console_translation_boundary.py`, `tests/test_projects_ui.py` |
| Server-side literals the console renders | Python in `src/crossaudit/console/` | the same `ZH` map; the translator runs over rendered text | `tests/test_console_translation_boundary.py` |
| CLI prompts, wizard, `--help` | `t("key")` in `src/crossaudit/cli/` | `CATALOGUE["zh"]` in `src/crossaudit/cli/i18n.py` | `tests/test_cli_i18n.py`, `tests/test_language_is_reachable.py` |
| Refusals (`Denial.reason`) | the reason string at the raise site | `src/crossaudit/cli/denials_zh.py`, keyed by the exact English; `{}` slots carry interpolated identifiers through | `tests/test_denial_strings_are_legible.py` |

Rules the tests check: identifiers, config keys, flags, commands, verdict words
(PASS, BLOCKED), and file names stay Latin; a template keeps every `{}` slot;
an entry whose English is raised nowhere is refused, so remove the Chinese when
you remove the English. Terminology follows the existing catalogues
(生成者 / 审计者, 收据, 判定, 账本, 准入, 章程, 周期, 轮). The user-facing
`README.md` deliberately stays English only; do not add a `README.zh-CN.md`.

## Pull requests

- One branch per change; state the invariant you were careful about and the
  test results honestly, including anything skipped.
- New behaviour has a test; a bug fix has a regression test with its mutation
  named.
- A change to the audit core (`auditor/`, `broker/`, `ledger/`, `policy/`,
  `dcl/`, `receipt.py`, `repair_guard.py`) needs an independent review that
  confirms it is strictly more fail-closed and byte-identical for in-bound
  inputs.
- A user-visible string lands in both languages in the same change.
- `CHANGELOG.md` gets a line under the unreleased version for anything a user
  can notice.

Security issues go through `SECURITY.md`, not the issue tracker.
