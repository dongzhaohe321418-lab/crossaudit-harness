"""Every sentence the repair guard can emit reaches a Chinese reader.

Closure audit D2 #8: a hand list of guard sentences pinned the rework-1
wording, and rework 2 changed seven of them under it. So this gate enumerates
the sentences from the emitters — `repair_guard`'s pattern tables and reason
builders, driven with diffs that trigger each one, and `cli/build.py`'s event
texts read from its source — and drives each REAL sentence through the
shipped `zhValue()`. A hand list cannot drift; a construct table can only
grow, and a new entry lands here the moment it exists.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crossaudit import repair_guard
from crossaudit.cli import build as build_mod
from crossaudit.console import page as page_mod
from crossaudit.repair_guard import (ADDED_PATTERNS, MARKER_PATTERNS, REMOVED_PATTERNS,
                                     RepairGuard, parse_unified_diff, screen_code_file)

HARNESS = Path(__file__).parent / "harness"
CJK = re.compile(r"[一-鿿]")
#: English sentence words (never path parts) that would mean a half-translation.
LATIN = re.compile(r"\b(?:adds|removes|changes|renames|that|which|were|and|because)\b")


def _diff(path: str, body: str, old: str = "") -> str:
    minus = "".join(f"-{line}\n" for line in old.splitlines())
    plus = "".join(f"+{line}\n" for line in body.splitlines())
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,9 +1,9 @@\n{minus}{plus}")


#: One diff per construct, so every table row is driven, not recited.
TRIGGERS = {
    "broad_exception": "try:\n    x()\nexcept Exception:\n    log()\n",
    "broad_exception:reraise": "try:\n    x()\nexcept Exception:\n    raise\n",
    "suppress_context": "with suppress(Exception):\n    x()\n",
    "empty_handler": "try:\n    x()\nexcept ValueError: pass\n",
    "relaxed_assertion": "assert True\n",
    "disabled_test": "@pytest.mark.skip\ndef test_x():\n    pass\n",
    "dead_branch": "if False:\n    x()\n",
    "shell_ignore_errors": "set +e\n",
    "lint_suppression": "x = 1  # noqa\n",
    "warning_suppression": "warnings.filterwarnings('ignore')\n",
}
REMOVALS = {
    "removed_check:strong": ("assert x\n", "y = 1\n"),
    "removed_check:weak": ("assert x\n", "assert y\n"),
    "removed_test:strong": ("def test_a():\n    pass\n", "z = 1\n"),
    "removed_test:weak": ("def test_a():\n    pass\n", "def test_b():\n    pass\n"),
}


def _screened_sentences() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, body in TRIGGERS.items():
        path = "work/x.sh" if name == "shell_ignore_errors" else "work/x.py"
        files = parse_unified_diff(_diff(path, body))
        hits = dict(screen_code_file(path, files[path]))
        key = name.split(":")[0]
        assert key in hits, (name, hits)
        out[name] = hits[key]
    for name, (old, new) in REMOVALS.items():
        files = parse_unified_diff(_diff("work/x.py", new, old))
        hits = dict(screen_code_file("work/x.py", files["work/x.py"]))
        key = name.split(":")[0]
        assert key in hits, (name, hits)
        out[name] = hits[key]
    return out


def _assessed_sentences() -> dict[str, str]:
    guard = RepairGuard(max_changed_lines=1)
    scope = guard.assess(_diff("docs/o.md", "hello\n"), scope_dirs=["work", "experiments"])
    binary = guard.assess("diff --git a/work/a.png b/work/a.png\n"
                          "Binary files /dev/null and b/work/a.png differ\n", scope_dirs=["work"])
    budget = guard.assess(_diff("work/x.py", "a = 1\nb = 2\nc = 3\n"), scope_dirs=["work"])
    unscreened = guard.assess(_diff("work/x.py", "a = 1\n"), scope_dirs=["work"],
                              staged_files=["work/x.py", "work/big.py"], truncated=True)
    nothing = guard.assess("", scope_dirs=["work"])
    out = {"scope": scope.refusals[0], "binary": binary.refusals[0],
           "budget": next(c for c in budget.cautions if c.startswith("the code change touches")),
           "unscreened": next(c for c in unscreened.cautions if "staged file(s)" in c),
           "nothing": nothing.refusals[0]}
    assert "outside the audited directories" in out["scope"]
    assert "binary file" in out["binary"] and "larger than the review" in out["unscreened"]
    return out


def _build_texts() -> dict[str, str]:
    """The texts build.py hands the console for the guard's events, from its
    source: the `emit("repair_*"|"revision_retry", "loop", <text>)` constants
    and the termination reason's template."""
    tree = ast.parse(inspect.getsource(build_mod))
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "emit"
                and len(node.args) >= 3 and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in ("repair_refused", "repair_caution", "revision_retry")
                and isinstance(node.args[2], ast.Constant)):
            out[f"event:{node.args[0].value}:{node.lineno}"] = node.args[2].value
    source = inspect.getsource(build_mod)
    match = re.search(r'f"the automatic repair was refused in round \{round_no\} "\s*f"because', source)
    assert match, "the termination reason moved"
    out["termination"] = "the automatic repair was refused in round 3 because " + _assessed_sentences()["scope"]
    assert any(k.startswith("event:repair_refused") for k in out)
    assert any(k.startswith("event:repair_caution") for k in out)
    return out


def _translate(values: list[str], tmp_path: Path) -> dict:
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"),
         str(Path(page_mod.__file__).parents[3])],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


def test_the_triggers_cover_every_construct_the_guard_can_name():
    """Enumerated from the tables, so a new construct fails HERE first."""
    names = set(ADDED_PATTERNS) | set(MARKER_PATTERNS)
    assert names == {n.split(":")[0] for n in TRIGGERS}, names ^ {n.split(":")[0] for n in TRIGGERS}
    assert set(REMOVED_PATTERNS) == {n.split(":")[0] for n in REMOVALS}
    sentences = set(_screened_sentences().values())
    for _n, (_p, what) in ADDED_PATTERNS.items():
        assert any(s.endswith(what) for s in sentences), what
    for _n, (_p, what) in MARKER_PATTERNS.items():
        assert any(s.endswith(what) for s in sentences), what
    for _n, (_p, strong, weak) in REMOVED_PATTERNS.items():
        assert any(s.endswith(strong) for s in sentences), strong
        assert any(s.endswith(weak) for s in sentences), weak
    assert any(s.endswith(repair_guard._BROAD_RERAISE_SENTENCE) for s in sentences)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_sentence_the_guard_emits_reaches_a_chinese_reader(tmp_path):
    screened = _screened_sentences()
    assessed = _assessed_sentences()
    joined = "; ".join([screened["empty_handler"], screened["removed_test:weak"],
                        assessed["scope"], assessed["budget"]])
    values = {**screened, **assessed, **_build_texts(), "joined": joined}
    rendered = _translate(sorted(set(values.values())), tmp_path)
    english = {k: v for k, v in values.items()
               if not CJK.search(rendered[v]) or LATIN.search(rendered[v])}
    assert english == {}, f"guard sentences a Chinese reader meets in English: {english}"
    # Paths, counts and construct names survive; the joined detail keeps every part.
    assert rendered[assessed["scope"]].startswith("docs/o.md ") and "`notes`" in rendered[assessed["scope"]]
    assert rendered[assessed["budget"]].startswith("代码改动涉及 3 行")
    assert "work/big.py" in rendered[assessed["unscreened"]]
    # The joined detail carries every part's own Chinese (the scope sentence
    # keeps its inner semicolon, so parts are checked, not counted).
    for part in (screened["empty_handler"], screened["removed_test:weak"],
                 assessed["scope"], assessed["budget"]):
        assert rendered[part] in rendered[joined], part
    assert rendered[values["termination"]].startswith("第 3 轮")


def test_the_console_catalogue_never_says_the_retired_word_for_the_auditor():
    page = Path(page_mod.__file__).read_text()
    assert "审计方" not in page
