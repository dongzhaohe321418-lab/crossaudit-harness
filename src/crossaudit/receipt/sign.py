"""Sign a receipt, and verify that signature — additively, never in the receipt.

A1 attaches a detached DSSE signature as a SIDECAR file (``receipt.dsse.json``)
next to ``receipt.json``. The receipt bytes and their content address are left
completely untouched, so every previously-written, unsigned receipt still
verifies exactly as before — signing is purely additive.

Signing is fail-open: if a key cannot be created or a signing step fails, the
receipt is simply left unsigned rather than blocking the audit. Verification is
fail-closed: a receipt with a sidecar whose signature does NOT match is refused,
because a present-but-invalid signature means the receipt or its signature was
altered after the fact.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import Config
from ..crypto import dsse, keys
from .schema import digest

SIDECAR = "receipt.dsse.json"


def _predicate(receipt: dict) -> dict:
    """A small, honest provenance predicate re-projected from the receipt."""
    cycle = receipt.get("cycle", {}) if isinstance(receipt, dict) else {}
    subject = receipt.get("subject", {}) if isinstance(receipt, dict) else {}
    verifier = receipt.get("verifier", {}) if isinstance(receipt, dict) else {}
    tool_ev = receipt.get("tool_evidence", {}) if isinstance(receipt, dict) else {}
    return {
        "cycle_id": cycle.get("cycle_id", ""),
        "round": cycle.get("round"),
        "verdict": receipt.get("verdict", ""),
        "report_sha256": subject.get("report_sha256", ""),
        "evidence_root": {"ledger_head": tool_ev.get("ledger_head", ""),
                          "entries": tool_ev.get("entries")},
        "verifier_code_digest": verifier.get("code_digest_sha256", ""),
    }


def sign_receipt(cfg: Config, receipt: dict, cycle_dir: Path) -> str:
    """Write ``receipt.dsse.json`` beside the receipt; return the key id, or "".

    Fail-open: any problem leaves the receipt unsigned and returns "".
    """
    try:
        seed, pub, keyid = keys.load_or_create(cfg)
        payload = dsse.statement(receipt_digest=digest(receipt),
                                 predicate=_predicate(receipt))
        envelope = dsse.sign(payload, seed, pub)
        (cycle_dir / SIDECAR).write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
        return keyid
    except Exception:  # noqa: BLE001 -- signing must never block an audit
        return ""


def verify_receipt(receipt: dict, cycle_dir: Path, *,
                   expected_pubkey: bytes | None = None) -> dict:
    """Check the receipt's signature sidecar, if any.

    ``{"signed": bool, "verified": bool, "keyid": str, "reason": str}``. An
    absent sidecar is ``signed=False`` (a legacy or unsigned receipt — allowed).
    A present sidecar must verify AND bind this exact receipt digest, or the
    caller should refuse.
    """
    sidecar = cycle_dir / SIDECAR
    if not sidecar.is_file():
        return {"signed": False, "verified": False, "keyid": "", "reason": "unsigned"}
    try:
        envelope = json.loads(sidecar.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"signed": True, "verified": False, "keyid": "",
                "reason": "the signature sidecar is unreadable"}
    report = dsse.verify(envelope, expected_pubkey=expected_pubkey)
    if not report["ok"]:
        return {"signed": True, "verified": False, "keyid": report["keyid"],
                "reason": report["reason"]}
    # The signature is valid; confirm it binds THIS receipt, not another.
    try:
        statement = dsse.payload_json(envelope)
        bound = statement["subject"][0]["digest"]["sha256"]
    except Exception:  # noqa: BLE001
        return {"signed": True, "verified": False, "keyid": report["keyid"],
                "reason": "the signed statement is malformed"}
    if bound != digest(receipt):
        return {"signed": True, "verified": False, "keyid": report["keyid"],
                "reason": "the signature is for a different receipt"}
    return {"signed": True, "verified": True, "keyid": report["keyid"],
            "reason": "ok"}
