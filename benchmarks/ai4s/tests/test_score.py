"""The AI4S runner and scorer, checked against hand-built ground truth and known values.

    PYTHONPATH=src python -m pytest -q benchmarks/ai4s/tests/test_score.py

What is checked: that ``run_checks.py`` on the hand-built fixture corpus writes the
caught / any_block / attributed each instance was built to produce under the
shipped ``science`` profile; the §5 classification rules on results the fixture
cannot produce (ADVISORY tier, unexpected blocker); the Wilson interval against
published values; the packed cluster bootstrap against a naive computation; the
coverage of the primary interval by simulation (EXPERIMENT_RECORD §10); and that
scoring is deterministic. What is not: the pack (``science-ai4s``) — these tests
run only the shipped profile so they do not depend on it landing.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
AI4S = TESTS.parent
sys.path.insert(0, str(AI4S))
sys.path.insert(0, str(TESTS))

import run_checks as rc  # noqa: E402
import score as sc  # noqa: E402
from _synth import write_two_profile_run  # noqa: E402

FIXTURE = TESTS / "fixtures" / "mini_corpus"

#: What each fixture instance was built to produce under `science`.
EXPECTED = {
    "arrhenius_kinetics-s1-clean": (None, False, None),
    "dft_convergence-s1-clean": (None, False, None),
    "arrhenius_kinetics-s1-D01-no_code_version": (True, True, True),
    "arrhenius_kinetics-s1-D02-empty_unit": (True, True, True),
    "arrhenius_kinetics-s1-D04-input_file_missing": (True, True, True),
    "dft_convergence-s1-D05-converged_false": (True, True, True),
    "arrhenius_kinetics-s1-D08-above_max": (False, False, False),
    "arrhenius_kinetics-s1-D16-no_seed": (False, False, False),
}


@pytest.fixture(scope="module")
def fixture_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    record = rc.run(FIXTURE, ["science", "no-such-profile"], out, repeat=2)
    return out, record


def _rows(out: Path) -> list[dict]:
    return [json.loads(x) for x in (out / "rows.jsonl").read_text().splitlines()]


# ------------------------------------------------------------------ runner

def test_fixture_manifest_matches_files():
    for row in rc.read_manifest(FIXTURE):
        files = rc.read_instance(rc.instance_dir(FIXTURE, row))
        assert {p: rc.sha256_bytes(b) for p, b in files.items()} == row["files_sha256"]


def test_runner_rows_carry_the_planted_ground_truth(fixture_run):
    out, _ = fixture_run
    rows = _rows(out)
    assert {r["profile"] for r in rows} == {"science"}
    assert len(rows) == len(EXPECTED)
    for r in rows:
        assert (r["caught"], r["any_block"], r["attributed"]) == EXPECTED[r["instance_id"]], r
        assert r["dcl_version"] == 3 and len(r["corpus_sha256"]) == 64
        for f in r["findings"]:
            assert set(f) == set(rc.FINDING_KEYS)


def test_runner_records_unknown_profile_and_replicate(fixture_run):
    out, record = fixture_run
    assert record["unknown_profiles"] == ["no-such-profile"]
    assert any(e.get("profile") == "no-such-profile" for e in record["errors"])
    assert not [e for e in record["errors"] if e.get("instance_id")]
    assert record["replicate_identical"] is True
    assert (out / "rows.replicate.jsonl").is_file()
    contracts = json.loads((out / "checks_contracts.json").read_text())
    assert set(contracts["science"]) == {"schema", "units", "convergence", "provenance",
                                         "number_source"}
    run = json.loads((out / "run.json").read_text())
    assert run["counts"] == {"instances": 8, "clean": 2, "planted": 6, "templates": 2,
                             "by_class": {"D01": 1, "D02": 1, "D04": 1, "D05": 1,
                                          "D08": 1, "D16": 1}}
    assert len(run["corpus_manifest_sha256"]) == 64
    assert run["environment"]["python"]


def test_pack_catches_what_the_shipped_profile_misses(tmp_path):
    """Integration, skipped until `science-ai4s` resolves: D08 and the ADVISORY-tier D16
    are missed by `science` and caught by the pack, with no false block on the two
    clean controls."""
    rc.import_packs()
    if rc.resolve_profile("science-ai4s")[0] is None:
        pytest.skip("science-ai4s is not registered in this tree")
    rc.run(FIXTURE, ["science-ai4s"], tmp_path, repeat=1)
    rows = {r["instance_id"]: r for r in _rows(tmp_path)}
    assert rows["arrhenius_kinetics-s1-D08-above_max"]["caught"] is True
    d16 = rows["arrhenius_kinetics-s1-D16-no_seed"]
    assert (d16["caught"], d16["any_block"]) == (True, False)
    assert not any(r["any_block"] for r in rows.values() if r["clean"])


def test_replicate_comparison_ignores_only_wall_ms():
    a = json.dumps({"x": 1, "wall_ms": 1.0}) + "\n"
    b = json.dumps({"x": 1, "wall_ms": 9.0}) + "\n"
    c = json.dumps({"x": 2, "wall_ms": 1.0}) + "\n"
    assert rc.strip_wall(a) == rc.strip_wall(b)
    assert rc.strip_wall(a) != rc.strip_wall(c)


# ------------------------------------------------------------------ classification

CLASSES = rc.taxonomy_classes(rc.load_taxonomy())


def _planted(cls, variant, severity=None):
    tax = CLASSES[cls]
    exp = {"tier": tax["tier"], "rules": tax["rules"], "checks": tax["checks"],
           "severity": severity or tax["severity"]}
    return {"instance_id": "x", "clean": False, "defect_class": cls, "variant": variant,
            "expected": exp}


def _result(verdict, *findings):
    return {"verdict": verdict, "findings": [
        {"severity": s, "implementation_code": code, "check": chk, "rule": f"DCL:{chk}"}
        for s, code, chk in findings]}


def test_advisory_tier_is_caught_by_an_advisory():
    row = _planted("D16", "no_seed")
    got = rc.classify(row, _result("PASS", ("ADVISORY", "CA-REPRO-001", "repro_declared")),
                      CLASSES)
    assert got == {"caught": True, "any_block": False, "attributed": True}


def test_caught_follows_the_instance_expected_severity_not_the_class():
    advisory = _result("PASS", ("ADVISORY", "CA-DATA-003", "provenance"))
    assert rc.classify(_planted("D04", "revision_mismatch", "ADVISORY"), advisory,
                       CLASSES)["caught"] is True
    # same class and variant, but the instance says BLOCKER: no class special case
    assert rc.classify(_planted("D04", "revision_mismatch", "BLOCKER"), advisory,
                       CLASSES)["caught"] is False
    # an ADVISORY-severity instance of a BLOCKER class (D15 todo_left via CA-FILE-004)
    row = {"instance_id": "x", "clean": False, "defect_class": "D15",
           "variant": "todo_left",
           "expected": {"tier": "deterministic_new", "rules": ["CA-FILE-004"],
                        "checks": ["complete"], "severity": "ADVISORY"}}
    got = rc.classify(row, _result("PASS", ("ADVISORY", "CA-FILE-004", "complete")), CLASSES)
    assert got == {"caught": True, "any_block": False, "attributed": True}


def test_missing_expected_fields_come_from_variant_overrides():
    row = {"instance_id": "x", "clean": False, "defect_class": "D15",
           "variant": "template_placeholder", "expected": None}
    exp = rc.expected_for(row, CLASSES)
    if "template_placeholder" in (CLASSES["D15"].get("variant_overrides") or {}):
        assert exp["severity"] == "ADVISORY" and exp["rules"] == ["CA-FILE-004"]
    row = {"instance_id": "x", "clean": False, "defect_class": "D04",
           "variant": "revision_mismatch",
           "expected": {"rules": ["CA-DATA-003"], "checks": ["provenance"],
                        "severity": "BLOCKER", "tier": "deterministic_existing"}}
    assert rc.expected_for(row, CLASSES)["severity"] == "BLOCKER"   # manifest wins


def test_blocker_tier_needs_a_blocker_from_an_expected_rule():
    row = _planted("D08", "above_max")
    assert rc.classify(row, _result("PASS", ("ADVISORY", "CA-PHYS-001", "range_rules")),
                       CLASSES)["caught"] is False
    other = rc.classify(row, _result("BLOCKED", ("BLOCKER", "CA-DERIV-001", "derivations")),
                        CLASSES)
    assert other == {"caught": False, "any_block": True, "attributed": False}
    by_check = rc.classify(row, _result("BLOCKED", ("BLOCKER", "CA-OTHER-9", "range_rules")),
                           CLASSES)
    assert by_check["caught"] is True


def test_clean_rows_have_null_caught_and_false_block_indicator():
    row = {"instance_id": "c", "clean": True}
    assert rc.classify(row, _result("BLOCKED", ("BLOCKER", "CA-META-001", "schema")),
                       CLASSES) == {"caught": None, "any_block": True, "attributed": None}


def test_d06_variant_tier_comes_from_taxonomy():
    row = {"instance_id": "x", "clean": False, "defect_class": "D06",
           "variant": "sign_word_flip", "expected": None}
    assert rc.expected_for(row, CLASSES)["tier"] == "referent"


# ------------------------------------------------------------------ statistics

def test_wilson_known_values():
    # 0/60: the Wilson upper bound is z^2 / (n + z^2) = 3.8415 / 63.8415 = 0.0602 in
    # closed form. The brief quoted 0.0598, which is not the Wilson value (the exact
    # Clopper-Pearson bound is 0.0596); the closed form is what is asserted.
    low, high = sc.wilson(0, 60)
    z2 = sc.Z95 ** 2
    assert high == pytest.approx(z2 / (60 + z2), abs=1e-12)
    assert (round(low, 4), round(high, 4)) == (0.0, 0.0602)
    low, high = sc.wilson(4, 398)        # the project's quoted §8g band, 0.39–2.56%
    assert (round(low, 4), round(high, 4)) == (0.0039, 0.0256)
    low, high = sc.wilson(1, 1)
    assert round(low, 4) == 0.2065 and high == 1.0
    assert sc.wilson(0, 0) == (None, None)


def test_percentile_type7():
    v = [1.0, 2.0, 3.0, 4.0]
    assert sc.percentile(v, 0) == 1.0 and sc.percentile(v, 100) == 4.0
    assert sc.percentile(v, 50) == 2.5
    assert abs(sc.percentile(v, 2.5) - 1.075) < 1e-12


def _naive_delta(table, classes):
    rs, re_, present = 0.0, 0.0, 0
    for c in classes:
        ks = sum(r.get(c, (0, 0, 0))[0] for r in table)
        ke = sum(r.get(c, (0, 0, 0))[1] for r in table)
        n = sum(r.get(c, (0, 0, 0))[2] for r in table)
        if n:
            rs, re_, present = rs + ks / n, re_ + ke / n, present + 1
    return (re_ - rs) / present


def test_packed_clusters_equal_naive_arithmetic():
    rng = random.Random(11)
    classes = [f"D{i:02d}" for i in range(1, 18)]
    for _ in range(30):
        table = []
        for _t in range(rng.randint(2, 40)):
            row = {}
            for c in classes:
                if rng.random() < 0.7:
                    n = rng.randint(1, 4)
                    ks = rng.randint(0, n)
                    row[c] = (ks, rng.randint(ks, n), n)
            table.append(row)
        if not any(table):
            continue
        pc = sc.PackedClusters(table, classes)
        assert abs(pc.delta(sum(pc.packed)) - _naive_delta(table, classes)) < 1e-12
        picks = [rng.randrange(len(table)) for _ in table]
        resampled = [table[i] for i in picks]
        if any(resampled):
            assert abs(pc.delta(sum(pc.packed[i] for i in picks))
                       - _naive_delta(resampled, classes)) < 1e-12


def test_bootstrap_is_seeded_and_brackets_the_point():
    table = [{"D01": (1, 1, 1), "D08": (0, i % 2, 1)} for i in range(20)]
    a = sc.cluster_bootstrap(table, ["D01", "D08"], resamples=500, seed=5)
    b = sc.cluster_bootstrap(table, ["D01", "D08"], resamples=500, seed=5)
    assert a == b
    assert a["delta"] == pytest.approx(0.25)
    assert a["ci_low"] <= a["delta"] <= a["ci_high"]
    same = sc.cluster_bootstrap([{"D01": (0, 1, 1)}] * 10, ["D01"], resamples=100, seed=1)
    assert same["delta"] == same["ci_low"] == same["ci_high"] == 1.0


def test_bootstrap_interval_coverage_at_corpus_design():
    """EXPERIMENT_RECORD §10: the interval's coverage is simulated, not assumed.

    60 templates (6 domains x 10 seeds), the 17 taxonomy classes with their real
    domain restrictions and variant counts, a logit-scale template random effect
    (sigma 1), 300 simulated corpora with 400 resamples each, under a null delta
    and a delta near 0.30. The committed coverage_check.json must equal this
    measurement exactly, so the flag score.py copies into numbers.json cannot go
    stale.
    """
    rec = sc.coverage_record()
    by = {r["scenario"]: r for r in rec["runs"]}
    assert by["null"]["true_delta"] == 0.0
    assert 0.27 <= by["effect"]["true_delta"] <= 0.33
    committed = json.loads(sc.COVERAGE_RECORD.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(rec)) == committed
    for r in rec["runs"]:
        assert sc.COVERAGE_BAND[0] <= r["coverage"] <= sc.COVERAGE_BAND[1], r
    assert rec["passed"] is True


# ------------------------------------------------------------------ scoring

def test_score_fixture(fixture_run):
    out, _ = fixture_run
    n = sc.score(out)
    rec = n["recall"]["by_class"]
    assert (rec["D01"]["science"]["k"], rec["D01"]["science"]["n"]) == (1, 1)
    assert rec["D08"]["science"]["rate"] == 0.0
    assert n["recall"]["by_class_variant"]["D16"]["no_seed"]["science"]["k"] == 0
    assert n["recall"]["class_avg"]["science"]["value"] == pytest.approx(4 / 6)
    assert n["recall"]["class_avg"]["science"]["n_classes"] == 6
    fb = n["false_block"]["science"]
    assert (fb["count"], fb["n"]) == (0, 2)
    assert round(fb["wilson_high"], 4) == round(sc.wilson(0, 2)[1], 4)
    assert n["primary"]["available"] is False
    assert n["claims"]["H1"]["holds"] is False and n["claims"]["H2"]["decidable"] is False
    assert n["attribution"]["overall"]["science"]["k"] == 4
    assert n["fired"]["by_class"]["D05"]["science"] == {"CA-METH-002": 1}
    assert n["wall_ms"]["science"]["n"] == 8
    assert n["profiles"]["unknown"] == ["no-such-profile"]


def test_score_two_profiles(tmp_path):
    run = write_two_profile_run(tmp_path / "run")
    n = sc.score(run)
    ca = n["recall"]["class_avg"]
    rows = [json.loads(x) for x in (run / "rows.jsonl").read_text().splitlines()]
    d08_ext = [r for r in rows if r["defect_class"] == "D08" and r["profile"] == "science-ai4s"]
    d08 = sum(r["caught"] for r in d08_ext) / len(d08_ext)
    assert ca["science"]["value"] == pytest.approx(1 / 3)
    assert ca["science-ai4s"]["value"] == pytest.approx((1 + d08 + 1) / 3)
    p = n["primary"]
    assert p["available"] and p["delta"] == pytest.approx((d08 + 1) / 3)
    assert p["ci_low"] <= p["delta"] <= p["ci_high"]
    assert (p["seed"], p["resamples"], p["clusters"]) == (20261021, 2000, 12)
    fb = n["false_block"]["science-ai4s"]
    assert fb["count"] == 1 and fb["by_check"] == {"range_rules": 1}
    assert fb["by_code"] == {"CA-PHYS-001": 1}
    assert n["recall"]["by_class"]["D16"]["science-ai4s"]["k"] == 12
    assert n["advisory_only"]["science-ai4s"]["k"] == 12
    assert n["claims"]["H2"]["decidable"] is True
    assert n["claims"]["H2"]["holds"] is False          # 1/12 false blocks: bound > 2.5%


def test_numbers_have_design_keys(tmp_path):
    n = sc.score(write_two_profile_run(tmp_path / "run"))
    c = n["recall"]["by_class"]["D08"]["science"]
    assert set(c) >= {"rate", "n", "wilson_low", "wilson_high"}
    assert set(n["false_block"]["science"]) >= {"count", "n", "wilson_low", "wilson_high"}
    assert set(n["primary"]) >= {"delta", "ci_low", "ci_high", "resamples", "seed",
                                 "clusters", "coverage_checked"}
    assert set(n["environment"]) >= {"python", "platform", "git", "generation_seed",
                                     "corpus_manifest_sha256"}
    assert set(n["wall_ms"]["science"]) == {"mean", "max", "n"}


def test_missing_coverage_record_marks_interval_uncalibrated(tmp_path):
    n = sc.score(write_two_profile_run(tmp_path / "run"), coverage_path=tmp_path / "none.json")
    assert n["primary"]["coverage_checked"] is False


def test_scoring_is_deterministic(tmp_path):
    run = write_two_profile_run(tmp_path / "run")
    first = sc.write_numbers(run, sc.score(run)).read_bytes()
    second = sc.write_numbers(run, sc.score(run)).read_bytes()
    assert first == second
