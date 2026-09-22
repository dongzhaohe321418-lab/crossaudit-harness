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


def run_all(instance_id: str, conditions: dict[str, dict], witness: dict,
            hidden_program: str) -> list[str]:
    """Every gate for one instance. Returns the problems; empty means it may be bought."""
    out = gate_code_identity(conditions)
    out += gate_no_leak(conditions["clarified"]["spec"], witness, hidden_program)
    out += gate_placebo_length(conditions["clarified"]["spec"],
                               conditions["placebo"]["spec"],
                               conditions["original"]["spec"])
    return [f"{instance_id}: {p}" for p in out]
