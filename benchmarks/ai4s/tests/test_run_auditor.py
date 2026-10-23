"""The model-layer runner: the dry run on the fixture, the live gates, and the live
path end to end through the project's offline ``replay`` provider.

    PYTHONPATH=src python -m pytest -q benchmarks/ai4s/tests/test_run_auditor.py

No network and no credential: the live test sets a placeholder value for the gate
variable and answers from recorded replies keyed by prompt digest, which is what
the replay provider exists for. Honest boundary: this proves the plumbing (prompt
assembly, gates, caching, parsing, rows), not anything about a real model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
AI4S = TESTS.parent
sys.path.insert(0, str(AI4S))

import run_auditor as ra  # noqa: E402
import run_checks as rc  # noqa: E402

FIXTURE = TESTS / "fixtures" / "mini_corpus"


def test_dry_run_on_fixture(tmp_path):
    summary = ra.dry_run(FIXTURE, tmp_path, "science", ra.DEFAULT_PRICE_MODELS, 1500)
    assert summary["instances"] == 8 and summary["bounded_instances"] == 0
    rows = [json.loads(x) for x in (tmp_path / "auditor_dryrun_rows.jsonl").read_text().splitlines()]
    assert all(len(r["prompt_sha256"]) == 64 for r in rows)
    assert summary["total_prompt_bytes"] == sum(r["prompt_bytes"] for r in rows)
    assert all(row["priced"] for row in summary["cost"])
    again = ra.dry_run(FIXTURE, tmp_path / "b", "science", ra.DEFAULT_PRICE_MODELS, 1500)
    assert [r["prompt_sha256"] for r in rows] == [
        json.loads(x)["prompt_sha256"]
        for x in (tmp_path / "b" / "auditor_dryrun_rows.jsonl").read_text().splitlines()]
    assert again["est_input_tokens"] == summary["est_input_tokens"]
    # nothing from the corpus beyond hashes and counts
    assert "Arrhenius" not in (tmp_path / "auditor_dryrun_rows.jsonl").read_text()


def test_live_refuses_without_every_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ra.KEY_ENV, raising=False)
    base = ["--live", "--corpus", str(FIXTURE), "--out", str(tmp_path),
            "--provider", "anthropic", "--model", "claude-sonnet-5"]
    assert ra.main(base + ["--max-usd", "1", "--i-accept-cost"]) == 2
    monkeypatch.setenv(ra.KEY_ENV, "placeholder-not-a-key")
    assert ra.main(base + ["--i-accept-cost"]) == 2
    assert ra.main(base + ["--max-usd", "1"]) == 2
    assert ra.main(base + ["--max-usd", "0", "--i-accept-cost"]) == 2
    assert "refuses" in capsys.readouterr().err
    assert not (tmp_path / "auditor_rows.jsonl").exists()


def test_live_path_through_replay_provider(tmp_path, monkeypatch):
    from crossaudit.auditor import prompt as prompt_mod
    from crossaudit.providers import replay

    transcripts = tmp_path / "transcripts"
    checks = rc.resolve_profile("science")[0]
    manifest = rc.read_manifest(FIXTURE)
    for row in manifest:
        a = ra.assemble(rc.read_instance(rc.instance_dir(FIXTURE, row)), checks)
        if row["instance_id"].endswith("D08-above_max"):
            text = "I could not decide."                     # unreadable: one repair turn
        elif row["clean"]:
            text = json.dumps({"verdict": "PASS", "sections_applied": ["CA-DATA-002"],
                               "findings": []})
        else:
            text = json.dumps({"verdict": "BLOCKED", "sections_applied": ["CA-PHYS-001"],
                               "findings": [{"severity": "BLOCKER", "rule": "CA-PHYS-001",
                                             "artifact": "results.json",
                                             "observation": "value out of range"}]})
        replay.record(transcripts, system=prompt_mod.SYSTEM, prompt=a["prompt"], text=text)
    monkeypatch.setenv(ra.KEY_ENV, "placeholder-not-a-key")
    monkeypatch.setenv(replay.ENV_DIR, str(transcripts))
    out = tmp_path / "live"
    argv = ["--live", "--corpus", str(FIXTURE), "--out", str(out), "--provider", "replay",
            "--vendor", "replay", "--model", "fixture", "--max-usd", "1", "--i-accept-cost"]
    assert ra.main(argv) == 0
    rows = {r["instance_id"]: r for r in
            map(json.loads, (out / "auditor_rows.jsonl").read_text().splitlines())}
    assert len(rows) == 8 and all(r["non_evidential"] for r in rows.values())
    clean = rows["arrhenius_kinetics-s1-clean"]
    assert clean["model_verdict"] == "PASS" and clean["invalid_reason"] is None
    d08 = rows["arrhenius_kinetics-s1-D08-above_max"]
    assert d08["model_verdict"] is None and d08["invalid_reason"]
    d05 = rows["dft_convergence-s1-D05-converged_false"]
    assert d05["model_verdict"] == "BLOCKED" and d05["expected_rule_cited"] is False
    assert rows["arrhenius_kinetics-s1-D02-empty_unit"]["dcl_verdict"] == "BLOCKED"
    assert "value out of range" not in (out / "auditor_rows.jsonl").read_text()
    cached = list((out / "cache").glob("*.json"))
    assert len(cached) == 8                                  # one per prompt; the failed repair is not cached
    assert all(set(json.loads(p.read_text())) >= {"prompt_sha256", "response_text"}
               for p in cached)
    assert ra.main(argv) == 0                                # second run: served from cache
    again = [json.loads(x) for x in (out / "auditor_rows.jsonl").read_text().splitlines()]
    assert sum(r["cached"] for r in again) == 8
