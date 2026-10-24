"""D171 R1: the README's export-then-verify pair works, and `verify` refuses
what the README says it refuses.

Each test runs the product's own commands against a real project: an offline
`crossaudit audit --write-ledger` mints a signed receipt (the replay provider is
never reached offline, so no fixture reply is needed), and the commands under
test then run exactly as a person types them. The mutation each guard catches is
named in its docstring (CONTRIBUTING, D10).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.cli import main as cli
from crossaudit.crypto import dsse, keys
from crossaudit.receipt.schema import digest
from crossaudit.receipt.sign import SIDECAR, verify_receipt

from .conftest import GOOD_RESULTS, write_increment

SRC = Path(__file__).resolve().parents[1] / "src"


def _mint(science: Path, monkeypatch) -> Path:
    """One offline audit with the ledger written; returns the receipt path."""
    write_increment(science, GOOD_RESULTS, "Fine.", "clean increment")
    monkeypatch.chdir(science)
    cli.main(["audit", "--offline", "--write-ledger", "--scope", "experiments"])
    # Directories only: since D176 ruling 43 an escalating audit (DCL_ONLY)
    # also writes cycles/rulings.jsonl, the escalation's committed row.
    (cycle,) = sorted(p for p in (science / "cycles").iterdir() if p.is_dir())
    assert (cycle / SIDECAR).is_file(), "the audit did not sign its receipt"
    return cycle / "receipt.json"


def _shell(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a README line through a real shell, `crossaudit` being this tree."""
    launcher = (f'{sys.executable} -c "import sys; from crossaudit.cli.main '
                f'import main; sys.exit(main())"')
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run(command.replace("crossaudit ", launcher + " ", 1),
                          shell=True, cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=120)


def _verify(receipt: Path, *extra: str) -> int:
    return cli.main(["verify", str(receipt), *extra])


def _corrupt_signature(receipt: Path) -> None:
    sidecar = receipt.parent / SIDECAR
    env = json.loads(sidecar.read_text())
    raw = bytearray(base64.b64decode(env["signatures"][0]["sig"]))
    raw[0] ^= 0x01
    env["signatures"][0]["sig"] = base64.b64encode(bytes(raw)).decode()
    sidecar.write_text(json.dumps(env))


def test_the_readme_export_then_verify_pair_succeeds(science, monkeypatch):
    """The two README lines, verbatim, through a shell redirection.

    Mutation: print `export-pubkey`'s `KEY <id>` line on stdout again -> the
    redirected file carries it, test red (and with the old PEM reader, verify
    died with a binascii traceback, exit 1)."""
    receipt = _mint(science, monkeypatch)
    rel = receipt.relative_to(science).as_posix()
    exported = _shell("crossaudit export-pubkey > project.pem", science)
    assert exported.returncode == 0, exported.stderr
    pem = (science / "project.pem").read_text()
    assert pem.startswith("-----BEGIN PUBLIC KEY-----\n")
    assert pem.endswith("-----END PUBLIC KEY-----\n")
    assert "KEY " not in pem                    # the id went to stderr
    assert exported.stderr.startswith("KEY ")
    verified = _shell(f"crossaudit verify {rel} --pubkey project.pem", science)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "Traceback" not in verified.stderr
    assert "\nSIGNED  " in verified.stdout


def test_a_file_from_the_old_export_still_verifies(science, monkeypatch, capsys):
    """Files people already wrote with the old export carry `KEY <id>` above
    the block. Text outside the block is ignored, as OpenSSL ignores it.

    Mutation: parse every non-dash line as base64 (the old reader) -> 20."""
    receipt = _mint(science, monkeypatch)
    pub, keyid = keys.public_key(cli.load())
    old = science / "old.pem"
    old.write_text(f"KEY {keyid}\n{keys.public_key_pem(pub)}")
    capsys.readouterr()
    assert _verify(receipt, "--pubkey", str(old)) == 0
    assert "\nSIGNED  " in capsys.readouterr().out


@pytest.mark.parametrize("content", [
    "not a key at all\n",
    "-----BEGIN PUBLIC KEY-----\n!!!!\n-----END PUBLIC KEY-----\n",
    # valid base64, valid PEM framing, but an RSA-sized blob, not Ed25519
    "-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(b"\x30" * 70).decode()
    + "\n-----END PUBLIC KEY-----\n",
    "",
])
def test_a_key_file_that_does_not_parse_is_a_config_refusal(
        science, monkeypatch, capsys, content):
    """Mutation: drop the ValueError -> ConfigDenial translation in
    `_pinned_public_key` -> a traceback escapes main() and the test errors."""
    receipt = _mint(science, monkeypatch)
    bad = science / "bad.pem"
    bad.write_text(content)
    capsys.readouterr()
    assert _verify(receipt, "--pubkey", str(bad)) == 20
    err = capsys.readouterr().err
    assert str(bad) in err and "Traceback" not in err


def test_a_missing_key_file_is_a_config_refusal(science, monkeypatch, capsys):
    receipt = _mint(science, monkeypatch)
    capsys.readouterr()
    assert _verify(receipt, "--pubkey", str(science / "nope.pem")) == 20
    assert "nope.pem" in capsys.readouterr().err


def test_a_corrupted_signature_is_refused_in_dry_run(science, monkeypatch, capsys):
    """README: "a present-but-invalid signature is refused" — in dry run too.

    Mutation: return "" from `_signature_refusal` for a signed-but-invalid
    sidecar (the pre-D171 dry run) -> exit 0, test red."""
    receipt = _mint(science, monkeypatch)
    _corrupt_signature(receipt)
    capsys.readouterr()
    assert _verify(receipt) == 21
    captured = capsys.readouterr()
    assert "SIGNATURE INVALID" in captured.out
    assert "signature does not verify" in captured.err


def test_a_corrupted_signature_is_refused_under_admit(science, monkeypatch, capsys):
    """The signature refuses before admission is attempted. (This offline
    receipt is DCL_ONLY, which admission would refuse anyway, so the guard is
    the sentence, not the exit code.) Mutation: as above -> the refusal names
    the verdict instead of the signature, test red."""
    receipt = _mint(science, monkeypatch)
    _corrupt_signature(receipt)
    capsys.readouterr()
    assert _verify(receipt, "--admit") == 21
    assert "signature does not verify" in capsys.readouterr().err


def test_a_corrupted_signature_refusal_is_one_json_document(
        science, monkeypatch, capsys):
    receipt = _mint(science, monkeypatch)
    _corrupt_signature(receipt)
    capsys.readouterr()
    assert cli.main(["--json", "verify", str(receipt)]) == 21
    doc = json.loads(capsys.readouterr().out)      # exactly one document
    assert doc["exit_code"] == 21 and doc["signed"] is True


def test_a_missing_sidecar_is_refused_only_when_a_key_is_pinned(
        science, monkeypatch, capsys):
    """Pinning a key asks for a signature by it; without a pin, UNSIGNED stays
    informational (every pre-A1 receipt is unsigned).

    Mutation: drop the `pinned and not signed` branch -> the pinned run exits
    0, test red. Mutation: refuse every unsigned receipt -> the unpinned run
    exits 21, test red."""
    receipt = _mint(science, monkeypatch)
    pem = science / "project.pem"
    pub, _ = keys.public_key(cli.load())
    pem.write_text(keys.public_key_pem(pub))
    (receipt.parent / SIDECAR).unlink()
    capsys.readouterr()
    assert _verify(receipt) == 0
    assert "\nUNSIGNED  " in capsys.readouterr().out
    assert _verify(receipt, "--pubkey", str(pem)) == 21
    captured = capsys.readouterr()
    assert "UNSIGNED" in captured.out and "pinned" in captured.err


def test_the_signed_predicate_carries_the_real_verdict_and_report_digest(
        science, monkeypatch):
    """Mutation: read `receipt["verdict"]` / `subject["report_sha256"]` again
    (the pre-D171 paths, absent from every minted receipt) -> both empty."""
    receipt_path = _mint(science, monkeypatch)
    receipt = json.loads(receipt_path.read_text())
    env = json.loads((receipt_path.parent / SIDECAR).read_text())
    predicate = dsse.payload_json(env)["predicate"]
    assert predicate["verdict"] == receipt["audit"]["verdict"] != ""
    assert predicate["report_sha256"] == receipt["ledger"]["report_sha256"] != ""


def _old_predicate(receipt: dict) -> dict:
    """`receipt/sign.py:_predicate` exactly as it stood before D171."""
    cycle = receipt.get("cycle", {}) if isinstance(receipt, dict) else {}
    subject = receipt.get("subject", {}) if isinstance(receipt, dict) else {}
    verifier = receipt.get("verifier", {}) if isinstance(receipt, dict) else {}
    tool_ev = receipt.get("tool_evidence", {}) if isinstance(receipt, dict) else {}
    return {
        "cycle_id": cycle.get("cycle_id", ""),
        "round": cycle.get("round"),
        "verdict": receipt.get("verdict", ""),
        "report_sha256": subject.get("report_sha256", ""),
        "evidence_root": {"ledger_head": tool_ev.get("ledger_head", ""),
                          "entries": tool_ev.get("entries")},
        "verifier_code_digest": verifier.get("code_digest_sha256", ""),
    }


def test_an_envelope_minted_by_the_old_predicate_still_verifies(
        science, monkeypatch, capsys):
    """Additive: verification binds the subject digest, not the predicate, so
    a receipt signed before D171 (empty verdict/report fields) verifies.

    Mutation: make `verify_receipt` also require the predicate's verdict to
    equal the receipt's -> SIGNATURE INVALID, exit 21, test red."""
    receipt_path = _mint(science, monkeypatch)
    receipt = json.loads(receipt_path.read_text())
    seed, pub, _kid = keys.load_or_create(cli.load())
    old = _old_predicate(receipt)
    assert old["verdict"] == "" and old["report_sha256"] == ""
    envelope = dsse.sign(dsse.statement(receipt_digest=digest(receipt),
                                        predicate=old), seed, pub)
    (receipt_path.parent / SIDECAR).write_text(json.dumps(envelope))
    assert verify_receipt(receipt, receipt_path.parent,
                          expected_pubkey=pub)["verified"] is True
    pem = science / "project.pem"
    pem.write_text(keys.public_key_pem(pub))
    capsys.readouterr()
    assert _verify(receipt_path, "--pubkey", str(pem)) == 0
    assert "\nSIGNED  " in capsys.readouterr().out
