"""`crossaudit build` exits with the README's codes for the loop's final state.

README "Exit codes": 22 is "Provider, network, or model request failure". The
acceptance run (claim C20) drove `build` against a vendor answering HTTP 500
on every call: the run parked as a provider stop and exited 11. The mapping
now lives in one table, `cli.build.BUILD_EXIT`; each row has a case here,
driven through the real `crossaudit build` (only the transport is faked),
except the budget row, whose park needs a usage guardrail and is emitted by
a stub loop with the exact event the real loop emits.

D10 mutation (checked by hand): map ("provider") to EXIT_ESCALATED in
BUILD_EXIT and three go red: the table case, and both provider cases with 11.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import (FakeVendors, audit_reply, http_500,  # noqa: E402
                            increment_reply, init_project, with_keys)

from crossaudit.cli import build as build_mod  # noqa: E402
from crossaudit.cli import main  # noqa: E402
from crossaudit.errors import (EXIT_ESCALATED, EXIT_OK,  # noqa: E402
                               EXIT_PROVIDER)
from crossaudit.runtime.events import RunEvent  # noqa: E402
from crossaudit.runtime.runs import RunState  # noqa: E402

def _started(on_event) -> None:
    on_event(RunEvent(kind="round_started", actor="loop", text="round 1",
                      state=RunState.GENERATING, round_no=1, round_limit=3))


TASK = ["Create", "a", "small", "reproducible", "benchmark"]


@pytest.fixture()
def project(tmp_path, monkeypatch, capsys):
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    capsys.readouterr()
    return root


def _status_cycles(capsys) -> list[dict]:
    import json

    capsys.readouterr()
    main.main(["--json", "status"])
    return json.loads(capsys.readouterr().out)["cycles"]


def test_the_table_has_one_row_per_documented_outcome():
    assert build_mod.BUILD_EXIT == {
        (EXIT_OK, ""): EXIT_OK,
        (EXIT_ESCALATED, "provider"): EXIT_PROVIDER,
        (EXIT_ESCALATED, "budget"): EXIT_ESCALATED,
        (EXIT_ESCALATED, ""): EXIT_ESCALATED,
    }
    # Anything unlisted passes through rather than being invented.
    assert build_mod.build_exit_code(EXIT_ESCALATED, "something-new") == EXIT_ESCALATED
    assert build_mod.build_exit_code(20) == 20


def test_pass_exits_0(project, monkeypatch, capsys):
    FakeVendors().install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_OK


def test_a_generator_provider_failing_every_call_exits_22(project, monkeypatch, capsys):
    vendors = FakeVendors(http_500).install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_PROVIDER
    assert vendors.calls and all(role == "generator" for _v, role in vendors.calls)
    assert "provider returned HTTP 500" in capsys.readouterr().out


def test_an_auditor_provider_failing_every_call_exits_22(project, monkeypatch, capsys):
    def answer(role, n, prompt):
        if role == "auditor":
            return http_500(role, n, prompt)
        return increment_reply()
    FakeVendors(answer).install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_PROVIDER


def test_a_blocked_round_that_spends_the_budget_exits_11(project, monkeypatch, capsys):
    """Final state ESCALATED, not a provider stop: 11, and status says so."""
    def answer(role, n, prompt):
        if role == "auditor":
            return audit_reply(prompt, "BLOCKED")
        return increment_reply().replace("seed 7.", f"seed 7 (revision {n}).")
    FakeVendors(answer).install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_ESCALATED
    assert any(c["status"] == "ESCALATED" for c in _status_cycles(capsys))


def test_a_budget_park_exits_11(project, monkeypatch, capsys):
    """A usage guardrail is not a provider failure: a person raises the limit."""
    def budget_park(_cfg, _task, *, on_event, **_kw):
        _started(on_event)
        on_event(RunEvent(
            kind="provider_unavailable", actor="loop", text="waiting for provider",
            state=RunState.PROVIDER_UNAVAILABLE, round_no=1, round_limit=3,
            waiting_reason={"kind": "budget", "category": "budget",
                            "detail": "usage guardrail: the daily limit was reached"}))
        return EXIT_ESCALATED
    monkeypatch.setattr(build_mod, "run_loop", budget_park)
    assert main.main(["build", *TASK]) == EXIT_ESCALATED


def test_a_provider_wait_that_recovered_is_not_reported_as_a_provider_failure(
        project, monkeypatch, capsys):
    """Only the FINAL event decides: a park followed by more work is not 22."""
    def recovered(_cfg, _task, *, on_event, **_kw):
        _started(on_event)
        on_event(RunEvent(
            kind="provider_unavailable", actor="loop", text="waiting for provider",
            state=RunState.PROVIDER_UNAVAILABLE, round_no=1, round_limit=3,
            waiting_reason={"kind": "provider", "category": "routes_exhausted",
                            "detail": "x"}))
        # The remedy resumed the phase; the run then stopped for another reason.
        on_event(RunEvent(kind="round_started", actor="loop", text="round 1",
                          state=RunState.GENERATING, round_no=1, round_limit=3))
        return EXIT_ESCALATED
    monkeypatch.setattr(build_mod, "run_loop", recovered)
    assert main.main(["build", *TASK]) == EXIT_ESCALATED
