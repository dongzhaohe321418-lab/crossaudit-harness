"""number → source: the span a generator QUOTES must resolve and contain the number.

`docs/design/PROVENANCE_CHECKS.md` §2.1/§3.1/§3.4 and
`docs/design/PROVENANCE_ADDRESSING.md` §2, on the right side of D155: the
generator names a locator, code opens the file and looks, and nothing anywhere
asks a model what the evidence says.

Since D159 the locator is **content**, not a line number: `src` is
`{"file": …, "quote": …}`, the quote is characters copied from one line of that
file, and there is no cap on its length. The generator is never shown line
numbers, so under the old contract it could not address the lines it was asked
for — Arm 2 blocked 24 of 24 drafts on that alone. A row that still carries the
old `at` field is accepted and its `at` is ignored.

D64 — a guard is specified with the mutation that reddens it, and each docstring
below names its own (`tests/test_repair_guard.py:3-7`). One test is the
exception that proves the rule: `test_the_quote_and_not_the_file_is_what_is_checked`
asserts its mutation goes **green**, because a check that still passed with the
quote widened to the whole file would be checking nothing the design measured.

The fixture is the real shape §4 asks for: a RECIPE.md whose value is on L11, an
explanation.md quoting L11, and the wrong-place case quoting L12 — the line the
value is NOT on, in the file it IS in.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.dcl import numbers
from crossaudit.dcl.framework import ADVISORY, BLOCKER, run_checks

#: L11 holds the values; L12 is a neighbouring line of the same file that does
#: not. Both numbers are in the file, so a file-scoped check cannot tell them
#: apart — which is the whole point of §6's 27.7% / 0.0% measurement.
RECIPE = "\n".join([
    "# Synthesis recipe",                       # L1
    "",                                         # L2
    "## Reagents",                              # L3
    "- barium carbonate",                       # L4
    "- titanium dioxide",                       # L5
    "",                                         # L6
    "## Steps",                                 # L7
    "1. Grind the powders under ethanol.",      # L8
    "2. Dry at 80 °C overnight.",               # L9
    "",                                         # L10
    "3. Calcine at 950 °C for 1 hour.",         # L11
    "4. Cool to 25 °C in the furnace.",         # L12
    "",                                         # L13
]) + "\n"

RECIPE_PATH = "work/synthesis/RECIPE.md"
DRAFT_PATH = "work/explanation.md"


def draft(rows: list[dict], prose: str = "Calcined at 950 °C for 1 h.") -> bytes:
    body = json.dumps(rows, ensure_ascii=False)
    return (f"# Explanation\n\n{prose}\n\n"
            f"```crossaudit-numbers\n{body}\n```\n").encode()


#: The two lines the fixtures quote, byte for byte out of RECIPE above. L11
#: holds the pair; L12 is its neighbour, in the same file, and does not.
L11 = "3. Calcine at 950 °C for 1 hour."
L12 = "4. Cool to 25 °C in the furnace."


def cite(quote, file=RECIPE_PATH, **extra) -> dict:
    """A contract-B locator: a file, and characters copied from one of its
    lines. `extra` carries the optional `sha` pin, and nothing else is read."""
    return {"file": file, "quote": quote, **extra}


def row(value="950", unit="°C", src=None) -> dict:
    return {"v": value, "u": unit, "src": cite(L11) if src is None else src}


def increment(*rows: dict, recipe: str = RECIPE) -> dict[str, bytes]:
    return {RECIPE_PATH: recipe.encode(), DRAFT_PATH: draft(list(rows))}


def findings(files: dict[str, bytes]):
    return run_checks(files, ["number_source"]).findings


def science_with_numbers() -> list[str]:
    """The science pack, which carries `number_source` since D164 ruling 1.

    Between D158 ruling 1 and D164 the profile did not carry the check, and this
    helper composed the pack with it by name; the tests below exercise that
    composition because the defects they guard were found where `provenance`
    and `number_source` read the same `results.json` in the same run. It now
    returns the resolved profile itself and asserts the check is in it, so a
    ruling that took the check out again would redden every caller here rather
    than silently list it twice."""
    from crossaudit.dcl.profiles import resolve

    checks = resolve("science")
    assert "number_source" in checks          # D164 ruling 1; the pack carries it
    return checks


# ------------------------------------------------------------- the seven (1/7)
def test_a_locator_naming_the_wrong_line_is_a_blocker():
    """MUTATION (§4 row 1, under contract B): quote L12 instead of L11, where
    the value lives on L11. Both quotations are in the file and only one holds
    the pair, so this is the same discrimination the line contract bought,
    bought by copying instead of counting. The check must raise CA-NUM-002 —
    and the finding must not name the rule id in its own words, because the
    activity stream shows the observation (ACTIVITY_STREAM.md rule 12,
    PROVENANCE_CHECKS.md §7).

    The address the observation opens with is DERIVED (`_derive_at`), never
    asked of the generator: the draft says "950 °C" on its own line 3 and code
    can read that for itself."""
    good = findings(increment(row(src=cite(L11))))
    assert good == [], "the annotation that quotes the right line must pass"

    bad = findings(increment(row(src=cite(L12))))
    assert len(bad) == 1
    f = bad[0]
    assert f.severity == BLOCKER and f.rule == "CA-NUM-002"
    assert f.artifact == DRAFT_PATH
    assert f.observation == (
        "line 3 quotes '4. Cool to 25 °C in the furnace.' from "
        'work/synthesis/RECIPE.md — "950 °C" is not in it')
    assert "CA-NUM" not in f.observation and "number_source" not in f.observation


# ------------------------------------------------------------- the seven (2/7)
def test_the_unit_synonym_table_is_load_bearing(monkeypatch):
    """MUTATION (§4 row 2): delete the unit-synonym table. The `hours`/`h`
    fixture reddens — the draft writes "1 h" where L11 says "1 hour", the right
    line, and the annotation becomes a spurious non-overridable blocker.

    §6 measured this as 8 of 373 traceable numbers (2.1%), over the >2% kill
    condition on its own, which is why the table is code and not a footnote."""
    hours = row(value="1", unit="h", src=cite(L11))
    assert findings(increment(hours)) == []

    monkeypatch.setattr(numbers, "SYNONYMS", {})
    reddened = findings(increment(hours))
    assert [f.rule for f in reddened] == ["CA-NUM-002"]


# ------------------------------------------------------------- the seven (3/7)
def test_the_quote_and_not_the_file_is_what_is_checked(monkeypatch):
    """MUTATION (§4 row 3, under contract B): widen the quote lookup to the
    whole file. The wrong-quote fixture goes **GREEN**, and this test asserts
    that green.

    It is the only guard here that proves something by passing. §6 measured a
    wrong *file* containing the claimed pair 27.7% of the time (596/2150) and a
    wrong *line* 0.0% (0/1825); if the check still blocked with `_quote_span`
    widened, the quotation would not be what is doing the work and the whole
    contract could have named files. The fixture quotes L12, which holds
    "25 °C" and not the pair; the pair is on L11, elsewhere in the same file.
    Quote-scoped that is a blocker, file-scoped it is a pass, and the difference
    between those two readings is the entire contract — which is also why the
    quote must lie within one line now that D159 has removed the length cap: a
    quotation allowed to run across line breaks is a file-scoped citation
    wearing a span's clothes."""
    wrong_line = increment(row(src=cite(L12)))
    assert [f.rule for f in findings(wrong_line)] == ["CA-NUM-002"]

    monkeypatch.setattr(                                        # the mutation
        numbers, "_quote_span",
        lambda text, quote: (numbers._Located(text, ((0, len(text)),)), 1))
    assert findings(wrong_line) == [], (
        "with the quote widened to the whole file the wrong line passes; that "
        "is the coincidence rate the quote scoping exists to remove")


# ------------------------------------------------------------- the seven (4/7)
def test_a_locator_that_does_not_resolve_is_a_blocker():
    """MUTATION (§3.1): drop the existence half — stop requiring that the path
    be a key of `files` and that the line range be inside it. Each fixture here
    then stops raising CA-NUM-001: the unresolvable path reaches the mapping
    lookup and raises `KeyError` out of `run_checks` rather than reporting, and
    the out-of-range and non-span cases pass. Both are the same defect — a
    citation to a location nobody committed stops being a finding.

    CA-NUM-001 is 'the FILE is not there, or the row cannot be read';
    CA-NUM-002 is 'the file is there and the quotation does not land'. Keeping
    them apart is what lets the stream say which of the two happened without
    printing either id — and under content addressing the quote is the span, so
    a quotation the file does not hold is a wrong span (CA-NUM-002, next test)
    and not a missing file."""
    absent = findings(increment(row(src=cite(L11, file="work/synthesis/MISSING.md"))))
    assert [(f.severity, f.rule) for f in absent] == [(BLOCKER, "CA-NUM-001")]
    assert "not in the audited scope" in absent[0].observation

    no_quote = findings(increment(row(src={"file": RECIPE_PATH})))
    assert [f.rule for f in no_quote] == ["CA-NUM-001"]
    assert "with no quotation" in no_quote[0].observation

    no_file = findings(increment(row(src={"quote": L11})))
    assert [f.rule for f in no_file] == ["CA-NUM-001"]
    assert "with no file" in no_file[0].observation

    # The old line-addressed locator is a string, and it is refused rather than
    # parsed: two grammars under one check name is two contracts.
    not_a_citation = findings(increment(row(src=f"{RECIPE_PATH}#L11")))
    assert [f.rule for f in not_a_citation] == ["CA-NUM-001"]
    assert "not a file and a quotation from it" in not_a_citation[0].observation


# ------------------------------------------------------------- the seven (5/7)
def test_uncited_is_advisory_and_an_unannotated_number_is_nothing():
    """MUTATION (§3.4): make `uncited` a blocker, or start reporting numbers
    that carry no annotation row. Either reddens this test, and either would be
    the product refusing to state a well-known constant — 13.3% of real draft
    numbers (57/430) are melting points and ionic radii that occur in no source.

    `uncited` is the generator declining to name a location: a fact about the
    annotation, never a claim about the world. And these checks enforce DECLARED
    provenance, not coverage, so a document with no fence passes vacuously
    (A4's shipped rule, `dcl/provenance.py:19-20`)."""
    result = run_checks(increment(row(src="uncited")), ["number_source"])
    assert result.hard_failures == 0
    assert [(f.severity, f.rule) for f in result.findings] == [(ADVISORY, "CA-NUM-003")]

    vacuous = {RECIPE_PATH: RECIPE.encode(),
               DRAFT_PATH: "# Explanation\n\nCalcined at 950 °C for 1 h.\n".encode()}
    assert run_checks(vacuous, ["number_source"]).findings == []


def test_an_uncited_row_is_advisory_whatever_else_the_row_says():
    """MUTATION (D158 ruling 1, §3.4): validate `at` FIRST — put the `at is
    None` blocker back above the `uncited` branch, which is where it stood
    until this hotfix (`numbers.py:406-421`). This test then reddens on its
    first assertion: the row becomes a non-overridable CA-NUM-001 BLOCKER.
    Run against the full suite, moving ONLY the address blocker back above the
    branch is **1 failed, 3274 passed, 8 skipped**, and the one is this node:

        tests/test_number_source_check.py::
            test_an_uncited_row_is_advisory_whatever_its_own_address_says

    Arm 2 measured that defect on real drafts: 6 of its 215 generator-written
    rows declined to name any evidence and blocked anyway, because they
    miscounted the lines of their own artefact
    (`benchmarks/expertlongbench/RESULTS-ARM2.md` §3). `PROVENANCE_CHECKS.md`
    §2.1 and §3.4 both say `uncited` never blocks; the code said otherwise, and
    the ordering was the defect. A row that names no source hands this layer
    nothing to open, so there is nothing in it that can fail.

    RETIRED WITH D159, and named here rather than deleted: the third assertion
    used to be "the identical malformed `at` on a row that DOES name a source is
    still a blocker", and there is no such branch any more. `at` is not read by
    anything — `_at_span` and `_AT` are gone from the module — so a row cannot
    be blocked on it, and the ordering defect it guarded cannot recur. What the
    generator writes beside `uncited` is now junk this check ignores, and the
    assertions below say exactly that: a legacy `at`, an impossible legacy `at`,
    an unknown key, `uncited` is ADVISORY through all of them.

    Advisory is not silence, and the value half still asserts that (next test):
    whatever the row got wrong that this layer can still read is reported inside
    the same ADVISORY, so the auditor and the person see it."""
    for extra in ({}, {"at": "#L999"}, {"at": "#L0"}, {"at": 7}, {"nonsense": []}):
        rows = [{"v": "950", "u": "°C", "src": "uncited", **extra}]
        body = json.dumps(rows, ensure_ascii=False)
        four_line = f"# E\n```crossaudit-numbers\n{body}\n```"
        assert four_line.count("\n") + 1 == 4, "the fixture must be the 4-line draft"

        result = run_checks({DRAFT_PATH: four_line.encode()}, ["number_source"])
        assert result.hard_failures == 0, extra
        assert [(f.severity, f.rule) for f in result.findings] == [
            (ADVISORY, "CA-NUM-003")], extra
        assert all(f.severity != BLOCKER for f in result.findings), extra
        assert "names no source" in result.findings[0].observation, extra
        # It is not repeated back either: `at` is ignored, not reported.
        assert "at" not in result.findings[0].observation.split("names")[0]

    assert not hasattr(numbers, "_at_span") and not hasattr(numbers, "_AT")


def test_an_uncited_row_never_blocks_on_a_value_it_could_not_transcribe():
    """MUTATION (D158 ruling 1): leave the value blockers — the empty-`v` arm of
    the CA-NUM-001 guard and the `normalise_number` refusal — above the
    `uncited` branch. Each row here goes from ADVISORY to BLOCKER, and the
    design's one disposition for a row that names no source (§3.4: ADVISORY,
    counted, carried to the auditor) is again contradicted by the field beside
    it, which is the shape of the defect Arm 2 found in `at`. Run against the
    full suite, moving ONLY the value blockers back above the branch is
    **1 failed, 3274 passed, 8 skipped**, and the one is this node:

        tests/test_number_source_check.py::
            test_an_uncited_row_never_blocks_on_a_value_it_could_not_transcribe

    It is a separate mutation from the address one above and reddens a separate
    node — moving the address blocker alone leaves this test green, so the two
    guards are not substitutes for one another.

    A row naming no source gives this layer nothing to open and nothing to look
    for; there is no comparison it can fail. What it got wrong is still said, in
    the advisory's own text."""
    for value, expected in [("", "it transcribes no number"),
                            ("about 950", "which is not a number")]:
        rows = [{"v": value, "u": "°C", "src": "uncited"}]
        result = run_checks(increment(*rows), ["number_source"])
        assert result.hard_failures == 0, value
        assert [(f.severity, f.rule) for f in result.findings] == [
            (ADVISORY, "CA-NUM-003")], value
        assert expected in result.findings[0].observation, value

    # And a row that names a source is refused for the same value, unchanged.
    cited = [{"v": "about 950", "u": "°C", "src": cite(L11)}]
    assert [f.rule for f in findings(increment(*cited))] == ["CA-NUM-001"]


# ------------------------------------------------------------- the seven (6/7)
def test_the_check_is_registered_and_selectable_and_in_the_science_profile_only():
    """MUTATION (D164 ruling 1): take `number_source` out of
    `dcl.PROFILES["science"]` — this node and `test_check_profiles.py`'s science
    test redden. Or, in the other direction, unregister it: the `available()`
    assertion reddens and the fenced run below raises `ConfigDenial` before its
    assertion is reached; the explicit-list `resolve` assertion does NOT
    detect that mutation, because `resolve` passes an explicit list through
    without checking registration (the second review executed all three).

    **What this node does NOT detect, stated so the docstring does not
    overclaim (AGENTS.md §3.5):** it reads `dcl.profiles` only. Taking the check
    out of `scaffold.SCIENCE_CHECKS` alone leaves it green; that list is held
    by `test_a_fresh_science_project_is_told_about_numbers` (which asserts the
    two lists equal and scaffolds a project), by
    `test_projects_ui.py::test_browser_creation_can_explicitly_choose_the_science_contract`
    and by `test_constitution_moment.py::test_an_explicit_profile_is_honoured`.
    The two lists are separate objects and each needs a test that names it.

    History, because the list has moved twice: §4 row 7 shipped the check in
    both profiles on 2026-09-06; Arm 2 (`RESULTS-ARM2.md`) then found **0 of
    215 rows passed, 24 of 24 drafts BLOCKED** — the generator is never shown
    line numbers and could not address them — and D158 ruling 1 took it out the
    same day, keeping it selectable by name. D159 replaced line numbers with
    content addressing; D160 licensed five containment extensions, each
    measured on a frozen gold at W = 0 (slices 4–8); Arm 5 (`RESULTS-ARM5.md`)
    then measured the shipped check on every T03 instance at **4 of 398 correct
    annotations blocked, Wilson 0.39–2.56%**, the preregistered §8g PASS band,
    and D164 ruling 1 put it back into the science list — both lists together,
    so a science project gets the check, the skill and the blocker at once.
    `general` and `research` are untouched. The opt-in `science-ai4s` profile
    is `science` plus the AI4S declaration pack, so it carries the check too and
    the membership loop below admits exactly those two names."""
    from crossaudit.dcl.framework import available
    from crossaudit.dcl.profiles import PROFILES, resolve

    assert resolve("science") == ["schema", "units", "convergence", "provenance",
                                  "number_source"]
    assert resolve("research") == ["parseable", "declared", "internal", "complete",
                                   "source_provenance"]
    # `science-ai4s` is `science` plus the AI4S pack (benchmarks/ai4s/DESIGN.md
    # §4), so it carries the check by construction; every other profile still
    # must not.
    for name, checks in PROFILES.items():
        assert ("number_source" in checks) == (name in ("science", "science-ai4s")), name

    # Registered, described, and it still runs when it is asked for by name.
    assert "number_source" in available()
    assert resolve(["schema", "number_source"]) == ["schema", "number_source"]
    assert findings(increment(row(src=cite(L12))))[0].rule == "CA-NUM-002"


# ------------------------------------------------------------- the seven (7/7)
def test_a_science_project_citing_a_nonexistent_input_is_blocked():
    """MUTATION (§1): remove the existence loop at the head of `check_provenance`.
    A science project whose metadata.yml names a missing input and whose
    results.json cites it passes — membership alone asserts that the source is an
    exact MEMBER of the inputs list and never opens the file, so a name that
    names nothing satisfies a check called provenance.

    It lives in `check_provenance` rather than in the neutral pack's `declared`,
    which was the first attempt and was wrong: `check_declared` reads every
    YAML's `sources`, `requires` and `depends_on` as filenames too, so bringing
    it into `science` turned `sources: [doi:10.1234/x]` and
    `requires: [python>=3.11]` into non-overridable blockers on correct work.
    `inputs` is the one key `check_schema` already defines as `path@revision`,
    which is why existence is a fact there and a guess everywhere else."""
    from crossaudit.dcl.profiles import resolve

    meta = b"code_version: v3\ninputs:\n  - data/runs.csv@v3\n"
    results = json.dumps({
        "quantities": [{"name": "yield", "value": 0.42, "unit": "1",
                        "source": "data/runs.csv@v3"}],
        "convergence": {"converged": True}}).encode()
    absent_input = {"experiments/e1/metadata.yml": meta,
                    "experiments/e1/results.json": results}

    blocked = run_checks(absent_input, resolve("science"))
    assert [(f.severity, f.rule) for f in blocked.findings] == [(BLOCKER, "CA-DATA-003")]
    assert "not in the audited scope" in blocked.findings[0].observation

    # The same project with the input actually committed passes, so the guard is
    # the missing file and not the revision suffix — `path@revision` inputs must
    # keep working, which is the whole reason this is scoped to `inputs`.
    present = dict(absent_input, **{"experiments/e1/data/runs.csv": b"yield\n0.42\n"})
    assert run_checks(present, resolve("science")).hard_failures == 0

    # And the keys that are NOT filenames stay out of it: legitimate science
    # metadata must not become a blocker for naming a DOI or a version range.
    legitimate = dict(present, **{"experiments/e1/metadata.yml":
                                  meta + b"sources:\n  - doi:10.1234/example\n"
                                         b"requires:\n  - python>=3.11\n"})
    assert run_checks(legitimate, resolve("science")).findings == []


# ------------------------------------------------------- the rest of the shape
def test_a_pinned_sha_still_resolves_and_a_stale_one_still_blocks():
    """MUTATION: ignore the declared `sha`. A byte-pinned citation stops meaning
    anything and an annotation survives the file changing underneath it.

    RETIRED WITH D159, the first half of the old test: `#L9-L12`, a citation to
    a RANGE of lines. A quotation is a run of one line by contract now, so there
    is no multi-line fence locator left to resolve; the range parser lives on
    for the `results.json` source, where a deterministic producer writes it, and
    is exercised by
    `test_provenance_accepts_only_a_line_fragment_and_nothing_else`.

    The pin keeps the grammar `PROVENANCE_ADDRESSING.md` §B.1 kept for it — a
    sha256 or a prefix of at least 8 hex characters — and a pin that is not one
    is a malformed row rather than a silently ignored field, which is the mirror
    case for the clause that reads it (D157 rule 3)."""
    import hashlib

    sha = hashlib.sha256(RECIPE.encode()).hexdigest()
    assert findings(increment(row(src=cite(L11, sha=sha)))) == []
    assert findings(increment(row(src=cite(L11, sha=sha[:12])))) == []
    assert findings(increment(row(src=cite(L11, sha=sha[:12].upper())))) == []

    stale = findings(increment(row(src=cite(L11, sha="0" * 12))))
    assert [f.rule for f in stale] == ["CA-NUM-001"]
    assert "not the ones the annotation pinned" in stale[0].observation

    for unusable in ("", "abc", "zz" * 8, 12, sha + "0"):
        bad = findings(increment(row(src=cite(L11, sha=unusable))))
        assert [f.rule for f in bad] == ["CA-NUM-001"], unusable
        assert "sha256 prefix" in bad[0].observation, unusable


def test_a_computed_locator_is_still_resolved_and_still_read():
    """MUTATION: pass `computed:` through unverified. Every blocker in this
    module becomes evadable by four characters of prefix.

    §3.1 defers `computed:` to §3.2, but only for the CAUSAL half — whether a
    script produced the value is figure_code's question. That the named span
    holds it is this check's, and it is answerable today."""
    ok = findings(increment(row(src=cite(L11, file=f"computed:{RECIPE_PATH}"))))
    assert ok == []
    bad = findings(increment(row(src=cite(L12, file=f"computed:{RECIPE_PATH}"))))
    assert [f.rule for f in bad] == ["CA-NUM-002"]


def test_a_governed_locator_is_advisory_because_the_bytes_are_not_kept():
    """MUTATION: pass a `governed:` locator in silence. The check then reports
    'verified' over evidence it never read.

    §1.2: the broker copies only a tool's declared `evidence_fields` into the
    ledger and `web_fetch`'s text is not among them, so no code in this project
    can re-read a fetched source. Saying so is honest; passing quietly is not."""
    result = run_checks(increment(row(src='governed:' + 'a' * 64 + '#"950 °C"')),
                        ["number_source"])
    assert result.hard_failures == 0
    assert [(f.severity, f.rule) for f in result.findings] == [(ADVISORY, "CA-NUM-003")]
    assert "does not keep" in result.findings[0].observation


@pytest.mark.parametrize("body", [
    "not valid json",
    '{"v": "950"}',
    '[{"v": "950", "u": "°C"}]',
    '["950 °C at RECIPE.md#L11"]',
])
def test_a_malformed_annotation_block_is_a_blocker(body):
    """MUTATION: skip a row whose shape is wrong instead of blocking on it. A
    generator that emits `[{"v": "950"}]` for every number then satisfies the
    check while naming nothing at all — the silent-pass failure §5.4 names."""
    files = {RECIPE_PATH: RECIPE.encode(),
             DRAFT_PATH: f"# E\n\n950 °C\n\n```crossaudit-numbers\n{body}\n```\n".encode()}
    out = findings(files)
    assert out and all(f.severity == BLOCKER and f.rule == "CA-NUM-001" for f in out)


def test_a_span_locator_relative_to_the_annotating_file_resolves():
    """MUTATION: resolve only exact keys. An artefact citing a sibling by its
    own directory's name is blocked for naming the file correctly."""
    assert findings(increment(row(src=cite(L11, file="synthesis/RECIPE.md")))) == []


def test_a_results_source_may_name_a_span_and_old_values_keep_passing():
    """MUTATION (§2.1): drop the `#` fragment strip in `check_provenance`. Every
    `path@revision#L14` source becomes CA-DATA-003 for not being an exact member
    of the inputs list, and the widening stops being additive.

    Both directions are asserted, because 'additive' is a claim about the values
    already committed, not only about the new ones."""
    meta = b"code_version: v3\ninputs:\n  - runs.csv@v3\n"
    csv = b"yield\n0.42\n"

    def project(source: str) -> dict[str, bytes]:
        return {"experiments/e1/metadata.yml": meta,
                "experiments/e1/runs.csv": csv,
                "experiments/e1/results.json": json.dumps({
                    "quantities": [{"name": "yield", "value": 0.42, "unit": "1",
                                    "source": source}],
                    "convergence": {"converged": True}}).encode()}

    assert run_checks(project("runs.csv@v3"), ["provenance"]).findings == []
    assert run_checks(project("runs.csv@v3#L2"), ["provenance"]).findings == []
    assert run_checks(project("runs.csv@v3#L2-L4"), ["provenance"]).findings == []

    undeclared = run_checks(project("other.csv@v3#L2"), ["provenance"])
    assert [f.rule for f in undeclared.findings] == ["CA-DATA-003"]


def test_the_check_is_registered_with_a_contract_and_wants_no_context():
    """MUTATION: register it with `wants_context=True`. The runner then calls it
    `fn(files, ctx)` and every caller that builds no context has to be widened —
    a kernel edit this check does not need, because it reads committed bytes and
    nothing about the run."""
    from crossaudit.dcl.framework import _WANTS_CONTEXT, available, contracts

    assert "number_source" in available()
    assert _WANTS_CONTEXT["number_source"] is False
    contract = contracts(["number_source"])["number_source"]
    assert "span" in contract and "never coverage" in contract
    assert "correct" in contract          # it says out loud what it does not do


NUMBERS_SKILL = "skills/provenance-numbers.md"
SOURCES_SKILL = "skills/provenance-sources.md"


def test_a_project_whose_checks_read_an_annotation_ships_the_skill_that_asks_for_one():
    """MUTATION (§5.4): stop writing the skill when the check list contains one
    of the annotation checks. `number_source` and `source_provenance` both read
    a block the GENERATOR emits, and nothing in `generator.py` or the
    Constitution asks for one — so the check would pass every document while
    appearing to guard it, which is worse than not having it. `general` enables
    neither and must get no such file.

    It travels the shipped channel and no other: a committed `skills/*.md` that
    `skills.load` reads, `skills.render` puts in the generator prompt, and the
    receipt hashes — never the auditor's prompt, and never a new channel."""
    from crossaudit import skills as skills_mod
    from crossaudit.scaffold import (GENERAL_CHECKS, SCIENCE_CHECKS,
                                     annotation_skill_tree)
    from crossaudit.dcl.profiles import PROFILES

    # The science pack carries `number_source` (D164 ruling 1), so a science
    # project is handed the numbers skill with the check; `general` enables no
    # annotation check and gets no such file. The gate is the check list, read
    # here rather than assumed.
    assert annotation_skill_tree(GENERAL_CHECKS) == {}
    for checks in (SCIENCE_CHECKS, PROFILES["science"], ["number_source"]):
        assert NUMBERS_SKILL in annotation_skill_tree(checks), checks
    assert sorted(annotation_skill_tree(PROFILES["research"])) == [SOURCES_SKILL]

    body = annotation_skill_tree(["number_source"])[NUMBERS_SKILL]
    # It tells the generator to transcribe and to locate. It must never ask it
    # to assess (D155).
    assert "```crossaudit-numbers" in body
    assert "uncited" in body and '"quote"' in body
    # The FENCE asks for no line number and no `at` — that is the whole of D159
    # ruling 1 on the generator's side: an address the model is never shown is
    # an address it cannot give, and Arm 2 blocked 24 of 24 drafts proving it.
    fence, _, structured = body.partition("## The one place a line number")
    assert "#L" not in fence and '"at"' not in fence
    # And the `results.json` source, which is NOT that interface, keeps the
    # sentence that describes it: a deterministic producer wrote that file and
    # knows which line it read, the check still verifies the fragment, and a
    # skill that stopped mentioning it would leave a live interface unwritten.
    assert "runs.csv@v3#L14" in structured
    assert structured.count("#L") == 1 and "Never write a line number" in structured
    assert "you name a location, you never say what is at it" in body.lower()
    # And it says the unit is compared whole, because a half-transcribed
    # compound unit is now a blocker and the generator has to be told.
    assert "in full" in body and "°C/min" in body

    # It is a legal skill: front matter parses, size is inside the bound, and it
    # renders into the generator block rather than anywhere else.
    skill = skills_mod._parse(body, "provenance-numbers", NUMBERS_SKILL)
    assert len(body.encode()) < skills_mod.MAX_SKILL_BYTES
    assert "crossaudit-numbers" in skills_mod.render([skill])

    # It carries NO `applies_to`, and that is the fix and not an oversight. A
    # round that has written nothing yet selects skills against `cfg.scope_dirs`
    # (`cli/build.py:794`), which is `["experiments"]` — a bare directory name
    # that matches neither `experiments/` nor `work/`, so a freshly scaffolded
    # project's FIRST generation carried no provenance instruction at all and
    # every document passed `number_source` vacuously.
    assert skill.applies_to == ()
    for touched in (["experiments"], ["work"], [], ["experiments/demo/x.md"]):
        assert skills_mod.select([skill], touched) == [skill], touched


@pytest.mark.parametrize("checks,files", [
    (["number_source"], [NUMBERS_SKILL]),
    (["source_provenance"], [SOURCES_SKILL]),
    (["parseable", "declared", "internal", "complete", "source_provenance",
      "number_source"], [NUMBERS_SKILL, SOURCES_SKILL]),
])
def test_the_skill_only_instructs_for_checks_the_project_actually_runs(checks, files):
    """MUTATION: ship one combined file for either check.

    A project configured with only `source_provenance` was handed the whole
    number-annotation contract for a fence nothing would ever read — guidance
    describing a check the project does not have, and output the generator pays
    for every round. One FILE per check, so each can also be gated later."""
    from crossaudit.scaffold import annotation_skill_tree

    assert sorted(annotation_skill_tree(checks)) == sorted(files)
    for path, body in annotation_skill_tree(checks).items():
        assert ("```crossaudit-numbers" in body) is (path == NUMBERS_SKILL)
        assert ("```crossaudit-sources" in body) is (path == SOURCES_SKILL)
        assert "you name a location, you never say what is at it" in body.lower()


def test_a_retained_skill_stops_being_delivered_when_its_check_is_turned_off():
    """MUTATION: drop `requires_check` from the template, or drop the `checks=`
    argument at `cli/build.py:794`.

    Composition happens once, at scaffold time. Turn `number_source` off a month
    later and the committed file is still in `skills/`, still selected, still in
    every generator prompt — describing a fence nothing will read and charging
    for it every round. The gate has to be read on every selection, so it lives
    in the file's own front matter and `skills.select` honours it.

    `checks=None` still selects everything: a person's own hand-written skill
    has no `requires_check`, and an unknown answer must never remove guidance."""
    from crossaudit import skills as skills_mod
    from crossaudit.scaffold import annotation_skill_tree

    tree = annotation_skill_tree(["number_source", "source_provenance"])
    house = [skills_mod._parse(body, path.rsplit("/", 1)[-1][:-3], path)
             for path, body in sorted(tree.items())]
    assert [s.requires_check for s in house] == [("number_source",),
                                                 ("source_provenance",)]

    def names(checks):
        return sorted(s.name for s in skills_mod.select(house, ["src"], checks=checks))

    assert names(["number_source", "source_provenance"]) == ["provenance-numbers",
                                                             "provenance-sources"]
    assert names(["source_provenance"]) == ["provenance-sources"]
    assert names(["parseable"]) == []
    assert names(None) == ["provenance-numbers", "provenance-sources"]

    # A skill a person wrote has no gate and is never dropped by one.
    mine = skills_mod._parse("# house style\n", "house", "skills/house.md")
    assert skills_mod.select([mine], ["src"], checks=[]) == [mine]


# ------------------------------------------------- the review's five, and more
@pytest.mark.parametrize("span,v,u,expected,why", [
    # The five the independent review reproduced against the first commit.
    ("-5 °C",              "-5",  "°C",    [],             "a signed value is a value"),
    ("-5 °C",              "5",   "°C",    ["CA-NUM-002"], "minus five is not five"),
    ("9007199254740992 g", "9007199254740993", "g",
                                           ["CA-NUM-002"], "two integers 2**53 apart"),
    ("5  °C",              "5",   "°C",    [],             "two spaces is whitespace"),
    ("5 mg/mL",            "5",   "mg/mL", [],             "a compound unit is a unit"),
    # The neighbourhood around them, so the fix is a rule and not five patches.
    ("9007199254740992 g", "9007199254740992", "g", [],    "and the true one passes"),
    ("5 °C",          "5",   "°C",    [],             "a non-breaking space"),
    ("5°C",                "5",   "°C",    [],             "no space at all"),
    ("5 m·s^-1",           "5",   "m·s^-1", [],            "a middle-dot compound"),
    ("5 cm-1",             "5",   "cm-1",  [],             "a hyphen exponent"),
    ("5 cm⁻¹",             "5",   "cm⁻¹",  [],             "a superscript exponent"),
    ("+5 g",               "5",   "g",     [],             "a leading plus is dropped"),
    ("0.50 m",             "0.5", "m",     [],             "trailing zeros are dropped"),
    ("05 m",               "5",   "m",     [],             "leading zeros are dropped"),
    ("1,000 rpm",          "1000", "rpm",  [],             "a grouped thousand"),
    ("1,000 rpm",          "1",   "",      ["CA-NUM-002"], "and one is not a thousand"),
    ("cool to 25–106 °C",  "106", "°C",    [],             "an en-dash range"),
    ("range 5-10 m",       "10",  "m",     [],             "a hyphen range"),
    ("1 hour",             "1",   "hours", [],             "the synonym table, raw"),
    ("10 wt % Ni",         "10",  "wt%",   [],             "the split percent"),
    ("5 mm",               "5",   "m",     ["CA-NUM-002"], "a prefix is not the unit"),
    ("5 °C",               "5",   "K",     ["CA-NUM-002"], "a different unit"),
    ("50 °C",              "5",   "°C",    ["CA-NUM-002"], "a substring is not a value"),
])
def test_the_pair_comparison_is_literal_in_both_directions(span, v, u, expected, why):
    """MUTATION: revert `normalise_number` to `float`, drop the sign from
    `_NUMBER`, allow only one space before the unit, or take a single unit
    reading. Each brings back one row of this table.

    Two failure directions, and the table asserts both, because a check that
    only avoided one of them would be worse than none: a BLOCKER on a correct
    transcription is non-overridable damage to correct work, and a PASS on a
    different number is the check saying it verified something it did not."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


def test_a_results_source_span_is_verified_by_this_check_and_not_by_provenance(
        monkeypatch):
    """MUTATION: restore `numbers.py`'s skip of `results.json`, or widen
    `check_provenance` to open the file.

    §2.1 widens a quantity's `source` to `path@revision#L14`, and the review
    found that after the widening NOBODY looked at the line: `check_provenance`
    decides membership and never opens a file — that is its entire contract, and
    changing it would put a second span implementation in a second module that
    then has to agree with this one. So the fragment is verified here, where the
    span logic already lives, with `wants_context=False` intact because this
    reads committed bytes and nothing about the run."""
    meta = b"code_version: v3\ninputs:\n  - runs.csv@v3\n"
    csv = b"run,yield\n1,0.42\n2,0.51\n"

    def project(source: str) -> dict[str, bytes]:
        return {"experiments/e1/metadata.yml": meta,
                "experiments/e1/runs.csv": csv,
                "experiments/e1/results.json": json.dumps({
                    "quantities": [{"name": "yield", "value": 0.42, "unit": "",
                                    "source": source}],
                    "convergence": {"converged": True}}).encode()}

    # `provenance` alone answers membership and says nothing about the line.
    assert run_checks(project("runs.csv@v3#L2"), ["provenance"]).findings == []
    assert run_checks(project("runs.csv@v3#L3"), ["provenance"]).findings == []

    # `number_source` is what opens the file, and both profiles carry the pair.
    assert run_checks(project("runs.csv@v3#L2"), ["number_source"]).findings == []
    wrong = run_checks(project("runs.csv@v3#L3"), ["number_source"])
    assert [f.rule for f in wrong.findings] == ["CA-NUM-002"]
    assert wrong.findings[0].observation.startswith("quantities[0] names runs.csv:3")
    past = run_checks(project("runs.csv@v3#L99"), ["number_source"])
    assert [f.rule for f in past.findings] == ["CA-NUM-001"]

    # A source with no fragment is the world before the widening, untouched.
    assert run_checks(project("runs.csv@v3"), ["number_source"]).findings == []

    # MUTATION (§4 row 3, for the locator that still names lines): widen `_span`
    # to the whole file, and the wrong-line citation goes GREEN. `_span` says in
    # its own docstring that this test holds it, so this test has to hold it —
    # the fence's half of that guard moved to `_quote_span` and the structured
    # half must not have been left behind with nobody asserting it.
    monkeypatch.setattr(numbers, "_span", lambda text, start, end: text)
    assert run_checks(project("runs.csv@v3#L3"), ["number_source"]).findings == []
    # The pair runs together in the science pack itself since D164 ruling 1
    # (between D158 and D164 the check was reachable only by name).
    from crossaudit.dcl.profiles import PROFILES
    assert {"provenance", "number_source"} <= set(PROFILES["science"])
    assert {"provenance", "number_source"} <= set(science_with_numbers())


@pytest.mark.parametrize("locator,note", [
    ("runs.csv@v3", "the shape every existing project already wrote"),
    ("runs.csv@v3#L2", "the widened shape"),
    ("runs.csv@v3#L2-L4", "the widened shape, as a range"),
])
def test_provenance_accepts_only_a_line_fragment_and_nothing_else(locator, note):
    """MUTATION: go back to `src.partition('#')`. `runs.csv@v3#garbage`,
    `runs.csv@v3#`, `runs.csv@v3#other@evil` and `runs.csv@v3#L999` all blocked
    with CA-DATA-003 before the widening and silently passed after it, and a
    committed file legitimately named `runs#raw.csv` — declared and cited
    exactly — started blocking because its source became `runs`.

    The order is the fix: exact membership on the WHOLE string first, then a
    fragment only if that failed, and only `#L<digits>[-L<digits>]` anchored to
    the end."""
    meta = b"code_version: v3\ninputs:\n  - runs.csv@v3\n"
    files = {"experiments/e1/metadata.yml": meta,
             "experiments/e1/runs.csv": b"run,yield\n1,0.42\n2,0.51\n3,0.6\n4,0.7\n",
             "experiments/e1/results.json": json.dumps({
                 "quantities": [{"name": "y", "value": 0.42, "unit": "",
                                 "source": locator}],
                 "convergence": {"converged": True}}).encode()}
    assert run_checks(files, ["provenance"]).findings == [], note


@pytest.mark.parametrize("locator", [
    "runs.csv@v3#garbage", "runs.csv@v3#", "runs.csv@v3#other@evil",
    "runs.csv@v3#L2extra", "runs.csv@v3#l2", "runs.csv#L2",
])
def test_anything_that_is_not_a_line_fragment_still_fails_membership(locator):
    """The other half of the same mutation: these blocked before the widening
    and must still block."""
    meta = b"code_version: v3\ninputs:\n  - runs.csv@v3\n"
    files = {"experiments/e1/metadata.yml": meta,
             "experiments/e1/runs.csv": b"run,yield\n1,0.42\n",
             "experiments/e1/results.json": json.dumps({
                 "quantities": [{"name": "y", "value": 0.42, "unit": "",
                                 "source": locator}],
                 "convergence": {"converged": True}}).encode()}
    assert [f.rule for f in run_checks(files, ["provenance"]).findings] == ["CA-DATA-003"]


def test_a_file_whose_name_contains_a_hash_keeps_passing():
    """MUTATION: strip at the first `#` instead of at an anchored line fragment.
    A committed `runs#raw.csv`, declared and cited byte-for-byte, becomes
    CA-DATA-003 for a source of `runs` — a backward-compatibility break invented
    by the widening, on a filename that was always legal."""
    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs#raw.csv@v3\n",
             "experiments/e1/runs#raw.csv": b"run,yield\n1,0.42\n",
             "experiments/e1/results.json": json.dumps({
                 "quantities": [{"name": "y", "value": 0.42, "unit": "",
                                 "source": "runs#raw.csv@v3"}],
                 "convergence": {"converged": True}}).encode()}
    assert run_checks(files, ["provenance"]).findings == []


# --------------------------------------------- malformed input never escapes
def test_a_malformed_annotation_becomes_a_finding_and_never_an_exception():
    """MUTATION: restore `\\d+` in `_LINE`, or catch only `JSONDecodeError`.

    `int()` refuses a string of more than 4300 digits, so `#L` followed by five
    thousand digits and a JSON integer of five thousand digits both raised an
    uncaught `ValueError` out of `run_checks` — the deterministic layer, which
    runs before any model and decides the verdict, crashing on text a generator
    can emit. A malformed annotation is a finding; it is never an exception.

    Both halves of the mutation are still live, in the two places a line number
    can still arrive: the `results.json` locator, which `_LINE` parses, and a
    JSON literal in the fence, which `normalise_number` reads. The fence's own
    locator no longer parses a number at all — five thousand digits inside a
    quotation are five thousand characters the file does not contain."""
    huge = "9" * 5000
    for body, rule in (
            (json.dumps([{"v": "1", "u": "",
                          "src": {"file": RECIPE_PATH, "quote": f"#L{huge}"}}]),
             "CA-NUM-002"),
            ('[{"v": ' + huge + ', "u": "", '
             f'"src": {{"file": "{RECIPE_PATH}", "quote": "3. Calcine"}}}}]',
             "CA-NUM-001")):
        files = {RECIPE_PATH: RECIPE.encode(),
                 DRAFT_PATH: f"# E\n\n```crossaudit-numbers\n{body}\n```\n".encode()}
        out = findings(files)
        assert out and all(f.rule == rule for f in out), body[:40]

    # And the same five thousand digits through the locator that IS still
    # parsed as a line number, where `_LINE`'s bound is what stops the crash.
    structured = {"experiments/e1/metadata.yml":
                  b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
                  "experiments/e1/runs.csv": b"run,y\n1,0.42\n",
                  "experiments/e1/results.json": json.dumps(
                      {"quantities": [{"name": "y", "value": 0.42, "unit": "",
                                       "source": f"runs.csv@v3#L{huge}"}],
                       "convergence": {"converged": True}}).encode()}
    assert run_checks(structured, ["number_source"]).findings == []


def test_an_unclosed_annotation_block_is_a_finding_not_silence():
    """MUTATION: drop the `_FENCE_OPEN` count. A block that was opened and never
    closed reads as 'this document annotated nothing' and passes vacuously —
    indistinguishable from a document that never annotated, which is exactly the
    silent-pass §5.4 says any slice shipping these checks must not have."""
    unclosed = (f"# E\n\n```crossaudit-numbers\n"
                f"{json.dumps([row()], ensure_ascii=False)}\n")
    out = findings({RECIPE_PATH: RECIPE.encode(), DRAFT_PATH: unclosed.encode()})
    assert [f.rule for f in out] == ["CA-NUM-001"]
    assert "opened and never closed" in out[0].observation


def test_a_row_that_omits_a_field_cannot_opt_out_of_the_check():
    """MUTATION: go back to `row.get("u", "")`. A row with no `u` was read as
    unitless, so a generator could skip the unit half of the comparison by not
    writing the key — the contract has four fields, and a row with three is not
    a row this check can verify.

    A JSON number for `v` or `u` is still accepted: writing `"v": 950` is a
    transcription, not a judgment, and refusing it would be a non-overridable
    blocker on a well-formed annotation. The fields are THREE since D159, and
    the mutation in the other direction — asking for `at` again — is the one
    `test_a_legacy_at_is_accepted_and_its_at_is_ignored` reddens."""
    no_unit = {"v": "950", "src": cite(L11)}
    out = findings({RECIPE_PATH: RECIPE.encode(), DRAFT_PATH: draft([no_unit])})
    assert [f.rule for f in out] == ["CA-NUM-001"]
    assert "is missing u" in out[0].observation
    assert "each row names v, u and src" in out[0].observation

    numeric = {"v": 950, "u": "°C", "src": cite(L11)}
    assert findings({RECIPE_PATH: RECIPE.encode(),
                     DRAFT_PATH: draft([numeric])}) == []

    nested = {"v": {"n": 950}, "u": "°C", "src": cite(L11)}
    bad = findings({RECIPE_PATH: RECIPE.encode(), DRAFT_PATH: draft([nested])})
    assert [f.rule for f in bad] == ["CA-NUM-001"]
    assert "non-text v" in bad[0].observation

    # `src` is a string or an object, and a row that makes it anything else is
    # malformed rather than silently unread — the mirror of the type widening
    # that let the locator become an object in the first place.
    listed = {"v": "950", "u": "°C", "src": [RECIPE_PATH, L11]}
    worse = findings({RECIPE_PATH: RECIPE.encode(), DRAFT_PATH: draft([listed])})
    assert [f.rule for f in worse] == ["CA-NUM-001"]
    assert "non-text src" in worse[0].observation


def _first_round_prompt(root) -> str:
    """The generator prompt a project builds on round 1, when nothing is written
    yet — the selection `cli/build.py:794` makes, against `cfg.scope_dirs` and
    the project's live `checks:`."""
    from crossaudit import generator, skills as skills_mod
    from crossaudit.config import load

    cfg = load(root / "crossaudit.yml")
    in_force = skills_mod.select(skills_mod.load(root), [] or cfg.scope_dirs,
                                 checks=cfg.checks)
    return generator.build_prompt(
        task="write the increment", constitution="# rules\n", current={},
        skills=skills_mod.render(in_force), allowed_dirs=cfg.scope_dirs)


def test_a_fresh_science_project_is_told_about_numbers(tmp_path, monkeypatch):
    """MUTATION (D164 ruling 1): take `number_source` out of
    `scaffold.SCIENCE_CHECKS` — the list BOTH creation paths read
    (`console/projects.py:1597` and `cli/wizard.py:438`) — and every assertion
    below reddens: the skill file is not written, the fence leaves the prompt,
    and a science project runs a check nobody told its generator to satisfy
    (§5.4's silent pass) or, worse, none at all.

    **The two lists are separate objects** coupled only by a comment
    (`scaffold/__init__.py`, "Kept identical to dcl/profiles.py"), which is
    exactly the drift a guard should catch; an independent review of the
    earlier form of this test proved that a profile-only mutation left a
    scaffold test green, so the equality of the two lists is asserted here
    directly, and a mutation of either list reddens this node.

    The assertion is on the rendered generator prompt and not only on the file,
    because a skill delivered but never rendered and a skill never written are
    different states and only one of them costs tokens. The gate doing the work
    is `requires_check:` in the skill's own front matter, read by
    `skills.select` against the live check list — nothing here special-cases
    `number_source` by name."""
    from crossaudit.dcl.profiles import resolve

    root = _science_project(tmp_path, monkeypatch, "labdefault")
    cfg = load(root / "crossaudit.yml")

    assert "number_source" in cfg.checks
    # The scaffold's list and the profile's are two objects, and a project that
    # scaffolds as "science" and one that writes `checks: science` must still
    # mean the same thing.
    assert cfg.checks == resolve("science")
    assert (root / NUMBERS_SKILL).exists()
    assert _git(root, "ls-files", "--", NUMBERS_SKILL).strip() == NUMBERS_SKILL

    prompt = _first_round_prompt(root)
    assert "crossaudit-numbers" in prompt
    assert "uncited" in prompt


def test_a_project_that_names_the_check_gets_the_skill_and_the_instruction(
        tmp_path, monkeypatch):
    """MUTATION: drop `number_source` from `scaffold.ANNOTATION_SKILLS`, or stop
    passing the project's own `checks:` to `annotation_skills_owned` /
    `skills.select`. Either leaves a project that explicitly asked for the check
    running it against a generator nobody told to annotate — §5.4's silent pass,
    a check that guards nothing while wearing the name of one that does.

    The check is selectable by name in any project (D158 kept that; D164 put it
    into the science pack, so a SCIENCE project already has the skill). This is
    the half that keeps the promise honest for a project whose pack does not
    carry it — a `general` project that writes the check into `checks:` by
    name: the same creation-path helper both the CLI and the console call
    (`wizard.annotation_skills_owned`), handed a check list that names it,
    writes the skill — and the first round's prompt carries the fence."""
    from crossaudit.cli import wizard

    root = _science_project(tmp_path, monkeypatch, "labexplicit", project_type="general")
    config = root / "crossaudit.yml"
    config.write_text(
        re.sub(r"^checks: \[(.*)\]$", r"checks: [\1, number_source]",
               config.read_text(encoding="utf-8"), flags=re.M),
        encoding="utf-8")
    cfg = load(config)
    assert cfg.checks[-1] == "number_source"

    assert wizard.annotation_skills_owned(root, cfg.checks) == [NUMBERS_SKILL]
    assert (root / NUMBERS_SKILL).is_file()

    prompt = _first_round_prompt(root)
    assert "```crossaudit-numbers" in prompt
    assert "you name a location, you never say what is at it" in prompt.lower()
    # And it arrives as guidance, never as law.
    assert "HOUSE SKILLS" in prompt


# ------------------------------------------- the second review's two root causes
@pytest.mark.parametrize("span,v,u,expected,why", [
    # Round two's regressions, and the sign and compound cases behind them.
    ("1e3 K",   "1e3",  "g",     ["CA-NUM-002"], "the substring fallback ignored the unit"),
    ("1e3 K",   "1e3",  "K",     [],             "and the same pair is a match"),
    ("1e3 K",   "1000", "K",     [],             "exponent and decimal are one number"),
    ("1000 K",  "1e3",  "K",     [],             "in both directions"),
    ("−5 °C",   "-5",   "°C",    [],             "U+2212 MINUS SIGN is a minus"),
    ("−5 °C",   "5",    "°C",    ["CA-NUM-002"], "and minus five is still not five"),
    ("5 mg/mL", "5",    "mg",    ["CA-NUM-002"], "a prefix of a compound unit"),
    ("5 cm-1",  "5",    "cm",    ["CA-NUM-002"], "a prefix of an exponent unit"),
    ("5\u2003°C", "5",  "°C",    [],             "U+2003 EM SPACE"),
    ("5\u202f°C", "5",  "°C",    [],             "U+202F NARROW NO-BREAK SPACE"),
    ("5\u00a0°C", "5",  "°C",    [],             "U+00A0 NO-BREAK SPACE"),
    ("0.42 1",  "0.42", "1",     [],             "a dimensionless numeric unit"),
    ("5 m2",    "5",    "m2",    [],             "an exponent written as a digit"),
    ("about 950", "~950", "°C",  ["CA-NUM-001"], "a value that is not a number"),
    ("about 950", "9-50", "",    ["CA-NUM-001"], "nor is a range"),
])
def test_the_matcher_after_the_second_review(span, v, u, expected, why):
    """MUTATION: restore the substring fallback at the foot of `contains_pair`,
    drop U+2212 from `_NUMBER`, hand-list the whitespace characters instead of
    using `\\s`, or take a non-maximal unit reading. Each brings back one row.

    The fallback is the one that mattered most. A value that failed decimal
    validation fell through to `value in span` and **ignored the unit entirely**,
    so source `1e3 K` satisfied an annotation of `1e3` with unit `g`: the check
    reporting that it had verified a literal pair while accepting a different
    quantity. There is no fallback now — a value that does not normalise is
    CA-NUM-001 — and normalisation is complete enough that legitimate forms do
    not reach that path."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


def test_precision_survives_the_json_parse():
    """MUTATION: parse the fence with a plain `json.loads`.

    Comparing canonical decimal strings buys nothing if the literal was already
    rounded through a double on the way in: `9007199254740993.0` arrives as
    9007199254740992.0 and matches a span that says 9007199254740992. The fence
    and `results.json` are both parsed with `parse_float=str, parse_int=str`, so
    the transcription reaches the comparison as the characters that were
    written."""
    body = ('[{"v": 9007199254740993.0, "u": "g", '
            f'"src": {{"file": "{RECIPE_PATH}", "quote": "9007199254740992 g"}}}}]')
    files = {RECIPE_PATH: b"9007199254740992 g\n",
             DRAFT_PATH: f"# E\n\n```crossaudit-numbers\n{body}\n```\n".encode()}
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"]

    exact = body.replace("9007199254740993.0", "9007199254740992.0")
    files[DRAFT_PATH] = f"# E\n\n```crossaudit-numbers\n{exact}\n```\n".encode()
    assert findings(files) == []


@pytest.mark.parametrize("value,unit", [
    (None, "K"), ({"a": 1}, "K"), ([1], "K"), (True, "K"),
    (0.42, {"a": 1}), (0.42, [1]), (0.42, None),
])
def test_a_quantity_this_check_cannot_read_may_not_carry_a_span(value, unit):
    """MUTATION: skip an unreadable value or unit "reported by units", and drop
    the `is_number_shape` gate on the fragment strip in `check_provenance`.

    `check_units` tests that `unit` and `source` are TRUTHY and has never looked
    at `value`. Trusting it meant a quantity with a null value citing line 999
    of a two-line file passed the complete science profile with no finding at
    all — where the code before the span widening blocked it with CA-DATA-003.
    Two independent guards, because one of them believing the other is what
    opened the hole: `check_provenance` only looks past a fragment for a row
    `number_source` can actually go and read, and `number_source` reports a row
    it cannot read rather than skipping it."""
    from crossaudit.dcl.profiles import resolve

    q = {"name": "y", "source": "runs.csv@v3#L999"}
    if value is not None or unit is None:
        q["value"] = value
    q["unit"] = unit
    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": b"run,y\n1,0.42\n",
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [q], "convergence": {"converged": True}}).encode()}
    result = run_checks(files, science_with_numbers())
    assert result.hard_failures >= 1
    assert {"CA-DATA-003", "CA-NUM-001"} <= {f.rule for f in result.findings}


def test_every_file_the_builtin_checks_read_is_a_file_this_one_reads():
    """MUTATION: match the exact basename `results.json` again.

    `builtin._results_files` accepts any path ENDING in `results.json`, so
    `myresults.json` was a file `check_provenance` widened for and
    `number_source` never opened — the compensation missing for exactly the
    files the other check had accepted. One helper, in `dcl/quantities.py`,
    used by both."""
    from crossaudit.dcl.builtin import _results_files
    from crossaudit.dcl.quantities import results_files

    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": b"run,y\n1,0.42\n",
             "experiments/e1/myresults.json": json.dumps(
                 {"quantities": [{"name": "y", "value": 0.42, "unit": "K",
                                  "source": "runs.csv@v3#L999"}],
                  "convergence": {"converged": True}}).encode()}
    assert _results_files(files) == results_files(files) == ["experiments/e1/myresults.json"]
    assert [f.rule for f in run_checks(files, ["number_source"]).findings] == ["CA-NUM-001"]


def test_a_source_declared_verbatim_is_opaque_to_both_checks():
    """MUTATION: drop the `opaque` set in `_results_findings`.

    Whole-string precedence has to hold in both checks or they contradict each
    other. If somebody literally declares `runs.csv@v3#L999` as an input, then
    `check_provenance` accepts the source as an exact member — a revision string
    that happens to contain a `#` — and `number_source` reading a line number
    out of it would hard-block a shape the other check just approved. Base
    accepted this with only the code_version advisory, and so does head."""
    from crossaudit.dcl.profiles import resolve

    files = {"experiments/e1/metadata.yml":
                 b"code_version: v3\ninputs:\n  - runs.csv@v3#L999\n",
             "experiments/e1/runs.csv": b"run,y\n1,0.42\n",
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "y", "value": 0.42, "unit": "K",
                                  "source": "runs.csv@v3#L999"}],
                  "convergence": {"converged": True}}).encode()}
    result = run_checks(files, science_with_numbers())
    assert result.hard_failures == 0
    assert [(f.severity, f.rule) for f in result.findings] == [(ADVISORY, "CA-DATA-003")]


@pytest.mark.parametrize("locator,blocks", [
    ("runs.csv@v3#L2", False),
    ("runs.csv@v3#L2\n", True),
    ("runs.csv@v3#L٢", True),
])
def test_the_fragment_is_ascii_and_at_the_absolute_end(locator, blocks):
    """MUTATION: use `$` instead of `\\Z`, or `\\d` instead of `[0-9]`.

    `$` also matches before a final newline, so `runs.csv@v3#L2\\n` was read as a
    line fragment; `\\d` matches Arabic-Indic digits, so `#L٢` was read as line
    two. Neither is a shape a transcription of committed bytes would produce,
    and both used to be CA-DATA-003."""
    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": b"run,y\n1,0.42\n",
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "y", "value": 0.42, "unit": "",
                                  "source": locator}],
                  "convergence": {"converged": True}}).encode()}
    found = [f.rule for f in run_checks(files, ["provenance"]).findings]
    assert (found == ["CA-DATA-003"]) is blocks


@pytest.mark.parametrize("ref,blocks", [
    ("https://example.org/a@v3", False),
    ("HTTPS://example.org/a@v3", False),
    ("ftp://example.org/a@v3", False),
    ("doi:10.1234/example@v3", False),
    ("pkg:pypi/numpy@1.0", False),
    ("data/runs.csv@v3", True),
])
def test_the_existence_check_skips_by_scheme_not_by_a_lowercase_prefix(ref, blocks):
    """MUTATION: go back to `ref.startswith(("http://", "https://"))`.

    A reference that names a scheme is not a file, and the check was looking for
    `HTTPS://…`, `ftp://…`, `doi:…` and `pkg:pypi/numpy` on disk and reporting
    them missing — a non-overridable blocker on metadata that is simply not a
    path. `check_declared` keeps its own base behaviour: widening what IT skips
    would be a weakening of a check that ships in every default project."""
    meta = ("code_version: v3\ninputs:\n  - " + ref + "\n").encode()
    found = [f.rule for f in run_checks({"e/metadata.yml": meta}, ["provenance"]).findings]
    assert (found == ["CA-DATA-003"]) is blocks


def test_a_file_ending_in_an_opening_fence_is_a_finding():
    """MUTATION: require a trailing newline in `_FENCE_OPEN` again. A file whose
    last bytes are the opening fence itself produced no finding, so a truncated
    annotation was indistinguishable from a document that never annotated."""
    for tail in ("```crossaudit-numbers", "```crossaudit-numbers\n"):
        out = findings({RECIPE_PATH: RECIPE.encode(),
                        DRAFT_PATH: ("# E\n\n" + tail).encode()})
        assert [f.rule for f in out] == ["CA-NUM-001"], tail
        assert "opened and never closed" in out[0].observation


@pytest.mark.parametrize("span,v,u,expected,why", [
    ("(20°C-25°C)", "20", "°C",     [],             "a range is not one unit token"),
    ("(20°C-25°C)", "20", "°C-25",  ["CA-NUM-002"], "and its halves are not either"),
    ("99-102 kPa",  "102", "kPa",   [],             "the second half carries the unit"),
    ("99-102 kPa",  "99",  "kPa",   [],             "and since E1 (study 11) the low endpoint carries it too"),
    ("5 cm-1",      "5",  "cm-1",   [],             "a hyphen exponent at end of token"),
    ("5 cm-1",      "5",  "cm",     ["CA-NUM-002"], "and its prefix is still refused"),
    ("5°C/min",     "5",  "°C/min", [],             "a ramp rate is its own unit"),
    ("5°C/min",     "5",  "°C",     ["CA-NUM-002"], "a temperature is not a ramp rate"),
])
def test_a_hyphen_range_is_not_an_exponent(span, v, u, expected, why):
    """MUTATION: drop the lookahead from `_EXPONENT_TAIL`.

    Making the unit token maximal — which is what stops `5 mg/mL` satisfying
    `mg` — read `(20°C-25°C)` as the single unit `°C-25`, so a draft citing
    `20 °C` off a line stating an ambient window was blocked for transcribing it
    correctly. Measured, not hypothesised: it cost 1 of 365 on the archived
    drafts and took the Arm 1 primary rate from 1.64% to 1.92%.

    A hyphen followed by digits and then more unit is a range; a hyphen followed
    by digits and then the end of the token is an exponent. The lookahead is the
    only thing that separates them, and both halves are asserted here because
    loosening it far enough to fix the range would give `cm` back."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


# ------------------------------------- the third review: a prefix never satisfies
@pytest.mark.parametrize("span,v,u,expected,why", [
    # Round three's P1 table: the annotation is a strict PREFIX of the token.
    ("5 m-2s-1",      "5", "m",            ["CA-NUM-002"], "prefix of an exponent compound"),
    ("5 m-2s-1",      "5", "m-2s-1",       [],             "and the whole token matches"),
    ("5 m2s-1",       "5", "m",            ["CA-NUM-002"], "the same without the hyphen"),
    ("10 kg-m",       "10", "kg",          ["CA-NUM-002"], "prefix of a hyphenated unit"),
    ("10 kg-m",       "10", "kg-m",        [],             "and the whole token matches"),
    ("5 g-equivalent", "5", "g",           ["CA-NUM-002"], "prefix of a hyphenated word"),
    ("5 g-equivalent", "5", "g-equivalent", [],            "and the whole token matches"),
    ("2 h-long",      "2", "h",            ["CA-NUM-002"], "prose is not a licence for a prefix"),
    ("2 h-long",      "2", "h-long",       [],             "and the whole token matches"),
    ("3 °C-1",        "3", "°C",           ["CA-NUM-002"], "prefix of a hyphen exponent"),
    ("3 °C-1",        "3", "°C-1",         [],             "and the whole token matches"),
    ("5 m-2 s-1",     "5", "m-2",          ["CA-NUM-002"], "nor does a space license one"),
    ("5 m-2 s-1",     "5", "m-2 s-1",      [],             "the whole spaced expression does"),
    # A range is split, and only where both halves are the same unit.
    ("(20°C-25°C)",   "20", "°C",          [],             "a closed-up range names one unit"),
    ("(20°C-25°C)",   "25", "°C",          [],             "from either end"),
    ("(20°C-25°C)",   "20", "°C-25°C",     [],             "the whole token is a reading too"),
    ("10 kg-2m",      "10", "kg",          ["CA-NUM-002"], "unequal halves are not a range"),
    ("99-102 kPa",    "102", "kPa",        [],             "the half that carries the unit"),
    ("99-102 kPa",    "99", "kPa",         [],             "and, since E1, the low endpoint (not a prefix: the whole `kPa`)"),
    # The exponent bound refuses; it never truncates.
    ("1e10001 g",     "1e1000", "1",       ["CA-NUM-002"], "no leftover digit becomes a unit"),
    ("1e10001 g",     "1e10001", "g",      [],             "and the real pair matches"),
    ("1e100 g",       "1e100", "g",        [],             "an ordinary exponent"),
    ("1e100 g",       "1e9999999", "g",    ["CA-NUM-001"], "past the bound is refused"),
    # Extraction sees every form normalisation accepts.
    (".5 g",          ".5", "g",           [],             "a leading-dot decimal"),
    (".5 g",          "0.5", "g",          [],             "and the same number written out"),
    ("mol/(L·s): 5 mol/(L·s)", "5", "mol/(L·s)", [],       "balanced brackets stay inside"),
    ("at 5 K.",       "5", "K",            [],             "a sentence period ends the token"),
    ("950 °C, then",  "950", "°C",         [],             "so does a comma"),
])
def test_a_prefix_of_the_unit_token_never_satisfies(span, v, u, expected, why):
    """MUTATION: read the unit with a pattern that can return a shorter
    alternative, or cap the exponent inside the SPAN scanner.

    Both were the same defect wearing two hats — something shorter than what the
    source wrote was accepted as what the source wrote. `5 m-2s-1` satisfied an
    annotation of `m`, `10 kg-m` satisfied `kg`, `2 h-long` satisfied `h`; and
    `1e10001` was read as the number `1e1000` followed by the unit `1`, which
    passed 100 of 100 exponents swept from 10000 to 10099.

    The rule is now one rule and it is the same for both halves of the pair: the
    token is extracted whole, to a true boundary, and compared whole-to-whole. A
    bound is a REFUSAL (CA-NUM-001), never a truncation. The only readings that
    may be added are ones LONGER than the token — a range split and the `wt %`
    percent split — so nothing can reintroduce a prefix."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


def test_the_exponent_sweep_that_gave_a_hundred_false_passes():
    """MUTATION: put a digit cap back in `_NUMBER`.

    The review swept exponents 10000–10099 and every one of them was a false
    pass: the scanner consumed four exponent digits and handed the fifth to the
    unit reader. One case would have been a curiosity; a contiguous hundred is a
    grammar defect, so the whole range is the guard."""
    from crossaudit.dcl.numbers import contains_pair

    for exponent in range(10000, 10100):
        digits = str(exponent)
        assert not contains_pair(f"1e{exponent} g", f"1e{digits[:4]}", digits[4:]), exponent
        assert contains_pair(f"1e{exponent} g", f"1e{exponent}", "g"), exponent


@pytest.mark.parametrize("locator", [
    f"{RECIPE_PATH}#L11", f"{RECIPE_PATH}#L11\n", f"{RECIPE_PATH}#L١١",
    f" {RECIPE_PATH}#L11", f"{RECIPE_PATH}#L9-L12", RECIPE_PATH, "",
])
def test_the_fence_locator_is_no_longer_a_line_number_at_all(locator):
    """MUTATION (D159 ruling 1): keep parsing `path#L<n>` in the fence beside
    the quotation, "for compatibility". Every one of these rows goes green, and
    the check has two locator grammars under one name — which is two contracts,
    and the one this slice removed is the one the generator provably cannot
    write (Arm 2: 0 of 215 rows passed).

    RETIRED WITH D159, and recorded here rather than deleted:
    `test_a_fenced_locator_is_ascii_and_exact`,
    `test_the_at_locator_is_validated_the_way_the_src_locator_is` and
    `test_the_at_locator_must_be_inside_the_artefact_that_carries_it` all
    asserted line-number semantics in the FENCE — ASCII digits, no surrounding
    whitespace, `#L0` and `#L5-L2` refused, a range inside the artefact. There
    is no line number in the fence to be exact about any more, and no `at` field
    to validate. What those tests were really guarding is `_LINE`'s digit and
    end-anchor discipline, which still governs the `results.json` locator and is
    still asserted by `test_the_fragment_is_ascii_and_at_the_absolute_end` and
    `test_a_structured_source_holds_its_own_contract_with_no_other_check_on`.
    A quotation needs none of it: whitespace is folded on both sides by
    contract, and every other character is compared as itself."""
    files = {RECIPE_PATH: RECIPE.encode(),
             DRAFT_PATH: draft([{"v": "950", "u": "°C", "src": locator}])}
    found = findings(files)
    assert [f.rule for f in found] == ["CA-NUM-001"]
    assert "not a file and a quotation from it" in found[0].observation


def test_the_contract_discloses_what_normalisation_does_to_a_number():
    """MUTATION: go back to promising literal containment.

    The contract is the sentence a person reads to decide whether to turn the
    check on, and it is bound into the receipt. Saying "literally contains" while
    treating `1.50` and `1.5` as one number overstates it: the check cannot tell
    a reported precision from a rounded one, and a contract that hides its own
    limit is the overclaim shape this whole line exists to remove."""
    from crossaudit.dcl.framework import contracts

    contract = contracts(["number_source"])["number_source"]
    assert "1.50" in contract and "not significant" in contract
    assert "WHOLE unit token" in contract and "prefix" in contract
    assert "never coverage" in contract and "never judges whether a number is correct" in contract


# ---------------------------- the fourth review: boundaries, not an allowlist
@pytest.mark.parametrize("span,v,u,expected,why", [
    # The three P1 rows: a character the allowlist did not list ended the token.
    ("5 kg.m",   "5", "kg",      ["CA-NUM-002"], "a period inside a unit is not a boundary"),
    ("5 kg.m",   "5", "kg.m",    [],             "and the whole token matches"),
    ("5 wt %/s", "5", "wt %",    ["CA-NUM-002"], "the percent reading runs on to the boundary"),
    ("5 wt %/s", "5", "wt %/s",  [],             "and the whole token matches"),
    ("5 °Cβ",    "5", "°C",      ["CA-NUM-002"], "β is not a boundary; nothing said it was"),
    ("5 °Cβ",    "5", "°Cβ",     [],             "and the whole token matches"),
    # Characters no allowlist author would have listed, all token.
    ("5 Ω′",     "5", "Ω′",      [],             "prime and ohm"),
    ("5 m⁄s",    "5", "m⁄s",     [],             "a fraction slash"),
    ("5 H₂O",    "5", "H₂O",     [],             "a subscript"),
    ("5 Å",      "5", "Å",       [],             "angstrom"),
    ("5 Ω′",     "5", "Ω",       ["CA-NUM-002"], "and a prefix of any of them still fails"),
    # The review's ordinary-prose table: every boundary, enumerated.
    ("(5 °C)",      "5", "°C", [], "an unopened closing bracket"),
    ("5 °C, then",  "5", "°C", [], "a comma"),
    ("5 °C; then",  "5", "°C", [], "a semicolon"),
    ("5 °C: then",  "5", "°C", [], "a colon"),
    ("5 °C.",       "5", "°C", [], "a period at the end of the text"),
    ("5 °C. Then",  "5", "°C", [], "a period before a space"),
    ("5 °C!",       "5", "°C", [], "an exclamation mark — a round-3 prose regression"),
    ("5 °C?",       "5", "°C", [], "a question mark — the same"),
    ("5 °C—",       "5", "°C", [], "an em dash"),
    ("5 °C–",       "5", "°C", [], "an en dash"),
    ('"5 °C"',      "5", "°C", [], "a quotation mark"),
    ("5 °C…",       "5", "°C", [], "an ellipsis"),
    ("5 °C ± 1",    "5", "°C", [], "whitespace, as always"),
    ("5 %",         "5", "%",  [], "a bare percent"),
    ("5%",          "5", "%",  [], "and a closed-up one"),
    ("10 wt % Ni",  "10", "wt%", [], "the percent split still ends at the space"),
    ("5 mol/(L·s)", "5", "mol/(L·s)", [], "balanced brackets stay inside"),
    ("5 mol/(L·s)", "5", "mol/(L",   ["CA-NUM-002"], "and half of one does not"),
    ("at 5 K.",     "5", "K",  [], "a sentence period after a bare unit"),
    ("a 5 g-sample", "5", "g", ["CA-NUM-002"], "a hyphenated word is one token"),
    ("5 °C¹",       "5", "°C", ["CA-NUM-002"], "a superscript belongs to the token"),
    ("5 °C¹",       "5", "°C¹", [],           "so the whole thing matches"),
    # Ranges, unchanged by the inversion.
    ("(20°C-25°C)", "20", "°C", [], "a closed-up range names one unit"),
    ("(20°C-25°C)", "25", "°C", [], "from either end"),
    ("20-25 °C",    "25", "°C", [], "the half that carries the unit"),
    ("20-25 °C",    "20", "°C", [], "and, since E1 (study 11), the low endpoint too"),
    ("1-2 h",       "2", "h",  [], "the same for a duration"),
    ("20°C–25°C",   "20", "°C", [], "an en-dash range ends the token outright"),
])
def test_the_boundary_list_is_exhaustive_and_everything_else_is_token(
        span, v, u, expected, why):
    """MUTATION: make `_scan` an allowlist of characters permitted INSIDE a unit
    again, or drop `!`/`?`/the dashes from `_BOUNDARY`.

    An allowlist is the prefix defect in a third costume: any character its
    author did not think of ends the token, so a shorter reading satisfies a
    longer source. `5 kg.m` satisfied `kg`, `5 wt %/s` satisfied `wt %`, and
    `5 °Cβ` satisfied `°C` — all three through a `results.json` citation under
    the complete science profile with zero findings, where base blocks.

    Inverted, the failure direction inverts with it: a character nobody
    anticipated keeps the token whole, so the worst case is a blocker on a
    half-transcribed unit rather than a pass on one. The boundaries are
    enumerated here in full because the enumeration IS the contract."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


@pytest.mark.parametrize("at", ["#L3", "#L2-L4", "#L0", "#L5-L2", "#L٣",
                               "#L1-L1000000", "", None, 7, {"line": 3}])
def test_a_legacy_at_is_accepted_and_its_at_is_ignored(at):
    """MUTATION (D159): validate `at` again — read it, refuse `#L0`, require it
    to be inside the artefact. Every row here that carries a legacy `at`
    reddens, and an annotation written under the pre-D159 contract becomes a
    non-overridable blocker for carrying a field the new contract does not want.

    Dropping a required field is ADDITIVE only if the field is IGNORED rather
    than rejected, and that is the whole of the claim: the row is verified by
    its quotation, and `at` — right, wrong, impossible or not even a string —
    changes nothing about the disposition. It is not echoed back either, so a
    person is never shown an address code did not use.

    This is the guard that replaces the two retired `at` validation tests; the
    reason `at` cannot be asked for at all is Arm 2's 50 of 215 rows naming a
    line past the end of their own draft."""
    good = {"v": "950", "u": "°C", "src": cite(L11), "at": at}
    assert findings({RECIPE_PATH: RECIPE.encode(),
                     DRAFT_PATH: draft([good])}) == [], at

    bad = {"v": "950", "u": "°C", "src": cite(L12), "at": at}
    found = findings({RECIPE_PATH: RECIPE.encode(), DRAFT_PATH: draft([bad])})
    assert [f.rule for f in found] == ["CA-NUM-002"], at
    assert "at" not in found[0].observation.split("quotes")[0], at


@pytest.mark.parametrize("source,blocks", [
    ("runs.csv@v3#L2", False),
    (" runs.csv@v3#L2", True),
    ("runs.csv@v3#L2\n", True),
    ("runs.csv@v3#L2 ", True),
])
def test_a_structured_source_holds_its_own_contract_with_no_other_check_on(
        source, blocks):
    """MUTATION: `.strip()` the structured source again.

    A whitespace-padded locator was caught only because `provenance` also runs
    in the science profile. A check that needs another check to hold its own
    contract is root cause 1 in miniature, and `checks: [number_source]` is a
    configuration a project may write."""
    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": b"run,y\n0.42 K\n",
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "y", "value": 0.42, "unit": "K",
                                  "source": source}],
                  "convergence": {"converged": True}}).encode()}
    found = [f.rule for f in run_checks(files, ["number_source"]).findings]
    assert (found == ["CA-NUM-001"]) is blocks


def test_an_exponent_past_the_bound_is_refused_and_not_truncated():
    """MUTATION: allow six exponent digits again.

    The contract said the literal was bounded while `1e999999` passed. The cap
    is what makes "bounded" true, and it is a refusal (CA-NUM-001) rather than a
    truncation — truncation is what handed `1e10001`'s last digit to the unit
    reader."""
    files = {RECIPE_PATH: b"1e999999 g\n",
             DRAFT_PATH: draft([row(value="1e999999", unit="g",
                                    src=cite("1e999999 g"))])}
    assert [f.rule for f in findings(files)] == ["CA-NUM-001"]

    ok = {RECIPE_PATH: b"1e99999 g\n",
          DRAFT_PATH: draft([row(value="1e99999", unit="g",
                                 src=cite("1e99999 g"))])}
    assert findings(ok) == []


@pytest.mark.parametrize("span,v,u,expected,why", [
    ("10⁵ g",   "10", "",  ["CA-NUM-002"], "a superscript exponent is not read"),
    ("10⁵ g",   "10", "g", ["CA-NUM-002"], "with or without a unit"),
    ("5×10³ g", "5",  "",  ["CA-NUM-002"], "nor is a multiplication sign"),
    ("10^5 g",  "10", "",  ["CA-NUM-002"], "nor a caret"),
    ("run 5 of 12", "5", "", [],           "but a WORD after a number is not notation"),
    ("5 samples",   "5", "", [],           "and neither is a plain noun"),
    ("at 5, then",  "5", "", [],           "nor punctuation"),
    ("5 m·s^-1", "5", "m·s^-1", [],        "a caret inside a unit is untouched"),
])
def test_an_unparsed_numeric_notation_is_not_a_match_for_any_unit(
        span, v, u, expected, why):
    """DECIDED, and this is the statement the review asked for.

    `10⁵ g` and `5×10³ g` were satisfying an annotation of `10` and `5` with an
    EMPTY unit, because the scanner reads the mantissa and an empty unit asks no
    further question. The rule is: an occurrence whose number continues directly
    into notation this layer does not parse — a superscript exponent, a
    multiplication sign or a caret before a digit — is not a match for any unit,
    the empty one included. The source's number is not the number that was read,
    so no annotation of it can be verified against that line.

    The alternative the review offered — treat an empty unit as a mismatch
    whenever the source has a unit — is rejected, and the reason is measurable
    rather than aesthetic. Under a boundary scanner ANY word after a number is a
    token: `run 5 of 12` would make `of` the unit and `Sample 3 was calcined`
    would make `was` one, so that rule would block every legitimately unitless
    annotation whose number is followed by prose — most of them, on this corpus.
    This rule fires on the number's own continuation and never on what merely
    follows it, so it removes the false pass without inventing a false blocker."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


@pytest.mark.parametrize("unit,expected", [
    ("m-2",      ["CA-NUM-002"]),
    ("m-2 s-1",  []),
    ("m-2s-1",   ["CA-NUM-002"]),
    ("m-2·s-1",  ["CA-NUM-002"]),
])
def test_a_unit_written_with_a_space_is_the_whole_spaced_expression(unit, expected):
    """MUTATION: change the shipped wording without changing this.

    **This table is inverted from the one that shipped in slice 2, and the
    inversion is D160 ruling 1.** It used to assert that `m-2` PASSES against a
    source writing `m-2 s-1` — a space being a boundary, the second half was
    invisible — and slice 2's contract called that reading structural. The
    containment gold says it is not structural: it is `unit_token` stopping at
    whitespace, and it is 9 of the 11 false passes in 150
    (`RESULTS-GOLD.md` §3), the same prefix defect D157 rounds 3-5 record being
    fixed three times. So the first token no longer satisfies, the whole spaced
    expression does, and neither `m-2s-1` nor `m-2·s-1` does, because those are
    not what is written at that spot either.

    The skill and the contract must now describe exactly this table."""
    files = {RECIPE_PATH: b"5 m-2 s-1\n",
             DRAFT_PATH: draft([row(value="5", unit=unit, src=cite("5 m-2 s-1"))])}
    assert [f.rule for f in findings(files)] == expected


def test_the_shipped_words_say_what_the_scanner_does():
    """The other half of the pair above: the guidance and the contract have to
    describe the behaviour the table just asserted, including the two limits a
    reader would otherwise have to discover by being blocked.

    An empty unit imposes NO unit constraint, so the check can confirm a number
    is present and can never establish that it is unitless; and `*` and `>` are
    not boundaries because multiplication and comparison are notation a unit can
    contain, which costs a footnote star."""
    from crossaudit.dcl.framework import contracts
    from crossaudit.scaffold import annotation_skill_tree

    contract = contracts(["number_source"])["number_source"]
    assert "A SPACE IS NOT WHERE A UNIT ENDS" in contract
    assert "'m-2 s-1'" in contract and "WHOLE spaced expression" in contract
    assert "exactly as the source writes it, spaces included" in contract
    assert "'5 wt % Ni' has the unit 'wt %'" in contract
    assert "reports NO reading and the row BLOCKS" in contract
    assert "never falls back to the part it managed to read" in contract
    assert "the fragment table is the only guard" in contract   # round 3's limit
    assert "first token only" not in contract       # D160 ruling 1 deleted it
    assert "structural" not in contract
    assert "EMPTY unit imposes no unit constraint" in contract.replace("an EMPTY", "EMPTY")
    assert "never establish that it is unitless" in contract
    assert "'*' and '>'" in contract
    assert contract.count("does not resolve") == 1        # and it reads once

    body = annotation_skill_tree(["number_source"])[NUMBERS_SKILL]
    assert "exactly as the source writes it, spaces included" in body
    assert "`m-2 s-1`" in body and "uncited" in body
    assert "`5 wt % Ni` the unit is `wt %`" in body
    assert "cannot read to its end" in body
    assert "is read as a word after the unit" in body           # and its limit
    assert "FIRST token only" not in body           # D160 ruling 1 deleted it
    assert "structural" not in body
    assert "so it is one token" not in body         # and the instruction with it


def test_an_empty_unit_imposes_no_constraint_and_the_contract_says_so():
    """MUTATION: make an empty unit mismatch a source that has one.

    Stated rather than assumed, because the review asked for the choice on the
    record. `5 g` annotated `5 / ""` PASSES. Under a boundary scanner any word
    after a number is a token, so the stricter rule would make `of` the unit in
    `run 5 of 12` and block most legitimately unitless annotations. The price is
    that this check can never establish that a source number is unitless, and
    the contract says that in those words."""
    for span in ("5 g", "5 samples", "run 5 of 12", "5"):
        files = {RECIPE_PATH: (span + "\n").encode(),
                 DRAFT_PATH: draft([row(value="5", unit="", src=cite(span))])}
        assert findings(files) == [], span


# ------------------- D160 ruling 1: a space is not where a unit ends
#: Source text, the unit as annotated, and whether the check must block. The
#: gold cannot supply this table — `RESULTS-GOLD.md` Amendment 2 says W = 0 is
#: "no evidence against", not "no regression", and the 300 frozen rows contain
#: exactly one shape of spaced unit (`°C min⁻¹` and its cousins) and no bare
#: word after a unit at all. Every row here is a class the corpus lacks, so the
#: cases live in the slice instead of in the study.
SPACED_UNITS = [
    # The nine false passes the gold found, in the shapes it found them.
    ("5 °C min⁻¹",          "°C",        ["CA-NUM-002"], "a prefix across a space"),
    ("5 °C min⁻¹",          "°C min⁻¹",  [],             "and the whole expression"),
    ("5 °C min⁻¹",          "°C min",    ["CA-NUM-002"], "a truncated join is not it"),
    ("5 mg h⁻¹",            "mg",        ["CA-NUM-002"], "the same for a rate"),
    ("5 mg h⁻¹",            "mg h⁻¹",    [],             "and its whole expression"),
    ("5 K min⁻¹",           "K",         ["CA-NUM-002"], "and for a ramp"),
    ("5 K min⁻¹",           "K min⁻¹",   [],             "and its whole expression"),
    ("5 m s⁻¹",             "m",         ["CA-NUM-002"], "a one-character prefix"),
    ("5 m s⁻¹",             "m s⁻¹",     [],             "and its whole expression"),
    ("5 mol L⁻¹",           "mol",       ["CA-NUM-002"], "a concentration prefix"),
    ("5 mol L⁻¹",           "mol L⁻¹",   [],             "and its whole expression"),
    ("5 °C min-1",          "°C",        ["CA-NUM-002"], "an ASCII exponent tail too"),
    ("5 °C min-1",          "°C min-1",  [],             "and its whole expression"),
    ("5 °C min−1",          "°C",        ["CA-NUM-002"], "and a U+2212 one"),
    ("5 °C min−1",          "°C min−1",  [],             "and its whole expression"),
    # A continuation with no exponent at all: the fragment table's one job.
    ("5 kg m",              "kg",        ["CA-NUM-002"], "a plain unit symbol continues"),
    ("5 kg m",              "kg m",      [],             "and the pair is one unit"),
    # The percent split, which used to be a special case and is now this rule.
    ("5 wt % Ni",           "wt %",      [],             "the basis qualifier is the unit"),
    ("5 wt % Ni",           "wt",        ["CA-NUM-002"], "and its first token is not"),
    ("5 wt % Ni",           "wt % Ni",   ["CA-NUM-002"], "an element is not part of it"),
    ("20% vol/vol ethanol", "%",         ["CA-NUM-002"], "R6a: a basis qualifier is in"),
    ("20% vol/vol ethanol", "% vol/vol", [],             "and naming it whole matches"),
    # THE MIRRORS. A word is not a unit fragment, and this is the half of the
    # rule that a stricter continuation test would break.
    ("5 g sample",          "g",         [],             "a word does not continue a unit"),
    ("5 g of powder",       "g",         [],             "nor does a preposition"),
    ("2 h later",           "h",         [],             "nor does an adverb"),
    ("10 g at 300 °C",      "g",         [],             "nor `at`, which IS a unit symbol"),
    ("5 mL in water",       "mL",        [],             "nor `in`, which is an inch"),
    ("5 g A2",              "g",         [],             "nor a sample label"),
    ("5 h (heating/cooling rate)", "h",  [],             "nor a parenthetical"),
    ("5 g heating/cooling", "g",         [],             "nor a long word with a solidus"),
    ("5 g wet/dry sample",  "g",         [],             "nor a word with a solidus"),
    ("5 g batch-1",         "g",         [],             "nor a word with a hyphen"),
    ("5 g sample\u00b9",       "g",         [],             "nor a footnoted word"),
    ("5 g K",               "g",         [],             "nor potassium"),
    ("5 g Pa",              "g",         [],             "nor protactinium"),
    ("5 g A",               "g",         [],             "nor a labelled batch"),
    ("5 g 10 mL",           "g",         [],             "nor a second numeral"),
    ("5 g (dry)",           "g",         [],             "nor a parenthetical"),
    # An expression the module CAN read to its end, in full and never in part.
    ("5 g / mL",            "g / mL",    [],             "an operator joins one unit"),
    ("5 g / mL",            "g",         ["CA-NUM-002"], "and its first token is not it"),
    ("5 kg·m",              "kg·m",      [],             "a middle dot needs no spaces"),
    ("5 kg·m",              "kg",        ["CA-NUM-002"], "and its first fragment is not it"),
    ("5 J K⁻¹",             "J K⁻¹",     [],             "a marked capital continues"),
    ("5 J K⁻¹",             "J",         ["CA-NUM-002"], "so the bare joule does not"),
]


@pytest.mark.parametrize("span,unit,expected,why", SPACED_UNITS)
def test_a_spaced_unit_is_one_unit_through_the_fence(span, unit, expected, why):
    """MUTATIONS, four, each with the row it reddens:

    * *stop at whitespace again* — delete the continuation loop in
      `_spaced_unit`, and every BLOCK row above goes green: that is the shipped
      behaviour slice 2 called structural and the gold called 9 of 11 false
      passes;
    * *accept the bare first token when a continuation exists* — return
      `[(parts[0], …)] + [(join, …)]` from `_unit_candidates`, and the same BLOCK
      rows go green while the PASS rows stay green, which is exactly why E4
      alone does not close the defect (`RESULTS-GOLD.md` §3);
    * *drop the join* — return `[]` for a spaced expression, and every PASS row
      whose unit holds a space reddens;
    * *treat any word as a continuation* — make `_continues_unit` return True,
      and the MIRRORS redden. That last one is the trade this rule is
      constantly one edit away from: a continuation test loose enough to catch
      every unit blocks `5 g sample` on a correct annotation.

    Every fix here ships with its mirror, which is D157 lesson 3."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=span.split()[0].rstrip("%"), unit=unit,
                                    src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


@pytest.mark.parametrize("span,unit,expected,why", SPACED_UNITS)
def test_a_spaced_unit_is_one_unit_through_results_json(span, unit, expected, why):
    """The same table through the OTHER interface.

    Both locators reach one `contains_pair`, and D157 lesson 3 is that a fix
    asserted through one interface is a fix asserted once: the `1e+5` sign bug
    survived 3,015 tests because no test compared a positive explicit exponent
    with its negative through both. A rule about what a unit IS cannot be
    allowed to hold for the fence and not for a `results.json` quantity."""
    value = span.split()[0].rstrip("%")
    files = {"experiments/e1/metadata.yml":
             b"code_version: v3\ninputs:\n  - src.txt@v3\n",
             "experiments/e1/src.txt": ("header\n" + span + "\n").encode(),
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "q", "value": value, "unit": unit,
                                  "source": "src.txt@v3#L2"}],
                  "convergence": {"converged": True}}).encode()}
    got = [f.rule for f in run_checks(files, ["number_source"]).findings]
    assert got == expected, why


def test_a_continuation_is_unit_shaped_in_itself_not_marker_bearing():
    """MUTATION: test for a marker ANYWHERE in the token instead of parsing the
    token as an expression over named fragments.

    That is what the first build of this rule did, and review found it reads
    short prose as a unit: `wet/dry` is a word with a slash, `batch-1` a word
    with a hyphen, `sample¹` a word with a footnote, and each turned a correct
    `(5, g)` into a non-overridable block. Guards against brackets and long
    words did not draw the boundary either, because the boundary is not length —
    it is whether the token PARSES: a named fragment, a fragment with an
    exponent attached, or such atoms joined by a solidus or a middle dot.

    The cost is stated rather than hidden: a unit nothing here names (`mK⁻¹`)
    does not continue, so before a join the bare token still matches as it does
    today, and after a join the expression is unreadable and blocks."""
    from crossaudit.dcl.numbers import _continues_unit

    for token in ("min⁻¹", "h⁻¹", "s-1", "min−1", "m^2", "vol/vol", "%",
                  "K⁻¹", "Pa·s", "mol⁻¹·K⁻¹·s⁻¹", "hours", "µm"):
        assert _continues_unit(token), token
    for token in ("sample", "of", "later", "powder", "Ni", "at", "in", "bar",
                  "S1", "A2", "(heating/cooling", "heating/cooling", "",
                  "wet/dry", "batch-1", "sample\u00b9", "mK⁻¹", "/", "g/"):
        assert not _continues_unit(token), token


def test_a_bare_element_symbol_or_capital_needs_a_marker_to_continue():
    """MUTATION: drop the element and bare-capital refusal from
    `_continues_unit`.

    `K`, `Pa`, `N`, `C`, `S`, `P`, `H`, `O`, `F`, `B`, `V`, `W`, `Y`, `I` and
    `U` are unit symbols AND element symbols, and `5 g K` is five grams of
    potassium far more often than it is grams per kelvin; a bare capital is a
    labelled batch (`5 g A`) as often as it is an ampere. They are in the
    fragment table because `5 J K⁻¹` has to read `K⁻¹` — so the refusal is on
    the BARE form, and a structural marker brings them back."""
    from crossaudit.dcl.numbers import contains_pair

    for element in ("K", "Pa", "N", "C", "S", "P", "H", "O", "F", "B", "V",
                    "W", "Y", "I", "U", "Ni", "Ti", "A", "T", "M"):
        assert contains_pair(f"5 g {element}", "5", "g"), element
    assert not contains_pair("5 J K⁻¹", "5", "J")
    assert contains_pair("5 J K⁻¹", "5", "J K⁻¹")
    assert not contains_pair("5 mPa·s", "5", "mPa")


#: A scan that stops without reaching a boundary has read a PREFIX of the unit,
#: and a prefix never satisfies. Review found the first build handing that
#: prefix back through three different stops.
STOPPED_SCANS = [
    ("5 g / 100 mL",                   "g /",       "an expression ending on an operator"),
    ("5 g / 100 mL",                   "g",         "and its first token"),
    ("5 kg m sr⁻¹ mol⁻¹ K⁻¹ s⁻¹ A⁻¹",  "kg m sr⁻¹ mol⁻¹ K⁻¹ s⁻¹", "seven tokens, six read"),
    ("5 kg m sr⁻¹ mol⁻¹ K⁻¹ s⁻¹ A⁻¹",  "kg m",      "and any shorter prefix of them"),
    ("5 kg m qz",                      "kg m",      "a token the table cannot read"),
    ("5 kg m qz",                      "kg m qz",   "and the whole line it appears in"),
]


@pytest.mark.parametrize("span,unit,why", STOPPED_SCANS)
def test_a_stopped_scan_yields_no_reading_at_all(span, unit, why):
    """MUTATION: return the joined prefix when `_spaced_unit` reports the scan
    incomplete — that is, delete the `complete` flag and always join.

    Review's first P1. The token cap, an operator with nothing after it, and a
    token that is neither a unit nor prose each stopped the scan, and
    `_unit_candidates` then offered what had been joined so far as if it were
    the whole unit: `5 kg m sr` satisfied `kg m`, a seven-token expression
    satisfied its first six, and `5 g / 100 mL` satisfied `g /`. Contiguous
    sweeps confirmed it was a grammar defect and not three curiosities —
    expressions of 7 to 20 tokens ALL accepted their first six.

    An unreadable unit is a block. The one thing it must never be is a shorter
    reading that happens to be readable, which is the defect D157 rounds 3-5
    record being fixed three times and this is the fourth.

    `qz` and not `Ni`: a short LOWERCASE token that is not a named fragment is
    a unit this table does not know, so the scan truncates. A capitalised one
    is a substance or a label — `5 wt % Ni` — and ends the expression, which is
    the row beside this table that must stay green."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value="5", unit=unit, src=cite(span))])}
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"], why


def test_no_prefix_of_an_overflowing_expression_is_ever_a_reading():
    """The sweep behind the table above, kept as the guard.

    One case would be a curiosity; 14 contiguous expression lengths each
    handing back their first six tokens is a grammar defect, so the whole range
    is asserted — the same discipline as the exponent sweep."""
    from crossaudit.dcl.numbers import contains_pair

    sup = "⁰¹²³⁴⁵⁶⁷⁸⁹"
    for n in range(2, 21):
        tokens = ["kg"] + [f"s⁻{sup[i % 9 + 1]}" for i in range(n - 1)]
        span = "5 " + " ".join(tokens)
        for k in range(1, n):
            assert not contains_pair(span, "5", " ".join(tokens[:k])), (n, k)
        # Within the cap the whole expression reads; past it, nothing does.
        assert contains_pair(span, "5", " ".join(tokens)) is (n <= 6), n


def test_a_substance_or_label_ends_a_joined_expression_before_the_table_is_read():
    """MUTATION: in `_is_boundary`, consult `_fragment` before the element and
    bare-capital test — the order the second build had.

    `_continues_unit` already refuses a bare element symbol or bare capital,
    so the token reaches `_is_boundary`; there `K`, `Pa`, `A` and twelve more
    elements are ALSO named fragments (for `K⁻¹`, `Pa·s`), and answering the
    table first made them "a unit this table cannot read" — a block on `wt %`
    for `5 wt % K` where `5 wt % Ni` passed. The second review counted 15 of
    118. After `5 g` the first-continuation path never asks, which is why the
    118-element loop above stayed green while this one was red.

    The mirror: a marker still brings the element back as a unit."""
    from crossaudit.dcl.numbers import _ELEMENTS, contains_pair

    for element in sorted(_ELEMENTS):
        assert contains_pair(f"5 wt % {element}", "5", "wt %"), element
        assert contains_pair(f"5 kg m {element}", "5", "kg m"), element
    for label in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert contains_pair(f"5 wt % {label}", "5", "wt %"), label
    assert contains_pair("5 wt % Sample", "5", "wt %")
    assert not contains_pair("5 wt % K⁻¹", "5", "wt %")
    assert contains_pair("5 wt % K⁻¹", "5", "wt % K⁻¹")
    assert not contains_pair("5 kg m Pa·s", "5", "kg m")
    assert contains_pair("5 kg m Pa·s", "5", "kg m Pa·s")
    for element in sorted(_ELEMENTS):    # the sixth review: a mark on an element is a unit
        assert not contains_pair(f"5 kg m {element}‰", "5", "kg m"), element
        assert not contains_pair(f"5 kg m {element}%", "5", "kg m"), element


#: Prose after a JOIN, in the shapes the review used after `5 g`, and the
#: unit-shaped tokens they must not be confused with. Each row is asserted
#: after `5 wt %` and after `5 kg m`, because both joins reach `_is_boundary`
#: by the same path and both were wrong.
JOINED_PROSE = [
    ("heating/cooling", "words joined by a solidus, a word among them"),
    ("wet/dry",      "two short words the module names, on a solidus"),
    ("batch-1",      "a label: a hyphen-numeral on a stem longer than a symbol"),
    ("sample\u00b9", "a footnote on a long stem"),
    ("A2",           "a label with a digit"),
    ("Li₂O",         "a formula with a subscript"),
    ("H2O",          "a formula with a digit"),
    ("sample2",      "a digit on a long stem"),
    ("sample",       "a word"),
    ("of",           "a function word"),
    ("Sample",       "a capitalised word"),
    ("high-purity",  "a hyphenated word — the third review's base-pass regression"),
    ("as-received",  "a hyphenated word whose first part is a function word"),
    ("e.g.",         "an abbreviation of single letters"),
    ("sample，",      "a word with trailing punctuation the scanner keeps"),
    ("样品",           "a word in a script that writes no unit symbol"),
    ("we're ready",   "a contraction — the scanner splits at the apostrophe"),
    ("don't",         "and a straight-apostrophe one"),
    ("l’état",        "and a typographic one"),
    ("α",             "a bare Greek letter: a variable"),
    ("pH",            "a short common word this module names"),
    ("dry powder",    "and a three-letter one — `dry` has a symbol's length"),
    ("sample%",       "a long word with a percent sign"),
    ("dry%",          "a short named word with one — the fifth review's row"),
    ("wet‰",          "and with a per-mille sign"),
    ("sample_name",   "an underscored word"),
    ("n.b.",          "a dotted abbreviation the module names"),
    ("样品。",          "trailing full-width punctuation"),
    ("batch-1/2",     "a label with a word among its parts and a digit"),
    ("Sample%",       "a capitalised word with a percent sign"),
    ("dry％",          "a full-width percent sign, which the scanner strips as punctuation"),
    ("2/dry",         "a numeral joined to a word: a label"),
    ("10",            "a numeral"),
]
JOINED_UNREADABLE = [
    ("xyz⁻¹",  "an exponent on a stem this table does not name"),
    ("run-2",  "an ASCII one on a three-letter stem — the shape of `s-1`"),
    ("m2",     "a digit on a short lower-case stem — the shape of `m2` the unit"),
    ("m₂",     "and a subscript one"),
    ("kg-m",   "short stems on a hyphen"),
    ("lot_id", "short stems on an underscore"),
    ("ab_cd",  "and two unknown ones"),
    ("oz·yd",  "short unknown parts on a middle dot"),
    ("oz⋅yd",  "and on a dot operator"),
    ("abc%",   "a percent sign on a short unnamed stem"),
    ("Ni‰",    "a per-mille sign on an element symbol — the sixth review's 118 rows"),
    ("K%",     "and a percent sign on one"),
    ("lot_id/2", "short parts with a digit added — the sixth review's fail-open"),
    ("ab_cd/2", "the same"),
    ("kg-m/2", "fragments with a digit added"),
    ("oz/yd/2", "short unknown parts with one"),
    ("qz/2",   "and a short unknown token with one"),
    ("kg-m/s", "fragments joined to a fragment: a unit half-read"),
    ("dry·g",  "a word joined to a fragment: the same"),
    ("kg／m",   "a full-width solidus, which is not a joiner this module reads"),
    ("kg－m",   "a full-width hyphen"),
    ("lot＿id", "a full-width underscore"),
    ("oz／yd",  "and short unknown parts on a full-width solidus"),
    ("dry／wet", "even when the parts are named words"),
    ("kg／m/dry", "a full-width joiner beside ASCII ones — the seventh review's bypass"),
    ("kg／m-batch", "the same"),
    ("kg－m/batch", "the same"),
    ("lot＿id/batch", "the same"),
    ("oz／yd-batch", "the same"),
    ("dry／wet-batch", "the same"),
    ("2/g",    "a numeral joined to a fragment — the seventh review's digit exit"),
    ("2/kg",   "the same"),
    ("2／g",    "and with a full-width solidus"),
    ("10／20",  "a full-width joiner between numerals"),
    ("g/xyz",  "a fragment joined to something that is not one"),
    ("oz/yd",  "short unknown parts on a solidus — the third review's false pass"),
    ("x/y",    "and its one-letter form"),
    ("a.u.",   "arbitrary units: a dotted abbreviation not named as a word — the fourth's"),
    ("p.u.",   "per-unit, the same shape"),
    ("r.u.",   "relative units"),
    ("qz",     "a short lower-case token: not a word, not a fragment"),
    ("°X",     "a degree sign on an unnamed letter"),
]


@pytest.mark.parametrize("token,why", JOINED_PROSE)
def test_prose_after_a_join_is_the_boundary_it_is_after_one_token(token, why):
    """MUTATION: in `_is_boundary`, return False for every token that is not
    purely alphabetic — the second build's rule, which the review found
    blocked `wt %` before `wet/dry`, `batch-1`, `sample¹`, `A2`, `Li₂O` and
    `H2O`: six forms the first-continuation path had just been taught to read
    as words. The prose shapes are enumerated in `_is_boundary`; this is the
    enumeration, asserted at both joins."""
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair(f"5 wt % {token}", "5", "wt %"), why
    assert contains_pair(f"5 kg m {token}", "5", "kg m"), why


@pytest.mark.parametrize("token,why", JOINED_UNREADABLE)
def test_an_unreadable_unit_after_a_join_still_blocks(token, why):
    """The mirror of the table above: widening prose to "anything that is not
    a fragment" would pass these, and each is, or has the shape of, a unit
    half-read. The third review's `oz/yd` is the row: two short lower-case
    parts on a solidus are the shape of a unit unless the module names them as
    words, which is the only reason `wet/dry` reads and `x/y` does not."""
    from crossaudit.dcl.numbers import contains_pair

    assert not contains_pair(f"5 wt % {token}", "5", "wt %"), why
    assert not contains_pair(f"5 kg m {token}", "5", "kg m"), why


def test_the_first_continuation_still_reads_the_shapes_the_join_blocks():
    """`wet/dry`, `run-2`, `m2` after a ONE-token unit end it as they always
    did (`_continues_unit` refuses them, and no join has begun). The block on
    the same shapes after a join is the disclosed limit, not a change here."""
    from crossaudit.dcl.numbers import contains_pair

    for token in ("wet/dry", "x/y", "oz/yd", "run-2", "m2", "kg-m", "high-purity", "样品",
                  "a.u.", "we're", "qz"):
        assert contains_pair(f"5 g {token} sample", "5", "g"), token


# ---------------------------------------------------------------------------------
# Study 10 (slice 4): E5 and E6, the two folds that cannot shorten a token.
# ---------------------------------------------------------------------------------

E5_ROWS = [
    ("80 wt.% sub-micron",   "wt.%",  True,  "a period before a percent sign continues the token"),
    ("80 wt.% sub-micron",   "wt",    False, "and its prefix is a prefix"),
    ("80 wt.% sub-micron",   "wt%",   False, "and the period is a character (gold R4)"),
    ("5 wt.‰ ash",           "wt.‰",  True,  "per mille too"),
    ("5 g. Then",            "g",     True,  "a period before a space still ends the token"),
    ("5 g.",                 "g",     True,  "and before the end of the text"),
    ("5 kg.m of torque",     "kg.m",  True,  "a period before a letter continued already"),
    ("5 %. Next",            "%",     True,  "a percent sign then a period: the period ends it"),
]
E5_JOIN_ROWS = [
    ("5 kg wt.% Ni",        "kg",        False, "the first review's P1: a lengthened token must still continue"),
    ("5 kg wt.% Ni",        "kg wt.%",   True,  "and the whole join reads"),
    ("5 kg vol.% ethanol",  "kg",        False, "the same for a volume basis"),
    ("5 kg wt.‰ ash",       "kg",        False, "and per mille"),
    ("5 g approx.% x",      "g",         True,  "a word with `.%` still ends a one-token unit"),
    ("5 kg m approx.% x",   "kg m",      True,  "and a join — the review's new-block regression"),
    ("5 kg m e.g.% x",      "kg m",      True,  "a dotted abbreviation with `.%` too"),
    ("5.% excess",          ".%",        False, "`.%` at a token's start is not a unit"),
    ("5.% excess",          "%",         False, "and nothing else reads there either"),
    ("5 kg K.% sample",     "kg",        True,  "an element with `.%` is refused as the bare element is"),
    ("5 kg m Ni.% x",       "kg m",      True,  "and ends a join as the bare element does"),
    ("5 kg Bq.% sample",    "kg",        False, "a capitalised non-element fragment continues"),
    ("5 kg Bq.% sample",    "kg Bq.%",   True,  "and the join reads"),
    ("5 kg wt.%% x",        "kg",        True,  "a fragment glued to junk is not unit-shaped and ends the unit — "
                                                "the base cut it to `wt` and continued; that was the scanner, not a reading"),
    ("5 kg .% sample",      "kg",        True,  "a bare `.%` reads nothing, as before"),
]
E6_ROWS = [
    ("0.22 s−1 (13 rpm)",    "s⁻¹",   True,  "U+2212 in the source, superscript in the annotation"),
    ("0.22 s⁻¹ (13 rpm)",    "s−1",   True,  "and the other way"),
    ("0.22 s-1 (13 rpm)",    "s⁻¹",   True,  "an ASCII hyphen in the source"),
    ("0.22 s⁻¹ (13 rpm)",    "s-1",   True,  "and in the annotation"),
    ("0.5 dm3/s flow",       "dm³/s", True,  "a superscript digit against an ASCII one"),
    ("0.5 dm³/s flow",       "dm3/s", True,  "and the other way"),
    ("0.22 s⁻¹ (13 rpm)",    "s⁻²",   False, "a different exponent is a different unit"),
    ("0.22 s−1 (13 rpm)",    "s-2",   False, "under either rendering"),
    ("5 °C min⁻¹ ramp",      "°C min-1", True, "the fold reaches a spaced expression's comparison"),
]


@pytest.mark.parametrize("span,unit,expected,why", E5_ROWS + E5_JOIN_ROWS + E6_ROWS)
def test_e5_and_e6_fold_without_shortening_a_token(span, unit, expected, why):
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair(span, span.split()[0].rstrip(".%"), unit) is expected, why


def test_a_period_percent_atom_continues_a_join_for_every_fragment():
    """GENERATED over the fragment table (the first review's sweep was 224
    combinations): for every named fragment f, `5 kg f.%` must block `kg` and
    read `kg f.%`. MUTATION: drop the `.%` atom from `_unit_atom` — every row
    reddens, because the join stops at `kg` and the prefix is offered."""
    from crossaudit.dcl.numbers import _UNIT_FRAGMENTS, _ELEMENTS, contains_pair

    for f in sorted(_UNIT_FRAGMENTS):
        if f in _ELEMENTS or (len(f) == 1 and f.isupper()) or not f.isalpha():
            continue                       # bare elements and marks are not continuations by design
        for sign in ("%", "‰"):           # `sample` after: a word, so the join is complete
            assert not contains_pair(f"5 kg {f}.{sign} sample", "5", "kg"), (f, sign)
            assert contains_pair(f"5 kg {f}.{sign} sample", "5", f"kg {f}.{sign}"), (f, sign)


def test_the_period_continuer_set_is_e5(monkeypatch):
    """MUTATION: empty `_PERIOD_CONTINUERS` — E5 off. `80 wt.%` annotated `wt.%`
    must redden, and nothing the base read must move."""
    import crossaudit.dcl.numbers as numbers

    monkeypatch.setattr(numbers, "_PERIOD_CONTINUERS", frozenset())
    assert not numbers.contains_pair("80 wt.% sub-micron", "80", "wt.%")
    assert numbers.contains_pair("5 kg.m of torque", "5", "kg.m")
    assert numbers.contains_pair("5 g. Then", "5", "g")


def test_the_exponent_fold_is_e6_and_lives_only_in_the_comparison(monkeypatch):
    """MUTATION: make `_unit_key` the identity on `normalise_unit` — E6 off. The
    cross-rendering rows must redden; the same-rendering ones must not."""
    import crossaudit.dcl.numbers as numbers

    monkeypatch.setattr(numbers, "_unit_key", numbers.normalise_unit)
    assert not numbers.contains_pair("0.22 s−1 (13 rpm)", "0.22", "s⁻¹")
    assert not numbers.contains_pair("0.5 dm3/s flow", "0.5", "dm³/s")
    assert numbers.contains_pair("0.22 s⁻¹ (13 rpm)", "0.22", "s⁻¹")


def test_the_fold_does_not_reach_the_notation_rule_or_the_scanner():
    """The mirrors E6 must not move: `10⁵` stays notation the check refuses, a
    superscript footnote stays prose, and `normalise_unit` folds nothing new
    (the fragment table, the boundary rule and the range split read the source
    as written). MUTATION: fold `−` or the superscripts inside `normalise_unit`
    instead of `_unit_key`."""
    from crossaudit.dcl.numbers import contains_pair, normalise_unit

    assert not contains_pair("3 × 10⁵ mbar", "3", "mbar")
    assert not contains_pair("pressure of 10⁵ Pa", "10", "")
    assert contains_pair("5 g sample¹ dried", "5", "g")
    assert normalise_unit("s⁻¹") == "s⁻¹" and normalise_unit("s−1") == "s−1"
    assert not contains_pair("5 kg m xyz⁻¹", "5", "kg m")       # the boundary rule, unchanged


# ---------------------------------------------------------------------------------
# Study 11 (slice 5): E1, the endpoints of a range.
# ---------------------------------------------------------------------------------

E1_ROWS = [
    ("775–850 °C",            "775",  "°C",      True,  "an en-dash range, the low endpoint"),
    ("775–850 °C",            "850",  "°C",      True,  "and the high one, which needed no rule"),
    ("775 – 850 °C",          "775",  "°C",      True,  "spaced dashes"),
    ("775—850 °C",            "775",  "°C",      True,  "an em dash"),
    ("99-102 kPa",            "99",   "kPa",     True,  "an ASCII hyphen"),
    ("1.5 – 6 sccm",          "1.5",  "sccm",    True,  "a decimal low endpoint"),
    ("775–850°C",             "775",  "°C",      True,  "closed up: the same answer as the `_RANGE` split"),
    ("20–25 wt %",            "20",   "wt %",    True,  "a spaced tail after the high endpoint"),
    ("20–25 °C min⁻¹",        "20",   "°C min⁻¹", True, "a spaced expression after it"),
    ("20–25 °C min⁻¹",        "20",   "°C",      False, "and its prefix is a prefix there too"),
    ("1,000–1,500 rpm",       "1,000", "rpm",    True,  "a thousands group in both endpoints"),
    ("5-10 °C",               "5",    "°C",      True,  "an ASCII hyphen with no space either side"),
    ("10 - 5 °C",             "10",   "°C",      False, "a SPACED ASCII hyphen is also a subtraction: refused (round 2)"),
    ("5 - 10 °C",             "5",    "°C",      False, "so a spaced-hyphen range is a false block, disclosed"),
    ("5 -10 °C",              "5",    "°C",      False, "and one space on either side is enough to refuse"),
    ("5- 10 °C",              "5",    "°C",      False, "either side"),
    ("5 – −3 °C",             "5",    "°C",      True,  "a signed high endpoint"),
    ("775–850 °C",            "800",  "°C",      False, "the interior is not in the text"),
    ("775–850 °C at 99 kPa",  "775",  "kPa",     False, "a unit borrowed across a different quantity"),
    ("5 g–10 mL",             "5",    "mL",      False, "a low endpoint with its own unit distributes nothing"),
    ("5 g–10 mL",             "5",    "g",       True,  "it keeps its own"),
    ("5–10",                  "5",    "",        True,  "no unit after: the empty-unit row states the value"),
    ("5–10",                  "5",    "°C",      False, "and nothing else"),
    ("5 g – heat to 10 °C",   "5",    "°C",      False, "a dash followed by a word is not a range"),
    ("5–10 × 10⁵ Pa",         "5",    "Pa",      False, "a high endpoint continued by refused notation offers nothing"),
    ("5-fold excess",         "5",    "fold",    False, "a hyphenated word is not a range (unchanged)"),
    ("2.54-cm diameter",      "2.54", "cm",      False, "a compound adjective is not a range (unchanged)"),
    ("1–2–3 °C",              "1",    "°C",      False, "a chain: the first number's high endpoint is itself continued by a dash, so nothing is read (Amendment 1)"),
    ("1–2–3 °C",              "2",    "°C",      True,  "the middle number is the low endpoint of the last range and reads its unit (Amendment 1)"),
]


@pytest.mark.parametrize("span,value,unit,expected,why", E1_ROWS)
def test_e1_offers_the_high_endpoints_unit_to_the_low_endpoint(span, value, unit, expected, why):
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair(span, value, unit) is expected, why


def test_e1_is_the_range_tail_and_nothing_else(monkeypatch):
    """MUTATION: empty `_RANGE_TAIL` — E1 off. Every low-endpoint row reddens; the
    high endpoints, the closed-up `_RANGE` split and the mirrors do not move."""
    import re
    import crossaudit.dcl.numbers as numbers

    monkeypatch.setattr(numbers, "_RANGE_TAIL", re.compile(r"(?!x)x"))
    assert not numbers.contains_pair("775–850 °C", "775", "°C")
    assert not numbers.contains_pair("99-102 kPa", "99", "kPa")
    assert numbers.contains_pair("775–850 °C", "850", "°C")
    assert numbers.contains_pair("(20°C-25°C)", "20", "°C")
    assert not numbers.contains_pair("775–850 °C", "800", "°C")


def test_e1_never_offers_the_interior_or_a_borrowed_unit():
    """MUTATION: accept any number between the endpoints, or take the unit after
    the high endpoint for any earlier number on the line — each is a truth claim
    about an interval or a different quantity, D155's line."""
    from crossaudit.dcl.numbers import contains_pair

    for interior in ("776", "800", "849.5"):
        assert not contains_pair("775–850 °C", interior, "°C"), interior
    assert not contains_pair("hold 10 min, then 775–850 °C", "10", "°C")
    assert contains_pair("hold 10 min, then 775–850 °C", "10", "min")


def test_e1_covers_the_whole_range_in_the_quote_interval():
    """The offered end reaches through the high endpoint's unit, so a quotation
    that stops inside the range does not contain the pair."""
    from crossaudit.dcl.numbers import pair_occurrences

    spans = list(pair_occurrences("ramp at 775–850 °C for 2 h", "775", "°C"))
    assert spans == [(8, 18)], spans          # `775–850 °C`, through the unit


# ---------------------------------------------------------------------------------
# Study 12 (slice 6): E2, a list with one trailing unit.
# ---------------------------------------------------------------------------------

E2_ROWS = [
    ("0, 20, 40, 80 wt.% powders", "0",   "wt.%",  True,  "the first member of a four-member list"),
    ("0, 20, 40, 80 wt.% powders", "40",  "wt.%",  True,  "and a middle one"),
    ("0, 20, 40, 80 wt.% powders", "80",  "wt.%",  True,  "the unit-bearing member needed no rule"),
    ("106 and 25 μm sieves",      "106", "μm",    True,  "the word `and` as the separator"),
    ("5, 10 and 20 °C",           "5",   "°C",    True,  "three members, two separator kinds"),
    ("5, 10, and 20 °C",          "5",   "°C",    True,  "an Oxford comma"),
    ("5 or 10 °C",                "5",   "°C",    True,  "the word `or`"),
    ("5 and/or 10 °C",            "5",   "°C",    True,  "`and/or`"),
    ("0.2 kg, 0.5 kg, or 1 kg",   "0.2", "kg",    True,  "a member with its own unit keeps it"),
    ("0.2 kg, 0.5 kg, or 1 kg",   "0.2", "μm",    False, "and nothing is borrowed"),
    ("5 g, 10 mL water",          "5",   "mL",    False, "a comma between unrelated quantities"),
    ("5 g, 10 mL water",          "5",   "g",     True,  "each keeps its own"),
    ("1 : 1 : 0.125–0.5 mass ratio", "1", "ratio", False, "a colon is not a separator"),
    ("5; 10 °C",                  "5",   "°C",    False, "nor a semicolon"),
    ("5, 10 × 10⁵ Pa",            "5",   "Pa",    False, "refused notation on a member stops the list"),
    ("5, 10 °C min⁻¹",            "5",   "°C min⁻¹", True, "a spaced expression after the last member"),
    ("5, 10 °C min⁻¹",            "5",   "°C",    False, "and its prefix is a prefix"),
    ("5,000 and 10,000 rpm",      "5,000", "rpm", True,  "a thousands comma is not a separator"),
    ("5, 10–20 °C",               "5",   "°C",    True,  "a range as the last member: E1 inside E2"),
    ("5 and 10",                  "5",   "",      True,  "no unit after: the empty-unit row states the value"),
    ("5 and 10",                  "5",   "°C",    False, "and nothing else"),
    ("5, 10 kg, or 20 μm",        "5",   "kg",    True,  "the first unit-bearing member decides (gold R8)"),
    ("5, 10 kg, or 20 μm",        "5",   "μm",    False, "not a later one"),
    ("5, 10, 20 °C",              "10",  "°C",    True,  "a middle member is a list member of its own"),
    ("Step 5, 10 mL of water",   "5",   "mL",    False, "a labelled number is not a member (amendment 1)"),
    ("Fig. 5, 10 °C",             "5",   "°C",    False, "with or without the period"),
    ("Sample 5, 10 °C",           "5",   "°C",    False, "a sample label"),
    ("at 5, 10 °C",               "5",   "°C",    True,  "a preposition is not a label"),
    ("step 5, 10 mL",             "5",   "mL",    False, "case-insensitive on the label word"),
    ("Figs. 5, 10 °C",            "5",   "°C",    False, "a plural label (round 2)"),
    ("Step: 5, 10 mL",            "5",   "mL",    False, "a colon after the label (round 2)"),
    ("Pages 5, 10 and 20 were",   "5",   "were",  False, "`pages` is a label (round 2)"),
    ("Schemes 5, 10 °C",          "5",   "°C",    False, "and `schemes`"),
    ("12,5 °C",                   "12",  "°C",    False, "a decimal comma is one number, not a list (round 2)"),
    ("12,5 °C",                   "12,5", "°C",   False, "and this module does not read it as a number either"),
    ("12, 5 °C",                  "12",  "°C",    True,  "a comma with a space is a separator"),
    ("12,and 5 °C",               "12",  "°C",    False, "`,and` glued is not a separator either"),
    ("Experiment 5, 10 °C",       "5",   "°C",    False, "more label stems (round 2)"),
    ("Tab. 5, 10 °C",             "5",   "°C",    False, "`Tab.`"),
    ("Eqn. 5, 10 °C",             "5",   "°C",    False, "`Eqn.`"),
    ("Compound 5, 10 °C",         "5",   "°C",    False, "`Compound`"),
    ("Step-5, 10 mL",             "5",   "mL",    False, "a hyphen after the label"),
    ("Heat 5, 10 mL",             "5",   "mL",    True,  "a capitalised word that is not a label distributes — the list is finite and named"),
    ("Step 5–10 °C",              "5",   "°C",    False, "the label guard reaches E1 too: steps five to ten"),
    ("at 5–10 °C",                "5",   "°C",    True,  "and a range after a preposition still reads"),
    ("Appendices 5, 10 °C",       "5",   "°C",    False, "an irregular plural (round 3)"),
    ("Formulae 5, 10 °C",         "5",   "°C",    False, "another"),
    ("Supplement 5, 10 °C",       "5",   "°C",    False, "a stem the second review named"),
    ("Trial #5, 10 °C",           "5",   "°C",    False, "a hash after the label"),
    ("samples 5, 10 and 20 were", "5",   "were",  False, "`samples` is a label word (amendment 1)"),
    ("heated 5, 10 and 20 were",  "5",   "were",  True,  "a word after the last member reads as the base reads `20 were` for (20, were): the check verifies transcription, not unit-hood"),
]


@pytest.mark.parametrize("span,value,unit,expected,why", E2_ROWS)
def test_e2_distributes_one_trailing_unit_over_bare_members(span, value, unit, expected, why):
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair(span, value, unit) is expected, why


def test_e2_is_the_list_tail_and_nothing_else(monkeypatch):
    """MUTATION: empty `_LIST_TAIL` — E2 off. The distributing rows redden; the
    adjacency rows, E1 and the mirrors do not move."""
    import re
    import crossaudit.dcl.numbers as numbers

    monkeypatch.setattr(numbers, "_LIST_TAIL", re.compile(r"(?!x)x"))
    assert not numbers.contains_pair("0, 20, 40, 80 wt.% powders", "0", "wt.%")
    assert not numbers.contains_pair("106 and 25 μm sieves", "106", "μm")
    assert numbers.contains_pair("0, 20, 40, 80 wt.% powders", "80", "wt.%")
    assert numbers.contains_pair("0.2 kg, 0.5 kg, or 1 kg", "0.2", "kg")
    assert numbers.contains_pair("775–850 °C", "775", "°C")


def test_e2_guard_is_adjacency_not_a_flag():
    """MUTATION: read a list member's own unit as a separator-less continuation —
    `0.2 kg, 0.5 kg, or 1 kg` must keep `(0.2, kg)` green and `(0.2, μm)` red; a
    colon or semicolon must never separate. MUTATION: delete the refused-notation
    stop — the first review showed `(5, Pa)` stays red under that mutant because
    nothing reads `Pa` past `× 10⁵`; what the stop actually prevents is the
    operator itself being offered as the unit, so `(5, ×)` is the row that
    reddens."""
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair("0.2 kg, 0.5 kg, or 1 kg", "0.5", "kg")
    assert not contains_pair("0.2 kg, 0.5 kg, or 1 kg", "0.5", "μm")
    assert not contains_pair("5: 10 °C", "5", "°C")
    assert not contains_pair("5; 10 °C", "5", "°C")
    assert not contains_pair("5, 10 × 10⁵ Pa", "5", "Pa")
    assert not contains_pair("5, 10 × 10⁵ Pa", "5", "×")


def test_e2_covers_the_whole_list_in_the_quote_interval():
    from crossaudit.dcl.numbers import pair_occurrences

    spans = list(pair_occurrences("mixed at 0, 20, 40, 80 wt.% ratios", "0", "wt.%"))
    assert spans == [(9, 27)], spans          # `0, 20, 40, 80 wt.%`, through the unit


E3_ROWS = [
    ("LiNi0.8Co0.2O2",          "0.8",  "",  True,  "a decimal stoichiometric subscript"),
    ("LiNi0.8Co0.2O2",          "0.2",  "",  True,  "and the second one"),
    ("LiNi0.8Co0.2O2",          "8",    "",  False, "the digits after the point are not a value"),
    ("LiNi0.8Co0.2O2",          "2",    "",  False, "an integer subscript is unreadable"),
    ("LiNi0.8Co0.2O2",          "0.8",  "M", False, "E3 yields nothing for a transcribed unit"),
    ("H2O",                     "2",    "",  False, "`H2O`"),
    ("Cr2O3",                   "3",    "",  False, "`Cr2O3`"),
    ("Co(NO3)2·6H2O",           "6",    "",  True,  "a hydrate count after the middle dot: the ORDINARY scan reads it, E3 does not"),
    ("Co(NO3)2·6H2O",           "3",    "",  False, "a bracketed integer"),
    ("Ni0.95Co0.04Mn0.01(OH)2", "0.04", "",  True,  "a subscript before a bracket"),
    ("Ni0.95Co0.04Mn0.01(OH)2", "0.01", "",  True,  "the last decimal"),
    ("Li0.75H1.25RuO3",         "1.25", "",  True,  "a subscript above one"),
    ("SrCo0.6Fe0.4O3−δ",        "0.6",  "",  True,  "the non-stoichiometry marker `−δ` (§1a)"),
    ("SrCo0.6Fe0.4O3−δ",        "0.4",  "",  True,  "and its second decimal"),
    ("SrCo0.6Fe0.4O3±δ",        "0.6",  "",  True,  "`±δ`"),
    ("SrCo0.6Fe0.4O3−0.5",      "0.6",  "",  False, "the marker before a digit is a subtraction: not a formula token"),
    ("SrCo0.6Fe0.4O3−0.5",      "0.5",  "",  True,  "and the signed number after it is the ordinary scan's, not E3's"),
    ("Zr(HPO4)0.5·H2O",         "0.5",  "",  True,  "after a bracket: the ordinary scan, not E3"),
    ("x²0.5",                   "0.5",  "",  False, "glued to a superscript digit: `x²` is no element run"),
    ("Fig.3.2",                 "3.2",  "",  False, "a period precedes: a figure label"),
    ("v1.2.3",                  "1.2",  "",  False, "a period follows: a version"),
    ("run_v1.5",                "1.5",  "",  False, "an underscore in the token"),
    ("x=Ni0.5",                 "0.5",  "",  False, "an equals sign in the token"),
    ("\"Ni0.5\"",               "0.5",  "",  False, "quotation marks in the token"),
    ("Ni0.5×10³",               "0.5",  "",  False, "refused notation on the value"),
    ("pH7.4",                   "7.4",  "",  False, "letters that are not element symbols: not a formula"),
    ("Figure3.2",               "3.2",  "",  False, "a label glued to its number (the first review)"),
    ("Table1.2",                "1.2",  "",  False, "another"),
    ("SampleA0.8",              "0.8",  "",  False, "an identifier"),
    ("DOI10.1234",              "10.1234", "", False, "a DOI prefix"),
    ("version1.2",              "1.2",  "",  False, "a version"),
    ("Nice1.5",                 "1.5",  "",  False, "`ce` is not `Ce`: the parse is case-sensitive"),
    ("BaNaNa1.2",               "1.2",  "",  True,  "letters that merely spell symbols read: the parse is syntactic"),
    ("CoIn1.2",                 "1.2",  "",  True,  "another"),
    ("Ni２0.5O",                 "0.5",  "",  False, "a full-width digit BEFORE the decimal (the second review)"),
    ("Ni٢0.5O",                 "0.5",  "",  False, "an Arabic-Indic digit before it"),
    ("Ni२0.5O",                 "0.5",  "",  False, "a Devanagari digit before it"),
    ("LiNi0.5O₂",               "0.5",  "",  True,  "a subscript digit elsewhere in the formula is a digit (the second review)"),
    ("LiNi0.5O²",               "0.5",  "",  True,  "a superscript digit likewise"),
    ("LiNi0.5(OH)₂",            "0.5",  "",  True,  "and after a bracket"),
    ("CuSO4·0.5H2O",            "0.5",  "",  True,  "after the middle dot: the ORDINARY scan reads a bare number; E3 yields nothing"),
    ("Ⅷ0.5",                    "0.5",  "",  False, "a Roman numeral is numeric, not a letter"),
    ("Li₂Ni0.5O",               "0.5",  "",  True,  "a subscript digit before the letters is a digit of the charset"),
    ("Ni0.5O½",                 "0.5",  "",  False, "a vulgar fraction is no digit (the fourth review)"),
    ("Ni0.5OⅧ",                 "0.5",  "",  False, "nor a Roman numeral"),
    ("Ni0.5O⑧",                 "0.5",  "",  False, "nor a circled number"),
    ("Ni0.5O⑴",                 "0.5",  "",  False, "nor a parenthesised one"),
    ("Ni0.5O２",                 "0.5",  "",  True,  "a full-width digit is a decimal digit"),
    ("Fe³Ni0.5O",               "0.5",  "",  True,  "a superscript digit is admitted"),
    ("Ni0.5O2）",                "0.5",  "",  False, "a full-width bracket is outside the charset"),
    ("Ni0.5O2’s",               "0.5",  "",  False, "an apostrophe likewise"),
    ("Ni\u200d0.5O",            "0.5",  "",  True,  "a zero-width joiner before the digits: the ORDINARY scan's bare number (pre-existing), not E3 — see the interval test"),
    ("Ni0.5O−₂",                "0.5",  "",  False, "the marker before a subscript numeral (the third review)"),
    ("Ni0.5O−²",                "0.5",  "",  False, "before a superscript numeral"),
    ("Ni0.5O−Ⅷ",                "0.5",  "",  False, "before a Roman numeral"),
    ("Ni0.5±₂",                 "0.5",  "",  False, "`±` likewise"),
    ("Ni0.5.",                  "0.5",  "",  True,  "a decimal ending the token, sentence-final (the third review)"),
    ("Ni0.5,",                  "0.5",  "",  True,  "before a comma"),
    ("Fe1.2.3",                 "1.2",  "",  False, "a period and a digit follow: a version, whatever the letters"),
    ("Ni.0.5O",                 "0.5",  "",  False, "a period before the digits: neither the ordinary scan nor E3"),
    ("Ni0.5２O",                 "0.5",  "",  False, "a full-width digit continues the number (the first review)"),
    ("Ni0.5₂O",                 "0.5",  "",  False, "a subscript digit continues it"),
    ("Ni0.5٢O",                 "0.5",  "",  False, "an Arabic-Indic digit continues it"),
    ("(OH)2",                   "2",    "",  True,  "an integer after a bracket: the ORDINARY scan, not E3"),
    ("[Fe(CN)6]3−",             "6",    "",  True,  "the same after a bracket inside brackets"),
    ("Li1.3Mn0.4Nb0.3O2−xFx",   "0.4",  "",  True,  "the variable `x` after the marker"),
    ("Fe1.2V",                  "1.2",  "",  True,  "an alloy"),
    ("target LiNi0.8Co0.2O2.",  "0.8",  "",  True,  "sentence-final punctuation is stripped"),
    ("(LiNi0.8Co0.2O2)",        "0.2",  "",  True,  "brackets are formula characters"),
    ("0.8 alone",               "0.8",  "",  True,  "an unglued number: the ordinary scan"),
    ("LiCo0.2O2",               "0.2",  "",  True,  "a different formula satisfies the same pair"),
]


@pytest.mark.parametrize("span,value,unit,expected,why", E3_ROWS)
def test_e3_a_decimal_stoichiometric_subscript(span, value, unit, expected, why):
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair(span, value, unit) is expected, why


def test_e3_is_the_subscript_hook_and_nothing_else(monkeypatch):
    """MUTATION: empty `_SUBSCRIPT` — E3 off. The formula rows redden; the
    ordinary scan, E1 and E2 do not move."""
    import re
    import crossaudit.dcl.numbers as numbers

    monkeypatch.setattr(numbers, "_SUBSCRIPT", re.compile(r"(?!x)x"))
    assert not numbers.contains_pair("LiNi0.8Co0.2O2", "0.8", "")
    assert not numbers.contains_pair("SrCo0.6Fe0.4O3−δ", "0.6", "")
    assert numbers.contains_pair("0.8 alone", "0.8", "")
    assert numbers.contains_pair("775–850 °C", "775", "°C")
    assert numbers.contains_pair("0, 20, 40, 80 wt.%", "0", "wt.%")


def test_e3_reads_decimals_only_glued_to_a_letter_inside_a_formula(monkeypatch):
    """MUTATION, one per guard, each with the row it turns green: read integer
    subscripts (`H2O` with `2` goes green); drop the charset requirement
    (`x=Ni0.5` and `Ni0.5O−₂` go green — `run_v1.5` is held red by the element
    parse too); drop the version guard (`Fe1.2.3` goes green);
    drop the element-symbol parse (`Figure3.2` goes green); drop the any-script
    digit guard after the decimal (`Ni0.5２O`, `Ni0.5₂O` go green); drop the
    letter guard before it (`Ni２0.5O`, `x²0.5` go green — the second review's
    finding, when the first build's guard had been removed as having no row).
    The rows above hold them red in the shipped code."""
    import re
    import crossaudit.dcl.numbers as numbers

    assert not numbers.contains_pair("H2O", "2", "")
    monkeypatch.setattr(numbers, "_SUBSCRIPT",
                        re.compile(r"(?<=[^\W\d_])([0-9]+(?:\.[0-9]+)?)(?![0-9.])"))
    assert numbers.contains_pair("H2O", "2", "")
    monkeypatch.undo()

    assert not numbers.contains_pair("x=Ni0.5", "0.5", "")
    assert not numbers.contains_pair("Ni0.5O−₂", "0.5", "")
    monkeypatch.setattr(numbers, "_formula_charset", lambda token: True)
    assert numbers.contains_pair("x=Ni0.5", "0.5", "")     # its letters parse; only the `=` held it
    assert numbers.contains_pair("Ni0.5O−₂", "0.5", "")    # the marker before a numeral (the third review)
    monkeypatch.undo()

    assert not numbers.contains_pair("Fe1.2.3", "1.2", "")
    monkeypatch.setattr(numbers, "_continued_by_version", lambda span, i: False)
    assert numbers.contains_pair("Fe1.2.3", "1.2", "")     # a period and a digit: a version
    monkeypatch.undo()

    assert not numbers.contains_pair("Figure3.2", "3.2", "")
    monkeypatch.setattr(numbers, "_element_symbols", lambda run: True)
    assert numbers.contains_pair("Figure3.2", "3.2", "")
    monkeypatch.undo()

    assert not numbers.contains_pair("Ni0.5２O", "0.5", "")
    monkeypatch.setattr(numbers, "_continued_by_digit", lambda span, i: False)
    assert numbers.contains_pair("Ni0.5２O", "0.5", "")   # the guard alone holds these
    assert numbers.contains_pair("Ni0.5₂O", "0.5", "")
    monkeypatch.undo()

    assert not numbers.contains_pair("Ni２0.5O", "0.5", "")
    assert not numbers.contains_pair("x²0.5", "0.5", "")
    monkeypatch.setattr(numbers, "_glued_to_letter", lambda span, i: True)
    assert numbers.contains_pair("Ni２0.5O", "0.5", "")   # the second review's row
    assert numbers.contains_pair("x²0.5", "0.5", "")


def test_e3_covers_the_whole_formula_in_the_quote_interval():
    """The first review: with the interval on the digits alone, a quotation of
    `0.8` passed, and nothing tied the unit-free match to its material."""
    from crossaudit.dcl.numbers import pair_occurrences

    spans = list(pair_occurrences("target LiNi0.8Co0.2O2 powder", "0.8", ""))
    assert spans == [(7, 21)], spans          # `LiNi0.8Co0.2O2`, the whole token
    assert list(pair_occurrences("target LiNi0.8Co0.2O2 powder", "0.8", "M")) == []
    # After a middle dot the ordinary scan yields the digits and E3 yields nothing:
    # the second review found the first build yielding the whole token there.
    assert list(pair_occurrences("CuSO4·0.5H2O", "0.5", "")) == [(6, 9)]
    # A zero-width joiner is not a word character, so the ordinary scan reads a bare
    # number after it — the frozen base's behaviour, not this slice's; E3 refuses the
    # token (the joiner is outside the charset) and yields nothing.
    assert list(pair_occurrences("Ni\u200d0.5O", "0.5", "")) == [(3, 6)]
    # A decimal ending the token before sentence punctuation: the token, not the period.
    assert list(pair_occurrences("the Ni0.5.", "0.5", "")) == [(4, 9)]


def test_e3_through_the_fenced_interface_needs_the_formula_quoted():
    """Under content addressing a quotation of the digits alone is a wrong span
    (CA-NUM-002); the formula quoted passes; a subscript in the wrong formula
    is contained — the disclosed weakness — and the quotation is what names it."""
    recipe = RECIPE.replace("- barium carbonate", "- LiNi0.8Co0.2O2 target")
    prose = "The target LiNi0.8Co0.2O2 is 0.8 nickel."
    files = {RECIPE_PATH: recipe.encode(),
             DRAFT_PATH: draft([row("0.8", "", src=cite("LiNi0.8Co0.2O2"))], prose)}
    assert findings(files) == []
    files[DRAFT_PATH] = draft([row("0.8", "", src=cite("0.8"))], prose)
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"]
    files[DRAFT_PATH] = draft([row("0.8", "", src=cite("- LiNi0.8Co0.2O2 target"))], prose)
    assert findings(files) == []


#: Each limit the contract and the shipped skill state, beside the behaviour that makes it
#: true. The third review found the words present and the behaviour unchecked — a phrase
#: test binds presence, not truth — so here a phrase is asserted only with its row; the
#: fourth found five rows skipping the skill, so every row now names a skill phrase too.
DISCLOSED_LIMITS = [
    ("the fragment table is the only guard", "is read as a word after the unit",
     "5 kg m mmHg", "kg m", True),
    ("more tokens than it scans", "more than six symbols in a row",
     "5 kg m s⁻² A⁻¹ K⁻¹ mol⁻¹ sr⁻¹", "kg m s⁻² A⁻¹ K⁻¹ mol⁻¹", False),
    ("more tokens than it scans", "more than six symbols in a row",
     "5 kg m s⁻² A⁻¹ K⁻¹ mol⁻¹ sr⁻¹", "kg m s⁻² A⁻¹ K⁻¹ mol⁻¹ sr⁻¹", False),
    ("an operator with nothing after it", "a `/` or `·` with nothing readable after it",
     "5 g / 100 mL", "g", False),
    ("an operator with nothing after it", "a `/` or `·` with nothing readable after it",
     "5 g / 100 mL", "g /", False),
    ("('GBq' likewise)", "(`mmHg`, `GBq`)", "5 kg m GBq", "kg m", True),
    ("('oz/yd', 'oz·yd', 'oz⋅yd'; 'wet/dry' reads)", "such as `oz/yd`, `oz·yd` or `oz⋅yd`", "5 kg m oz/yd", "kg m", False),
    ("('oz/yd', 'oz·yd', 'oz⋅yd'; 'wet/dry' reads)", "such as `oz/yd`, `oz·yd` or `oz⋅yd`", "5 kg m oz·yd", "kg m", False),
    ("('oz/yd', 'oz·yd', 'oz⋅yd'; 'wet/dry' reads)", "such as `oz/yd`, `oz·yd` or `oz⋅yd`", "5 kg m oz⋅yd", "kg m", False),
    ("('oz/yd', 'oz·yd', 'oz⋅yd'; 'wet/dry' reads)", "such as `oz/yd`, `oz·yd` or `oz⋅yd`", "5 wt % wet/dry", "wt %", True),
    ("('run-2', 'm2')", "such as `run-2` or `m2`", "5 wt % run-2", "wt %", False),
    ("('run-2', 'm2')", "such as `run-2` or `m2`", "5 kg m m2", "kg m", False),
    ("('kg-m', 'lot_id', and 'lot_id/2' with a digit added)", "such as `kg-m` or `lot_id` (with or without a digit, as in `lot_id/2`)",
     "5 wt % kg-m", "wt %", False),
    ("('kg-m', 'lot_id', and 'lot_id/2' with a digit added)", "such as `kg-m` or `lot_id` (with or without a digit, as in `lot_id/2`)",
     "5 wt % lot_id", "wt %", False),
    ("('kg-m', 'lot_id', and 'lot_id/2' with a digit added)", "such as `kg-m` or `lot_id` (with or without a digit, as in `lot_id/2`)",
     "5 kg m lot_id/2", "kg m", False),
    ("('g/xyz', 'dry·g', 'kg-m/s', and '2/g' with a numeral in front)", "such as `g/xyz`, `dry·g`, `kg-m/s` or `2/g`",
     "5 wt % g/xyz", "wt %", False),
    ("('g/xyz', 'dry·g', 'kg-m/s', and '2/g' with a numeral in front)", "such as `g/xyz`, `dry·g`, `kg-m/s` or `2/g`",
     "5 wt % dry·g", "wt %", False),
    ("('g/xyz', 'dry·g', 'kg-m/s', and '2/g' with a numeral in front)", "such as `g/xyz`, `dry·g`, `kg-m/s` or `2/g`",
     "5 wt % kg-m/s", "wt %", False),
    ("('g/xyz', 'dry·g', 'kg-m/s', and '2/g' with a numeral in front)", "such as `g/xyz`, `dry·g`, `kg-m/s` or `2/g`",
     "5 kg m 2/g", "kg m", False),
    ("('g/xyz', 'dry·g', 'kg-m/s', and '2/g' with a numeral in front)", "such as `g/xyz`, `dry·g`, `kg-m/s` or `2/g`",
     "5 kg m 2/kg", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 wt % kg／m", "wt %", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m kg／m/dry", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m kg－m/batch", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m lot＿id/batch", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m oz／yd-batch", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m dry／wet-batch", "kg m", False),
    ("a token with a full-width joiner anywhere in it ('kg／m', 'kg／m/dry')", "a full-width joiner in it such as `kg／m` or `kg／m/dry`",
     "5 kg m 2／g", "kg m", False),
    ("('a.u.' is arbitrary units)", "a dotted abbreviation such as `a.u.`", "5 kg m a.u. signal", "kg m", False),
    ("other than e.g., i.e., a.m., p.m., n.b., c.f.", "(other than e.g., i.e., a.m., p.m., n.b., c.f.)",
     "5 kg m n.b. note", "kg m", True),
    ("a short lower-case word this check does not name", "a short lower-case word the checker does not know",
     "5 wt % qz", "wt %", False),
    ("hyphenated, contracted, abbreviated, in another script", "Hyphenated words, contractions, abbreviations such as `e.g.`",
     "5 wt % high-purity powder", "wt %", True),
    ("hyphenated, contracted, abbreviated, in another script", "Hyphenated words, contractions, abbreviations such as `e.g.`",
     "5 wt % batch-1/2", "wt %", True),
    ("hyphenated, contracted, abbreviated, in another script", "Hyphenated words, contractions, abbreviations such as `e.g.`",
     "5 wt % we're ready", "wt %", True),
    ("hyphenated, contracted, abbreviated, in another script", "Hyphenated words, contractions, abbreviations such as `e.g.`",
     "5 wt % e.g. this", "wt %", True),
    ("hyphenated, contracted, abbreviated, in another script", "words in another script",
     "5 wt % 样品", "wt %", True),
    ("carrying trailing punctuation", "words with trailing punctuation", "5 wt % sample，", "wt %", True),
    ("carrying trailing punctuation", "words with trailing punctuation", "5 wt % 样品。", "wt %", True),
    ("('sample%', 'dry%', 'wet‰') reads", "such as `sample%`, `dry%` or `wet‰`", "5 wt % sample%", "wt %", True),
    ("('sample%', 'dry%', 'wet‰') reads", "such as `sample%`, `dry%` or `wet‰`", "5 wt % dry% powder", "wt %", True),
    ("('sample%', 'dry%', 'wet‰') reads", "such as `sample%`, `dry%` or `wet‰`", "5 wt % wet‰", "wt %", True),
    ("on an unnamed short stem ('abc%') or an element symbol ('Ni‰') it is a unit", "(not an element symbol such as `Ni‰`)",
     "5 wt % abc%", "wt %", False),
    ("on an unnamed short stem ('abc%') or an element symbol ('Ni‰') it is a unit", "(not an element symbol such as `Ni‰`)",
     "5 kg m Ni‰", "kg m", False),
    ("('wt.%' is one unit)", "`wt.%` is one unit", "5 wt.% sub-micron", "wt.%", True),
    ("written as 's⁻¹', 's−1' or 's-1' is one unit", "count as the same unit", "5 s−1 (13 rpm)", "s⁻¹", True),
    ("the fold does not reach the rule that refuses a number continued by a power of ten",
     "copy the source's own rendering", "5 × 10⁵ mbar", "mbar", False),
    ("a dash and a second number follow it directly", "either endpoint may be annotated",
     "5–10 °C", "°C", True),
    ("a SPACED ASCII hyphen ('10 - 5 °C') is not read as a range", "spaced ASCII hyphen",
     "5 - 10 °C", "°C", False),
    ("no value between the endpoints is stated", "never a value inside the range",
     "1–10 °C", "°C", False),
    ("never reaches a number that carries its own unit", "never the unit of a different quantity",
     "5 g–10 mL", "mL", False),
    ("a comma, 'and' or 'or' and the next number follow it directly", "every member may be annotated",
     "5, 10 and 20 °C", "°C", True),
    ("a member with its own unit keeps it", "a member that carries its own unit keeps it",
     "5 g, 10 mL water", "mL", False),
    ("a colon or a semicolon is not a separator", "a colon or a semicolon does not make a list",
     "5; 10 °C", "°C", False),
    ("a number that a label word precedes", "a labelled number",
     "Step 5, 10 mL", "mL", False),
    ("a comma needs a space after it to separate", "a comma needs a space after it to separate",
     "5,12 °C", "°C", False),          # the fixture's value is 5: a glued comma distributes nothing to it
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "a word outside it does not protect a number",
     "Heat 5, 10 mL", "mL", True),
    # The third review: every phrase the skill carries is pinned to a row, so a template
    # patch that silently fails (round 2) cannot pass this test again.
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "`Step 5`", "Step 5, 10 mL", "mL", False),
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "`Figs. 5`", "Figs. 5, 10 °C", "°C", False),
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "`Step: 5`", "Step: 5, 10 mL", "mL", False),
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "fixed named list", "Matrices 5, 10 °C", "°C", False),
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "with their plurals", "Indices 5, 10 °C", "°C", False),
    ("('Step 5, 10 mL', 'Figs. 5', 'Step: 5')", "compounds and the like", "Compounds 5, 10 °C", "°C", False),
    ("a comma needs a space after it to separate", "is not a list", "5,12 °C", "°C", False),
    # Six-element rows carry their own value (the fixture's default is 5): the decimal
    # comma is only testable on the value that contains it.
    ("neither a list nor a number this check reads", "nor a number this checker reads",
     "12,5 °C", "12,5", "°C", False),
    ("neither a list nor a number this check reads", "write `uncited` for a decimal-comma value",
     "12,5 °C", "12", "°C", False),
    ("every member states that unit", "every member may be annotated",
     "0, 20, 40, 80 wt.% powders", "40", "wt.%", True),
    # The fourth review: the contract's own clauses, each pinned to a row too.
    ("only the last member carries a unit expression", "every member may be annotated",
     "5, 10 kg, or 20 μm", "μm", False),
    ("provided every member between it and the unit-bearing one is a bare number", "keeps it",
     "5 kg, 10 kg, or 20 kg", "μm", False),
    ("provided every member between it and the unit-bearing one is a bare number", "keeps it",
     "5 kg, 10 kg, or 20 kg", "kg", True),
    ("refused notation on a member stops the list", "every member may be annotated",
     "5, 10 × 10⁵ Pa", "×", False),      # the row the stop's deletion turns green
    # E3 (study 13): a decimal stoichiometric subscript, the one unit-free extension.
    ("decimal stoichiometric subscript", "decimal stoichiometric subscript",
     "LiNi0.8Co0.2O2", "0.8", "", True),
    ("with the empty unit", "with the empty unit", "LiNi0.8Co0.2O2", "0.8", "M", False),
    ("an integer subscript glued to a letter", "integer subscript glued to a letter",
     "H2O", "2", "", False),
    ("'3' in 'Cr2O3'", "`3` in `Cr2O3`", "Cr2O3", "3", "", False),
    # The first review: `(OH)2` makes `2` citable through the ordinary scan, so the
    # words say so instead of "never read".
    ("after a bracket or a middle dot", "after a bracket or a middle dot", "(OH)2", "2", "", True),
    ("after a bracket or a middle dot", "after a bracket or a middle dot",
     "Co(NO3)2·6H2O", "6", "", True),
    ("the '−δ' / '±δ' marker", "`−δ` marker", "SrCo0.6Fe0.4O3−δ", "0.6", "", True),
    ("parse as element symbols", "element symbols", "Figure3.2", "3.2", "", False),
    ("not Roman numerals", "not Roman numerals", "Ni0.5OⅧ", "0.5", "", False),
    ("'pH7.4'", "`pH7.4`", "pH7.4", "7.4", "", False),
    ("'x=Ni0.5'", "`x=Ni0.5`", "x=Ni0.5", "0.5", "", False),
    ("'run_v1.5'", "`run_v1.5`", "run_v1.5", "1.5", "", False),
    ("the parse is syntactic", "spell symbols", "BaNaNa1.2", "1.2", "", True),
    ("weakest match this check makes", "weakest match the checker makes",
     "LiCo0.2O2", "0.2", "", True),
    # The interval half of this phrase is bound by the fenced-interface test above.
    ("the quotation must contain the whole formula", "quote the whole formula",
     "LiNi0.8Co0.2O2", "0.8", "", True),
    # M10 (study 14): measured and not shipped; the limit is stated and its behaviour pinned.
    ("written with an EN DASH ('L·h–1') is NOT read", "written with an en dash", "2 L·h–1", "2", "L·h-1", False),
    ("written with an EN DASH ('L·h–1') is NOT read", "however you transcribe it", "2 L·h–1", "2", "L·h–1", False),
    ("measured and not shipped", "write `uncited` for that number", "5 K·min–1", "5", "K·min-1", False),
]


def _limit_rows():
    """Five-element rows annotate the value 5; six-element rows carry their own value."""
    for row in DISCLOSED_LIMITS:
        yield row if len(row) == 6 else (row[0], row[1], row[2], "5", row[3], row[4])


@pytest.mark.parametrize("contract_phrase,skill_phrase,span,value,unit,expected",
                         list(_limit_rows()))
def test_each_disclosed_limit_is_in_the_words_and_in_the_behaviour(
        contract_phrase, skill_phrase, span, value, unit, expected):
    """MUTATION: delete a limit sentence from the contract, or change the
    behaviour it describes — either alone reddens the row."""
    from crossaudit.dcl.framework import contracts
    from crossaudit.dcl.numbers import contains_pair
    from crossaudit.scaffold import annotation_skill_tree

    contract = " ".join(contracts(["number_source"])["number_source"].split())
    body = " ".join(annotation_skill_tree(["number_source"])[NUMBERS_SKILL].split())
    assert contract_phrase in contract, contract_phrase
    assert skill_phrase in body, skill_phrase     # whitespace-normalised: wrapping is not a claim
    assert contains_pair(span, value, unit) is expected, (span, value, unit)


def test_the_cap_is_consulted_only_when_the_next_token_would_continue():
    """MUTATION: test the cap before asking whether the next token continues —
    the second build's order, which made a complete six-token expression
    unreadable whenever ANYTHING followed it on the line: `… mol⁻¹ sample`,
    `… mol⁻¹ 10 s` and `… mol⁻¹ (dry)` all blocked their whole unit while
    `… mol⁻¹,` read. The cap is an overflow guard: it fires when a seventh
    fragment would join, and then nothing reads, as the sweep above asserts."""
    from crossaudit.dcl.numbers import contains_pair

    six = "kg m s⁻² A⁻¹ K⁻¹ mol⁻¹"
    for tail in ("", ",", " sample", " 10 s", " (dry)", " of water", " Ni", " —",
                 " batch-1"):
        assert contains_pair(f"5 {six}{tail}", "5", six), tail
        assert not contains_pair(f"5 {six}{tail}", "5", "kg m s⁻² A⁻¹ K⁻¹"), tail
    for tail in (" sr⁻¹", " · s", " / mL", " qz", " xyz⁻¹"):
        assert not contains_pair(f"5 {six}{tail}", "5", six), tail


#: The entries of the fragment table that nothing but the table guards: an
#: alphabetic fragment of four or more letters, or a capitalised one, reads as
#: PROSE when it is not named, so a join before it is offered. Pinned as a
#: literal so the count in study 9's RESULTS §3 is a tested number, and an
#: addition to the table that lands in this class is a visible change.
TABLE_ONLY_GUARDED = frozenset("""
    Bq GHz GPa Gy Hz MHz MPa MeV Sv Torr Wb mbar mmol nmol sccm torr µmol μmol
""".split())


def test_which_omissions_from_the_table_block_and_which_read_as_prose(monkeypatch):
    """GENERATED over the whole table, because the second review showed the
    example-driven claim was false: "after a join an omission is a block" held
    for `s` and `sr` and failed for `mbar`, `Torr`, `sccm` and `µmol`.

    Every entry is removed in turn and `5 kg m <entry>` is asked for `kg m`
    (an element or bare capital in its `⁻¹` form, since the bare form is a
    substance by design). One to three lower-case letters, or any marked
    entry: BLOCK. Four or more letters, or capitalised: the join is offered,
    and the table is the only guard — those are the entries listed above,
    exactly. `µm` stays named when removed because `normalise_unit` folds
    `μm` onto it; it is asserted for what it does, not skipped. And with its
    fragment unnamed the WHOLE expression never reads, whichever class."""
    import crossaudit.dcl.numbers as numbers

    table = set(numbers._UNIT_FRAGMENTS)
    offered = set()
    for entry in sorted(table):
        monkeypatch.setattr(numbers, "_UNIT_FRAGMENTS", frozenset(table - {entry}))
        bare = entry in numbers._ELEMENTS or (len(entry) == 1 and entry.isupper())
        form = entry + "⁻¹" if bare else entry
        if numbers.contains_pair(f"5 kg m {form}", "5", "kg m"):
            offered.add(entry)
        if not numbers._fragment(entry):
            assert not numbers.contains_pair(f"5 kg m {form}", "5", f"kg m {form}"), entry
    assert offered == TABLE_ONLY_GUARDED
    assert all(e.isalpha() and (len(e) >= 4 or e[0].isupper()) for e in offered)
    assert not any(e.isalpha() and (len(e) >= 4 or e[0].isupper()) for e in table - offered
                   if not numbers._ELEMENTS.__contains__(e) and not (len(e) == 1 and e.isupper()))


def test_a_continuation_never_crosses_a_line():
    """MUTATION: use `\\s` instead of `_INLINE` for the gap in `_spaced_unit`.

    A `results.json` locator still names a line RANGE, so the text this matcher
    scans can hold several lines, and the token at the head of the next line is
    that line's prose. Reading it as this number's unit would turn a correct
    annotation into a non-overridable block for a line break — the same shape as
    the footnote `_UNPARSED` refuses to read as an exponent (slice 2)."""
    from crossaudit.dcl.numbers import contains_pair

    assert contains_pair("held at 5 g\nmin⁻¹ was the ramp", "5", "g")
    assert not contains_pair("held at 5 g min⁻¹", "5", "g")


def test_the_pair_interval_covers_the_characters_the_source_wrote():
    """MUTATION: yield `len(candidate)` instead of the candidate's extent.

    A spaced expression joined with single spaces is SHORTER than the text it
    covers when the source wrote two spaces, and the interval is what the quote
    contract tests containment against (slice 2). An interval that stops inside
    the unit would let a quotation ending mid-unit satisfy the row — the
    cropping defect slice 2's review found, met one more time."""
    from crossaudit.dcl.numbers import pair_occurrences

    line = "ramp 5 °C  min⁻¹ then"
    (start, end), = pair_occurrences(line, "5", "°C min⁻¹")
    assert line[start:end] == "5 °C  min⁻¹"

    files = {RECIPE_PATH: (line + "\n").encode(),
             DRAFT_PATH: draft([row(value="5", unit="°C min⁻¹",
                                    src=cite("5 °C  min"))])}
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"], "a quote that stops inside the unit"


LEGACY_FIXTURES = Path(__file__).parent / "fixtures" / "legacy_provenance_skills"


@pytest.mark.parametrize("rendering", ["numbers.md", "sources.md", "both.md"])
def test_every_pre_split_rendering_is_recognised_and_removed(tmp_path, rendering):
    """MUTATION: prune on a substring again, or drop one rendering's digest.

    The round-3 composer could emit three files — numbers only, sources only,
    both — and the first migration matched two SUBSTRINGS instead. That deleted
    a hand-written policy whose only crime was quoting the fence name in an
    example, and it missed the source-only rendering entirely, which carries no
    numeric marker at all. Ownership of a generated file is proved by its bytes.

    The fixtures here are the actual round-3 output, and asserting their digests
    against the pinned set is what keeps the set honest: if somebody edits the
    templates and recomputes the constants from the NEW ones, this reddens."""
    from crossaudit.scaffold import (LEGACY_ANNOTATION_DIGESTS,
                                     LEGACY_ANNOTATION_SKILL,
                                     prune_legacy_annotation_skill)

    body = (LEGACY_FIXTURES / rendering).read_bytes()
    assert hashlib.sha256(body).hexdigest() in LEGACY_ANNOTATION_DIGESTS

    legacy = tmp_path / LEGACY_ANNOTATION_SKILL
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(body)
    assert prune_legacy_annotation_skill(tmp_path) == [LEGACY_ANNOTATION_SKILL]
    assert not legacy.exists()


@pytest.mark.parametrize("kept", [
    # The exact file the first migration deleted.
    "Hand written custom policy\nMy example uses ```crossaudit-numbers; keep my"
    " custom advice.\n",
    "---\nrequires_check: number_source\n---\n```crossaudit-numbers\n```\n",
    "# my own house style\n",
    "```crossaudit-sources\n[]\n```\n",
])
def test_a_file_this_scaffold_did_not_write_is_never_removed(tmp_path, kept):
    """MUTATION: match on "mentions the fence name" instead of on the bytes.

    A person may write anything at `skills/provenance.md`, including a document
    that quotes the fence it is teaching. Deleting that is data loss caused by a
    migration for a file that shipped to nobody."""
    from crossaudit.scaffold import (LEGACY_ANNOTATION_SKILL,
                                     prune_legacy_annotation_skill)

    legacy = tmp_path / LEGACY_ANNOTATION_SKILL
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(kept)
    assert prune_legacy_annotation_skill(tmp_path) == []
    assert legacy.read_text() == kept


def test_nothing_to_prune_is_not_an_error(tmp_path):
    from crossaudit.scaffold import prune_legacy_annotation_skill

    assert prune_legacy_annotation_skill(tmp_path) == []
    assert prune_legacy_annotation_skill(None) == []


def _science_project(tmp_path, monkeypatch, name, project_type="science"):
    """A real project on disk, made by the console creation path."""
    from crossaudit.console import projects

    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    return Path(projects.create_project(
        tmp_path,
        {"name": name, "description": "Numbers need units and sources.",
         "max_rounds": 3, "auditor_vendor": "openai", "auditor_model": "gpt-5.6-sol",
         "generator_vendor": "anthropic", "generator_model": "claude-sonnet-4-6",
         "github": False, "project_type": project_type},
        lambda *_: None)["root"])


def _git(root, *args, **kw):
    return subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True, check=kw.get("check", True)).stdout


def _run_creation(path_name, tmp_path, monkeypatch, name):
    """Drive ONE of the two real creation entry points and return its root.

    `wizard.run` is the `crossaudit init` path and `projects.create_project` is
    the console path. Both are entered here, not stood in for: an earlier
    version of these tests mapped both labels onto the shared helper and created
    every project through the console, so deleting the CLI caller's invocation
    of that helper would not have reddened anything.
    """
    from crossaudit.cli import wizard
    from crossaudit.console import projects

    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    if path_name == "cli":
        target = tmp_path / name
        wizard.run(target, mode="local", profile="science")
        return target
    return Path(projects.create_project(
        tmp_path,
        {"name": name, "description": "Numbers need units and sources.",
         "max_rounds": 3, "auditor_vendor": "openai", "auditor_model": "gpt-5.6-sol",
         "generator_vendor": "anthropic", "generator_model": "claude-sonnet-4-6",
         "github": False, "project_type": "science"},
        lambda *_: None)["root"])


def _inject_legacy_before_the_helper(monkeypatch, rendering, commit: bool):
    """Put a pre-split `skills/provenance.md` in the project at the moment the
    creation path reaches `annotation_skills_owned`, and record that it did.

    This is the seam BOTH production paths go through, and patching it on the
    `wizard` module intercepts each of them — `projects.py` looks the name up on
    the module and `wizard.py` looks it up as a module global. If either caller
    stops invoking it, the spy never runs, no legacy file is ever created, and
    the assertions below fail: which is the coverage the previous version of
    this test claimed and did not have.
    """
    from crossaudit.cli import wizard
    from crossaudit.scaffold import LEGACY_ANNOTATION_SKILL

    real = wizard.annotation_skills_owned
    seen: list[Path] = []

    def spy(target, checks):
        root = Path(target)
        (root / "skills").mkdir(parents=True, exist_ok=True)
        (root / LEGACY_ANNOTATION_SKILL).write_bytes(
            (LEGACY_FIXTURES / rendering).read_bytes())
        if commit:
            _git(root, "add", "--", LEGACY_ANNOTATION_SKILL)
            _git(root, "-c", "user.name=t", "-c", "user.email=t@t.invalid",
                 "commit", "-qm", "legacy skill from a previous version")
        seen.append(root)
        return real(target, checks)

    monkeypatch.setattr(wizard, "annotation_skills_owned", spy)
    return seen


@pytest.mark.parametrize("path_name", ["cli", "console"])
@pytest.mark.parametrize("rendering", ["numbers.md", "sources.md", "both.md"])
def test_each_creation_path_removes_a_tracked_legacy_skill_and_commits_it(
        tmp_path, monkeypatch, path_name, rendering):
    """MUTATION: delete either path's call to `annotation_skills_owned`, or drop
    the removal from what it returns.

    Both callers once discarded the removal, so the file was deleted from the
    working tree and left alive in the commit — a migration that runs and does
    not stick. The legacy file is injected INSIDE each real creation path, at
    the moment it reaches the shared helper, and the assertions run on the
    project that path produced."""
    from crossaudit.scaffold import LEGACY_ANNOTATION_SKILL as legacy_path

    seen = _inject_legacy_before_the_helper(monkeypatch, rendering, commit=True)
    root = _run_creation(path_name, tmp_path, monkeypatch,
                         f"lab{path_name}{rendering[:3]}")

    assert seen == [root], "the creation path never reached the shared helper"
    assert not (root / legacy_path).exists()
    # Committed, not merely deleted: gone from the index, tree clean, and the
    # deletion visible in the setup commit this path wrote.
    assert _git(root, "ls-files", "--", legacy_path).strip() == ""
    assert _git(root, "status", "--porcelain").strip() == ""
    # `--no-renames`, because git's similarity heuristic reports the removal as
    # a rename to `provenance-numbers.md` for two of the three renderings. The
    # end state is the claim — the path left the tree in this commit — and it
    # must not depend on how similar the replacement happens to be.
    assert f"D\t{legacy_path}" in _git(
        root, "log", "--no-renames", "--name-status", "--format=", "-3")
    # And what was written in its place is the SHIPPED skill, byte for byte,
    # tracked in the same setup commit: since D164 ruling 1 a science scaffold
    # enables `number_source`, so the migration is a removal AND a swap, and
    # both halves have to stick — a legacy file left alive would shadow the
    # rendered one in the generator's prompt.
    from crossaudit.scaffold import SCIENCE_CHECKS, annotation_skill_tree
    assert (root / NUMBERS_SKILL).exists()
    assert _git(root, "ls-files", "--", NUMBERS_SKILL).strip() == NUMBERS_SKILL
    assert (root / NUMBERS_SKILL).read_text(encoding="utf-8") == \
        annotation_skill_tree(SCIENCE_CHECKS)[NUMBERS_SKILL]


@pytest.mark.parametrize("path_name", ["cli", "console"])
def test_each_creation_path_removes_an_untracked_legacy_skill_without_staging_it(
        tmp_path, monkeypatch, path_name):
    """MUTATION: stage the removal without checking that git tracks the path.

    `git add -- <path>` on a pathspec that neither exists nor is tracked is
    FATAL, so an untracked leftover would turn setup itself into a denial over a
    file nobody was tracking. It is still removed; it is simply not staged, and
    the creation path completes."""
    from crossaudit.scaffold import LEGACY_ANNOTATION_SKILL as legacy_path

    seen = _inject_legacy_before_the_helper(monkeypatch, "both.md", commit=False)
    root = _run_creation(path_name, tmp_path, monkeypatch, f"lab{path_name}untracked")

    assert seen == [root]
    assert not (root / legacy_path).exists()
    assert _git(root, "status", "--porcelain").strip() == ""
    assert _git(root, "ls-files", "--", legacy_path).strip() == ""


@pytest.mark.parametrize("alias", ["symlink", "case", "file"])
def test_setup_writes_no_guidance_through_an_alias(tmp_path, alias):
    """MUTATION: write before validating — `write_tree(...)` above the
    `house_dir` call.

    Pruning validated the guidance directory and writing did not, so on
    `skills -> work/guidance` setup wrote `provenance-numbers.md` and
    `-sources.md` into somebody's WORK and only then refused: the denial
    arriving after the damage it exists to prevent, and on a path where those
    two files are audited as work rather than read as guidance. The whole
    destination tree is snapshotted, not just the legacy file, because the
    defect was files nobody was looking for."""
    from crossaudit.cli import wizard
    from crossaudit.errors import ConfigDenial

    root = tmp_path / f"lab{alias}"
    root.mkdir()
    if alias == "symlink":
        (root / "work" / "guidance").mkdir(parents=True)
        (root / "work" / "guidance" / "note.md").write_text("mine\n")
        (root / "skills").symlink_to(root / "work" / "guidance")
    elif alias == "case":
        (root / "SKILLS").mkdir()
        (root / "SKILLS" / "note.md").write_text("mine\n")
    else:
        (root / "skills").write_text("i am a file\n")

    def snapshot():
        return sorted((str(p.relative_to(root)),
                       p.read_bytes() if p.is_file() and not p.is_symlink() else b"")
                      for p in root.rglob("*"))

    before = snapshot()
    with pytest.raises(ConfigDenial):
        wizard.annotation_skills_owned(root, ["number_source", "source_provenance"])
    assert snapshot() == before, "setup wrote guidance through an alias"


def test_a_project_with_no_legacy_skill_is_untouched(tmp_path, monkeypatch):
    """The negative control: the migration must be silent where it has nothing
    to do, and must not stage a path that was never there."""
    from crossaudit.cli import wizard
    from crossaudit.config import load
    from crossaudit.scaffold import LEGACY_ANNOTATION_SKILL

    root = _science_project(tmp_path, monkeypatch, "labclean")
    owned = wizard.annotation_skills_owned(root, load(root / "crossaudit.yml").checks)
    assert LEGACY_ANNOTATION_SKILL not in owned
    assert _git(root, "status", "--porcelain").strip() == ""


# ------------------ the fifth review: signed notation, and quotes as boundaries
@pytest.mark.parametrize("span,v,u,expected,why", [
    # The review's four rows, plus the structured pair it also reported.
    ("10⁻⁵ g",   "10", "",   ["CA-NUM-002"], "a superscript MINUS exponent"),
    ("10⁺⁵ g",   "10", "",   ["CA-NUM-002"], "a superscript PLUS exponent"),
    ("5×-10³ g", "5",  "",   ["CA-NUM-002"], "an ASCII sign after the operator"),
    ("5^−3 g",   "5",  "",   ["CA-NUM-002"], "a U+2212 sign after the caret"),
    ("10⁻⁵ g",   "10", "⁻⁵", ["CA-NUM-002"], "and naming the exponent as a unit"),
    ("10⁺⁵ g",   "10", "⁺⁵", ["CA-NUM-002"], "in either sign"),
    # The neighbourhood, so this is a rule and not four patches.
    ("5⋅10³ g",  "5", "",  ["CA-NUM-002"], "a dot operator"),
    ("5·10³ g",  "5", "",  ["CA-NUM-002"], "a middle dot operator"),
    ("5*-10³ g", "5", "",  ["CA-NUM-002"], "a signed asterisk product"),
    ("5x±10³ g", "5", "",  ["CA-NUM-002"], "a plus-minus operand"),
    ("10⁵ g",    "10", "", ["CA-NUM-002"], "the unsigned case still blocks"),
    # And nothing that is merely prose or a legitimate unit is caught by it.
    ("run 5 of 12", "5", "",       [], "a word after a number is not notation"),
    ("5 g",         "5", "",       [], "nor is a unit"),
    ("5 m·s^-1",    "5", "m·s^-1", [], "a caret INSIDE a unit is untouched"),
    ("5 cm-1",      "5", "cm-1",   [], "and so is a hyphen exponent"),
    ("5 x 3 grid",  "5", "",       [], "a spaced multiplication sign is prose"),
])
def test_signed_notation_is_unparsed_notation_too(span, v, u, expected, why):
    """MUTATION: drop the sign alternatives from `_UNPARSED`.

    The rule was "a number that continues into notation this layer cannot read
    is not a match for any unit", and it enumerated superscript DIGITS only. So
    `10⁻⁵ g` still satisfied an annotation of `10` with an empty unit, and
    `10 / "⁻⁵"` satisfied it through a `results.json` citation under the
    complete science profile, where base blocks. The sign is part of the
    notation; leaving it out left the same hole one character to the left."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


def test_signed_notation_blocks_through_a_structured_citation_too():
    """The same rule where the review found it: a `results.json` quantity, under
    every check the science profile resolves to."""
    from crossaudit.dcl.profiles import resolve

    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": "run,y\n10⁻⁵ g\n".encode(),
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "y", "value": 10, "unit": "⁻⁵",
                                  "source": "runs.csv@v3#L2"}],
                  "convergence": {"converged": True}}).encode()}
    assert [f.rule for f in
            run_checks(files, science_with_numbers()).findings] == ["CA-NUM-002"]


@pytest.mark.parametrize("mark", list("‘’‚‛“”„‟‹›«»†‡§¶"))
def test_quotes_and_footnote_marks_end_a_unit_token(mark):
    """MUTATION: take the typographic quotes or the note marks back out.

    `5 °C”` and `5 °C’s` blocked on `°C` — a word processor's closing quote and
    an English possessive turning into unit text — and `5 °C†` and `5 °C§`
    blocked wherever a footnote is marked. Inverting the scanner made the
    boundary list the whole contract, so a boundary left out of it is a blocker
    on ordinary prose. Every direction of single and double quote is listed by
    codepoint, because several are indistinguishable from ASCII by eye."""
    files = {RECIPE_PATH: f"5 °C{mark}\n".encode(),
             DRAFT_PATH: draft([row(value="5", unit="°C", src=cite(f"5 °C{mark}"))])}
    assert findings(files) == [], mark


@pytest.mark.parametrize("mark", ["*", ">"])
def test_multiplication_and_comparison_stay_inside_the_token(mark):
    """The deliberate other side, stated in the contract: `*` and `>` are
    notation a unit can contain, so they are NOT boundaries. The cost is that a
    footnote star reads as unit text, and that cost is named rather than traded
    away — making them boundaries would let a shortened unit satisfy a longer
    source, which is the defect this whole line has been closing."""
    files = {RECIPE_PATH: f"5 °C{mark}\n".encode(),
             DRAFT_PATH: draft([row(value="5", unit="°C", src=cite(f"5 °C{mark}"))])}
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"]
    whole = {RECIPE_PATH: f"5 °C{mark}\n".encode(),
             DRAFT_PATH: draft([row(value="5", unit=f"°C{mark}",
                                    src=cite(f"5 °C{mark}"))])}
    assert findings(whole) == []


@pytest.mark.parametrize("value,canonical", [
    ("1e000005", "1e5"), ("1e5", "1e5"), ("1e0000000000005", "1e5"),
    ("1e-000005", "1e-5"), ("1e99999", "1e99999"),
    ("1e100000", None), ("1e0999999", None),
])
def test_the_exponent_cap_is_on_magnitude_not_on_padding(value, canonical):
    """MUTATION: count exponent characters again.

    `1e000005` was CA-NUM-001 and `1e99999` was fine — the padding deciding, not
    the number. A cap that a literal can trip by being written verbosely is not
    a cap on anything."""
    from crossaudit.dcl.quantities import normalise_number

    assert normalise_number(value) == canonical


# --------- the sixth review: an explicit `+` is padding, and `-` is a magnitude
@pytest.mark.parametrize("exponent", range(1, 101))
def test_an_explicit_positive_exponent_is_never_a_negative_one(exponent):
    """MUTATION: write the sign with one tuple —
    `("-", exponent[1:]) if exponent[0] in "+-" else ("", exponent)` — which maps
    BOTH `+` and `-` onto `-`.

    `normalise_number("1e+5")` became `1e-5`: ten orders of magnitude apart
    comparing equal, so a citation of one satisfied the other, and the values
    that genuinely ARE equal stopped matching. Through the fence and through a
    `results.json` citation under the complete science profile, 100 of 100
    exponents were wrong in both directions.

    The sweep is parametrised over the whole range and stays that way. A sign
    bug in the one function every numeric comparison passes through survived a
    3015-test suite because no case compared an explicit `+` exponent against
    its `-` twin: the pair is the test, and one example of it is not."""
    plus, minus = f"1e+{exponent}", f"1e-{exponent}"
    bare, expanded = f"1e{exponent}", "1" + "0" * exponent

    def rule(span, value):
        files = {RECIPE_PATH: (span + "\n").encode(),
                 DRAFT_PATH: draft([row(value=value, unit="g",
                                        src=cite(span))])}
        return [f.rule for f in findings(files)]

    # `1e+N` ≡ `1eN` ≡ the expanded integer, in both directions.
    assert rule(f"{plus} g", bare) == []
    assert rule(f"{bare} g", plus) == []
    if exponent <= 30:                       # keep the expanded literal sane
        assert rule(f"{expanded} g", plus) == []
        assert rule(f"{plus} g", expanded) == []
    # And `1e+N` is never `1e-N`, in either direction.
    assert rule(f"{plus} g", minus) == ["CA-NUM-002"]
    assert rule(f"{minus} g", plus) == ["CA-NUM-002"]
    # A negative exponent still matches itself.
    assert rule(f"{minus} g", minus) == []


@pytest.mark.parametrize("exponent", range(1, 101))
def test_the_exponent_sign_holds_through_a_structured_citation_too(exponent):
    """The same pair where the review also found it: a `results.json` quantity,
    under every check the science profile resolves to.

    The whole 1–100 range, like the fence sweep beside it. Sampling four
    exponents and describing it as a sweep is the kind of claim this slice has
    been correcting all the way through: the fence and the structured interface
    reach `contains_pair` by different routes, and only one of them was actually
    swept."""
    from crossaudit.dcl.profiles import resolve

    def rule(span, value):
        files = {"experiments/e1/metadata.yml":
                     b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
                 "experiments/e1/runs.csv": f"run,y\n{span}\n".encode(),
                 "experiments/e1/results.json": json.dumps(
                     {"quantities": [{"name": "y", "value": value, "unit": "g",
                                      "source": "runs.csv@v3#L2"}],
                      "convergence": {"converged": True}}).encode()}
        return [f.rule for f in run_checks(files, science_with_numbers()).findings]

    assert rule(f"1e+{exponent} g", f"1e{exponent}") == []
    assert rule(f"1e+{exponent} g", f"1e+{exponent}") == []
    assert rule(f"1e+{exponent} g", f"1e-{exponent}") == ["CA-NUM-002"]
    assert rule(f"1e-{exponent} g", f"1e+{exponent}") == ["CA-NUM-002"]


@pytest.mark.parametrize("value,canonical", [
    ("1e+5", "1e5"), ("1e5", "1e5"), ("100000", "1e5"),
    ("1e-5", "1e-5"), ("0.00001", "1e-5"),
    ("1e+000005", "1e5"), ("1e-000005", "1e-5"),
    ("1e+0", "1e0"), ("1e-0", "1e0"), ("-1e+5", "-1e5"), ("1E+5", "1e5"),
])
def test_the_canonical_key_reads_the_exponent_sign_it_was_given(value, canonical):
    """The unit-level twin of the sweep, so a future reader can see the keys
    rather than infer them from a pass/block table."""
    from crossaudit.dcl.quantities import normalise_number

    assert normalise_number(value) == canonical


# ------------- after the rebase: this slice's skills under the tightened loader
def _house(root, files: dict[str, bytes]) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / "skills" / name).write_bytes(body)


def test_the_check_gate_survives_the_house_dir_loader(tmp_path):
    """The two slices meet here: `skills.load` now routes through `house_dir`
    (D156), and this slice's `requires_check` is read by `_parse` and honoured
    by `select(checks=)`. Neither knows about the other, and that is the claim
    under test — front matter parses through the new loader, and the gate still
    decides what reaches the generator.

    MUTATION: drop `requires_check` from `_parse`'s front-matter loop, or the
    `checks=` argument from `select`."""
    from crossaudit import skills as skills_mod
    from crossaudit.scaffold import annotation_skill_tree

    tree = annotation_skill_tree(["number_source", "source_provenance"])
    _house(tmp_path, {Path(p).name: body.encode() for p, body in tree.items()})

    house = skills_mod.load(tmp_path)
    assert sorted(s.name for s in house) == ["provenance-numbers", "provenance-sources"]
    assert {s.name: s.requires_check for s in house} == {
        "provenance-numbers": ("number_source",),
        "provenance-sources": ("source_provenance",)}
    # And both front-matter keys still parse side by side.
    both = skills_mod._parse(
        "---\napplies_to: work/, experiments/\nrequires_check: number_source\n---\nx\n",
        "both", "skills/both.md")
    assert both.applies_to == ("work/", "experiments/")
    assert both.requires_check == ("number_source",)

    def names(checks):
        return sorted(s.name for s in skills_mod.select(house, ["src"], checks=checks))

    assert names(["number_source"]) == ["provenance-numbers"]
    assert names(["source_provenance"]) == ["provenance-sources"]
    assert names(["parseable"]) == []
    assert names(None) == ["provenance-numbers", "provenance-sources"]


@pytest.mark.parametrize("break_it", ["case", "symlink", "file"])
def test_this_slices_skills_are_refused_with_the_rest_when_the_directory_is_wrong(
        tmp_path, break_it):
    """MUTATION: give the provenance skills a loader of their own.

    They are ordinary `skills/*.md` and must be refused exactly as a
    hand-written one is when the guidance directory is a case variant, a
    symlink, or a file — D156's invariant is that guidance and work cannot be
    the same bytes, and a second loading path would reopen it for precisely the
    files this slice ships."""
    from crossaudit import skills as skills_mod
    from crossaudit.errors import ConfigDenial
    from crossaudit.scaffold import annotation_skill_tree

    body = annotation_skill_tree(["number_source"])[NUMBERS_SKILL].encode()
    if break_it == "case":
        (tmp_path / "SKILLS").mkdir()
        (tmp_path / "SKILLS" / "provenance-numbers.md").write_bytes(body)
    elif break_it == "symlink":
        (tmp_path / "work" / "guidance").mkdir(parents=True)
        (tmp_path / "work" / "guidance" / "provenance-numbers.md").write_bytes(body)
        (tmp_path / "skills").symlink_to(tmp_path / "work" / "guidance")
    else:
        (tmp_path / "skills").write_bytes(body)

    with pytest.raises(ConfigDenial):
        skills_mod.load(tmp_path)


@pytest.mark.parametrize("break_it", ["case", "symlink"])
def test_pruning_uses_the_loader_identity_and_never_a_filesystem_alias(
        tmp_path, break_it):
    """MUTATION: `Path(root) / "skills/provenance.md"` again.

    Reproduced on this tree before the fix: with `skills -> work/guidance`, the
    migration deleted `work/guidance/provenance.md` — a file git tracks as WORK
    and `house_dir` refuses to read as guidance. A migration that follows an
    alias the loader denies is deleting somebody's work on the strength of a
    name. It now resolves the directory the way the loader does, so an alias is
    a denial and never a deletion."""
    from crossaudit.errors import ConfigDenial
    from crossaudit.scaffold import prune_legacy_annotation_skill

    legacy = (LEGACY_FIXTURES / "both.md").read_bytes()
    if break_it == "case":
        (tmp_path / "SKILLS").mkdir()
        victim = tmp_path / "SKILLS" / "provenance.md"
    else:
        (tmp_path / "work" / "guidance").mkdir(parents=True)
        victim = tmp_path / "work" / "guidance" / "provenance.md"
        (tmp_path / "skills").symlink_to(tmp_path / "work" / "guidance")
    victim.write_bytes(legacy)

    with pytest.raises(ConfigDenial):
        prune_legacy_annotation_skill(tmp_path)
    assert victim.exists(), "the migration followed an alias and deleted it"

    # The real directory still prunes, and an absent one is still not an error.
    real = tmp_path / "real"
    (real / "skills").mkdir(parents=True)
    (real / "skills" / "provenance.md").write_bytes(legacy)
    assert prune_legacy_annotation_skill(real) == ["skills/provenance.md"]
    assert prune_legacy_annotation_skill(tmp_path / "empty") == []


def test_tracked_paths_asks_git_about_the_git_path(tmp_path):
    """`wizard.tracked_paths` compares what `git ls-files` prints, which is the
    tree path — the same identity `house_dir` enforces and the audited-scope
    filters compare. Asserted rather than assumed, because the whole D156
    finding was two notions of "the skills directory" disagreeing."""
    from crossaudit.cli import wizard

    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "provenance.md").write_text("x\n")
    (tmp_path / "skills" / "other.md").write_text("y\n")
    _git(tmp_path, "add", "--", "skills/provenance.md")
    _git(tmp_path, "commit", "-qm", "one tracked")

    assert wizard.tracked_paths(tmp_path, ["skills/provenance.md"]) == [
        "skills/provenance.md"]
    assert wizard.tracked_paths(tmp_path, ["skills/other.md"]) == []
    assert wizard.tracked_paths(tmp_path, []) == []


# ------------------------- D159: content addressing, and the Arm 3 fixtures
#
# `benchmarks/expertlongbench/study8/test_arm3_verifiers.py` is the instrument
# these are ported from: the §4 mutation fixtures of
# `docs/design/PROVENANCE_ADDRESSING.md`, written against the harness's own
# `verify_b` before Arm 3 ran. Ported rather than rewritten, and where the
# shipped check disagrees with the harness the difference is named in the test
# that carries it: the cap is gone (D159, below), a quotation is line-scoped
# rather than file-scoped (`test_a_quotation_lies_within_one_line`), and a quote
# the file does not hold is CA-NUM-002 rather than the harness's CA-NUM-001,
# because the quote is the SPAN and a wrong span has always been -002.

#: One long line, SYNTHETIC, with the shape both of Arm 3's false blockers had:
#: a sentence whose value and unit are far enough apart that no quotation of
#: eighty characters contains them both. The archived quotations themselves are
#: corpus text and are not in this repository; see the test below.
LONG_LINE = ("Calcination was carried out in a muffle furnace at 950 °C for 1 hour "
             "under flowing synthetic air at 100 mL/min, then cooled slowly.")
LONG_RECIPE = f"# Long\n\n{LONG_LINE}\n\nnothing else here.\n"


#: Arm 3's record of its own two false blockers, and the whole of what the
#: repository keeps of them: `quote_len` and a `quote_sha256`, never the text
#: (EXPERIMENT_RECORD §3 — corpus bytes live in the archive, not in a checkout).
#: The lengths below are read back from it where the file is present, so the
#: number this test parametrises on is the archived fact and not a memory of it.
ARM3_ROWS = (Path(__file__).parent.parent / "benchmarks" / "expertlongbench"
             / "study8" / "rows.jsonl")


@pytest.mark.parametrize("length", [97, 104])
def test_a_quote_longer_than_eighty_characters_is_not_a_blocker(length):
    """MUTATION (D159 ruling 1): reinstate the design's 80-character cap —
    `if not 1 <= len(quote) <= 80: return CA-NUM-001` at the head of
    `_verify_quote`. Both rows here redden.

    **The fixture is a synthetic line of the archived LENGTH, not the archived
    quotation.** Arm 3's only two false blockers were 2 of 167 rows, from
    `T03MaterialSEG-10.1002/aic.18378` and `…/smll.201800441`: quotations of 97
    and 104 characters that the named file contained exactly once and that did
    contain the transcribed pair, refused by the length rule alone
    (`RESULTS-ARM3.md` §1, §8). Their text is corpus and stays in the archive —
    `study8/rows.jsonl` keeps `quote_len` and `quote_sha256` and no bytes — so
    what a committed test can reproduce is the property that mattered, a correct
    quotation longer than the cap, at exactly the lengths the record carries.
    The lengths are read back from that record below rather than remembered.

    The cap was there to stop a "quote" that is the whole file — a file-scoped
    citation in disguise, which contains the claimed pair by coincidence 27.7%
    of the time. That job now belongs to the one-line rule, which does it
    without refusing a long line: see
    `test_a_quotation_lies_within_one_line`."""
    if ARM3_ROWS.exists():
        archived = sorted(int(r["quote_len"]) for r in
                          (json.loads(line) for line in
                           ARM3_ROWS.read_text(encoding="utf-8").splitlines() if line.strip())
                          if r.get("class") == "verifier wrong")
        assert archived == [97, 104], archived
        assert length in archived

    quote = LONG_LINE[:length]
    assert len(quote) == length and "950 °C" in quote
    files = {RECIPE_PATH: LONG_RECIPE.encode(),
             DRAFT_PATH: draft([row(src=cite(quote))])}
    assert findings(files) == []


def test_a_quotation_lies_within_one_line():
    """MUTATION: fold the whole file into one string and search that — which is
    what the Arm 3 harness did, because there the 80-character cap was still
    keeping quotations short. With the cap gone that mutation makes the whole
    file a legal quotation, and a file-scoped citation contains the claimed pair
    by coincidence 27.7% of the time (596/2150). The one-line rule is what
    replaces the cap, so this is the guard the cap's removal is paid for with.

    The observation says which failure it is, because the writer's remedy
    differs: a quotation that runs across a line break is quoted too widely, and
    a quotation the file does not have at all is quoted wrongly."""
    across = findings(increment(row(src=cite(f"{L11} {L12}"))))
    assert [(f.severity, f.rule) for f in across] == [(BLOCKER, "CA-NUM-002")]
    assert "across a line break" in across[0].observation
    assert "a quotation is a run of one line" in across[0].observation

    whole_file = findings(increment(row(src=cite(RECIPE))))
    assert [(f.severity, f.rule) for f in whole_file] == [(BLOCKER, "CA-NUM-002")]
    assert "across a line break" in whole_file[0].observation
    # And the finding stays a line a person reads: the contract caps no quote,
    # so the REPORT bounds what it echoes back.
    assert "…" in whole_file[0].observation and len(whole_file[0].observation) < 240


def test_a_quotation_the_file_does_not_contain_is_a_blocker():
    """MUTATION (§4): alter one character inside the quote and let it pass —
    a prefix match, a case fold, or a fuzzy compare. Each row here goes green,
    and a quotation that is not in the file stops being evidence of anything.

    B's whole premise is that the generator COPIES rather than retypes, which
    Arm 3 measured: 0 paraphrases in 192 rows. The premise is only worth
    anything if the check can tell the difference."""
    for quote, why in [
            ("3. Calcinate at 950 °C for 1 hour.", "one word retyped"),
            ("3. calcine at 950 °C for 1 hour.", "case is not folded"),
            ("3. Calcine at 950 °C for 1 hour. EXTRA", "a longer run"),
            ("3.  Calcine at 950 °C for 1 h.", "an abbreviation expanded"),
            ("Calcine at 950 degrees C for 1 hour.", "a symbol spelled out")]:
        out = findings(increment(row(src=cite(quote))))
        assert [(f.severity, f.rule) for f in out] == [(BLOCKER, "CA-NUM-002")], why
        assert "does not contain those characters" in out[0].observation, why


def test_a_quotation_the_file_says_twice_is_advisory_and_never_blocks():
    """MUTATION (§4): drop the occurrence count and accept the FIRST match. The
    row here stops being an advisory and passes silently, and the check reports
    that it verified a place it could not identify.

    ADVISORY and not BLOCKER is load-bearing, and it is §3.4's rule: only a
    NAMED locator can block — one that does not resolve, or that resolves
    without containing the value. A quotation the source says twice resolves and
    contains the pair; what is unresolved is WHICH occurrence, a property of the
    source rather than a defect in the annotation. Blocking it would be a
    non-overridable stop on a correct transcription of a repetitive source,
    which is D155's shape exactly. It routes where `uncited` routes: counted,
    carried to the auditor, never blocking.

    Arm 3 measured 0 of 192 rows landing here — a copied quotation is longer
    than a line and disambiguates itself — which is why it is the disposition
    that costs nothing and the one that would be dangerous to get wrong."""
    twice = ("# Steps\n\n"
             "Dissolve 5 g of precursor.\n"
             "Stir for ten minutes.\n"
             "Dissolve 5 g of precursor.\n")
    files = {RECIPE_PATH: twice.encode(),
             DRAFT_PATH: draft([row(value="5", unit="g",
                                    src=cite("Dissolve 5 g of precursor."))],
                               prose="Dissolve 5 g of precursor twice.")}
    result = run_checks(files, ["number_source"])
    assert result.hard_failures == 0
    assert [(f.severity, f.rule) for f in result.findings] == [(ADVISORY, "CA-NUM-004")]
    said = result.findings[0].observation
    assert "says on 2 lines" in said and "names no one place" in said
    assert "CA-NUM" not in said and "number_source" not in said

    # The count is over LINES, and that is a deliberate difference from the Arm
    # 3 harness, which counted occurrences in the whole file folded to one
    # string. The same characters twice on ONE line still name that line, and
    # the located text — the quotation itself — is identical whichever
    # occurrence was meant, so there is nothing for the auditor to weigh. It
    # passes, and it is asserted rather than left to be discovered.
    one_line = {RECIPE_PATH: b"Add 5 g and then 5 g again.\n",
                DRAFT_PATH: draft([row(value="5", unit="g", src=cite("5 g"))],
                                  prose="Two portions of 5 g.")}
    assert findings(one_line) == []


@pytest.mark.parametrize("quote,why", [
    ("3. Calcine at  950 °C  for 1 hour.", "the annotation doubled a space"),
    ("3. Calcine at 950 °C for 1 hour.", "U+00A0 NO-BREAK SPACE"),
    ("3. Calcine at 950 °C for 1 hour.", "U+202F NARROW NO-BREAK SPACE"),
    ("3. Calcine\n   at 950 °C for 1 hour.", "a line break inside the quote"),
    ("  3. Calcine at 950 °C for 1 hour.  ", "leading and trailing space"),
])
def test_whitespace_is_folded_on_both_sides_and_nothing_else_is(quote, why):
    """MUTATION: compare the raw characters, or fold something else as well.

    Folding every run of whitespace to one space is the ONE normalisation this
    contract performs, on both sides, and it is `normalise_unit`'s own fold
    applied to a longer string. It is what lets a quotation survive a line break
    the writer put inside it, a double space the source put inside itself, and
    the non-breaking spaces a word processor leaves behind. Fold anything more —
    case, punctuation, accents — and a retyped quotation starts passing as a
    copied one, which is the premise the whole contract rests on.

    The case fold is asserted in the other direction by
    `test_a_quotation_the_file_does_not_contain_is_a_blocker`."""
    assert findings(increment(row(src=cite(quote)))) == [], why


@pytest.mark.parametrize("named", [
    "../../../etc/passwd",
    "../synthesis/RECIPE.md",
    "/etc/passwd",
    "/work/synthesis/RECIPE.md",
    "work/synthesis/../synthesis/RECIPE.md",
    "./work/synthesis/RECIPE.md",
])
def test_a_file_outside_the_audited_scope_is_refused_however_it_is_written(named):
    """MUTATION: resolve the path against the filesystem instead of against the
    increment mapping — `Path(root, named).read_text()`, or a walk that follows
    a link. Every row here becomes a read of a file nobody committed, and a
    check that opens arbitrary paths on behalf of a model's output is the
    deny-by-default invariant gone.

    There is nothing to traverse: `_resolve` is two dictionary lookups against
    the audited scope, so traversal, an absolute path, a normalised alias and a
    symlink are all refused by the same clause and for the same reason — none of
    them is a key. The symlink half is asserted below with a real link on
    disk."""
    out = findings(increment(row(src=cite(L11, file=named))))
    assert [(f.severity, f.rule) for f in out] == [(BLOCKER, "CA-NUM-001")], named
    assert "not in the audited scope" in out[0].observation


def test_a_symlink_on_disk_is_not_a_path_into_the_audited_scope(tmp_path):
    """MUTATION: the same one — resolve through the filesystem. This asserts it
    where a link exists to be followed: a real symlink, in a real directory,
    pointing at a real file whose bytes contain the pair, and a check that
    never opens it because the increment mapping is the only scope there is.

    The same identity mistake was the root cause D156's second correction
    records — a loader resolving through the filesystem while the filters
    compared Git tree paths — so it is asserted here rather than assumed from
    the shape of `_resolve`."""
    (tmp_path / "work").mkdir()
    real = tmp_path / "work" / "RECIPE.md"
    real.write_text(RECIPE, encoding="utf-8")
    link = tmp_path / "work" / "linked.md"
    link.symlink_to(real)
    assert link.is_symlink() and "950 °C" in link.read_text(encoding="utf-8")

    for named in (str(link), "work/linked.md", "linked.md"):
        out = findings(increment(row(src=cite(L11, file=named))))
        assert [f.rule for f in out] == ["CA-NUM-001"], named
        assert "not in the audited scope" in out[0].observation, named


def test_the_address_a_finding_prints_is_derived_and_never_asked_for():
    """MUTATION (D158, §0): ask the row for `at` again and print that. The first
    assertion reddens on the row whose `at` is a lie, and — worse — the product
    is back to printing an address the generator guessed, which on Arm 2's
    drafts was outside the draft itself on 50 of 215 rows.

    The generator emits a whole file in one reply, so the line its sentence
    lands on is a function of prose it has not written yet. Code has the draft
    and the transcription and can simply look, which is what `_derive_at` does.
    The fence bodies are blanked before it looks, newline for newline: without
    that a row locates ITSELF, because `"v": "42"` in the annotation is a 42
    followed by no unit and an empty unit constrains nothing."""
    prose = "# E\n\nintro\n\nCalcined at 950 °C for 1 h.\n"
    body = json.dumps([{"v": "950", "u": "°C", "src": cite(L12), "at": "#L2"}],
                      ensure_ascii=False)
    files = {RECIPE_PATH: RECIPE.encode(),
             DRAFT_PATH: f"{prose}\n```crossaudit-numbers\n{body}\n```\n".encode()}
    out = findings(files)
    assert [f.rule for f in out] == ["CA-NUM-002"]
    assert out[0].observation.startswith("line 5 quotes "), out[0].observation

    # A draft that never states the pair in its own prose gets an honest
    # nothing, and the row is still identified by the value it quotes for.
    unstated = json.dumps([{"v": "42", "u": "", "src": cite(L12)}])
    files[DRAFT_PATH] = (f"# E\n\nno numbers here.\n\n"
                         f"```crossaudit-numbers\n{unstated}\n```\n").encode()
    out = findings(files)
    assert [f.rule for f in out] == ["CA-NUM-002"]
    assert out[0].observation.startswith('the row quotes '), out[0].observation


# ---------------- the containment note's live false pass, fixed out of band
@pytest.mark.parametrize("span,v,u,expected,why", [
    # The row the note found, in the shape the corpus writes it (M9a).
    ("base pressure ≈ 3 × 10⁻² mbar", "3", "",     ["CA-NUM-002"], "the live false pass"),
    ("base pressure ≈ 3 × 10⁻² mbar", "3", "mbar", ["CA-NUM-002"], "and with a unit named"),
    ("3×10⁻² mbar",                   "3", "",     ["CA-NUM-002"], "the adjacent form, unchanged"),
    ("5 x 10^3 g",                    "5", "",     ["CA-NUM-002"], "an ASCII x and a caret"),
    ("5 · 10⁵ g",                     "5", "",     ["CA-NUM-002"], "a spaced middle dot"),
    ("5 ⋅ 10⁵ g",                     "5", "",     ["CA-NUM-002"], "and a spaced dot operator"),
    ("5 × -10³ g",                    "5", "",     ["CA-NUM-002"], "a sign after the operator"),
    # The mirror, and it is the reason the spaced form needs its extra clause.
    ("a 5 x 3 grid",                  "5", "",     [],             "prose between two integers"),
    ("5 * 3 items",                   "5", "",     [],             "and with an asterisk"),
    ("run 5 of 12",                   "5", "",     [],             "a word after a number"),
    ("3 mbar",                        "3", "mbar", [],             "a number and its unit"),
    ("5 m·s^-1",                      "5", "m·s^-1", [],           "a caret INSIDE a unit"),
    ("cool to 25–106 °C",             "106", "°C", [],             "an en-dash range"),
])
def test_a_space_does_not_end_an_unparsed_continuation(span, v, u, expected, why):
    """MUTATION (`docs/design/CONTAINMENT_RULE.md` §4, "Out of band, and not an
    extension"): drop the `\\s+` alternative from `_UNPARSED`. The first row goes
    green — and green here is a **false PASS**, the check reporting that a
    source states three when what it states is 0.03.

    `_UNPARSED` was matched with no leading-whitespace allowance, so `3×10⁻²`
    was refused and `3 × 10⁻²` was not; with an empty transcribed unit
    `contains_pair("… ≈ 3 × 10⁻² mbar", "3", "")` returned True in the shipped
    matcher. The note verified it against the code and routed it here rather
    than into its six extensions, because a narrowing can only ever remove a
    match: it cannot add a false pass, and so it is not subject to the gold's
    kill rule. It can add a false BLOCKER, which is what the second half of this
    table is for.

    The spaced form fires only where the right operand is exponentiated, and
    that clause is the whole difference between `3 × 10⁻²` and `5 x 3`. Delete
    it and the mirror rows redden instead: every grid, window and matrix written
    with an `x` becomes a non-overridable blocker on a correct unitless
    transcription, which is the trade D157 lesson 2 and D155 both refuse."""
    files = {RECIPE_PATH: (span + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(span))])}
    assert [f.rule for f in findings(files)] == expected, why


def test_the_same_narrowing_holds_through_a_structured_citation():
    """The other interface, because `_UNPARSED` is read by one matcher and two
    callers, and the review that found the signed-notation hole found it through
    a `results.json` quantity.

    `checks: [number_source]` alone rather than the science profile, because the
    empty unit is the point: `check_units` requires a truthy `unit` and would
    answer first with CA-DATA-001, and a check that needs another check to hold
    its own contract is root cause 1 (D157 lesson 1)."""
    files = {"experiments/e1/metadata.yml": b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": "run,p\nbase pressure 3 × 10⁻² mbar\n".encode(),
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "p", "value": 3, "unit": "",
                                  "source": "runs.csv@v3#L2"}],
                  "convergence": {"converged": True}}).encode()}
    assert [f.rule for f in
            run_checks(files, ["number_source"]).findings] == ["CA-NUM-002"]


# ---------------- the review's P1: the quote selects where, the line says what
@pytest.mark.parametrize("line,quote,v,u,expected,why", [
    # Every row of the review's table. Left column is what the base check said
    # of the same source through a line citation, and it said BLOCKER to all.
    ("5 mg/mL",  "5 mg", "5", "mg", ["CA-NUM-002"], "a unit token cropped in half"),
    ("5 m-2s-1", "5 m",  "5", "m",  ["CA-NUM-002"], "and a compound exponent unit"),
    ("-5 g",     "5 g",  "5", "g",  ["CA-NUM-002"], "a minus sign cropped away"),
    ("1e+5 g",   "5 g",  "5", "g",  ["CA-NUM-002"], "an exponent cropped away"),
    ("30 °C",    "3",    "3", "",   ["CA-NUM-002"], "a digit cropped off a number"),
    ("base pressure ≈ 3 × 10⁻² mbar", "3", "3", "",
                                     ["CA-NUM-002"], "and the notation rule itself"),
    # The other bypass the fix must not open: the quote has to bound the match,
    # or a quotation of one phrase is satisfied by a number elsewhere on it.
    ("Add 5 g, then hold at 25 °C.", "then hold at 25 °C.", "5", "g",
                                     ["CA-NUM-002"], "the pair is outside the quotation"),
    # And every honest crop still passes: the quotation is a WINDOW on the line,
    # not a replacement for it.
    ("Add 5 g, then hold at 25 °C.", "Add 5 g",  "5", "g",  [], "the first pair"),
    ("Add 5 g, then hold at 25 °C.", "at 25 °C", "25", "°C", [], "the second pair"),
    ("5 mg/mL",  "5 mg/mL",  "5", "mg/mL", [], "the whole unit token, quoted whole"),
    ("10 wt % Ni", "10 wt %", "10", "wt%",  [], "the percent split, quoted to its end"),
    ("3. Calcine at 950 °C for 1 hour.", "950 °C", "950", "°C", [], "a crop of the fixture"),
    ("cool to 25–106 °C", "106 °C", "106", "°C", [], "the endpoint that carries the unit"),
])
def test_the_quote_selects_the_window_and_the_line_decides_the_pair(
        line, quote, v, u, expected, why):
    """MUTATION: match the isolated quotation — hand `contains_pair` the quoted
    characters instead of the line they came from. Every blocking row above goes
    green, and this is not a new defect but three old ones returning at once:
    the unit prefix (D157 lesson 2, fixed three times), the sign rule (the fifth
    review), and the exponent sign (the sixth). **Cropping the adjoining
    characters out of the text handed to the matcher disables every boundary
    rule in the module simultaneously**, because each of them reads what adjoins
    an occurrence — which is what an independent review found in the first cut
    of this slice, and what `test_the_sign_cropping_sweep_the_review_ran`
    measures at a hundred rows.

    The rule that replaces it: the matcher scans the whole folded LINE, so
    `_NUMBER`'s lookbehind, the sign, the whole-unit-token boundary and
    `_UNPARSED` all see their context; the occurrence it returns must then lie
    INSIDE the quoted interval. Drop the interval clause and the row marked "the
    pair is outside the quotation" goes green instead — a quotation satisfied by
    a number it does not contain, which is the other half of the same bypass.
    The design's sentence "every property the span rule bought stays bought" is
    only true under both halves."""
    files = {RECIPE_PATH: (line + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(quote))],
                               prose="see the source")}
    assert [f.rule for f in findings(files)] == expected, why


@pytest.mark.parametrize("magnitude", range(1, 101))
def test_the_sign_cropping_sweep_the_review_ran(magnitude):
    """MUTATION: the same one — match the isolated quotation. All 100 rows go
    green, which is what the review measured against the first cut of this
    slice: `-1 g` through `-100 g`, each annotated as the positive value and
    quoted from just after the minus sign, was **100 of 100 incorrect PASS**.

    A contiguous hundred is a grammar defect and not a curiosity, which is the
    same reason the round-3 exponent sweep and the round-6 sign sweep are whole
    ranges rather than examples. The base check blocks all 100 through a line
    citation; so does this one now."""
    files = {RECIPE_PATH: f"-{magnitude} g\n".encode(),
             DRAFT_PATH: draft([row(value=str(magnitude), unit="g",
                                    src=cite(f"{magnitude} g"))],
                               prose="see the source")}
    assert [f.rule for f in findings(files)] == ["CA-NUM-002"]


# ------------------ the review's P2: a separated superscript is a footnote
@pytest.mark.parametrize("line,quote,v,u,expected,why", [
    ("Participants: 5 ¹", "Participants: 5 ¹", "5", "", [],
     "a footnote mark is not an exponent"),
    ("Enrolled 12 ² at baseline", "Enrolled 12 ²", "12", "", [],
     "and it is not one mid-sentence either"),
    ("Yield 5 ⁻ see note", "Yield 5 ⁻", "5", "", [],
     "nor is a separated superscript sign"),
    # The adjacent forms are untouched: they are the bytes that shipped.
    ("Yield 10⁵ g", "Yield 10⁵ g", "10", "", ["CA-NUM-002"], "adjacent stays notation"),
    ("Yield 10⁻⁵ g", "Yield 10⁻⁵ g", "10", "", ["CA-NUM-002"], "in either sign"),
    # And the separated OPERATOR form, which is the whole point of the change.
    ("base pressure ≈ 3 × 10⁻² mbar", "base pressure ≈ 3 × 10⁻² mbar", "3", "",
     ["CA-NUM-002"], "a separated operator is still notation"),
])
def test_a_separated_superscript_is_a_footnote_and_not_an_exponent(
        line, quote, v, u, expected, why):
    """MUTATION: allow whitespace before the superscript alternatives of
    `_UNPARSED` as well as before the operator — which is what the first cut of
    this slice did. The footnote rows redden: `Participants: 5 ¹`, with
    `¹ Enrollment count` further down the page, becomes a non-overridable
    blocker on a correct unitless annotation, and a footnote mark is the most
    ordinary thing in the world to find after a number in a paper.

    Only an OPERATOR may be separated from its left operand, and only where its
    right operand is exponentiated. The four adjacent alternatives are the bytes
    that shipped before this slice and are asserted here beside the new one, so
    the change is visibly one alternative and not four."""
    files = {RECIPE_PATH: (line + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(quote))],
                               prose="see the source")}
    assert [f.rule for f in findings(files)] == expected, why


def test_the_continuation_never_crosses_a_line_break():
    """MUTATION: write the new alternative's whitespace as `\\s` rather than
    `[^\\S\\r\\n]`. A superscript or an operator on the NEXT line then continues
    the number above it, and both rows here redden.

    It reaches the check through the `results.json` locator, which is the one
    place a span can still be MORE than one line — a footnote definition on the
    line after the number is exactly the shape `#L2-L3` names."""
    footnote = "run,p\nParticipants: 5\n¹ Enrollment count; see the trial log.\n"
    def project(source):
        return {"experiments/e1/metadata.yml":
                b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
                "experiments/e1/runs.csv": footnote.encode(),
                "experiments/e1/results.json": json.dumps(
                    {"quantities": [{"name": "p", "value": 5, "unit": "",
                                     "source": source}],
                     "convergence": {"converged": True}}).encode()}
    assert run_checks(project("runs.csv@v3#L2-L3"), ["number_source"]).findings == []
    assert run_checks(project("runs.csv@v3#L2"), ["number_source"]).findings == []

    # The operator form, one line down, is not this number's continuation either.
    product = "run,p\nBase pressure 3\n× 10⁻² mbar in the chamber.\n"
    files = {"experiments/e1/metadata.yml":
             b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
             "experiments/e1/runs.csv": product.encode(),
             "experiments/e1/results.json": json.dumps(
                 {"quantities": [{"name": "p", "value": 3, "unit": "",
                                  "source": "runs.csv@v3#L2-L3"}],
                  "convergence": {"converged": True}}).encode()}
    assert run_checks(files, ["number_source"]).findings == []


# ------- the second review's P2: a footnote on the RIGHT operand, too
#: `Grid dimensions: 5 x 3 ¹`, with `¹ Dimensions are in cells.` beneath it.
#: The footnote sits on the operand to the RIGHT of the `x`, which the second
#: cut of the separated-operator rule read as an exponent on the 3.
#:
#: FOR THE GOLD RECORD, `benchmarks/expertlongbench/RESULTS-GOLD.md` Amendment 2
#: (owned by that record; stated here rather than edited in on this branch):
#: *the footnoted grid `Grid dimensions: 5 x 3 ¹` is a second instance of the
#: class the corpus lacks — the frozen 300 items contain no row at all in which
#: a digit is followed by whitespace and then a superscript, so the gold scored
#: W = 0 for the rule that blocked 100 of 100 such rows exactly as it did for
#: the rule that does not, and could no more distinguish this draft than the
#: first one.*
GRID = "Grid dimensions: 5 x 3 ¹"
GRID_NOTE = "¹ Dimensions are in cells."


@pytest.mark.parametrize("line,v,u,expected,why", [
    (GRID,                      "5",  "", [], "a footnote on the right operand"),
    ("Grid dimensions: 5 x 3 ¹", "5", "", [], "and with a no-break space before it"),
    ("Grid dimensions: 5 x 3 ¹", "3",  "", [], "the operand it is attached to, too"),
    ("5 x 10 ³ g",              "5",  "", [], "a spaced superscript is a footnote on a ten"),
    ("a 5 x 3 grid",            "5",  "", [], "and a plain product is still prose"),
    ("Participants: 5 ¹",       "5",  "", [], "the left operand, unchanged"),
    # The mirrors: an ADJACENT marker on the right operand is still notation.
    ("5 x 10³ g",               "5",  "", ["CA-NUM-002"], "5 × 10³ is not 5"),
    ("5 x 10^3 g",              "5",  "", ["CA-NUM-002"], "nor with a caret"),
    ("5 × -10³ g",              "5",  "", ["CA-NUM-002"], "nor with a sign between"),
    ("base pressure ≈ 3 × 10⁻² mbar", "3", "", ["CA-NUM-002"], "the row this rule exists for"),
    ("3×10⁻² mbar",             "3",  "", ["CA-NUM-002"], "and its adjacent form"),
])
def test_an_exponent_marker_must_adjoin_the_operand_it_exponentiates(
        line, v, u, expected, why):
    """MUTATION: restore the trailing `[^\\S\\r\\n]*` before the marker in
    `_UNPARSED`'s fifth alternative — the allowance this slice's second cut
    carried. `Grid dimensions: 5 x 3 ¹` becomes a non-overridable blocker on a
    correctly annotated unitless five, and
    `test_the_footnoted_grid_sweep_the_second_review_ran` reddens at all 100
    rows. Both were PASS at the base commit; this was a weakening.

    The whitespace allowance is in front of the OPERATOR and nowhere else. A
    superscript separated from the number it follows is a footnote mark — the
    rule the left-hand operand already had — and the right-hand operand is owed
    the same answer: `5 x 10³` is notation, `5 x 10 ³` is a footnote on a ten.

    Both interfaces, because a footnote definition on the line BELOW the number
    is exactly the shape a `results.json` range names: see the structured half
    in `test_the_footnoted_grid_reaches_both_interfaces`."""
    files = {RECIPE_PATH: (line + "\n" + GRID_NOTE + "\n").encode(),
             DRAFT_PATH: draft([row(value=v, unit=u, src=cite(line))],
                               prose="see the source")}
    assert [f.rule for f in findings(files)] == expected, why


@pytest.mark.parametrize("magnitude", range(1, 101))
def test_the_footnoted_grid_sweep_the_second_review_ran(magnitude):
    """MUTATION: the same one — restore the trailing whitespace allowance. All
    100 rows redden. The second review swept `Grid dimensions: <n> x 101 ¹` for
    n = 1…100 and measured **0 base blockers against 100 head false blockers**;
    a contiguous hundred is a grammar defect and not a curiosity, so the range
    is the guard, as it is for the sign sweep and the exponent sweep."""
    line = f"Grid dimensions: {magnitude} x 101 ¹"
    files = {RECIPE_PATH: (line + "\n" + GRID_NOTE + "\n").encode(),
             DRAFT_PATH: draft([row(value=str(magnitude), unit="", src=cite(line))],
                               prose="see the source")}
    assert findings(files) == []


def test_the_footnoted_grid_reaches_both_interfaces():
    """The structured half of the case above, in the shape that makes it real: a
    `results.json` quantity citing `#L1-L2`, where line 2 is the footnote's own
    definition. That span is the one place this check reads more than one line,
    so it is where a footnote marker and its definition can meet the matcher
    together.

    MUTATION: as above. The range citation blocks, and a quantity a script wrote
    correctly is refused by the deterministic layer before any model sees it."""
    def project(source: str) -> dict[str, bytes]:
        return {"experiments/e1/metadata.yml":
                b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
                "experiments/e1/runs.csv": f"{GRID}\n{GRID_NOTE}\n".encode(),
                "experiments/e1/results.json": json.dumps(
                    {"quantities": [{"name": "cells", "value": 5, "unit": "",
                                     "source": source}],
                     "convergence": {"converged": True}}).encode()}

    assert run_checks(project("runs.csv@v3#L1-L2"), ["number_source"]).findings == []
    assert run_checks(project("runs.csv@v3#L1"), ["number_source"]).findings == []

    # And the notation form through the same interface still blocks, so the
    # narrowing this slice exists for is not what was given up to fix it.
    product = {"experiments/e1/metadata.yml":
               b"code_version: v3\ninputs:\n  - runs.csv@v3\n",
               "experiments/e1/runs.csv": "base pressure 3 × 10⁻² mbar\n".encode(),
               "experiments/e1/results.json": json.dumps(
                   {"quantities": [{"name": "p", "value": 3, "unit": "",
                                    "source": "runs.csv@v3#L1"}],
                    "convergence": {"converged": True}}).encode()}
    assert [f.rule for f in run_checks(product, ["number_source"]).findings] == \
        ["CA-NUM-002"]
