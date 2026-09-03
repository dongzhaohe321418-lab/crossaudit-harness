"""Escalation rows built through the REAL recording paths, then the REAL
projection.

Every case here is written the way the product writes it — the same
`StateStore` method, with the same arguments, in the same order the CLI calls
them — and then read back through `console.overview.escalations`, which is the
payload the console is actually handed.

That discipline is not decoration. The previous version of this file built all
fourteen cases with one call, `record_build_escalation(kind=..., cause=...)`,
and the escalation-lock case passed **no `locked_by`**. `overview.py` clears the
cause of a lock whose holder cannot be named, so the row it produced was not a
lock at all — and the console's "Open the earlier decision" button, which opened
a modal, made the shell `inert` and took the composer away, was never rendered
by any test. Two of the eight design rules were broken on a path 2674 green
tests could not reach. A fixture that cannot reproduce the real shape is worse
than no fixture, because it is read as coverage.

So: `CASES` names, for each cause, the product call site it imitates, and
`rows()` asserts the projection came back with the cause and the fields that
case is supposed to carry. A fixture that silently degrades again fails here
rather than passing quietly somewhere else.
"""
import json
import pathlib
import subprocess
import tempfile

from crossaudit.config import load
from crossaudit.console import chats, overview
from crossaudit.controller import StateStore
from crossaudit.errors import (CONTESTED_MODEL_BLOCKER_REASON,
                               NO_SCIENCE_COMMIT_CAUSE, escalation_cause)

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\nmax_rounds: 3\n")
REPORT = """# Audit Report — t/p@{sha}

| | |
|---|---|
| verdict | **{verdict}** |
| round | {round} |
| constitution | `abc123def456` |
| auditor | `openai_compat:gpt` |

## Model findings

{findings}
"""
BLOCKER = ("### [BLOCKER] CA-TXT-001 — work/review.md\n"
           "The cited speed-up is not in the paper.\n")

#: The stop reason each case carries, as the ENGINE mints it — never an
#: invented sentence. A fixture that writes its own English hides exactly the
#: defect this file exists to expose: an escalation_reason painted, unopened,
#: into a Chinese first paint (`build round budget spent (3)` was).
DEFAULT_REASON = "build round budget spent (3)"          # cli/build.py
REASONS = {
    "auditor_concern": CONTESTED_MODEL_BLOCKER_REASON,   # errors.py
    "no_progress": "generator produced no new auditable revision in round 2",
    "repair_refused": ("the automatic repair was refused in round 2 because "
                       "work/a.md is a binary file written directly by the "
                       "generator, which cannot be reviewed line by line"),
    # cli/build.py mints both of these with an English lead and the provider's
    # own reason after the colon.
    "generator_format": ("the generator could not produce auditable work in "
                         "round 2: no fenced file block in the reply"),
    "generator_refused": ("the generator's request was refused in round 2: "
                          "the configured model is not available to this key"),
    "answered": "the generator answered conversationally and produced no increment",
    "nothing_audited": "nothing was produced in the audited directories",
    "provider": ("generator provider failure in round 2: all configured "
                 "generator provider routes failed. anthropic"),
    "budget": "usage guardrail: the daily limit was reached",
    "escalation_locked": "",           # _record_lock records the lock with no reason
    "no_science_commit": "that commit had no experiment in it",
}

#: The words in the fixtures above that a PROVIDER or a MODEL wrote, not the
#: engine. They are never translated — that is the design's rule, and the
#: exemption is by identity (this exact string came back from a provider),
#: never by a predicate that would also exempt an engine sentence for looking
#: English. A rule-7 test that walks painted text reads this list.
PROVIDER_TEXT = (
    "no fenced file block in the reply",
    "the configured model is not available to this key",
    "all configured generator provider routes failed. anthropic",
)

SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
#: One commit per round, because that is what a revision IS: the loop advances
#: a cycle with `open_or_advance(sha, parent_sha=previous)`, and the store
#: refuses to advance one on the same commit twice.
ROUND_SHAS = [SHA,
              "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
              "c3d4e5f60718293a4b5c6d7e8f90123456789012"]
HOLDER_SHAS = ["0f1e2d3c4b5a69788796a5b4c3d2e1f001234567",
               "1f2e3d4c5b6a79880897a6b5c4d3e2f102345678"]

#: (name, how) — `how` names the PRODUCT call site each case reproduces.
#: `ladder`  cli/main.py::_record_round -> record_verdict(escalation_cause=...)
#: `build`   cli/build.py::_escalate    -> escalate(kind=, cause=)
#: `anchor`  cli/build.py::_escalate    -> record_build_escalation (no cycle yet)
#: `setup`   cli/main.py::cmd_run       -> record_build_escalation(no_science_commit)
#: `lock`    cli/main.py::_record_lock  -> record_build_escalation(locked_by=holder)
CASES = [
    ("provider",          dict(how="build", kind="provider", cause="provider_unavailable")),
    ("budget",            dict(how="build", kind="budget", cause="budget")),
    ("invalid_reply",     dict(how="ladder", integrity="INVALID_REPLY")),
    ("nothing_audited",   dict(how="ladder", integrity="NOTHING_AUDITED")),
    ("bounds_exceeded",   dict(how="ladder", integrity="BOUNDS_EXCEEDED")),
    ("auditor_concern",   dict(how="ladder", integrity="OK", contested=True)),
    ("auditor_escalated", dict(how="ladder", integrity="OK", model_verdict="ESCALATE")),
    ("no_science_commit", dict(how="setup")),
    ("generator_format",  dict(how="build", kind="audit", cause="generator_format")),
    ("generator_refused", dict(how="build", kind="audit", cause="generator_refused")),
    ("no_progress",       dict(how="build", kind="audit", cause="no_progress")),
    ("repair_refused",    dict(how="build", kind="audit", cause="repair_refused")),
    ("answered",          dict(how="build", kind="audit", cause="answered")),
    ("limit_reached",     dict(how="ladder", integrity="OK", rounds=3)),
    ("escalation_locked", dict(how="lock")),
    ("provider_no_cycle", dict(how="anchor", kind="provider",
                               cause="provider_unavailable")),
]

#: What the projection MUST carry for each case, so a fixture cannot degrade
#: into a differently-shaped row and still be counted as coverage.
EXPECTED = {
    "provider": {"cause": "provider_unavailable", "kind": "provider"},
    "provider_no_cycle": {"cause": "provider_unavailable", "kind": "provider"},
    "budget": {"cause": "budget", "kind": "budget"},
    "invalid_reply": {"cause": "invalid_reply"},
    "nothing_audited": {"cause": "nothing_audited"},
    "bounds_exceeded": {"cause": "bounds_exceeded"},
    "auditor_concern": {"cause": "auditor_concern"},
    "auditor_escalated": {"cause": "auditor_escalated"},
    "no_science_commit": {"cause": "no_science_commit"},
    "generator_format": {"cause": "generator_format"},
    "generator_refused": {"cause": "generator_refused"},
    "no_progress": {"cause": "no_progress"},
    "repair_refused": {"cause": "repair_refused"},
    "answered": {"cause": "answered"},
    "limit_reached": {"limit_reached": True},
    # The whole point of this file: a lock that is really a lock.
    "escalation_locked": {"cause": "escalation_locked", "earlier_cycle_id": str},
}


def make(tmp: pathlib.Path):
    root = tmp / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-TXT-001\n**BLOCKER.** exact\n\nx\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    return load(root / "crossaudit.yml")


def add_audit(cfg, sha, verdict, findings="", round_=1):
    d = cfg.root / cfg.ledger_dir / f"{sha}-r{round_}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.md").write_text(
        REPORT.format(sha=sha, verdict=verdict, round=round_, findings=findings))
    return d


def _open_to_round(store, cfg, shas, rounds):
    """Advance a cycle to `rounds` the way the loop does: one BLOCKED verdict
    and one new revision commit per round. Returns (cycle_id, active_sha)."""
    cycle = store.open_or_advance(cfg.science_repo, shas[0], None)
    for i in range(1, rounds):
        store.record_verdict(cycle["cycle_id"], shas[i - 1], "BLOCKED", "r" * 64,
                             cfg.max_rounds)
        cycle = store.open_or_advance(cfg.science_repo, shas[i], shas[i - 1])
    return cycle["cycle_id"], shas[rounds - 1]


def _record(store, cfg, name, spec):
    """Reproduce ONE product call site."""
    how = spec["how"]
    task = "Write the cache-warming review."
    reason = REASONS.get(name, DEFAULT_REASON)
    if how == "ladder":
        # cli/main.py::_record_round — the ladder's own cause, from the ladder's
        # own inputs, through record_verdict.
        rounds = int(spec.get("rounds", 2))
        cid, sha = _open_to_round(store, cfg, ROUND_SHAS, rounds)
        cause = escalation_cause(integrity=spec.get("integrity", "OK"),
                                 verdict="ESCALATE",
                                 model_verdict=spec.get("model_verdict", ""),
                                 contested=bool(spec.get("contested")))
        store.record_verdict(cid, sha, "ESCALATE", "h" * 64, cfg.max_rounds,
                             escalation_reason=reason, escalation_cause=cause)
        return
    if how == "build":
        # cli/build.py::_escalate, cycle branch.
        cid, _sha = _open_to_round(store, cfg, ROUND_SHAS, 2)
        store.escalate(cid, reason, task=task, kind=spec["kind"],
                       cause=spec["cause"])
        return
    if how == "anchor":
        # cli/build.py::_escalate, no-cycle branch (a provider refused every
        # generator attempt, so there is no work commit to open).
        store.record_build_escalation(cfg.science_repo, SHA, reason, 2, "c1",
                                      task, kind=spec["kind"], cause=spec["cause"])
        return
    if how == "setup":
        # cli/main.py::cmd_run — a commit with no experiment in it.
        store.record_build_escalation(cfg.science_repo, SHA, reason, 1, "c1",
                                      task, kind="audit",
                                      cause=NO_SCIENCE_COMMIT_CAUSE)
        return
    if how == "lock":
        # cli/main.py::_record_lock. The holder FIRST — a real, unsettled
        # decision on its own commit — then the refused commit's own decision
        # object naming it. Without the holder the store has nothing to point
        # at and overview.py rightly strips the cause.
        holder, holder_sha = _open_to_round(store, cfg, HOLDER_SHAS, 2)
        store.record_verdict(holder, holder_sha, "ESCALATE", "h" * 64,
                             cfg.max_rounds,
                             escalation_reason=REASONS["auditor_concern"],
                             escalation_cause="auditor_concern")
        store.record_build_escalation(cfg.science_repo, SHA, "", 1, "c1", task,
                                      kind="audit", cause="escalation_locked",
                                      locked_by=holder)
        return
    raise AssertionError(f"unknown recording path {how!r}")


#: The thread these decisions belong to. `console/server.py` stamps every
#: escalation row with `chats.canonical_id(row.chat_id or cycle_chats[cycle])`
#: before the console ever sees it, so a fixture that stops at
#: `overview.escalations` is handing the page a payload the page is never
#: handed. That line is reproduced here, with the conversation that owns the
#: cycle, rather than a chat id typed into a dict.
CHAT = "c1"


def _projected(cfg) -> list:
    rows = overview.escalations(cfg)
    for row in rows:
        row["chat_id"] = chats.canonical_id(row.get("chat_id") or CHAT)
    return rows


def _check(name, row):
    """The projection carries what this case is supposed to carry."""
    for field, want in EXPECTED.get(name, {}).items():
        got = row.get(field)
        if want is str:
            assert isinstance(got, str) and got, (
                f"{name}: {field} is {got!r}; this fixture no longer builds the "
                f"state the product builds")
        else:
            assert got == want, (
                f"{name}: {field} is {got!r}, expected {want!r} — the fixture "
                f"has drifted from the product's own recording path")


def rows():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for name, spec in CASES:
            tmp = pathlib.Path(td) / name
            tmp.mkdir()
            cfg = make(tmp)
            add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER, 2)
            store = StateStore(cfg.root / cfg.state_dir / "state.json")
            _record(store, cfg, name, spec)
            got = _projected(cfg)
            if not got:
                out[name] = {"error": "no escalation row"}
                continue
            # The lock case records TWO decisions; the row under test is the
            # locked one, which is the one that carries `earlier_cycle_id`.
            row = next((r for r in got if r.get("cause") == "escalation_locked"),
                       got[0]) if name == "escalation_locked" else got[0]
            _check(name, row)
            out[name] = row
        # The lock in the shape a person actually meets it: BOTH rows, in the
        # order the console lists them, so a render sees the holder's row and
        # the locked row on one screen.
        out["_lock_pair"] = _lock_pair(pathlib.Path(td))
    return out


def _lock_pair(td: pathlib.Path) -> list:
    tmp = td / "lockpair"
    tmp.mkdir()
    cfg = make(tmp)
    add_audit(cfg, SHA[:12], "BLOCKED", BLOCKER, 2)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    _record(store, cfg, "escalation_locked", dict(how="lock"))
    got = _projected(cfg)
    assert len(got) == 2, f"a lock is two open decisions, got {len(got)}"
    assert any(r.get("cause") == "escalation_locked" and r.get("earlier_cycle_id")
               for r in got), got
    return got


_CACHE: dict | None = None


def cached_rows() -> dict:
    """`rows()` once per process — sixteen git inits is enough of them."""
    global _CACHE
    if _CACHE is None:
        _CACHE = rows()
    return _CACHE


if __name__ == "__main__":
    print(json.dumps(rows(), indent=1, default=str))
