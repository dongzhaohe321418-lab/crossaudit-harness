## What this changes

<!-- One deliverable. Which surface: console, CLI, audit core, docs, website? -->

## Checklist

- [ ] Full suite green (`python -m pytest -q --timeout=30`, or `PYTHONPATH=src` against the tree); anything skipped is named below
- [ ] New behaviour has a test; a bug fix has a regression test, and the test records the mutation it was shown to fail on (D10)
- [ ] User-visible strings exist in English and Chinese (see CONTRIBUTING.md, "Adding a Chinese string")
- [ ] The audit core is not weakened: old receipts and ledgers still verify, no new bypass, no new native dependency; if the core was touched, an independent reviewer is named below
- [ ] `CHANGELOG.md` has a line if a user can notice the change
- [ ] No API key, token, or user data in the diff, the tests, or this description

## Invariant this change is closest to, and how it stays safe

## Test results

<!-- Paste the summary line. State honestly what did not run. -->

## Reviewer

<!-- Independent of the author. Required for audit-core changes. -->
