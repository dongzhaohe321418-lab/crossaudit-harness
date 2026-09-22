#!/usr/bin/env python3
"""P3's three gates. Each must be proved able to fail before anything is spent.

Registered at `plan/P3-PREREGISTRATION.md` §5. The design manipulates the specification and
nothing else, so the gates exist to check exactly that: that nothing else moved, that the
clarification does not hand over the answer, and that the placebo is comparable in length.

This programme has a standing rule that a gate nobody has seen fail is not a gate. Each
function here has a matching planted violation in `prove_gates.py`.
"""
from __future__ import annotations

import hashlib
import re


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gate_code_identity(conditions: dict[str, dict]) -> list[str]:
    """GATE 1 — the candidate and the visible suite are byte-identical across conditions.

    The whole claim of this design is that only the specification differs. A single differing
    byte in the code or the visible tests makes the contrast something else entirely.
    """
    problems = []
    for field in ("candidate", "visible_tests"):
        seen = {name: digest(c[field]) for name, c in conditions.items()}
        if len(set(seen.values())) != 1:
            problems.append(f"{field} differs across conditions: "
                            + ", ".join(f"{n}={d[:8]}" for n, d in sorted(seen.items())))
    return problems


def gate_no_leak(clarified: str, witness: dict, hidden_program: str) -> list[str]:
    """GATE 2 — the clarification states the rule, not the failure.

    A clarification may add the behavioural rule the prose never settled. It may not contain
    the failing input, the value the hidden suite expects there, or a line lifted from the
    hidden test. A text that describes the failure is a leak: the auditor would be diagnosing
    a defect it was handed rather than one it found.
    """
    if not isinstance(hidden_program, str):
        raise TypeError(
            "gate_no_leak needs the hidden program's TEXT, not "
            f"{type(hidden_program).__name__}. `Problem.hidden_program` is a method taking the "
            "solution and returning (text, bool); passing the bound method made the first run "
            "die inside the gate rather than fail the instance.")
    problems = []
    body = " ".join(clarified.split())
    for case in (witness.get("cases") or [])[:8]:
        for field in ("input", "expected"):
            val = str(case.get(field) or "").strip()
            if len(val) >= 3 and val in body:
                problems.append(f"clarification contains the {field} of a failing case: {val[:60]!r}")
    for line in hidden_program.splitlines():
        line = " ".join(line.split())
        if len(line) >= 25 and line in body:
            problems.append(f"clarification quotes a hidden-test line: {line[:60]!r}")
    return problems


def gate_placebo_length(clarified: str, placebo: str, original: str,
                        tolerance: float = 0.15) -> list[str]:
    """GATE 3 — the placebo adds a comparable amount of text.

    The placebo controls for two things at once: that the specification was edited at all, and
    that it got longer. Neither control works if the two edits are different sizes.
    """
    base = len(original.split())
    added_c = len(clarified.split()) - base
    added_p = len(placebo.split()) - base
    if added_c <= 0 or added_p <= 0:
        return [f"an edited condition added no words: clarified +{added_c}, placebo +{added_p}"]
    ratio = added_p / added_c
    if not (1 - tolerance) <= ratio <= (1 + tolerance):
        return [f"added word counts differ by more than {tolerance:.0%}: "
                f"clarified +{added_c}, placebo +{added_p} (ratio {ratio:.2f})"]
    return []


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", flat) if p.strip()]


def gate_preserves_original(edited: str, original: str, arm: str) -> list[str]:
    """Gate 4: the edit ADDED to the specification and changed nothing that was there.

    Both generators are instructed to "change no sentence that is already there", and until
    2026-09-22 nothing checked it.

    The check is order-preserving containment at SENTENCE granularity, not line granularity.
    The first draft of this gate compared lines and failed its own clean fixture: appending a
    sentence to an existing paragraph rewrites that line while deleting nothing, which is
    exactly what the generators are asked to do. Sentences are the unit the instruction is
    written in, so they are the unit the gate checks.
    """
    edited_flat = " ".join(edited.split())
    pos = 0
    for sent in _sentences(original):
        idx = edited_flat.find(sent, pos)
        if idx < 0:
            return [f"{arm} does not preserve the original prose; sentence missing or "
                    f"reordered: {sent[:60]!r}"]
        pos = idx + len(sent)
    return []


def gate_no_scaffolding(edited: str, scaffold_lines: list[str], arm: str) -> list[str]:
    """Gate 5: none of the PROMPT's own structure appears in the edited specification.

    The smoke run returned specifications beginning with a `SPECIFICATION:` header echoed back
    out of the prompt -- present in two of three edited arms and in no original. Gate 4 cannot
    see it: prepending a line deletes nothing, so every original sentence is still there in
    order. A leak gate cannot see it either; it carries no hidden information.

    What it does carry is a label. An arm that is visibly marked as edited is readable by the
    determinacy rater whose blinding the manipulation check depends on, and by the auditor
    afterwards. The gate is therefore stated over the scaffolding as a whole rather than over
    the one header that was observed: the caller passes the lines it used to BUILD the prompt,
    and none of them may appear in what comes back.
    """
    flat = " ".join(edited.split())
    for line in scaffold_lines:
        line = " ".join(line.split())
        if line and line in flat:
            return [f"{arm} echoes the prompt's scaffolding: {line[:60]!r}"]
    return []


def run_all(instance_id: str, conditions: dict[str, dict], witness: dict,
            hidden_program: str,
            scaffold_lines: list[str] | None = None) -> list[str]:
    """Every gate for one instance. Returns the problems; empty means it may be bought."""
    out = gate_code_identity(conditions)
    out += gate_no_leak(conditions["clarified"]["spec"], witness, hidden_program)
    out += gate_placebo_length(conditions["clarified"]["spec"],
                               conditions["placebo"]["spec"],
                               conditions["original"]["spec"])
    for arm in ("clarified", "placebo"):
        out += gate_preserves_original(conditions[arm]["spec"],
                                       conditions["original"]["spec"], arm)
        out += gate_no_scaffolding(conditions[arm]["spec"], scaffold_lines or [], arm)
    return [f"{instance_id}: {p}" for p in out]
