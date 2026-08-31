"""CLI i18n wave 1: a person enters in one language and stays in it (D21, D25).

D25 is why this is not polish. For a Chinese-speaking first-timer an
English-only CLI is not degradation, it is exclusion — and averaging harm across
users hides exactly the users who are most harmed, because people who cannot use
something at all are always a minority of the people who can.

D21 is why the unit is the whole `init` wizard. Steps 1 through 4 are one
continuous sequence in one session, so a Chinese panel after three English
prompts is not a partial translation, it is a seam in the middle of one flow.

Every test here executes the real `crossaudit init` and reads what it printed.
None asserts that a string exists in a source file: the property is what a person
SEES, and only running it can show that.
"""
from __future__ import annotations

import argparse
import inspect
import re
from pathlib import Path

import pytest

from crossaudit.cli import i18n, main, tui, wizard


# ------------------------------------------------------ the catalogue itself
def test_every_english_key_has_a_translation():
    en, zh = set(i18n.CATALOGUE["en"]), set(i18n.CATALOGUE["zh"])
    assert en - zh == set(), f"untranslated keys: {sorted(en - zh)}"
    assert zh - en == set(), f"translations with no English: {sorted(zh - en)}"


#: Entries whose Chinese is deliberately identical to their English, because
#: what they contain is typed, matched or traced rather than read.
_IDENTICAL_BY_DESIGN = {"checks.proposal.ground", "doctor.title"}


def test_no_translation_is_still_sitting_in_english():
    """A key copied across without being translated would pass the key check.

    Two honest exceptions, each justified by SPEC-7 §4 rather than waved
    through: `checks.proposal.ground` is slots and an arrow with nothing in it
    to translate, and `doctor.title` is the command a person TYPES.
    """
    untranslated = [
        key for key, value in i18n.CATALOGUE["zh"].items()
        if value == i18n.CATALOGUE["en"][key] and key not in _IDENTICAL_BY_DESIGN]
    assert untranslated == [], f"copied, not translated: {untranslated}"


def test_every_slot_a_translation_uses_exists_in_the_english_template():
    """A translation may reorder slots; it may not invent one.

    An invented slot raises at format time and would reach a person as a
    `[missing:...]` marker on the exact screen this wave exists to fix.
    """
    slots = lambda text: set(re.findall(r"\{(\w+)\}", text))
    for key, english in i18n.CATALOGUE["en"].items():
        assert slots(i18n.CATALOGUE["zh"][key]) <= slots(english), (
            f"{key}: translation uses a slot English does not define")


# --------------------------------------------------------- the fallback rule
def test_a_missing_translation_is_served_in_english_marked_and_counted(monkeypatch):
    monkeypatch.setitem(i18n.CATALOGUE["en"], "test.only", "English text")
    i18n.set_language("zh")
    i18n.reset_fallbacks()
    try:
        rendered = i18n.t("test.only")
    finally:
        i18n.set_language("en")
    assert rendered == i18n.FALLBACK_MARK + "English text"
    assert i18n.fallbacks() == ("test.only",)


def test_a_key_that_exists_nowhere_is_shown_rather_than_raised():
    """A typo must not end somebody's setup; it must be impossible to miss."""
    i18n.reset_fallbacks()
    assert i18n.t("no.such.key") == "[missing:no.such.key]"
    assert i18n.fallbacks() == ("no.such.key",)


def test_english_is_never_marked_as_a_fallback():
    i18n.set_language("en")
    i18n.reset_fallbacks()
    assert i18n.t("done.ready") == "Ready"
    assert i18n.fallbacks() == ()


# --------------------------------------------------- the real wizard, both ways
def _init(tmp_path, monkeypatch, capsys, *, lang, name, **over):
    project = tmp_path / name
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{name}"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.chdir(project)
    args = dict(path=str(project), github=False, force=True, no_console=True,
                json=False, auditor_vendor="anthropic",
                auditor_model="claude-opus-4", generator_vendor="openai",
                generator_model="gpt-5", profile="own", lang=lang)
    args.update(over)
    main.cmd_init(argparse.Namespace(**args))
    return project, capsys.readouterr().out


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    `tui.note` WRAPS, so a sentence a person reads as one line arrives split and
    indented in the raw stream. Asserting on the raw text would miss it — the
    CLI's version of the rendered-versus-raw distinction that has caught this
    team repeatedly.
    """
    return re.sub(r"\s+", " ", text)


def test_the_whole_wizard_speaks_english_by_default(tmp_path, monkeypatch, capsys):
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="en", name="en")
    flat = _flat(out)
    for key in ("init.banner.title", "init.step1.title", "init.step3.title",
                "init.step4.title", "done.not_ready", "done.next"):
        assert i18n.CATALOGUE["en"][key] in flat, key
    assert i18n.fallbacks() == ()


def test_the_whole_wizard_speaks_chinese_end_to_end(tmp_path, monkeypatch, capsys):
    """Every step, not one panel. D21's seam is what this asserts against."""
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="zh")
    flat = _flat(out)
    for key in ("init.banner.title", "init.step1.title", "init.step1.note",
                "init.step2.title", "init.step3.title", "init.step4.title",
                "start.own.frame", "start.own.c1", "rules.free_to_change",
                "rules.written", "done.not_ready", "done.next",
                "prepare.git_init", "next.doctor_recheck"):
        # A template may open with a slot, so match its longest literal run
        # rather than its head. `tui.note` wraps, hence the flattening above.
        expected = max(re.split(r"\{\w+\}", i18n.CATALOGUE["zh"][key]),
                       key=len).strip()
        assert expected and expected in flat, f"{key}: {expected!r} not on screen"
    assert i18n.fallbacks() == (), f"fell back: {i18n.fallbacks()}"
    assert i18n.FALLBACK_MARK not in out


#: What may legitimately appear in Latin script on a Chinese screen.
#:
#: The criterion is SPEC-7 §4, supplied by the design engineer: the seam falls at
#: anything a person or a script may have to TYPE, MATCH, or TRACE. Every entry
#: below is justified by one of those three, and an entry that cannot be is not
#: an exception — it is prose we failed to translate.
#:
#: This list started at 52 entries and 37 of them were never needed. It had
#: collected `the`, `of`, `test`, `wizard` and `shell` — from wrapped sandbox
#: paths — and those are PROSE. An allowlist padded with English words is a
#: guard shaped like the bug it is meant to catch: real untranslated copy could
#: have walked straight through it. `test_the_allowlist_carries_no_padding`
#: below is what stops that happening again.
_ALLOWED_LATIN = {
    # TRACE — the product's own name, which identifies it in a bug report.
    "CrossAudit",
    # TYPE — commands and command words a person is being told to run.
    "crossaudit", "init", "build", "doctor", "git", "export",
    # TYPE / MATCH — environment variables. A person exports them; a script
    # greps for them. Translating one would make the instruction wrong.
    "CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY", "CROSSAUDIT_SHOW_KEYS",
    # TYPE / MATCH — file names and extensions that appear on disk.
    "AUDIT_RULES", "md", "yml", "env",
    # Terms of art that Chinese technical writing does not translate either.
    # Kept deliberately and named, rather than waved through as "technical".
    "API", "markdown",
}


def test_no_untranslated_english_survives_on_the_chinese_screen(
        tmp_path, monkeypatch, capsys):
    """The guard the fallback counter cannot give.

    A string that was never routed through `t()` at all is invisible to
    `fallbacks()` — it is not a missing translation, it is a missing key, and
    that is exactly how the first version of this slice shipped English `git
    init` and `Next` rows into a Chinese wizard. So the screen itself is read:
    every Latin-script run must be a thing we deliberately do not translate.
    """
    project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="latin")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
    # The sandbox path is printed verbatim and `tui.note` wraps it, so its
    # fragments land in the stream as bare Latin runs. They are characters from
    # a path, not prose, and allow-listing this machine's temp directory names
    # would make the guard pass for the wrong reason on this machine and fail on
    # anyone else's.
    # Every absolute path this run prints verbatim. Substring membership rather
    # than word equality, because `tui.note` WRAPS: a path broken across lines
    # leaves fragments like "key" from "keys-latin.env", and whether a given
    # fragment appears at all depends on where the wrapper happened to break.
    # A guard whose result depends on that is not a guard.
    where = " ".join(str(x) for x in (
        project, project.resolve(), tmp_path, tmp_path.resolve(),
        tmp_path / "keys-latin.env", tmp_path / "home-latin"))
    hexish = re.compile(r"(?i)^[0-9a-f]+$")
    stray = sorted({
        word for word in re.findall(r"[A-Za-z][A-Za-z_]{1,}", plain)
        if word not in _ALLOWED_LATIN and word not in where
        # The setup commit sha is printed and wrapped; its fragments are hex,
        # not prose.
        and not hexish.match(word)})
    assert stray == [], f"untranslated English on a Chinese screen: {stray}"

    # And the sharper half, which needs no allowlist at all: no sentence from
    # the English catalogue may appear on a Chinese screen.
    leaked = sorted(
        key for key, english in i18n.CATALOGUE["en"].items()
        if len(english) > 12 and "{" not in english and english in plain
        and key not in _IDENTICAL_BY_DESIGN)
    assert leaked == [], f"English catalogue copy on a Chinese screen: {leaked}"


def test_the_allowlist_carries_no_padding(tmp_path, monkeypatch, capsys):
    """Every declared exception must actually be needed.

    Without this, the allowlist silently accumulates: each entry that stops
    appearing stays behind as a hole, and the next English word to leak through
    lands in one of them. An unused entry is not harmless — it is pre-approved
    English. If this fails, delete the named entries; do not add to them.
    """
    project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="latin")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
    seen = set(re.findall(r"[A-Za-z][A-Za-z_]{1,}", plain))
    unused = sorted(_ALLOWED_LATIN - seen)
    assert unused == [], (
        f"allowlist entries never seen on screen — delete them: {unused}")


def test_an_unknown_language_is_english_rather_than_a_broken_screen():
    assert i18n.set_language("klingon") == "en"
    i18n.set_language("en")


def test_the_machine_contract_is_not_translated(tmp_path, monkeypatch, capsys):
    """Exit codes and --json are a scripting contract; copy is not (errors.py)."""
    from crossaudit.errors import EXIT_OK
    project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="json",
                         json=True)
    import json as _json
    payload = _json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert set(payload) >= {"config", "constitution", "mode"}
    assert payload["mode"] == "local"          # not a translated word
    assert Path(payload["config"]).name == "crossaudit.yml"


# ------------------------------------------- D10: demonstrate the guard fails
def test_the_fallback_guard_goes_red_when_a_translation_falls_back_silently(
        tmp_path, monkeypatch, capsys):
    """Mutate the real product so a missing translation is served silently.

    Mutation: `FALLBACK_MARK` becomes empty and `_record` stops recording — the
    two halves of "visible", removed together, which is precisely what `gettext`
    would have given us for free. Compared against a live unmutated run in the
    same session rather than a recorded snapshot (D10 as amended).
    """
    honest_key = sorted(i18n.CATALOGUE["zh"])[0]
    zh_without_one = dict(i18n.CATALOGUE["zh"])
    zh_without_one.pop("done.next")

    # Baseline: with the string genuinely missing, the real product marks and counts.
    monkeypatch.setitem(i18n.CATALOGUE, "zh", zh_without_one)
    _project, honest = _init(tmp_path, monkeypatch, capsys, lang="zh", name="gap")
    assert i18n.FALLBACK_MARK in honest, "the real product failed to mark the gap"
    assert "done.next" in i18n.fallbacks()
    assert "[i18n]" in honest, "the run did not report its own incompleteness"

    # Mutation: make the same gap silent.
    monkeypatch.setattr(i18n, "FALLBACK_MARK", "")
    monkeypatch.setattr(i18n, "_record", lambda key: None)
    _project2, silent = _init(tmp_path, monkeypatch, capsys, lang="zh", name="silent")
    assert i18n.FALLBACK_MARK == ""
    assert "[i18n]" not in silent, (
        "the mutation did not take; this demonstration proves nothing")
    assert i18n.fallbacks() == (), (
        "the mutation did not take; this demonstration proves nothing")
    assert i18n.CATALOGUE["en"]["done.next"] in silent, (
        "the mutation should still serve English — silently, which is the defect")


# --------------------------------------------------------- width and wrapping
def test_chinese_never_overflows_the_boxes_it_is_drawn_in(
        tmp_path, monkeypatch, capsys):
    """Chinese is fewer characters and more columns; the boxes are fixed width."""
    _project, out = _init(tmp_path, monkeypatch, capsys, lang="zh", name="width")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
    for line in plain.splitlines():
        if line.strip().startswith("│") and line.strip().endswith("│"):
            assert tui._visible(line.strip()) == tui.WIDTH, (
                f"box line is {tui._visible(line.strip())} columns, "
                f"not {tui.WIDTH}: {line!r}")


# ======================================================================= wave 2
# D21 wave 2: the keyless failure paths a first-timer hits in the next two
# minutes — doctor's FAIL detail, its fix and its verdict; build's stop message;
# the un-initialised refusal. Design's reason for that grouping is the one to
# hold onto: this is where someone lands BECAUSE SOMETHING WENT WRONG, which is
# the worst possible moment to change language on them.

def _doctor(tmp_path, monkeypatch, capsys, *, lang, name, project=None, **over):
    from crossaudit.cli import main as _main
    home = tmp_path / f"home-{name}"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    where = project or (tmp_path / f"empty-{name}")
    where.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(where)
    argv = ["doctor", "--lang", lang] + list(over.get("argv", []))
    code = _main.main(argv)
    return code, capsys.readouterr()


def test_doctor_speaks_the_language_it_was_asked_for(tmp_path, monkeypatch, capsys):
    """Verdict, FAIL label, consequence and fix — the whole default view."""
    code_en, cap_en = _doctor(tmp_path, monkeypatch, capsys, lang="en", name="den")
    code_zh, cap_zh = _doctor(tmp_path, monkeypatch, capsys, lang="zh", name="dzh")
    assert code_en == code_zh, "the exit code must not depend on the language"

    en, zh = _flat(cap_en.out), _flat(cap_zh.out)
    assert i18n.CATALOGUE["en"]["doctor.not_ready.plural"].split("{")[0] in en
    for key in ("doctor.config.label", "doctor.config.why"):
        assert i18n.CATALOGUE["en"][key] in en, key
        assert i18n.CATALOGUE["zh"][key] in zh, key
    # The verdict is translated, not merely the rows.
    assert "尚未就绪" in zh
    assert i18n.fallbacks() == (), f"fell back: {i18n.fallbacks()}"


def test_the_doctor_machine_surfaces_stay_english(tmp_path, monkeypatch, capsys):
    """`--all` is the stable surface for CI, and check NAMES are --json keys.

    SPEC-7 §4: anything a person or a script may TYPE, MATCH or TRACE is not
    translated. Translating a check name would break a scripting contract in the
    same way translating EXIT_CONFIG would.
    """
    code, cap = _doctor(tmp_path, monkeypatch, capsys, lang="zh", name="dall",
                        argv=["--all"])
    out = cap.out
    assert "[FAIL] config" in out or "[FAIL] admission-capable" in out
    assert "not ready — fix the FAIL lines above" in out
    # No Chinese anywhere in the machine view.
    assert not any(ord(ch) > 0x2E80 for ch in out), (
        "Chinese reached `doctor --all`, which CI and scripts parse")


def test_the_un_initialised_refusal_translates_its_human_half_only(
        tmp_path, monkeypatch, capsys):
    """`reason` is the machine contract; `human` is the sentence a person reads.

    The seam already existed — `human` is deliberately kept out of `as_dict()` —
    and wave 2 uses it rather than inventing a new one.
    """
    from crossaudit.config import find
    monkeypatch.chdir(tmp_path)
    i18n.set_language("zh")
    try:
        with pytest.raises(Exception) as caught:
            find(tmp_path)
    finally:
        i18n.set_language("en")
    exc = caught.value
    assert "no crossaudit.yml found from" in exc.reason, "reason must stay English"
    assert "run `crossaudit init`" in exc.reason
    assert "denied" in exc.as_dict() and exc.as_dict()["reason"] == exc.reason
    assert "human" not in exc.as_dict(), "the human sentence is not a contract"
    assert i18n.CATALOGUE["zh"]["refusal.no_project.title"] in exc.human
    assert "crossaudit init" in exc.human, "the command a person types stays Latin"


def test_build_says_what_did_not_happen_in_the_persons_language():
    """The stop message, both ways, without needing a provider."""
    for lang, key in (("en", "build.nothing"), ("zh", "build.nothing")):
        i18n.set_language(lang)
        rendered = i18n.t(key)
        assert rendered == i18n.CATALOGUE[lang][key]
    i18n.set_language("zh")
    try:
        assert "没有写出任何东西" in i18n.t("build.nothing")
        # The command in the remedy is still the command.
        assert "crossaudit build" in i18n.t("build.nothing.then", task="x")
        assert 'x' in i18n.t("build.nothing.then", task="x")
    finally:
        i18n.set_language("en")


#: The one block on a Chinese doctor screen that is still English, named rather
#: than silently tolerated. `admission.TIER_MEANING` and `Assessment.shortfalls`
#: are literal sentences with no stable ids, and they are carried verbatim by
#: `Assessment.as_dict()` — so translating them at the render site needs ids
#: added in `admission.py`, which is audit-core-adjacent and is a decision, not
#: a commit (AGENTS.md §1). Escalated rather than reached into.
_KNOWN_ENGLISH_POSTURE = (
    "self-review; the history is yours to rewrite",
    "history out of unilateral control",
    "privilege separation between the two agents",
    "the verdict is published and checkable, but nothing is refused",
    "a failed audit refuses the merge",
    "one repository holds both the work and the rules",
    "the controller's state does not outlive the run",
    "receipt consumption is not atomic",
    "branch protection was not probed",
    "the history can be rewritten by whoever holds it",
)


def _doctor_on_a_real_project(tmp_path, monkeypatch, capsys, *, lang, name):
    """A doctor run that actually reaches the posture block.

    In an empty directory doctor stops at "no project here", so the admission
    tier and its shortfalls never render — and a test written against that
    fixture would be asserting over a screen the person never sees.
    """
    from crossaudit.config import load as load_cfg
    project, _out = _init(tmp_path, monkeypatch, capsys, lang="en",
                          name=f"proj-{name}")
    load_cfg(project / "crossaudit.yml")
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    monkeypatch.chdir(project)
    code = main.main(["doctor", "--lang", lang])
    return code, capsys.readouterr()


def test_no_untranslated_english_on_the_chinese_doctor_screen(
        tmp_path, monkeypatch, capsys):
    """Same guard as the wizard's, with one named and justified exemption."""
    _code, cap = _doctor_on_a_real_project(tmp_path, monkeypatch, capsys,
                                           lang="zh", name="dscreen")
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", cap.out)
    for known in _KNOWN_ENGLISH_POSTURE:
        plain = plain.replace(known, "")
    leaked = sorted(
        key for key, english in i18n.CATALOGUE["en"].items()
        if len(english) > 12 and "{" not in english and english in plain
        and key not in _IDENTICAL_BY_DESIGN)
    assert leaked == [], f"English catalogue copy on a Chinese doctor: {leaked}"


def test_the_posture_exemption_is_real_and_not_a_blanket(tmp_path, monkeypatch,
                                                         capsys):
    """The exemption must name strings that ACTUALLY appear, or it is a hole.

    An exemption list that stops matching becomes pre-approved English exactly
    the way an unused allowlist entry does.
    """
    _code, cap = _doctor_on_a_real_project(tmp_path, monkeypatch, capsys,
                                           lang="zh", name="dexempt")
    used = [s for s in _KNOWN_ENGLISH_POSTURE if s in cap.out]
    assert used, ("no exempted posture string appeared; if the admission block is "
                  "now translated, delete this exemption rather than keep it")


def test_every_key_the_code_asks_for_exists_in_the_catalogue():
    """Static companion to the screen tests.

    The screen tests catch a key that is used and missing only on the paths they
    happen to drive. This reads every `t("...")` call in the translated modules
    and checks it against the catalogue, so a key on a rarely-taken branch
    cannot reach a person as `[missing:...]`.

    It is also the guard that would have caught a real slip in this slice: an
    unguarded string replacement failed to add `from .i18n import t` to
    `build.py`, so `t` was called and never imported. Three unrelated tests
    found it as a NameError; this finds the class.
    """
    import ast

    modules = ["src/crossaudit/cli/wizard.py", "src/crossaudit/cli/main.py",
               "src/crossaudit/cli/build.py", "src/crossaudit/cli/tui.py",
               "src/crossaudit/config.py"]
    missing = []
    for path in modules:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        # The module must be able to reach `t` at all, not merely name it.
        uses_t = any(
            (getattr(n.func, "attr", None) or getattr(n.func, "id", None)) == "t"
            for n in ast.walk(tree) if isinstance(n, ast.Call))
        if uses_t:
            assert "i18n import t" in source or "i18n.t" in source, (
                f"{path} calls t() without importing it")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name != "t" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value not in i18n.CATALOGUE["en"]:
                    missing.append((path, first.value))
    assert missing == [], f"t() keys with no catalogue entry: {missing}"


def _drifted_doctor(tmp_path, monkeypatch, capsys, *, lang, name):
    """A project whose constitution IS committed and then edited on disk.

    The third state. `git log` finds it, so it is not "not committed"; the
    working copy differs, so an audit would cite bytes the person is not looking
    at. Telling them the wrong one of those is the D71 misleading, not a wording
    preference.
    """
    from crossaudit.gitio import git

    project, _out = _init(tmp_path, monkeypatch, capsys, lang="en",
                          name=f"drift-{name}")
    rules = project / "AUDIT_RULES.md"
    git("add", "--", "AUDIT_RULES.md", cwd=project)
    git("commit", "-q", "-m", "rules", cwd=project, check=False)
    rules.write_text(rules.read_text() + "\n### CA-EXTRA-001 edited on disk\n")
    assert git("log", "-1", "--format=%H", "--", "AUDIT_RULES.md",
               cwd=project, check=False).strip(), "fixture did not commit"
    assert git("status", "--porcelain", "--", "AUDIT_RULES.md",
               cwd=project, check=False).strip(), "fixture did not drift"

    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    monkeypatch.chdir(project)
    i18n.reset_fallbacks()
    main.main(["doctor", "--lang", lang])
    return capsys.readouterr().out


def test_a_drifted_constitution_is_named_as_drift_not_as_uncommitted(
        tmp_path, monkeypatch, capsys):
    """Composed while rebasing onto v5-redesign, so it is guarded here.

    Integration carried three constitution states; this branch carried the copy
    mechanism over two. Resolving toward either side alone would have dropped
    Chinese or told a person their committed-and-then-edited rules were "not
    committed" — a claim about a different thing.
    """
    out = _flat(_drifted_doctor(tmp_path, monkeypatch, capsys, lang="en",
                                name="en"))
    assert "Your rules have uncommitted changes" in out, out[-700:]
    assert "Your rules are not committed" not in out, (
        "the drifted state was reported as never committed")
    assert "not what is on disk" in out


def test_the_drifted_row_is_chinese_with_no_fallback(tmp_path, monkeypatch,
                                                     capsys):
    """A new key reaches a zh reader translated, or it is not done (D21)."""
    out = _flat(_drifted_doctor(tmp_path, monkeypatch, capsys, lang="zh",
                                name="zh"))
    assert "你的规则有未提交的改动" in out, out[-700:]
    assert "审计会引用已提交的版本" in out
    leaked = [key for key in ("doctor.constitution_drifted.label",
                              "doctor.constitution_drifted.why",
                              "doctor.constitution_drifted.fix")
              if key in i18n.fallbacks()]
    assert leaked == [], f"the drifted copy fell back to English: {leaked}"


# ----------------------------------------------------------- plural agreement
def _count_bearing(catalogue: dict) -> dict:
    """Keys whose English renders a count immediately before a plural noun."""
    import re as _re

    noun = _re.compile(r"\{(?:count|n|total)\}\s+([a-z]+s)\b")
    return {key: text for key, text in catalogue.items()
            if not key.endswith(".plural") and noun.search(text)}


def test_every_counted_noun_has_a_singular_form():
    """"1 rules" — found by the manager, and the class rather than the instance.

    Derived from the catalogue rather than listed, so a new counted string
    cannot be added without its singular. English agrees with its number and
    Chinese does not, which is exactly why the `.plural` sibling convention
    exists rather than a rule in code.
    """
    en = i18n.CATALOGUE["en"]
    missing = sorted(key for key in _count_bearing(en)
                     if f"{key}.plural" not in en)
    assert missing == [], (
        f"counted strings with no singular form, so they say '1 rules': "
        f"{missing}. Add `<key>` as the singular and `<key>.plural` beside it, "
        f"and select on n == 1 the way doctor does.")


def test_a_plural_sibling_is_never_english_only():
    """A missing zh `.plural` is not cosmetic: the lookup falls back.

    Chinese has no plural agreement, so both forms are the same sentence — but
    the KEY must exist in the zh catalogue, or a Chinese reader meets the
    English header at exactly the moment a count appears.
    """
    en, zh = i18n.CATALOGUE["en"], i18n.CATALOGUE["zh"]
    plural_keys = [key for key in en if key.endswith(".plural")]
    assert plural_keys, "the plural convention has disappeared"
    untranslated = sorted(key for key in plural_keys if key not in zh)
    assert untranslated == [], (
        f"plural forms missing from the Chinese catalogue: {untranslated}")


def test_the_drafted_header_agrees_with_its_count():
    """F5: this named itself "driven through the shipped selection" and read the
    catalogue instead. Its `inspect.getsource()` result was unused, and changing
    the shipped selection to always choose `.plural` left it green — a guard
    that cannot fail, occupying the slot where a real one would go.

    It executes the shipped selection now, which had to be given a name before
    it could be executed at all.
    """
    from crossaudit.cli.wizard import drafted_header_key

    assert drafted_header_key(1, False) == "rules.drafted_header"
    assert drafted_header_key(3, False) == "rules.drafted_header.plural"
    assert drafted_header_key(1, True) == "rules.drafted_header.attributed"
    assert drafted_header_key(2, True) == "rules.drafted_header.attributed.plural"

    # And the rendered result, through the real catalogue: what a person reads.
    assert i18n.CATALOGUE["en"][drafted_header_key(1, False)].format(
        count=1).endswith("1 rule")
    assert i18n.CATALOGUE["en"][drafted_header_key(4, False)].format(
        count=4).endswith("4 rules")

    # Kept: this uniquely guards the singular catalogue text (D97 subsumption).
    for lang in ("en", "zh"):
        for key in ("rules.drafted_header.plural",
                    "rules.drafted_header.attributed.plural"):
            assert key in i18n.CATALOGUE[lang], f"{key} missing from {lang}"

# ============================ the human / machine boundary (F3) ============
CJK = re.compile(r"[　-鿿＀-￯]")


def _machine_project(tmp_path):
    """A project that reaches the posture and contract rows, not an empty seam.

    The committed machine-surface test used an earlier empty-project seam that
    never reached the row which leaked, which is why the leak survived it.
    """
    import subprocess

    proj = tmp_path / "machine"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=proj, check=True)
    # "No rules yet." is what puts doctor on the `note()` branch — the row that
    # leaked. A file that merely lacks headings takes the `add()` branch and
    # never reaches it, which is precisely why the committed machine-surface
    # test passed while the leak shipped. My first fixture had the same flaw and
    # the mutation run is what found it.
    (proj / "AUDIT_RULES.md").write_text(
        "# Constitution\n\nNo rules yet. Add one when you know what to require.\n")
    (proj / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "state: {dir: .crossaudit}\nchecks: [parseable]\n")
    return proj


def _doctor_output(proj, monkeypatch, capsys, **kw):
    import argparse

    monkeypatch.chdir(proj)
    main.cmd_doctor(argparse.Namespace(fix=False, online=False, lang="zh", **kw))
    return capsys.readouterr().out


def test_no_translated_text_reaches_a_machine_surface(tmp_path, monkeypatch,
                                                      capsys):
    """F3. The BOUNDARY, not the strings that happen to cross it today.

    `--all` and `--json` are a contract with a parser, and a parser does not
    read Chinese. A script consuming doctor broke under LANG=zh, silently and
    only for Chinese users. This asserts the rule rather than the instance, so
    the next producer that translates into `detail` is caught by the same test.
    """
    proj = _machine_project(tmp_path)
    for label, kw in (("--all", dict(json=False, all=True)),
                      ("--json", dict(json=True, all=True))):
        out = _doctor_output(proj, monkeypatch, capsys, **kw)
        leaked = [line for line in out.splitlines() if CJK.search(line)]
        assert leaked == [], (
            f"translated text reached the {label} machine surface: {leaked[:3]}")


def test_the_human_surface_still_speaks_chinese(tmp_path, monkeypatch, capsys):
    """The boundary must not have been held by removing the translation."""
    proj = _machine_project(tmp_path)
    out = _doctor_output(proj, monkeypatch, capsys, json=False, all=False)
    assert [line for line in out.splitlines() if CJK.search(line)], (
        "the machine surface was cleaned by making the human one English")


def test_every_check_carries_its_machine_detail_untranslated(tmp_path,
                                                             monkeypatch, capsys):
    """The rule stated on the objects themselves, one level below rendering."""
    import argparse
    import json as _json

    proj = _machine_project(tmp_path)
    monkeypatch.chdir(proj)
    main.cmd_doctor(argparse.Namespace(json=True, all=True, fix=False,
                                       online=False, lang="zh"))
    out = capsys.readouterr().out
    payload = _json.loads(out[out.index("{"):out.rindex("}") + 1])
    for row in payload["checks"]:
        for field in ("check", "detail", "fix"):
            assert not CJK.search(str(row.get(field, ""))), (
                f"{row['check']}.{field} is translated; that field is the "
                f"parser's, and a human string belongs in detail_copy")


# ==================================== the reachable Chinese paths (F2) =====
def test_the_console_handoff_speaks_the_language_the_setup_used(monkeypatch,
                                                                capsys):
    """F2. init is translated and this is its tail; an English remedy after a
    Chinese setup tells the person something broke."""
    from crossaudit.cli import main as m
    from crossaudit.console import daemon

    i18n.set_language("zh")
    try:
        monkeypatch.setattr(daemon, "reusable_for_launch", lambda *a, **k: None)
        monkeypatch.setattr(daemon, "spawn", lambda *a, **k: (
            _ for _ in ()).throw(OSError("the port was refused")))
        m._open_console(Path("/tmp/nonexistent-project"))
        out = capsys.readouterr().out
    finally:
        i18n.set_language("en")
    assert CJK.search(out), f"the console failure stayed English: {out!r}"
    assert "crossaudit console" in out, "the command a person types is not translated"


def test_build_is_not_offered_a_language_it_cannot_finish(capsys):
    """F2. Consistently one language beats a switch mid-flow.

    build's banner and closing copy are translated, but its round narration is
    RunEvent prose from the agent loop; translating that needs a
    kind-to-catalogue mapping and is wave 2. So `--lang` is not offered here
    until the narration can follow it.
    """
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        main.main(["build", "--lang", "zh", "do", "a", "thing"])
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err or "invalid choice" in err, err


# ========================= fallback reporting on every command (F4) ========
def test_a_fallback_is_counted_on_a_normal_doctor_run(tmp_path, monkeypatch,
                                                      capsys):
    """F4. `_report_untranslated` existed and only init called it."""
    proj = _machine_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.delitem(i18n.CATALOGUE["zh"], "doctor.admission_capable.label",
                        raising=False)
    i18n.reset_fallbacks()
    main.main(["doctor", "--lang", "zh"])
    out = capsys.readouterr().out
    assert "[i18n]" in out, "the fallback was visible inline but never counted"
    assert "doctor.admission_capable.label" in out, "the key was not named"


def test_the_fallback_notice_never_enters_the_machine_surface(tmp_path,
                                                              monkeypatch, capsys):
    """A defect notice printed into --json would be F3 wearing another hat."""
    import json as _json

    proj = _machine_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.delitem(i18n.CATALOGUE["zh"], "doctor.admission_capable.label",
                        raising=False)
    i18n.reset_fallbacks()
    main.main(["--json", "doctor", "--lang", "zh"])
    out = capsys.readouterr().out
    assert "[i18n]" not in out, "the notice corrupted the parser's surface"
    _json.loads(out[out.index("{"):out.rindex("}") + 1])


# ==================== F3: the emit boundary, on the ERROR route ===========
def _doctor_error_route(monkeypatch, capsys, tmp_path, *argv):
    """An UNCONFIGURED directory: the route the guards never took."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    code = main.main(list(argv))
    return code, capsys.readouterr().out


def test_the_error_route_emits_json_like_the_success_route(monkeypatch, capsys,
                                                           tmp_path):
    """F3. `--json` with no project emitted a human screen and no JSON at all.

    A parser met Chinese prose, and only on the error path — which is exactly
    where nobody was looking. The guards seeded a configured project and proved
    producer fields on the happy path, where the defect is not.
    """
    import json as _json

    code, out = _doctor_error_route(monkeypatch, capsys, tmp_path,
                                    "--json", "doctor", "--lang", "zh")
    assert code != 0, "an unconfigured project should not report success"
    payload = _json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert payload["ok"] is False
    assert payload["checks"], "the error route emitted no checks"
    assert not CJK.search(out), "the error route leaked prose into the parser"


def test_the_error_route_still_speaks_to_a_person(monkeypatch, capsys, tmp_path):
    """The boundary must not have been made common by dropping the human half."""
    _code, out = _doctor_error_route(monkeypatch, capsys, tmp_path,
                                     "doctor", "--lang", "zh")
    assert CJK.search(out), "the human error route stopped speaking Chinese"


def test_no_doctor_exit_bypasses_the_emit_boundary():
    """Common in FACT, not by convention: asserted over the shipped source.

    `_render_doctor` may only be handed to `_emit`. A branch that prints it
    directly is the F3 defect, and it is the kind of thing a reviewer reads past.
    """
    import ast

    tree = ast.parse(Path(main.__file__).read_text())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_doctor")
    stray = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "")
        if name != "print":
            continue
        for arg in ast.walk(node):
            if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "_render_doctor":
                stray.append(node.lineno)
    assert stray == [], (
        f"cmd_doctor prints a rendered screen outside _emit at line(s) {stray}; "
        f"that branch cannot emit JSON and only the error route takes it")


# ==================== F2: disclosure a person actually sees ===============
def _keyed_init(tmp_path, monkeypatch, capsys, lang, name):
    """A setup that COMPLETES, so init offers the next actions.

    `_init` deletes the credential env vars, so its run always lists a missing
    key instead — and the language switch this is about is never reached from
    there. The switch only exists on the path where setup succeeded.
    """
    import argparse

    project = tmp_path / name
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{name}"))
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "auditor-secret")
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "generator-secret")
    monkeypatch.chdir(project)
    main.cmd_init(argparse.Namespace(
        path=str(project), github=False, force=True, no_console=True, json=False,
        auditor_vendor="anthropic", auditor_model="claude-opus-4",
        generator_vendor="openai", generator_model="gpt-5", profile="own",
        lang=lang))
    return capsys.readouterr().out


def test_a_chinese_setup_says_build_answers_in_english(tmp_path, monkeypatch,
                                                       capsys):
    """F2. Not a comment, not a findings file — the screen, before the switch."""
    flat = _flat(_keyed_init(tmp_path, monkeypatch, capsys, "zh", "disc"))
    assert "crossaudit build" in flat, "the switch is not even offered here"
    assert i18n.CATALOGUE["zh"]["next.build.english_only"] in flat, (
        "the person walks from Chinese into English with nothing said")


def test_an_english_setup_is_not_told_about_a_switch_that_does_not_happen(
        tmp_path, monkeypatch, capsys):
    flat = _flat(_keyed_init(tmp_path, monkeypatch, capsys, "en", "nodisc"))
    assert "crossaudit build" in flat, "the fixture never reached the next actions"
    assert i18n.CATALOGUE["en"]["next.build.english_only"] not in flat


def test_init_and_doctor_state_the_same_wave_scope():
    """They stated different scopes, which is a contradiction met before the
    limitation itself."""
    source = Path(main.__file__).read_text()
    helps = re.findall(r'help="language for [^"]*"', source)
    assert helps == [], (
        f"the wave scope is written inline again, so the two can drift: {helps}")
    assert source.count("help=LANG_HELP") == 2, (
        "init and doctor no longer share one wave-scope sentence")
    assert "wave 1: init and doctor only" in main.LANG_HELP


def test_build_help_states_that_it_answers_in_english():
    """build has no --lang, so its own help is where its limit belongs."""
    assert "English in this wave" in main.BUILD_ENGLISH_NOTE
