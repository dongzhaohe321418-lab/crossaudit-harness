"""One audit cycle: DCL, model audit, verdict synthesis, report, receipt.

Verdict synthesis is code, never model output (I4), and every path that is not
a clean, valid, model-backed PASS lands somewhere other than PASS (I8):

    escalation lock            -> ESCALATE   (an escalated cycle is not routed around)
    DCL hard failure           -> BLOCKED    (dominates any model opinion)
    invalid or failed audit    -> ESCALATE
    prompt bound exceeded      -> ESCALATE   (the model did not see everything)
    unstarted scope            -> ESCALATE   (NOTHING_AUDITED: an empty scope is not clean)
    no model ran               -> DCL_ONLY   (never a conforming PASS)
    otherwise                  -> the model's own verdict
    lone model BLOCKER         -> BLOCKED by default (bounded revision, recorded as
                                  unverified); ESCALATE under
                                  authority.lone_model_blocker: escalate

The evidence-authority layer (authority.py) runs AFTER the ladder and derives
from its result; it changes the verdict only under that opt-in dial.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config, Role, heterogeneity
from ..dcl import run_checks
from ..errors import ConfigDenial, Denial, ProviderDenial
from ..providers import resilience as provider_resilience
from ..providers.registry import NON_EVIDENTIAL
from ..runtime.runs import PROVIDER_WAIT_CATEGORIES
from ..usage import record_completion
from . import prompt as prompt_mod
from .authority import decide_authority, records_from_audit
from .validate import known_rules, parse_reply, validate_reply

#: Deterministic checks named in words for the phase narration (D150). A
#: plugin or future check falls back to its configured name — a word, not an
#: id. The console maps these English words to Chinese; one list, here.
CHECK_NAMES = {
    "schema": "Schema",
    "units": "Units",
    "convergence": "Convergence",
    "provenance": "Provenance",
    "parseable": "Parseable",
    "source_provenance": "Source provenance",
    "documents": "Document integrity",
}


def check_words(name: str) -> str:
    return CHECK_NAMES.get(name, name.replace("_", " "))


@dataclass
class AuditOutcome:
    verdict: str
    dcl: dict
    model_reply: dict | None
    invalid_reason: str | None
    integrity: str
    exchange: dict
    prompt_sha256: str
    report: str
    #: The evidence-authority record (authority.py); empty when an outcome is
    #: constructed by hand, so every existing construction keeps working.
    authority: dict = field(default_factory=dict)


def finding_states(dcl: dict, model_reply: dict | None) -> list[dict]:
    """Every finding this round raised, with what has become of it so far.

    Two tiers, two honest defaults. Deterministic findings are CONFIRMED: that
    layer is verdict-in-code and never consulted a model. Model findings are
    ALLEGED: raised, with nothing yet establishing them — which is what makes a
    confirmation rate computable later.

    INTERNAL. Nothing renders these words to a person, and the report is
    deliberately not their home: it is the surface a user reads.
    """
    from ..dcl.framework import ALLEGED, CONFIRMED, FINDING_STATES

    rows = []
    for f in dcl.get("findings", []):
        # The default lives here as well as on the dataclass: a plain dict
        # (checks.json read back, a hand-built fixture) without the key is a
        # deterministic finding all the same, and an unknown word is a bug,
        # not a seventh state.
        state = f.get("state") or CONFIRMED
        if state not in FINDING_STATES:
            raise ValueError(f"finding state {state!r} is not one of {FINDING_STATES}")
        rows.append({"tier": "deterministic", "severity": f.get("severity", ""),
                     "rule": f.get("rule", ""), "artifact": f.get("artifact", "?"),
                     "state": state})
    for f in (model_reply or {}).get("findings", []) or []:
        rows.append({"tier": "model", "severity": f.get("severity", ""),
                     "rule": f.get("rule", ""),
                     "artifact": f.get("artifact", "?"), "state": ALLEGED})
    return rows


def dcl_source_digest() -> str:
    """Hash of the check layer's own source, so a receipt pins what ran."""
    # Allowlisted check packs contribute findings with the same authority as
    # the builtin layer; leave their code out of the digest and two
    # byte-identical receipts could hide different plugin implementations.
    from ..dcl.plugins import loaded_sources
    plugin_sources = loaded_sources()

    if getattr(sys, "frozen", False):
        identity_file = Path(getattr(sys, "_MEIPASS", "")) / "crossaudit-build.json"
        try:
            value = json.loads(identity_file.read_text(encoding="utf-8"))
            digest = str(value["dcl_source_sha256"])
            if len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest):
                if not plugin_sources:
                    return digest
                # The baked identity pins only the bundled layer; packs loaded
                # at runtime are check code it never saw, so fold them in.
                h = hashlib.sha256(digest.encode())
                for tag, data in plugin_sources:
                    h.update(tag.encode() + b"\x00")
                    h.update(data)
                return h.hexdigest()
        except (OSError, ValueError, KeyError, TypeError):
            pass
        raise ConfigDenial(
            "the frozen application is missing its deterministic-layer identity; "
            "reinstall CrossAudit from a verified build")
    import crossaudit.dcl as pkg

    root = Path(pkg.__file__).parent
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    # The mandatory document check delegates container parsing and semantic
    # recovery to this module; bind that implementation into the DCL digest.
    from crossaudit import document_export
    h.update(b"document_export.py")
    h.update(Path(document_export.__file__).read_bytes())
    # With no packs loaded this adds nothing: a receipt minted without plugins
    # hashes exactly as it did before packs could join the digest.
    for tag, data in plugin_sources:
        h.update(tag.encode() + b"\x00")
        h.update(data)
    return h.hexdigest()


def render_report(*, cfg: Config, sha: str, round_: int, verdict: str, dcl: dict,
                  reply: dict | None, invalid: str | None, constitution_commit: str,
                  provider: str, model: str, vendor: str | None = None,
                  reasoning_effort: str | None = None,
                  provider_failure: str | None = None,
                  authority: dict | None = None) -> str:
    lines = [
        f"# Audit Report — {cfg.science_repo}@{sha[:12]}",
        "",
        "| | |",
        "|---|---|",
        f"| verdict | **{verdict}** |",
        f"| round | {round_} |",
        f"| constitution | `{constitution_commit[:12]}` |",
        (f"| auditor | `{provider}:{model}` (vendor {vendor or cfg.auditor.vendor}; effort "
         f"{reasoning_effort or 'provider-default'}) |"),
        f"| deterministic layer | {dcl['total_hard_failures']} hard failure(s) |",
    ]
    if authority:
        # verify() binds this row to the receipt's authority block, mapping the
        # plain words back to the route name; the policy version stays in the
        # receipt, where a verifier reads it, and out of the report.
        from .authority import ROUTE_LABELS
        lines += [f"| evidence route | **{ROUTE_LABELS[authority['route']]}** |"]
    lines += [
        "",
        "## Deterministic findings",
        "",
    ]
    if dcl["findings"]:
        for f in dcl["findings"]:
            lines.append(f"### [{f['severity']}] {f['rule']} — {f['artifact']}")
            if f.get("check"):
                origin = ("mandatory runtime document-integrity boundary"
                          if f["check"] == "document-export-integrity" else
                          "configured in `crossaudit.yml`; not a Constitution amendment")
                lines.append(f"Machine check: `{f['check']}` ({origin})")
            lines.append(f"{f['observation']}")
            lines.append("")
    else:
        lines += ["None.", ""]

    lines += ["## Model findings", ""]
    if provider_failure:
        # A provider failure is not a finding. This paragraph deliberately
        # does not use the "### [SEVERITY] RULE — artifact" finding shape:
        # everything in that shape is machine-parsed as audit content
        # (dispute.parse_findings, generator.render_findings, the decision
        # modal), and an outage rendered as a CA-META-002 BLOCKER was fed to
        # the generator to "fix" and escalated with content guidance.
        lines += [f"Model audit unavailable (provider failure: {provider_failure}).",
                  "No model reviewed this increment; the verdict above is a "
                  "deterministic-tier result only.", ""]
    elif invalid:
        lines += ["### [BLOCKER] CA-META-002 — invalid Auditor reply",
                  (f"The model audit was rejected: {invalid}. Under I3 an invalid audit "
                   f"escalates; it can never pass an increment."), ""]
    elif reply:
        if reply.get("findings"):
            for f in reply["findings"]:
                lines.append(f"### [{f['severity']}] {f['rule']} — {f.get('artifact', '?')}")
                lines.append(f"{f['observation']}")
                lines.append("")
        else:
            lines += ["None.", ""]
        lines += [f"Rules applied: {', '.join(reply.get('sections_applied', []))}", ""]
    else:
        lines += ["No model audit ran; this is a deterministic-tier result only.", ""]
    if authority:
        from ..dcl.framework import CONFIRMED
        lines += ["## Evidence", ""]
        lines += [str(sentence) for sentence in authority.get("rationale", ())]
        rows = authority.get("evidence") or []
        if rows:
            lines += ["", "| finding | artifact | tier | verified by a check |",
                      "|---|---|---|---|"]
            for row in rows:
                verified = "yes" if row.get("state") == CONFIRMED else "no"
                lines.append(f"| {row['finding_key'].split('@', 1)[0]} | "
                             f"{row['artifact']} | {row['tier']} | {verified} |")
        else:
            lines += ["", "No finding was raised by either tier."]
        lines.append("")
    return "\n".join(lines)


def run_audit(*, cfg: Config, sha: str, round_: int, files: Mapping[str, bytes],
              notes: list[str], constitution: str, constitution_commit: str,
              task: str = "",
              escalation_lock: bool = False, offline: bool = False,
              allow_custom_endpoint: bool = False, retention: str = "sealed",
              on_event=None, usage_context: dict | None = None
              ) -> AuditOutcome:
    # A4/C.2: the opt-in source-provenance check needs the governed source-id set
    # from the evidence ledger; build it only when that check is enabled.
    ctx = None
    if "source_provenance" in cfg.checks:
        from ..dcl.framework import CheckContext
        from ..receipt.sources import governed_source_ids
        ctx = CheckContext(governed_source_ids=governed_source_ids(cfg))
    # D150: phase narration rides the same handle the recovery callback uses
    # (``on_event.narrate``); absent for the CLI verbs, present under a run.
    narrate = getattr(on_event, "narrate", None)

    def on_check(name: str, status: str, count: int) -> None:
        if narrate is None:
            return
        word = check_words(name)
        if status == "started":
            narrate("check_started", f"Running the {word} check")
        elif count == 0:
            narrate("check_finished", f"{word} check passed")
        else:
            narrate("check_finished", f"{word} check found {count} issue"
                    + ("" if count == 1 else "s"))

    dcl = run_checks(files, cfg.checks, notes, cfg.plugins, context=ctx,
                     on_check=on_check).as_dict()
    from ..broker.routing import evidence_view
    prompt, bounded, prompt_sha = prompt_mod.build(
        constitution, constitution_commit, dcl, files, task,
        tool_evidence=evidence_view(cfg))
    reply: dict | None = None
    invalid: str | None = None
    provider_failure: str | None = None
    integrity = "OK"
    exchange: dict = {"mode": "none"}
    actual = cfg.auditor
    model_decided = False

    if not offline:
        ok, why = heterogeneity(cfg)
        if not ok and cfg.generator_vendor:
            raise ConfigDenial(why)                   # a same-vendor pair is not CrossAudit
        if narrate is not None:
            narrate("auditor_reading", f"The auditor is reading {len(files)} file"
                    + ("" if len(files) == 1 else "s"))
        try:
            started = time.monotonic()
            raw = provider_resilience.complete(
                cfg, "auditor", cfg.auditor, system=prompt_mod.SYSTEM,
                prompt=prompt, allow_custom=allow_custom_endpoint,
                on_event=on_event)
            route = provider_resilience.route_from_reply(raw, cfg.auditor)
            # The kernel passes the caller's attribution through untouched and
            # adds only what it measured itself (the turn's duration).
            usage_meta = dict(usage_context or {})
            usage_meta["duration_ms"] = int((time.monotonic() - started) * 1000)
            record_completion(root=cfg.root, state_dir=cfg.state_dir, role="auditor",
                              phase="audit", vendor=route["vendor"],
                              provider=route["provider"], model=route["model"],
                              reply=raw, system=prompt_mod.SYSTEM, prompt=prompt,
                              base_url=route.get("base_url"), context=usage_meta)
            actual = Role(provider=route["provider"], model=route["model"],
                          vendor=route["vendor"], key_env=route["key_env"],
                          base_url=route.get("base_url"),
                          reasoning_effort=route.get("reasoning_effort"))
            exchange = {"mode": retention, "provider": actual.provider,
                        "vendor": actual.vendor, "model": actual.model,
                        "base_url": actual.base_url,
                        "fallback": bool(route.get("fallback")),
                        "reasoning_effort": actual.reasoning_effort or "provider-default",
                        **raw.commitments(retention)}
            parsed, perr = parse_reply(raw.text)
            invalid = perr or validate_reply(parsed, known_rules(constitution))
            reply = parsed if invalid is None else None
        except ProviderDenial as exc:
            if (str(exc.detail.get("category", "")) in PROVIDER_WAIT_CATEGORIES
                    and not escalation_lock
                    and dcl["total_hard_failures"] == 0):
                # Every configured auditor route is exhausted or cooling
                # down (or the usage guardrail refused to place the call),
                # and the missing model reply is the only thing that could
                # decide this round: that is an infrastructure or spending
                # stop, not an audit opinion. Re-raise so the build loop's
                # park path records an explicit wait and the direct
                # `crossaudit audit` verb maps it to EXIT_PROVIDER. When
                # the deterministic tier already hard-blocked the round (or
                # an escalation lock already decided it), the verdict below
                # is code's own and the outage decides nothing, so those
                # rounds keep their deterministic result instead of
                # stalling.
                raise
            # The audit did not happen. That is never a *finding*: it must
            # not enter the Model findings section, reach the generator as
            # something to "fix", or masquerade as an invalid reply — the
            # receipt records it in its integrity field and the report
            # states it in plain prose.
            provider_failure = exc.reason
            integrity = "PROVIDER_FAILURE"
            exchange = {"mode": "none", "error": exc.reason}
        except Denial:
            raise

    if escalation_lock:
        verdict = "ESCALATE"
    elif dcl["total_hard_failures"] > 0:
        verdict = "BLOCKED"
    elif not dcl.get("scope_started", True):
        # THE WEAKENING GUARD. An unstarted scope produces no hard failures, so
        # without this it would fall through to the model tier and could reach
        # PASS — an empty directory becoming a route to a clean verdict, which
        # is the one outcome worse than the alarming message this replaces.
        # ESCALATE is honest: nothing was audited, and a person owns that.
        verdict = "ESCALATE"
        integrity = integrity if integrity != "OK" else "NOTHING_AUDITED"
    elif invalid:
        verdict = "ESCALATE"
        integrity = integrity if integrity != "OK" else "INVALID_REPLY"
    elif bounded:
        verdict = "ESCALATE"
        integrity = "BOUNDS_EXCEEDED"
    elif reply:
        verdict = reply["verdict"]
        model_decided = True
    else:
        # No model opinion exists (offline, or the provider failed with the
        # deterministic tier already decisive): a deterministic-tier result,
        # explicitly marked as such, never a synthesized model verdict.
        verdict = "DCL_ONLY"

    if actual.provider in NON_EVIDENTIAL and verdict == "PASS":
        # A fixture is not an audit; it may exercise the loop, never bless a commit.
        integrity = "NON_EVIDENTIAL_PROVIDER"

    # Evidence authority (D148): derive the route and the evidence partition
    # from the ladder's verdict. Under the default dial this returns the verdict
    # unchanged; only `authority.lone_model_blocker: escalate` can move a
    # model-only BLOCKED to ESCALATE.
    records = records_from_audit(
        dcl, reply, provider=actual.provider, model=actual.model,
        vendor=actual.vendor, dcl_digest=dcl_source_digest(),
        prompt_sha256=prompt_sha)
    decision = decide_authority(
        records, verdict=verdict, integrity=integrity,
        escalation_lock=escalation_lock,
        scope_started=bool(dcl.get("scope_started", True)),
        model_decided=model_decided,
        lone_model_blocker=cfg.authority.lone_model_blocker)
    verdict = decision.workflow_verdict
    authority = decision.as_dict()

    report = render_report(cfg=cfg, sha=sha, round_=round_, verdict=verdict, dcl=dcl,
                           reply=reply, invalid=invalid,
                           constitution_commit=constitution_commit,
                           provider=actual.provider, model=actual.model,
                           vendor=actual.vendor,
                           reasoning_effort=actual.reasoning_effort,
                           provider_failure=provider_failure,
                           authority=authority)
    return AuditOutcome(verdict=verdict, dcl=dcl, model_reply=reply,
                        invalid_reason=invalid, integrity=integrity, exchange=exchange,
                        prompt_sha256=prompt_sha, report=report, authority=authority)
