"""`crossaudit build` — the closed loop (DESIGN.md §8, a3).

The user states a task once. The generator writes, the work is committed, the
auditor judges it, and if it was blocked the findings go back to the generator
for another round — until PASS, or until the round budget hands it to a human.

What the user sees is a narration. What the ledger receives is unchanged: every
round is a commit, every verdict a report and a receipt, every escalation a
decision waiting for a person. The box is opaque to interact with and glass on
the inside.

Two things this verb refuses to do, both deliberate:

* **It never lifts a rule to make progress.** A blocked round is returned to the
  generator, never to the rulebook. Loosening a rule is an amendment, which is a
  human's lane and takes effect only between cycles.
* **It stops at the round budget.** Three failed rounds mean the loop cannot
  resolve this itself, which is exactly what I5 is for: escalate rather than
  spin.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import time

from .. import document_export, hpc, mcp
from ..broker import secretscan
from ..context import shape_work
from ..broker.humanapproval import INBOX, HumanApprovalGate
from ..broker.routing import (
    BROKER_SERVER_ID, broker_tool_call, build_broker_and_token, build_catalog,
    compute_authorized, run_commands_authorized, writes_authorized)
from .. import generator as gen_mod
from .. import skills as skills_mod
from ..config import Config, heterogeneity, load
from ..controller import StateStore
from ..dcl import describe as describe_checks
from ..errors import (EXIT_ESCALATED, EXIT_OK, ConfigDenial, Denial,
                      ProviderDenial, park_escalation_kind)
from ..file_identity import AppliedFiles
from ..gitio import git, git_bytes, is_repo
from . import i18n as _i18n
from .i18n import t
from ..providers import resilience as provider_resilience
from ..repair_guard import RepairGuard
from ..runtime import (
    PROVIDER_WAIT_CATEGORIES,
    PreparedRun,
    RunCommandService,
    RunEvent,
    RunJournal,
    RunState,
    journal_path,
    waiting_kind,
)
from ..usage import check_budget_warnings, record_completion
from .main import ALLOW_CUSTOM_ENV, cmd_run

TASK_FILE = "TASK.md"
MAX_AGENT_JOBS_PER_BUILD = 20
MAX_MCP_CALLS_PER_BUILD = 40


def usage_attribution(cfg: Config, live: dict | None, started: float | None = None) -> dict:
    """A copy of the loop's live attribution plus duration and price overrides."""
    context = dict(live or {})
    if started is not None:
        context["duration_ms"] = int((time.monotonic() - started) * 1000)
    prices = getattr(cfg, "prices", None)
    if prices:
        context["prices"] = prices
    return context


def _generator_complete(cfg: Config, allow_custom: bool, on_event=None,
                        heartbeat=None, usage_context: dict | None = None):
    """A `complete(system, prompt)` bound to the generator role.

    The generator role needs its own credential; falling back to the auditor's
    would put one key behind both ends of a loop whose whole premise is that the
    ends are separate.

    ``usage_context`` is a live mapping the loop keeps current (run id, chat id,
    round, cycle id); each completion is recorded with a copy of it, so the
    usage ledger can be read back per run, per cycle and per chat.
    """
    primary = provider_resilience.generator_role(cfg)

    def complete(*, system: str, prompt: str):
        # A provider turn can be silent for minutes; the lease renewal at its
        # boundary is what distinguishes "slow model" from "hung worker".
        if heartbeat is not None:
            heartbeat()
        started = time.monotonic()
        reply = provider_resilience.complete(
            cfg, "generator", primary, system=system, prompt=prompt,
            allow_custom=allow_custom, on_event=on_event)
        if heartbeat is not None:
            heartbeat()
        route = provider_resilience.route_from_reply(reply, primary)
        complete.last_route = route
        record_completion(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                          phase="generation", vendor=route["vendor"],
                          provider=route["provider"], model=route["model"], reply=reply,
                          system=system, prompt=prompt, base_url=route.get("base_url"),
                          context=usage_attribution(cfg, usage_context, started))
        return reply

    complete.last_route = None
    return complete


#: How many of the most-recent tool / compute results are kept verbatim in the
#: generator prompt. Older ones are folded to a hash+length marker so a long,
#: tool-heavy run stops re-serializing every past result into every later round.
KEEP_RECENT_RESULTS = 6


#: Fields that vary run-to-run (a fresh random id, a per-run ordinal) and would
#: otherwise make the folded marker non-deterministic. Stripped before the
#: fingerprint/preview so an identical run folds to identical text.
_VOLATILE_RESULT_FIELDS = ("call_id", "id", "ordinal")


def _fold_results(results: list[dict], on_condense=None) -> list[dict]:
    """Keep the most-recent results verbatim; condense older ones deterministically.

    Each older entry becomes a compact marker: the tool name, its byte length, a
    stable content fingerprint, and a short preview — so a long, tool-heavy run
    stops re-serializing every past result into every later prompt. The recent
    tail stays verbatim; if the generator needs an older result in full it
    re-runs the tool (the raw bytes are not retained anywhere — the evidence
    ledger keeps only hashes and policy decisions). Only shapes what the
    GENERATOR re-reads; the auditor never sees these. A pure, deterministic
    function of the input list.
    """
    if len(results) <= KEEP_RECENT_RESULTS:
        return results
    folded: list[dict] = []
    for item in results[:-KEEP_RECENT_RESULTS]:
        stable = {k: v for k, v in item.items()
                  if k not in _VOLATILE_RESULT_FIELDS}
        blob = json.dumps(stable, ensure_ascii=False, sort_keys=True)
        label = (stable.get("tool") or stable.get("name")
                 or stable.get("server_id") or stable.get("host_id") or "result")
        folded.append({
            "elided": True,
            "tool": str(label),
            "status": stable.get("status"),
            "bytes": len(blob.encode("utf-8")),
            "fingerprint": hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16],
            "preview": blob[:300] + ("…" if len(blob) > 300 else ""),
            "note": "earlier result condensed to save context; re-run the tool if "
                    "you need it in full",
        })
    shaped = folded + list(results[-KEEP_RECENT_RESULTS:])
    if on_condense is not None:
        on_condense({
            "reduction": "results",
            "count": len(folded),
            "labels": [str(item.get("tool") or "result") for item in folded],
        })
    return shaped


#: Owner steering accumulates across every round of a run; keep the most-recent
#: bytes verbatim (recent steering is what still applies) and mark that older
#: guidance was folded, so a very long run cannot grow this block without bound.
MAX_GUIDANCE_BYTES = 16_000


def _bound_guidance(text: str, on_condense=None) -> str:
    """Keep the recent tail of accumulated owner guidance; note older elisions."""
    raw = text or ""
    raw_bytes = len(raw.encode("utf-8"))
    if raw_bytes <= MAX_GUIDANCE_BYTES:
        return raw
    tail = raw.encode("utf-8")[-MAX_GUIDANCE_BYTES:].decode("utf-8", errors="ignore")
    if on_condense is not None:
        on_condense({
            "reduction": "owner_guidance",
            "condensed_bytes": raw_bytes - len(tail.encode("utf-8")),
        })
    return ("<earlier owner guidance folded to keep context bounded; the most "
            "recent guidance follows>\n" + tail)


#: The earlier-turns condensation notice. Module-level and imported by the
#: locale catalogue rather than repeated there: the sentence used to exist in
#: two files with nothing tying them together, so editing one would have left
#: the other silently falling back to English — the exact i18n gap this notice
#: exists to prevent, in the notice itself. Found by its own mutation.
EARLIER_TURNS_NOTICE = ("Earlier turns in this chat were summarised for the "
                        "generator; the full conversation is still here")


def _conversation_context(cfg: Config, chat_id: str, run_id: str,
                         on_condense=None) -> str:
    """A compact, read-only transcript of this chat's earlier turns.

    Grounding for the generator so a task that refers back to the conversation
    ("continue", "make it about that") resolves to what the person meant rather
    than to whatever files happen to sit in the working tree. Best-effort: a
    missing journal or an empty chat simply yields no context, and it never
    becomes a second source of the deliverable's subject (THE TASK stays that).
    """
    if not chat_id:
        return ""
    try:
        journal = RunJournal(journal_path(cfg))
        turns = journal.chat_history(chat_id, exclude_run_id=run_id)
        total = journal.chat_turn_count(chat_id)
    except Exception:  # noqa: BLE001 -- context is best-effort; never fail a round
        return ""
    lines = []
    for turn in turns:
        subject = " ".join(str(turn.get("task", "")).split())[:200]
        if not subject:
            continue
        note = str(turn.get("outcome") or turn.get("state") or "").lower()
        tail = f"  [{note}]" if note and note not in ("", "none") else ""
        lines.append(f"- the person asked: {subject}{tail}")
    if not lines:
        return ""
    # A long chat keeps only its recent turns verbatim; say how many older ones
    # exist so the digest is honestly bounded, not silently amnesiac. (total
    # counts this run too, so the earlier-than-window count discounts it.)
    earlier = total - len(lines) - 1
    if earlier > 0:
        lines.insert(0, f"(+{earlier} earlier turn(s) in this chat, not shown)")
        # S4. The line above told the GENERATOR that turns were folded and told
        # the person nothing. Every other reduction on this path emits a
        # `context_condensed` notice; this one computed the same fact, wrote it
        # into the prompt, and stopped — so a chat past its window condensed
        # silently and the console had nothing to show because nothing was
        # sent. That is the absence-of-event class: no artifact to read, no
        # consumer to check, no identity to assert, and a person who simply is
        # not told.
        #
        # The observer is how the fact leaves this function. It is deliberately
        # NOT a client-side inference: a page that guesses when condensation
        # happened is a page that will eventually guess wrong.
        if on_condense is not None:
            on_condense({"reduction": "earlier_turns", "earlier": earlier})
    return "\n".join(lines)


def _current_work(cfg: Config, task: str = "", findings: str = "",
                  on_condense=None) -> dict[str, str]:
    """The work as it stands, read from the working tree inside the scope dirs.

    Small files are inlined verbatim (the common case); a large file's body is
    replaced with a structural outline (shape_work) so a big or file-heavy
    project does not re-dump its entire tree into every round's prompt. When even
    the outlined set is over budget, shape_work spends recall on the files least
    relevant to `task` first, keeping any file the auditor's `findings` name (the
    ones being fixed) fullest. Every path stays represented. The observer is
    told which reduced paths exist in the committed tree (and are therefore
    available to file_read as committed versions) and which exist only in the
    working tree.
    """
    out: dict[str, str] = {}
    for d in (cfg.scope_dirs or []):
        base = cfg.root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if "TEMPLATE" in p.parts:
                continue
            if p.is_file() and not p.is_symlink():
                try:
                    out[p.relative_to(cfg.root).as_posix()] = p.read_text(
                        encoding="utf-8")
                except UnicodeDecodeError:
                    rendered = document_export.current_document_text(p)
                    if rendered is not None:
                        out[p.relative_to(cfg.root).as_posix()] = rendered
    if on_condense is None:
        return shape_work(out, task, findings)

    # file_read deliberately reads HEAD, never the working tree. Classify the
    # paths against that same boundary so the user-facing recovery notice cannot
    # promise access to an uncommitted file. A failed/empty git query degrades
    # safely to "working tree only" rather than overclaiming recoverability.
    committed_raw = git(
        "ls-tree", "-r", "--name-only", "-z", "HEAD", "--",
        *(cfg.scope_dirs or []), cwd=cfg.root, check=False)
    committed = {path for path in committed_raw.split("\0") if path}

    def report_condensation(report: dict) -> None:
        projected = dict(report)
        if projected.get("reduction") == "work_files":
            reduced = [*projected.get("outlined", []),
                       *projected.get("stubbed", [])]
            projected["file_readable"] = [path for path in reduced
                                          if path in committed]
            projected["working_tree_only"] = [path for path in reduced
                                               if path not in committed]
        on_condense(projected)

    return shape_work(out, task, findings, on_condense=report_condensation)


def _stage_authorized(cfg: Config, written: AppliedFiles) -> None:
    """Stage receipt bytes and retain prior tracked entries for round paths."""
    written.verify()
    paths = [entry.relative for entry in written.entries]
    prior_index = git_bytes(
        "ls-files", "--stage", "-z", "--", *paths, cwd=cfg.root)
    object_format = git("rev-parse", "--show-object-format", cwd=cfg.root)
    if object_format == "sha1":
        zero_oid = "0" * 40
    elif object_format == "sha256":
        zero_oid = "0" * 64
    else:
        raise ConfigDenial(
            f"git returned an unsupported object format: {object_format!r}")
    delete_rows = b"".join(
        f"0 {zero_oid}\t".encode("ascii")
        + path.encode("utf-8") + b"\0"
        for path in paths)

    def restore_index() -> None:
        # Delete every round path first, then replay the exact stage entries
        # (including unmerged stages) that existed before this round.
        git_bytes("update-index", "-z", "--index-info", cwd=cfg.root,
                  input_data=delete_rows + prior_index)

    rows: list[bytes] = []
    for entry in written.entries:
        oid = git_bytes("hash-object", "-w", "--stdin", cwd=cfg.root,
                        input_data=entry.payload).decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", oid):
            raise ConfigDenial("git returned an invalid generated blob identity")
        rows.append(
            f"{entry.git_mode} {oid}\t".encode("ascii")
            + entry.relative.encode("utf-8") + b"\0")
    written.register_index_rollback(restore_index)
    # One update-index process takes one index lock for the complete round.
    git_bytes("update-index", "-z", "--index-info", cwd=cfg.root,
              input_data=b"".join(rows))


def _staged_paths(cfg: Config) -> list[str]:
    """The staged paths exactly as git holds them (NUL-separated, unquoted).

    ``--name-only`` without ``-z`` quotes non-ASCII and unusual names
    (``"\346\212\245\345\221\212.md"``), and a screen that compared those
    spellings refused a Chinese report name as out of scope.
    """
    raw = git_bytes("diff", "--cached", "--name-only", "-z", cwd=cfg.root)
    return [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]


def _stage_generated(cfg: Config, written: list[str] | AppliedFiles) -> list[str]:
    """Stage exactly the files returned by the generator, and nothing else.

    A scope directory may contain a user's untracked work or the starter
    template. Staging the whole directory silently sweeps both into the model's
    commit and later audit. Generator apply returns a retained authorization
    receipt, whose bytes are written to the index without reopening a pathname.
    """
    if not written:
        return []
    if isinstance(written, AppliedFiles):
        try:
            _stage_authorized(cfg, written)
        except Exception:
            written.rollback()
            raise
    else:
        # Backward-compatible for trusted callers outside the generator loop.
        # Generator output is required to carry AppliedFiles authority.
        git("add", "--", *written, cwd=cfg.root)
    return _staged_paths(cfg)


#: Bound the staged-diff the commit secret-scan reads (mirrors tools_git).
_MAX_SCAN_BYTES = 512 * 1024


def _staged_secret(cfg: Config) -> str:
    """The KIND of any credential the staged round would commit, or '' if clean.

    The build's per-round commit is CrossAudit's own lifecycle action, not a
    model-proposed tool call, so it does not pass through the broker. It gets the
    same defense-in-depth the brokered git_commit has: the generator can never
    write a credential into the audit history. Only the added lines and committed
    paths are scanned, and only the secret's KIND (never its value) is returned.
    """
    diff = git("diff", "--cached", "--no-color", "--unified=0",
               cwd=cfg.root, check=False)[:_MAX_SCAN_BYTES]
    added = "\n".join(ln[1:] for ln in diff.splitlines()
                      if ln.startswith("+") and not ln.startswith("+++"))
    return secretscan.first_finding(added, _staged_paths(cfg))


def _last_report(cfg: Config) -> str:
    ledger = cfg.root / cfg.ledger_dir
    reports = sorted(ledger.glob("*/report.md"), key=lambda p: p.stat().st_mtime)
    return reports[-1].read_text(encoding="utf-8") if reports else ""


class _Args:
    """The argument shape `cmd_run` expects, when the loop calls it rather than a user."""

    json = False
    sha = None
    yes = True

    def __init__(self) -> None:
        # Sending a key to a non-builtin origin is opt-in — flag or environment
        # — and the loop may not be a quieter path than the verb. A hardcoded
        # True here waived, for every auditor call the build loop makes, the
        # very consent `crossaudit run` demands; the loop has no flags, so the
        # environment gate the generator already uses is the whole opt-in.
        self.allow_custom_endpoint = bool(os.environ.get(ALLOW_CUSTOM_ENV))


def derive_goal(cfg: Config, task: str) -> dict:
    """The structured Goal for this run (§12), derived deterministically.

    Computed from the config and the task text alone — no model call — so the
    same inputs always describe the same goal, and the goal cannot drift
    mid-run (§5.6: the task is fixed at start; changing it means a new run).
    """
    from ..autonomy import requested_document_format

    scope = [str(d) for d in (cfg.scope_dirs or [])]
    outputs = ["audited work files"
               + (f" under {', '.join(scope)}" if scope else "")]
    # The goal record must never refuse a task the loop itself accepts: format
    # ambiguity is the loop's question to raise, not the goal derivation's.
    try:
        format_name = requested_document_format(task)
    except Denial:
        format_name = None
    if format_name:
        outputs.append(f"a rendered {format_name.upper()} document")
    return {
        "task": task.strip(),
        "desired_outputs": outputs,
        "constraints": {
            "max_rounds": cfg.max_rounds,
            "scope_dirs": scope,
            "writes_authorized": writes_authorized(cfg),
            "commands_authorized": run_commands_authorized(cfg),
            "compute_authorized": compute_authorized(cfg),
        },
        "success_criteria": [
            "every deterministic check passes",
            "the independent auditor returns PASS",
            "the receipt is admission-ready",
        ],
    }


def run_loop(cfg, task: str, *, on_event=None, attachments: str = "",
             chat_id: str = "", continuation_cycle: str = "") -> int:
    """The build loop itself emits typed operational facts.

    Kept separate from cmd_build so the console can watch the same loop the CLI
    runs, rather than a reimplementation of it that could drift on the one thing
    that matters: when the loop stops.
    """
    current_round = 0
    operational_state = RunState.QUEUED
    # The run shell exposes lease renewal and this run's durable identity on
    # the emit callable, so the loop's provider boundaries can prove liveness
    # and its escalations can reference the exact run they record — without a
    # second command channel.
    heartbeat = getattr(on_event, "heartbeat", None)
    run_id = str(getattr(on_event, "run_id", "") or "")
    is_cancelled = getattr(on_event, "is_cancelled", None)
    # Owner messages queued while the run is live, delivered by the journal at
    # round boundaries (consume-once). Absent for foreground CLI builds.
    drain_guidance = getattr(on_event, "drain_guidance", None)
    owner_guidance = ""
    reported_condensations: set[tuple[str, str]] = set()

    def emit(kind: str, actor: str, text: str, detail: str = "", *,
             state: RunState | None = None, waiting_reason: dict | None = None,
             stream: dict | None = None,
             ) -> None:
        nonlocal operational_state
        operational_state = state or operational_state
        if on_event is not None:
            on_event(RunEvent(
                kind=kind, actor=actor, text=text, detail=detail,
                state=operational_state, round_no=current_round,
                round_limit=cfg.max_rounds, waiting_reason=waiting_reason,
                stream=stream))

    def context_notice(text: str, detail: str = "") -> None:
        """Emit each distinct shaping fact once, without flooding later turns."""
        key = (text, detail)
        if key in reported_condensations:
            return
        reported_condensations.add(key)
        emit("context_condensed", "generator", text, detail,
             state=RunState.GENERATING)

    def context_report(report: dict) -> None:
        """Turn deterministic shaping metadata into honest human narration."""
        reduction = str(report.get("reduction") or "")

        def labels(values) -> str:
            items = [str(value)[:160] for value in (values or [])]
            shown = items[:10]
            suffix = f" … (+{len(items) - len(shown)})" if len(items) > len(shown) else ""
            return ", ".join(shown) + suffix

        if reduction == "work_files":
            outlined = list(report.get("outlined") or [])
            stubbed = list(report.get("stubbed") or [])
            file_readable = set(report.get("file_readable") or [])
            readable_outlines = [path for path in outlined
                                 if path in file_readable]
            working_outlines = [path for path in outlined
                                if path not in file_readable]
            readable_stubs = [path for path in stubbed
                              if path in file_readable]
            working_stubs = [path for path in stubbed
                             if path not in file_readable]
            if readable_outlines:
                context_notice(
                    "Tracked project files outlined; file_read can retrieve the committed version",
                    labels(readable_outlines))
            if working_outlines:
                context_notice(
                    "Working-tree-only project files outlined; content is not available to file_read",
                    labels(working_outlines))
            if readable_stubs:
                context_notice(
                    "Tracked project files briefly stubbed; file_read can retrieve the committed version",
                    labels(readable_stubs))
            if working_stubs:
                context_notice(
                    "Working-tree-only project files briefly stubbed; content is not available to file_read",
                    labels(working_stubs))
        elif reduction == "tool_results":
            context_notice(
                "Earlier tool results condensed to previews; rerun the tool for full output",
                labels(report.get("labels")))
        elif reduction == "compute_results":
            context_notice(
                "Earlier compute results condensed to previews; rerun compute for full output",
                labels(report.get("labels")))
        elif reduction == "owner_guidance":
            context_notice(
                "Earlier owner guidance condensed; full messages remain in the run record",
                f"{int(report.get('condensed_bytes') or 0)} bytes")
        elif reduction == "earlier_turns":
            # The count travels in the DETAIL, not in the sentence. That keeps
            # the sentence a fixed catalogue entry that can never fall back to
            # English when the number changes, while the number itself is
            # translated by the counted-unit pattern — which is where counted
            # strings on this surface belong. The sentence says what was folded
            # AND that nothing is gone, because "+N" alone is a number and the
            # point is that the transcript is intact.
            folded = int(report.get("earlier") or 0)
            # SPEC-20 §2. This read "1 turns" for a single folded turn. It is an
            # English-only defect — Chinese has no plural, so `1 轮` was always
            # right — which is why a locale sweep would not have caught it and
            # reading the grammar did.
            context_notice(EARLIER_TURNS_NOTICE,
                           f"{folded} turn{'' if folded == 1 else 's'}")

    def generator_provider_event(actor: str, text: str, detail: str = "") -> None:
        emit("provider_recovery", actor, text, detail,
             state=RunState.GENERATING)

    def generation_chunk(text: str, stream: dict) -> None:
        """Bridge provider-coalesced text into the typed operational stream."""
        emit("generation_chunk", "generator", text,
             state=RunState.GENERATING, stream=stream)

    # The resilience layer renews the lease before each retry attempt through
    # the same attribute convention the run shell uses. Its streaming adapter
    # reads ``on_chunk`` from this callback, keeping existing provider-event
    # call signatures backward compatible for adapters without streaming.
    generator_provider_event.heartbeat = heartbeat
    generator_provider_event.on_chunk = generation_chunk

    if chat_id and not re.fullmatch(r"(?:history|[a-f0-9]{16})", chat_id):
        raise ConfigDenial("chat id is invalid")
    allow_custom = bool(os.environ.get(ALLOW_CUSTOM_ENV))
    # Usage attribution for this run: the loop keeps the round and cycle
    # current; every generator and auditor completion is recorded with a copy.
    usage_context: dict = {"run_id": run_id, "chat_id": chat_id,
                           "cycle_id": continuation_cycle or "", "round": 0}
    complete = _generator_complete(cfg, allow_custom, generator_provider_event,
                                   heartbeat, usage_context)

    def budget_notice() -> None:
        """Raise any 80 % / 95 % budget alarm newly crossed, once per period."""
        for warning in check_budget_warnings(cfg):
            emit("budget_warning", "loop", warning["text"], warning["resets"])
    constitution = (cfg.root / cfg.constitution).read_text(encoding="utf-8")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    house = skills_mod.load(cfg.root)
    findings = ""
    #: The last BLOCKED audit's findings on their own, so a refusal before the
    #: next audit (apply, document export, the repair screen) can be appended
    #: to them instead of replacing the cause the generator must still fix.
    audit_findings = ""
    deterministic_contract = describe_checks(cfg.checks)
    compute_hosts = hpc.MANAGER.agent_context(cfg)
    compute_results: list[dict] = []
    compute_counts: dict[str, int] = {}
    total_compute_jobs = 0
    mcp_servers = mcp.MANAGER.agent_context(cfg)
    tool_results: list[dict] = []
    tool_counts: dict[str, int] = {}
    total_tool_calls = 0
    broker_token = None                   # broker + token built lazily on 1st tool
    broker_obj = None
    # Read-only tools always; write tools too, but only for a project whose user
    # authorized recoverable edits (build_catalog / build_broker_and_token decide).
    builtin_tools = build_catalog(cfg)
    build_cycle_id: str | None = continuation_cycle or None
    termination_reason = f"build round budget spent ({cfg.max_rounds})"
    last_round = 0
    provider_wait: ProviderDenial | None = None
    #: One free corrective re-ask when a round changes nothing (self-heal
    #: before any human is bothered); a second no-progress round stops with a
    #: structured cause instead of a bare sentence.
    no_progress_retry_used = False
    no_progress_stop = False
    #: Whether the next revision repairs a BLOCKED audit (D148 slice D): the
    #: repair screen runs only then. False on round 1 and after every audit
    #: until it blocks again.
    repair_round = False
    #: What the screen flagged in this round's revision, handed to the next
    #: audit as deterministic notes so the auditor model can weigh them.
    revision_cautions: list[str] = []
    #: One free re-ask after a refused repair (self-heal before a human is
    #: bothered); a second refusal stops with the structured cause
    #: "repair_refused" (the string the Decision Center keys on — stable).
    repair_refusal_used = False
    repair_refusal_stop = False
    #: The denial that terminated the loop (non-park path), kept so the stop
    #: can name a structured, human-actionable cause instead of raw prose.
    terminal_denial: ProviderDenial | None = None

    # §12: the run's Goal, stated once and durably before any work happens.
    # The plan surface (Plan tab) reads this event plus the loop's own gates.
    emit("goal", "loop", task.strip().splitlines()[0][:80],
         detail=json.dumps(derive_goal(cfg, task), ensure_ascii=False)[:2000],
         state=RunState.QUEUED)

    # Read-only grounding: earlier turns of this same chat, so a task that refers
    # back to them resolves to the person's real intent instead of to stale files
    # in the tree. Stable for the run; THE TASK remains the authoritative subject.
    conversation = _conversation_context(cfg, chat_id, run_id,
                                        on_condense=context_report)

    for round_no in range(1, cfg.max_rounds + 1):
        current_round = round_no
        last_round = round_no
        usage_context["round"] = round_no
        usage_context["cycle_id"] = build_cycle_id or ""
        emit("round_started", "loop", f"round {round_no} of {cfg.max_rounds}",
             state=RunState.GENERATING)
        # The safe boundary where mid-run owner messages join the work: drained
        # exactly once, accumulated for every later round, and recorded as a
        # visible event (steering is auditable, never a whisper). The task and
        # goal stay fixed; guidance shapes HOW, never WHAT.
        if drain_guidance is not None:
            try:
                fresh_guidance = list(drain_guidance() or [])
            except Exception:  # noqa: BLE001 -- a queue hiccup must not kill the round
                fresh_guidance = []
            if fresh_guidance:
                joined = "\n\n".join(fresh_guidance)
                owner_guidance = (owner_guidance + "\n\n" + joined
                                  if owner_guidance else joined)
                emit("guidance_received", "input",
                     f"reading {len(fresh_guidance)} owner message(s)",
                     joined[:2000], state=RunState.GENERATING)
        emit("generation_started", "generator", "writing",
             state=RunState.GENERATING)
        current = _current_work(cfg, task, findings, context_report)
        in_force = skills_mod.select(house, list(current) or cfg.scope_dirs)
        try:
            while True:
                outcome = gen_mod.generate(
                    task=task, constitution=constitution, current=current,
                    complete=complete, findings=findings,
                    allowed_dirs=cfg.scope_dirs,
                    root=cfg.root,
                    skills=skills_mod.render(in_force),
                    deterministic_contract=deterministic_contract,
                    attachments=attachments, compute_hosts=compute_hosts,
                    compute_results=_fold_results(
                        compute_results,
                        lambda report: context_report(
                            {**report, "reduction": "compute_results"})),
                    mcp_servers=mcp_servers,
                    tool_results=_fold_results(
                        tool_results,
                        lambda report: context_report(
                            {**report, "reduction": "tool_results"})),
                    builtin_tools=builtin_tools,
                    owner_guidance=_bound_guidance(owner_guidance, context_report),
                    conversation=conversation,
                    # A malformed reply gets one visible, recorded repair
                    # attempt (§24.1) before anything reaches a human.
                    on_repair=lambda why: emit(
                        "generation_retried", "generator",
                        "correcting a malformed reply", str(why)[:200],
                        state=RunState.GENERATING))
                if isinstance(outcome, gen_mod.Work):
                    # The physical identity boundary precedes every downstream
                    # document check, write and Git pathspec.  ``generate`` binds
                    # production replies before returning; this idempotent call
                    # also protects alternate/test providers that return Work.
                    work = gen_mod.bind_file_identities(
                        outcome, cfg.root, cfg.scope_dirs)
                    break
                if isinstance(outcome, gen_mod.ToolRequest):
                    total_tool_calls += 1
                    if total_tool_calls > MAX_MCP_CALLS_PER_BUILD:
                        raise ProviderDenial(
                            "the Generator exceeded the automatic MCP call limit")
                    server_id = str(outcome.request.get("server_id", ""))
                    if server_id == BROKER_SERVER_ID:
                        # A built-in read-only tool: route through the Tool Broker
                        # (policy decision + evidence ledger), never MCP. The
                        # result is fed back as untrusted context like any tool.
                        tool_name = str(outcome.request.get("tool", "tool"))
                        emit("capability_requested", "tool", "running built-in tool",
                             tool_name[:200], state=RunState.WAITING_FOR_CAPABILITY)
                        if broker_obj is None:
                            # A live run shell (heartbeat handle present) gets the
                            # real-time per-call approval gate: a flagged action
                            # pauses in place, surfaces a pending-action card, and
                            # the user's Allow/Deny — recorded as the grant —
                            # resumes this same worker. Without a run shell the
                            # broker stays deny-by-default (standing approval only).
                            gate = (HumanApprovalGate(
                                        inbox=INBOX, heartbeat=heartbeat,
                                        is_cancelled=is_cancelled)
                                    if heartbeat is not None else None)
                            broker_obj, broker_token = build_broker_and_token(
                                cfg, run_id=run_id, now_epoch=time.time(),
                                approver=gate)
                        result = broker_tool_call(
                            cfg, outcome.request, broker_token,
                            run_id=run_id, now_epoch=time.time(), broker=broker_obj)
                        tool_results.append(result)
                        current = _current_work(
                            cfg, task, findings, context_report)
                        emit("generation_resumed", "generator",
                             "resuming with tool result", state=RunState.GENERATING)
                        continue
                    tool_counts[server_id] = tool_counts.get(server_id, 0) + 1
                    tool_name = str(outcome.request.get("tool", "MCP tool"))
                    emit("capability_requested", "tool", "calling MCP tool",
                         tool_name[:200], state=RunState.WAITING_FOR_CAPABILITY)
                    try:
                        result = mcp.MANAGER.call_agent(
                            cfg, outcome.request, chat_id=chat_id,
                            ordinal=tool_counts[server_id],
                            notify=lambda status, detail: emit(
                                "capability_progress", "tool", status, detail,
                                state=RunState.WAITING_FOR_CAPABILITY))
                    except Denial as exc:
                        result = {"status": "refused", "message": exc.reason,
                                  "server_id": server_id, "tool": tool_name}
                        emit("capability_refused", "tool", "refused",
                             exc.reason[:300], state=RunState.WAITING_FOR_CAPABILITY)
                    tool_results.append(result)
                    current = _current_work(cfg, task, findings, context_report)
                    emit("generation_resumed", "generator", "resuming with tool result",
                         state=RunState.GENERATING)
                    continue
                total_compute_jobs += 1
                if total_compute_jobs > MAX_AGENT_JOBS_PER_BUILD:
                    raise ProviderDenial(
                        "the Generator exceeded the automatic remote-compute call limit")
                host_id = str(outcome.request.get("host_id", ""))
                compute_counts[host_id] = compute_counts.get(host_id, 0) + 1
                emit("capability_requested", "compute",
                     "requesting remote calculation",
                     str(outcome.request.get("name", "Generator compute"))[:200],
                     state=RunState.WAITING_FOR_CAPABILITY)
                try:
                    result = hpc.MANAGER.run_agent(
                        cfg, outcome.request, chat_id=chat_id,
                        ordinal=compute_counts[host_id],
                        notify=lambda status, detail: emit(
                            "capability_progress", "compute", status, detail,
                            state=RunState.WAITING_FOR_CAPABILITY))
                except Denial as exc:
                    result = {"status": "refused", "message": exc.reason,
                              "host_id": host_id}
                    emit("capability_refused", "compute", "refused",
                         exc.reason[:300], state=RunState.WAITING_FOR_CAPABILITY)
                compute_results.append(result)
                current = _current_work(cfg, task, findings, context_report)
                emit("generation_resumed", "generator",
                     "resuming with compute result", state=RunState.GENERATING)
        except ProviderDenial as exc:
            if str(exc.detail.get("category", "")) in PROVIDER_WAIT_CATEGORIES:
                # Every configured route is exhausted or cooling down — or
                # the local usage guardrail refused to place the call at
                # all. No further request can differ from the last one, and
                # burning the remaining rounds on it would present an
                # infrastructure or spending stop as spent content revisions
                # (§14 red line). Stop and park the run for a human remedy.
                provider_wait = exc
                termination_reason = (
                    f"generator provider failure in round {round_no}: "
                    f"{exc.reason[:400]}")
                break
            # An overreaching or malformed round is a refused round, not a
            # crashed loop: the generator is told what the guard refused and
            # gets its next attempt inside the same budget.
            emit("generation_refused", "generator", "refused", exc.reason,
                 state=RunState.GENERATING)
            scope_note = (f"Return only files inside "
                          f"{', '.join(cfg.scope_dirs)}/ and try again."
                          if cfg.scope_dirs else "Try again.")
            refusal = (f"[BLOCKER] Your last round was refused before it reached "
                       f"the auditor: {exc.reason}\n{scope_note}")
            findings = f"{audit_findings}\n\n{refusal}" if audit_findings else refusal
            # A non-retryable denial (authentication, permission, endpoint,
            # invalid model, an exceeded automation limit) cannot improve by
            # sending the same request for every remaining round. Stop once,
            # retain the actionable explanation, and expose a human decision
            # in the UI. The judgment keys on the denial's own retryable
            # claim, never on whether an HTTP status happened to be attached
            # — a guardrail stop without one must not burn the whole budget
            # in a zero-call loop.
            if not exc.detail.get("retryable", False):
                terminal_denial = exc
                # A conversational answer (the generator could not make an audited
                # deliverable and explained why — e.g. a false premise) is NOT a
                # failure: surface its reply verbatim so the person gets a useful
                # answer, not a "could not produce auditable work" stop.
                if exc.detail.get("conversational"):
                    termination_reason = exc.reason[:2000]
                else:
                    # Name the stop by what it actually is (a format or a refused
                    # round), not "provider failure" — the Decision Center reads the
                    # structured cause, and a misleading prefix would send the user
                    # to the wrong remedy. Real provider outages take the park path
                    # above, which keeps its own "provider failure" wording.
                    lead = ("the generator could not produce auditable work"
                            if str(exc.detail.get("category", "")) == "format"
                            else "the generator's request was refused")
                    termination_reason = (
                        f"{lead} in round {round_no}: {exc.reason[:400]}")
                break
            if round_no == cfg.max_rounds:
                break
            continue

        written: AppliedFiles | None = None
        revision_cautions = []
        try:
            document_export.validate_export_work(cfg.root, work.files, task)
            written = gen_mod.apply(work, cfg.root, cfg.scope_dirs)
            model_written = set(written)
        except ProviderDenial as exc:
            emit("document_refused", "generator", "document export refused",
                 exc.reason, state=RunState.GENERATING)
            refusal = ("[BLOCKER] The local document export boundary refused the "
                       f"last round: {exc.reason}\nReturn exactly one valid "
                       f"*{document_export.SOURCE_SUFFIX} Markdown source and try again.")
            findings = f"{audit_findings}\n\n{refusal}" if audit_findings else refusal
            if round_no == cfg.max_rounds:
                termination_reason = (
                    f"document export failed in round {round_no}: {exc.reason[:400]}")
                break
            continue
        # One lexical scope owns every operation after apply.  Explicit
        # finalize() is the only success exit; every exception/continue/break
        # restores both filesystem and the prior tracked stage entries.
        with written:
            try:
                if document_export.parse_export_task(task) is not None:
                    emit("document_rendering", "generator",
                         "rendering final document locally",
                         state=RunState.GENERATING)
                rendered = document_export.render_export(
                    cfg.root, written, task)
                if rendered is not written:
                    raise ConfigDenial(
                        "document export discarded its authorization receipt")
                # What CrossAudit itself rendered from the model's source: the
                # one kind of binary the repair guard accepts.
                locally_rendered = set(written) - model_written
            except ProviderDenial as exc:
                emit("document_refused", "generator", "document export refused",
                     exc.reason, state=RunState.GENERATING)
                refusal = ("[BLOCKER] The local document export boundary refused the "
                           f"last round: {exc.reason}\nReturn exactly one valid "
                           f"*{document_export.SOURCE_SUFFIX} Markdown source and try again.")
                findings = f"{audit_findings}\n\n{refusal}" if audit_findings else refusal
                if round_no == cfg.max_rounds:
                    termination_reason = (
                        f"document export failed in round {round_no}: {exc.reason[:400]}")
                    break
                continue

            emit("generation_completed", "generator", work.summary,
                 ", ".join(written[:4]), state=RunState.GENERATING)
            if work.notes:
                emit("generation_note", "generator", "note", work.notes[:200],
                     state=RunState.GENERATING)

            # Dirtiness is judged over what will actually be committed. Asking
            # about the whole tree lets unrelated work fake a change.
            staged = _stage_generated(cfg, written)
            if not staged:
                # Self-heal first (§24.1): a byte-identical round gets one
                # chance to produce an actual revision before escalation.
                if not no_progress_retry_used and round_no < cfg.max_rounds:
                    no_progress_retry_used = True
                    emit("revision_retry", "loop",
                         "the round changed nothing; asking for a real revision",
                         state=RunState.GENERATING)
                    findings = ("[BLOCKER] Your last reply was byte-identical to the "
                                "work already committed — nothing new could be "
                                "audited. Produce an actual revision that addresses "
                                "the task: change or extend the relevant files. If "
                                "you believe the committed work already satisfies "
                                "the task completely, say why in `notes` and make "
                                "the smallest meaningful improvement instead.")
                    continue
                emit("revision_unchanged", "loop",
                     "the round reproduced the previous one; nothing new to audit",
                     state=RunState.GENERATING)
                no_progress_stop = True
                termination_reason = (
                    f"generator produced no new auditable revision in round {round_no}")
                break

            # Defense-in-depth: never commit a credential into audit history.
            secret = _staged_secret(cfg)
            if secret:
                emit("commit_refused", "loop", "the round could not be committed",
                     f"the generated changes appear to contain {secret}; the secret "
                     "was not committed", state=RunState.GENERATING)
                termination_reason = (
                    f"generator revision would have committed {secret} in round {round_no}")
                break
            # A repair round is screened before it is committed (D148 slice
            # D): same insertion point as the secret scan, the staged diff is
            # the whole candidate. Out-of-scope files and unrendered binaries
            # are refused — the `with written:` exit restores files AND
            # index. Likely defensive edits are cautions: they ride to the
            # next audit as notes (mode caution) or refuse too (mode refuse).
            if repair_round and cfg.repair.enabled:
                diff = git("-c", "core.quotepath=false", "diff", "--cached",
                           "--binary", "--no-ext-diff",
                           cwd=cfg.root, check=False)[:_MAX_SCAN_BYTES]
                assessment = RepairGuard(
                    cfg.repair.max_changed_lines, mode=cfg.repair.mode).assess(
                    diff, scope_dirs=cfg.scope_dirs, staged_files=staged,
                    locally_rendered_files=locally_rendered,
                    truncated=len(diff) >= _MAX_SCAN_BYTES)
                if not assessment.allowed:
                    emit("repair_refused", "loop",
                         "the revision was refused before the audit",
                         "; ".join(assessment.refusals)[:2000],
                         state=RunState.REVISING)
                    refusal = (
                        "[BLOCKER] The repair guard refused the last revision:\n"
                        + "\n".join(f"- {reason}" for reason in assessment.refusals)
                        + "\nThe previous attempt was rolled back. Repair the "
                          "findings above without that change; if the fix "
                          "genuinely needs it, say so in `notes`.")
                    # The audit's findings stay in the prompt: the generator
                    # must still see the cause it is being asked to repair.
                    findings = f"{audit_findings}\n\n{refusal}" if audit_findings else refusal
                    if repair_refusal_used or round_no == cfg.max_rounds:
                        repair_refusal_stop = True
                        termination_reason = (
                            f"the automatic repair was refused in round {round_no} "
                            f"because {assessment.refusals[0][:300]}")
                        break
                    repair_refusal_used = True
                    emit("revision_retry", "loop",
                         "asking for a repair that stays within the audited files",
                         state=RunState.REVISING)
                    continue
                if assessment.cautions:
                    revision_cautions = list(assessment.cautions)
                    emit("repair_caution", "loop",
                         "the revision has edits the auditor should weigh",
                         "; ".join(assessment.cautions)[:2000],
                         state=RunState.REVISING)
            try:
                commit_args = ["commit", "-q", "-m",
                               f"{work.summary} (round {round_no})"]
                route = getattr(complete, "last_route", None)
                if isinstance(route, dict):
                    commit_args += ["-m", ("CrossAudit-Generator: "
                                    f"{route['vendor']}/{route['provider']}:{route['model']}; "
                                    f"fallback={str(bool(route.get('fallback'))).lower()}")]
                if chat_id:
                    # A commit trailer associates durable work/audit evidence
                    # with its UI chat without putting conversation metadata in files.
                    commit_args += ["-m", f"CrossAudit-Chat: {chat_id}"]
                git(*commit_args, cwd=cfg.root)
            except ConfigDenial as exc:
                # The scope restores prior tracked stage entries and the
                # filesystem; a broad git reset would destroy unrelated staged
                # user work.
                emit("commit_refused", "loop", "the round could not be committed",
                     exc.reason[:200], state=RunState.GENERATING)
                termination_reason = (
                    f"generator revision could not be committed in round {round_no}")
                break

            written.finalize()

        audit_sha = git("rev-parse", "HEAD", cwd=cfg.root)
        repair_round = False           # every audit re-decides the next round
        emit("audit_started", "auditor", "reviewing the commit",
             state=RunState.AUDITING)
        buffer = io.StringIO()
        run_args = _Args()
        run_args.continue_cycle = build_cycle_id
        # The screen's cautions reach the auditor as deterministic notes (the
        # `dcl.notes` the prompt and the ledger's checks.json carry), never as
        # findings: the auditor decides whether a caution is a defect.
        run_args.extra_notes = [f"revision caution: {c}" for c in revision_cautions]
        run_args.on_step = lambda actor, text, detail="": emit(
            "provider_recovery", actor, text, detail, state=RunState.AUDITING)
        # The auditor's resilience layer renews the lease before each retry
        # attempt through the same handle convention as the generator's.
        run_args.on_step.heartbeat = heartbeat
        run_args.usage_context = {"run_id": run_id, "chat_id": chat_id}
        if heartbeat is not None:
            heartbeat()          # auditor provider turn: same silence problem
        budget_notice()          # the generator's spend, before the audit
        try:
            with contextlib.redirect_stdout(buffer):
                code = cmd_run(run_args)
        except ProviderDenial as exc:
            if str(exc.detail.get("category", "")) not in PROVIDER_WAIT_CATEGORIES:
                raise
            # The auditor, not the generator, lost every configured route.
            # run_audit re-raises this instead of synthesizing a verdict, so
            # the run parks exactly like a generator outage via the tail
            # below. cmd_run opened or advanced the cycle before the audit
            # call, so anchor the escalation to it rather than minting a
            # duplicate.
            provider_wait = exc
            termination_reason = (
                f"auditor provider failure in round {round_no}: "
                f"{exc.reason[:400]}")
            cycles = store.snapshot().get("cycles", {})
            matched = [(cid, c) for cid, c in cycles.items()
                       if c.get("active_sha") == audit_sha]
            if matched:
                build_cycle_id = matched[0][0]
            break
        inner = buffer.getvalue()
        budget_notice()          # and the auditor's
        cycles = store.snapshot().get("cycles", {})
        matched = [(cid, c) for cid, c in cycles.items()
                   if c.get("active_sha") == audit_sha]
        if matched:
            build_cycle_id, latest = matched[0]
        else:
            latest = {}
        status = latest.get("status", "?")

        if code == EXIT_OK:
            emit("audit_passed", "auditor", "PASS", state=RunState.AUDITING)
            return EXIT_OK
        if status == "ESCALATED":
            emit("audit_escalated", "auditor", "ESCALATED",
                 "the loop cannot settle this itself", state=RunState.AUDITING)
            return EXIT_ESCALATED
        blocking = [ln.strip("- ").strip() for ln in inner.splitlines()
                    if ln.strip().startswith("- [")]
        emit("audit_blocked", "auditor", "BLOCKED",
             "; ".join(blocking[:2])[:300], state=RunState.AUDITING)
        audit_findings = findings = gen_mod.render_findings(_last_report(cfg))
        repair_round = True
        emit("revision_requested", "loop", "findings returned to the generator",
             state=RunState.REVISING)

    reason = termination_reason

    def record_decision_object() -> str:
        """The cycle-side decision object for this stop, referencing this run.

        Wrapped fail-closed: the verdict-rewriting guards in the cycle store
        (a PASSED/CONSUMED cycle at the anchor, a human's close) may refuse
        the write, and that refusal must never detonate the loop or dress the
        stop as a content refusal — the run side still records the honest
        stop, and the run-side signal carries the human surface.
        """
        # A provider outage and a content stop share this recorder but route
        # to different remedies; name the kind structurally so the Console
        # never has to re-read the reason to tell them apart. A budget
        # (usage-guardrail) park is a provider wait whose remedy is billing,
        # not a connection review — derive the kind from the run-side park
        # category (runs.waiting_kind, the single source) so the cycle side
        # names the SAME kind the run parked with, never a blanket 'provider'.
        if provider_wait is not None:
            kind = park_escalation_kind(
                waiting_kind(str(provider_wait.detail.get("category", ""))))
        else:
            kind = "audit"
        # The structured cause the Decision Center renders as human guidance
        # (what happened / what you can do). Additive: old records without it
        # still render through the raw-reason fallback.
        if provider_wait is not None:
            cause = ("budget" if kind == "budget" else "provider_unavailable")
        elif terminal_denial is not None and terminal_denial.detail.get("conversational"):
            cause = "answered"
        elif (terminal_denial is not None
              and str(terminal_denial.detail.get("category", "")) == "format"):
            cause = "generator_format"
        elif terminal_denial is not None:
            cause = "generator_refused"
        elif repair_refusal_stop:
            # The repair screen refused twice (or on the last round): the
            # revision left the audited directories, wrote a binary no local
            # renderer produced, or (mode refuse) made a likely defensive edit.
            cause = "repair_refused"
        elif no_progress_stop:
            cause = "no_progress"
        else:
            cause = ""
        try:
            if build_cycle_id:
                store.escalate(build_cycle_id, reason, task=task,
                               run_id=run_id, kind=kind, cause=cause)
                return build_cycle_id
            # A provider can refuse every generator attempt before there is
            # a work commit for cmd_run to open. Anchor that stop to the
            # current durable task/routing commit so the UI exposes an
            # actual human decision instead of an ephemeral "needs input"
            # banner with nothing to resolve.
            anchor = git("rev-parse", "HEAD", cwd=cfg.root)
            cycle = store.record_build_escalation(
                cfg.science_repo, anchor, reason, last_round, chat_id, task,
                run_id=run_id, kind=kind, cause=cause)
            return cycle["cycle_id"]
        except Denial:
            return ""

    if provider_wait is not None:
        # Run side first: the park is the honest record of this stop, and
        # the waiting reason is machine-readable so the UI can offer the
        # provider (or budget) remedies rather than content guidance. The
        # cycle decision object follows; if the process dies between the two
        # writes, the status-gated reconciler completes the cycle side. The
        # park is the last journal event on purpose — a later event would
        # clear the persisted waiting reason.
        category = str(provider_wait.detail.get("category", ""))
        emit("loop_stopped", "loop", reason)
        emit("provider_unavailable", "loop", "waiting for provider", reason,
             state=RunState.PROVIDER_UNAVAILABLE,
             waiting_reason={
                 "kind": waiting_kind(category),
                 "category": category,
                 "detail": provider_wait.reason[:400]})
        record_decision_object()
        return EXIT_ESCALATED
    # For a non-park escalation the cycle is written first: the run side
    # reaches WAITING_FOR_HUMAN only through the shell's finish after this
    # function returns, and the run_id reference lets reconciliation
    # complete exactly this run if the process dies in between.
    cycle_ref = record_decision_object()
    emit("audit_escalated", "auditor", "ESCALATED",
         (f"cycle {cycle_ref} is waiting for a human" if cycle_ref else
          "this stop is waiting for a human"))
    emit("loop_stopped", "loop", reason)
    return EXIT_ESCALATED


def resolve_task(cfg, words: list[str]) -> str:
    """The task, from the command line or from the committed TASK.md."""
    task = " ".join(words).strip()
    task_path = cfg.root / TASK_FILE
    if not task:
        if not task_path.is_file():
            raise ConfigDenial('say what to build: crossaudit build "..."')
        return task_path.read_text(encoding="utf-8")
    # The task joins the ledger too: a reader asking "why does this exist"
    # should find the answer in the repository, not in someone's terminal.
    # Restating the same task is not a change, and git has nothing to commit.
    unchanged = (task_path.is_file() and
                 task_path.read_text(encoding="utf-8").strip() == task.strip())
    task_path.write_text(task + "\n", encoding="utf-8", newline="\n")
    if not unchanged:
        git("add", "--", TASK_FILE, cwd=cfg.root)
        git("commit", "-q", "-m", f"task: {task.splitlines()[0][:68]}", cwd=cfg.root)
    return task


def preflight(cfg) -> None:
    """What must hold before either caller starts a loop."""
    if not is_repo(cfg.root):
        raise ConfigDenial(f"{cfg.root} is not a git repository; the ledger is git")
    if not cfg.scope_dirs:
        raise ConfigDenial(
            "scope.dirs is not set: the generator must be told where it may write, "
            "or it could rewrite the rules it is judged by")
    het_ok, why = heterogeneity(cfg)
    if not het_ok:
        raise ConfigDenial(why)


def _missing_role_keys(cfg) -> list[str]:
    """Every absent role credential, generator first.

    Naming only the first would print the AUDITOR variable under a message that
    just said the GENERATOR failed, which reads as a non-sequitur at the exact
    moment someone is trying to act on it.
    """
    import os as _os

    from ..providers.registry import NEEDS_KEY

    missing = []
    generator_env = cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY"
    if (cfg.generator_vendor or "").lower() != "human" and not _os.environ.get(
            generator_env, "").strip():
        missing.append(generator_env)
    if NEEDS_KEY.get(cfg.auditor.provider, True) and not _os.environ.get(
            cfg.auditor.key_env, "").strip():
        missing.append(cfg.auditor.key_env)
    return missing


def cmd_build(args) -> int:
    _i18n.set_language(getattr(args, "lang", "en") or "en")
    _i18n.reset_fallbacks()
    cfg = load()
    preflight(cfg)
    service = RunCommandService(cfg)
    verbose = bool(getattr(args, "verbose", False))
    #: Whether any round reached the auditor. Nothing reaching it means nothing
    #: was committed, which is what makes the closing sentence true.
    produced: set[str] = set()
    prepared_task = resolve_task(cfg, args.words)

    def prepare() -> PreparedRun:
        return PreparedRun(task=prepared_task)

    def worker(prepared: PreparedRun, emit) -> int:
        constitution = (cfg.root / cfg.constitution).read_text(encoding="utf-8")
        house = skills_mod.load(cfg.root)
        print("\nCrossAudit — building under audit")
        print("=" * 60)
        print(f"  task     {prepared.task.splitlines()[0][:60]}")
        print(f"  rules    {cfg.constitution} "
              f"({constitution.count(chr(10) + '### ')} rules)")
        print(f"  writing  {', '.join(cfg.scope_dirs)}/")
        if house:
            print(f"  skills   {', '.join(s.name for s in house)}")
        print(f"  rounds   up to {cfg.max_rounds}, then it goes to you")

        def on_event(event: RunEvent) -> None:
            emit(event)
            # The source-mode console consumes chunks through named SSE events.
            # A raw edit envelope on stdout has no live-draft affordance yet, so
            # the CLI keeps its existing phase narration rather than presenting
            # unaudited structured bytes as a finished-looking result.
            if event.kind == "generation_chunk":
                return
            if event.kind == "round_started":
                label = f"round {event.round_no} of {event.round_limit}"
                print(f"\n  ── {label} " + "─" * max(0, 44 - len(label)))
                return
            # 1. Never print a raw payload. The goal event carries the run's
            #    JSON goal as detail; truncated at 96 characters it reads as
            #    corrupted output, and it is internal state either way.
            detail = event.detail or ""
            if detail.lstrip().startswith(("{", "[")):
                detail = "" if not verbose else detail
            # 2. Do not say "waiting" and then exit. In the console a parked run
            #    genuinely waits and can be resumed; a foreground build exits, so
            #    the CLI says what actually happened. The event is unchanged —
            #    only this renderer differs, because only here is it untrue.
            text = event.text
            if event.kind == "provider_unavailable":
                text = "stopped: " + (detail or text)
                detail = ""
            if event.kind == "audit_started":
                produced.add("yes")
            line = f"  {event.actor:10s} {text}"
            print(line if not detail
                  else f"{line}\n  {'':10s} {detail[:96]}")

        # The CLI narrator wraps the shell's emit; carry the lease-renewal
        # handle and the run identity across the wrapper so foreground
        # builds heartbeat and reference their run like console builds do.
        on_event.heartbeat = getattr(emit, "heartbeat", None)
        on_event.run_id = getattr(emit, "run_id", "")
        return run_loop(cfg, prepared.task, on_event=on_event)

    code = service.start(prepare, worker, background=False)
    assert isinstance(code, int)
    if code == EXIT_OK:
        print("\n  " + t("build.done"))
        print("  " + t("build.done.read"))
    elif not produced:
        # 3. State the outcome, then the remedy. "It is yours now" is a handoff
        #    after a success; nothing was produced. The blunt sentence is
        #    deliberate — it is what stops someone hunting for a partial result
        #    that does not exist.
        print("\n  " + t("build.nothing"))
        missing = _missing_role_keys(cfg)
        if missing:
            from . import wizard as _wizard
            print("\n  " + t("build.nothing.fix", path=_wizard.keys_file(),
                                envs=" and ".join(missing)))
        # The task is reprinted verbatim so the person does not have to
        # reconstruct what they typed.
        print("  " + t("build.nothing.then", task=prepared_task))
    else:
        # Something exists. The sentence above would be false, so say what is
        # there instead of claiming nothing is.
        print("\n  " + t("build.partial"))
    return code
