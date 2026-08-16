"""Capability tokens + the deterministic policy engine.

These pin the boundary the Agentic Runtime rests on: a grant only permits what
it explicitly lists, paths cannot escape the workspace, network is denied unless
a host is listed, grants expire, ceilings hold, and the engine decides with no
model in the loop — every unlisted or out-of-scope proposal fails closed.
"""
from __future__ import annotations

import pytest

from crossaudit.policy import CapabilityToken, TokenError, decide


def _tok(**kw):
    base = dict(project_id="p1", run_id="r1", tools=["file_read", "search"],
                paths=["work/**"], expires_at="2100-01-01T00:00:00Z")
    base.update(kw)
    return CapabilityToken.parse(base)


# ---- token: construction ----
def test_parse_rejects_unknown_fields():
    with pytest.raises(TokenError):
        CapabilityToken.parse({"project_id": "p", "run_id": "r", "wat": 1})


def test_parse_requires_project_and_run():
    with pytest.raises(TokenError):
        CapabilityToken.parse({"project_id": "", "run_id": "r"})


def test_bad_expiry_is_rejected():
    with pytest.raises(TokenError):
        _tok(expires_at="not-a-date")


# ---- token: tool + path scoping ----
def test_allows_only_listed_tools():
    t = _tok()
    assert t.allows_tool("file_read") and not t.allows_tool("write_file")


def test_path_scope_allows_in_and_denies_out():
    t = _tok(paths=["work/**"])
    assert t.allows_path("work/review.md")
    assert t.allows_path("work/sub/a.txt")
    assert not t.allows_path("secret.env")
    assert not t.allows_path("other/x")


@pytest.mark.parametrize("evil", [
    "/etc/passwd", "../outside", "work/../../etc/passwd", "~/x", "work/../secret",
])
def test_path_scope_is_escape_proof(evil):
    assert not _tok(paths=["work/**"]).allows_path(evil)


def test_bare_dir_and_glob_patterns():
    assert _tok(paths=["work"]).allows_path("work/a")          # bare dir prefix
    assert _tok(paths=["*.md"]).allows_path("readme.md")        # glob
    assert not _tok(paths=["*.md"]).allows_path("readme.txt")


# ---- token: network / expiry / ceilings ----
def test_network_denied_unless_host_listed():
    assert not _tok().network_allowed()
    t = _tok(hosts=["api.example.com"])
    assert t.network_allowed()
    assert t.allows_host("api.example.com") and not t.allows_host("evil.com")


def test_expiry_uses_caller_clock():
    t = _tok(expires_at="2026-01-01T00:00:00Z")
    assert not t.expired(now_epoch=0)                # before
    assert t.expired(now_epoch=4102444800)           # year 2100
    assert not _tok(expires_at="").expired(now_epoch=4102444800)  # no expiry set


def test_cost_and_byte_ceilings():
    t = _tok(max_cost_usd=1.0, max_bytes=1000)
    assert t.within_cost(0.5) and not t.within_cost(2.0)
    assert t.within_bytes(500) and not t.within_bytes(2000)
    assert _tok(max_cost_usd=0).within_cost(9e9)     # 0 == unlimited


# ---- engine: decisions ----
def _proposal(**kw):
    base = dict(tool="file_read", level=1, writes=False, paths=["work/review.md"])
    base.update(kw)
    return base


def test_readonly_in_scope_is_auto_allowed():
    d = decide(_proposal(), _tok(), now_epoch=0)
    assert d.allow and d.auto and not d.requires_approval


def test_unknown_tool_denied():
    d = decide(_proposal(tool="rm_rf"), _tok(), now_epoch=0)
    assert not d.allow and "not in this grant" in d.reason


def test_out_of_scope_path_denied():
    d = decide(_proposal(paths=["/etc/passwd"]), _tok(), now_epoch=0)
    assert not d.allow and "outside this grant" in d.reason


def test_write_under_readonly_grant_denied():
    d = decide(_proposal(tool="file_read", writes=True), _tok(), now_epoch=0)
    assert not d.allow and "read-only" in d.reason


def test_network_host_enforced():
    p = _proposal(tool="search", host="evil.com")
    assert not decide(p, _tok(), now_epoch=0).allow            # no network at all
    d = decide(p, _tok(tools=["search"], hosts=["ok.com"]), now_epoch=0)
    assert not d.allow and "not in this grant" in d.reason


def test_expired_grant_denied():
    d = decide(_proposal(), _tok(expires_at="2000-01-01T00:00:00Z"), now_epoch=4102444800)
    assert not d.allow and "expired" in d.reason


def test_ceilings_enforced_by_engine():
    t = _tok(max_cost_usd=0.10, max_bytes=100)
    assert not decide(_proposal(estimated_cost_usd=1.0), t, now_epoch=0).allow
    assert not decide(_proposal(estimated_bytes=9999), t, now_epoch=0).allow


def test_higher_level_requires_approval_even_in_scope():
    # A level-2 (workspace edit) proposal, path in scope + writable grant:
    # policy permits it but flags approval — never auto.
    t = _tok(writable=True)
    d = decide(_proposal(tool="file_read", level=2, writes=True), t, now_epoch=0)
    assert d.allow and d.requires_approval and not d.auto
