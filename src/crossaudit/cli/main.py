"""The CLI. Verbs mirror the loop; exit codes are the contract.

Every verb prints human text by default and a versioned object under --json.
Nothing here writes to a remote without an explicit --apply, and no verb
invents a default when configuration is missing: absent config denies.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .. import RECEIPT_SCHEMA, __version__, _selfid
from ..auditor import dcl_source_digest, run_audit
from ..config import CONFIG_NAME, Config, heterogeneity, load
from ..controller import StateStore
from ..dcl import run_checks
from .. import doctor_shared
from ..doctor_shared import constitution_state, CONSTITUTION_READY_SENTENCE
from ..errors import (EXIT_BLOCKED, EXIT_CONFIG, EXIT_ESCALATED, EXIT_INTEGRITY,
                      EXIT_OK, ConfigDenial, Denial, IntegrityDenial)
from ..gitio import (changed_paths, entries, git, is_ancestor, is_repo, materialise,
                     parent, read_cap, read_committed_bytes, resolve)
from ..receipt import build as build_receipt
from ..receipt import digest as receipt_digest
from ..receipt import load as load_receipt
from ..receipt import verify as verify_receipt
from ..receipt.sign import sign_receipt
from ..receipt.verify import admit as admit_receipt
from ..receipt import reproduction as _reproduction
from ..receipt import sources as _sources
from . import i18n, tui, wizard
from .talk import cmd_routing, cmd_talk

ALLOW_CUSTOM_ENV = "CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT"


def _allow_custom(args: argparse.Namespace) -> bool:
    """Sending a key to a non-builtin origin is opt-in, by flag or environment.

    Both spellings exist because the conversational surface has no flags; they
    must mean the same thing, or one verb would send a key where another
    refused to.
    """
    return bool(getattr(args, "allow_custom_endpoint", False)
                or os.environ.get(ALLOW_CUSTOM_ENV))


def _committed_constitution(cfg: Config, commit: str) -> tuple[str, bytes]:
    """The exact UTF-8 rules bytes named by an audit and its receipt."""
    data = read_committed_bytes(cfg.root, commit, cfg.constitution)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityDenial(
            f"the committed constitution at {commit[:12]} is not valid UTF-8",
            commit=commit, path=cfg.constitution) from exc
    if not text.strip():
        raise ConfigDenial(
            f"the committed constitution at {commit[:12]} is empty; an audit "
            "cannot apply a missing standard", commit=commit, path=cfg.constitution)
    return text, data

def _print_origin() -> None:
    """One line under the front door naming which install this is.

    D40: the version alone does not answer "which crossaudit did I just run",
    which is the question somebody has when a DMG app and a pip install disagree.
    """
    mode, where = running_from()
    print("\n  " + i18n.t("origin.front_door", version=f"crossaudit {__version__}",
                          mode=mode, path=where))


def running_from() -> tuple[str, str]:
    """(install mode, the path this process is actually running from).

    D40. A person who installs the DMG and types `crossaudit` can be routed to a
    completely different, older install that is already on PATH — and nothing
    told them. The ledger stays honest either way: receipts carry the version, a
    path-tagged code digest and the install mode, and `verify --admit` already
    refuses modes whose code could have changed under it. What is misled is the
    PERSON, so the fix belongs on the surfaces a person reads.

    Facts about THIS process only. It deliberately does not go looking for other
    installs: guessing where a rival copy might live would be inventing evidence
    on exactly the surface that exists to stop us doing that. Two runs printing
    two versions and two paths is self-evident without anyone asserting a
    mismatch.
    """
    mode = _selfid.install_mode()
    if getattr(sys, "frozen", False):
        return mode, sys.executable
    # What the person invoked, when that is knowable; otherwise where the code
    # actually is. `argv[0]` is the console script they typed.
    invoked = Path(sys.argv[0]) if sys.argv and sys.argv[0] else None
    if invoked is not None and invoked.name and invoked.exists():
        return mode, str(invoked.resolve())
    return mode, str(Path(_selfid.__file__).resolve().parent)


GETTING_STARTED = """\
CrossAudit {version} — cross-vendor generation and audit loop

Nothing is configured yet in this directory. One command sets it up; it will
ask for the two models, the two API keys, and your plain-language quality
requirements. It writes keys to a 0600 file outside the repository.

    crossaudit init              guided setup, right here
    crossaudit init --github     the same, plus the two-repository plan

Then, two ways to work:

    crossaudit build "..."       say what you need; CrossAudit writes it, then a
                                 second model from a different vendor checks the
                                 result before you see it
    crossaudit console           the same loop in a browser, live, and it
                                 outlives the window

    crossaudit run               already have a commit? audit that instead

It reads the increment from the commit itself, runs the deterministic checks,
runs the model audit when a key is present, writes the ledger, and tells you
what to do next. The precise tools underneath it, when you want them:

    crossaudit doctor · check · audit · verify · status

Docs: README.md in the repository.
"""


#: One sentence about the language wave, said identically everywhere it is
#: said. init and doctor previously stated DIFFERENT scopes in their help, which
#: is a contradiction a person meets before they meet the limitation itself.
LANG_HELP = ("language for this command; overrides your system locale "
             "(wave 1: init and doctor only)")

#: Stated in `build`'s own help, because build is where the language stops and
#: a limitation only an engineer can read is not disclosed.
BUILD_ENGLISH_NOTE = ("  Output is English in this wave; --lang is not offered "
                      "here until the round-by-round narration can follow it.")
#: What `check` says when there is nothing to check yet. Deliberately free of
#: `DCL:schema` and `audited scope`: this is the first thing a new user sees
#: after setup, and it has to be readable by someone who has not learned the
#: product's vocabulary. It states what the command is for, that it has nothing
#: to look at, and what would give it something.
NOTHING_TO_AUDIT_SENTENCE = (
    "Nothing to check yet — this command reviews work you have added, and "
    "there is none here so far.")
NOTHING_TO_AUDIT_NEXT = (
    "  Add a folder under {scope}/ with your results, then run this again.")


def _emit(obj: dict, as_json: bool, human: str = "") -> None:
    if as_json:
        print(json.dumps({"crossaudit": __version__, **obj}, indent=2, sort_keys=True))
    elif human:
        print(human)


#: How each re-derived receipt input is announced. The two check-layer statuses
#: get their own words on purpose: that comparison is against THIS installation,
#: not against an object the receipt cites, and a reader must not be able to
#: mistake it for a re-derivation.
_DERIVATION_LABEL = {
    "corroborated": "DERIVED",
    "diverged": "DIVERGED",
    "not-derivable": "NOT DERIVABLE",
    "local-match": "SAME CHECK LAYER",
    "local-differs": "OTHER CHECK LAYER",
}


def _derivation_lines(evidence: dict) -> str:
    """What `verify` tells a person about the three inputs it re-derived.

    Rendered from the rows the verifier returned, never re-computed here: a
    reader of this line and a consumer of the JSON must be looking at the same
    evidence.
    """
    lines = []
    for row in evidence.get("input_derivations") or ():
        label = _DERIVATION_LABEL.get(row.get("status", ""), "UNKNOWN")
        lines.append(f"\n{label}  {row['claim']}: {row['detail']}")
    return "".join(lines)


def _skills_manifest(cfg: Config, sha: str = "") -> dict:
    """House skills as the SUBJECT COMMIT holds them, by path and hash.

    This read the working directory, so a receipt named and hashed
    `skills/late.md` as guidance that "shaped this round" when that file was
    created after the audited commit and existed in no tree. A receipt claiming
    a skill informed work that predates the skill is a provenance falsehood, and
    it is the constitution defect wearing different clothes: the field names a
    source of truth and the writer reads whatever is on disk.

    Deliberately the SAME idea as the constitution rather than a second
    mechanism — the receipt's inputs are derived from the commit being judged. A
    skill absent from that commit cannot be attested, exactly as an uncommitted
    rule cannot be cited. Under-claiming is the honest direction; the
    alternative is an unverifiable claim about the past.

    `sha` is optional so sample and legacy callers keep working; an empty one
    falls back to the disk read and is the only path that still can.
    """
    from .. import skills as skills_mod

    if not sha:
        try:
            return skills_mod.manifest(skills_mod.load(cfg.root))
        except Denial:
            return {}
    try:
        files, _notes = materialise(cfg.root, sha, skills_mod.SKILLS_DIR)
    except Denial:
        return {}
    import hashlib

    return {rel: hashlib.sha256(data).hexdigest()
            for rel, data in sorted(files.items()) if rel.endswith(".md")}


def _sha256_file(path: Path) -> str:
    return __import__("hashlib").sha256(path.read_bytes()).hexdigest()


def _write_reproduction(receipt: dict, cycle_dir: Path) -> bool:
    """A2: write reproduction.json beside the receipt when the audited tree
    carried a dependency lock. Fail-open — a write problem never blocks an audit,
    it just leaves the (still fully-bound) receipt without its expanded sidecar."""
    try:
        if receipt.get("reproduction") is None:
            return False
        bundle = _reproduction.build_bundle(receipt)
        (cycle_dir / "reproduction.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
        return True
    except Exception:  # noqa: BLE001 -- the sidecar is a convenience, never a gate
        return False


def _write_sources(cfg: Config, receipt: dict, cycle_dir: Path) -> bool:
    """A4: write sources.json (the expanded governed-source provenance list)
    beside the receipt when the cycle retrieved governed literature. Fail-open."""
    try:
        if receipt.get("sources") is None:
            return False
        full = _sources.bundle(cfg, receipt)
        if full is None:
            return False
        (cycle_dir / "sources.json").write_text(
            json.dumps(full, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
        return True
    except Exception:  # noqa: BLE001 -- the sidecar is a convenience, never a gate
        return False


def _state(cfg: Config) -> StateStore:
    """The state store lives beside the configuration, never in site-packages."""
    return StateStore(cfg.root / cfg.state_dir / "state.json")


def _is_scaffold_template(path: str) -> bool:
    return "TEMPLATE" in Path(path).parts


def _materialise_tree_scope(cfg: Config, sha: str,
                            explicit_scope: str | None
                            ) -> tuple[dict[str, bytes], list[str], str]:
    """Read the explicit scope, or every configured science scope, from git."""
    prefixes = [explicit_scope] if explicit_scope else (cfg.scope_dirs or [""])
    files: dict[str, bytes] = {}
    notes: list[str] = []
    for prefix in prefixes:
        scoped, scoped_notes = materialise(cfg.root, sha, prefix)
        files.update(scoped)
        notes.extend(scoped_notes)
    files = {p: data for p, data in files.items() if not _is_scaffold_template(p)}
    notes = [n for n in notes
             if not _is_scaffold_template(n.partition(": ")[2])]
    scope_text = ", ".join(prefixes) if any(prefixes) else ""
    return files, notes, scope_text


def _committed_task(cfg: Config, sha: str) -> str:
    """Return TASK.md from the audited tree, never from the working directory."""
    task_files, _notes = materialise(cfg.root, sha, "TASK.md")
    raw = task_files.get("TASK.md")
    if raw is None:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigDenial("committed TASK.md is not UTF-8") from exc


# ----------------------------------------------------------------- doctor
def _offer(args, prompt: str) -> bool:
    """In --fix mode on a terminal, ask; otherwise never touch anything."""
    if not getattr(args, "fix", False) or not sys.stdin.isatty():
        return False
    return input(f"       fix now — {prompt} [Y/n] ").strip().lower() in ("", "y", "yes")


def _speak(args: argparse.Namespace) -> None:
    """Select this COMMAND's language. Called only by commands in a shipped wave.

    Deliberately per-command rather than in the dispatcher. A central switch
    would translate any command that happened to carry a `--lang` attribute,
    which is how a half-translated surface ships (D21); and it would do nothing
    for a caller that invokes `cmd_doctor` directly rather than through argv,
    which is how the console and the tests call these. Here, the set of
    translated commands is visible at the commands themselves.
    """
    # An explicit flag wins; then the language the person's system already
    # asked for; then English. The middle step is the one that matters: a Mac
    # set to Chinese should not need a flag nobody documented.
    i18n.set_language(getattr(args, "lang", None)
                      or i18n.from_environment()
                      or i18n.DEFAULT_LANGUAGE)
    i18n.reset_fallbacks()


def cmd_doctor(args: argparse.Namespace) -> int:
    _speak(args)
    checks: list[dict] = []
    ok = True

    def add(name: str, passed: bool, detail: str, fix: str = "", *,
            copy: str = "", slots: dict | None = None,
            detail_copy: str = "") -> None:
        """A tested condition. [PASS] here means it ran and it held.

        ``copy`` names this check's HUMAN copy in the catalogue — the default
        view renders ``<copy>.label`` / ``.why`` / ``.fix`` with ``slots``. It
        sits BESIDE ``detail`` and ``fix`` rather than replacing them, because
        those two are carried verbatim by ``--json`` and by ``--all``, which is
        the stable surface for CI. Translating them in place would put Chinese
        in a scripting contract; the check NAME is a ``--json`` key for the same
        reason and is never translated (SPEC-7 §4: type, match, or trace).
        """
        nonlocal ok
        ok = ok and passed
        checks.append({"check": name, "ok": passed, "detail": detail, "fix": fix,
                       "kind": "verdict", "copy": copy,
                       "detail_copy": detail_copy,
                       "slots": {k: str(v) for k, v in (slots or {}).items()}})

    def note(name: str, detail: str, *, copy: str = "",
             slots: dict | None = None, detail_copy: str = "",
             standing: str = "") -> None:
        """A posture, a mode or a configured contract — NOT a test result.

        SPEC 2 (design/UX, Ledger D6): ``[PASS]`` means a condition was tested
        and held. A line that reports how the deployment is *set up* has no
        pass/fail axis, so it renders as ``[INFO]`` and is excluded from the
        tally. The defect this removes is a green marker sitting beside text
        that says a guarantee does not hold — the CLI twin of the console's four
        green ticks for checks that never ran.
        """
        checks.append({"check": name, "ok": None, "detail": detail, "fix": "",
                       "kind": "info", "copy": copy,
                       "detail_copy": detail_copy, "standing": standing,
                       "slots": {k: str(v) for k, v in (slots or {}).items()}})

    ident = _selfid.identity()
    add("python", sys.version_info >= (3, 10),
        f"{sys.version.split()[0]}", "CrossAudit requires Python 3.10+",
        copy="doctor.python")
    # Doctor already named the mode and the digest; it did not say WHERE. The
    # path is appended to that same line rather than given a second sentence of
    # its own — two phrasings for one truth is its own defect (D40).
    add("install", ident["install_mode"] != "unknown",
        f"{ident['install_mode']}, code digest "
        f"{ident['code_digest_sha256'][:12]}, at {running_from()[1]}",
        "reinstall from a wheel if this says unknown", copy="doctor.install")
    for name, detail in doctor_shared.install_blocks(ident):
        if name == "admission-capable":
            add("admission-capable", False, detail,
                "install the built wheel to admit receipts",
                copy="doctor.admission_capable")
    add("git", shutil.which("git") is not None, shutil.which("git") or "not found",
        "install git", copy="doctor.git")

    try:
        cfg = load()
    except ConfigDenial as exc:
        add("config", False, exc.reason,
            f"run `crossaudit init` to write {CONFIG_NAME}",
            copy="doctor.config", slots={"name": CONFIG_NAME})
        # F3. The error route leaves through the SAME boundary as the success
        # route. It used to print the human screen directly and return, so
        # `--json` on an unconfigured project emitted a Chinese human screen and
        # no JSON at all: a parser met prose, and only on the error path — which
        # is exactly where nobody was looking. One emit, both routes.
        _emit({"ok": False, "checks": checks, "verifier": ident,
               "admission": None}, getattr(args, "json", False),
              _render_doctor(checks, False, getattr(args, "all", False)))
        if not getattr(args, "json", False) and _offer(
                args, "run the setup wizard here"):
            wizard.run(Path("."), mode="local", force=False)
            print("\nSetup written — running doctor again:\n")
            return cmd_doctor(args)
        return EXIT_CONFIG

    add("config", True, str(cfg.path))
    const = cfg.root / cfg.constitution
    add("constitution", const.is_file(), str(const),
        "point `constitution:` at your rules markdown", copy="doctor.constitution")
    if const.is_file():
        from ..auditor import known_rules
        rules = known_rules(const.read_text(encoding="utf-8"))
        # A constitution with no rules is a legitimate choice, not a broken
        # file: the constitution is the STANDARD and the audit is the MECHANISM,
        # so an empty standard produces an honest audit of an empty standard
        # (Ledger D8). `init` offers it by name — "Only what I write myself" —
        # so doctor must not then call the person's choice a defect. A file that
        # meant to have rules and parsed none is still worth flagging, and the
        # difference is whether it says so.
        deliberately_empty = "No rules yet." in const.read_text(encoding="utf-8")
        if rules or not deliberately_empty:
            add("constitution rules", bool(rules),
                f"{len(rules)} rule IDs parsed" if rules
                else "no CA-* rule headings found",
                "each rule needs a '### CA-AREA-NNN' heading, or every citation "
                "is unknown", copy="doctor.constitution_rules")
        else:
            # F3. This stored the TRANSLATED sentence in `detail`, which is the
            # machine field `--json` and `--all` carry verbatim — so a script
            # parsing doctor got Chinese under LANG=zh, silently and only for
            # Chinese users. A parser does not read Chinese; `detail` is a
            # contract with it. The human string moves to `detail_copy`.
            note("constitution rules",
                 "no rules yet — nothing is gated until you add one; the automatic checks still run",
                 copy="doctor.constitution_rules",
                 detail_copy="doctor.constitution_rules.none")

    # These are the CONFIGURED contracts, printed so a person can read what the
    # deterministic layer will enforce. Nothing has run: doctor is offline and
    # read-only, and there is no increment to judge. They carried [PASS] before,
    # which is the same false green as the console panel D6 flagged.
    from ..dcl import contracts as live_contracts
    for name, contract in live_contracts(cfg.checks).items():
        note(f"machine:{name}", contract)

    het_ok, why = heterogeneity(cfg)
    add("heterogeneity (I1)", het_ok, why,
        "declare generator.vendor, and make it differ from auditor.vendor",
        copy="doctor.heterogeneity")

    from ..providers.registry import NEEDS_KEY, known
    key_needed = NEEDS_KEY.get(cfg.auditor.provider, True)
    key_present = (not key_needed or
                   bool(os.environ.get(cfg.auditor.key_env, "").strip()))
    if key_needed and not key_present and _offer(
            args, f"enter the auditor API key (hidden, saved to {wizard.keys_file()})"):
        import getpass
        entered = getpass.getpass("       auditor API key: ").strip()
        if entered:
            written = wizard.write_keys({cfg.auditor.key_env: entered})
            os.environ[cfg.auditor.key_env] = entered
            key_present = True
            print(f"       saved; future shells: source {written}")
    # Presence only. Doctor output is commonly copied into bug reports; even a
    # key suffix and length are unnecessary credential metadata there.
    add("auditor connection", key_present,
        ("provider-managed subscription; no API key needed"
         if not key_needed else
         f"${cfg.auditor.key_env} " + ("present" if key_present else "is empty")),
        ("sign in through CrossAudit Settings" if not key_needed else
         f"source {wizard.keys_file()} or export {cfg.auditor.key_env}"),
        copy=("doctor.auditor_key" if key_needed else ""),
        slots={"path": wizard.keys_file(), "env": cfg.auditor.key_env})

    # The credential that stops `build` in its first round. doctor said "check
    # everything" while never looking at it, so a person could pass doctor and
    # then fail on their first task (Ledger D6, P1).
    generator_env = cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY"
    generator_key_present = bool(os.environ.get(generator_env, "").strip())
    generator_needs_key = _generator_needs_key(cfg)
    if generator_needs_key and not generator_key_present and _offer(
            args, f"enter the generator API key (hidden, saved to {wizard.keys_file()})"):
        import getpass
        entered = getpass.getpass("       generator API key: ").strip()
        if entered:
            written = wizard.write_keys({generator_env: entered})
            os.environ[generator_env] = entered
            generator_key_present = True
            print(f"       saved; future shells: source {written}")
    add("generator connection", (not generator_needs_key) or generator_key_present,
        ("no API key needed for this generator"
         if not generator_needs_key else
         f"${generator_env} " + ("present" if generator_key_present else "is empty")),
        f"source {wizard.keys_file()} or export {generator_env} — "
        f"without it `crossaudit build` stops in round one",
        copy="doctor.generator_key",
        slots={"path": wizard.keys_file(), "env": generator_env})
    if cfg.isolation_minimum.get("permissive") and key_present and generator_key_present:
        add("isolation minimum", False,
            "permissive isolation is required, but this process can reach both roles' keys",
            "run the auditor in a separate credential boundary, or deliberately lower "
            "isolation.minimum.permissive between cycles", copy="doctor.isolation")

    # Asked of the registry, not restated here: a local allowlist failed valid
    # Gemini/Qwen setups the release after those vendors were registered.
    add("provider", cfg.auditor.provider in known(),
        f"{cfg.auditor.provider}:{cfg.auditor.model}",
        "set auditor.provider to one of: " + ", ".join(sorted(known())),
        copy="doctor.provider", slots={"providers": ", ".join(sorted(known()))})

    # A trust store this interpreter cannot read fails every call to every
    # vendor, and does it at the moment someone types their first sentence.
    # Costs nothing to check here, where the fix still reads as setup.
    from ..providers.base import tls_context

    certs = len(tls_context().get_ca_certs())
    add("tls trust store", bool(certs),
        f"{certs} root certificate(s)" if certs
        else "empty — every HTTPS call to a vendor will fail",
        "pip install certifi, or export SSL_CERT_FILE=/path/to/ca-bundle.pem "
        "(macOS python.org builds: run Install Certificates.command)",
        copy="doctor.tls")

    state_dir = cfg.root / cfg.state_dir
    writable = os.access(state_dir.parent, os.W_OK)
    add("state store", writable, str(state_dir / "state.json"),
        "the controller must be able to persist consumed receipts",
        copy="doctor.state", slots={"path": state_dir / "state.json"})

    repo_ok = is_repo(cfg.root)
    if not repo_ok and _offer(args, f"run git init in {cfg.root}"):
        git("init", "-q", "-b", "main", cwd=cfg.root)
        repo_ok = is_repo(cfg.root)
    add("science repo is git", repo_ok, str(cfg.root),
        "run `git init` — the ledger is git, not a directory", copy="doctor.repo")
    if repo_ok:
        git_name = git("config", "user.name", cwd=cfg.root, check=False).strip()
        git_email = git("config", "user.email", cwd=cfg.root, check=False).strip()
        add("git identity", bool(git_name and git_email),
            f"{git_name} <{git_email}>" if git_name and git_email
            else "this clone has no effective user.name/user.email",
            "set them for this repository with `git config user.name NAME` and "
            "`git config user.email EMAIL`", copy="doctor.git_identity")
        # ONE implementation of "are the rules committed", not two that agree
        # today. `doctor_shared.constitution_state` already decides the three
        # states and owns their sentences; this consumed a second helper and
        # then rebuilt the same wording beside it, which is how the CLI and the
        # app came to say the same thing in two voices.
        const_status, const_detail = constitution_state(cfg)
        if const_status != "ready" and _offer(
                args, f"commit {cfg.constitution} so audits can cite its version"):
            git("add", "--", cfg.constitution, cwd=cfg.root)
            git("commit", "-q", "-m", "constitution: initial version", cwd=cfg.root)
            const_status, const_detail = constitution_state(cfg)
        # The state the shared helper already decided picks the human copy, so
        # "committed, then edited" cannot be reported as "never committed".
        add("constitution committed", const_status == "ready", const_detail,
            f"git add {cfg.constitution} && git commit",
            copy=("doctor.constitution_drifted" if const_status == "drifted"
                  else "doctor.constitution_committed"),
            slots={"name": cfg.constitution})

    if args.online:
        gh_ok, gh_detail = wizard.gh_available()
        add("gh cli", gh_ok, gh_detail, "install gh and run `gh auth login`",
            copy="doctor.gh")

    # The tier this deployment can honestly claim, from evidence rather than
    # from configuration. Reported always: a system that only mentions its
    # weaknesses when asked is not being honest, it is being quiet.
    from .. import admission as adm

    caps = _state(cfg).capabilities()
    verdict = adm.assess(root=cfg.root, paired=bool(cfg.audit_repo),
                         controller_persistent=caps["persistent"],
                         controller_atomic=caps["atomic"], online=args.online)
    note("admission tier", f"{verdict.tier} — {adm.TIER_MEANING[verdict.tier]}",
         copy="doctor.tier",
         standing=f"doctor.tier.standing.{verdict.tier.lower()}")
    for shortfall in verdict.shortfalls:
        note("  toward enforced", shortfall)

    _emit({"ok": ok, "checks": checks, "verifier": ident,
           "admission": verdict.as_dict()}, args.json,
          _render_doctor(checks, ok, getattr(args, "all", False)))
    return EXIT_OK if ok else EXIT_CONFIG


#: Plain language for the checks a newcomer meets first, with the rule id kept.
#: Precision over friendliness (SPEC 6 §4): renaming without the id would break
#: a person's ability to trace a verdict back to their own constitution and to
#: the receipt, so the id stays in parentheses rather than being replaced.
#: A missing entry keeps the raw name — this table adds clarity, it is never
#: required for a line to render.
DOCTOR_COPY: dict[str, tuple[str, str]] = {
    "auditor connection": ("No auditor API key",
                           "CrossAudit cannot run an audit without one."),
    "generator connection": ("No generator API key",
                             "CrossAudit cannot write anything without one."),
    "heterogeneity (I1)": ("Generator and auditor are different vendors (I1)", ""),
    "admission tier": ("How much this project's history proves", ""),
    "  toward enforced": ("", ""),
    "machine:schema": ("Results file has the required structure (schema)", ""),
    "machine:units": ("Every number carries a unit and a source (units)", ""),
    "machine:convergence": ("Anything reported as converged met its threshold "
                               "(convergence)", ""),
    "machine:provenance": ("Every source traces to a declared input "
                              "(provenance)", ""),
    "admission-capable": ("This install cannot admit receipts",
                          "It can generate, audit and verify; it cannot consume a "
                          "receipt as admitted evidence."),
    "constitution rules": ("Your rules", ""),
}


def _doctor_label(check: dict) -> tuple[str, str]:
    """(label, consequence) for the HUMAN view, translated.

    Falls back to the untranslated DOCTOR_COPY table and then to the check NAME,
    which is a `--json` key and therefore never translated (SPEC-7 §4).
    """
    stem = check.get("copy") or ""
    if stem:
        slots = check.get("slots", {})
        # An INFO row prints its own detail, never a consequence, so asking the
        # catalogue for `.why` here would invent a missing translation and mark
        # a gap that does not exist.
        why = ("" if check.get("kind") == "info"
               else i18n.t(f"{stem}.why", **slots))
        return i18n.t(f"{stem}.label", **slots), why
    if check["check"] in DOCTOR_COPY:
        return DOCTOR_COPY[check["check"]]
    return check["check"], ""


def _doctor_fix(check: dict) -> str:
    """The remedy, in the person's language, with the command left alone.

    `fix` itself stays English because `--all` and `--json` carry it verbatim;
    this is the parallel human string. A command inside it (`crossaudit init`,
    `git config`) is something a person TYPES and is not translated — but the
    sentence around it is prose and does not ride along in English merely
    because it contains one.
    """
    stem = check.get("copy") or ""
    if not stem:
        return check["fix"]
    key = f"{stem}.fix"
    if stem == "doctor.auditor_key" and "no API key needed" in check["detail"]:
        key = f"{stem}.fix.subscription"
    return i18n.t(key, **check.get("slots", {}))


def _doctor_detail(check: dict) -> str:
    """The human detail for a line, or the machine one when there is no parallel.

    `detail` is what `--all` and `--json` carry verbatim, so it is never
    translated — the boundary this function exists to hold. A line that needs a
    sentence in the person's language names it with `detail_copy`.
    """
    key = check.get("detail_copy") or ""
    if not key:
        return check["detail"]
    return i18n.t(key, **check.get("slots", {}))


def _render_doctor(checks: list[dict], ok: bool, show_all: bool = False) -> str:
    """[PASS] tested and held · [FAIL] tested and did not · [INFO] not a test.

    An INFO line reports a posture, a mode or a configured contract. It carries
    no verdict and is not counted, so the tally below means what it says.
    """
    if show_all:
        return _render_doctor_full(checks, ok)
    failed = [c for c in checks if c.get("kind") != "info" and not c["ok"]]
    info = [c for c in checks if c.get("kind") == "info"]
    passed = [c for c in checks if c.get("kind") != "info" and c["ok"]]

    lines = [i18n.t("doctor.title"), ""]
    # The verdict is the FIRST line. It used to be the last, so a person read
    # twenty-one lines before learning the answer.
    if failed:
        n = len(failed)
        lines.append("  " + i18n.t("doctor.not_ready" if n == 1
                                   else "doctor.not_ready.plural", n=n))
    else:
        lines.append("  " + i18n.t("doctor.ready"))
    lines.append("")
    for c in failed:
        label, consequence = _doctor_label(c)
        lines.append(f"  ✗ {label}")
        # Consequence before remedy: what you cannot do, then what to type.
        lines.append(f"      {consequence or _doctor_detail(c)}")
        if c["fix"]:
            lines.append(f"      → {_doctor_fix(c)}")
    if failed:
        lines.append("")
    # The configured deterministic contracts are reference material, not
    # something a person needs at first contact, so they collapse the same way
    # the passing checks do. What stays visible is the posture — the thing that
    # changes what this project can prove.
    contracts = [c for c in info if c["check"].startswith("machine:")]
    posture = [c for c in info if not c["check"].startswith("machine:")]
    for c in posture:
        label, _consequence = _doctor_label(c)
        if label:
            lines.append(f"  ℹ {label}")
        lines.append(f"      {_doctor_detail(c)}")
        # The row's own second sentence, never an arrow. `→` means "you have
        # something to do"; a posture has nothing to do, and putting one here
        # manufactures a task out of a state of the world. What a person is
        # missing is not a remedy but whether this state needs anything --
        # which is why the sentence starts by saying that it does not.
        if c["standing"]:
            lines.append(f"      {i18n.t(c['standing'])}")
    if posture:
        lines.append("")
    if contracts:
        n = len(contracts)
        lines.append("  ℹ " + i18n.t("doctor.contracts" if n == 1
                                     else "doctor.contracts.plural", n=n))
    # The passing majority collapses to a count. `--all` prints every line
    # unchanged, so nothing is lost and CI keeps a stable surface.
    n = len(passed)
    lines.append("  ✓ " + i18n.t("doctor.other_passed" if n == 1
                                 else "doctor.other_passed.plural", n=n))
    return "\n".join(lines)


def _render_doctor_full(checks: list[dict], ok: bool) -> str:
    """Every line, unchanged. `--all` is the stable surface for CI and scripts."""
    lines = ["crossaudit doctor", "=" * 60]
    width = max([len(c["check"]) for c in checks] or [22]) + 1
    for c in checks:
        mark = "INFO" if c.get("kind") == "info" else ("PASS" if c["ok"] else "FAIL")
        lines.append(f"[{mark}] {c['check']:{width}s} {c['detail']}")
        if mark == "FAIL" and c["fix"]:
            lines.append(f"       -> {c['fix']}")
    lines.append("=" * 60)
    lines.append("ready" if ok else "not ready — fix the FAIL lines above")
    return "\n".join(lines)


def _generator_needs_key(cfg) -> bool:
    """Whether this project's generator role needs an API key of its own."""
    from ..providers.registry import NEEDS_KEY
    if (cfg.generator_vendor or "").lower() == "human":
        return False
    provider = getattr(getattr(cfg, "generator", None), "provider", "") or ""
    return NEEDS_KEY.get(provider, True) if provider else True


# ------------------------------------------------------------------ check
def cmd_check(args: argparse.Namespace) -> int:
    cfg = load()

    if args.sha:
        sha, _tree = resolve(cfg.root, args.sha)
        files, notes, scope_text = _materialise_tree_scope(cfg, sha, args.scope)
        scope_text = scope_text or "repository"
        where = f"{sha[:12]}:{scope_text} (from the git tree)"
    else:
        files, notes = {}, []
        explicit = bool(args.path)
        if explicit:
            roots = [(Path(args.path).resolve(), Path(args.path).resolve())]
        elif cfg.scope_dirs:
            roots = [(cfg.root / scope, cfg.root) for scope in cfg.scope_dirs]
        else:
            roots = [(cfg.root, cfg.root)]
        excluded = {".git", cfg.state_dir.split("/", 1)[0],
                    cfg.ledger_dir.split("/", 1)[0]}
        kept: dict[str, bytes] = {}
        oversized: list[str] = []
        for root, relative_to in roots:
            # os.walk is lazy and lets us PRUNE .git / the state dir / the ledger
            # dir before descending, so a multi-GB ledger or object store is
            # never walked — unlike the old sorted(rglob("*")) which materialised
            # the whole recursive listing and filtered it afterwards.
            for dirpath, dirnames, filenames in os.walk(root):
                base = Path(dirpath)
                keep_dirs = []
                for name in dirnames:
                    child = base / name
                    parts = child.relative_to(relative_to).parts
                    if not explicit and parts and parts[0] in excluded:
                        continue
                    if child.is_symlink():
                        raise ConfigDenial(
                            f"refusing to read through a symlink: {child}")
                    keep_dirs.append(name)
                dirnames[:] = keep_dirs
                for name in filenames:
                    p = base / name
                    if p.is_symlink():
                        raise ConfigDenial(f"refusing to read through a symlink: {p}")
                    if not p.is_file():
                        continue
                    rel = p.relative_to(relative_to).as_posix()
                    if _is_scaffold_template(rel):
                        continue
                    if not explicit and Path(rel).parts[0] in excluded:
                        continue
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    # Same per-path bound the blob reader uses; an oversized file
                    # is noted unread rather than pulled whole into memory.
                    if st.st_size > read_cap(rel):
                        oversized.append(rel)
                        continue
                    kept[rel] = p.read_bytes()
        # Preserve the previous global path ordering by sorting the kept keys
        # only, rather than sorting a listing of the entire tree up front.
        for rel in sorted(kept):
            files[rel] = kept[rel]
        notes.extend(f"unread (too large): {rel}" for rel in sorted(oversized))
        where = f"{', '.join(str(root) for root, _ in roots)} (working tree)"
    # A4/C.2: give the opt-in source-provenance check the governed source-id set.
    ctx = None
    if "source_provenance" in cfg.checks:
        from ..dcl.framework import CheckContext
        ctx = CheckContext(governed_source_ids=_sources.governed_source_ids(cfg))
    result = run_checks(files, cfg.checks, notes, cfg.plugins, context=ctx).as_dict()
    if not result["scope_started"]:
        # What a first-time user meets straight after `init`. No rule ids, no
        # "audited scope": this command has nothing to look at yet, and saying
        # BLOCKED with two hard failures told them they had done something
        # wrong before they had done anything at all.
        human = [NOTHING_TO_AUDIT_SENTENCE,
                 NOTHING_TO_AUDIT_NEXT.format(scope=cfg.scope_dirs[0])]
        _emit(result, args.json, "\n".join(human))
        return EXIT_OK
    human = [f"deterministic layer over {where}",
             f"verdict: {result['verdict']}  ({result['total_hard_failures']} hard failures)"]
    for f in result["findings"]:
        human.append(f"  [{f['severity']}] {f['rule']} {f['artifact']}: {f['observation']}")
    _emit(result, args.json, "\n".join(human))
    return EXIT_BLOCKED if result["total_hard_failures"] else EXIT_OK


def _provider_stop_reason(outcome) -> str:
    """The human sentence for an escalation whose model audit could not run.

    Routing to the provider remedies is the structured ``escalation_kind``'s
    job now (see _provider_stop_kind); this reason is the sentence a person
    reads, and it keeps the "provider failure" marker so a record written
    before the field existed still classifies. Content rounds keep their
    default reasons.
    """
    if outcome.integrity != "PROVIDER_FAILURE":
        return ""
    detail = str(outcome.exchange.get("error", "")).strip()
    return ("provider failure: the model audit could not run"
            + (f" — {detail[:300]}" if detail else ""))


def _provider_stop_kind(outcome) -> str:
    """The structured escalation kind for a round's stop.

    The classification the controller stores, so the Console routes on a
    field instead of re-reading the reason. "" lets the store infer a content
    ("audit") stop; a provider outage is named outright.
    """
    return "provider" if outcome.integrity == "PROVIDER_FAILURE" else ""


# ------------------------------------------------------------------ audit
def cmd_audit(args: argparse.Namespace) -> int:
    cfg = load()
    if not is_repo(cfg.root):
        raise ConfigDenial(f"{cfg.root} is not a git repository")
    sha, tree = resolve(cfg.root, args.sha or "HEAD")

    # Local mode writes the ledger into the audited repository, so HEAD moves
    # when a report is committed. Auditing that commit would audit the audit —
    # a self-referential cycle that inflates the ledger and audits nothing.
    changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha,
                  cwd=cfg.root, check=False).splitlines()
    if changed and all(p.startswith(cfg.ledger_dir.rstrip("/") + "/") for p in changed):
        raise ConfigDenial(
            f"{sha[:12]} only touches the ledger ({cfg.ledger_dir}/): this is an audit "
            f"artefact, not an increment. Audit the science commit instead, or move the "
            f"ledger to the audit repository (github-pair mode).")

    store = _state(cfg)
    continuation = getattr(args, "continue_cycle", None)
    # The standard this audit will apply, chosen BEFORE the cycle is opened so a
    # newly opened cycle can be pinned to it (D36 clause 1).
    head_const_commit = git("log", "-1", "--format=%H", "--", cfg.constitution,
                            cwd=cfg.root, check=False) or ""
    if not head_const_commit:
        raise ConfigDenial(
            f"{cfg.constitution} is not committed: an audit must cite the commit that "
            f"versioned the rules (I3). Commit it first.")

    if continuation:
        prior = store.cycle(continuation)
        if prior is None:
            raise ConfigDenial(f"build continuation cycle {continuation} no longer exists")
        if not is_ancestor(cfg.root, prior["active_sha"], sha):
            raise ConfigDenial(
                f"refusing to continue cycle {continuation}: {sha[:12]} does not "
                f"descend from its active commit {prior['active_sha'][:12]}")
        cycle = store.continue_cycle(continuation, cfg.science_repo, sha)
    else:
        cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha),
                                      constitution_commit=head_const_commit)
    if cycle.get("already_admitted"):
        raise ConfigDenial(f"{sha[:12]} was already admitted; open a new increment")
    if cycle.get("verdict_already_recorded"):
        # D36 clause 2. Re-running the same commit used to advance a round and
        # replace the recorded decision. It is refused rather than absorbed, and
        # the sentence says which of the two legitimate routes to take.
        raise ConfigDenial(
            f"{sha[:12]} already has a recorded decision in this cycle "
            f"({cycle['status']}); a decision already made is not replaced by "
            f"re-running it. Commit a revision to continue the cycle, or start a "
            f"new increment to be judged afresh.",
            cycle_id=cycle["cycle_id"], status=cycle["status"])

    files, notes, scope_text = _materialise_tree_scope(cfg, sha, args.scope)
    # A cycle is judged against the standard it began under. Reading the working
    # tree instead let a constitution loosened mid-cycle re-judge work the cycle
    # had already decided on — the D34 defect. Pre-D36 cycles carry no pin and
    # fall back to HEAD, which is exactly today's behaviour for them.
    const_commit = cycle.get("constitution_commit") or head_const_commit
    constitution, constitution_bytes = _committed_constitution(cfg, const_commit)

    task = _committed_task(cfg, sha)
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files, notes=notes,
                        constitution=constitution, constitution_commit=const_commit,
                        task=task,
                        escalation_lock=bool(cycle.get("blocked_by_escalation")),
                        offline=args.offline,
                        allow_custom_endpoint=_allow_custom(args),
                        retention=args.retention,
                        on_event=getattr(args, "on_step", None))

    # Ledger write, in the only order that can be honest: report first, then a
    # receipt that binds the report's commit.
    base = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ledger, attempt = base, 2
    while ledger.exists():
        ledger = Path(f"{base}.{attempt}")
        attempt += 1
    ledger.mkdir(parents=True)
    report_path = ledger / "report.md"
    report_path.write_text(outcome.report, encoding="utf-8", newline="\n")
    (ledger / "checks.json").write_text(json.dumps(outcome.dcl, indent=2),
                                          encoding="utf-8", newline="\n")

    report_commit = ""
    if args.write_ledger:
        git("add", "--", report_path.relative_to(cfg.root).as_posix(), cwd=cfg.root)
        git("commit", "-q", "-m", f"audit report {sha[:12]} r{cycle['round']}", cwd=cfg.root)
        report_commit = git("rev-parse", "HEAD", cwd=cfg.root)

    manifest = {path: __import__("hashlib").sha256(data).hexdigest()
                for path, data in files.items()}
    if task:
        manifest["TASK.md"] = __import__("hashlib").sha256(
            task.encode("utf-8")).hexdigest()
    receipt = build_receipt(
        cfg=cfg, subject={"sha": sha, "tree": tree, "scope": scope_text},
        cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
        constitution_bytes=constitution_bytes, constitution_commit=const_commit,
        dcl_source_sha256=dcl_source_digest(), prompt_sha256=outcome.prompt_sha256,
        checks=cfg.checks, skills=_skills_manifest(cfg, sha),
        verdict=outcome.verdict, exchange=outcome.exchange,
        retention=args.retention, report_bytes=report_path.read_bytes(),
        report_commit=report_commit, cycle_path=ledger.relative_to(cfg.root).as_posix(),
        audit_repo=cfg.audit_repo or "local", mode=args.mode,
        integrity=outcome.integrity)
    (ledger / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True),
                                           encoding="utf-8", newline="\n")
    # A1: sign the receipt additively (detached sidecar; the receipt bytes are
    # untouched, so unsigned receipts still verify). Fail-open.
    signed_keyid = sign_receipt(cfg, receipt, ledger)
    repro_written = _write_reproduction(receipt, ledger)  # A2 sidecar (fail-open)
    sources_written = _write_sources(cfg, receipt, ledger)  # A4 sidecar (fail-open)

    # Second phase of the ordering rule: the report was committed first so the
    # receipt could bind its commit; now the receipt itself joins the ledger. A
    # receipt can never contain the hash of the commit that carries it, which is
    # why this is two commits rather than one.
    if args.write_ledger:
        rel = ledger.relative_to(cfg.root)
        git("add", "--", str(rel / "receipt.json"), str(rel / "checks.json"), cwd=cfg.root)
        if signed_keyid:
            git("add", "--", str(rel / "receipt.dsse.json"), cwd=cfg.root, check=False)
        if repro_written:
            git("add", "--", str(rel / "reproduction.json"), cwd=cfg.root, check=False)
        if sources_written:
            git("add", "--", str(rel / "sources.json"), cwd=cfg.root, check=False)
        git("commit", "-q", "-m",
            f"audit receipt {sha[:12]} r{cycle['round']} ({outcome.verdict})", cwd=cfg.root)

    status = store.record_verdict(cycle["cycle_id"], sha, outcome.verdict,
                                  receipt_digest(receipt), cfg.max_rounds,
                                  escalation_reason=_provider_stop_reason(outcome),
                                  escalation_kind=_provider_stop_kind(outcome),
                                  constitution_commit=const_commit)
    result = {"verdict": outcome.verdict, "cycle_status": status,
              "cycle_id": cycle["cycle_id"], "round": cycle["round"],
              "integrity": outcome.integrity, "receipt": str(ledger / "receipt.json"),
              "report": str(report_path),
              "invalid_reason": outcome.invalid_reason}
    human = (f"{outcome.verdict}  (cycle {cycle['cycle_id']} round {cycle['round']}"
             f" -> {status})\n  report:  {report_path}\n  receipt: {ledger}/receipt.json")
    if outcome.invalid_reason:
        human += f"\n  audit rejected: {outcome.invalid_reason}"
    _emit(result, args.json, human)
    # The cycle's status outranks the round's verdict: a BLOCKED round that
    # exhausted the budget has escalated, and a caller scripting the loop needs
    # to hear that rather than plan another revision.
    if status == "ESCALATED":
        return EXIT_ESCALATED
    return {"PASS": EXIT_OK, "BLOCKED": EXIT_BLOCKED}.get(outcome.verdict, EXIT_ESCALATED)


# ----------------------------------------------------------------- verify
def cmd_verify(args: argparse.Namespace) -> int:
    cfg = load()
    path = Path(args.receipt).resolve()
    receipt = load_receipt(path)
    evidence = verify_receipt(
        receipt, science_root=Path(args.science_root or cfg.root).resolve(),
        audit_root=Path(args.audit_root or cfg.root).resolve(),
        expect_repo=args.expect_repo or cfg.science_repo,
        expect_sha=args.expect_sha or receipt["subject"]["sha"], cfg=cfg)
    digest = evidence["receipt_digest"]
    state = _state(cfg).snapshot()
    cycle = state.get("cycles", {}).get(evidence["cycle_id"])
    recorded = any(
        event.get("event") == "verdict"
        and event.get("cycle") == evidence["cycle_id"]
        and event.get("receipt") == digest[:16]
        for event in state.get("history", []))
    latest = bool(cycle and cycle.get("parent_receipt") == digest)
    ready = bool(evidence["admission_ready"] and recorded and latest
                 and cycle and cycle.get("status") == "PASSED")
    # A1: report the detached signature, if any, as its own independent fact.
    from ..receipt.sign import verify_receipt as verify_receipt_sig
    pin = None
    if getattr(args, "pubkey", None):
        import base64 as _b64
        pem = Path(args.pubkey).read_text(encoding="utf-8")
        body = "".join(line for line in pem.splitlines()
                       if line and not line.startswith("-----"))
        raw = _b64.b64decode(body)
        pin = raw[-32:] if len(raw) >= 32 else raw   # last 32 bytes of SPKI = the key
    sig = verify_receipt_sig(receipt, path.parent, expected_pubkey=pin)
    # A present-but-invalid signature is a hard failure: the record was altered.
    if sig["signed"] and not sig["verified"]:
        ready = False
    out = {"verified": True, **evidence, "recorded": recorded,
           "latest_recorded_receipt": latest, "admission_ready": ready,
           "admitted": False, "signed": sig["signed"],
           "signature_verified": sig["verified"],
           "signature_keyid": sig["keyid"], "signature_reason": sig["reason"]}
    if args.admit and sig["signed"] and not sig["verified"]:
        _emit(out, args.json,
              "SIGNATURE INVALID  the receipt or its signature was altered; "
              "refusing to admit")
        return EXIT_DENIED
    if args.admit:
        out.update(admit_receipt(receipt, _state(cfg), evidence, cfg=cfg))
    sig_line = ("\nSIGNED  " + sig["keyid"] + "  verifiable offline with the "
                "project public key" if sig["verified"]
                else "\nSIGNATURE INVALID  " + sig["reason"] if sig["signed"]
                else "\nUNSIGNED  no signature sidecar (pre-A1 or signing off)")
    human = (f"BINDINGS VERIFIED  receipt {digest[:16]} for {evidence['sha'][:12]}"
             + sig_line
             + ("\nRECORDED  controller history contains this exact receipt"
                if recorded else
                "\nUNRECORDED  controller history does not contain this receipt")
             + _derivation_lines(evidence)
             + ("\nADMISSION READY  latest recorded PASS"
                if ready and not args.admit else "")
             + ("\nADMITTED  consumed once; the cycle is closed" if args.admit
                else "\nDRY RUN  nothing consumed"))
    _emit(out, args.json, human)
    return EXIT_OK


def cmd_export_pubkey(args: argparse.Namespace) -> int:
    """Print the project's signing public key so a third party can verify
    receipts offline with openssl / ssh-keygen / cryptography — no key created."""
    from ..crypto import keys as _keys
    cfg = load()
    got = _keys.public_key(cfg)
    if got is None:
        _emit({"signed": False}, args.json,
              "NO SIGNING KEY YET  run an audit first; a key is minted on the "
              "first signed receipt")
        return EXIT_CONFIG
    pub, keyid = got
    pem = _keys.public_key_pem(pub)
    _emit({"key_id": keyid, "public_key_pem": pem}, args.json,
          f"KEY {keyid}\n{pem.rstrip()}")
    return EXIT_OK


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Show what it takes to reproduce a receipt's result: the pinned dependency
    environment, whether the working tree still matches it, and the re-run steps.

    Honest by construction: it reports the pinned locks and any drift, and hands
    back a concrete recipe. It does not claim the research result is bit-for-bit
    reproducible — that depends on the audited project's own determinism.
    """
    cfg = load()
    path = Path(args.receipt).resolve()
    receipt = load_receipt(path)
    bundle = _reproduction.build_bundle(receipt)
    recorded = bundle["environment"]["locks"]
    drift = []
    for rel, want in sorted(recorded.items()):
        p = cfg.root / rel
        if not p.is_file():
            state = "missing"
        else:
            state = "match" if _sha256_file(p) == want else "changed"
        drift.append({"path": rel, "state": state})
    env_matches = bool(recorded) and all(d["state"] == "match" for d in drift)
    out = {"cycle_id": receipt["cycle"]["cycle_id"], "commit": bundle["subject"]["commit"],
           "locks": drift, "lock_kinds": bundle["environment"]["kinds"],
           "environment_matches": env_matches, "rerun": bundle["rerun"]}
    if not recorded:
        head = ("NO DEPENDENCY LOCK RECORDED  the audited scope carried no lock "
                "file, so the environment is not pinned by this receipt")
    elif env_matches:
        head = (f"ENVIRONMENT MATCHES  {len(recorded)} lock file(s) "
                f"[{', '.join(bundle['environment']['kinds'])}] are byte-identical "
                f"to the audited commit")
    else:
        changed = ", ".join(f"{d['path']} ({d['state']})" for d in drift
                            if d["state"] != "match")
        head = f"ENVIRONMENT DRIFTED  {changed}"
    recipe = (f"\nTO REPRODUCE\n  1. {bundle['rerun']['checkout']}"
              f"\n  2. {bundle['rerun']['restore']}"
              f"\n  3. {bundle['rerun']['verify']}"
              f"\n\n{bundle['rerun']['note']}")
    _emit(out, args.json, head + recipe)
    return EXIT_OK


# ----------------------------------------------------------------- status
def _run_summary(cfg: Config) -> dict | None:
    """One line of run-journal truth for pure-CLI users.

    A stalled, abandoned or parked run is otherwise visible only in the
    console; `crossaudit status` must not present a blocked run slot as a
    quiet, healthy project.
    """
    from ..runtime import ACTIVE_STATES, RunJournal, RunState, journal_path, pid_alive

    runtime = journal_path(cfg)
    if not runtime.is_file():
        return None
    row = RunJournal(runtime).latest()
    if row is None:
        return None
    state = row["state"]
    note = ""
    if RunState(state) in ACTIVE_STATES:
        owner = int(row.get("owner_pid", 0))
        if owner != os.getpid() and not pid_alive(owner):
            note = f"owner pid {owner} is gone; recovery pending"
        elif any(s.get("kind") == "run_stalled" for s in row.get("steps", [])[-1:]):
            note = "no recent heartbeat"
    elif state == "PROVIDER_UNAVAILABLE":
        waiting = row.get("waiting_reason") or {}
        note = str(waiting.get("detail") or "waiting for a provider")[:80]
    elif state in ("INTERRUPTED", "FAILED"):
        note = str(row.get("error", ""))[:80]
    return {"run_id": row["run_id"], "state": state,
            "outcome": row.get("outcome", ""),
            "task": str(row.get("task", "")).splitlines()[0][:60],
            "note": note}


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load()
    snap = _state(cfg).snapshot()
    cycles = snap.get("cycles", {})
    rows = [{"cycle_id": cid, "status": c["status"], "round": c["round"],
             "active_sha": c["active_sha"][:12], "consumed": len(c.get("consumed", []))}
            for cid, c in sorted(cycles.items())]
    human = ["cycle            status     round  sha           consumed",
             "-" * 60]
    human += [f"{r['cycle_id']:16s} {r['status']:10s} {r['round']:5d}  "
              f"{r['active_sha']}  {r['consumed']}" for r in rows] or ["(no cycles yet)"]
    run = _run_summary(cfg)
    if run is not None:
        human.append(f"run: {run['state']}"
                     + (f" ({run['note']})" if run["note"] else "")
                     + f" — {run['task']!r}")
    _emit({"cycles": rows, "run": run}, args.json, "\n".join(human))
    return EXIT_OK


# ---------------------------------------------------------------- resolve
def cmd_resolve(args: argparse.Namespace) -> int:
    """The human principal rules on an escalated cycle. Interactive only: this
    is a human act and must not be scriptable by the agents themselves."""
    if not sys.stdin.isatty():
        raise ConfigDenial("resolve is a human act; it refuses to run without a terminal")
    cfg = load()
    action = "reopen" if args.reopen else "close"
    c = _state(cfg).resolve_escalation(args.cycle_id, action, args.because)
    if action == "close":
        # The close ruling settles the parked run this escalation references:
        # a stopped task must not keep signalling "needs your decision".
        from ..console import daemon

        daemon.settle_closed_escalation(cfg, c)
    print(f"ruling recorded: {args.cycle_id} {action} — {args.because}")
    print(f"cycle is now {c['status']} (round {c['round']}); "
          + ("run `crossaudit run` to re-audit." if action == "reopen"
             else "the increment stays out of the record."))
    return EXIT_OK


def cmd_skills(args: argparse.Namespace) -> int:
    """Show the house skills, or write a starter one.

    Skills shape how the generator works. They are deliberately not rules: the
    auditor never sees them, so nothing here can move the bar the work is judged
    against — that is what `amend` is for, and why it leaves a dated record.
    """
    from .. import skills as skills_mod

    cfg = load()
    base = cfg.root / skills_mod.SKILLS_DIR
    if args.new:
        base.mkdir(parents=True, exist_ok=True)
        target = base / f"{args.new}.md"
        if target.exists():
            raise ConfigDenial(f"{target} already exists")
        target.write_text(skills_mod.TEMPLATE, encoding="utf-8", newline="\n")
        print(f"wrote {target.relative_to(cfg.root)} — edit it, commit it, and the "
              f"generator follows it from the next round.")
        return EXIT_OK

    house = skills_mod.load(cfg.root)
    if not house:
        print(f"No skills yet. `crossaudit skills --new house-style` writes one.\n"
              f"A skill is guidance on how to work: conventions, the shape of a good\n"
              f"output, worked examples. The standards your work is judged by are the\n"
              f"Constitution instead, because those need a dated record when they move.")
        return EXIT_OK
    rows = [{"name": s.name, "path": s.path, "applies_to": list(s.applies_to),
             "sha256": s.digest} for s in house]
    human = ["house skills (guidance for the generator; the auditor never sees them)",
             "-" * 72]
    for s in house:
        scope = ", ".join(s.applies_to) if s.applies_to else "every round"
        human.append(f"  {s.name:22s} {scope}")
        human.append(f"  {'':22s} {s.path}  {s.digest[:12]}")
    _emit({"skills": rows}, args.json, "\n".join(human))
    return EXIT_OK


def cmd_console(args: argparse.Namespace) -> int:
    """The console, optionally outliving the terminal that started it.

    Default behaviour is to keep running after the window closes and to reattach
    on the next invocation: closing a tab was never meant to end a build, and
    neither should closing a shell.
    """
    import signal

    from ..console import daemon, serve

    cfg = load()

    if args.stop:
        print(daemon.stop(cfg))
        return EXIT_OK

    running = daemon.live(cfg) if args.status or args.stop else daemon.reusable_for_launch(cfg)
    if args.status:
        if running:
            print(f"  console running (pid {running['pid']}) — {daemon.url_for(running)}")
        else:
            print("  no console running here")
        return EXIT_OK

    if running and not args.foreground:
        # Reattach rather than start a rival: two consoles would race on the
        # working tree and on the round budget.
        print(f"\n  A console is already running for this project (pid "
              f"{running['pid']}).\n  {daemon.url_for(running)}\n\n"
              f"  Stop it with `crossaudit console --stop`.", flush=True)
        return EXIT_OK

    if not args.foreground:
        try:
            info = daemon.spawn(cfg, args.port)
        except TimeoutError as exc:
            raise ConfigDenial(str(exc)) from exc
        print(f"\n  CrossAudit console — running in the background (pid "
              f"{info['pid']})\n  {daemon.url_for(info)}\n\n"
              "  It keeps running when you close this window, and a build keeps\n"
              "  going with it. Come back with `crossaudit console` for the URL,\n"
              "  or end it with `crossaudit console --stop`.", flush=True)
        return EXIT_OK

    # Foreground: this is the process the daemon actually runs.
    url, httpd = serve(cfg, port=args.port, register=True,
                       idle_timeout=float("inf") if os.environ.get(
                           "CROSSAUDIT_CONSOLE_CHILD") else 900.0)
    print(f"\n  CrossAudit console — read/write over loopback\n  {url}\n\n"
          "  Loopback only, and the token above is required on every request.\n"
          "  Ctrl-C to stop.", flush=True)

    def bye(*_a) -> None:
        # shutdown() blocks until serve_forever() returns, and serve_forever() is
        # suspended inside this very handler — calling it here deadlocks the
        # process into an orphan that holds the port, answers nothing, and cannot
        # be signalled again. A thread breaks the cycle.
        import threading

        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, bye)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  closed")
    finally:
        # Only once we are actually leaving. Clearing it from the handler removed
        # the one record that could find this process, before it had died.
        daemon.clear_run(cfg)
    return EXIT_OK


def _cmd_pair(args: argparse.Namespace) -> int:
    from .pair import cmd_pair

    return cmd_pair(args)


def _cmd_build(args: argparse.Namespace) -> int:
    from .build import cmd_build

    return cmd_build(args)


# ------------------------------------------------------------------ amend
def cmd_amend(args: argparse.Namespace) -> int:
    """Change the rules by saying what should change. Same path as `talk`'s
    amendment lane, reachable directly when the user already knows the lane."""
    from .talk import lane_amendment
    from ..router import Routing
    from .talk import _record_routing

    cfg = load()
    text = " ".join(args.words).strip()
    if not text:
        raise ConfigDenial('say what should change: crossaudit amend "from now on ..."')
    routing = Routing(utterance=text, lane="amendment", confidence=1.0,
                      reasoning="named explicitly by the user", restated=text)
    executed = lane_amendment(cfg, routing, assume_yes=args.yes)
    _record_routing(cfg, routing, executed)
    return EXIT_OK


# ------------------------------------------------------------------ watch
def cmd_watch(args: argparse.Namespace) -> int:
    from .watch import run_watch

    return run_watch(load())


# ------------------------------------------------------------------- init
def cmd_init(args: argparse.Namespace) -> int:
    _speak(args)
    summary = wizard.run(Path(args.path or "."), mode="github" if args.github else "local",
                         force=args.force,
                         auditor_vendor=getattr(args, "auditor_vendor", None),
                         auditor_model=getattr(args, "auditor_model", None),
                         generator_vendor=getattr(args, "generator_vendor", None),
                         generator_model=getattr(args, "generator_model", None),
                         profile=getattr(args, "profile", "") or "")

    # Finish by opening the console, because the setup ends exactly where the
    # work begins and asking someone to find the next command themselves is a
    # gap for no reason. It is a convenience, not a requirement: a headless
    # machine, a missing browser or --no-console all end with the URL printed
    # instead, and setup is never reported as failed because a browser was not
    # available.
    if not args.no_console:
        summary.update(_open_console(Path(summary["config"]).parent))
    _report_untranslated()
    _emit(summary, args.json)
    return EXIT_OK


def _report_untranslated() -> None:
    """Say out loud that this run was not fully translated.

    The inline `[en]` marks make a gap visible in a screenshot; this line makes
    it countable, and names the keys so the person reporting it does not have to
    describe which sentence looked wrong. Deliberately English and deliberately
    outside the catalogue: it is a defect notice about the catalogue, and a
    notice that can itself go missing is no notice.
    """
    missing = i18n.fallbacks()
    if not missing:
        return
    print(f"\n  [i18n] {len(missing)} string(s) fell back to English in this "
          f"run: {', '.join(missing[:8])}"
          + (" ..." if len(missing) > 8 else ""))


def _open_console(root: Path) -> dict:
    """Start the console for a freshly created project and show it."""
    import subprocess
    import webbrowser

    from ..console import daemon

    try:
        cfg = load(root / CONFIG_NAME)
        info = daemon.reusable_for_launch(cfg) or daemon.spawn(cfg, 0)
    except (Denial, TimeoutError, OSError) as exc:
        # F2: init is a translated flow, and this is its tail. An English
        # remedy after a Chinese setup tells the person something broke.
        print("\n  " + i18n.t("console.failed", reason=str(exc)))
        print("    crossaudit console")
        return {"console": None}

    url = daemon.url_for(info)
    print("\n  " + i18n.t("console.url", url=url))
    opened = False
    try:
        # webbrowser can hand a URL to a text browser or block on a headless
        # box, so it gets its own guard rather than the benefit of the doubt.
        opened = webbrowser.open(url)
    except Exception:                                        # noqa: BLE001
        opened = False
    print("  " + i18n.t("console.opened" if opened
                        else "console.open_yourself"))
    return {"console": url, "console_opened": opened}


# -------------------------------------------------------------------- run
def _step(n: int, total: int, label: str) -> None:
    print(f"  [{n}/{total}] {label:24s}", end="", flush=True)


def _done(msg: str) -> None:
    print(f"ok — {msg}")


def cmd_run(args: argparse.Namespace) -> int:
    """The guided verb: audit the latest commit, narrate every step, decide
    nothing the commit itself cannot decide. `audit` remains the precise tool;
    `run` is the one you can give a colleague with no explanation."""
    try:
        cfg = load()
    except ConfigDenial:
        if sys.stdin.isatty():
            print("Nothing is configured here yet — starting setup.\n")
            wizard.run(Path("."), mode="local", force=False)
            print("\nSetup done. Run `crossaudit run` again to audit your latest commit.")
            return EXIT_OK
        raise

    if not is_repo(cfg.root):
        raise ConfigDenial(f"{cfg.root} is not a git repository; the loop audits commits")

    sha, tree = resolve(cfg.root, args.sha or "HEAD")
    subject = git("log", "-1", "--format=%s", cwd=cfg.root, check=False)

    # The increment is what the commit changed, minus the loop's own artefacts.
    own = {cfg.constitution, "crossaudit.yml", ".gitignore"}
    prefix_own = (cfg.ledger_dir.rstrip("/") + "/", cfg.state_dir.rstrip("/") + "/",
                  ".github/")
    def science_of(s: str) -> list[str]:
        picked = [f for f in changed_paths(cfg.root, s)
                  if f not in own and not f.startswith(prefix_own)]
        if cfg.scope_dirs:
            # The deployment names its science directories (the reference
            # implementation always did: pushes under experiments/ trigger).
            # Tooling and housekeeping commits outside them are not increments
            # and are not forced through the experiment format.
            picked = [f for f in picked
                      if f.split("/", 1)[0] in cfg.scope_dirs]
        return picked

    def enclose(paths: list[str], s: str) -> list[str]:
        """Widen a diff to the increments it touched.

        A revision commit often changes results.json alone, but an increment is
        the whole experiment directory: metadata, summary and data are read
        together, and checks that see only the diff would report the untouched
        files as missing. So the scope is every file under the directories the
        commit touched, taken from the tree, which is also the containment
        property the roadmap asks for at directory granularity.
        """
        dirs = {str(Path(f).parent) for f in paths}
        dirs = {d for d in dirs if d not in (".", "")}
        if not dirs:
            return paths
        widened = {f for _m, f, _b in entries(cfg.root, s)
                   if str(Path(f).parent) in dirs
                   and f not in own and not f.startswith(prefix_own)}
        return sorted(widened | set(paths))

    science = science_of(sha)
    if not science and not args.sha:
        # HEAD is a ledger or config commit (the loop's own bookkeeping moves
        # HEAD in local mode). Walk back to the newest commit that actually
        # changed science, instead of asking the user to think about it.
        for cand in git("log", "--format=%H", "-n", "50", cwd=cfg.root,
                        check=False).splitlines()[1:]:
            found = science_of(cand)
            if found:
                sha, tree = resolve(cfg.root, cand)
                subject = git("log", "-1", "--format=%s", sha, cwd=cfg.root, check=False)
                science = found
                print(f"  (HEAD is ledger bookkeeping; auditing the newest science "
                      f"commit instead: {sha[:12]})")
                break
    if not science:
        raise ConfigDenial(
            f"{sha[:12]} ({subject!r}) changed no science files — only rules, "
            f"configuration or ledger. Commit your experiment, then run again.")

    dirty = git("status", "--porcelain", cwd=cfg.root, check=False)
    from ..providers.registry import NEEDS_KEY
    key_present = bool(os.environ.get(cfg.auditor.key_env, "").strip())
    key_needed = NEEDS_KEY.get(cfg.auditor.provider, True)
    offline = key_needed and not key_present
    if not offline:
        het_ok, het_why = heterogeneity(cfg)
        if not het_ok:
            # Refused before a cycle opens or a request leaves: a same-vendor
            # pair is same-source supervision, the thing this protocol exists
            # to prevent (I1).
            raise ConfigDenial(het_why)

    print("CrossAudit — one increment through the loop")
    print("=" * 60)
    print(f"  commit     {sha[:12]}  {subject!r}")
    touched = len(science)
    science = enclose(science, sha)
    scope_note = (f"{len(science)} file(s) in the touched experiment folder(s)"
                  if len(science) != touched else f"{len(science)} file(s)")
    print(f"  increment  {scope_note}, resolved from the commit")
    const_commit = git("log", "-1", "--format=%H", "--", cfg.constitution,
                       cwd=cfg.root, check=False)
    if not const_commit:
        raise ConfigDenial(f"{cfg.constitution} is not committed; commit it first "
                           f"(an audit must cite the rules' commit)")
    from ..auditor import known_rules
    const_text, const_bytes = _committed_constitution(cfg, const_commit)
    print(f"  rules      {cfg.constitution} @ {const_commit[:12]} "
          f"({len(known_rules(const_text))} rules)")
    print(f"  auditor    {cfg.auditor.provider}:{cfg.auditor.model} "
          f"({'no key needed' if not key_needed else 'key found' if key_present else 'key MISSING -> deterministic checks only'})")
    if dirty:
        print("  note       uncommitted changes exist; the audit reads the COMMIT, "
              "not your working tree")
    print()

    store = _state(cfg)
    continuation = getattr(args, "continue_cycle", None)
    if continuation:
        prior = store.cycle(continuation)
        if prior is None:
            raise ConfigDenial(f"build continuation cycle {continuation} no longer exists")
        if not is_ancestor(cfg.root, prior["active_sha"], sha):
            raise ConfigDenial(
                f"refusing to continue cycle {continuation}: {sha[:12]} does not "
                f"descend from its active commit {prior['active_sha'][:12]}")
        cycle = store.continue_cycle(continuation, cfg.science_repo, sha)
    else:
        cycle = store.open_or_advance(cfg.science_repo, sha, parent(cfg.root, sha),
                                      constitution_commit=const_commit)
    if cycle.get("already_admitted"):
        print("  This commit was already audited, passed, and admitted. Nothing to do.")
        return EXIT_OK
    if cycle.get("blocked_by_escalation"):
        print("  An earlier round ESCALATED: a human decision is pending, and new "
              "commits cannot route around it.")
        print(f"  You are the human here. Rule on it:  crossaudit resolve "
              f"{cycle['cycle_id']} --reopen --because '<why>'")
        return EXIT_ESCALATED
    if not cycle.get("awaiting_verdict") and cycle["active_sha"] == sha:
        print(f"  Already audited (round {cycle['round']}, status {cycle['status']}).")
        # It used to advertise `crossaudit audit --sha <sha>` here as a dispute
        # or second-opinion route. Since a decided commit is refused, that
        # advice pointed at a guaranteed failure. The two routes below are the
        # ones that work, and they are the same two the `audit` refusal names —
        # one sentence for one truth. It does NOT invent a dispute route: there
        # is no such verb, and replacing a false promise with a vaguer one would
        # be the same defect in softer language.
        print("  Commit a revision and run again to continue this cycle, or start "
              "a new increment to be judged under the current rules.")
        print("  Re-running this same commit will not produce a different "
              "decision: a decision already made is not replaced by repeating it.")
        return EXIT_OK

    # Continuations use the standard pinned when their cycle opened. New cycles
    # already carry the current committed standard passed above.
    const_commit = cycle.get("constitution_commit") or const_commit
    const_text, const_bytes = _committed_constitution(cfg, const_commit)

    total = 2 if offline else 3
    _step(1, total, "deterministic checks")
    files, notes = materialise(cfg.root, sha, "", only=science)
    task = _committed_task(cfg, sha)
    outcome = run_audit(cfg=cfg, sha=sha, round_=cycle["round"], files=files, notes=notes,
                        constitution=const_text, constitution_commit=const_commit,
                        task=task,
                        offline=offline,
                        allow_custom_endpoint=_allow_custom(args),
                        retention="sealed")
    hard = outcome.dcl["total_hard_failures"]
    _done("clean" if hard == 0 else f"{hard} hard failure(s)")
    if not offline:
        _step(2, total, "model audit")
        if outcome.invalid_reason:
            _done(f"rejected ({outcome.invalid_reason[:60]})")
        elif outcome.model_reply is None:
            _done("did not run")
        else:
            n = len(outcome.model_reply.get("findings", []))
            b = sum(1 for f in outcome.model_reply["findings"]
                    if f["severity"] == "BLOCKER")
            _done(f"reply valid, {n} finding(s), {b} blocking")

    _step(total, total, "ledger")
    # Append-only with legitimate re-audits: a resumed or human-reopened round
    # re-runs the same round number, so the directory takes the next attempt
    # suffix instead of overwriting anything. The voided attempt stays visible
    # beside its replacement, which is what an append-only ledger means.
    base = cfg.root / cfg.ledger_dir / f"{sha[:12]}-r{cycle['round']}"
    ledger, attempt = base, 2
    while ledger.exists():
        ledger = Path(f"{base}.{attempt}")
        attempt += 1
    ledger.mkdir(parents=True)
    (ledger / "report.md").write_text(outcome.report, encoding="utf-8", newline="\n")
    (ledger / "checks.json").write_text(json.dumps(outcome.dcl, indent=2),
                                          encoding="utf-8", newline="\n")
    rel = ledger.relative_to(cfg.root)
    git("add", "--", str(rel / "report.md"), str(rel / "checks.json"), cwd=cfg.root)
    git("commit", "-q", "-m", f"audit report {sha[:12]} r{cycle['round']}", cwd=cfg.root)
    report_commit = git("rev-parse", "HEAD", cwd=cfg.root)
    manifest = {p_: __import__("hashlib").sha256(b).hexdigest()
                for p_, b in files.items()}
    if task:
        manifest["TASK.md"] = __import__("hashlib").sha256(
            task.encode("utf-8")).hexdigest()
    receipt = build_receipt(
        cfg=cfg, subject={"sha": sha, "tree": tree, "scope": "changed-paths"},
        cycle=cycle, manifest=manifest, constitution_path=cfg.constitution,
        constitution_bytes=const_bytes, constitution_commit=const_commit,
        dcl_source_sha256=dcl_source_digest(), prompt_sha256=outcome.prompt_sha256,
        checks=cfg.checks, skills=_skills_manifest(cfg, sha),
        verdict=outcome.verdict, exchange=outcome.exchange,
        retention="sealed", report_bytes=outcome.report.encode(),
        report_commit=report_commit, cycle_path=str(rel),
        audit_repo=cfg.audit_repo or "local", mode="local",
        integrity=outcome.integrity)
    (ledger / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True),
                                           encoding="utf-8", newline="\n")
    if sign_receipt(cfg, receipt, ledger):
        git("add", "--", str(rel / "receipt.dsse.json"), cwd=cfg.root, check=False)
    if _write_reproduction(receipt, ledger):
        git("add", "--", str(rel / "reproduction.json"), cwd=cfg.root, check=False)
    if _write_sources(cfg, receipt, ledger):
        git("add", "--", str(rel / "sources.json"), cwd=cfg.root, check=False)
    git("add", "--", str(rel / "receipt.json"), cwd=cfg.root)
    git("commit", "-q", "-m",
        f"audit receipt {sha[:12]} r{cycle['round']} ({outcome.verdict})", cwd=cfg.root)
    status = store.record_verdict(cycle["cycle_id"], sha, outcome.verdict,
                                  receipt_digest(receipt), cfg.max_rounds,
                                  escalation_reason=_provider_stop_reason(outcome),
                                  escalation_kind=_provider_stop_kind(outcome),
                                  constitution_commit=const_commit)
    _done("report + receipt committed")

    print()
    print(f"  VERDICT: {outcome.verdict}   (cycle {cycle['cycle_id'][:8]}, "
          f"round {cycle['round']} of {cfg.max_rounds})")
    print()
    if outcome.verdict == "BLOCKED":
        blockers = [f for f in outcome.dcl["findings"] if f["severity"] == "BLOCKER"]
        if outcome.model_reply:
            blockers += [f for f in outcome.model_reply["findings"]
                         if f["severity"] == "BLOCKER"]
        print("  What blocked it:")
        for f in blockers:
            print(f"    - [{f['rule']}] {f['artifact']}: {f['observation'][:100]}")
        print()
        if status == "ESCALATED":
            print("  Round budget exhausted: this increment is now in human hands (I5).")
        else:
            print("  Fix these, commit, and run `crossaudit run` again "
                  f"(round {cycle['round'] + 1} of {cfg.max_rounds}).")
    elif outcome.verdict == "PASS":
        print("  Next: consume the receipt to admit this increment:")
        print(f"    crossaudit verify {rel}/receipt.json --admit")
    elif outcome.verdict == "DCL_ONLY":
        print("  Checks passed, but no model reviewed this (no API key), so it can")
        print("  never be PASS. Add a key (`crossaudit init --force`), then re-run.")
    else:
        print(f"  Escalated: {outcome.invalid_reason or 'a human decision is needed'}")
        print(f"  Report: {rel}/report.md")
    if status == "ESCALATED":
        return EXIT_ESCALATED
    return {"PASS": EXIT_OK, "BLOCKED": EXIT_BLOCKED}.get(outcome.verdict, EXIT_ESCALATED)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crossaudit", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    _mode, _where = running_from()
    p.add_argument("--version", action="version",
                   version=f"crossaudit {__version__} "
                           f"(receipt schema {RECEIPT_SCHEMA}) · {_mode} · {_where}")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    # Registered on the TOP-LEVEL parser as well as on the commands that take
    # it, because `crossaudit --lang zh doctor` is what a person types and it
    # used to be read as a verb: "invalid choice: 'zh'". The per-command flags
    # use SUPPRESS so an absent one cannot overwrite this with its own default —
    # the argparse trap that would silently undo it.
    p.add_argument("--lang", choices=i18n.LANGUAGES, default=None,
                   help=LANG_HELP)
    sub = p.add_subparsers(dest="verb")

    i = sub.add_parser("init", help="guided setup: keys, rules, configuration")
    i.add_argument("path", nargs="?",
                   help="directory to set up; created if it does not exist "
                        "(default: here)")
    i.add_argument("--github", action="store_true", help="also plan the repository pair")
    i.add_argument("--force", action="store_true", help="overwrite an existing config")
    i.add_argument("--profile", choices=("general", "science", "own"),
                   help="pick the constitution starting point without being asked")
    i.add_argument("--no-console", action="store_true",
                   help="do not start or open the console when setup finishes")
    # Wave 1 (D21) translates the init wizard and nothing else, so the flag is
    # offered on `init` and nowhere else. Accepting it globally would let
    # somebody choose Chinese and then meet English at the first thing that goes
    # wrong, which is the half-translated product D21 refuses. LANG and LC_ALL
    # are deliberately NOT consulted: an environment that happens to be Chinese
    # must not opt a person into a partly-translated tool without asking.
    i.add_argument("--lang", choices=i18n.LANGUAGES,
                   default=argparse.SUPPRESS, help=LANG_HELP)
    i.add_argument("--auditor-vendor", choices=tuple(wizard.VENDORS),
                   help="auditor vendor; useful when stdin is not a terminal")
    i.add_argument("--auditor-model",
                   help="exact auditor model id; accepts models newer than this release")
    # Same catalogue the wizard offers, plus "human": a shorter list here would
    # make a vendor scriptable interactively but not from CI.
    i.add_argument("--generator-vendor", choices=(*wizard.VENDORS, "human"),
                   help="generator vendor; must differ from the auditor")
    i.add_argument("--generator-model",
                   help="exact generator model id; accepts models newer than this release")
    i.set_defaults(func=cmd_init)

    r = sub.add_parser("run", help="audit your latest commit; everything else is automatic")
    r.add_argument("--sha", help="a specific commit instead of HEAD")
    r.add_argument("--allow-custom-endpoint", action="store_true",
                   help=argparse.SUPPRESS)
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("doctor", help="preflight; --fix walks you through repairs")
    d.add_argument("--online", action="store_true", help="also probe gh")
    d.add_argument("--fix", action="store_true",
                   help="offer to repair each failure interactively")
    d.add_argument("--all", action="store_true",
                   help="list every check instead of collapsing the passing ones")
    d.add_argument("--lang", choices=i18n.LANGUAGES,
                   default=argparse.SUPPRESS, help=LANG_HELP)
    d.set_defaults(func=cmd_doctor)

    c = sub.add_parser("check", help="run the deterministic layer, no model involved")
    c.add_argument("path", nargs="?", help="directory to check")
    c.add_argument("--sha", help="check a commit's tree instead of the working directory")
    c.add_argument("--scope", help="path prefix within the tree")
    c.set_defaults(func=cmd_check)

    a = sub.add_parser("audit", help="one full cycle: checks, model audit, report, receipt")
    a.add_argument("--sha", help="commit to audit (default HEAD)")
    a.add_argument("--scope", help="path prefix within the tree")
    a.add_argument("--offline", action="store_true",
                   help="deterministic layer only; yields DCL_ONLY, never PASS")
    a.add_argument("--write-ledger", action="store_true",
                   help="commit the report so the receipt can bind its commit")
    a.add_argument("--allow-custom-endpoint", action="store_true",
                   help="permit a non-builtin provider origin (sends your key there)")
    a.add_argument("--retention", choices=("sealed", "redacted", "no-raw"),
                   default="sealed")
    a.add_argument("--mode", choices=("local", "github-pair"), default="local")
    a.set_defaults(func=cmd_audit)

    v = sub.add_parser("verify", help="re-derive every binding; --admit to consume")
    v.add_argument("receipt")
    v.add_argument("--admit", action="store_true", help="consume the receipt, once")
    v.add_argument("--science-root")
    v.add_argument("--audit-root")
    v.add_argument("--expect-repo")
    v.add_argument("--expect-sha")
    v.add_argument("--pubkey", help="a public-key PEM to pin the signature "
                                    "against (third-party offline verification)")
    v.set_defaults(func=cmd_verify)

    ek = sub.add_parser("export-pubkey",
                        help="print this project's signing public key (PEM) so "
                             "others can verify its receipts offline")
    ek.set_defaults(func=cmd_export_pubkey)

    rp = sub.add_parser("reproduce",
                        help="show the pinned environment, drift, and re-run steps "
                             "for a receipt")
    rp.add_argument("receipt")
    rp.set_defaults(func=cmd_reproduce)

    s = sub.add_parser("status", help="where each cycle stands")
    s.set_defaults(func=cmd_status)

    w = sub.add_parser("watch", help="live view: generator, auditor, and their conversation")
    w.set_defaults(func=cmd_watch)

    sk = sub.add_parser("skills", help="house guidance for the generator")
    sk.add_argument("--new", metavar="NAME", help="write a starter skill")
    sk.set_defaults(func=cmd_skills)

    co = sub.add_parser("console", help="the dashboard in a browser; runs in the background")
    co.add_argument("--port", type=int, default=0, help="0 picks a free port")
    co.add_argument("--foreground", action="store_true",
                    help="run here and stop when this window closes")
    co.add_argument("--stop", action="store_true", help="stop the running console")
    co.add_argument("--status", action="store_true", help="is one running?")
    co.set_defaults(func=cmd_console)

    pr = sub.add_parser("pair", help="create the two repositories (plan, then --apply)")
    pr.add_argument("--science", help="owner/name for the work repository")
    pr.add_argument("--audit", help="owner/name for the audit repository")
    pr.add_argument("--public", action="store_true")
    pr.add_argument("--apply", action="store_true", help="actually create them")
    pr.set_defaults(func=_cmd_pair)

    b = sub.add_parser("build", help='say what to build; the loop writes and audits it')
    b.add_argument("words", nargs="*")
    b.add_argument("--verbose", action="store_true",
                   help="also print the run goal payload and other internal state")
    b.description = (b.description or "") + BUILD_ENGLISH_NOTE
    # F2. `build` is NOT offered --lang this wave, deliberately. Its banner and
    # closing copy are translated, but the round-by-round narration is
    # `RunEvent` prose produced by the agent loop, and translating that needs a
    # kind-to-catalogue mapping that is wave 2. Offering --lang here would ship
    # a run that reports what happened in Chinese and what went wrong in
    # English — a switch mid-flow tells a person something broke. Consistently
    # one language until the narration can follow.
    b.set_defaults(func=_cmd_build)

    tk = sub.add_parser("talk", help="say what you want; the program routes it")
    tk.add_argument("words", nargs="+")
    tk.add_argument("--yes", action="store_true", help="skip confirmations")
    tk.set_defaults(func=cmd_talk)

    rt = sub.add_parser("routing", help="every routing decision ever made")
    rt.add_argument("--limit", type=int, default=50)
    rt.set_defaults(func=cmd_routing)

    am = sub.add_parser("amend", help='change the rules: amend "from now on ..."')
    am.add_argument("words", nargs="+")
    am.add_argument("--yes", action="store_true")
    am.set_defaults(func=cmd_amend)

    res = sub.add_parser("resolve", help="rule on an escalated cycle (human only)")
    res.add_argument("cycle_id")
    g = res.add_mutually_exclusive_group(required=True)
    g.add_argument("--reopen", action="store_true", help="return it to the loop")
    g.add_argument("--close", action="store_true", help="end it without admission")
    res.add_argument("--because", required=True, help="the reason; it enters the ledger")
    res.set_defaults(func=cmd_resolve)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Load the credentials file we wrote, if the variables are not already set.
    # Done here rather than at import time: importing this package must stay
    # free of side effects, and only a command actually needs a key.
    wizard.load_keys_into_env()
    if not getattr(args, "verb", None):
        # First-run funnel: pip cannot run a wizard at install time (and must
        # not — constraint 7), so the first bare invocation is the doorway.
        try:
            load()
        except Denial:
            if sys.stdin.isatty():
                print("CrossAudit is installed but this directory is not set up.")
                if input("Set it up now? [Y/n] ").strip().lower() in ("", "y", "yes"):
                    wizard.run(Path("."), mode="local", force=False)
                    print("\nNow: `crossaudit doctor --fix` to finish, then "
                          "`crossaudit run`.")
                    return EXIT_OK
            print(GETTING_STARTED.format(version=__version__))
            _print_origin()
            return EXIT_OK
        print(GETTING_STARTED.format(version=__version__))
        _print_origin()
        return EXIT_OK
    try:
        # F4. Reported once here rather than at each command's return, so a
        # command cannot be added that silently drops the notice — the same
        # reason the action set comes from argparse rather than a list. It goes
        # to stderr and is skipped for --json, because a defect notice printed
        # into a machine surface would be F3 wearing a different hat.
        code = args.func(args)
        if not getattr(args, "json", False):
            _report_untranslated()
        return code
    except Denial as exc:
        if getattr(args, "json", False):
            print(json.dumps(exc.as_dict(), indent=2, sort_keys=True))
        elif getattr(exc, "human", ""):
            # Some refusals are only "not set up yet". DENIED is a permission
            # word and reads as a wall. The machine contract is unchanged: the
            # exit code and --json still carry kind and reason, because scripts
            # depend on them and a human-readable sentence is not a contract.
            print(exc.human, file=sys.stderr)
            _report_untranslated()
        else:
            print(f"DENIED ({exc.kind}): {exc.reason}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\n" + i18n.t("build.interrupted"), file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
