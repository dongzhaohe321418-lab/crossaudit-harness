# w1 — app_doctor R3: making the anti-fake-check not a fake check

Agent: claude implementation engineer (w1). Per D38.
Answers D64. Branch descends from `fix/app-doctor-parity` at `109170e`, so the
file has one history.

## 1. The enumeration test is real, and here is it failing

Both sides are now **derived by calling the two doctors**: `cmd_doctor` is run
with `json=True` and its emitted `checks` are read; `app_doctor.collect()` is
called and its `id`s are read. The previous version compared two hardcoded
literal sets, with `app_doctor.collect` appearing only in a dead `if False`
branch — it asserted that one list I typed matched another list I typed.

**Per D64 the deliverable is the test plus the observation of it failing.** A
real, unmirrored check was added to `cmd_doctor` and the real comparison run:

    MUTATION: added a real, unmirrored CLI check to cmd_doctor
      FAILED test_cli_doctor_checks_are_mirrored_or_named_excluded
      FAILED test_the_parity_guard_reddens_for_an_unmirrored_cli_check
      E  'unmirrored probe'
    === restoring ===
      4 passed

Red with the mutation, green without it, against the shipped `cmd_doctor` rather
than a simulated list.

**It found two real defects in my own work while I wrote it**, which is the
strongest thing I can say for it:

* my exclusion list used the prefix `automatic:` where the shipped checks are
  named `machine:` — eight entries excluding nothing;
* it listed `generator connection`, a check that **does not exist on this
  branch**. I wrote it from memory of the first-three-minutes slice. The
  stale-exclusion test caught it and it is removed, not moved to a waiver:
  pre-approving a check that does not exist is the padding this file forbids.

Neither would have been visible to the tautology.

Two supporting guards, both from the allowlist lesson:

* `test_every_exclusion_names_a_check_that_exists` — an exclusion for a check
  nobody emits stops meaning anything, and the next check to go missing lands in
  it silently.
* `test_no_exclusion_is_justified_by_mere_absence` — guards the reason drifting
  back to "the GUI does not have it", which is the observation an exclusion is
  supposed to explain.

## 2. The duplicate is deleted

`cmd_doctor` called `main.constitution_commit_state` and then rebuilt the same
three states and the same sentences beside `doctor_shared.constitution_state`.
It now consumes the shared helper, and the duplicate is gone. A shared helper
means one implementation, not two that agree today.

`test_constitution_drift_visible` moved to the survivor rather than being
deleted with the duplicate, and now covers all three states. Writing it taught
me one thing worth recording: **"missing" means never committed, not removed** —
`git log -- <path>` still finds history after a delete, and an audit could still
cite that commit. My first version asserted the wrong thing.

## 3. Exclusions

Rewritten against the criterion rather than the observation: an exclusion says
why a check **does not belong** in the GUI, not why it is currently absent. The
two doctors ask different questions — `cmd_doctor` asks *is this project's audit
trustworthy?*, `app_doctor` asks *is this Mac able to run the app?* — and every
surviving entry is justified by that difference or by naming its mirror.

Of the four the auditor challenged: the two contradicted ones are fixed
(`install` and `tls trust store` are mirrored, so they are aliases now, not
exclusions), one is substantiated (`admission-capable` — admission is a property
of the install and is consumed by `verify --admit`; the app has no admission
workflow to gate), and `generator connection` is **dropped** because the check
does not exist here.

## 4. Byte-0

Left alone. It was the author's call and the auditor would not gate on it; I
have no evidence that would change either judgement, and changing it because I
happened to be in the file is not a reason.

## The PATH-identity row and this test

The row is GUI-only by design, so it is outside what this test constrains — the
comparison runs CLI-to-app. It needs no exclusion because it is not a CLI check.
Now that the test is real, it will have an opinion about any CLI counterpart, as
it should.

---

# R4 — self-check at the manager's request: two defects, both mine

Re-checked `cc87378` per the D64 instruction, and the check found two things
the branch shipped wrong. Both were found by mutating the production side and
watching what the guards did, which is the only method that has worked here.

## 1. The parity guard was real on one side and blind on the other

**Mutation A — a real, unmirrored check added to the shipped `cmd_doctor`:**

    FAILED test_cli_doctor_checks_are_mirrored_or_named_excluded
    FAILED test_the_parity_guard_reddens_for_an_unmirrored_cli_check
    E  CLI doctor checks with no GUI mirror and no named exclusion:
       ['unmirrored probe']
    restored -> 4 passed

Reproduced. The CLI side is derived by calling `cmd_doctor`, and it reddens.

**Mutation B — the app doctor's mirror deleted instead:** I renamed the `python`
row's id in `app_doctor.collect()`, so the CLI's `python` check no longer has a
mirror anywhere.

    4 passed

**Green.** The guard did not notice that the mirror it names had been deleted.

Because `python` sat in `CLI_ONLY` with the reason *"mirrored by the app's
`python` row"* — and `_unmirrored` consults `CLI_ONLY` first and short-circuits.
Six entries were justified that way. Four of them (`install`, `tls trust store`,
`gh cli`, `constitution`) were *also* in `ALIASES`, which reads as covered and is
not: the alias branch is unreachable for any name `CLI_ONLY` already matched.

So an exclusion whose stated reason is a claim that a mirror exists is a claim
nothing executes. **That is the D64 defect — a parity assertion with nothing
behind it — reproduced inside the fix for D64, by me, while writing the fix.**
It is the third time I have seen the shape and the first time I have seen it in
my own repair of it.

FIX: a mirror claim belongs in `ALIASES`, which *is* executed against the ids
`app_doctor.collect()` emits. The six moved. Plus
`test_no_exclusion_is_justified_by_a_mirror_it_does_not_check`, the structural
guard, alongside the two existing ones about absence and staleness.

After the fix, both mutations redden, by name:

    A -> FAILED ... ['unmirrored probe']       (CLI side derived)
    B -> FAILED ... ['python']                 (app side derived)
    baseline and restored -> 5 passed

## 2. The PATH-identity row did not fire in the state it was built for

D66 says execute the change against the reported symptom. The symptom is live on
this machine, so I ran the row against it rather than against a fixture:

    which crossaudit -> /Library/Frameworks/.../3.13/bin/crossaudit
    that binary says -> crossaudit 3.2.0 (receipt schema 2)
    our __version__  -> 4.15.0

    app_doctor.path_identity()  ->  {'state': 'same', ...}   NO ROW

**Silent.** `mine = Path(sys.executable).resolve()` follows a virtualenv's
`bin/python` symlink back to the base prefix — which is the directory the stale
3.2.0 script is in. The sibling test then called the shadowing install a
sibling. The row whose entire purpose is saying which program answers you was
quiet exactly when there was something to say, and the metadata proving it was
3.2.0 was on disk the whole time, unread, because the heuristic returned first.

I reported this row as verified in my handoff. What I verified was
`_other_crossaudit_version` against the real 3.2.0 install — the version
reader, which was correct. I never ran `path_identity()` itself on this machine.

Worse, and this is the part worth keeping: the test that guarded the silence
bias, `test_our_own_install_is_not_reported_as_a_stranger`, pointed at
`Path(sys.executable).resolve().parent / "crossaudit"` — on this machine, the
3.2.0 file. It asserted "same" about a genuine stranger and passed. **It was
validated by the environment that has the defect.**

FIX: the version evidence outranks the directory heuristic. If the other
install's version is readable and is not ours, it is a different program however
the paths sit; the sibling test is only reached when the filesystem has not
already answered. Sameness is asked of the interpreter as invoked as well as
resolved, and the row now names the invoked interpreter as "this app" rather
than the base prefix a venv borrows a binary from.

    app_doctor.path_identity()  ->  {'state': 'different', 'version': '3.2.0', ...}

    the row collect() renders, on this machine:
      Typing `crossaudit` runs /Library/Frameworks/.../3.13/bin/crossaudit
      (version 3.2.0). This app is 4.15.0 at /…/crossaudit_v4/.venv/bin/python.

**Mutation C — the `resolve()`-only test restored:**

    FAILED test_a_virtualenv_does_not_mistake_its_base_prefix_for_itself
    E  - different
    E  + same
    and the live machine under the mutation: state = same

The regression test builds the two prefixes on disk and asserts the topology it
depends on before asserting behaviour, so it cannot pass for the wrong reason if
the layout stops reproducing.

## executes_foreign = no, and it is now a fact about the live call

The existing test patches `subprocess.run`/`Popen`/`check_output` to raise. In
addition, the real call on this machine was run under a CPython audit hook over
`subprocess.Popen`, `os.exec*` and `os.posix_spawn`:

    processes spawned during path_identity(): NONE

## unknown_honest = yes, unchanged

An unreadable layout still yields `version: ""` and the row still says *"Its
version could not be determined without running it, which CrossAudit does not
do."* The new short-circuit only fires on a version it actually read.

## What this does NOT change

The CLI failure case is still not closable from our side, exactly as recorded in
`w1-path-identity.md`: a person who types `crossaudit` still reaches 3.2.0, and
no change of ours executes in that process. What is now true, and was not, is
that a person who opens the app is told which program that is.
