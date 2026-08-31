# Dead-guard sweep — a measurement under version control, NOT standing infrastructure

Under the consolidation directive: **running this to find dead guards is a
measurement; leaving it wired into the suite is a mechanism.** Only the first was
authorised, and this directory is the first only.

**Nothing here runs by default.** No file in this directory is imported by
`src/` or `tests/`, no conftest references it, and pytest does not collect it —
the scripts are numbered, not named `test_*`. It is here because the empty-page
result became load-bearing evidence (D106) and evidence outside version control
is the failure mode this project has hit repeatedly tonight.

    FINDINGS.md        what the sweep found, including the two demonstrations
    HOW-TO-RERUN.md    the five steps, and what the instrument cannot tell you
    1_..4_*.py         the harness, in order

If someone later wants this to run continuously, that is a separate decision
with its own cost — and by then we know what it found, which is the only honest
basis for making it.
