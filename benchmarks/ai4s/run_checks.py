"""Run the deterministic check layer over the AI4S corpus and record one row per
instance per profile.

    PYTHONPATH=../../src python run_checks.py --corpus records/corpus \
        --profiles science,science-ai4s --out records/run-2026-10-21 [--repeat 2]

For every manifest row (``DESIGN.md`` §8.1) and every profile, the instance
directory is read into ``files: dict[str, bytes]`` exactly as the DCL receives an
increment (paths relative to the instance root, POSIX separators, sorted, nothing
skipped), handed to ``crossaudit.dcl.run_checks`` with the profile's check list,
and the result is written to ``<out>/rows.jsonl`` in the §8.2 schema with
``caught`` / ``any_block`` / ``attributed`` decided by ``classify`` (§5).

Also written: ``run.json`` (environment, UTC times, corpus manifest sha256,
instance counts, errors, replicate status) and ``checks_contracts.json`` (the
contract text each profile's checks carried, so the record names exactly what
ran). ``--repeat 2`` runs everything a second time into ``rows.replicate.jsonl``
and records whether the two are byte-identical once ``wall_ms`` is removed — the
noise-floor assertion of DESIGN §1. A mismatch is recorded, and the process
exits non-zero, rather than being averaged away.

Honest boundary: this measures what the checks *say* about the bytes; it does
not judge whether the planted defect was planted correctly (the corpus tests do
that), and a row never carries corpus text beyond rule ids, paths, the checks'
own observations, and hashes. An unknown profile (for example ``science-ai4s``
before its pack lands) is recorded in ``run.json`` and skipped, not crashed on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAXONOMY_PATH = HERE / "taxonomy.json"

FINDING_KEYS = ("severity", "rule", "implementation_code", "check", "artifact",
                "observation")


# ------------------------------------------------------------------ helpers

def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def taxonomy_classes(tax: dict) -> dict[str, dict]:
    return {c["id"]: c for c in tax.get("classes", [])}


def read_manifest(corpus: Path) -> list[dict]:
    rows = []
    for line in (corpus / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def instance_dir(corpus: Path, row: dict) -> Path:
    """``<corpus>/<instance_id>``, or ``<corpus>/<row['dir']>`` when the manifest names one."""
    return corpus / str(row.get("dir") or row["instance_id"])


def read_instance(root: Path) -> dict[str, bytes]:
    """Every regular file under ``root``: relative POSIX path -> bytes, sorted."""
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return dict(sorted(out.items()))


def files_digest(files_sha256: dict[str, str]) -> str:
    """sha256 over the instance's files_sha256 map (canonical JSON, sorted keys)."""
    blob = json.dumps(files_sha256, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(blob.encode("utf-8"))


def expected_for(row: dict, classes: dict[str, dict]) -> dict:
    """The expected block for a planted row.

    The manifest's per-instance ``expected`` block is authoritative, field by
    field. Only a field it lacks is filled from taxonomy.json: the class entry
    with that variant's ``variant_overrides`` (and ``variant_tiers``) applied.
    """
    cls = classes.get(row.get("defect_class") or "", {})
    variant = row.get("variant")
    base = {"tier": cls.get("tier"), "rules": list(cls.get("rules", [])),
            "checks": list(cls.get("checks", [])),
            "severity": cls.get("severity", "BLOCKER")}
    if variant in (cls.get("variant_tiers") or {}):
        base["tier"] = cls["variant_tiers"][variant]
    base.update((cls.get("variant_overrides") or {}).get(variant) or {})
    exp = dict(row.get("expected") or {})
    for key, value in base.items():
        if exp.get(key) is None:
            exp[key] = value
    return exp


def relaxed(exp: dict) -> bool:
    """Whether "caught" uses the ADVISORY rule: decided by the instance's own
    ``expected.severity``, never by class id."""
    return exp.get("severity") == "ADVISORY"


def _matches(finding: dict, exp: dict) -> bool:
    return (finding.get("implementation_code") in set(exp.get("rules") or [])
            or finding.get("check") in set(exp.get("checks") or []))


def classify(row: dict, result: dict, classes: dict[str, dict]) -> dict:
    """``caught`` / ``any_block`` / ``attributed`` for one instance under one profile (§5).

    * planted, ``expected.severity`` BLOCKER: caught = BLOCKED and a BLOCKER
      finding whose implementation_code is an expected rule or whose check is an
      expected check;
    * planted, ``expected.severity`` ADVISORY (per instance: D16, D17, D04
      revision_mismatch, D15 todo_left / template_placeholder in the current
      taxonomy): caught = any finding of any severity matching an expected rule
      or check;
    * any_block = verdict BLOCKED (for a clean instance: the false-block indicator);
    * attributed = at least one finding of any severity matched an expected rule
      or check (attribution accuracy is reported among any_block instances);
    * clean: caught and attributed are None.
    """
    verdict = result.get("verdict")
    findings = result.get("findings") or []
    any_block = verdict == "BLOCKED"
    if row.get("clean"):
        return {"caught": None, "any_block": any_block, "attributed": None}
    exp = expected_for(row, classes)
    matched = [f for f in findings if _matches(f, exp)]
    if relaxed(exp):
        caught = bool(matched)
    else:
        caught = any_block and any(f.get("severity") == "BLOCKER" for f in matched)
    return {"caught": caught, "any_block": any_block, "attributed": bool(matched)}


def import_packs() -> list[str]:
    """Import optional check packs so profiles that need them resolve; return what loaded."""
    loaded = []
    try:
        import crossaudit.dcl.ai4s  # noqa: F401
        loaded.append("crossaudit.dcl.ai4s")
    except ImportError:
        pass
    return loaded


def resolve_profile(name: str) -> tuple[list[str] | None, str | None]:
    from crossaudit.dcl import profiles
    from crossaudit.errors import ConfigDenial

    try:
        return profiles.resolve(name), None
    except ConfigDenial as exc:
        return None, f"profile {name!r} did not resolve: {exc}"


def git_sha(cwd: Path = HERE) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                                  text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    return {"sha": run("rev-parse", "HEAD") or None,
            "dirty": bool(run("status", "--porcelain"))}


# ------------------------------------------------------------------ the run

def one_pass(corpus: Path, manifest: list[dict], profiles: dict[str, list[str]],
             classes: dict[str, dict], errors: list[dict]) -> list[dict]:
    from crossaudit.dcl import run_checks

    rows: list[dict] = []
    for mrow in manifest:
        root = instance_dir(corpus, mrow)
        files = read_instance(root)
        shas = {p: sha256_bytes(b) for p, b in files.items()}
        declared = mrow.get("files_sha256")
        if declared is not None and declared != shas:
            errors.append({"instance_id": mrow["instance_id"],
                           "error": "files on disk differ from manifest files_sha256"})
        digest = files_digest(shas)
        for profile, names in profiles.items():
            started = time.perf_counter()
            try:
                result = run_checks(files, names).as_dict()
                error = None
            except Exception as exc:          # recorded, never averaged away
                result, error = {}, f"{type(exc).__name__}: {exc}"
            wall_ms = round((time.perf_counter() - started) * 1000.0, 3)
            if error:
                errors.append({"instance_id": mrow["instance_id"], "profile": profile,
                               "error": error})
                verdict_cls = {"caught": None if mrow.get("clean") else False,
                               "any_block": False,
                               "attributed": None if mrow.get("clean") else False}
            else:
                verdict_cls = classify(mrow, result, classes)
            findings = [{k: f.get(k, "") for k in FINDING_KEYS}
                        for f in result.get("findings", [])]
            row = {
                "instance_id": mrow["instance_id"],
                "pair_id": mrow.get("pair_id"),
                "domain": mrow.get("domain"),
                "clean": bool(mrow.get("clean")),
                "defect_class": mrow.get("defect_class"),
                "variant": mrow.get("variant"),
                "profile": profile,
                "verdict": result.get("verdict", "ERROR"),
                "hard_failures": result.get("total_hard_failures", 0),
                "scope_started": result.get("scope_started"),
                "findings": findings,
                **verdict_cls,
                "wall_ms": wall_ms,
                "dcl_version": result.get("crossaudit_dcl_version"),
                "corpus_sha256": digest,
            }
            if error:
                row["error"] = error
            rows.append(row)
    return rows


def dump_rows(rows: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)


def strip_wall(text: str) -> str:
    out = []
    for line in text.splitlines():
        row = json.loads(line)
        row.pop("wall_ms", None)
        out.append(json.dumps(row, sort_keys=True, ensure_ascii=False))
    return "\n".join(out)


def counts(manifest: list[dict]) -> dict:
    by_class: dict[str, int] = {}
    for r in manifest:
        if not r.get("clean"):
            by_class[r["defect_class"]] = by_class.get(r["defect_class"], 0) + 1
    return {"instances": len(manifest),
            "clean": sum(1 for r in manifest if r.get("clean")),
            "planted": sum(1 for r in manifest if not r.get("clean")),
            "templates": len({r.get("pair_id") for r in manifest}),
            "by_class": dict(sorted(by_class.items()))}


def generation_seed(corpus: Path, tax: dict) -> dict:
    for name in ("corpus.json", "generation.json"):
        p = corpus / name
        if p.is_file():
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for key in ("generation_seed", "seed"):
                if key in doc:
                    return {"value": doc[key], "source": name}
    return {"value": tax.get("generation_seed"), "source": "taxonomy.json"}


def run(corpus: Path, profile_names: list[str], out: Path, repeat: int = 1) -> dict:
    import crossaudit
    from crossaudit.dcl import contracts

    out.mkdir(parents=True, exist_ok=True)
    tax = load_taxonomy()
    classes = taxonomy_classes(tax)
    packs = import_packs()
    manifest = read_manifest(corpus)
    started = datetime.now(timezone.utc)
    errors: list[dict] = []
    resolved: dict[str, list[str]] = {}
    unknown: list[str] = []
    for name in profile_names:
        names, why = resolve_profile(name)
        if names is None:
            unknown.append(name)
            errors.append({"profile": name, "error": why})
        else:
            resolved[name] = names
    contract_record = {p: contracts(names) for p, names in resolved.items()}
    (out / "checks_contracts.json").write_text(
        json.dumps(contract_record, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")

    first = dump_rows(one_pass(corpus, manifest, resolved, classes, errors))
    (out / "rows.jsonl").write_text(first, encoding="utf-8")
    replicate_identical = None
    if repeat >= 2:
        second = dump_rows(one_pass(corpus, manifest, resolved, classes, []))
        (out / "rows.replicate.jsonl").write_text(second, encoding="utf-8")
        replicate_identical = strip_wall(first) == strip_wall(second)
    ended = datetime.now(timezone.utc)

    record = {
        "study": "ai4s-dcl",
        "corpus": str(corpus.resolve()),
        "corpus_manifest_sha256": sha256_bytes((corpus / "manifest.jsonl").read_bytes()),
        "generation_seed": generation_seed(corpus, tax),
        "taxonomy_sha256": sha256_bytes(TAXONOMY_PATH.read_bytes()),
        "profiles_requested": profile_names,
        "profiles": resolved,
        "unknown_profiles": unknown,
        "packs_loaded": packs,
        "counts": counts(manifest),
        "rows": first.count("\n"),
        "repeat": repeat,
        "replicate_identical": replicate_identical,
        "errors": errors,
        "checks_contracts_sha256": sha256_bytes((out / "checks_contracts.json").read_bytes()),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "git": git_sha(),
            "crossaudit_file": str(Path(crossaudit.__file__).resolve()),
            "crossaudit_version": getattr(crossaudit, "__version__", None),
        },
        "utc_start": started.isoformat(timespec="seconds"),
        "utc_end": ended.isoformat(timespec="seconds"),
    }
    (out / "run.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n",
                                  encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--profiles", default="science,science-ai4s")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--repeat", type=int, default=1, choices=(1, 2))
    args = ap.parse_args(argv)
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    record = run(args.corpus, profiles, args.out, args.repeat)
    print(json.dumps({k: record[k] for k in ("rows", "unknown_profiles",
                                             "replicate_identical")}
                     | {"errors": len(record["errors"])}))
    return 1 if record["replicate_identical"] is False else 0


if __name__ == "__main__":
    sys.exit(main())
