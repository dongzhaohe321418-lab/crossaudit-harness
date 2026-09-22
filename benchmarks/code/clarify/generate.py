#!/usr/bin/env python3
"""P3 — generate the clarified and placebo specifications. Registered before this ran.

One model call per instance per edited condition, over the 44-instance population frozen in
`records/clarify/population.json`. The original condition is the dataset's own prose and costs
nothing.

**The generator is shown the specification and the witness; the auditor is shown neither the
witness nor the code's failure.** That asymmetry is the design: a clarification can only be
written by someone who knows which rule was left open, and the point is to test whether writing
it down changes what a reader of the code can diagnose.

**What the generator may not do is put the failure into the prose.** Gate 2 checks that
mechanically afterwards, and an instance that fails it is regenerated once and then dropped with
its reason recorded, rather than being edited by hand into compliance.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "benchmarks/code")
sys.path.insert(0, "benchmarks/expertlongbench")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gates  # noqa: E402
from corpus import load_problems  # noqa: E402
from crossaudit.providers import openai_compat as provider  # noqa: E402

# Amendment 3: the clarifier must NOT be the auditor that will read these specs. The
# first draft had it set to gpt-5.6-terra -- the shipped cross auditor, which missed
# these very instances -- writing the clarifications it would then be asked to read.
# Amendment 4: claude-sonnet-4-6 cannot run -- the Anthropic credit is exhausted.
# Of the OpenAI models, terra is the auditor and astra is one of the families whose
# misses define this residual, so luna is the least entangled and the weakest. The
# weakness is answered by the manipulation check rather than by a stronger choice.
MODEL = "gpt-5.6-luna"
KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"   # openai
POP = Path("benchmarks/code/records/clarify/population.json")
DUMP = Path.home() / "Documents/Crossaudit/study-data/wt-ceiling-runs/residual/index.json"
OUT = Path("benchmarks/code/records/clarify/conditions.json")

CLARIFY_SYSTEM = """You are editing a programming problem's specification prose.

The specification below leaves a behavioural rule unstated, and a hidden test suite depends on
that rule. You are told which inputs the hidden suite exercises where the prose is silent.

Add one or two sentences that state the missing behavioural rule in general terms, as the
specification's own author would have written it.

You must NOT:
  - quote or paraphrase any specific input you were shown,
  - state what the function returns on any specific input,
  - mention tests, failures, bugs, or that anything is wrong,
  - change any sentence that is already there.

Reply with the complete edited specification and nothing else."""

PLACEBO_SYSTEM = """You are editing a programming problem's specification prose.

Add one or two sentences in the register of the surrounding text that resolve
NO ambiguity whatever: context about where the function sits, a restatement of something the
prose already says, or a note about style. After your edit a reader must be able to derive
exactly what they could derive before, and no more.

You must NOT:
  - state or imply any behavioural rule not already present,
  - mention tests, failures, bugs, or that anything is wrong,
  - change any sentence that is already there.

Your addition must be TARGET_WORDS words long, give or take a word or two. That length is
not a stylistic preference: the placebo exists to hold everything constant except the
information, so if it is shorter than the clarification the two conditions differ in bulk as
well as in content and the contrast is confounded.

Reply with the complete edited specification and nothing else."""


# Gate 5 forbids any of the prompt's own structure from appearing in what comes back. These
# are the lines the prompts are BUILT from, so the gate cannot drift out of step with them.
SCAFFOLD = ["SPECIFICATION:",
            "The hidden suite exercises these inputs, where the prose is silent:"]


def load_keys() -> None:
    for line in (Path.home() / ".crossaudit-keys.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class GenerationFailed(RuntimeError):
    """The provider never returned text. NOT a gate violation.

    `ask` used to return "" after three failed attempts. The empty string went on to the gates,
    which reported "an edited condition added no words" -- and that sentence would have entered
    the study's record as the reason the instance was dropped. The provider refusing three times
    and the generator writing something the gates caught are different events, and a record that
    calls one the other is false about why instances were lost.
    """


def ask(system: str, prompt: str) -> str:
    last = "no attempt ran"
    for attempt in range(3):
        try:
            reply = provider.complete(model=MODEL, key_env=KEY_ENV, system=system,
                                           prompt=prompt, max_tokens=2000, timeout=240.0)
            text = (getattr(reply, "text", "") or "").strip()
            if not text:
                last = "provider returned empty text"
            if text:
                text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
                # The model sometimes echoes the prompt's own `SPECIFICATION:` header back.
                # Gate 4 catches it, but catching it costs the instance a regeneration for a
                # transcription artefact rather than anything about the edit, so strip it here
                # and let the gate stay the independent check it is.
                return re.sub(rf"^{re.escape(SCAFFOLD[0])}\s*\n", "", text).strip()
        except Exception as exc:                                       # noqa: BLE001
            last = f"{type(exc).__name__}: {str(exc)[:200]}"
            print(f"    {type(exc).__name__} attempt {attempt + 1}/3", flush=True)
        time.sleep(4 * (attempt + 1))
    raise GenerationFailed(last)


def main() -> int:
    load_keys()
    pop = json.loads(POP.read_text(encoding="utf-8"))
    witnesses = {r["instance_id"]: r for r in json.loads(DUMP.read_text(encoding="utf-8"))}
    problems = {p.problem_id: p for p in load_problems()}

    # A smoke run writes to its OWN file. A limited run that wrote `conditions.json` would leave
    # a record whose `n_kept` is a fraction of the population and whose name says otherwise.
    limit = int(os.environ.get("P3_LIMIT", "0"))
    out_path = OUT.with_name("conditions-smoke.json") if limit else OUT
    ids = pop["instance_ids"][:limit] if limit else pop["instance_ids"]

    out, dropped, failed, regenerated = {}, [], [], []
    for n, iid in enumerate(ids, 1):
        problem = problems[iid.split(":", 1)[1]]
        wit = witnesses[iid]
        cases = (wit.get("witness") or {}).get("cases") or []
        inputs = "\n".join(f"  {c.get('input')}" for c in cases[:4])
        base = (f"{SCAFFOLD[0]}\n{problem.spec}\n\n"
                f"{SCAFFOLD[1]}\n{inputs}\n")

        # Amendment 5. The first run dropped every instance it reached, and four of the five
        # drops were the placebo-length gate, not a leak: the placebo was written blind, told
        # only to match "the surrounding text", while the gate measures it against the
        # CLARIFICATION's added words. The placebo was being asked to hit a number it had not
        # been told. The clarification is therefore written first and its added length passed
        # to the placebo as the target. The gate is unchanged and still checks the result
        # independently -- what changes is that the writer is now told what it must achieve.
        n_words = lambda t: len(t.split())                           # noqa: E731
        conds = {"original": {"spec": problem.spec, "candidate": "", "visible_tests": ""}}
        try:
            clarified = ask(CLARIFY_SYSTEM, base)
            added = max(n_words(clarified) - n_words(problem.spec), 1)
            placebo = ask(PLACEBO_SYSTEM.replace("TARGET_WORDS", str(added)),
                          f"{SCAFFOLD[0]}\n{problem.spec}\n")
        except GenerationFailed as exc:
            failed.append({"instance_id": iid, "why": str(exc)})
            print(f"  [{n}/{len(ids)}] {iid}: GENERATION FAILED -- {exc}", flush=True)
            continue
        conds["clarified"] = {"spec": clarified, "candidate": "", "visible_tests": ""}
        conds["placebo"] = {"spec": placebo, "candidate": "", "visible_tests": ""}

        # The code is identical by construction here -- nothing in this script touches it --
        # and gate 1 checks that rather than trusting it.
        for c in conds.values():
            c["candidate"] = problem.canonical_solution
            c["visible_tests"] = problem.visible_tests_text()

        # `hidden_program` is a method taking the solution and returning (text, bool), not a
        # string. The first run passed the bound method to the gate, which asked a function for
        # its `.splitlines()` and died on instance one -- so nothing was generated and nothing
        # was spent. A gate that receives the wrong type is not a gate that passed.
        hidden_text = problem.hidden_program(problem.canonical_solution)[0]
        problems_found = gates.run_all(iid, conds, wit.get("witness") or {}, hidden_text, SCAFFOLD)
        first_pass = list(problems_found)
        if problems_found:
            print(f"  [{n}/{len(ids)}] {iid}: regenerating, "
                  f"{problems_found[0].split(': ', 1)[1][:70]}", flush=True)
            # Regenerate the condition the failure NAMES. The first run regenerated the
            # clarification on every failure, including length failures -- which moves the
            # target the placebo missed instead of moving the placebo.
            try:
              if any("word counts" in f for f in problems_found):
                added = max(n_words(conds["clarified"]["spec"]) - n_words(problem.spec), 1)
                conds["placebo"]["spec"] = ask(
                    PLACEBO_SYSTEM.replace("TARGET_WORDS", str(added)),
                    f"{SCAFFOLD[0]}\n{problem.spec}\n")
              else:
                conds["clarified"]["spec"] = ask(CLARIFY_SYSTEM, base)
            except GenerationFailed as exc:
                failed.append({"instance_id": iid, "why": f"on regeneration: {exc}"})
                print(f"  [{n}/{len(ids)}] {iid}: GENERATION FAILED -- {exc}", flush=True)
                continue
            problems_found = gates.run_all(iid, conds, wit.get("witness") or {}, hidden_text, SCAFFOLD)
        if problems_found:
            # Both evaluations are recorded. The first run kept only the second, so when the
            # expected-value rule turned out to fire on bare `True`/`False`, there was no way
            # to tell retrospectively whether the eight instances it sent back for regeneration
            # had any other problem -- the evidence needed to judge the gate had been discarded
            # by the record that the gate's own drops were written into.
            dropped.append({"instance_id": iid, "reasons": problems_found,
                            "first_pass_reasons": first_pass})
            print(f"  [{n}/{len(ids)}] {iid}: DROPPED", flush=True)
            continue
        out[iid] = conds
        if first_pass:
            regenerated.append({"instance_id": iid, "first_pass_reasons": first_pass})
        print(f"  [{n}/{len(ids)}] {iid}: ok", flush=True)

    out_path.write_text(json.dumps({"model": MODEL, "n_of_population": len(ids),
                               "smoke": bool(limit), "n_kept": len(out), "n_dropped_by_gate": len(dropped),
                               "n_generation_failed": len(failed), "generation_failed": failed,
                               "n_kept_after_regeneration": len(regenerated),
                               "kept_after_regeneration": regenerated,
                               "dropped": dropped, "conditions": out},
                              indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {out_path}: {len(out)} kept, {len(dropped)} dropped by a gate, "
          f"{len(failed)} never generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
