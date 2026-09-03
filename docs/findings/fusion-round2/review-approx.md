# Review: 61a6b58 "Let `approximately` mean approximately" (fix/approximately-means-approximately)

Worktree: /private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/wt-review-approx
Fusion base: 50349f9. Merge base: 3af0317.

## Verdict: NEEDS CHANGES (wording defects and an overstated reach claim; no kernel or merge problem)

## What the change is

Four files, +160/-3. The only production change is the text of the `criterion`
string in `universal_task_rule()` (`src/crossaudit/constitution.py:96-118`): the
sentence "A length stated approximately must be within 5%" is replaced by "A
length stated approximately is a guide, not a threshold: note it as ADVISORY only
if the artefact departs from it by more than a quarter, and never raise it as a
BLOCKER. Someone who writes 'about 300 words' has chosen a word that does not make
313 wrong." The rest of the rule (BLOCKER severity, exact-must-match, missing/
substituted/extra/materially-noncompliant blocks) is unchanged.

This is model-facing rule text, not a deterministic check. Nothing under
`auditor/ broker/ ledger/ policy/ dcl/` is touched (`git show --stat`). No code
parses "approximately", "5%", or lengths anywhere in `src/` (grep: only the
constitution string and unrelated usage.py/controller comments). The previously
"failing" input (313 words for "about 300") was ruled a false positive by the
owner in D141 (verified claim table) and D142 (sequencing item 3: "CA-TASK-001
must relax"), so this is an authorized narrowing, not a kernel weakening.

## 1. Tests

Import check: `crossaudit.__file__` -> worktree `src/crossaudit/__init__.py` (not the stale venv copy).

- Touched tests (`test_approximately_means_approximately.py`, `test_router_and_constitution.py`): 46 passed.
- `pytest tests -k "dcl or check or schema or approx"`: 86 passed, 1945 deselected.
- Full suite (`pytest -q -p no:cacheprovider tests`): **2029 passed, 2 skipped, 0 failed** in 4m37s. (A first run with `-x` stopped on `tests/test_projects_ui.py::test_failed_github_setup_is_visible_and_resumes_idempotently`, the known load-sensitive GitHub flake noted in D69 and by the author; it passed in the full run.)

### Mutations (D10/D64) — each applied to `constitution.py`, then `git checkout -- .`

| # | mutation | result |
|---|---|---|
| M1 | restore "must be within 5%" | RED (2: five_percent_band_is_gone, exact_still_blocks) |
| M2 | "never raise it as a BLOCKER" -> "raise it as a BLOCKER when egregious" | RED (1) |
| M3 | rule severity BLOCKER -> ADVISORY | RED (2, incl. provider-substitution test) |
| M4 | drop the exact-length clause | RED (1) |
| M5 | `render()` no longer displaces the provider's CA-TASK-001 | RED (2) |
| M6 | "more than a quarter" -> "within one twentieth" (i.e. 5% spelled in words) | **GREEN — survives** |
| M7 | "note it as ADVISORY only" -> "note it as a BLOCKER only" | RED (1) |
| M8 | "...materially noncompliant deliverable is a BLOCKER" -> "is an ADVISORY" | RED (1) |
| M9 | delete the "about 300 words"/313 example sentence | RED (1) |

The author's A1-A5 reproduce. M6 shows `test_the_five_percent_band_is_gone`
guards a spelling (`within \d+%`), not the property.

Worktree left clean after mutations (`git status --short` empty).

## 2. Merge onto 50349f9

`git merge-tree 3af0317 61a6b58 50349f9 | grep -c '^<<<<<<<'` -> **0**.
Both sides modify `src/crossaudit/constitution.py` and
`tests/test_router_and_constitution.py`, in disjoint hunks (fusion side:
advisory-only constitutions accepted, `validate()` refusal removed and the
never-gate test replaced; this side: the criterion string and the
provider-substitution assertion). 50349f9 still carries the literal
`assert "A length stated approximately must be within 5%" in rendered` at
`tests/test_router_and_constitution.py:78`; this branch's hunk replaces that line
and merge-tree resolves it without markers. The new fusion-side comment in
`validate()` ("render() unconditionally prepends CA-TASK-001, which is a
BLOCKER") remains true after this change. Merges cleanly.

## 3. Semantics — what changed verdict

Only projects whose constitution went through `Draft.render()` (the model-drafted
path: `distil` in `cli/wizard.py:653`, console `projects.py` when a draft
succeeds) carry `universal_task_rule()` text. For those, with a committed task
stating an approximate length L and a delivered length n:

| input | before | after |
|---|---|---|
| "about 300 words", n=313 (4.3%) | **passes** (already inside the 5% band) | no finding (unchanged) |
| "about 300 words", n=316 (5.3%) | BLOCKER | **no finding** |
| "about 300 words", n=340 (13%) | BLOCKER | **no finding** (< a quarter) |
| "about 300 words", n=400 (33%) | BLOCKER | **ADVISORY** (never gates) |
| "about 300 words", n=40 or n=3000 | BLOCKER | **text says "never raise it as a BLOCKER"** — but the next sentence says a materially noncompliant deliverable IS a BLOCKER. Contradiction; the model chooses. |
| "exactly 300 words", n=301 | BLOCKER | BLOCKER (unchanged) |
| any project initialised from the scaffold templates | unchanged | unchanged (see defect 2) |

(Note the commit's own example: 313 vs 300 is 4.3%, which was already inside
the old 5% band. The example in the commit message, findings doc, test docstring
and the rule text itself does not demonstrate the old defect; 316+ would.)

Configurability: none. The "quarter" is a constant in a string; there is no
per-project dial and no mention in `docs/`. Documented: only inside the rule text
itself, which is rendered into the project's `AUDIT_RULES.md` and quoted to the
auditor — so a user who reads their rules file can see the threshold, and a
finding citing CA-TASK-001 points at it. That is adequate for a rule, but the
threshold is not stated as "a quarter *of the stated length*" (see defect 1b).

## 4. User-facing text / ZH

No product strings (`cli/i18n.py`) are added or changed. The new sentence lives
in the drafted constitution (the user's committed English document, same as the
rest of the drafted rules) and is quoted to the auditor model; no console or CLI
surface renders it as a product string, so D130's translation boundary is not
crossed. Pre-existing and unchanged: the drafted constitution is English even for
a ZH user.

## Defects (numbered, actionable)

1. **The rule contradicts itself at the extremes.** `src/crossaudit/constitution.py:108-113`
   says an approximate length is "never" a BLOCKER; line 113-114 says a
   "materially noncompliant deliverable is a BLOCKER". For "about 300 words"
   delivered as 40 words (or 3,000), the auditor is handed both commands.
   Worse, "never" re-creates the incentive the change was meant to remove, in
   the other direction: the cheapest way to satisfy a rule that can never block
   on approximate length is to under-deliver (D121 — missing a wrong one is
   also a defect). Fix the sentence: e.g. "...is not a BLOCKER on its own; a
   departure so large that the deliverable is a different thing — a fraction
   or a multiple of what was asked — is materially noncompliant under the next
   sentence." Then adjust `test_an_approximate_length_can_never_block` (it pins
   the literal "never raise it as a BLOCKER").
   1b. "departs from it by more than a quarter" does not say a quarter *of
   what*. Write "by more than a quarter of the stated length".
   1c. The example (313 vs 300 = 4.3%) was already inside the old 5% band, so
   the rule's own illustration, the commit message, the findings doc, and the
   test docstring all cite a case the old rule did not block. Use a number the
   old clause actually blocked (e.g. 320) or keep 313 but do not claim it
   "blocks" under the old text.

2. **Reach is overstated and the stated goal is not met on the main init path.**
   Commit/findings say "this reaches NEW projects". It reaches only new
   projects whose rules were *drafted* by the model. `crossaudit init`
   (`src/crossaudit/app.py:61-62`), the wizard's template mode
   (`cli/wizard.py:264-268`), and the console's starter/demo project
   (`console/projects.py:1624, 2011`) copy `scaffold/templates/GENERAL_AUDIT_RULES.md:13-17`
   / `AUDIT_RULES.md:24-29`, whose CA-TASK-001 says length must be satisfied
   and says nothing about "approximately", while `auditor/prompt.py:62-64`
   tells the auditor "a missed or substituted requirement is a BLOCKER under
   CA-TASK-001". So on template projects an auditor can still block 313 for
   "about 300". Either (a) add the same approximate-length sentence to both
   templates, or (b) put the interpretation in the CA-TASK-001 bullet of
   `auditor/prompt.py` (reaches every project, including existing ones, without
   an amendment — note `test_loop_integrity.py:163` pins "CA-TASK-001" in
   `pm.SYSTEM`). At minimum correct the claim in the commit message and
   `docs/findings/w1-approximately.md` section 2.

3. **`test_the_five_percent_band_is_gone` guards spelling, not the property**
   (`tests/test_approximately_means_approximately.py:38-43`). M6 ("within one
   twentieth") passes. Either pin the actual phrase ("more than a quarter of
   the stated length") or rename/document the test as a wording pin; a regex on
   `\d+%` gives false confidence.

4. (minor) `docs/DECISIONS.md` has no entry for this change although D142 item 3
   scheduled it and D138-D147 record neighbouring work; the findings doc is
   under `docs/findings/`. Add a one-paragraph D-entry on merge so the "±5%"
   row in D141's verified-claims table is closed by reference.

## Not defects (checked)

- No kernel directory touched; no deterministic check changed; no previously
  failing *deterministic* input now passes.
- `test_provider_cannot_weaken_or_duplicate_the_reserved_task_rule` now derives
  the expected text from `universal_task_rule()`; M5 confirms it still reddens
  when displacement is removed (2 tests), so the derivation is not tautological.
- Old receipts are unaffected: the constitution is read from the committed file
  and cited by commit (`auditor/run.py:105`), never regenerated from code.
