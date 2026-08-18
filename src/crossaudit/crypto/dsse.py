"""DSSE (Dead-Simple Signing Envelope) over Ed25519 — the signed evidence format.

A CrossAudit signature is a standard DSSE envelope (the same format Sigstore and
in-toto use) wrapping an in-toto Statement whose subject is the receipt digest.
Because it is a standard envelope over a standard statement, a third party can
verify it with off-the-shelf tooling and the project's public key — no bespoke
verifier, no CrossAudit install, no network. Verification is: recompute the DSSE
PAE over the payload and check the Ed25519 signature against the PEM public key
with any conforming library (e.g. ``cryptography`` or a modern OpenSSL 3.x;
Apple's bundled LibreSSL ``openssl`` is too old for Ed25519).

Honest scope: on one local machine the operator holds the signing key, so a
valid signature proves the evidence was produced by this project's key and has
not been altered since (tamper-evidence + offline external verifiability +
provenance binding). It is NOT a defence against the key holder, and it does not
replace the independent cross-vendor audit — it makes the audit's record
verifiable by outsiders.
"""
from __future__ import annotations

import base64
import json

from . import ed25519, keys

PAYLOAD_TYPE = "application/vnd.in-toto+json"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://crossaudit.io/attestation/audit-receipt/v1"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(str(text).encode("ascii"))


def _pae(payload_type: str, payload: bytes) -> bytes:
    """The DSSE Pre-Authentication Encoding — what is actually signed."""
    pt = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(pt), pt, len(payload), payload)


def statement(*, receipt_digest: str, predicate: dict) -> bytes:
    """The canonical in-toto Statement bytes bound to a receipt digest."""
    doc = {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "receipt.json",
                     "digest": {"sha256": str(receipt_digest)}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sign(payload: bytes, seed: bytes, pubkey: bytes) -> dict:
    """A DSSE envelope over ``payload`` signed with ``seed``."""
    sig = ed25519.sign(seed, _pae(PAYLOAD_TYPE, payload))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": _b64(payload),
        "signatures": [{"keyid": keys.key_id(pubkey), "sig": _b64(sig)}],
        "public_key": _b64(pubkey),
    }


def verify(envelope: dict, *, expected_pubkey: bytes | None = None) -> dict:
    """Verify a DSSE envelope. Returns a report; never raises on bad input.

    ``{"ok": bool, "keyid": str, "reason": str}``. When ``expected_pubkey`` is
    given (a third party pinning a key out of band), the envelope's embedded key
    must match it — otherwise the embedded key is trusted-on-first-use and only
    proves internal consistency (the key id equals the hash of the key that
    signed).
    """
    try:
        payload_type = str(envelope.get("payloadType", ""))
        payload = _unb64(envelope["payload"])
        embedded = _unb64(envelope["public_key"])
        sigs = envelope.get("signatures") or []
    except Exception:  # noqa: BLE001 -- a malformed envelope is simply invalid
        return {"ok": False, "keyid": "", "reason": "malformed DSSE envelope"}
    if expected_pubkey is not None and embedded != expected_pubkey:
        return {"ok": False, "keyid": keys.key_id(embedded),
                "reason": "the envelope was signed by a different key than pinned"}
    pae = _pae(payload_type, payload)
    for entry in sigs:
        try:
            sig = _unb64(entry["sig"])
            keyid = str(entry.get("keyid", ""))
        except Exception:  # noqa: BLE001
            continue
        if keyid and keyid != keys.key_id(embedded):
            return {"ok": False, "keyid": keyid,
                    "reason": "key id does not match the embedded public key"}
        if ed25519.verify(embedded, sig, pae):
            return {"ok": True, "keyid": keys.key_id(embedded), "reason": "ok"}
    return {"ok": False, "keyid": keys.key_id(embedded),
            "reason": "no valid signature"}


def payload_json(envelope: dict) -> dict:
    """The decoded in-toto Statement from a (already-verified) envelope."""
    return json.loads(_unb64(envelope["payload"]).decode("utf-8"))
