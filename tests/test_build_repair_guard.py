"""The build loop's repair screen, driven through run_loop (D148 slice D).

Round 1 commits an incomplete increment (no metadata), so the audit BLOCKS on
the deterministic tier and round 2 is a repair round. What that round may do,
what the auditor is told about it, and what is refused is the subject here.
Each test names its D10 mutation.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from crossaudit.config import RepairPolicy
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_ESCALATED

from .conftest import git

SUMMARY = "experiments/demo/SUMMARY.md"
CALC = "experiments/demo/calc.py"
CALC_OK = "def run():\n    return compute()\n"
CALC_DEFENSIVE = ("def run():\n    try:\n        return compute()\n"
                  "    except Exception:\n        pass\n")
CALC_FIXED = "def run():\n    return compute(strict=True)\n"
ROUND_ONE = {SUMMARY: "attempt one\n", CALC: CALC_OK}
PNG = "\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00"
CAUTIONS = (f"{CALC} adds a catch-all `except` that swallows every error",
            f"{CALC} adds an error handler that does nothing")


def _drive(cfg, science, monkeypatch, rounds, *, task="produce the experiment"):
    """Run the loop with a scripted generator; return (code, events, calls).

    Each generator call records what it was shown and what the tree looked
    like at that moment, so a rollback is asserted mid-run, not inferred.
    """
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    calls: list[dict] = []
    script = iter(rounds)

    def fake_generate(**kwargs):
        calc = science / CALC
        calls.append({
            "findings": kwargs.get("findings", ""),
            "calc": calc.read_text() if calc.exists() else None,
            "staged": git("diff", "--cached", "--name-only", cwd=science),
        })
        return generator_mod.Work(summary="revision", files=next(script))

    # A route-bearing completer, so commits carry the CrossAudit-Generator
    # trailer that marks rendered documents as CrossAudit's own (re-render).
    from types import SimpleNamespace
    completer = SimpleNamespace(last_route={"vendor": "openai", "provider": "fake",
                                            "model": "scripted", "fallback": False})
    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: completer)
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)
    events = []
    code = build_mod.run_loop(cfg, task, on_event=events.append)
    return code, events, calls


def _kinds(events) -> list[str]:
    return [e.kind for e in events]


def _cycle(cfg) -> dict:
    cycles = StateStore(cfg.root / cfg.state_dir / "state.json").snapshot()["cycles"]
    assert len(cycles) == 1
    return next(iter(cycles.values()))


def _ledger_notes(cfg) -> list[str]:
    notes: list[str] = []
    for path in (cfg.root / cfg.ledger_dir).glob("*/checks.json"):
        notes.extend(json.loads(path.read_text()).get("notes", []))
    return notes


def _ledger_reports(cfg) -> str:
    return "\n".join(p.read_text() for p in (cfg.root / cfg.ledger_dir).glob("*/report.md"))


# ------------------------------------------------------------ caution mode

def test_a_defensive_repair_is_committed_with_a_caution_the_auditor_sees(
        science, cfg, transcripts, monkeypatch):
    """Default mode. Mutation: comment out the guard call -> no repair_caution
    event; drop the extra_notes line in main.py -> the note never reaches
    the ledger's checks.json (the auditor's dcl input)."""
    code, events, calls = _drive(
        cfg, science, monkeypatch, [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])

    kinds = _kinds(events)
    assert "repair_refused" not in kinds and kinds.count("repair_caution") == 1
    caution = next(e for e in events if e.kind == "repair_caution")
    assert caution.detail == "; ".join(CAUTIONS)
    assert "except Exception" in git("log", "-p", cwd=science)       # committed, not rolled back
    # The auditor was told, through the deterministic notes it reads.
    for sentence in CAUTIONS:
        assert f"revision caution: {sentence}" in _ledger_notes(cfg)
    # ...and the note is a note, not an input-bound blocker (CA-META-004).
    assert "CA-META-004" not in _ledger_reports(cfg)
    # Round 3 carried no caution of its own: the note is per revision.
    assert _ledger_notes(cfg).count(f"revision caution: {CAUTIONS[0]}") == 1
    assert code == EXIT_ESCALATED and _cycle(cfg).get("escalation_cause") != "repair_refused"


def test_a_docs_only_revision_using_the_word_fallback_has_no_caution(
        science, cfg, transcripts, monkeypatch):
    """D121. Mutation: classify .md as code -> a caution appears."""
    prose = "We skip the retry and fallback to the plan.\n"
    code, events, calls = _drive(
        cfg, science, monkeypatch, [ROUND_ONE, {SUMMARY: prose}, {SUMMARY: "attempt three\n"}])
    assert not {"repair_refused", "repair_caution"} & set(_kinds(events))
    assert _ledger_notes(cfg) == [] and prose.strip() in git("log", "-p", cwd=science)


def test_an_honest_small_fix_passes_with_no_caution(science, cfg, transcripts, monkeypatch):
    code, events, calls = _drive(
        cfg, science, monkeypatch, [ROUND_ONE, {CALC: CALC_FIXED}, {SUMMARY: "attempt three\n"}])
    assert not {"repair_refused", "repair_caution"} & set(_kinds(events))
    assert "strict=True" in git("log", "-p", cwd=science)
    assert "revision (round 2)" in git("log", "--format=%s", cwd=science)


def test_repair_enabled_false_disables_the_screen(science, cfg, transcripts, monkeypatch):
    """Mutation: ignore cfg.repair.enabled -> a caution appears."""
    off = dataclasses.replace(cfg, repair=RepairPolicy(enabled=False))
    code, events, calls = _drive(
        off, science, monkeypatch, [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])
    assert not {"repair_refused", "repair_caution"} & set(_kinds(events))
    assert _ledger_notes(off) == []


def test_round_one_is_never_a_repair_round(science, cfg, transcripts, monkeypatch):
    """Mutation: initialise repair_round = True -> a round-1 caution."""
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [{SUMMARY: "attempt one\n", CALC: CALC_DEFENSIVE},
         {SUMMARY: "attempt two\n"}, {SUMMARY: "attempt three\n"}])
    assert not {"repair_refused", "repair_caution"} & set(_kinds(events))


# -------------------------------------------------------- hard refusals

def test_a_model_written_binary_is_refused_rolled_back_and_the_findings_kept(
        science, cfg, transcripts, monkeypatch):
    """Mutation: drop the binary screen -> the PNG lands in history; replace
    `findings` instead of appending -> the DCL cause vanishes from round 3's
    prompt."""
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {"experiments/demo/fig.png": PNG, CALC: CALC_FIXED}, {CALC: CALC_FIXED}])

    assert _kinds(events).count("repair_refused") == 1
    refused = next(e for e in events if e.kind == "repair_refused")
    assert refused.detail == ("experiments/demo/fig.png is a binary file written directly by "
                              "the generator, which cannot be reviewed line by line")
    # Files and index were rolled back before the generator was asked again.
    assert calls[2]["calc"] == CALC_OK and calls[2]["staged"] == ""
    assert not (science / "experiments/demo/fig.png").exists()
    # Round 3's prompt: the audit's own findings first, then the refusal.
    third = calls[2]["findings"]
    assert "metadata.yml" in third                                   # the DCL cause survives
    assert third.index("metadata.yml") < third.index("[BLOCKER] The repair guard refused")
    assert "- experiments/demo/fig.png is a binary file" in third
    assert "The previous attempt was rolled back." in third
    assert "fig.png" not in git("log", "--name-only", cwd=science)
    assert "strict=True" in git("log", "-p", cwd=science)            # the honest retry committed


def test_a_second_refusal_stops_the_run_with_the_repair_refused_cause(
        science, cfg, transcripts, monkeypatch):
    """One free retry, then a clear stop. max_rounds 5 proves the stop is the
    second refusal, not the budget. Mutation: never set repair_refusal_used
    -> the loop burns all five rounds."""
    five = dataclasses.replace(cfg, max_rounds=5)
    bad = {"experiments/demo/fig.png": PNG}
    code, events, calls = _drive(five, science, monkeypatch,
                                 [ROUND_ONE, bad, bad, {CALC: CALC_FIXED}, {CALC: CALC_FIXED}])
    assert code == EXIT_ESCALATED and len(calls) == 3
    assert _kinds(events).count("repair_refused") == 2
    cycle = _cycle(five)
    assert cycle["status"] == "ESCALATED" and cycle["escalation_kind"] == "audit"
    assert cycle["escalation_cause"] == "repair_refused"
    assert cycle["escalation_reason"].startswith(
        "the automatic repair was refused in round 3 because experiments/demo/fig.png is a binary")
    assert (science / CALC).read_text() == CALC_OK
    assert git("diff", "--cached", "--name-only", cwd=science) == ""


def test_a_file_outside_the_audited_directories_is_refused(
        science, cfg, transcripts, monkeypatch):
    """gen_mod.apply already confines the generator to scope.dirs, so the
    screen is reached only by something else staging a stray path; that is
    simulated by wrapping _stage_generated. Mutation: drop the scope screen
    -> the stray file is committed in round 2."""
    from crossaudit.cli import build as build_mod

    scoped = dataclasses.replace(cfg, scope_dirs=["experiments"])
    (science / "notes").mkdir()
    (science / "notes/stray.md").write_text("not part of the increment\n")
    real_stage = build_mod._stage_generated
    seen = {"n": 0}

    def staging_a_stray(cfg_, written):
        seen["n"] += 1
        if seen["n"] >= 2:
            git("add", "--", "notes/stray.md", cwd=science)
        return real_stage(cfg_, written)

    monkeypatch.setattr(build_mod, "_stage_generated", staging_a_stray)
    code, events, calls = _drive(scoped, science, monkeypatch,
                                 [ROUND_ONE, {CALC: CALC_FIXED}, {CALC: CALC_FIXED}])
    refused = [e for e in events if e.kind == "repair_refused"]
    assert refused and refused[0].detail == (
        "notes/stray.md is outside the audited directories (experiments). Only files inside "
        "them may change; if the fix needs another file, say so in `notes`.")
    assert "stray" not in git("log", "--name-only", cwd=science)
    assert _cycle(scoped)["escalation_cause"] == "repair_refused"


# ------------------------------------------------------------ refuse mode

def test_refuse_mode_rolls_back_a_defensive_repair_and_keeps_the_findings(
        science, cfg, transcripts, monkeypatch):
    """Mutation: ignore cfg.repair.mode -> committed with a caution instead."""
    strict = dataclasses.replace(cfg, repair=RepairPolicy(mode="refuse"))
    code, events, calls = _drive(
        strict, science, monkeypatch, [ROUND_ONE, {CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])
    refused = [e for e in events if e.kind == "repair_refused"]
    assert len(refused) == 1 and refused[0].detail == "; ".join(CAUTIONS)
    assert "repair_caution" not in _kinds(events)
    assert calls[2]["calc"] == CALC_OK and calls[2]["staged"] == ""
    assert "metadata.yml" in calls[2]["findings"] and f"- {CAUTIONS[0]}" in calls[2]["findings"]
    assert "except Exception" not in git("log", "-p", cwd=science)
    assert "strict=True" in git("log", "-p", cwd=science)


# ------------------------------------------- surviving mutations M9 / M12

def test_a_pdf_from_the_local_document_export_is_not_a_model_written_binary(
        science, cfg, transcripts, monkeypatch):
    """M9. The export task makes CrossAudit render a PDF from the model's
    Markdown source; that binary is in round 2's diff and must pass. A
    rendered-only increment has no failing deterministic check, so the audit
    is faked as BLOCKED (the pattern test_document_export uses) to make round
    2 a repair round. Mutation: `locally_rendered = set()` in run_loop ->
    refused."""
    from crossaudit.cli import build as build_mod
    from crossaudit.document_export import SOURCE_SUFFIX, export_instructions
    from crossaudit.errors import EXIT_BLOCKED

    from .test_document_export import SOURCE

    def fake_audit(_args):
        sha = git("rev-parse", "HEAD", cwd=science)
        store = StateStore(cfg.root / cfg.state_dir / "state.json")
        cycle = store.open_or_advance(cfg.science_repo, sha, None)
        store.record_verdict(cycle["cycle_id"], sha, "BLOCKED", "receipt", cfg.max_rounds)
        return EXIT_BLOCKED

    monkeypatch.setattr(build_mod, "cmd_run", fake_audit)
    scoped = dataclasses.replace(cfg, scope_dirs=["experiments"])
    task = "Write a verified report" + export_instructions("pdf")
    source = f"experiments/report{SOURCE_SUFFIX}"
    code, events, calls = _drive(
        scoped, science, monkeypatch,
        [{source: SOURCE}, {source: SOURCE + "\n\nA second paragraph.\n"},
         {source: SOURCE + "\n\nA third paragraph.\n"}], task=task)
    assert "repair_refused" not in _kinds(events)
    names = git("log", "--format=%s", "--name-only", cwd=science)
    assert names.count("experiments/report.pdf") == 3 and "revision (round 2)" in names


def test_the_diff_size_cap_reports_unscreened_files_instead_of_hiding_them(
        science, cfg, transcripts, monkeypatch):
    """M12. With the cap lowered, a long SUMMARY.md sorts before calc.py in
    the diff and pushes it past the cap. Mutation: drop the `[:_MAX_SCAN_BYTES]`
    slice -> calc.py is screened normally and the unscreened caution never
    appears."""
    from crossaudit.cli import build as build_mod

    monkeypatch.setattr(build_mod, "_MAX_SCAN_BYTES", 4096)
    long_prose = "".join(f"paragraph {i} of an honest but long report\n" for i in range(300))
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {SUMMARY: long_prose, CALC: CALC_DEFENSIVE}, {CALC: CALC_FIXED}])
    caution = next(e for e in events if e.kind == "repair_caution")
    assert caution.detail == ("1 staged file(s) were larger than the review can read and "
                              f"were not screened: {CALC}")
    assert "repair_refused" not in _kinds(events)


# ----------------------------------------------------------- config knob

def test_init_then_load_accepts_the_scaffolded_repair_block(tmp_path, monkeypatch):
    """Mutation: drop "repair" from _ALLOWED_TOP -> load refuses its own template."""
    import argparse

    from crossaudit.cli import main
    from crossaudit.config import load

    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5"))
    text = (project / "crossaudit.yml").read_text()
    assert "repair:\n  enabled: true\n  mode: caution\n  max_changed_lines: 200\n" in text
    assert load(project / "crossaudit.yml").repair == RepairPolicy(
        enabled=True, mode="caution", max_changed_lines=200)


def _load_with(science, block: str):
    from crossaudit.config import load

    from .conftest import CONFIG
    (science / "crossaudit.yml").write_text(CONFIG + block)
    return load(science / "crossaudit.yml")


def test_repair_config_defaults_when_absent(cfg):
    assert cfg.repair == RepairPolicy(enabled=True, mode="caution", max_changed_lines=200)


def test_repair_config_reads_all_knobs(science):
    loaded = _load_with(science, "repair:\n  enabled: false\n  mode: refuse\n  max_changed_lines: 50\n")
    assert loaded.repair == RepairPolicy(enabled=False, mode="refuse", max_changed_lines=50)


@pytest.mark.parametrize("block,message", [
    ("repair: 3\n", "repair must be a mapping"),
    ("repair:\n  budget: 1\n", "repair: unknown keys ['budget']"),
    ("repair:\n  enabled: yes please\n", "repair.enabled must be true or false"),
    ("repair:\n  mode: loud\n", "repair.mode must be caution or refuse"),
    ("repair:\n  mode: true\n", "repair.mode must be caution or refuse"),
    ("repair:\n  max_changed_lines: 0\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
    ("repair:\n  max_changed_lines: 10001\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
    ("repair:\n  max_changed_lines: true\n", "repair.max_changed_lines must be an integer from 1 to 10000"),
])
def test_repair_config_refuses_bad_values_with_the_config_error(science, block, message):
    """Mutation: accept bool for max_changed_lines -> `true` loads as 1."""
    from crossaudit.errors import ConfigDenial
    with pytest.raises(ConfigDenial) as exc:
        _load_with(science, block)
    assert message in exc.value.reason


# ============================================================ review D2

def test_a_chinese_report_name_in_scope_is_not_refused(science, cfg, transcripts, monkeypatch):
    """T2. Mutation: read staged names without -z (git quotes them) -> the
    round is refused twice as out of scope and the run stops."""
    scoped = dataclasses.replace(cfg, scope_dirs=["experiments"])
    code, events, calls = _drive(
        scoped, science, monkeypatch,
        [ROUND_ONE, {"experiments/demo/报告.md": "报告正文\n"}, {CALC: CALC_FIXED}])
    assert not {"repair_refused", "repair_caution"} & set(_kinds(events))
    assert "experiments/demo/报告.md" in git("-c", "core.quotepath=false", "log",
                                             "--name-only", cwd=science)


def test_scope_dirs_spelt_with_dot_slash_do_not_refuse_honest_repairs(
        science, cfg, transcripts, monkeypatch):
    """T3 / N11. Mutation: drop normalise_path from in_scope -> two refusals,
    cause repair_refused."""
    scoped = dataclasses.replace(cfg, scope_dirs=["./experiments"])
    code, events, calls = _drive(
        scoped, science, monkeypatch, [ROUND_ONE, {CALC: CALC_FIXED}, {SUMMARY: "three\n"}])
    assert "repair_refused" not in _kinds(events)
    assert "strict=True" in git("log", "-p", cwd=science)


def test_a_model_written_binary_with_a_space_in_its_name_is_refused(
        science, cfg, transcripts, monkeypatch):
    """T8. Mutation: header regex `a/\\S+` (no space) -> the PNG is never
    parsed and is committed."""
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {"experiments/demo/fig 1.png": PNG}, {CALC: CALC_FIXED}])
    refused = [e for e in events if e.kind == "repair_refused"]
    assert len(refused) == 1 and refused[0].detail.startswith(
        "experiments/demo/fig 1.png is a binary file written directly by the generator")
    assert "fig 1.png" not in git("log", "--name-only", cwd=science)


def test_the_apply_side_scope_denial_keeps_the_audit_findings_in_the_retry_prompt(
        science, cfg, transcripts, monkeypatch):
    """T4 / D2 #9: a real out-of-scope write is denied by gen_mod.apply before
    the screen; that retry prompt must still carry the cause. Mutation:
    rebuild `findings` from the denial alone -> "metadata.yml" is gone."""
    scoped = dataclasses.replace(cfg, scope_dirs=["experiments"])
    code, events, calls = _drive(
        scoped, science, monkeypatch,
        [ROUND_ONE, {"notes/stray.md": "outside\n"}, {CALC: CALC_FIXED}])
    assert "generation_refused" in _kinds(events) and "repair_refused" not in _kinds(events)
    third = calls[2]["findings"]
    assert "metadata.yml" in third
    assert third.index("metadata.yml") < third.index("refused before it reached the auditor")
    assert "Return only files inside experiments/" in third
    assert "strict=True" in git("log", "-p", cwd=science)


def test_a_repeated_apply_denial_does_not_pile_up_refusal_blocks(
        science, cfg, transcripts, monkeypatch):
    """The audit's findings are kept once; each retry prompt has one refusal
    block, not one per refused round. Mutation: append to `findings` instead
    of `audit_findings` -> round 4's prompt carries two blocks."""
    scoped = dataclasses.replace(cfg, scope_dirs=["experiments"], max_rounds=4)
    stray = {"notes/stray.md": "outside\n"}
    code, events, calls = _drive(scoped, science, monkeypatch,
                                 [ROUND_ONE, stray, stray, {CALC: CALC_FIXED}])
    fourth = calls[3]["findings"]
    assert fourth.count("refused before it reached the auditor") == 1
    assert fourth.count("metadata.yml") == calls[1]["findings"].count("metadata.yml")


# ==================================================== closure audit D #6

def test_a_model_written_binary_past_the_diff_cap_is_still_refused(
        science, cfg, transcripts, monkeypatch):
    """The closure audit's loop: cap lowered to 4 KB, a long SUMMARY.md sorts
    before `fig 1.png` and pushes it past the cap. Mutation: drop
    `binary_files=_staged_binaries(cfg)` -> the PNG is committed with only an
    'unscreened' caution."""
    from crossaudit.cli import build as build_mod

    monkeypatch.setattr(build_mod, "_MAX_SCAN_BYTES", 4096)
    long_prose = "".join(f"paragraph {i} of an honest but long report\n" for i in range(300))
    code, events, calls = _drive(
        cfg, science, monkeypatch,
        [ROUND_ONE, {SUMMARY: long_prose, "experiments/demo/fig 1.png": PNG}, {CALC: CALC_FIXED}])
    refused = [e for e in events if e.kind == "repair_refused"]
    assert len(refused) == 1 and refused[0].detail == (
        "experiments/demo/fig 1.png is a binary file written directly by the generator, "
        "which cannot be reviewed line by line")
    assert calls[2]["staged"] == "" and not (science / "experiments/demo/fig 1.png").exists()
    assert "fig 1.png" not in git("log", "--name-only", cwd=science)
    assert "strict=True" in git("log", "-p", cwd=science)
