"""Console rows produced by the PRODUCT, and the shapes they come in.

Three times in this rebuild a guard was green over a branch reality never
takes, because a fixture hand-wrote a projection row and gave it a field the
wire does not carry:

* the modal fixture was one keyword short (`kind=`), so a whole cause was
  reclassified;
* the escalation-lock fixture had no `locked_by`, so `overview.py` stripped the
  cause and the button that opened a dialog over the composer never rendered;
* every auditor-row fixture set `sha`, which `console/streams.py` did not emit,
  so `cycleReports`' matching branch was exercised only by tests and production
  always fell through to a fallback that shows an *earlier* cycle's rule ids
  and provenance note under the decision a person is being asked to overrule.

Each time the assertion was right and the state was fiction. So no fixture in
this suite hand-writes a projection row any more. This module builds a real
project on disk, drives the product's own recorders, reads the result back
through the exact calls `console/server.py::snapshot` makes, and hands out:

* ``rows(kind)``   — the production rows of a kind, as the console gets them;
* ``TEMPLATES``    — the key sets production emits per kind (one entry per
                     legitimate variant, e.g. an auditor report vs a dispute);
* ``row(kind, **overrides)`` — a fixture row built FROM a production row.
  An override naming a key production does not emit raises. That is the whole
  point: a fixture can no longer invent a field, and cannot omit one either.

`tests/harness/real_stops.py` does the same job for recorded stops.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from crossaudit import dispute as dispute_mod
from crossaudit import router as router_mod
from crossaudit.config import load
from crossaudit.console import chats, overview, server, streams
from crossaudit.controller import StateStore

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\nmax_rounds: 3\n")
RULES = ("### CA-TXT-001\n**BLOCKER.** exact\n\nx\n\n"
         "### CA-TXT-002\n**BLOCKER.** exact\n\ny\n")
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
BLOCKER = ("### [BLOCKER] {rule} — work/review.md\n"
           "{observation}\n")
CHAT = "c1"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True,
                          capture_output=True).stdout.strip()


def _commit(root: Path, message: str, chat_id: str = CHAT) -> str:
    """A generator commit, with the chat trailer the console reads."""
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "-m", f"{message}\n\nCrossAudit-Chat: {chat_id}\n")
    return _git(root, "rev-parse", "HEAD")


def build(tmp: Path):
    """One project with two audited cycles: a settled PASS and a BLOCKED one.

    Enough to produce every conversation row kind the stream renders.
    """
    root = tmp / "proj"
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    (root / "AUDIT_RULES.md").write_text(RULES)
    (root / "crossaudit.yml").write_text(CONFIG)
    (root / "work").mkdir()
    (root / "work" / "review.md").write_text("first\n")
    sha_a = _commit(root, "Drafted the cache-warming review. (round 1)")
    (root / "work" / "review.md").write_text("second\n")
    sha_b = _commit(root, "Revised the cache-warming review. (round 2)")
    cfg = load(root / "crossaudit.yml")

    def report(sha: str, verdict: str, round_: int, findings: str = "") -> None:
        d = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{round_}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "report.md").write_text(REPORT.format(
            sha=sha[:12], verdict=verdict, round=round_, findings=findings))

    report(sha_a, "PASS", 1)
    report(sha_b, "BLOCKED", 2, BLOCKER.format(
        rule="CA-TXT-002", observation="The cited speed-up is not in the paper."))

    # The person's own words reach the console only through the routing
    # ledger, written by `router.record` — the same call `cli/talk.py` makes
    # for every utterance. A hand-written `you` row would be the fourth
    # fixture-shaped state in this rebuild.
    for lane, text, executed in (
            ("build", "Write the cache-warming review.", "queued"),
            ("chat", "What does the auditor check for?",
             "answered by generator: It checks the constitution."),
            ("auditor", "Why was that blocked?",
             "answered by auditor: The speed-up is not in the paper.")):
        router_mod.record(
            cfg.root / cfg.ledger_dir / "routing.jsonl",
            router_mod.Routing(utterance=text, lane=lane, confidence=0.98,
                               reasoning="clear", restated=text, t=1700000000,
                               chat_id=CHAT),
            executed)

    # A dispute ruling, through `dispute.record` — the other `kind: auditor`
    # row `console/streams.py` builds, and the one whose shape used to differ.
    dispute_mod.record(
        cfg.root / cfg.ledger_dir / dispute_mod.DISPUTES_LOG,
        dispute_mod.Ruling(finding_key="CA-TXT-002@work/review.md",
                           rule="CA-TXT-002", artifact="work/review.md",
                           grounds="the figure is in table 2",
                           ruling="WITHDRAWN",
                           reasoning="The reviewer accepted the citation.",
                           note="", cycle_id="r2", t=1700000100))

    # The ledger is committed, as the loop commits it, so `report_state` is
    # "committed" here the way it is in a healthy project. A fixture that wants
    # the drift note overrides `report_note` on the row it asks for.
    _commit(root, "audit: record the reports")

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    first = store.open_or_advance(cfg.science_repo, sha_a, None)
    store.record_verdict(first["cycle_id"], sha_a, "PASS", "r" * 64,
                         cfg.max_rounds)
    second = store.open_or_advance(cfg.science_repo, sha_b, sha_a)
    store.record_verdict(second["cycle_id"], sha_b, "BLOCKED", "s" * 64,
                         cfg.max_rounds)
    return cfg, {"a": sha_a, "b": sha_b}


#: One run projection carrying a condensation notice, so `generator_stream`
#: emits the `context_condensed` row too — `turn()` reads `m.summary_i18n` off
#: it, and a field only a fixture produces is a branch only a fixture visits.
PROGRESS = {
    "run_id": "r1", "chat_id": CHAT, "state": "GENERATING", "finished": False,
    "outcome": "", "elapsed": 12, "task": "Write the review.", "queued": 0,
    "started": 0, "updated": 0, "waiting_reason": None,
    "steps": [{"kind": "context_condensed", "actor": "loop", "t": 1700000200,
               "text": "Context reduced", "detail": "work/review.md",
               "round_no": 1, "round_limit": 3, "event_id": 7,
               "state": "GENERATING"}],
}


def snapshot(cfg) -> dict:
    """The conversation slice of `/api/state`, through server.snapshot's own
    calls, in the same order and with the same sharing."""
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    controller_state = store.snapshot()
    report_texts = overview.read_report_sources(cfg)
    gen_stream, aud_stream, commit_chats = streams.bundle(
        cfg, reports=report_texts, progress=PROGRESS)
    cycles = server._ordered_cycles(controller_state, commit_chats)
    cycle_chats = {row["id"]: row["chat_id"] for row in cycles}
    escalation_rows = overview.escalations(cfg)
    for row in escalation_rows:
        row["chat_id"] = chats.canonical_id(
            row.get("chat_id") or cycle_chats.get(row["cycle_id"]))
    return {"generator_stream": gen_stream, "auditor_stream": aud_stream,
            "cycles": cycles, "escalations": escalation_rows}


_CACHE: dict | None = None


def produced() -> dict:
    """The snapshot slice, built once per process."""
    global _CACHE
    if _CACHE is None:
        with tempfile.TemporaryDirectory() as td:
            cfg, shas = build(Path(td))
            snap = snapshot(cfg)
        _CACHE = {"snapshot": snap, "shas": shas}
    return _CACHE


def rows(kind: str) -> list[dict]:
    """Every production row of a kind, newest last."""
    snap = produced()["snapshot"]
    out = [r for r in snap["generator_stream"] + snap["auditor_stream"]
           if r.get("kind") == kind]
    if kind == "cycle":
        return list(snap["cycles"])
    return out


def _templates() -> dict[str, list[frozenset]]:
    snap = produced()["snapshot"]
    out: dict[str, list[frozenset]] = {}
    for row in snap["generator_stream"] + snap["auditor_stream"]:
        out.setdefault(str(row.get("kind", "")), [])
        keys = frozenset(row)
        if keys not in out[str(row.get("kind", ""))]:
            out[str(row.get("kind", ""))].append(keys)
    for row in snap["cycles"]:
        out.setdefault("cycle", [])
        if frozenset(row) not in out["cycle"]:
            out["cycle"].append(frozenset(row))
    return out


#: The shapes the console is handed, keyed by row kind. Declared variants only:
#: a kind whose rows differ in SHAPE has more than one entry, and the reason is
#: named in DECLARED_VARIANTS below.
TEMPLATES: dict[str, list[frozenset]] = {}

#: A row kind whose production shape legitimately varies, and why. Anything not
#: named here that varies is an accident, and `test_activity_stream` says so.
#:
#: Empty on purpose. `kind: "auditor"` used to be two shapes — an audit report
#: and a dispute ruling — and `row["report_state"]` raised on half of them.
#: `console/streams.py` gives both the same keys now, so every kind has exactly
#: one shape and a consumer can be written without knowing which half it has.
DECLARED_VARIANTS: dict[str, str] = {}


def templates() -> dict[str, list[frozenset]]:
    global TEMPLATES
    if not TEMPLATES:
        TEMPLATES = _templates()
    return TEMPLATES


def row(kind: str, *, for_sha: str | None = None, index: int = -1,
        **overrides) -> dict:
    """A fixture row built from a PRODUCTION row of `kind`.

    Values may be overridden; keys may not be invented, and none may be
    dropped. A `KeyError` here means the fixture is describing a state the
    product cannot produce — which is the failure this module exists to make
    impossible rather than merely unlikely.
    """
    produced_rows = rows(kind)
    assert produced_rows, f"the product produced no {kind!r} row to build from"
    if for_sha is not None:
        # Selected by the commit it is about, never by position: cycle ids are
        # hashes, so `_ordered_cycles` breaks a same-second tie by hash and the
        # order of two cycles recorded in one second is not stable.
        matched = [r for r in produced_rows
                   if r.get("sha") and (for_sha.startswith(str(r["sha"]))
                                        or str(r["sha"]).startswith(for_sha))]
        assert matched, f"no production {kind!r} row for {for_sha!r}"
        base = dict(matched[-1])
    else:
        base = dict(produced_rows[index])
    unknown = sorted(set(overrides) - set(base))
    if unknown:
        raise KeyError(
            f"{kind!r} rows do not carry {unknown} on the wire "
            f"(console/streams.py emits {sorted(base)}). A fixture that sets "
            f"a field production never sends tests a branch production never "
            f"takes.")
    base.update(overrides)
    return base


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        cfg, shas = build(Path(td))
        print(json.dumps(snapshot(cfg), indent=1, default=str))
