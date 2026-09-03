"""Bind CLEAR's model seam to CrossAudit's own provider layer.

Mapper and judge calls go through :func:`crossaudit.providers.resilience.complete`, so
they get the product's retries, fallback routes, circuit breaker and budget enforcement,
and they land in the project's ``usage.jsonl`` ledger like any other call. That is what
makes the benchmark's own cost visible next to the cost of the thing it measures.

Models are named by a ``vendor:model`` spec string, e.g. ``openai:gpt-5.6-terra``. The
spec is both the parameter the study reports and the key the client dispatches on, so a
run directory records exactly which model judged it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from crossaudit.config import Config, Role
from crossaudit.providers import specs
from crossaudit.providers import resilience

from clear import Completion


class SpecError(ValueError):
    """A malformed or unknown ``vendor:model`` spec."""


def parse_spec(spec: str) -> tuple[str, str]:
    """Split ``vendor:model``. The model half may itself contain colons."""
    if ":" not in spec:
        raise SpecError(
            f"{spec!r} is not a vendor:model spec (e.g. 'openai:gpt-5.6-terra'). "
            f"Known vendors: {', '.join(sorted(specs.SPECS))}"
        )
    vendor, model = spec.split(":", 1)
    vendor, model = vendor.strip(), model.strip()
    if vendor not in specs.SPECS:
        raise SpecError(f"unknown vendor {vendor!r}; known: {', '.join(sorted(specs.SPECS))}")
    if not model:
        raise SpecError(f"{spec!r} names no model")
    return vendor, model


def role_for(spec: str, *, reasoning_effort: str | None = None) -> Role:
    """Build a :class:`Role` from a ``vendor:model`` spec using the vendor's catalogue entry."""
    vendor, model = parse_spec(spec)
    provider_spec = specs.SPECS[vendor]
    return Role(
        provider=provider_spec.provider,
        model=model,
        vendor=vendor,
        key_env=provider_spec.key_env,
        base_url=None,
        reasoning_effort=reasoning_effort,
    )


def default_model(vendor: str) -> str:
    return specs.SPECS[vendor].default_model


def credential_present(spec: str) -> bool:
    vendor, _ = parse_spec(spec)
    return bool(os.environ.get(specs.SPECS[vendor].key_env, "").strip())


def missing_credentials(specs_wanted: list[str]) -> list[str]:
    """Which of these specs have no key in the environment. Empty means a live run is possible."""
    missing = []
    for spec in specs_wanted:
        vendor, _ = parse_spec(spec)
        key_env = specs.SPECS[vendor].key_env
        if not os.environ.get(key_env, "").strip():
            missing.append(f"{spec} (needs ${key_env})")
    return missing


@dataclass
class CrossAuditClient:
    """A :class:`clear.ModelClient` over the product's provider layer.

    ``cfg`` supplies the resilience policy, the budget guard and the ledger location.
    ``run_id`` and ``phase`` are attribution written onto every ledger line, so the
    benchmark's mapper/judge spend can be separated from the arms' generation spend
    afterwards.

    Two honest limitations, both inherited from the layer we are deliberately reusing:

    * ``max_tokens`` is **not** plumbed through ``resilience.complete``; adapters use their
      own default (4096). We accept the parameter to satisfy the protocol and ignore it.
    * ``temperature`` is likewise not a parameter -- the adapters decide it from the
      model's :class:`CapabilityCard` (0 where the model supports it). We therefore cannot
      *set* determinism, only record which model was used. See "Deviations" in RESULTS.md.
    """

    cfg: Config
    phase: str = "scoring"
    run_id: str = ""
    allow_custom: bool = False
    reasoning_effort: str | None = None
    #: Filled as specs are used, so a run can record exactly what it routed to.
    _roles: dict[str, Role] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._roles is None:
            self._roles = {}

    def role(self, spec: str) -> Role:
        if spec not in self._roles:
            self._roles[spec] = role_for(spec, reasoning_effort=self.reasoning_effort)
        return self._roles[spec]

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,  # noqa: ARG002 - see class docstring
        temperature: float = 0.0,  # noqa: ARG002 - see class docstring
    ) -> Completion:
        role = self.role(model)
        role_name = f"bench-{self.phase}"

        started = time.monotonic()
        reply = resilience.complete(
            self.cfg,
            role_name,
            role,
            system=system,
            prompt=user,
            allow_custom=self.allow_custom,
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        # Meter it exactly as the product meters its own calls. record_reply returns the
        # persisted event, which is where cost comes from -- there is no second price table.
        from crossaudit import usage

        event = usage.record_reply(
            root=self.cfg.root,
            state_dir=self.cfg.state_dir,
            role=role_name,
            phase=self.phase,
            vendor=role.vendor,
            provider=role.provider,
            model=role.model,
            reply=reply,
            system=system,
            prompt=user,
            base_url=role.base_url,
            context={
                "run_id": self.run_id,
                "duration_ms": duration_ms,
                "prices": self.cfg.prices,
            },
        )

        return Completion(
            text=reply.text,
            model=f"{role.vendor}:{role.model}",
            input_tokens=int(event.get("input", 0)),
            output_tokens=int(event.get("output", 0)),
            # An unpriced model yields None; treat as 0.0 but the ledger keeps the
            # billing_kind so a report can say "unpriced" rather than "free".
            cost_usd=float(event.get("api_value_usd") or 0.0),
            latency_s=duration_ms / 1000.0,
        )
