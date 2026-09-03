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

from adjudicate import Adjudicator, Finding, parse_report_findings  # noqa: E402
from clear import ClearScorer, NAPolicy, ScoreCost  # noqa: E402
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


def bootstrap_project(root: Path, task: Task, row: dict, options: "Options") -> Path:
    """A fresh git project shaped the way a real user's would be for this kind of work.

    The general constitution and the general check profile, because the deliverable is
    expert prose rather than an experiment with `results.json`. The task's input is
    committed *inside the audited scope* as ``RECIPE.md``, so the auditor can hold the
    explanation against its source material -- which is exactly what CA-CONTENT-002 asks
    of it, and the only way a content audit of this task can mean anything.
    """
    from crossaudit.scaffold import read as read_template

    project = root / "project"
    (project / INCREMENT_DIR).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(project), check=True)
    git("config", "user.email", "bench@crossaudit.invalid", cwd=project)
    git("config", "user.name", "ExpertLongBench harness", cwd=project)

    (project / "AUDIT_RULES.md").write_text(
        read_template("GENERAL_AUDIT_RULES.md").replace("<PROJECT>", task.task_id),
        encoding="utf-8",
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
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and the credentials it needs, call nothing")
    args = parser.parse_args(argv)

    load_credentials()

    task = get_task(args.task)
    corpus_sha = verify_corpus(args.task)
    rows = choose_samples(load_task_rows(args.task), args.n, args.seed)

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
    out_dir = Path(options.out) if options.out else RUNS_DIR / f"{args.task}-{run_id}"

    plan = {
        "run_id": run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "task": args.task,
        "corpus_sha256": corpus_sha,
        "n": len(rows),
        "seed": args.seed,
        "sample_ids": [row["id"] for row in rows],
        "arms": options.arms,
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
        },
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
            entry = _score_arm(scorer, task, result, reference, outputs, "B")
            entry["adjudications"] = _adjudicate_round_findings(
                adjudicator, scorer, task, result, reference, outputs
            )
            record["arms"]["B"] = entry
            shutil.rmtree(scratch, ignore_errors=True)

        write_instance(out_dir, sample_id, record, outputs)
        records.append(record)
        _write_index(out_dir, plan, records)

    print(f"\ndone. {len(records)} instances -> {out_dir}")
    print(f"next: python {HERE / 'report.py'} {out_dir}")
    return 0


def _score_arm(scorer, task, result: ArmResult, reference, outputs: dict, arm: str) -> dict:
    entry = {k: v for k, v in asdict(result).items() if k not in {"output_text", "round_outputs"}}
    outputs[f"arm{arm}.output.md"] = result.output_text
    for round_no, text in result.round_outputs.items():
        outputs[f"arm{arm}.round{round_no}.md"] = text

    if not result.output_text.strip():
        entry["score"] = None
        entry["score_cost_usd"] = 0.0
        return entry

    scored = scorer.score(task, result.sample_id, result.output_text, reference)
    entry["score"] = scored.score.to_json()
    entry["score_cost_usd"] = scored.cost.cost_usd
    entry["score_calls"] = scored.cost.calls
    entry["_judgements"] = [
        {"key": j.key, "precision_hit": j.precision_hit, "recall_hit": j.recall_hit}
        for j in scored.score.judgements
    ]
    return entry


def _adjudicate_round_findings(adjudicator, scorer, task, result: ArmResult, reference,
                               outputs: dict) -> list[dict]:
    """Adjudicate every BLOCKER against the output of the round it was raised on.

    Scoring a mid-round output costs a full CLEAR pass, so it is done once per round that
    actually carries a blocker, and cached.
    """
    blockers = [f for f in result.findings if f.get("severity") == "BLOCKER"]
    if not blockers:
        return []

    per_round_judgements: dict[int, list] = {}
    adjudications = []
    for finding in blockers:
        round_no = int(finding.get("round") or 0)
        if round_no not in per_round_judgements:
            text = result.round_outputs.get(str(round_no), "")
            if not text.strip():
                per_round_judgements[round_no] = []
            else:
                scored = scorer.score(task, f"{result.sample_id}#r{round_no}", text, reference)
                per_round_judgements[round_no] = list(scored.score.judgements)
                outputs[f"armB.round{round_no}.score.json"] = json.dumps(
                    scored.score.to_json(), indent=2
                )
        judgements = per_round_judgements[round_no]
        if not judgements:
            adjudications.append(
                {"rule": finding["rule"], "round": round_no, "verdict": "unreadable",
                 "note": "no scored output for this round"}
            )
            continue

        decision = adjudicator.adjudicate(
            task,
            Finding(
                severity=finding["severity"],
                rule=finding["rule"],
                artifact=finding["artifact"],
                observation=finding["observation"],
                tier=finding.get("tier", ""),
                round_no=round_no,
            ),
            judgements,
        )
        adjudications.append(
            {
                "rule": decision.finding.rule,
                "artifact": decision.finding.artifact,
                "tier": decision.finding.tier,
                "round": round_no,
                "verdict": decision.verdict,
                "cited_items": list(decision.cited_items),
                "item_was_wrong": decision.item_was_wrong,
                "note": decision.note,
            }
        )
    return adjudications


def _write_index(out_dir: Path, plan: dict, records: list[dict]) -> None:
    """Rewrite the index after every instance, so a run killed halfway is still readable."""
    (out_dir / "results.json").write_text(
        json.dumps({"plan": plan, "instances": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
