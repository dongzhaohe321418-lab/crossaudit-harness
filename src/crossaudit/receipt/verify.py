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

import yaml

from .. import _selfid
from ..config import Config
from ..controller import StateStore
from ..errors import ConfigDenial, Denial, IntegrityDenial
from ..gitio import (blob_limit, commit_exists, entries, is_ancestor,
                     materialise, read_blob, read_committed_bytes, resolve)
from . import schema


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


#: The project configuration's filename, from `config` rather than restated
#: here — a transcribed constant drifts from the source it claims to track. The
#: receipt does not cite a path for it, which is itself a limit of the format.
from ..config import CONFIG_NAME as CONFIG_FILENAME

#: Distinguishes "the commit has no ``checks:`` key" (which means the default
#: profile) from "the key is present and null" (which config.load refuses).
#: config.load makes exactly this distinction; re-deriving without it would
#: resolve a different list than the one the audit actually ran.
_ABSENT = object()


def _cited_audit_commit(receipt: dict, audit_root: Path) -> str | None:
    """The audit-repository commit whose tree is this receipt's own evidence for
    the project configuration and the house skills that shaped the round.

    Resolved from the receipt, and confirmed to exist **in the repository being
    asked**, never assumed from the science side:

    1. ``ledger.report_commit`` — written in the audit repo during this audit,
       immediately before the receipt was built, so its tree is the audit repo
       as it stood at audit time. The strongest pin the format offers.
    2. ``subject.sha`` — only when that commit actually exists here. In the
       single-repo layout the audit repo and the science repo are one
       repository, so the audited commit carries these files. Verifying a
       receipt against a *separate* audit repo must not look up a science sha in
       it: that reached a person as ``git ls-tree failed: fatal: not a tree
       object``.
    3. Otherwise ``None`` — the claims below are not derivable, and say so.
    """
    report_commit = str(receipt["ledger"].get("report_commit") or "")
    if report_commit and commit_exists(audit_root, report_commit):
        return report_commit
    subject_sha = str(receipt["subject"]["sha"])
    if subject_sha and commit_exists(audit_root, subject_sha):
        return subject_sha
    return None


def _committed_config_bytes(audit_root: Path, commit: str) -> bytes:
    """``crossaudit.yml`` exactly as stored in ``commit``.

    Named separately so the working-tree read it replaces cannot creep back in
    unnoticed: reading the *current* file both denies honest history (edit your
    config and your ledger is retroactively invalid) and accepts a forged
    ``inputs.checks`` from anyone who can edit an uncommitted file.
    """
    return read_committed_bytes(audit_root, commit, CONFIG_FILENAME)


def _resolve_committed_checks(raw) -> list[str]:
    """Re-run the selection ``config.load`` ran, on the committed value.

    A profile name is expanded through the same ``dcl.profiles.resolve``, so
    ``checks: general`` in the commit re-derives to the four concrete names a
    receipt records and a profile whose membership changed is caught.
    """
    from ..dcl.profiles import DEFAULT_PROFILE, resolve as _resolve
    return _resolve(DEFAULT_PROFILE if raw is _ABSENT else raw)


def _skills_match(declared: dict, derived: dict) -> tuple[bool, str]:
    """Whether the recorded manifest is the committed one, and under which of
    the two shipped digest conventions.

    A convention must hold for EVERY entry: one writer minted one receipt, so a
    manifest that is parsed-body for one skill and committed-bytes for another
    was produced by no writer this product ships and is not corroborated.
    """
    if set(declared) != set(derived):
        return False, ""
    if all(declared[path] == derived[path][0] for path in declared):
        return True, "the parsed skill body"
    if all(declared[path] == derived[path][1] for path in declared):
        return True, "the committed file bytes"
    return False, ""


def _checks_match(declared: list, derived: list) -> bool:
    """Whether the recorded selection is the committed one — ordered, on purpose.

    ``checks:`` is a list in the committed file and the receipt records it in
    that order, so a reordered list is a different configuration text and set
    equality would report two different configurations as the same one. This is
    stricter than the checks themselves require, which is safe here because the
    comparison only ever reports and never denies.
    """
    return list(declared) == list(derived)


def _refuse_oversize_skill(path: str, data: bytes, total: int, skills_mod) -> None:
    """The skills module's own size policy, applied to committed bytes.

    `materialise` bounds a blob at `blob_limit` — 512 KiB for a .md — while
    `skills.load` refuses anything over MAX_SKILL_BYTES (60,000). Those are
    different numbers, so the bound is re-applied here; without it the verifier
    would derive a skill the shipped disk writer refuses to mint.
    """
    if len(data) > skills_mod.MAX_SKILL_BYTES:
        raise ConfigDenial(
            f"skill {path} is {len(data)} bytes, over the "
            f"{skills_mod.MAX_SKILL_BYTES}-byte limit skills.load enforces")
    if total > skills_mod.MAX_TOTAL_BYTES:
        raise ConfigDenial(
            f"the committed skills total more than {skills_mod.MAX_TOTAL_BYTES} bytes")


def _committed_skills(audit_root: Path, commit: str) -> dict:
    """The house-skills manifest ``commit``'s tree implies, whole.

    Reads the tree through **`gitio.materialise`** — the same primitive the
    shipped writer uses on its subject-commit path. That is deliberate and it is
    not deference: sharing the reader means producer and verifier refuse the
    same symlinks and the same submodules by construction, rather than by two
    hand-rolled mode checks that happen to agree today. My own first version
    checked only for symlinks and would have silently ignored a submodule under
    `skills/` that the writer refuses outright.

    The size policy is re-applied on top, because it belongs to `skills` and not
    to `gitio` — see `_refuse_oversize_skill`.

    Returns ``path -> (parsed-body digest, committed-bytes digest)``, because the
    product ships BOTH conventions and the receipt does not say which minted it.
    `cli/main.py:_skills_manifest` hashes `skills.manifest`'s parsed body on its
    disk path and `sha256` of the raw blob on its subject-commit path, and those
    differ for any skill with front matter. A verifier that knew only one would
    call half the product's own honest receipts forged.

    The parsed-body digest comes from the writer's own ``skills._parse`` /
    ``skills.manifest``, so front-matter stripping and CRLF normalisation are
    shared by construction rather than reimplemented here.
    """
    from .. import skills as skills_mod

    files, _notes = materialise(audit_root, commit, skills_mod.SKILLS_DIR)
    parsed, blob_digests, total = [], {}, 0
    for path, data in sorted(files.items()):
        if not path.endswith(".md"):
            continue
        total += len(data)
        _refuse_oversize_skill(path, data, total, skills_mod)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigDenial(f"skill {path} is not UTF-8: {exc}") from exc
        parsed.append(skills_mod._parse(text, Path(path).stem, path))
        blob_digests[path] = _sha256(data)
    bodies = skills_mod.manifest(parsed)
    return {path: (bodies[path], blob_digests[path]) for path in bodies}


def _local_dcl_source_digest() -> str | None:
    """This installation's check-layer digest, or ``None`` if it cannot say.

    A frozen build missing ``crossaudit-build.json`` raises ``ConfigDenial``
    here; a config error must never reach a person from inside an integrity
    read, so it is reported as an unavailable comparison instead.
    """
    from ..auditor.run import dcl_source_digest
    try:
        return dcl_source_digest()
    except Denial:
        return None


def _derivation(claim: str, source: str, status: str, detail: str) -> dict:
    return {"claim": claim, "source": source, "status": status, "detail": detail}


def _input_derivations(receipt: dict, *, audit_root: Path) -> list[dict]:
    """Re-derive the three receipt inputs D41 left unchecked, and report them.

    **This never raises on a divergence, by decision.** A verifier that denies
    honest, signed, controller-recorded receipts is worse than one that is too
    permissive: too permissive lets a bad receipt through and the ledger is
    still a ledger, while a false denial tells a person their genuine audit is
    invalid — and the true case is the only one most people will ever have.
    None of these three claims is pinned by the *producer*, so no divergence
    here can be distinguished from an honest one:

    * ``checks`` — ``crossaudit.yml`` is not required to be committed (only the
      constitution is), so an operator who edits config without committing
      diverges honestly;
    * ``skills`` — the shipped writer (``cli/main.py:_skills_manifest``) reads
      ``skills.load(cfg.root)``, the working directory, so a skill added after
      the audited commit is genuinely recorded by an honest mint;
    * ``dcl_source_sha256`` — see below, there is no cited object at all.

    Each becomes enforceable the day its producer pins it, and this returns the
    status a caller would then promote. ``admit()`` meanwhile still refuses on
    ``verifier.code_digest_sha256``, a strictly stronger digest over the whole
    package, at the moment identity must hold.
    """
    inputs = receipt["inputs"]
    rows: list[dict] = []
    cited = _cited_audit_commit(receipt, audit_root)
    at = f"{cited[:12]}" if cited else ""

    # --- #10: the configured check list -----------------------------------
    if cited is None:
        rows.append(_derivation(
            "checks", "none", "not-derivable",
            f"the receipt cites no audit-repository commit that could carry "
            f"{CONFIG_FILENAME}, so the recorded check selection cannot be "
            f"re-derived offline"))
    else:
        source = f"{at}:{CONFIG_FILENAME}"
        try:
            raw_doc = yaml.safe_load(
                _committed_config_bytes(audit_root, cited).decode("utf-8"))
            doc = raw_doc if isinstance(raw_doc, dict) else {}
            derived = _resolve_committed_checks(
                doc["checks"] if "checks" in doc else _ABSENT)
        except (Denial, yaml.YAMLError, UnicodeDecodeError) as exc:
            rows.append(_derivation("checks", source, "not-derivable",
                             f"{CONFIG_FILENAME} could not be re-derived from "
                             f"{at}: {exc}"))
        else:
            declared = list(inputs.get("checks") or [])
            if _checks_match(declared, derived):
                rows.append(_derivation("checks", source, "corroborated",
                                 f"the recorded check selection re-derives from "
                                 f"{source}"))
            else:
                rows.append(_derivation(
                    "checks", source, "diverged",
                    f"the receipt records checks {declared} but {source} selects "
                    f"{list(derived)}"))

    # --- #11: the house-skills manifest -----------------------------------
    declared_skills = dict(inputs.get("skills") or {})
    if cited is None:
        rows.append(_derivation(
            "skills", "none", "not-derivable",
            "the receipt cites no audit-repository commit whose skills/ prefix "
            "could be re-derived offline"))
    else:
        source = f"{at}:skills/"
        try:
            derived_skills = _committed_skills(audit_root, cited)
        except Denial as exc:
            rows.append(_derivation("skills", source, "not-derivable",
                             f"the skills manifest could not be re-derived from "
                             f"{at}: {exc}"))
        else:
            matched, convention = _skills_match(declared_skills, derived_skills)
            if matched:
                rows.append(_derivation(
                    "skills", source, "corroborated",
                    f"all {len(derived_skills)} recorded skills re-derive from "
                    f"{source}, hashed over {convention}"))
            else:
                missing = sorted(set(derived_skills) - set(declared_skills))
                extra = sorted(set(declared_skills) - set(derived_skills))
                changed = sorted(k for k in set(declared_skills) & set(derived_skills)
                                 if declared_skills[k] not in derived_skills[k])
                parts = []
                if missing:
                    parts.append(f"in force but not recorded: {missing}")
                if extra:
                    parts.append(f"recorded but not in {source}: {extra}")
                if changed:
                    parts.append(f"recorded with a different body: {changed}")
                rows.append(_derivation("skills", source, "diverged",
                                 "; ".join(parts)))

    # --- #9: the deterministic-layer source digest -------------------------
    # There is no cited object and none can exist in this format: the digest
    # hashes crossaudit/dcl/**.py *of the process that minted the receipt*, plus
    # any plugin packs it had loaded. That source lives in the installed
    # program, not in either repository, and the receipt names no repo, commit
    # or path for it. Comparing it to this host is an identity claim about two
    # installations, not a re-derivation of the receipt's claim, so it is
    # labelled with its own vocabulary and can never be read as one.
    declared_dcl = str(inputs.get("dcl_source_sha256") or "")
    local = _local_dcl_source_digest()
    if local is None:
        rows.append(_derivation(
            "dcl_source_sha256", "this installation", "not-derivable",
            "this installation cannot identify its own check layer, so the "
            "receipt's deterministic-layer digest cannot be compared"))
    elif declared_dcl == local:
        rows.append(_derivation(
            "dcl_source_sha256", "this installation", "local-match",
            "this receipt was minted by the same check layer this installation "
            "runs (an identity match, not a re-derivation: no committed object "
            "pins the check layer)"))
    else:
        rows.append(_derivation(
            "dcl_source_sha256", "this installation", "local-differs",
            f"this receipt was minted by a different check layer than this "
            f"installation runs ({declared_dcl[:12] or 'absent'} vs "
            f"{local[:12]}); expected after any release, and expected on every "
            f"run where check packs were loaded at audit time"))
    return rows


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


def _verify_cycle_record(receipt: dict, cfg: Config | None) -> None:
    """Re-derive a D36 cycle pin and the verdict row that produced a receipt."""
    cycle_pin = receipt["cycle"].get("constitution_commit")
    if not cycle_pin:
        return                         # old v2 receipts remain readable
    if cfg is None:
        raise IntegrityDenial(
            "cycle-bound receipt verification needs the project's controller state")
    stored = StateStore(cfg.root / cfg.state_dir / "state.json").cycle(
        receipt["cycle"]["cycle_id"])
    if stored is None:
        raise IntegrityDenial("receipt cycle is absent from the controller state")
    cy = receipt["cycle"]
    if (stored.get("root_sha") != cy["root_sha"]
            or stored.get("constitution_commit") != cycle_pin
            or cycle_pin != receipt["inputs"]["constitution_commit"]):
        raise IntegrityDenial("receipt cycle does not match its pinned constitution")
    match = [row for row in stored.get("verdicts", ())
             if row.get("round") == cy["round"]
             and row.get("sha") == cy["active_sha"]
             and row.get("verdict") == receipt["audit"]["verdict"]]
    if not match:
        raise IntegrityDenial("receipt verdict is not recorded for its cycle round")
    expected = schema.digest(receipt)[:16]
    if not any(str(row.get("receipt", "")) == expected for row in match):
        raise IntegrityDenial("receipt is not the controller's recorded verdict")


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

    # Constitution: the cited Git object is the source of truth (I3). Never
    # substitute the current working-tree path for a receipt's commit pin.
    const_rel = inputs.get("constitution_path", "AUDIT_RULES.md")
    const_commit = inputs["constitution_commit"]
    if const_commit in ("", None, "unversioned"):
        raise IntegrityDenial("receipt declares the constitution unversioned")
    const_bytes = read_committed_bytes(audit_root, const_commit, const_rel)
    if _sha256(const_bytes) != inputs["constitution_sha256"]:
        raise IntegrityDenial("constitution content differs from the receipt's hash")

    # D36: when present, re-derive the controller record and immutable verdict.
    _verify_cycle_record(receipt, cfg)

    # Report blob, in the cycle directory the receipt names. A cited report
    # commit is authoritative; the working-tree fallback is retained only for
    # old receipts that intentionally carried no report commit.
    cycle_dir = audit_root / ledger["cycle_path"]
    report = cycle_dir / "report.md"
    if report_commit := ledger["report_commit"]:
        report_bytes = read_committed_bytes(
            audit_root, report_commit, f"{ledger['cycle_path']}/report.md")
    else:
        if not report.is_file():
            raise IntegrityDenial(f"report missing at {ledger['cycle_path']}/report.md")
        report_bytes = report.read_bytes()
    if _sha256(report_bytes) != ledger["report_sha256"]:
        raise IntegrityDenial("report blob hash mismatch")
    report_text = report_bytes.decode("utf-8", errors="replace")
    reported = re.search(r"^\| verdict \| \*\*([A-Z_]+)\*\* \|$",
                         report_text, re.MULTILINE)
    if reported is None:
        raise IntegrityDenial("bound report has no machine-readable verdict row")
    if reported.group(1) != receipt["audit"]["verdict"]:
        raise IntegrityDenial(
            f"receipt verdict {receipt['audit']['verdict']} differs from bound "
            f"report verdict {reported.group(1)}")
    authority = receipt.get("authority")
    if authority is not None:
        # D148: re-derive the block's own bindings (evidence digest, ids, route
        # from verdict) even for a receipt handed in as a dict, then bind the
        # report's route row to it the way its verdict row is bound above.
        from ..auditor.authority import validate_block
        block_errors = validate_block(authority)
        if block_errors:
            raise IntegrityDenial("authority block does not validate: "
                                  + "; ".join(block_errors), errors=block_errors)
        route_row = re.search(r"^\| evidence route \| \*\*([a-z-]+)\*\* \|$",
                              report_text, re.MULTILINE)
        if route_row is None:
            raise IntegrityDenial("bound report has no evidence-route row")
        if route_row.group(1) != authority["route"]:
            raise IntegrityDenial(
                f"receipt evidence route {authority['route']} differs from bound "
                f"report route {route_row.group(1)}")
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
    if authority is not None and authority["route"] != "receipt":
        admission_shortfalls.append(
            f"evidence route is {authority['route']}, not receipt")
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

    # D41 #9/#10/#11, re-derived from the object each receipt cites and
    # reported. Deliberately additive: it adds no denial and no admission
    # shortfall, so every receipt that verified and admitted before this still
    # does — including a plugins: deployment, whose minted check-layer digest
    # folds in packs a verifier never loads.
    derivations = _input_derivations(receipt, audit_root=audit_root)

    return {
        "receipt_digest": schema.digest(receipt),
        "sha": subject["sha"],
        "cycle_id": receipt["cycle"]["cycle_id"],
        "verified": True,
        "admission_ready": not admission_shortfalls,
        "admission_shortfalls": admission_shortfalls,
        "input_derivations": derivations,
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
    authority = receipt.get("authority")
    if authority is not None and authority["route"] != "receipt":
        raise IntegrityDenial(
            f"evidence route is {authority['route']}, not receipt — nothing to admit",
            route=authority["route"])
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
