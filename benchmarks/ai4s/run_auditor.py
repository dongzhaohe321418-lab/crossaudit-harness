"""The model-layer runner for the AI4S corpus — prepared, and dry-run by default.

Dry run (default; no network, no key, no cost):

    PYTHONPATH=../../src python run_auditor.py --corpus records/corpus \
        --out records/auditor-dryrun [--profile science]

For every manifest row it assembles exactly what the shipped auditor would read,
using the project's own prompt assembly: the instance's DCL result under
``--profile`` (``crossaudit.dcl.run_checks(...).as_dict()``), then
``crossaudit.auditor.prompt.build(constitution, constitution_commit, dcl,
increment, task)`` — the call ``auditor/run.py::run_audit`` makes — with
``AUDIT_RULES.md`` as the constitution, ``TASK.md`` as the task and every other
file as the increment. It records per instance the prompt's byte count, sha256,
an estimated token count (UTF-8 bytes of system + prompt, divided by 4) and
whether the prompt bound was exceeded, and writes a cost table for the models in
``--price-models`` priced from ``crossaudit.providers.specs.capability_card``
(the table ``usage.py`` bills from), or "unpriced" where the card has no price.
Output tokens are an assumption (``--est-output-tokens``, default 1500), and the
table says so.

Live run (refuses unless every gate is met; NOT run in the session that wrote it):

    CROSSAUDIT_AUDITOR_KEY=... PYTHONPATH=../../src python run_auditor.py --live \
        --corpus records/corpus --out records/auditor-live \
        --provider anthropic --vendor anthropic --model claude-sonnet-5 \
        --max-usd 25 --i-accept-cost

``--live`` refuses unless ``CROSSAUDIT_AUDITOR_KEY`` is set, ``--max-usd`` is a
positive number and ``--i-accept-cost`` is passed. It then drives the provider
layer the way ``auditor/run.py`` does: ``providers.resilience.complete(cfg,
"auditor", role, system=prompt.SYSTEM, prompt=...)``, ``usage.record_completion``
into ``<out>/.crossaudit/usage.jsonl`` (cost comes from that ledger event, not
reconstructed), ``auditor.validate.parse_reply`` / ``validate_reply`` against
``known_rules(constitution)``, and the same single bounded repair turn on an
unreadable reply (``prompt.repair_note``). Every response is cached by prompt
sha256 under ``<out>/cache/`` (the response text, its digests and its usage —
no prompt text), so a re-run never pays twice. Rows in ``auditor_rows.jsonl``
carry verdict, findings (rule, severity, artifact and a digest of the
observation, never the observation text), tokens and cost. The run stops before
any call whose estimated cost would take the total past ``--max-usd``.

Honest boundary: the dry run measures prompt size, not model behaviour; its cost
is an estimate from a price snapshot and an assumed reply length. The live path
reuses the product's functions but not ``run_audit`` itself (which needs a git
project, a ledger and a receipt), so it does not exercise the evidence-authority
layer or receipts; it records the model's own verdict next to the DCL verdict
and leaves verdict synthesis to the scorer. Its numbers, when produced, belong in
a separate RESULTS section with their own n (DESIGN §6).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_checks import (import_packs, instance_dir, read_instance,  # noqa: E402
                        read_manifest, sha256_bytes)

KEY_ENV = "CROSSAUDIT_AUDITOR_KEY"
CONSTITUTION_FILE = "AUDIT_RULES.md"
TASK_FILE = "TASK.md"
DEFAULT_PRICE_MODELS = "openai:gpt-5.6-terra,anthropic:claude-sonnet-5"
DEFAULT_EST_OUTPUT_TOKENS = 1500


def assemble(files: dict[str, bytes], checks: list[str]) -> dict:
    """The auditor's prompt for one instance, built by the product's own functions."""
    from crossaudit.auditor import prompt as prompt_mod
    from crossaudit.dcl import run_checks

    dcl = run_checks(files, checks).as_dict()
    constitution_bytes = files.get(CONSTITUTION_FILE, b"")
    constitution = constitution_bytes.decode("utf-8", errors="replace")
    task = files.get(TASK_FILE, b"").decode("utf-8", errors="replace")
    increment = {p: b for p, b in files.items() if p not in (CONSTITUTION_FILE, TASK_FILE)}
    commit = "sha256:" + sha256_bytes(constitution_bytes)[:16]
    prompt, bounded, prompt_sha = prompt_mod.build(constitution, commit, dcl, increment, task)
    system = prompt_mod.SYSTEM
    nbytes = len(prompt.encode("utf-8"))
    return {"dcl": dcl, "constitution": constitution, "prompt": prompt, "system": system,
            "bounded": bounded, "prompt_sha256": prompt_sha, "prompt_bytes": nbytes,
            "system_bytes": len(system.encode("utf-8")),
            "est_input_tokens": math.ceil((nbytes + len(system.encode("utf-8"))) / 4)}


def price_table(models: list[tuple[str, str]], total_in: int, n: int,
                est_out: int) -> list[dict]:
    from crossaudit.providers.specs import PRICE_SNAPSHOT, capability_card

    out = []
    for vendor, model in models:
        rates = capability_card(vendor, model).price
        row = {"vendor": vendor, "model": model, "price_snapshot": PRICE_SNAPSHOT,
               "est_input_tokens": total_in, "est_output_tokens": n * est_out,
               "output_tokens_assumed_per_instance": est_out}
        if rates is None:
            row.update({"priced": False, "usd": "unpriced"})
        else:
            usd_in = total_in * rates.input / 1e6
            usd_out = n * est_out * rates.output / 1e6
            row.update({"priced": True, "usd_per_mtok_input": rates.input,
                        "usd_per_mtok_output": rates.output, "usd_input": round(usd_in, 4),
                        "usd_output": round(usd_out, 4), "usd": round(usd_in + usd_out, 4)})
        out.append(row)
    return out


def _parse_models(text: str) -> list[tuple[str, str]]:
    pairs = []
    for item in text.split(","):
        vendor, _, model = item.strip().partition(":")
        if vendor and model:
            pairs.append((vendor, model))
    return pairs


def _resolve_checks(profile: str) -> list[str]:
    from crossaudit.dcl import profiles
    import_packs()
    return profiles.resolve(profile)


def dry_run(corpus: Path, out: Path, profile: str, price_models: str,
            est_out: int) -> dict:
    checks = _resolve_checks(profile)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for mrow in read_manifest(corpus):
        a = assemble(read_instance(instance_dir(corpus, mrow)), checks)
        rows.append({"instance_id": mrow["instance_id"], "profile": profile,
                     "prompt_sha256": a["prompt_sha256"], "prompt_bytes": a["prompt_bytes"],
                     "system_bytes": a["system_bytes"],
                     "est_input_tokens": a["est_input_tokens"], "bounded": a["bounded"],
                     "dcl_verdict": a["dcl"]["verdict"]})
    total_in = sum(r["est_input_tokens"] for r in rows)
    summary = {
        "mode": "dry-run", "profile": profile, "corpus": str(corpus.resolve()),
        "corpus_manifest_sha256": sha256_bytes((corpus / "manifest.jsonl").read_bytes()),
        "instances": len(rows),
        "total_prompt_bytes": sum(r["prompt_bytes"] for r in rows),
        "system_bytes": rows[0]["system_bytes"] if rows else 0,
        "est_input_tokens": total_in,
        "token_estimate": "ceil((prompt bytes + system bytes) / 4); not provider-counted",
        "bounded_instances": sum(1 for r in rows if r["bounded"]),
        "cost": price_table(_parse_models(price_models), total_in, len(rows), est_out),
    }
    (out / "auditor_dryrun_rows.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    (out / "auditor_dryrun.json").write_text(json.dumps(summary, indent=1, sort_keys=True)
                                             + "\n", encoding="utf-8")
    return summary


# ------------------------------------------------------------------ live

def live_gate(args) -> str | None:
    """Why the live run must not start, or None when every gate is met."""
    if not os.environ.get(KEY_ENV, "").strip():
        return f"--live refuses: ${KEY_ENV} is not set"
    if args.max_usd is None or not args.max_usd > 0:
        return "--live refuses: --max-usd <positive number> is required"
    if not args.i_accept_cost:
        return "--live refuses: pass --i-accept-cost to acknowledge that this spends money"
    if not args.provider or not args.model:
        return "--live refuses: --provider and --model are required"
    return None


def _live_config(out: Path, args, checks: list[str]):
    from crossaudit.config import Config, Role

    role = Role(provider=args.provider, model=args.model,
                vendor=args.vendor or args.provider, key_env=KEY_ENV,
                base_url=args.base_url, reasoning_effort=args.reasoning_effort)
    return Config(path=out / "crossaudit.yml", science_repo=".", audit_repo=None,
                  constitution=CONSTITUTION_FILE, max_rounds=1, auditor=role,
                  generator_vendor=None, generator_provider=None, generator_model=None,
                  generator_key_env=None, generator_base_url=None,
                  generator_reasoning_effort=None, isolation_minimum={},
                  state_dir=".crossaudit", ledger_dir=".crossaudit/ledger",
                  scope_dirs=None, checks=checks)


def _ask(cfg, system: str, text: str, cache_dir: Path) -> dict:
    """One auditor turn, served from the cache when this exact prompt was asked before."""
    from crossaudit.providers import resilience as provider_resilience
    from crossaudit.usage import record_completion

    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.is_file():
        return {**json.loads(path.read_text(encoding="utf-8")), "cached": True}
    started = time.monotonic()
    answer = provider_resilience.complete(cfg, "auditor", cfg.auditor, system=system,
                                          prompt=text)
    route = provider_resilience.route_from_reply(answer, cfg.auditor)
    event = record_completion(
        root=cfg.root, state_dir=cfg.state_dir, role="auditor", phase="audit",
        vendor=route["vendor"], provider=route["provider"], model=route["model"],
        reply=answer, system=system, prompt=text, base_url=route.get("base_url"),
        context={"run_id": "ai4s-auditor",
                 "duration_ms": int((time.monotonic() - started) * 1000)}) or {}
    entry = {"prompt_sha256": key, "request_sha256": answer.request_sha256,
             "response_sha256": answer.response_sha256, "response_text": answer.text,
             "provider": route["provider"], "vendor": route["vendor"],
             "model": route["model"],
             "usage": {k: event.get(k) for k in ("input", "output", "cache_write",
                                                  "cache_read", "total", "method")},
             "cost_usd": event.get("api_value_usd"),
             "billing_kind": event.get("billing_kind")}
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {**entry, "cached": False}


def _estimate_call_usd(rates, est_in: int, est_out: int) -> float:
    return (est_in * rates.input + est_out * rates.output) / 1e6 if rates else 0.0


def live_run(corpus: Path, out: Path, args) -> dict:
    from crossaudit.auditor import prompt as prompt_mod
    from crossaudit.auditor.validate import (NO_JSON_REASON, known_rules, parse_reply,
                                             validate_reply)
    from crossaudit.errors import ProviderDenial
    from crossaudit.providers.registry import NON_EVIDENTIAL
    from crossaudit.providers.specs import capability_card

    checks = _resolve_checks(args.profile)
    out.mkdir(parents=True, exist_ok=True)
    cfg = _live_config(out, args, checks)
    rates = capability_card(cfg.auditor.vendor, cfg.auditor.model).price
    if rates is None and cfg.auditor.provider not in NON_EVIDENTIAL:
        raise SystemExit(f"--live refuses: {cfg.auditor.vendor}:{cfg.auditor.model} has no "
                         "price in the capability card, so --max-usd cannot be enforced")
    cache_dir = out / "cache"
    started = datetime.now(timezone.utc)
    spent, rows, stopped = 0.0, [], None
    for mrow in read_manifest(corpus):
        a = assemble(read_instance(instance_dir(corpus, mrow)), checks)
        cached_path = cache_dir / f"{a['prompt_sha256']}.json"
        estimate = _estimate_call_usd(rates, a["est_input_tokens"], args.est_output_tokens)
        if not cached_path.is_file() and spent + estimate > args.max_usd:
            stopped = (f"stopped before {mrow['instance_id']}: estimated "
                       f"{spent + estimate:.4f} USD would exceed --max-usd {args.max_usd}")
            break
        turns, error = [], None
        try:
            turn = _ask(cfg, a["system"], a["prompt"], cache_dir)
            turns.append(turn)
            parsed, invalid = parse_reply(turn["response_text"])
            if invalid is not None:
                shape = "no_json" if invalid == NO_JSON_REASON else "malformed_json"
                try:
                    turn = _ask(cfg, a["system"],
                                a["prompt"] + prompt_mod.repair_note(shape), cache_dir)
                except ProviderDenial:
                    # As in run.py: a repair that cannot be placed leaves the
                    # original rejection standing.
                    turn = None
                if turn is not None:
                    turns.append(turn)
                    parsed, invalid = parse_reply(turn["response_text"])
            if invalid is None:
                invalid = validate_reply(parsed, known_rules(a["constitution"]))
        except ProviderDenial as exc:
            parsed, invalid, error = None, None, exc.reason
        cost = sum(t.get("cost_usd") or 0.0 for t in turns if not t["cached"])
        spent += cost
        reply = parsed if (invalid is None and error is None) else None
        expected = set(((mrow.get("expected") or {}).get("rules")) or [])
        findings = [{"rule": f.get("rule"), "severity": f.get("severity"),
                     "artifact": f.get("artifact"),
                     "observation_sha256": hashlib.sha256(
                         str(f.get("observation", "")).encode("utf-8")).hexdigest()}
                    for f in (reply or {}).get("findings", []) if isinstance(f, dict)]
        rows.append({
            "instance_id": mrow["instance_id"], "pair_id": mrow.get("pair_id"),
            "clean": bool(mrow.get("clean")), "defect_class": mrow.get("defect_class"),
            "variant": mrow.get("variant"), "profile": args.profile,
            "provider": cfg.auditor.provider, "model": cfg.auditor.model,
            "non_evidential": cfg.auditor.provider in NON_EVIDENTIAL,
            "prompt_sha256": a["prompt_sha256"],
            "response_sha256": turns[-1]["response_sha256"] if turns else None,
            "repair_turns": max(0, len(turns) - 1),
            "dcl_verdict": a["dcl"]["verdict"],
            "dcl_hard_failures": a["dcl"]["total_hard_failures"],
            "model_verdict": reply.get("verdict") if reply else None,
            "invalid_reason": invalid, "provider_error": error, "bounded": a["bounded"],
            "findings": findings,
            "expected_rule_cited": (any(f["rule"] in expected for f in findings)
                                    if not mrow.get("clean") else None),
            "tokens": [t.get("usage") for t in turns],
            "cost_usd": round(cost, 10), "cached": all(t["cached"] for t in turns) if turns else False,
        })
    (out / "auditor_rows.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    summary = {"mode": "live", "profile": args.profile, "provider": cfg.auditor.provider,
               "vendor": cfg.auditor.vendor, "model": cfg.auditor.model,
               "max_usd": args.max_usd, "spent_usd": round(spent, 6), "rows": len(rows),
               "stopped": stopped,
               "corpus_manifest_sha256": sha256_bytes((corpus / "manifest.jsonl").read_bytes()),
               "usage_ledger": str(out / ".crossaudit" / "usage.jsonl"),
               "utc_start": started.isoformat(timespec="seconds"),
               "utc_end": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (out / "auditor_run.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--profile", default="science",
                    help="the DCL profile whose output the auditor is shown")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--live", action="store_true")
    ap.add_argument("--price-models", default=DEFAULT_PRICE_MODELS,
                    help="vendor:model pairs for the dry-run cost table")
    ap.add_argument("--est-output-tokens", type=int, default=DEFAULT_EST_OUTPUT_TOKENS)
    ap.add_argument("--provider")
    ap.add_argument("--vendor")
    ap.add_argument("--model")
    ap.add_argument("--base-url")
    ap.add_argument("--reasoning-effort")
    ap.add_argument("--max-usd", type=float)
    ap.add_argument("--i-accept-cost", action="store_true")
    args = ap.parse_args(argv)
    if args.live:
        why = live_gate(args)
        if why:
            print(why, file=sys.stderr)
            return 2
        summary = live_run(args.corpus, args.out, args)
    else:
        summary = dry_run(args.corpus, args.out, args.profile, args.price_models,
                          args.est_output_tokens)
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
