"""The first three minutes must tell the truth (Ledger D6, P1/P2).

The design engineer walked the product from an empty directory. What it found on
the setup path, in order of how early a person hits it:

* ``init`` prints **Ready** in a green box while no credential exists, then
  recommends ``build``, which cannot work — and ``doctor``, one command later,
  says *not ready*. Two commands the product routes people between, contradicting
  each other.
* ``doctor``'s tagline is "check everything" and it never checks the generator
  key, which is the credential that stops ``build`` in round one.
* ``doctor`` prints ``[PASS]`` on a line whose own text says a guarantee is not
  being enforced.
* The front door headlines ``crossaudit run`` and omits ``build`` and
  ``console``, so the generation half of the product is missing from the first
  thing anyone reads.

Every test here **executes** the command and reads what it printed (AGENTS.md
§3.5). None asserts that a string exists in a source file: the defects were all
in what the commands *say to a person*, which only running them can show.
"""
from __future__ import annotations

import argparse
import re

import pytest

from crossaudit.cli import main
from crossaudit.errors import EXIT_CONFIG, EXIT_OK

#: The per-line view. The default view now leads with a verdict and collapses
#: the passing majority (SPEC 6 §4); `--all` is the stable full surface, and it
#: is what the classification tests below read, because classification is
#: exactly what it shows.
_ARGS = dict(fix=False, online=False, json=False, all=True)
_BRIEF = dict(fix=False, online=False, json=False, all=False)


def _wheel(monkeypatch):
    """Pretend to be an admissible install so unrelated FAILs do not mask ours."""
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})


def _run_doctor(cfg, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.chdir(cfg.root)
    _wheel(monkeypatch)
    code = main.cmd_doctor(argparse.Namespace(**_ARGS))
    return code, capsys.readouterr().out


def _lines(out: str) -> list[tuple[str, str, str]]:
    """Every rendered doctor line as (marker, check name, detail)."""
    rows = []
    for line in out.splitlines():
        # The renderer sizes the label column from the longest label, so at
        # least two spaces always separate label from detail. An earlier version
        # of this parser assumed a fixed width and silently dropped every row
        # whose label reached it — the rows this file exists to check.
        m = re.match(r"\[(PASS|FAIL|INFO)\] (.*?)\s{2,}(.*)$", line)
        if m:
            rows.append((m.group(1), m.group(2).strip(), m.group(3)))
    return rows


# ------------------------------------------------- doctor checks the key that stops build
def test_doctor_checks_the_generator_key_that_stops_build_in_round_one(
        cfg, monkeypatch, capsys):
    monkeypatch.delenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY",
                       raising=False)
    monkeypatch.setenv(cfg.auditor.key_env, "auditor-secret")
    code, out = _run_doctor(cfg, monkeypatch, capsys)

    rows = _lines(out)
    generator = [r for r in rows if r[1] == "generator connection"]
    assert generator, "doctor must look at the generator credential at all"
    assert generator[0][0] == "FAIL"
    assert code == EXIT_CONFIG and "not ready" in out
    # The fix line names the consequence, not just the variable.
    assert "stops in round one" in out


def test_doctor_passes_the_generator_check_once_the_key_is_present(
        cfg, monkeypatch, capsys):
    monkeypatch.setenv(cfg.auditor.key_env, "auditor-secret")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY",
                       "generator-secret")
    _code, out = _run_doctor(cfg, monkeypatch, capsys)

    generator = [r for r in _lines(out) if r[1] == "generator connection"]
    assert generator and generator[0][0] == "PASS"
    # Presence only: doctor output gets pasted into bug reports.
    assert "generator-secret" not in out


# ------------------------------------------- [PASS] means tested and held (SPEC 2)
def test_no_green_marker_sits_on_a_line_that_reports_a_posture(
        cfg, monkeypatch, capsys):
    """The finding, by category rather than by editing one line.

    D6 named the "toward enforced" line. Applying SPEC 2's rule to all of them
    found six: the four configured deterministic contracts, the admission tier,
    and the shortfall line. All six were hard-coded ``ok: True`` and none of them
    had run anything.
    """
    from crossaudit.dcl import builtin, neutral  # noqa: F401  (registers checks)
    monkeypatch.setenv(cfg.auditor.key_env, "auditor-secret")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY", "g")
    _code, out = _run_doctor(cfg, monkeypatch, capsys)
    rows = _lines(out)

    contract_rows = [r for r in rows if r[1].startswith("machine:")]
    assert contract_rows, "the configured deterministic contracts should be listed"

    posture = [r for r in rows
               if r[1].startswith("machine:")
               or r[1] in ("admission tier", "toward enforced")]
    assert len(posture) >= 3, f"expected the posture lines, saw {[r[1] for r in rows]}"
    for marker, name, _detail in posture:
        assert marker == "INFO", f"{name} reports a posture and must not be a verdict"

    # The specific sentence D6 caught: no green marker beside text saying a
    # guarantee does not hold.
    for marker, _name, detail in rows:
        if "cannot hold anyone to account" in detail:
            assert marker == "INFO", "a green PASS on a guarantee that does not hold"


def test_info_lines_are_excluded_from_the_ready_verdict(cfg, monkeypatch, capsys):
    """A tally that counts non-verdicts does not mean what it says."""
    monkeypatch.setenv(cfg.auditor.key_env, "auditor-secret")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY", "g")
    code, out = _run_doctor(cfg, monkeypatch, capsys)
    rows = _lines(out)

    assert any(r[0] == "INFO" for r in rows), "the fixture should produce INFO lines"
    failed = [r for r in rows if r[0] == "FAIL"]
    # The verdict follows the verdict lines only.
    if failed:
        assert code == EXIT_CONFIG and "not ready" in out
    else:
        assert code == EXIT_OK and out.rstrip().endswith("ready")


def test_an_info_line_never_offers_a_fix_arrow(cfg, monkeypatch, capsys):
    """A posture has nothing to fix; offering a remedy implies it is broken."""
    monkeypatch.setenv(cfg.auditor.key_env, "auditor-secret")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY", "g")
    _code, out = _run_doctor(cfg, monkeypatch, capsys)

    lines = out.splitlines()
    for index, line in enumerate(lines[:-1]):
        if line.startswith("[INFO]"):
            assert not lines[index + 1].strip().startswith("->"), line


# --------------------------------------------------- init and doctor agree
def _init_args(project) -> argparse.Namespace:
    """Exactly the non-interactive invocation the CLI exposes."""
    return argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5")


def test_init_does_not_claim_ready_when_the_next_command_cannot_run(
        tmp_path, monkeypatch, capsys):
    """Executed end to end: the real init command, then the real doctor."""
    project = tmp_path / "prose"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for name in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(project)
    main.cmd_init(_init_args(project))
    init_out = capsys.readouterr().out

    assert "not ready to run yet" in init_out, init_out[-600:]
    # The blocking credential leads, rather than scrolling above a green box.
    banner = init_out.index("not ready to run yet")
    assert init_out.index("export CROSSAUDIT_", banner) > banner
    # And it does not OFFER the command that cannot work as a next step. The
    # phrase may still appear inside an explanation of what the key unblocks —
    # naming the consequence is the point — so this checks the command rows.
    tail = init_out[banner:]
    offered = [ln.strip().lstrip("│ ").strip() for ln in tail.splitlines()]
    assert not any(ln.startswith("crossaudit build") for ln in offered), tail

    # doctor, one command later, must agree rather than contradict.
    from crossaudit.config import load as load_cfg
    cfg = load_cfg(project / "crossaudit.yml")
    code, doctor_out = _run_doctor(cfg, monkeypatch, capsys)
    assert code == EXIT_CONFIG and "not ready" in doctor_out


def test_init_says_ready_only_when_doctor_would_agree(tmp_path, monkeypatch,
                                                     capsys):
    """F1: the contradiction, driven rather than asserted about.

    The previous version of this test checked that init printed "Ready" and
    never ran doctor at all. So it passed on a tree where a keyed init said
    Ready and the very next command denied readiness — in the person's own
    language, with the second line being the true one. It runs BOTH now and
    asserts only that they agree, because which answer is right depends on the
    machine and the agreement is the property.
    """
    import argparse

    project = tmp_path / "keyed"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "auditor-secret")
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "generator-secret")
    monkeypatch.chdir(project)
    main.cmd_init(_init_args(project))
    init_out = capsys.readouterr().out

    code = main.cmd_doctor(argparse.Namespace(json=False, all=False, fix=False,
                                              online=False, lang="en"))
    capsys.readouterr()

    init_says_ready = ("Ready" in init_out
                       and "not ready" not in init_out.lower())
    doctor_says_ready = code == 0
    assert init_says_ready == doctor_says_ready, (
        f"init and doctor disagree one command apart: init "
        f"{'said Ready' if init_says_ready else 'did not say Ready'}, doctor "
        f"returned {code}. Setup finishing is not the same as being able to "
        f"run, and whichever is right they must not contradict each other.")

    if not doctor_says_ready:
        # Saying "not ready" is only half the fix; the person needs the reason.
        assert any(word in init_out.lower()
                   for word in ("admit", "credential", "key")), (
            "init withheld Ready without saying what remains")
    # With both credentials in place, the run commands are offered either way.
    assert "crossaudit build" in init_out


# ----------------------------------------------------------- the front door
def test_the_front_door_names_the_generation_half_of_the_product(capsys):
    """Bare `crossaudit` omitted build and console entirely."""
    main.main([])
    out = capsys.readouterr().out

    assert "crossaudit build" in out, "the command that writes is not mentioned"
    assert "crossaudit console" in out, "the browser loop is not mentioned"
    assert "crossaudit run" in out, "auditing an existing commit is still offered"
    # build is introduced before run: it is what most people arrive wanting.
    assert out.index("crossaudit build") < out.index("crossaudit run")


# ===================== SPEC 6: the CLI's first three screens =================
# Acceptance executed against real invocations, never asserted against source
# strings. §7 names the exit-code regression as the one that would silently
# break scripting, so it is checked explicitly rather than assumed.
def test_the_un_initialised_refusal_reads_as_setup_not_permission(
        tmp_path, monkeypatch, capsys):
    """DENIED is a permission word for what is only "not set up yet"."""
    from crossaudit.errors import ConfigDenial

    empty = tmp_path / "bare"
    empty.mkdir()
    monkeypatch.chdir(empty)
    code = main.main(["console"])
    err = capsys.readouterr().err

    assert "DENIED" not in err, "the human stream must not use a permission word"
    assert "No CrossAudit project here." in err
    # The diagnosis that tells someone in a subdirectory why their project was
    # not found is kept, not trimmed for brevity.
    assert "and every directory above it" in err
    assert "crossaudit init" in err
    # The machine contract is untouched: scripts depend on this exit code.
    assert code == EXIT_CONFIG

    # ...and the machine-readable form still carries kind and reason.
    payload = ConfigDenial("x", human="friendly").as_dict()
    assert "human" not in payload, "the human sentence must stay out of --json"
    assert payload["kind"] and payload["reason"]


def test_doctor_leads_with_the_verdict_and_collapses_the_passing_majority(
        cfg, monkeypatch, capsys):
    monkeypatch.delenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY",
                       raising=False)
    monkeypatch.delenv(cfg.auditor.key_env, raising=False)
    monkeypatch.chdir(cfg.root)
    _wheel(monkeypatch)
    main.cmd_doctor(argparse.Namespace(**_BRIEF))
    out = capsys.readouterr().out
    body = [ln for ln in out.splitlines() if ln.strip()]

    # The verdict is the first thing after the title, not the last line.
    assert body[1].strip().startswith("Not ready —")
    # Failures carry a consequence and then a remedy, in that order. The
    # auditor credential may legitimately be present from a keys file on the
    # machine running the suite, so the generator — which this fixture always
    # clears — is the one asserted on.
    assert "✗ No generator API key" in out
    assert out.index("CrossAudit cannot write anything without one.") < out.index(
        "export CROSSAUDIT_GENERATOR_KEY")
    # Posture carries ℹ and is not a verdict.
    assert "ℹ How much this project's history proves" in out
    # The passing majority collapses, and says how to see it.
    assert "other checks passed" in out and "--all to list them" in out


def test_doctor_all_still_prints_every_line(cfg, monkeypatch, capsys):
    """`--all` is the stable surface: CI and scripts keep the full list."""
    monkeypatch.setenv(cfg.auditor.key_env, "a")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY", "g")
    monkeypatch.chdir(cfg.root)
    _wheel(monkeypatch)
    main.cmd_doctor(argparse.Namespace(**_ARGS))
    full = capsys.readouterr().out
    rows = _lines(full)
    assert len(rows) > 10, "the full list must still be printed"
    assert full.rstrip().endswith("ready")


def test_the_collapsed_count_equals_the_checks_actually_run(cfg, monkeypatch, capsys):
    """A count that does not match the list is the tally defect again."""
    import re as _re
    monkeypatch.setenv(cfg.auditor.key_env, "a")
    monkeypatch.setenv(cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY", "g")
    monkeypatch.chdir(cfg.root)
    _wheel(monkeypatch)
    main.cmd_doctor(argparse.Namespace(**_BRIEF))
    brief = capsys.readouterr().out
    main.cmd_doctor(argparse.Namespace(**_ARGS))
    rows = _lines(capsys.readouterr().out)

    claimed = int(_re.search(r"✓ (\d+) other check", brief).group(1))
    actually_passed = len([r for r in rows if r[0] == "PASS"])
    assert claimed == actually_passed, (
        f"the collapsed line claims {claimed} but {actually_passed} checks passed")


def test_the_front_door_names_the_mechanism_not_just_the_action():
    """Precision over friendliness: the gloss says what makes it worth anything."""
    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main.main([])
    out = buffer.getvalue()
    assert "a second model from a different vendor" in " ".join(out.split())
    assert "crossaudit build" in out and "crossaudit console" in out
    # `run` is offered for what it is for, not as the one command to remember.
    assert "one command to remember" not in out
