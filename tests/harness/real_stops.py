"""Escalation rows built through the REAL console projection.

`StateStore.record_build_escalation` -> `overview.escalations`, one row per
cause the design names, so a test asserts against the payload the console is
actually handed rather than a hand-written dict that can drift from it.

Adapted from the independent review of the activity stream, whose method —
drive the real projection, then render through the whole shipped page — is now
the standard for this surface.
"""
import json, subprocess, tempfile, pathlib, sys
from crossaudit.config import load
from crossaudit.console import overview
from crossaudit.controller import StateStore
from crossaudit.errors import CONTESTED_MODEL_BLOCKER_REASON

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")
REPORT = """# Audit Report — t/p@{sha}

| | |
|---|---|
| verdict | **{verdict}** |
| round | {round} |
| constitution | `abc123def456` |
| auditor | `openai_compat:gpt` |

## Model findings

{findings}
"""
BLOCKER = ("### [BLOCKER] CA-TXT-001 — work/review.md\n"
           "The cited speed-up is not in the paper.\n")

#: The stop reason each case carries, as the ENGINE mints it — never an
#: invented sentence. A fixture that writes its own English hides exactly the
#: defect this file exists to expose: an escalation_reason painted, unopened,
#: into a Chinese first paint (`build round budget spent (3)` was).
DEFAULT_REASON = "build round budget spent (3)"          # cli/build.py:701
REASONS = {
    "auditor_concern": CONTESTED_MODEL_BLOCKER_REASON,   # errors.py
    "no_progress": "generator produced no new auditable revision in round 2",
    "repair_refused": ("the automatic repair was refused in round 2 because "
                       "work/a.md is a binary file written directly by the "
                       "generator, which cannot be reviewed line by line"),
    "provider": ("generator provider failure in round 2: all configured "
                 "generator provider routes failed. anthropic"),
    "escalation_locked": "",           # cmd_run records the lock with no reason
}

SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"

def make(tmp: pathlib.Path):
    root = tmp / "proj"; root.mkdir()
    subprocess.run(["git","init","-q","-b","main"], cwd=root, check=True)
    (root/"AUDIT_RULES.md").write_text("### CA-TXT-001\n**BLOCKER.** exact\n\nx\n")
    (root/"crossaudit.yml").write_text(CONFIG)
    return load(root/"crossaudit.yml")

def add_audit(cfg, sha, verdict, findings="", round_=1):
    d = cfg.root/cfg.ledger_dir/f"{sha}-r{round_}"
    d.mkdir(parents=True, exist_ok=True)
    (d/"report.md").write_text(REPORT.format(sha=sha,verdict=verdict,round=round_,findings=findings))
    return d

# every machine failure cause the design names, plus the judgment calls
CASES = [
    ("provider",        dict(kind="provider", cause="")),
    ("budget",          dict(kind="budget", cause="")),
    ("invalid_reply",   dict(kind="audit", cause="invalid_reply")),
    ("no_science_commit",dict(kind="audit", cause="no_science_commit")),
    ("nothing_audited", dict(kind="audit", cause="nothing_audited")),
    ("generator_format",dict(kind="audit", cause="generator_format")),
    ("no_progress",     dict(kind="audit", cause="no_progress")),
    ("bounds_exceeded", dict(kind="audit", cause="bounds_exceeded")),
    ("repair_refused",  dict(kind="audit", cause="repair_refused")),
    ("answered",        dict(kind="audit", cause="answered")),
    ("auditor_concern", dict(kind="audit", cause="auditor_concern")),
    ("auditor_escalated",dict(kind="audit", cause="auditor_escalated")),
    ("escalation_locked",dict(kind="audit", cause="escalation_locked")),
    ("limit_reached",   dict(kind="audit", cause="", limit=True)),
]

def rows():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        for name, spec in CASES:
            tmp = pathlib.Path(td)/name; tmp.mkdir()
            cfg = make(tmp)
            add_audit(cfg, SHA[:12], "BLOCKED" if spec.get("cause")!="" or spec["kind"]=="audit" else "PASS", BLOCKER, 2)
            store = StateStore(cfg.root/cfg.state_dir/"state.json")
            kw = dict(kind=spec["kind"])
            if spec.get("cause"): kw["cause"] = spec["cause"]
            try:
                store.record_build_escalation(
                    cfg.science_repo, SHA, REASONS.get(name, DEFAULT_REASON),
                    3 if spec.get("limit") else 2, "c1", "Fix the summary", **kw)
            except TypeError as e:
                out[name] = {"error": f"record_build_escalation: {e}"}
                continue
            got = overview.escalations(cfg)
            out[name] = got[0] if got else {"error":"no escalation row"}
    return out

_CACHE: dict | None = None


def cached_rows() -> dict:
    """`rows()` once per process — fourteen git inits is enough of them."""
    global _CACHE
    if _CACHE is None:
        _CACHE = rows()
    return _CACHE


if __name__ == "__main__":
    print(json.dumps(rows(), indent=1, default=str))
