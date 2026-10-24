"""The AI4S declaration pack: properties a generator declares and code decides.

`benchmarks/ai4s/DESIGN.md` §4, under D155's surviving rule: **the generator
names evidence; code decides what it says.** Every check here reads a
declaration the increment itself makes — a range in the constitution, a
derivation over a committed file, a split, a claim — and asks a mechanical
question of it. None of them asks a model anything, and none of them judges
whether a method is appropriate, whether a derivation is the *right* one for
the claim, or whether an undeclared quantity should have been declared.

Two rules hold for every check in the module, and they are the whole design:

* **A declaration the generator did not make produces nothing.** These enforce
  declared properties, never coverage. A results file with no `derivations`
  passes `derivations` vacuously; a constitution with no ranges block passes
  `range_rules` vacuously. Whether a quantity *should* have been declared is
  the auditor's tier.
* **A declaration that cannot be verified is not verified.** An unknown method,
  a file that is not in scope, a missing column, a non-numeric cell, a claim
  naming a quantity that does not exist, a malformed block — each is a
  BLOCKER, the same fail-closed shape as CA-NUM-001. Silence over an
  unreadable declaration would make the declaration a way to look checked.

A results.json that does not parse is skipped here, exactly as `check_units`
skips it: `schema` already reports it as CA-META-001, and reporting it again
under every pack check would multiply one defect into eight findings.

**A JSON object that repeats a key is a declaration that cannot be read**
(cross-vendor review round 1, DESIGN §9 Amendment 5). Python's JSON reader
keeps the last of two `"max"` keys silently, so `{"max": 0.05, "max": 1}` would
check the bound nobody meant. The pack reads results.json, the ranges block and
splits.json with an `object_pairs_hook` that marks every repeated key, and a
file that repeats one ANYWHERE is not read: the ranges block and splits.json
block under their own check, and a results.json blocks under each blocking
check that reads it — `numeric_validity` always, `range_rules` when ranges are
declared, `derivations` when it carries `derivations`, `claims` when it carries
`claims` — naming the key and where it sits. The two advisory checks skip it.
The shipped profile's own readers (`schema`, `units`, `number_source`, …) are
outside this pack and keep `json.loads`'s last-wins reading.

**A declared path stays inside the directory of the file that declares it.** A
derivation's `file` and splits.json's `data` are normalised and must resolve
inside the directory holding that results.json / splits.json; `../…`, an
absolute path, or a sibling experiment's committed file blocks, naming the
path. The skill tells the generator paths never climb out; this keeps it.

**The codes, and which failure wears which.**

* CA-NUM-005 (BLOCKER, `numeric_validity`) — a quantity's `value` is not a
  finite number: missing, `null`, a bool, NaN/Infinity (which Python's JSON
  reader accepts), or a string that is not a decimal literal. A numeric string
  such as `"0.125"` IS a number here (`quantities.is_number_shape`), because
  `precision` reads a value as written and a string is how a writer preserves
  trailing zeros.
* CA-PHYS-001 (BLOCKER, `range_rules`) — a quantity matched by a declared range
  has a unit that is not byte-equal to the declared one (no case folding, no
  whitespace stripping, no synonym table: `kJ/mol`, `kJ mol⁻¹` and `kJ/mol `
  are three different units here, unlike in `number_source`), a value outside the
  inclusive bounds, or a value that cannot be compared at all; OR the
  ```crossaudit-ranges block itself is malformed (not JSON, a repeated JSON
  key, not a list of entries with non-empty `name` and `unit`, an entry key
  other than `name`, `unit`, `min`, `max` — `maximum` would drop a bound
  silently —, a non-numeric bound, min > max, an unclosed fence, two fences in
  one file).
* CA-DERIV-001 (BLOCKER, `derivations`) — a declared derivation, recomputed
  from the committed file, disagrees with the reported value under the
  declared tolerance; or it cannot be recomputed (malformed row, unknown
  method, missing argument, file not in scope, undecodable or unparseable CSV,
  missing or duplicated column, empty or non-numeric cell, too few rows, a
  quantity name that matches no row or more than one, a `where` clause of the
  wrong shape, a zero divisor in `ratio` or `percent_change`, an input key the
  method does not take — the message names the keys it does take, so a
  guessed argument name reads "`mae` takes truth, pred; got x, y" and an
  ignored filter is a shape error rather than a "value disagrees"; a selected
  row set that is EMPTY after every declared filter, for every method, `count`
  and `sum` included, since both would otherwise verify a reported 0 over rows
  that do not exist; an `uncommitted` that is not a boolean, or
  `uncommitted: true` without a non-empty string `file`; a `file` that
  normalises outside the results.json directory). When the row is
  `t_pvalue_two_sided` and its `t` or `df` is not a quantity grounded by a
  derivation chain of its own (below), the message adds one sentence: `t` and
  `df` are read as REPORTED values, never as columns, so declare `welch_t` /
  `welch_df` rows for them to verify the chain end to end. A sentence, not a
  separate finding.
* CA-DERIV-002 (ADVISORY, `derivations`) — a derivation whose file is declared
  uncommitted (`"uncommitted": true` beside a non-empty string `file` inside
  the results.json directory, or `"file": "uncommitted"`) and is indeed not in
  scope: the generator said where, the
  project does not keep it, so the check says it could not look rather than
  passing in silence. A file declared uncommitted that IS in scope is verified
  like any other.
* CA-DERIV-003 (ADVISORY, `derivations`) — a derivation that AGREES, with a
  caveat about its declaration; two shapes. (a) It was declared with the one
  accepted alias, `filter: {<column>: <value>}` (one column, one value, and
  only in a one-sample or paired form) for `where`, and the
  finding gives the canonical form; an alias selects the same rows and is
  reported, so reading it is not fail-open, and an alias that could mean two
  things (beside a `where`, shaped like a where clause, empty, a non-text
  value) blocks under CA-DERIV-001. (b) It is computed from scalar
  operands (`t_pvalue_two_sided`, `scale`, and `ratio` / `percent_change` in
  their scalar form) that AGREES with its reported value, but reads a quantity
  that is not grounded: no derivation row recomputes that quantity from a
  committed file, directly or through a chain of scalar rows whose own
  operands are grounded. The arithmetic was checked; the input to it is a
  reported number nobody checked, so the row is "verified against a reported
  number", not "verified", and says so. A numeric literal operand is part of
  the declaration itself and needs no grounding. A row that already blocks
  under CA-DERIV-001 gets no CA-DERIV-003 as well. Never blocks: whether the
  operand should have been declared is coverage, and coverage is the
  auditor's tier.
* CA-ML-001 (BLOCKER, `split_integrity`) — a `splits.json` whose train/test
  (and optional val/validation) id lists overlap, repeat an id, name an id the
  data file does not hold, or share a group when `group_column` is set; or the
  declaration cannot be read (unparseable, a repeated JSON key, missing keys,
  a key outside `data`, `id_column`, `group_column`, `train`, `test`, `val`,
  `validation` — `group_colum` would switch the group test off silently —,
  both `val` and `validation`, a `data` path outside the splits.json
  directory, data file or column absent, an id the data file holds twice).
* CA-REPRO-001 (ADVISORY, `repro_declared`) — a results.json that says
  `"stochastic": true` sits beside a metadata.yml lacking a non-empty
  `command`, a non-empty `environment`, or an integer `seed`. One finding per
  missing key. Never blocks: the constitution's rule is advisory and this
  keeps it so.
* CA-STAT-004 (BLOCKER, `claims`) — a declared claim is false when its operands
  are compared, or cannot be decided (unknown test, missing operand, an operand
  naming no quantity or several, a non-numeric operand, an interval whose low
  end exceeds its high end).
* CA-PREC-001 (ADVISORY, `precision`) — a value written with more decimal
  places than one beyond the first significant digit of its own numeric
  `uncertainty`.

**The derivation methods** (`_METHODS`; DESIGN §4.3, v2 additions in §9
Amendment 3). Column vectors: count, mean, sd and sem (n − 1), sd_population
and sem_population (n — numpy's `std` default, which the first dogfood audit
found reported as sample sds), median, min, max, sum, last, last_delta_abs.
Two samples: difference, welch_t, welch_df, ci95_low, ci95_high. Paired
columns: mae, rmse, r2, pearson_r, linfit_slope, linfit_intercept,
arrhenius_ea_kj_per_mol, arrhenius_ln_a; bragg_cubic_a. Scalar operands only:
t_pvalue_two_sided, scale. Either form, decided by the presence of `file`:
ratio(a, b) = a / b and percent_change(new, old) = 100 · (new − old) / |old| —
over the MEANS of two selected samples with a file, over quantity names or
literals without one. `where` is one `{"column", "equals"}` clause or a
non-empty list of them, all of which must hold; any other shape blocks.

**An unrecognised declaration key is a declaration that cannot be read.** A
derivation's `input` may carry only `file`, the method's own argument keys,
`where`, `uncommitted`, `column` (the alias of a single-column `x`),
`wavelength` (bragg_cubic_a only) and the one alias `filter`; a two-sample
argument mapping is exactly `{"column", "where"}`; a where clause is exactly
`{"column", "equals"}`. Anything else is CA-DERIV-001 naming the keys the
method takes — never ignored. v1 ignored unknown `input` keys, so a filter
under another name ran over every row and came back as "value disagrees"
(the live-generator experiment's Arm C, records under
`~/Claude/crossaudit-dogfood/declarations-experiment/`).

**Which comparisons are exact and which are floating point.** Range bounds,
claims and the `sig` tolerance compare canonical decimals (`Decimal` built from
the literal as written, or from `repr` of a float — the shortest string that
round-trips, which is what the JSON said), so no comparison there passes
through binary rounding. Derivations are *computed* in IEEE double precision
(`math.fsum` for sums, `math.lgamma` for the beta function), so an `abs` or
`rel` tolerance is a float comparison and a relative tolerance below about
1e-14 cannot be met reliably; the default `rel: 1e-9` is five orders above
that, and an increment that rounds its reported values must declare a tolerance
at least as wide as its rounding. `sig` rounds the computed double exactly (by
its full binary value) and the reported literal exactly, then compares the two
canonical decimals.
"""
from __future__ import annotations

import csv
import io
import json
import math
import posixpath
import re
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from fnmatch import fnmatchcase
from typing import Callable, Mapping

import yaml

from .framework import ADVISORY, BLOCKER, Finding, register
from .quantities import is_number_shape, normalise_number, results_files

#: Joules per mole-kelvin, CODATA 2018 exact.
GAS_CONSTANT = 8.314462618
#: Cu K-alpha-1, in ångström. Used only when a Bragg derivation names none.
DEFAULT_WAVELENGTH = 1.5406


# ----------------------------------------------------------------- reading
class _Repeated(dict):
    """A JSON object that spelled one key more than once. It holds the LAST
    value of each key, as `json.loads` would; `repeated` names the keys, so a
    reader can refuse the object instead of trusting whichever came last."""

    repeated: list[str]


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    seen: dict = {}
    repeated: list[str] = []
    for key, value in pairs:
        if key in seen and key not in repeated:
            repeated.append(key)
        seen[key] = value
    if not repeated:
        return seen
    out = _Repeated(seen)
    out.repeated = repeated
    return out


def _loads(text: str):
    """`json.loads` that marks every object repeating a key (`_Repeated`)."""
    return json.loads(text, object_pairs_hook=_pairs)


def _repeats(node, where: str = "") -> list[str]:
    """'key' in location, for every repeated key anywhere in a parsed tree."""
    out: list[str] = []
    if isinstance(node, dict):
        if isinstance(node, _Repeated):
            at = where or "the top-level object"
            out += [f"{key!r} in {at}" for key in node.repeated]
        for key, value in node.items():
            out += _repeats(value, f"{where}.{key}" if where else str(key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out += _repeats(value, f"{where}[{i}]")
    return out


def _repeat_text(what: str, repeats: list[str]) -> str:
    shown = "; ".join(repeats[:5]) + (" …" if len(repeats) > 5 else "")
    return (f"{what} repeats a JSON key ({shown}); a JSON reader keeps only the "
            "last occurrence, so which value was declared is ambiguous")


def _results_scan(files: Mapping[str, bytes]) -> tuple[list[tuple[str, dict]],
                                                        list[tuple[str, dict, str]]]:
    """(readable docs, docs that repeat a key), each sorted by path.

    Unparseable files are skipped: `schema` reports them as CA-META-001. A
    mapping that repeats a key anywhere is NOT readable here — every pack check
    would otherwise read whichever value came last — and comes back in the
    second list as (path, doc, the refusal text) for the blocking checks that
    read it to report under their own code.
    """
    out: list[tuple[str, dict]] = []
    bad: list[tuple[str, dict, str]] = []
    for path in sorted(results_files(files)):
        try:
            doc = _loads(files[path].decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            continue
        if not isinstance(doc, dict):
            continue
        repeats = _repeats(doc)
        if repeats:
            bad.append((path, doc, _repeat_text("results.json", repeats)))
        else:
            out.append((path, doc))
    return out, bad


def _results_docs(files: Mapping[str, bytes]) -> list[tuple[str, dict]]:
    """Every readable results.json mapping, sorted by path (`_results_scan`)."""
    return _results_scan(files)[0]


def _contained(base: str, raw: str, owner: str) -> str:
    """The scope path `raw` names, relative to `base`; it must stay inside it.

    Normalised first, so `scripts/../data/d.csv` is `data/d.csv`. A path that
    leaves `base` — `../…`, an absolute path, a sibling experiment's file that
    IS in scope — cannot be read: the skill tells the generator paths never
    climb out, and a check that followed them anyway would verify against
    another experiment's data.
    """
    target = posixpath.normpath(posixpath.join(base, raw))
    if base:
        inside = target.startswith(base + "/")
    else:
        inside = not (target == ".." or target.startswith("../"))
    if raw.startswith("/") or target.startswith("/") or not inside:
        raise _Undecidable(
            f"file {raw!r} resolves to {target!r}, which is outside "
            f"{base or 'the scope root'!r}, the directory holding this {owner}; input "
            f"files are named relative to {base or 'the scope root'!r} and must stay "
            "inside it (never ../… or an absolute path)")
    return target


def _quantities(doc: dict) -> list:
    raw = doc.get("quantities")
    return raw if isinstance(raw, list) else []


def _label(q, i: int) -> str:
    name = q.get("name") if isinstance(q, dict) else None
    return f"quantities[{i}] ({name})" if isinstance(name, str) else f"quantities[{i}]"


def _decimal(value) -> Decimal | None:
    """The exact decimal a JSON value spells, or None when it is not a number.

    A float is read through `repr`, the shortest literal that round-trips —
    which is the literal the JSON carried — so 0.1 is 0.1 and not the binary
    expansion of the nearest double. A string must be a plain decimal literal
    (`normalise_number`'s grammar), with a U+2212 minus folded and NO thousands
    separator: `normalise_number` drops commas, which would read a decimal
    comma `12,5` as 125, and a check that compares magnitudes must not.
    """
    if not is_number_shape(value):
        return None
    if isinstance(value, str):
        text = value.strip().replace("−", "-")
        if "," in text or normalise_number(text) is None:
            return None
    elif isinstance(value, float):
        text = repr(value)
    else:
        text = str(value)
    try:
        d = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _float(value) -> float | None:
    d = _decimal(value)
    if d is None:
        return None
    f = float(d)
    return f if math.isfinite(f) else None


def _lookup(doc: dict, name: str) -> tuple[dict | None, str]:
    """The single quantity row called `name`, or (None, why)."""
    rows = [q for q in _quantities(doc) if isinstance(q, dict) and q.get("name") == name]
    if not rows:
        return None, f"names quantity {name!r}, which no results row carries"
    if len(rows) > 1:
        return None, f"names quantity {name!r}, which {len(rows)} results rows carry"
    return rows[0], ""


# ------------------------------------------------------- numeric_validity
def check_numeric_validity(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-NUM-005: every quantity value is a finite number."""
    docs, repeated = _results_scan(files)
    out: list[Finding] = [Finding(BLOCKER, "CA-NUM-005", path,
                                  f"{text}; its values cannot be verified")
                          for path, _doc, text in repeated]
    for path, doc in docs:
        for i, q in enumerate(_quantities(doc)):
            if not isinstance(q, dict):
                continue                                   # reported by check_units
            if "value" not in q:
                out.append(Finding(BLOCKER, "CA-NUM-005", path,
                                   f"{_label(q, i)} has no value"))
                continue
            value = q["value"]
            if not is_number_shape(value):
                out.append(Finding(
                    BLOCKER, "CA-NUM-005", path,
                    f"{_label(q, i)} value {value!r} is not a finite number"))
    return out


# ------------------------------------------------------------ range_rules
_RANGES_OPEN = re.compile(r"```crossaudit-ranges[^\n]*(?:\n|\Z)")
_RANGES = re.compile(r"```crossaudit-ranges[^\n]*\n(.*?)\n```", re.S)
#: Every key a range entry may carry. Any other — `maximum` for `max` — would
#: silently drop a bound, so it blocks.
_RANGE_KEYS = frozenset({"name", "unit", "min", "max"})


def _bound(entry: dict, key: str) -> tuple[bool, Decimal | None]:
    """(ok, bound). A bound is an int or float, never a bool or a string."""
    if key not in entry or entry[key] is None:
        return True, None
    raw = entry[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return False, None
    d = _decimal(raw)
    return (d is not None), d


def _range_entries(files: Mapping[str, bytes]) -> tuple[list[dict], list[Finding]]:
    """Every declared range, in (sorted path, block order); plus malformed-block
    findings. A malformed block contributes NO entries: half a rulebook is not
    a rulebook, and its failure is already a blocker."""
    entries: list[dict] = []
    out: list[Finding] = []
    for path in sorted(p for p in files
                       if p.endswith("AUDIT_RULES.md")):
        try:
            text = files[path].decode("utf-8")
        except UnicodeDecodeError:
            if b"crossaudit-ranges" in files[path]:
                out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                                   "the file carrying a crossaudit-ranges block is "
                                   "not UTF-8, so the ranges cannot be read"))
            continue
        text = text.replace("\r\n", "\n")
        opened = _RANGES_OPEN.findall(text)
        blocks = _RANGES.findall(text)
        if not opened:
            continue
        if len(opened) != len(blocks):
            out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                               "a crossaudit-ranges block is never closed"))
            continue
        if len(blocks) > 1:
            out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                               f"{len(blocks)} crossaudit-ranges blocks in one file; "
                               "the constitution carries one, so which rules apply "
                               "is ambiguous"))
            continue
        try:
            rows = _loads(blocks[0])
        except (ValueError, RecursionError) as exc:
            out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                               f"the crossaudit-ranges block does not parse as JSON: {exc}"))
            continue
        repeats = _repeats(rows)
        if repeats:
            out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                               _repeat_text("the crossaudit-ranges block", repeats)
                               + "; the ranges cannot be read"))
            continue
        if not isinstance(rows, list):
            out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                               "the crossaudit-ranges block must be a JSON array of "
                               "{name, unit, min?, max?} entries"))
            continue
        good: list[dict] = []
        bad = False
        for j, row in enumerate(rows):
            problem = ""
            if not isinstance(row, dict):
                problem = "is not a mapping"
            elif set(row) - _RANGE_KEYS:
                problem = ("has a key the range format does not take ("
                           + ", ".join(repr(k) for k in sorted(set(row) - _RANGE_KEYS))
                           + "); an entry takes exactly name, unit, min, max")
            elif not isinstance(row.get("name"), str) or not row["name"]:
                problem = "has no non-empty string name"
            elif not isinstance(row.get("unit"), str) or not row["unit"]:
                problem = "has no non-empty string unit"
            else:
                ok_lo, lo = _bound(row, "min")
                ok_hi, hi = _bound(row, "max")
                if not (ok_lo and ok_hi):
                    problem = "has a min or max that is not a finite number"
                elif lo is not None and hi is not None and lo > hi:
                    problem = f"has min {row['min']!r} above max {row['max']!r}"
                else:
                    good.append({"name": row["name"], "unit": row["unit"],
                                 "min": lo, "max": hi, "where": path})
            if problem:
                bad = True
                out.append(Finding(BLOCKER, "CA-PHYS-001", path,
                                   f"crossaudit-ranges entry [{j}] {problem}"))
        if not bad:
            entries.extend(good)
    return entries, out


def check_range_rules(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-PHYS-001: quantities obey the ranges the constitution declares."""
    entries, out = _range_entries(files)
    if not entries:
        return out
    docs, repeated = _results_scan(files)
    out += [Finding(BLOCKER, "CA-PHYS-001", path,
                    f"{text}; the declared ranges cannot be verified against it")
            for path, _doc, text in repeated]
    for path, doc in docs:
        for i, q in enumerate(_quantities(doc)):
            if not isinstance(q, dict) or not isinstance(q.get("name"), str):
                continue
            name = q["name"]
            # Case-sensitive on every platform: `fnmatch.fnmatch` folds case
            # through `os.path.normcase`, so the same rulebook would match
            # differently on Windows.
            rule = next((e for e in entries
                         if name == e["name"] or fnmatchcase(name, e["name"])), None)
            if rule is None:
                continue
            label = _label(q, i)
            if q.get("unit") != rule["unit"]:
                out.append(Finding(
                    BLOCKER, "CA-PHYS-001", path,
                    f"{label} unit {q.get('unit')!r} is not the declared unit "
                    f"{rule['unit']!r} for {rule['name']!r} ({rule['where']})"))
                continue
            value = _decimal(q.get("value"))
            if value is None:
                out.append(Finding(
                    BLOCKER, "CA-PHYS-001", path,
                    f"{label} value {q.get('value')!r} is not a finite number, so "
                    f"the declared range for {rule['name']!r} cannot be verified"))
                continue
            lo, hi = rule["min"], rule["max"]
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                span = f"[{'-inf' if lo is None else lo}, {'inf' if hi is None else hi}]"
                out.append(Finding(
                    BLOCKER, "CA-PHYS-001", path,
                    f"{label} value {q.get('value')!r} {rule['unit']} lies outside "
                    f"the declared range {span} for {rule['name']!r} ({rule['where']})"))
    return out


# ------------------------------------------------------------ statistics
class _Undecidable(Exception):
    """A derivation that cannot be recomputed. Its message is the finding."""


def _mean(v: list[float]) -> float:
    if not v:
        raise _Undecidable("needs at least one row")
    return math.fsum(v) / len(v)


def _var(v: list[float]) -> float:
    if len(v) < 2:
        raise _Undecidable("needs at least two rows for a sample variance")
    m = _mean(v)
    return math.fsum((x - m) ** 2 for x in v) / (len(v) - 1)


def _var_population(v: list[float]) -> float:
    """The n-divisor variance — `numpy.std`'s default (`ddof=0`), which the
    first dogfood audit found reported as a sample sd in two real repositories.
    Declaring it is how a generator says honestly which one it computed."""
    m = _mean(v)
    return math.fsum((x - m) ** 2 for x in v) / len(v)


def _median(v: list[float]) -> float:
    if not v:
        raise _Undecidable("needs at least one row")
    s = sorted(v)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def _ratio(a: float, b: float) -> float:
    if b == 0:
        raise _Undecidable("the divisor b is zero; the ratio is undefined")
    return a / b


def _percent_change(new: float, old: float) -> float:
    """100 * (new - old) / |old|: the sign follows the change, whatever old's sign."""
    if old == 0:
        raise _Undecidable("the reference value old is zero; a percent change is undefined")
    return 100.0 * (new - old) / abs(old)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta, modified Lentz."""
    tiny, eps = 1e-300, 1e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 10001):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise _Undecidable("the incomplete beta continued fraction did not converge")


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b), pure Python."""
    if not (a > 0 and b > 0) or not (0.0 <= x <= 1.0):
        raise _Undecidable("incomplete beta outside its domain")
    if x in (0.0, 1.0):
        return x
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_pvalue_two_sided(t: float, df: float) -> float:
    """P(|T| >= |t|) for Student's t with `df` degrees of freedom."""
    if not (math.isfinite(t) and math.isfinite(df)) or df <= 0:
        raise _Undecidable("t and df must be finite with df > 0")
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def t_quantile_two_sided(p: float, df: float) -> float:
    """The q > 0 with t_pvalue_two_sided(q, df) == p, by bisection on the CDF."""
    if not (0.0 < p < 1.0):
        raise _Undecidable("a two-sided tail probability must lie in (0, 1)")
    lo, hi = 0.0, 1.0
    while t_pvalue_two_sided(hi, df) > p:
        lo, hi = hi, hi * 2.0
        if hi > 1e12:
            raise _Undecidable("the t quantile is out of range")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if mid in (lo, hi):
            break
        if t_pvalue_two_sided(mid, df) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _welch(a: list[float], b: list[float]) -> tuple[float, float, float]:
    """(difference of means, standard error, Welch–Satterthwaite df)."""
    va, vb = _var(a) / len(a), _var(b) / len(b)
    se2 = va + vb
    denom = (va * va / (len(a) - 1)) + (vb * vb / (len(b) - 1))
    if se2 <= 0 or denom <= 0:
        raise _Undecidable("both groups have zero variance; Welch's t is undefined")
    return _mean(a) - _mean(b), math.sqrt(se2), se2 * se2 / denom


def _linfit(x: list[float], y: list[float]) -> tuple[float, float]:
    if len(x) < 2:
        raise _Undecidable("needs at least two rows for a line")
    mx, my = _mean(x), _mean(y)
    sxx = math.fsum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        raise _Undecidable("x has zero variance; the slope is undefined")
    sxy = math.fsum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    slope = sxy / sxx
    return slope, my - slope * mx


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        raise _Undecidable("needs at least two rows for a correlation")
    mx, my = _mean(x), _mean(y)
    sxx = math.fsum((xi - mx) ** 2 for xi in x)
    syy = math.fsum((yi - my) ** 2 for yi in y)
    if sxx == 0 or syy == 0:
        raise _Undecidable("a column has zero variance; r is undefined")
    return math.fsum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / math.sqrt(sxx * syy)


def _r2(truth: list[float], pred: list[float]) -> float:
    m = _mean(truth)
    ss_tot = math.fsum((t - m) ** 2 for t in truth)
    if ss_tot == 0:
        raise _Undecidable("truth has zero variance; r2 is undefined")
    return 1.0 - math.fsum((t - p) ** 2 for t, p in zip(truth, pred)) / ss_tot


def _arrhenius(T: list[float], k: list[float]) -> tuple[float, float]:
    if any(t <= 0 for t in T) or any(v <= 0 for v in k):
        raise _Undecidable("Arrhenius needs every T_K and k strictly positive")
    return _linfit([1.0 / t for t in T], [math.log(v) for v in k])


def _bragg(tt: list[float], h: list[float], k: list[float], l: list[float],
           wavelength: float) -> float:
    if not tt:
        raise _Undecidable("needs at least one peak")
    values = []
    for t, hh, kk, ll in zip(tt, h, k, l):
        if not (0.0 < t < 180.0):
            raise _Undecidable(f"two_theta {t} is not in (0, 180) degrees")
        s = hh * hh + kk * kk + ll * ll
        if s <= 0:
            raise _Undecidable("a peak has h = k = l = 0")
        d = wavelength / (2.0 * math.sin(math.radians(t / 2.0)))
        values.append(d * math.sqrt(s))
    return _mean(values)


def _last(y: list[float]) -> float:
    if not y:
        raise _Undecidable("needs at least one row")
    return y[-1]


def _last_delta(y: list[float]) -> float:
    if len(y) < 2:
        raise _Undecidable("needs at least two rows")
    return abs(y[-1] - y[-2])


def _nonempty(fn):
    def wrapped(v):
        if not v:
            raise _Undecidable("needs at least one row")
        return fn(v)
    return wrapped


def _paired_mae(t, p):
    return _mean([abs(a - b) for a, b in zip(t, p)])


def _paired_rmse(t, p):
    return math.sqrt(_mean([(a - b) ** 2 for a, b in zip(t, p)]))


def _ci(sign: int):
    def fn(a, b):
        diff, se, df = _welch(a, b)
        return diff + sign * t_quantile_two_sided(0.05, df) * se
    return fn


#: The registry, exactly DESIGN §4.3 (v2 additions: Amendment 3). Each entry:
#: (kind, argument keys, fn). kind "single": one column vector; "two": two
#: independent samples, each argument a column or {"column", "where"};
#: "paired": columns of the same rows; "scalar": operands are numeric literals
#: or quantity names; "mixed": with a `file`, each operand is a sample exactly
#: as for "two" and fn receives the two sample MEANS; without one, each operand
#: is a scalar exactly as for "scalar". Which form a row uses is decided by the
#: presence of `file` and nothing else.
_METHODS: dict[str, tuple[str, tuple[str, ...], Callable]] = {
    "count": ("count", ("x",), len),
    "mean": ("single", ("x",), _mean),
    "sd": ("single", ("x",), lambda v: math.sqrt(_var(v))),
    "sem": ("single", ("x",), lambda v: math.sqrt(_var(v) / len(v))),
    "sd_population": ("single", ("x",), lambda v: math.sqrt(_var_population(v))),
    "sem_population": ("single", ("x",),
                       lambda v: math.sqrt(_var_population(v)) / math.sqrt(len(v))),
    "median": ("single", ("x",), _median),
    "min": ("single", ("x",), _nonempty(min)),
    "max": ("single", ("x",), _nonempty(max)),
    "sum": ("single", ("x",), math.fsum),
    "last": ("single", ("y",), _last),
    "last_delta_abs": ("single", ("y",), _last_delta),
    "difference": ("two", ("a", "b"), lambda a, b: _mean(a) - _mean(b)),
    "welch_t": ("two", ("a", "b"), lambda a, b: (lambda w: w[0] / w[1])(_welch(a, b))),
    "welch_df": ("two", ("a", "b"), lambda a, b: _welch(a, b)[2]),
    "ci95_low": ("two", ("a", "b"), _ci(-1)),
    "ci95_high": ("two", ("a", "b"), _ci(+1)),
    "mae": ("paired", ("truth", "pred"), _paired_mae),
    "rmse": ("paired", ("truth", "pred"), _paired_rmse),
    "r2": ("paired", ("truth", "pred"), _r2),
    "pearson_r": ("paired", ("x", "y"), _pearson),
    "linfit_slope": ("paired", ("x", "y"), lambda x, y: _linfit(x, y)[0]),
    "linfit_intercept": ("paired", ("x", "y"), lambda x, y: _linfit(x, y)[1]),
    "arrhenius_ea_kj_per_mol": ("paired", ("T_K", "k"),
                                lambda T, k: -_arrhenius(T, k)[0] * GAS_CONSTANT / 1000.0),
    "arrhenius_ln_a": ("paired", ("T_K", "k"), lambda T, k: _arrhenius(T, k)[1]),
    "bragg_cubic_a": ("bragg", ("two_theta_deg", "h", "k", "l"), _bragg),
    "t_pvalue_two_sided": ("scalar", ("t", "df"), t_pvalue_two_sided),
    "scale": ("scalar", ("x", "factor"), lambda x, f: x * f),
    "ratio": ("mixed", ("a", "b"), _ratio),
    "percent_change": ("mixed", ("new", "old"), _percent_change),
}
METHODS = tuple(_METHODS)

#: One line per method: what it computes. With `_METHODS` this is the single
#: source of the generator-facing table (`method_table`), which the scaffold
#: writes into skills/ai4s-declarations.md — so the table a generator reads and
#: the keys this check accepts cannot drift apart. A method registered without
#: a line here fails `method_table` (and its test), never silently.
_MEANINGS: dict[str, str] = {
    "count": "number of selected rows",
    "mean": "arithmetic mean",
    "sd": "sample standard deviation (n − 1)",
    "sem": "sample standard error, sd / √n",
    "sd_population": "population standard deviation (n; numpy.std's default, ddof=0)",
    "sem_population": "population sd / √n",
    "median": "median (mean of the two middle values for an even count)",
    "min": "smallest value",
    "max": "largest value",
    "sum": "sum",
    "last": "value in the last selected row",
    "last_delta_abs": "abs(y[−1] − y[−2]) over the last two selected rows",
    "difference": "mean(a) − mean(b)",
    "welch_t": "Welch's t statistic of a against b",
    "welch_df": "Welch–Satterthwaite degrees of freedom",
    "ci95_low": "lower end of the Welch 95% interval for mean(a) − mean(b)",
    "ci95_high": "upper end of the Welch 95% interval for mean(a) − mean(b)",
    "mae": "mean of abs(truth − pred)",
    "rmse": "√mean (truth − pred)²",
    "r2": "1 − SS_res / SS_tot of pred against truth",
    "pearson_r": "Pearson correlation of x and y",
    "linfit_slope": "least-squares slope of y on x",
    "linfit_intercept": "least-squares intercept of y on x",
    "arrhenius_ea_kj_per_mol": "−R × slope of ln k on 1/T_K, in kJ/mol",
    "arrhenius_ln_a": "intercept of ln k on 1/T_K",
    "bragg_cubic_a": "mean over peaks of d·√(h²+k²+l²), d = λ / (2 sin θ); λ in Å, default 1.5406",
    "t_pvalue_two_sided": "two-sided Student-t p-value of t with df degrees of freedom",
    "scale": "x × factor",
    "ratio": "a / b (with a file: mean(a) / mean(b))",
    "percent_change": "100 × (new − old) / abs(old) (with a file: over the means)",
}

_FORMS = {
    "count": "columns", "single": "columns", "paired": "columns (same rows)",
    "bragg": "columns (same rows)", "two": "two samples",
    "scalar": "quantities", "mixed": "samples or quantities",
}


def _allowed_keys(method: str) -> set[str]:
    """Every input key a row for `method` may carry. Anything else blocks."""
    kind, keys, _fn = _METHODS[method]
    if kind == "scalar":
        return set(keys)
    allowed = set(keys) | {"file", "where", "uncommitted"}
    if kind in ("single", "count") and keys == ("x",):
        allowed.add("column")
    if kind == "bragg":
        allowed.add("wavelength")
    return allowed


def _key_spec(method: str) -> str:
    kind, keys, _fn = _METHODS[method]
    names = ", ".join(f"`{k}`" for k in keys)
    if kind == "scalar":
        return f"{names} — each a quantity name or a number (no file)"
    if kind == "mixed":
        return (f"{names} — with `file`: each a column or `{{\"column\", \"where\"}}`; "
                "without: each a quantity name or a number")
    if kind == "two":
        return f"`file`, {names} — each a column or `{{\"column\", \"where\"}}`"
    extra = " (or `column`)" if "column" in _allowed_keys(method) else ""
    extra += ", optional `wavelength`" if kind == "bragg" else ""
    return f"`file`, {names}{extra} — column names"


def method_table() -> str:
    """The generator-facing derivation table, rendered from `_METHODS`.

    Markdown, one row per registered method: name, form, the EXACT input keys,
    and what it computes. `where` (optional for every file-reading form) is
    described once, under the table, rather than in every row.
    """
    missing = [m for m in METHODS if m not in _MEANINGS]
    if missing:
        raise RuntimeError(f"no meaning recorded for methods {missing}")
    bad = [m for m, text in _MEANINGS.items() if "|" in text]
    if bad:
        raise RuntimeError(f"a table cell may not hold '|': {bad}")
    rows = ["| method | form | input keys (exactly these) | computes |",
            "|---|---|---|---|"]
    for m in METHODS:
        rows.append(f"| `{m}` | {_FORMS[_METHODS[m][0]]} | {_key_spec(m)} | {_MEANINGS[m]} |")
    rows.append("")
    rows.append("Every form that reads a `file` also takes an optional `where`: one "
                "`{\"column\": …, \"equals\": …}` clause or a non-empty list of them "
                "(all must hold), cells compared as strings. Any other input key "
                "blocks; the message names the keys the method takes.")
    return "\n".join(rows)


#: Where the `filter` alias is read. Only forms whose top-level `where` selects
#: THE rows the method reads (one sample, or one set of paired rows). In a
#: two-sample form a top-level filter beside `a`/`b` could mean "both samples
#: from these rows" or "this is how a differs from b" — the shape the second
#: live-generator run wrote, which then ran Welch's t over every row and was
#: reported as a value mismatch — so there `filter` is an unknown key and blocks.
_ALIAS_KINDS = ("single", "count", "paired", "bragg")

#: Keys a generator writes for a filter that is not `where`, and what to say.
_FILTER_WORDS = ("filter", "filters", "select", "subset", "rows", "group", "split",
                 "condition", "where_column")


def _normalise_input(method: str, spec: dict) -> tuple[dict, str]:
    """Check a row's input keys against the method; read the one alias.

    Returns (input, note): `note` is non-empty when the `filter` alias was read,
    and is what the CA-DERIV-003 advisory says. `filter: {<column>: <value>, …}`
    — the shape the first live-generator experiment wrote 17 times — is read as
    `where: [{"column": <column>, "equals": <value>}, …]`. An alias is not a
    truth claim: the same rows are selected either way, the arithmetic is the
    check's own, and the reading is reported, so accepting it is not fail-open.
    Everything that could mean two things still blocks: `filter` beside
    `where`, a `filter` shaped like a where clause, an empty one, a non-string
    value. Any other key the method does not take blocks, naming the keys it
    does take — an ignored filter used to run the mean over every row and
    report "value disagrees" for what was a shape error.
    """
    kind, keys, _fn = _METHODS[method]
    note = ""
    if "filter" in spec and kind in _ALIAS_KINDS:
        raw = spec["filter"]
        if "where" in spec:
            raise _Undecidable("input gives both 'filter' and 'where'; write one where")
        if (not isinstance(raw, dict) or len(raw) != 1 or "column" in raw or "equals" in raw
                or any(not isinstance(c, str) or not c for c in raw)
                or any(isinstance(v, bool) or not isinstance(v, (str, int))
                       for v in raw.values())):
            raise _Undecidable(
                f"input 'filter' {raw!r} cannot be read; the alias is accepted only as "
                "one column and one value, {<column>: <value>}; write where: "
                "{\"column\": <name>, \"equals\": <value>} (or a list of such clauses)")
        (col, val), = raw.items()
        spec = {k: v for k, v in spec.items() if k != "filter"}
        spec["where"] = {"column": col, "equals": val}
        note = (f"read 'filter': {json.dumps(raw, ensure_ascii=False)} as 'where': "
                f"{json.dumps(spec['where'], ensure_ascii=False)}; write the where form")
    allowed = _allowed_keys(method)
    unknown = sorted(k for k in spec if k not in allowed)
    given = sorted(k for k in spec if k not in ("file", "where", "uncommitted"))
    takes = ", ".join(keys) + ("" if kind == "scalar" else " and optional where")
    if unknown:
        hints = []
        for k in unknown:
            if k in _FILTER_WORDS:
                hints.append(f"to keep rows by a column write where: {{\"column\": ..., "
                             f"\"equals\": ...}} instead of {k!r}")
            elif k in ("file", "where") and kind in ("scalar", "mixed"):
                hints.append(f"{method} reads quantities, not a file, here")
            else:
                users = [m for m in METHODS if k in _METHODS[m][1] and m != method]
                if users:
                    hints.append(f"{k!r} is an argument of {', '.join(users[:4])}"
                                 f"{', …' if len(users) > 4 else ''}")
        raise _Undecidable(
            f"input has a key this method does not take "
            f"({', '.join(repr(k) for k in unknown)}); {method} takes {takes}; got "
            f"{', '.join(given) or 'nothing'}" + (f" ({'; '.join(hints)})" if hints else ""))
    present = set(spec) | ({"x"} if "column" in spec else set())
    missing = [k for k in keys if k not in present]
    if missing:
        raise _Undecidable(f"{method} takes {takes}; got {', '.join(given) or 'nothing'} "
                           f"(missing {', '.join(missing)})")
    return spec, note


# ------------------------------------------------------------- CSV access
class _Table:
    def __init__(self, path: str, header: list[str], rows: list[dict]):
        self.path, self.header, self.rows = path, header, rows


def _read_table(files: Mapping[str, bytes], path: str) -> _Table:
    if path not in files:
        raise _Undecidable(f"file {path!r} is not in the audited scope")
    try:
        # utf-8-sig: a byte-order mark is an export artefact, not part of the
        # first column's name, and keeping it would block on a missing column.
        text = files[path].decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _Undecidable(f"file {path!r} is not UTF-8") from None
    try:
        raw = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise _Undecidable(f"file {path!r} does not parse as CSV: {exc}") from None
    # `csv.reader` rather than `csv.DictReader`, because DictReader SKIPS a
    # blank line — and in a one-column file a blank line is an empty cell, so
    # a missing measurement vanished and the mean of the rest passed. Trailing
    # blank lines are layout and are dropped; a blank line between data rows
    # is a row whose every cell is empty, and it is kept so `_cell` refuses it.
    while raw and not raw[-1]:
        raw.pop()
    if not raw:
        raise _Undecidable(f"file {path!r} has no header row")
    header, rows = raw[0], []
    for n, cells in enumerate(raw[1:], start=2):
        if len(cells) > len(header):
            raise _Undecidable(f"file {path!r} row {n} has more fields than its header")
        rows.append({h: (cells[i] if i < len(cells) else None)
                     for i, h in enumerate(header)})
    return _Table(path, header, rows)


def _column(table: _Table, name) -> str:
    if not isinstance(name, str) or not name:
        raise _Undecidable(f"column {name!r} is not a non-empty string")
    n = table.header.count(name)
    if n == 0:
        raise _Undecidable(f"{table.path!r} has no column {name!r}")
    if n > 1:
        # DictReader keeps the LAST duplicate silently; which one was meant is
        # not something this check gets to guess.
        raise _Undecidable(f"{table.path!r} has {n} columns named {name!r}")
    return name


def _clauses(where) -> list[dict]:
    """`where` as a list of clauses: one {"column", "equals"} mapping, or a
    non-empty list of them (all must hold). Anything else cannot be read."""
    if isinstance(where, dict):
        where = [where]
    elif not isinstance(where, list) or not where:
        raise _Undecidable("where must be {\"column\", \"equals\"} or a non-empty list "
                           "of them")
    for n, clause in enumerate(where):
        if not isinstance(clause, dict) or set(clause) != {"column", "equals"}:
            raise _Undecidable(f"where clause [{n}] must be exactly "
                               "{\"column\", \"equals\"}")
        want = clause["equals"]
        if isinstance(want, bool) or not isinstance(want, (str, int)):
            raise _Undecidable(f"where clause [{n}] equals must be a string or an integer")
    return where


def _no_rows(table: _Table, where, narrowed: bool = False) -> str:
    if where is None:
        return (f"{table.path!r} has no data rows; a derivation over zero rows "
                "cannot be verified")
    scope = "the rows the top-level where kept" if narrowed else f"{table.path!r}"
    return (f"the where filter {json.dumps(where, ensure_ascii=False)} selects no rows of "
            f"{scope}; a derivation over zero rows cannot be verified (check the "
            "column and the value as written in the file)")


def _filter(table: _Table, rows: list[dict], where) -> list[dict]:
    if where is None:
        return rows
    # Every clause is read (shape AND column) before any row is kept, so a
    # malformed second clause blocks even when the first selects nothing.
    tests = [(_column(table, c["column"]), str(c["equals"])) for c in _clauses(where)]
    return [r for r in rows if all(r.get(col) == want for col, want in tests)]


def _cell(table: _Table, row: dict, col: str) -> float:
    raw = row.get(col)
    text = raw.strip().replace("−", "-") if isinstance(raw, str) else ""
    # The same grammar `normalise_number` accepts, minus the thousands
    # separator: a decimal comma `12,5` would otherwise read as 125.
    if not text or "," in text or normalise_number(text) is None:
        raise _Undecidable(f"{table.path!r} column {col!r} has a non-numeric cell {raw!r}")
    value = float(text)
    if not math.isfinite(value):
        raise _Undecidable(f"{table.path!r} column {col!r} has a non-finite cell {raw!r}")
    return value


def _vector(table: _Table, rows: list[dict], col: str) -> list[float]:
    return [_cell(table, r, col) for r in rows]


def _scalar_operand(doc: dict, raw, key: str) -> float:
    if isinstance(raw, str):
        q, why = _lookup(doc, raw)
        if q is None:
            raise _Undecidable(f"argument {key!r} {why}")
        value = _float(q.get("value"))
        if value is None:
            raise _Undecidable(f"argument {key!r} names {raw!r}, whose value is not "
                               "a finite number")
        return value
    value = None if isinstance(raw, bool) else _float(raw)
    if value is None:
        raise _Undecidable(f"argument {key!r} must be a number or a quantity name")
    return value


def _compute(files: Mapping[str, bytes], base: str, doc: dict, method: str,
             spec: dict) -> float:
    kind, keys, fn = _METHODS[method]
    if kind in ("single", "count") and keys == ("x",) and "column" in spec:
        # The coordinator's convention names a single-column argument "column";
        # the pack's names it "x". Both are accepted, never both at once: two
        # names for one argument that disagree are a declaration that cannot
        # be read.
        if "x" in spec:
            raise _Undecidable("input gives both 'x' and 'column' for one argument")
        spec = {**spec, "x": spec["column"]}
    missing = [k for k in keys if k not in spec]
    if missing:
        raise _Undecidable(f"method {method!r} needs input {missing}")
    if kind == "mixed" and "file" not in spec and (
            "where" in spec or any(isinstance(spec[k], dict) for k in keys)):
        # A row-filter with no file is a column-form row that lost its file;
        # reading its strings as quantity names instead would be a guess.
        raise _Undecidable(f"method {method!r} has a where filter but no file; give "
                           "the file for the column form, or plain quantity names or "
                           "numbers for the scalar form")
    if _scalar_form(method, spec):
        return fn(*(_scalar_operand(doc, spec[k], k) for k in keys))
    if not isinstance(spec.get("file"), str) or not spec["file"]:
        raise _Undecidable("input names no file")
    target = _contained(base, spec["file"], "results.json")
    if target not in files:
        raise _Undecidable(
            f"file {spec['file']!r} resolves to {target!r}, which is not in the audited "
            f"scope; input files are named relative to {base or 'the scope root'!r}, the "
            "directory holding this results.json")
    table = _read_table(files, target)
    rows = _filter(table, table.rows, spec.get("where"))
    if not rows:
        # Before dispatch, for EVERY method: `count` of nothing is 0 and `sum`
        # of nothing is 0, so a filter that matches no row (a misspelt label)
        # would otherwise verify a reported 0 over rows that do not exist.
        raise _Undecidable(_no_rows(table, spec.get("where")))
    if kind == "count":
        _column(table, spec["x"])
        return float(len(rows))
    if kind in ("two", "mixed"):
        samples = []
        for k in keys:
            arg = spec[k]
            sub = rows
            if isinstance(arg, dict):
                if set(arg) - {"column", "where"} or "column" not in arg:
                    raise _Undecidable(f"argument {k!r} must be a column name or "
                                       "{\"column\", \"where\"}")
                sub = _filter(table, rows, arg.get("where"))
                if not sub:
                    raise _Undecidable(f"argument {k!r}: " + _no_rows(table, arg.get("where"),
                                                                        rows is not table.rows))
                arg = arg["column"]
            samples.append(_vector(table, sub, _column(table, arg)))
        if kind == "mixed":
            return fn(*(_mean(v) for v in samples))
        return fn(*samples)
    cols = [_column(table, spec[k]) for k in keys]
    vectors = [_vector(table, rows, c) for c in cols]
    if kind == "bragg":
        wl = spec.get("wavelength", DEFAULT_WAVELENGTH)
        wl = None if isinstance(wl, bool) else _float(wl)
        if wl is None or wl <= 0:
            raise _Undecidable("wavelength must be a positive number (Å)")
        return fn(*vectors, wl)
    return fn(*vectors)


def _scalar_form(method: str, spec: dict) -> bool:
    """Whether this row reads its operands from the quantities list."""
    kind = _METHODS[method][0]
    return kind == "scalar" or (kind == "mixed" and "file" not in spec)


def _grounded(files: Mapping[str, bytes], base: str, rows: list) -> set[str]:
    """The quantity names a derivation chain recomputes from a committed file.

    A row in column form grounds its quantity when its file is not declared
    uncommitted-and-absent; a scalar-form row grounds its quantity when every
    operand that names a quantity is itself grounded (numeric literals need
    nothing). Iterated to a fixed point, so a chain of scalar rows grounds only
    if its first link reads a file, and a cycle grounds nothing. Whether each
    row AGREES is CA-DERIV-001's business; grounding asks only whether a
    committed file stands at the root of the chain.
    """
    usable = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name, method, spec = row.get("quantity"), row.get("method"), row.get("input")
        if isinstance(name, str) and method in _METHODS and isinstance(spec, dict):
            usable.append((name, method, spec))
    grounded: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, method, spec in usable:
            if name in grounded:
                continue
            if _scalar_form(method, spec):
                ops = [spec.get(k) for k in _METHODS[method][1]]
                ok = all(isinstance(o, str) and o in grounded
                         or (not isinstance(o, (str, bool)) and _float(o) is not None)
                         for o in ops)
            elif _is_uncommitted(spec):
                target = spec.get("file")
                try:
                    ok = (isinstance(target, str) and target != "uncommitted"
                          and _contained(base, target, "results.json") in files)
                except _Undecidable:
                    ok = False
            else:
                ok = True
            if ok:
                grounded.add(name)
                changed = True
    return grounded


def _ungrounded_operands(method: str, spec: dict, grounded: set[str]) -> list[str]:
    """The quantity names a scalar-form row reads that no chain grounds."""
    return [spec[k] for k in _METHODS[method][1]
            if isinstance(spec.get(k), str) and spec[k] not in grounded]


def _pvalue_hint(spec, grounded: set[str]) -> str:
    """The sentence a t_pvalue_two_sided CA-DERIV-001 carries when its t or df
    is not a grounded quantity — the first dogfood audit declared them as
    columns and got only "cannot be verified" back."""
    if not isinstance(spec, dict):
        spec = {}
    loose = []
    for k in ("t", "df"):
        raw = spec.get(k)
        if isinstance(raw, str):
            if raw not in grounded:
                loose.append(f"{k!r} names {raw!r}, which no derivation row verifies")
        elif isinstance(raw, bool) or _float(raw) is None:
            loose.append(f"{k!r} is " + ("missing" if k not in spec
                                         else "neither a quantity name nor a number"))
    if not loose:
        return ""
    return (" t_pvalue_two_sided reads t and df as REPORTED values (a quantity name "
            "or a number), never as columns; here " + "; ".join(loose) + ". Declare "
            "the t statistic with method welch_t and the degrees of freedom with "
            "welch_df over the committed file, so the chain is verified end to end.")


def _round_sig(d: Decimal, n: int) -> str | None:
    if d == 0:
        return "0"
    q = Decimal(1).scaleb(d.adjusted() - n + 1)
    return normalise_number(format(d.quantize(q, rounding=ROUND_HALF_EVEN), "f")
                            if abs(d.adjusted()) < 400 else
                            str(d.quantize(q, rounding=ROUND_HALF_EVEN)))


def _tolerance(raw) -> tuple[str, float | int]:
    if raw is None:
        return "rel", 1e-9
    if not isinstance(raw, dict) or len(raw) != 1:
        raise _Undecidable("tolerance must be exactly one of {abs}, {rel}, {sig}")
    (kind, value), = raw.items()
    if kind in ("abs", "rel"):
        v = None if isinstance(value, bool) else _float(value)
        if v is None or v < 0 or not isinstance(value, (int, float)):
            raise _Undecidable(f"tolerance {kind} must be a non-negative number")
        return kind, v
    if kind == "sig":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 17:
            raise _Undecidable("tolerance sig must be an integer from 1 to 17")
        return kind, value
    raise _Undecidable(f"unknown tolerance kind {kind!r}")


def agrees(computed: float, reported, tolerance) -> bool:
    """Whether a reported value matches a computed one under a tolerance.

    abs: |c - r| <= abs. rel: |c - r| <= rel * |c| (relative to the
    recomputed value, so a computed zero demands an exact zero). sig: both
    rounded half-even to n significant figures — the double by its exact
    binary value, the report by its literal — compare as canonical decimals.
    """
    kind, tol = _tolerance(tolerance)
    if kind == "sig":
        rep = _decimal(reported)
        if rep is None:
            return False
        return _round_sig(Decimal(computed), tol) == _round_sig(rep, tol)
    r = _float(reported)
    if r is None:
        return False
    diff = abs(computed - r)
    return diff <= tol if kind == "abs" else diff <= tol * abs(computed)


def _is_uncommitted(spec: dict) -> bool:
    return spec.get("uncommitted") is True or spec.get("file") == "uncommitted"


def check_derivations(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-DERIV-001/002/003: declared derivations recompute from committed files."""
    docs, repeated = _results_scan(files)
    out: list[Finding] = [Finding(BLOCKER, "CA-DERIV-001", path,
                                  f"{text}; its derivations cannot be verified")
                          for path, doc, text in repeated if "derivations" in doc]
    for path, doc in docs:
        if "derivations" not in doc:
            continue
        rows = doc["derivations"]
        if not isinstance(rows, list):
            out.append(Finding(BLOCKER, "CA-DERIV-001", path,
                               "derivations must be a list"))
            continue
        base = posixpath.dirname(path)
        grounded = _grounded(files, base, rows)
        for j, row in enumerate(rows):
            where = f"derivations[{j}]"
            method = row.get("method") if isinstance(row, dict) else None
            hint = (_pvalue_hint(row.get("input"), grounded)
                    if method == "t_pvalue_two_sided" else "")
            try:
                if not isinstance(row, dict):
                    raise _Undecidable("is not a mapping")
                name, method, spec = row.get("quantity"), row.get("method"), row.get("input")
                if isinstance(name, str):
                    where += f" ({name})"
                if not isinstance(name, str) or not name:
                    raise _Undecidable("names no quantity")
                q, why = _lookup(doc, name)
                if q is None:
                    raise _Undecidable(why)
                if method not in _METHODS:
                    raise _Undecidable(f"method {method!r} is not one this check "
                                       f"can recompute; known: {', '.join(METHODS)}")
                if not isinstance(spec, dict):
                    raise _Undecidable("input must be a mapping")
                _tolerance(row.get("tolerance"))         # malformed blocks first
                spec, alias = _normalise_input(method, spec)
                if "uncommitted" in spec:
                    flag, target = spec["uncommitted"], spec.get("file")
                    if not isinstance(flag, bool):
                        raise _Undecidable(f"input 'uncommitted' is {flag!r}; it must be "
                                           "true or false")
                    if flag and (not isinstance(target, str) or not target.strip()):
                        raise _Undecidable(
                            f"input declares uncommitted: true but its file is {target!r}; "
                            "an uncommitted file must still be named, as a non-empty "
                            "string 'file' beside it, so the advisory says which file "
                            "could not be checked")
                if _is_uncommitted(spec):
                    target = spec.get("file")
                    if isinstance(target, str) and target != "uncommitted":
                        _contained(base, target, "results.json")
                    present = (isinstance(target, str) and target != "uncommitted"
                               and posixpath.normpath(posixpath.join(base, target)) in files)
                    if not present:
                        out.append(Finding(
                            ADVISORY, "CA-DERIV-002", path,
                            f"{where} recomputes from a file declared uncommitted "
                            f"({target!r}); this project does not keep it, so the "
                            "derivation could not be checked"))
                        continue
                if _float(q.get("value")) is None:
                    raise _Undecidable(f"reported value {q.get('value')!r} is not a "
                                       "finite number")
                computed = _compute(files, base, doc, method, spec)
                if not math.isfinite(computed):
                    raise _Undecidable("recomputed value is not finite")
                if not agrees(computed, q.get("value"), row.get("tolerance")):
                    tol = row.get("tolerance") or {"rel": 1e-9}
                    origin = ("from the quantities it names" if _scalar_form(method, spec)
                              else "from the committed file")
                    out.append(Finding(
                        BLOCKER, "CA-DERIV-001", path,
                        f"{where}: {method} recomputed {origin} gives "
                        f"{computed!r}, the reported value is {q.get('value')!r}, which "
                        f"does not agree under tolerance {tol}"
                        + (f" ({alias})" if alias else "") + (f".{hint}" if hint else "")))
                    continue
                if alias:
                    out.append(Finding(
                        ADVISORY, "CA-DERIV-003", path,
                        f"{where}: {method} agrees with the reported value, but the "
                        f"declaration is not in the canonical form: {alias}"))
                if _scalar_form(method, spec):
                    loose = _ungrounded_operands(method, spec, grounded)
                    if loose:
                        out.append(Finding(
                            ADVISORY, "CA-DERIV-003", path,
                            f"{where}: {method} agrees with the reported value, but it "
                            f"reads {', '.join(repr(n) for n in loose)}, which no "
                            "derivation chain recomputes from a committed file; it is "
                            "verified against a reported number, not end to end"))
            except _Undecidable as exc:
                out.append(Finding(BLOCKER, "CA-DERIV-001", path,
                                   f"{where} cannot be verified: {exc}"
                                   + (f".{hint}" if hint else "")))
            except (ArithmeticError, ValueError) as exc:
                out.append(Finding(BLOCKER, "CA-DERIV-001", path,
                                   f"{where} cannot be verified: arithmetic failed "
                                   f"({exc})" + (f".{hint}" if hint else "")))
    return out


# -------------------------------------------------------- split_integrity
_SPLIT_KEYS = ("train", "test", "val", "validation")
#: Every key a splits.json may carry. Any other — `group_colum` — would
#: silently switch a test off, so it blocks.
_SPLIT_DOC_KEYS = frozenset({"data", "id_column", "group_column", *_SPLIT_KEYS})


def _split_findings(files: Mapping[str, bytes], path: str) -> list[Finding]:
    def block(msg: str) -> list[Finding]:
        return [Finding(BLOCKER, "CA-ML-001", path, msg)]

    try:
        doc = _loads(files[path].decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        return block(f"splits.json does not parse, so split integrity cannot be "
                     f"verified: {exc}")
    repeats = _repeats(doc)
    if repeats:
        return block(_repeat_text("splits.json", repeats)
                     + "; split integrity cannot be verified")
    if not isinstance(doc, dict):
        return block("splits.json must be a mapping")
    unknown = sorted(set(doc) - _SPLIT_DOC_KEYS)
    if unknown:
        return block(f"splits.json has a key the split format does not take "
                     f"({', '.join(repr(k) for k in unknown)}); it takes data, "
                     "id_column, group_column, train, test, val or validation, so split "
                     "integrity cannot be verified")
    if "val" in doc and "validation" in doc:
        return block("splits.json gives both 'val' and 'validation'; one validation "
                     "split has one name, so which list is the validation split is "
                     "ambiguous")
    for key in ("data", "id_column"):
        if not isinstance(doc.get(key), str) or not doc[key]:
            return block(f"splits.json has no non-empty string {key!r}")
    group = doc.get("group_column")
    if group is not None and (not isinstance(group, str) or not group):
        return block("splits.json group_column must be a non-empty string or absent")
    splits: dict[str, list[str]] = {}
    for key in _SPLIT_KEYS:
        if key not in doc:
            if key in ("train", "test"):
                return block(f"splits.json has no {key!r} list")
            continue
        ids = doc[key]
        if not isinstance(ids, list) or any(
                isinstance(i, bool) or not isinstance(i, (str, int)) for i in ids):
            return block(f"splits.json {key!r} must be a list of string or integer ids")
        splits[key] = [str(i) for i in ids]
    try:
        data_path = _contained(posixpath.dirname(path), doc["data"], "splits.json")
        table = _read_table(files, data_path)
        id_col = _column(table, doc["id_column"])
        group_col = _column(table, group) if group else None
    except _Undecidable as exc:
        return block(f"split integrity cannot be verified: {exc}")

    out: list[Finding] = []
    data_rows: dict[str, list[dict]] = {}
    for r in table.rows:
        data_rows.setdefault(r.get(id_col), []).append(r)
    for key, ids in splits.items():
        seen, dups = set(), []
        for i in ids:
            if i in seen and i not in dups:
                dups.append(i)
            seen.add(i)
        if dups:
            out += block(f"split {key!r} repeats ids {dups[:10]}"
                         f"{' …' if len(dups) > 10 else ''}")
    names = list(splits)
    for x in range(len(names)):
        for y in range(x + 1, len(names)):
            both = sorted(set(splits[names[x]]) & set(splits[names[y]]))
            if both:
                out += block(f"splits {names[x]!r} and {names[y]!r} share ids "
                             f"{both[:10]}{' …' if len(both) > 10 else ''}")
    named = sorted({i for ids in splits.values() for i in ids})
    absent = [i for i in named if i not in data_rows]
    if absent:
        out += block(f"split ids not in {data_path!r}: {absent[:10]}"
                     f"{' …' if len(absent) > 10 else ''}")
    twice = [i for i in named if len(data_rows.get(i, [])) > 1]
    if twice:
        out += block(f"split ids that {data_path!r} holds more than once, so their "
                     f"rows are ambiguous: {twice[:10]}")
    if group_col and not absent and not twice:
        groups = {k: {data_rows[i][0].get(group_col) for i in ids}
                  for k, ids in splits.items()}
        for x in range(len(names)):
            for y in range(x + 1, len(names)):
                both = sorted(str(g) for g in groups[names[x]] & groups[names[y]])
                if both:
                    out += block(f"splits {names[x]!r} and {names[y]!r} share "
                                 f"{group_col!r} groups {both[:10]}"
                                 f"{' …' if len(both) > 10 else ''}")
    return out


def check_split_integrity(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-ML-001: a declared train/test split is disjoint and grounded."""
    out: list[Finding] = []
    for path in sorted(p for p in files
                       if p == "splits.json" or p.endswith("/splits.json")):
        out.extend(_split_findings(files, path))
    return out


# --------------------------------------------------------- repro_declared
def check_repro_declared(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-REPRO-001 (advisory): a stochastic increment says how to re-run it."""
    out: list[Finding] = []
    for path, doc in _results_docs(files):
        if doc.get("stochastic") is not True:
            continue
        base = posixpath.dirname(path)
        meta_path = posixpath.join(base, "metadata.yml") if base else "metadata.yml"
        meta = None
        if meta_path in files:
            try:
                meta = yaml.safe_load(files[meta_path].decode("utf-8"))
            except Exception:                              # reported by check_schema
                meta = None
        if not isinstance(meta, dict):
            out.append(Finding(ADVISORY, "CA-REPRO-001", path,
                               "results are declared stochastic but no readable "
                               f"{meta_path} beside them says how to re-run them"))
            continue
        cmd, env, seed = meta.get("command"), meta.get("environment"), meta.get("seed")
        if not (isinstance(cmd, str) and cmd.strip()):
            out.append(Finding(ADVISORY, "CA-REPRO-001", meta_path,
                               "stochastic results, but metadata declares no command"))
        if not ((isinstance(env, str) and env.strip())
                or (isinstance(env, dict) and env)):
            out.append(Finding(ADVISORY, "CA-REPRO-001", meta_path,
                               "stochastic results, but metadata declares no environment"))
        if isinstance(seed, bool) or not isinstance(seed, int):
            out.append(Finding(ADVISORY, "CA-REPRO-001", meta_path,
                               "stochastic results, but metadata declares no integer seed"))
    return out


# ----------------------------------------------------------------- claims
#: test -> (operand keys, predicate over Decimals).
_TESTS: dict[str, tuple[tuple[str, ...], Callable[..., bool]]] = {
    "p_below": (("quantity", "alpha"), lambda p, a: p < a),
    "p_at_least": (("quantity", "alpha"), lambda p, a: p >= a),
    "ci_excludes_zero": (("low", "high"), lambda lo, hi: lo > 0 or hi < 0),
    "ci_contains": (("low", "high", "value"), lambda lo, hi, v: lo <= v <= hi),
    "less_than": (("quantity", "than"), lambda q, t: q < t),
    "greater_than": (("quantity", "than"), lambda q, t: q > t),
    "within": (("quantity", "low", "high"), lambda q, lo, hi: lo <= q <= hi),
}
TESTS = tuple(_TESTS)


def _claim_operand(doc: dict, raw, key: str) -> Decimal:
    if isinstance(raw, str):
        q, why = _lookup(doc, raw)
        if q is None:
            raise _Undecidable(f"operand {key!r} {why}")
        d = _decimal(q.get("value"))
        if d is None:
            raise _Undecidable(f"operand {key!r} names {raw!r}, whose value is not a "
                               "finite number")
        return d
    d = None if isinstance(raw, bool) or not isinstance(raw, (int, float)) else _decimal(raw)
    if d is None:
        raise _Undecidable(f"operand {key!r} must be a number or a quantity name")
    return d


def check_claims(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-STAT-004: declared statistical claims hold over the reported numbers."""
    docs, repeated = _results_scan(files)
    out: list[Finding] = [Finding(BLOCKER, "CA-STAT-004", path,
                                  f"{text}; its claims cannot be decided")
                          for path, doc, text in repeated if "claims" in doc]
    for path, doc in docs:
        if "claims" not in doc:
            continue
        claims = doc["claims"]
        if not isinstance(claims, list):
            out.append(Finding(BLOCKER, "CA-STAT-004", path, "claims must be a list"))
            continue
        for j, claim in enumerate(claims):
            label = f"claims[{j}]"
            try:
                if not isinstance(claim, dict):
                    raise _Undecidable("is not a mapping")
                if isinstance(claim.get("text"), str):
                    label += f" ({claim['text']!r})"
                test = claim.get("test")
                if test not in _TESTS:
                    raise _Undecidable(f"test {test!r} is not one this check can "
                                       f"decide; known: {', '.join(TESTS)}")
                keys, predicate = _TESTS[test]
                missing = [k for k in keys if k not in claim]
                if missing:
                    raise _Undecidable(f"test {test!r} needs {missing}")
                values = [_claim_operand(doc, claim[k], k) for k in keys]
                if test in ("ci_excludes_zero", "ci_contains", "within"):
                    lo, hi = (values[0], values[1]) if test != "within" else values[1:]
                    if lo > hi:
                        raise _Undecidable(f"its interval has low {lo} above high {hi}")
                if not predicate(*values):
                    shown = ", ".join(f"{k}={claim[k]!r}→{v}" for k, v in zip(keys, values))
                    out.append(Finding(BLOCKER, "CA-STAT-004", path,
                                       f"{label} is false: {test} does not hold for "
                                       f"{shown}"))
            except _Undecidable as exc:
                out.append(Finding(BLOCKER, "CA-STAT-004", path,
                                   f"{label} cannot be decided: {exc}"))
    return out


# -------------------------------------------------------------- precision
def _decimal_places(literal: str) -> int | None:
    """Decimal places as WRITTEN: digits after the point minus the exponent.
    Trailing zeros count — they are what a writer uses to claim precision."""
    text = literal.strip().replace("−", "-").lstrip("+-")
    if "," in text or normalise_number(text) is None:
        return None
    mantissa, _, exponent = text.lower().partition("e")
    frac = mantissa.partition(".")[2]
    return max(0, len(frac) - (int(exponent) if exponent else 0))


def check_precision(files: Mapping[str, bytes]) -> list[Finding]:
    """CA-PREC-001 (advisory): no digits beyond what the uncertainty supports."""
    out: list[Finding] = []
    for path, doc in _results_docs(files):
        for i, q in enumerate(_quantities(doc)):
            if not isinstance(q, dict) or "uncertainty" not in q:
                continue
            u = _decimal(q.get("uncertainty"))
            value = q.get("value")
            if u is None or u == 0 or not is_number_shape(value):
                continue
            literal = value if isinstance(value, str) else repr(value)
            places = _decimal_places(literal)
            if places is None:
                continue
            allowed = -abs(u).adjusted() + 1
            if places > allowed:
                out.append(Finding(
                    ADVISORY, "CA-PREC-001", path,
                    f"{_label(q, i)} value {literal} carries {places} decimal places; "
                    f"its uncertainty {q.get('uncertainty')!r} supports at most "
                    f"{max(allowed, 0)}"))
    return out


_BOUNDARY = ("It never judges whether a method is appropriate, whether a derivation "
             "is the right one for the claim, or whether an undeclared quantity "
             "should have been declared.")

register("numeric_validity", check_numeric_validity,
         "Every results.json quantity has a value that is a finite number: an int, a "
         "finite float, or a string holding a plain decimal literal. A missing value, "
         "null, a bool, NaN or Infinity, and a non-numeric string each block. A "
         "results.json that repeats a JSON key anywhere blocks (which value was "
         "meant is ambiguous; the key and its place are named). A "
         "results.json that does not parse is left to schema. It says nothing about "
         "whether a number is correct.")
register("range_rules", check_range_rules,
         "Reads the one ```crossaudit-ranges block in each AUDIT_RULES.md in the "
         "audited scope (a JSON list of {name, unit, min?, max?}); for every "
         "results.json quantity whose name equals or case-sensitively glob-matches "
         "an entry (first match wins, files in path order), the unit must be "
         "byte-equal to the declared unit (no case folding, no whitespace "
         "stripping and no synonym table, unlike number_source: 'kJ/mol', "
         "'kJ mol⁻¹' and 'kJ/mol ' with a trailing space are three different "
         "units, and a quantity carrying the wrong one blocks) and the value must lie within the "
         "inclusive bounds, compared as exact decimals. A malformed block (bad JSON, "
         "a repeated JSON key, an entry without a non-empty name or unit, an entry "
         "key other than name, unit, min and max, a non-numeric bound, min above "
         "max, an unclosed fence, two fences in one file) blocks, and so does a "
         "results.json that repeats a JSON key while ranges are declared. A quantity no entry "
         "matches is not checked, and a project with no block gets nothing: the "
         "ranges are the project's rules, read and never invented. " + _BOUNDARY)
register("derivations", check_derivations,
         "For each row a results.json declares under derivations ({quantity, method, "
         "input, tolerance?}), recomputes the method with the standard library over "
         "the named CSV (path relative to the results.json directory and "
         "normalised; a path that leaves that directory blocks, optional "
         "where filter comparing cells as strings: one {column, equals} clause or "
         "a non-empty list of them, all of which must hold) or over named "
         "quantities, and "
         "blocks if the reported value disagrees under the declared tolerance (abs, "
         "rel relative to the recomputed value, or sig significant figures; default "
         "rel 1e-9). Methods: " + ", ".join(METHODS) + ". sd and sem divide by "
         "n-1; sd_population and sem_population divide by n (numpy's default). "
         "ratio(a, b) is a/b and percent_change(new, old) is 100*(new-old)/|old|; "
         "with a file each operand is a column (or {column, where}) and the "
         "means of the selected rows are used, without one each operand is a "
         "quantity name or a number. t_pvalue_two_sided and scale take quantity "
         "names or numbers only, never columns. Recomputation is IEEE "
         "double arithmetic, so abs and rel are float comparisons and a relative "
         "tolerance below about 1e-14 is not meaningful; sig compares exact "
         "decimal roundings. An unknown method, a missing argument, a file not in "
         "scope, a missing or duplicated column, an empty or non-numeric cell, too "
         "few rows, a filter or file that selects no rows (for every method, "
         "count and sum included), a malformed where clause, a zero divisor, "
         "an uncommitted that is not a boolean, a repeated JSON key in "
         "results.json, an input key the "
         "method does not take (the message names the keys it does take), or a "
         "quantity name "
         "matching no row or several blocks: what cannot be verified is not "
         "verified. A file declared uncommitted (\"uncommitted\": true beside a "
         "non-empty string file, or file \"uncommitted\") and absent is advisory "
         "(CA-DERIV-002); uncommitted true without such a file blocks. In a one-sample or paired form, filter: {column_name: "
         "value} (one column, one value) is read as the where clause it spells "
         "and reported as advisory CA-DERIV-003 with the canonical form; any "
         "other filter, and any key the method does not take, blocks. A row "
         "computed from "
         "quantity operands that agrees, but "
         "reads a quantity no derivation chain recomputes from a committed file, "
         "is advisory (CA-DERIV-003): verified against a reported number, not end "
         "to end. A quantity with no derivation row is not checked. " + _BOUNDARY)
register("split_integrity", check_split_integrity,
         "For every splits.json in the audited scope ({data, id_column, "
         "group_column?, train, test, val? or validation?} and no other key, data "
         "relative to the splits.json directory and inside it): the id lists must be pairwise disjoint, no list "
         "may repeat an id, every id must name exactly one row of the data CSV, and "
         "when group_column is set no group may appear in two lists. Any violation, "
         "or a declaration that cannot be read (including an unknown key, both "
         "val and validation, or a repeated JSON key), blocks. It checks the declared ids "
         "only: it cannot tell whether predictions were actually made on the test "
         "rows, or whether the grouping is the scientifically right one. With no "
         "splits.json it does nothing.")
register("repro_declared", check_repro_declared,
         "Advisory only, never blocks: when results.json says \"stochastic\": true, "
         "the metadata.yml beside it should declare a non-empty command, a non-empty "
         "environment (string or mapping) and an integer seed; each missing key is "
         "one advisory finding. It checks that the keys are declared, not that "
         "running the command reproduces the results.")
register("claims", check_claims,
         "For each claim a results.json declares under claims ({text?, test, "
         "operands}), decides it over the reported numbers as exact decimals: "
         "p_below (quantity < alpha), p_at_least (quantity >= alpha), "
         "ci_excludes_zero (low > 0 or high < 0), ci_contains (low <= value <= "
         "high), less_than (quantity < than), greater_than (quantity > than), "
         "within (low <= quantity <= high). An operand that is a string always names "
         "a quantity; a number is a literal. A false claim, an unknown test, a "
         "missing operand, an operand naming no quantity or several, an interval "
         "with low above high, or a repeated JSON key in a results.json that "
         "declares claims blocks. It decides only the declared comparison; "
         "whether that comparison supports the prose, and whether the statistic was "
         "computed by an appropriate test, is the auditor's question. " + _BOUNDARY)
register("precision", check_precision,
         "Advisory only, never blocks: a results.json quantity with a numeric "
         "uncertainty whose value is written with more decimal places than one "
         "beyond the first significant digit of that uncertainty is reported "
         "(strings as written, floats through repr, so trailing zeros of a float "
         "are invisible). It does not check whether the uncertainty itself is right.")
