"""`crossaudit pair` — creating the two repositories, and saying honestly what
that buys (DESIGN.md §6.2).

Two repositories are not about research. They are about privilege separation:
the generator cannot reach the rules it is judged by or the reports written
about it, and the auditor cannot reach the work's history. That separation is
what lets the ledger hold the two agents to account against *each other*, which
a single repository can never do.

This verb plans before it acts, always. `--plan` (the default) prints exactly
what would be created and changed; `--apply` does it. Nothing here writes to
anyone's account without that second word.

It also refuses to overstate what it achieved. Creating repositories and
uploading secrets produces the `paired` tier — privilege separation, history
out of unilateral control. It does not produce `enforced`: that needs an
independent, persistent controller consuming receipts atomically and an
admission check bound to a verified App, and until `doctor` can see both, the
honest word is "verified notification", not "enforced".
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..config import load
from ..app_keys import child_env
from ..errors import EXIT_CONFIG, EXIT_OK, ConfigDenial, RemediationAction as RA

TIERS = {
    "local": "one history, yours to rewrite: self-review, not accountability",
    "remote": "history out of unilateral control: you can be held to your own record",
    "paired": "privilege separation: the two agents can be held to account "
              "against each other",
    "enforced": "admission actually refused on a failed audit",
}

# External tools must never be allowed to freeze the desktop control plane.
# Authentication and identity checks run while rendering the Projects page, so
# keep those especially short.  Mutating network operations get a larger but
# still finite budget and run in a background job in the app.
GH_AUTH_TIMEOUT = 5
GH_IDENTITY_TIMEOUT = 10
GH_COMMAND_TIMEOUT = 120
GIT_COMMAND_TIMEOUT = 120


def _timed_out(tool: str, seconds: int) -> ConfigDenial:
    return ConfigDenial(
        f"{tool} did not respond within {seconds} seconds. Check the network or "
        "close any hidden sign-in prompt, then retry.",
        issue="command_timeout", action="retry", remediations=[RA.RETRY],
        url="https://www.githubstatus.com" if tool == "GitHub" else "")


def gh() -> str:
    bundled = os.environ.get("CROSSAUDIT_BUNDLED_GH", "").strip()
    path = bundled if bundled and Path(bundled).is_file() else shutil.which("gh")
    if not path:
        raise ConfigDenial(
            "pairing needs the GitHub CLI: install it from https://cli.github.com "
            "and run `gh auth login`. CrossAudit deliberately does not implement "
            "its own OAuth flow or handle your token",
            issue="github_cli", action="install_github_cli",
            remediations=[RA.INSTALL_GITHUB_CLI, RA.CONNECT_GITHUB],
            url="https://cli.github.com")
    try:
        proc = subprocess.run([path, "auth", "status"], capture_output=True,
                              text=True, timeout=GH_AUTH_TIMEOUT, env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_AUTH_TIMEOUT) from exc
    if proc.returncode != 0:
        raise ConfigDenial(
            "GitHub is not connected. Connect the account in CrossAudit and retry.",
            issue="github_auth", action="connect_github",
            remediations=[RA.CONNECT_GITHUB],
            url="https://github.com/login/device")
    return path


def _gh(*args: str, check: bool = True,
        timeout: int = GH_COMMAND_TIMEOUT) -> str:
    try:
        proc = subprocess.run([gh(), *args], capture_output=True, text=True,
                              timeout=timeout, env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", timeout) from exc
    if check and proc.returncode != 0:
        said = proc.stderr.strip()[:300]
        low = said.lower()
        hint = ""
        if "saml" in low or "sso" in low:
            hint = " Authorize GitHub CLI for the organisation's SSO, then retry."
            issue, action, url = ("github_sso", "open_github",
                                  "https://github.com/settings/applications")
            remedies = [RA.OPEN_GITHUB, RA.RETRY]
        elif "rate limit" in low:
            hint = " GitHub rate-limited this account; wait for the reset, then retry."
            issue, action, url = ("github_rate_limit", "retry",
                                  "https://www.githubstatus.com")
            remedies = [RA.RETRY]
        elif "resource not accessible" in low or "forbidden" in low or "403" in low:
            hint = " The connected account lacks repository or organisation permission."
            issue, action, url = ("github_permission", "open_github",
                                  "https://github.com/settings/repositories")
            remedies = [RA.OPEN_GITHUB]
        elif "already exists" in low:
            hint = " The name exists but may not be visible to this account; verify ownership."
            issue, action, url = ("repo_exists", "edit_repositories", "")
            remedies = [RA.EDIT_REPOSITORIES]
        else:
            issue, action, url = ("github_error", "retry", "")
            remedies = [RA.RETRY]
        raise ConfigDenial(f"gh {' '.join(args[:2])} failed: {said}.{hint}".rstrip(),
                           issue=issue, action=action, url=url, remediations=remedies)
    return proc.stdout.strip()


def _owner() -> str:
    return json.loads(_gh("api", "user", timeout=GH_IDENTITY_TIMEOUT))["login"]


def github_scopes() -> set[str]:
    """Read OAuth scope names from GitHub response headers without exposing the token."""
    try:
        proc = subprocess.run([gh(), "api", "-i", "user"], capture_output=True,
                              text=True, timeout=GH_IDENTITY_TIMEOUT, env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_IDENTITY_TIMEOUT) from exc
    if proc.returncode != 0:
        raise ConfigDenial(
            "GitHub could not verify authorization scopes: "
            f"{(proc.stderr or proc.stdout).strip()[:240]}",
            issue="github_auth", action="connect_github",
            remediations=[RA.CONNECT_GITHUB],
            url="https://github.com/login/device")
    match = re.search(r"(?im)^x-oauth-scopes:\s*(.*)$", proc.stdout)
    return ({scope.strip() for scope in match.group(1).split(",") if scope.strip()}
            if match else set())


def _exists(repo: str) -> bool:
    try:
        proc = subprocess.run([gh(), "repo", "view", repo], capture_output=True,
                              text=True, timeout=GH_IDENTITY_TIMEOUT, env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_IDENTITY_TIMEOUT) from exc
    if proc.returncode == 0:
        return True
    said = f"{proc.stdout}\n{proc.stderr}".casefold()
    if ("not found" in said or "could not resolve to a repository" in said or
            "could not resolve to a repo" in said):
        return False
    raise ConfigDenial(
        f"GitHub could not check {repo}: {(proc.stderr or proc.stdout).strip()[:240]}",
        issue="github_check", action="retry", remediations=[RA.RETRY])


def _git(root: Path, *args: str, check: bool = True) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                              text=True, timeout=GIT_COMMAND_TIMEOUT, env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
    if check and proc.returncode != 0:
        raise ConfigDenial(f"git {' '.join(args[:2])} failed: "
                           f"{proc.stderr.strip()[:240]}")
    return proc.stdout.strip()


def _github_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _normalise_remote(value: str) -> str:
    value = value.strip().removesuffix(".git")
    value = re.sub(r"^git@github\.com:", "https://github.com/", value)
    return value.rstrip("/").lower()


def _record_local_state_ignores(root: Path) -> None:
    path = root / ".gitignore"
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    entries = (".crossaudit/", ".crossaudit-home/", ".crossaudit-trash/")
    missing = [entry for entry in entries if entry not in current]
    if not missing:
        return
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n# CrossAudit's local state. The ledger is committed; this is not.\n"
                     + "\n".join(missing) + "\n")
    _git(root, "add", "--", ".gitignore")
    parents = _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if len(parents) >= 3:
        _git(root, "-c", "user.name=CrossAudit", "-c",
             "user.email=crossaudit@local.invalid", "commit", "-q", "--amend",
             "--no-edit")
    else:
        _git(root, "-c", "user.name=CrossAudit", "-c",
             "user.email=crossaudit@local.invalid", "commit", "-q", "-m",
             "crossaudit: ignore local state", "--", ".gitignore")


def _sync_existing_main(root: Path) -> None:
    """Bring an adopted remote main into the local history without discarding either side."""
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", "main"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT,
        env=child_env())
    if remote.returncode == 2:
        return  # An accessible but empty repository has no main branch yet.
    if remote.returncode != 0:
        raise ConfigDenial(
            "could not inspect the existing working repository main branch: "
            f"{(remote.stderr or remote.stdout).strip()[:240]}",
            issue="github_check", action="retry", remediations=[RA.RETRY])
    local_state = (".crossaudit/", ".crossaudit-home/", ".crossaudit-trash/")
    dirty = []
    for line in _git(root, "status", "--porcelain", check=False).splitlines():
        path = line[3:].split(" -> ")[-1]
        if any(path == prefix.rstrip("/") or path.startswith(prefix)
               for prefix in local_state):
            continue
        dirty.append(line)
    if dirty:
        raise ConfigDenial(
            "the local working repository has uncommitted changes; commit or stash "
            "them before adopting its remote history",
            issue="remote_history", action="retry", remediations=[RA.RETRY])
    _git(root, "fetch", "-q", "origin", "main")
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=str(root),
        capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT, env=child_env())
    if head.returncode != 0:
        _git(root, "checkout", "-q", "-B", "main", "origin/main")
        return
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT,
        env=child_env())
    if ancestor.returncode == 0:
        return
    merged = subprocess.run(
        ["git", "-c", "user.name=CrossAudit", "-c",
         "user.email=crossaudit@local.invalid", "merge", "--no-edit",
         "--allow-unrelated-histories", "-X", "theirs", "origin/main"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT,
        env=child_env())
    if merged.returncode == 0:
        _record_local_state_ignores(root)
        return
    subprocess.run(["git", "merge", "--abort"], cwd=str(root),
                   capture_output=True, text=True, timeout=GIT_COMMAND_TIMEOUT, env=child_env())
    raise ConfigDenial(
        "the local and remote working repository histories conflict; the merge was "
        "aborted without changing either history. Resolve the local files or choose "
        "a clean matching clone, then retry",
        issue="remote_history", action="retry", remediations=[RA.RETRY])


def _paired_config_body(cfg, science: str, audit: str) -> tuple[str, str]:
    """(current, paired) text of crossaudit.yml; equal when nothing would change.

    Edits the two lines in place so the person's comments survive."""
    current = cfg.path.read_text(encoding="utf-8")
    body, science_count = re.subn(r"(?m)^science_repo:\s*.*$",
                                  f"science_repo: {science}", current, count=1)
    body, audit_count = re.subn(r"(?m)^(?:#\s*)?audit_repo:\s*.*$",
                                f"audit_repo: {audit}", body, count=1)
    if not science_count:
        raise ConfigDenial("crossaudit.yml has no science_repo line to update")
    if not audit_count:
        body = body.replace(f"science_repo: {science}\n",
                            f"science_repo: {science}\naudit_repo: {audit}\n", 1)
    return current, body


def _write_pair_config(cfg, science: str, audit: str) -> None:
    """Persist the exact adopted repositories without flattening user comments."""
    _current, body = _paired_config_body(cfg, science, audit)
    tmp = cfg.path.with_suffix(".yml.tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    tmp.replace(cfg.path)


def _check_names(science: str, audit: str) -> None:
    if science == audit:
        raise ConfigDenial("science and audit repositories must be different")
    for label, repo in (("science", science), ("audit", audit)):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ConfigDenial(f"{label} repository must be owner/name, got {repo!r}")


# ------------------------------------------------------------------ the steps
#
# D173. The plan used to be a hand-written list beside the code that applied
# it, and the two drifted: `--apply` pushed the local history, committed the
# pair and added an `origin` remote, none of which the plan named, while the
# plan's branch-protection step was never applied. Now there is one table.
# `steps()` returns it; `cmd_pair` prints it and `apply_pair` runs it, in the
# same order, and what `--apply` does not do is a separate list, `afterwards()`.

@dataclass(frozen=True)
class Step:
    """One thing `--apply` does, and what the plan says about it.

    `ops` names every command the step may run that changes something — a
    GitHub call, a commit, a remote, a push — as an argv whose first word is
    the tool. `when` is empty for a step that always runs its commands, and
    otherwise names the one case in which it does (the rest of the time it
    runs none of them)."""
    stage: str
    says: str
    why: str
    ops: tuple[tuple[str, ...], ...]
    run: Callable[["_Pairing"], None]
    when: str = ""


@dataclass
class _Pairing:
    cfg: Any
    science: str
    audit: str
    private: bool
    allow_existing: bool
    tell: Callable[[str, str], None]
    created: list = field(default_factory=list)
    adopted: set = field(default_factory=set)
    secret_uploaded: bool = False


def _staging(cfg) -> Path:
    return cfg.root / cfg.state_dir / "pair-staging"


def _create_or_adopt(repo: str, visibility: str) -> Callable[[_Pairing], None]:
    def run(p: _Pairing) -> None:
        if _exists(repo):
            if not p.allow_existing:
                raise ConfigDenial(
                    f"repository {repo} already exists; edit the name or explicitly "
                    "allow CrossAudit to use repositories you can access",
                    issue="repo_exists", action="edit_repositories",
                    remediations=[RA.EDIT_REPOSITORIES], repositories=[repo])
            p.adopted.add(repo)
            p.tell("github", f"Adopting existing {repo}")
        else:
            _gh("repo", "create", repo, visibility)
            p.created.append(repo)
            p.tell("github", f"Created {repo}")
    return run


def _record_pair(p: _Pairing) -> None:
    # The repository identities are part of the governed project, so publish
    # them in the science history rather than leaving a local-only config edit.
    cfg = p.cfg
    config_rel = cfg.path.relative_to(cfg.root).as_posix()
    _write_pair_config(cfg, p.science, p.audit)
    _git(cfg.root, "add", "--", config_rel)
    try:
        pending = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", config_rel],
            cwd=str(cfg.root), timeout=GIT_COMMAND_TIMEOUT, env=child_env()).returncode
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
    if pending == 1:
        _git(cfg.root, "commit", "-q", "-m", "crossaudit: record repository pair",
             "--", config_rel)
    elif pending != 0:
        raise ConfigDenial("could not inspect the repository configuration change")
    p.tell("config", f"Recorded the repository pair in {config_rel}")


def _add_origin(p: _Pairing) -> None:
    _git(p.cfg.root, "remote", "add", "origin", _github_url(p.science))
    p.tell("science", f"Added origin {_github_url(p.science)}")


def _sync(p: _Pairing) -> None:
    if p.science in p.adopted:
        p.tell("github", f"Synchronizing existing history from {p.science}")
        _sync_existing_main(p.cfg.root)


def _push(p: _Pairing) -> None:
    _git(p.cfg.root, "push", "-u", "origin", "HEAD:main")
    p.tell("science", f"Pushed the local project to {p.science}")


def _identity(repo: Path) -> list[str]:
    """`-c` options naming CrossAudit only where the repository names nobody,
    so a configured identity is kept and no config file is written."""
    out = []
    if not _git(repo, "config", "user.name", check=False):
        out += ["-c", "user.name=CrossAudit"]
    if not _git(repo, "config", "user.email", check=False):
        out += ["-c", "user.email=crossaudit@local.invalid"]
    return out


def _seed(p: _Pairing) -> None:
    cfg = p.cfg
    const = cfg.root / cfg.constitution
    staging = _staging(cfg)
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        _gh("repo", "clone", p.audit, str(staging), "--", "-q")
        shutil.copyfile(const, staging / const.name)
        (staging / "cycles").mkdir(exist_ok=True)
        (staging / "cycles" / "README.md").write_text(
            "# Ledger\n\nOne directory per audit cycle: the report, the deterministic\n"
            "check output, and the receipt that binds them to a commit. Append-only:\n"
            "a re-audit adds an attempt, it never rewrites one.\n",
            encoding="utf-8", newline="\n")
        _git(staging, "add", "-A")
        try:
            pending = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                     cwd=str(staging),
                                     timeout=GIT_COMMAND_TIMEOUT, env=child_env()).returncode
        except subprocess.TimeoutExpired as exc:
            raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
        if pending == 1:
            _git(staging, *_identity(staging), "commit", "-q", "-m",
                 "seed: constitution and ledger")
            _git(staging, "push", "-q", "origin", "HEAD:main")
        elif pending != 0:
            raise ConfigDenial("could not inspect the audit repository staging area")
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    p.tell("audit", f"Seeded {p.audit} with the Constitution and ledger")


def _secret(p: _Pairing) -> None:
    cfg = p.cfg
    key = os.environ.get(cfg.auditor.key_env, "").strip()
    if not key:
        return  # loaded when the steps were drawn up, gone now: upload nothing
    try:
        proc = subprocess.run([gh(), "secret", "set", cfg.auditor.key_env,
                              "--repo", p.audit], input=key, text=True,
                              capture_output=True, timeout=GH_COMMAND_TIMEOUT,
                              env=child_env())
    except subprocess.TimeoutExpired as exc:
        raise _timed_out("GitHub", GH_COMMAND_TIMEOUT) from exc
    if proc.returncode != 0:
        raise ConfigDenial(f"could not upload {cfg.auditor.key_env}: "
                           f"{proc.stderr.strip()[:240]}",
                           issue="github_secret_permission",
                           action="open_github", remediations=[RA.OPEN_GITHUB],
                           url=f"https://github.com/{p.audit}/settings/secrets/actions")
    p.secret_uploaded = True
    p.tell("secret", f"Uploaded {cfg.auditor.key_env} to the audit repository")


def steps(cfg, science: str, audit: str, *, private: bool) -> list[Step]:
    """Everything `--apply` does, in the order it does it.

    Read only from local state (the config file, the `origin` remote, the
    environment), so the plan needs no network and no GitHub sign-in."""
    vis = "--private" if private else "--public"
    config_rel = cfg.path.relative_to(cfg.root).as_posix()
    staging = str(_staging(cfg))
    key_env = cfg.auditor.key_env
    out = [
        Step("github", f"Create {science} on GitHub",
             "the work and its history",
             (("gh", "repo", "create", science, vis),),
             _create_or_adopt(science, vis),
             when=f"{science} does not exist yet (one this account can see is "
                  "adopted instead)"),
        Step("github", f"Create {audit} on GitHub",
             "the rules and every report: the generator has no write path here",
             (("gh", "repo", "create", audit, vis),),
             _create_or_adopt(audit, vis),
             when=f"{audit} does not exist yet (one this account can see is "
                  "adopted instead)"),
    ]
    current, paired = _paired_config_body(cfg, science, audit)
    if paired != current:
        out.append(Step(
            "config", f"Commit the repository pair to {config_rel} (a local commit)",
            "the pair is part of the governed project, so it travels with the history",
            (("git", "add", "--", config_rel),
             ("git", "commit", "-q", "-m", "crossaudit: record repository pair",
              "--", config_rel)),
            _record_pair))
    if not _git(cfg.root, "config", "--get", "remote.origin.url", check=False):
        out.append(Step(
            "science", f"Add the local remote origin -> {_github_url(science)}",
            "where the work's history is pushed",
            (("git", "remote", "add", "origin", _github_url(science)),),
            _add_origin))
    out += [
        Step("github", f"Merge the existing main of {science} into the local history",
             "an adopted repository's history is kept, never overwritten",
             (("git", "fetch", "-q", "origin", "main"),
              ("git", "checkout", "-q", "-B", "main", "origin/main"),
              ("git", "merge", "--no-edit", "--allow-unrelated-histories",
               "-X", "theirs", "origin/main"),
              ("git", "merge", "--abort"),
              ("git", "add", "--", ".gitignore"),
              ("git", "commit", "-q", "--amend", "--no-edit"),
              ("git", "commit", "-q", "-m", "crossaudit: ignore local state",
               "--", ".gitignore")),
             _sync,
             when=f"{science} already existed with a main branch the local history "
                  "does not contain (an aborted merge changes nothing)"),
        Step("science", f"Push the local history (every commit on HEAD) to {science} "
             "as main",
             "the work's record leaves your sole control",
             (("git", "push", "-u", "origin", "HEAD:main"),),
             _push),
        Step("audit", f"Seed {audit} with {cfg.constitution} and cycles/README.md",
             "the Constitution lives where the audited party cannot edit it; the "
             "temporary clone is deleted afterwards",
             (("gh", "repo", "clone", audit, staging, "--", "-q"),
              ("git", "add", "-A"),
              ("git", "commit", "-q", "-m", "seed: constitution and ledger"),
              ("git", "push", "-q", "origin", "HEAD:main")),
             _seed,
             when=f"{audit} does not hold these files yet, for the commit and "
                  "push (the clone always runs)"),
    ]
    if os.environ.get(key_env, "").strip():
        out.append(Step(
            "secret", f"Upload ${key_env} as a secret of {audit}",
            "the auditor's key, readable only by the audit side",
            (("gh", "secret", "set", key_env, "--repo", audit),),
            _secret))
    return out


def afterwards(cfg, science: str, audit: str) -> list[tuple[str, tuple[str, ...]]]:
    """What `--apply` does NOT do, as (sentence, commands) for the person."""
    key_env = cfg.auditor.key_env
    rows: list[tuple[str, tuple[str, ...]]] = []
    if not os.environ.get(key_env, "").strip():
        rows.append((f"upload the auditor key: ${key_env} is not loaded here, so "
                     "--apply skips it",
                     (f"gh secret set {key_env} --repo {audit}",)))
    rows.append((
        "branch protection: make admission a required check. It needs admin "
        "rights and, on private repositories, a paid plan on some tiers",
        (f"gh api repos/{science}/branches/main/protection -X PUT \\",
         "  -f 'required_status_checks[strict]=true' \\",
         "  -f 'required_status_checks[contexts][]=crossaudit/admission'")))
    rows.append(("read the rules that actually exist and the tier you are really "
                 "at; plan text is not evidence",
                 ("crossaudit doctor --online",)))
    return rows


def show(argv: tuple[str, ...], root: Path) -> str:
    """A step's command as a person would type it, paths under the project
    shown relative to it."""
    prefix = str(root).rstrip(os.sep) + os.sep
    words = [w[len(prefix):] if w.startswith(prefix) else w for w in argv]
    return shlex.join(words)


def plan_lines(cfg, science: str, audit: str, *, private: bool,
               todo: list[Step] | None = None) -> tuple[list[str], list[str]]:
    """(the steps `--apply` performs, what you do afterwards) as printable
    lines. The `$ ` lines are exactly the commands, in order."""
    todo = steps(cfg, science, audit, private=private) if todo is None else todo
    does: list[str] = []
    for i, step in enumerate(todo, 1):
        does.append(f"{i}. {step.says}")
        does.append(f"   {step.why}")
        if step.when:
            does.append(f"   only if: {step.when}")
        does += [f"   $ {show(op, cfg.root)}" for op in step.ops]
    after: list[str] = []
    for sentence, commands in afterwards(cfg, science, audit):
        after.append(f"- {sentence}")
        after += [f"  $ {line}" if not line.startswith("  ") else f"    {line.strip()}"
                  for line in commands]
    return does, after


def apply_pair(cfg, science: str, audit: str, *, private: bool,
               progress=None, allow_existing: bool = True,
               on_step=None) -> dict:
    """Create, connect and seed the two repositories, checking every mutation.

    This is shared by the CLI and the browser project wizard.  It runs the
    list `steps()` returns, in order, and nothing else that changes anything
    (D173). It is idempotent: an existing repository is adopted, but an
    unrelated local ``origin`` is never overwritten. ``on_step(i, n, step)``
    is called as each step begins.
    """
    tell = progress or (lambda _stage, _detail: None)
    _check_names(science, audit)

    const = cfg.root / cfg.constitution
    if not const.is_file():
        raise ConfigDenial(f"no Constitution at {const}; run `crossaudit init` first")

    expected = _github_url(science)
    current = _git(cfg.root, "config", "--get", "remote.origin.url", check=False)
    if current and _normalise_remote(current) != _normalise_remote(expected):
        raise ConfigDenial(
            f"local origin is {current}, not {expected}; refusing to replace it",
            issue="origin_conflict", action="edit_repositories", remediations=[RA.EDIT_REPOSITORIES])
    config_rel = cfg.path.relative_to(cfg.root).as_posix()
    for staged in (False, True):
        args = ["git", "diff"]
        if staged:
            args.append("--cached")
        args.extend(["--quiet", "--", config_rel])
        try:
            clean = subprocess.run(args, cwd=str(cfg.root),
                                   timeout=GIT_COMMAND_TIMEOUT, env=child_env()).returncode
        except subprocess.TimeoutExpired as exc:
            raise _timed_out("Git", GIT_COMMAND_TIMEOUT) from exc
        if clean != 0:
            where = "staged " if staged else ""
            raise ConfigDenial(
                f"{config_rel} has {where}changes; commit or restore them before pairing")

    gh()  # all local preflights passed; remote mutations may now begin
    tell("github", "GitHub authentication verified")
    todo = steps(cfg, science, audit, private=private)
    state = _Pairing(cfg, science, audit, private, allow_existing, tell)
    for i, step in enumerate(todo, 1):
        if on_step:
            on_step(i, len(todo), step)
        step.run(state)
    if not state.secret_uploaded:
        tell("secret", f"{cfg.auditor.key_env} is not loaded; secret upload skipped")

    tell("config", "Saved the exact repository pair in crossaudit.yml")
    return {"science": science, "audit": audit, "created": state.created,
            "secret_uploaded": state.secret_uploaded,
            "tier": "paired", "branch_protection": "manual"}


def cmd_pair(args) -> int:
    cfg = load()
    owner = _owner()
    science = args.science or f"{owner}/{cfg.root.name}"
    audit = args.audit or f"{science}-audit"
    private = not args.public
    _check_names(science, audit)

    print("\nCrossAudit — pairing the repositories")
    print("=" * 66)
    print(f"  science  {science}")
    print(f"  audit    {audit}")
    print(f"  buys     {TIERS['paired']}")
    print(f"  not      {TIERS['enforced']} — that needs a controller and an App")
    print()

    todo = steps(cfg, science, audit, private=private)
    does, after = plan_lines(cfg, science, audit, private=private, todo=todo)
    print("  --apply does exactly this, in this order:")
    for line in does:
        print(f"  {line}")
    print("\n  You do afterwards (--apply does not do these):")
    for line in after:
        print(f"  {line}")

    if not args.apply:
        print("\n  This was a plan; nothing was created or changed. Run again with --apply.")
        return EXIT_OK

    print("\n  Applying…")
    result = apply_pair(
        cfg, science, audit, private=private,
        progress=lambda _stage, detail: print(f"  · {detail}"),
        on_step=lambda i, n, step: print(f"  [{i}/{n}] {step.says}"))

    print(f"\n  Done: {result['science']} and {result['audit']} are paired. The steps "
          "under \"You do afterwards\" above are still yours.")
    return EXIT_OK
