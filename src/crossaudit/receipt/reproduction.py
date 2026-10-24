"""Reproducibility bundle (A2): name the pinned dependency environment, and how
to re-run — additively, and honestly.

An audit already binds the exact commit, the git tree, and a content-addressed
manifest of every audited input (schema.py). What it does not do is *say which
of those inputs are the dependency environment* or *how to reproduce the result*.
A2 adds both, as a small derived view:

  * ``detect_locks`` picks the dependency-lock files out of the already-verified
    manifest (so their hashes are the same ones the receipt digest — and, under
    A1, the signature — already cover; nothing new is trusted);
  * ``detect_tree_locks`` (D171) finds the locks the manifest does NOT carry:
    a manifest can be only the increment's changed paths (``crossaudit build``)
    or only the scope directories, so a ``requirements.txt`` committed earlier,
    or at the repository root, was never named. It reads the AUDITED COMMIT
    through ``gitio`` — never the working tree — over the scope directories and
    the files at the repository root, and the receipt binds each blob digest in
    ``reproduction.tree_locks``; ``verify`` re-reads each one at the commit;
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


#: The read bound for a dependency lock found outside the manifest. Locks are
#: hashed whole (a truncated hash would pin nothing); a lock larger than this is
#: left unrecorded rather than hashed in part — the same rule on both sides,
#: because ``verify`` re-reads under this one constant.
LOCK_READ_LIMIT = 16 * 1024 * 1024

#: Git modes of a regular file. A symlink or submodule entry named like a lock
#: is not a lock: its "content" is a path or a commit id, not a resolved pin.
_REGULAR_MODES = ("100644", "100755")


def _in_lock_scope(path: str, prefixes: list[str]) -> bool:
    """At the repository root, or under one of the audited scope prefixes
    (``""`` — no configured scope — is the whole tree)."""
    if "/" not in path:
        return True
    for prefix in prefixes:
        prefix = str(prefix or "").strip("/")
        if not prefix or path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def detect_tree_locks(repo, sha: str, prefixes: list[str] | None,
                      manifest: dict) -> dict[str, str]:
    """Dependency locks in the audited tree that the manifest does not carry:
    ``{path: sha256 of the blob}``, sorted by path.

    Read from commit ``sha`` through ``gitio`` (never the working tree), over
    the files at the repository root plus everything under ``prefixes`` (the
    configured scope directories; ``None`` or ``[""]`` is the whole tree).
    Paths the manifest already lists are skipped — their digest is bound there.
    A scaffold ``TEMPLATE`` path, a non-regular entry, and a lock larger than
    :data:`LOCK_READ_LIMIT` are not recorded.
    """
    from ..gitio import entries, read_blob
    scope = [str(p) for p in (prefixes or [""])]
    listed = {p for p, d in (manifest or {}).items() if d != "ABSENT"}
    out: dict[str, str] = {}
    for mode, path, blob in entries(repo, sha):
        if (mode not in _REGULAR_MODES or _basename(path) not in LOCK_KINDS
                or path in listed or "TEMPLATE" in path.split("/")
                or not _in_lock_scope(path, scope)):
            continue
        data, truncated = read_blob(repo, blob, limit=LOCK_READ_LIMIT)
        if truncated:
            continue
        out[path] = _sha256(data)
    return dict(sorted(out.items()))


def tree_locks(receipt: dict) -> dict[str, str]:
    """The ``reproduction.tree_locks`` a receipt binds (``{}`` when absent)."""
    block = receipt.get("reproduction") if isinstance(receipt, dict) else None
    value = block.get("tree_locks") if isinstance(block, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def all_locks(receipt: dict, extra: dict | None = None) -> dict[str, str]:
    """Every lock a receipt pins: the manifest's, plus its tree locks (or
    ``extra``, while the block is still being built), sorted by path."""
    locks = detect_locks(receipt.get("inputs", {}).get("manifest", {}))
    locks.update(tree_locks(receipt) if extra is None else extra)
    return dict(sorted(locks.items()))


def lock_kinds(locks: dict) -> list[str]:
    """The sorted, de-duplicated ecosystems named by a set of lock paths."""
    return sorted({LOCK_KINDS[_basename(p)] for p in locks})


def build_bundle(receipt: dict, tree: dict | None = None) -> dict:
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
    locks = all_locks(receipt, tree)
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


def receipt_block(receipt: dict, tree: dict | None = None) -> dict | None:
    """The optional ``reproduction`` block for a receipt, or ``None`` when the
    audited tree carries no dependency lock (so the receipt stays byte-identical
    to a pre-A2 receipt — additive, exactly like ``tool_evidence``).

    ``tree`` is :func:`detect_tree_locks`' result. It appears in the block as
    ``tree_locks`` only when non-empty, so a receipt whose every lock is in its
    manifest is byte-identical to one minted before D171.
    """
    tree = dict(tree or {})
    locks = all_locks(receipt, tree)
    if not locks:
        return None
    bundle = build_bundle(receipt, tree)
    block = {
        "bundle_sha256": bundle_digest(bundle),
        "locks": len(locks),
        "lock_kinds": lock_kinds(locks),
    }
    if tree:
        block["tree_locks"] = tree
    return block
