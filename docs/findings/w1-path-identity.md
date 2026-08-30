# w1 — which `crossaudit` answers (D40, reframed)

Agent: claude implementation engineer (w1). Per D38.

## The limit, stated first because it is the finding

**The CLI path in the failure case cannot be closed from our side, and this
slice does not close it.**

Someone installs the app, types `crossaudit`, and runs an older pip
installation earlier on PATH — 3.2.0 from three weeks before 4.15.0 on the
machine where this was found, a build predating the symlink escape fix, the
erasable verdict and the trimmed constitution reader. In that state **our code
never executes**; the stale binary's does. `--version` was the first attempt and
it is structurally incapable of reaching the case, because the `--version` that
runs is the old binary's. No change to the new program reaches a person who only
ever types `crossaudit`.

That is a property of the person's environment. It is recorded as a limit rather
than softened into a caveat, because a remedy whose truth depends on something
that cannot happen belongs out rather than reworded.

## What is built, and why it is where it is

**A PATH-identity row in `app_doctor`.** The app is the one surface that
certainly runs in the failure state — the person opened it, so our code is
executing — and it can look OUTWARD at what `crossaudit` resolves to rather than
describing itself.

**An install-time note in the DMG.** The moment a person installs is the moment
the shadowing begins, and it is the only other point at which we can say
anything. It states that the app adds no `crossaudit` command by design, that an
existing pip install will keep answering, and how to check.

## It does not execute the other binary — and that is load-bearing

Running an arbitrary `crossaudit` found on PATH means executing a program we did
not build, in the person's environment, because we found it. §1.1 is
allowlist-only loading and no arbitrary code, and "we ran it to be helpful" is
not an exception; anyone able to write to a PATH directory would get code
execution out of a diagnostic.

**The version is not needed for the point.** The mismatch that matters is
IDENTITY: the command you type is not the program you installed. `shutil.which`
answers that with a filesystem lookup.

Where the version IS available it is read from metadata — a pip console script
sits in `<prefix>/bin` and its distribution metadata in
`<prefix>/lib/python*/site-packages/crossaudit-<version>.dist-info`, so the
version is a directory NAME. Verified against the real 3.2.0 install on this
machine: read correctly, nothing spawned. A test patches `subprocess.run`,
`Popen` and `check_output` to raise, so "never executed" is a fact rather than a
promise.

## Honest when it cannot tell

An unrecognised layout yields no version, and the row says so:
*"Its version could not be determined without running it, which CrossAudit does
not do."* That names the reason rather than shrugging. A test asserts no version
is invented.

**The bias is toward silence.** The row appears only in the `different` state;
`absent` and `same` produce nothing. This is the surface whose entire purpose is
telling somebody which program is answering them, so a confident wrong "there is
another one" is worse than any other wrong answer in the product, while staying
quiet costs a person nothing they did not already have.

## Chinese

Label and explanation are exact ZH entries. The detail is assembled at runtime
from paths and versions, which are identifiers and stay Latin (SPEC-7 §4), so
the sentence around them is translated with two `ZH_PATTERNS` entries. All four
strings were rendered through the page's real `zhValue` in node; none fell back.

## Note on the parity test I built against

`tests/test_doctor_parity.py` (from `fix/app-doctor-parity`, under audit)
enumerates CLI checks and requires each to be mirrored or excluded. My row is
GUI-only by design, so it is outside what that test constrains, and it passes.

Worth the auditor's attention while that branch is open: the test asserts over
**two hardcoded literal sets**, not over the code — `app_doctor.collect` is
referenced in a dead `if False` branch and the app-side set is a literal. It
would not notice a new row on either side. I have not touched it; it is not my
branch and it is mid-audit.
