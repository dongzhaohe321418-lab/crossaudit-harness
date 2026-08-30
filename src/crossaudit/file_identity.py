"""Canonical identity and authorization for Generator-owned file writes.

The model supplies names, but names are not filesystem identities.  This module
is the single boundary that follows existing links, recovers the filesystem's
actual spelling, authorizes the resulting physical target, and rejects a reply
whose names converge on one target.  Callers retain the returned binding through
validation, application, and Git staging; they never reconstruct a target from
the model's string.
"""
from __future__ import annotations

import os
import stat
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .errors import ProviderDenial


@dataclass(frozen=True)
class FilesystemRules:
    """Name equivalences observed on the project filesystem."""

    case_insensitive: bool
    unicode_normalizing: bool


@dataclass(frozen=True)
class FileTarget:
    """One requested name bound to one authorized physical target."""

    requested: str
    relative: str
    physical: Path
    exists: bool
    device: int | None
    inode: int | None


def _path_denial(reason: str) -> ProviderDenial:
    return ProviderDenial(reason, category="path_identity", retryable=True)


def _request_parts(requested: str) -> tuple[str, ...]:
    """Return exact POSIX parts, rejecting syntax that can escape before resolve."""
    if not requested or "\x00" in requested:
        raise _path_denial("refusing an empty or invalid generated file path")
    if requested.endswith("/"):
        raise _path_denial(
            f"refusing a generated file path with directory syntax: {requested!r}")
    path = PurePosixPath(requested)
    if path.is_absolute() or ".." in path.parts:
        raise _path_denial(
            f"refusing a path that escapes the project: {requested!r}")
    if not path.parts:
        raise _path_denial(f"refusing an unusable generated file path: {requested!r}")
    return path.parts


def _canonical_existing(root: Path, physical: Path) -> Path:
    """Recover the directory entries' real spelling for an existing target.

    ``realpath`` follows symlinks but does not promise to recover case or Unicode
    spelling on a filesystem that aliases names.  Walking the resolved path by
    inode does, without guessing a normalization form.
    """
    try:
        parts = physical.relative_to(root).parts
    except ValueError as exc:
        raise _path_denial(
            f"resolved target is outside the project: {physical}") from exc
    current = root
    for part in parts:
        candidate = current / part
        try:
            wanted = candidate.stat()
            entries = list(os.scandir(current))
        except (OSError, ValueError) as exc:
            raise _path_denial(
                f"could not establish physical file identity for {physical}") from exc
        matches: list[str] = []
        for entry in entries:
            try:
                found = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if (found.st_dev, found.st_ino) == (wanted.st_dev, wanted.st_ino):
                matches.append(entry.name)
        if len(matches) != 1:
            raise _path_denial(
                f"could not establish one directory identity for {candidate}")
        current /= matches[0]
    return current


def _physical_target(root: Path, requested_path: Path) -> tuple[Path, bool, os.stat_result | None]:
    """Resolve one request to its canonical physical target.

    This deliberately small function is the resolution seam used by the D10
    counterfactual test: replacing it with the historical lexical path makes the
    symlink escape observable again.
    """
    try:
        physical = requested_path.resolve(strict=True)
    except FileNotFoundError:
        if requested_path.is_symlink():
            raise _path_denial(
                f"refusing dangling symlink target {requested_path}")
        ancestor = requested_path.parent
        suffix: list[str] = [requested_path.name]
        while not ancestor.exists():
            if ancestor.is_symlink():
                raise _path_denial(
                    f"refusing dangling symlink parent {ancestor}")
            if ancestor == ancestor.parent:
                raise _path_denial(
                    f"could not establish a parent for {requested_path}")
            suffix.append(ancestor.name)
            ancestor = ancestor.parent
        try:
            resolved_parent = ancestor.resolve(strict=True)
        except OSError as exc:
            raise _path_denial(
                f"could not establish a parent for {requested_path}") from exc
        if not resolved_parent.is_dir():
            raise _path_denial(
                f"generated file parent is not a directory: {ancestor}")
        physical = resolved_parent.joinpath(*reversed(suffix))
        return physical, False, None
    except OSError as exc:
        raise _path_denial(
            f"could not resolve generated file path {requested_path}") from exc

    try:
        info = physical.stat()
    except OSError as exc:
        raise _path_denial(
            f"could not inspect generated file target {requested_path}") from exc
    physical = _canonical_existing(root, physical)
    return physical, True, info


def _within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _scope_roots(root: Path, allowed_dirs: list[str] | None) -> tuple[Path, ...]:
    if not allowed_dirs:
        return (root,)
    roots: list[Path] = []
    for raw in allowed_dirs:
        parts = _request_parts(raw)
        lexical = root.joinpath(*parts)
        physical, exists, info = _physical_target(root, lexical)
        if not _within(physical, root):
            raise _path_denial(
                f"working directory {raw!r} resolves outside the project")
        if exists and (info is None or not stat.S_ISDIR(info.st_mode)):
            raise _path_denial(f"working directory is not a directory: {raw!r}")
        roots.append(physical)
    return tuple(roots)


def _filesystem_rules(root: Path) -> FilesystemRules:
    """Measure name equivalence on the actual volume, leaving no probe behind."""
    try:
        with tempfile.TemporaryDirectory(prefix=".crossaudit-identity-", dir=root) as raw:
            probe = Path(raw)
            case_source = probe / "case-probe"
            unicode_source = probe / "\N{LATIN SMALL LETTER E WITH ACUTE}"
            case_source.touch()
            unicode_source.touch()
            case_alias = probe / "CASE-PROBE"
            unicode_alias = probe / unicodedata.normalize("NFD", unicode_source.name)
            case_insensitive = case_alias.exists() and case_alias.samefile(case_source)
            unicode_normalizing = (unicode_alias.exists()
                                   and unicode_alias.samefile(unicode_source))
    except OSError as exc:
        raise _path_denial(
            "could not establish filename identity rules on the project filesystem") from exc
    return FilesystemRules(case_insensitive, unicode_normalizing)


def _namespace_key(relative: str, rules: FilesystemRules) -> tuple[str, ...]:
    parts: list[str] = []
    for part in PurePosixPath(relative).parts:
        value = unicodedata.normalize("NFC", part) if rules.unicode_normalizing else part
        parts.append(value.casefold() if rules.case_insensitive else value)
    return tuple(parts)


def resolve_file_targets(root: Path, requested_paths: Iterable[str],
                         allowed_dirs: list[str] | None) -> tuple[FileTarget, ...]:
    """Bind every requested name before any caller validates, stages, or writes.

    Authorization is against the resolved physical target.  Existing hardlinks
    are refused because one pathname cannot identify every directory entry the
    inode would mutate, including aliases outside the authorized directories.
    """
    try:
        physical_root = root.resolve(strict=True)
    except OSError as exc:
        raise _path_denial("could not establish the physical project directory") from exc
    if not physical_root.is_dir():
        raise _path_denial("the project root is not a directory")
    scopes = _scope_roots(physical_root, allowed_dirs)

    pending: list[tuple[str, Path, bool, os.stat_result | None]] = []
    for requested in requested_paths:
        parts = _request_parts(requested)
        lexical = physical_root.joinpath(*parts)
        physical, exists, info = _physical_target(physical_root, lexical)
        if not _within(physical, physical_root):
            raise _path_denial(
                f"{requested!r} resolves outside the project to {physical}")
        if not any(_within(physical, scope) for scope in scopes):
            raise _path_denial(
                f"{requested!r} resolves outside the authorized working directories; "
                "the generator may not write rules, ledger or configuration")
        relative = physical.relative_to(physical_root)
        if relative.parts and relative.parts[0].startswith("."):
            raise _path_denial(f"refusing a hidden physical target: {requested!r}")
        if "TEMPLATE" in relative.parts:
            raise _path_denial(
                f"refusing to edit scaffold template {requested!r}; create a new "
                "increment directory instead")
        if exists:
            assert info is not None
            if not stat.S_ISREG(info.st_mode):
                raise _path_denial(
                    f"generated file target is not a regular file: {requested!r}")
            if info.st_nlink != 1:
                raise _path_denial(
                    f"refusing hardlinked file target with non-unique identity: {requested!r}")
        pending.append((requested, physical, exists, info))

    rules = _filesystem_rules(physical_root) if len(pending) > 1 else FilesystemRules(False, False)
    seen_inode: dict[tuple[int, int], str] = {}
    seen_namespace: dict[tuple[str, ...], str] = {}
    targets: list[FileTarget] = []
    for requested, physical, exists, info in pending:
        relative = physical.relative_to(physical_root).as_posix()
        if exists:
            assert info is not None
            inode_key = (info.st_dev, info.st_ino)
            previous = seen_inode.get(inode_key)
            if previous is not None:
                raise _path_denial(
                    f"refusing two generated paths for one physical file: "
                    f"{previous!r} and {requested!r}")
            seen_inode[inode_key] = requested
            device, inode = inode_key
        else:
            device = inode = None
        namespace_key = _namespace_key(relative, rules)
        previous = seen_namespace.get(namespace_key)
        if previous is not None:
            raise _path_denial(
                f"refusing filesystem-equivalent generated paths: "
                f"{previous!r} and {requested!r}")
        seen_namespace[namespace_key] = requested
        targets.append(FileTarget(requested, relative, physical, exists, device, inode))

    physical_paths = [target.physical for target in targets]
    for index, left in enumerate(physical_paths):
        for right in physical_paths[index + 1:]:
            if _within(left, right) or _within(right, left):
                raise _path_denial(
                    "refusing generated paths where one physical target contains another")
    return tuple(targets)
