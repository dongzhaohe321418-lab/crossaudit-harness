"""Human rulings on escalations, recorded in the audit ledger (D172 ruling 5).

`crossaudit resolve <cycle> --reopen/--close --because "..."` is the human
answer to an escalation. The README promises "The reason is committed to the
ledger"; it used to live only in the gitignored controller state. A ruling is
now one line appended to ``<ledger>/rulings.jsonl`` -- the same append-only
JSONL shape as ``routing.jsonl`` and ``disputes.jsonl`` beside the receipts --
and committed on its own, with the reason in the commit message.

Append-only: a line is never rewritten or removed, so a second ruling on the
same cycle adds a line and both stay readable, in order. Readers split on
"\\n" only (see D168: ``str.splitlines`` also splits on U+2028/U+2029/U+0085,
which a reason may carry).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .gitio import git

RULINGS_LOG = "rulings.jsonl"


def log_path(cfg) -> Path:
    return Path(cfg.root) / cfg.ledger_dir / RULINGS_LOG


def _who(cfg) -> str:
    name = git("config", "user.name", cwd=cfg.root, check=False).strip()
    email = git("config", "user.email", cwd=cfg.root, check=False).strip()
    return f"{name} <{email}>" if email else name


def record(cfg, cycle: dict, action: str, reason: str) -> dict:
    """Append one ruling and commit exactly that file. Returns the row,
    with the ledger commit that carries it under ``commit``."""
    now = time.time()
    row = {
        "cycle_id": cycle["cycle_id"],
        "action": action,
        "reason": reason,
        "by": _who(cfg),
        "t": int(now),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "round": cycle.get("round"),
        "active_sha": cycle.get("active_sha", ""),
        "status_after": cycle.get("status", ""),
        "escalation_reason": str(cycle.get("escalation_reason", ""))[:400],
    }
    path = log_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    rel = path.relative_to(cfg.root).as_posix()
    first = reason.strip().splitlines()[0] if reason.strip() else ""
    subject = f"ruling {cycle['cycle_id']} {action}: {first}"
    if len(subject) > 120:
        subject = subject[:117] + "..."
    git("add", "--", rel, cwd=cfg.root)
    # Only this file: anything else the person has staged stays staged.
    git("commit", "-q", "-m", subject, "-m",
        f"Human ruling on escalated cycle {cycle['cycle_id']} "
        f"(round {cycle.get('round')}, {str(cycle.get('active_sha', ''))[:12]}): "
        f"{action}.\n\nReason:\n{reason}\n\nBy: {row['by']}\nAt: {row['at']}",
        "--", rel, cwd=cfg.root)
    row["commit"] = git("rev-parse", "HEAD", cwd=cfg.root)
    return row


def history(cfg) -> list[dict]:
    path = log_path(cfg)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("cycle_id"):
            rows.append(row)
    return rows


def by_cycle(cfg) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in history(cfg):
        out.setdefault(str(row["cycle_id"]), []).append(row)
    return out
