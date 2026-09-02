"""The numbers on the dashboard, every one of them derived from the ledger.

A supervision dashboard is the last place a figure should be invented. Each
metric here is computed from committed reports, receipts and controller state,
and where the ledger cannot answer, the answer is absent rather than zero:
"0 escalations" and "we have never looked" are different claims, and only one of
them is safe to show in a large font.

The shape follows what a person actually asks, in order: how much came through,
how much passed, what is stuck, where is the current increment in the loop, and
what is waiting on me.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..controller import StateStore
from ..dcl.framework import CONFIRMED
from ..dispute import DISPUTES_LOG, parse_findings
from ..errors import (CONTESTED_MODEL_BLOCKER_REASON, classify_escalation_kind,
                      escalation_remediations)
from ..cli import i18n
from ..gitio import git, is_repo, read_committed_bytes

VERDICT_RE = re.compile(r"\|\s*verdict\s*\|\s*\*\*(\w+)\*\*")
ROUND_RE = re.compile(r"\|\s*round\s*\|\s*(\d+)")
AUDITOR_RE = re.compile(r"\|\s*auditor\s*\|\s*`([^`]+)`")
CONST_RE = re.compile(r"\|\s*constitution\s*\|\s*`([0-9a-f]+)`")

SEVERITY_ORDER = ("BLOCKER", "ADVISORY")


@dataclass(frozen=True)
class ReportSource:
    """One ``report.md``, and WHOSE bytes these are.

    F1. The console used to read the working copy. `verify` used to as well,
    which meant a report rewritten after its audit made verification fail — an
    accidental detector nobody designed. The verifier merge correctly moved
    `verify` to the commit the receipt cites, and that removed the detector.
    Nothing replaced it, and this file read exactly the rewritten bytes.

    Driven, the consequence was worse than "a person reads edited prose": the
    edit changed the VERDICT the console reported, moved the dashboard
    counters, and injected a fabricated BLOCKER whose hand-typed observation was
    attributed to the independent auditor — the one artifact whose independence
    is the product's central claim.

    So the text is the AUDITED text, and where the working copy disagrees the
    surface says so rather than silently correcting a person who may have had a
    good reason to edit. Both halves matter: showing the audited bytes without
    mentioning the divergence would hide an edit the person made, and mentioning
    the divergence while still rendering the edited bytes would still put
    invented prose under the auditor's name.
    """

    path: Path
    text: str
    commit: str
    on_disk_differs: bool
    #: Whether the RECEIPT named this commit, or we merely asked git which
    #: commit last touched the file. R2: the difference is the whole claim.
    cited: bool = True

    @property
    def state(self) -> str:
        if not self.commit:
            return "uncommitted"
        if not self.cited:
            # R2. The fallback used to report "committed" — it did not merely
            # omit provenance, it ASSERTED it. That is F1's original defect
            # alive in a narrower state: a report rewritten AFTER its audit and
            # then committed is what `git log -1` hands back, and the console
            # presented those bytes as the audited ones.
            #
            # Without a receipt naming the audited commit, the honest statement
            # is that we cannot tell. "A committed version" is not "the version
            # that was audited", and only the receipt knows which.
            return "unverified"
        return "drifted" if self.on_disk_differs else "committed"

    @property
    def note(self) -> str:
        """What to tell the person, or nothing.

        A sentence rather than a status word, and it names the command that
        settles the question — the receipt is honest in every one of these
        cases, so the useful thing to hand someone is the way to check it.
        Emitted in English and translated by the page's own locale layer, which
        is how the rest of this surface handles copy.
        """
        if self.state == "drifted":
            return ("The copy of this report on disk differs from the audited "
                    "one shown here. Run crossaudit verify to check the record.")
        if self.state == "uncommitted":
            return ("This report is not committed yet, so it cannot be "
                    "verified yet.")
        if self.state == "unverified":
            return ("No receipt names the commit this report was audited at, "
                    "so CrossAudit cannot confirm the version shown here is "
                    "the one that was audited. Run crossaudit verify to check "
                    "the record.")
        return ""


@dataclass
class Cycle:
    """One audit round, as the ledger recorded it."""

    directory: str
    sha: str
    round: int
    verdict: str
    findings: list[dict]
    at: int
    auditor: str = ""
    constitution: str = ""
    # Additive, and never inferred: "committed" is only claimed when the bytes
    # rendered came from a commit.
    report_state: str = "committed"
    report_note: str = ""
    #: D148: the route the receipt's authority block recorded for this round
    #: ("automatic-repair", "human-decision", "obtain-audit"), or "" when the
    #: receipt predates the block. Inspector-only: nothing renders the name.
    authority_route: str = ""
    #: Whether the receipt names a contested blocker — a model-only block
    #: the escalate dial handed to a person. THE field the cause reads: every
    #: ESCALATE routes to human-decision, so the route cannot tell the dial
    #: from the auditor's own escalation or an integrity stop.
    authority_contested: bool = False

    @property
    def blockers(self) -> int:
        return sum(1 for f in self.findings if f["severity"] == "BLOCKER")


def _cited_report_commit(cycle_dir: Path) -> str:
    """The commit the RECEIPT cites for this cycle, if it cites one.

    `receipt.json` is written beside `report.md`, so the audited commit is
    reachable without touching the receipt store. This is preferred over asking
    git which commit last touched the file, because those answers differ in
    exactly the case that matters: a report rewritten AND committed — the
    shared-audit-repo path, which needs push access and no local access at all.
    `git log -1` would hand back the rewrite; the receipt still names the audit.
    """
    receipt = cycle_dir / "receipt.json"
    if not receipt.is_file():
        return ""
    try:
        return str(json.loads(receipt.read_text(encoding="utf-8"))
                   .get("ledger", {}).get("report_commit") or "")
    except (OSError, ValueError):
        return ""


def receipt_authority(cycle_dir: Path) -> dict:
    """The receipt's evidence-authority block for this cycle, or ``{}``.

    Same file `_cited_report_commit` reads; the block is verifier-bound, so it
    is preferred over parsing the report's table. Absent for receipts written
    before D148, and then nothing downstream changes.
    """
    receipt = cycle_dir / "receipt.json"
    if not receipt.is_file():
        return {}
    try:
        block = json.loads(receipt.read_text(encoding="utf-8")).get("authority")
    except (OSError, ValueError, AttributeError):
        return {}
    return block if isinstance(block, dict) else {}


_receipt_authority = receipt_authority  # the name the first slice used


def annotate_findings(findings: list[dict], authority: dict) -> list[dict]:
    """Add each finding's evidence tier and whether a deterministic check
    verified it, from the receipt's authority block. In place, and additive.

    Keyed the way `records_from_audit` keys evidence (``rule@artifact``), with
    a rule-only fallback when the report names the artifact differently and
    the rule was raised once. A finding the block does not know is left
    untouched, so an old receipt renders exactly as before. The finding STATE
    is deliberately not copied: no user surface renders a state word.
    """
    records = authority.get("evidence") if authority else None
    if not isinstance(records, list) or not records:
        return findings
    by_key: dict[str, dict] = {}
    by_rule: dict[str, list[dict]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("finding_key", ""))
        by_key.setdefault(key, record)
        by_rule.setdefault(key.split("@", 1)[0], []).append(record)
    for f in findings:
        rule = str(f.get("rule", ""))
        record = by_key.get(f"{rule}@{f.get('artifact', '')}")
        if record is None and len(by_rule.get(rule, [])) == 1:
            record = by_rule[rule][0]
        if record is None:
            continue
        tier = str(record.get("tier", ""))
        if tier not in ("deterministic", "model"):
            continue
        f["tier"] = tier
        # A deterministic finding is verified by construction; a model finding
        # only once something established it (the sidecar's own rule).
        f["verified"] = bool(tier == "deterministic"
                             or record.get("state") == CONFIRMED)
    return findings


def _derived_report_commit(root: Path, rel: str) -> str:
    """Fallback for a cycle whose receipt cites no commit — legacy receipts and
    `--no-write-ledger` runs both produce that. Deliberately a FALLBACK for the
    commit only: it never becomes a fallback to reading the working tree under
    the same presentation, which would be the defect wearing a fallback."""
    try:
        return git("log", "-1", "--format=%H", "--", rel, cwd=root).strip()
    except Exception:
        return ""


def read_report_sources(cfg: Config) -> list[ReportSource]:
    """Every ``*/report.md`` under the ledger, as the AUDITED bytes plus whose
    they are.

    read_cycles and streams.auditor_stream both derive from this same set, so
    there is one reader and the two surfaces cannot disagree about what the
    auditor said — the producer/consumer seam this codebase keeps splitting on.
    """
    ledger = cfg.root / cfg.ledger_dir
    if not ledger.is_dir():
        return []
    repo = is_repo(cfg.root)
    out: list[ReportSource] = []
    for report in ledger.glob("*/report.md"):
        disk = report.read_bytes()
        rel = report.relative_to(cfg.root).as_posix()
        commit = ""
        cited = True
        committed: bytes | None = None
        if repo:
            commit = _cited_report_commit(report.parent)
            if not commit:
                # Derived, not cited. Kept as a way to SHOW something rather
                # than nothing, but never as a way to claim it was audited.
                commit, cited = _derived_report_commit(cfg.root, rel), False
            if commit:
                try:
                    committed = read_committed_bytes(cfg.root, commit, rel)
                except Exception:
                    # The cited commit is unreachable here — a shallow clone, a
                    # ledger copied without its history. Say "uncommitted"
                    # rather than present the working copy as audited.
                    commit, committed, cited = "", None, True
        text = (committed if committed is not None else disk)
        out.append(ReportSource(
            path=report, text=text.decode("utf-8", errors="replace"),
            commit=commit, cited=cited,
            on_disk_differs=committed is not None and committed != disk))
    return out


def read_report_texts(cfg: Config) -> list[tuple[Path, str]]:
    """The audited (path, text) pairs, for callers that do not need provenance.

    Kept as the pair shape it has always been so existing callers are unchanged;
    what changed is WHOSE bytes the text is.
    """
    return [(source.path, source.text) for source in read_report_sources(cfg)]


def read_cycles(cfg: Config,
                reports: list[ReportSource] | None = None) -> list[Cycle]:
    """Every audit the ledger holds, oldest first.

    ``reports`` may carry a pre-read set (see read_report_sources) so a caller
    that already read the reports does not read them again; when absent they are
    read here, preserving the original standalone behaviour.
    """
    out: list[Cycle] = []
    ledger = cfg.root / cfg.ledger_dir
    if not ledger.is_dir():
        return out
    sources = (reports if reports is not None else read_report_sources(cfg))
    for source in sources:
        report, text = source.path, source.text
        name = report.parent.name
        sha, _, _rest = name.partition("-r")
        verdict = (VERDICT_RE.search(text) or [None, "?"])[1] if VERDICT_RE.search(text) else "?"
        round_m = ROUND_RE.search(text)
        aud = AUDITOR_RE.search(text)
        const = CONST_RE.search(text)
        authority = receipt_authority(report.parent)
        out.append(Cycle(
            directory=name, sha=sha, round=int(round_m.group(1)) if round_m else 1,
            verdict=verdict,
            findings=annotate_findings(
                [{"severity": f.severity, "rule": f.rule, "artifact": f.artifact,
                  "observation": f.observation} for f in parse_findings(text)],
                authority),
            at=int(report.stat().st_mtime),
            auditor=aud.group(1) if aud else "",
            constitution=const.group(1) if const else "",
            report_state=source.state, report_note=source.note,
            authority_route=str(authority.get("route", "") or ""),
            authority_contested=bool(authority.get("contested_evidence_ids"))))
    # Cycle directory names begin with a content hash, so lexical order is
    # random with respect to time. The UI's "latest" pipeline must follow the
    # ledger write order, with the protocol round as a deterministic tie-break.
    out.sort(key=lambda c: (
        (ledger / c.directory / "report.md").stat().st_mtime_ns, c.round,
        c.directory))
    return out


def metrics(cfg: Config, cycles: list[Cycle]) -> list[dict]:
    """The headline band. Absent evidence shows as absent, never as zero."""
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    states = store.snapshot().get("cycles", {})
    total = len(cycles)
    passed = sum(1 for c in cycles if c.verdict == "PASS")
    blocked = sum(1 for c in cycles if c.verdict == "BLOCKED")
    escalated = sum(1 for s in states.values() if s["status"] == "ESCALATED")
    admitted = sum(1 for s in states.values() if s["status"] == "CONSUMED")

    def pct(n: int) -> str:
        return f"{n / total:.0%}" if total else ""

    return [
        {"label": "Audits", "value": total, "note": "rounds the ledger holds",
         "tone": "neutral"},
        {"label": "Passed", "value": passed, "badge": pct(passed),
         "note": "cleared both layers", "tone": "good"},
        {"label": "Blocked", "value": blocked, "badge": pct(blocked),
         # Not "a defect was caught": a blocked round means a concern was
         # raised, and until something establishes it that is all the system
         # knows. The old line was the only thing the data structure could
         # offer; now that a finding can be `alleged`, it is checkably false.
         "note": "a concern was raised", "tone": "bad"},
        {"label": "Waiting on you", "value": escalated,
         "note": "escalated; the loop cannot settle these", "tone": "warn"},
        {"label": "Admitted", "value": admitted,
         "note": "receipts consumed, once each", "tone": "good"},
    ]


def pipeline(cfg: Config, cycles: list[Cycle]) -> list[dict]:
    """The five steps of one increment, and where the latest one stopped.

    Steps are marked done, current, failed or pending — never optimistically. A
    step nobody reached is pending, which is a different thing from passing.
    """
    latest = cycles[-1] if cycles else None
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    states = store.snapshot().get("cycles", {})
    status = ""
    if latest:
        for s in states.values():
            if s["active_sha"].startswith(latest.sha):
                status = s["status"]
                break

    def state(done: bool, failed: bool = False, current: bool = False) -> str:
        return ("failed" if failed else "current" if current
                else "done" if done else "pending")

    if latest is None:
        blank = [("Commit", "the generator writes and commits"),
                 ("Checks", "deterministic layer, no model involved"),
                 ("Audit", "a different vendor reads the commit"),
                 ("Verdict", "code decides; the checks dominate"),
                 ("Admission", "a receipt is consumed, once")]
        return [{"title": t, "detail": d, "state": "pending"} for t, d in blank]

    dcl_failed = any(f["rule"].startswith("DCL:")
                     and f["severity"] == "BLOCKER" for f in latest.findings)
    model_ran = latest.verdict != "DCL_ONLY"
    passed = latest.verdict == "PASS"
    admitted = status == "CONSUMED"

    return [
        # The round, not the sha: the run card is a main surface and carries
        # words (D150); the sha stays on the audit detail and the ledger.
        {"title": "Commit", "detail": f"round {latest.round}",
         "state": "done"},
        {"title": "Checks",
         "detail": "clean" if not dcl_failed else "hard failure — final, no model "
                                                 "may waive it",
         "state": state(True, failed=dcl_failed)},
        {"title": "Audit",
         "detail": (latest.auditor or "auditor") if model_ran
                   else "no model ran — cannot be PASS",
         "state": state(model_ran, current=not model_ran)},
        {"title": "Verdict",
         "detail": f"{latest.verdict} · {len(latest.findings)} finding(s)",
         "state": state(passed, failed=latest.verdict in ("BLOCKED", "ESCALATE"))},
        {"title": "Admission",
         "detail": "receipt consumed" if admitted
                   else "waiting: verify the receipt to admit" if passed
                   else "not reached",
         "state": state(admitted, current=passed and not admitted)},
    ]


def findings_by_severity(cycles: list[Cycle]) -> dict:
    counts: dict[str, int] = {}
    for c in cycles:
        for f in c.findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    total = sum(counts.values())
    order = [s for s in SEVERITY_ORDER if s in counts] + [
        s for s in sorted(counts) if s not in SEVERITY_ORDER]
    return {"total": total,
            "rows": [{"severity": s, "count": counts[s],
                      "share": counts[s] / total if total else 0} for s in order]}


def top_rules(cycles: list[Cycle], limit: int = 5) -> list[dict]:
    """Which rules actually catch things — the Constitution's own report card."""
    counts: dict[str, int] = {}
    for c in cycles:
        for f in c.findings:
            counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"rule": r, "count": n} for r, n in ranked]


def _is_auditor_concern(stop_reason: str, latest: Cycle | None) -> bool:
    """Whether this content stop is the escalate dial handing a model-only
    blocker to a person (D148). The receipt's contested ids are the
    structured source — never the route, which every ESCALATE shares; the
    CLI's one sentence is the fallback for a cycle whose receipt is not
    beside its report. A plain ESCALATE keeps the generic copy."""
    if latest is not None and latest.authority_contested:
        return True
    return stop_reason.strip() == CONTESTED_MODEL_BLOCKER_REASON


def escalations(cfg: Config) -> list[dict]:
    """What is waiting on a person, with enough evidence to make a decision.

    An escalation is not merely a yellow status.  The UI must be able to tell
    the human how many automatic rounds ran, what the latest audit still
    rejects, and what kind of intervention can move the work forward.  Every
    field here is reconstructed from controller history and committed reports;
    the view never asks a model to summarize its own failure.
    """
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    state = store.snapshot()
    cycles = read_cycles(cfg)
    out = []
    history = state.get("history", [])
    for cid, s in sorted(state.get("cycles", {}).items()):
        if s["status"] != "ESCALATED":
            continue
        stop_reason = s.get("escalation_reason") or "the automatic audit loop stopped"
        # The kind is a stored, structured field (controller.escalate et al.).
        # Records written before it existed are classified once from the
        # reason here — the one surviving read of the "provider failure"
        # marker, and only for legacy state.
        kind = s.get("escalation_kind") or classify_escalation_kind(stop_reason)
        provider_failure = kind == "provider"
        shas = {str(s.get("root_sha", "")), str(s.get("active_sha", ""))}
        shas.update(str(row.get("sha", "")) for row in history
                    if row.get("cycle") == cid and row.get("sha"))
        related = [c for c in cycles if any(
            sha.startswith(c.sha) or c.sha.startswith(sha) for sha in shas if sha)]
        related.sort(key=lambda c: (c.round, c.at, c.directory))
        latest = related[-1] if related else None
        issues = list(latest.findings[:8]) if latest else []
        cause = str(s.get("escalation_cause", "") or "")
        if not cause and kind == "audit" and _is_auditor_concern(stop_reason, latest):
            # D148, escalate dial: cmd_run/cmd_audit record no cause, but the
            # receipt's route (verifier-bound) and the one sentence they mint
            # both say a model-only blocker was handed to a person. Derived
            # here, once, so the page keys on a field rather than on prose.
            cause = "auditor_concern"
        why = stop_reason
        if cause == "repair_refused":
            # "the automatic repair was refused in round N because <reason>":
            # the guard's own sentence names the file and the pattern, and
            # that is the part a person needs on the screen.
            why = stop_reason.partition(" because ")[2] or stop_reason
        elif latest:
            if latest.verdict == "DCL_ONLY":
                why = "no model audit ran, so the result cannot pass"
            elif issues:
                why = issues[0]["observation"][:220]
        if cause == "repair_refused":
            requested = (
                "Tell the generator to keep the fix inside the audited files, or "
                "stop the task without admitting its output.")
        elif cause == "auditor_concern":
            # Names only what the dialog offers: continue with a reason
            # (Revise) or stop. There is no third control.
            requested = (
                "Review the auditor's concern and its evidence. If it is a "
                "misreading, say so in your reason and continue; if it is right, "
                "tell the generator how to address it; or stop without admitting "
                "the work.")
        elif issues:
            requested = (
                "Tell the generator how to correct the remaining blockers, or stop "
                "the task without admitting its output.")
        elif provider_failure:
            requested = (
                "Retry the provider now, review the model connection first, or stop "
                "the task. No correction guidance is needed because no audit ran.")
        else:
            requested = (
                "Review why the loop stopped, then either give concrete guidance "
                "for one more round or stop the task.")
        out.append({"cycle_id": cid, "sha": s["active_sha"],
                    "short_sha": s["active_sha"][:12],
                    "round": s["round"], "max_rounds": cfg.max_rounds,
                    "limit_reached": s["round"] >= cfg.max_rounds,
                    "chat_id": s.get("chat_id", ""), "why": why,
                    "stop_reason": stop_reason, "issues": issues,
                    # Additive, D130 provenance-first: the Chinese for THIS
                    # stop reason, looked up by the sentence the controller
                    # recorded (a provider refusal is a composite of our own
                    # clauses — the route id and the vendor's words are
                    # carried through). Absent when the table has none, and
                    # the page then renders `why` exactly as before.
                    **({"why_zh": i18n.denial_zh(why)}
                       if i18n.denial_zh(why) is not None else {}),
                    **({"stop_reason_zh": i18n.denial_zh(stop_reason)}
                       if i18n.denial_zh(stop_reason) is not None else {}),
                    "kind": kind,
                    # Structured cause (additive) for human-readable rendering.
                    "cause": cause,
                    "remediations": escalation_remediations(kind),
                    "task": str(s.get("task", ""))[:12000],
                    "attempts": [{"round": c.round, "verdict": c.verdict,
                                  "findings": len(c.findings)} for c in related],
                    "requested": requested})
    return out


def disputes(cfg: Config, limit: int = 5) -> list[dict]:
    path = cfg.root / cfg.ledger_dir / DISPUTES_LOG
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    return [{"rule": r["rule"], "artifact": r["artifact"], "ruling": r["ruling"],
             "reasoning": r["reasoning"][:160], "t": r.get("t", 0)}
            for r in rows[-limit:]]
