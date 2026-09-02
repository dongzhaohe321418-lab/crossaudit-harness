SEAT: security-boundary auditor (claude). Writes no feature code.

# Dead-guard sweep — a MEASUREMENT, run once, deliberately NOT checked in

Run under the consolidation directive. The distinction that governs this
directory: **running this once to find dead guards is a measurement; leaving it
in the tree as standing infrastructure is a mechanism.** Only the first was
authorised. Nothing here is wired into the suite, no conftest is touched, and
no file in this directory is imported by anything in `src/` or `tests/`.

To re-run it deliberately (it is not maintained, and it will drift):

    # 1. per-test coverage contexts, from a detached worktree
    cat > .coveragerc-dg <<'EOF'
    [run]
    source = src/crossaudit
    dynamic_context = test_function
    EOF
    PYTHONPATH=src python -m coverage run --rcfile=.coveragerc-dg -m pytest -q -p no:randomly

    # 2. test -> production lines it actually executed
    python 1_extract_contexts.py .coverage ctx.json

    # 3. behaviour-changing mutations on COVERED lines only
    python 2_make_mutations.py ctx.json <worktree> muts.json 8

    # 4. apply each, run only the tests that execute that line, revert
    python 3_run_mutations.py ctx.json muts.json <worktree> mutres.json 150

    # 5. separate cannot-fire from mutation-missed from undetermined
    python 4_classify.py ctx.json mutres.json no_prod.json classified.json

## Why it is built this way

Only covered lines are mutated: a mutation on code no test runs says nothing
about any guard and would inflate the dead count with sites nobody was ever
meant to reach.

Only the covering tests are run per mutation: a test that does not execute the
mutated line cannot be expected to notice it, and counting it as "did not fire"
would manufacture dead guards out of a coarse instrument. This is the
`cannot_fire` / `mutation_missed` split, and it is the whole reason the run is
worth anything.

`undetermined` is a real category and must not be folded into either. 69 tests
drive a node subprocess and 1 reads Swift source; Python coverage cannot see
their execution. They are invisible to this instrument, not dead.

## What it cannot tell you

A guard on an invariant that has held all year has not fired and is not dead —
the test is whether it *would*, which is what mutating its own covered lines
asks. But a mutation this generator did not think of is not evidence of death
either, so `cannot_fire` here means "survived the mutations tried", not
"unfalsifiable". Read it as a shortlist to look at, never as a verdict.
