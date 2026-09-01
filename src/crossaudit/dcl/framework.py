"""Check registry and runner.

A check is a callable taking the materialised increment (path -> bytes) and
returning findings. Builtins are registered by name; third-party packs arrive
through the `crossaudit.checks` entry-point group in 0.4 and are, by design,
not discovered automatically — an entry point is arbitrary code execution, so
loading is allowlist-only (installer-design 05a).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Mapping

from ..errors import ConfigDenial

BLOCKER, ADVISORY = "BLOCKER", "ADVISORY"

#: What has become of a finding. `BLOCKER` was carrying two meanings at once —
#: *a model believes there is a problem* and *there is a problem* — and the
#: dashboard could only say "a defect was caught" because the structure had
#: nothing else to offer. These separate the claim from its fate.
#:
#: INTERNAL. No user-facing surface renders these words; a person must never
#: meet "alleged".
ALLEGED = "alleged"          # raised, nothing yet establishes it
CONFIRMED = "confirmed"      # a human or a deterministic check established it
FIXED = "fixed"              # the artefact changed; it no longer reproduces
WITHDRAWN = "withdrawn"      # the raiser retracted it
OVERRIDDEN = "overridden"    # a human ruled against it, on the record
UNRESOLVED = "unresolved"    # rounds ended, neither established nor retracted
FINDING_STATES = (ALLEGED, CONFIRMED, FIXED, WITHDRAWN, OVERRIDDEN, UNRESOLVED)


@dataclass(frozen=True)
class CheckContext:
    """Read-only facts a check may need beyond the increment bytes.

    Most checks are a pure function of the files; a few (e.g. source provenance)
    also need what the run actually did — here, the set of per-source provenance
    ids retrieved through the governed research tools. Empty by default, so a
    caller that has no such context (or no evidence ledger) is always safe.
    """
    governed_source_ids: frozenset = frozenset()


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    artifact: str
    observation: str
    check: str = ""
    #: Deterministic findings default to CONFIRMED, and that is the point of
    #: having states at all. This layer is verdict-in-code: `hard_failures` is
    #: computed without consulting any model, and `auditor/run.py` reads it
    #: BEFORE the model's verdict. A deterministic finding was never an
    #: allegation and must not be demoted into one.
    state: str = CONFIRMED

    def as_dict(self) -> dict:
        data = asdict(self)
        if self.check:
            data["implementation_code"] = data["rule"]
            data["rule"] = f"DCL:{self.check}"
        return data


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    contracts: dict[str, str] = field(default_factory=dict)

    @property
    def hard_failures(self) -> int:
        return sum(1 for f in self.findings if f.severity == BLOCKER)

    def as_dict(self) -> dict:
        return {
            "crossaudit_dcl_version": 3,
            "verdict": "BLOCKED" if self.hard_failures else "PASS",
            "total_hard_failures": self.hard_failures,
            "findings": [f.as_dict() for f in self.findings],
            "notes": self.notes,
            "contracts": self.contracts,
        }


CheckFn = Callable[[Mapping[str, bytes]], list[Finding]]
_REGISTRY: dict[str, CheckFn] = {}
_CONTRACTS: dict[str, str] = {}
_WANTS_CONTEXT: dict[str, bool] = {}


def register(name: str, fn: CheckFn, contract: str = "", *,
             wants_context: bool = False) -> None:
    _REGISTRY[name] = fn
    _CONTRACTS[name] = " ".join((contract or fn.__doc__ or "").split())
    _WANTS_CONTEXT[name] = wants_context


def available() -> list[str]:
    return sorted(_REGISTRY)


def contracts(names: list[str]) -> dict[str, str]:
    """Return the exact live contract for configured checks.

    Importing here keeps the registry lazy while ensuring this view and the
    runner can never disagree about which implementation is enabled.
    """
    from . import builtin, neutral, provenance  # noqa: F401

    missing = [n for n in names if n not in _REGISTRY]
    if missing:
        raise ConfigDenial(f"unknown checks {missing}; available: {available()}")
    return {name: _CONTRACTS[name] for name in names}


def describe(names: list[str]) -> str:
    live = contracts(names)
    lines = [
        "DETERMINISTIC CHECK CONTRACT (configured by `checks:` in crossaudit.yml)",
        "These checks run before the model and cannot be changed by amending AUDIT_RULES.md.",
    ]
    lines.extend(f"- {name}: {contract}" for name, contract in live.items())
    return "\n".join(lines)


def run_checks(files: Mapping[str, bytes], names: list[str],
               notes: list[str] | None = None,
               plugins: list[str] | None = None,
               context: CheckContext | None = None) -> CheckResult:
    """Run the named checks. An unknown name denies rather than being skipped.

    A check registered with ``wants_context=True`` is called ``fn(files, ctx)``;
    every other check stays ``fn(files)``. ``context`` is optional and defaults to
    an empty ``CheckContext``, so existing callers are unaffected.
    """
    from . import builtin, neutral, provenance  # noqa: F401  (registration on import)
    from .plugins import load_allowed

    load_allowed(plugins)
    ctx = context if context is not None else CheckContext()
    missing = [n for n in names if n not in _REGISTRY]
    if missing:
        raise ConfigDenial(f"unknown checks {missing}; available: {available()}")
    result = CheckResult(notes=list(notes or []), contracts=contracts(names))
    for name in names:
        fn = _REGISTRY[name]
        findings = fn(files, ctx) if _WANTS_CONTEXT.get(name) else fn(files)
        result.findings.extend(replace(f, check=name) for f in findings)
    # Final office documents are opaque containers, so this integrity boundary
    # is mandatory rather than a project-selectable quality rule.
    from . import documents
    result.contracts[documents.CHECK_NAME] = documents.INTEGRITY_CONTRACT
    result.findings.extend(documents.validate(files))
    # I8: an input we could not fully read — truncated at a blob bound, or left
    # unread because it was too large for the working-tree walk — can never end
    # in PASS.
    if any(n.startswith(("truncated:", "unread ")) for n in result.notes):
        result.findings.append(Finding(
            BLOCKER, "CA-META-004", "increment",
            "an input was truncated or too large to read before the checks ran; "
            "a partial read cannot yield PASS",
            check="input-bound"))
    return result
