"""Governed-source provenance (A4): bind WHICH literature sources a research
cycle retrieved through the human-approved governed tools — additively.

An audit already binds the evidence-ledger head (``tool_evidence``), so the whole
set of governed retrievals is cryptographically covered. This module re-projects
that already-bound prefix into a small, self-contained receipt view: the set of
per-source provenance ids (``source_id`` for each web page and each paper
retrieved through ``web_fetch`` / ``paper_search``), so a verifier — and, in the
next slice, a deterministic citation check — can enumerate exactly what was
governed-fetched without re-reading the whole ledger.

Present only when the cycle actually ran a governed research retrieval, so a
non-research receipt stays byte-identical to a pre-A4 receipt (additive, exactly
like ``tool_evidence`` and ``reproduction``). ``verify`` re-derives the set from
the same ledger prefix and refuses a mismatch.

Honest scope (never overclaim, §3.3): the block attests, over governed-tool
observations only, WHICH sources were retrieved through human-approved tools and
their per-source provenance id. It does NOT attest that the remote server was
honest or still serves those bytes, that a cited claim is true (CrossAudit audits
provenance and internal consistency, never ground truth), nor — in this slice —
that the report cites only these sources (that deterministic guarantee is the
following check). ``count`` is the number of distinct governed-fetched sources;
a ``paper_search`` id hashes a paper's public identity (id+url), not its text.
"""
from __future__ import annotations

import hashlib
import json

#: The governed retrieval tools whose results are literature sources.
RESEARCH_TOOLS = frozenset({"web_fetch", "paper_search"})

BUNDLE_SCHEMA = "crossaudit/sources/v1"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def set_digest(source_ids) -> str:
    """The digest bound in the receipt: sha256 over the sorted, de-duplicated
    source-id set (matches the receipt canonical form)."""
    return _sha256_hex(_canonical({"source_ids": sorted(set(source_ids))}))


def _collect(cfg, prefix_count: int) -> tuple[list[str], list[str], list[str]]:
    """Walk the evidence ledger over exactly the ``tool_evidence``-bound prefix
    and return (unique sorted source_ids, sorted origins, sorted tools) from the
    SUCCEEDED governed-research rows. Derives over ``entries[:prefix_count]`` — not
    the live ledger — so a later round's appends never change re-derivation."""
    from ..ledger import EvidenceLedger
    led = EvidenceLedger(cfg.root / cfg.state_dir / "evidence.jsonl")
    rows = led.entries()[:prefix_count]
    ids: set[str] = set()
    origins: set[str] = set()
    tools: set[str] = set()
    for row in rows:
        if row.get("kind") != "tool_result":
            continue
        payload = row.get("payload") or {}
        if payload.get("tool") not in RESEARCH_TOOLS:
            continue
        if payload.get("status") != "succeeded":
            continue
        sids = payload.get("source_ids") or []
        if not isinstance(sids, list) or not sids:
            continue
        for sid in sids:
            if isinstance(sid, str) and sid:
                ids.add(sid)
        origin = payload.get("host") or payload.get("source")
        if origin:
            origins.add(str(origin))
        tools.add(str(payload.get("tool")))
    return sorted(ids), sorted(origins), sorted(tools)


def bundle(cfg, receipt: dict) -> dict | None:
    """The expanded, human/tool-facing ``sources.json`` sidecar, or ``None`` when
    the cycle retrieved no governed literature source."""
    te = receipt.get("tool_evidence")
    if not isinstance(te, dict) or "entries" not in te:
        return None
    try:
        prefix = int(te["entries"])
    except (TypeError, ValueError):
        return None
    ids, origins, tools = _collect(cfg, prefix)
    if not ids:
        return None
    return {
        "schema": BUNDLE_SCHEMA,
        "count": len(ids),
        "source_ids": ids,
        "origins": origins,
        "tools": tools,
        "note": ("Per-source provenance ids for the literature retrieved through "
                 "the human-approved governed tools. Attests what was fetched and "
                 "from where; not the remote server's honesty, URL persistence, or "
                 "the truth of any cited claim."),
    }


def receipt_block(cfg, receipt: dict) -> dict | None:
    """The compact optional ``sources`` block for the receipt, or ``None`` when
    the cycle retrieved no governed literature source (so the receipt stays
    byte-identical to a pre-A4 receipt). Fail-safe: any read problem yields
    ``None`` and never breaks receipt assembly."""
    try:
        full = bundle(cfg, receipt)
    except Exception:  # noqa: BLE001 -- provenance projection never blocks a receipt
        return None
    if full is None:
        return None
    return {
        "set_sha256": set_digest(full["source_ids"]),
        "count": full["count"],
        "origins": full["origins"],
    }
