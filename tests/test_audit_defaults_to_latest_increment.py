"""`audit` and `run` without `--sha` judge the latest increment, not HEAD.

README: `crossaudit build "..."`, then `crossaudit audit --offline` ("returns
DCL_ONLY, never PASS") or `crossaudit run` ("Audit the latest committed
increment"). The acceptance run (claim C10) found the literal flow exiting 20:
after `build`, HEAD is the loop's own `audit receipt ... (PASS)` commit, and
`audit` refused it as a ledger artefact.

D10 mutations (checked by hand): make `_latest_increment` return "" and
five go red (`audit` lands on the ledger commit and exits 20; `run` finds no
increment); delete the "never overwrite a cycle" loop in
`StateStore.open_or_advance` and four go red (the build's PASSED cycle is
replaced, its receipt no longer admits, status loses it, the id is reused).
The fake vendors stub only the transport: the adapters, the resilience layer,
the build loop, the audit and the ledger writes are the real ones.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import FakeVendors, init_project, with_keys  # noqa: E402

from crossaudit.cli import main  # noqa: E402
from crossaudit.errors import EXIT_CONFIG, EXIT_ESCALATED, EXIT_OK  # noqa: E402
from crossaudit.gitio import git  # noqa: E402


@pytest.fixture()
def built(tmp_path, monkeypatch, capsys):
    """A project after the README's `init` and one passing `build` round."""
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    vendors = FakeVendors().install(monkeypatch)
    assert main.main(["build", "Create a small reproducible benchmark"]) == EXIT_OK
    capsys.readouterr()
    increment = git("log", "-1", "--format=%H", "--", "experiments", cwd=root)
    assert git("log", "-1", "--format=%s", cwd=root).startswith("audit receipt ")
    vendors.calls.clear()
    return root, vendors, increment


def _cycles(root: Path) -> dict:
    return json.loads((root / ".crossaudit" / "state.json").read_text())["cycles"]


def test_offline_audit_after_build_judges_the_increment(built, capsys):
    root, vendors, increment = built
    code = main.main(["audit", "--offline"])
    out = capsys.readouterr().out
    assert code == EXIT_ESCALATED
    assert out.splitlines()[0].startswith(f"auditing {increment[:12]} (")
    assert "DCL_ONLY" in out
    assert vendors.calls == []                    # no provider request at all


def test_the_json_result_names_the_commit_it_chose(built, capsys):
    root, _vendors, increment = built
    assert main.main(["--json", "audit", "--offline"]) == EXIT_ESCALATED
    result = json.loads(capsys.readouterr().out)  # nothing but JSON on stdout
    assert result["verdict"] == "DCL_ONLY"
    assert result["sha"] == increment
    assert result["sha_source"] == "latest_increment"


def test_offline_audit_does_not_overwrite_the_passed_cycle(built, capsys):
    root, _vendors, increment = built
    passed = {cid: c for cid, c in _cycles(root).items() if c["status"] == "PASSED"}
    assert passed
    main.main(["audit", "--offline"])
    after = _cycles(root)
    for cid, cycle in passed.items():
        assert after[cid]["status"] == "PASSED"
        assert after[cid]["verdicts"] == cycle["verdicts"]
    assert any(c["status"] == "ESCALATED" and c["active_sha"] == increment
               for cid, c in after.items() if cid not in passed)


def test_run_after_build_audits_the_increment(built, capsys):
    root, vendors, increment = built
    code = main.main(["run"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert increment[:12] in out
    assert vendors.calls == [("openai", "auditor")]


def test_an_explicit_ledger_sha_is_still_refused(built, capsys):
    root, vendors, _increment = built
    head = git("rev-parse", "HEAD", cwd=root)
    code = main.main(["audit", "--offline", "--sha", head])
    err = capsys.readouterr().err
    assert code == EXIT_CONFIG
    assert "only touches the ledger" in err
    assert vendors.calls == []


def test_an_explicit_increment_sha_is_taken_as_given(built, capsys):
    root, _vendors, increment = built
    assert main.main(["--json", "audit", "--offline", "--sha", increment]) == EXIT_ESCALATED
    result = json.loads(capsys.readouterr().out)
    assert result["sha"] == increment and result["sha_source"] == "explicit"


def test_the_passed_cycle_stays_admissible_after_the_offline_re_audit(
        built, capsys, monkeypatch):
    """The re-audit's DCL_ONLY cycle never shadows the PASS for admission."""
    root, _vendors, increment = built
    passed_id, passed = next((cid, c) for cid, c in _cycles(root).items()
                             if c["status"] == "PASSED")
    main.main(["audit", "--offline"])
    capsys.readouterr()
    receipt = next(p for p in sorted((root / "cycles").glob(f"{increment[:12]}-r1*/receipt.json"))
                   if json.loads(p.read_text())["cycle"]["cycle_id"] == passed_id)
    # Admission refuses a source checkout (its code can change under its
    # digest); the suite runs from source, so the install mode is the one
    # field stood in for. Everything else verify checks is real.
    from crossaudit import _selfid
    real = _selfid.identity
    monkeypatch.setattr(_selfid, "identity",
                        lambda: dict(real(), install_mode="wheel"))
    assert main.main(["verify", str(receipt), "--admit"]) == EXIT_OK
    assert _cycles(root)[passed_id]["status"] == "CONSUMED"
    assert main.main(["verify", str(receipt), "--admit"]) != EXIT_OK   # once


def test_status_lists_both_cycles_in_opening_order(built, capsys):
    root, _vendors, increment = built
    main.main(["audit", "--offline"])
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    rows = json.loads(capsys.readouterr().out)["cycles"]
    assert [r["status"] for r in rows] == ["PASSED", "ESCALATED"]
    assert rows[1]["reaudit_of"] == rows[0]["cycle_id"]
    main.main(["status"])
    human = capsys.readouterr().out
    assert human.index("PASSED") < human.index("ESCALATED")
    assert f"re-audit of {rows[0]['cycle_id']}" in human


def test_the_re_audit_id_is_deterministic(tmp_path):
    """Same repo, same sha, same attempt: the same id, on any run."""
    from crossaudit.controller import StateStore
    from crossaudit.controller.state import cycle_id_for

    ids = []
    for run in ("a", "b"):
        store = StateStore(tmp_path / run / "state.json")
        first = store.open_or_advance("t/p", "a" * 40, None)
        store.record_verdict(first["cycle_id"], "a" * 40, "PASS",
                             receipt_hash="r" * 64, max_rounds=3)
        again = store.open_or_advance("t/p", "a" * 40, None)
        ids.append((first["cycle_id"], again["cycle_id"]))
        assert again["reaudit_of"] == first["cycle_id"] and again["attempt"] == 2
        assert store.cycle(first["cycle_id"])["status"] == "PASSED"
    assert ids[0] == ids[1]
    assert ids[0] == (cycle_id_for("t/p", "a" * 40),
                      cycle_id_for("t/p", "a" * 40 + "\n2"))
