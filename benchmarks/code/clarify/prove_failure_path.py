#!/usr/bin/env python3
"""Prove that a provider refusal is recorded as a refusal, not as a gate violation.

This path was wrong once and the wrongness was invisible: `ask` returned "" after three failed
attempts, the empty specification reached the gates, and the record said the instance was
dropped because "an edited condition added no words". That sentence would have entered the
study as the reason an instance was lost.

The provider is replaced with one that raises -- the real loop, the real gates and the real
record writer all run. No network call is made.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "benchmarks/code")
sys.path.insert(0, "benchmarks/expertlongbench")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate  # noqa: E402

OUT = Path("benchmarks/code/records/clarify/conditions-smoke.json")


def run(always_raise: bool) -> dict:
    calls = {"n": 0}

    class Reply:
        text = ("Write a function to find the Eulerian number a(n, m). Counts are taken over "
                "permutations of the given length with the stated number of descents, and the "
                "result is returned as a single integer value for those inputs always.")

    def fake_complete(**kw):
        calls["n"] += 1
        if always_raise:
            raise RuntimeError("ProviderDenial: refused")
        return Reply()

    generate.provider.complete = fake_complete           # the real loop, a fake wire
    os.environ["P3_LIMIT"] = "1"
    OUT.unlink(missing_ok=True)
    generate.main()
    rec = json.loads(OUT.read_text(encoding="utf-8"))
    rec["_calls"] = calls["n"]
    return rec


def main() -> int:
    failures = []

    denied = run(always_raise=True)
    if denied["n_generation_failed"] != 1:
        failures.append(f"a refused instance was not recorded as a generation failure: {denied}")
    if denied["n_dropped_by_gate"] != 0:
        failures.append("a refused instance was recorded as dropped BY A GATE -- the exact "
                        f"false record this check exists to prevent: {denied['dropped']}")
    if denied["_calls"] != 3:
        failures.append(f"expected 3 attempts before giving up, got {denied['_calls']}")
    why = (denied.get("generation_failed") or [{}])[0].get("why", "")
    if "ProviderDenial" not in why:
        failures.append(f"the record does not say what the provider said: {why!r}")

    # The other direction: a reply that arrives must NOT be recorded as a generation failure.
    served = run(always_raise=False)
    if served["n_generation_failed"] != 0:
        failures.append(f"a served instance was recorded as a generation failure: {served}")

    OUT.unlink(missing_ok=True)
    for f in failures:
        print(f"  [FAIL] {f}")
    if failures:
        return 1
    print("  [ok ] a refusal is recorded as a refusal, with the provider's own words")
    print("  [ok ] a refusal is NOT recorded as a gate drop")
    print("  [ok ] a served reply is not recorded as a refusal")
    print("\nthe failure path behaves in both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
