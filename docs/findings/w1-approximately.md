# w1 — `approximately` stops being redefined as a number

Per D38. Branch `fix/approximately-means-approximately` off `v5-redesign@3af0317`.

## 1. What changed

CA-TASK-001 read: *"A length stated approximately must be within 5%."* A user
writes *about 300 words*; 320 blocks. That is not strictness — it is the product
**redefining the word the person chose**, and the cheapest way to satisfy it is
mechanical text counted to the character: optimising for the auditor rather than
for the person who asked.

    BEFORE  A length stated approximately must be within 5%; a length stated as
            exact must match exactly.

    AFTER   A length stated as exact must match exactly. A length stated
            approximately is a guide, not a threshold: note it as ADVISORY only
            if the artefact departs from it by more than a quarter of the
            stated length, and it is not a BLOCKER on its own; a departure so
            large that the deliverable is a different thing (a fraction or a
            multiple of what was asked) is materially noncompliant under the
            next sentence. Someone who writes 'about 300 words' has chosen a
            word that does not make 320 wrong.

**One clause narrowed, nothing else.** The rule is still a BLOCKER, an explicit
`exact` still matches exactly, and *missing, substituted, extra, or materially
noncompliant* still blocks — each pinned verbatim in a test, because the brief
was to narrow one clause rather than loosen a rule.

Two corrections from review. The first draft said "never raise it as a
BLOCKER", which contradicted the next sentence at the extremes (40 or 3,000
words for "about 300" is both "never a BLOCKER" and "materially noncompliant")
and, worse, made under-delivery the cheapest way to satisfy the rule. The
sentence now says *not a BLOCKER on its own* and routes the different-thing
case to the clause that already blocks it. And the example was 313, which at
4.3% was already inside the old 5% band and so illustrated nothing; 320
(6.7%) is a case the old clause actually blocked.

The sentence names its own example. A rule a person can read is a rule they can
tell is wrong.

## 2. Reach: three paths, stated honestly

The first draft claimed this "reaches new projects". It reached only new
projects whose rules were **drafted** by the model (`Draft.render()` via the
wizard's `distil` or a console draft). `crossaudit init`, the wizard's template
mode and the console's starter project copy the scaffold templates, whose
CA-TASK-001 said nothing about `approximately` — so on the main init path an
auditor could still block 320. Now:

1. **Drafted constitutions** carry the narrowed clause from
   `universal_task_rule()`.
2. **Template projects** carry the same reading: both
   `scaffold/templates/GENERAL_AUDIT_RULES.md` and `AUDIT_RULES.md` state it in
   their CA-TASK-001, pinned per template in a test.
3. **Every auditor, every project** — including one whose committed rules
   still say "within 5%" — is told the reading in one additive sentence in the
   CA-TASK-001 bullet of the auditor SYSTEM prompt (`auditor/prompt.py`).
   The bullet's other sentences are unchanged; `test_loop_integrity` still
   pins "CA-TASK-001" in `pm.SYSTEM`.

The limit that remains: **an existing project's committed `AUDIT_RULES.md`
keeps whatever it says** until its owner amends it, and its receipts continue
to cite the text they were audited against — which is correct, and is why old
receipts are unaffected. For such a project the prompt sentence and the
committed 5% clause both reach the auditor; the committed constitution is the
document the receipt cites, so replacing the clause there is still the
amendment path (`crossaudit amend`) and a separate decision.

## 3. Mutations — 5 of 5 red, plus the one the review found surviving

The review's M6 replaced "more than a quarter" with "within one twentieth" (5%
spelled in words) and `test_the_five_percent_band_is_gone` stayed green: it
guarded the spelling `within \d+%`, not the property. It now pins the phrase
*more than a quarter of the stated length*, and M6 reddens (re-verified by
applying the mutation).

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
