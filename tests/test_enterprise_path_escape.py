"""Adversarial path-escape red-team: no read/write leaves the workspace root or
the capability token's path scope.

The invariant has two layers that must BOTH hold, and the tests attack each:

* the capability token's ``allows_path`` scopes what a grant may name, and
* ``recovery.resolve_in_root`` is defense-in-depth that re-checks the *resolved*
  filesystem path is strictly inside the workspace — even a token that would
  allow a name (e.g. a symlink under root) cannot be used to escape.

Every test below actually performs the traversal attack against the real code
paths (``resolve_in_root``, ``CapabilityToken.allows_path``, ``file_write``,
``git_diff``, and the ``ToolBroker`` chokepoint) and asserts the escape is
refused (``ToolError`` / ``None`` / ``refused`` / ``failed``) and — the binding
property — that NOTHING is ever written or read outside ``cfg.root``. These are
not smoke tests: each would fail if the corresponding guard were deleted.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.approval import AuthorizationStore, WORKSPACE_WRITES
from crossaudit.broker.recovery import resolve_in_root
from crossaudit.broker.registry import ToolError
from crossaudit.broker.tools_git import git_diff
from crossaudit.broker.tools_write import file_write
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken

# Path traversal payloads that must be refused outright: every one drives the
# *resolved* location outside the workspace, or is otherwise unnameable.
_ESCAPE = [
    "../outside",
    "../../etc/passwd",
    "/etc/passwd",
    "~/x",
    "",
    "a/../../b",
    "work/../../../x",
    "work/\x00/x",   # embedded NUL
    "a\x00b",        # embedded NUL
]

# Backslash traversal: on POSIX the backslash is a literal filename char, so it
# does NOT escape the root -- but the token still refuses it (it normalizes the
# backslash to '/', sees '../win', and denies). Kept separate because
# ``resolve_in_root`` legitimately returns an *in-root* literal path for it.
_BACKSLASH = "..\\win"

# Look-alikes that are NOT traversal to the filesystem: '%2e%2e' is not URL
# decoded and U+2025 (TWO DOT LEADER) is not '..'. They resolve to literal,
# strictly-in-root filenames; the attack is proving they do NOT get decoded into
# an escape. ``allows_path`` permits them, and that is safe precisely because the
# resolved path stays inside root.
_LOOKALIKE = ["%2e%2e/x", "work/‥/x"]

# allows_path must return False for all of these (traversal + backslash).
_ALLOWS_FALSE = _ESCAPE + [_BACKSLASH]

# Everything, for the universal "nothing escapes root" sweeps.
_ALL = _ESCAPE + [_BACKSLASH] + _LOOKALIKE

# git_diff refuses a path filter it cannot scope; "" is not a path filter (it
# means a repo-wide diff), so it is excluded from the refusal set.
_GIT_DIFF_REFUSED = [p for p in _ALLOWS_FALSE if p != ""]


def _writable(paths=("**",)):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r",
        "tools": ["file_write", "file_read", "git_diff"],
        "paths": list(paths), "writable": True,
        "expires_at": "2100-01-01T00:00:00Z"})


def _inside(root: Path, p) -> bool:
    """True iff ``p`` resolves strictly inside ``root`` (root itself excluded)."""
    try:
        rp, rootp = Path(p).resolve(), root.resolve()
    except OSError:
        return False
    return rp != rootp and rp.is_relative_to(rootp)


def _outside_files(root: Path) -> set[str]:
    """Every real file under ``root``'s parent that does NOT live inside root.

    Used to prove a write attack never materialised a file outside the
    workspace. ``os.walk`` does not follow symlinks, so a symlink pointing out
    is not traversed here -- exactly what we want.
    """
    base, root_res = root.parent, root.resolve()
    found: set[str] = set()
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            fp = Path(dirpath) / name
            try:
                if not fp.resolve().is_relative_to(root_res):
                    found.add(str(fp.resolve()))
            except OSError:
                found.add(str(fp))
    return found


# --------------------------------------------------------------------------
# 1. resolve_in_root -- the filesystem-level guard
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p", _ALL)
def test_resolve_in_root_never_escapes(cfg, p):
    """For every payload, resolve_in_root either refuses (None) or returns a
    path that resolves strictly inside the workspace. Nothing points out."""
    r = resolve_in_root(cfg.root, p)
    if r is None:
        return                       # refused outright -- safe
    assert _inside(cfg.root, r), f"{p!r} resolved outside root: {r}"


@pytest.mark.parametrize("p", _ESCAPE)
def test_resolve_in_root_refuses_hard_traversal(cfg, p):
    """The unambiguous traversal / absolute / ~ / NUL payloads resolve to None."""
    assert resolve_in_root(cfg.root, p) is None


def test_resolve_in_root_accepts_a_legit_in_scope_path(cfg):
    """Guard is not vacuously rejecting everything: a normal path is accepted."""
    ok = resolve_in_root(cfg.root, "work/ok.md")
    assert ok is not None and _inside(cfg.root, ok)


# --------------------------------------------------------------------------
# 2. CapabilityToken.allows_path -- the token-scope guard
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p", _ALLOWS_FALSE)
def test_token_scope_refuses_escape(p):
    """A '**' grant is the widest possible, yet it still refuses every traversal
    payload -- the token can never be widened into an escape."""
    tok = _writable(paths=("**",))
    assert tok.allows_path(p) is False


def test_token_scope_refuses_in_root_but_out_of_scope(cfg):
    """The scope guard also confines *within* the workspace: a narrow grant
    denies an in-root path outside the grant, and file_write refuses it."""
    tok = _writable(paths=("work/**",))
    assert tok.allows_path("work/sub/a.md") is True
    assert tok.allows_path("secret.env") is False
    assert tok.allows_path("other/x.md") is False
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "secret.env", "content": "x"}, tok)
    assert not (cfg.root / "secret.env").exists()


def test_lookalikes_are_not_decoded_into_escape(cfg):
    """'%2e%2e' and U+2025 are literal names, never decoded to '..': allows_path
    may permit them, but the resolved path stays strictly inside root."""
    tok = _writable()
    for p in _LOOKALIKE:
        # If the grant admits the name, the resolved location must be in-root.
        if tok.allows_path(p):
            r = resolve_in_root(cfg.root, p)
            assert r is not None and _inside(cfg.root, r)


# --------------------------------------------------------------------------
# 3. file_write -- the write path must never land outside root
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p", _ALL)
def test_file_write_never_escapes_root(cfg, p):
    """Attack file_write with each payload. It either raises ToolError, or (for
    the literal look-alikes) writes strictly inside root -- and in NO case does a
    file appear outside the workspace."""
    before = _outside_files(cfg.root)
    tok = _writable()
    try:
        file_write(cfg, {"path": p, "content": "PWNED"}, tok)
        wrote = True
    except ToolError:
        wrote = False
    if wrote:
        target = (cfg.root / p).resolve()
        assert _inside(cfg.root, target), f"{p!r} wrote outside root: {target}"
        assert target.read_text() == "PWNED"
    # The binding invariant: no file materialised outside the workspace root.
    assert _outside_files(cfg.root) == before


def test_file_write_lookalike_stays_literal_and_in_root(cfg):
    """'%2e%2e/x' is written as a literal in-root file, NOT decoded to '../x'."""
    tok = _writable()
    file_write(cfg, {"path": "%2e%2e/x", "content": "PWNED"}, tok)
    assert (cfg.root / "%2e%2e" / "x").read_text() == "PWNED"      # literal, in-root
    assert not (cfg.root.parent / "x").exists()                    # NOT decoded to ../x


# --------------------------------------------------------------------------
# 4. git_diff -- a read path filter cannot be scoped outside the grant
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p", _GIT_DIFF_REFUSED)
def test_git_diff_refuses_out_of_grant_path(cfg, p):
    """git_diff refuses to scope its read to a traversal path filter."""
    with pytest.raises(ToolError):
        git_diff(cfg, {"path": p}, _writable())


def test_git_diff_allows_in_scope_path(cfg):
    """Sanity: an in-scope path filter is accepted (guard is not vacuous)."""
    out = git_diff(cfg, {"path": "experiments/demo"}, _writable())
    assert "diff_stat" in out


# --------------------------------------------------------------------------
# 5. Real symlink under root pointing OUT -- defense-in-depth
# --------------------------------------------------------------------------
def test_symlink_dir_escape_is_refused(cfg, tmp_path):
    """A directory symlink under root pointing outside cannot be written through:
    the token's name-scope WOULD admit it (proving why the second guard exists),
    but resolve_in_root refuses because the resolved path leaves the root."""
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (cfg.root / "link").symlink_to(outside, target_is_directory=True)
    tok = _writable()

    # Defense-in-depth: name-scope alone would allow it ...
    assert tok.allows_path("link/evil.txt") is True
    # ... but the filesystem guard refuses the escape.
    assert resolve_in_root(cfg.root, "link/evil.txt") is None
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "link/evil.txt", "content": "PWNED"}, tok)
    assert not (outside / "evil.txt").exists()          # nothing written outside
    assert list(outside.iterdir()) == []


def test_symlink_file_escape_does_not_overwrite_outside(cfg, tmp_path):
    """A file symlink under root pointing at an outside file cannot be used to
    clobber that outside file: the write is refused and the target is untouched."""
    outside = tmp_path / "outside_file_dir"
    outside.mkdir()
    target = outside / "target.txt"
    target.write_text("ORIGINAL")
    (cfg.root / "leak.txt").symlink_to(target)
    tok = _writable()

    assert resolve_in_root(cfg.root, "leak.txt") is None
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "leak.txt", "content": "PWNED"}, tok)
    assert target.read_text() == "ORIGINAL"             # outside file untouched


# --------------------------------------------------------------------------
# 6. The ToolBroker chokepoint -- escapes are refused end-to-end, ledger intact
# --------------------------------------------------------------------------
def test_broker_refuses_scope_escape_and_ledgers_it(cfg, tmp_path):
    """Through the real broker with a widest '**' writable grant, a '../escape'
    write is denied by policy (out of scope) -- refused, nothing written, and the
    proposal+decision are still recorded to a verifiable ledger."""
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute(
        {"tool": "file_write", "args": {"path": "../escape.txt", "content": "PWNED"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "refused"
    assert not (cfg.root.parent / "escape.txt").exists()   # nothing written outside root
    report = broker.ledger.verify()
    assert report.ok and report.count >= 2


def test_broker_symlink_escape_fails_even_when_write_is_approved(cfg, tmp_path):
    """Even with the project's standing write authorization turned on (so the
    approval gate says yes), a symlink-escape write still fails at the handler --
    resolve_in_root refuses it -- and nothing is written outside root."""
    AuthorizationStore(cfg).set(WORKSPACE_WRITES, True)   # human already authorized writes
    outside = tmp_path / "broker_outside"
    outside.mkdir()
    (cfg.root / "blink").symlink_to(outside, target_is_directory=True)
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))

    r = broker.execute(
        {"tool": "file_write", "args": {"path": "blink/evil.txt", "content": "PWNED"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)

    assert r.status == "failed"                           # handler refused the escape
    assert not (outside / "evil.txt").exists()            # nothing written outside root
    assert list(outside.iterdir()) == []
    assert broker.ledger.verify().ok
