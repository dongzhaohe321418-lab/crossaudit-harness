# Release checklist

The product is the Python package: the command line, `crossaudit tui` and the
optional browser console. A release is a version bump, a tag, and a GitHub
release made from that tag. The native macOS app and its DMG are not on the
main line (D175); their steps are the optional appendix below and are not part
of a release unless someone chooses to build the app.

- [ ] Run `python -m ruff check --select E9,F63,F7,F82 src tests`, the static
      check CI and CONTRIBUTING.md use, and confirm it is clean.
- [ ] Run `./scripts/release_gate.sh`; do not substitute an ad-hoc pytest run.
      It runs the full suite under coverage with a per-test timeout and the
      branch-coverage floor, builds the wheel and source distribution, installs
      the wheel into a fresh environment and runs its self-test, audits the
      installed dependencies when `pip-audit` is present, and checks repository
      hygiene. Where `swiftc` is absent it says so and skips the native app's
      Swift type-check.
- [ ] Confirm GitHub CI is green on Python 3.10–3.13, Linux/macOS/Windows,
      including coverage, dependency audit, source/wheel build, and installed
      runtime self-test jobs.
- [ ] Run opt-in live provider checks with non-production credentials.
- [ ] Bump the version in `pyproject.toml`, `src/crossaudit/__init__.py`, the
      README title and badges, the console page's `V…` literal, and
      SECURITY.md's supported version (`tests/test_product_readiness.py` checks
      that the package, the README title and the page agree), and turn
      CHANGELOG.md's `## Unreleased` into the version's heading.
- [ ] Confirm no key, tokenized localhost URL, build directory, or app support
      data is tracked by Git.
- [ ] Confirm `main` is clean and README links target the current version.
- [ ] Push `main`, tag the release commit `v<version>`, push the tag, and create
      the GitHub release from that tag with the CHANGELOG section as its notes.
      The wheel and source distribution `python -m build` produces may be
      attached; nothing is uploaded to PyPI. Verify the repository default
      branch is `main`.

## Appendix: the native macOS app (optional, not on the main line)

Only when someone chooses to build and publish the app from
`packaging/macos/`. The last released DMG is the v4.17.0 GitHub release.

- [ ] Build with `./packaging/macos/build_dmg.sh` on Apple Silicon.
- [ ] Run `packaging/macos/verify_dmg.sh` against the final immutable DMG.
- [ ] For a public release, set `CROSSAUDIT_PUBLIC_RELEASE=1` and provide a
      Developer ID identity plus notarytool keychain profile. Ad-hoc signed
      builds are review candidates, not public production releases.
- [ ] Verify the application plist, architecture, and deep signature.
- [ ] Verify, mount, inspect, and copy the DMG into an isolated directory.
- [ ] Start the copied frozen core with isolated support/workspace directories.
- [ ] Test project creation, independent worker attachment, token refusals, and
      final-artifact download.
- [ ] Generate PDF and DOCX through the UI; verify only the requested binary is
      committed, semantic audit sees the final bytes, CJK text renders, every
      supported preview opens safely, and unknown binaries remain download-only.
- [ ] Open a long audit at maximum scroll with a tall composer and attachments;
      confirm the final evidence stays visible above the composer. Exercise the
      SSH host dialog with Generator access both collapsed and expanded.
- [ ] Run Environment Doctor with current, missing, and outdated Git; verify
      real-time refresh, project-creation blocking, update guidance, local Git
      identity repair, and first-launch recovery without a usable Git binary.
- [ ] Close the native window during an active controller session, verify the
      shell/core remain alive, restore from Dock/menu bar, then verify explicit
      Quit stops the controller.
- [ ] Create two Chats in one Project, switch their isolated views, pin one Chat
      and the Project, reload, and verify Git-trailer recovery.
- [ ] Test a native folder choice, two editable repository names, name
      preflight, explicit adoption, one-click creation, and partial-failure UI
      recovery against an isolated test project.
- [ ] Verify provider-reported API and subscription token events, custom-model
      unpriced handling, local-ledger privacy, and immediate Usage SSE refresh.
- [ ] Register an SSH-config host, exercise unknown/changed-key and offline
      guidance, submit both Slurm and detached workstation jobs, restart the
      local controller, and verify reattachment, live status/logs, cancellation,
      input streaming, and portable remote-output download.
- [ ] Upload the DMG and its checksum to the release and verify them from the
      release page.
