"""The tool registry — an allowlist of everything the model may propose.

A tool is known only if it is registered by name (mirroring
``dcl/plugins.load_allowed``); an unregistered name is refused before any policy
check. Each ``ToolSpec`` declares its permission level and which of its
arguments are project-relative paths or a network host, so the broker can build
a policy proposal generically without hard-coding tool internals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..errors import ConfigDenial


class ToolError(ConfigDenial):
    """A registered tool failed while executing (a normal, recorded outcome)."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    level: int
    writes: bool
    needs_network: bool
    #: handler(cfg, args, token) -> dict. Returns a structured result; raises
    #: ToolError on an expected failure. Must have no side effect beyond what
    #: its level declares.
    handler: Callable
    summary: str = ""
    #: arg keys whose values are project-relative paths (fed to policy scoping).
    path_args: tuple[str, ...] = ()
    #: arg key whose value is a network host, if any.
    host_arg: str | None = None
    est_cost_usd: float = 0.0
    est_bytes: int = 0
    #: output keys that are SAFE to record as evidence (hashes/metadata, never
    #: raw content). The broker copies only these from the result into the
    #: ledger, so e.g. a write's before/after hashes are auditable while a read's
    #: raw bytes never enter the ledger.
    evidence_fields: tuple[str, ...] = ()


@dataclass
class ToolRegistry:
    _tools: dict = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if not spec.name:
            raise ConfigDenial("a tool must have a name")
        if spec.name in self._tools:
            raise ConfigDenial(f"tool {spec.name!r} is already registered")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def catalog(self) -> list[dict]:
        """What the model is told it may propose — names, levels, scope hints."""
        return [{"name": s.name, "level": s.level, "writes": s.writes,
                 "needs_network": s.needs_network, "summary": s.summary}
                for s in sorted(self._tools.values(), key=lambda s: s.name)]
