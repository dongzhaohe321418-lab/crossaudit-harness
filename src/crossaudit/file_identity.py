"""Canonical identity and authorization for Generator-owned file writes.

The model supplies names, but names are not filesystem identities.  This module
is the single boundary that follows existing links, recovers the filesystem's
actual spelling, authorizes the resulting physical target, and rejects a reply
whose names converge on one target.  Callers retain the returned binding through
validation, application, and Git staging; they never reconstruct a target from
the model's string.

Authorization-boundary change contract (D18/D19): REVIEWER: claude; AUDIT:
independent auditor.  Resolution, parent creation, replacement, rollback, and
staging share one physical binding.  Normal/injected failure is all-or-nothing
for a round; cross-file power-loss atomicity is not claimed.  The executable
enumeration crosses one/many files, existing/new targets, existing/missing
parents, and failure before every replacement plus success.  Existing identity
tests separately enumerate symlink, hardlink, lexical/case/Unicode aliases,
scope escape, trailing-space names, and bind/apply races.  Arbitrary kernel or
hardware failure modes and hostile replacement after the exact-byte index write
are not exhaustively enumerable; the latter cannot put replacement bytes in the
index because staging never reopens the pathname.

Receipt-scope change contract (D24): REVIEWER: claude; AUDIT: independent
auditor.  Closure is by construction, not enumeration: the same AppliedFiles
object carries the prepared payload's open-file identity through physical
publication, exact-byte staging, and commit.  It retains the prior tracked
stage entries for the round's paths as well as the filesystem backups; every
scope exit rolls both back unless successful commit explicitly calls
finalize().  Document export transfers its derived binding into that same
object rather than returning a second unguarded lifecycle.
Enumerated tests cover failure after apply, after stage, and immediately before
commit; absent/present prior index entries; source-to-derived export transfer;
explicit success; and the historical implicit-accept guard mutation.  They do
not claim process-crash or power-loss rollback: Git and filesystem durability
remain their respective recovery domains after abrupt process death.
"""
from __future__ import annotations

import os
import secrets
import stat
import tempfile
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

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


@dataclass(frozen=True)
class AppliedFile:
    """Exact authorized bytes to stage for one physical target."""

    target: FileTarget
    payload: bytes
    git_mode: str

    @property
    def relative(self) -> str:
        return self.target.relative


@dataclass
class _PreparedFile:
    target: FileTarget
    payload: bytes
    git_mode: str
    parent_fd: int
    payload_name: str | None
    backup_fd: int | None
    payload_identity: tuple[int, int]
    applied_identity: tuple[int, int] | None = None


@dataclass
class _CreatedDirectory:
    parent_fd: int
    name: str


class AppliedFiles(Sequence[str]):
    """A live authorization receipt spanning apply, staging, and commit.

    The sequence interface is intentionally read-only and preserves the old
    list-like consumer contract.  Security-sensitive consumers use ``entries``
    instead: it carries the physical binding and exact bytes, so reducing this
    object to path strings is an explicit loss of authority rather than an
    accidental one.
    """

    def __init__(self, prepared: list[_PreparedFile],
                 created: list[_CreatedDirectory], *, root: Path,
                 allowed_dirs: list[str] | None) -> None:
        self._prepared = prepared
        self._created = created
        self.root = root
        self.allowed_dirs = (tuple(allowed_dirs)
                             if allowed_dirs is not None else None)
        self._index_rollback: Callable[[], None] | None = None
        self._active = True

    def __enter__(self) -> "AppliedFiles":
        if not self._active:
            raise _path_denial("generated file authorization receipt is no longer active")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> bool:
        # finalize() is the sole success signal.  Every exception, return,
        # continue, and break that leaves an active scope restores both the
        # index and filesystem through the retained authorization.
        if self._active:
            self.rollback()
        return False

    def register_index_rollback(self, restore: Callable[[], None]) -> None:
        """Attach restoration of prior tracked stage entries to this receipt."""
        if not self._active or self._index_rollback is not None:
            raise _path_denial("generated file staging receipt is not available")
        self._index_rollback = restore

    def replace_with(self, replacement: "AppliedFiles") -> "AppliedFiles":
        """Transfer a derived artifact's bindings into this same live scope.

        Document export replaces its temporary source with a derived binary.
        The caller's context manager continues to guard this object, so the new
        receipt must not escape through a different Python object.
        """
        if replacement is self:
            return self
        if (not self._active or not replacement._active
                or self.root != replacement.root
                or self.allowed_dirs != replacement.allowed_dirs):
            raise _path_denial("cannot transfer a generated file authorization receipt")
        self.rollback()
        self._prepared = replacement._prepared
        self._created = replacement._created
        self.root = replacement.root
        self.allowed_dirs = replacement.allowed_dirs
        self._index_rollback = replacement._index_rollback
        self._active = True
        replacement._prepared = []
        replacement._created = []
        replacement._index_rollback = None
        replacement._active = False
        return self

    @property
    def entries(self) -> tuple[AppliedFile, ...]:
        return tuple(AppliedFile(row.target, row.payload, row.git_mode)
                     for row in self._prepared)

    def __len__(self) -> int:
        return len(self._prepared)

    def __getitem__(self, index):
        paths = [row.target.relative for row in self._prepared]
        return paths[index]

    def __iter__(self) -> Iterator[str]:
        return iter(row.target.relative for row in self._prepared)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sequence) and not isinstance(other, (str, bytes)):
            return list(self) == list(other)
        return False

    def verify(self) -> None:
        """Refuse if a pathname stopped naming the file this round installed."""
        if not self._active:
            raise _path_denial("generated file authorization receipt is no longer active")
        for row in self._prepared:
            try:
                info = os.stat(row.target.physical.name, dir_fd=row.parent_fd,
                               follow_symlinks=False)
            except OSError as exc:
                raise _path_denial(
                    f"generated file identity changed before staging: "
                    f"{row.target.relative!r}") from exc
            if ((info.st_dev, info.st_ino) != row.applied_identity
                    or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                raise _path_denial(
                    f"generated file identity changed before staging: "
                    f"{row.target.relative!r}")

    def rollback(self) -> None:
        """Restore the entire pre-round filesystem state through pinned fds."""
        if not self._active:
            return
        errors: list[Exception] = []
        if self._index_rollback is not None:
            try:
                self._index_rollback()
            except Exception as exc:
                errors.append(exc)
            self._index_rollback = None
        for row in reversed(self._prepared):
            try:
                if row.applied_identity is not None:
                    if row.backup_fd is None:
                        try:
                            os.unlink(row.target.physical.name, dir_fd=row.parent_fd)
                        except FileNotFoundError:
                            pass
                    else:
                        restore_name, restore_fd = _temporary_name(
                            row.parent_fd, "restore")
                        try:
                            try:
                                backup_info = os.fstat(row.backup_fd)
                                os.fchmod(
                                    restore_fd, stat.S_IMODE(backup_info.st_mode))
                                os.lseek(row.backup_fd, 0, os.SEEK_SET)
                                _copy_to_backup(row.backup_fd, restore_fd)
                                os.fsync(restore_fd)
                            finally:
                                os.close(restore_fd)
                            os.replace(restore_name, row.target.physical.name,
                                       src_dir_fd=row.parent_fd,
                                       dst_dir_fd=row.parent_fd)
                        finally:
                            try:
                                os.unlink(restore_name, dir_fd=row.parent_fd)
                            except FileNotFoundError:
                                pass
                    os.fsync(row.parent_fd)
                if row.payload_name is not None:
                    try:
                        os.unlink(row.payload_name, dir_fd=row.parent_fd)
                    except FileNotFoundError:
                        pass
                row.payload_name = None
            except OSError as exc:
                errors.append(exc)
        self._remove_created_directories(errors)
        self._close()
        if errors:
            from .errors import IntegrityDenial
            raise IntegrityDenial(
                "could not restore the complete pre-round filesystem state") from errors[0]

    def finalize(self) -> None:
        """Accept the applied round and remove its rollback material."""
        if not self._active:
            return
        errors: list[OSError] = []
        for row in self._prepared:
            for name in (row.payload_name,):
                if name is None:
                    continue
                try:
                    os.unlink(name, dir_fd=row.parent_fd)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    errors.append(exc)
            row.payload_name = None
        self._close()
        if errors:
            from .errors import IntegrityDenial
            raise IntegrityDenial(
                "could not remove generated round transaction material") from errors[0]

    def _remove_created_directories(self, errors: list[Exception]) -> None:
        for created in reversed(self._created):
            try:
                os.rmdir(created.name, dir_fd=created.parent_fd)
            except FileNotFoundError:
                pass
            except OSError as exc:
                errors.append(exc)

    def _close(self) -> None:
        for row in self._prepared:
            if row.backup_fd is not None:
                try:
                    os.close(row.backup_fd)
                except OSError:
                    pass
                row.backup_fd = None
            try:
                os.close(row.parent_fd)
            except OSError:
                pass
        for created in self._created:
            try:
                os.close(created.parent_fd)
            except OSError:
                pass
        self._index_rollback = None
        self._active = False

    def __del__(self) -> None:
        # Abandonment is failure, never implicit acceptance.  __exit__ is the
        # deterministic guard; this is the fail-closed last resort for callers
        # that neglect the context-manager contract.
        try:
            self.rollback()
        except Exception:
            pass


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


_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _same_binding(left: FileTarget, right: FileTarget) -> bool:
    return (left.requested, left.relative, left.physical, left.exists,
            left.device, left.inode) == (
                right.requested, right.relative, right.physical, right.exists,
                right.device, right.inode)


def _open_directory(name: str | Path, *, dir_fd: int | None = None) -> int:
    """Open one directory identity without following its final component."""
    return os.open(name, _DIRECTORY_FLAGS | _NOFOLLOW, dir_fd=dir_fd)


def _walk_parent(root_fd: int, relative: str, *, create: bool,
                 created: list[_CreatedDirectory]) -> int:
    """Open a target's parent component-by-component from the pinned root."""
    current = os.dup(root_fd)
    try:
        for part in PurePosixPath(relative).parts[:-1]:
            try:
                child = _open_directory(part, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    return current
                try:
                    os.mkdir(part, 0o777, dir_fd=current)
                    created.append(_CreatedDirectory(os.dup(current), part))
                except FileExistsError:
                    # A concurrent creator gets no trust: the no-follow open
                    # below must still prove it installed a directory.
                    pass
                child = _open_directory(part, dir_fd=current)
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise


def _preflight_parent(root_fd: int, relative: str) -> None:
    """Establish every existing ancestor before any directory is created."""
    current = os.dup(root_fd)
    try:
        for part in PurePosixPath(relative).parts[:-1]:
            try:
                child = _open_directory(part, dir_fd=current)
            except FileNotFoundError:
                return
            os.close(current)
            current = child
    finally:
        os.close(current)


def _temporary_name(parent_fd: int, purpose: str,
                    mode: int = 0o600) -> tuple[str, int]:
    for _ in range(128):
        name = f".crossaudit-{purpose}-{secrets.token_hex(12)}"
        try:
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                         mode, dir_fd=parent_fd)
            return name, fd
        except FileExistsError:
            continue
    raise OSError("could not allocate a unique round transaction file")


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        count = os.write(fd, payload[offset:])
        if count <= 0:
            raise OSError("generated file write made no progress")
        offset += count


def _copy_to_backup(source_fd: int, backup_fd: int) -> None:
    while True:
        chunk = os.read(source_fd, 1024 * 1024)
        if not chunk:
            return
        _write_all(backup_fd, chunk)


def _prepare_target(target: FileTarget, payload: bytes,
                    parent_fd: int) -> _PreparedFile:
    """Snapshot one old target and prepare replacement bytes without publishing."""
    name = target.physical.name
    backup_name: str | None = None
    retained_backup_fd: int | None = None
    payload_name: str | None = None
    try:
        if target.exists:
            source_fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent_fd)
            try:
                info = os.fstat(source_fd)
                if ((info.st_dev, info.st_ino) != (target.device, target.inode)
                        or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                    raise _path_denial(
                        f"refusing a generated file that changed during apply: "
                        f"{target.relative!r}")
                backup_name, backup_fd = _temporary_name(parent_fd, "rollback")
                try:
                    os.fchmod(backup_fd, stat.S_IMODE(info.st_mode))
                    _copy_to_backup(source_fd, backup_fd)
                    os.fsync(backup_fd)
                    os.lseek(backup_fd, 0, os.SEEK_SET)
                    os.unlink(backup_name, dir_fd=parent_fd)
                    backup_name = None
                    retained_backup_fd = backup_fd
                except Exception:
                    os.close(backup_fd)
                    raise
                mode = stat.S_IMODE(info.st_mode)
            finally:
                os.close(source_fd)
        else:
            try:
                os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise _path_denial(
                    f"refusing a generated file created after authorization: "
                    f"{target.relative!r}")
            mode = 0o666

        payload_name, payload_fd = _temporary_name(
            parent_fd, "payload", 0o600 if target.exists else 0o666)
        try:
            if target.exists:
                os.fchmod(payload_fd, mode)
            _write_all(payload_fd, payload)
            os.fsync(payload_fd)
            payload_info = os.fstat(payload_fd)
            installed_mode = stat.S_IMODE(payload_info.st_mode)
            payload_identity = (payload_info.st_dev, payload_info.st_ino)
        finally:
            os.close(payload_fd)
        git_mode = "100755" if installed_mode & 0o111 else "100644"
        return _PreparedFile(target, payload, git_mode, parent_fd,
                             payload_name, retained_backup_fd, payload_identity)
    except Exception:
        for temporary in (payload_name, backup_name):
            if temporary is None:
                continue
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except OSError:
                pass
        if retained_backup_fd is not None:
            try:
                os.close(retained_backup_fd)
            except OSError:
                pass
        raise


def _target_still_original(row: _PreparedFile) -> bool:
    name = row.target.physical.name
    try:
        info = os.stat(name, dir_fd=row.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return not row.target.exists
    if not row.target.exists:
        return False
    return ((info.st_dev, info.st_ino) == (row.target.device, row.target.inode)
            and stat.S_ISREG(info.st_mode) and info.st_nlink == 1)


def _replace_prepared(row: _PreparedFile) -> None:
    """Publish one already-prepared payload through its pinned parent."""
    assert row.payload_name is not None
    os.replace(row.payload_name, row.target.physical.name,
               src_dir_fd=row.parent_fd, dst_dir_fd=row.parent_fd)
    row.payload_name = None
    row.applied_identity = row.payload_identity
    os.fsync(row.parent_fd)


def apply_bound_files(root: Path, targets: tuple[FileTarget, ...],
                      payloads: dict[str, bytes],
                      allowed_dirs: list[str] | None) -> AppliedFiles:
    """Apply one authorized file round as a rollback-capable transaction.

    Enumeration of the construction: existing/new targets, existing/missing
    parent chains, one/many targets, and failures before/during/after the first
    replacement all use the same prepare-then-publish path.  Symlink, hardlink,
    namespace-alias and scope dimensions remain owned by
    :func:`resolve_file_targets`.  Process crash/power-loss atomicity across
    several filesystem objects is not claimed; normal and injected exceptions
    are all-or-nothing.
    """
    physical_root = root.resolve(strict=True)
    rebound = resolve_file_targets(
        physical_root, (target.requested for target in targets), allowed_dirs)
    if len(rebound) != len(targets) or any(
            not _same_binding(before, after)
            for before, after in zip(targets, rebound)):
        raise _path_denial(
            "refusing generated files whose physical identity changed before apply")
    if set(payloads) != {target.relative for target in targets}:
        raise _path_denial("generated payloads do not match their authorized targets")

    root_fd = _open_directory(physical_root)
    prepared: list[_PreparedFile] = []
    created: list[_CreatedDirectory] = []
    unowned_parent_fds: set[int] = set()
    receipt: AppliedFiles | None = None
    try:
        root_info = os.fstat(root_fd)
        expected_root = physical_root.stat()
        if ((root_info.st_dev, root_info.st_ino)
                != (expected_root.st_dev, expected_root.st_ino)):
            raise _path_denial("the physical project directory changed before apply")

        # This pass has no filesystem mutation.  Every existing component for
        # every target must be a no-follow directory before mkdir is possible.
        for target in targets:
            _preflight_parent(root_fd, target.relative)

        # Creation is relative to the pinned root and every opened component is
        # no-follow.  A swapped lexical ancestor is never traversed.
        parent_fds: list[tuple[FileTarget, int]] = []
        for target in sorted(targets, key=lambda item: item.relative):
            parent_fd = _walk_parent(root_fd, target.relative, create=True,
                                     created=created)
            parent_fds.append((target, parent_fd))
            unowned_parent_fds.add(parent_fd)
        for target, parent_fd in parent_fds:
            row = _prepare_target(target, payloads[target.relative], parent_fd)
            prepared.append(row)
            unowned_parent_fds.discard(parent_fd)

        receipt = AppliedFiles(prepared, created, root=physical_root,
                               allowed_dirs=allowed_dirs)
        for row in prepared:
            if not _target_still_original(row):
                raise _path_denial(
                    f"refusing a generated file that changed before publish: "
                    f"{row.target.relative!r}")
            _replace_prepared(row)
        return receipt
    except ProviderDenial:
        if receipt is None:
            receipt = AppliedFiles(prepared, created, root=physical_root,
                                   allowed_dirs=allowed_dirs)
        receipt.rollback()
        raise
    except OSError as exc:
        if receipt is None:
            receipt = AppliedFiles(prepared, created, root=physical_root,
                                   allowed_dirs=allowed_dirs)
        receipt.rollback()
        raise _path_denial("could not atomically apply the generated file round") from exc
    finally:
        for parent_fd in unowned_parent_fds:
            try:
                os.close(parent_fd)
            except OSError:
                pass
        os.close(root_fd)


def apply_file_payloads(root: Path, payloads: dict[str, bytes],
                        allowed_dirs: list[str] | None) -> AppliedFiles:
    """Resolve, authorize, and transactionally apply an exact byte mapping."""
    targets = resolve_file_targets(root, payloads, allowed_dirs)
    return apply_bound_files(root, targets, payloads, allowed_dirs)
