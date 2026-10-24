"""An input the auditor never sees can never reach PASS (D169, F2; I8).

Before D169 a file that was not UTF-8 and was not a PDF/DOCX the extractor
recovers reached the prompt as ``<binary, N bytes, not shown>`` without
setting ``bounded``, and `check_parseable` skipped it. The reproduction --
a UTF-16 ``results.csv`` and an ``.xlsx`` -- went through the `general`
profile with 0 hard failures and the model's PASS stood.

Every audit here is the real path: the files are committed, `materialise`
reads them, `run_audit` runs the checks, builds the prompt and replays a
recorded PASS for that exact prompt, so the ladder -- not the model -- has to
refuse.

Mutations (D10), run by hand:
  * delete the ``elif built.unseen`` branch in auditor/run.py -> the
    ESCALATE tests read PASS;
  * restore the silent ``continue`` in dcl/neutral.check_parseable -> every
    row of the encoding sweep and the general-profile test go red;
  * make `_not_shown` return False -> the sweep's `unseen_files` / bounded
    assertions and the ESCALATE tests go red.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crossaudit.auditor import prompt as pm
from crossaudit.auditor import run_audit
from crossaudit.config import load
from crossaudit.controller import StateStore
from crossaudit.dcl import run_checks
from crossaudit.dcl.neutral import TEXT_SUFFIXES, check_parseable
from crossaudit.gitio import materialise, parent
from crossaudit.providers import replay
from crossaudit.scaffold import GENERAL_CHECKS

from .conftest import PASS_REPLY, git

UTF16_CSV = "x,y\n1,2\nä,3\n".encode("utf-16")
XLSX = b"PK..\xff"
REPRO = {"experiments/demo/results.csv": UTF16_CSV,
         "experiments/demo/model.xlsx": XLSX}


def _project(science: Path, checks: list[str]):
    yml = science / "crossaudit.yml"
    text = yml.read_text().replace("checks: [schema, units, convergence, provenance]",
                                   f"checks: [{', '.join(checks)}]")
    assert f"checks: [{', '.join(checks)}]" in text
    yml.write_text(text)
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "checks", cwd=science)
    return load(yml)


def _commit(science: Path, files: dict[str, bytes]) -> str:
    for rel, data in files.items():
        target = science / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "increment", cwd=science)
    return git("rev-parse", "HEAD", cwd=science)


def _audit_with_model_pass(cfg, sha: str, transcripts: Path):
    files, notes = materialise(cfg.root, sha, "experiments")
    const = (cfg.root / cfg.constitution).read_text()
    cc = git("log", "-1", "--format=%H", "--", cfg.constitution, cwd=cfg.root)
    dcl = run_checks(files, cfg.checks, notes).as_dict()
    prompt, _bounded, _sha = pm.build(const, cc, dcl, files)
    replay.record(transcripts, system=pm.SYSTEM, prompt=prompt,
                  text=json.dumps(PASS_REPLY))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha))
    return files, run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files,
                            notes=notes, constitution=const, constitution_commit=cc)


# ------------------------------------------------------------ the reproduction
def test_the_reproduction_under_the_general_profile_is_never_pass(science, transcripts):
    """The exact files from the report, `general` profile, model says PASS.

    The UTF-16 CSV is now a CA-FILE-001 BLOCKER, and a deterministic hard
    failure dominates the ladder, so the verdict is BLOCKED -- not ESCALATE.
    Both files are still named in the report as not shown to the auditor.
    """
    cfg = _project(science, GENERAL_CHECKS)
    sha = _commit(science, REPRO)
    files, outcome = _audit_with_model_pass(cfg, sha, transcripts)

    assert set(REPRO) <= set(files)
    assert outcome.model_reply and outcome.model_reply["verdict"] == "PASS"
    assert outcome.verdict == "BLOCKED"
    blockers = [f for f in outcome.dcl["findings"] if f["severity"] == "BLOCKER"]
    assert [(f["artifact"], f["implementation_code"]) for f in blockers] == [
        ("experiments/demo/results.csv", "CA-FILE-001")]
    assert "## Files the auditor was not shown" in outcome.report
    for path in REPRO:
        assert f"- `{path}`" in outcome.report


def test_the_reproduction_without_parseable_escalates_and_names_the_files(
        science, transcripts):
    """With no deterministic check reading the CSV, the ladder alone stops it."""
    cfg = _project(science, ["declared", "internal", "complete"])
    sha = _commit(science, REPRO)
    _files, outcome = _audit_with_model_pass(cfg, sha, transcripts)

    assert outcome.dcl["total_hard_failures"] == 0
    assert outcome.model_reply and outcome.model_reply["verdict"] == "PASS"
    assert outcome.verdict == "ESCALATE"
    assert outcome.integrity == "INPUT_NOT_SHOWN"
    assert outcome.authority["rationale"][0] == (
        "A file was not shown to the auditor because it is not readable text, "
        "so a person owns this round.")
    section = outcome.report.split("## Files the auditor was not shown", 1)[1]
    section = section.split("## Deterministic findings", 1)[0]
    assert sorted(line for line in section.splitlines() if line.startswith("- ")) == [
        "- `experiments/demo/model.xlsx`", "- `experiments/demo/results.csv`"]


def test_a_binary_beside_readable_work_escalates_under_the_general_profile(
        science, transcripts):
    """A non-text suffix (no CA-FILE-001) next to clean UTF-8 work."""
    cfg = _project(science, GENERAL_CHECKS)
    sha = _commit(science, {"experiments/demo/SUMMARY.md": b"# Result\n\nAll fine.\n",
                            "experiments/demo/model.xlsx": XLSX})
    _files, outcome = _audit_with_model_pass(cfg, sha, transcripts)

    assert outcome.dcl["total_hard_failures"] == 0
    assert outcome.verdict == "ESCALATE" and outcome.integrity == "INPUT_NOT_SHOWN"
    assert "- `experiments/demo/model.xlsx`" in outcome.report
    assert "SUMMARY.md`" not in outcome.report.split("## Deterministic findings")[0]


def test_readable_work_alone_still_passes_and_its_report_is_unchanged(
        science, transcripts):
    """The twin: the same project with only UTF-8 files passes as before, and
    the report carries no unseen-files section."""
    cfg = _project(science, GENERAL_CHECKS)
    sha = _commit(science, {"experiments/demo/SUMMARY.md": b"# Result\n\nAll fine.\n"})
    _files, outcome = _audit_with_model_pass(cfg, sha, transcripts)

    assert outcome.verdict == "PASS"
    assert "not shown" not in outcome.report


# ------------------------------------------------------------ encoding sweep
ENCODINGS = {
    "utf-16": "name,value\nä,1\n".encode("utf-16"),
    "utf-16-le": "name,value\nä,1\n".encode("utf-16-le"),
    "latin-1": "name,value\ncaf\xe9,1\n".encode("latin-1"),
    "cp1252": "name,value\n€ price,1\n".encode("cp1252"),
    "raw-ff": b"name,value\n\xff,1\n",
}
SWEEP_SUFFIXES = (".json", ".yml", ".yaml", ".csv", ".md", ".txt", ".py", ".tex", ".rst")


def test_the_sweep_suffixes_are_text_suffixes():
    assert set(SWEEP_SUFFIXES) <= set(TEXT_SUFFIXES)


@pytest.mark.parametrize("suffix", sorted(set(TEXT_SUFFIXES)))
@pytest.mark.parametrize("encoding", sorted(ENCODINGS))
def test_a_text_suffix_that_is_not_utf8_blocks_and_is_unseen(suffix, encoding):
    data = ENCODINGS[encoding]
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    for path in (f"experiments/a/file{suffix}", f"experiments/a/FILE{suffix.upper()}"):
        files = {path: data}
        findings = check_parseable(files)
        assert [(f.severity, f.rule, f.artifact) for f in findings] == [
            ("BLOCKER", "CA-FILE-001", path)], (path, encoding)
        assert pm.unseen_files(files) == [path]
        _text, bounded = pm.render_increment(files)
        assert bounded is True
        built = pm.build_audit_prompt("rules", "c", {"findings": []}, files)
        assert built.unseen == (path,) and not built.overflow and built.bounded


@pytest.mark.parametrize("suffix", sorted(set(TEXT_SUFFIXES)))
def test_a_utf8_text_file_is_seen_and_not_blocked_for_its_encoding(suffix):
    path = f"experiments/a/file{suffix}"
    data = {".json": b'{"a": "\xc3\xa4"}', ".yml": b"a: \xc3\xa4\n",
            ".yaml": b"a: \xc3\xa4\n"}.get(suffix, "ä text\n".encode("utf-8"))
    files = {path: data}
    assert check_parseable(files) == []
    assert pm.unseen_files(files) == []
    assert pm.render_increment(files)[1] is False


@pytest.mark.parametrize("path", ["experiments/a/plot.png", "experiments/a/model.xlsx",
                                  "experiments/a/weights.npz", "experiments/a/blob"])
def test_a_binary_with_no_text_suffix_is_unseen_but_not_a_parse_blocker(path):
    files = {path: b"\x89PNG\r\n\x1a\n\xff\x00"}
    assert check_parseable(files) == []
    assert pm.unseen_files(files) == [path]
    assert pm.render_increment(files)[1] is True


def test_build_returns_the_same_bytes_as_before_for_readable_input():
    """In-bound inputs are byte-identical: build() is build_audit_prompt()."""
    files = {"experiments/a/SUMMARY.md": b"# ok\n"}
    prompt, bounded, sha = pm.build("rules", "c", {"findings": []}, files)
    built = pm.build_audit_prompt("rules", "c", {"findings": []}, files)
    assert (prompt, bounded, sha) == (built.prompt, False, built.sha256)
    assert built.unseen == () and not built.overflow


# ------------------------------------------------------------ documents
@pytest.mark.parametrize("format_name", ["pdf", "docx"])
def test_a_recovered_document_is_seen_and_still_passes(science, transcripts, format_name):
    """No regression: a PDF/DOCX the extractor recovers is shown, so it is
    neither unseen nor a parse blocker, and the round passes."""
    from crossaudit.document_export import (SOURCE_SUFFIX, export_instructions,
                                            render_export)

    cfg = _project(science, GENERAL_CHECKS)
    task = "Report" + export_instructions(format_name)
    relative = f"experiments/demo/final{SOURCE_SUFFIX}"
    (science / relative).parent.mkdir(parents=True, exist_ok=True)
    (science / relative).write_text("# Verified report\n\nAll fine.\n")
    final_relative = render_export(science, [relative], task)[0]
    (science / relative).unlink(missing_ok=True)
    data = (science / final_relative).read_bytes()
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    assert pm.unseen_files({final_relative: data}) == []
    git("add", "-A", cwd=science)
    git("commit", "-q", "-m", "final document", cwd=science)
    sha = git("rev-parse", "HEAD", cwd=science)
    files, outcome = _audit_with_model_pass(cfg, sha, transcripts)

    assert final_relative in files
    assert outcome.verdict == "PASS", outcome.report
    assert "not shown" not in outcome.report
