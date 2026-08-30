"""Every CLI doctor check is mirrored in the app doctor, or excluded by name.

**This test was previously a tautology** (D64). It compared two hardcoded literal
sets — `app_doctor.collect` appeared only in a dead `if False` branch — so it
asserted that one list I typed matched another list I typed. It would not have
noticed a new check on either side, which is the only thing it exists to notice.
It carried a name that reads like assurance, so a reviewer met
`test_cli_doctor_checks_are_mirrored_or_named_excluded`, ticked it, and stopped.

Both sides are now derived by CALLING the two doctors. And per D64 the
deliverable is not the test: it is the test plus the observation of it failing,
so `test_the_parity_guard_reddens_for_an_unmirrored_cli_check` adds a real CLI
check that nobody mirrors and requires the real comparison to raise.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from crossaudit import app_doctor
from crossaudit.cli import main


#: Why a CLI check does not BELONG in the GUI — never why it is merely absent.
#: The two doctors answer different questions: `cmd_doctor` asks "is this
#: project's audit trustworthy?", `app_doctor` asks "is this Mac able to run the
#: app?". An entry that cannot be justified by that difference is not an
#: exclusion, it is a gap wearing one.
CLI_ONLY: dict[str, str] = {
    "admission-capable": (
        "admission is a property of how this build was installed and is consumed "
        "by `verify --admit`; the app has no admission workflow to gate"),
    "isolation minimum": (
        "isolation is a deployment posture about credential boundaries between "
        "two roles, not a question about this Mac"),
    "science repo is git": (
        "asks whether one project's ledger is a repository; the app's project "
        "readiness answers this per project, not per machine"),
    "constitution rules": (
        "reads the rule IDs inside one project's constitution; the app reports "
        "the constitution's readiness, not its contents"),
    "git identity": (
        "commit authorship for one repository. The app commits its own "
        "controller state under a fallback identity, so it is never blocked on "
        "this"),
    "provider": (
        "names which provider one project's auditor is configured for; the app "
        "reports connection readiness per provider instead"),
    "state store": (
        "one project's controller directory; the app's workspace check covers "
        "the directory it actually owns"),
    "auditor connection": (
        "per-project credential for one role; the app reports connections per "
        "provider rather than per project role"),
    # NOTE: `generator connection` is deliberately NOT listed. It does not exist
    # on this branch — it arrives with the first-three-minutes slice — and the
    # stale-exclusion test below caught me listing it from memory of another
    # branch. Pre-approving a check that does not exist is the padding this file
    # forbids; it gets an entry when it gets a check.
    "heterogeneity (I1)": (
        "compares two vendors configured in one project's config; nothing about "
        "this Mac can make it true or false"),
    "config": (
        "whether one directory holds a crossaudit.yml; the app surfaces this as "
        "project readiness"),
    # The deterministic pack a PROJECT configured, reported one row per check.
    # Which checks are enabled is a property of that project's crossaudit.yml,
    # so the machine cannot be ready or unready for them.
    "machine:schema": "one project's configured deterministic checks",
    "machine:units": "one project's configured deterministic checks",
    "machine:convergence": "one project's configured deterministic checks",
    "machine:provenance": "one project's configured deterministic checks",
    "machine:declared": "one project's configured deterministic checks",
    "machine:internal": "one project's configured deterministic checks",
    "machine:complete": "one project's configured deterministic checks",
    "machine:parseable": "one project's configured deterministic checks",
    "admission tier": "a deployment posture, not a machine capability",
    "  toward enforced": "continuation line of the admission tier posture",
}

#: CLI check name -> app check id, where the two ask the same question under
#: different names. Anything not here and not in CLI_ONLY must match by name.
ALIASES = {
    # Every entry here is a CLAIM THAT A MIRROR EXISTS, and `_unmirrored`
    # executes it against the ids `app_doctor.collect()` actually produced. A
    # mirror claim parked in CLI_ONLY instead is never executed: deleting the
    # app's row leaves the guard green. That is what mutation B found in this
    # file's own exclusion list, so `python` and `git` moved here from there.
    "python": "python",
    "git": "git",
    "constitution": "constitution",
    # Both CLI rows ask about the same file and the app answers both with one
    # row built from the shared helper: is this project's constitution present
    # and committed. Two questions there, one row here.
    "constitution committed": "constitution",
    "tls trust store": "tls",
    "install": "install",
    "gh cli": "github_cli",
}


def _cli_check_names(cfg, monkeypatch, capsys) -> set[str]:
    """Run the REAL `cmd_doctor` and read the checks it emitted."""
    monkeypatch.chdir(cfg.root)
    main.cmd_doctor(argparse.Namespace(json=True, all=True, fix=False,
                                       online=False))
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):out.rindex("}") + 1])
    return {row["check"] for row in payload["checks"]}


def _app_check_ids(cfg) -> set[str]:
    """Run the REAL `app_doctor.collect` and read the checks it produced."""
    return {row["id"] for row in app_doctor.collect(cfg, online=False)["checks"]}


def _unmirrored(cli: set[str], app: set[str]) -> set[str]:
    """CLI checks that are neither mirrored nor excluded by name. The property."""
    missing = set()
    for name in cli:
        if name in CLI_ONLY:
            continue
        if name in app or ALIASES.get(name) in app:
            continue
        missing.add(name)
    return missing


def test_cli_doctor_checks_are_mirrored_or_named_excluded(cfg, monkeypatch,
                                                          capsys):
    cli = _cli_check_names(cfg, monkeypatch, capsys)
    app = _app_check_ids(cfg)
    assert cli, "the CLI doctor produced no checks; the comparison is vacuous"
    assert app, "the app doctor produced no checks; the comparison is vacuous"
    missing = _unmirrored(cli, app)
    assert missing == set(), (
        f"CLI doctor checks with no GUI mirror and no named exclusion: "
        f"{sorted(missing)}. Either mirror them in app_doctor.collect(), or add "
        f"an entry to CLI_ONLY saying why the check does not BELONG in the GUI "
        f"— not merely why it is currently absent.")


def _shipped_module_with(source: str, package: str, name: str,
                         replacements: list[tuple[str, str]]):
    """A REAL copy of a shipped module, compiled with one textual change.

    Not a stub and not a monkeypatched return value: the shipped source is read
    from disk, altered, compiled and executed, so the function under test is the
    production function plus the mutation. If an anchor stops matching, this
    raises rather than silently testing an unmutated module — a fixture that
    quietly stops mutating is the failure mode this whole file exists about.
    """
    text = Path(source).read_text()
    for old_text, new_text in replacements:
        assert text.count(old_text) >= 1, f"anchor moved: {old_text!r}"
        text = text.replace(old_text, new_text)
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    sys.modules[name] = module
    try:
        exec(compile(text, source, "exec"), module.__dict__)
    finally:
        sys.modules.pop(name, None)
    return module


def test_the_guard_reddens_when_cmd_doctor_really_gains_an_unmirrored_check(
        cfg, monkeypatch, capsys):
    """D64, and F5: the mutation has to run through the DERIVATION.

    The previous version of this test injected a synthetic name into the
    already-computed set and asserted that a set difference does set difference.
    It never touched `cmd_doctor`, so `_cli_check_names` could revert to a typed
    literal — the exact D64 defect — and this file stayed green (the auditor's
    mutation D). The check below is added to a real, compiled `cmd_doctor`, and
    the guard has to derive it by running that function.
    """
    probe = "unmirrored probe"
    mutated = _shipped_module_with(
        main.__file__, "crossaudit.cli", "crossaudit.cli._main_f5_probe",
        [('    het_ok, why = heterogeneity(cfg)',
          f'    add("{probe}", True, "a real CLI check nobody mirrors", "")\n'
          '    het_ok, why = heterogeneity(cfg)')])
    monkeypatch.setattr(main, "cmd_doctor", mutated.cmd_doctor)

    cli = _cli_check_names(cfg, monkeypatch, capsys)
    assert probe in cli, (
        "the CLI side did not come from running cmd_doctor: the probe was added "
        "to a real compiled copy of the shipped function and never arrived. The "
        "derivation is not being exercised, so this file is asserting its own "
        "helpers rather than parity.")

    app = _app_check_ids(cfg)
    assert probe in _unmirrored(cli, app), (
        "an unmirrored CLI check did not turn the comparison red")


def test_the_guard_reddens_when_the_app_doctor_really_loses_a_mirror(
        cfg, monkeypatch, capsys):
    """The same, from the app side (the auditor's mutation D2).

    A mirror is deleted from a real compiled `app_doctor.collect`, and the guard
    has to notice by running it. If `_app_check_ids` reverts to a typed literal
    the deletion is invisible and this reddens.
    """
    mutated = _shipped_module_with(
        app_doctor.__file__, "crossaudit", "crossaudit._app_doctor_f5_probe",
        [('"id": "python",', '"id": "python_runtime",')])
    monkeypatch.setattr(app_doctor, "collect", mutated.collect)

    app = _app_check_ids(cfg)
    assert "python" not in app and "python_runtime" in app, (
        "the app side did not come from running app_doctor.collect(): the row "
        "was renamed in a real compiled copy and the change never arrived.")

    cli = _cli_check_names(cfg, monkeypatch, capsys)
    assert "python" in _unmirrored(cli, app), (
        "a deleted GUI mirror did not turn the comparison red")


def test_every_exclusion_names_a_check_that_exists(cfg, monkeypatch, capsys):
    """An exclusion for a check nobody emits is pre-approved absence.

    Same failure as an unused allowlist entry: it stops meaning anything, and
    the next check to go missing lands in it silently.
    """
    cli = _cli_check_names(cfg, monkeypatch, capsys)
    # Only the checks this fixture can reach are asserted; ones behind --online
    # or a broken install are listed here so the set stays honest. This list
    # waives REACHABILITY ONLY — that an entry names a check the shipped code can
    # emit at all is established from the source below, where no waiver applies.
    unreachable = {"isolation minimum", "admission-capable",
                   "  toward enforced"}
    stale = {name for name in CLI_ONLY
             if name not in cli and name not in unreachable
             and not name.startswith("machine:")}
    assert stale == set(), (
        f"exclusions naming checks the CLI doctor does not emit: {sorted(stale)}")


def test_no_exclusion_is_justified_by_mere_absence():
    """The test for an exclusion is WHY it does not belong, not that it is gone.

    Guards against the reason drifting back to "the GUI does not have it",
    which is the observation the exclusion is supposed to explain.
    """
    lazy = [name for name, why in CLI_ONLY.items()
            if "not implemented" in why.lower() or "currently absent" in why.lower()
            or why.strip().lower().startswith("the gui does not have")]
    assert lazy == [], f"exclusions justified by their own absence: {lazy}"


def test_no_exclusion_is_justified_by_a_mirror_it_does_not_check():
    """A mirror claim belongs in ALIASES, where something executes it.

    Found by mutating the app doctor rather than the CLI one: deleting the app's
    `python` row left this file green, because "python" sat in CLI_ONLY with the
    reason "mirrored by the app's `python` row". CLI_ONLY is consulted first and
    short-circuits, so the claim that a mirror exists was never checked against
    the ids `app_doctor.collect()` emits — the D64 defect (a parity claim with
    nothing executing it) reproduced inside the fix for D64.

    Four of the six were in ALIASES *as well*, which reads as covered and is not:
    the alias branch is unreachable for any name CLI_ONLY already matched.
    """
    claims = {name: why for name, why in CLI_ONLY.items()
              if "mirror" in why.lower()}
    assert claims == {}, (
        f"exclusions asserting a mirror that nothing executes: "
        f"{sorted(claims)}. Move each to ALIASES so the app doctor's own output "
        f"has to contain the row.")


def _names_cmd_doctor_can_emit() -> tuple[set[str], set[str]]:
    """Every check name in the shipped `cmd_doctor`, read out of its source.

    Extracted rather than transcribed: a copied list drifts from the code it
    claims to describe and nothing notices, which is the same failure as a
    fixture that stops mutating. Returns the literal names and the f-string
    prefixes (`machine:`), because the deterministic pack is named by
    interpolation and its entries are real checks.
    """
    body = Path(main.__file__).read_text()
    body = body[body.index("def cmd_doctor("):]
    end = re.search(r"\ndef ", body)
    body = body[:end.start()] if end else body
    literals = (set(re.findall(r'add\(\s*"([^"]+)"', body))
                | set(re.findall(r'"check":\s*"([^"]+)"', body)))
    prefixes = (set(re.findall(r'"check":\s*f"([^"{]*)\{', body))
                | set(re.findall(r'add\(\s*f"([^"{]*)\{', body)))
    return literals, prefixes


def test_no_exclusion_names_a_check_the_shipped_code_cannot_emit():
    """F7: the staleness guard carried its own unchecked waiver list.

    `test_every_exclusion_names_a_check_that_exists` skips anything parked in
    `unreachable` or prefixed `machine:`, and nothing verified those. So an
    exclusion could be pre-approved absence at one remove — the same shape the
    test exists to prevent, one level down, which is this file's recurring
    defect. Existence is checked here against the shipped source, where the
    waiver does not reach: `unreachable` may excuse a check being unreachable
    from this fixture, never a name that no code emits.
    """
    literals, prefixes = _names_cmd_doctor_can_emit()
    assert literals, "no check names were extracted; the reader has drifted"

    def emitted(name: str) -> bool:
        return name in literals or any(name.startswith(p) for p in prefixes)

    unknown = sorted(n for n in set(CLI_ONLY) | set(ALIASES) if not emitted(n))
    assert unknown == [], (
        f"exclusions or aliases naming checks the shipped cmd_doctor never "
        f"emits: {unknown}. Being unreachable from the test fixture is not the "
        f"same as not existing, and only the first is waivable.")
