"""Local, privacy-preserving token metering and API-value estimates.

The ledger contains counts and routing metadata only.  Prompts, completions,
provider request ids, and credentials deliberately never enter it.  Token
counts are provider-reported when available and explicitly marked as estimates
when an OpenAI-compatible endpoint omits usage.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .errors import ProviderDenial
from .providers.base import Reply
from .providers.specs import PRICE_SNAPSHOT, Rates, capability_card

try:  # Unix advisory locking.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised by Windows CI
    _fcntl = None

try:  # Windows advisory locking.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised by Unix CI
    _msvcrt = None

LEDGER_NAME = "usage.jsonl"
_WRITE_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_SUMMARY_CACHE: dict[str, tuple[tuple, dict]] = {}
_LISTENERS: list[Callable[[], None]] = []


def _lock_file(fd: int) -> bool:
    """Serialize ledger appends across app and CLI processes."""
    if _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        return True
    if _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
        return True
    return False


def _unlock_file(fd: int) -> None:
    if _fcntl is not None:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
    elif _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)


def subscribe(listener: Callable[[], None]) -> None:
    """Wake live views immediately after a new usage event is durable."""
    with _CACHE_LOCK:
        _LISTENERS.append(listener)


def _nonnegative(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _rates(vendor: str, model: str, overrides: dict | None = None) -> Rates | None:
    """The model's price: a per-project override first, else its capability card.

    Price is part of a model's capability record, not a table kept in parallel
    here: unknown models resolve to a card with no price and stay unpriced while
    keeping their exact token counts. A project may declare its own rates for a
    model (``prices:`` in crossaudit.yml, USD per 1M tokens); those win over the
    snapshot and the event is stamped ``user_priced`` so the origin of every
    dollar figure stays legible.
    """
    override = price_override(overrides, model)
    if override is not None:
        return override
    return capability_card(vendor, model).price


def price_override(overrides: dict | None, model: str) -> Rates | None:
    """The user's declared rates for ``model``, or None when there are none."""
    if not isinstance(overrides, dict):
        return None
    row = overrides.get(model)
    if not isinstance(row, dict):
        return None
    try:
        return Rates(input=float(row.get("input", 0) or 0),
                     output=float(row.get("output", 0) or 0),
                     cache_write=float(row.get("cache_write", 0) or 0),
                     cache_read=float(row.get("cache_read", 0) or 0))
    except (TypeError, ValueError):
        return None


def normalise_usage(raw: dict, *, system: str = "", prompt: str = "",
                    response: str = "") -> dict:
    """Return one stable token vocabulary from OpenAI, Anthropic, or Codex."""
    usage = raw.get("usage") if isinstance(raw, dict) else None
    usage = usage if isinstance(usage, dict) else {}

    # Codex App Server tokenUsage.last uses camelCase and counts cached input in
    # inputTokens. OpenAI Chat Completions does the same in prompt_tokens.
    if any(k in usage for k in ("inputTokens", "outputTokens", "totalTokens")):
        inclusive = _nonnegative(usage.get("inputTokens"))
        cache_read = _nonnegative(usage.get("cachedInputTokens"))
        cache_write = _nonnegative(usage.get("cacheWriteInputTokens"))
        counts = {
            # Both cache classes are subsets of inputTokens. Keeping the four
            # buckets mutually exclusive makes their sum equal totalTokens.
            "input": max(0, inclusive - cache_read - cache_write),
            "output": _nonnegative(usage.get("outputTokens")),
            "cache_write": cache_write,
            "cache_read": cache_read,
        }
        method = "reported"
    elif any(k in usage for k in ("prompt_tokens", "completion_tokens")):
        details = usage.get("prompt_tokens_details")
        details = details if isinstance(details, dict) else {}
        inclusive = _nonnegative(usage.get("prompt_tokens"))
        cache_read = _nonnegative(details.get("cached_tokens"))
        counts = {
            "input": max(0, inclusive - cache_read),
            "output": _nonnegative(usage.get("completion_tokens")),
            "cache_write": 0,
            "cache_read": cache_read,
        }
        method = "reported"
    elif any(k in usage for k in ("input_tokens", "output_tokens")):
        counts = {
            "input": _nonnegative(usage.get("input_tokens")),
            "output": _nonnegative(usage.get("output_tokens")),
            "cache_write": _nonnegative(usage.get("cache_creation_input_tokens")),
            "cache_read": _nonnegative(usage.get("cache_read_input_tokens")),
        }
        method = "reported"
    else:
        # A transparent fallback for compatible/self-hosted endpoints. This is
        # deliberately approximate and is never presented as provider-reported.
        counts = {
            "input": math.ceil((len(system) + len(prompt)) / 4),
            "output": math.ceil(len(response) / 4),
            "cache_write": 0,
            "cache_read": 0,
        }
        method = "estimated"
    counts["total"] = sum(counts.values())
    counts["method"] = method
    return counts


def _api_value(counts: dict, rates: Rates | None) -> float | None:
    if rates is None:
        return None
    value = (
        counts["input"] * rates.input
        + counts["output"] * rates.output
        + counts["cache_write"] * rates.cache_write
        + counts["cache_read"] * rates.cache_read
    ) / 1_000_000
    return round(value, 10)


def _is_official(provider: str, base_url: str | None) -> bool:
    if provider == "openai_codex":
        return True
    if base_url:
        # Configured base URLs carry paths ("https://api.openai.com/v1"), so a
        # whole-string comparison would treat even the official endpoint as a
        # third-party proxy and silently drop it to "unpriced". Only the
        # origin decides who bills the call; anything else stays unpriced.
        parts = urlsplit(base_url)
        origin = f"{parts.scheme}://{parts.netloc}".casefold()
        return origin in {"https://api.openai.com", "https://api.anthropic.com"}
    return provider in {"openai_compat", "anthropic"}


#: Attribution the caller may hand a completion (all optional; old ledger lines
#: simply lack them). ``prices`` rides in the same context so the audit kernel
#: passes one opaque mapping through rather than learning about billing.
CONTEXT_ID_FIELDS = ("run_id", "cycle_id", "chat_id")
ROLES = ("generator", "auditor", "router")


def record_reply(*, root: Path, state_dir: str, role: str, phase: str,
                 vendor: str, provider: str, model: str, reply: Reply,
                 system: str, prompt: str, base_url: str | None = None,
                 context: dict | None = None) -> dict:
    """Append a completion's metadata, returning the exact persisted event.

    ``context`` is optional attribution: ``run_id``, ``cycle_id``, ``round``,
    ``chat_id``, ``duration_ms`` and the project's ``prices`` overrides. Fields
    that are absent or empty are not written, so a line recorded without them
    is byte-for-byte what the ledger always held (``v`` stays 1).
    """
    counts = normalise_usage(reply.raw, system=system, prompt=prompt,
                             response=reply.text)
    ctx = dict(context) if isinstance(context, dict) else {}
    prices = ctx.pop("prices", None)
    override = price_override(prices, model)
    subscription = provider == "openai_codex"
    if override is not None:
        rates, billing_kind = override, "user_priced"
    elif _is_official(provider, base_url):
        rates = _rates(vendor, model)
        billing_kind = ("subscription_api_value" if subscription and rates
                        else "api_value" if rates else "unpriced")
    else:
        rates, billing_kind = None, "unpriced"
    event = {
        "v": 1,
        "id": uuid.uuid4().hex,
        "t": int(time.time() * 1000),
        "role": role,
        "phase": phase,
        "vendor": vendor,
        "provider": provider,
        "model": model,
        **counts,
        "api_value_usd": _api_value(counts, rates),
        "billing_kind": billing_kind,
        "price_snapshot": PRICE_SNAPSHOT,
    }
    for key in CONTEXT_ID_FIELDS:
        value = str(ctx.get(key) or "").strip()
        if value:
            event[key] = value[:64]
    round_no = _nonnegative(ctx.get("round"))
    if round_no:
        event["round"] = round_no
    if ctx.get("duration_ms") is not None:
        event["duration_ms"] = _nonnegative(ctx.get("duration_ms"))
    path = root / state_dir / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    with _WRITE_LOCK:
        fd = os.open(path, flags, 0o600)
        locked = False
        try:
            # CLI and app workers are separate processes. O_APPEND protects the
            # offset; an advisory lock plus a complete write protects the record.
            locked = _lock_file(fd)
            os.chmod(path, 0o600)
            pending = memoryview(line.encode("utf-8"))
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise OSError("usage ledger write made no progress")
                pending = pending[written:]
            os.fsync(fd)
        finally:
            if locked:
                _unlock_file(fd)
            os.close(fd)
    with _CACHE_LOCK:
        _SUMMARY_CACHE.pop(str(path), None)
        listeners = tuple(_LISTENERS)
    for listener in listeners:
        try:
            listener()
        except Exception:
            # Metering can wake a UI, but a view listener can never be allowed
            # to turn a successful provider completion into a failed task.
            continue
    return event


def record_completion(**kwargs) -> dict | None:
    """Best-effort application hook: metering must not invalidate model work.

    The explicit ``record_reply`` API still raises for diagnostics and tests.
    Production completion paths use this wrapper because a full disk or a
    permissions problem in local analytics is not an audit-integrity failure.
    """
    try:
        return record_reply(**kwargs)
    except (OSError, ValueError, TypeError):
        return None


def _blank() -> dict:
    return {"calls": 0, "input": 0, "output": 0, "cache_write": 0,
            "cache_read": 0, "tokens": 0, "api_value_usd": 0.0,
            "reported_calls": 0, "estimated_calls": 0, "unpriced_calls": 0}


def _add(bucket: dict, event: dict) -> None:
    bucket["calls"] += 1
    for key in ("input", "output", "cache_write", "cache_read"):
        bucket[key] += _nonnegative(event.get(key))
    bucket["tokens"] += _nonnegative(event.get("total"))
    value = event.get("api_value_usd")
    if isinstance(value, (int, float)) and math.isfinite(value):
        bucket["api_value_usd"] += value
    if event.get("method") == "reported":
        bucket["reported_calls"] += 1
    else:
        bucket["estimated_calls"] += 1
    if value is None:
        bucket["unpriced_calls"] += 1


def _finish(bucket: dict) -> dict:
    bucket["api_value_usd"] = round(bucket["api_value_usd"], 8)
    return bucket


def _budget_view(cfg, today: dict, month: dict, *, now: datetime | None = None,
                 unpriced_models: list[dict] | None = None) -> dict:
    policy = getattr(cfg, "budgets", None)
    if policy is None:
        return {"state": "unconfigured", "warnings": [], "blocked": False}
    now = now or datetime.now().astimezone()
    warnings: list[str] = []
    reasons: list[str] = []
    blocked_by: list[str] = []
    daily_tokens = int(today.get("tokens", 0))
    month_cost = float(month.get("api_value_usd", 0.0))
    unpriced = int(month.get("unpriced_calls", 0))
    if policy.daily_token_warning and daily_tokens >= policy.daily_token_warning:
        warnings.append(
            f"Daily usage reached {daily_tokens:,} tokens (warning {policy.daily_token_warning:,}).")
    if policy.daily_token_limit and daily_tokens >= policy.daily_token_limit:
        reasons.append(
            f"Daily token limit reached: {daily_tokens:,} / {policy.daily_token_limit:,}.")
        blocked_by.append("daily")
    if policy.monthly_cost_warning_usd and month_cost >= policy.monthly_cost_warning_usd:
        warnings.append(
            f"Monthly API value reached ${month_cost:.2f} "
            f"(warning ${policy.monthly_cost_warning_usd:.2f}).")
    if policy.monthly_cost_limit_usd:
        if unpriced:
            reasons.append(
                "The monthly cost limit cannot be proven because one or more calls use "
                "an unpriced model. Remove the cost limit or select priced models.")
            blocked_by.append("unpriced")
        elif month_cost >= policy.monthly_cost_limit_usd:
            reasons.append(
                f"Monthly API-value limit reached: ${month_cost:.2f} / "
                f"${policy.monthly_cost_limit_usd:.2f}.")
            blocked_by.append("monthly")
    configured = any((policy.daily_token_warning, policy.daily_token_limit,
                      policy.monthly_cost_warning_usd,
                      policy.monthly_cost_limit_usd))
    return {
        "state": "blocked" if reasons else "warning" if warnings else
                 "ok" if configured else "unconfigured",
        "warnings": warnings,
        "reasons": reasons,
        "blocked": bool(reasons),
        "daily_tokens": daily_tokens,
        "daily_token_warning": policy.daily_token_warning,
        "daily_token_limit": policy.daily_token_limit,
        "monthly_api_value_usd": round(month_cost, 8),
        "monthly_cost_warning_usd": policy.monthly_cost_warning_usd,
        "monthly_cost_limit_usd": policy.monthly_cost_limit_usd,
        "unpriced_calls": unpriced,
        # Which guardrail closed the gate, so a card can say when it reopens.
        "blocked_by": blocked_by,
        "resets": reset_moments(now),
        # Threshold alarms already raised this period (80 % / 95 %), read from
        # the small file beside the ledger so a restart never re-fires them.
        "fired": budget_warning_state(cfg, now=now).get("active", []),
        "unpriced_models": list(unpriced_models or []),
        "price_snapshot": PRICE_SNAPSHOT,
    }


def enforce_budget(cfg, *, system: str = "", prompt: str = "") -> dict:
    """Refuse a new provider call after a configured hard guardrail is reached."""
    view = summary(cfg).get("budget", {})
    if view.get("blocked"):
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. " + " ".join(view["reasons"])
            + " Open Project controls to raise or clear the limit, then retry.",
            category="budget", retryable=False, budget=view)
    projected_input = math.ceil((len(system) + len(prompt)) / 4)
    limit = view.get("daily_token_limit")
    if limit and int(view.get("daily_tokens", 0)) + projected_input > int(limit):
        projected = dict(view)
        projected.update(blocked=True, state="blocked",
                         projected_input_tokens=projected_input)
        reason = (f"The next request is estimated to exceed the daily token limit: "
                  f"{int(view.get('daily_tokens', 0)):,} used + approximately "
                  f"{projected_input:,} input > {int(limit):,}.")
        projected["reasons"] = [*view.get("reasons", []), reason]
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. " + reason
            + " Open Project controls to raise or clear the limit, then retry.",
            category="budget", retryable=False, budget=projected)
    return view


def summary(cfg) -> dict:
    """Aggregate one project's local ledger for the live console snapshot."""
    path = cfg.root / cfg.state_dir / LEDGER_NAME
    now = datetime.now().astimezone()
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size, now.date().toordinal())
    except OSError:
        signature = (0, 0, now.date().toordinal())
    policy = getattr(cfg, "budgets", None)
    signature += tuple(getattr(policy, name, None) for name in (
        "daily_token_warning", "daily_token_limit", "monthly_cost_warning_usd",
        "monthly_cost_limit_usd"))
    signature += (_warning_signature(cfg),)
    cache_key = str(path)
    with _CACHE_LOCK:
        cached = _SUMMARY_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1]

    events, malformed = read_events(path) if signature[:2] != (0, 0) else ([], 0)

    today = now.date()
    month = (now.year, now.month)
    today_total, month_total, all_total = _blank(), _blank(), _blank()
    days = {today - timedelta(days=i): _blank() for i in range(6, -1, -1)}
    roles: dict[str, dict] = defaultdict(_blank)
    models: dict[tuple[str, str, str], dict] = defaultdict(_blank)
    recent: list[dict] = []
    for event in events:
        _add(all_total, event)
        try:
            when = datetime.fromtimestamp(int(event.get("t", 0)) / 1000,
                                         tz=now.tzinfo)
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        if when.date() == today:
            _add(today_total, event)
        if (when.year, when.month) == month:
            _add(month_total, event)
            role = str(event.get("role", "unknown"))[:40]
            _add(roles[role], event)
            key = (str(event.get("model", "unknown"))[:160], role,
                   str(event.get("provider", "unknown"))[:80])
            _add(models[key], event)
        if when.date() in days:
            _add(days[when.date()], event)
        recent.append({
            "t": int(event.get("t", 0) or 0),
            "role": str(event.get("role", "unknown"))[:40],
            "phase": str(event.get("phase", "completion"))[:80],
            "provider": str(event.get("provider", "unknown"))[:80],
            "model": str(event.get("model", "unknown"))[:160],
            "input": _nonnegative(event.get("input")),
            "output": _nonnegative(event.get("output")),
            "cache_write": _nonnegative(event.get("cache_write")),
            "cache_read": _nonnegative(event.get("cache_read")),
            "tokens": _nonnegative(event.get("total")),
            "method": "reported" if event.get("method") == "reported" else "estimated",
            "api_value_usd": event.get("api_value_usd"),
            "billing_kind": str(event.get("billing_kind", "unpriced")),
        })
    model_rows = []
    for (model, role, provider), value in models.items():
        model_rows.append({"model": model, "role": role, "provider": provider,
                           **_finish(value)})
    model_rows.sort(key=lambda row: (-row["tokens"], row["model"], row["role"]))
    result = {
        "today": _finish(today_total),
        "month": _finish(month_total),
        "all": _finish(all_total),
        "days": [{"date": day.isoformat(), **_finish(value)}
                 for day, value in days.items()],
        "roles": [{"role": role, **_finish(value)}
                  for role, value in sorted(roles.items())],
        "models": model_rows,
        "recent": sorted(recent, key=lambda row: row["t"], reverse=True)[:30],
        "price_snapshot": PRICE_SNAPSHOT,
        "malformed_lines": malformed,
        "local_only": True,
        "cost_label": "API-value estimate",
    }
    result["attribution"] = attribution(events)
    result["budget"] = _budget_view(
        cfg, result["today"], result["month"], now=now,
        unpriced_models=unpriced_models(events, now=now))
    with _CACHE_LOCK:
        _SUMMARY_CACHE[cache_key] = (signature, result)
    return result


# =========================================================================
# Attribution, warnings-as-events, exports and roll-ups (billing slice).
# Everything below is pure over the ledger's event dicts, or reads/writes one
# small JSON file beside the ledger; nothing here reaches another app's files
# or a vendor's usage endpoint.
# =========================================================================

WARNINGS_NAME = "usage-warnings.json"
#: AgentIsland-style alarm thresholds, as a percentage of the configured budget.
WARNING_THRESHOLDS = (80, 95)
#: How many of the most-recent runs / cycles / chats / calls ride in a state
#: frame. The full ledger remains queryable through the export endpoint.
ATTRIBUTION_WINDOW = 50
TURN_WINDOW = 200
#: Columns of the CSV export: the event fields, the attribution, the value.
EXPORT_COLUMNS = ("t", "iso", "role", "phase", "vendor", "provider", "model",
                  "input", "output", "cache_write", "cache_read", "total",
                  "method", "api_value_usd", "billing_kind", "price_snapshot",
                  "run_id", "cycle_id", "round", "chat_id", "duration_ms")


def read_events(path: Path) -> tuple[list[dict], int]:
    """Every parseable event line of a ledger, plus the count of malformed lines.

    Old lines without attribution fields are events like any other: readers
    below treat every attribution field as optional.
    """
    events: list[dict] = []
    malformed = 0
    try:
        with Path(path).open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except (ValueError, TypeError):
                    malformed += 1
                    continue
                if isinstance(item, dict):
                    events.append(item)
                else:
                    malformed += 1
    except OSError:
        return [], 0
    return events, malformed


def project_events(cfg) -> list[dict]:
    """The project's ledger events (malformed lines dropped)."""
    return read_events(Path(cfg.root) / cfg.state_dir / LEDGER_NAME)[0]


def _blank_attributed() -> dict:
    return {**_blank(), "first_t": 0, "last_t": 0, "duration_ms": 0}


def _add_attributed(bucket: dict, event: dict) -> None:
    _add(bucket, event)
    when = _nonnegative(event.get("t"))
    if when:
        bucket["first_t"] = when if not bucket["first_t"] else min(bucket["first_t"], when)
        bucket["last_t"] = max(bucket["last_t"], when)
    bucket["duration_ms"] += _nonnegative(event.get("duration_ms"))


def aggregate_by(events: list[dict], key: str) -> dict[str, dict]:
    """Totals per distinct value of ``key`` (events lacking it are skipped)."""
    out: dict[str, dict] = {}
    for event in events:
        value = str(event.get(key) or "").strip()
        if not value:
            continue
        bucket = out.setdefault(value, _blank_attributed())
        _add_attributed(bucket, event)
    return {value: _finish(bucket) for value, bucket in out.items()}


def per_run(events: list[dict], run_id: str) -> dict:
    """Totals for one run: tokens, cache, ≈value, calls, reported/estimated."""
    return aggregate_by(events, "run_id").get(run_id) or _finish(_blank_attributed())


def per_cycle(events: list[dict], cycle_id: str) -> dict:
    return aggregate_by(events, "cycle_id").get(cycle_id) or _finish(_blank_attributed())


def per_chat(events: list[dict], chat_id: str) -> dict:
    return aggregate_by(events, "chat_id").get(chat_id) or _finish(_blank_attributed())


def _recent_keys(groups: dict[str, dict], limit: int) -> dict[str, dict]:
    ordered = sorted(groups.items(), key=lambda item: item[1]["last_t"], reverse=True)
    return dict(ordered[:limit])


def attribution(events: list[dict]) -> dict:
    """Per-run / per-cycle / per-chat totals plus a compact per-call tail.

    The tail (``turns``) is what the chat surface uses to put one muted cost
    line under a completed turn; it carries counts, ids and a duration only.
    """
    turns = []
    for event in events[-TURN_WINDOW:]:
        turns.append({
            "t": _nonnegative(event.get("t")),
            "role": str(event.get("role", "unknown"))[:40],
            "phase": str(event.get("phase", "completion"))[:80],
            "chat_id": str(event.get("chat_id") or "")[:64],
            "run_id": str(event.get("run_id") or "")[:64],
            "cycle_id": str(event.get("cycle_id") or "")[:64],
            "round": _nonnegative(event.get("round")),
            "tokens": _nonnegative(event.get("total")),
            "api_value_usd": (event.get("api_value_usd")
                              if isinstance(event.get("api_value_usd"), (int, float))
                              else None),
            "duration_ms": _nonnegative(event.get("duration_ms")),
        })
    return {
        "runs": _recent_keys(aggregate_by(events, "run_id"), ATTRIBUTION_WINDOW),
        "cycles": _recent_keys(aggregate_by(events, "cycle_id"), ATTRIBUTION_WINDOW),
        "chats": _recent_keys(aggregate_by(events, "chat_id"), ATTRIBUTION_WINDOW),
        "turns": turns,
    }


def _event_time(event: dict, tz) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(event.get("t", 0)) / 1000, tz=tz)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def unpriced_models(events: list[dict], *, now: datetime | None = None) -> list[dict]:
    """This month's unpriced calls, grouped by model, for a visible fail-close.

    A monthly cost limit that cannot be proven pauses the loop; that pause must
    name the model and the snapshot it was missing from, never stay silent.
    """
    now = now or datetime.now().astimezone()
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for event in events:
        if event.get("api_value_usd") is not None:
            continue
        when = _event_time(event, now.tzinfo)
        if when is None or (when.year, when.month) != (now.year, now.month):
            continue
        counts[(str(event.get("model", "unknown"))[:160],
                str(event.get("vendor", "unknown"))[:40])] += 1
    rows = [{"model": model, "vendor": vendor, "calls": calls,
             "price_snapshot": PRICE_SNAPSHOT}
            for (model, vendor), calls in counts.items()]
    rows.sort(key=lambda row: (-row["calls"], row["model"]))
    return rows


# ------------------------------------------------------------ warnings
def _warning_path(cfg) -> Path:
    return Path(cfg.root) / cfg.state_dir / WARNINGS_NAME


def _warning_signature(cfg) -> tuple:
    try:
        stat = _warning_path(cfg).stat()
        return (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return (0, 0)


def _load_warnings(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_warnings(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    temp.replace(path)


def period_keys(now: datetime) -> dict[str, str]:
    """The budget periods a moment belongs to: the day and the month."""
    return {"daily": now.date().isoformat(), "monthly": f"{now.year:04d}-{now.month:02d}"}


def reset_moments(now: datetime) -> dict[str, str]:
    """When each budget period rolls over, in words, EN and ZH."""
    first_next = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    return {
        "daily": "Resets at midnight",
        "daily_zh": "明天 0:00 重置",
        "monthly": f"Resets on {_MONTHS[first_next.month - 1]} {first_next.day}",
        "monthly_zh": f"{first_next.month} 月 {first_next.day} 日重置",
    }


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
           "Nov", "Dec")


def warning_sentence(kind: str, threshold: int) -> dict[str, str]:
    """The plain sentence a threshold alarm says, in both languages."""
    if kind == "daily":
        return {"en": f"Today's token budget is {threshold}% used",
                "zh": f"今日 token 预算已用 {threshold}%"}
    return {"en": f"This month's cost budget is {threshold}% used",
            "zh": f"本月费用预算已用 {threshold}%"}


def budget_figures(cfg, view: dict) -> dict[str, tuple[float, float]]:
    """(used, budget) per period. The budget is the hard limit when one is set,
    else the warning line; a period with neither is not returned."""
    policy = getattr(cfg, "budgets", None)
    out: dict[str, tuple[float, float]] = {}
    if policy is None:
        return out
    daily = policy.daily_token_limit or policy.daily_token_warning
    if daily:
        out["daily"] = (float(view.get("daily_tokens", 0) or 0), float(daily))
    monthly = policy.monthly_cost_limit_usd or policy.monthly_cost_warning_usd
    if monthly:
        out["monthly"] = (float(view.get("monthly_api_value_usd", 0.0) or 0.0),
                          float(monthly))
    return out


def _warning_row(kind: str, threshold: int, period: str, now: datetime,
                 used: float, budget: float) -> dict:
    sentence = warning_sentence(kind, threshold)
    resets = reset_moments(now)
    percent = int(min(999, math.floor(used * 100 / budget))) if budget else 0
    return {"budget": kind, "threshold": threshold, "period": period,
            "percent": percent, "text": sentence["en"], "text_zh": sentence["zh"],
            "resets": resets[kind], "resets_zh": resets[f"{kind}_zh"]}


def budget_warning_state(cfg, *, now: datetime | None = None) -> dict:
    """What has already fired this period (rolled over in memory when stale)."""
    now = now or datetime.now().astimezone()
    periods = period_keys(now)
    stored = _load_warnings(_warning_path(cfg))
    state: dict = {}
    active: list[dict] = []
    for kind, period in periods.items():
        row = stored.get(kind) if isinstance(stored.get(kind), dict) else {}
        fired = row.get("fired") if row.get("period") == period else []
        fired = sorted({int(v) for v in fired if isinstance(v, (int, float))
                        and int(v) in WARNING_THRESHOLDS}) if isinstance(fired, list) else []
        state[kind] = {"period": period, "fired": fired}
        for threshold in fired:
            active.append(_warning_row(kind, threshold, period, now, 0.0, 0.0))
    state["active"] = active
    return state


def check_budget_warnings(cfg, *, now: datetime | None = None) -> list[dict]:
    """Fire any threshold newly crossed; persist so a restart cannot re-fire.

    Returns only the alarms raised by THIS call (AgentIsland's rule: an alarm
    sounds once per threshold and re-arms only when a genuinely new period
    begins). Unconfigured budgets never fire. The summary cache is dropped so
    the next frame carries the new state.
    """
    now = now or datetime.now().astimezone()
    view = summary(cfg).get("budget", {})
    figures = budget_figures(cfg, view)
    if not figures:
        return []
    path = _warning_path(cfg)
    periods = period_keys(now)
    stored = _load_warnings(path)
    fired_now: list[dict] = []
    changed = False
    for kind, (used, budget) in figures.items():
        period = periods[kind]
        row = stored.get(kind) if isinstance(stored.get(kind), dict) else {}
        already = (row.get("fired") if row.get("period") == period else None) or []
        already = [int(v) for v in already if isinstance(v, (int, float))]
        if row.get("period") != period:
            changed = True
        for threshold in WARNING_THRESHOLDS:
            if threshold in already or budget <= 0:
                continue
            if used * 100 >= threshold * budget:
                already.append(threshold)
                fired_now.append(_warning_row(kind, threshold, period, now, used, budget))
                changed = True
        stored[kind] = {"period": period, "fired": sorted(set(already))}
    if changed:
        try:
            _save_warnings(path, stored)
        except OSError:
            return fired_now
        with _CACHE_LOCK:
            _SUMMARY_CACHE.pop(str(Path(cfg.root) / cfg.state_dir / LEDGER_NAME), None)
    return fired_now


# ------------------------------------------------------------ export
def _in_period(when: datetime | None, period: str, now: datetime) -> bool:
    if period == "all":
        return True
    if when is None:
        return False
    if period == "day":
        return when.date() == now.date()
    return (when.year, when.month) == (now.year, now.month)


def export_rows(cfg, period: str = "month", *, now: datetime | None = None) -> list[dict]:
    """The ledger as flat rows (one per completion), oldest first.

    Counts, routing metadata, attribution and ≈value only — the ledger never
    held prompts, replies or credentials, so neither can an export of it.
    """
    now = now or datetime.now().astimezone()
    if period not in ("day", "month", "all"):
        raise ValueError("period must be day, month or all")
    rows = []
    for event in project_events(cfg):
        when = _event_time(event, now.tzinfo)
        if not _in_period(when, period, now):
            continue
        row = {column: event.get(column) for column in EXPORT_COLUMNS}
        row["t"] = _nonnegative(event.get("t"))
        row["iso"] = when.isoformat(timespec="seconds") if when else ""
        for column in ("input", "output", "cache_write", "cache_read", "total"):
            row[column] = _nonnegative(event.get(column))
        row["method"] = "reported" if event.get("method") == "reported" else "estimated"
        row["billing_kind"] = str(event.get("billing_kind", "unpriced"))
        rows.append(row)
    rows.sort(key=lambda r: r["t"])
    return rows


def export_csv(rows: list[dict]) -> str:
    import csv
    import io

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(EXPORT_COLUMNS), extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k))
                         for k in EXPORT_COLUMNS})
    return out.getvalue()


# ------------------------------------------------------------ roll-up
def project_rollup(cfg, *, now: datetime | None = None) -> dict:
    """One project's line in the workspace table: today / month / budget state."""
    result = summary(cfg)
    budget = result.get("budget", {})
    return {
        "name": Path(cfg.root).name,
        "root": str(cfg.root),
        "today_tokens": int(result["today"]["tokens"]),
        "today_api_value_usd": float(result["today"]["api_value_usd"]),
        "month_tokens": int(result["month"]["tokens"]),
        "month_api_value_usd": float(result["month"]["api_value_usd"]),
        "month_calls": int(result["month"]["calls"]),
        "unpriced_calls": int(result["month"].get("unpriced_calls", 0)),
        "budget_state": str(budget.get("state", "unconfigured")),
        "has_usage": int(result["all"]["calls"]) > 0,
    }


def workspace_rollup(configs, *, now: datetime | None = None) -> dict:
    """Every project the app knows, plus a "this month across projects" total."""
    rows = []
    for cfg in configs:
        try:
            rows.append(project_rollup(cfg, now=now))
        except (OSError, ValueError, TypeError, KeyError):
            continue
    rows.sort(key=lambda row: (-row["month_api_value_usd"], -row["month_tokens"],
                               row["name"].lower()))
    total = {
        "projects": len(rows),
        "today_tokens": sum(r["today_tokens"] for r in rows),
        "today_api_value_usd": round(sum(r["today_api_value_usd"] for r in rows), 8),
        "month_tokens": sum(r["month_tokens"] for r in rows),
        "month_api_value_usd": round(sum(r["month_api_value_usd"] for r in rows), 8),
        "unpriced_calls": sum(r["unpriced_calls"] for r in rows),
    }
    return {"projects": rows, "total": total, "price_snapshot": PRICE_SNAPSHOT,
            "local_only": True}


def monthly_report(result: dict, *, passed_audits: int | None = None) -> dict:
    """The month's report card as plain rows: top models, role share, audits."""
    month = result.get("month", {})
    models = sorted(result.get("models", []), key=lambda r: -r["tokens"])[:5]
    roles = {row["role"]: row for row in result.get("roles", [])}
    total_tokens = max(1, int(month.get("tokens", 0)))
    share = {role: round(int(roles[role]["tokens"]) * 100 / total_tokens)
             for role in roles}
    return {
        "top_models": [{"model": r["model"], "role": r["role"], "tokens": r["tokens"],
                        "api_value_usd": r["api_value_usd"],
                        "unpriced_calls": r.get("unpriced_calls", 0)} for r in models],
        "role_share": share,
        "calls": int(month.get("calls", 0)),
        "tokens": int(month.get("tokens", 0)),
        "api_value_usd": float(month.get("api_value_usd", 0.0)),
        "unpriced_calls": int(month.get("unpriced_calls", 0)),
        "passed_audits": passed_audits,
    }
