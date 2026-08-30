# w1 — cycle integrity, rebuilt small on integration

Agent: claude implementation engineer (w1). Per D38.
Branch: `fix/cycle-integrity-small`, cut on integration at `92d1fe1`.
Supersedes `fix/cycle-integrity` (`5a0a8eb`), which is abandoned.

## Why this branch exists instead of a rebase

`fix/cycle-integrity` would not rebase cleanly, and reading the conflict showed
the reason was not mechanical. **Integration had independently solved most of
what that branch carried, and solved the hardest part better.**

Already on integration when I looked:

* `_committed_constitution(cfg, commit) -> (text, bytes)` — one read, two views,
  used by **both** `cmd_audit` and `cmd_run`
* pinning at cycle open in both commands
* clause 2 in the controller (`verdict_already_recorded`, `_has_verdict_for`,
  `verdicts`), from my own `138db3e`, merged
* `tests/test_cycle_integrity.py`, 9 tests, identical to my first version

**And integration's primitive beats the one I wrote.** Verified by execution,
not by reading:

    committed symlink at AUDIT_RULES.md
      git ls-tree            120000 blob …   -> read_committed_bytes refuses on mode
      git show <commit>:path "real.md"       -> exit 0, the LINK TARGET as content

My `git_bytes("show", …)` would have handed the Auditor the literal string
`real.md` as the constitution and hashed the same string into the receipt —
**both agreeing with each other while neither held the rules**, the exact
coherent-wrong-answer shape the branch existed to remove. `read_committed_bytes`
requires exactly one `ls-tree` match on the exact path bytes and refuses
anything that is not a blob with mode 100644/100755. It also raises
`IntegrityDenial` where mine raised `ConfigDenial`; a constitution that cannot
be read exactly from the commit it is cited against is an integrity failure and
belongs at exit 21, not 20.

So the constitution read is **theirs and stays theirs**. Replaying five commits
would mainly have undone better work, and resolving hunk-by-hunk toward HEAD
reaches the same code with far more chances to get one hunk wrong.

## The four properties this branch carries

**1. A verdict row names the standard the round was ACTUALLY judged against.**
`record_verdict` gains an optional `constitution_commit`; a cycle with no pin
adopts it, a cycle with a different pin refuses with `IntegrityDenial`, and the
row records the audited commit rather than copying the cycle's stored value —
copying is what let the two drift. The sweep found a round whose controller
record said C0 while its receipt said C1 and the Auditor received neither.

**2. `inputs.skills` derives from the subject commit.** It read the working
directory, so a receipt attributed `skills/late.md` to work committed before
that file existed. Same idea as the constitution, deliberately, rather than a
second mechanism: a skill absent from the judged commit cannot be attested,
exactly as an uncommitted rule cannot be cited.

**3. `run` no longer advertises `crossaudit audit --sha`,** which always
refuses on a decided commit. It names the two routes that work — the same two
the `audit` refusal names. It does **not** invent a dispute route; there is no
such verb, and a test asserts the word does not appear.

**4. The suite reaches neither the developer's credentials nor the network.**
`CROSSAUDIT_KEYS_FILE` is sandboxed for every test and non-loopback sockets
raise a named error. Loopback stays open for the console tests.

## The five unpinned-by-design paths are untouched

The `constitution_commit` parameter is optional precisely so the sample project
and the three pre-revision escalation producers stay silent. A test asserts an
illustrative cycle still records an empty commit and `record_build_escalation`
still carries none. Normalising a defensible difference into consistency would
not look like a defect in a diff, which is why it has its own test.

## The guard that matters

`test_a_new_cycle_audits_and_hashes_the_commit_it_cites` drives the real
`cmd_audit` into real `build_receipt` — `run_audit` returns a stub rather than
raising, which is what its predecessor got wrong — and compares against an
**independent** `read_committed_bytes` of the cited blob. Its D10 mutation
restores the working-file read and requires the shared property assertion to
**raise**, naming which assertion fired, rather than asserting a defect was
reproduced.

## Cost, stated

The R3 audit was against `7d691fa`, a branch now abandoned. It verified these
properties across four routes on code that no longer exists in this form. Same
properties, different code, is not something I would accept from anyone else, so
**this branch needs a fresh cross-vendor audit.** The four-row table to reproduce
is unchanged: pin, auditor bytes, receipt hash and receipt commit agreeing on
the cited object in all four rows.
