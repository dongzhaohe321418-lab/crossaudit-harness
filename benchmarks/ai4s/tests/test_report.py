"""RESULTS.md is bound to numbers.json: every number in its prose is a formatted value.

    PYTHONPATH=src python -m pytest -q benchmarks/ai4s/tests/test_report.py

The report is rendered from ``numbers.json`` only. These tests check that the
``<!-- numbers: sha -->`` comment names the exact file it came from, that every
number in the prose (tables included; code blocks, inline code, identifiers such
as ``D07`` / ``CA-PHYS-001`` and section references excluded) is ``report.fmt``
applied to some numeric value in that file, and that the H1/H2 sentences and the
coverage status follow the recorded booleans. Honest boundary: binding a number
to *some* value in numbers.json does not prove it sits next to the right label;
the label checks below cover the claims and the primary outcome only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
AI4S = TESTS.parent
sys.path.insert(0, str(AI4S))
sys.path.insert(0, str(TESTS))

import report as rp  # noqa: E402
import run_checks as rc  # noqa: E402
import score as sc  # noqa: E402
from _synth import write_two_profile_run  # noqa: E402

FIXTURE = TESTS / "fixtures" / "mini_corpus"

_STRIP = [
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r"```.*?```", re.S),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"§\s*\d+(?:\.\d+)*"),
    re.compile(r"(?<![\w-])[A-Za-z][\w-]*\d[\w-]*"),
]
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?%?")


def prose_numbers(text: str) -> list[str]:
    for pattern in _STRIP:
        text = pattern.sub(" ", text)
    return _NUMBER.findall(text)


def numeric_leaves(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from numeric_leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from numeric_leaves(v)


def allowed_strings(numbers: dict) -> set[str]:
    return {rp.fmt(v, s) for v in numeric_leaves(numbers) for s in rp.STYLES}


def _render(run_dir: Path, **score_kwargs) -> tuple[str, dict]:
    sc.write_numbers(run_dir, sc.score(run_dir, **score_kwargs))
    raw = (run_dir / "numbers.json").read_bytes()
    text = rp.render_file(run_dir)
    assert f"<!-- numbers: {hashlib.sha256(raw).hexdigest()} -->" in text
    return text, json.loads(raw)


def _assert_bound(text: str, numbers: dict):
    allowed = allowed_strings(numbers)
    found = prose_numbers(text)
    assert found, "the report quotes no numbers at all"
    stray = sorted({x for x in found if x not in allowed})
    assert not stray, f"numbers in RESULTS.md prose not in numbers.json: {stray}"


def test_formatter_styles():
    assert rp.fmt(0.6666, "p") == "0.667"
    assert rp.fmt(0.6666, "pct") == "66.7%"
    assert rp.fmt(0.95, "pct0") == "95%"
    assert rp.fmt(12, "int") == "12"
    assert rp.fmt(3.034, "ms") == "3.03"
    assert rp.fmt(2.5) == "2.5" and rp.fmt(2000) == "2000"
    assert rp.fmt(None, "p") == "n/a"


def test_prose_extractor_skips_identifiers():
    text = "D07 and `CA-PHYS-001` and H1 and §6 give 0.667 and 12 and 4.5%"
    assert prose_numbers(text) == ["0.667", "12", "4.5%"]


def test_fixture_report_is_bound_to_numbers(tmp_path):
    out = tmp_path / "run"
    rc.run(FIXTURE, ["science", "science-ai4s"], out, repeat=1)
    text, numbers = _render(out)
    _assert_bound(text, numbers)
    h1 = numbers["claims"]["H1"]
    assert ("H1 holds on this corpus" in text) == bool(h1["holds"])
    assert "H1 does not hold on this corpus" in text
    if "science-ai4s" in numbers["profiles"]["unknown"]:
        assert "H2 cannot be decided" in text
        assert "`science-ai4s` did not resolve" in text
    else:                                   # the pack has landed in this tree
        h2 = numbers["claims"]["H2"]
        assert ("H2 holds on this corpus" in text) == bool(h2["holds"])


def test_two_profile_report_is_bound_and_states_the_contrast(tmp_path):
    text, numbers = _render(write_two_profile_run(tmp_path / "run"))
    _assert_bound(text, numbers)
    p = numbers["primary"]
    assert (f"**{rp.fmt(p['delta'], 'p')}**, 95% cluster-bootstrap percentile interval "
            f"[{rp.fmt(p['ci_low'], 'p')}, {rp.fmt(p['ci_high'], 'p')}]") in text
    assert "H2 does not hold on this corpus" in text
    h2 = numbers["claims"]["H2"]
    assert h2["ci_low"] == p["ci_low"]
    above = "is" if h2["ci_low_above_zero"] else "is not"
    assert (f"the bootstrap interval's lower bound {rp.fmt(p['ci_low'], 'p')} {above} "
            "above 0.") in text
    assert "Coverage status: calibrated" in text
    assert "the calibration does not transfer" in text      # 12 templates, not 60


def test_uncalibrated_interval_is_printed(tmp_path):
    text, numbers = _render(write_two_profile_run(tmp_path / "run"),
                            coverage_path=tmp_path / "none.json")
    assert numbers["primary"]["coverage_checked"] is False
    assert "**uncalibrated**" in text
    _assert_bound(text, numbers)
