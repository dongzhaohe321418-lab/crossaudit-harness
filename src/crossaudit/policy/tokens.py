"""The Capability Token — a scoped, expiring grant the model cannot widen.

A token is issued by CrossAudit for one run and names exactly what a proposal
may touch: which tools, which project-relative paths, whether writes are
allowed, which network hosts (empty ⇒ no network), and ceilings on runtime,
cost, and transferred bytes, plus an expiry and an optional single-use flag.
Every membership test is deny-by-default and escape-proof: an absolute path, a
``..`` traversal, an unknown tool, or an unlisted host is never allowed, and the
Generator has no way to mint or widen its own token.
"""
from __future__ import annotations

import calendar
import fnmatch
import posixpath
import time
from dataclasses import dataclass, field
from typing import Any

from ..errors import ConfigDenial

#: Fields a token dict may carry; anything else is a construction error so a
#: forged/typo'd grant fails closed rather than silently dropping a limit.
_ALLOWED_KEYS = frozenset({
    "project_id", "run_id", "tools", "paths", "writable", "hosts",
    "max_runtime_seconds", "max_cost_usd", "max_bytes", "background",
    "expires_at", "once",
})


class TokenError(ConfigDenial):
    """A capability token was malformed or refers to an impossible grant."""


def _safe_rel(rel: str) -> str | None:
    """Normalize a project-relative path, or None if it escapes the project.

    Absolute paths, ``~`` expansion, and any ``..`` component are refused — the
    normalization cannot be tricked into pointing outside the workspace.
    """
    if not isinstance(rel, str) or not rel:
        return None
    if rel.startswith("/") or rel.startswith("~") or "\x00" in rel:
        return None
    norm = posixpath.normpath(rel.replace("\\", "/"))
    if norm == "." or norm.startswith("/"):
        return None
    if norm == ".." or norm.startswith("../") or any(p == ".." for p in norm.split("/")):
        return None
    return norm


def _parse_iso_utc(stamp: str) -> float | None:
    """Epoch seconds for an ISO-8601 UTC stamp (``...Z``), or None if unparseable."""
    if not isinstance(stamp, str) or not stamp:
        return None
    s = stamp.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return calendar.timegm(time.strptime(s, fmt))
        except (ValueError, TypeError):
            continue
    # tolerate a +00:00 suffix
    if s.endswith("+00:00"):
        return _parse_iso_utc(s[:-6] + "Z")
    return None


@dataclass(frozen=True)
class CapabilityToken:
    project_id: str
    run_id: str
    tools: frozenset[str] = frozenset()
    paths: tuple[str, ...] = ()
    writable: bool = False
    hosts: frozenset[str] = frozenset()
    max_runtime_seconds: float = 0.0
    max_cost_usd: float = 0.0
    max_bytes: int = 0
    background: bool = False
    expires_at: str = ""
    once: bool = False
    _expires_epoch: float | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.project_id or not self.run_id:
            raise TokenError("a capability token needs a project_id and run_id")
        object.__setattr__(self, "tools", frozenset(self.tools))
        object.__setattr__(self, "paths", tuple(self.paths))
        object.__setattr__(self, "hosts", frozenset(self.hosts))
        for pat in self.paths:
            if not isinstance(pat, str) or not pat.strip():
                raise TokenError(f"invalid path pattern in token: {pat!r}")
        if self.expires_at:
            epoch = _parse_iso_utc(self.expires_at)
            if epoch is None:
                raise TokenError(f"unparseable token expiry: {self.expires_at!r}")
            object.__setattr__(self, "_expires_epoch", epoch)

    # -- membership tests (all deny-by-default) -------------------------------
    def allows_tool(self, name: str) -> bool:
        return bool(name) and name in self.tools

    def network_allowed(self) -> bool:
        return len(self.hosts) > 0

    def allows_host(self, host: str) -> bool:
        return bool(host) and host in self.hosts

    def allows_path(self, rel_path: str) -> bool:
        p = _safe_rel(rel_path)
        if p is None:
            return False
        for pat in self.paths:
            pat = pat.strip()
            if not pat:
                continue
            if pat.endswith("/**"):
                base = pat[:-3].strip("/")
                if base == "" or p == base or p.startswith(base + "/"):
                    return True
            if fnmatch.fnmatch(p, pat):
                return True
            bare = pat.strip("/")
            if bare and (p == bare or p.startswith(bare + "/")):
                return True
        return False

    def expired(self, now_epoch: float) -> bool:
        """Whether the grant has lapsed at ``now_epoch`` (caller supplies the clock)."""
        return self._expires_epoch is not None and now_epoch >= self._expires_epoch

    def within_cost(self, estimated_usd: float) -> bool:
        return self.max_cost_usd <= 0.0 or estimated_usd <= self.max_cost_usd

    def within_bytes(self, estimated_bytes: int) -> bool:
        return self.max_bytes <= 0 or estimated_bytes <= self.max_bytes

    # -- construction ---------------------------------------------------------
    @classmethod
    def parse(cls, raw: Any) -> "CapabilityToken":
        """Build a token from a plain dict, refusing unknown keys."""
        if not isinstance(raw, dict):
            raise TokenError("a capability token must be a mapping")
        unknown = set(raw) - _ALLOWED_KEYS
        if unknown:
            raise TokenError(f"unknown token fields: {sorted(unknown)}")
        return cls(
            project_id=str(raw.get("project_id", "")),
            run_id=str(raw.get("run_id", "")),
            tools=frozenset(str(t) for t in raw.get("tools", []) or []),
            paths=tuple(str(p) for p in raw.get("paths", []) or []),
            writable=bool(raw.get("writable", False)),
            hosts=frozenset(str(h) for h in raw.get("hosts", []) or []),
            max_runtime_seconds=float(raw.get("max_runtime_seconds", 0) or 0),
            max_cost_usd=float(raw.get("max_cost_usd", 0) or 0),
            max_bytes=int(raw.get("max_bytes", 0) or 0),
            background=bool(raw.get("background", False)),
            expires_at=str(raw.get("expires_at", "") or ""),
            once=bool(raw.get("once", False)),
        )
