"""A conservative secret scanner — the last gate before a governed commit.

Even after a human approves ``git_commit``, CrossAudit refuses to commit content
that looks like a credential: an accidental key in a diff is exactly the kind of
irreversible mistake a governed agent should not be able to make on the user's
behalf. The scanner is deliberately tuned for *low false positives* — it flags
well-known, high-signal credential shapes (private-key blocks, provider tokens
with fixed prefixes, an assignment of a long opaque value to a secret-named key)
and skips obvious placeholders.

Crucially, it returns only the *kind* of secret it matched, never the secret
value — so a refusal reason can be surfaced and even ledgered without the
credential ever entering a prompt, a log, or the evidence ledger.
"""
from __future__ import annotations

import re

#: (label, compiled pattern). Order is only cosmetic (first match names the kind).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("a private key block",
     re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----")),
    ("an AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("a GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("a Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("a Stripe secret key", re.compile(r"\bsk_live_[0-9A-Za-z]{24,}\b")),
    ("a private OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
]

#: A secret-named field assigned a long opaque value, e.g. api_key = "…".
_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token
        |client[_-]?secret|password|passwd|private[_-]?key)\b
    \s*[:=]\s*
    ['"]?(?P<value>[A-Za-z0-9+/_\-]{20,})['"]?
    """)

#: Values that are clearly placeholders, not real secrets.
_PLACEHOLDER = re.compile(
    r"(?i)(?:example|changeme|placeholder|your[_-]?|xxx+|<[^>]+>|\$\{|dummy|redacted|"
    r"replace[_-]?me|todo|none|null|test[_-]?token|f+0+|0+f+|deadbeef)")


def _value_is_opaque(value: str) -> bool:
    """A real token is long, mixed, and not a placeholder or a single repeated char."""
    if _PLACEHOLDER.search(value):
        return False
    if len(set(value)) < 6:                     # e.g. "aaaaaaaaaaaaaaaaaaaa"
        return False
    has_alpha = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_alpha and has_digit


def scan_text(text: str) -> list[str]:
    """Return the distinct kinds of secret found in ``text`` (labels, never the
    values). An empty list means nothing credential-shaped was detected."""
    if not text:
        return []
    found: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)
    for match in _ASSIGNMENT.finditer(text):
        if _value_is_opaque(match.group("value")):
            label = "a hard-coded credential"
            if label not in found:
                found.append(label)
            break
    return found


#: Filenames that should not be committed at all (real secrets, not templates).
_ENV_FILE = re.compile(r"(?:^|/)\.env(?:\.[A-Za-z0-9]+)?$")
_ENV_TEMPLATE = re.compile(r"\.env\.(?:example|sample|template|dist)$", re.IGNORECASE)


def scan_paths(paths) -> list[str]:
    """Flag committed paths that are themselves credential files (a real .env)."""
    for path in paths or ():
        p = str(path)
        if _ENV_FILE.search(p) and not _ENV_TEMPLATE.search(p):
            return ["an environment file that may contain secrets"]
    return []


def first_finding(text: str, paths=None) -> str:
    """The first secret kind found in the content or paths, or '' if clean."""
    hits = scan_text(text) or scan_paths(paths or [])
    return hits[0] if hits else ""
