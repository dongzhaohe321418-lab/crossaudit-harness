"""A1: DSSE-signed, externally-verifiable receipts.

These tests hold the A1 invariants: signatures are real Ed25519 (byte-identical
to a conforming library), a signed receipt verifies offline with only the public
key, tampering is caught, and — crucially — signing is purely additive so every
older unsigned receipt keeps working exactly as before.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit.crypto import dsse, ed25519, keys
from crossaudit.receipt.schema import digest
from crossaudit.receipt.sign import SIDECAR, sign_receipt, verify_receipt

try:  # the reference impl is proven against a real library WHEN one is present,
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E501
        Ed25519PrivateKey, Ed25519PublicKey)
    from cryptography.hazmat.primitives import serialization
    _HAVE_CRYPTOGRAPHY = True
except Exception:  # noqa: BLE001 -- but it is never an app dependency, so absence is fine
    _HAVE_CRYPTOGRAPHY = False


def _cfg(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(root=tmp_path, state_dir=".crossaudit")


def _receipt() -> dict:
    return {
        "version": 2,
        "cycle": {"cycle_id": "cyc-1", "round": 3},
        "verdict": "PASS",
        "subject": {"report_sha256": "a" * 64},
        "verifier": {"project": "crossaudit", "version": "5",
                     "code_digest_sha256": "b" * 64, "install_mode": "frozen"},
    }


# ---------------------------------------------------------------- ed25519 core

def test_ed25519_sign_verify_roundtrip():
    seed = ed25519.generate_seed()
    pub = ed25519.public_key(seed)
    assert len(seed) == 32 and len(pub) == 32
    sig = ed25519.sign(seed, b"hello evidence")
    assert len(sig) == 64
    assert ed25519.verify(pub, sig, b"hello evidence")
    assert not ed25519.verify(pub, sig, b"hello evidenc3")


def test_ed25519_rejects_malformed_without_raising():
    assert ed25519.verify(b"short", b"\x00" * 64, b"m") is False
    assert ed25519.verify(b"\x00" * 32, b"short", b"m") is False


@pytest.mark.skipif(not _HAVE_CRYPTOGRAPHY, reason="cryptography not installed")
def test_ed25519_is_byte_identical_to_cryptography():
    """The vendored reference must be indistinguishable from a conforming lib:
    same public key, same signature bytes, mutually verifiable."""
    for i in range(25):
        seed = bytes((i * 7 + j) % 256 for j in range(32))
        msg = b"receipt-" + bytes([i])
        ours_pub = ed25519.public_key(seed)
        ours_sig = ed25519.sign(seed, msg)

        sk = Ed25519PrivateKey.from_private_bytes(seed)
        lib_pub = sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        lib_sig = sk.sign(msg)

        assert ours_pub == lib_pub, f"pubkey mismatch at {i}"
        assert ours_sig == lib_sig, f"signature mismatch at {i}"
        # cross-verify both directions
        Ed25519PublicKey.from_public_bytes(ours_pub).verify(ours_sig, msg)
        assert ed25519.verify(lib_pub, lib_sig, msg)


# ---------------------------------------------------------------------- keys

def test_key_is_created_once_and_is_stable(tmp_path):
    cfg = _cfg(tmp_path)
    seed1, pub1, kid1 = keys.load_or_create(cfg)
    seed2, pub2, kid2 = keys.load_or_create(cfg)
    assert (seed1, pub1, kid1) == (seed2, pub2, kid2)
    assert len(kid1) == 16


def test_seed_file_is_private(tmp_path):
    cfg = _cfg(tmp_path)
    keys.load_or_create(cfg)
    seed_path = tmp_path / ".crossaudit" / "signing" / "ed25519.seed"
    assert seed_path.is_file()
    assert (seed_path.stat().st_mode & 0o777) == 0o600


def test_public_key_read_only_never_creates(tmp_path):
    cfg = _cfg(tmp_path)
    assert keys.public_key(cfg) is None            # nothing minted by a read
    assert not (tmp_path / ".crossaudit" / "signing").exists()
    keys.load_or_create(cfg)
    got = keys.public_key(cfg)
    assert got is not None and len(got[1]) == 16


def test_public_key_pem_is_loadable_spki(tmp_path):
    _, pub, _ = keys.load_or_create(_cfg(tmp_path))
    pem = keys.public_key_pem(pub)
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
    if _HAVE_CRYPTOGRAPHY:
        loaded = serialization.load_pem_public_key(pem.encode())
        raw = loaded.public_bytes(serialization.Encoding.Raw,
                                  serialization.PublicFormat.Raw)
        assert raw == pub


# ------------------------------------------------------------- sign / verify

def test_sign_then_verify_receipt(tmp_path):
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    kid = sign_receipt(cfg, receipt, cyc)
    assert kid and (cyc / SIDECAR).is_file()
    v = verify_receipt(receipt, cyc)
    assert v == {"signed": True, "verified": True, "keyid": kid, "reason": "ok"}


def test_unsigned_receipt_is_signed_false_not_an_error(tmp_path):
    """Back-compat: a receipt with no sidecar (every receipt minted before A1)
    is reported unsigned — never as a verification failure."""
    cyc = tmp_path / "cycles" / "old-r1"
    cyc.mkdir(parents=True)
    v = verify_receipt(_receipt(), cyc)
    assert v["signed"] is False and v["verified"] is False


def test_tampering_the_receipt_breaks_verification(tmp_path):
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    sign_receipt(cfg, receipt, cyc)
    tampered = json.loads(json.dumps(receipt))
    tampered["verdict"] = "BLOCKED"
    v = verify_receipt(tampered, cyc)
    assert v["signed"] is True and v["verified"] is False
    assert "different receipt" in v["reason"]


def test_tampering_the_signature_breaks_verification(tmp_path):
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    sign_receipt(cfg, receipt, cyc)
    env = json.loads((cyc / SIDECAR).read_text())
    raw = bytearray(base64.b64decode(env["signatures"][0]["sig"]))
    raw[0] ^= 0x01
    env["signatures"][0]["sig"] = base64.b64encode(bytes(raw)).decode()
    (cyc / SIDECAR).write_text(json.dumps(env))
    v = verify_receipt(receipt, cyc)
    assert v["signed"] is True and v["verified"] is False


def test_pinning_a_wrong_public_key_is_refused(tmp_path):
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    sign_receipt(cfg, receipt, cyc)
    other = ed25519.public_key(ed25519.generate_seed())
    v = verify_receipt(receipt, cyc, expected_pubkey=other)
    assert v["verified"] is False


# --------------------------------------------------- third-party offline verify

@pytest.mark.skipif(not _HAVE_CRYPTOGRAPHY, reason="cryptography not installed")
def test_third_party_can_verify_with_only_the_public_key(tmp_path):
    """The whole point of A1: someone with just the public key and off-the-shelf
    tooling — no CrossAudit code — can confirm the signature over the DSSE PAE."""
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    sign_receipt(cfg, receipt, cyc)
    pub, _ = keys.public_key(cfg)
    pem = keys.public_key_pem(pub)

    env = json.loads((cyc / SIDECAR).read_text())
    payload = base64.b64decode(env["payload"])
    sig = base64.b64decode(env["signatures"][0]["sig"])
    pae = b"DSSEv1 %d %s %d %s" % (
        len(env["payloadType"].encode()), env["payloadType"].encode(),
        len(payload), payload)

    loaded = serialization.load_pem_public_key(pem.encode())
    loaded.verify(sig, pae)   # raises if invalid — external verification passes


def test_signed_statement_binds_this_exact_receipt(tmp_path):
    cfg = _cfg(tmp_path)
    cyc = tmp_path / "cycles" / "cyc-1-r3"
    cyc.mkdir(parents=True)
    receipt = _receipt()
    sign_receipt(cfg, receipt, cyc)
    env = json.loads((cyc / SIDECAR).read_text())
    statement = dsse.payload_json(env)
    assert statement["subject"][0]["digest"]["sha256"] == digest(receipt)


def test_env_override_keyfile_location(tmp_path, monkeypatch):
    alt = tmp_path / "alt-keys"
    monkeypatch.setenv("CROSSAUDIT_SIGNING_KEYFILE", str(alt))
    cfg = _cfg(tmp_path)
    keys.load_or_create(cfg)
    assert (alt / "ed25519.seed").is_file()
    assert not (tmp_path / ".crossaudit" / "signing").exists()


def test_signing_is_fail_open_on_bad_cycle_dir(tmp_path):
    """If the sidecar cannot be written, the audit is not blocked: sign_receipt
    returns "" and the receipt is simply left unsigned."""
    cfg = _cfg(tmp_path)
    missing = tmp_path / "does" / "not" / "exist"
    assert sign_receipt(cfg, _receipt(), missing) == ""
