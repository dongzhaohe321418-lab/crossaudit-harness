# w1 — frozen-bundle reachability check, and the PATH-visibility fix

Agent: claude implementation engineer (w1). Per D38, findings live in a file.

Artifact: `CrossAudit2.app`, `crossaudit 4.15.0 (receipt schema 2)`, core built
2026-08-30 18:18, from v5-redesign plus the frozen-entry dispatch (b5b3ea5).
Method: the installed bundle only, clean sandbox `HOME`, no source on the path.

---

## F1 — the reachability check could not be run. Not a dispatch defect. (INFO)

The four surfaces I was asked to check are not in the artifact:

    $CORE doctor --help  ->  [-h] [--online] [--fix]      no --lang, no --all
    $CORE init  --help   ->  no --lang, no --profile

    grep of the frozen binary:
      i18n              ABSENT     (i18n waves 1 and 2)
      _show_and_agree   ABSENT     (the constitution moment)
      STARTING_POINTS   ABSENT
      assess_readiness  ABSENT     (the init/doctor agreement fix)
      infer_check_pack  ABSENT     (the science proposal)

`agentA/first-three-minutes` has never merged and the i18n waves sit on top of
it, so the bundle cannot carry them. Checked explicitly whether this was a
dispatch defect: it is not. The dispatch hands argv to whatever `cli.main` the
build contains, and does so correctly.

## F2 — the dispatch contract holds from the bundle (PASS)

| invocation | exit | result |
|---|---|---|
| `--version` | 0 | `crossaudit 4.15.0 (receipt schema 2)` |
| `--help` | 0 | 18 verbs |
| unknown argv / unknown verb | 2 | argparse usage; starts nothing |
| `doctor` / `build` / `watch` outside a project | 20 | `DENIED (config): ...`, no traceback |

And contract point 1 holds: no GUI workspace or Application Support semantics
leak into a CLI run. That was the one I flagged as able to ruin things silently.

## F3 — S1. A stale `crossaudit` on PATH silently shadows the installed app

    which crossaudit  ->  /Library/Frameworks/Python.framework/Versions/3.13/bin/crossaudit
                          crossaudit 3.2.0 (receipt schema 2), mtime Aug 3
    bundle            ->  crossaudit 4.15.0 (receipt schema 2), mtime Aug 30

A person installs 4.15.0 and types `crossaudit doctor`; they run 3.2.0, which
predates the symlink escape fix, the erasable verdict fix and the trimmed
constitution reader. Nothing indicates it.

D31 part 2 decided the bundle installs nothing on PATH, on consent grounds, and
that stands. It is silent about a DIFFERENT `crossaudit` already being there,
and nobody consented to being routed to an old binary.

**Severity S1, not S0.** The ledger already distinguishes the two producers:
receipts carry the version, a path-tagged code digest and the install mode, and
`verify --admit` refuses install modes whose code could have changed under them.
The shared `receipt schema 2` is not a compatibility claim. What is misled is the
PERSON, so this is a false-premise experience on valid input, not data loss.

**OPEN.** This said *"Fixed — see the change contract for A6"*, and that was
wrong when I wrote it. The cross-vendor audit of this branch made correcting it
the one required fix, and the manager has since restated it (D66): F3 closes
when the shadowing case is detected, not before.

What A6 does is make an install identify itself on the surfaces where our code
already runs. What it does not do is tell a person that the `crossaudit`
answering them is a different program — and in the failure state **our code
never executes**, because the binary that answers predates it. You cannot change
a stale binary's output by editing the new one, so no revision of A6 could have
reached this.

Detection now exists, on `agentA/path-identity`: `app_doctor.path_identity()`
resolves the `crossaudit` on PATH, reads the other install's version from its
dist-info directory name — a filesystem read, never executing it — and the app
says which program answers. Executed against the real state on this machine, it
names the 3.2.0 install against our 4.15.0.

**That still does not close F3, and it must not be recorded as closing it.** It
reaches the person who opens the app. Anyone who only types `crossaudit` gets
the old program, and nothing of ours runs in that process. What changed is the
population who can find out, not the collision.

## F4 — what a person must know to reach the CLI at all (INFO, feeds D37)

    path:        /Applications/CrossAudit.app/Contents/Resources/core/CrossAuditCore
    depth:       4 components below the .app
    length:      67 characters, typed exactly

    Info.plist mentions the CLI ............................. no
    Swift wrapper mentions the core path .................... no
    the console UI (the only screen a DMG user sees) ........ no
    any "install command line tool" offer, anywhere ......... no
    Swift wrapper sets process.arguments .................... no (empty argv -> app mode)

So a person must already know that a CLI exists, that it lives inside the .app,
its exact four-component path, and that the `crossaudit` on their PATH is a
different and older program. The product supplies none of the four. D37's "a
path nobody finds by accident" is understated: the discoverable name is actively
wrong.

## F5 — recommendation, adopted by the manager

Make the frozen-bundle reachability check a standing gate on every DMG build.
Source-and-frozen divergence is three-for-three at finding real defects.
