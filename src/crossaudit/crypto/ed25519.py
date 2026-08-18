"""Ed25519 signatures with no native dependency (A1).

A faithful, self-contained implementation of the Ed25519 signature scheme
(RFC 8032), depending only on the Python standard library (``hashlib`` for
SHA-512). It exists so CrossAudit's evidence can carry real, externally
verifiable, asymmetric signatures while the application stays a single frozen,
offline macOS app with no compiled crypto dependency to bundle, sign, or
notarize.

Provenance & correctness: this is the well-known public-domain reference
construction described in RFC 8032. It is intentionally the plain, slow
reference — signatures and public keys are byte-for-byte identical to any
conforming Ed25519 implementation (verified in tests against ``cryptography``
when it is installed), so a third party may verify a CrossAudit signature with
the public key using any conforming Ed25519 verifier — the ``cryptography``
library or a modern OpenSSL 3.x. (Apple's bundled ``openssl`` is LibreSSL and
too old for Ed25519; use the ``cryptography`` path there.) The
reference is not constant-time; that is acceptable here because it signs public
audit evidence with a key the operator already holds — it is a provenance and
tamper-evidence tool, not a defence against the key holder.

Public API: ``generate_seed()``, ``public_key(seed)``, ``sign(seed, message)``,
``verify(public_key, signature, message)``. Seeds and public keys are 32 bytes;
signatures are 64 bytes.
"""
from __future__ import annotations

import hashlib
import os

__all__ = ["generate_seed", "public_key", "sign", "verify",
           "SEED_BYTES", "PUBLIC_KEY_BYTES", "SIGNATURE_BYTES"]

SEED_BYTES = 32
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _sha512_int(data: bytes) -> int:
    return int.from_bytes(hashlib.sha512(data).digest(), "little")


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    x = pow(xx % _P, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if (x * x - xx) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


# The base point B, in extended homogeneous coordinates (X, Y, Z, T).
_By = 4 * pow(5, _P - 2, _P) % _P
_Bx = _recover_x(_By, 0)
_B = (_Bx % _P, _By % _P, 1, (_Bx * _By) % _P)


def _point_add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    dd = 2 * z1 * z2 % _P
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _scalar_mult(p, e: int):
    q = (0, 1, 1, 0)                      # the neutral element
    while e > 0:
        if e & 1:
            q = _point_add(q, p)
        p = _point_add(p, p)
        e >>= 1
    return q


def _point_equal(p, q) -> bool:
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _point_compress(p) -> bytes:
    x, y, z, _ = p
    zinv = pow(z, _P - 2, _P)
    x = x * zinv % _P
    y = y * zinv % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _point_decompress(data: bytes):
    if len(data) != 32:
        raise ValueError("invalid point length")
    n = int.from_bytes(data, "little")
    sign = (n >> 255) & 1
    y = n & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _secret_expand(seed: bytes):
    if len(seed) != SEED_BYTES:
        raise ValueError("seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return a, h[32:]


def generate_seed() -> bytes:
    """A fresh 32-byte Ed25519 seed (private key) from the OS CSPRNG."""
    return os.urandom(SEED_BYTES)


def public_key(seed: bytes) -> bytes:
    a, _ = _secret_expand(seed)
    return _point_compress(_scalar_mult(_B, a))


def sign(seed: bytes, message: bytes) -> bytes:
    a, prefix = _secret_expand(seed)
    pk = _point_compress(_scalar_mult(_B, a))
    r = _sha512_int(prefix + message) % _L
    big_r = _point_compress(_scalar_mult(_B, r))
    k = _sha512_int(big_r + pk + message) % _L
    s = (r + k * a) % _L
    return big_r + s.to_bytes(32, "little")


def verify(pubkey: bytes, signature: bytes, message: bytes) -> bool:
    """True iff ``signature`` is a valid Ed25519 signature of ``message``.

    Never raises on malformed input — a bad signature or key is simply invalid.
    """
    try:
        if len(pubkey) != PUBLIC_KEY_BYTES or len(signature) != SIGNATURE_BYTES:
            return False
        big_a = _point_decompress(pubkey)
        if big_a is None:
            return False
        big_r = _point_decompress(signature[:32])
        if big_r is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _L:
            return False
        k = _sha512_int(signature[:32] + pubkey + message) % _L
        return _point_equal(_scalar_mult(_B, s),
                            _point_add(big_r, _scalar_mult(big_a, k)))
    except Exception:  # noqa: BLE001 -- verification never raises; it returns False
        return False
