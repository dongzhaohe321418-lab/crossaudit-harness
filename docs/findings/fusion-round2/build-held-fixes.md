# Build: held fixes (fusion/held-fixes)

Worktree: scratchpad/wt-held-fixes, branched from 50349f9. Not pushed.
Import verified: `crossaudit.__file__` -> the worktree's `src/`.

## Commits (on top of the two clean merges ac7922b, 8107e77)

- 6f6b28c approximately: no self-contradiction, the tolerance says what it is a quarter of, and it reaches every init path
- 0b7d424 approximately: pin that the prompt's reading of an approximate departure is ADVISORY
- 6a60d09 guard: cover what the name says (connect_ex, sendto, sendmsg), name DNS and the raw socket as NOT COVERED, and make the suite hermetic

## A. `approximately` — review defects 1, 1b, 1c, 2, 3 (+ brief item 4)

- `src/crossaudit/constitution.py`: "...more than a quarter of the stated
  length, and it is not a BLOCKER on its own; a departure so large that the
  deliverable is a different thing (a fraction or a multiple of what was
  asked) is materially noncompliant under the next sentence." Example 313 -> 320
  (6.7%, a case the old 5% band actually blocked) in the rule, the findings doc
  and the test docstrings.
- Reach: same reading added to CA-TASK-001 in BOTH scaffold templates
  (`GENERAL_AUDIT_RULES.md`, `AUDIT_RULES.md`) and ONE additive sentence in the
  CA-TASK-001 bullet of `src/crossaudit/auditor/prompt.py` (nothing else in the
  kernel package changed; `test_loop_integrity` "CA-TASK-001" pin holds).
  `docs/findings/w1-approximately.md` section 2 rewritten to state the three
  paths and the remaining limit (a committed constitution keeps its text until
  amended).
- Tests: `test_the_five_percent_band_is_gone` pins "more than a quarter of the
  stated length"; `test_an_approximate_length_can_never_block` replaced by
  `test_an_approximate_length_does_not_block_on_its_own` (pins "not a BLOCKER
  on its own", forbids "never", requires the routing sentence); new pins per
  template and for `pm.SYSTEM`.

Mutations (each reverted; worktree clean after):

| # | mutation | result |
|---|---|---|
| M6 | "more than a quarter" -> "within one twentieth" (the review's survivor) | RED (1) |
| M1 | restore "must be within 5%" | RED (2) |
| M2 | "not a BLOCKER on its own" -> "never raise it as a BLOCKER" | RED (1) |
| M2b | drop the routing to the materially-noncompliant sentence | RED (1) |
| M9 | example back to 313 | RED (1) |
| M3 | rule severity -> ADVISORY | RED (2) |
| MT1 | GENERAL template: quarter -> tenth | RED (1) |
| MT2 | AUDIT_RULES template: "is a BLOCKER on its own" | RED (1) |
| MP | prompt sentence ADVISORY -> BLOCKER | RED (1, after 0b7d424; survived before it) |
| MP2 | prompt sentence removed | RED (1) |

## B. guard rename — review defects 1-5 (+ the hermeticity handbook item)

- `tests/conftest.py`: guard patches `connect`, `connect_ex`, `sendto`,
  `sendmsg`; loopback by name set or `ipaddress.is_loopback`; NOT COVERED
  gains DNS RESOLUTION (`getaddrinfo`) and THE RAW `_socket.socket`.
- `tests/test_guards_state_their_reach.py`: remote check `settimeout(1)` +
  `pytest.raises(AssertionError)` (missing guard fails in ~1s, no
  pytest-timeout); loopback check with main-thread `accept()`, every socket
  closed, no thread; name test against `request.fixturenames`; DNS and raw
  socket bullets pinned; live checks for connect_ex / sendto (both shapes) /
  sendmsg refused and UDP loopback still delivered.
- `tests/test_console_strings_by_execution.py`: `projects.github_status`
  monkeypatched (as test_projects_ui.py does). gh-shim proof (only this file):
  before: `gh auth status`, `gh api user`, 6.80s; after: no gh calls, 0.71s.
  Logs: codex-compare/gh-calls-held-fixes.log.before / .after.

Mutations (all on tests/conftest.py, reverted after):

| # | mutation | result |
|---|---|---|
| MB1 | drop NOT COVERED header | RED (4) |
| MB2 | unname git/gh/codex | RED (1) |
| MB3 | old fixture name back | RED (1 failed, 5 errors) |
| MB4 | drop keychain bullet | RED (1) |
| MB5 | guard body no-op | RED (4, 2.1s total — was 30s via pytest-timeout) |
| MB6 | no patches installed | RED (4, 2.1s) |
| MB7 | drop DNS bullet | RED (1) |
| MB8 | delete raw-socket bullet | RED (1) |
| MB9 | connect_ex unpatched | RED (1) |
| MB10 | sendto unpatched | RED (1) |
| MB11 | sendmsg unpatched | RED (1) |
| MB12 | `_is_local` always False | RED (3: loopback TCP, UDP, 127.0.0.2) |

## Deviations / notes

- No DECISIONS.md entry (lead writes it). Nothing under the owned-by-others
  list touched; `auditor/prompt.py` change is one added sentence.
- Review item 6 (private `getfixturedefs` in `guard_doc`) left as is: there is
  no public route to a fixture's function object; works on pinned pytest.
- Widening the guard to `sendto`/`sendmsg` broke no existing test (see suite).
- Enumerated console strings on this machine: 11 (floor >= 9 unchanged).

## Full suite

`pytest -q -p no:cacheprovider -rf tests/` (foreground; a first background
run was killed externally at ~60%): **2095 passed, 2 skipped, 1 failed,
1 warning, 280s** — log: codex-compare/full-suite-held-fixes.txt.

- The failure is NOT from this slice:
  `test_guard_names_match_what_they_check.py::test_no_test_name_claims_an_outcome_its_body_does_not_check`
  flags `test_finding_states.py::test_no_user_facing_surface_renders_a_state_word`
  (a D106 name/body mismatch). Both files come from the fusion base 50349f9
  (slice A, feat/finding-states) and are untouched by my commits; the
  offending test exists verbatim on 50349f9. Belongs to the slice-A owner.
- The 1 warning is `test_run_liveness_identity.py:125` (DeprecationWarning:
  fork() in a multi-threaded process) — not this slice's file. **Warnings from
  this slice's files: 0** (the previous single warning, from the loopback
  guard test, is gone).
- Touched files in isolation: test_approximately_means_approximately.py,
  test_router_and_constitution.py, test_loop_integrity.py,
  test_constitution_moment.py: 100 passed; test_guards_state_their_reach.py +
  test_console_strings_by_execution.py: 15 passed, 0 warnings;
  test_projects_ui.py: 52 passed.
