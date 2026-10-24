"""Planters: one per (class, variant) in taxonomy.json, each a single-fault edit.

``plant(cls, variant, instance, rng) -> (instance', planted)`` returns a NEW
instance (the clean one is never mutated) and the manifest ``planted`` record:

    {"file": <primary instance-root path>, "files": [<every path that differs>],
     "locator": ..., "before": ..., "after": ...,
     "edits": [<one {file, locator, before, after} per edit>]   # multi-file plants only
    }

Locators are JSON paths (``quantities[2].value``, ``convergence.converged``,
``test[29]``) for JSON files, ``line`` for a one-line text edit (before/after
are the lines or substrings), ``file`` for a deleted file (before is its
sha256), ``move:<from>-><to>`` for an id moved between split lists, and
``regenerated`` for D13 (the data were redrawn and every output recomputed by
the committed analyse.py; before/after are the value of the quantity the
claim turns on). D09 ``nan``/``inf`` record ``after`` as the JSON token text
(``"NaN"``/``"Infinity"``) with ``"after_is_token": true``, because the
manifest itself is strict JSON.

Most planters make exactly one edit to one file. Three kinds touch more than
one file, because the defect cannot be written honestly any other way, and
list every file in ``files``:

* D04 ``revision_mismatch``: ``check_provenance`` raises its advisory only
  when the source is still an exact member of ``inputs`` but carries a
  revision other than ``code_version``. So the plant appends an ``inputs``
  entry ``data/x.csv@<old rev>`` to metadata.yml AND points one quantity's
  source at it.
* D13 (all variants): a false claim must be false AGAINST THE COMMITTED DATA,
  or ``derivations`` would catch the changed number before ``claims`` does.
  So the data column is redrawn under a null (or wrong-scale) effect, the
  committed analysis is re-run (results.json, results.txt, derived CSVs) and
  the SUMMARY is re-rendered from the new numbers, with the declared claim
  left in place.

Applicability (``applicable``) follows taxonomy.json and narrows a class where
the defect needs a feature only some domains have; each narrowing is written
next to its rule.

Honest boundary: a planter edits bytes; whether the edit is the defect a
reviewer would name is what the taxonomy notes argue, not something code here
can establish.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import domains

HERE = Path(__file__).resolve().parent
TAXONOMY = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
CLASSES = {c["id"]: c for c in TAXONOMY["classes"]}
FENCE = "```crossaudit-numbers\n"


def expected_block(cls: str, variant: str, classes: dict | None = None) -> dict:
    """The manifest `expected` block, copied from taxonomy.json: the class's
    tier/rules/checks/severity, then the variant's `variant_tiers` entry, then
    its `variant_overrides` entry (each key optional; an override replaces the
    class value for that key)."""
    c = (classes or CLASSES)[cls]
    block = {"tier": c["tier"], "rules": list(c["rules"]), "checks": list(c["checks"]),
             "severity": c["severity"]}
    if variant in c.get("variant_tiers", {}):
        block["tier"] = c["variant_tiers"][variant]
    for key, value in c.get("variant_overrides", {}).get(variant, {}).items():
        if key in block:
            block[key] = list(value) if isinstance(value, list) else value
    return block


# ---------------------------------------------------------------- helpers

def dump_json(doc) -> bytes:
    """The serialisation analyse.py uses for results.json (so a re-dump of an
    unedited document is byte-identical)."""
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _qindex(doc: dict, name: str) -> int:
    for i, q in enumerate(doc["quantities"]):
        if q["name"] == name:
            return i
    raise KeyError(name)


def _decimals(doc: dict, name: str) -> tuple[int, float]:
    """Decimals a quantity was rounded to, read back from its derivation tolerance."""
    for d in doc.get("derivations", []):
        if d["quantity"] == name:
            tol = d["tolerance"]["abs"]
            return (0 if tol >= 0.5 else round(-math.log10(tol / 6.0)) - 1), tol
    raise KeyError(f"no derivation for {name}")


def _record(file, locator, before, after, files=None, **extra) -> dict:
    rec = {"file": file, "files": sorted(files or [file]), "locator": locator,
           "before": before, "after": after}
    rec.update(extra)
    return rec


def _edit_results(inst, locator_fn):
    """Apply locator_fn(doc) -> (locator, before, after) to results.json."""
    new = inst.copy()
    path = new.path("results.json")
    doc = json.loads(new.files[path])
    locator, before, after = locator_fn(doc)
    new.files[path] = dump_json(doc)
    return new, _record(path, locator, before, after)


def _set_q(name, field, value_fn):
    def fn(doc):
        i = _qindex(doc, name)
        before = doc["quantities"][i][field]
        after = value_fn(before, doc)
        doc["quantities"][i][field] = after
        return f"quantities[{i}].{field}", before, after
    return fn


def _first_q(doc):
    return doc["quantities"][0]["name"]


def _edit_text(inst, rel, old, new_text):
    new = inst.copy()
    path = new.path(rel)
    text = new.files[path].decode("utf-8")
    if text.count(old) != 1:
        raise ValueError(f"{inst.domain}: {old!r} occurs {text.count(old)} times in {rel}")
    new.files[path] = text.replace(old, new_text).encode("utf-8")
    return new, _record(path, "line", old, new_text)


def _drop_meta_key(inst, key):
    text = inst.text("metadata.yml")
    line = next(l for l in text.splitlines(keepends=True) if l.startswith(key + ":"))
    new, rec = _edit_text(inst, "metadata.yml", line, "")
    rec["locator"] = f"metadata.yml:{key}"
    rec["before"], rec["after"] = line.rstrip("\n"), None
    return new, rec


def _split_summary(text):
    i = text.index(FENCE)
    return text[:i], text[i:]


def _block_rows(block):
    body = block[len(FENCE):block.index("\n```", len(FENCE))]
    return json.loads(body)


_TOKEN = r"(?<![\w.\-]){}(?![\w]|\.\d)"


def _token_count(prose, v):
    return len(re.findall(_TOKEN.format(re.escape(v)), prose))


def _replace_token(prose, v, new):
    return re.sub(_TOKEN.format(re.escape(v)), lambda m: new, prose, count=1)


def _swap_digits(v: str) -> str | None:
    """Swap the rightmost pair of adjacent, different digits; never creates a
    leading zero."""
    for i in range(len(v) - 2, -1, -1):
        a, b = v[i], v[i + 1]
        if a.isdigit() and b.isdigit() and a != b:
            lead = i == 0 or (i == 1 and v[0] == "-")
            if lead and b == "0":
                continue
            return v[:i] + b + a + v[i + 2:]
    return None


def _annotated_target(inst):
    """(row index, rows, prose, block) for the first annotated number whose
    value is written once in the prose and has swappable digits, preferring
    non-integers."""
    text = inst.text("SUMMARY.md")
    prose, block = _split_summary(text)
    rows = _block_rows(block)
    order = sorted(range(len(rows)), key=lambda i: ("." not in rows[i]["v"], i))
    for i in order:
        v = rows[i]["v"]
        if _token_count(prose, v) == 1 and _swap_digits(v):
            return i, rows, prose, block
    raise ValueError(f"{inst.domain}: no annotated number to swap")


# ---------------------------------------------------------------- planters

def d01_no_code_version(inst, rng):
    return _drop_meta_key(inst, "code_version")


def d01_no_quantities(inst, rng):
    def fn(doc):
        before = doc.pop("quantities")
        return "quantities", before, None
    return _edit_results(inst, fn)


def d01_inputs_not_path_at_rev(inst, rng):
    text = inst.text("metadata.yml")
    line = next(l for l in text.splitlines(keepends=True) if l.startswith("  - "))
    new, rec = _edit_text(inst, "metadata.yml", line, line.split("@")[0] + "\n")
    rec["locator"] = "metadata.yml:inputs[0]"
    rec["before"], rec["after"] = line.strip()[2:], line.split("@")[0].strip()[2:]
    return new, rec


def d02_empty_unit(inst, rng):
    return _edit_results(inst, lambda doc: _set_q(_first_q(doc), "unit", lambda b, d: "")(doc))


def d02_empty_source(inst, rng):
    return _edit_results(inst, lambda doc: _set_q(_first_q(doc), "source", lambda b, d: "")(doc))


def d03_label_swapped(inst, rng):
    name, unit = domains.get(inst.domain).SPEC["d03"]
    return _edit_results(inst, _set_q(name, "unit", lambda b, d: unit))


def d04_source_not_declared(inst, rng):
    def fn(doc):
        q = doc["quantities"][0]
        before = q["source"]
        path, rev = before.rsplit("@", 1)
        stem, ext = path.rsplit(".", 1)
        q["source"] = f"{stem}_v2.{ext}@{rev}"
        return "quantities[0].source", before, q["source"]
    return _edit_results(inst, fn)


def d04_input_file_missing(inst, rng):
    mod = domains.get(inst.domain)
    path = inst.path(mod.INPUTS[0])
    new = inst.copy()
    data = new.files.pop(path)
    return new, _record(path, "file", hashlib.sha256(data).hexdigest(), None)


def d04_revision_mismatch(inst, rng):
    mod = domains.get(inst.domain)
    stale = f"{mod.INPUTS[0]}@{domains.OLD_REVISION}"
    new = inst.copy()
    meta_path = new.path("metadata.yml")
    text = new.files[meta_path].decode("utf-8")
    anchor = "command:"
    new.files[meta_path] = text.replace(anchor, f"  - {stale}\n{anchor}", 1).encode("utf-8")
    res_path = new.path("results.json")
    doc = json.loads(new.files[res_path])
    before = doc["quantities"][0]["source"]
    doc["quantities"][0]["source"] = stale
    new.files[res_path] = dump_json(doc)
    edits = [{"file": meta_path, "locator": "line", "before": None, "after": f"  - {stale}"},
             {"file": res_path, "locator": "quantities[0].source", "before": before, "after": stale}]
    return new, _record(res_path, "quantities[0].source", before, stale,
                        files=[meta_path, res_path], edits=edits)


def d05_converged_false(inst, rng):
    def fn(doc):
        doc["convergence"]["converged"] = False
        return "convergence.converged", True, False
    return _edit_results(inst, fn)


def d05_achieved_over_threshold(inst, rng):
    def fn(doc):
        c = doc["convergence"]
        before = c["achieved"]
        c["achieved"] = round(c["threshold"] * 1.7, 3)
        return "convergence.achieved", before, c["achieved"]
    return _edit_results(inst, fn)


def d06_annotated_digit_swap(inst, rng):
    i, rows, prose, block = _annotated_target(inst)
    v = rows[i]["v"]
    nv = _swap_digits(v)
    rows[i]["v"] = nv
    new = inst.copy()
    new.files[new.path("SUMMARY.md")] = (_replace_token(prose, v, nv) + domains.numbers_block(rows)).encode("utf-8")
    return new, _record(new.path("SUMMARY.md"), f"prose + crossaudit-numbers[{i}].v", v, nv)


def d06_unannotated_digit_swap(inst, rng):
    i, rows, prose, block = _annotated_target(inst)
    v = rows[i]["v"]
    nv = _swap_digits(v)
    new = inst.copy()
    new.files[new.path("SUMMARY.md")] = (_replace_token(prose, v, nv).rstrip("\n") + "\n").encode("utf-8")
    return new, _record(new.path("SUMMARY.md"), "prose (crossaudit-numbers block removed)", v, nv)


def d06_sign_word_flip(inst, rng):
    old, new = domains.get(inst.domain).SPEC["direction"]
    return _edit_text(inst, "SUMMARY.md", old, new)


def d07_value_negated(inst, rng):
    name = domains.get(inst.domain).SPEC["d07"]
    return _edit_results(inst, _set_q(name, "value", lambda b, d: -b))


def _d08(kind):
    def plant(inst, rng):
        name, value = domains.get(inst.domain).SPEC["d08"][kind]
        return _edit_results(inst, _set_q(name, "value", lambda b, d: value))
    return plant


def _d09(kind):
    def plant(inst, rng):
        def value(before, doc):
            q = doc["quantities"][0]
            return {"nan": float("nan"), "inf": float("inf"), "null": None,
                    "string_value": f"{before} {q['unit']}"}[kind]
        new, rec = _edit_results(inst, lambda doc: _set_q(_first_q(doc), "value", value)(doc))
        if kind in ("nan", "inf"):
            rec["after"] = "NaN" if kind == "nan" else "Infinity"
            rec["after_is_token"] = True
        return new, rec
    return plant


def _d10_perturb(frac):
    def plant(inst, rng):
        doc = inst.results()
        for name in domains.get(inst.domain).SPEC["d10_targets"]:
            v = domains.qvalue(doc, name)
            d, tol = _decimals(doc, name)
            nv = round(v * (1.0 + frac), d)
            if abs(nv - v) > 2 * tol:
                return _edit_results(inst, _set_q(name, "value", lambda b, dd: nv))
        raise ValueError(f"{inst.domain}: no quantity large enough to perturb by {frac}")
    return plant


def d10_wrong_rows_used(inst, rng):
    doc = inst.results()
    for name, raw in domains.get(inst.domain).SPEC["wrong_rows"](inst):
        d, tol = _decimals(doc, name)
        nv = round(raw, d)
        if abs(nv - domains.qvalue(doc, name)) > 2 * tol:
            return _edit_results(inst, _set_q(name, "value", lambda b, dd: nv))
    raise ValueError(f"{inst.domain}: the wrong rows give the reported values")


def _d11(sign):
    def plant(inst, rng):
        name = domains.get(inst.domain).SPEC["n_quantity"]
        return _edit_results(inst, _set_q(name, "value", lambda b, d: b + sign * max(1, round(0.25 * b))))
    return plant


def _splits_edit(inst, fn):
    new = inst.copy()
    path = new.path("splits.json")
    doc = json.loads(new.files[path])
    locator, before, after = fn(doc)
    new.files[path] = (json.dumps(doc, indent=1) + "\n").encode("utf-8")
    return new, _record(path, locator, before, after)


def d12_id_overlap(inst, rng):
    def fn(doc):
        doc["train"].append(doc["test"][0])
        return f"train[{len(doc['train']) - 1}]", None, doc["test"][0]
    return _splits_edit(inst, fn)


def d12_group_overlap(inst, rng):
    def fn(doc):
        moved = doc["test"].pop(0)
        doc["train"].append(moved)
        return f"move:test[0]->train[{len(doc['train']) - 1}]", moved, moved
    return _splits_edit(inst, fn)


def d12_test_id_not_in_data(inst, rng):
    def fn(doc):
        k = len(doc["test"]) - 1
        before = doc["test"][k]
        doc["test"][k] = "c999"
        return f"test[{k}]", before, "c999"
    return _splits_edit(inst, fn)


def d12_duplicate_test_id(inst, rng):
    def fn(doc):
        doc["test"].append(doc["test"][0])
        return f"test[{len(doc['test']) - 1}]", None, doc["test"][0]
    return _splits_edit(inst, fn)


#: The quantity each D13 variant's claim turns on, per domain.
_CLAIM_Q = {"biostat_two_group": "p_value", "crystal_bandgap_ml": "mae_test",
            "nmr_shift_calibration": "slope"}


def _d13(variant):
    def plant(inst, rng):
        mod = domains.get(inst.domain)
        new = mod.regenerate(inst, variant, rng)
        name = _CLAIM_Q[inst.domain]
        doc_before, doc_after = inst.results(), new.results()
        i = _qindex(doc_after, name)
        changed = sorted(p for p in set(inst.files) | set(new.files)
                         if inst.files.get(p) != new.files.get(p))
        return new, _record(new.path("results.json"), f"quantities[{i}].value",
                            domains.qvalue(doc_before, name), domains.qvalue(doc_after, name),
                            files=changed, regenerated=new.path(mod.INPUTS[0]))
    return plant


def d14_prose_method_differs(inst, rng):
    old, new = domains.get(inst.domain).SPEC["method"]
    return _edit_text(inst, "SUMMARY.md", old, new)


def d15_todo_left(inst, rng):
    prose, block = _split_summary(inst.text("SUMMARY.md"))
    line = "TODO: re-check the outlier handling before this goes out.\n"
    new = inst.copy()
    new.files[new.path("SUMMARY.md")] = (prose + line + "\n" + block).encode("utf-8")
    return new, _record(new.path("SUMMARY.md"), "line", None, line.rstrip("\n"))


def d15_template_placeholder(inst, rng):
    i, rows, prose, block = _annotated_target(inst)
    v = rows[i]["v"]
    new = inst.copy()
    new.files[new.path("SUMMARY.md")] = (_replace_token(prose, v, "<VALUE>") + block).encode("utf-8")
    return new, _record(new.path("SUMMARY.md"), "line", v, "<VALUE>")


def d15_summary_truncated_mid_block(inst, rng):
    text = inst.text("SUMMARY.md")
    cut = text.index(FENCE) + len(FENCE) + 25
    new = inst.copy()
    new.files[new.path("SUMMARY.md")] = text[:cut].encode("utf-8")
    return new, _record(new.path("SUMMARY.md"), f"truncated at char {cut}", text[cut:], None)


def _d18_target(inst, variant):
    """(name, value, decimals, tolerance) of the quantity a D18 variant edits."""
    doc = inst.results()
    name = domains.get(inst.domain).SPEC["d18"][variant]
    d, tol = _decimals(doc, name)
    return doc, name, domains.qvalue(doc, name), d, tol


def _d18_set(inst, name, v, nv, tol, why):
    if abs(nv - v) <= 2 * tol:
        raise ValueError(f"{inst.domain}: {why} leaves {name} within its tolerance")
    return _edit_results(inst, _set_q(name, "value", lambda b, dd: nv))


def _d18_column(inst, doc, name):
    """The values a single-column derivation of `name` reads, recomputed here
    from the committed CSV with its declared where filter (one clause or a list)."""
    import csv
    import io
    spec = next(r["input"] for r in doc["derivations"] if r["quantity"] == name)
    where = spec.get("where")
    clauses = [] if where is None else [where] if isinstance(where, dict) else list(where)
    rows = csv.DictReader(io.StringIO(inst.text(spec["file"])))
    return [float(r[spec["x"]]) for r in rows
            if all(r[c["column"]] == str(c["equals"]) for c in clauses)]


def d18_ratio_inverted(inst, rng):
    """The ratio written the wrong way up: b / a reported for a declared a / b."""
    doc, name, v, d, tol = _d18_target(inst, "ratio_inverted")
    return _d18_set(inst, name, v, round(1.0 / v, d), tol, "inverting the ratio")


def d18_percent_sign_flipped(inst, rng):
    """A percent change reported with the opposite sign (old - new over |old|)."""
    doc, name, v, d, tol = _d18_target(inst, "percent_sign_flipped")
    return _d18_set(inst, name, v, -v, tol, "flipping the sign")


def _d18_sd(variant, ddof):
    def plant(inst, rng):
        """The other standard deviation of the same rows: the population sd
        (ddof 0, numpy's default) reported for a declared sample sd, or the
        sample sd (ddof 1) reported for a declared population sd."""
        doc, name, v, d, tol = _d18_target(inst, variant)
        xs = _d18_column(inst, doc, name)
        m = math.fsum(xs) / len(xs)
        alt = math.sqrt(math.fsum((x - m) ** 2 for x in xs) / (len(xs) - ddof))
        return _d18_set(inst, name, v, round(alt, d), tol, f"the ddof={ddof} sd")
    return plant


def d18_median_perturbed_1pct(inst, rng):
    doc, name, v, d, tol = _d18_target(inst, "median_perturbed_1pct")
    return _d18_set(inst, name, v, round(v * 1.01, d), tol, "a 1% perturbation")


def _d16(key):
    def plant(inst, rng):
        return _drop_meta_key(inst, key)
    return plant


def d17_digits_beyond_uncertainty(inst, rng):
    doc = inst.results()
    q = next(q for q in doc["quantities"] if isinstance(q.get("uncertainty"), (int, float)))
    d, _tol = _decimals(doc, q["name"])
    nv = round(q["value"] + 0.0137 * 10 ** -d, d + 4)
    return _edit_results(inst, _set_q(q["name"], "value", lambda b, dd: nv))


PLANTERS = {
    ("D01", "no_code_version"): d01_no_code_version,
    ("D01", "no_quantities"): d01_no_quantities,
    ("D01", "inputs_not_path_at_rev"): d01_inputs_not_path_at_rev,
    ("D02", "empty_unit"): d02_empty_unit,
    ("D02", "empty_source"): d02_empty_source,
    ("D03", "label_swapped"): d03_label_swapped,
    ("D04", "source_not_declared"): d04_source_not_declared,
    ("D04", "input_file_missing"): d04_input_file_missing,
    ("D04", "revision_mismatch"): d04_revision_mismatch,
    ("D05", "converged_false"): d05_converged_false,
    ("D05", "achieved_over_threshold"): d05_achieved_over_threshold,
    ("D06", "annotated_digit_swap"): d06_annotated_digit_swap,
    ("D06", "unannotated_digit_swap"): d06_unannotated_digit_swap,
    ("D06", "sign_word_flip"): d06_sign_word_flip,
    ("D07", "value_negated"): d07_value_negated,
    ("D08", "above_max"): _d08("above_max"),
    ("D08", "below_min"): _d08("below_min"),
    ("D09", "nan"): _d09("nan"),
    ("D09", "inf"): _d09("inf"),
    ("D09", "null"): _d09("null"),
    ("D09", "string_value"): _d09("string_value"),
    ("D10", "value_perturbed_1pct"): _d10_perturb(0.01),
    ("D10", "value_perturbed_10pct"): _d10_perturb(0.10),
    ("D10", "wrong_rows_used"): d10_wrong_rows_used,
    ("D11", "n_inflated"): _d11(+1),
    ("D11", "n_deflated"): _d11(-1),
    ("D12", "id_overlap"): d12_id_overlap,
    ("D12", "group_overlap"): d12_group_overlap,
    ("D12", "test_id_not_in_data"): d12_test_id_not_in_data,
    ("D12", "duplicate_test_id"): d12_duplicate_test_id,
    ("D13", "significance_overclaim"): _d13("significance_overclaim"),
    ("D13", "ci_claim_false"): _d13("ci_claim_false"),
    ("D13", "improvement_claim_false"): _d13("improvement_claim_false"),
    ("D14", "prose_method_differs"): d14_prose_method_differs,
    ("D15", "todo_left"): d15_todo_left,
    ("D15", "template_placeholder"): d15_template_placeholder,
    ("D15", "summary_truncated_mid_block"): d15_summary_truncated_mid_block,
    ("D16", "no_seed"): _d16("seed"),
    ("D16", "no_command"): _d16("command"),
    ("D16", "no_environment"): _d16("environment"),
    ("D17", "digits_beyond_uncertainty"): d17_digits_beyond_uncertainty,
    ("D18", "ratio_inverted"): d18_ratio_inverted,
    ("D18", "percent_sign_flipped"): d18_percent_sign_flipped,
    ("D18", "sd_population_as_sd"): _d18_sd("sd_population_as_sd", 0),
    ("D18", "sd_as_sd_population"): _d18_sd("sd_as_sd_population", 1),
    ("D18", "median_perturbed_1pct"): d18_median_perturbed_1pct,
}


def applicable(cls: str, variant: str, inst) -> bool:
    """Whether (cls, variant) is planted on this clean instance's domain.

    taxonomy.json `domains` first; then the narrowings the defect itself needs:
    D07 where the domain names a non-negative quantity to negate; D10
    `wrong_rows_used` only where there is a split or group column (crystal,
    biostat); D11 where an n-like quantity exists (all six); D12 where a
    splits.json exists; D13 per variant where the domain declares that kind of
    claim (significance_overclaim and ci_claim_false: biostat;
    improvement_claim_false: crystal, and nmr read as "the declared
    calibration-quality claim is false"); D16 only where results.json says
    `"stochastic": true` (the check is gated on it), which is every domain
    except dft_convergence; D17 where a quantity carries numeric uncertainty
    (all six); D18 per variant where the domain's SPEC names the aggregate it
    reports (ratio and percent change: crystal, biostat; a declared sample sd:
    biostat; a declared population sd: xrd; a median: biostat, xrd).
    """
    c = CLASSES[cls]
    if c["domains"] != "all" and inst.domain not in c["domains"]:
        return False
    spec = domains.get(inst.domain).SPEC
    doc = inst.results()
    if cls == "D07":
        return bool(spec.get("d07"))
    if cls == "D10" and variant == "wrong_rows_used":
        return spec.get("wrong_rows") is not None
    if cls == "D11":
        return bool(spec.get("n_quantity"))
    if cls == "D12":
        return bool(spec.get("has_split"))
    if cls == "D13":
        return variant in spec.get("d13", [])
    if cls == "D16":
        return doc.get("stochastic") is True
    if cls == "D18":
        return variant in spec.get("d18", {})
    if cls == "D17":
        return any(isinstance(q.get("uncertainty"), (int, float)) for q in doc["quantities"])
    return True


def plant(cls: str, variant: str, inst, rng):
    """Plant one defect; returns (new instance, planted record, expected block)."""
    new, rec = PLANTERS[(cls, variant)](inst, rng)
    changed = sorted(p for p in set(inst.files) | set(new.files) if inst.files.get(p) != new.files.get(p))
    if changed != rec["files"]:
        raise AssertionError(f"{inst.domain} {cls}/{variant}: changed {changed}, recorded {rec['files']}")
    return new, rec, expected_block(cls, variant)
