"""The execution-scoped enumeration, reported with its predicate.

A census by pattern is a floor by construction. This drives the shipped server
and reports what those paths actually produced — a smaller claim, and a true one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))
import enumerate_console_strings as harness  # noqa: E402

#: The paths and states this claim covers. A completeness claim is only as wide
#: as what is listed here, and the state matters as much as the endpoint.
PLAN = [
    ("/api/health", None),
    ("/api/state", None),
    ("/api/projects", None),
    ("/api/settings", None),
    ("/api/chats/new", b'{"title":"x"}'),
    ("/api/projects/open", b'{"root":"/nope"}'),
    ("/api/doctor", b"{}"),
    ("/api/settings", b'{"bogus":1}'),
]


def test_the_execution_scoped_count_is_reported_with_its_paths(
        tmp_path, capsys, monkeypatch):
    """Publishes the number AND what it counts, in one place.

    The number on its own is what made 25 and 26 look like a disagreement when
    they were the same measurement in different units.

    `/api/projects` calls `projects.github_status()` -> `pair._owner()` ->
    `gh auth status` / `gh api user`: the only three subprocess invocations in
    a full run that leave the machine (tests/conftest.py, NOT COVERED). Stubbed
    the way test_projects_ui.py stubs it, so this file is hermetic; the strings
    it enumerates are the console's, and a stub returns a comparable shape.
    """
    from crossaudit.console import projects

    monkeypatch.setattr(projects, "github_status", lambda force=False: {
        "connected": False, "owner": None,
        "detail": "GitHub CLI is not signed in on this machine"})
    root = tmp_path / "p"
    root.mkdir()
    cfg = harness.project(root)
    found, executed = harness.drive(cfg, PLAN)

    reached = [row for row in executed if row[3] == ""]
    assert reached, "no path returned JSON; the enumeration proves nothing"

    with capsys.disabled():
        print("\n  EXECUTION-SCOPED ENUMERATION")
        print(f"    unit          distinct values (not occurrences)")
        print(f"    strings       {len(found)}")
        print(f"    paths driven  {len(executed)} ({len(reached)} returned JSON)")
        for path, status, new, note in executed:
            print(f"      {path:24} HTTP {status}  +{new} {note}")

    # Pinned so a drop is deliberate rather than silent. This does NOT claim the
    # console has this many user-facing strings — only that these paths, in this
    # state, produced this many.
    assert len(found) >= 9, (
        f"execution over {len(reached)} paths produced {len(found)} strings; it "
        f"produced at least 9 when measured. A drop means a path stopped "
        f"returning what it did, not that the console has fewer strings.")


def test_the_harness_states_what_its_number_counts():
    """The predicate travels with the number or the number is not a count."""
    doc = harness.__doc__ or ""
    for required in ("shape", "files", "method", "paths", "states", "unit",
                     "WHAT IT CANNOT CLAIM"):
        assert required in doc, f"the predicate no longer states {required!r}"
