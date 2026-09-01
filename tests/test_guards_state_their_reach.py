"""A guard's name and docstring are part of its contract.

`_no_credentials_and_no_outbound_network` asserted a property the suite does not
have — a subprocess walks straight past it — and the name was read as "the suite
is hermetic" by someone deciding on that basis. This is the `sealed` defect,
sitting in the infrastructure that protects the product's central promise.

The rename fixes the claim. This file keeps it fixed: the clause that says WHAT
IS NOT COVERED is the load-bearing half, because it is the half that stops the
next reader concluding more than the fixture delivers.
"""
from __future__ import annotations

import inspect

import pytest

GUARD = "_sandboxed_keys_file_and_no_in_process_network"


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


def test_the_name_does_not_claim_the_whole_network():
    assert "outbound_network" not in GUARD, (
        "the name claims outbound network coverage again; a subprocess is not "
        "covered and the name is what everything downstream reads")
    assert "in_process" in GUARD, GUARD


def test_the_docstring_says_a_subprocess_is_not_covered(guard_doc):
    doc = guard_doc
    assert "NOT** COVERED" in doc or "NOT COVERED" in doc, (
        "the docstring no longer separates what it covers from what it does "
        f"not; that separation is the whole point of the rename.\n{doc}")
    assert "SUBPROCESS" in doc.upper(), (
        "a subprocess is the channel this fixture cannot reach, and the "
        f"docstring no longer says so.\n{doc}")


def test_the_docstring_names_the_network_capable_children(guard_doc):
    """Naming them is what makes the gap actionable rather than abstract."""
    doc = guard_doc
    for binary in ("gh", "git", "codex"):
        assert f"`{binary}`" in doc, (
            f"{binary!r} is a known network-capable child and the docstring no "
            f"longer names it, so a reader cannot tell what to look for.\n{doc}")


def test_the_docstring_says_the_keychain_is_a_separate_channel(guard_doc):
    doc = guard_doc
    assert "keychain" in doc.lower(), (
        "the fixture moves the keys FILE; the login keychain is a different "
        f"channel and the docstring no longer distinguishes them.\n{doc}")


def test_the_guard_still_actually_refuses_a_remote_peer():
    """The name is honest AND the thing it does name still works."""
    import socket

    with pytest.raises(AssertionError) as caught:
        socket.socket().connect(("198.51.100.7", 443))
    assert "network connection" in str(caught.value)


def test_loopback_is_still_allowed():
    """The narrowing must not have narrowed it to uselessness."""
    import socket
    import threading

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    threading.Thread(target=lambda: srv.accept(), daemon=True).start()
    client = socket.socket()
    client.settimeout(2)
    client.connect(("127.0.0.1", srv.getsockname()[1]))
    client.close()
    srv.close()
