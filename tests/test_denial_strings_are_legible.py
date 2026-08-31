"""The refusal a person meets must be one they can read.

The fail-closed denial from the audit core — a corrupt evidence ledger refuses
to produce a receipt — worked perfectly on the frozen build and was illegible to
a Chinese user. A safety mechanism that functions and cannot be read by its
subject is worse than one that fails loudly: the person proceeds confidently
past a warning they could not understand.

These strings are the least translated in the product, and the reason is
structural: nobody walks the failure paths in another language. Setup is
translated because everyone runs setup. A denial that fires when an evidence
ledger is corrupt is seen by nobody — until it is the only thing between a
person and a forged receipt.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.console import page as page_mod

HARNESS = Path(__file__).parent / "harness"
SRC = Path(page_mod.__file__).parent.parent
DENIAL_TYPES = {"Denial", "ConfigDenial", "IntegrityDenial", "ProviderDenial"}


def _denial_messages() -> list[tuple[str, int, str]]:
    """Every message handed to a Denial constructor, from the shipped source.

    Interpolated messages are probed with a placeholder standing in for the
    substituted part, because that is the shape a person actually reads.
    """
    found: list[tuple[str, int, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name not in DENIAL_TYPES or not node.args:
                continue
            first = node.args[0]
            rel = str(path.relative_to(SRC))
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append((rel, node.lineno, first.value))
            elif isinstance(first, ast.JoinedStr):
                rendered = "".join(
                    v.value if isinstance(v, ast.Constant) else "X"
                    for v in first.values)
                found.append((rel, node.lineno, rendered))
    return found


def _translate(values: list[str], tmp_path: Path) -> dict:
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"), str(SRC.parent.parent)],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_fail_closed_evidence_denial_is_legible_in_chinese(tmp_path):
    """The specific sentence: the audit core's own refusal.

    It carries the verifier's reason after a colon, so it is matched as a
    pattern — an exact entry would never match what a person sees, which is the
    same trap as a fixed string carrying a count.
    """
    sentence = ("evidence ledger cannot be shown to the Auditor: "
                "entry 0 digest mismatch (content tampered)")
    rendered = _translate([sentence], tmp_path)[sentence]

    assert re.search(r"[一-鿿]", rendered), (
        f"the fail-closed denial reaches a Chinese reader in English: {rendered!r}")
    assert "entry 0 digest mismatch" in rendered, (
        "the verifier's own reason was dropped instead of carried through")


def test_the_denial_still_exists_where_the_translation_expects_it():
    """A pattern for a sentence nobody raises is a catalogue entry that rots."""
    routing = (SRC / "broker/routing.py").read_text()
    assert "evidence ledger cannot be shown to the Auditor" in routing, (
        "the denial moved; its catalogue pattern now matches nothing")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_denial_catalogue_gap_is_measured_not_guessed(tmp_path):
    """The COUNT, recorded as a test so it cannot drift silently upward.

    This does not assert the class is translated — it is not, by a long way. It
    pins the measurement so that a change making it worse has to change this
    number deliberately, and so the scope of the work stays visible.
    """
    messages = _denial_messages()
    assert len(messages) > 400, f"the denial reader has drifted: {len(messages)}"
    distinct = sorted({m for _f, _l, m in messages if m.strip()})
    rendered = _translate(distinct, tmp_path)
    covered = [m for m in distinct if re.search(r"[一-鿿]", rendered[m])]

    # A floor, not a total: this counts the four Denial constructors only.
    assert len(covered) >= 52, (
        f"denial catalogue coverage fell to {len(covered)}/{len(distinct)}; it "
        f"was 52 when measured. Refusals are the strings that most need "
        f"translating, not the least.")
