"""D171 R2: "a changed byte fails it" holds for the file a person opens, not
only for the committed record.

`verify` re-reads `report.md` at the bound `report_commit`; before D171 a byte
flipped in the working-tree copy — or committed on top — still printed
`BINDINGS VERIFIED`, exit 0. Each test mints a real receipt with an offline
`crossaudit audit --write-ledger` and runs `crossaudit verify` as typed. The
mutation each guard catches is named in its docstring (CONTRIBUTING, D10).
"""
from __future__ import annotations

import json
from pathlib import Path

from crossaudit.cli import main as cli

from .conftest import git
from .test_verify_signature_cli import _mint


def _flip_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    i = data.index(b"verdict")                 # a byte a reader would see
    data[i] ^= 0x20                            # 'v' -> 'V'
    path.write_bytes(bytes(data))


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def test_an_untouched_tree_prints_four_claims_and_passes(science, monkeypatch, capsys):
    receipt = _mint(science, monkeypatch)
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 0
    lines = _lines(capsys.readouterr().out)
    assert lines[0].startswith("BINDINGS VERIFIED  ")
    assert lines[1].startswith("SIGNED  ")
    assert lines[2].startswith("RECORDED  ")
    assert lines[3].startswith("WORKING TREE MATCHES  ")
    assert "report.md" in lines[3]


def test_a_byte_flipped_in_the_working_tree_report_is_refused(
        science, monkeypatch, capsys):
    """Mutation: make `_drift_line` never return a refusal -> exit 0, red.
    Mutation: compare against `report_commit`'s blob instead of the file on
    disk (what `verify` already does) -> MATCHES, red."""
    receipt = _mint(science, monkeypatch)
    report = receipt.parent / "report.md"
    _flip_byte(report)
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 21
    captured = capsys.readouterr()
    rel = report.relative_to(science).as_posix()
    assert f"WORKING TREE DRIFTED  {rel}" in captured.out
    assert "BINDINGS VERIFIED" in captured.out      # the record itself held
    assert "the report on disk is not the audited report" in captured.err
    assert rel in captured.err


def test_a_flip_committed_on_top_is_refused(science, monkeypatch, capsys):
    """The bound commit still carries the audited bytes, so the record
    verifies; the file at HEAD and on disk does not, and is refused."""
    receipt = _mint(science, monkeypatch)
    report = receipt.parent / "report.md"
    _flip_byte(report)
    git("add", "--", report.relative_to(science).as_posix(), cwd=science)
    git("commit", "-q", "-m", "edit the report", cwd=science)
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 21
    assert "the report on disk is not the audited report" in capsys.readouterr().err


def test_record_only_verifies_the_record_and_still_reports_the_drift(
        science, monkeypatch, capsys):
    """Mutation: drop the drift line under --record-only -> red."""
    receipt = _mint(science, monkeypatch)
    _flip_byte(receipt.parent / "report.md")
    capsys.readouterr()
    assert cli.main(["verify", str(receipt), "--record-only"]) == 0
    out = capsys.readouterr().out
    assert "WORKING TREE DRIFTED  " in out and "--record-only" in out
    assert "DRY RUN" in out


def test_a_drifted_report_refusal_is_one_json_document(science, monkeypatch, capsys):
    receipt = _mint(science, monkeypatch)
    _flip_byte(receipt.parent / "report.md")
    capsys.readouterr()
    assert cli.main(["--json", "verify", str(receipt)]) == 21
    doc = json.loads(capsys.readouterr().out)
    assert doc["exit_code"] == 21
    assert doc["drifted"] == [(receipt.parent / "report.md")
                              .relative_to(science).as_posix()]


def test_a_drifted_reproduction_sidecar_is_refused(science, monkeypatch, capsys):
    """The reproduction sidecar is the other cycle file whose digest the
    receipt carries (`reproduction.bundle_sha256`, over its canonical JSON).

    Mutation: remove `reproduction.json` from `_BOUND_CYCLE_FILES` -> 0, red."""
    (science / "experiments" / "demo" / "requirements.txt").write_text("numpy==1.26.4\n")
    receipt = _mint(science, monkeypatch)
    assert json.loads(receipt.read_text()).get("reproduction")
    sidecar = receipt.parent / "reproduction.json"
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 0
    assert "reproduction.json" in capsys.readouterr().out    # checked and matching
    bundle = json.loads(sidecar.read_text())
    bundle["rerun"]["restore"] = "pip install whatever"
    sidecar.write_text(json.dumps(bundle, indent=2))
    assert cli.main(["verify", str(receipt)]) == 21
    assert "reproduction bundle on disk" in capsys.readouterr().err


def test_reformatting_the_sidecar_is_not_drift(science, monkeypatch, capsys):
    """The digest is over canonical JSON, so whitespace is not content."""
    (science / "experiments" / "demo" / "requirements.txt").write_text("numpy==1.26.4\n")
    receipt = _mint(science, monkeypatch)
    sidecar = receipt.parent / "reproduction.json"
    sidecar.write_text(json.dumps(json.loads(sidecar.read_text())))
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 0


def test_a_report_not_on_disk_is_reported_not_refused(science, monkeypatch, capsys):
    """A checkout without the cycle file shows nobody a wrong text; the record
    (read at report_commit) is what verified, and the line says so."""
    receipt = _mint(science, monkeypatch)
    (receipt.parent / "report.md").unlink()
    capsys.readouterr()
    assert cli.main(["verify", str(receipt)]) == 0
    assert "WORKING TREE NOT ON DISK" in capsys.readouterr().out
