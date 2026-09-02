"""A heuristic screen over automatic Generator repair rounds.

After an audit BLOCKS a round, the generator is asked to repair the cause.
This module reads the repair's staged diff and sorts what it sees into two
kinds of outcome:

**Refusals** (hard, in every mode) are the two things no automatic round may
do because nothing downstream could review them: change a file outside the
audited directories, or commit a binary that CrossAudit's own document
renderer did not produce.

**Cautions** are *likely* defensive edits — a catch-all ``except``, an
empty error handler, a suppression marker, a skipped test, a relaxed or
deleted assertion, a shell step that ignores its own failure, or a code change
larger than the automatic budget.  Under the default ``repair.mode: caution``
they never stop a round: they are surfaced to the auditor (as deterministic
notes in the next audit's input, so the auditor model can raise a finding)
and shown in the run's events.  Under ``repair.mode: refuse`` they are
refusals.

What this is not (D10, D146): a guarantee.  It is a handful of regular
expressions over the added and removed lines of code files.  It cannot see an
early ``return {}``, a narrowed ``except`` that ``continue``s, or a relaxed
threshold in a data file; the auditor can, and that is why cautions go to the
auditor instead of ending the round.

Three file classes (`classify`):

- **code** — screened for patterns and counted against the line budget;
- **data** (JSON, YAML, TOML, INI, CSV, notebooks) — never pattern-screened,
  never budgeted: a regenerated ``results.json`` is the deliverable, and
  ``retries: 3`` in a config is a value, not a construct;
- **document** (everything else: Markdown, text, TeX, ...) — never
  pattern-screened, never budgeted.  A report that says "skip the
  introduction" is honest prose (D121).

Comments, docstrings and string literals are stripped from a code line before
the construct patterns run; the suppression markers, which live in comments,
are matched on the raw line.  Pure: the caller passes the diff text; nothing
here calls git.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Sequence

#: The two dial positions for cautions (config ``repair.mode``).
MODES = ("caution", "refuse")

CODE_SUFFIXES = frozenset({
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".go", ".rs", ".java", ".kt", ".scala",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".rb", ".php", ".cs", ".swift", ".m",
    ".r", ".R", ".jl", ".sql", ".make", ".mk",
})
CODE_BASENAMES = frozenset({"Makefile", "Dockerfile", "Justfile"})
DATA_SUFFIXES = frozenset({
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".csv", ".tsv", ".ipynb", ".xml", ".parquet", ".npy", ".npz",
})


def classify(path: str) -> str:
    """'code', 'data' or 'document' — which screens apply to ``path``."""
    name = posixpath.basename(path)
    if name in CODE_BASENAMES:
        return "code"
    suffix = posixpath.splitext(name)[1]
    if suffix in CODE_SUFFIXES:
        return "code"
    if suffix in DATA_SUFFIXES:
        return "data"
    return "document"


def is_code_file(path: str) -> bool:
    return classify(path) == "code"


def in_scope(path: str, scope_dirs: Sequence[str] | None) -> bool:
    """Whether ``path`` lies under one of the audited directories.

    No scope directories means the whole tree is audited.
    """
    if not scope_dirs:
        return True
    for raw in scope_dirs:
        d = raw.strip().strip("/")
        if not d or d == ".":
            return True
        if path == d or path.startswith(d + "/"):
            return True
    return False


# ------------------------------------------------------------- the patterns

_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_COMMENT_START = ("#", "//", "/*", "*", '"""', "'''")


def strip_code(line: str) -> str:
    """The construct-bearing part of a code line: no comments, no strings."""
    text = line.strip()
    if not text or text.startswith(_COMMENT_START):
        return ""
    text = _STRING.sub('""', line)
    text = re.split(r"(?<!:)//|#", text, maxsplit=1)[0]
    return text.rstrip()


#: Construct patterns over a stripped ADDED line of a code file:
#: name -> (pattern, what the file "adds", in plain words).
ADDED_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "broad_exception": (
        re.compile(r"\bexcept\s*(?::|\(?\s*(?:[\w.]+\s*,\s*)*(?:Exception|BaseException)\b)"
                   r"|\bcatch\s*\(\s*(?:Throwable|Exception)\b"),
        "a catch-all `except` that swallows every error"),
    "suppress_context": (
        re.compile(r"\bsuppress\s*\("),
        "a `suppress(...)` block that hides errors"),
    "empty_handler": (
        # `except ...: pass` on one line, or `catch (e) {}` in JS; the
        # two-line `except ...:` / `pass` form is matched with context below.
        re.compile(r"\bexcept\b[^:]*:\s*pass\s*$|\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}"),
        "an error handler that does nothing"),
    "relaxed_assertion": (
        re.compile(r"^\s*assert\s+(?:True|1)\b|^\s*assert\b.*\bor\s+True\b"),
        "an assertion that can no longer fail"),
    "disabled_test": (
        re.compile(r"\bmark\.skip\b|\bskipif\(\s*True\b|\bmark\.xfail\b|\bunittest\.skip\b"),
        "a skipped or expected-to-fail test"),
    "shell_ignore_errors": (
        re.compile(r"^\s*set\s+\+e\b|\|\|\s*true\b"),
        "a shell step that ignores its own failure"),
}

#: Marker patterns over the RAW added line (these live in comments/strings).
MARKER_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "lint_suppression": (
        re.compile(r"#\s*noqa\b|#\s*type:\s*ignore\b|pragma:\s*no\s*cover"
                   r"|#\s*pylint:\s*disable|#\s*pyright:\s*ignore|#\s*mypy:\s*ignore"
                   r"|eslint-disable|@ts-ignore|@ts-nocheck"),
        "a marker that silences a checker (`noqa`, `type: ignore`, `pragma: no cover`, ...)"),
    "warning_suppression": (
        re.compile(r"\b(?:filterwarnings|simplefilter)\(\s*['\"]ignore"),
        "a warnings filter set to ignore"),
}

#: Patterns over a REMOVED code line that was not re-added anywhere in the
#: same file: deleting the failing check is the classic evasion.
REMOVED_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "removed_check": (
        re.compile(r"^\s*(?:assert|raise)\b"),
        "removes an `assert` or `raise` without replacing it"),
    "removed_test": (
        re.compile(r"^\s*(?:def\s+test_\w+|func\s+Test\w+|it\(|test\()"),
        "removes a test"),
}

_EXCEPT_HEADER = re.compile(r"^\s*except\b[^:]*:\s*$|\bcatch\s*(?:\([^)]*\))?\s*\{\s*$")
_PASS_ONLY = re.compile(r"^\s*(?:pass|\.\.\.|\})\s*$")


# ------------------------------------------------------------------ parsing

@dataclass
class FileDiff:
    """One file's hunk lines: (kind, text) with kind in '+', '-', ' '."""

    hunk: list[tuple[str, str]] = field(default_factory=list)
    binary: bool = False

    @property
    def added(self) -> list[str]:
        return [t for k, t in self.hunk if k == "+"]

    @property
    def removed(self) -> list[str]:
        return [t for k, t in self.hunk if k == "-"]

    @property
    def lines(self) -> int:
        return sum(1 for k, _ in self.hunk if k != " ")


_HEADER_PREFIXES = ("--- ", "index ", "@@", "similarity index", "dissimilarity index",
                    "rename from", "rename to", "copy from", "copy to",
                    "new file mode", "deleted file mode", "old mode", "new mode",
                    "\\ No newline")


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        try:
            return token[1:-1].encode("latin-1").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return token[1:-1]
    return token


def parse_unified_diff(unified_diff: str) -> dict[str, FileDiff]:
    """Per-file hunk lines and binary flags, in order of appearance.

    Accepts the shape of ``git diff --cached --binary --no-ext-diff``: a
    ``diff --git a/X b/Y`` header names each file (post-image path), ``+++
    b/Y`` confirms it, and ``Binary files ... differ`` / ``GIT binary patch``
    mark a binary.  Git-quoted paths are unquoted.
    """
    files: dict[str, FileDiff] = {}
    current: FileDiff | None = None
    in_hunk = False
    for line in unified_diff.splitlines():
        if line.startswith("diff --git "):
            rest = line[len("diff --git "):]
            path = ""
            m = re.match(r'^(?:"a/(?:\\.|[^"\\])*"|a/\S+)\s+("b/(?:\\.|[^"\\])*"|b/.+)$', rest)
            if m:
                path = _unquote(m.group(1)).removeprefix("b/")
            current = files.setdefault(path, FileDiff()) if path else None
            in_hunk = False
            continue
        if line.startswith("+++ "):
            path = _unquote(line[4:].strip()).removeprefix("b/")
            if path and path != "/dev/null":
                current = files.setdefault(path, FileDiff())
            continue
        if line.startswith(("Binary files ", "GIT binary patch")):
            if current is not None:
                current.binary = True
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if line.startswith(_HEADER_PREFIXES):
            continue
        if current is None or not in_hunk:
            continue
        if line.startswith(("+", "-", " ")):
            current.hunk.append((line[0], line[1:]))
    return files


# ------------------------------------------------------------ the decision

@dataclass(frozen=True)
class RepairAssessment:
    """What the screen saw and how it sorted it."""

    allowed: bool
    mode: str
    changed_files: tuple[str, ...]
    #: added+removed lines over CODE files (the budgeted quantity).
    changed_lines: int
    #: added+removed lines over data and document files (never budgeted).
    document_lines: int
    unsupported_files: tuple[str, ...]
    binary_files: tuple[str, ...]
    #: pattern names that fired (added, marker and removed screens).
    patterns: tuple[str, ...]
    #: unscreened staged files (beyond the caller's size cap).
    unscreened_files: tuple[str, ...]
    #: hard stops: one plain sentence each, naming the file.
    refusals: tuple[str, ...]
    #: likely defensive edits for the auditor to weigh (empty in refuse mode,
    #: where they have become refusals).
    cautions: tuple[str, ...]

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.refusals + self.cautions

    def as_dict(self) -> dict:
        return asdict(self)


def _squash(text: str) -> str:
    return "".join(text.split())


def screen_code_file(path: str, diff: FileDiff) -> list[tuple[str, str]]:
    """(pattern name, sentence) for every construct the file's change shows."""
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()

    def hit(name: str, sentence: str) -> None:
        if name not in seen:
            seen.add(name)
            hits.append((name, sentence))

    previous = ""
    for kind, text in diff.hunk:
        stripped = strip_code(text)
        if kind == "+":
            for name, (pattern, what) in ADDED_PATTERNS.items():
                if stripped and pattern.search(stripped):
                    hit(name, f"{path} adds {what}")
            for name, (pattern, what) in MARKER_PATTERNS.items():
                if pattern.search(text):
                    hit(name, f"{path} adds {what}")
            if stripped and _PASS_ONLY.match(stripped) and _EXCEPT_HEADER.search(previous):
                hit("empty_handler", f"{path} adds {ADDED_PATTERNS['empty_handler'][1]}")
        if stripped and kind != "-":       # the post-image is what runs
            previous = stripped
    added_squashed = {_squash(strip_code(t)) for t in diff.added}
    for text in diff.removed:
        stripped = strip_code(text)
        if not stripped or _squash(stripped) in added_squashed:
            continue
        for name, (pattern, what) in REMOVED_PATTERNS.items():
            if pattern.search(stripped):
                hit(name, f"{path} {what}")
    return hits


class RepairGuard:
    """Sort one automatic repair's staged diff into refusals and cautions."""

    def __init__(self, max_changed_lines: int = 200, mode: str = "caution") -> None:
        if max_changed_lines < 1:
            raise ValueError("max_changed_lines must be positive")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.max_changed_lines = max_changed_lines
        self.mode = mode

    def assess(self, unified_diff: str, *, scope_dirs: Sequence[str] | None = None,
               staged_files: Iterable[str] | None = None,
               locally_rendered_files: Iterable[str] | None = None,
               truncated: bool = False) -> RepairAssessment:
        """Screen a staged diff.

        ``scope_dirs`` are the audited directories (None: the whole tree).
        ``staged_files`` is git's own list of staged paths; it drives the scope
        screen so a diff cut at the caller's size cap cannot hide a file, and
        with ``truncated=True`` every staged file the diff no longer shows is
        reported as unscreened.  ``locally_rendered_files`` are the documents
        CrossAudit itself rendered from the model's source — the one kind of
        binary a round may commit.
        """
        rendered = set(locally_rendered_files or ())
        staged = list(dict.fromkeys(staged_files or ()))
        files = parse_unified_diff(unified_diff)
        known = list(dict.fromkeys([*files, *staged]))
        refusals: list[str] = []
        cautions: list[str] = []

        unsupported = sorted(p for p in known if not in_scope(p, scope_dirs))
        dirs = ", ".join(d.strip().strip("/") for d in (scope_dirs or ()))
        for path in unsupported:
            refusals.append(
                f"{path} is outside the audited directories ({dirs}); only files "
                "inside them may change — if the fix needs another file, say so in `notes`")

        untrusted_binary = sorted(
            p for p, d in files.items() if d.binary and p not in rendered)
        for path in untrusted_binary:
            refusals.append(
                f"{path} is a binary file written directly by the generator, "
                "which cannot be reviewed line by line")

        code_lines = sum(d.lines for p, d in files.items() if classify(p) == "code")
        other_lines = sum(d.lines for p, d in files.items() if classify(p) != "code")
        if code_lines > self.max_changed_lines:
            cautions.append(
                f"the code change touches {code_lines} lines, more than the "
                f"{self.max_changed_lines}-line limit for an automatic repair")

        patterns: list[str] = []
        for path, diff in files.items():
            if classify(path) != "code" or diff.binary:
                continue
            for name, sentence in screen_code_file(path, diff):
                patterns.append(name)
                cautions.append(sentence)

        unscreened = sorted(set(staged) - set(files)) if truncated else []
        if unscreened:
            cautions.append(
                f"{len(unscreened)} staged file(s) lay beyond the review size limit "
                f"and were not screened: {', '.join(unscreened)}")

        if not known:
            refusals.append("the revision changed nothing that could be reviewed")

        if self.mode == "refuse":
            refusals, cautions = refusals + cautions, []
        return RepairAssessment(
            allowed=not refusals,
            mode=self.mode,
            changed_files=tuple(known),
            changed_lines=code_lines,
            document_lines=other_lines,
            unsupported_files=tuple(unsupported),
            binary_files=tuple(untrusted_binary),
            patterns=tuple(dict.fromkeys(patterns)),
            unscreened_files=tuple(unscreened),
            refusals=tuple(refusals),
            cautions=tuple(cautions))
