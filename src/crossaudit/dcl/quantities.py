"""What a quantity is, and what makes two numbers the same number.

Shared by `builtin.check_provenance` and `numbers.check_number_source` because
they must agree, and the way they stopped agreeing is instructive. The span
widening let `check_provenance` accept `path@revision#L14` on the promise that
`number_source` would open the file and look — but `number_source` recognised
only the exact basename `results.json` where builtin recognised any path ending
in it, and it skipped rows whose `value` was a shape it could not read, on the
belief that `check_units` validated `value`. `check_units` tests the truthiness
of `unit` and `source` and has never looked at `value` at all. Between the two
gaps, a quantity with a null value citing line 999 of a two-line file passed the
complete science profile with no finding, where the code before the widening
blocked it.

So the three things both checks need — which files hold quantities, what the
declared inputs are, and whether a value is a number — live here, once.

**Numbers are compared as canonical decimal strings, never as floats.** Two
integers 2**53 apart round to the same double, so a float comparison would
report a span containing 9007199254740992 as containing 9007199254740993: a
check saying it verified a number literally while accepting a different one.
`Decimal` construction from a string is exact and unbounded, and `format(d, "f")`
is exact, so `1e3` and `1000` canonicalise to the same string without either
one passing through binary floating point.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Mapping

import yaml

RESULTS_SUFFIX = "results.json"

#: A decimal or exponent literal, for validating a TRANSCRIPTION before
#: comparing it. ASCII digits only — `\d` also matches Arabic-Indic and
#: Devanagari digits, which `int()` accepts and which no transcription of a
#: source's bytes would ever mean.
#:
#: The lengths are bounded, and a literal outside the bound is REFUSED rather
#: than truncated. The distinction is the whole finding: capping the exponent
#: inside a scanning pattern let `1e10001` be read as the number `1e1000`
#: followed by the unit `1`, so an annotation of `1e1000`/`1` passed against a
#: span saying 1e10001 — and a contiguous sweep of exponents 10000–10099 gave
#: 100 false passes out of 100. Here the pattern is used with `fullmatch`, so an
#: over-long literal matches nothing, `normalise_number` returns None, and the
#: caller raises CA-NUM-001.
#: The exponent is capped by MAGNITUDE: above 99,999 it is refused, not
#: truncated. The pattern admits the padding a literal may carry and the cap is
#: applied to the significant digits, because a rule that counted characters
#: made `1e000005` malformed and `1e99999` fine — the zeros deciding, not the
#: number. Six digits was the contract saying "bounded" while `1e999999` sailed
#: through; the number a source could actually state is many orders of magnitude
#: below either bound, so the cap only has to be a cap.
_MAX_EXPONENT_DIGITS = 5
_DECIMAL = re.compile(r"[+-]?(?:[0-9]{1,512}(?:\.[0-9]{1,512})?|\.[0-9]{1,512})"
                      r"(?:[eE][+-]?[0-9]{1,512})?")
#: The only comma a transcribed number may carry: thousands grouping, three
#: ASCII digits per group after a leading group of one to three (D169). Any
#: other comma makes the token not a number. Stripping every comma read a
#: decimal comma as grouping, so a transcribed `1,5` equalled `15` and
#: `1,0,0` equalled `100` -- the "wrong number accepted" direction.
_GROUPED = re.compile(r"[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
#: U+2212 MINUS SIGN is what a typesetter, a spreadsheet export and half the
#: scientific literature write for a negative number. It is a minus.
_MINUS = "−"


def results_files(files: Mapping[str, bytes]) -> list[str]:
    """Every path holding structured quantities. One definition, so a file the
    builtin checks read is never a file `number_source` silently ignores."""
    return [p for p in files if p.endswith(RESULTS_SUFFIX)]


def declared_inputs(files: Mapping[str, bytes]) -> list[tuple[str, str]]:
    """Every `(metadata path, inputs entry)` pair, in file order."""
    out: list[tuple[str, str]] = []
    for m in sorted(p for p in files if p.endswith("metadata.yml")):
        try:
            doc = yaml.safe_load(files[m].decode("utf-8")) or {}
        except Exception:                              # reported by check_schema
            continue
        if not isinstance(doc, dict):
            continue
        raw = doc.get("inputs")
        for item in (raw if isinstance(raw, list) else []):
            if isinstance(item, str) and item.strip():
                out.append((m, item.strip()))
    return out


def normalise_number(token) -> str | None:
    """One canonical key for a transcribed number, or None.

    The key is `<significant digits>e<scale>`, so two literals are the same
    number exactly when their keys are equal: `1e3` and `1000` both give
    `1e3`, `0.50` and `.5` both give `5e-1`, and 9007199254740992 and
    9007199254740993 differ. Built from the digits by hand rather than through
    `float` — two integers 2**53 apart round to the same double, so a float
    comparison would report a span containing one as containing the other, a
    check saying it verified a number literally while accepting a different
    one. Not through `Decimal` either: `format(Decimal("1e999999"), "f")` is a
    megabyte of zeros inside the deterministic layer.

    Canonical means: a U+2212 minus folded onto `-`, thousands separators
    dropped (only where they group thousands -- `1,000`, `12,345.67`; a
    decimal comma or any other comma is not a number, D169), exponent notation folded into the scale, a leading `+` dropped,
    leading and trailing insignificant zeros dropped, and a negative zero
    folded onto zero. **Trailing zeros are not significant here:** `1.50` and
    `1.5` are one number, which the check's contract string says out loud
    because it is a real limit — the check cannot tell a reported precision
    from a rounded one.

    None means "this is not a number", and every caller must treat that as a
    finding. There is no looser fallback anywhere: the substring one that used
    to exist ignored the unit entirely.
    """
    text = str(token).strip().replace(_MINUS, "-")
    if "," in text:
        if not _GROUPED.fullmatch(text):
            return None
        text = text.replace(",", "")
    if not _DECIMAL.fullmatch(text):
        return None
    negative = text.startswith("-")
    body = text.lstrip("+-")
    mantissa, _, exponent = body.partition("e") if "e" in body else body.partition("E")
    # The cap is on MAGNITUDE, not on how the magnitude was written. Counting
    # digits made `1e000005` a malformed row while `1e99999` was fine — the
    # padding, not the number, decided it.
    if exponent:
        # The sign is read, not assumed. A single tuple wrote "-" for BOTH `+`
        # and `-` here, so `1e+5` normalised to `1e-5`: ten orders of magnitude
        # apart compared equal, and a citation of one satisfied the other on 100
        # of 100 exponents. `+` is not a sign, it is padding, and it is dropped;
        # only `-` survives into the key.
        sign = "-" if exponent[0] == "-" else ""
        digits = exponent[1:] if exponent[0] in "+-" else exponent
        digits = digits.lstrip("0") or "0"
        if len(digits) > _MAX_EXPONENT_DIGITS:
            return None
        exponent = sign + digits
    whole, _, frac = mantissa.partition(".")
    digits = (whole + frac).lstrip("0")
    if not digits:
        return "0"
    scale = (int(exponent) if exponent else 0) - len(frac)
    stripped = digits.rstrip("0")
    scale += len(digits) - len(stripped)
    return f"{'-' if negative else ''}{stripped}e{scale}"


def is_number_shape(value) -> bool:
    """Whether a `results.json` `value` is a number at all.

    `check_units` never asked this — it tests that `unit` and `source` are
    truthy — so nothing in the layer established it before a span locator was
    allowed to hang off the row. A bool is not a number here: JSON `true` is not
    a measurement, and Python would otherwise call it 1.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        return normalise_number(value) is not None
    return False
