"""Static guard around automatic Generator repair rounds.

After an audit BLOCKS a round, the generator is asked to repair the cause.
This guard reads the repair's staged diff and refuses the kinds of change
that make a finding *disappear* without fixing it: broad exception handling,
silent suppression, new retry/fallback paths, skipped tests, out-of-scope
edits, oversized patches and binaries no local renderer produced.  It does
not claim every flagged construct is wrong; it claims such constructs are
too consequential to enter an audited artifact merely because a model was
asked to clear a finding (D148 slice D).

Three screens, two domains:

- scope and binary screens apply to EVERY changed file;
- the defensive-pattern screen and the line budget apply ONLY to code files
  (`is_code_file`).  Markdown, text, CSV, TeX and other documents are never
  pattern-screened and never budgeted: a report that says "skip the
  introduction" or "provider fallback" is honest prose, and a re-rendered
  document is legitimately large.  A guard that reddens on correct content
  is as much a defect as one that misses defective content (D121).

Pure: the caller passes the unified diff text; nothing here calls git.
"""
from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import asdict, dataclass, field

#: Suffixes whose ADDED lines are screened for defensive patterns and whose
#: added+removed lines count toward the automatic-repair line budget.
CODE_SUFFIXES = frozenset({
    ".py", ".pyi", ".js", ".mjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".go", ".rs", ".java", ".kt",
    ".c", ".h", ".cc", ".cpp", ".rb", ".php", ".cs", ".swift", ".m",
    ".r", ".R", ".jl", ".sql",
    ".yaml", ".yml", ".toml", ".json", ".ini", ".cfg", ".make",
})
#: Extension-less files that are code by name.
CODE_BASENAMES = frozenset({"Makefile", "Dockerfile"})


def is_code_file(path: str) -> bool:
    """Whether ``path`` is a code file for the pattern screen and the budget."""
    name = posixpath.basename(path)
    if name in CODE_BASENAMES:
        return True
    _stem, suffix = posixpath.splitext(name)
    return suffix in CODE_SUFFIXES


#: name -> (pattern over one ADDED line, plain-words description of what the
#: file "adds").  The description completes the sentence "<file> adds ...".
DEFENSIVE_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "broad_exception": (
        re.compile(r"\bexcept\s+(?:Exception|BaseException)\b|\bexcept\s*:"),
        "a catch-all `except` that swallows every error"),
    "silent_pass": (
        re.compile(r"^\s*pass\s*(?:#.*)?$"),
        "a bare `pass` where a failure would otherwise surface"),
    "retry_or_fallback": (
        re.compile(r"(?i)\b(?:retry|retries|fallback|best[_ -]?effort)\b"),
        "a retry or fallback path instead of fixing the cause"),
    "suppression": (
        re.compile(r"(?i)\b(?:suppress|noqa|type:\s*ignore|eslint-disable|noinspection)\b"),
        "a suppression that hides a warning or check"),
    "disabled_assertion": (
        re.compile(r"(?i)\b(?:skip|xfail)\b|\bassert\s+(?:True|1)\b"),
        "a skipped test or a relaxed assertion"),
}


@dataclass(frozen=True)
class RepairAssessment:
    """What the guard saw and why it decided as it did."""

    allowed: bool
    changed_files: tuple[str, ...]
    #: added+removed lines across CODE files (the budgeted quantity).
    changed_lines: int
    #: added+removed lines across document files (informational, unbudgeted).
    document_lines: int
    unsupported_files: tuple[str, ...]
    defensive_patterns: tuple[str, ...]
    binary_files: tuple[str, ...]
    #: One plain sentence each, naming the file and the problem; the material
    #: for the user-facing message.
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class _FileDiff:
    added: list[str] = field(default_factory=list)
    removed: int = 0
    binary: bool = False

    @property
    def lines(self) -> int:
        return len(self.added) + self.removed


_HEADER_PREFIXES = ("--- ", "index ", "@@", "similarity index", "dissimilarity index",
                    "rename from", "rename to", "copy from", "copy to",
                    "new file mode", "deleted file mode", "old mode", "new mode",
                    "\\ No newline")


def parse_unified_diff(unified_diff: str) -> dict[str, _FileDiff]:
    """Per-file added lines, removed-line counts and binary flags, in order.

    Accepts the shape of ``git diff --cached --binary --no-ext-diff``: a
    ``diff --git a/X b/Y`` header names each file (the post-image path), and
    ``+++ b/Y`` confirms it; ``Binary files ... differ`` and ``GIT binary
    patch`` mark a binary.  Paths git quoted are unquoted with shlex.
    """
    files: dict[str, _FileDiff] = {}
    current: _FileDiff | None = None
    for line in unified_diff.splitlines():
        if line.startswith("diff --git "):
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = []
            path = parts[3].removeprefix("b/") if len(parts) == 4 else ""
            current = files.setdefault(path, _FileDiff()) if path else None
            continue
        if line.startswith("+++ "):
            path = line[4:].strip().removeprefix("b/")
            if path and path != "/dev/null":
                current = files.setdefault(path, _FileDiff())
            continue
        if line.startswith(("Binary files ", "GIT binary patch")):
            if current is not None:
                current.binary = True
            continue
        if line.startswith(_HEADER_PREFIXES):
            continue
        if current is None:
            continue
        if line.startswith("+"):
            current.added.append(line[1:])
        elif line.startswith("-"):
            current.removed += 1
    return files


class RepairGuard:
    """Decide whether one automatic repair may be committed."""

    def __init__(self, max_changed_lines: int = 200) -> None:
        if max_changed_lines < 1:
            raise ValueError("max_changed_lines must be positive")
        self.max_changed_lines = max_changed_lines

    def assess(self, unified_diff: str, allowed_files: set[str], *,
               locally_rendered_files: set[str] | None = None) -> RepairAssessment:
        """Screen a staged diff.

        ``allowed_files`` is the set of paths the last audit's findings named;
        every changed path must be in it or in ``locally_rendered_files`` (the
        documents CrossAudit itself rendered from the model's source, which may
        also be binary).
        """
        rendered = set(locally_rendered_files or ())
        files = parse_unified_diff(unified_diff)
        reasons: list[str] = []

        unsupported = sorted(set(files) - set(allowed_files) - rendered)
        for path in unsupported:
            reasons.append(
                f"{path} is outside what the last audit asked to change"
                + (f" (allowed: {', '.join(sorted(allowed_files))})"
                   if allowed_files else ""))

        untrusted_binary = sorted(
            path for path, diff in files.items() if diff.binary and path not in rendered)
        for path in untrusted_binary:
            reasons.append(
                f"{path} is a binary file written directly by the generator, "
                "which cannot be reviewed line by line")

        code_lines = sum(d.lines for p, d in files.items() if is_code_file(p))
        document_lines = sum(d.lines for p, d in files.items() if not is_code_file(p))
        if code_lines > self.max_changed_lines:
            reasons.append(
                f"the code change touches {code_lines} lines, more than the "
                f"{self.max_changed_lines}-line limit for an automatic repair")

        patterns: set[str] = set()
        for path, diff in files.items():
            if not is_code_file(path) or diff.binary:
                continue
            for name, (pattern, what) in DEFENSIVE_PATTERNS.items():
                if any(pattern.search(line) for line in diff.added):
                    patterns.add(name)
                    reasons.append(f"{path} adds {what}")

        if not files:
            reasons.append("the revision changed nothing that could be reviewed")

        return RepairAssessment(
            allowed=not reasons,
            changed_files=tuple(files),
            changed_lines=code_lines,
            document_lines=document_lines,
            unsupported_files=tuple(unsupported),
            defensive_patterns=tuple(sorted(patterns)),
            binary_files=tuple(untrusted_binary),
            reasons=tuple(reasons))
