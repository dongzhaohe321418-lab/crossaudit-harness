# w1 — `approximately` stops being redefined as a number

Per D38. Branch `fix/approximately-means-approximately` off `v5-redesign@3af0317`.

## 1. What changed

CA-TASK-001 read: *"A length stated approximately must be within 5%."* A user
writes *about 300 words*; 313 blocks. That is not strictness — it is the product
**redefining the word the person chose**, and the cheapest way to satisfy it is
mechanical text counted to the character: optimising for the auditor rather than
for the person who asked.

    BEFORE  A length stated approximately must be within 5%; a length stated as
            exact must match exactly.

    AFTER   A length stated as exact must match exactly. A length stated
            approximately is a guide, not a threshold: note it as ADVISORY only
            if the artefact departs from it by more than a quarter, and never
            raise it as a BLOCKER. Someone who writes 'about 300 words' has
            chosen a word that does not make 313 wrong.

**One clause narrowed, nothing else.** The rule is still a BLOCKER, an explicit
`exact` still matches exactly, and *missing, substituted, extra, or materially
noncompliant* still blocks — each pinned verbatim in a test, because the brief
was to narrow one clause rather than loosen a rule.

The sentence names its own example. A rule a person can read is a rule they can
tell is wrong.

## 2. The limit: this reaches NEW projects only

`universal_task_rule()` is rendered into a project's `AUDIT_RULES.md` at `init`
and committed there. **A project already set up keeps the 5% sentence** until
its owner amends it, and its receipts continue to cite the text they were
audited against — which is correct, and is why old receipts are unaffected.

So the honest scope is: **new projects get the narrower clause; existing ones do
not.** If the intent is to reach existing projects, that is an amendment path
(`crossaudit amend`) and a separate decision, not something this change does
quietly.

## 3. Mutations — 5 of 5 red

    A1  a percentage band comes back                    RED (2 tests)
    A2  an approximate length can block again           RED
    A3  a surviving clause dropped while narrowing      RED (2 tests)
    A4  an explicitly exact length stops being exact    RED
    A5  the provider's substitute is no longer displaced RED

A3 **failed to apply** on its first run — a whitespace mismatch in the anchor —
and the harness said so rather than reporting a pass. Re-anchored and it
reddens.

## 4. One test corrected rather than worked around

`test_provider_cannot_weaken_or_duplicate_the_reserved_task_rule` proved the
reserved rule survived a provider's attempt to replace it by asserting the
literal string *"A length stated approximately must be within 5%"*. That pinned
**our wording** as the evidence for **their substitution failing**, so a
legitimate change to our sentence broke a test about something else.

It now derives the expected text from `universal_task_rule()` — extraction
rather than transcription — and A5 confirms it still catches a provider
substitution.

## 5. Suite

Full suite green at the branch head. One run showed
`test_failed_github_setup_is_visible_and_resumes_idempotently` failing; it
passes in isolation and is the known load-sensitive GitHub flake (D69). My
branch touches `constitution.py` and two test files and nothing that test uses.
