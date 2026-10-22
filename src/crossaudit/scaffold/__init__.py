"""Templates `init` instantiates. The Constitution is a template here, never law."""
from __future__ import annotations

import hashlib
from pathlib import Path

TEMPLATES = Path(__file__).parent / "templates"
GENERAL_CHECKS = ["parseable", "declared", "internal", "complete"]
# Kept identical to dcl/profiles.py PROFILES["science"]: a project scaffolded
# as "science" and a project that writes `checks: science` must mean the same
# thing, or the profile name is documentation for a list nobody uses.
# `number_source` left this list with D158 ruling 1 (the generator could not
# address lines it was never shown; 24 of 24 measured drafts blocked) and
# returned with D164 ruling 1, after content addressing and the containment
# extensions brought the shipped check to 4 of 398 wrong blocks on Arm 5 —
# the reason is recorded in `dcl/profiles.py`. It is last on purpose, and a
# science project scaffolded from this list is also handed the skill that
# asks the generator for the annotation (`annotation_skill_tree`), never the
# check alone.
SCIENCE_CHECKS = ["schema", "units", "convergence", "provenance", "number_source"]
# The CLI keeps its established science-first scaffold for compatibility. The
# browser project wizard chooses explicitly between GENERAL_CHECKS and
# SCIENCE_CHECKS instead of silently applying a laboratory contract to prose.
DEFAULT_CHECKS = SCIENCE_CHECKS


#: The generator-side half of the provenance checks, and the reason it is not
#: optional. `number_source` and `source_provenance` both read a block the
#: GENERATOR emits; nothing in `generator.py` or the Constitution asks for one.
#: Turning such a check on with nothing telling the generator to annotate gives
#: a check that passes every document while appearing to guard it — a name that
#: lies (PROVENANCE_CHECKS.md §5.4). So the skill ships beside the check, on the
#: shipped channel and no other: a committed `skills/*.md`, loaded by
#: `skills.load`, rendered into the generator prompt by `skills.render`, hashed
#: into the receipt, and never shown to the auditor.
#: One FILE per check, not one file per project. A single composed file could
#: only be gated as a whole, and its composition is fixed at scaffold time —
#: turn `number_source` off a month later and the number-annotation contract
#: keeps arriving in every generator prompt, describing a fence nothing will
#: ever read. Each file carries `requires_check:` in its front matter and
#: `skills.select` reads it against the project's live `checks:` on every round.
ANNOTATION_SKILLS: dict[str, tuple[str, str]] = {
    "number_source": ("skills/provenance-numbers.md", "PROVENANCE_NUMBERS_SKILL.md"),
    "source_provenance": ("skills/provenance-sources.md", "PROVENANCE_SOURCES_SKILL.md"),
    # The AI4S declaration pack reads two blocks the generator writes into
    # results.json. One file serves both checks — they share a vocabulary
    # (quantity names, literals) — and its front matter names both, so
    # `skills.select` keeps it while EITHER check is on and drops it when
    # neither is. Neither check is in `SCIENCE_CHECKS`, so no scaffolded
    # project receives it unless its own `checks:` names one of them.
    "derivations": ("skills/ai4s-declarations.md", "AI4S_DECLARATIONS_SKILL.md"),
    "claims": ("skills/ai4s-declarations.md", "AI4S_DECLARATIONS_SKILL.md"),
}
ANNOTATION_CHECKS = tuple(ANNOTATION_SKILLS)


#: A generated skill from before the per-check split. It carried both fences and
#: no `requires_check:` key, so it stays selected however the check list moves —
#: including `checks: []`. Nothing shipped with it and there is no migration
#: path, so it is removed where it is found rather than left instructing a
#: generator about checks the project may no longer run.
LEGACY_ANNOTATION_SKILL = "skills/provenance.md"

#: **Ownership is proved by digest, never by a substring.** Matching on "this
#: file mentions the fence name" deleted a hand-written policy whose only crime
#: was quoting ```crossaudit-numbers in an example, and it simultaneously MISSED
#: the source-only rendering, which contains no numeric marker at all. A
#: generated file is one this scaffold generated, and the only honest test of
#: that is the bytes.
#:
#: Every rendering the pre-split composer could emit, over every combination of
#: the two annotation checks (numbers only, sources only, both), computed from
#: the round-3 templates at `da8ddfe` and pinned here. A file whose sha256 is not
#: one of these is somebody's, and is left alone.
LEGACY_ANNOTATION_DIGESTS = frozenset({
    # header + numbers          (checks: science, or ["number_source"])
    "1fda0d9187c1de90f6ad571f450e0a678f7c119ae6b7302e9cb087108eaeafef",
    # header + sources          (checks: ["source_provenance"])
    "967213437932ca9fc7d62a6f67d8c7332be48d496df0b40c7bb76e2b9ca5fc90",
    # header + numbers + sources (checks: research)
    "36c79202e7a9de020c31303d6821fddd80854ef3cf08a95e116e5efd3d1f2d40",
})


def prune_legacy_annotation_skill(root) -> list[str]:
    """Delete the pre-split generated skill if it is there, byte for byte.

    Returns the paths removed. The caller MUST add them to whatever it stages:
    the first version returned them and both creation paths dropped the value on
    the floor, so `commit_setup` never saw the deletion and the file stayed in
    the tree it had just been removed from.
    """
    if root is None:
        return []
    # THE SAME DIRECTORY IDENTITY THE LOADER ACCEPTS, never a filesystem alias.
    # `Path(root) / "skills/provenance.md"` opens whatever the OS resolves: on a
    # case-insensitive host that is `SKILLS/`, and through `skills ->
    # work/guidance` it is an ordinary work file. Measured on this tree before
    # the fix, pruning deleted `work/guidance/provenance.md` — a file git tracks
    # as work and `house_dir` refuses to read as guidance. `house_dir` resolves
    # the one identity and denies every alias; a malformed directory raises here
    # exactly as it would on the next round's load, rather than being quietly
    # followed.
    from .. import skills as skills_mod

    base = skills_mod.house_dir(Path(root))
    if base is None:
        return []
    target = base / Path(LEGACY_ANNOTATION_SKILL).name
    if not target.is_file() or target.is_symlink():
        return []
    try:
        data = target.read_bytes()
    except OSError:
        return []
    if hashlib.sha256(data).hexdigest() not in LEGACY_ANNOTATION_DIGESTS:
        return []                                  # not ours; do not touch it
    target.unlink()
    return [LEGACY_ANNOTATION_SKILL]


def annotation_skill_tree(checks, root=None) -> dict[str, str]:
    """The house skills a project's checks need, or nothing at all.

    Keyed off the resolved check list rather than the project type, so a project
    that composes its own mix is told exactly what its own checks will read —
    and a `general` project, which enables neither, gets no advice about
    annotating numbers it has no reason to annotate.

    `root`, when given, also clears the pre-split generated skill: a keyless
    `skills/provenance.md` from before this round survives every check gate,
    because the gate it would be read by lives in front matter it does not have.
    Its removal is reported through `prune_legacy_annotation_skill`, which the
    caller must stage; this function only writes.
    """
    return {path: render_skill(template)
            for name, (path, template) in ANNOTATION_SKILLS.items()
            if name in (checks or ())}


#: The line in AI4S_DECLARATIONS_SKILL.md that becomes the derivation method
#: table. Generated from the registry the check itself reads
#: (`crossaudit.dcl.ai4s.method_table`), so the argument names a generator is
#: shown are, by construction, the ones the check accepts: the first
#: live-generator experiment's commonest miss was a guessed argument name.
AI4S_METHOD_TABLE = "{{AI4S_METHOD_TABLE}}"


def render_skill(template: str) -> str:
    """A packaged skill template as it is written into a project."""
    text = read(template)
    if AI4S_METHOD_TABLE in text:
        from ..dcl.ai4s import method_table
        text = text.replace(AI4S_METHOD_TABLE, method_table())
    return text


def read(name: str) -> str:
    path = TEMPLATES / name
    if not path.is_file():
        raise FileNotFoundError(f"packaged template {name!r} is missing")
    return path.read_text(encoding="utf-8")


CONFIG_TEMPLATE = """\
# crossaudit.yml — the one configuration file.
# Credentials are NOT here: each role names the environment variable that
# carries its key, and the value is read at call time.
version: 1

science_repo: {science_repo}
{audit_repo_line}
constitution: {constitution}
max_rounds: {max_rounds}

auditor:
  vendor: {auditor_vendor}
  provider: {auditor_provider}
  model: {auditor_model}
  key_env: CROSSAUDIT_AUDITOR_KEY
{base_url_line}
generator:
  # Declared so I1 (heterogeneity) can be asserted from configuration.
  vendor: {generator_vendor}
{generator_details}

isolation:
  # Refuse to admit a receipt whose isolation evidence is weaker than this.
  # permissive: true means the two roles' credentials were never both reachable
  # by one process — a single machine holding both keys cannot evidence it.
  minimum:
    parametric: true
    contextual: true
    permissive: {permissive_minimum}

state:
  dir: {state_dir}

scope:
  # The generator and the default deterministic check may only read/write here.
  dirs: [{scope_dirs}]

# Machine-enforced contracts are independent of AUDIT_RULES.md. Their exact
# live definitions are shown in DETERMINISTIC_CHECKS.md and to the generator.
checks: [{checks}]

# After a BLOCKED audit the repair is screened (docs/EVIDENCE_AUTHORITY.md).
# Files outside the audited directories and unrendered binaries are refused.
# Likely defensive edits (catch-all except, skipped tests, deleted asserts,
# oversized code changes) are cautions the auditor weighs (mode: caution)
# or refusals that roll the round back (mode: refuse).
repair:
  enabled: true
  mode: caution
  max_changed_lines: 200
"""


# --------------------------------------------------------------- repo shapes
# What each repository looks like the moment it is created, so a science repo
# reads as a lab notebook and an audit repo reads as a ledger, from commit one.

GENERAL_TREE: dict[str, str] = {
    "cycles/README.md": """\
# cycles/ — the audit ledger (append-only)

Written by `crossaudit`, never by hand. Each cycle directory holds the audit
report, deterministic check output, and the receipt that binds them to one
work commit. History is the point: nothing here is ever rewritten.
""",
}

SCIENCE_TREE: dict[str, str] = {
    "experiments/README.md": """\
# experiments/

One directory per increment. An increment is the unit the auditor reads, so it
must stand alone:

    experiments/<date>-<slug>/
    ├── metadata.yml     code_version + declared inputs (what produced this?)
    ├── results.json     quantities, each with unit and source; convergence block
    └── SUMMARY.md       the claim, in prose that must agree with the data

`crossaudit run` audits the latest commit's increment against AUDIT_RULES.md.
The audit trail lands in cycles/ as paired report + receipt commits.

The exact machine-enforced file contract is in `DETERMINISTIC_CHECKS.md`.
Change the `checks:` list in `crossaudit.yml` between cycles to change that
contract; `crossaudit amend` changes the model-audited Constitution only.
""",
    "experiments/TEMPLATE/metadata.yml": """\
# Copy this directory to experiments/<date>-<slug>/ and fill it in.
code_version: <git sha or tag of the code that produced the results>
inputs:
  - <script-or-data-path>@<revision>
""",
    "experiments/TEMPLATE/results.json": """\
{
  "quantities": [
    {"name": "<quantity>", "value": 0.0, "unit": "<unit>",
     "source": "<declared-input>@<revision>"}
  ],
  "convergence": {"converged": true}
}
""",
    "experiments/TEMPLATE/SUMMARY.md": """\
One paragraph: what was computed, and what it shows. The prose here is audited
against results.json — a sign or magnitude that disagrees is a BLOCKER.
""",
    "cycles/README.md": """\
# cycles/ — the audit ledger (append-only)

Written by `crossaudit`, never by hand. Each cycle directory holds the audit
report, the deterministic check output, and the receipt that binds them to one
science commit. History is the point: nothing here is ever rewritten.
""",
}

AUDIT_TREE: dict[str, str] = {
    "README.md": """\
# Audit repository

This repository is a ledger, not a workspace. It holds:

- `AUDIT_RULES.md` — the Constitution: versioned, human-authored rules the
  auditor cites by ID. Changes land only between cycles.
- `cycles/` — one append-only directory per audit cycle: report, deterministic
  check output, receipt.

The generating agent has no write access here; the auditing side has no write
access to the science repository. That mutual unwritability is the point.
""",
    "cycles/README.md": """\
# cycles/ — append-only

`<science-sha>-r<round>/report.md` + `checks.json` + `receipt.json`.
A receipt binds the science commit, every input hash, the Constitution's
commit, and the verifier's own identity. Verify one with:

    crossaudit verify <path>/receipt.json
""",
}


def write_tree(root, tree: "dict[str, str]", *, force: bool = False) -> list[str]:
    """Materialise a repo shape. Existing files are never overwritten."""
    written = []
    for rel, content in tree.items():
        dest = Path(root) / rel
        if dest.exists() and not force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        written.append(rel)
    return written
