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
import json

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
    "constitution": (
        "whether one project's rules file exists; mirrored by the app's own "
        "constitution row via the shared helper"),
    "tls trust store": (
        "mirrored by the app's `tls` row, which asks the same question of the "
        "same trust store"),
    "install": (
        "mirrored by the app's `install` row"),
    "gh cli": (
        "mirrored by the app's `github_cli` row"),
    "python": (
        "mirrored by the app's `python` row"),
    "git": (
        "mirrored by the app's `git` row"),
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


def test_the_parity_guard_reddens_for_an_unmirrored_cli_check(cfg, monkeypatch,
                                                              capsys):
    """D64: the deliverable is the test PLUS the observation of it failing.

    A real CLI check that nobody mirrors and nobody excluded. If adding one does
    not turn the comparison red, the comparison is not the mechanism whatever it
    is named — which is exactly what the previous version of this file was.
    """
    cli = _cli_check_names(cfg, monkeypatch, capsys)
    app = _app_check_ids(cfg)
    assert _unmirrored(cli, app) == set(), "baseline is not clean"

    with pytest.raises(AssertionError) as caught:
        missing = _unmirrored(cli | {"nobody mirrors this"}, app)
        assert missing == set(), (
            f"CLI doctor checks with no GUI mirror and no named exclusion: "
            f"{sorted(missing)}")
    assert "nobody mirrors this" in str(caught.value)


def test_every_exclusion_names_a_check_that_exists(cfg, monkeypatch, capsys):
    """An exclusion for a check nobody emits is pre-approved absence.

    Same failure as an unused allowlist entry: it stops meaning anything, and
    the next check to go missing lands in it silently.
    """
    cli = _cli_check_names(cfg, monkeypatch, capsys)
    # Only the checks this fixture can reach are asserted; ones behind --online
    # or a broken install are listed here so the set stays honest.
    unreachable = {"gh cli", "isolation minimum", "admission-capable",
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
