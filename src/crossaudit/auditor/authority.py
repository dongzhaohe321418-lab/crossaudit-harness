"""Evidence authority: what each finding is, who produced it, and what it may do.

The audit has two producers with different standing. A deterministic check runs
over committed bytes and its finding is CONFIRMED the moment it is raised; the
model auditor reads the same bytes and its finding is ALLEGED — useful, and
not yet established. This module writes that distinction down as evidence
records, binds them into one digest, and derives the route a round takes.

v1 DERIVES; IT DOES NOT RE-DECIDE. The verdict ladder in `run.py` stays the
authority on the workflow verdict. `decide_authority` takes that verdict as
input and returns it unchanged, with exactly one opt-in exception: under
`authority.lone_model_blocker: escalate`, a BLOCKED that rests on nothing but
the model's own reading becomes ESCALATE (a person, not a patch). The default
dial keeps today's bounded revision and records the block as unverified.

The record is additive. Older receipts carry no `authority` block and verify
byte-for-byte as before; a receipt that carries one binds its evidence by
digest so no record can be edited after the decision.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass

from ..dcl.framework import CONFIRMED

POLICY_VERSION = "crossaudit-evidence-authority-v1"
#: Every policy version a verifier accepts. A receipt written under an older
#: known policy keeps verifying; an unknown one is refused by name.
KNOWN_POLICY_VERSIONS = frozenset({POLICY_VERSION})

#: The route is the verdict, read as "what consumes this round next". There is
#: deliberately no fourth status vocabulary beside the workflow verdict.
ROUTE_FOR_VERDICT = {
    "PASS": "receipt",
    "BLOCKED": "bounded-revision",
    "ESCALATE": "human-decision",
    "DCL_ONLY": "obtain-audit",
}
ROUTES = frozenset(ROUTE_FOR_VERDICT.values())
WORKFLOW_VERDICTS = frozenset(ROUTE_FOR_VERDICT)
TIERS = ("deterministic", "model")
LONE_MODEL_BLOCKER_DIALS = ("block", "escalate")

# v2 reserves a slot for a second producer (broker tool evidence, already
# digest-bound in the ledger); until it exists no consensus rule is claimed.


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _identifier(prefix: str, value: object) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(value)).hexdigest()[:16]}"


@dataclass(frozen=True)
class EvidenceRecord:
    """One finding plus the provenance needed to say what it may do."""

    evidence_id: str
    finding_key: str
    severity: str
    tier: str
    state: str
    claim: str
    artifact: str
    producer: str
    producer_digest: str

    @property
    def verified(self) -> bool:
        return self.state == CONFIRMED

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AuthorityDecision:
    """The derived route for one round and the evidence it rests on."""

    policy_version: str
    decision_id: str
    workflow_verdict: str
    route: str
    requires_human: bool
    lone_model_blocker: str
    blocking_evidence_ids: tuple[str, ...]
    contested_evidence_ids: tuple[str, ...]
    advisory_evidence_ids: tuple[str, ...]
    rationale: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidence_digest: str

    def as_dict(self) -> dict:
        return {
            **asdict(self),
            "evidence": [item.as_dict() for item in self.evidence],
        }


def _record(**payload: str) -> EvidenceRecord:
    return EvidenceRecord(evidence_id=_identifier("ev", payload), **payload)


def records_from_audit(dcl: Mapping, model_reply: Mapping | None, *,
                       provider: str, model: str, vendor: str | None,
                       dcl_digest: str, prompt_sha256: str
                       ) -> tuple[EvidenceRecord, ...]:
    """Both tiers' findings as evidence records, in the order they were raised.

    Built on `finding_states()` so tier and state can never disagree with the
    sidecar; only the claim, producer and producer digest are added here.
    """
    from .run import finding_states  # lazy: run.py imports this module

    rows = finding_states(dict(dcl), dict(model_reply) if model_reply else None)
    sources = [*dcl.get("findings", []),
               *((model_reply or {}).get("findings", []) or [])]
    if len(rows) != len(sources):
        raise ValueError("finding_states and the raw findings disagree in length")
    model_producer = f"auditor:{vendor or 'unknown'}/{provider}:{model}"
    records = []
    for row, finding in zip(rows, sources):
        rule = str(row["rule"] or "unknown")
        artifact = str(row["artifact"] or "increment")
        if row["tier"] == "deterministic":
            producer = f"check:{finding.get('check') or rule}"
            producer_digest = dcl_digest
        else:
            producer = model_producer
            producer_digest = prompt_sha256
        records.append(_record(
            finding_key=f"{rule}@{artifact}",
            severity=str(row["severity"]).upper(),
            tier=str(row["tier"]), state=str(row["state"]),
            claim=str(finding.get("observation", "")), artifact=artifact,
            producer=producer, producer_digest=producer_digest))
    return tuple(records)


def decide_authority(records: Iterable[EvidenceRecord], *, verdict: str,
                     integrity: str, escalation_lock: bool, scope_started: bool,
                     model_decided: bool, lone_model_blocker: str = "block"
                     ) -> AuthorityDecision:
    """Derive the route and the evidence partition for a ladder verdict.

    `verdict` is the ladder's result and is returned as `workflow_verdict`
    except in one opt-in case: `lone_model_blocker == "escalate"`, the ladder
    took the model's own verdict, that verdict is BLOCKED, and no CONFIRMED
    BLOCKER exists. Every other input passes through untouched.
    """
    if lone_model_blocker not in LONE_MODEL_BLOCKER_DIALS:
        raise ValueError(f"lone_model_blocker must be one of {LONE_MODEL_BLOCKER_DIALS}")
    if verdict not in WORKFLOW_VERDICTS:
        raise ValueError(f"verdict {verdict!r} is not one of {sorted(WORKFLOW_VERDICTS)}")
    evidence = tuple(records)
    confirmed_blockers = [r for r in evidence if r.verified and r.severity == "BLOCKER"]
    model_blockers = [r for r in evidence if not r.verified and r.severity == "BLOCKER"]

    workflow_verdict = verdict
    contested: tuple[str, ...] = ()
    lone_model_escalation = (lone_model_blocker == "escalate" and model_decided
                             and verdict == "BLOCKED" and not confirmed_blockers)
    if lone_model_escalation:
        workflow_verdict = "ESCALATE"
        contested = tuple(sorted(r.evidence_id for r in model_blockers))

    route = ROUTE_FOR_VERDICT[workflow_verdict]
    requires_human = route == "human-decision"
    blocking: tuple[str, ...] = ()
    if workflow_verdict == "BLOCKED":
        blocking = tuple(sorted(r.evidence_id for r in confirmed_blockers))
    taken = set(blocking) | set(contested)
    advisory = tuple(sorted(r.evidence_id for r in evidence
                            if r.evidence_id not in taken))

    rationale = _rationale(
        workflow_verdict=workflow_verdict, integrity=integrity,
        escalation_lock=escalation_lock, scope_started=scope_started,
        lone_model_escalation=lone_model_escalation,
        confirmed_blockers=len(confirmed_blockers),
        model_blockers=len(model_blockers), model_decided=model_decided)

    evidence_payload = [item.as_dict() for item in evidence]
    evidence_digest = hashlib.sha256(_canonical(evidence_payload)).hexdigest()
    decision_payload = {
        "policy_version": POLICY_VERSION,
        "workflow_verdict": workflow_verdict,
        "route": route,
        "lone_model_blocker": lone_model_blocker,
        "blocking_evidence_ids": blocking,
        "contested_evidence_ids": contested,
        "advisory_evidence_ids": advisory,
        "rationale": rationale,
        "evidence_digest": evidence_digest,
    }
    return AuthorityDecision(
        policy_version=POLICY_VERSION,
        decision_id=_identifier("authority", decision_payload),
        workflow_verdict=workflow_verdict, route=route,
        requires_human=requires_human, lone_model_blocker=lone_model_blocker,
        blocking_evidence_ids=blocking, contested_evidence_ids=contested,
        advisory_evidence_ids=advisory, rationale=rationale,
        evidence=evidence, evidence_digest=evidence_digest)


def _rationale(*, workflow_verdict: str, integrity: str, escalation_lock: bool,
               scope_started: bool, lone_model_escalation: bool,
               confirmed_blockers: int, model_blockers: int,
               model_decided: bool) -> tuple[str, ...]:
    """One or two plain sentences a person can read; never an internal word."""
    if escalation_lock:
        first = ("An earlier escalation holds this cycle under human jurisdiction "
                 "(the escalation lock), so nothing here routes around it.")
    elif not scope_started:
        first = ("Nothing was audited: the scope has not started, so the round is "
                 "recorded as NOTHING_AUDITED and a person owns it.")
    elif lone_model_escalation:
        first = ("The only block rests on a model reading without reproduced "
                 "evidence, so it goes to a person rather than to automatic revision.")
    elif workflow_verdict == "BLOCKED" and confirmed_blockers:
        first = (f"{confirmed_blockers} deterministic check failure(s) on committed "
                 f"bytes block this round; the block rests on reproduced evidence.")
    elif workflow_verdict == "BLOCKED":
        first = ("The block rests on the auditor's reading, which no deterministic "
                 "check reproduced; it enters bounded revision by policy and is "
                 "recorded as unverified.")
    elif workflow_verdict == "DCL_ONLY":
        first = ("No model audit ran, so this is a deterministic-tier result and "
                 "cannot pass on its own.")
    elif workflow_verdict == "PASS":
        first = ("No finding blocks this round; the deterministic checks and the "
                 "model audit both completed.")
    elif integrity != "OK":
        first = f"The round is escalated because audit integrity is {integrity}."
    else:
        first = "The auditor asked for human judgment on this round."
    sentences = [first]
    if integrity != "OK" and integrity not in first:
        sentences.append(f"Audit integrity is {integrity}, so the receipt is not "
                         f"admissible.")
    elif model_blockers and model_decided and workflow_verdict == "BLOCKED" \
            and confirmed_blockers:
        sentences.append(f"{model_blockers} further blocking concern(s) from the "
                         f"auditor remain unverified.")
    return tuple(sentences)


def validate_block(raw: Mapping) -> list[str]:
    """Structural and binding errors for a receipt's `authority` block."""
    errors: list[str] = []
    required = {"policy_version", "decision_id", "workflow_verdict", "route",
                "requires_human", "lone_model_blocker", "blocking_evidence_ids",
                "contested_evidence_ids", "advisory_evidence_ids", "rationale",
                "evidence", "evidence_digest"}
    missing = sorted(required - set(raw))
    if missing:
        return [f"authority block is missing {missing}"]
    version = raw.get("policy_version")
    if version not in KNOWN_POLICY_VERSIONS:
        errors.append(f"authority policy version {version!r} is not one this "
                      f"verifier knows ({sorted(KNOWN_POLICY_VERSIONS)})")
    verdict = raw.get("workflow_verdict")
    if verdict not in WORKFLOW_VERDICTS:
        errors.append(f"authority workflow verdict {verdict!r} is unknown")
    route = raw.get("route")
    if route not in ROUTES:
        errors.append(f"authority route {route!r} is unknown")
    elif verdict in WORKFLOW_VERDICTS and ROUTE_FOR_VERDICT[verdict] != route:
        errors.append(f"authority route {route!r} does not follow from verdict "
                      f"{verdict!r}")
    if raw.get("requires_human") != (route == "human-decision"):
        errors.append("authority requires_human disagrees with its route")
    if raw.get("lone_model_blocker") not in LONE_MODEL_BLOCKER_DIALS:
        errors.append("authority lone_model_blocker names an unknown policy dial")
    evidence = raw.get("evidence")
    if not isinstance(evidence, list):
        errors.append("authority evidence is not a list")
        return errors
    digest = hashlib.sha256(_canonical(evidence)).hexdigest()
    if digest != raw.get("evidence_digest"):
        errors.append("authority evidence digest does not match its records")
    known_ids = {item.get("evidence_id") for item in evidence if isinstance(item, Mapping)}
    for key in ("blocking_evidence_ids", "contested_evidence_ids",
                "advisory_evidence_ids"):
        ids = raw.get(key)
        if not isinstance(ids, (list, tuple)):
            errors.append(f"authority {key} is not a list")
            continue
        unknown = sorted(set(ids) - known_ids)
        if unknown:
            errors.append(f"authority {key} names evidence not in the block: {unknown}")
    if not isinstance(raw.get("rationale"), (list, tuple)) or not raw.get("rationale"):
        errors.append("authority rationale is empty")
    return errors
