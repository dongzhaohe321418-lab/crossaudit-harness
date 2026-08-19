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


def _elide(path: str, text: str) -> str:
    size = len(text.encode("utf-8"))
    return (f"<large file elided: {size} bytes. Structural outline only — use the "
            f"file_read tool to load the full contents before editing this file.>\n"
            f"--- outline ---\n{outline(path, text)}")


def shape_work(files: dict[str, str],
               total_budget: int = MAX_WORK_BYTES) -> dict[str, str]:
    """Inline small files verbatim; outline what won't fit.

    Two deterministic passes: (1) any file over ``MAX_FILE_BYTES`` is replaced by
    a structural outline; (2) if the working set still exceeds ``total_budget``,
    the largest still-full files are outlined largest-first (path as a stable
    tie-break) until it fits. Every path stays present, and the generator can
    pull any elided file in full with the audited file_read tool — so this
    shrinks context without losing recall, and never touches the auditor, the
    ledger, or the committed bytes. Pure and side-effect free.
    """
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
    # Outline the biggest full files first until the set fits (or none remain).
    for path in sorted(full, key=lambda p: (-full[p], p)):
        if total <= total_budget:
            break
        before = len(shaped[path].encode("utf-8"))
        shaped[path] = _elide(path, files[path])
        total -= before - len(shaped[path].encode("utf-8"))
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
