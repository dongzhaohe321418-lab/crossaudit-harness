"""Full receipt verification, and the admission transaction.

Verification is read-only and offline: it re-derives every binding from the two
git trees and refuses on the first mismatch. Admission is a separate, explicit
step that consumes the receipt inside the controller's lock.

What `--admit` refuses beyond verification (installer-design 05a):
  * an install mode whose code could have changed since it identified itself;
  * a receipt whose isolation evidence is weaker than the deployment's minimum;
  * a state store inside a throwaway checkout, where "consumed" survives nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import _selfid
from ..config import Config
from ..controller import StateStore
from ..errors import IntegrityDenial
from ..gitio import blob_limit, commit_exists, entries, is_ancestor, read_blob, resolve
from . import schema


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityDenial(f"receipt unreadable: {exc}", path=str(path)) from exc
    return schema.validate(raw)


def _verify_tool_evidence(te: dict, ledger_file: Path) -> None:
    """Re-derive the evidence ledger and confirm the receipt bound a genuine,
    untampered prefix of it. Raises IntegrityDenial on any mismatch."""
    from ..ledger import EvidenceLedger
    led = EvidenceLedger(ledger_file)
    report = led.verify()
    if not report.ok:
        raise IntegrityDenial(f"evidence ledger failed re-derivation: {report.error}")
    n = int(te["entries"])
    head = str(te["ledger_head"])
    rows = led.entries()
    if n < 1 or n > len(rows) or str(rows[n - 1].get("digest", "")) != head:
        raise IntegrityDenial(
            "receipt tool_evidence head does not match the evidence ledger")


def verify(receipt: dict, *, science_root: Path, audit_root: Path,
           expect_repo: str, expect_sha: str, cfg: Config | None = None) -> dict:
    """Re-derive every binding. Returns an evidence dict; raises on any mismatch."""
    subject, inputs, ledger = receipt["subject"], receipt["inputs"], receipt["ledger"]

    if subject["science_repo"] != expect_repo:
        raise IntegrityDenial(f"science_repo {subject['science_repo']!r} != expected "
                              f"{expect_repo!r}")
    if subject["sha"] != expect_sha:
        raise IntegrityDenial(f"receipt sha {subject['sha'][:12]} != expected "
                              f"{expect_sha[:12]}")
    if not commit_exists(science_root, subject["sha"]):
        raise IntegrityDenial("audited commit is not in the science repository",
                              sha=subject["sha"][:12])

    sha, tree = resolve(science_root, subject["sha"])
    if tree != subject["tree"]:
        raise IntegrityDenial(f"science tree {tree[:12]} != receipt tree "
                              f"{subject['tree'][:12]}")

    # Manifest against the tree, not the working directory.
    blobs = {path: blob for _mode, path, blob in entries(science_root, sha)}
    for rel, declared in inputs["manifest"].items():
        if declared == "ABSENT":
            if rel in blobs:
                raise IntegrityDenial(f"manifest says ABSENT but {rel} is in the tree")
            continue
        if rel not in blobs:
            raise IntegrityDenial(f"manifest lists {rel}, absent from the tree")
        # Re-read under the same per-path bound the audit hashed with; a limit
        # that differs from audit-time would deny intact large documents forever.
        data, truncated = read_blob(science_root, blobs[rel], limit=blob_limit(rel))
        if truncated or _sha256(data) != declared:
            raise IntegrityDenial(f"manifest mismatch for {rel}")

    # Constitution: content hash and the commit that versions it (I3).
    const_rel = inputs.get("constitution_path", "AUDIT_RULES.md")
    const_path = audit_root / const_rel
    if not const_path.is_file():
        raise IntegrityDenial(f"constitution {const_rel} missing from the audit tree")
    if _sha256(const_path.read_bytes()) != inputs["constitution_sha256"]:
        raise IntegrityDenial("constitution content differs from the receipt's hash")
    if inputs["constitution_commit"] in ("", None, "unversioned"):
        raise IntegrityDenial("receipt declares the constitution unversioned")

    # Report blob, in the cycle directory the receipt names.
    cycle_dir = audit_root / ledger["cycle_path"]
    report = cycle_dir / "report.md"
    if not report.is_file():
        raise IntegrityDenial(f"report missing at {ledger['cycle_path']}/report.md")
    if _sha256(report.read_bytes()) != ledger["report_sha256"]:
        raise IntegrityDenial("report blob hash mismatch")
    report_text = report.read_text(encoding="utf-8", errors="replace")
    reported = re.search(r"^\| verdict \| \*\*([A-Z_]+)\*\* \|$",
                         report_text, re.MULTILINE)
    if reported is None:
        raise IntegrityDenial("bound report has no machine-readable verdict row")
    if reported.group(1) != receipt["audit"]["verdict"]:
        raise IntegrityDenial(
            f"receipt verdict {receipt['audit']['verdict']} differs from bound "
            f"report verdict {reported.group(1)}")
    if not cycle_dir.name.startswith(subject["sha"][:12]):
        raise IntegrityDenial(f"cycle directory {cycle_dir.name} does not belong to "
                              f"{subject['sha'][:12]}")

    # The report commit must exist and precede this receipt (ordering rule).
    report_commit = ledger["report_commit"]
    if report_commit and commit_exists(audit_root, report_commit):
        head = resolve(audit_root, "HEAD")[0]
        if head != report_commit and not is_ancestor(audit_root, report_commit, head):
            raise IntegrityDenial("report commit is not an ancestor of the audit head")
    elif report_commit:
        raise IntegrityDenial("report commit named by the receipt is not in the audit repo")

    admission_shortfalls = []
    if receipt["audit"]["verdict"] != "PASS":
        admission_shortfalls.append(
            f"verdict is {receipt['audit']['verdict']}, not PASS")
    if receipt["audit"]["audit_integrity"] != "OK":
        admission_shortfalls.append(
            f"audit integrity is {receipt['audit']['audit_integrity']}")
    if cfg is not None:
        short = schema.isolation_shortfall(receipt, cfg.isolation_minimum)
        if short:
            admission_shortfalls.append(
                f"isolation evidence is missing {short}")

    # Cross-check the bound evidence ledger when it is present locally. The head
    # is already bound cryptographically (part of the receipt digest); this also
    # re-derives the ledger chain and confirms the receipt bound an untampered
    # prefix. Skipped when the ledger file is absent, so offline verification
    # without the local ledger still succeeds.
    te = receipt.get("tool_evidence")
    if te is not None and cfg is not None:
        ledger_file = cfg.root / cfg.state_dir / "evidence.jsonl"
        if ledger_file.exists():
            _verify_tool_evidence(te, ledger_file)

    # Reproducibility bundle (A2): the manifest was just re-derived from the git
    # tree above, so recomputing the bundle and comparing its digest confirms the
    # named dependency locks are exactly the audited ones. A tampered lock in the
    # tree already fails the manifest check; this also catches a forged block.
    rep = receipt.get("reproduction")
    if rep is not None:
        from . import reproduction
        recomputed = reproduction.build_bundle(receipt)
        if reproduction.bundle_digest(recomputed) != rep["bundle_sha256"]:
            raise IntegrityDenial(
                "reproduction bundle digest does not match the receipt")
        locks = reproduction.detect_locks(inputs["manifest"])
        if len(locks) != rep["locks"]:
            raise IntegrityDenial(
                "reproduction lock count does not match the audited manifest")

    # Governed-source provenance (A4): re-derive the source-id set from the same
    # tool_evidence-bound ledger prefix and refuse a mismatch. Gated on the local
    # ledger being present, so signature-only offline verification still passes.
    src = receipt.get("sources")
    if src is not None and cfg is not None:
        ledger_file = cfg.root / cfg.state_dir / "evidence.jsonl"
        if ledger_file.exists():
            from . import sources as sources_mod
            recomputed = sources_mod.receipt_block(cfg, receipt)
            if recomputed is None:
                raise IntegrityDenial(
                    "receipt claims governed sources but none re-derive from the "
                    "evidence ledger")
            if (recomputed["set_sha256"] != src["set_sha256"]
                    or recomputed["count"] != src["count"]):
                raise IntegrityDenial(
                    "governed-source set does not match the evidence ledger")

    return {
        "receipt_digest": schema.digest(receipt),
        "sha": subject["sha"],
        "cycle_id": receipt["cycle"]["cycle_id"],
        "verified": True,
        "admission_ready": not admission_shortfalls,
        "admission_shortfalls": admission_shortfalls,
    }


def admit(receipt: dict, store: StateStore, evidence: dict,
          cfg: Config | None = None) -> dict:
    """Consume the receipt once, in the controller's lock.

    Refuses install modes that cannot stand behind their own digest, because an
    admission is exactly the moment that identity has to hold.
    """
    if receipt["audit"]["verdict"] != "PASS":
        raise IntegrityDenial(f"verdict is {receipt['audit']['verdict']}, not PASS — "
                              f"nothing to admit", verdict=receipt["audit"]["verdict"])
    if receipt["audit"]["audit_integrity"] != "OK":
        raise IntegrityDenial(f"audit integrity: {receipt['audit']['audit_integrity']}")
    if cfg is not None:
        short = schema.isolation_shortfall(receipt, cfg.isolation_minimum)
        if short:
            raise IntegrityDenial(
                f"isolation evidence is weaker than this deployment requires: "
                f"missing {short}", missing=short)

    ident = _selfid.identity()
    if ident["install_mode"] not in _selfid.ADMISSIBLE_MODES:
        raise IntegrityDenial(
            f"install mode {ident['install_mode']!r} may verify but never admit: its "
            f"code can change under the digest it reports",
            install_mode=ident["install_mode"])
    if receipt["verifier"]["code_digest_sha256"] != ident["code_digest_sha256"]:
        raise IntegrityDenial(
            "the verifier that minted this receipt is not the one admitting it; "
            "re-verify with the recorded version before admitting",
            minted_by=receipt["verifier"].get("version"))
    store.admit(evidence["cycle_id"], evidence["sha"], evidence["receipt_digest"])
    return {"admitted": True, "receipt_digest": evidence["receipt_digest"],
            "cycle_id": evidence["cycle_id"]}
