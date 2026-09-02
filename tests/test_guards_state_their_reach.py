"""A guard's name and docstring are part of its contract.

`_no_credentials_and_no_outbound_network` asserted a property the suite does not
have — a subprocess walks straight past it — and the name was read as "the suite
is hermetic" by someone deciding on that basis. This is the `sealed` defect,
sitting in the infrastructure that protects the product's central promise.

The rename fixes the claim. This file keeps it fixed: the clause that says WHAT
IS NOT COVERED is the load-bearing half, because it is the half that stops the
next reader concluding more than the fixture delivers. Review of the rename
found the renamed guard still overstating along the same axis (`connect_ex`,
UDP `sendto`, DNS and the raw `_socket.socket` all passed through), so the
covered set was widened to what the name says and the two channels it cannot
reach are named in NOT COVERED — and pinned here, like the subprocess clause.
"""
from __future__ import annotations

import inspect
import socket

import pytest

GUARD = "_sandboxed_keys_file_and_no_in_process_network"

#: TEST-NET-2 (RFC 5737): never routed, so a leak times out instead of landing.
REMOTE = ("198.51.100.7", 443)


@pytest.fixture()
def guard_doc(request) -> str:
    """The LIVE fixture's docstring, via pytest's own registry.

    Not a read of conftest.py: the object the suite actually installs is what
    the claim is about, and `import conftest` does not work under the
    documented invocation (`PYTHONPATH=src`) anyway.
    """
    defs = request._fixturemanager.getfixturedefs(GUARD, request.node)
    assert defs, (
        f"{GUARD} is not registered. If it was renamed, this guard moves with "
        f"it; a rename that leaves a stale reference is worse than the old name.")
    func = defs[-1].func
    return inspect.getdoc(getattr(func, "__wrapped__", func)) or ""


def _not_covered(doc: str) -> str:
    """The text after the NOT COVERED header — the half this file is about."""
    for header in ("NOT** COVERED", "NOT COVERED"):
        if header in doc:
            return doc[doc.index(header):]
    pytest.fail(
        "the docstring no longer separates what it covers from what it does "
        f"not; that separation is the whole point of the rename.\n{doc}")


def test_the_name_does_not_claim_the_whole_network(request):
    """Against the fixtures the suite actually installs on this test (autouse
    included), via public `request.fixturenames` — not a literal in this file."""
    active = list(request.fixturenames)
    assert GUARD in active, (
        f"{GUARD} is not active on this test; the registry and this file "
        f"disagree about the guard's name: {active}")
    claiming = [name for name in active if "outbound_network" in name]
    assert not claiming, (
        f"{claiming} claims outbound network coverage again; a subprocess is "
        "not covered and the name is what everything downstream reads")
    assert any("in_process" in name for name in active), active


def test_the_docstring_says_a_subprocess_is_not_covered(guard_doc):
    assert "SUBPROCESS" in _not_covered(guard_doc).upper(), (
        "a subprocess is the channel this fixture cannot reach, and the "
        f"docstring no longer says so.\n{guard_doc}")


def test_the_docstring_names_the_network_capable_children(guard_doc):
    """Naming them is what makes the gap actionable rather than abstract."""
    doc = guard_doc
    for binary in ("gh", "git", "codex"):
        assert f"`{binary}`" in doc, (
            f"{binary!r} is a known network-capable child and the docstring no "
            f"longer names it, so a reader cannot tell what to look for.\n{doc}")


def test_the_docstring_says_the_keychain_is_a_separate_channel(guard_doc):
    assert "keychain" in _not_covered(guard_doc).lower(), (
        "the fixture moves the keys FILE; the login keychain is a different "
        f"channel and the docstring no longer distinguishes them.\n{guard_doc}")


def test_the_docstring_says_dns_resolution_is_not_covered(guard_doc):
    """`getaddrinfo` leaves the machine in-process before any socket connects,
    and the product calls it (mcp.py, broker/tools_research.py)."""
    tail = _not_covered(guard_doc)
    assert "DNS" in tail and "getaddrinfo" in tail, (
        "DNS resolution is not patched and the NOT COVERED clause no longer "
        f"says so; a reader would conclude name lookups are blocked.\n{guard_doc}")


def test_the_docstring_says_the_raw_socket_is_not_covered(guard_doc):
    """The patch lives on the Python class; `_socket.socket` bypasses it."""
    assert "_socket.socket" in _not_covered(guard_doc), (
        "the C-level socket bypasses the patch and the NOT COVERED clause no "
        f"longer says so.\n{guard_doc}")


# ---- the thing the name does claim still works, for every patched entry -----

def test_the_guard_still_actually_refuses_a_remote_peer():
    """The name is honest AND the thing it does name still works.

    `settimeout(1)`: with the guard missing, the SYN to TEST-NET times out in a
    second as a distinct `TimeoutError` rather than the ~75s macOS SYN timeout
    that pytest-timeout would otherwise have to cut off.
    """
    with socket.socket() as s:
        s.settimeout(1)
        with pytest.raises(AssertionError) as caught:
            s.connect(REMOTE)
    assert "network connection" in str(caught.value)


def test_connect_ex_is_refused_too():
    """`connect_ex` was the measured bypass in review; it is the same call with
    an errno return, and it went straight through the old patch."""
    with socket.socket() as s:
        s.settimeout(1)
        with pytest.raises(AssertionError):
            s.connect_ex(REMOTE)


def test_udp_sendto_is_refused_for_a_remote_peer():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        with pytest.raises(AssertionError):
            s.sendto(b"x", REMOTE)
        with pytest.raises(AssertionError):
            s.sendto(b"x", 0, REMOTE)


def test_sendmsg_is_refused_for_a_remote_peer():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        with pytest.raises(AssertionError):
            s.sendmsg([b"x"], [], 0, REMOTE)


def test_loopback_is_still_allowed():
    """The narrowing must not have narrowed it to uselessness.

    No helper thread: the kernel completes the handshake into the listen
    backlog, so `accept()` after `connect()` is deterministic, and every socket
    — server, client and the accepted connection — is closed. The full suite's
    one warning came from the previous version of this test (a daemon
    `accept()` racing `close()`, and a leaked connection).
    """
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        srv.settimeout(2)
        with socket.socket() as client:
            client.settimeout(2)
            client.connect(("127.0.0.1", srv.getsockname()[1]))
            conn, peer = srv.accept()
            with conn:
                assert peer[0] == "127.0.0.1"


def test_udp_to_loopback_is_still_allowed():
    """Widening the patch to `sendto`/`sendmsg` must not break loopback UDP."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as srv:
        srv.bind(("127.0.0.1", 0))
        srv.settimeout(2)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"ping", srv.getsockname())
            data, _ = srv.recvfrom(16)
            assert data == b"ping"
            client.sendmsg([b"pong"], [], 0, srv.getsockname())
            data, _ = srv.recvfrom(16)
            assert data == b"pong"


def test_non_canonical_loopback_is_still_local():
    """`127.0.0.2` is loopback too; refusing it would be a false positive.

    Only the guard's verdict is under test: the kernel may not have that
    address configured (macOS does not), so an `OSError` from the real
    connect is fine — an `AssertionError` from the guard is not.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.2", 9))
        except OSError:
            pass
