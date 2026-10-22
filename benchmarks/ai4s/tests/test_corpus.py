"""The corpus generator's contract (benchmarks/ai4s/DESIGN.md §2, §8.1).

The test that matters most is the clean-control one: every clean instance
passes the SHIPPED `science` profile (and `science` + `complete`) with no
finding at all, so a block on a clean instance in the measurement is the
check's false block and never the corpus's fault.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SEED, SEEDS, instance_files

import domains
import generate
import planted

TAXONOMY = planted.TAXONOMY


def _clean(rows):
    return [r for r in rows if r["clean"]]


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


# (a) ---------------------------------------------------------------------
def test_generation_is_byte_deterministic(corpus, tmp_path):
    out, _rows = corpus
    again = tmp_path / "again"
    generate.generate(SEED, again, seeds_per_domain=SEEDS)
    assert (again / "manifest.jsonl").read_bytes() == (out / "manifest.jsonl").read_bytes()
    assert _tree(again) == _tree(out)


def test_a_subset_run_reproduces_the_shared_instances(corpus, tmp_path):
    out, rows = corpus
    sub = tmp_path / "sub"
    generate.generate(SEED, sub, seeds_per_domain=1, domain_names=["biostat_two_group"],
                      classes={"D13"})
    sub_rows = [json.loads(l) for l in (sub / "manifest.jsonl").read_text().splitlines()]
    full = {r["instance_id"]: r for r in rows}
    assert sub_rows and all(full[r["instance_id"]] == r for r in sub_rows)


# (b), (c) ------------------------------------------------------------------
@pytest.mark.parametrize("extra", [[], ["complete"]], ids=["science", "science+complete"])
def test_every_clean_instance_passes_the_shipped_profile_with_zero_findings(corpus, extra):
    from crossaudit.dcl import run_checks
    from crossaudit.dcl.profiles import resolve
    out, rows = corpus
    bad = {}
    for row in _clean(rows):
        result = run_checks(instance_files(out, row), resolve("science") + extra).as_dict()
        if result["verdict"] != "PASS" or result["findings"]:
            bad[row["instance_id"]] = [(f["severity"], f.get("implementation_code", f["rule"]),
                                        f["observation"][:160]) for f in result["findings"]]
    assert not bad, bad


def _ai4s_profile():
    from crossaudit.dcl.profiles import PROFILES
    if "science-ai4s" not in PROFILES:
        pytest.skip("science-ai4s profile not present in this tree")
    return PROFILES["science-ai4s"]


def test_every_clean_instance_passes_the_ai4s_profile_with_zero_findings(corpus):
    """The declarations (ranges, derivations, claims, splits, precision) are
    honest on clean controls, as the extended pack reads them."""
    from crossaudit.dcl import run_checks
    names = _ai4s_profile()
    out, rows = corpus
    bad = {}
    for row in _clean(rows):
        result = run_checks(instance_files(out, row), names).as_dict()
        if result["findings"]:
            bad[row["instance_id"]] = [(f["severity"], f.get("implementation_code"), f["observation"][:160])
                                       for f in result["findings"]]
    assert not bad, bad


def test_false_claims_are_false_against_the_committed_data(corpus):
    """A D13 plant must be caught by `claims` alone: its derivations (and every
    other check) still pass, because the data were redrawn and recomputed."""
    from crossaudit.dcl import run_checks
    names = _ai4s_profile()
    out, rows = corpus
    for row in rows:
        if row["defect_class"] != "D13":
            continue
        result = run_checks(instance_files(out, row), names).as_dict()
        codes = {f["implementation_code"] for f in result["findings"]}
        assert codes == {"CA-STAT-004"}, (row["instance_id"], result["findings"])


def test_aggregate_plants_are_caught_by_the_derivation_alone(corpus):
    """A D18 plant (v2, DESIGN.md §9 Amendment 3) edits one reported aggregate
    in results.json: under science-ai4s exactly one finding comes back, the
    CA-DERIV-001 of that aggregate's own derivation (no other check, and no
    other derivation, notices); under `science` there is nothing, because the
    shipped profile does not recompute anything."""
    from crossaudit.dcl import run_checks
    from crossaudit.dcl.profiles import resolve
    names = _ai4s_profile()
    out, rows = corpus
    seen = set()
    for row in rows:
        if row["defect_class"] != "D18":
            continue
        files = instance_files(out, row)
        result = run_checks(files, names).as_dict()
        got = [(f["severity"], f["implementation_code"]) for f in result["findings"]]
        assert got == [("BLOCKER", "CA-DERIV-001")], (row["instance_id"], result["findings"])
        name = domains.get(row["domain"]).SPEC["d18"][row["variant"]]
        assert f"({name})" in result["findings"][0]["observation"], row["instance_id"]
        assert run_checks(files, resolve("science")).as_dict()["findings"] == []
        seen.add(row["variant"])
    assert seen == set(planted.CLASSES["D18"]["variants"])


# (d) ----------------------------------------------------------------------
_PATH = __import__("re").compile(r"([A-Za-z_][\w]*)|\[(\d+)\]")


def _resolve(doc, locator):
    cur = doc
    for name, index in _PATH.findall(locator):
        try:
            cur = cur[name] if name else cur[int(index)]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def _check_edit(clean_files, new_files, edit, variant):
    path, loc, before, after = edit["file"], edit["locator"], edit["before"], edit["after"]
    if loc == "file":
        assert path not in new_files
        assert hashlib.sha256(clean_files[path]).hexdigest() == before
        return
    if loc.startswith("move:"):
        src, dst = loc[5:].split("->")
        old, new = json.loads(clean_files[path]), json.loads(new_files[path])
        assert before == after
        assert _resolve(old, src) == before and before not in old[dst.split("[")[0]]
        assert _resolve(new, dst) == after and after not in new[src.split("[")[0]]
        return
    if path.endswith(".json") and loc not in ("line",):
        old, new = json.loads(clean_files[path]), json.loads(new_files[path])
        assert _resolve(old, loc) == before
        got = _resolve(new, loc)
        if edit.get("after_is_token"):
            assert (math.isnan(got) if after == "NaN" else got == math.inf)
        else:
            assert got == after
        return
    old_text = clean_files[path].decode("utf-8")
    new_text = new_files.get(path, b"").decode("utf-8")
    if before is not None:
        assert before in old_text
    if after is not None:
        assert after in new_text
    if loc.startswith("truncated"):
        assert old_text.startswith(new_text) and old_text[len(new_text):] == before


def test_each_planted_instance_differs_from_its_pair_in_exactly_the_recorded_files(corpus):
    out, rows = corpus
    clean = {r["pair_id"]: r for r in _clean(rows)}
    for row in rows:
        if row["clean"]:
            continue
        c = clean[row["pair_id"]]
        a, b = c["files_sha256"], row["files_sha256"]
        changed = sorted(p for p in set(a) | set(b) if a.get(p) != b.get(p))
        rec = row["planted"]
        assert changed == rec["files"], row["instance_id"]
        assert rec["file"] in rec["files"]
        cf, nf = instance_files(out, c), instance_files(out, row)
        if rec["locator"] == "regenerated" or row["defect_class"] == "D13":
            # The claim's quantity moved; the data file was redrawn.
            assert rec["regenerated"] in changed
        for edit in rec.get("edits", [rec]):
            _check_edit(cf, nf, edit, row["variant"])
        if len(rec["files"]) > 1:
            assert row["defect_class"] == "D13" or row["variant"] == "revision_mismatch", row["instance_id"]


def test_single_file_plants_edit_one_spot_only(corpus):
    """Text plants change exactly the recorded substring; JSON plants change
    exactly the recorded path (re-serialised documents are otherwise equal)."""
    out, rows = corpus
    clean = {r["pair_id"]: r for r in _clean(rows)}
    for row in rows:
        rec = row["planted"]
        if row["clean"] or len(rec["files"]) != 1 or rec["locator"] != "line" or rec["before"] is None:
            continue
        cf, nf = instance_files(out, clean[row["pair_id"]]), instance_files(out, row)
        old, new = cf[rec["file"]].decode(), nf[rec["file"]].decode()
        assert old.replace(rec["before"], rec["after"] or "", 1) == new, row["instance_id"]


# (e) ----------------------------------------------------------------------
#: Where a variant is planted, beyond taxonomy.json's `domains` (planted.applicable).
NARROWED = {
    ("D10", "wrong_rows_used"): {"crystal_bandgap_ml", "biostat_two_group"},
    ("D13", "significance_overclaim"): {"biostat_two_group"},
    ("D13", "ci_claim_false"): {"biostat_two_group"},
    ("D13", "improvement_claim_false"): {"crystal_bandgap_ml", "nmr_shift_calibration"},
    ("D16", "no_seed"): set(domains.DOMAIN_NAMES) - {"dft_convergence"},
    ("D16", "no_command"): set(domains.DOMAIN_NAMES) - {"dft_convergence"},
    ("D16", "no_environment"): set(domains.DOMAIN_NAMES) - {"dft_convergence"},
    ("D18", "ratio_inverted"): {"crystal_bandgap_ml", "biostat_two_group"},
    ("D18", "percent_sign_flipped"): {"crystal_bandgap_ml", "biostat_two_group"},
    ("D18", "sd_population_as_sd"): {"biostat_two_group"},
    ("D18", "sd_as_sd_population"): {"xrd_bragg"},
    ("D18", "median_perturbed_1pct"): {"biostat_two_group", "xrd_bragg"},
}


def test_every_class_variant_is_instantiated_on_every_applicable_domain_and_seed(corpus):
    _out, rows = corpus
    have = {(r["domain"], r["seed"], r["defect_class"], r["variant"]) for r in rows if not r["clean"]}
    for c in TAXONOMY["classes"]:
        listed = set(domains.DOMAIN_NAMES) if c["domains"] == "all" else set(c["domains"])
        for v in c["variants"]:
            want = NARROWED.get((c["id"], v), listed)
            assert want, (c["id"], v)
            for d in domains.DOMAIN_NAMES:
                for s in range(SEEDS):
                    assert ((d, s, c["id"], v) in have) == (d in want), (d, s, c["id"], v)


def _expected_from_taxonomy(c: dict, variant: str) -> dict:
    """Independent restatement of the override rule: class values, then
    variant_tiers, then variant_overrides (each key replaces the class value)."""
    exp = {"tier": c.get("variant_tiers", {}).get(variant, c["tier"]),
           "rules": c["rules"], "checks": c["checks"], "severity": c["severity"]}
    exp.update(c.get("variant_overrides", {}).get(variant, {}))
    return exp


def test_manifest_expected_matches_taxonomy(corpus):
    _out, rows = corpus
    classes = {c["id"]: c for c in TAXONOMY["classes"]}
    for row in rows:
        if row["clean"]:
            assert row["defect_class"] is None and row["planted"] is None and row["expected"] is None
            assert row["instance_id"] == f"{row['pair_id']}-clean"
            continue
        c = classes[row["defect_class"]]
        assert row["expected"] == _expected_from_taxonomy(c, row["variant"]), row["instance_id"]
        assert row["instance_id"] == f"{row['pair_id']}-{row['defect_class']}-{row['variant']}"


def test_variant_overrides_reach_the_manifest(corpus):
    _out, rows = corpus
    by = {(r["defect_class"], r["variant"]): r["expected"] for r in rows if not r["clean"]}
    assert by[("D04", "revision_mismatch")]["severity"] == "ADVISORY"
    assert by[("D04", "source_not_declared")]["severity"] == "BLOCKER"
    for v in ("todo_left", "template_placeholder"):
        assert by[("D15", v)] == {"tier": "deterministic_new", "rules": ["CA-FILE-004"],
                                  "checks": ["complete"], "severity": "ADVISORY"}
    t = by[("D15", "summary_truncated_mid_block")]
    assert t["tier"] == "deterministic_existing" and t["severity"] == "BLOCKER"
    assert "CA-NUM-001" in t["rules"]


def test_corpus_layout_is_flat(corpus):
    """The runner reads <corpus>/<instance_id>/...: one directory per manifest
    row directly under the corpus root, and nothing else there."""
    out, rows = corpus
    entries = {p.name for p in out.iterdir()}
    assert entries == {r["instance_id"] for r in rows} | {"manifest.jsonl", generate.MARKER}
    for r in rows:
        assert "TASK.md" in r["files_sha256"] and (out / r["instance_id"] / "TASK.md").is_file()


# (f) ----------------------------------------------------------------------
def test_clean_analysis_scripts_reproduce_their_results(corpus, tmp_path):
    out, rows = corpus
    for row in _clean(rows):
        files = instance_files(out, row)
        exp = next(p for p in files if p.endswith("/metadata.yml")).rsplit("/", 1)[0]
        work = tmp_path / row["instance_id"]
        shutil.copytree(out / row["instance_id"] / exp, work)
        meta = (work / "metadata.yml").read_text()
        command = json.loads(next(l for l in meta.splitlines() if l.startswith("command:")).split(":", 1)[1])
        argv = command.split()
        assert argv[0] == "python3"
        proc = subprocess.run([sys.executable] + argv[1:], cwd=work, capture_output=True,
                              timeout=20, text=True)
        assert proc.returncode == 0, proc.stderr
        printed = json.loads(proc.stdout)
        committed = json.loads(files[f"{exp}/results.json"])
        assert printed == committed, row["instance_id"]
        for rel in ("results.json", "results.txt"):
            assert (work / rel).read_bytes() == files[f"{exp}/{rel}"], (row["instance_id"], rel)
        tol = {d["quantity"]: d["tolerance"]["abs"] for d in committed.get("derivations", [])}
        for q, p in zip(committed["quantities"], printed["quantities"]):
            assert abs(q["value"] - p["value"]) <= tol.get(q["name"], 0.0)


# (g) ----------------------------------------------------------------------
def test_manifest_hashes_match_the_files_on_disk(corpus):
    out, rows = corpus
    for row in rows:
        root = out / row["instance_id"]
        on_disk = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
        assert on_disk == set(row["files_sha256"]), row["instance_id"]
        for rel, digest in row["files_sha256"].items():
            assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest


def test_instances_stay_small(corpus):
    out, rows = corpus
    for row in _clean(rows):
        for rel in row["files_sha256"]:
            data = (out / row["instance_id"] / rel).read_bytes()
            assert len(data) <= 20_000, rel
            if rel.endswith(".csv"):
                assert data.count(b"\n") <= 201, rel
