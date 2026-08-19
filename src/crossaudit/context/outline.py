"""Deterministic, stdlib-only structural outlines for large work files.

When a file is too large to inline in the generator prompt, we send a compact
STRUCTURAL outline instead of its whole body: Python via ``ast`` (exact defs,
classes, imports), Markdown/reST and LaTeX via a heading regex, structured data
(JSON/YAML/TOML/INI) via top-level keys, and a leading-lines fallback for
everything else. The generator is told it can pull the full file with the
audited ``file_read`` tool, so nothing is lost — only deferred. Pure functions:
identical input always yields the identical outline (so a run stays replayable),
and none of this touches the auditor, the ledger, or the committed bytes.
"""
from __future__ import annotations

import ast
import re
from collections import Counter

#: Generic task verbs and function words carry no relevance signal — kept out of
#: the term set so a file merely full of common words cannot outrank a real
#: match. Deliberately excludes domain nouns (review, report, paper, data, …).
_STOPWORDS = frozenset("""
the a an and or nor but for yet so of to in on at by with from into onto upon off
out over under again further then once this that these those it its is are was
were be been being do does did doing done have has had having will would shall
should can could may might must not no nor yes please
add make made write writes writing wrote create creates created creating build
built update updates use uses used using get gets got set sets new all any some
more most also just only very much many few any about above below between during
each other same such your you our their them they what when where which who whom
why how than too if as it is
""".split())

#: Files whose UTF-8 size is at or under this are inlined verbatim (the common
#: case); larger ones are outlined. Generous on purpose — a conservative start,
#: so ordinary documents and code are unaffected and only genuinely large files
#: are summarized structurally.
MAX_FILE_BYTES = 48_000

#: The aggregate budget for the whole working set. Even when every file is
#: individually under MAX_FILE_BYTES, a file-heavy project can sum past a
#: provider window; when the total exceeds this, the largest still-full files
#: are outlined (largest-first, deterministic) until the set fits.
MAX_WORK_BYTES = 400_000

#: Leading lines shown by the fallback outline.
HEAD_LINES = 40

#: An outline itself is capped, so a pathological file (e.g. tens of thousands of
#: one-line defs) cannot produce a huge "outline" that blows the budget it was
#: meant to shrink. Kept well below MAX_FILE_BYTES so an elided form is always
#: strictly smaller than any file large enough to be elided.
MAX_OUTLINE_BYTES = 16_000


def _fit_bytes(text: str, room: int) -> str:
    """Longest prefix of `text` whose UTF-8 encoding is <= `room` bytes."""
    return text.encode("utf-8")[:max(0, room)].decode("utf-8", errors="ignore")


def _elide(path: str, text: str) -> str:
    size = len(text.encode("utf-8"))
    body = outline(path, text)
    if len(body.encode("utf-8")) > MAX_OUTLINE_BYTES:
        body = _fit_bytes(body, MAX_OUTLINE_BYTES) + "\n... (outline truncated)"
    return (f"<large file elided: {size} bytes. Structural outline only — use the "
            f"file_read tool to load the full contents before editing this file.>\n"
            f"--- outline ---\n{body}")


def _terms(task: str) -> list[str]:
    """The distinct, meaningful word tokens of the task, for relevance scoring."""
    return sorted({w for w in re.findall(r"[a-z0-9]{3,}", (task or "").lower())
                   if w not in _STOPWORDS})


def _relevance(path: str, text: str, terms: list[str]) -> int:
    """How strongly a file relates to the task — a whole-word lexical overlap.

    Cheap and deterministic (no embeddings, no native dep): the total WHOLE-WORD
    occurrences of any task term across the path and the file's content. Matching
    whole words (not substrings) stops a file full of words that merely *contain*
    a task-token's letters ("theme" for "the") from scoring, and scanning the
    whole content — not just a head — stops a keyword past an arbitrary cutoff
    from being missed. 0 when the task is empty, so with no task shape_work is
    size-ordered exactly as before.
    """
    if not terms:
        return 0
    counts = Counter(re.findall(r"[a-z0-9]{3,}", (path + "\n" + text).lower()))
    return sum(counts[t] for t in terms)


def _stub(path: str, text: str) -> str:
    return (f"<file not shown this round to keep context within budget: "
            f"{len(text.encode('utf-8'))} bytes. Use the file_read tool to load "
            f"it if it is relevant to the task.>")


def shape_work(files: dict[str, str], task: str = "",
               total_budget: int = MAX_WORK_BYTES) -> dict[str, str]:
    """Inline small files verbatim; outline, then (last resort) stub what won't fit.

    Deterministic passes, each keeping every path present and the full file one
    audited file_read away — so this shrinks context without losing recall, and
    never touches the auditor, the ledger, or the committed bytes:
      1. any file over ``MAX_FILE_BYTES`` is replaced by a bounded outline;
      2. if the set still exceeds ``total_budget``, full files are outlined
         least-relevant-and-biggest first (relevance = lexical overlap with the
         task), skipping any an outline would not shrink;
      3. if it STILL exceeds budget, the least-relevant files are reduced to a
         one-line stub, spending recall on what the task cares about least first.
    The loop always terminates and never grows the set. It drives the total down
    toward the budget but does not guarantee it: the reachable floor is the sum
    of each file's stub, so a project with pathologically many files can settle
    above budget (every path is still present and one file_read away). A pure,
    side-effect-free function; with no task it degrades to size-ordering.
    """
    terms = _terms(task)
    shaped: dict[str, str] = {}
    full: dict[str, int] = {}                 # path -> byte size, for files kept full
    for path, text in files.items():
        size = len(text.encode("utf-8"))
        if size <= MAX_FILE_BYTES:
            shaped[path] = text
            full[path] = size
        else:
            shaped[path] = _elide(path, text)
    total = sum(len(v.encode("utf-8")) for v in shaped.values())
    if total <= total_budget:
        return shaped
    rel = {p: _relevance(p, files[p], terms) for p in files}
    # Pass 2: outline full files, least-relevant then biggest first; skip any
    # where outlining would not shrink it (so `total` only ever decreases).
    for path in sorted(full, key=lambda p: (rel[p], -full[p], p)):
        if total <= total_budget:
            break
        elided = _elide(path, files[path])
        gain = len(shaped[path].encode("utf-8")) - len(elided.encode("utf-8"))
        if gain <= 0:
            continue
        shaped[path] = elided
        total -= gain
    # Pass 3 (hard ceiling): stub the least-relevant files until it fits. A goal-
    # relevant file is only stubbed once every less-relevant one already is.
    for path in sorted(files, key=lambda p: (rel[p], -len(files[p].encode("utf-8")), p)):
        if total <= total_budget:
            break
        stub = _stub(path, files[path])
        gain = len(shaped[path].encode("utf-8")) - len(stub.encode("utf-8"))
        if gain <= 0:
            continue
        shaped[path] = stub
        total -= gain
    return shaped


def outline(path: str, text: str) -> str:
    """A compact structural outline of one file, chosen by extension."""
    lower = path.lower()
    if lower.endswith(".py"):
        got = _python_outline(text)
        if got:
            return got
    elif lower.endswith((".md", ".markdown", ".rst")):
        got = _heading_outline(text, r"^#{1,6}\s+\S")
        if got:
            return got
    elif lower.endswith(".tex"):
        got = _heading_outline(
            text, r"^\\(?:chapter|section|subsection|subsubsection|paragraph)\*?\{")
        if got:
            return got
    elif lower.endswith((".json", ".yml", ".yaml", ".toml", ".ini", ".cfg")):
        got = _key_outline(text)
        if got:
            return got
    return _head_outline(text)


def _python_outline(text: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    lines: list[str] = []
    doc = ast.get_docstring(tree)
    if doc:
        lines.append(f'"""{doc.strip().splitlines()[0]}"""')
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(text, node)
            if seg:
                lines.append(seg.splitlines()[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(f"def {node.name}(...):  # line {node.lineno}")
        elif isinstance(node, ast.ClassDef):
            lines.append(f"class {node.name}:  # line {node.lineno}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines.append(f"    def {sub.name}(...):  # line {sub.lineno}")
    return "\n".join(lines)


def _heading_outline(text: str, pattern: str) -> str:
    rx = re.compile(pattern)
    hits = [ln.rstrip() for ln in text.splitlines() if rx.match(ln)]
    return "\n".join(hits[:400])


def _key_outline(text: str) -> str:
    keys: list[str] = []
    for ln in text.splitlines():
        m = re.match(r'^(?:"([^"]+)"|([\w.\-]+))\s*[:=]', ln)   # indent-0 keys only
        if m:
            keys.append(m.group(1) or m.group(2))
    if not keys:
        return ""
    return "top-level keys: " + ", ".join(keys[:200])


def _head_outline(text: str) -> str:
    lines = text.splitlines()
    head = "\n".join(lines[:HEAD_LINES])
    if len(lines) > HEAD_LINES:
        head += f"\n... ({len(lines) - HEAD_LINES} more lines elided)"
    return head
