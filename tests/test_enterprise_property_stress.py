"""Property/stress attacks on the runtime's load-bearing invariants.

Four invariants are hammered over many/diverse inputs, each phrased so the test
would FAIL if the corresponding defense were removed:

(a) token path-safety — over a large, adversarial-and-random corpus of path
    strings (traversal, absolute, ``~``, NUL, unicode, huge, mixed separators),
    ``CapabilityToken(paths=("work/**",)).allows_path`` is NEVER True for a
    string that does not genuinely normalize to inside ``work/``, and
    ``resolve_in_root`` NEVER returns a path outside ``cfg.root`` (symlink
    escapes included);
(b) ledger integrity at scale — 500 appends verify ok, with contiguous seqs
    0..499 and every ``prev`` strictly linking the prior digest;
(c) determinism — ``decide(proposal, token, now_epoch)`` returns byte-identical
    Decision fields across repeated calls and across freshly-parsed identical
    tokens, for a wide variety of proposals;
(d) registry shape — every registered ToolSpec has a level in 0..6 and a
    callable handler.

These mirror the call shapes in test_capability_policy.py / test_evidence_ledger.py
and use the real code paths (no mocks) and the conftest ``cfg``/``tmp_path``.
"""
from __future__ import annotations

import posixpath
import random

import pytest

from crossaudit.broker import full_registry
from crossaudit.broker.recovery import resolve_in_root
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken, Decision, decide


# --------------------------------------------------------------------------
# Shared: the grant every path-safety test attacks, and an INDEPENDENT oracle
# for "does this string genuinely resolve to inside work/?" (deny-by-default on
# absolute paths, ``~``, NUL, and any surviving ``..`` component).
# --------------------------------------------------------------------------
def _tok(**kw) -> CapabilityToken:
    base = dict(project_id="p1", run_id="r1", tools=["file_read", "search"],
                paths=["work/**"], expires_at="2100-01-01T00:00:00Z")
    base.update(kw)
    return CapabilityToken.parse(base)


def _safe_norm(s) -> str | None:
    """Oracle: the normalized project-relative path, or None if ``s`` escapes.

    Deliberately independent of the token internals: an absolute path, ``~``
    expansion, a NUL byte, or ANY ``..`` component that survives normalization
    means "escapes the project" -> None.
    """
    if not isinstance(s, str) or not s:
        return None
    if s.startswith("/") or s.startswith("~") or "\x00" in s:
        return None
    norm = posixpath.normpath(s.replace("\\", "/"))
    if norm == "." or norm.startswith("/"):
        return None
    if any(p == ".." for p in norm.split("/")):
        return None
    return norm


def _under_work(s) -> bool:
    """True iff ``s`` genuinely resolves to ``work`` or something inside it."""
    n = _safe_norm(s)
    return n is not None and (n == "work" or n.startswith("work/"))


# Hand-verified escapes: allows_path("work/**", ...) must be False for every one.
_EVIL_PATHS = [
    "", ".", "/", "//", "/etc/passwd", "/work/x", "/../work",
    "..", "../", "../x", "../../etc/passwd", "work/../../etc/passwd",
    "work/../secret", "work/../../work", "a/../../b", "./../x",
    "work/./../../x", "work/sub/../../../root", "..\\..\\etc",
    "work\\..\\..\\etc", "~", "~/x", "~root/.ssh/id_rsa",
    "\x00", "work/\x00etc", "secret.env", "other/x", "workshop/x",
    "wörk/secret", "ｗork/secret",          # look-alike 'w' -> not 'work'
    "work⁄..⁄..⁄etc",         # U+2044 fraction slash, not a real /
    "../" * 500 + "etc", "a/" * 300 + "../../../../etc",
]

# Genuinely-inside-work strings: allows_path must be True for every one.
_GOOD_PATHS = [
    "work", "work/", "work/.", "work/a", "work/review.md",
    "work/sub/a.txt", "work/sub/../sub2/b",     # internal .. that stays inside
    "work/../work", "work/./deep/file", "work\\sub\\a",   # backslashes -> /
    "work/café.md", "work/‮.md", "work/" + "a" * 4000,
    "work/*", "work/[weird]name",
]


def _fuzz_paths(n: int) -> list[str]:
    """Deterministic pseudo-random corpus mixing escaping and benign segments."""
    rng = random.Random(20260817)
    ok = ["work", "sub", "a", "b", "review.md", "café.md", "deep", "x", "."]
    bad = ["..", "", "/etc", "~", "\x00", "..\\..", "⁄", "%2e%2e", "//"]
    out: list[str] = []
    for _ in range(n):
        depth = rng.randint(1, 6)
        pool = ok + (bad if rng.random() < 0.55 else [])
        parts = [rng.choice(pool) for _ in range(depth)]
        sep = rng.choice(["/", "\\", "/"])
        out.append(sep.join(parts))
    return out


# --------------------------------------------------------------------------
# (a) token path-safety over a large diverse corpus
# --------------------------------------------------------------------------
def test_allows_path_never_escapes_work_curated():
    t = _tok(paths=["work/**"])
    for evil in _EVIL_PATHS:
        assert not t.allows_path(evil), f"escaped grant via {evil!r}"
    for good in _GOOD_PATHS:
        assert t.allows_path(good), f"legit in-scope path wrongly denied: {good!r}"


def test_allows_path_security_direction_holds_over_fuzz():
    """The security invariant: allows_path(s) True => s genuinely inside work/.

    Checked over curated + a few hundred pseudo-random strings. A defense
    regression (e.g. dropping the ``..``/absolute normalization) would let an
    escaping string return True while the independent oracle says it is outside.
    """
    t = _tok(paths=["work/**"])
    corpus = _EVIL_PATHS + _GOOD_PATHS + _fuzz_paths(400)
    allowed = denied = 0
    for s in corpus:
        if t.allows_path(s):
            allowed += 1
            assert _under_work(s), f"allows_path leaked outside work/: {s!r}"
        else:
            denied += 1
    # The corpus must actually exercise BOTH outcomes, or the check is vacuous.
    assert allowed > 0 and denied > 0


def test_resolve_in_root_never_escapes_root_over_fuzz(cfg):
    root_resolved = cfg.root.resolve()
    corpus = _EVIL_PATHS + _GOOD_PATHS + _fuzz_paths(400)
    for s in corpus:
        res = resolve_in_root(cfg.root, s)
        if res is None:
            continue
        rp = res.resolve()
        assert root_resolved in rp.parents, (
            f"resolve_in_root returned {rp} outside root {root_resolved} for {s!r}")


def test_resolve_in_root_refuses_symlink_escape(cfg):
    """Defense-in-depth: a symlink inside root that points OUT must not be a door."""
    outside = cfg.root.parent / "outside_secret"
    outside.mkdir(exist_ok=True)
    (outside / "passwd").write_text("secret")
    link = cfg.root / "evil_link"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(outside)
    # The link itself resolves out of root, and so does anything under it.
    assert resolve_in_root(cfg.root, "evil_link") is None
    assert resolve_in_root(cfg.root, "evil_link/passwd") is None


# --------------------------------------------------------------------------
# (b) ledger integrity at scale
# --------------------------------------------------------------------------
def test_500_appends_verify_contiguous_and_strictly_chained(tmp_path):
    led = EvidenceLedger(tmp_path / "evidence.jsonl")
    n = 500
    heads = [led.append("note", run_id="r", payload={"i": i}, ts=f"t{i}")
             for i in range(n)]

    report = led.verify()
    assert report.ok, report.error
    assert report.count == n
    assert report.head == heads[-1]

    rows = led.entries()
    assert len(rows) == n
    # contiguous 0..n-1, no gaps or duplicates
    assert [e["seq"] for e in rows] == list(range(n))
    # strict chaining: genesis prev == "", each prev links the prior digest,
    # and the recorded digests match the returned heads.
    assert rows[0]["prev"] == ""
    for i in range(n):
        assert rows[i]["digest"] == heads[i]
        if i > 0:
            assert rows[i]["prev"] == rows[i - 1]["digest"], f"chain broke at {i}"


# --------------------------------------------------------------------------
# (c) decide() determinism over a variety of proposals
# --------------------------------------------------------------------------
def _proposal(**kw) -> dict:
    base = dict(tool="file_read", level=1, writes=False, paths=["work/review.md"])
    base.update(kw)
    return base


_PROPOSALS = [
    _proposal(),                                             # in-scope read (auto)
    _proposal(tool="rm_rf"),                                 # unknown tool
    _proposal(paths=["/etc/passwd"]),                        # out-of-scope path
    _proposal(paths=["work/../../etc"]),                     # traversal path
    _proposal(tool="file_read", writes=True),               # write under read-only
    _proposal(tool="search", host="evil.com"),              # host, no network
    _proposal(estimated_cost_usd=99.0),                      # cost ceiling
    _proposal(estimated_bytes=10 ** 9),                      # byte ceiling
    _proposal(tool="file_read", level=2, writes=True),      # needs approval tier
    _proposal(level=6, tool="file_read"),                    # high level, in scope
    "not-a-mapping",                                         # malformed proposal
]


def test_decide_is_deterministic_across_repeats_and_token_rebuilds():
    now = 1_700_000_000.0
    for spec in _PROPOSALS:
        # Fixed token, repeated calls -> identical Decision (all fields).
        t = _tok(writable=True, max_cost_usd=1.0, max_bytes=1000,
                 tools=["file_read", "search"], hosts=["ok.com"])
        first = decide(spec, t, now_epoch=now)
        assert isinstance(first, Decision)
        for _ in range(8):
            again = decide(spec, t, now_epoch=now)
            assert again == first, f"non-deterministic decision for {spec!r}"
            # spell out the fields so a divergence names itself
            assert (again.allow, again.reason, again.level,
                    again.requires_approval) == (
                    first.allow, first.reason, first.level,
                    first.requires_approval)
        # A freshly parsed but identical token must decide identically, too.
        t2 = _tok(writable=True, max_cost_usd=1.0, max_bytes=1000,
                  tools=["file_read", "search"], hosts=["ok.com"])
        assert decide(spec, t2, now_epoch=now) == first


def test_decide_is_deterministic_over_random_proposals():
    rng = random.Random(4242)
    tools = ["file_read", "search", "file_write", "rm_rf"]
    paths = [["work/a.md"], ["/etc/passwd"], ["work/../x"], ["work/sub/b"]]
    now = 1_700_000_000.0
    t = _tok(writable=False, tools=["file_read", "search"])
    for _ in range(200):
        spec = _proposal(
            tool=rng.choice(tools),
            level=rng.randint(0, 6),
            writes=rng.random() < 0.5,
            paths=rng.choice(paths),
            estimated_cost_usd=rng.choice([0.0, 5.0]),
            estimated_bytes=rng.choice([0, 10 ** 9]),
        )
        d1 = decide(spec, t, now_epoch=now)
        d2 = decide(spec, t, now_epoch=now)
        assert d1 == d2


# --------------------------------------------------------------------------
# (d) registry shape: levels in 0..6, every tool has a callable handler
# --------------------------------------------------------------------------
def test_every_registered_tool_has_valid_level_and_handler():
    reg = full_registry()
    names = reg.names()
    assert names, "the full registry should not be empty"
    for name in names:
        spec = reg.get(name)
        assert spec is not None, f"{name!r} in names() but get() returned None"
        assert isinstance(spec.level, int), f"{name!r} level is not an int"
        assert 0 <= spec.level <= 6, f"{name!r} level {spec.level} outside 0..6"
        assert callable(spec.handler), f"{name!r} has no callable handler"
    # catalog() levels agree with the specs (same allowlist, same levels).
    cat = {row["name"]: row["level"] for row in reg.catalog()}
    assert cat == {n: reg.get(n).level for n in names}
