"""Every event kind the engine can emit, read FROM THE SOURCE.

Design rule 6 — *a new event kind declares its shape, or it is not rendered* —
is only a rule if something notices. A hand-written list in a test notices
nothing: it is written once by the person who already knew, and it goes stale
the first time someone adds an ``emit()``. So the kinds are enumerated by
reading the files that emit them, with one targeted pattern per file.

The patterns are deliberately narrow. ``kind=`` appears in this codebase for
escalation kinds (``kind="audit"``), waiting-reason kinds (``kind="provider"``)
and SQL placeholders (``kind=?``) that are not run events at all, so only the
modules that actually construct run events are swept, and only through the
call shapes they use.

WHAT IT CANNOT CLAIM: a kind assembled at runtime from a variable — the
auditor's ``narrate(kind, ...)`` forwarder in ``build.py`` is one — is invisible
to a reader of source text. Those arrive here through the module that *names*
them (``auditor/run.py``), which is where a person adding one would type it.
"""
from __future__ import annotations

import re
from pathlib import Path

#: file (relative to ``src/crossaudit``) -> the pattern that names a kind in it.
SOURCES: dict[str, str] = {
    # The audit loop's own narration.
    "cli/build.py": r'emit\("([a-z_]+)"',
    # Phases the auditor and the intake narrate through on_event.narrate.
    "auditor/run.py": r'narrate\("([a-z_]+)"',
    "console/intake.py": r'narrate\("([a-z_]+)"',
    # The run journal's own lifecycle rows, and the run-command service's.
    "runtime/runs.py": r'kind=["\']([a-z_]+)["\']',
    "runtime/commands.py": r'kind=["\']([a-z_]+)["\']',
    # The one run event the HTTP layer appends (an upload arriving mid-run).
    "console/server.py": r'kind=["\']([a-z_]+)["\'],\s*\n?\s*actor=',
    # The conversation messages the console projects for the page.
    "console/streams.py": r'"kind":\s*"([a-z_]+)"',
}

#: Kinds a reader of source text cannot see, with why each is invisible.
#: Every one is a real kind the page must still declare a shape for.
UNREADABLE = {
    # RunEvent's own dataclass default: a step whose emitter named no kind.
    "activity": "runtime/events.py RunEvent.kind default",
}


def source_root() -> Path:
    from crossaudit import console  # noqa: F401  (locate the installed tree)

    return Path(console.__file__).parents[1]


def emitted_kinds() -> dict[str, set[str]]:
    """{kind: {the files that name it}} for every kind the engine can emit."""
    root = source_root()
    found: dict[str, set[str]] = {}
    for rel, pattern in SOURCES.items():
        text = (root / rel).read_text(encoding="utf-8")
        for kind in re.findall(pattern, text):
            found.setdefault(kind, set()).add(rel)
    for kind, why in UNREADABLE.items():
        found.setdefault(kind, set()).add(why)
    return found
