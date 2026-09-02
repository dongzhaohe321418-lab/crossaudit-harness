"""The refusal a person meets must be one they can read.

The fail-closed denial from the audit core — a corrupt evidence ledger refuses
to produce a receipt — worked perfectly on the frozen build and was illegible to
a Chinese user. A safety mechanism that functions and cannot be read by its
subject is worse than one that fails loudly: the person proceeds confidently
past a warning they could not understand.

These strings are the least translated in the product, and the reason is
structural: nobody walks the failure paths in another language. Setup is
translated because everyone runs setup. A denial that fires when an evidence
ledger is corrupt is seen by nobody — until it is the only thing between a
person and a forged receipt.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit.cli import i18n
from crossaudit.console import page as page_mod

HARNESS = Path(__file__).parent / "harness"
CJK = re.compile(r"[一-鿿]")
SRC = Path(page_mod.__file__).parent.parent

def _trees() -> dict[Path, ast.Module]:
    trees = {}
    for path in sorted(SRC.rglob("*.py")):
        try:
            trees[path] = ast.parse(path.read_text())
        except SyntaxError:
            continue
    return trees


def _denial_types(trees) -> set[str]:
    """Every class that IS a Denial — `errors.py`'s four and every subclass
    anywhere in `src/` (ToolError, TokenError, LedgerError, SSHFailure, …),
    found by walking the class hierarchy to a fixpoint rather than by a list
    somebody has to remember to extend."""
    types = {"Denial"}
    changed = True
    while changed:
        changed = False
        for tree in trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name not in types:
                    bases = {getattr(b, "id", "") or getattr(b, "attr", "")
                             for b in node.bases}
                    if bases & types:
                        types.add(node.name)
                        changed = True
    return types


def _denial_factories(trees, types) -> set[str]:
    """Functions annotated to return a Denial that pass their FIRST parameter
    straight through as the reason (`_path_denial(reason)`): their call sites
    are raise sites, and the reason is the argument."""
    names = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.args.args:
                continue
            returns = getattr(node.returns, "id", "")
            if returns not in types:
                continue
            first = node.args.args[0].arg
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call) and inner.args
                        and (getattr(inner.func, "id", "") in types)
                        and isinstance(inner.args[0], ast.Name)
                        and inner.args[0].id == first):
                    names.add(node.name)
    return names


def _render(node) -> str | None:
    """The reason as a template — `{}` per interpolated part — for a literal,
    an f-string, a `%` or `.format()` on a literal, a `+` chain whose parts
    are any of those, or `.strip()` around one. None for a bare variable."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_render(v) if isinstance(v, ast.Constant) else "{}"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _render(node.left), _render(node.right)
        if left is None and right is None:
            return None
        return (left if left is not None else "{}") + (right if right is not None else "{}")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = _render(node.left)
        return None if left is None else re.sub(r"%[srd]", "{}", left)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            left = _render(node.func.value)
            return None if left is None else re.sub(r"\{[^{}]*\}", "{}", left)
        if node.func.attr in ("strip", "rstrip", "lstrip"):
            return _render(node.func.value)
    return None


def _denial_messages() -> list[tuple[str, int, str]]:
    """Every reason handed to a Denial constructor — any subclass, any
    factory — from the shipped source, as a template (`X` per interpolated
    part, because that is the shape a person actually reads).

    Reasons that are a bare variable at the raise site are not here; the
    sentences behind them are proven against the source text by the orphan
    test instead.
    """
    trees = _trees()
    types = _denial_types(trees)
    constructors = types | _denial_factories(trees, types)
    found: list[tuple[str, int, str]] = []
    for path, tree in trees.items():
        rel = str(path.relative_to(SRC))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name not in constructors:
                continue
            rendered = _render(node.args[0])
            if rendered is not None:
                found.append((rel, node.lineno, rendered.replace("{}", "X")))
    return found


def _translate(values: list[str], tmp_path: Path) -> dict:
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"), str(SRC.parent.parent)],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_fail_closed_evidence_denial_is_legible_in_chinese(tmp_path):
    """The specific sentence: the audit core's own refusal.

    It carries the verifier's reason after a colon, so it is matched as a
    pattern — an exact entry would never match what a person sees, which is the
    same trap as a fixed string carrying a count.
    """
    sentence = ("evidence ledger cannot be shown to the Auditor: "
                "entry 0 digest mismatch (content tampered)")
    rendered = _translate([sentence], tmp_path)[sentence]

    assert re.search(r"[一-鿿]", rendered), (
        f"the fail-closed denial reaches a Chinese reader in English: {rendered!r}")
    assert "entry 0 digest mismatch" in rendered, (
        "the verifier's own reason was dropped instead of carried through")


def test_the_denial_still_exists_where_the_translation_expects_it():
    """A pattern for a sentence nobody raises is a catalogue entry that rots."""
    routing = (SRC / "broker/routing.py").read_text()
    assert "evidence ledger cannot be shown to the Auditor" in routing, (
        "the denial moved; its catalogue pattern now matches nothing")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_denial_reason_reaches_the_console_in_chinese(tmp_path):
    """The console-driven COUNT, measured at the seam the console now uses.

    It was 52/540 when the console translated a refusal by its text alone
    (`page.py` ZH + ZH_PATTERNS). The server now attaches `reason_zh`, looked
    up by the Denial's own reason (`i18n.denial_zh`, D130 provenance-first),
    and the page prefers it under zh, falling back to the text catalogue. So
    a reason is covered when EITHER seam has Chinese for it, and the residual
    may be at most the two sentences ALLOWED_RESIDUAL explains — never more.

    D10 mutation: drop `reason_zh` from `server._deny` — this stays green
    (the seam is measured, not the wire; see the wire test below). Add one
    `ConfigDenial("anything new")` without an entry — red, naming it.
    """
    messages = _denial_messages()
    assert len(messages) > 400, f"the denial reader has drifted: {len(messages)}"
    distinct = sorted({m for _f, _l, m in messages if m.strip()})
    rendered = _translate(distinct, tmp_path)
    by_text = {m for m in distinct if re.search(r"[一-鿿]", rendered[m])}
    by_seam = {m for m in distinct if i18n.denial_zh(m) is not None}
    covered = by_text | by_seam
    residual = set(distinct) - covered
    assert residual <= set(ALLOWED_RESIDUAL), (
        f"refusals the console shows a Chinese reader in English: "
        f"{sorted(residual - set(ALLOWED_RESIDUAL))!r}")
    # The two seams are reported separately so the number keeps its unit.
    assert len(by_text) >= 52 and len(covered) >= len(distinct) - len(ALLOWED_RESIDUAL)


def test_the_console_serves_the_refusal_in_both_languages_on_the_wire():
    """Through the shipped server: a structured refusal carries `reason_zh`
    beside `reason`, and `reason` is byte-identical to what it always was.

    D10 mutation: drop the `reason_zh` line in `server._deny` — red here.
    """
    import threading
    import urllib.error
    import urllib.request

    sys.path.insert(0, str(HARNESS))
    import enumerate_console_strings as harness
    from crossaudit.console.server import serve

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        root.mkdir()
        cfg = harness.project(root)
        url, httpd = serve(cfg, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            request = urllib.request.Request(
                url.replace("/?t=", "/api/projects/open?t="),
                data=b'{"root":"/nope"}', method="POST",
                headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raise AssertionError(f"expected a refusal, got {response.status}")
            except urllib.error.HTTPError as denied:
                body = json.loads(denied.read().decode("utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()
    assert body.get("denied") is True and body.get("reason"), body
    assert not CJK.search(body["reason"]), "the English reason must not change"
    assert CJK.search(body.get("reason_zh", "")), body
    assert body["reason_zh"] == i18n.denial_zh(body["reason"]), (
        "reason_zh must be the table's answer for THIS reason, nothing else")


def test_the_page_prefers_the_served_chinese_and_falls_back_to_its_catalogue():
    """MARKUP ONLY: the page reads `reason_zh` under zh at both fetch seams
    and still renders `reason` when the body has none."""
    page = Path(page_mod.__file__).read_text()
    assert "(currentLocale==='zh'&&data.reason_zh)||data.reason||''" in page
    assert page.count("denialText(data)") == 3  # the definition and both seams


# ----------------------------------------------------------- the CLI seam
# The console serves a refusal with `reason_zh` beside `reason` (server._deny,
# tests above); the CLI prints it on stderr as `DENIED (kind): reason`, where
# the macOS shell parses the prefix and a person reads the rest.
# `cli/denials_zh.py` is the Chinese for that rest, keyed by the English
# reason, and these tests keep it complete, honest and free of rot.
from crossaudit.cli.denials_zh import CLAUSES, COMPOSITES, ENTRIES  # noqa: E402

#: Reasons deliberately left without an entry, each with the reason why. Keys
#: are the rendering the static reader produces (`X` per interpolated part).
ALLOWED_RESIDUAL = {
    "X: X": (
        "receipt/build.py wraps EVIDENCE_BROKEN_REASON, a constant; the reader "
        "sees only the join. The sentence a person meets is covered by its own "
        "template (proven against the constant below)."),
    "X\n\n  underlying: X": (
        "providers/base.py wraps tls_advice(), a paragraph composed at runtime "
        "from this machine's certificate paths. Translating the two-word frame "
        "around an English paragraph would be a half-translation, which reads "
        "as done and is not."),
}

#: Entries whose English the static reader cannot see because the sentence is
#: assembled from a variable, and whose literal text is not in the source
#: either. Each is checked against the source, so an entry for a sentence
#: nobody raises still fails.
RAISED_BEHIND_THE_READER = {
    "{} has staged changes; commit or restore them before pairing":
        ("cli/pair.py", ['has {where}changes', '"staged "']),
    "{} has changes; commit or restore them before pairing":
        ("cli/pair.py", ['has {where}changes', 'else ""']),
    "provider returned HTTP {}\n  it said: {}\n  {}":
        ("providers/base.py", ['lines = [f"provider returned HTTP {status}"]',
                               'lines.append(f"  it said: {said}")',
                               'lines.append(f"  {_STATUS_ADVICE[status]}")']),
    "provider returned HTTP {}\n  it said: {}":
        ("providers/base.py", ['lines.append(f"  it said: {said}")']),
    "provider returned HTTP {}\n  {}":
        ("providers/base.py", ['lines.append(f"  {_STATUS_ADVICE[status]}")']),
    "ChatGPT subscription completion failed: {}":
        ("providers/codex_subscription.py", ['(f": {collector.error}" if collector.error else "")']),
}

#: The sentences the audit reads to a person, retired by the lead's ruling:
#: the console's vocabulary (审计者 / 生成者 / 准入) is the product surface.
#: Clauses whose Chinese is a proper noun plus a word the existing catalogues
#: keep Latin (`bearer token`, `API key`), so they contain no CJK by design.
LATIN_BY_DESIGN = {"a GitHub token", "a Slack token", "a Google API key"}

RETIRED_TERMS = ("审计方", "生成方", "采信", "铸出", "转录", "补全")
REQUIRED_TERMS = ("审计者", "生成者", "准入", "收据", "账本", "判定")


def _distinct_denials() -> list[str]:
    return sorted({m for _f, _l, m in _denial_messages() if m.strip()})


def _source_text() -> dict[str, str]:
    return {str(p.relative_to(SRC)): p.read_text() for p in SRC.rglob("*.py")}


def test_the_reader_enumerates_every_denial_subclass():
    """The blind spot the first review found: `ToolError("…")` left the gate
    green because the reader knew four names. Now it walks the hierarchy.

    D10 mutation: add `class Nope(ToolError)` raising a new sentence — the
    count test below goes red naming the sentence.
    """
    trees = _trees()
    types = _denial_types(trees)
    assert {"Denial", "ConfigDenial", "IntegrityDenial", "ProviderDenial",
            "ToolError", "TokenError", "LedgerError", "SSHFailure"} <= types, types
    assert "_path_denial" in _denial_factories(trees, types)
    messages = {m for _f, _l, m in _denial_messages()}
    assert "path X is outside the grant" in messages, "ToolError reasons are not read"
    assert "unknown token fields: X" in messages, "TokenError reasons are not read"
    assert "refusing dangling symlink target X" in messages, "factory reasons are not read"
    assert "gh X failed: X.X" in messages, "composed (`+`) reasons are not read"


def test_every_denial_reason_has_chinese_at_the_cli_seam():
    """The COUNT, pinned at its residual rather than at its coverage.

    D130 measured 479 refusals with no Chinese. The gate is the other way
    round now: every reason any Denial constructor, subclass or factory
    raises has an entry, except the two listed in ALLOWED_RESIDUAL with their
    reasons. It asserts equality, not a ceiling: a residual that disappears
    must be removed from the list too, so the list never carries padding.

    D10 mutation: add one `ConfigDenial("anything new")` — or one
    `ToolError("anything new")` — anywhere in `src/` without an entry, and
    this goes red naming the sentence. Remove an entry from the table, same
    result. Reword a raised sentence so its entry no longer matches, same
    result — and the orphan test below names the entry.
    """
    distinct = _distinct_denials()
    assert len(distinct) > 580, f"the denial reader has drifted: {len(distinct)}"
    residual = {m for m in distinct if i18n.denial_zh(m) is None}
    assert residual == set(ALLOWED_RESIDUAL), (
        f"refusals a Chinese reader meets in English: "
        f"{sorted(residual - set(ALLOWED_RESIDUAL))!r}; residuals listed but no "
        f"longer raised: {sorted(set(ALLOWED_RESIDUAL) - residual)!r}")


def test_every_denial_entry_translates_itself_and_carries_its_slots():
    """Each entry, driven through the shipped lookup with `X` in every slot.

    Three things at once: the result is Chinese (an entry copied across in
    English would pass the count); every interpolated part survives (a
    translation that drops the path or the sha says less than the English);
    and the entry that answered is THIS one — a more generic template placed
    earlier would otherwise swallow a specific sentence into a half-translated
    one, the exact defect the console's ZH_PATTERNS comment records.
    """
    for english, chinese in ENTRIES:
        slots = english.count("{}")
        rendered = i18n.denial_zh(english.replace("{}", "X"))
        assert rendered is not None, f"entry does not match itself: {english!r}"
        assert CJK.search(rendered), f"copied, not translated: {english!r}"
        assert rendered.count("X") >= slots, (
            f"a slot was dropped: {english!r} -> {rendered!r}")
        expected = (chinese.replace("{}", "X") if "{}" in chinese
                    else chinese.format(*["X"] * slots))
        assert rendered == expected, (
            f"{english!r} was answered by a different entry: {rendered!r}")
    for english, chinese in CLAUSES:
        if english not in LATIN_BY_DESIGN:
            assert CJK.search(chinese), f"clause copied, not translated: {english!r}"
        assert english != chinese or english in LATIN_BY_DESIGN, english
        assert english.count("{}") == chinese.count("{}"), english


def test_no_denial_entry_is_for_a_sentence_nobody_raises():
    """A catalogue entry for a sentence nobody raises is an entry that rots.

    Every English key must be raised somewhere in `src/` — as the static
    reader sees it; or, for a sentence assembled from a variable, as the
    source text proves (its longest literal run is written there verbatim);
    or by the needles in RAISED_BEHIND_THE_READER. Clauses are checked the
    same way against the source, and every COMPOSITE must be an entry.
    """
    from crossaudit.receipt.build import EVIDENCE_BROKEN_REASON

    raised = set(_distinct_denials())
    source = _source_text()
    # Adjacent string literals split across lines are one sentence in the
    # source; join them so a long sentence is found the way it is written.
    everything = re.sub(r'"\s*\n\s*f?"', "", "\n".join(source.values()))

    def written(english: str) -> bool:
        runs = [run.strip(" ") for run in english.split("{}") if len(run.strip()) >= 6]
        return bool(runs) and all(run in everything for run in runs)

    orphans = []
    for english, _zh in ENTRIES:
        if english.replace("{}", "X") in raised:
            continue
        if english in RAISED_BEHIND_THE_READER:
            rel, needles = RAISED_BEHIND_THE_READER[english]
            assert all(n in source[rel] for n in needles), (
                f"{english!r} is no longer assembled the way its entry assumes")
            continue
        if english.startswith(EVIDENCE_BROKEN_REASON + ": "):
            continue
        if not written(english):
            orphans.append(english)
    assert orphans == [], f"entries for sentences nobody raises: {orphans!r}"
    clause_orphans = [english for english, _zh in CLAUSES if not written(english)]
    assert clause_orphans == [], f"clauses nobody composes: {clause_orphans!r}"
    keys = [e for e, _ in ENTRIES]
    assert len(keys) == len(set(keys)), "duplicate English keys in the table"
    assert COMPOSITES <= set(keys), sorted(COMPOSITES - set(keys))


def test_the_glossary_is_the_consoles_and_the_retired_terms_are_gone():
    """One vocabulary across the CLI catalogue, the denial table, the clauses
    and the evidence-authority sentences: 审计者 / 生成者 / 准入 (the console's,
    by weight), never 审计方 / 生成方 / 采信; 签发 for minting a receipt, never
    铸出. A person reading `doctor --lang zh` and then a refusal must meet the
    same words for the same things.
    """
    tables = {
        "CATALOGUE[zh]": list(i18n.CATALOGUE["zh"].values()),
        "ENTRIES": [zh for _en, zh in ENTRIES],
        "CLAUSES": [zh for _en, zh in CLAUSES],
        "SENTENCES_ZH": [zh for _en, zh in i18n.SENTENCES_ZH],
    }
    for name, values in tables.items():
        for value in values:
            for term in RETIRED_TERMS:
                assert term not in value, f"{name} still says {term}: {value!r}"
    joined = "".join(zh for _en, zh in ENTRIES)
    for term in REQUIRED_TERMS:
        assert term in joined, f"the denial table never uses {term}"


def test_composed_refusals_translate_their_own_clauses_and_keep_the_rest():
    """The reasons assembled at runtime from our own clauses — an HTTP status
    with its advice, an admission shortfall list, a gh hint, a secret kind, a
    guardrail reason — come out whole in Chinese, with the foreign part (the
    vendor's words, a count, a status) carried through untouched.
    """
    cases = {
        "provider returned HTTP 401\n  it said: bad key\n  the key was rejected. "
        "Check the one in your keys file is for this vendor and not truncated — "
        "re-enter it if the paste may be incomplete":
            ("密钥被拒绝", ["bad key", "401"], ["the key was rejected"]),
        "provider returned HTTP 404\n  the endpoint does not exist. If you set a "
        "custom base URL, check it":
            ("该端点不存在", ["404"], ["endpoint does not exist"]),
        "the selected PASS is not ready for admission: verdict is BLOCKED, not "
        "PASS; audit integrity is NON_EVIDENTIAL_PROVIDER":
            ("判定是 BLOCKED，不是 PASS；审计完整性是 NON_EVIDENTIAL_PROVIDER",
             [], ["verdict is", "audit integrity is"]),
        "gh repo create failed: API rate limit exceeded. GitHub rate-limited this "
        "account; wait for the reset, then retry.":
            ("GitHub 对此账户限流了", ["API rate limit exceeded"], ["wait for the reset"]),
        "commit refused: the staged changes appear to contain a private key block; "
        "remove the secret (or add the file to .gitignore) and try again":
            ("含有私钥块", [".gitignore"], ["private key block"]),
        "Local usage guardrail paused provider calls. Daily token limit reached: "
        "3 / 1. Open Project controls to raise or clear the limit, then retry.":
            ("已达到每日 token 上限：3 / 1。", [], ["Daily token"]),
        "project cannot be deleted while a Generator/Auditor task is running; 2 "
        "remote compute job(s) are active":
            ("有生成者/审计者任务正在运行；有 2 个远程计算作业处于活动状态", [], ["running"]),
        "authority block does not validate: authority evidence digest does not "
        "match its records":
            ("authority 的证据摘要与其记录不匹配", [], ["does not match"]),
        # The specific sentence beats the generic template it also matches.
        "a capability token must be a mapping": ("能力令牌必须是映射", [], ["token"]),
        "scratch directory must be an absolute normalized POSIX path":
            ("临时目录必须是", ["POSIX"], ["scratch"]),
        "Connect Anthropic subscription in Settings before creating this project":
            ("连接 Anthropic 订阅", [], ["subscription"]),
        "max attempts must be a number": ("最大尝试次数必须是数字", [], ["max attempts"]),
    }
    for reason, (chinese, kept, gone) in cases.items():
        rendered = i18n.denial_zh(reason)
        assert rendered is not None, reason
        assert chinese in rendered, (reason, rendered)
        for part in kept:
            assert part in rendered, (reason, rendered)
        for part in gone:
            assert part not in rendered, (reason, rendered)


def test_the_cli_denied_line_speaks_chinese_after_its_parsed_prefix(
        monkeypatch, capsys, tmp_path):
    """The line a person meets on stderr, both languages, through `main()`.

    `DENIED (kind): ` stays Latin because CrossAuditApp.swift parses it
    (`hasPrefix("DENIED (")`, then the text after `): `); the sentence after
    it is served in the language the command was asked for. In English the
    line is byte-identical to what it always was.
    """
    import argparse

    from crossaudit.cli import main as main_mod
    from crossaudit.errors import ConfigDenial

    def raising(reason):
        def func(args):
            raise ConfigDenial(reason)
        return func

    def run(reason, lang):
        parser = argparse.ArgumentParser()
        parser.add_argument("--lang", default=None)
        sub = parser.add_subparsers(dest="verb")
        p = sub.add_parser("boom")
        p.set_defaults(func=raising(reason))
        monkeypatch.setattr(main_mod, "build_parser", lambda: parser)
        try:
            code = main_mod.main(["--lang", lang, "boom"])
        finally:
            i18n.set_language("en")
        captured = capsys.readouterr()
        return code, captured.err, captured.out

    repo = str(tmp_path / "proj")
    code, err, out = run(f"{repo} is not a git repository", "zh")
    assert code == ConfigDenial.exit_code
    assert err.startswith("DENIED (config): "), err
    assert f"{repo} 不是 git 仓库" in err, err
    assert "is not a git repository" not in err
    assert "[i18n]" not in out + err, "a translated refusal was counted as a fallback"

    code, err, out = run(f"{repo} is not a git repository", "en")
    assert err == f"DENIED (config): {repo} is not a git repository\n"
    assert out == ""

    # A reason with no entry is served in English, MARKED and COUNTED — the
    # same contract as `t()`, so the gap is visible in a screenshot and in CI.
    code, err, out = run("a sentence with no entry", "zh")
    assert "DENIED (config): [en] a sentence with no entry" in err
    assert "[i18n] 1 string(s) fell back to English" in out


@pytest.mark.parametrize("argv", [["run"], ["check"], ["verify", "r.json"],
                                  ["build", "make it so"]])
def test_every_command_refuses_in_the_persons_language(
        argv, monkeypatch, capsys, tmp_path):
    """Through the REAL entry, under a Chinese locale, for the commands a
    person actually meets a refusal on — not only the two that call
    `_speak()`. The first review drove 13 refusals under `zh_CN.UTF-8` and
    read 13 English lines; the language is now resolved once, in `main()`'s
    Denial branch, by the same resolver `_speak()` uses.

    D10 mutation: drop the `i18n.set_language(_language_for(args))` line in
    that branch — every case here goes red.
    """
    from crossaudit.cli import main as main_mod

    (tmp_path / "crossaudit.yml").write_text("version: 2\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    i18n.set_language("en")
    try:
        code = main_mod.main(argv)
    finally:
        i18n.set_language("en")
    err = capsys.readouterr().err
    assert code != 0
    assert "DENIED (config): 不支持的配置版本 2（应为 1）" in err, err
    assert "[en]" not in err and "config version 2 unsupported" not in err, err


def test_a_missing_key_provider_failure_is_chinese_on_both_surfaces(
        monkeypatch, capsys, tmp_path):
    """The first refusal a new Chinese user meets: no key stored, every route
    fails. Driven through the REAL resilience path (no provider is called —
    the key check refuses before a request leaves), then through the CLI
    line and the console's Decision Center row.

    Runtime values — `vendor:model`, the env var — are kept; the prose is
    Chinese on both surfaces; the English `why` is byte-identical.
    """
    from crossaudit.config import Role
    from crossaudit.controller import StateStore
    from crossaudit.console import overview
    from crossaudit.errors import ProviderDenial
    from crossaudit.providers import resilience

    sys.path.insert(0, str(HARNESS))
    import enumerate_console_strings as harness
    cfg = harness.project(tmp_path / "p")
    monkeypatch.delenv("CROSSAUDIT_GENERATOR_KEY", raising=False)
    role = Role(provider="anthropic", model="claude-opus-4-8", vendor="anthropic",
                key_env="CROSSAUDIT_GENERATOR_KEY", base_url=None,
                reasoning_effort=None, fallbacks=())
    with pytest.raises(ProviderDenial) as caught:
        resilience.complete(cfg, "generator", role, system="s", prompt="p")
    reason = caught.value.reason
    assert reason.startswith("all configured generator provider routes failed. "
                             "anthropic:claude-opus-4-8 — anthropic credential "
                             "$CROSSAUDIT_GENERATOR_KEY is not configured"), reason

    zh = i18n.denial_zh(reason)
    assert zh is not None
    assert zh.startswith("已配置的所有生成者供应商路由都失败了。anthropic:claude-opus-4-8 — "
                         "未配置 anthropic 凭据 $CROSSAUDIT_GENERATOR_KEY"), zh
    assert "routes failed" not in zh and "is not configured" not in zh

    # The Decision Center row, as the daemon records it and the server serves it.
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    escalation = ("provider failure left this task waiting for a person: " + reason)[:400]
    store.record_build_escalation(cfg.science_repo, "d" * 40, escalation, 1,
                                  "chat", "写一份报告", kind="provider")
    row = overview.escalations(cfg)[0]
    assert row["why"] == escalation, "the English sentence must not change"
    assert row["why_zh"].startswith("供应商失败，该任务正在等待人工处理：已配置的所有生成者供应商路由都失败了。"
                                   "anthropic:claude-opus-4-8 — 未配置 anthropic 凭据 "
                                   "$CROSSAUDIT_GENERATOR_KEY"), row["why_zh"]
    page = Path(page_mod.__file__).read_text()
    assert "(currentLocale==='zh'&&(row.stop_reason_zh||row.why_zh))" in page
