"""Named check profiles — strictness as a legible dial, not a flat name list.

CrossAudit's identity (independent cross-vendor audit, evidence ledger, signed
receipts, per-call human approval) is always on and domain-agnostic. The
deterministic checks are an OPTIONAL rigor layer on top, and `checks:` in
``crossaudit.yml`` selects how much of it runs. Rather than hand-listing opaque
check names, a project can name a profile:

    off      core audit chain only (no deterministic checks)
    general  the domain-neutral pack — the light default: parses, dangling
             declarations, broken links (advisory), leftover placeholders
             (advisory). Binds no data format; fits code, docs, web, contracts.
    science  structured-science rigor: schema, units, convergence, provenance
             (inputs that exist and are cited exactly).
    science-ai4s
             science plus the AI4S declaration pack: numeric validity,
             declared ranges, recomputed derivations, split integrity,
             declared claims (blockers) and reproducibility / precision
             (advisory). Opt-in by name; `science` is unchanged.

An explicit list is still accepted verbatim, so a project can compose its own mix
(e.g. the general pack plus ``complete-strict`` to make placeholders hard-fail).
"""
from __future__ import annotations

from ..errors import ConfigDenial

#: Named profiles → the check list each expands to. Kept minimal and honest:
#: exactly the packs that exist today, now addressable by name.
PROFILES: dict[str, list[str]] = {
    "off": [],
    "general": ["parseable", "declared", "internal", "complete"],
    # §1's gap — a quantity citing an input that is listed and does not exist —
    # is closed INSIDE `check_provenance`, not by adding the neutral pack's
    # `declared` here. `declared` reads every YAML's `sources`, `requires` and
    # `depends_on` as filenames as well, so bringing it into science blocked
    # legitimate metadata (`sources: [doi:10.1234/x]`); the profile stays as it
    # was and the check got stronger, which is the direction that is allowed.
    #
    # `number_source` is here since D164 ruling 1 (2026-09-07). Its history is
    # the reason the list is guarded by name: D157 put it in both profiles;
    # Arm 2 (`benchmarks/expertlongbench/RESULTS-ARM2.md`) ran it against what
    # a real generator writes and **no annotation row of 215 passed, 24 of 24
    # drafts BLOCKED**, because the generator is never shown line numbers and
    # could not address the lines the contract asked for; D158 took it out the
    # same day. Content addressing replaced line numbers (D159), a frozen gold
    # licensed five containment extensions measured at W = 0 each (D160,
    # slices 4–8), and Arm 5 (`RESULTS-ARM5.md`) then measured the shipped
    # check on every T03 instance at **4 of 398 correct annotations blocked**
    # (Wilson 0.39–2.56%) — the preregistered §8g PASS band. It sits LAST so
    # that a project's `checks:` reads as the pack plus the annotation check
    # it depends on; `scaffold.SCIENCE_CHECKS` carries the same list, so a
    # science project gets the check, the skill that asks the generator for
    # the annotation, and the blocker together (the design's §6.4 failure — a
    # check on without the skill — is what the two lists moving together
    # prevents). `general` and `research` are untouched; the check remains
    # selectable by name everywhere, as it was between D158 and D164.
    "science": ["schema", "units", "convergence", "provenance", "number_source"],
    # The general pack plus the opt-in, deterministic citation-provenance check:
    # a report may only cite sources it fetched through a governed research tool.
    "research": ["parseable", "declared", "internal", "complete", "source_provenance"],
    # The AI4S declaration pack (`dcl/ai4s.py`, `benchmarks/ai4s/DESIGN.md` §4)
    # is a SEPARATE profile and not an extension of `science`, because a
    # project that already wrote `checks: science` must not wake up to new
    # blockers (AGENTS.md §1.2). Every pack check is silent where nothing is
    # declared, but `complete` and `numeric_validity` are not declaration-gated,
    # and an existing science increment carrying a `"value": null` or a
    # leftover TODO would change verdict. It is `science` byte-for-byte plus the
    # pack, so the arms of the AI4S measurement differ in the pack and nothing
    # else; `complete` joins because a placeholder left in a science deliverable
    # is a defect class the measurement counts (D15).
    "science-ai4s": ["schema", "units", "convergence", "provenance", "number_source",
                     "complete", "numeric_validity", "range_rules", "derivations",
                     "split_integrity", "claims", "repro_declared", "precision"],
}

DEFAULT_PROFILE = "general"


def resolve(value) -> list[str]:
    """Turn a `checks:` value into the concrete check list.

    Accepts a profile name (``"general"``), an explicit list of check names
    (returned verbatim, so custom mixes keep working), or an empty list (which
    means exactly "no checks", never the default). An unknown profile name denies
    rather than silently running the wrong rigor.
    """
    if isinstance(value, str):
        name = value.strip()
        if name not in PROFILES:
            raise ConfigDenial(
                f"unknown check profile {name!r}; choose one of "
                f"{sorted(PROFILES)} or list check names explicitly")
        return list(PROFILES[name])
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ConfigDenial("checks must be a profile name or a list of check names")
        return list(value)
    raise ConfigDenial("checks must be a profile name or a list of check names")
