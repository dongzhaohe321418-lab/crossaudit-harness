"""`crossaudit init` — the guided setup, from an empty directory to a first run.

It creates the project if it does not exist, makes it a git repository if it is
not one, settles who audits and who generates, takes the two keys, and turns a
sentence about the project into the rules it will be judged by. Everything is
shown before it is written, and the only thing here that reaches the network is
the one call that drafts the rules.

Interactive when it can be — arrow keys, framed panels — and completely
non-interactive when it cannot: piped stdin and CI take defaults rather than
hanging on a keypress that will never arrive.

Keys go to a 0600 file outside the repository and are never echoed, never put in
`crossaudit.yml`, and never committed.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import CONFIG_NAME
from ..errors import ConfigDenial, Denial
from ..scaffold import (AUDIT_TREE, CONFIG_TEMPLATE, GENERAL_CHECKS,
                        SCIENCE_CHECKS, SCIENCE_TREE,
                        read, write_tree)
from ..providers.specs import SPECS
from . import tui

DEFAULT_KEYS_FILE = Path.home() / ".crossaudit-keys.env"

_VENDOR_ORDER = ("anthropic", "openai", "google", "deepseek", "zhipu",
                 "moonshot", "minimax", "qwen", "xai", "mistral")
VENDORS = {vendor: (SPECS[vendor].provider, SPECS[vendor].default_model,
                    SPECS[vendor].api_base) for vendor in _VENDOR_ORDER}
VENDORS["other"] = ("openai_compat", "", "")
VENDOR_HINTS = {vendor: item.label for vendor, item in SPECS.items()}
VENDOR_HINTS["other"] = "any explicitly trusted OpenAI-compatible endpoint"

#: Models offered per vendor, most capable first. A list is not a promise that
#: every entry is available on your account — the last option always lets you
#: type an id, because a wizard that only offers what it knew when it shipped
#: goes stale the week after a release.
VENDOR_MODELS = {vendor: list(item.models) for vendor, item in SPECS.items()}
VENDOR_MODELS["other"] = []
TYPE_IT = "__type__"


def choose_model(vendor: str, default: str, *, role: str = "Auditor") -> str:
    """Pick a model from a list, or type one.

    Typing an exact model id from memory is the step people get wrong, and a
    wrong id fails much later with a provider error that says nothing about the
    wizard. Offer the ones we know and keep the escape hatch.
    """
    known = VENDOR_MODELS.get(vendor) or []
    if not known:
        return tui.text("Model id", default, placeholder="exactly as the vendor spells it")
    options = [tui.Option(m, m, hint) for m, hint in known]
    options.append(tui.Option(TYPE_IT, "something else", "type the id yourself"))
    picked = tui.select(f"{role} model:", options, default=0)
    if picked == TYPE_IT:
        return tui.text("Model id", default,
                        placeholder="exactly as the vendor spells it")
    return picked
# Kept for callers and tests that predate the arrow-key flow.
VENDOR_PRESETS = VENDORS


def keys_file() -> Path:
    """Where credentials are stored; overridable so a sandbox leaves no residue."""
    return Path(os.environ.get("CROSSAUDIT_KEYS_FILE", DEFAULT_KEYS_FILE)).expanduser()


def read_keys_file(path: Path | None = None) -> dict[str, str]:
    """Parse the `export NAME="value"` lines we wrote. Nothing else is executed.

    The file is shell-shaped so a person can `source` it, but reading it here
    parses rather than runs: a credentials file is the last thing that should be
    able to execute anything.
    """
    path = path or keys_file()
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            words = shlex.split(line, comments=True, posix=True)
        except ValueError:
            continue
        if len(words) != 2 or words[0] != "export" or "=" not in words[1]:
            continue
        name, _, value = words[1].partition("=")
        if name.startswith("CROSSAUDIT_") and value:
            out[name] = value
    return out


def load_keys_into_env() -> list[str]:
    """Make the keys we wrote available to the process that needs them.

    The wizard writes this file and then hands off — to the console it starts, or
    to the next command. Expecting the person to `source` it in between is a seam
    that produces a 400 from a provider rather than a sentence about setup, and
    it is our file: we wrote it, we know where it is, we can read it.

    An exported variable always wins: someone who set a key deliberately in this
    shell meant that one.
    """
    loaded = []
    for name, value in read_keys_file().items():
        if not os.environ.get(name):
            os.environ[name] = value
            loaded.append(name)
    return loaded


def write_keys(pairs: dict[str, str]) -> Path:
    """Append keys to a 0600 file. Existing values are kept unless replaced."""
    path = keys_file()
    existing = read_keys_file(path)
    existing.update({k: v for k, v in pairs.items() if v})
    body = "# CrossAudit credentials. Never commit this file.\n" + "\n".join(
        f"export {k}={shlex.quote(v)}" for k, v in sorted(existing.items())) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    if os.name != "nt":
        path.chmod(0o600)
    return path


def gh_available() -> tuple[bool, str]:
    if not shutil.which("gh"):
        return False, "gh CLI not installed"
    proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if proc.returncode != 0:
        return False, "gh installed but not authenticated (run: gh auth login)"
    return True, "gh authenticated"


def github_plan(science: str, audit: str) -> list[str]:
    """What pairing would do. Printed for review; `pair --apply` performs it."""
    return [
        f"gh repo create {science} --private",
        f"gh repo create {audit} --private        rules and reports live here",
        f"gh secret set CROSSAUDIT_AUDITOR_KEY --repo {audit}",
        f"gh api repos/{science}/branches/main/protection -X PUT",
        "crossaudit pair --apply                  does all of it, after showing you",
    ]


def prepare(target: Path) -> list[str]:
    """Create the directory and make it a repository. Returns what it did.

    The audit reads commits, so a project that is not a repository cannot be
    audited at all — better to make it one here than to fail later with a
    message about git.
    """
    done: list[str] = []
    if not target.exists():
        target.mkdir(parents=True)
        done.append(f"created {target}")
    if not (target / ".git").is_dir():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(target),
                       check=True)
        done.append("git init — the ledger is git, and an audit reads commits")
    gitignore = target / ".gitignore"
    current = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    local_state = (".crossaudit/", ".crossaudit-home/", ".crossaudit-trash/")
    missing_state = [entry for entry in local_state if entry not in current]
    if missing_state:
        with open(gitignore, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n# CrossAudit's local state. The ledger is committed; this is not.\n"
                     + "\n".join(missing_state) + "\n")
        done.append("ignored CrossAudit local state directories — not the ledger")
    return done


def commit_setup(target: Path, paths: list[str]) -> str:
    """Version only the files setup owns and return the new commit hash.

    An existing repository may already have unrelated changes staged.  A plain
    ``git commit`` would silently sweep those into CrossAudit's setup commit,
    so the pathspec is repeated with ``--only``.  New git users often have no
    author configured yet; in that case install an explicit repository-local
    automation identity.  The local setting matters beyond this one commit:
    later build rounds also commit their work, and must not fail only after the
    user has finished setup.
    """
    owned = sorted(set(paths))
    add = subprocess.run(["git", "add", "--", *owned], cwd=str(target),
                         capture_output=True, text=True)
    if add.returncode != 0:
        raise ConfigDenial(f"could not stage the setup files: {add.stderr.strip()[:200]}")

    name = subprocess.run(["git", "config", "user.name"], cwd=str(target),
                          capture_output=True, text=True).stdout.strip()
    email = subprocess.run(["git", "config", "user.email"], cwd=str(target),
                           capture_output=True, text=True).stdout.strip()
    for key, current, fallback in (
        ("user.name", name, "CrossAudit"),
        ("user.email", email, "crossaudit@local.invalid"),
    ):
        if current:
            continue
        configured = subprocess.run(["git", "config", key, fallback], cwd=str(target),
                                    capture_output=True, text=True)
        if configured.returncode != 0:
            raise ConfigDenial(f"could not configure the local git identity: "
                               f"{configured.stderr.strip()[:200]}")

    changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *owned],
                             cwd=str(target))
    if changed.returncode == 0:
        # Re-running --force with byte-identical answers has nothing to version.
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(target),
                              capture_output=True, text=True).stdout.strip()
    if changed.returncode != 1:
        raise ConfigDenial("could not inspect the staged setup files")

    commit = subprocess.run(
        ["git", "commit", "-q", "--only", "-m",
         "crossaudit: initialize supervised project", "--", *owned],
        cwd=str(target), capture_output=True, text=True)
    if commit.returncode != 0:
        raise ConfigDenial(f"could not commit the setup files: "
                           f"{commit.stderr.strip()[:200]}")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(target),
                          capture_output=True, text=True, check=True).stdout.strip()


#: The starting points a person chooses between, per SPEC 3 §4.2. Each carries
#: its own plain-language consequence lines: the rule criteria are written for an
#: auditor to apply, and reading four of them is not how somebody decides whether
#: a standard is the one they want. The consequences are what the rules mean.
#:
#: "Only what I write myself" is named for what it gives up. "Minimal" or "Empty"
#: would read as a lighter version of the same thing; this says you get nothing
#: until you write it. It is a legitimate choice — the constitution is the
#: STANDARD and the audit is the MECHANISM, so a trivial standard produces an
#: honest audit of a trivial standard, not a weak audit (Ledger D8).
#: The sentence the consequence lines are read under. It is per starting point
#: because one of them gates nothing: "it will check that nothing will be gated"
#: is not a check, and a frame that promises checking over a list describing its
#: ABSENCE is the overclaim shape this slice exists to remove (AGENTS.md §1.5).
GATING_FRAME = "Before CrossAudit accepts any work, it will check that:"

STARTING_POINTS: dict[str, dict] = {
    "general": {
        "label": "General",
        "hint": "any deliverable — prose, documents, code",
        "template": "GENERAL_AUDIT_RULES.md",
        "frame": GATING_FRAME,
        "consequences": [
            "it does what you asked for",
            "it is finished — no TODO or placeholder text left in",
            "nothing it states contradicts the sources you gave it",
        ],
    },
    "science": {
        "label": "Science & data",
        "hint": "numerical results with declared inputs and units",
        "template": "AUDIT_RULES.md",
        "frame": GATING_FRAME,
        "consequences": [
            "every result declares the inputs and code version it came from",
            "every number carries a unit and a traceable source",
            "anything reported as converged actually met its threshold",
            "the prose does not disagree with the data files",
        ],
    },
    "own": {
        "label": "Only what I write myself",
        "hint": "no rules yet; nothing is gated until you add some",
        "template": None,
        "frame": "There are no rules to check yet, so until you write one:",
        "consequences": [
            "nothing will be blocked, whatever the work says",
            "the automatic checks still run, and every result is still recorded",
        ],
    },
}
DEFAULT_STARTING_POINT = "general"

#: The deterministic pack that belongs with each starting point. The CLI used
#: DEFAULT_CHECKS (= SCIENCE_CHECKS), so a prose review was blocked twice over:
#: 7 BLOCKER rules about metadata.yml AND four checks demanding the same files.
#: app.py and console/projects.py already choose per project type; this makes the
#: CLI agree with them and with dcl/profiles.py, which calls "general" the
#: default. A sweep confirmed DEFAULT_CHECKS had no consumer outside this module.
#: What each science-pack check mechanically verifies, in the words a rule that
#: needed it would use. A term counts as GROUNDS only where it appears in the
#: DRAFTED RULES — the model's structured statement about this project — never
#: in the raw description. A person can mention units in passing while writing a
#: prose review; a rule that says every quantity carries a unit is a commitment,
#: and only a commitment justifies turning a machine check on.
SCIENCE_GROUNDS: dict[str, tuple[str, ...]] = {
    "schema": ("metadata.yml", "results.json"),
    "units": ("unit", "units"),
    "convergence": ("converge", "convergence", "threshold"),
    "provenance": ("provenance", "code_version", "input file", "inputs", "revision"),
}

#: How many of the four must be grounded before the pack is proposed at all.
#: One incidental match is not a shape, and proposing on one would make the
#: proposal noise that people learn to dismiss without reading — which is worse
#: than not proposing, because the next one is real.
SCIENCE_GROUNDS_REQUIRED = 2


@dataclass(frozen=True)
class CheckPackProposal:
    """A proposed deterministic pack and the person's own reasons for it."""

    key: str
    checks: tuple[str, ...]
    instead_of: tuple[str, ...]
    #: One entry per GROUNDING RULE, not per check: a single rule can justify
    #: two checks ("each entry in results.json has a unit" grounds both schema
    #: and units), and printing it twice reads as a bug and tells nobody
    #: anything. (rule id, title, the person's own words or "", checks grounded)
    grounds: tuple[tuple[str, str, str, tuple[str, ...]], ...]


def infer_check_pack(drafted, chosen: str) -> CheckPackProposal | None:
    """Propose the science pack when the drafted rules already ask for it.

    SPEC 3 §3.5. The walkthrough's harm was a laboratory contract arriving
    unasked and surfacing later as a BLOCKER about `metadata.yml` — the moment
    the audit stopped reading as a second opinion and started reading as
    obstruction. Batch 2 fixed that by always defaulting to general, which is
    correct for a prose review and silently wrong for real science: the rules
    get drafted from the person's description, and the machine checks that would
    verify those very rules never run.

    So the inference is made, but as a PROPOSAL WITH ITS GROUNDS rather than a
    choice taken on the person's behalf. It returns None unless the draft itself
    supplies the reasons, and the reasons it returns are quotable back to the
    person: a rule they can read, and where the drafting model attributed it,
    the fragment of their own sentence it came from.

    Nothing here changes the constitution — that is already drafted from what
    they said. What is proposed is the deterministic `checks:` list, which is
    the half batch 2 left welded to a starting point nobody revisits.
    """
    if drafted is None or chosen != DEFAULT_STARTING_POINT:
        # An explicit choice — including `--profile` — is not ours to revisit.
        return None
    proposed = STARTING_CHECKS["science"]
    claimed: set[str] = set()
    by_rule: list[tuple[str, str, str, list[str]]] = []
    for rule in drafted.rules:
        text = f"{rule.title} {rule.criterion}".lower()
        grounds_here = [check for check in proposed
                        if check not in claimed
                        and any(term in text
                                for term in SCIENCE_GROUNDS.get(check, ()))]
        if not grounds_here:
            continue
        claimed.update(grounds_here)
        by_rule.append((rule.id, rule.title.strip().rstrip("."),
                        str(getattr(rule, "from_user", "")).strip(), grounds_here))
    if len(claimed) < SCIENCE_GROUNDS_REQUIRED:
        return None
    return CheckPackProposal(
        key="science",
        checks=tuple(proposed),
        instead_of=tuple(STARTING_CHECKS[DEFAULT_STARTING_POINT]),
        grounds=tuple((rid, title, said, tuple(checks))
                      for rid, title, said, checks in by_rule))


STARTING_CHECKS: dict[str, list[str]] = {
    "general": GENERAL_CHECKS,
    "science": SCIENCE_CHECKS,
    "own": GENERAL_CHECKS,
}


def _substitute_project(text: str, project: str) -> str:
    """No placeholder token survives into a committed file.

    `draft.render()` already did this; the template path did not, which is how a
    live `# Constitution — <PROJECT>` reached a person's repository.
    """
    return text.replace("<PROJECT>", project)


def _empty_constitution(project: str) -> str:
    """A constitution with no rules yet, and honest about what that means."""
    return _substitute_project(
        "# Constitution — <PROJECT>\n\n"
        "Version this file in git. Every audit cites the commit that carried it.\n"
        "Rule changes take effect only between cycles, so work is never judged\n"
        "against a target that moved underneath it.\n\n"
        "No rules yet. Nothing is gated until you add one. Add a rule with a\n"
        "`### CA-AREA-NNN` heading, a **BLOCKER.** or **ADVISORY.** marker, and a\n"
        "criterion someone else could check by reading the work.\n", project)


def _show_and_agree(*, target: Path, const_path: Path, const_name: str,
                    drafted, chosen: str, description: str) -> tuple[str, str]:
    """The constitution moment: show what will be required, then ask.

    Runs on EVERY path, including the keyless one. Previously the drafted path
    showed its rules and asked, and the fallback path wrote and committed a
    document the person never saw — while the screen one step earlier promised it
    would be "shown to you, and committed only if you agree" (Ledger D6).

    Returns (markdown, starting_point_key).

    Accessibility note: this is a terminal, so there is no aria-live to add. The
    equivalent obligation is that every line reads correctly in linear order and
    that nothing needed to operate the moment is carried only by colour, position
    or box drawing. `tui.select` numbers its options and accepts the number as
    input (Ledger D17), so a screen reader gets the options, their names and
    their consequences as text and can choose without tracking a marker; the
    green `❯` and the bold weight are redundant emphasis on top of that number.
    The chosen option is then said in words when the menu closes rather than
    left implied by a glyph.
    """
    while True:
        point = STARTING_POINTS[chosen]
        if drafted is not None:
            attributed = [r for r in drafted.rules if getattr(r, "from_user", "")]
            frame = GATING_FRAME
            header = (f"Rules drafted from what you said · {len(drafted.rules)} rules"
                      + (f", {len(attributed)} from your description"
                         if attributed else ""))
            consequences = [r.title.strip().rstrip(".").lower()
                            for r in drafted.rules if r.severity == "BLOCKER"][:4]
            body = _substitute_project(drafted.render(target.name), target.name)
        else:
            # The word "drafted" may appear only when a draft happened.
            header = f"A starting point — not drafted from your description · {point['label']}"
            frame = point["frame"]
            consequences = point["consequences"]
            body = (_empty_constitution(target.name) if point["template"] is None
                    else _substitute_project(read(point["template"]), target.name))

        tui.note(frame)
        for line in consequences:
            print(f"      · {line}")
        print()
        tui.note(header)

        options = [
            tui.Option("use", "Use these rules", "writes and commits them"),
            tui.Option("switch", "Use a different starting point",
                       "general, science & data, or only what you write"),
            tui.Option("edit", "Edit them first", "opens the file in your editor"),
            tui.Option("show", "Show the full rules", "every rule, in full"),
        ]
        # Said BEFORE the choice, not after it. This is the sentence that makes
        # editing safe to offer freely (Ledger D8) — it is true because every
        # audit cites the constitution commit and rule changes take effect only
        # between cycles. Read after the person has already chosen, it is a
        # reassurance about a decision they have made; read before, it is the
        # fact they need in order to make it.
        tui.note("You can change these at any time. Changing the rules never "
                 "changes a decision already made.")
        picked = tui.select("These rules:", options, default=0)

        if picked == "show":
            tui.panel(f"{const_name} — in full", body.splitlines())
            continue
        if picked == "switch":
            chosen = tui.select("Starting point:", [
                tui.Option(key, item["label"], item["hint"])
                for key, item in STARTING_POINTS.items()],
                default=list(STARTING_POINTS).index(chosen))
            drafted = None          # an explicit choice replaces the draft
            continue
        if picked == "edit":
            const_path.write_text(body, encoding="utf-8", newline="\n")
            _open_in_editor(const_path)
            body = const_path.read_text(encoding="utf-8")
            drafted = None
            tui.ok("edits loaded — showing them again before committing")
            continue
        chosen = _propose_check_pack(drafted, chosen)
        return body, chosen


def _propose_check_pack(drafted, chosen: str) -> str:
    """Show the inference, with its grounds, and let the person refuse it.

    Only ever shown to somebody who can answer. A proposal made into a pipe is
    not a proposal — the default would be taken by silence, and batch 2's rule
    that silence never selects the laboratory contract is exactly what stopped
    the walkthrough's harm. So with no terminal the pack is left alone and this
    returns unchanged, which also keeps every non-interactive path byte-identical.

    "Edit them first" and "Use a different starting point" both drop the draft,
    and after that there is no structured rule set left to read grounds out of —
    so no proposal is made. That is deliberate rather than a gap: the reasons
    have to come from somewhere, and markdown a person has just hand-edited is
    not somewhere we can honestly quote.

    The grounds are quoted rather than summarised. "Because you said X" is only
    printed where the drafting model actually attributed the rule to a fragment
    of the person's sentence; where it did not, the rule itself is the reason and
    the line says so. An invented reason for a real choice is the §1.5 failure
    this whole slice exists to remove.
    """
    proposal = infer_check_pack(drafted, chosen)
    if proposal is None or not tui.interactive():
        return chosen

    tui.note("Your rules ask for things CrossAudit can check mechanically:")
    for rule_id, title, from_user, checks in proposal.grounds:
        said = (f'\n        from what you said: "{from_user}"' if from_user else "")
        print(f"      · {rule_id} {title} → {', '.join(checks)}{said}")
    tui.note(f"So it proposes the {STARTING_POINTS[proposal.key]['label'].lower()} "
             f"automatic checks. They run before any model reads the work, and "
             f"they never change what your rules say.")

    picked = tui.select("Automatic checks:", [
        tui.Option(proposal.key, f"Use the {STARTING_POINTS[proposal.key]['label']} checks",
                   ", ".join(proposal.checks)),
        tui.Option(chosen, f"Keep the {STARTING_POINTS[chosen]['label']} checks",
                   ", ".join(proposal.instead_of)),
    ], default=0)
    if picked != chosen:
        tui.note("You can change these at any time by editing `checks:` in "
                 "crossaudit.yml. Like the rules, a change takes effect only "
                 "between cycles.")
    return picked


def _reason_inside_setup(exc: Denial) -> str:
    """The refusal, with a remedy that is true where it is being read.

    A provider refusal names ``crossaudit init`` as the way to store a key. That
    is right everywhere except inside ``crossaudit init``, which is where this
    one is printed — the person is already in it, and step 3 offered them the
    key a moment ago. Sending them to the command they are running is a dead
    end at the moment they are trying to act.

    The missing-key refusal is recognised by what it CARRIES rather than by
    matching its prose: it names an environment variable and no keys file,
    because no keys file held the key. The other refusal from the same function
    — a key that is in the file but not in this process — carries ``keys_file``
    as well, and its remedy is already correct here, so it passes through
    untouched. So does anything else, which keeps this from quietly rewriting
    refusals it does not understand.
    """
    env = str(exc.detail.get("env", ""))
    if not env or "keys_file" in exc.detail:
        return exc.reason
    return (f"there is no key in ${env} yet — export ${env}, or re-run setup "
            f"with `crossaudit init --force` to store one. The rest of setup "
            f"does not need it")


def _open_in_editor(path: Path) -> None:
    """$EDITOR, or print the path.

    `crossaudit amend` is provider-backed, so it cannot run in the keyless state
    that this moment is most often met in. Offering it there would be offering a
    route that does not exist; plain file editing needs no provider.
    """
    import os
    import subprocess

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor or not tui.interactive():
        tui.note(f"edit it here, then re-run setup: {path}")
        return
    try:
        subprocess.run([*editor.split(), str(path)], check=False)
    except OSError as exc:  # noqa: BLE001 -- an editor that will not start is not fatal
        tui.warn(f"could not start {editor}: {exc}")
        tui.note(f"edit it here instead: {path}")


def _missing_credentials(target: Path, keys_file) -> list[tuple[str, str]]:
    """Which role credentials are absent, as (env var, human role name).

    Read the same way every other command reads them — the environment, plus the
    keys file if `init` just wrote one — so `init` cannot report a state that
    `doctor` will contradict a moment later.
    """
    import os as _os

    from ..config import load as _load

    present = dict(_os.environ)
    if keys_file:
        try:
            for line in Path(keys_file).read_text(encoding="utf-8").splitlines():
                line = line.strip().removeprefix("export ").strip()
                if "=" in line and not line.startswith("#"):
                    name, _sep, value = line.partition("=")
                    present.setdefault(name.strip(), value.strip().strip("\"'"))
        except OSError:
            pass
    try:
        cfg = _load(target / CONFIG_NAME)
    except Exception:  # noqa: BLE001 -- a report must never break setup
        return []
    missing: list[tuple[str, str]] = []
    from ..providers.registry import NEEDS_KEY

    if NEEDS_KEY.get(cfg.auditor.provider, True) and not present.get(
            cfg.auditor.key_env, "").strip():
        missing.append((cfg.auditor.key_env, "auditor"))
    generator_env = cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY"
    if (cfg.generator_vendor or "").lower() != "human" and not present.get(
            generator_env, "").strip():
        missing.append((generator_env, "generator"))
    return missing


def _distil(description: str, provider: str, model: str, base_url: str, *,
            key_env: str = "CROSSAUDIT_AUDITOR_KEY", usage_root: Path | None = None,
            vendor: str = "unknown"):
    """Draft rules on the auditor-side model, before any config file exists."""
    from .. import constitution as const_mod
    from ..providers import get_provider
    from ..usage import record_completion

    fn = get_provider(provider)

    def complete(*, system: str, prompt: str):
        reply = fn(model=model, system=system, prompt=prompt,
                   key_env=key_env, base_url=base_url or None,
                   allow_custom=bool(os.environ.get("CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT")))
        if usage_root is not None:
            record_completion(root=usage_root, state_dir=".crossaudit", role="auditor",
                              phase="setup", vendor=vendor, provider=provider,
                              model=model, reply=reply, system=system, prompt=prompt,
                              base_url=base_url or None)
        return reply

    return const_mod.distil(description, complete=complete)


def run(target: Path, *, mode: str, force: bool = False,
        auditor_vendor: str | None = None, auditor_model: str | None = None,
        generator_vendor: str | None = None,
        generator_model: str | None = None,
        profile: str = "") -> dict:
    """Guided setup. Returns a summary of what was written."""
    requested_generator_model = generator_model
    target = target.resolve()
    cfg_path = target / CONFIG_NAME
    # Flag-driven setup already knows both roles. Refuse an impossible pair
    # before prepare() creates a directory or git repository.
    if auditor_vendor and auditor_vendor not in VENDORS:
        raise ConfigDenial(f"unknown auditor vendor {auditor_vendor!r}")
    if generator_vendor and generator_vendor not in (*VENDORS, "human"):
        raise ConfigDenial(f"unknown generator vendor {generator_vendor!r}")
    if (auditor_vendor and generator_vendor and generator_vendor != "human"
            and auditor_vendor == generator_vendor):
        raise ConfigDenial(
            f"auditor and generator are both {auditor_vendor!r}: that is "
            f"same-source supervision, which the protocol refuses")
    if cfg_path.exists() and not force:
        raise ConfigDenial(f"{cfg_path} already exists; refusing to overwrite "
                           f"(pass --force if you mean it)")

    tui.banner("CrossAudit — setting up a supervised project",
               "Two models from different vendors, one ledger in git. "
               "Four questions, then it runs.")

    gitignore_existed = (target / ".gitignore").exists()
    for line in prepare(target):
        tui.ok(line)

    # ---- 1. the auditor ----------------------------------------------------
    tui.step(1, 4, "Who audits")
    tui.note("The model that reviews everything before it counts as done.")
    auditor_vendor = auditor_vendor or tui.select(
        "Auditor vendor:",
        [tui.Option(v, v, VENDOR_HINTS[v]) for v in VENDORS], default=0)
    if auditor_vendor not in VENDORS:
        raise ConfigDenial(f"unknown auditor vendor {auditor_vendor!r}")
    provider, default_model, _url = VENDORS[auditor_vendor]
    model = auditor_model or choose_model(auditor_vendor, default_model)
    base_url = ""
    if auditor_vendor == "other":
        base_url = tui.text("OpenAI-compatible base URL",
                            placeholder="https://host/v1")
        provider = "openai_compat"

    # ---- 2. the generator --------------------------------------------------
    tui.step(2, 4, "Who generates")
    tui.note("The model that writes each build round. Its vendor is also recorded "
             "so same-source supervision can be refused before either key is used.")
    others = [v for v in VENDORS if v not in (auditor_vendor, "other")]
    generator_vendor = generator_vendor or tui.select(
        "Generator vendor:",
        [tui.Option(v, v, VENDOR_HINTS[v]) for v in others]
        + [tui.Option("human", "human", "you write it yourself")], default=0)
    if generator_vendor == auditor_vendor:
        raise ConfigDenial(
            f"auditor and generator are both {auditor_vendor!r}: that is "
            f"same-source supervision, which is the thing this protocol exists "
            f"to avoid")
    if generator_vendor not in (*others, "human"):
        raise ConfigDenial(f"unknown or unsupported generator vendor "
                           f"{generator_vendor!r}")
    generator_provider = ""
    generator_model = ""
    if generator_vendor != "human":
        generator_provider, generator_default_model, _generator_url = VENDORS[
            generator_vendor]
        generator_model = requested_generator_model or choose_model(
            generator_vendor, generator_default_model, role="Generator")

    # ---- 3. keys -----------------------------------------------------------
    tui.step(3, 4, "API keys")
    tui.note(f"Written to {keys_file()} with mode 600, never placed in the "
             f"repository. Leave blank to export them yourself.")
    tui.note("Hidden by default. After entry, only length and the final four "
             "characters are shown for paste checking. Set CROSSAUDIT_SHOW_KEYS=1 "
             "only when you explicitly want visible input.")
    auditor_key = tui.secret(f"{auditor_vendor} key — the auditor")
    generator_key = ""
    if generator_vendor != "human":
        generator_key = tui.secret(f"{generator_vendor} key — the generator "
                                   f"(leave blank to export it yourself)")
    written = None
    if auditor_key or generator_key:
        written = write_keys({"CROSSAUDIT_AUDITOR_KEY": auditor_key,
                              "CROSSAUDIT_GENERATOR_KEY": generator_key})
        # The keys arrived after main() looked for them, and the console this run
        # is about to start inherits this environment. Load them now, or the very
        # first thing the person types into the console fails on a missing key
        # they just supplied.
        load_keys_into_env()
        tui.ok(f"keys written to {written} (mode 600)")

    # ---- 4. the rules, spoken rather than written --------------------------
    tui.step(4, 4, "What this is, and what would be a mistake")
    # True on EVERY path. "Drafted" was promised before it was known whether a
    # draft could happen, and on the keyless path none does — so the promise was
    # broken by the state, not by the code. What is always true is that the
    # rules are shown and chosen before anything is committed.
    tui.note("Say it in your own words. You will see the rules before anything "
             "is committed, and you choose — you never write markdown.")
    const_name = "AUDIT_RULES.md"
    const_path = target / const_name
    description = tui.text(
        "your project, in a sentence or three",
        placeholder="e.g. a review of the PV industry; every figure must trace "
                    "to a source")

    # An explicit --profile skips the proposal entirely; otherwise the default
    # is general, and silence never selects the laboratory contract.
    starting_point = profile if profile in STARTING_POINTS else DEFAULT_STARTING_POINT
    draft = None
    if description.strip():
        try:
            draft = _distil(description, provider, model or default_model, base_url,
                            usage_root=target, vendor=auditor_vendor or "unknown")
        except Denial as exc:
            # Honest about what did not happen, and it does NOT offer
            # `crossaudit amend` as the remedy: that is provider-backed and
            # cannot run in exactly the state this message appears in. Nor does
            # it offer `crossaudit init`, which is what the person is inside.
            tui.warn(f"could not draft rules from your description: "
                     f"{_reason_inside_setup(exc)}")
            tui.note("Showing a starting point instead — you can edit it here, "
                     "or pick a different one.")

    # Shown and agreed on every path, which is what the step-4 promise said and
    # only the drafted path delivered.
    constitution_text, starting_point = _show_and_agree(
        target=target, const_path=const_path, const_name=const_name,
        drafted=draft, chosen=starting_point, description=description)
    const_path.write_text(constitution_text, encoding="utf-8", newline="\n")
    tui.ok(f"{const_name} written and committed with the rest of setup")

    # ---- configuration and shape -------------------------------------------
    science_repo = tui.text("Project name (owner/name, or a label)", target.name)
    audit_repo = "" if mode == "local" else f"{science_repo}-audit"

    cfg_path.write_text(CONFIG_TEMPLATE.format(
        science_repo=science_repo,
        audit_repo_line=(f"audit_repo: {audit_repo}" if audit_repo
                         else "# audit_repo: (local ledger)"),
        constitution=const_name,
        max_rounds=3,
        auditor_vendor=auditor_vendor,
        auditor_provider=provider,
        auditor_model=model or default_model,
        base_url_line=f"  base_url: {base_url}\n" if base_url else "",
        generator_vendor=generator_vendor,
        generator_details=(
            f"  provider: {generator_provider}\n"
            f"  model: {generator_model}\n"
            f"  key_env: CROSSAUDIT_GENERATOR_KEY"
            if generator_vendor != "human" else
            "  # Human-written changes are committed first, then `crossaudit run`."
        ),
        permissive_minimum="false" if mode == "local" else "true",
        state_dir=".crossaudit",
        scope_dirs="experiments",
        checks=", ".join(STARTING_CHECKS[starting_point]),
    ), encoding="utf-8", newline="\n")
    tui.ok(f"{CONFIG_NAME} written")
    from ..dcl import describe as describe_checks

    contract_name = "DETERMINISTIC_CHECKS.md"
    (target / contract_name).write_text(
        "# Deterministic checks\n\n"
        "This file is generated from the implementations enabled by `checks:` in "
        "`crossaudit.yml`. These machine checks run before model review and are "
        "not changed by `crossaudit amend`. Edit `checks:` between cycles to change "
        "the enabled contract.\n\n```text\n"
        + describe_checks(STARTING_CHECKS[starting_point])
        + "\n```\n", encoding="utf-8", newline="\n")
    owned = [CONFIG_NAME, const_name, contract_name]
    if not gitignore_existed:
        owned.append(".gitignore")
    owned.extend(write_tree(target, SCIENCE_TREE))
    if mode == "local":
        owned.extend(write_tree(target, AUDIT_TREE))

    setup_commit = commit_setup(target, owned)
    tui.ok(f"setup committed — {setup_commit[:12]}")

    # ---- what to do next ---------------------------------------------------
    # `init` and `doctor` must not contradict each other one command apart
    # (Ledger D6, P1). Setup finishing is not the same as the project being able
    # to run, so the banner reports which of the two happened, and a missing
    # credential leads the Next list instead of scrolling above a green box.
    missing = _missing_credentials(target, written)
    if missing:
        tui.banner("Setup written — not ready to run yet", str(target))
    else:
        tui.banner("Ready", str(target))
    rows = []
    if missing:
        # Named first, because it is the thing that stops the very next command.
        for env_name, role in missing:
            rows.append(f"export {env_name}=...")
            rows.append(tui.dim(f"    the {role} has no key yet; "
                                f"`crossaudit build` stops without it"))
        if written:
            rows.append(f"source {written}")
            rows.append(tui.dim("    load the keys you entered into this shell"))
        rows.append("crossaudit doctor")
        rows.append(tui.dim("    re-check once a key is in place; it agrees with this"))
    else:
        if written:
            rows.append(f"source {written}")
            rows.append(tui.dim("    load the keys into this shell"))
        rows += [
            "crossaudit doctor",
            tui.dim("    check everything, offline and read-only"),
            'crossaudit build "…"',
            tui.dim("    say what to build; the loop writes and audits it"),
            "crossaudit console",
            tui.dim("    two windows in a browser, live, and it outlives the window"),
        ]
    tui.panel("Next", rows)

    if mode != "local":
        tui.panel("Two repositories (privilege separation)",
                  github_plan(science_repo, audit_repo or f"{science_repo}-audit"))
        gh_ok, detail = gh_available()
        if not gh_ok:
            tui.warn(f"{detail} — install from https://cli.github.com first")

    return {"config": str(cfg_path), "constitution": str(const_path),
            "keys_file": str(written) if written else None, "mode": mode,
            "setup_commit": setup_commit}
