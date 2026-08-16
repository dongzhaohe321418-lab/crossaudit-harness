"""Adversarial proof: the model cannot mint or widen its capability token.

The Capability Token is the ceiling on everything the Agentic Runtime may do.
This file attacks that ceiling from every direction a hostile generator could
reach through the real API surface (``CapabilityToken.parse`` from an untrusted
dict, the frozen dataclass, and ``policy.engine.decide``) and asserts the grant
holds:

  (a) the token is frozen — no attribute can be reassigned to widen it;
  (b) ``parse`` refuses unknown keys and fails closed (a typo'd limit is NOT
      silently dropped into "unlimited", a forged ``admin`` flag is rejected);
  (c) a tool absent from ``tools`` is denied by ``decide`` even with writable +
      wide paths (the tool set cannot be widened);
  (d) ``allows_path`` is escape-proof for absolute paths, ``..`` traversal,
      backslash/null tricks, prefix-confusion, and even a maximally-wide
      ``"/**"`` pattern still refuses to leave the workspace;
  (e) an EXPIRED grant is denied by ``decide`` regardless of the tool;
  (f) ``within_cost`` / ``within_bytes`` ceilings deny an over-budget proposal,
      and ``decide`` honours both;
  (g) even a token whose paths are widened to ``"/**"``/``"**"`` cannot escape
      ``cfg.root`` at the tool layer — ``resolve_in_root`` guards the write
      handler as defense-in-depth (including through a symlink the token's own
      scope test cannot see through), and the broker never auto-runs a write.

Every test performs the attack and asserts the block; each would go green->red
if the corresponding guard were deleted (positive controls prove selectivity).
"""
from __future__ import annotations

import calendar
import time
from dataclasses import FrozenInstanceError

import pytest

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.recovery import resolve_in_root
from crossaudit.broker.registry import ToolError
from crossaudit.broker.tools_write import file_write
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken, TokenError, decide

#: 2100-01-01T00:00:00Z as epoch — used as "now" when testing an expired grant.
FUTURE = 4102444800


def _tok(**kw) -> CapabilityToken:
    base = dict(project_id="p1", run_id="r1", tools=["file_read", "search"],
                paths=["work/**"], expires_at="2100-01-01T00:00:00Z")
    base.update(kw)
    return CapabilityToken.parse(base)


def _proposal(**kw) -> dict:
    base = dict(tool="file_read", level=1, writes=False, paths=["work/review.md"])
    base.update(kw)
    return base


def _wide_writable() -> CapabilityToken:
    """A maximally-permissive grant a hostile generator might wish it had."""
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r",
        "tools": ["file_read", "file_write"], "paths": ["/**", "**"],
        "writable": True, "expires_at": "2100-01-01T00:00:00Z"})


# ---------------------------------------------------------------------------
# (a) the token is frozen: no attribute reassignment can widen it
# ---------------------------------------------------------------------------
def test_token_attributes_are_frozen_against_widening():
    t = _tok(tools=["file_read"], writable=False, paths=["work/**"],
             max_cost_usd=1.0, max_bytes=10)
    widenings = [
        ("tools", frozenset({"file_write", "self_install"})),
        ("writable", True),
        ("paths", ("/**",)),
        ("hosts", frozenset({"evil.example.com"})),
        ("max_cost_usd", 1e9),
        ("max_bytes", 10 ** 12),
        ("expires_at", "2999-01-01T00:00:00Z"),
    ]
    for attr, val in widenings:
        with pytest.raises(FrozenInstanceError):
            setattr(t, attr, val)
    # a brand-new attribute is refused too (no smuggling an `admin` flag on)
    with pytest.raises(FrozenInstanceError):
        t.admin = True  # type: ignore[attr-defined]
    # and nothing actually mutated
    assert t.tools == frozenset({"file_read"})
    assert t.writable is False
    assert t.paths == ("work/**",)
    assert t.max_cost_usd == 1.0 and t.max_bytes == 10


# ---------------------------------------------------------------------------
# (b) parse rejects unknown keys and fails closed (no silent grant)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key,val", [
    ("admin", True),
    ("privileged", True),
    ("level", 6),
    ("allow_all", True),
    ("scope", "*"),
    ("extra_tools", ["file_write"]),   # cannot bolt extra tools onto the grant
    ("_expires_epoch", 9e18),          # cannot inject the private expiry cache
])
def test_parse_refuses_unknown_widening_keys(key, val):
    raw = {"project_id": "p", "run_id": "r", "tools": ["file_read"],
           "paths": ["work/**"], key: val}
    with pytest.raises(TokenError):
        CapabilityToken.parse(raw)


@pytest.mark.parametrize("key", ["max_cost", "max_byte", "max_cost_usd_", "cost"])
def test_typoed_limit_fails_closed_not_unlimited(key):
    # A forged token cannot relax a ceiling by *misspelling* the limit key: an
    # unrecognized key is rejected outright rather than silently dropping the
    # real limit (which would leave it at the 0 == unlimited default).
    with pytest.raises(TokenError):
        CapabilityToken.parse({"project_id": "p", "run_id": "r", key: 10 ** 9})


@pytest.mark.parametrize("bad", [None, [], "token", 42, ("project_id", "p")])
def test_parse_refuses_non_mapping(bad):
    with pytest.raises(TokenError):
        CapabilityToken.parse(bad)


def test_valid_subset_still_parses_control():
    # Control: a well-formed grant with only allowed keys parses fine — proving
    # the rejections above are about *unknown* keys, not a blanket failure.
    t = CapabilityToken.parse({"project_id": "p", "run_id": "r",
                               "tools": ["file_read"], "paths": ["work/**"]})
    assert t.allows_tool("file_read") and not t.allows_tool("file_write")


# ---------------------------------------------------------------------------
# (c) the tool set cannot be widened: a tool not in `tools` is denied by decide
# ---------------------------------------------------------------------------
def test_decide_denies_tool_outside_grant_even_when_writable():
    # writable + maximally-wide paths, yet file_write is NOT in the tool set.
    t = _tok(tools=["file_read"], writable=True, paths=["**"])
    d = decide(_proposal(tool="file_write", level=2, writes=True,
                         paths=["work/x.md"]), t, now_epoch=0)
    assert not d.allow and "not in this grant" in d.reason
    # selectivity control: the tool it *does* list is allowed under the same grant
    assert decide(_proposal(tool="file_read"), t, now_epoch=0).allow


@pytest.mark.parametrize("tool", [
    "self_install", "git_push", "git_commit", "run_check", "repo_create",
    "mcp_call", "hpc_submit", "rm_rf", "",
])
def test_decide_denies_unlisted_escalation_tools(tool):
    d = decide(_proposal(tool=tool, level=1), _tok(), now_epoch=0)
    assert not d.allow and "not in this grant" in d.reason


# ---------------------------------------------------------------------------
# (d) allows_path is escape-proof for tricky inputs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("evil", [
    "/etc/passwd",
    "~/secret",
    "../outside",
    "work/../../etc/passwd",         # would match 'work/**' literally if unnormalized
    "work/../secret.env",
    "work/./../../etc/passwd",
    "work/sub/../../../etc/passwd",
    "work\\..\\..\\etc\\passwd",      # backslash traversal
    "work/\x00/etc",                  # embedded null byte
    "work/../work_sibling/x",         # prefix-confusion (sibling of 'work')
    "work_sibling/x",                 # not under 'work/' despite shared prefix
    "",
])
def test_allows_path_cannot_be_tricked_out_of_scope(evil):
    assert _tok(paths=["work/**"]).allows_path(evil) is False


def test_allows_path_positive_controls():
    # These MUST be allowed, so the escape assertions above are discriminating
    # (a broken guard that denied everything would be caught here).
    t = _tok(paths=["work/**"])
    assert t.allows_path("work/review.md")
    assert t.allows_path("work/deep/nested/file.txt")


def test_wildcard_root_pattern_still_blocks_traversal():
    # Widening the grant to the broadest relative pattern '/**' opens every
    # in-workspace relative path — but absolute paths and '..' traversal are
    # STILL refused, so the widened pattern is not an escape.
    t = _tok(paths=["/**"])
    assert t.allows_path("anywhere/inside.txt") is True
    for evil in ["/etc/passwd", "../escape", "work/../../etc", "~/x", "\x00"]:
        assert t.allows_path(evil) is False


# ---------------------------------------------------------------------------
# (e) an expired grant is denied by decide regardless of the tool
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tool", [
    "file_read", "search", "file_write", "doctor", "git_status", "not_a_tool",
])
def test_expired_grant_denied_for_every_tool(tool):
    expired = _tok(tools=["file_read", "search", "file_write"], writable=True,
                   paths=["**"], expires_at="2000-01-01T00:00:00Z")
    d = decide(_proposal(tool=tool, level=1), expired, now_epoch=FUTURE)
    # expiry is checked before the tool/scope, so even an unlisted tool reports
    # 'expired' — proving the denial is unconditional on the tool.
    assert not d.allow and "expired" in d.reason


def test_live_grant_allows_read_control():
    # Same shape, not yet expired → allowed. Proves the denials above are the
    # expiry check, not scope.
    d = decide(_proposal(tool="file_read"), _tok(), now_epoch=0)
    assert d.allow


def test_expiry_boundary_is_inclusive():
    epoch = calendar.timegm(time.strptime("2026-01-01T00:00:00Z",
                                          "%Y-%m-%dT%H:%M:%SZ"))
    t = _tok(expires_at="2026-01-01T00:00:00Z")
    assert t.expired(epoch - 1) is False
    assert t.expired(epoch) is True          # now >= expiry → lapsed


# ---------------------------------------------------------------------------
# (f) cost / byte ceilings deny an over-budget proposal
# ---------------------------------------------------------------------------
def test_within_cost_and_bytes_boundaries():
    t = _tok(max_cost_usd=1.0, max_bytes=1000)
    assert t.within_cost(1.0) and not t.within_cost(1.0 + 1e-6)
    assert t.within_bytes(1000) and not t.within_bytes(1001)


def test_decide_denies_cost_over_ceiling():
    t = _tok(max_cost_usd=0.10, max_bytes=100)
    d = decide(_proposal(estimated_cost_usd=1.00), t, now_epoch=0)
    assert not d.allow and "cost" in d.reason and "ceiling" in d.reason


def test_decide_denies_bytes_over_ceiling():
    t = _tok(max_cost_usd=0.10, max_bytes=100)
    d = decide(_proposal(estimated_bytes=10_000), t, now_epoch=0)
    assert not d.allow and "ceiling" in d.reason


def test_decide_allows_within_both_ceilings_control():
    t = _tok(max_cost_usd=0.10, max_bytes=100)
    d = decide(_proposal(estimated_cost_usd=0.05, estimated_bytes=50),
               t, now_epoch=0)
    assert d.allow


# ---------------------------------------------------------------------------
# (g) a widened-paths token still cannot escape cfg.root at the tool layer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("evil", ["../escape.txt", "/etc/passwd", "~/x"])
def test_wide_token_cannot_escape_root_at_write_handler(cfg, evil):
    # Even with paths widened to '/**'+'**' and writable=True, the write handler
    # refuses to leave the workspace.
    with pytest.raises(ToolError):
        file_write(cfg, {"path": evil, "content": "pwned"}, _wide_writable())
    assert not (cfg.root.parent / "escape.txt").exists()


def test_resolve_in_root_is_last_line_of_defense(cfg):
    assert resolve_in_root(cfg.root, "work/ok.md") is not None      # in-scope ok
    for evil in ["/etc/passwd", "../x", "~/x", "", "work/\x00"]:
        assert resolve_in_root(cfg.root, evil) is None


def test_symlink_escape_blocked_by_resolve_in_root(cfg, tmp_path):
    # The subtle escape the token's own scope test CANNOT catch: a symlink that
    # lives inside the workspace but points outside it. token.allows_path sees a
    # clean relative path and permits it; resolve_in_root resolves the link and
    # refuses because the real target is outside cfg.root.
    outside = tmp_path / "outside_ws"
    outside.mkdir()
    link = cfg.root / "sneaky_link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported on this platform")

    wide = _wide_writable()
    assert wide.allows_path("sneaky_link/pwned.txt") is True   # token can't see it
    with pytest.raises(ToolError):
        file_write(cfg, {"path": "sneaky_link/pwned.txt", "content": "x"}, wide)
    assert not (outside / "pwned.txt").exists()                # nothing escaped


def test_broker_never_auto_runs_write_even_with_wide_token(cfg, tmp_path):
    # A wide, writable token grants *scope*, not a bypass: the broker still gates
    # the level-2 write behind approval (no approver here), so nothing is written
    # and the attempt is recorded as tamper-evident evidence.
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute(
        {"tool": "file_write", "args": {"path": "work/x.md", "content": "y"}},
        _wide_writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert not (cfg.root / "work/x.md").exists()
    assert broker.ledger.verify().ok and broker.ledger.verify().count >= 2
