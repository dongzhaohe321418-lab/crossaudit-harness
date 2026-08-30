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
