"""Run both arms of the accuracy study over one ExpertLongBench task.

**arm A -- single model.** One generator call: the task's own prompt (transcribed from the
paper) as the system, the sample's input as the user turn. No audit, no revision.

**arm B -- CrossAudit.** The product's real build loop, entered through
``crossaudit.cli.build.run_loop``, with the *same generator vendor, model and reasoning
effort as arm A*. Generator, deterministic checks, cross-vendor auditor and bounded
revision all run for real, against a real git repo with a real ``crossaudit.yml``.

Each instance gets a fresh scratch project, because the loop writes files and commits
them. Every round's output is recovered from git, so a finding raised at round *r* can
later be checked against the output it was actually raised against.

Both arms are scored with :mod:`clear`, and every arm-B BLOCKER is adjudicated by
:mod:`adjudicate`. The run directory holds the outputs, the per-round findings, the cost
and the wall time; ``report.py`` turns it into the two numbers.

Run directories are gitignored: they contain model outputs, which quote the corpus.

Usage::

    export PYTHONPATH=<repo>/src
    python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 10 --seed 20260904
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adjudicate import (  # noqa: E402
    CONFIRMED,
    FALSE_POSITIVE,
    UNMAPPED,
    UNREADABLE,
    Adjudicator,
    Finding,
    parse_report_findings,
)
from clear import ClearScorer, NAPolicy, ScoreCost, parse_mapper_json  # noqa: E402
from provider import CrossAuditClient, missing_credentials, parse_spec, role_for  # noqa: E402
from tasks import Task, get_task  # noqa: E402

DATA_DIR = HERE / "data"
RUNS_DIR = HERE / "runs"
MANIFEST = HERE / "manifest.json"

#: Where the generator is told to put the deliverable, inside the audited scope.
#:
#: The increment is a DIRECTORY under the scope root, not a file sitting at it.
#: ``dcl.framework.scope_started`` treats a scope whose only contents are files at its
#: root as scaffolding rather than work ("an increment is a directory, and a file sitting
#: at the root is what `init` wrote"), and a scope it calls unstarted escalates at round
#: one with NOTHING_TO_AUDIT before the auditor's verdict is ever consulted. The pilot run
#: hit exactly that. This is the product's documented shape, so the harness adopts it.
SCOPE_DIR = "work"
INCREMENT_DIR = f"{SCOPE_DIR}/synthesis"
OUTPUT_PATH = f"{INCREMENT_DIR}/explanation.md"
RECIPE_PATH = f"{INCREMENT_DIR}/RECIPE.md"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


@contextlib.contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


# --------------------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------------------


def load_task_rows(task_id: str) -> list[dict]:
    path = DATA_DIR / f"{task_id}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"{path} is missing. Run:\n"
            f"  python {HERE / 'fetch.py'}\n"
            "(the corpus is CC BY-NC-SA 4.0 and is not committed)"
        )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_corpus(task_id: str) -> str:
    """Confirm the data on disk is the data the manifest pinned. Returns the digest."""
    result = subprocess.run(
        [sys.executable, str(HERE / "fetch.py"), "--verify", "--tasks", task_id],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "the corpus on disk does not match the pinned manifest, so no number measured "
            f"against it would be verifiable:\n{result.stdout}\n{result.stderr}"
        )
    return json.loads(MANIFEST.read_text())["tasks"][task_id]["sha256"]


def choose_samples(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Deterministic sample. Sorted by id first so the pick does not depend on file order."""
    ordered = sorted(rows, key=lambda row: row["id"])
    if n >= len(ordered):
        return ordered
    return sorted(random.Random(seed).sample(ordered, n), key=lambda row: row["id"])


# --------------------------------------------------------------------------------------
# the scratch project for arm B
# --------------------------------------------------------------------------------------

CONFIG_TEMPLATE = """\
version: 1
science_repo: {project}
constitution: AUDIT_RULES.md
max_rounds: {max_rounds}
auditor:
  vendor: {auditor_vendor}
  provider: {auditor_provider}
  model: {auditor_model}
  key_env: {auditor_key_env}
generator:
  vendor: {generator_vendor}
  provider: {generator_provider}
  model: {generator_model}
  key_env: {generator_key_env}
isolation:
  minimum:
    parametric: true
    contextual: true
    permissive: false
state:
  dir: .crossaudit
ledger:
  dir: cycles
scope:
  dirs: [{scope}]
checks: {checks}
authority:
  lone_model_blocker: {lone_model_blocker}
"""


#: The preamble of a CrossAudit constitution, shared by both the shipped general rules and
#: the rubric-derived ones, so that arm B and arm B-prime differ ONLY in their rule bodies.
#: Copied from ``scaffold/templates/GENERAL_AUDIT_RULES.md``; if that template's preamble
#: changes this becomes a silent divergence, which is why the study records both files'
#: sha256 in ``plan.json``.
CONSTITUTION_PREAMBLE = """\
# Constitution — {project}

Version this file in git. Every audit cites the commit that carried it. Rule
changes take effect only between cycles, so work is never judged against a
target that moved underneath it.

Each rule has a stable ID and a decidable criterion. **BLOCKER** gates the
increment when an objective requirement is not met. **ADVISORY** records
judgement or an improvement opportunity and never gates admission.

---
"""


def rubric_constitution(task: Task) -> str:
    """A constitution generated mechanically from the task's own evaluation rubric.

    One BLOCKER per rubric item, whose criterion is the item's description transcribed
    from the paper's Appendix B -- no rewriting, no emphasis, no hints about what the
    auditor "should" look for beyond what the rubric itself says. This is arm B-prime's
    only difference from arm B, and it exists to answer one question: is the auditor quiet
    because the generic rules never told it what this task is graded on?

    Nothing here is derived from any score. It is a pure function of ``tasks.py``.
    """
    parts = [CONSTITUTION_PREAMBLE.format(project=task.task_id)]
    for index, item in enumerate(task.items, start=1):
        label = f"{item.group} / {item.name}" if item.group else item.name
        parts.append(
            f"### CA-RUBRIC-{index:03d}\n"
            f"**BLOCKER.** *{label}.* {item.description} The deliverable must contain "
            f"this explicitly, and what it says must be consistent with the supplied "
            f"source material. An item the deliverable does not address, or addresses "
            f"in a way the source material contradicts, is a defect.\n"
        )
    parts.append(
        "### CA-CONTENT-001\n"
        "**BLOCKER.** The primary deliverable is complete, internally consistent, and\n"
        "contains no unresolved placeholder such as TODO, TBD, or sample text.\n"
    )
    return "\n".join(parts)


def constitution_text(task: Task, options: "Options") -> str:
    """The AUDIT_RULES.md the scratch project is bootstrapped with."""
    if options.audit_rules == "rubric":
        return rubric_constitution(task)
    from crossaudit.scaffold import read as read_template

    return read_template("GENERAL_AUDIT_RULES.md").replace("<PROJECT>", task.task_id)


def bootstrap_project(root: Path, task: Task, row: dict, options: "Options") -> Path:
    """A fresh git project shaped the way a real user's would be for this kind of work.

    The general constitution and the general check profile, because the deliverable is
    expert prose rather than an experiment with `results.json`. The task's input is
    committed *inside the audited scope* as ``RECIPE.md``, so the auditor can hold the
    explanation against its source material -- which is exactly what CA-CONTENT-002 asks
    of it, and the only way a content audit of this task can mean anything.
    """
    project = root / "project"
    (project / INCREMENT_DIR).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(project), check=True)
    git("config", "user.email", "bench@crossaudit.invalid", cwd=project)
    git("config", "user.name", "ExpertLongBench harness", cwd=project)

    (project / "AUDIT_RULES.md").write_text(
        constitution_text(task, options), encoding="utf-8"
    )
    generator_role = role_for(options.generator)
    auditor_role = role_for(options.auditor)
    (project / "crossaudit.yml").write_text(
        CONFIG_TEMPLATE.format(
            project=task.task_id,
            max_rounds=options.max_rounds,
            auditor_vendor=auditor_role.vendor,
            auditor_provider=auditor_role.provider,
            auditor_model=auditor_role.model,
            auditor_key_env=auditor_role.key_env,
            generator_vendor=generator_role.vendor,
            generator_provider=generator_role.provider,
            generator_model=generator_role.model,
            generator_key_env=generator_role.key_env,
            scope=SCOPE_DIR,
            checks=options.checks,
            lone_model_blocker=options.lone_model_blocker,
        ),
        encoding="utf-8",
    )
    (project / ".gitignore").write_text(".crossaudit/\n", encoding="utf-8")
    (project / RECIPE_PATH).write_text(
        f"# Source material\n\nThis is the material the explanation must be justified "
        f"against. Do not change this file.\n\n{row['input']}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(project), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "bootstrap"], cwd=str(project), check=True)
    return project


def arm_b_task(task: Task) -> str:
    """The instruction handed to the loop.

    It is the paper's own model prompt plus the two facts the loop needs: where the source
    material is, and where the deliverable goes. Nothing here is tuned for the audit -- if
    it ever is, the study restarts.
    """
    return (
        f"{task.model_prompt}\n\n"
        f"The synthesis recipe is in `{RECIPE_PATH}`. Write your explanation to "
        f"`{OUTPUT_PATH}` as the single deliverable. Do not modify `{RECIPE_PATH}`."
    )


# --------------------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------------------


@dataclass
class ArmResult:
    arm: str
    sample_id: str
    ok: bool
    output_text: str = ""
    error: str = ""
    wall_s: float = 0.0
    cost_usd: float = 0.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    rounds: int = 0
    exit_code: int | None = None
    #: arm B only: per-round output text, keyed by round number as a string.
    round_outputs: dict[str, str] = field(default_factory=dict)
    #: arm B only: findings per round.
    findings: list[dict] = field(default_factory=list)
    prompt_sha256: str = ""
    model: str = ""


@dataclass
class Options:
    task_id: str
    n: int
    seed: int
    generator: str
    auditor: str
    judge: str
    mapper: str
    adjudicator: str
    max_rounds: int
    checks: str
    lone_model_blocker: str
    na_policy: str
    arms: str
    out: str
    #: ``general`` (the shipped constitution) or ``rubric`` (generated from the task's own
    #: evaluation rubric). Arm B-prime is exactly ``rubric``, everything else held fixed.
    audit_rules: str = "general"
    #: If non-zero, keep only the first ``subset`` of the seeded sample. Lets a follow-up
    #: arm run on a strict subset of the main arm's instances, so the comparison is paired.
    subset: int = 0
    #: A name for this run's arm, carried into ``plan.json`` so runs can be joined.
    label: str = "B"
    #: Ask a model, once per sample, which rubric items are derivable from the committed
    #: source material alone. Answers Q1's "the task" hypothesis.
    probe_checkability: bool = False


# --------------------------------------------------------------------------------------
# arm A
# --------------------------------------------------------------------------------------


def run_arm_a(cfg, task: Task, row: dict, options: Options, run_id: str) -> ArmResult:
    """One generator call. No audit."""
    client = CrossAuditClient(cfg=cfg, phase="arm-a-generation", run_id=run_id)
    system, user = task.model_prompt, row["input"]
    started = time.monotonic()
    try:
        completion = client.complete(model=options.generator, system=system, user=user)
    except Exception as exc:  # noqa: BLE001 - recorded on the result, never swallowed
        return ArmResult(
            arm="A",
            sample_id=row["id"],
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            wall_s=time.monotonic() - started,
            prompt_sha256=sha256_text(system + "\n" + user),
            model=options.generator,
        )
    return ArmResult(
        arm="A",
        sample_id=row["id"],
        ok=True,
        output_text=completion.text,
        wall_s=time.monotonic() - started,
        cost_usd=completion.cost_usd,
        calls=1,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        rounds=1,
        prompt_sha256=sha256_text(system + "\n" + user),
        model=completion.model,
    )


# --------------------------------------------------------------------------------------
# arm B
# --------------------------------------------------------------------------------------


def read_round_outputs(project: Path) -> dict[str, str]:
    """Recover the deliverable as it stood at each generator commit, newest last.

    The loop commits once per round, so git *is* the per-round record. A finding raised at
    round r must be checked against the output of round r, not against the final one.
    """
    log = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", "--", OUTPUT_PATH],
        cwd=str(project),
        capture_output=True,
        text=True,
    ).stdout.split()
    outputs: dict[str, str] = {}
    for index, sha in enumerate(log, start=1):
        blob = subprocess.run(
            ["git", "show", f"{sha}:{OUTPUT_PATH}"], cwd=str(project), capture_output=True, text=True
        )
        if blob.returncode == 0:
            outputs[str(index)] = blob.stdout
    return outputs


def read_findings(project: Path, cfg) -> list[dict]:
    """Every finding the audit recorded, per round, from the cycle ledger.

    ``findings.json`` carries tier/severity/state; ``report.md`` carries the observation
    text the adjudicator needs. We join them by (rule, artifact) and keep both.
    """
    ledger = project / cfg.ledger_dir
    if not ledger.is_dir():
        return []
    out: list[dict] = []
    for cycle_dir in sorted(ledger.iterdir()):
        if not cycle_dir.is_dir():
            continue
        round_no = 0
        if "-r" in cycle_dir.name:
            tail = cycle_dir.name.rsplit("-r", 1)[1].split(".")[0]
            round_no = int(tail) if tail.isdigit() else 0

        observations: dict[tuple[str, str], str] = {}
        report_path = cycle_dir / "report.md"
        if report_path.exists():
            for finding in parse_report_findings(report_path.read_text(encoding="utf-8"), round_no):
                observations[(finding.rule, finding.artifact)] = finding.observation

        structured = cycle_dir / "findings.json"
        records = []
        if structured.exists():
            with contextlib.suppress(json.JSONDecodeError):
                records = json.loads(structured.read_text(encoding="utf-8")).get("findings", [])

        if records:
            for record in records:
                key = (record.get("rule", ""), record.get("artifact", ""))
                out.append(
                    {
                        "round": round_no,
                        "cycle_dir": cycle_dir.name,
                        "severity": record.get("severity", ""),
                        "rule": key[0],
                        "artifact": key[1],
                        "tier": record.get("tier", ""),
                        "state": record.get("state", ""),
                        "observation": observations.get(key, ""),
                    }
                )
        else:
            for key, observation in observations.items():
                out.append(
                    {
                        "round": round_no,
                        "cycle_dir": cycle_dir.name,
                        "severity": "",
                        "rule": key[0],
                        "artifact": key[1],
                        "tier": "",
                        "state": "",
                        "observation": observation,
                    }
                )

        verdict_path = cycle_dir / "receipt.json"
        if verdict_path.exists():
            with contextlib.suppress(json.JSONDecodeError, KeyError):
                verdict = json.loads(verdict_path.read_text(encoding="utf-8"))["audit"]["verdict"]
                for record in out:
                    if record["cycle_dir"] == cycle_dir.name:
                        record["verdict"] = verdict
    return out


def arm_b_cost(cfg, run_id: str) -> tuple[float, int, int, int]:
    """Read this run's spend straight out of the product's own usage ledger."""
    from crossaudit import usage

    events, _malformed = usage.read_events(cfg.root / cfg.state_dir / usage.LEDGER_NAME)
    mine = [event for event in events if event.get("run_id") == run_id]
    return (
        sum(float(event.get("api_value_usd") or 0.0) for event in mine),
        len(mine),
        sum(int(event.get("input", 0)) for event in mine),
        sum(int(event.get("output", 0)) for event in mine),
    )


def run_arm_b(scratch: Path, task: Task, row: dict, options: Options, run_id: str) -> ArmResult:
    """The real loop, in a fresh project."""
    from crossaudit.cli import build as build_mod
    from crossaudit.config import load

    result = ArmResult(arm="B", sample_id=row["id"], ok=False, model=options.generator)
    instruction = arm_b_task(task)
    result.prompt_sha256 = sha256_text(instruction + "\n" + row["input"])

    project = bootstrap_project(scratch, task, row, options)
    cfg = load(project / "crossaudit.yml")

    events: list[str] = []

    def on_event(event) -> None:
        events.append(getattr(event, "kind", "") or "")

    on_event.run_id = run_id
    on_event.heartbeat = lambda: None

    started = time.monotonic()
    try:
        with chdir(project):
            result.exit_code = build_mod.run_loop(cfg, instruction, on_event=on_event)
        result.ok = True
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        result.error = f"{type(exc).__name__}: {exc}"
    result.wall_s = time.monotonic() - started

    result.round_outputs = read_round_outputs(project)
    result.output_text = result.round_outputs.get(
        str(max((int(k) for k in result.round_outputs), default=0)), ""
    )
    result.rounds = len(result.round_outputs)
    result.findings = read_findings(project, cfg)
    result.cost_usd, result.calls, result.input_tokens, result.output_tokens = arm_b_cost(
        cfg, run_id
    )
    if not result.output_text and not result.error:
        result.error = f"the loop produced no {OUTPUT_PATH}"
        result.ok = False
    return result


# --------------------------------------------------------------------------------------
# the study
# --------------------------------------------------------------------------------------


def write_instance(out_dir: Path, sample_id: str, payload: dict, outputs: dict[str, str]) -> None:
    """Write one instance's record.

    Model outputs quote the corpus, so they live only here, under a gitignored directory.
    """
    safe = sample_id.replace("/", "__")
    instance_dir = out_dir / "instances" / safe
    instance_dir.mkdir(parents=True, exist_ok=True)
    (instance_dir / "record.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for name, text in outputs.items():
        (instance_dir / name).write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--task", default="T03MaterialSEG")
    parser.add_argument("--n", type=int, default=10, help="sample size")
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--generator", default="anthropic:claude-sonnet-4-6")
    parser.add_argument("--auditor", default="openai:gpt-5.6-terra")
    parser.add_argument(
        "--judge",
        default="",
        help="vendor:model for the CLEAR judge. Defaults to a vendor that is neither the "
        "generator's nor the auditor's, so no model grades its own work.",
    )
    parser.add_argument("--mapper", default="", help="defaults to the judge")
    parser.add_argument("--adjudicator", default="", help="defaults to the judge")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--checks", default="general", help="crossaudit.yml checks profile")
    parser.add_argument("--lone-model-blocker", default="block", choices=["block", "escalate"])
    parser.add_argument("--na-policy", default=NAPolicy.LITERAL.value,
                        choices=[policy.value for policy in NAPolicy])
    parser.add_argument("--arms", default="AB", help="which arms to run: A, B or AB")
    parser.add_argument("--out", default="", help="run directory (default: runs/<timestamp>)")
    parser.add_argument(
        "--audit-rules", default="general", choices=["general", "rubric"],
        help="arm B's constitution: the shipped general rules, or one generated from the "
             "task's own evaluation rubric (arm B-prime).",
    )
    parser.add_argument(
        "--subset", type=int, default=0,
        help="after seeding with --n, keep only the first SUBSET instances, so a "
             "follow-up arm runs on a strict subset of the main arm's samples.",
    )
    parser.add_argument("--label", default="", help="a name for this run's arm")
    parser.add_argument(
        "--probe-checkability", action="store_true",
        help="one extra model call per sample: which rubric items are derivable from the "
             "committed source material alone.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and the credentials it needs, call nothing")
    args = parser.parse_args(argv)

    load_credentials()

    task = get_task(args.task)
    corpus_sha = verify_corpus(args.task)
    rows = choose_samples(load_task_rows(args.task), args.n, args.seed)
    full_sample = [row["id"] for row in rows]
    if args.subset:
        rows = rows[: args.subset]

    generator_vendor, _ = parse_spec(args.generator)
    auditor_vendor, _ = parse_spec(args.auditor)
    judge = args.judge or _default_judge(generator_vendor, auditor_vendor)
    options = Options(
        task_id=args.task,
        n=len(rows),
        seed=args.seed,
        generator=args.generator,
        auditor=args.auditor,
        judge=judge,
        mapper=args.mapper or judge,
        adjudicator=args.adjudicator or judge,
        max_rounds=args.max_rounds,
        checks=args.checks,
        lone_model_blocker=args.lone_model_blocker,
        na_policy=args.na_policy,
        arms=args.arms.upper(),
        out=args.out,
        audit_rules=args.audit_rules,
        subset=args.subset,
        label=args.label or ("B-" + args.audit_rules if args.audit_rules != "general" else "B"),
        probe_checkability=args.probe_checkability,
    )

    if generator_vendor == auditor_vendor:
        raise SystemExit(
            f"generator and auditor are both {generator_vendor}. CrossAudit refuses a "
            "same-vendor pair (config.heterogeneity), and a same-vendor audit would not be "
            "the thing this study claims to measure."
        )

    wanted = [options.generator, options.mapper, options.judge, options.adjudicator]
    if "B" in options.arms:
        wanted.append(options.auditor)
    missing = missing_credentials(sorted(set(wanted)))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Absolute, always. ``run_arm_b`` chdirs into the scratch project so the loop sees a
    # real working directory, and a Config whose ``root`` was relative would then resolve
    # against the project rather than against the repo -- the loop would look for
    # AUDIT_RULES.md inside itself and fail with a FileNotFoundError recorded as an
    # instance failure. Study 1 never hit this because it used the default run directory,
    # which is already absolute.
    out_dir = (
        Path(options.out) if options.out else RUNS_DIR / f"{args.task}-{options.label}-{run_id}"
    ).resolve()

    plan = {
        "run_id": run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "task": args.task,
        "corpus_sha256": corpus_sha,
        "n": len(rows),
        "seed": args.seed,
        "sample_ids": [row["id"] for row in rows],
        "full_sample_ids": full_sample,
        "subset": args.subset,
        "arms": options.arms,
        "label": options.label,
        "models": {
            "generator": options.generator,
            "auditor": options.auditor,
            "mapper": options.mapper,
            "judge": options.judge,
            "adjudicator": options.adjudicator,
        },
        "settings": {
            "max_rounds": options.max_rounds,
            "checks": options.checks,
            "lone_model_blocker": options.lone_model_blocker,
            "na_policy": options.na_policy,
            "audit_rules": options.audit_rules,
            "probe_checkability": options.probe_checkability,
        },
        "constitution_sha256": sha256_text(constitution_text(task, options)),
        "prompts": {
            "task_model_prompt_sha256": sha256_text(task.model_prompt),
            "arm_b_instruction_sha256": sha256_text(arm_b_task(task)),
            "mapper_system_sha256": _prompt_sha("MAPPER_SYSTEM"),
            "judge_system_sha256": _prompt_sha("JUDGE_SYSTEM"),
            "adjudicator_system_sha256": _prompt_sha("ADJUDICATOR_SYSTEM", module="adjudicate"),
        },
        "judge_calls_per_output": 2 * len(task.items) + 1,
        "missing_credentials": missing,
    }

    if args.dry_run or missing:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        if missing:
            print(
                "\nNo live run: these credentials are absent, so nothing was called and no "
                "numbers were produced.\n  " + "\n  ".join(missing),
                file=sys.stderr,
            )
            return 2
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    print(f"run {run_id}: {args.task}, n={len(rows)}, seed={args.seed} -> {out_dir}")

    return _execute(task, rows, options, plan, out_dir, run_id)


def load_credentials() -> None:
    """Resolve keys the way the product does: exported env, then the keys file, then Keychain.

    Without this the harness would need a hand-sourced shell, and "no credentials" would be
    indistinguishable from "the key file was not read" -- which is exactly the confusion
    that produces a fabricated result.
    """
    with contextlib.suppress(Exception):
        from crossaudit.cli.wizard import load_keys_into_env

        load_keys_into_env()
    with contextlib.suppress(Exception):
        from crossaudit import app_keys

        app_keys.load_into_environment()

    # A role-fallback key (CROSSAUDIT_AUDITOR_KEY / CROSSAUDIT_GENERATOR_KEY) is the same
    # secret under a different name; mirror it onto the vendor's own variable so a role
    # built from a vendor:model spec finds it.
    with contextlib.suppress(Exception):
        from crossaudit.app_keys import PROVIDER_ENVS, ROLE_FALLBACKS

        for vendor, fallback in ROLE_FALLBACKS.items():
            native = PROVIDER_ENVS.get(vendor)
            if native and not os.environ.get(native, "").strip():
                value = os.environ.get(fallback, "").strip()
                if value:
                    os.environ[native] = value


def _default_judge(generator_vendor: str, auditor_vendor: str) -> str:
    """A vendor that produced neither the output nor the audit, where one is available.

    Falls back to the auditor's vendor -- still not the generator's -- rather than
    silently letting the generator grade itself.
    """
    from provider import default_model
    from crossaudit.providers import specs

    for vendor in ("google", "openai", "anthropic", "deepseek", "qwen", "xai", "mistral"):
        if vendor in {generator_vendor, auditor_vendor} or vendor not in specs.SPECS:
            continue
        if os.environ.get(specs.SPECS[vendor].key_env, "").strip():
            return f"{vendor}:{default_model(vendor)}"
    return f"{auditor_vendor}:{default_model(auditor_vendor)}"


def _prompt_sha(name: str, module: str = "clear") -> str:
    import importlib

    return sha256_text(getattr(importlib.import_module(module), name))


def _execute(task: Task, rows: list[dict], options: Options, plan: dict, out_dir: Path,
             run_id: str) -> int:
    from crossaudit.config import load

    # A host project for arm A and for the scoring calls: resilience and metering need a
    # Config, and this keeps the benchmark's own spend in one ledger.
    host = out_dir / "_host"
    # A stale host from an interrupted run would be reused with its old git state and its
    # old usage ledger, which would misattribute this run's cost. Start clean.
    shutil.rmtree(host, ignore_errors=True)
    host.mkdir(parents=True)
    host_project = bootstrap_project(host, task, rows[0], options)
    host_cfg = load(host_project / "crossaudit.yml")

    scorer_client = CrossAuditClient(cfg=host_cfg, phase="clear-scoring", run_id=run_id)
    scorer = ClearScorer(
        scorer_client,
        mapper_model=options.mapper,
        judge_model=options.judge,
        na_policy=NAPolicy(options.na_policy),
    )
    adjudicator = Adjudicator(
        CrossAuditClient(cfg=host_cfg, phase="adjudication", run_id=run_id),
        model=options.adjudicator,
    )

    records = []
    for index, row in enumerate(rows, start=1):
        sample_id = row["id"]
        print(f"[{index}/{len(rows)}] {sample_id}", flush=True)
        reference = {k: str(v) for k, v in row["human_reference_checklist"].items()}
        record: dict = {"sample_id": sample_id, "arms": {}}
        outputs: dict[str, str] = {}

        if "A" in options.arms:
            result = run_arm_a(host_cfg, task, row, options, run_id)
            record["arms"]["A"] = _score_arm(scorer, task, result, reference, outputs, "A")

        if "B" in options.arms:
            scratch = out_dir / "_scratch" / sample_id.replace("/", "__")
            shutil.rmtree(scratch, ignore_errors=True)
            scratch.mkdir(parents=True)
            result = run_arm_b(scratch, task, row, options, run_id)
            # Every round is scored, not just the last one and not just the rounds that
            # carried a blocker. That is what makes the pre-revision / post-revision
            # difference measurable on the same instance -- the study's primary number.
            scored_rounds = _score_rounds(scorer, task, result, reference, outputs)
            entry = _score_arm(scorer, task, result, reference, outputs, "B",
                               prescored=_final_scored(result, scored_rounds))
            entry["round_scores"] = {
                str(r): sc.score.to_json() for r, sc in sorted(scored_rounds.items())
            }
            entry["round_score_cost_usd"] = sum(
                sc.cost.cost_usd for sc in scored_rounds.values()
            )
            entry["round_score_calls"] = sum(sc.cost.calls for sc in scored_rounds.values())
            entry["score_cost_usd"] = entry["round_score_cost_usd"]
            entry["score_calls"] = entry["round_score_calls"]
            entry["revision"] = _revision_pair(scored_rounds)
            findings_mapped, recall = _instrument_audit(
                adjudicator, task, result, scored_rounds
            )
            entry["findings_mapped"] = findings_mapped
            entry["audit_recall"] = recall
            # Kept in the shape report.py already reads, so the D142 confirmation rate
            # continues to be computed the same way across both studies.
            entry["adjudications"] = [
                f for f in findings_mapped if f.get("severity") == "BLOCKER"
            ]
            record["arms"]["B"] = entry
            shutil.rmtree(scratch, ignore_errors=True)

        if options.probe_checkability:
            record["checkability"] = _probe_checkability(
                scorer_client, task, row, reference, options
            )

        write_instance(out_dir, sample_id, record, outputs)
        records.append(record)
        _write_index(out_dir, plan, records)

    print(f"\ndone. {len(records)} instances -> {out_dir}")
    print(f"next: python {HERE / 'report.py'} {out_dir}")
    return 0


def _score_arm(scorer, task, result: ArmResult, reference, outputs: dict, arm: str,
               prescored=None) -> dict:
    entry = {k: v for k, v in asdict(result).items() if k not in {"output_text", "round_outputs"}}
    outputs[f"arm{arm}.output.md"] = result.output_text
    for round_no, text in result.round_outputs.items():
        outputs[f"arm{arm}.round{round_no}.md"] = text

    if not result.output_text.strip():
        entry["score"] = None
        entry["score_cost_usd"] = 0.0
        return entry

    scored = prescored or scorer.score(task, result.sample_id, result.output_text, reference)
    entry["score"] = scored.score.to_json()
    entry["score_cost_usd"] = 0.0 if prescored is not None else scored.cost.cost_usd
    entry["score_calls"] = 0 if prescored is not None else scored.cost.calls
    entry["_judgements"] = [
        {"key": j.key, "precision_hit": j.precision_hit, "recall_hit": j.recall_hit}
        for j in scored.score.judgements
    ]
    return entry


def _score_rounds(scorer, task, result: ArmResult, reference, outputs: dict) -> dict:
    """Score the deliverable as it stood at the end of EVERY round.

    Study 1 scored only the final output plus, opportunistically, any round that carried a
    blocker. That made "did the revision help?" answerable across arms (n = instances,
    confounded by generation variance) but not within an instance. Scoring every round
    makes it answerable within the instance: the same sample, the same generator, the same
    scorer, with and without the audit's correction. n is then the number of revisions.
    """
    scored_rounds: dict[int, object] = {}
    for key in sorted(result.round_outputs, key=int):
        text = result.round_outputs[key]
        if not text.strip():
            continue
        scored = scorer.score(task, f"{result.sample_id}#r{key}", text, reference)
        scored_rounds[int(key)] = scored
        outputs[f"armB.round{key}.score.json"] = json.dumps(
            scored.score.to_json(), indent=2
        )
    return scored_rounds


def _final_scored(result: ArmResult, scored_rounds: dict):
    """The ScoredOutput for the round whose text IS the final output, if there is one.

    ``run_arm_b`` sets ``output_text`` to the highest-numbered round's text, so this is a
    lookup, not a re-score -- and it is guarded by a text comparison so that a change to
    that invariant costs a duplicate scoring pass rather than silently mislabelling one.
    """
    if not scored_rounds:
        return None
    last = max(scored_rounds)
    if result.round_outputs.get(str(last), "") != result.output_text:
        return None
    return scored_rounds[last]


def _revision_pair(scored_rounds: dict) -> dict | None:
    """The paired pre-revision / post-revision measurement. The study's primary number.

    ``None`` when the loop passed at round one: there was no revision, so there is nothing
    to measure. Counting those as zeros would dilute the very quantity being measured,
    which is what study 1's headline did.
    """
    if len(scored_rounds) < 2:
        return None
    first, last = min(scored_rounds), max(scored_rounds)
    pre = scored_rounds[first].score
    post = scored_rounds[last].score
    return {
        "pre_round": first,
        "post_round": last,
        "n_revisions": last - first,
        "pre_f1": pre.f1,
        "post_f1": post.f1,
        "delta_f1": post.f1 - pre.f1,
        "pre_accuracy": pre.accuracy,
        "post_accuracy": post.accuracy,
        "delta_accuracy": post.accuracy - pre.accuracy,
        "pre_precision": pre.precision,
        "post_precision": post.precision,
        "pre_recall": pre.recall,
        "post_recall": post.recall,
        "items_fixed": sorted(
            j.key
            for j in post.judgements
            if j.accuracy_hit
            and not next(k for k in pre.judgements if k.key == j.key).accuracy_hit
        ),
        "items_broken": sorted(
            j.key
            for j in post.judgements
            if not j.accuracy_hit
            and next(k for k in pre.judgements if k.key == j.key).accuracy_hit
        ),
    }


def _instrument_audit(adjudicator, task, result: ArmResult, scored_rounds: dict):
    """Map every finding onto rubric items and measure the auditor against ground truth.

    Two products, and the second is the point of the study:

    * **per finding** -- which rubric items it is about, and whether CLEAR had in fact
      scored those items wrong in the very output the finding was raised against. That is
      study 1's confirmation rate, now computed over findings of *every* severity rather
      than BLOCKERs only.
    * **per round** -- of the rubric items CLEAR marked wrong in that output, how many did
      *any* finding name? That is the auditor's **recall against ground truth**. A round
      with six wrong items and no findings scores 0/6, and that is the number study 1
      could not produce.

    Mapping is a model call and is fallible; the lookup of CLEAR's verdict is not.
    """
    by_round = {
        r: {j.key: j for j in sc.score.judgements} for r, sc in scored_rounds.items()
    }

    mapped: list[dict] = []
    for finding in result.findings:
        round_no = int(finding.get("round") or 0)
        record = {
            "round": round_no,
            "severity": finding.get("severity", ""),
            "rule": finding.get("rule", ""),
            "artifact": finding.get("artifact", ""),
            "tier": finding.get("tier", ""),
            "state": finding.get("state", ""),
            "verdict": UNREADABLE,
            "cited_items": [],
            "item_was_wrong": {},
            "note": "",
        }
        try:
            indices = adjudicator.map_finding(
                task,
                Finding(
                    severity=record["severity"],
                    rule=record["rule"],
                    artifact=record["artifact"],
                    observation=finding.get("observation", ""),
                    tier=record["tier"],
                    round_no=round_no,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - recorded, never silently scored
            record["note"] = f"adjudicator call failed: {type(exc).__name__}: {exc}"
            mapped.append(record)
            continue

        cited = [task.items[i].key for i in indices]
        record["cited_items"] = cited
        judgements = by_round.get(round_no, {})
        if not cited:
            record["verdict"] = UNMAPPED
            record["note"] = "the objection is about no rubric item"
        elif not judgements:
            record["note"] = f"no scored output for round {round_no}"
        else:
            was_wrong = {k: not judgements[k].accuracy_hit for k in cited if k in judgements}
            record["item_was_wrong"] = was_wrong
            if not was_wrong:
                record["note"] = "cited items absent from the round's judgements"
            else:
                record["verdict"] = CONFIRMED if any(was_wrong.values()) else FALSE_POSITIVE
        mapped.append(record)

    recall: list[dict] = []
    for round_no, judgements in sorted(by_round.items()):
        wrong = {k for k, j in judgements.items() if not j.accuracy_hit}
        in_round = [m for m in mapped if m["round"] == round_no]
        named: set[str] = set()
        for m in in_round:
            named.update(m["cited_items"])
        hit = wrong & named
        recall.append(
            {
                "round": round_no,
                "n_findings": len(in_round),
                "n_blockers": sum(1 for m in in_round if m["severity"] == "BLOCKER"),
                "n_advisories": sum(1 for m in in_round if m["severity"] == "ADVISORY"),
                "rules_cited": sorted({m["rule"] for m in in_round if m["rule"]}),
                "n_items": len(judgements),
                "n_items_wrong": len(wrong),
                "n_items_named": len(named),
                "n_wrong_and_named": len(hit),
                "n_named_but_correct": len(named - wrong),
                "recall": (len(hit) / len(wrong)) if wrong else None,
            }
        )
    return mapped, recall


#: One call per sample. Answers Q1's third candidate cause -- "the task" -- with a
#: measurement rather than an argument: the auditor sees only the committed bytes (the
#: recipe and the deliverable), while the reference checklist was annotated by a human
#: from the full published paper. If most reference content is not derivable from the
#: recipe, then no auditor reading the repo could name most of what CLEAR marks wrong.
CHECKABILITY_SYSTEM = (
    "You are a {domain} expert assessing what a reviewer could possibly verify.\n\n"
    "You will be given a SOURCE RECIPE and, for each item of an evaluation rubric, the "
    "REFERENCE ANSWER that a human expert wrote after reading the full published paper "
    "that the recipe came from.\n\n"
    "For each item, decide whether the reference answer's substance could be derived by a "
    "competent expert from the SOURCE RECIPE alone.\n\n"
    "- Answer YES if the recipe states, or an expert could soundly infer from the recipe "
    "and general domain knowledge, what the reference answer says.\n"
    "- Answer NO if the reference answer depends on information that appears nowhere in "
    "the recipe -- specific characterisation results, the authors' stated motivations, "
    "measured values, or comparisons to other work.\n\n"
    "Output a single JSON object with keys item_1 .. item_{n} and values \"YES\" or "
    "\"NO\". Output the JSON object and nothing else."
)

CHECKABILITY_USER = (
    "Rubric items and their reference answers:\n{blocks}\n\n"
    "SOURCE RECIPE:\n<recipe>\n{recipe}\n</recipe>\n\n"
    "Return the JSON object with keys item_1 .. item_{n}."
)


def _probe_checkability(client, task: Task, row: dict, reference: dict, options: Options) -> dict:
    """Which rubric items are answerable from the bytes the auditor can see."""
    blocks = []
    for index, item in enumerate(task.items, start=1):
        label = f"{item.group} / {item.name}" if item.group else item.name
        blocks.append(
            f"item_{index}. {label}\n"
            f"  definition: {item.description}\n"
            f"  reference answer: {reference.get(item.key, 'N/A')}"
        )
    try:
        completion = client.complete(
            model=options.judge,
            system=CHECKABILITY_SYSTEM.format(domain=task.domain, n=len(task.items)),
            user=CHECKABILITY_USER.format(
                blocks="\n\n".join(blocks), recipe=row["input"], n=len(task.items)
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}

    try:
        raw = parse_mapper_json(completion.text, task.items)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"unparseable: {type(exc).__name__}: {exc}",
                "cost_usd": completion.cost_usd}
    verdicts = {
        key: ("yes" if value.strip().upper().startswith("Y") else
              "no" if value.strip().upper().startswith("N") else "unclear")
        for key, value in raw.items()
    }
    return {
        "per_item": verdicts,
        "n_yes": sum(1 for v in verdicts.values() if v == "yes"),
        "n_items": len(task.items),
        "cost_usd": completion.cost_usd,
        "model": completion.model,
    }


def _write_index(out_dir: Path, plan: dict, records: list[dict]) -> None:
    """Rewrite the index after every instance, so a run killed halfway is still readable."""
    (out_dir / "results.json").write_text(
        json.dumps({"plan": plan, "instances": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
