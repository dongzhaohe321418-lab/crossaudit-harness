"""Reproducibility bundle (A2): name the pinned dependency environment, and how
to re-run — additively, and honestly.

An audit already binds the exact commit, the git tree, and a content-addressed
manifest of every audited input (schema.py). What it does not do is *say which
of those inputs are the dependency environment* or *how to reproduce the result*.
A2 adds both, as a small derived view:

  * ``detect_locks`` picks the dependency-lock files out of the already-verified
    manifest (so their hashes are the same ones the receipt digest — and, under
    A1, the signature — already cover; nothing new is trusted);
  * ``build_bundle`` assembles a self-contained ``reproduction.json`` sidecar
    (the pinned locks, the audit identity, and a concrete re-run recipe);
  * ``build.py`` binds only the bundle's digest into the receipt, in an optional
    block that appears **only when the tree actually carries a lock file** — so a
    lock-free project's receipt stays byte-identical to a pre-A2 receipt, and
    ``verify`` re-derives the bundle from the tree and refuses a mismatch.

Honest scope (never overclaim, §3.3): the bundle re-derives the audited bindings
and pins the dependency environment that produced the result. Bit-for-bit
reproducibility of the *research result itself* depends on the audited project's
own determinism, which CrossAudit does not control and does not claim.
"""
from __future__ import annotations

import hashlib
import json

BUNDLE_SCHEMA = "crossaudit/reproduction/v1"

#: Dependency-lock file basenames CrossAudit recognises, mapped to the ecosystem
#: they pin. Matched by exact basename — a lock is only ever the whole, resolved
#: manifest, never a loose requirement spec whose versions float.
LOCK_KINDS: dict[str, str] = {
    "requirements.txt": "python",
    "requirements.lock": "python",
    "poetry.lock": "python",
    "Pipfile.lock": "python",
    "uv.lock": "python",
    "pdm.lock": "python",
    "conda-lock.yml": "conda",
    "environment.yml": "conda",
    "environment.yaml": "conda",
    "package-lock.json": "node",
    "npm-shrinkwrap.json": "node",
    "yarn.lock": "node",
    "pnpm-lock.yaml": "node",
    "bun.lockb": "node",
    "Cargo.lock": "rust",
    "go.sum": "go",
    "go.mod": "go",
    "Gemfile.lock": "ruby",
    "composer.lock": "php",
    "Package.resolved": "swift",
    "gradle.lockfile": "jvm",
    "mix.lock": "elixir",
    "flake.lock": "nix",
    "renv.lock": "r",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _basename(path: str) -> str:
    return str(path).rsplit("/", 1)[-1]


def detect_locks(manifest: dict) -> dict[str, str]:
    """The subset of the (already git-verified) manifest that is a dependency
    lock: ``{path: sha256}``, sorted by path. ``ABSENT`` sentinels are ignored —
    a manifest can assert a path is absent, which pins nothing."""
    out: dict[str, str] = {}
    for path, digest in sorted((manifest or {}).items()):
        if digest == "ABSENT":
            continue
        if _basename(path) in LOCK_KINDS:
            out[path] = digest
    return out


def lock_kinds(locks: dict) -> list[str]:
    """The sorted, de-duplicated ecosystems named by a set of lock paths."""
    return sorted({LOCK_KINDS[_basename(p)] for p in locks})


def build_bundle(receipt: dict) -> dict:
    """A deterministic reproduction bundle derived purely from the receipt.

    Purely a function of the receipt (whose manifest ``verify`` re-derives from
    the git tree), so a verifier can recompute this byte-for-byte and confirm the
    bound digest. It deliberately does not invent an audit-host runtime CrossAudit
    cannot attest — the lock files are the environment pin.
    """
    subject = receipt.get("subject", {})
    audit = receipt.get("audit", {})
    verifier = receipt.get("verifier", {})
    ledger = receipt.get("ledger", {})
    locks = detect_locks(receipt.get("inputs", {}).get("manifest", {}))
    cycle_path = ledger.get("cycle_path", "")
    return {
        "schema": BUNDLE_SCHEMA,
        "subject": {
            "science_repo": subject.get("science_repo", ""),
            "commit": subject.get("sha", ""),
            "tree": subject.get("tree", ""),
            "scope": subject.get("scope", ""),
        },
        "environment": {
            "locks": locks,
            "kinds": lock_kinds(locks),
        },
        "audit": {
            "verdict": audit.get("verdict", ""),
            "provider": audit.get("provider", ""),
            "model": audit.get("model", ""),
        },
        "produced_by": {
            "project": verifier.get("project", ""),
            "version": verifier.get("version", ""),
            "code_digest_sha256": verifier.get("code_digest_sha256", ""),
        },
        "rerun": {
            "checkout": f"git checkout {subject.get('sha', '')}",
            "restore": ("reinstall from the pinned lock files listed under "
                        "environment.locks"),
            "verify": f"crossaudit verify {cycle_path}/receipt.json"
                      if cycle_path else "crossaudit verify <cycle>/receipt.json",
            "note": ("Re-derives the audited bindings and pins the dependency "
                     "environment. Bit-for-bit reproducibility of the research "
                     "result depends on the audited project's own determinism."),
        },
    }


def canonical(bundle: dict) -> bytes:
    """The byte form a bundle digest is taken over (matches receipt canonical)."""
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def bundle_digest(bundle: dict) -> str:
    return _sha256(canonical(bundle))


def receipt_block(receipt: dict) -> dict | None:
    """The optional ``reproduction`` block for a receipt, or ``None`` when the
    audited tree carries no dependency lock (so the receipt stays byte-identical
    to a pre-A2 receipt — additive, exactly like ``tool_evidence``)."""
    locks = detect_locks(receipt.get("inputs", {}).get("manifest", {}))
    if not locks:
        return None
    bundle = build_bundle(receipt)
    return {
        "bundle_sha256": bundle_digest(bundle),
        "locks": len(locks),
        "lock_kinds": lock_kinds(locks),
    }
