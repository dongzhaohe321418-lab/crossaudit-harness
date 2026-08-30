"""Executable security cases for the Generator's physical file identity boundary."""
from __future__ import annotations

import os
import subprocess
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import file_identity as identity
from crossaudit import generator
from crossaudit.cli import build as build_mod
from crossaudit.cli.build import _stage_generated
from crossaudit.errors import ProviderDenial


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir(parents=True)
    (root / "work").mkdir()
    return root


def _git_project(tmp_path: Path) -> Path:
    root = _project(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"],
                   cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    return root


def _s0_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = _git_project(tmp_path)
    rules = root / "AUDIT_RULES.md"
    rules.write_text("BLOCKER: must hold\n", encoding="utf-8")
    (root / "work" / "seed.md").write_text("seed\n", encoding="utf-8")
    (root / "work" / "rules-link.md").symlink_to("../AUDIT_RULES.md")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True)
    return root, rules


def test_whole_file_symlink_escape_is_refused_before_write_or_stage(tmp_path: Path):
    root, rules = _s0_fixture(tmp_path)
    work = generator.Work("rewrite", {
        "work/rules-link.md": "ADVISORY: may skip\n",
    })

    with pytest.raises(ProviderDenial, match="authorized working directories"):
        generator.bind_file_identities(work, root, ["work"])

    assert rules.read_text(encoding="utf-8") == "BLOCKER: must hold\n"
    assert _stage_generated(SimpleNamespace(root=root), []) == []
    assert subprocess.run(
        ["git", "status", "--short"], cwd=root, check=True,
        capture_output=True, text=True).stdout == ""


def test_real_apply_refuses_even_if_resolution_is_mutated_to_lexical(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The D10 mutation now runs real apply; atomic replace is a second guard."""
    def assert_rules_cannot_be_rewritten(root: Path, rules: Path) -> None:
        try:
            work = generator.bind_file_identities(generator.Work("rewrite", {
                "work/rules-link.md": "ADVISORY: may skip\n",
            }), root, ["work"])
            receipt = generator.apply(work, root, ["work"])
        except ProviderDenial:
            receipt = None
        if receipt is not None:
            receipt.finalize()
        assert rules.read_text(encoding="utf-8") == "BLOCKER: must hold\n"

    safe_root, safe_rules = _s0_fixture(tmp_path / "safe")
    assert_rules_cannot_be_rewritten(safe_root, safe_rules)

    def lexical_mutant(_root: Path, requested: Path):
        return requested.absolute(), True, requested.stat()

    mutant_root, mutant_rules = _s0_fixture(tmp_path / "mutant")
    monkeypatch.setattr(identity, "_physical_target", lexical_mutant)
    assert_rules_cannot_be_rewritten(mutant_root, mutant_rules)


def test_in_scope_symlink_binds_writes_and_stages_the_physical_file(tmp_path: Path):
    root = _git_project(tmp_path)
    target = root / "work" / "actual.md"
    target.write_text("old\n", encoding="utf-8")
    (root / "work" / "alias.md").symlink_to("actual.md")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True)

    work = generator.bind_file_identities(
        generator.Work("change", {"work/alias.md": "new\n"}), root, ["work"])
    assert work.files == {"work/actual.md": "new\n"}
    written = generator.apply(work, root, ["work"])
    staged = _stage_generated(SimpleNamespace(root=root), written)

    assert written == ["work/actual.md"]
    assert staged == ["work/actual.md"]
    assert target.read_text(encoding="utf-8") == "new\n"
    status = subprocess.run(["git", "status", "--short"], cwd=root, check=True,
                            capture_output=True, text=True).stdout
    assert status == "M  work/actual.md\n"


@pytest.mark.parametrize("aliases", [
    ("work/a.md", "work/./a.md"),
    ("work/a.md", "work//a.md"),
])
def test_lexical_alias_pairs_for_one_file_refuse_whole_reply(
        tmp_path: Path, aliases: tuple[str, str]):
    root = _project(tmp_path)
    (root / "work" / "a.md").write_text("old", encoding="utf-8")
    work = generator.Work("ambiguous", {aliases[0]: "one", aliases[1]: "two"})

    with pytest.raises(ProviderDenial, match="one physical file|equivalent"):
        generator.bind_file_identities(work, root, ["work"])
    assert (root / "work" / "a.md").read_text(encoding="utf-8") == "old"


def test_symlink_and_target_requests_for_one_file_refuse_whole_reply(tmp_path: Path):
    root = _project(tmp_path)
    target = root / "work" / "a.md"
    target.write_text("old", encoding="utf-8")
    (root / "work" / "alias.md").symlink_to("a.md")
    work = generator.Work("ambiguous", {
        "work/a.md": "one", "work/alias.md": "two",
    })

    with pytest.raises(ProviderDenial, match="one physical file"):
        generator.bind_file_identities(work, root, ["work"])
    assert target.read_text(encoding="utf-8") == "old"


def test_hardlinked_target_is_refused_even_when_only_one_name_was_requested(
        tmp_path: Path):
    root = _project(tmp_path)
    target = root / "work" / "a.md"
    outside = root / "AUDIT_RULES.md"
    outside.write_text("BLOCKER", encoding="utf-8")
    os.link(outside, target)

    with pytest.raises(ProviderDenial, match="hardlinked.*non-unique"):
        generator.bind_file_identities(
            generator.Work("change", {"work/a.md": "ADVISORY"}), root, ["work"])
    assert outside.read_text(encoding="utf-8") == "BLOCKER"


@pytest.mark.parametrize("kind", ["case", "unicode"])
def test_filesystem_equivalent_existing_names_refuse_on_this_volume(
        tmp_path: Path, kind: str):
    root = _project(tmp_path)
    if kind == "case":
        actual, alias = "Case-alias.txt", "case-alias.txt"
    else:
        actual = "caf\N{LATIN SMALL LETTER E WITH ACUTE}.txt"
        alias = unicodedata.normalize("NFD", actual)
    path = root / "work" / actual
    path.write_text("old", encoding="utf-8")
    alias_path = root / "work" / alias
    if not alias_path.exists() or not alias_path.samefile(path):
        pytest.skip(f"{kind} aliases are distinct on this test filesystem")

    work = generator.Work("ambiguous", {
        f"work/{actual}": "one", f"work/{alias}": "two",
    })
    with pytest.raises(ProviderDenial, match="one physical file"):
        generator.bind_file_identities(work, root, ["work"])
    assert path.read_text(encoding="utf-8") == "old"


def test_two_new_case_and_unicode_aliases_follow_measured_volume_rules(tmp_path: Path):
    root = _project(tmp_path)
    rules = identity._filesystem_rules(root)
    pairs = []
    if rules.case_insensitive:
        pairs.append(("work/New.txt", "work/new.txt"))
    if rules.unicode_normalizing:
        nfc = "work/caf\N{LATIN SMALL LETTER E WITH ACUTE}.txt"
        pairs.append((nfc, unicodedata.normalize("NFD", nfc)))
    assert pairs, "the macOS product volume must expose at least one alias rule"

    for first, second in pairs:
        with pytest.raises(ProviderDenial, match="filesystem-equivalent"):
            generator.bind_file_identities(
                generator.Work("ambiguous", {first: "one", second: "two"}),
                root, ["work"])


def test_quoted_trailing_space_is_honoured_without_stripping(tmp_path: Path):
    root = _project(tmp_path)
    spaced = root / "work" / "report.md "
    plain = root / "work" / "report.md"
    spaced.write_text("spaced-old", encoding="utf-8")
    plain.write_text("plain-old", encoding="utf-8")
    reply = '''SUMMARY: exact path
<<<CROSSAUDIT-OUTPUT-FILE path="work/report.md ">>>
spaced-new
<<<END-CROSSAUDIT-OUTPUT-FILE>>>
NOTES:
'''

    work = generator.parse_work_reply(reply)
    assert list(work.files) == ["work/report.md "]
    bound = generator.bind_file_identities(work, root, ["work"])
    generator.apply(bound, root, ["work"])

    assert spaced.read_text(encoding="utf-8") == "spaced-new"
    assert plain.read_text(encoding="utf-8") == "plain-old"


def test_json_paths_differing_by_trailing_space_do_not_collapse(tmp_path: Path):
    root = _project(tmp_path)
    work = generator.Work.from_json({
        "summary": "two exact files",
        "files": [
            {"path": "work/a.txt", "content": "plain"},
            {"path": "work/a.txt ", "content": "spaced"},
        ],
    })

    bound = generator.bind_file_identities(work, root, ["work"])
    written = generator.apply(bound, root, ["work"])
    assert written == ["work/a.txt", "work/a.txt "]
    assert (root / "work" / "a.txt").read_text(encoding="utf-8") == "plain"
    assert (root / "work" / "a.txt ").read_text(encoding="utf-8") == "spaced"


def test_json_exact_duplicate_requests_are_refused_before_dictionary_collapse():
    with pytest.raises(ProviderDenial, match="duplicate file request"):
        generator.Work.from_json({
            "files": [
                {"path": "work/a.txt", "content": "one"},
                {"path": "work/a.txt", "content": "two"},
            ],
        })


def test_trailing_slash_is_refused_instead_of_becoming_a_different_file(tmp_path: Path):
    root = _project(tmp_path)
    with pytest.raises(ProviderDenial, match="directory syntax"):
        generator.bind_file_identities(
            generator.Work("bad path", {"work/report/": "content"}), root, ["work"])
    assert not (root / "work" / "report").exists()


def test_authorized_directory_that_resolves_outside_project_is_refused(tmp_path: Path):
    root = tmp_path / "project"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "work").symlink_to(outside)

    with pytest.raises(ProviderDenial, match="outside the project"):
        generator.bind_file_identities(
            generator.Work("escape", {"work/a.txt": "content"}), root, ["work"])
    assert not (outside / "a.txt").exists()


@pytest.mark.parametrize("target_kind", ["outside", "dangling", "directory"])
def test_unestablishable_physical_targets_refuse_before_any_valid_peer_is_written(
        tmp_path: Path, target_kind: str):
    root = _project(tmp_path)
    suspicious = root / "work" / "suspicious"
    if target_kind == "outside":
        (root / "outside.txt").write_text("outside", encoding="utf-8")
        suspicious.symlink_to("../outside.txt")
    elif target_kind == "dangling":
        suspicious.symlink_to("missing.txt")
    else:
        suspicious.mkdir()
    valid = root / "work" / "valid.txt"
    work = generator.Work("all or nothing", {
        "work/valid.txt": "must-not-land", "work/suspicious": "bad",
    })

    with pytest.raises(ProviderDenial):
        generator.bind_file_identities(work, root, ["work"])
    assert not valid.exists()
    if target_kind == "outside":
        assert (root / "outside.txt").read_text(encoding="utf-8") == "outside"


def test_identity_change_between_binding_and_apply_refuses_before_content_write(
        tmp_path: Path):
    root = _project(tmp_path)
    outside = root / "outside"
    outside.mkdir()
    work = generator.bind_file_identities(
        generator.Work("new", {"work/new/a.txt": "payload"}), root, ["work"])
    (root / "work" / "new").symlink_to("../outside")

    with pytest.raises(ProviderDenial):
        generator.apply(work, root, ["work"])
    assert not (outside / "a.txt").exists()


def test_symlink_target_change_between_binding_and_apply_refuses_all_content(
        tmp_path: Path):
    root = _project(tmp_path)
    first = root / "work" / "first.txt"
    second = root / "work" / "second.txt"
    first.write_text("first-old", encoding="utf-8")
    second.write_text("second-old", encoding="utf-8")
    alias = root / "work" / "alias.txt"
    alias.symlink_to("first.txt")
    work = generator.bind_file_identities(
        generator.Work("change", {"work/alias.txt": "new"}), root, ["work"])
    alias.unlink()
    alias.symlink_to("second.txt")

    with pytest.raises(ProviderDenial, match="identity changed"):
        generator.apply(work, root, ["work"])
    assert first.read_text(encoding="utf-8") == "first-old"
    assert second.read_text(encoding="utf-8") == "second-old"


def test_parent_and_child_targets_are_refused_before_apply(tmp_path: Path):
    root = _project(tmp_path)
    work = generator.Work("ambiguous shape", {
        "work/node": "file", "work/node/child.txt": "child",
    })
    with pytest.raises(ProviderDenial, match="contains another"):
        generator.bind_file_identities(work, root, ["work"])
    assert not (root / "work" / "node").exists()


ROUND_TRANSACTION_SHAPES = [
    (count, parent_exists, target_exists, failure_index)
    for count in (1, 2)
    for parent_exists in (False, True)
    for target_exists in (False, True)
    for failure_index in (*range(count), None)
]


@pytest.mark.parametrize(
    "count,parent_exists,target_exists,failure_index",
    ROUND_TRANSACTION_SHAPES,
)
def test_round_transaction_exhaustive_shape_matrix(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int,
        parent_exists: bool, target_exists: bool,
        failure_index: int | None):
    """Enumerate target count/state, parent state, and every publish boundary."""
    root = _project(tmp_path)
    parent = root / "work" / "nested"
    if parent_exists or target_exists:
        parent.mkdir()
    files = {f"work/nested/{index}.txt": f"new-{index}"
             for index in range(count)}
    if target_exists:
        for index in range(count):
            (parent / f"{index}.txt").write_text(
                f"old-{index}", encoding="utf-8")
    bound = generator.bind_file_identities(
        generator.Work("matrix", files), root, ["work"])

    original_replace = identity._replace_prepared
    calls = {"value": 0}

    def injected(row):
        index = calls["value"]
        calls["value"] += 1
        if index == failure_index:
            raise OSError("injected publish refusal")
        original_replace(row)

    monkeypatch.setattr(identity, "_replace_prepared", injected)
    if failure_index is not None:
        with pytest.raises(ProviderDenial, match="atomically apply"):
            generator.apply(bound, root, ["work"])
    else:
        receipt = generator.apply(bound, root, ["work"])
        assert [
            (parent / f"{index}.txt").read_text(encoding="utf-8")
            for index in range(count)
        ] == [f"new-{index}" for index in range(count)]
        receipt.rollback()

    for index in range(count):
        path = parent / f"{index}.txt"
        if target_exists:
            assert path.read_text(encoding="utf-8") == f"old-{index}"
        else:
            assert not path.exists()
    assert parent.exists() is (parent_exists or target_exists)
    assert not list((root / "work").rglob(".crossaudit-*-*"))


def test_round_atomicity_guard_counterfactual_uses_real_apply(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """D10: deleting rollback makes the first real replacement survive refusal."""
    def exercise(base: Path, mp: pytest.MonkeyPatch) -> None:
        root = _project(base)
        for name in ("a.txt", "b.txt"):
            (root / "work" / name).write_text(f"{name}-old", encoding="utf-8")
        bound = generator.bind_file_identities(generator.Work("round", {
            "work/a.txt": "a-new", "work/b.txt": "b-new",
        }), root, ["work"])
        real_replace = identity._replace_prepared
        calls = {"value": 0}

        def fail_second(row):
            calls["value"] += 1
            if calls["value"] == 2:
                raise OSError("second replacement refused")
            real_replace(row)

        mp.setattr(identity, "_replace_prepared", fail_second)
        with pytest.raises(ProviderDenial):
            generator.apply(bound, root, ["work"])
        assert (root / "work" / "a.txt").read_text(encoding="utf-8") == "a.txt-old"
        assert (root / "work" / "b.txt").read_text(encoding="utf-8") == "b.txt-old"

    with monkeypatch.context() as safe:
        exercise(tmp_path / "safe", safe)

    with monkeypatch.context() as mutant:
        mutant.setattr(identity.AppliedFiles, "rollback",
                       identity.AppliedFiles.finalize)
        with pytest.raises(AssertionError):
            exercise(tmp_path / "mutant", mutant)


def test_parent_creation_guard_counterfactual_uses_real_apply(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """D10: following one swapped component recreates the outside mkdir/write."""
    def exercise(base: Path, mp: pytest.MonkeyPatch, *,
                 mutate_guard: bool) -> None:
        root = _project(base)
        outside = base / "outside"
        outside.mkdir()
        sub = root / "work" / "sub"
        sub.mkdir()
        bound = generator.bind_file_identities(generator.Work("nested", {
            "work/sub/deep/a.txt": "generator bytes",
        }), root, ["work"])
        real_preflight = identity._preflight_parent
        swapped = {"value": False}

        def swap_after_preflight(root_fd: int, relative: str) -> None:
            real_preflight(root_fd, relative)
            if not swapped["value"]:
                sub.rmdir()
                sub.symlink_to(outside, target_is_directory=True)
                swapped["value"] = True

        mp.setattr(identity, "_preflight_parent", swap_after_preflight)
        if mutate_guard:
            def following_open(name, *, dir_fd=None):
                return os.open(name, identity._DIRECTORY_FLAGS, dir_fd=dir_fd)
            mp.setattr(identity, "_open_directory", following_open)
        try:
            receipt = generator.apply(bound, root, ["work"])
        except ProviderDenial:
            receipt = None
        if receipt is not None:
            receipt.finalize()
        assert not (outside / "deep").exists()

    with monkeypatch.context() as safe:
        exercise(tmp_path / "safe", safe, mutate_guard=False)

    with monkeypatch.context() as mutant:
        with pytest.raises(AssertionError):
            exercise(tmp_path / "mutant", mutant, mutate_guard=True)


def test_staging_authority_guard_counterfactual_uses_real_stage(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """D10: reopening the path stages swapped outside bytes; the receipt refuses."""
    def exercise(base: Path, mp: pytest.MonkeyPatch, *,
                 mutate_guard: bool) -> None:
        root = _git_project(base)
        secret = base / "outside-secret.txt"
        secret.write_text("OUTSIDE SECRET\n", encoding="utf-8")
        receipt = generator.apply(
            generator.bind_file_identities(generator.Work("stage", {
                "work/a.txt": "authorized bytes\n",
            }), root, ["work"]), root, ["work"])
        target = root / "work" / "a.txt"
        target.unlink()
        os.link(secret, target)
        if mutate_guard:
            def historical_stage(cfg, written):
                subprocess.run(["git", "add", "--", *written], cwd=cfg.root,
                               check=True)
            mp.setattr(build_mod, "_stage_authorized", historical_stage)
        try:
            _stage_generated(SimpleNamespace(root=root), receipt)
        except ProviderDenial:
            pass
        staged = subprocess.run(
            ["git", "show", ":work/a.txt"], cwd=root, capture_output=True,
            text=True).stdout
        assert staged != secret.read_text(encoding="utf-8")
        receipt.rollback()

    with monkeypatch.context() as safe:
        exercise(tmp_path / "safe", safe, mutate_guard=False)

    with monkeypatch.context() as mutant:
        with pytest.raises(AssertionError):
            exercise(tmp_path / "mutant", mutant, mutate_guard=True)
