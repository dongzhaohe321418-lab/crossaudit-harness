"""CrossAudit V4 macOS application core.

The Swift shell owns the native window. This process owns the loopback server,
Git ledger, providers, and project workers. It prints exactly one tokenised URL
for the shell, then remains in the foreground until the application exits.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .app_keys import load_into_environment
from .config import CONFIG_NAME, load
from .console import daemon, serve
from .console.server import PROJECT_IDLE_TIMEOUT_S
from .dcl import describe as describe_checks
from .errors import ConfigDenial, Denial
from .scaffold import CONFIG_TEMPLATE, GENERAL_CHECKS, read
from .workspace import configured_workspace


_CORE_USAGE = f"""usage: CrossAuditCore [MODE]

CrossAudit's frozen application core.

With no arguments, start the desktop application.
  --project-console DIRECTORY [PORT]  serve one configured project
  --self-test                         verify the frozen runtime
  --version                           print CrossAudit's version
  --help                              show this help
"""


def app_support() -> Path:
    override = os.environ.get("CROSSAUDIT_APP_SUPPORT", "").strip()
    return (Path(override).expanduser() if override else
            Path.home() / "Library" / "Application Support" / "CrossAudit")


def workspace_root(support: Path | None = None) -> Path:
    return configured_workspace(support or app_support())


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _controller_project(workspace: Path) -> Path:
    """Create the hidden controller, even when Git still needs installation.

    The Settings/Doctor UI must be reachable precisely when a prerequisite is
    broken.  Configuration files therefore come first; Git initialization is a
    best-effort final step that Doctor can safely complete after the user has
    installed Apple's Command Line Tools.
    """
    root = workspace / ".crossaudit-home"
    config = root / CONFIG_NAME
    if config.is_file():
        return root
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(
        ".crossaudit/\n*.env\n.DS_Store\n", encoding="utf-8", newline="\n")
    (root / "AUDIT_RULES.md").write_text(
        read("GENERAL_AUDIT_RULES.md"), encoding="utf-8", newline="\n")
    body = CONFIG_TEMPLATE.format(
        science_repo="CrossAudit-Home", audit_repo_line="# audit_repo: (local ledger)",
        constitution="AUDIT_RULES.md", max_rounds=3,
        auditor_vendor="openai", auditor_provider="openai_compat",
        auditor_model="gpt-5.6-sol", base_url_line="",
        generator_vendor="anthropic",
        generator_details=("  provider: anthropic\n  model: claude-sonnet-4-6\n"
                           "  key_env: CROSSAUDIT_ANTHROPIC_KEY"),
        permissive_minimum="false", state_dir=".crossaudit",
        scope_dirs="work", checks=", ".join(GENERAL_CHECKS))
    body = body.replace("key_env: CROSSAUDIT_AUDITOR_KEY",
                        "key_env: CROSSAUDIT_OPENAI_KEY", 1)
    config.write_text(body, encoding="utf-8", newline="\n")
    (root / "DETERMINISTIC_CHECKS.md").write_text(
        "# Deterministic checks\n\n```text\n" + describe_checks(GENERAL_CHECKS)
        + "\n```\n", encoding="utf-8", newline="\n")
    git_path = shutil.which("git")
    git_usable = False
    if git_path:
        try:
            tools_ready = True
            if sys.platform == "darwin" and git_path == "/usr/bin/git":
                tools_ready = subprocess.run(
                    ["/usr/bin/xcode-select", "-p"], capture_output=True,
                    timeout=5, check=False).returncode == 0
            if tools_ready:
                probe = subprocess.run([git_path, "--version"], capture_output=True,
                                       timeout=5, check=False)
                git_usable = probe.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    if git_usable:
        try:
            _git(root, "init", "-q", "-b", "main")
            _git(root, "add", "-A")
            subprocess.run(
                [git_path, "-c", "user.name=CrossAudit", "-c",
                 "user.email=app@crossaudit.local", "commit", "-q", "-m",
                 f"CrossAudit V{__version__} application controller"],
                cwd=root, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            # The app can still open its local recovery UI. Doctor will show
            # the exact Git failure and offer to initialize this ledger again.
            pass
    return root


def self_test() -> dict:
    """Exercise the frozen runtime without credentials or persistent writes.

    This is intentionally broader than ``--version``: release verification must
    prove that bundled document libraries import, both output formats round-trip,
    the controller can bootstrap, and the loopback UI enforces its session
    token. Everything lives in a temporary directory and no provider is called.
    """
    from .auditor.run import dcl_source_digest
    from .document_export import extract_document, render_docx, render_pdf
    from .providers.base import tls_context

    with tempfile.TemporaryDirectory(prefix="crossaudit-self-test-") as temporary:
        root = Path(temporary)
        project = _controller_project(root / "workspace")
        cfg = load(project / CONFIG_NAME)
        trusted_roots = len(tls_context().get_ca_certs())
        if not trusted_roots:
            raise RuntimeError("TLS trust store is empty")
        source = "# CrossAudit self-test\n\nEnglish and 中文 survive export.\n"
        formats = {}
        for suffix, renderer in (("pdf", render_pdf), ("docx", render_docx)):
            target = root / f"roundtrip.{suffix}"
            renderer(source, target)
            view = extract_document(target.name, target.read_bytes())
            if not view.valid or "CrossAudit self-test" not in view.text:
                raise RuntimeError(f"{suffix.upper()} round-trip validation failed")
            formats[suffix] = {"valid": True, "bytes": target.stat().st_size}

        url, httpd = serve(cfg, port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310
                authenticated = response.status == 200 and b"CrossAudit" in response.read()
            bare = url.split("?", 1)[0]
            try:
                urllib.request.urlopen(bare, timeout=5)  # nosec B310
            except urllib.error.HTTPError as exc:
                refused_without_token = exc.code == 403
            else:
                refused_without_token = False
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
            httpd.server_close()
            daemon.clear_run(cfg)
        if not authenticated or not refused_without_token:
            raise RuntimeError("loopback UI authentication self-test failed")
        deterministic_digest = dcl_source_digest()
        if len(deterministic_digest) != 64:
            raise RuntimeError("deterministic-layer identity is invalid")
        return {"ok": True, "version": __version__, "documents": formats,
                "dcl_source_sha256": deterministic_digest,
                "tls": {"trusted_certificate_authorities": trusted_roots},
                "loopback_token_enforced": True}


def _self_test_cli() -> int:
    try:
        print(json.dumps(self_test(), sort_keys=True), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 -- self-test contract is structured JSON
        print(json.dumps({"ok": False, "error": type(exc).__name__,
                          "detail": str(exc)[:300]}, sort_keys=True),
              file=sys.stderr, flush=True)
        return 1


def _display_path(path: Path) -> str:
    """Render a local path without exposing more of the home path than needed."""
    try:
        relative = path.relative_to(Path.home())
    except ValueError:
        return str(path)
    return "~" if not relative.parts else f"~/{relative.as_posix()}"


def _startup_step(operation, reason: str):
    """Translate an expected OS startup refusal at the entry boundary."""
    try:
        return operation()
    except OSError as exc:
        raise ConfigDenial(reason) from exc


def _run_app() -> int:
    os.environ["CROSSAUDIT_APP_MODE"] = "1"
    support = app_support()
    workspace = workspace_root(support)
    _startup_step(
        lambda: support.mkdir(parents=True, exist_ok=True, mode=0o700),
        "CrossAudit could not prepare its private application data in "
        f"{_display_path(support)} — grant access in System Settings › Privacy "
        "& Security › Files and Folders, then retry.")
    workspace_location = workspace if workspace.exists() else workspace.parent
    workspace_reason = (
        "CrossAudit could not create its workspace in "
        f"{_display_path(workspace_location)} — grant access in System Settings "
        "› Privacy & Security › Files and Folders, or choose another location.")
    _startup_step(
        lambda: workspace.mkdir(parents=True, exist_ok=True), workspace_reason)
    os.environ["CROSSAUDIT_APP_SUPPORT"] = str(support)
    os.environ["CROSSAUDIT_WORKSPACE_ROOT"] = str(workspace)
    _startup_step(
        load_into_environment,
        "CrossAudit could not read its saved connection settings — unlock the "
        "login Keychain and retry.")
    root = _startup_step(lambda: _controller_project(workspace), workspace_reason)
    cfg = _startup_step(lambda: load(root / CONFIG_NAME), workspace_reason)
    url, httpd = _startup_step(
        lambda: serve(cfg, port=0),
        "CrossAudit could not start its private local console — allow local "
        "connections and retry.")

    def stop(_signum=None, _frame=None) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("CROSSAUDIT_APP_URL=" + url + "#projects", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        httpd.server_close()
    return 0


def _parse_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigDenial(
            f"project-console port must be an integer, not {raw!r}") from exc
    if not 0 <= port <= 65535:
        raise ConfigDenial("project-console port must be between 0 and 65535")
    return port


def _dispatch(argv: list[str]) -> int:
    """Select one explicit frozen-core mode; arguments never imply app mode."""
    if not argv:
        return _run_app()
    if argv == ["--help"]:
        print(_CORE_USAGE, end="")
        return 0
    if argv == ["--version"]:
        print(f"CrossAudit {__version__}")
        return 0
    if argv[0] == "--self-test":
        return _self_test_cli()
    if argv[0] == "--project-console":
        if len(argv) not in (2, 3):
            raise ConfigDenial(
                "project-console requires DIRECTORY and an optional PORT")
        port = _parse_port(argv[2]) if len(argv) == 3 else 0
        return project_console(Path(argv[1]), port)
    raise ConfigDenial(
        "unrecognized CrossAuditCore arguments; use --help")


def _entry_boundary(operation) -> int:
    """Turn every frozen entry refusal into output plus a stable exit status."""
    try:
        return operation()
    except Denial as exc:
        print(f"DENIED ({exc.kind}): {exc.reason}", file=sys.stderr, flush=True)
        return exc.exit_code
    except KeyboardInterrupt:
        print("DENIED (config): CrossAudit startup was interrupted",
              file=sys.stderr, flush=True)
        return ConfigDenial.exit_code
    except Exception as exc:  # noqa: BLE001 -- nothing may escape the frozen boundary
        print(
            "DENIED (config): CrossAudit could not safely start the requested "
            f"mode ({type(exc).__name__}); use --self-test for runtime details",
            file=sys.stderr, flush=True)
        return ConfigDenial.exit_code


def main(argv: list[str] | None = None) -> int:
    """Run one explicit frozen-core mode without leaking an exception."""
    args = list(sys.argv[1:] if argv is None else argv)
    return _entry_boundary(lambda: _dispatch(args))


def project_console(root: Path, port: int = 0) -> int:
    """Bundled daemon entry used for independent per-project backgrounds."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ConfigDenial(
            f"project directory does not exist or is not a directory: {root}")
    config = root / CONFIG_NAME
    if not config.is_file():
        raise ConfigDenial(
            f"no {CONFIG_NAME} found in {root} — run `crossaudit init` there")
    os.environ["CROSSAUDIT_APP_MODE"] = "1"
    # CLI commands invoked by the shared console layer call config.load() from
    # the process working directory. Make the entrypoint self-contained rather
    # than relying on every parent launcher to remember cwd=project.
    os.chdir(root)
    load_into_environment()
    cfg = load(config)
    # E1: a per-project daemon starts detached (start_new_session=True) and never
    # receives the app's SIGTERM, so an infinite idle timeout let daemons pile up
    # unbounded after the app closed or a project stopped being viewed. A finite,
    # generous window lets an idle daemon self-retire, while a run in flight or a
    # live SSE client holds it open (server.idle_watch never reaps real work).
    _url, httpd = serve(cfg, port=port, register=True,
                        idle_timeout=PROJECT_IDLE_TIMEOUT_S)

    def stop(_signum=None, _frame=None) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        daemon.clear_run(cfg)
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
