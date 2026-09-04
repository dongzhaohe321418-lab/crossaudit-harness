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
import os
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


# --------------------------------------------------------------- chat list
#: The chat list is a column of rows, and each of the six shapes below broke a
#: different part of it in 4.17.0. They are built the only way this module
#: builds anything: by driving the product's own recorders — `chats.create` /
#: `touch` / `archive` for the navigation record, a Git trailer for a thread's
#: durable anchor, `StateStore` for the cycle whose status becomes a dot, and
#: a plain untrailered commit plus its report for the legacy thread. A row is
#: then read back through `console/server.snapshot`, whose `chats` slice is
#: exactly what the sidebar renders.
LONG_CJK = "生成一个钙钛矿太阳能电池稳定性研究的详细综述，并附上引用来源"
#: The owner's own two examples, which have to stay distinguishable from each
#: other at the sidebar's real width — the bar this list is judged against.
OWNER_CJK = ("生成一个钙钛矿的综述", "写一个详细的实验方案")
LONG_LATIN = ("Write a detailed review of perovskite solar-cell stability "
              "with citations to the primary literature")


class _Clock:
    """The wall clock the product reads, held still.

    A thread's `updated` is written by the product at the moment the person
    touches it, so the only honest way to get a thread that is twelve hours
    old is to touch it twelve hours ago. Nothing here writes a timestamp into
    a row; it only moves the clock the recorders read.
    """

    def __init__(self, now: int):
        self.now = now

    def __call__(self) -> float:
        return float(self.now)


def chat_list(tmp: Path, now: int | None = None, noise: int = 0):
    """A project whose sidebar holds every chat-row shape that has broken.

    Returns ``(cfg, ids)``: the legacy thread, a chat with a status dot (a
    blocked cycle), a chat without one (nothing has run in it), a very long
    CJK title, a very long Latin title, and an archived row.

    ``noise`` adds that many later commits and reports belonging to a real
    thread. The streams are windowed, so enough of them push every legacy row
    out of the window — the state in which the legacy thread lost its date.
    """
    import time as _time
    from unittest import mock

    now = int(_time.time()) if now is None else int(now)
    root = tmp / "proj"
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    (root / "AUDIT_RULES.md").write_text(RULES)
    (root / "crossaudit.yml").write_text(CONFIG)
    (root / "work").mkdir()
    cfg = load(root / "crossaudit.yml")
    clock = _Clock(now)

    def at(seconds_ago: int):
        clock.now = now - seconds_ago
        return mock.patch("time.time", clock)

    def commit(message: str, seconds_ago: int, chat_id: str | None = None):
        _git(root, "add", "-A")
        when = str(now - seconds_ago)
        body = message + (f"\n\nCrossAudit-Chat: {chat_id}\n" if chat_id else "")
        env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "-m", body], cwd=root, check=True,
                       text=True, capture_output=True, env={**os.environ, **env})
        return _git(root, "rev-parse", "HEAD")

    def report(sha: str, verdict: str, round_: int, seconds_ago: int):
        d = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{round_}"
        d.mkdir(parents=True, exist_ok=True)
        path = d / "report.md"
        path.write_text(REPORT.format(sha=sha[:12], verdict=verdict,
                                      round=round_, findings=""))
        os.utime(path, (now - seconds_ago, now - seconds_ago))

    # The legacy thread: work committed before the chat trailer existed, and
    # the audit report about it. Nothing here carries a chat id, which is
    # precisely what makes it the legacy thread's.
    (root / "work" / "legacy.md").write_text("before threads\n")
    legacy_sha = commit("Reviewed the first draft", 40 * 86400)
    report(legacy_sha, "PASS", 1, 40 * 86400)

    ids: dict[str, str] = {"legacy": chats.LEGACY_CHAT_ID}
    # A chat with a status dot: a real thread with a blocked cycle behind it.
    with at(12 * 3600):
        ids["dot"] = chats.create(cfg, "Cache-warming review")["id"]
        chats.touch(cfg, ids["dot"], "Write the cache-warming review.")
    (root / "work" / "review.md").write_text("draft\n")
    blocked_sha = commit("Drafted the cache-warming review. (round 1)",
                         12 * 3600, ids["dot"])
    report(blocked_sha, "BLOCKED", 1, 12 * 3600)
    with at(12 * 3600):
        store = StateStore(cfg.root / cfg.state_dir / "state.json")
        cycle = store.open_or_advance(cfg.science_repo, blocked_sha, None)
        store.record_verdict(cycle["cycle_id"], blocked_sha, "BLOCKED",
                             "s" * 64, cfg.max_rounds)
    # A chat with no dot: nothing has ever run in it, so its status is "ready".
    with at(3 * 86400):
        ids["plain"] = chats.create(cfg, "Notes")["id"]
        chats.touch(cfg, ids["plain"], "Notes on the reviewer's comments.")
    with at(5 * 60):
        ids["cjk"] = chats.create(cfg, LONG_CJK)["id"]
        chats.touch(cfg, ids["cjk"], LONG_CJK)
    with at(14 * 86400):
        ids["latin"] = chats.create(cfg, LONG_LATIN)["id"]
        chats.touch(cfg, ids["latin"], LONG_LATIN)
    for key, title, hours in (("owner_a", OWNER_CJK[0], 4),
                              ("owner_b", OWNER_CJK[1], 6)):
        with at(hours * 3600):
            ids[key] = chats.create(cfg, title)["id"]
            chats.touch(cfg, ids[key], title)
    with at(2 * 86400):
        ids["archived"] = chats.create(cfg, "Older figure pass")["id"]
        chats.touch(cfg, ids["archived"], "Redo figure 2.")
        chats.archive(cfg, ids["archived"])
    for i in range(noise):
        (root / "work" / f"n{i}.md").write_text(str(i))
        sha = commit(f"Revised the review. (round {i + 1})", 3600, ids["dot"])
        report(sha, "PASS", i + 1, 3600)
    return cfg, ids


def chat_rows(cfg) -> dict:
    """The sidebar's own chat slice, through `console/server.snapshot`."""
    return server.snapshot(cfg)["chats"]


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
