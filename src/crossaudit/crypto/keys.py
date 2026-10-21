"""Per-project Ed25519 signing key lifecycle (A1).

A project's evidence is signed with a keypair that belongs to that project. The
private seed lives, mode 0600, under the gitignored state dir (never committed,
never in argv or logs); the public key is published so anyone can verify the
signatures offline without CrossAudit. The key is created lazily on first use
and never rotated automatically — a stable key is what lets old receipts stay
verifiable.

This is a file-based keystore that works identically in the frozen macOS app,
the CLI, CI, and Linux. (An OS-Keychain-backed private key is a possible later
enhancement; the file under the private state dir is the portable default.)
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from ..config import Config
from . import ed25519

_DIR = "signing"
_SEED_FILE = "ed25519.seed"
_PUB_FILE = "ed25519.pub"
_ENV_OVERRIDE = "CROSSAUDIT_SIGNING_KEYFILE"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def key_id(pubkey: bytes) -> str:
    """A short, stable identifier for a public key: sha256(pubkey)[:16] hex."""
    return hashlib.sha256(pubkey).hexdigest()[:16]


def _signing_dir(cfg: Config) -> Path:
    override = os.environ.get(_ENV_OVERRIDE, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return cfg.root / cfg.state_dir / _DIR


def load_or_create(cfg: Config) -> tuple[bytes, bytes, str]:
    """Return (seed, public_key, key_id), creating the keypair on first use.

    The seed file is written with 0600 permissions inside the private state dir.
    Creation is best-effort atomic; a concurrent creator is tolerated by reading
    back whatever landed.
    """
    directory = _signing_dir(cfg)
    seed_path = directory / _SEED_FILE
    if seed_path.is_file():
        seed = _unb64(seed_path.read_text(encoding="ascii").strip())
        pub = ed25519.public_key(seed)
        return seed, pub, key_id(pub)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    seed = ed25519.generate_seed()
    pub = ed25519.public_key(seed)
    # Write the private seed 0600 via O_EXCL so we never clobber a rival writer.
    fd = os.open(seed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, _b64(seed).encode("ascii"))
    except FileExistsError:  # pragma: no cover -- lost the create race
        os.close(fd)
        seed = _unb64(seed_path.read_text(encoding="ascii").strip())
        pub = ed25519.public_key(seed)
        return seed, pub, key_id(pub)
    finally:
        os.close(fd)
    (directory / _PUB_FILE).write_text(_b64(pub) + "\n", encoding="ascii")
    return seed, pub, key_id(pub)


def public_key(cfg: Config) -> tuple[bytes, str] | None:
    """The project's public key + key id if a signing key exists, else None.

    Read-only: it never creates a key, so a snapshot/settings read cannot mint
    one as a side effect.
    """
    seed_path = _signing_dir(cfg) / _SEED_FILE
    if not seed_path.is_file():
        return None
    seed = _unb64(seed_path.read_text(encoding="ascii").strip())
    pub = ed25519.public_key(seed)
    return pub, key_id(pub)


_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")
_PEM_BEGIN = "-----BEGIN PUBLIC KEY-----"
_PEM_END = "-----END PUBLIC KEY-----"


def public_key_pem(pubkey: bytes) -> str:
    """The public key as PEM SubjectPublicKeyInfo, so openssl / ssh-keygen -Y /
    cryptography can all verify offline without any CrossAudit code."""
    spki = _SPKI_PREFIX + pubkey   # Ed25519 SPKI prefix
    body = base64.encodebytes(spki).decode("ascii").strip()
    return _PEM_BEGIN + "\n" + body + "\n" + _PEM_END + "\n"


def parse_public_key_pem(text: str) -> bytes:
    """The raw 32-byte Ed25519 key from a PEM SubjectPublicKeyInfo block.

    The inverse of :func:`public_key_pem`. Text outside the one ``BEGIN/END
    PUBLIC KEY`` block is ignored, as OpenSSL ignores it, so a file that an
    older ``export-pubkey`` wrote with a ``KEY <id>`` line above the block still
    parses. Everything inside the block is held to the exact form: strict
    base64, exactly the Ed25519 SPKI prefix and 32 key bytes. Raises
    ``ValueError`` with a short reason otherwise — never a ``binascii.Error``
    reaching a person as a traceback.
    """
    lines = [line.strip() for line in str(text).splitlines()]
    try:
        start = lines.index(_PEM_BEGIN)
        end = lines.index(_PEM_END, start + 1)
    except ValueError:
        raise ValueError("it holds no BEGIN/END PUBLIC KEY block") from None
    if _PEM_BEGIN in lines[end + 1:]:
        raise ValueError("it holds more than one PUBLIC KEY block")
    body = "".join(lines[start + 1:end])
    try:
        der = base64.b64decode(body.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise ValueError("the PUBLIC KEY block is not valid base64") from None
    if len(der) != len(_SPKI_PREFIX) + 32 or not der.startswith(_SPKI_PREFIX):
        raise ValueError("the PUBLIC KEY block is not an Ed25519 key")
    return der[len(_SPKI_PREFIX):]
