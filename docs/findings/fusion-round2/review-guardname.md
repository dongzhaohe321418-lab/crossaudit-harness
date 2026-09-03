# Review: c0791ff "Rename the network guard to what it actually covers, and pin the clause"

Worktree: scratchpad/wt-review-guardname (detached at c0791ff, branch fix/guard-name-states-its-reach).
Fusion base: 50349f9. Import verified: `crossaudit.__file__` resolves to the worktree's src.

## Verdict: NEEDS CHANGES

The rename is a strict improvement and the pinned-clause test genuinely reddens under
every mutation, but the new name/docstring still overstates the guard's reach along
exactly the axis D146 rules on, and both live checks in the new test have hygiene defects.

### Defects

1. **tests/conftest.py:24 and :38-39 — `no_in_process_network` / "FOR CALLS MADE IN THIS PROCESS" still overstates.**
   Measured under the live fixture (scratch test, since removed):
   - `socket.socket().connect_ex(("198.51.100.7",443))` -> passes through, not intercepted
   - UDP `sendto` to a remote host -> passes through
   - `socket.getaddrinfo("example.com", 443)` -> resolves; DNS leaves the machine in-process
   - `_socket.socket().connect(remote)` -> bypasses the patch; timed out against TEST-NET, i.e. the SYN left the machine
   - Covered correctly: `connect`, `create_connection`, `http.client`, `ssl` wrap, `asyncio.open_connection`, `loop.sock_connect`
   `src/crossaudit/mcp.py:183` and `src/crossaudit/broker/tools_research.py:70` call `getaddrinfo`, so the DNS path is product-relevant.
   Fix: patch `connect_ex` too (and `sendto`/`sendmsg` if UDP matters), and add a NOT COVERED bullet for DNS resolution and raw `_socket.socket`; or rename to `_no_in_process_tcp_connect`. Pin whichever you choose in test_guards_state_their_reach.py so the docstring cannot drift back to the wider claim.

2. **tests/test_guards_state_their_reach.py:71-75 — remote-peer live check fails by hanging.**
   With the guard disabled (M5) or not installed (M6) the test reddens only as `Failed: Timeout (>30.0s) from pytest-timeout`; without the plugin it would hang ~75s on the macOS SYN timeout. Add `s.settimeout(1)` and keep `pytest.raises(AssertionError)` so a missing guard is a fast, distinct failure.

3. **tests/test_guards_state_their_reach.py:78-92 — loopback check leaks a thread exception and a socket.**
   The daemon `srv.accept()` thread races `srv.close()` and raises `ConnectionAbortedError: [Errno 53]`; the accepted connection is never closed. This is the full suite's single warning (`PytestUnhandledThreadExceptionWarning` + `ResourceWarning`) and is the escaped-thread pattern D145 is about, sitting inside the guard that pins D145. Fix: `srv.settimeout(2)`, accept in the main thread after `client.connect`, close `conn`, or join the thread before closing.

4. **tests/test_guards_state_their_reach.py:35-38 (minor) — the name test asserts on a literal in its own file.**
   `GUARD` is a string constant, so this test alone is tautological; it bites only through the `guard_doc` registry lookup. Assert against the live registry (no registered autouse fixture name contains `outbound_network`) instead.

5. **tests/conftest.py:20 (minor) — false positives on non-canonical loopback.** `127.0.0.2`, `::ffff:127.0.0.1`, `LOCALHOST` are refused. No test currently uses them (grep clean), so informational only.

6. **tests/test_guards_state_their_reach.py:28 (minor)** — `request._fixturemanager.getfixturedefs` is private pytest API whose signature changed in 8.1; works on the pinned 9.1.1.

### D10/D64 mutation evidence (each followed by `git checkout -- tests/conftest.py`; worktree clean after)
- M1 drop "WHAT IS NOT COVERED" header -> 1 failed (subprocess clause)
- M2 unname git/gh/codex -> 1 failed
- M3 old name back -> 3 errors (registry lookup)
- M4 drop keychain bullet (0 "keychain" left) -> 1 failed
- M5 guard body `if False:` -> 1 failed (via 30s timeout, see defect 2)
- M6 patch not installed -> 1 failed (via 30s timeout)

### Test counts
- Touched file: 6 passed (1 warning, defect 3).
- Full suite (worktree, plain): **2026 passed, 2 skipped, 1 warning, 335s**, exit 0. Matches the commit's claim.
- Network-off: full proxied run was stopped after the plain run to stay within time. Targeted run of the three relevant files with `https_proxy=http://127.0.0.1:9`, loopback exempted via `no_proxy`: **59 passed**. (A first attempt without `no_proxy` failed one test on urllib -> loopback console server; that was my method, not a finding.)

### What touched the network (gh shim on PATH, logging every invocation)
Full plain run: 17 `gh` invocations — 14 `gh --version` (local), 2 `gh auth status`, 1 `gh api user`. The last three leave the machine.
Path, verified: tests/test_console_strings_by_execution.py -> enumerate_console_strings harness hits `/api/projects` -> src/crossaudit/console/projects.py:1397 `github_status()` -> src/crossaudit/cli/pair.py:122 `_owner()` -> `gh api user`.
With GitHub unreachable, `gh auth status` fails fast, `api user` is never reached, and the test still passes — the suite **touches** the network but does not **need** it. The commit does not address the handbook item (it says so, consistent with D146 ruling 3) but the docstring now names the file and call path. The later hermeticity slice is a one-line `monkeypatch.setattr(projects, "github_status", ...)` in that test, as test_projects_ui.py already does.

### Merge onto 50349f9
`git merge-tree --write-tree 50349f9 c0791ff` -> clean tree 8b9aa71f, no conflicts. Base has no drift in tests/conftest.py or tests/test_console_strings_by_execution.py, still carries the old fixture name, and has no guard test, so the commit applies as-is.

### Stale references to the old name
`grep -rn no_credentials_and_no_outbound_network`: tests/conftest.py:27 and tests/test_guards_state_their_reach.py:3 (both narrative, intentional), docs/DECISIONS.md:6368 and :6426 (historical record, intentionally kept). No functional reference, nothing in packaging or scripts.
